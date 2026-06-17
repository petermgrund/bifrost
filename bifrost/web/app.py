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
from ..core.clients import GeminiClient, GrampsClient, ImmichClient, PaperlessClient
from ..core.clients.anthropic import AnthropicClient
from ..core.config import load_config
from ..modules import inbox as inbox_mod

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
    app.state.anthropic = AnthropicClient(cfg.anthropic.api_key, cfg.anthropic.model)
    app.state.gemini = GeminiClient(cfg.gemini.api_key, cfg.gemini.model)
    app.state.caches = {}
    yield
    await app.state.gramps.close()
    await app.state.immich.close()
    await app.state.paperless.close()
    await app.state.anthropic.close()
    await app.state.gemini.close()
    app.state.conn.close()


app = FastAPI(title="Bifrost", version=__version__, lifespan=lifespan)
app.mount("/static", StaticFiles(directory=WEB_DIR / "static"), name="static")

from .routes.activity import router as activity_router  # noqa: E402
from .routes.citations import router as citations_router  # noqa: E402
from .routes.faces import router as faces_router  # noqa: E402
from .routes.idgen import router as idgen_router  # noqa: E402
from .routes.places import router as places_router  # noqa: E402
from .routes.sync import router as sync_router  # noqa: E402

app.include_router(activity_router)
app.include_router(citations_router)
app.include_router(faces_router)
app.include_router(idgen_router)
app.include_router(places_router)
app.include_router(sync_router)


@app.get("/healthz")
async def healthz() -> dict:
    return {"status": "ok", "version": __version__}


@app.get("/api/runs")
async def recent_runs(request: Request, limit: int = 10):
    rows = request.app.state.conn.execute(
        "SELECT id, job, status, started_at, finished_at, summary"
        " FROM runs ORDER BY id DESC LIMIT ?",
        (min(limit, 50),),
    ).fetchall()
    return [dict(r) for r in rows]


@app.get("/api/inbox")
async def inbox(request: Request, refresh: bool = False):
    """One tolerant call for the home page: pending work, snapshot, recent runs."""
    st = request.app.state
    if st.caches.get("inbox") is None or refresh:
        st.caches["inbox"] = await inbox_mod.gather(
            st.gramps, st.immich, st.paperless, st.conn, st.cfg)
    data = dict(st.caches["inbox"])
    rows = st.conn.execute(
        "SELECT id, job, status, started_at, summary FROM runs ORDER BY id DESC LIMIT 8"
    ).fetchall()
    data["runs"] = [dict(r) for r in rows]
    return data


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse(request, "index.html", {"version": __version__})
