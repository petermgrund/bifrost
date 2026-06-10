# Bifrost — design document

*The bridge between realms: one console for everything Gramps.*

**Status:** draft v1 — agreed direction, pre-implementation
**Date:** 2026-06-10

## 1. What and why

Bifrost consolidates the Gramps tooling that grew up as independent projects —
paper-to-gramps, immich-to-gramps, the face-linker GUI, osm-to-gramps, the
citation ideas from gda-sync, and the control-center job runner — into a single
web application: one place for syncing, face linking, citation generation, and
place boundaries.

The core architectural change from control-center: integration moves from the
**process** level (subprocess + flags + log lines) to the **function** level
(library calls yielding structured events). That single change is what makes
real progress UIs, preview/approve flows, and interactive tools possible in one
app.

Simplifying assumption that makes this tractable: **Gramps Web is the sole
writer of the tree.** No desktop sync, no Mac agent, no file locking. Every
feature is "talk to three REST APIs."

Bifrost is the *curation* half of the long-term unified-ancestry-app vision.
The eventual *presentation* half (browsing photos/documents/tree as one
experience) will reuse Bifrost's core library.

## 2. Principles

1. **Strangler fig.** The legacy pipeline stays untouched and running. Bifrost
   reaches feature parity module by module; legacy pieces are retired only
   after a module fully cuts over.
2. **Idempotency keys live in the target systems**, exactly as today: "Immich
   ID" attributes on Gramps media, `gramps_id` custom fields written back to
   Paperless. Bifrost's database is mapping/cache/audit — if it is lost, a
   reconcile pass can rebuild it from the systems of record.
3. **Events, not logs.** Every operation yields typed events. The web UI, the
   run history, and the CLI renderer are all consumers of the same stream.
4. **One client per system.** Exactly one Gramps client, one Immich client,
   one Paperless client, in one package. (Today: 3 Gramps, 2 Paperless,
   2 Immich implementations across projects.)
5. **Boring tech, deliberately.** FastAPI + Jinja + htmx + SSE, vanilla-JS
   islands for interactive pages. SQLite. No task queue, no SPA framework —
   single user, asyncio is plenty.
6. **Tailnet-only binding** (`100.89.34.77` + `127.0.0.1`), like everything
   else on eir. Never eth0.
7. **Open for extension.** Adding a new sync source, citation type, or inbox
   card must be additive, not surgical: a sync module is anything conforming
   to the small protocol (async generator of `SyncEvent`s + an inbox-count
   hook + optional routes/templates) and registering itself; citation types
   are data/templates, not code branches. When a design choice trades
   convenience now against a closed door later, prefer the open door — but
   don't build speculative abstraction for futures we haven't met. The
   registry pattern lands when the second sync module does (Phase 3), not
   before.

## 3. Repository layout

```
bifrost/
├── bifrost/                    # the Python package
│   ├── core/
│   │   ├── clients/
│   │   │   ├── gramps.py       # seeded from control-center's async client
│   │   │   ├── immich.py
│   │   │   └── paperless.py
│   │   ├── config.py           # single config.yaml: all creds, all services
│   │   ├── db.py               # SQLite access + schema migrations
│   │   └── events.py           # event dataclasses (section 5)
│   ├── modules/                # domain logic, no web imports
│   │   ├── faces.py            # person links, face-rectangle MediaRefs
│   │   ├── sync_immich.py      # asset sync, dates, places, descriptions
│   │   ├── sync_paperless.py   # doc sync, date qualifiers, write-back
│   │   ├── transcriptions.py   # OCR → Notes, --- delimiter, hashes
│   │   ├── boundaries.py       # OSM relations → PNG + GeoJSON (phase 4)
│   │   ├── citations.py        # sources/citations builder (phase 4)
│   │   └── reconcile.py        # rebuild DB state from systems of record
│   ├── web/
│   │   ├── app.py
│   │   ├── routes/             # dashboard, faces, sync, places, runs
│   │   ├── templates/
│   │   └── static/
│   └── cli.py                  # thin wrappers for cron: sync, reconcile, doctor
├── tests/
│   └── golden/                 # legacy-vs-bifrost comparison harness
├── docs/DESIGN.md              # this file
├── config.example.yaml
├── docker-compose.yml          # tailnet+loopback port 8800
├── Dockerfile
└── requirements.txt
```

