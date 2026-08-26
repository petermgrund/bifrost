"""Configuration page"""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from ... import __version__
from ...core import health
from ...core import settings as ui_settings

router = APIRouter(prefix="/config", tags=["config"])
templates = Jinja2Templates(directory=Path(__file__).resolve().parents[1] / "templates")


@router.get("", response_class=HTMLResponse)
async def config_page(request: Request):
    return templates.TemplateResponse(request, "config.html", {})


@router.get("/api/status")
async def status(request: Request) -> dict:
    st = request.app.state
    return {
        "services": await health.probe_services(
            st.gramps, st.paperless, getattr(st, "immich_accounts", [])),
        "version": __version__,
        "config_path": str(st.cfg.config_path),
        "database": str(st.cfg.db_path),
    }


class ThemeBody(BaseModel):
    seed: str


def _theme(conn) -> dict:
    return {"seed": ui_settings.get_theme_seed(conn),
            "default": ui_settings.DEFAULT_THEME_SEED}


@router.get("/api/theme")
async def get_theme(request: Request) -> dict:
    return _theme(request.app.state.conn)


@router.post("/api/theme")
async def set_theme(request: Request, body: ThemeBody) -> dict:
    conn = request.app.state.conn
    try:
        ui_settings.set_theme_seed(conn, body.seed)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    return _theme(conn)
