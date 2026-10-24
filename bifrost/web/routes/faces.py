"""Faces page + API"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse, Response
from pydantic import BaseModel

from ...core.clients.immich import ImmichError
from ...modules import faces
from ..runs import record_run

router = APIRouter(prefix="/faces", tags=["faces"])
PEOPLE_KEY = "faces_gramps_people"


def _state(request: Request):
    return request.app.state


def _accounts(request: Request) -> list:
    accounts = getattr(_state(request), "immich_accounts", [])
    if not accounts:
        raise HTTPException(503, "Immich is not configured")
    return accounts


def _forget_people(st) -> None:
    st.caches.pop(PEOPLE_KEY, None)
    st.caches.pop("person_links", None)


async def _people(request: Request, refresh: bool = False) -> list[dict]:
    st = _state(request)
    if st.caches.get(PEOPLE_KEY) is None or refresh:
        try:
            st.caches[PEOPLE_KEY] = faces.people_index(await st.gramps.list_people())
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(502, f"Gramps could not be read: {str(exc)[:200]}")
    return st.caches[PEOPLE_KEY]


@router.get("")
async def faces_page(request: Request):
    return RedirectResponse(url="/photos#/faces")


@router.get("/api/gramps-people")
async def gramps_people(request: Request, refresh: bool = False):
    return await _people(request, refresh)


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
        content, mime = await faces.person_thumbnail_bytes(_accounts(request), person_id)
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
        "faces": await faces.grouped_links(accounts, await _people(request)),
    }


@router.get("/api/links")
async def get_links(request: Request):
    return await _links_payload(request)


class LinkBody(BaseModel):
    gramps_handle: str
    immich_person_id: str


@router.post("/api/links")
async def create_link(request: Request, body: LinkBody):
    st = _state(request)
    handle = body.gramps_handle.strip()
    person_id = body.immich_person_id.strip()
    if not handle or not person_id:
        raise HTTPException(400, "gramps_handle and immich_person_id required")
    accounts = _accounts(request)
    known = False
    hard: ImmichError | None = None
    for client in accounts:
        try:
            await client.get_person(person_id)
        except ImmichError as exc:
            if exc.status not in (400, 404):
                hard = hard or exc
            continue
        known = True
        break
    if not known:
        if hard is not None:
            raise HTTPException(502, f"could not verify the person id: {hard.message}")
        raise HTTPException(404, "no configured Immich account knows this person id")
    linked = {pid: p["handle"] for p in await _people(request) for pid in p["immich_ids"]}
    await faces.set_link(st.gramps, linked, handle, person_id)
    _forget_people(st)
    return await _links_payload(request)


@router.delete("/api/links/{gramps_handle}")
async def remove_link(request: Request, gramps_handle: str):
    st = _state(request)
    if not await faces.delete_link(st.gramps, gramps_handle):
        raise HTTPException(404, "no link for this person")
    _forget_people(st)
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
