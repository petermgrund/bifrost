"""Sync everything from one source"""

import asyncio
from types import SimpleNamespace

from bifrost.core.config import GeminiConfig, SyncImmichConfig, SyncPaperlessConfig
from bifrost.core.events import SyncEvent
from bifrost.modules import check, sync_immich


def _gen(*events):
    async def gen(*args, **kwargs):
        for ev in events:
            yield ev
    return gen


def collect(gen):
    async def go():
        return [e async for e in gen]
    return asyncio.run(go())


def cfg(ocr_tag=""):
    return SimpleNamespace(sync_paperless=SyncPaperlessConfig(ocr_tag=ocr_tag),
                           sync_immich=SyncImmichConfig(), gemini=GeminiConfig())


def test_documents_run_the_sync_then_the_transcriptions_and_add_up(monkeypatch):
    monkeypatch.setattr(check, "sync_paperless", SimpleNamespace(sync=_gen(
        SyncEvent(kind="started", detail="2 docs"),
        SyncEvent(kind="item", entity="doc", action="created", source_id="1"),
        SyncEvent(kind="summary", data={"created": 1, "errors": 0}))))
    monkeypatch.setattr(check, "ocr", SimpleNamespace(run_with_sync=_gen(
        SyncEvent(kind="item", entity="doc", action="replaced", source_id="2"),
        SyncEvent(kind="summary", data={"replaced": 1, "errors": 1}))))
    events = collect(check.documents("gramps", "paperless", "gemini", cfg(ocr_tag="Gemini OCR")))
    assert [(e.kind, e.source_id) for e in events[:-1]] == [("started", None), ("item", "1"), ("item", "2")]
    assert events[-1].data == {"created": 1, "errors": 1, "replaced": 1}
    events = collect(check.documents("gramps", "paperless", "gemini", cfg()))
    assert events[-1].data == {"created": 1, "errors": 0}


def test_photos_run_the_assets_then_the_faces(monkeypatch):
    monkeypatch.setattr(check, "sync_immich", SimpleNamespace(sync_assets=_gen(
        SyncEvent(kind="item", entity="media", action="updated", source_id="a1"),
        SyncEvent(kind="summary", data={"versions_updated": 1, "errors": 0})), SyncError=sync_immich.SyncError))
    monkeypatch.setattr(check, "faces", SimpleNamespace(apply_links=_gen(
        SyncEvent(kind="item", entity="face", action="created", source_id="a1"),
        SyncEvent(kind="summary", data={"faces_linked": 1, "errors": 0}))))
    events = collect(check.photos("gramps", ["immich"], cfg()))
    assert [(e.entity, e.source_id) for e in events[:-1]] == [("media", "a1"), ("face", "a1")]
    assert events[-1].data == {"versions_updated": 1, "errors": 0, "faces_linked": 1}


def test_an_immich_failure_is_an_error_event_and_the_faces_still_run(monkeypatch):
    async def boom(*args, **kwargs):
        raise sync_immich.SyncError(400, "trigger tag not found")
        yield  # noqa: unreachable, makes this an async generator

    monkeypatch.setattr(check, "sync_immich", SimpleNamespace(sync_assets=boom, SyncError=sync_immich.SyncError))
    monkeypatch.setattr(check, "faces", SimpleNamespace(apply_links=_gen(
        SyncEvent(kind="summary", data={"faces_linked": 2}))))
    events = collect(check.photos("gramps", ["immich"], cfg()))
    assert [e.kind for e in events] == ["error", "summary"]
    assert "trigger tag" in events[0].detail and events[-1].data == {"errors": 1, "faces_linked": 2}


# ---- the endpoints

def test_the_sync_endpoints_return_the_summary_and_what_failed(monkeypatch):
    import httpx
    from fastapi import FastAPI

    from bifrost.web.routes import sync as sync_routes

    monkeypatch.setattr(check, "sync_paperless", SimpleNamespace(sync=_gen(
        SyncEvent(kind="item", entity="doc", action="created", source_id="1"),
        SyncEvent(kind="item", entity="doc", action="failed", source_id="2", detail="no file"),
        SyncEvent(kind="summary", data={"created": 1, "errors": 1}))))
    app = FastAPI()
    app.include_router(sync_routes.router)
    app.state.gramps, app.state.paperless, app.state.gemini = "gramps", "paperless", "gemini"
    app.state.immich_accounts = []
    app.state.cfg = cfg()
    app.state.caches = {"stale": 1}

    async def go():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://b") as c:
            return await c.post("/sync/api/paperless"), await c.post("/sync/api/immich")
    documents, photos = asyncio.run(go())
    assert documents.json()["summary"] == {"created": 1, "errors": 1}
    assert [(e["source_id"], e["detail"]) for e in documents.json()["events"]] == [("2", "no file")]
    assert app.state.caches == {} and photos.status_code == 503
