"""Bifrost"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from .. import __version__
from ..core.clients import GeminiClient, GrampsClient, ImmichClient, PaperlessClient
from ..core.clients.immich import ImmichError
from ..core.config import load_config

WEB_DIR = Path(__file__).parent
templates = Jinja2Templates(directory=WEB_DIR / "templates")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logging.basicConfig(format="%(levelname)s: %(name)s: %(message)s")
    logging.getLogger("bifrost").setLevel(logging.INFO)
    cfg = load_config()
    app.state.cfg = cfg
    app.state.gramps = GrampsClient(cfg.gramps.base_url, cfg.gramps.username, cfg.gramps.password)
    app.state.paperless = (PaperlessClient(cfg.paperless.base_url, cfg.paperless.api_token)
                           if cfg.paperless.base_url else None)
    app.state.gemini = GeminiClient(cfg.gemini.api_key, cfg.gemini.model)
    app.state.immich_accounts = []
    if cfg.immich.base_url:
        for acct in cfg.immich.accounts:
            client = ImmichClient(cfg.immich.base_url, acct.api_key)
            client.label = acct.label
            app.state.immich_accounts.append(client)
    app.state.caches = {}
    yield
    await app.state.gramps.close()
    if app.state.paperless is not None:
        await app.state.paperless.close()
    await app.state.gemini.close()
    for client in app.state.immich_accounts:
        await client.close()


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

from .routes.media import router as media_router  # noqa: E402
from .runs import ACTIVE  # noqa: E402
from .routes.faces import router as faces_router  # noqa: E402
from .routes.photos import router as photos_router  # noqa: E402
from .routes.settings import router as settings_router  # noqa: E402
from .routes.sync import router as sync_router  # noqa: E402

app.include_router(media_router)
app.include_router(faces_router)
app.include_router(photos_router)
app.include_router(settings_router)
app.include_router(sync_router)


@app.get("/healthz")
async def healthz() -> dict:
    return {"status": "ok", "version": __version__}


@app.get("/api/runs/active")
async def runs_active() -> dict:
    """live done/total  in-flight runs"""
    return {"runs": list(ACTIVE.values())}


@app.get("/api/config")
async def config(request: Request) -> dict:
    """What the page needs to know before it asks for anything else"""
    st = request.app.state
    accounts = getattr(st, "immich_accounts", [])
    return {
        "version": __version__,
        "codes": st.cfg.codes,
        "immich": bool(accounts),
        "accounts": [getattr(c, "label", "") for c in accounts],
        "paperless": st.paperless is not None,
        "ocr": st.paperless is not None and bool(st.cfg.sync_paperless.ocr_tag),
    }


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse(request, "index.html", {})
