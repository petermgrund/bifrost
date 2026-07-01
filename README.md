# Bifrost

*The bridge between realms: one console for everything Gramps.*

One web console for curating the Grund Digital Archive's Gramps tree:
Paperless → Gramps sync, Gemini OCR transcription, EE-style citations, OSM
place boundaries, and the ID registers (random-6 media ids + the a-series
scan register).

**Stack:** FastAPI + SQLite backend; Lit light-DOM components on **BeerCSS**
(vendored in `bifrost/web/static/vendor/`, no build step, offline).

**2026-07-01 — Immich integration removed.** The Immich sync, faces, and
stack-versioning modules are gone; archival photos move to **ArchivesSpace**
(see `/opt/stacks/archive-scheme/SCHEME.md`), and an ArchivesSpace source
module will take the Immich slot. The standalone `face-linker.service` (:8767)
remains the face-linking tool. Dormant DB tables (`person_links`, `face_pads`,
`immich_versions*`, immich rows in `minted_media`) are kept — no data was
deleted. `docs/IMMICH_VERSIONING.md` is retained as a design reference for the
removed feature.

See [docs/DESIGN.md](docs/DESIGN.md) for the original architecture (partly
historical — it predates the Immich removal and the BeerCSS UI).
