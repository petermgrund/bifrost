# Bifrost — Project Overview

A complete, plain-language description of what Bifrost is, how it fits into the
surrounding self-hosted stack, how it is built, and why it exists. For the
architecture rationale and phased build history see `DESIGN.md`; for the media
copy/label convention see `MEDIA_ID_SCHEME.md`.

---

## 1. What Bifrost is, in one paragraph

Bifrost is a single self-hosted web application that curates a **Gramps Web**
genealogy database by pulling together everything that used to be a pile of
separate scripts and services. It connects a photo manager (**Immich**), a
document archive (**Paperless-ngx**), a boundary renderer (**osm-to-gramps**),
and two LLMs (**Anthropic Claude** for citations, **Google Gemini** for OCR),
and gives one consistent "preview, then apply" interface for getting people,
photos, documents, places, citations, transcriptions, and IDs into Gramps
correctly. It runs as one Docker container on a Raspberry Pi ("eir"), reachable
only over the Tailscale tailnet at `http://100.89.34.77:8800/`.

---

## 2. Why it exists (the problem it solves)

Before Bifrost, the same family tree was fed by a handful of independent tools —
`immich-to-gramps`, `paper-to-gramps`, a face-linker GUI, `osm-to-gramps`, and a
"control-center" job runner — each with its own state files (`person_map.yaml`,
two `minted.csv`s, `versions.json`, `transcriptions.json`), its own UI or no UI,
and its own assumptions. That created three recurring pains:

- **Dual-writer state.** More than one tool could write the same state, risking
  drift and duplicate work.
- **No single review surface.** Each tool ran blind or in its own window; there
  was no one place to see "what would change" before it changed.
- **Manual gluing.** Getting a photo or document fully into Gramps — media
  object, faces, place link, date, citation, transcription — meant running
  several tools by hand in the right order.

Bifrost replaces that with **one app, one mental model, one source of truth**.
Its guiding principle is *preview everything, apply deliberately*: every
operation can be run read-only first to show exactly what it would do, then
applied. State that must be authoritative lives in the **target systems**
(Gramps attributes, Paperless custom fields); Bifrost's own SQLite database is a
rebuildable cache and audit log.

---

## 3. The systems it integrates

| System | Role | How Bifrost reaches it |
|---|---|---|
| **Gramps Web** | The genealogy database — the destination for everything. | REST API (`/api/...`), token auth with 429 retry + 401 re-auth; `follow_redirects` (POST `/objects` 308-redirects). |
| **Immich** | Photo library; people/face clusters; EXIF dates & GPS. | REST API, `x-api-key`. |
| **Paperless-ngx** | Document archive (records, letters, certificates) with OCR text, tags, custom fields, and 3.0 document versioning. | REST API, Token auth; `content` field is writable; custom fields carry the Gramps link. |
| **osm-to-gramps** | Renders OpenStreetMap admin boundaries / building footprints to GeoJSON. | HTTP service at `:82`; Bifrost orchestrates, it renders. |
| **Anthropic Claude** | Composes Evidence-Explained citations and the weekly Activity narrative. | Messages API; model `claude-opus-4-8`. |
| **Google Gemini** | LLM OCR — transcribes hard documents (handwriting, old print, photos) far better than Tesseract. | Generative Language API; model `gemini-3-flash-preview`. |

Everything binds to the Tailscale IP + loopback only — never `eth0` — matching
the host's "private by network discipline" posture.

---

## 4. Architecture

Three clean layers, plus a thin CLI:

- **`bifrost/core/clients/`** — one async HTTP client per external service
  (`gramps`, `immich`, `paperless`, `anthropic`, `gemini`). Each wraps auth and
  the service's quirks; methods are grown as modules need them.
- **`bifrost/modules/`** — the domain logic. Each module is an **async
  generator** that yields typed `SyncEvent`s. The same generator runs in preview
  (`apply=False`, emitting `would_create`/`would_update`) or apply
  (`apply=True`). Modules: `faces`, `sync_immich`, `sync_paperless`, `boundaries`,
  `citations`, `activity`, `idgen`, `ocr`, plus `import_legacy`.
- **`bifrost/web/`** — FastAPI app (`app.py`) holding the clients, the SQLite
  connection, config, and a cache dict on `app.state`. One router per surface
  under `routes/`; Jinja templates render a shell; the real UI is **Lit web
  components** (one `*-page.js` per surface) under `static/app/`.

