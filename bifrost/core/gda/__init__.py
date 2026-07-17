"""The gda.* key-value contract stored on Immich assets.

Bifrost layers genealogy metadata on Immich photos WITHOUT touching Immich's
database, via the Stable per-asset `PUT /api/assets/{id}/metadata` endpoint:

- ``gda.date``   — a Gramps-model fuzzy date (dates.py). Consumed by
  modules/sync_immich.py, which maps it onto the Gramps API Date object.
- ``gda.scan``   — the media-ID scheme role of this file (scan.py).
- ``gda.gramps`` — Gramps linkage: ``{"title": ...}`` set by the Photos
  editor; ``{"gramps_id", "synced_at"}`` written back by the sync.

These value shapes are contracts: physical photo IDs and the Gramps tree
reference them. Change a shape here and its consumer in
modules/sync_immich.py together or not at all.
"""
