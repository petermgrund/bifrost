"""Activity page + API."""

from __future__ import annotations

from fastapi import APIRouter, Request

from ...modules import activity

router = APIRouter(prefix="/activity", tags=["activity"])


@router.get("")
async def activity_page(request: Request):
    from ..app import templates  # late import to avoid cycle

    return templates.TemplateResponse(request, "activity.html", {})


@router.get("/api/weekly")
async def weekly(request: Request):
    return await activity.weekly(request.app.state.gramps)
