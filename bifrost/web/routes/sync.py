"""Sync page + API. Preview and apply are the same generator (apply flag)."""

from __future__ import annotations

from fastapi import APIRouter, Request

from ...modules import sync_immich
from ..runs import record_run

router = APIRouter(prefix="/sync", tags=["sync"])


def _state(request: Request):
    return request.app.state


@router.get("")
async def sync_page(request: Request):
    from ..app import templates  # late import to avoid cycle

    return templates.TemplateResponse(request, "sync.html", {})


@router.post("/api/immich/preview")
async def immich_preview(request: Request):
    st = _state(request)
    gen = sync_immich.sync(st.gramps, st.immich, st.conn, st.cfg.sync_immich, apply=False)
    run_id, events = await record_run(st.conn, "sync.immich.preview", gen)
    return {"run_id": run_id, "apply": False, "events": [e.__dict__ for e in events]}


@router.post("/api/immich/apply")
async def immich_apply(request: Request):
    st = _state(request)
    gen = sync_immich.sync(st.gramps, st.immich, st.conn, st.cfg.sync_immich, apply=True)
    run_id, events = await record_run(st.conn, "sync.immich", gen)
    # Media and faces changed — every cached view is stale.
    st.caches.clear()
    return {"run_id": run_id, "apply": True, "events": [e.__dict__ for e in events]}
