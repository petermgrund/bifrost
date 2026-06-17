"""ID generator page + API — mint and track reserved random-6 media ids."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from ...modules import idgen

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


@router.post("/api/generate")
async def generate(request: Request, body: GenerateBody):
    st = _state(request)
    new_ids = await idgen.generate(st.conn, st.gramps, body.count)
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