**Frontend stack:** Lit 3 web components rendering into **light DOM** (so one
global stylesheet themes everything), a vendored Lit bundle + self-hosted fonts
(Space Grotesk headings / Space Mono body), an importmap, and **no build step**.
Visual language is Scandinavian-minimal with a light/dark theme. SVG icons are
used instead of glyphs for status (shape + color, for legibility).

**The event model.** `SyncEvent(kind, entity, action, source_id, gramps_id,
title, detail, data)` is the universal unit. `kind` ∈ started/item/summary/error;
`action` ∈ created/updated/skipped/failed and the `would_*` preview variants;
`data.cols` is a dict that the frontend renders as per-row table columns. Every
run is recorded to the `runs` / `run_events` tables for the audit trail.

---

## 5. The surfaces (what each tab does)

Reachable from the top nav at `:8800`:

- **Inbox (`/`)** — the home dashboard. Pending-work cards: faces to link,
  Paperless documents not yet synced, recent runs.
- **Faces (`/faces`)** — links Immich face clusters to Gramps people. Uses a
  per-(person, photo) padding model (a slider, default 15%) instead of
  operation buttons; the photo grid/detail draws rectangles on the image; one
  "Apply pending" bulk action. `person_links` (SQLite) is the source of truth,
  with a write-through `person_map.yaml` shim kept only until the legacy
  face-linker is retired.
- **Sync (`/sync`)** — the import engines, each a preview→apply panel:
  - *Paperless → Gramps*: tagged documents become Gramps media; a four-phase
    pipeline keeps media, versions, titles/dates, and transcriptions current.
  - *Immich → Gramps*: tagged photos become Gramps media with dates, GPS-based
    place links (closest tagged place ≤ 250 m), descriptions, and faces.
  - *Gemini OCR → Paperless*: documents you tag are transcribed by Gemini and
    written into the same Paperless document's text **in place**, then
    auto-tagged for transcription so the text flows on to a Gramps note.
  - A single-object transcription resync, and a "rewrite all transcription
    notes" maintenance pass.
  - On the preview, an optional **"Assign my own Gramps IDs"** checkbox lets you
    hand-pick the media id for new items.
- **Places (`/places`)** — OSM boundary management. Lists places, lets you add a
  relation/way URL inline, and generates the GeoJSON boundary (single or bulk)
  that the Gramps place-minimap overlay draws.
- **Citations (`/citations`)** — the Evidence-Explained citation generator.
  Start from a media object **or** cycle through uncited events; describe the
  record (freeform "dump" or a structured wizard); Claude composes the EE layers
  to the house style; review/edit; save creates the Repository→Source→Note→
  Citation chain and links it to the media and/or event.
- **Activity (`/activity`)** — an interactive productivity dashboard built from
  the Gramps transaction log: a stacked weekly chart of objects added/edited/
  deleted, a "This week" analytics view (with an optional Claude-written
  narrative), an event-citation-coverage chart, and per-class "Database size"
  sparklines.
- **IDs (`/idgen`)** — mints random-6 media ids ahead of time, **reserves** them
  (the sync auto-generator never reuses a reserved id, but you can type one in as
  a manual id), and tracks which were eventually minted. Supports the photo
  copy/verso naming scheme.

---

## 6. Data model (SQLite)

The database (append-only migrations in `core/db.py`, currently at version 4) is
a rebuildable cache + audit log — never the authoritative copy of anything that
also lives in a target system.

| Table | Purpose |
|---|---|
| `person_links` | Gramps person ↔ Immich face-cluster links (faces source of truth). |
| `face_pads` | Per-(person, photo) face bounding-box padding. |
| `minted_media` | Audit of every media id created, with its source system/id. |
| `doc_versions` | Paperless document checksums → change/version detection. |
| `transcription_state` | Transcription/translation notes tracked by content hash. |
| `reserved_ids` | UI-generated media ids reserved ahead of minting. |
| `ocr_state` | Documents already Gemini-OCR'd (so a run doesn't re-spend). |
| `runs` / `run_events` | Full history of every preview/apply run and its events. |

**Idempotency keys live in the target systems**, not here: Gramps media carry an
"Immich ID" / "Paperless ID" attribute; Paperless documents carry the Gramps id
in a custom field. That makes the SQLite cache disposable and reconstructable.

---

## 7. Key conventions Bifrost enforces

- **Media ID convention.** Bare random 6-character ids (safe alphabet, no
  I/O/L/0/1) are used **exclusively** for media objects — for deletion-collision
  safety and so a physical photo's verso can be labeled with six characters.
  Everything else (Citations, Sources, Repositories, Notes) mints sequentially in
  the tree's native pattern (C0001, S0001, …).
