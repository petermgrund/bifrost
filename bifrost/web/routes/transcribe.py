"""Transcribe page — Gemini OCR + transcription-note maintenance. The actual
work runs through the existing /sync/api/* endpoints; this only serves the page."""

from __future__ import annotations

import yaml
from fastapi import APIRouter, Request

router = APIRouter(prefix="/transcribe", tags=["transcribe"])


@router.get("")
async def transcribe_page(request: Request):
    from ..app import templates  # late import to avoid cycle

    return templates.TemplateResponse(request, "transcribe.html", {})


@router.get("/api/config")
async def transcribe_config(request: Request):
    """Read-only config for the Transcribe Settings tab (model, OCR tag,
    house-style master, Gramps link)."""
    cfg = request.app.state.cfg
    # house_style_path isn't on the dataclass — read it from the raw YAML.
    house_style = ""
    try:
        raw = yaml.safe_load(cfg.config_path.read_text()) or {}
        house_style = ((raw.get("sync") or {}).get("paperless") or {}).get("house_style_path") or ""
    except Exception:
        pass
    return {
        "model": cfg.gemini.model,
        "ocr_tag": cfg.sync_paperless.ocr_tag,
        "house_style_path": house_style,
        "gramps_public_url": cfg.sync_paperless.gramps_public_url,
    }
