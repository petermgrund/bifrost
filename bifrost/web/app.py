"""Bifrost web app."""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from .. import __version__
from ..core import db
from ..core.clients import GrampsClient, ImmichClient, PaperlessClient
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
    app.state.immich = ImmichClient(cfg.immich.base_url, cfg.immich.api_key)
    app.state.paperless = PaperlessClient(cfg.paperless.base_url, cfg.paperless.api_token)
    app.state.caches = {}
    yield
    await app.state.gramps.close()
    await app.state.immich.close()
    await app.state.paperless.close()
    app.state.conn.close()


app = FastAPI(title="Bifrost", version=__version__, lifespan=lifespan)
app.mount("/static", StaticFiles(directory=WEB_DIR / "static"), name="static")

from .routes.faces import router as faces_router  # noqa: E402

app.include_router(faces_router)


@app.get("/healthz")
async def healthz() -> dict:
    return {"status": "ok", "version": __version__}


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse(request, "index.html", {"version": __version__})