- **Copy / verso naming scheme.** Files and physical labels are named off the
  base media id with a category letter + 2-char code: `_o` original, `_c##` crop,
  `_d##` duplicate, `_v##` verso scan, `_a##` AI-edited. (See
  `MEDIA_ID_SCHEME.md`.)
- **Citation house style.** Composition follows Peter's US + Swedish style guides
  (data files appended to the LLM system prompt): two layers only (First/Short
  Reference Note), never a Source List Entry, citation date always blank,
  bracketed English glosses on foreign series names in the First Reference Note
  only, GPS-quality → Gramps confidence 0–4, `[NEEDED: …]` placeholders.
- **Transcriptions.** OCR text becomes a Gramps "Transcription" note; an English
  translation, when present, is separated by the delimiter
  `======== ENGLISH TRANSLATION ========`.

---

## 8. Notable integration mechanics

- **Paperless document versioning (3.0).** A document keeps its id and serves the
  *selected* version's file, so its checksum changes when you switch versions.
  Bifrost's version-sync detects that and repoints the Gramps media path, so
  Gramps renders the selected version. A cron wrapper (`versions_sync.sh`, every
  10 min) runs the versions-only pass unattended.
- **Gemini OCR in place.** Because Paperless's `content` field is API-writable,
  Bifrost transcribes a document and writes the text straight back into the same
  document (same id, no new document, no broken links), then stamps the
  transcription tag so the note flows to Gramps on the next sync. Preview is
  free; only apply calls Gemini.
- **Boundary overlay.** `osm-to-gramps` writes a GeoJSON sidecar per place; the
  same directory is mounted read-only into Gramps Web, whose place minimap draws
  the polygon via an injected `config.js`/`overlay.js`.
- **Gramps API quirks handled:** POST `/objects` 308-redirects (need
  `follow_redirects`); DELETE returns HTTP 500 but succeeds (a post-delete index
  error); token endpoint rate-limits (429 retry). After a delete, the search
  index is reconciled.

---

## 9. Migration story (strangler fig)

Bifrost is replacing the legacy tools one module at a time, leaving each legacy
tool untouched until its replacement is validated against it (a "golden-master"
gate: legacy `--dry-run` output must match Bifrost's preview on the same live
data). Phases: 0 foundation → 1 faces → 2 Immich sync → 3 Paperless +
transcriptions → 4 boundaries + citations → 5 retire the control-center. All
surfaces are live; the remaining cutover steps (disabling the systemd
face-linker, removing legacy jobs and the `person_map.yaml` shim, retiring
control-center) are deliberately held until Peter validates them, to avoid
dual-writer state in the meantime.

---

## 10. Deployment & operations

- **Runtime:** one Docker container (`bifrost`), built from the repo, port 8800
  bound to the tailnet IP + loopback only.
- **Config:** a single `config.yaml` at the repo root (mode 600, gitignored)
  holds every credential and setting — Gramps/Immich/Paperless/Anthropic/Gemini
  keys, sync tags, Paperless custom-field ids, the OCR tag, place service URL.
  A redacted `config.example.yaml` is committed. **Config is read at startup, so
  any change needs `docker compose restart`.**
- **Mounts:** `config.yaml` (ro), `./data` (the SQLite db), the GeoJSON
  boundaries dir (ro), and the legacy `person_map.yaml` (the Phase-1 shim).
- **Scheduled jobs (host cron):** `versions_sync.sh` every 10 min to propagate
  selected Paperless versions into Gramps.
- **CLI:** `bifrost doctor` (connectivity/auth check against all services) and
  `bifrost import-legacy` (load legacy state files into SQLite).
- **Repo:** `github.com/petermgrund/bifrost`.

---

## 11. Why it is used (the payoff)

Bifrost turns a fragile, multi-tool, manual process into a single reviewable
workflow:

- **One place** to see and approve every change before it touches the tree.
- **Better data, less effort:** Gemini reads documents Tesseract can't; Claude
  drafts house-style citations; GPS auto-links places; faces link from Immich;
  boundaries render on place maps — each as a preview→apply step.
- **Safe by construction:** idempotency keys in the target systems, a disposable
  SQLite cache, a full run audit log, honest error reporting, and a no-overwrite
  stance (a taken id is skipped, not clobbered).
- **One coherent UI** with a single mental model, consistent preview/apply
  semantics, and an accessibility-minded design.

It is the **curation half** of a longer-term goal — a unified ancestry
experience combining Immich, Paperless, and Gramps — and its core client library
is intended to feed the future presentation half as well.