## 4. Data model (SQLite)

One database absorbs the scattered state files. Legacy file → table mapping:

| Legacy file | Table | Notes |
|---|---|---|
| `person_map.yaml` | `person_links` | the one true mutable state; see cutover shim §7 |
| `minted.csv` (×2 projects) | `minted_media` | audit trail of created media |
| `versions.json` | `doc_versions` | Paperless doc checksums |
| `transcriptions.json` | `transcription_state` | content hashes + note handles |
| control-center SQLite | `runs` / `run_events` | richer: structured events, not log tails |

```sql
CREATE TABLE person_links (
    gramps_handle    TEXT NOT NULL,
    immich_person_id TEXT NOT NULL,
    label            TEXT,
    created_at       TEXT NOT NULL,
    PRIMARY KEY (gramps_handle, immich_person_id)
);

CREATE TABLE minted_media (
    gramps_id     TEXT PRIMARY KEY,
    source_system TEXT NOT NULL CHECK (source_system IN ('immich','paperless')),
    source_id     TEXT NOT NULL,
    title         TEXT,
    minted_at     TEXT NOT NULL
);

CREATE TABLE doc_versions (
    paperless_id INTEGER PRIMARY KEY,
    checksum     TEXT NOT NULL,
    gramps_id    TEXT,
    updated_at   TEXT NOT NULL
);

CREATE TABLE transcription_state (
    -- columns match the legacy transcriptions.json schema exactly
    paperless_id        INTEGER PRIMARY KEY,
    content_hash        TEXT NOT NULL,
    note_handle         TEXT,
    gramps_note_id      TEXT,
    gramps_media_id     TEXT,
    translation_handle  TEXT,
    translation_note_id TEXT,
    updated_at          TEXT NOT NULL
);

CREATE TABLE runs (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    job         TEXT NOT NULL,
    status      TEXT NOT NULL,          -- running|ok|error|cancelled|interrupted
    started_at  TEXT NOT NULL,
    finished_at TEXT,
    summary     TEXT                    -- JSON: counts by action
);

CREATE TABLE run_events (
    run_id  INTEGER NOT NULL REFERENCES runs(id),
    seq     INTEGER NOT NULL,
    ts      TEXT NOT NULL,
    payload TEXT NOT NULL,              -- JSON-serialized event (section 5)
    PRIMARY KEY (run_id, seq)
);

CREATE TABLE schema_version (version INTEGER NOT NULL);
```

`bifrost import-legacy` is a one-shot importer for all five legacy sources.
`bifrost reconcile` rebuilds `minted_media`/`doc_versions` from Gramps and
Paperless if the DB is ever lost (principle 2), and doubles as the
duplicate-window integrity check from the original system review.

## 5. Event schema

Domain modules are async generators; everything else consumes.

```python
@dataclass
class SyncEvent:
    kind:   Literal["started", "item", "summary", "error"]
    entity: Literal["media", "face", "note", "place", "doc"] | None = None
    action: Literal["created", "updated", "skipped", "failed",
                    "would_create", "would_update"] | None = None
    source_id: str | None = None      # Immich UUID / Paperless ID / OSM relation
    gramps_id: str | None = None
    title:     str | None = None
    detail:    str | None = None      # human-readable specifics
    data:      dict | None = None     # structured extras (counts in summary, etc.)
```

- **Preview = the same generator run with `apply=False`**, yielding
  `would_*` actions. The web layer renders those as a checklist; approving
  re-runs with `apply=True` (optionally restricted to selected source_ids).
- The web layer fans events out to SSE (live UI) and `run_events` (history).
- `cli.py` renders the same stream as log lines, preserving cron usability.

## 6. Pages (v1 scope)

