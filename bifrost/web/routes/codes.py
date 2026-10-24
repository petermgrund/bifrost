"""Codes page + API: mint, claim, withdraw and reconcile GDA codes"""

from __future__ import annotations

import asyncio
import logging
from datetime import date

from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import RedirectResponse
from pydantic import BaseModel

from ...core.clients.gramps import GrampsError
from ...modules import codes, reconcile
from ..runs import record_run

router = APIRouter(prefix="/codes", tags=["codes"])
log = logging.getLogger("bifrost.codes")


def _state(request: Request):
    return request.app.state


def _urls(cfg) -> codes.Urls:
    return codes.Urls(
        gramps=cfg.sync_paperless.gramps_public_url or cfg.sync_immich.gramps_public_url,
        paperless=cfg.sync_paperless.public_url,
        immich=cfg.sync_immich.public_url,
    )


async def _live(st) -> tuple[dict[str, str] | None, str | None]:
    """Live Gramps media titles by id, or None with the reason when Gramps can't be read"""
    try:
        return await st.gramps.media_descriptions(), None
    except Exception as exc:  # noqa: BLE001
        log.warning("codes: Gramps media ids unavailable: %s", exc)
        return None, str(exc)[:200]


async def _documents(st) -> set[str] | None:
    """Every Paperless document id, or None when Paperless can't be read"""
    try:
        return {str(i) for i in await st.paperless.document_ids()}
    except Exception as exc:  # noqa: BLE001
        log.warning("codes: Paperless document ids unavailable: %s", exc)
        return None


async def _taken(st) -> tuple[set[str], dict[str, list[int]]]:
    """Everything outside bifrost that may already hold a code: live Gramps media
    ids and the Paperless gramps_id field. A new code is only handed out when
    both could be read"""
    try:
        live = await st.gramps.list_media_gramps_ids()
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(503, "Gramps could not be read to check which codes are taken, "
                                 f"so nothing was changed: {str(exc)[:200]}")
    paperless: dict[str, list[int]] = {}
    field_id = st.cfg.sync_paperless.gramps_id_field_id
    if field_id:
        try:
            values = await st.paperless.custom_field_values(field_id)
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(503, "Paperless could not be read to check which codes are "
                                     f"taken, so nothing was changed: {str(exc)[:200]}")
        for doc_id, value in values.items():
            if key := codes.normalize(str(value)):
                paperless.setdefault(key, []).append(doc_id)
    return live, paperless


def _refuse(exc: codes.CodeError) -> HTTPException:
    return HTTPException(exc.status, exc.detail)


def _item(st, code: str, live: set[str] | None = None) -> dict | None:
    found = codes.rows(st.conn, live, _urls(st.cfg), only=[code])
    return found[0] if found else None


@router.get("")
async def codes_page(request: Request):
    return RedirectResponse(url="/#codes")


@router.get("/api/list")
async def list_codes(request: Request, status: str = "", q: str = "") -> dict:
    """Every code with its derived status; ?status= and ?q= narrow the items"""
    st = _state(request)
    try:
        wanted = codes.status_filter(status)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    (titles, gramps_error), documents = await asyncio.gather(_live(st), _documents(st))
    live = None if titles is None else set(titles)
    items = codes.search(codes.rows(st.conn, live, _urls(st.cfg), titles=titles,
                                    documents=documents), q)
    return {
        "gramps": "unknown" if live is None else "ok",
        "gramps_error": gramps_error,
        "counts": codes.counts(items),
        "items": [r for r in items if codes.matches(r, wanted)],
    }


class MintBody(BaseModel):
    count: int = 1


@router.post("/api/mint")
async def mint(request: Request, body: MintBody) -> dict:
    st = _state(request)
    try:
        if not 1 <= body.count <= codes.MAX_MINT:
            raise codes.CodeError(400, f"Mint between 1 and {codes.MAX_MINT} codes at a time.")
        live, paperless = await _taken(st)
        new = codes.mint(st.conn, body.count, live, paperless)
    except codes.CodeError as exc:
        raise _refuse(exc)
    items = {r["code"]: r for r in codes.rows(st.conn, live, _urls(st.cfg), only=new)}
    return {"codes": new, "items": [items[c] for c in new]}


class ClaimBody(BaseModel):
    code: str = ""


