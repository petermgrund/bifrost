"""Sync everything"""

from __future__ import annotations

from typing import AsyncIterator

from ..core.config import Config
from ..core.events import SyncEvent
from . import faces, ocr, sync_immich, sync_paperless


async def _together(*parts) -> AsyncIterator[SyncEvent]:
    """The parts' events in turn, their summaries added up into one"""
    counts: dict[str, int] = {}
    for part in parts:
        try:
            async for ev in part:
                if ev.kind == "summary":
                    for key, n in (ev.data or {}).items():
                        counts[key] = counts.get(key, 0) + n
                else:
                    yield ev
        except sync_immich.SyncError as exc:
            counts["errors"] = counts.get("errors", 0) + 1
            yield SyncEvent(kind="error", detail=f"Immich: {exc.detail}")
    yield SyncEvent(kind="summary", data=counts)


def documents(gramps, paperless, gemini, cfg: Config) -> AsyncIterator[SyncEvent]:
    parts = [sync_paperless.sync(paperless, gramps, cfg.sync_paperless, apply=True)]
    if cfg.sync_paperless.ocr_tag:
        parts.append(ocr.run_with_sync(paperless, gramps, gemini, cfg.sync_paperless, cfg.gemini))
    return _together(*parts)


def photos(gramps, accounts: list, cfg: Config) -> AsyncIterator[SyncEvent]:
    return _together(sync_immich.sync_assets(gramps, accounts, cfg.sync_immich, apply=True),
                     faces.apply_links(gramps, accounts, apply=True))
