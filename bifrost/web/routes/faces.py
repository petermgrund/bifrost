"""Faces page + API"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse, Response
from pydantic import BaseModel

from ...core.clients.gramps import person_display_name
from ...core.clients.immich import ImmichError
from ...modules import faces, sync_immich
from ..runs import record_run

router = APIRouter(prefix="/faces", tags=["faces"])


def _state(request: Request):
    return request.app.state


def _accounts(request: Request) -> list:
    accounts = getattr(_state(request), "immich_accounts", [])
    if not accounts:
        raise HTTPException(503, "Immich is not configured")
    return accounts


@router.get("")
async def faces_page(request: Request):
    return RedirectResponse(url="/#faces")


@router.get("/api/gramps-people")
async def gramps_people(request: Request, refresh: bool = False):
    st = _state(request)
    if st.caches.get("faces_gramps_people") is None or refresh:
        raw = await st.gramps.list_people()
        st.caches["faces_gramps_people"] = sorted(
            ({
                "handle": p["handle"],
                "name": person_display_name(p),
                "gramps_id": p.get("gramps_id", ""),
                "media_count": len(p.get("media_list") or []),
                "rect_count": sum(1 for mr in p.get("media_list") or []
                                  if mr.get("rect")),
            } for p in raw),
            key=lambda r: r["name"].lower())
    return st.caches["faces_gramps_people"]


@router.get("/api/immich-people")
async def immich_people(request: Request, refresh: bool = False):
    st = _state(request)
    accounts = _accounts(request)
    if st.caches.get("faces_immich_people") is None or refresh:
        st.caches["faces_immich_people"] = await faces.merged_people(accounts)
    return st.caches["faces_immich_people"]


@router.get("/api/person-thumbnail/{person_id}")
async def person_thumbnail(request: Request, person_id: str):
    try:
        content, mime = await faces.person_thumbnail_bytes(
            _accounts(request), _state(request).conn, person_id)
    except ImmichError as exc:
        raise HTTPException(404 if exc.status in (400, 404) else 502, exc.message)
    return Response(content, media_type=mime,
                    headers={"Cache-Control": "public, max-age=3600"})


async def _links_payload(request: Request) -> dict:
    st = _state(request)
    accounts = _accounts(request)
    return {
        "gramps_url": st.cfg.sync_paperless.gramps_public_url,
        "accounts": [getattr(c, "label", "") for c in accounts],
        "faces": await faces.grouped_links(accounts, st.conn),
    }


@router.get("/api/links")
async def get_links(request: Request):
    return await _links_payload(request)


class LinkBody(BaseModel):
    gramps_handle: str
    immich_person_id: str
    label: str = ""


@router.post("/api/links")
async def create_link(request: Request, body: LinkBody):
    st = _state(request)
    if not body.gramps_handle.strip() or not body.immich_person_id.strip():
        raise HTTPException(400, "gramps_handle and immich_person_id required")
    accounts = _accounts(request)
    handle = body.gramps_handle.strip()
    person_id = body.immich_person_id.strip()
    info = None
    hard: ImmichError | None = None
    for client in accounts:
        try:
            person = await client.get_person(person_id)
        except ImmichError as exc:
            if exc.status not in (400, 404):
                hard = hard or exc
            continue
        try:
            uid = await sync_immich._user_id(client)
        except ImmichError as exc:
            hard = hard or exc
            continue
        info = {"owner_user_id": uid,
                "account_label": getattr(client, "label", "")}
        break
    if info is None:
        if hard is not None:
            # an account was unreachable but does it exist?
            raise HTTPException(502, f"could not verify the person id: {hard.message}")
        raise HTTPException(404, "no configured Immich account knows this person id")
    for row in st.conn.execute(
            "SELECT immich_person_id FROM person_links "
            "WHERE gramps_handle=? AND owner_user_id IS NULL", (handle,)).fetchall():
        old = await faces.resolve_person(accounts, row["immich_person_id"])
        if old is not None:
            with st.conn:
                st.conn.execute(
                    "UPDATE person_links SET owner_user_id=? "
                    "WHERE gramps_handle=? AND immich_person_id=?",
                    (old["owner_user_id"], handle, row["immich_person_id"]))
    faces.set_link(st.conn, handle, person_id,
                   body.label, owner_user_id=info["owner_user_id"])
    return await _links_payload(request)


@router.delete("/api/links/{gramps_handle}")
async def remove_link(request: Request, gramps_handle: str):
    st = _state(request)
    if not faces.delete_link(st.conn, gramps_handle):
        raise HTTPException(404, "no link for this person")
    return await _links_payload(request)


class BackfillBody(BaseModel):
    selected: list[str] | None = None

@router.get("/api/backfill/config")
async def backfill_config(request: Request) -> dict:
    return {"enabled": bool(getattr(_state(request), "immich_accounts", []))}


@router.post("/api/backfill/preview")
async def backfill_preview(request: Request, body: BackfillBody = BackfillBody()):
    st = _state(request)
    gen = faces.apply_links(st.gramps, _accounts(request), st.conn, apply=False)
    run_id, events = await record_run(st.conn, "faces.backfill.preview", gen)
    return {"run_id": run_id, "apply": False, "events": [e.__dict__ for e in events]}


@router.post("/api/backfill/apply")
async def backfill_apply(request: Request, body: BackfillBody = BackfillBody()):
    st = _state(request)
    gen = faces.apply_links(
        st.gramps, _accounts(request), st.conn, apply=True,
        selected=set(body.selected) if body.selected is not None else None)
    run_id, events = await record_run(st.conn, "faces.backfill", gen)
    st.caches.clear()
    return {"run_id": run_id, "apply": True, "events": [e.__dict__ for e in events]}
