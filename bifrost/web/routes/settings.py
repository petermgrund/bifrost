"""Whether the configured services answer"""

from __future__ import annotations

from fastapi import APIRouter, Request

from ... import __version__
from ...core import health

router = APIRouter(prefix="/config", tags=["config"])


@router.get("/api/status")
async def status(request: Request) -> dict:
    st = request.app.state
    return {
        "services": await health.probe_services(
            st.gramps, st.paperless, getattr(st, "immich_accounts", []),
            getattr(st, "gemini", None), st.cfg.sync_paperless.ocr_tag),
        "version": __version__,
        "config_path": str(st.cfg.config_path),
    }
