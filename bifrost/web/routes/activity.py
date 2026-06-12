"""Activity page + API."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from ...core.clients.anthropic import AnthropicError
from ...modules import activity

router = APIRouter(prefix="/activity", tags=["activity"])


@router.get("")
async def activity_page(request: Request):
    from ..app import templates  # late import to avoid cycle

    return templates.TemplateResponse(request, "activity.html", {})


@router.get("/api/weekly")
async def weekly(request: Request, refresh: bool = False):
    st = request.app.state
    # the payload-bearing history fetch is a few MB — cache the computed result;
    # a cached result from a previous week is stale (this_week moved on)
    cached = st.caches.get("activity")
    stale = cached is None or cached["this_week"]["week"] != activity.current_week()
    if stale or refresh:
        cached = st.caches["activity"] = await activity.dashboard(st.gramps)
    return {**cached, "gramps_url": st.cfg.sync_paperless.gramps_public_url,
            "llm": st.anthropic.configured}


@router.post("/api/interpret")
async def interpret(request: Request, refresh: bool = False):
    st = request.app.state
    if not st.anthropic.configured:
        raise HTTPException(503, "no Anthropic API key configured")
    if st.caches.get("activity") is None:
        st.caches["activity"] = await activity.dashboard(st.gramps)
    dash = st.caches["activity"]
    week = dash["this_week"]["week"]
    key = f"activity_interp:{week}"
    if st.caches.get(key) is None or refresh:
        try:
            st.caches[key] = await st.anthropic.complete_text(
                activity.INTERPRET_SYSTEM, activity.interpret_prompt(dash))
        except AnthropicError as exc:
            raise HTTPException(502, str(exc)) from exc
    return {"text": st.caches[key]}