@router.post("/api/claim")
async def claim(request: Request, body: ClaimBody) -> dict:
    """Register a code that was written down by hand"""
    st = _state(request)
    try:
        codes.check_new(st.conn, body.code)
        live, paperless = await _taken(st)
        code = codes.claim(st.conn, body.code, live, paperless)
    except codes.CodeError as exc:
        raise _refuse(exc)
    return {"codes": [code], "items": [_item(st, code, live)]}


@router.get("/api/open")
async def open_codes(request: Request) -> dict:
    """Reserved codes a photo can take when it is synced"""
    st = _state(request)
    titles, gramps_error = await _live(st)
    if titles is None:
        raise HTTPException(503, f"Gramps could not be read: {gramps_error}")
    return {"items": codes.open_codes(st.conn, set(titles))}


@router.get("/api/export.csv")
async def export_csv(request: Request) -> Response:
    st = _state(request)
    (titles, _error), documents = await asyncio.gather(_live(st), _documents(st))
    live = None if titles is None else set(titles)
    body = codes.to_csv(codes.rows(st.conn, live, _urls(st.cfg), titles=titles,
                                   documents=documents))
    name = f"gda-codes-{date.today().isoformat()}.csv"
    return Response(body.encode("utf-8"), media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="{name}"'})


class ReconcileBody(BaseModel):
    selected: list[str] | None = None


@router.get("/api/reconcile/config")
async def reconcile_config(request: Request) -> dict:
    return {"enabled": True}


@router.post("/api/reconcile/preview")
async def reconcile_preview(request: Request, body: ReconcileBody = ReconcileBody()) -> dict:
    st = _state(request)
    gen = reconcile.scan(st.gramps, st.paperless, getattr(st, "immich_accounts", []), st.conn,
                         apply=False)
    run_id, events = await record_run(st.conn, "codes.reconcile.preview", gen)
    return {"run_id": run_id, "apply": False, "events": [e.__dict__ for e in events]}


@router.post("/api/reconcile/apply")
async def reconcile_apply(request: Request, body: ReconcileBody = ReconcileBody()) -> dict:
    st = _state(request)
    gen = reconcile.scan(st.gramps, st.paperless, getattr(st, "immich_accounts", []), st.conn,
                         apply=True, selected=set(body.selected) if body.selected is not None else None)
    run_id, events = await record_run(st.conn, "codes.reconcile", gen)
    st.caches.clear()
    return {"run_id": run_id, "apply": True, "events": [e.__dict__ for e in events]}


class WithdrawBody(BaseModel):
    reason: str = ""
    superseded_by: str | None = None


@router.post("/api/{code}/withdraw")
async def withdraw(request: Request, code: str, body: WithdrawBody) -> dict:
    st = _state(request)
    try:
        code = codes.withdraw(st.conn, code, body.reason, body.superseded_by)
    except codes.CodeError as exc:
        raise _refuse(exc)
    return {"item": _item(st, code)}


class PatchBody(BaseModel):
    superseded_by: str | None = None


@router.patch("/api/{code}")
async def patch(request: Request, code: str, body: PatchBody) -> dict:
    """Name, change or clear the code that takes a withdrawn code's place"""
    st = _state(request)
    try:
        code = codes.supersede(st.conn, code, body.superseded_by)
    except codes.CodeError as exc:
        raise _refuse(exc)
    return {"item": _item(st, code)}


@router.delete("/api/{code}")
async def delete(request: Request, code: str) -> dict:
    """Remove a reservation nothing has used yet"""
    st = _state(request)
    try:
        live, paperless = await _taken(st)
        code = codes.delete(st.conn, code, live, paperless)
    except codes.CodeError as exc:
        raise _refuse(exc)
    return {"deleted": code}


@router.get("/api/{code}/thumbnail")
async def thumbnail(request: Request, code: str, size: int = 256):
    """The code's Gramps media thumbnail"""
    st = _state(request)
    code = codes.normalize(code)
    try:
        media = await st.gramps.get_media_by_gramps_id(code)
        if media is None:
            raise HTTPException(404, f"{code} is not in Gramps.")
        content, mime = await st.gramps.media_thumbnail(media["handle"], size)
    except GrampsError as exc:
        raise HTTPException(502, str(exc)[:200]) from exc
    return Response(content, media_type=mime, headers={"Cache-Control": "public, max-age=3600"})
