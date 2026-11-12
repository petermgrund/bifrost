"""One scan of Paperless, copyparty, Immich and faces against Gramps"""

from __future__ import annotations

from typing import AsyncIterator

from ..core.config import Config
from ..core.events import SyncEvent
from . import faces, ocr, sync_copyparty, sync_immich, sync_paperless


async def run(gramps, paperless, gemini, accounts: list, cfg: Config, apply: bool,
              selected: set[str] | None = None, copyparty=None) -> AsyncIterator[SyncEvent]:
    counts: dict[str, int] = {}

    async def part(gen):
        async for ev in gen:
            if ev.kind == "summary":
                for key, n in (ev.data or {}).items():
                    counts[key] = counts.get(key, 0) + n
            else:
                yield ev

    async for ev in part(sync_paperless.sync(paperless, gramps, cfg.sync_paperless, apply, selected=selected)):
        yield ev
    if cfg.sync_paperless.ocr_tag:
        gen = (ocr.run_with_sync(paperless, gramps, gemini, cfg.sync_paperless, cfg.gemini, selected=selected)
               if apply else ocr.run(paperless, gemini, cfg.sync_paperless, cfg.gemini, apply=False))
        async for ev in part(gen):
            yield ev
    if copyparty is not None and cfg.sync_copyparty.path_mappings:
        async for ev in part(sync_copyparty.sync(copyparty, gramps, cfg.sync_copyparty, apply, selected)):
            yield ev
    if accounts and cfg.sync_immich.enabled:
        try:
            async for ev in part(sync_immich.sync_assets(gramps, accounts, cfg.sync_immich, apply, selected)):
                yield ev
        except sync_immich.SyncError as exc:
            counts["errors"] = counts.get("errors", 0) + 1
            yield SyncEvent(kind="error", detail=f"Immich: {exc.detail}")
    if accounts:
        async for ev in part(faces.apply_links(gramps, accounts, apply, selected)):
            yield ev
    yield SyncEvent(kind="summary", data=counts)
