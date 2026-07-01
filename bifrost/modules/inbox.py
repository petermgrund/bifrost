"""Home (Inbox) aggregate — one tolerant call assembling pending work across
every surface plus a tree snapshot. Each piece is computed independently: a
single down service degrades that one item to "unavailable" (n = None) rather
than breaking the home page.
"""

from __future__ import annotations

import sqlite3

from . import boundaries, citations, ocr
from .sync_paperless import _doc_gramps_id
from ..core.clients import GrampsClient, PaperlessClient
from ..core.config import Config


async def _paperless_pending(paperless: PaperlessClient, cfg) -> int:
    tag_ids = []
    for name in cfg.sync_tags:
        tid = await paperless.resolve_tag_id(name)
        if tid is not None:
            tag_ids.append(tid)
    docs = await paperless.list_documents_by_tags(tag_ids)
    return sum(1 for d in docs if not _doc_gramps_id(d, cfg.gramps_id_field_id))


async def _places_missing(gramps: GrampsClient, cfg) -> int:
    rows = await boundaries.listing(gramps, cfg.boundaries_dir)
    return sum(1 for r in rows if r.get("osm_id") and not r.get("has_boundary"))


async def gather(
    gramps: GrampsClient, paperless: PaperlessClient,
    conn: sqlite3.Connection, cfg: Config,
) -> dict:
    items: list[dict] = []
    errors: list[str] = []

    def fail(key, label, href):
        items.append({"key": key, "label": label, "href": href, "n": None})
        errors.append(key)

    async def add(key, label, href, coro_fn):
        try:
            items.append({"key": key, "label": label, "href": href, "n": await coro_fn()})
        except Exception:  # noqa: BLE001
            fail(key, label, href)

    await add("paperless", "documents to sync", "/sync",
              lambda: _paperless_pending(paperless, cfg.sync_paperless))
    await add("ocr", "docs tagged for OCR", "/transcribe",
              lambda: ocr.pending_count(paperless, conn, cfg.sync_paperless))
    await add("places", "places missing boundaries", "/places?filter=missing",
              lambda: _places_missing(gramps, cfg.places))
    await add("citations", "events with no citation", "/citations",
              lambda: _uncited(gramps))

    snapshot: dict = {}
    for key, path in (("people", "/people/"), ("events", "/events/"),
                      ("places", "/places/"), ("citations", "/citations/"),
                      ("media", "/media/"), ("sources", "/sources/")):
        try:
            snapshot[key] = await gramps.count(path)
        except Exception:  # noqa: BLE001
            snapshot[key] = None

    return {"attention": items, "snapshot": snapshot, "errors": errors}


async def _uncited(gramps: GrampsClient) -> int:
    return len(await citations.uncited_events(gramps))
