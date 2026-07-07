# Bifrost

*The bridge between realms: one console for everything Gramps.*

One web console for curating the Grund Digital Archive's Gramps tree — a
switchboard between Gramps Web and the services around it: Paperless → Gramps
sync, Gemini OCR transcription, EE-style citations, and OSM place boundaries.

**Stack:** FastAPI + SQLite backend; Lit light-DOM components on **BeerCSS**
(vendored in `bifrost/web/static/vendor/`, no build step, offline).

**UI conventions** — the UI is ONE page: a stack of `<details>` section
expanders in the Gramps-Web settings style, one per operation. Every section
is built from the same shared kit in `static/app/core.js`, whose header
comment is the normative spec: `h6` stanza headings, one `nav.wrap` control
row (`field()` → `chip()` filters with counts → `btn()` → `statusLine()`),
plain sentence-case tables with `emptyRow()` empty states, busy-guarded
buttons with gerund labels, and every outcome through `statusLine()`. No
cards, no tabs, no custom CSS beyond the small brand layer in `bifrost.css`;
buttons are one uniform filled style via `btn()` — order conveys emphasis,
never color.

**2026-07-06 — ID feature removed.** The IDs tab (reserved-id ledger, the
"assign my own Gramps IDs" switch on the Sync preview, and the a-series scan
register) is gone — media ids are simply auto-minted random-6 codes from the
safe alphabet (`core/ids.py`, see `docs/MEDIA_ID_SCHEME.md`), and the scan
register lives with `/opt/stacks/archive-scheme/SCHEME.md`. Dormant DB tables
(`reserved_ids`, `scan_register`) are kept — no data was deleted.

**2026-07-01 — Immich integration removed.** The Immich sync, faces, and
stack-versioning modules are gone; archival photos move to **ArchivesSpace**
(see `/opt/stacks/archive-scheme/SCHEME.md`), and an ArchivesSpace source
module will take the Immich slot. The standalone `face-linker.service` (:8767)
remains the face-linking tool. Dormant DB tables (`person_links`, `face_pads`,
`immich_versions*`, immich rows in `minted_media`) are kept — no data was
deleted. `docs/IMMICH_VERSIONING.md` is retained as a design reference for the
removed feature.

See [docs/OVERVIEW.md](docs/OVERVIEW.md) for what each section does and
[docs/DESIGN.md](docs/DESIGN.md) for the original architecture (partly
historical — see its update banners).