| Page | Contents |
|---|---|
| **Inbox** (home) | pending counts with links: unsynced tagged Immich assets, unsynced tagged Paperless docs, unlinked Immich faces, places missing boundaries; recent runs strip |
| **Faces** | ported two-pane linker (Gramps people ↔ Immich people w/ thumbnails); unlinked-faces queue; link/unlink writes `person_links` |
| **Sync** | Immich + Paperless panels: preview → review checklist → apply, live per-item progress |
| **Places** | boundary coverage table, generate/regenerate (phase 4) |
| **Citations** | source/citation builder (phase 4) |
| **Runs** | history with structured event detail, filterable by job/action |

## 7. Phases & cutover criteria

**Phase 0 — foundation.**
Scaffold repo, port the three clients into `core/clients/`, unified
`config.yaml`, DB schema + migrations, `import-legacy`, `doctor` command
(connectivity + auth check against all three APIs).
*Exit: `bifrost doctor` green; legacy state imported.*

**Phase 1 — faces (first full cutover).**
Port the face-linker GUI into `web/`; `person_links` becomes the source of
truth. Scope turned out larger than "linking UI": the legacy GUI also *applies*
links (sync faces, re-pad, manual-faces lock with tight-rect recompute), so
those operations port now too — the service can only retire with full parity.
**Compat shim:** on every link change, Bifrost re-exports
`person_map.yaml`, because the legacy `immich_to_gramps.py --link-faces` path
reads it during syncs — this keeps the legacy pipeline correct until Phase 2
retires it.
*Exit: face-linker.service stopped and disabled; daily face-linking happens in
Bifrost; person_map.yaml is generated, never hand-edited.*

**Phase 2 — Immich sync.**
Port asset sync (tags, date qualifiers, GPS→place linking, descriptions,
face MediaRefs) as `sync_immich.py` with inbox + preview/apply.
**Golden-master gate:** legacy `--dry-run` and Bifrost preview run against the
same live data; normalized outputs must match before cutover.
*Exit: control-center "immich" job retired; person_map.yaml export shim
removed.*

**Phase 3 — Paperless sync + transcriptions.**
Same pattern, same golden-master gate (including `---` delimiter handling and
custom-field write-back ordering).
*Exit: control-center "paperless" job retired.*

**Phase 4 — places & citations.**
Absorb osm-to-gramps as `boundaries.py` (it is already async FastAPI; mostly a
move). Build citations on gda-sync's salvaged client patterns.
*Exit: osm-to-gramps container retired; citations usable end-to-end.*

**Phase 5 — retire control-center.**
Anything still useful (link tiles, history) lives in Bifrost by now.
*Exit: ports 8088/8765/8767/82 all dark; Bifrost on 8800 is the console.*

## 8. Risks & mitigations

| Risk | Mitigation |
|---|---|
| Monoliths encode ~3,200 lines of edge cases (date qualifier composition, path mapping, face-crop padding, delimiter parsing) | port with legacy as reference implementation; golden-master diffs gate every sync cutover; unit-test the gnarly pure functions first |
| Parallel-run state divergence | only `person_map.yaml` is dual-writer; write-through shim in Phase 1, removed in Phase 2 |
| DB loss | principle 2 + `bifrost reconcile`; DB lives under `/opt/stacks/bifrost/data/` → covered by nightly stacks borg job |
| Scope creep toward "generic job platform" | control-center already exists; Bifrost builds domain features only |
| Solo-maintainer tech ceiling | boring stack (principle 5); no build step for the frontend |

## 9. Deployment

Docker, like the rest of the stacks: image built from this repo, ports
`100.89.34.77:8800` + `127.0.0.1:8800`, volumes for `config.yaml` (ro) and
`data/` (db). Credentials: one config file, mode 600, gitignored, with
committed `config.example.yaml`. No auth in v1 (tailnet is the boundary,
consistent with current posture).

## 10. Open questions (non-blocking)

- Citation UX: freeform EE-style text vs. templated per record type — decide
  in Phase 4 with real examples.
- Should the Inbox poll source systems on a schedule (cheap counts via API)
  or only on page load? Start with on-load + manual refresh; revisit.
- Whether Bifrost eventually exposes webhook endpoints (Paperless workflows
  can push "new tagged doc" instead of polling). Post-v1.
