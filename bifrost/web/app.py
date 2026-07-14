"""Bifrost"""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from .. import __version__
from ..core import db
from ..core.clients import GeminiClient, GrampsClient, ImmichClient, PaperlessClient
from ..core.clients.anthropic import AnthropicClient
from ..core.config import load_config

WEB_DIR = Path(__file__).parent
templates = Jinja2Templates(directory=WEB_DIR / "templates")


@asynccontextmanager
async def lifespan(app: FastAPI):
    cfg = load_config()
    app.state.cfg = cfg
    app.state.conn = db.connect(cfg.db_path)
    app.state.conn.execute("PRAGMA busy_timeout=5000")
    app.state.gramps = GrampsClient(cfg.gramps.base_url, cfg.gramps.username, cfg.gramps.password)
    app.state.paperless = PaperlessClient(cfg.paperless.base_url, cfg.paperless.api_token)
    app.state.anthropic = AnthropicClient(cfg.anthropic.api_key, cfg.anthropic.model)
    app.state.gemini = GeminiClient(cfg.gemini.api_key, cfg.gemini.model)
    # Optional — sync/immich/asset answers 503 when unconfigured.
    app.state.immich = (
        ImmichClient(cfg.immich.base_url, cfg.immich.api_key)
        if cfg.immich.base_url and cfg.immich.api_key
        else None
    )
    app.state.caches = {}
    yield
    await app.state.gramps.close()
    await app.state.paperless.close()
    await app.state.anthropic.close()
    await app.state.gemini.close()
    if app.state.immich is not None:
        await app.state.immich.close()
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
    resp.headers["Cache-Control"] = "no-cache"
    return resp


app.mount("/static", _NoCacheStatic(directory=WEB_DIR / "static"), name="static")

from .routes.citations import router as citations_router  # noqa: E402
from .runs import ACTIVE  # noqa: E402
from .routes.places import router as places_router  # noqa: E402
from .routes.reprocess import router as reprocess_router  # noqa: E402
from .routes.style import router as style_router  # noqa: E402
from .routes.sync import router as sync_router  # noqa: E402
from .routes.transcribe import router as transcribe_router  # noqa: E402

app.include_router(citations_router)
app.include_router(places_router)
app.include_router(reprocess_router)
app.include_router(style_router)
app.include_router(sync_router)
app.include_router(transcribe_router)


@app.get("/healthz")
async def healthz() -> dict:
    return {"status": "ok", "version": __version__}


@app.get("/api/runs/active")
async def runs_active() -> dict:
    """Live done/total of in-flight runs — the UI polls this during long jobs."""
    return {"runs": list(ACTIVE.values())}


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse(request, "index.html", {"version": __version__})
