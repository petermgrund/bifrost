"""Bifrost"""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from .. import __version__
from ..core import db
from ..core.clients import GeminiClient, GrampsClient, ImmichClient, PaperlessClient
from ..core.clients.anthropic import AnthropicClient
from ..core.clients.immich import ImmichError
from ..core.config import load_config
from ..modules import citations as citations_mod
from ..modules import faces as faces_mod

WEB_DIR = Path(__file__).parent
templates = Jinja2Templates(directory=WEB_DIR / "templates")


@asynccontextmanager
async def lifespan(app: FastAPI):
    cfg = load_config()
    app.state.cfg = cfg
    citations_mod.configure_house_style(cfg.citations.house_style_path)
    app.state.conn = db.connect(cfg.db_path)
    app.state.conn.execute("PRAGMA busy_timeout=5000")
    faces_mod.import_person_map_yaml(app.state.conn, cfg.sync_immich.person_map_path)
    app.state.gramps = GrampsClient(cfg.gramps.base_url, cfg.gramps.username, cfg.gramps.password)
    app.state.paperless = PaperlessClient(cfg.paperless.base_url, cfg.paperless.api_token)
    app.state.anthropic = AnthropicClient(cfg.anthropic.api_key, cfg.anthropic.model)
    app.state.gemini = GeminiClient(cfg.gemini.api_key, cfg.gemini.model)
    # Immich sync endpoints answer 503 with no accounts configured
    app.state.immich_accounts = []
    if cfg.immich.base_url:
        for acct in cfg.immich.accounts:
            client = ImmichClient(cfg.immich.base_url, acct.api_key)
            client.label = acct.label
            app.state.immich_accounts.append(client)
    app.state.caches = {}
    yield
    await app.state.gramps.close()
    await app.state.paperless.close()
    await app.state.anthropic.close()
    await app.state.gemini.close()
    for client in app.state.immich_accounts:
        await client.close()
    app.state.conn.close()


class _NoCacheStatic(StaticFiles):
    def file_response(self, *args, **kwargs):
        resp = super().file_response(*args, **kwargs)
        resp.headers["Cache-Control"] = "no-cache"
        return resp


app = FastAPI(title="Bifrost", version=__version__, lifespan=lifespan)


@app.middleware("http")
async def _no_cache(request: Request, call_next):
    resp = await call_next(request)
    resp.headers.setdefault("Cache-Control", "no-cache")
    return resp


@app.exception_handler(ImmichError)
async def _immich_error(_request: Request, exc: ImmichError):
    if 400 <= exc.status < 500 and exc.status not in (401, 403):
        status = exc.status
    else:
        status = 502
    return JSONResponse(status_code=status, content={"detail": str(exc)})


app.mount("/static", _NoCacheStatic(directory=WEB_DIR / "static"), name="static")

from .routes.citations import router as citations_router  # noqa: E402
from .runs import ACTIVE  # noqa: E402
from .routes.faces import router as faces_router  # noqa: E402
from .routes.places import router as places_router  # noqa: E402
from .routes.reprocess import router as reprocess_router  # noqa: E402
from .routes.style import router as style_router  # noqa: E402
from .routes.settings import router as settings_router  # noqa: E402
from .routes.sync import router as sync_router  # noqa: E402
from .routes.transcribe import router as transcribe_router  # noqa: E402

app.include_router(citations_router)
app.include_router(faces_router)
app.include_router(places_router)
app.include_router(reprocess_router)
app.include_router(style_router)
app.include_router(settings_router)
app.include_router(sync_router)
app.include_router(transcribe_router)


@app.get("/healthz")
async def healthz() -> dict:
    return {"status": "ok", "version": __version__}


@app.get("/api/runs/active")
async def runs_active() -> dict:
    """live done/total  in-flight runs"""
    return {"runs": list(ACTIVE.values())}


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse(request, "index.html", {"version": __version__})
