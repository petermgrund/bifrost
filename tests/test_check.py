"""The one scan over Paperless, Immich and faces"""

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


def run(cfg, accounts=(), **parts):
    for name, gen in parts.items():
        setattr(check, name, gen)

    async def collect():
        return [e async for e in check.run("gramps", "paperless", "gemini", list(accounts), cfg, apply=False)]
    return asyncio.run(collect())


def cfg(ocr_tag="", immich=True):
    return SimpleNamespace(sync_paperless=SyncPaperlessConfig(ocr_tag=ocr_tag),
                           sync_immich=SyncImmichConfig(enabled=immich), gemini=GeminiConfig())


def test_parts_run_in_turn_and_their_summaries_add_up(monkeypatch):
    paperless = SimpleNamespace(sync=_gen(
        SyncEvent(kind="started", detail="2 docs"),
        SyncEvent(kind="item", entity="doc", action="would_create", source_id="1"),
        SyncEvent(kind="summary", data={"created": 1, "errors": 0})))
    ocr = SimpleNamespace(run=_gen(
        SyncEvent(kind="item", entity="doc", action="would_replace", source_id="2"),
        SyncEvent(kind="summary", data={"replaced": 1, "errors": 1})))
    immich = SimpleNamespace(sync_assets=_gen(
        SyncEvent(kind="item", entity="media", action="would_update", source_id="a1"),
        SyncEvent(kind="summary", data={"versions_updated": 1, "errors": 0})), SyncError=sync_immich.SyncError)
    faces = SimpleNamespace(apply_links=_gen(
        SyncEvent(kind="item", entity="face", action="would_create", source_id="a1"),
        SyncEvent(kind="summary", data={"faces_linked": 1, "errors": 0})))
    for name, mod in (("sync_paperless", paperless), ("ocr", ocr), ("sync_immich", immich), ("faces", faces)):
        monkeypatch.setattr(check, name, mod)
    events = run(cfg(ocr_tag="Gemini OCR"), accounts=["immich"])
    assert [(e.kind, e.entity, e.source_id) for e in events if e.kind != "summary"] == [
        ("started", None, None), ("item", "doc", "1"), ("item", "doc", "2"), ("item", "media", "a1"),
        ("item", "face", "a1")]
    assert events[-1].kind == "summary"
    assert events[-1].data == {"created": 1, "errors": 1, "replaced": 1, "versions_updated": 1, "faces_linked": 1}


def test_without_immich_or_an_ocr_tag_only_paperless_runs(monkeypatch):
    calls = []

    def part(name):
        async def gen(*args, **kwargs):
            calls.append(name)
            yield SyncEvent(kind="summary", data={})
        return gen

    monkeypatch.setattr(check, "sync_paperless", SimpleNamespace(sync=part("paperless")))
    monkeypatch.setattr(check, "ocr", SimpleNamespace(run=part("ocr")))
    monkeypatch.setattr(check, "sync_immich", SimpleNamespace(sync_assets=part("immich"), SyncError=sync_immich.SyncError))
    monkeypatch.setattr(check, "faces", SimpleNamespace(apply_links=part("faces")))
    run(cfg())
    assert calls == ["paperless"]
    calls.clear()
    run(cfg(immich=False), accounts=["immich"])
    assert calls == ["paperless", "faces"]


def test_an_immich_failure_is_an_error_event_and_the_rest_still_runs(monkeypatch):
    async def boom(*args, **kwargs):
        raise sync_immich.SyncError(400, "trigger tag not found")
        yield  # noqa: unreachable, makes this an async generator

    monkeypatch.setattr(check, "sync_paperless", SimpleNamespace(sync=_gen(SyncEvent(kind="summary", data={}))))
    monkeypatch.setattr(check, "sync_immich", SimpleNamespace(sync_assets=boom, SyncError=sync_immich.SyncError))
    monkeypatch.setattr(check, "faces", SimpleNamespace(apply_links=_gen(
        SyncEvent(kind="summary", data={"faces_linked": 2}))))
    events = run(cfg(), accounts=["immich"])
    assert [e.kind for e in events] == ["error", "summary"]
    assert "trigger tag" in events[0].detail
    assert events[-1].data == {"errors": 1, "faces_linked": 2}
