"""Image-version management API (the VERSIONS strip — docs/IMMICH_VERSIONING.md).

Bifrost is the cockpit; the durable state (stack membership, primaryAssetId, the
Gramps/Role tags) lives in Immich. Reads merge the live stack with Bifrost's
role/label/seq cache; writes go to Immich + the cache. Promotion reuses
set_stack_primary + the versions_only sync (which repoints Gramps).
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from ...modules import sync_immich
from ..runs import record_run

router = APIRouter(prefix="/versions", tags=["versions"])


def _state(request: Request):
    return request.app.state


@router.get("/api/by-asset/{asset_id}")
async def version_set(request: Request, asset_id: str):
    """The version set for the photo currently displayed as `asset_id`."""
    st = _state(request)
    return await sync_immich.version_set(
        st.immich, st.gramps, st.conn, st.cfg.sync_immich, asset_id)


class SetDisplayedBody(BaseModel):
    stack_id: str
    member_id: str


@router.post("/api/set-displayed")
async def set_displayed(request: Request, body: SetDisplayedBody):
    """Promote a member to the displayed version, then repoint Gramps to it."""
    st = _state(request)
    await st.immich.set_stack_primary(body.stack_id, body.member_id)
    gen = sync_immich.sync(st.gramps, st.immich, st.conn, st.cfg.sync_immich,
                           apply=True, versions_only=True)
    run_id, events = await record_run(st.conn, "sync.immich.versions", gen)
    st.caches.clear()  # media/faces changed
    return {"run_id": run_id, "events": [e.__dict__ for e in events]}


class SetRoleBody(BaseModel):
    gramps_id: str
    asset_id: str
    role: str | None = None  # original|ai|crop|duplicate|verso, or null to clear


@router.post("/api/set-role")
async def set_role(request: Request, body: SetRoleBody):
    st = _state(request)
    try:
        return await sync_immich.set_role(
            st.immich, st.conn, body.gramps_id, body.asset_id, body.role)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


class SetLabelBody(BaseModel):
    gramps_id: str
    asset_id: str
    label: str | None = None


@router.post("/api/set-label")
async def set_label(request: Request, body: SetLabelBody):
    st = _state(request)
    return sync_immich.set_label(st.conn, body.gramps_id, body.asset_id, body.label)


class AdoptBody(BaseModel):
    gramps_id: str
    displayed_asset_id: str
    add_asset_ids: list[str]


@router.post("/api/adopt")
async def adopt(request: Request, body: AdoptBody):
    """Fold already-uploaded asset(s) into a stack with the synced photo."""
    st = _state(request)
    try:
        result = await sync_immich.adopt(
            st.immich, st.conn, st.cfg.sync_immich,
            body.gramps_id, body.displayed_asset_id, body.add_asset_ids)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    st.caches.clear()
    return result
