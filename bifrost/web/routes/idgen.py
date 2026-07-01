"""ID generator page + API — mint and track reserved random-6 media ids."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from ...modules import idgen, scans

router = APIRouter(prefix="/idgen", tags=["idgen"])


def _state(request: Request):
    return request.app.state


@router.get("")
async def idgen_page(request: Request):
    from ..app import templates  # late import to avoid cycle

    return templates.TemplateResponse(request, "idgen.html", {})


@router.get("/api/list")
async def list_ids(request: Request):
    st = _state(request)
    return {"ids": await idgen.listing(st.conn, st.gramps)}


class GenerateBody(BaseModel):
    count: int = 1
    note: str | None = None


@router.post("/api/generate")
async def generate(request: Request, body: GenerateBody):
    st = _state(request)
    new_ids = await idgen.generate(st.conn, st.gramps, body.count, note=body.note)
    return {"generated": new_ids, "ids": await idgen.listing(st.conn, st.gramps)}


class IdBody(BaseModel):
    gramps_id: str


@router.post("/api/release")
async def release(request: Request, body: IdBody):
    st = _state(request)
    if not idgen.release(st.conn, body.gramps_id.strip()):
        raise HTTPException(409, "already minted — cannot release")
    return {"ids": await idgen.listing(st.conn, st.gramps)}


@router.post("/api/assign")
async def assign(request: Request, body: IdBody):
    st = _state(request)
    if not idgen.assign(st.conn, body.gramps_id.strip()):
        raise HTTPException(409, "already minted — cannot assign")
    return {"ids": await idgen.listing(st.conn, st.gramps)}


@router.post("/api/unassign")
async def unassign(request: Request, body: IdBody):
    st = _state(request)
    if not idgen.unassign(st.conn, body.gramps_id.strip()):
        raise HTTPException(409, "already minted — cannot unassign")
    return {"ids": await idgen.listing(st.conn, st.gramps)}


# --- the a-series scan register (SCHEME.md §2) ---------------------------


@router.get("/api/scans")
async def scans_overview(request: Request):
    return scans.overview(_state(request).conn)


class ScanRegisterBody(BaseModel):
    count: int = 1
    container: str | None = None
    note: str | None = None
    captured: str | None = None


@router.post("/api/scans/register")
async def scans_register(request: Request, body: ScanRegisterBody):
    conn = _state(request).conn
    nos = scans.register_batch(
        conn, body.count,
        container=(body.container or "").strip() or None,
        note=(body.note or "").strip() or None,
        captured=(body.captured or "").strip() or None)
    out = scans.overview(conn)
    out["registered"] = nos
    return out


class ScanObjectBody(BaseModel):
    scan_no: str
    object_id: str | None = None


@router.post("/api/scans/object")
async def scans_object(request: Request, body: ScanObjectBody):
    conn = _state(request).conn
    if not scans.set_object_id(conn, body.scan_no.strip(), (body.object_id or "").strip() or None):
        raise HTTPException(404, "unknown scan number")
    return scans.overview(conn)
