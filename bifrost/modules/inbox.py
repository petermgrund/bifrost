"""Home (Inbox) aggregate — one tolerant call assembling pending work across
every surface plus a tree snapshot. Each piece is computed independently: a
single down service degrades that one item to "unavailable" (n = None) rather
than breaking the home page.
"""

from __future__ import annotations

import sqlite3

from . import boundaries, citations, faces as faces_mod, ocr
from .sync_paperless import _doc_gramps_id
from ..core.clients import GrampsClient, ImmichClient, PaperlessClient
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
    gramps: GrampsClient, immich: ImmichClient, paperless: PaperlessClient,
    conn: sqlite3.Connection, cfg: Config,
) -> dict:
    items: list[dict] = []
    errors: list[str] = []

    def fail(key, label, href):
        items.append({"key": key, "label": label, "href": href, "n": None})
        errors.append(key)

    # Faces + Immich photos: one listing covers all three counts.
    try:
        listing = await faces_mod.photo_listing(gramps, immich, conn)
        photos = listing.get("photos", [])
        unlinked = sum(1 for p in photos for f in p.get("faces", [])
                       if f.get("status") == "unlinked")
        items.append({"key": "faces", "label": "faces to link",
                      "href": "/faces?filter=unlinked", "n": unlinked})
        items.append({"key": "faces_pending", "label": "faces pending apply",
                      "href": "/faces?filter=pending", "n": listing.get("pending_total", 0)})
        items.append({"key": "immich", "label": "photos to sync",
                      "href": "/sync", "n": sum(1 for p in photos if not p.get("synced"))})
    except Exception:  # noqa: BLE001
        fail("faces", "faces to link", "/faces?filter=unlinked")
        fail("faces_pending", "faces pending apply", "/faces?filter=pending")
        fail("immich", "photos to sync", "/sync")

    async def add(key, label, href, coro_fn):
        try:
            items.append({"key": key, "label": label, "href": href, "n": await coro_fn()})
        except Exception:  # noqa: BLE001
            fail(key, label, href)

    await add("paperless", "documents to sync", "/sync",
              lambda: _paperless_pending(paperless, cfg.sync_paperless))
    await add("ocr", "docs tagged for OCR", "/sync",
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


# Home snapshot key -> Gramps object class (matches activity._db_totals counts).
SNAP_CLASS = {
    "people": "Person", "events": "Event", "places": "Place",
    "citations": "Citation", "media": "Media", "sources": "Source",
}


def trends(dash: dict, weeks_tail: int = 18) -> dict:
    """Compact per-class history for the interactive home snapshot, derived from
    the (cached) activity dashboard. Returns the last `weeks_tail` weeks of
    cumulative counts per snapshot class plus event-citation coverage."""
    totals = (dash.get("totals") or [])[-weeks_tail:]
    series = {
        key: [t["counts"].get(cls, 0) for t in totals]
        for key, cls in SNAP_CLASS.items()
    }
    cov = (dash.get("coverage") or [])[-weeks_tail:]
    coverage_series = [
        round(100 * (c.get("total", 0) - c.get("c0", 0)) / c["total"])
        if c.get("total") else 0
        for c in cov
    ]
    return {
        "weeks": [t["week"] for t in totals],
        "series": series,
        "coverage_pct": coverage_series[-1] if coverage_series else None,
        "coverage_series": coverage_series,
    }
