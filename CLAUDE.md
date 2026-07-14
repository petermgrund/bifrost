# Bifrost

Gramps curation console: syncs Paperless documents and Immich photos into
Gramps Web, plus citations/transcription/places tooling. FastAPI + vendored
BeerCSS 4 + Lit, SQLite at `data/bifrost.db` (migrations in `core/db.py`).
Runs in production on the Pi (eir) via docker compose on :8800; develop on
the Mac natively and ship with `./deploy.sh`.

## Architecture conventions

- **Sync modules are async generators** yielding `SyncEvent`
  (`core/events.py`) consumed through `web/runs.py:record_run` into the
  `runs`/`run_events` ledger. New sync work follows that shape.
- **Clients live in `core/clients/`** — one adapter per external system.
  Gramps API quirks that are load-bearing: `POST /objects` takes a
  **single-element JSON list**; `follow_redirects=True` is required (Gramps
  308-redirects object creation); `gramps_id` and `handle` are client-set
  (`core/ids.py`, safe alphabet `ABCDEFGHJKMNPQRSTUVWXYZ23456789`).
- **The Immich sync is single-asset** (`POST /sync/immich/asset`, called by
  urd). Its contract with urd's KV keys (`gda.date`, `gda.gramps`) is shared
  — change `modules/sync_immich.py` and urd's `dates.py` together. Person
  links come from the face-linker's `person_map.yaml` (read fresh per call;
  the face-linker GUI owns that file). Path mappings hard-fail on unmapped
  paths — never guess a media path. No face rectangles, by design.

## Databases and live-data warnings

- `reserved_ids` / `minted_media` / `scan_register` in the **Pi's**
  `data/bifrost.db` are real registers (physically penciled photo IDs
  reference them). A fresh dev db knows none of it — **do not run sync
  writes from a dev bifrost against the production Gramps**; that testing
  waits for scratch instances (restore Gramps Web + bifrost.db from borg
  backups into throwaway containers).
- Dev configs point at production Gramps/Paperless/Immich on the Pi
  (192.168.1.69) — reads are fine; treat any write path with respect.
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
