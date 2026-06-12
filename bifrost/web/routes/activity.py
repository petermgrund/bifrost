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
async def weekly(request: Request, refresh: bool = False):
    st = request.app.state
    # the payload-bearing history fetch is a few MB — cache the computed result
    if st.caches.get("activity") is None or refresh:
        st.caches["activity"] = await activity.dashboard(st.gramps)
    return st.caches["activity"]
