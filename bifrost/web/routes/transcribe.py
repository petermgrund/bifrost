"""Transcribe page — Gemini OCR + transcription-note maintenance. The actual
work runs through the existing /sync/api/* endpoints; this only serves the page."""

from __future__ import annotations

from fastapi import APIRouter, Request

router = APIRouter(prefix="/transcribe", tags=["transcribe"])


@router.get("")
async def transcribe_page(request: Request):
    from ..app import templates  # late import to avoid cycle

    return templates.TemplateResponse(request, "transcribe.html", {})
