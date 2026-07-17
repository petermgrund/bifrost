# Bifrost

Gramps curation console: syncs Paperless documents and Immich photos into
Gramps Web, plus photo-metadata editing (the Photos page, formerly the
standalone urd app) and citations/transcription/places tooling. FastAPI +
vendored BeerCSS 4 + Lit, SQLite at `data/bifrost.db` (migrations in
`core/db.py`). Runs in production on the Pi (eir) via docker compose on
:8800; develop on the Mac natively and ship with `./deploy.sh`.

## Architecture conventions

- **Sync modules are async generators** yielding `SyncEvent`
  (`core/events.py`) consumed through `web/runs.py:record_run` into the
  `runs`/`run_events` ledger. New sync work follows that shape.
- **Clients live in `core/clients/`** — one adapter per external system.
  Gramps API quirks that are load-bearing: `POST /objects` takes a
  **single-element JSON list**; `follow_redirects=True` is required (Gramps
  308-redirects object creation); `gramps_id` and `handle` are client-set
  (`core/ids.py`, safe alphabet `ABCDEFGHJKMNPQRSTUVWXYZ23456789`).
  All Immich HTTP lives in `core/clients/immich.py` — Immich majors break
  third-party API consumers roughly annually (v2→v3 did); one adapter file
  is the containment. Every caller-supplied id that reaches an Immich URL
  path goes through `_checked_id` (UUID guard) — the server holds an API key.
- **The `gda.*` KV value shapes are contracts** (`core/gda/`): `gda.date`
  mirrors the Gramps date model (string modifier/quality, month/day `0` =
  unknown), `gda.scan` the media-ID scheme roles, `gda.gramps` the Gramps
  linkage, `gda.verso` the recto/verso pair link (`{"verso": id}` on the
  front, `{"recto": id}` on the back). `modules/sync_immich.py` consumes
  them — change a shape and its consumer together or not at all
  (`tests/test_gda.py` pins the couplings).
- **The Immich sync runs from the Sync section** (`sync_assets`,
  preview/apply like Paperless): a titled, unsynced asset (`gda.gramps.title`
  set) is a create — the title is the deliberate "put this in Gramps"
  signal; a synced asset whose gda title/date drifted from Gramps is an
  update. It never clears a Gramps-side date, and it never creates media for
  untitled assets. `POST /sync/immich/asset` remains for external callers.
  Person links come from the face-linker's `person_map.yaml` (read fresh per
  call; the face-linker GUI owns that file). Path mappings hard-fail on
  unmapped paths — never guess a media path. No face rectangles, by design.
- **Versos carry no metadata of their own** — they are the back of their
  recto (pairing UI on the Photos page; flip/unlink in the editor). They
  never sync, never render in the Photos grid (the recto's flip chip is the
  only trace), and an already-synced asset may not become one (its Gramps
  media object would be orphaned). Automatic verso detection is planned,
  not built.
- **A stack's metadata lives on its Immich primary** (the "main image" —
  Immich's own `primaryAssetId`, changeable from the editor). Stack children
  never render in the grid, never sync, and the editor redirects them to the
  main; the variant chips only preview the other files. "Make main image"
  moves gda.date/gramps/verso to the new main (gda.scan stays per-file), and
  the next Sync scan repoints the Gramps media to the new main's file — the
  photo analog of the Paperless selected-version repoint. Membership must
  come from `GET /stacks` — v3.0.1 search results report `stack: null` even
  for stacked assets (verified live). Stacks are managed from bifrost too:
  the grid's Stack button creates or merges (Immich's `POST /stacks` pulls a
  listed asset's whole stack along; first id = primary), the editor removes
  variants; joiners may be neither versos nor already-synced media, and the
  main can't leave its own stack.
- **Photos-page invariants** (from the urd fold-in, 2026-07-15): never write
  a fake exact date into Immich's `dateTimeOriginal` — fuzzy dates live in
  `gda.date` only. Custom KV keys are not searchable server-side, and Immich
  search with multiple `albumIds` is an **intersection**, not a union
  (verified on v3.0.1) — that's why the album-whitelist merged view fans out
  one search per album (`_merged_page` in `web/routes/photos.py`). Only
  **managed-library** assets may carry KV metadata (external-library asset
  ids change when files move). The album whitelist lives in the
  `app_settings` table, not config.

## Databases and live-data warnings

- `reserved_ids` / `minted_media` / `scan_register` in the **Pi's**
  `data/bifrost.db` are real registers (physically penciled photo IDs
  reference them). A fresh dev db knows none of it — **do not run sync
  writes from a dev bifrost against the production Gramps**; that testing
  waits for scratch instances (restore Gramps Web + bifrost.db from borg
  backups into throwaway containers).
- Dev configs point at production Gramps/Paperless/Immich on the Pi
  (192.168.1.69) — reads are fine; treat any write path with respect. The
  Photos page's saves are real Immich metadata writes (that is the page's
  purpose, but treat bulk operations with respect). Set
  `sync.immich.enabled: false` in a dev config to disable the Sync section's
  Immich block and 503 the apply/single-asset sync endpoints (the fold-in's
  replacement for urd's empty `bifrost.base_url` safety knob).
- `config.yaml`, `house_style_master.md` (real family data), and `data/`
  are gitignored on purpose — copy them from the Pi when a dev instance
  needs them, and fix the container-only paths (`/app/repo/...`, `/legacy/...`,
  `/boundaries`) to Mac-local ones.

## UI rule (owner's standing preference)

Build UI from **BeerCSS's own documented materials**; never re-implement a
framework primitive in `bifrost.css`. Verify classes exist by grepping
`bifrost/web/static/vendor/beer.min.css`.

## Running / testing / deploying

- Dev: `venv/bin/uvicorn bifrost.web.app:app --reload --port 8800`
  (`BIFROST_CONFIG` env var overrides the config path; default is repo-root
  `config.yaml`). Docker compose is prod-shaped — its bind mounts only exist
  on the Pi.
- Tests: `venv/bin/python -m pytest tests/` (`test_reprocess.py` needs
  `pypdf`).
- Deploy: `./deploy.sh` (push → ssh → pull --ff-only → compose build → up).
  The Pi checkout `/opt/stacks/bifrost` is a deploy target — never edit it
  in place.
