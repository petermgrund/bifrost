"""Read-only API v1: pinpoints, PIDs, codes and an export of what only Bifrost holds"""

from __future__ import annotations

import asyncio
import logging
from datetime import date

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse

from ...modules import api, codes, tables
from .codes import _urls

router = APIRouter(prefix="/api/v1", tags=["api v1"])
log = logging.getLogger("bifrost.api")


def _state(request: Request):
    return request.app.state


def _base(request: Request) -> str:
    return str(request.base_url).rstrip("/")


async def _people(st, handles: list[str]) -> dict[str, dict]:
    """Gramps summaries by handle; none when Gramps can't be read"""
    if not handles:
        return {}
    try:
        return {p["handle"]: p for p in await tables.person_summaries(st.gramps, handles)}
    except Exception as exc:  # noqa: BLE001
        log.warning("api: Gramps people unavailable: %s", exc)
        return {}


async def _doc_id(st, pid: str) -> int:
    doc_id = await tables.find_doc(st.paperless, st.conn, st.cfg.sync_paperless.gramps_id_field_id, pid)
    if doc_id is None:
        raise HTTPException(404, f"no Paperless document has the PID {pid}")
    return doc_id


def _links(request: Request, st, doc_id: int, pid: str) -> dict:
    cfg = st.cfg.sync_paperless
    gramps = cfg.gramps_public_url or st.cfg.sync_immich.gramps_public_url
    return {
        "bifrost": f"{_base(request)}/tables/{doc_id}",
        "paperless": f"{cfg.public_url}/documents/{doc_id}/details" if cfg.public_url else None,
        "gramps": f"{gramps}/media/{pid}" if gramps and pid else None,
        "code": f"{_base(request)}/api/v1/code/{pid}" if pid else None,
    }


@router.get("/pinpoint/{pinpoint}")
async def get_pinpoint(request: Request, pinpoint: str) -> dict:
    """The cells a pinpoint points at, with their values, people and place on the page, or the note it names"""
    st = _state(request)
    pin = tables.parse_pinpoint(pinpoint)
    if pin is None:
        raise HTTPException(404, f"'{pinpoint}' is not a pinpoint")
    doc_id = await _doc_id(st, pin["code"])
    links = {"pid": f"{_base(request)}/api/v1/pid/{pin['code']}"}
    if pin["note"]:
        note = tables.note_by_no(st.conn, doc_id, pin["note"])
        if note is None:
            raise HTTPException(404, f"{pin['code']} has no note {pin['note']}")
        out = api.note_pinpoint(pin, doc_id, api.doc_title(st.conn, doc_id), note)
        return {**out, "links": {"bifrost": f"{_base(request)}/tables/{doc_id}?page={note['page']}#N{note['no']}",
                                 **links}}
    saved = tables.get_table(st.conn, doc_id, pin["page"])
    if saved is None:
        raise HTTPException(404, f"{pin['code']} has no table on page {pin['page']}")
    grid = saved["grid"]
    try:
        rows, cols = api.select(grid, pin)
    except api.NotFound as exc:
        raise HTTPException(404, str(exc)) from exc
    out = api.pinpoint(pin, doc_id, api.doc_title(st.conn, doc_id), grid, rows, cols,
                       await _people(st, api.handles(grid, rows, cols)))
    frag = tables.pinpoint_fragment(pin)
    return {**out, "links": {"bifrost": f"{_base(request)}/tables/{doc_id}?page={pin['page']}"
                                        + (f"#{frag}" if frag else ""), **links}}


@router.get("/pid/{pid}")
async def get_pid(request: Request, pid: str) -> dict:
    """A document's tables and page notes, by its PID"""
    st = _state(request)
    code = codes.normalize(pid)
    if not code:
        raise HTTPException(404, f"'{pid}' is not a PID")
    doc_id = await _doc_id(st, code)
    linked = [h for grid in api.grids(st.conn, doc_id).values() for h in api.handles(grid)]
    out = api.document(st.conn, doc_id, code, await _people(st, list(dict.fromkeys(linked))))
    return {**out, "links": _links(request, st, doc_id, code)}


@router.get("/code/{code}")
async def get_code(request: Request, code: str) -> dict:
    """A code's entry in the Codes ledger"""
    st = _state(request)
    wanted = codes.normalize(code)
    try:
        media = await st.gramps.get_media_by_gramps_id(wanted) if wanted else None
        live = {wanted} if media else set()
    except Exception as exc:  # noqa: BLE001
        log.warning("api: Gramps media unavailable: %s", exc)
        media, live = None, None
    titles = {wanted: media["desc"]} if media and media.get("desc") else {}
    found = codes.rows(st.conn, live, _urls(st.cfg), only=[wanted], titles=titles) if wanted else []
    if not found or not api.known(found[0]):
        raise HTTPException(404, f"{wanted or code} isn't in Bifrost's ledger")
    return api.code(found[0], api.children(st.conn))


@router.get("/export")
async def get_export(request: Request) -> JSONResponse:
    """Everything only Bifrost holds, as one JSON file"""
    st = _state(request)
    field = st.cfg.sync_paperless.gramps_id_field_id

    async def pids() -> dict[int, str]:
        ids = set(api.doc_ids(st.conn))
        if not ids or not field:
            return {}
        try:
            values = await st.paperless.custom_field_values(field, ids=ids)
        except Exception as exc:  # noqa: BLE001
            log.warning("api: Paperless PIDs unavailable: %s", exc)
            return {}
        return {d: codes.normalize(str(v)) for d, v in values.items() if v}

    async def titles() -> dict[str, str] | None:
        try:
            return await st.gramps.media_descriptions()
        except Exception as exc:  # noqa: BLE001
            log.warning("api: Gramps media unavailable: %s", exc)
            return None

    by_doc, media = await asyncio.gather(pids(), titles())
    rows = codes.rows(st.conn, None if media is None else set(media), _urls(st.cfg), titles=media)
    name = f"bifrost-export-{date.today().isoformat()}.json"
    return JSONResponse(api.export(st.conn, by_doc, rows),
                        headers={"Content-Disposition": f'attachment; filename="{name}"'})
