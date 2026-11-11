"""Configuration page"""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from ... import __version__
from ...core import health

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
    }
