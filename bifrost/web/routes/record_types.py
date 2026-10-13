"""Record types page + API: Bifrost is the master for record types"""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from ...modules import record_types

router = APIRouter(prefix="/citations", tags=["record types"])
templates = Jinja2Templates(directory=Path(__file__).resolve().parents[1] / "templates")


def _refused(exc: record_types.RecordTypeError) -> HTTPException:
    return HTTPException(exc.status, str(exc))


@router.get("/types", response_class=HTMLResponse)
async def types_page(request: Request):
    return templates.TemplateResponse(request, "types.html", {})


@router.get("/api/types")
async def list_types(request: Request) -> dict:
    return {"types": record_types.list_types(request.app.state.conn)}


class TypeBody(BaseModel):
    kind: str
    definition: dict


@router.put("/api/types/{type_id}")
async def save_type(request: Request, type_id: str, body: TypeBody) -> dict:
    try:
        return record_types.save(request.app.state.conn, type_id, body.kind, body.definition)
    except record_types.RecordTypeError as exc:
        raise _refused(exc) from exc


@router.post("/api/types/{type_id}/restore")
async def restore_type(request: Request, type_id: str) -> dict:
    try:
        return record_types.restore(request.app.state.conn, type_id)
    except record_types.RecordTypeError as exc:
        raise _refused(exc) from exc


class DeleteBody(BaseModel):
    kind: str = "override"


@router.post("/api/types/{type_id}/delete")
async def delete_type(request: Request, type_id: str, body: DeleteBody = DeleteBody()) -> dict:
    try:
        return record_types.delete(request.app.state.conn, type_id, body.kind)
    except record_types.RecordTypeError as exc:
        raise _refused(exc) from exc


@router.get("/api/general-drafts")
async def general_drafts(request: Request) -> dict:
    return {"drafts": record_types.general_drafts(request.app.state.conn)}


@router.get("/api/types/{type_id}/versions")
async def type_versions(request: Request, type_id: str) -> dict:
    return {"versions": record_types.versions(request.app.state.conn, type_id)}
