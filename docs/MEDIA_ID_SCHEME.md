# Media ID & copy naming scheme

Every image media object in Gramps gets a **random‑6 base id** from the safe
alphabet `ABCDEFGHJKMNPQRSTUVWXYZ23456789` (no `I O L 0 1` — unambiguous when
hand‑written on a photo verso). Example base id: `VGRN54`. These are minted by
Bifrost (the Sync flow, or reserved ahead of time in the **IDs** tab).

Copies, crops, and edits that live on the personal computer — and labels on the
backs of physical photos — are named off that base id with a **category letter**
plus a uniform **2‑char code** from the same safe alphabet. The category letter
(not the length) tells you what kind of copy it is.

| Name | Means | Where it applies |
|------|-------|------------------|
| `VGRN54.jpg` (bare) | The exact copy that is on Gramps Web — could be original, edited, derivative, AI, any combo. | PC files; the canonical physical print |
| `VGRN54_o.jpg` | The **original**, unedited version. Only exists when the Gramps copy is *not* itself the original. | PC files; the physical original if Gramps shows an edited version |
| `VGRN54_c##.jpg` | A version **cropped / derived** from the full image. | PC files only |
| `VGRN54_d##.jpg` | A **duplicate** of the full image (same content, different file or print). | PC files; **additional physical prints** |
| `VGRN54_v##.jpg` | A **scan of the verso** (back side) of a physical print — handwriting, stamps, dates. | PC files only |
| `VGRN54_a##.jpg` | An **AI‑edited** version (only that it was AI‑edited — the kind of edit is not tracked). | PC files only |

`##` = a plain decimal ordinal `01`–`99` *(amended 2026-07-01 — SCHEME.md §1)*.
The safe alphabet exists for the handwritten 6-char base; suffixes are
machine-only filing and never appear alone on a verso, so ordinary numbers are
clearer (`_a01` was already the de-facto practice).

## Rules

- **Bare = what's on Gramps.** The no‑suffix file mirrors whatever the Gramps
  media object currently shows.
- **`_o` only when needed.** If the Gramps copy is itself the unedited original,
  that *is* the bare file — there is no separate `_o`. Use `_o` only when the
  Gramps copy has been edited/cropped/AI'd and you're keeping the untouched
  original alongside it.
- **Verso labeling.** A physical photo's back gets the **base id** for the
  canonical print, or `_d##` for each additional physical copy of the same
  image. Crops (`_c##`), verso *scans* (`_v##`), and AI edits (`_a##`) are
  digital files and never appear written on a verso — what you write on the
  back is the base id (or `_d##`); a scan of that back is then filed as `_v##`.
- **Combos.** A file that is several things at once takes the dominant
  transformation's letter (rare; not worth a combinatorial scheme).

## Where the base ids come from

- Auto‑minted during an Immich/Paperless sync, or
- Reserved ahead of time in the **IDs** tab so you can write them on versos /
  name files before syncing, then type them in as a manual id on the Sync
  preview ("Assign my own Gramps IDs"). Reserved ids are never auto‑assigned to
  some other asset.

The suffix codes (`_o`, `_c##`, `_d##`, `_a##`) are a personal filing
convention — they are **not** minted into Gramps and not tracked in Bifrost's
database. Only the base id is a real Gramps object id.

## Not to be confused with scan numbers

The base id identifies an **object** (the photograph, front and back together).
A **scan number** (`a000277`) identifies one **capture file** in the a-series
digitization log — masters, the `archive-static/a0/` web copies, contact
sheets, and ArchivesSpace digital objects are named/identified by scan number,
while the object id names the item record (AS `component_id`, Gramps media id,
the penciled verso). One object commonly has two scan numbers (recto + verso).
The register lives in Bifrost (`scan_register`, IDs tab / `/idgen/api/scans`);
the full three-register scheme is `/opt/stacks/archive-scheme/SCHEME.md`.
