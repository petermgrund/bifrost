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
from ..core.clients import GeminiClient, GrampsClient, PaperlessClient
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
    app.state.paperless = PaperlessClient(cfg.paperless.base_url, cfg.paperless.api_token)
    app.state.anthropic = AnthropicClient(cfg.anthropic.api_key, cfg.anthropic.model)
    app.state.gemini = GeminiClient(cfg.gemini.api_key, cfg.gemini.model)
    app.state.caches = {}
    yield
    await app.state.gramps.close()
    await app.state.paperless.close()
    await app.state.anthropic.close()
    await app.state.gemini.close()
    app.state.conn.close()


class _NoCacheStatic(StaticFiles):
    """Serve static with Cache-Control: no-cache so the browser always
    revalidates (via ETag). With the dev bind-mount, edited CSS/JS then show on
    a plain refresh — no stale-cache confusion, no per-file version query."""

    def file_response(self, *args, **kwargs):
        resp = super().file_response(*args, **kwargs)
        resp.headers["Cache-Control"] = "no-cache"
        return resp


app = FastAPI(title="Bifrost", version=__version__, lifespan=lifespan)


@app.middleware("http")
async def _no_cache(request: Request, call_next):
    """Single-user app: never let the browser serve a stale page or asset.
    Mark every response no-cache so it always revalidates (ETag) — kills the
    stale-HTML/stale-CSS caching that made UI edits appear not to take."""
    resp = await call_next(request)
    resp.headers["Cache-Control"] = "no-cache"
    return resp


app.mount("/static", _NoCacheStatic(directory=WEB_DIR / "static"), name="static")

from .routes.citations import router as citations_router  # noqa: E402
from .routes.idgen import router as idgen_router  # noqa: E402
from .routes.places import router as places_router  # noqa: E402
from .routes.sync import router as sync_router  # noqa: E402
from .routes.transcribe import router as transcribe_router  # noqa: E402

app.include_router(citations_router)
app.include_router(idgen_router)
app.include_router(places_router)
app.include_router(sync_router)
app.include_router(transcribe_router)


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
            st.gramps, st.paperless, st.conn, st.cfg)
    data = dict(st.caches["inbox"])
    rows = st.conn.execute(
        "SELECT id, job, status, started_at, summary FROM runs ORDER BY id DESC LIMIT 8"
    ).fetchall()
    data["runs"] = [dict(r) for r in rows]
    return data


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse(request, "index.html", {"version": __version__})
