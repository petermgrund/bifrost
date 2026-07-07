# Immich image versioning

Status: **ALL PHASES BUILT (1–6b). Backend (1–6a) deployed + proven on real
data; 6b frontend (VERSIONS strip) written, awaiting a rebuild + Peter's visual
review. Cron not yet installed** (June 21 2026). This mirrors the existing
Paperless version-sync, adapted to Immich's very different asset model.

## 1. The problem

Immich (live **v2.7.5** on this Pi) has **no native image versioning**. Every
upload is its own immutable asset (UUID + base64 SHA-1 checksum). There is no
"one logical photo, many file-versions, pick the current one, keep history":

- **Non-destructive editing** (`/api/assets/{id}/edits`) is a single revertable
  layer limited to crop / rotate / mirror — not a multi-version history, and it
  cannot ingest a rescan or an externally AI-restored file.
- **`replaceAsset`** (`PUT /api/assets/{id}/original`) keeps the id but is
  **destructive** (old file gone) and is flagged `deprecated: true`. Do not use.
- **`getVersionHistory`** is the *server* upgrade chronology, not per-asset.

The only usable primitive is the **stack**: a group of independent assets under
one designated `primaryAssetId` (the cover); stack children are hidden from the
timeline. So versioning has to be a **bifrost-owned layer** on top of stacks —
which fits bifrost's principle (*connect/curate assets that already exist; never
create source material*).

## 2. Principles

1. **Three independent axes — never inferred from each other:**
   - *add-order* of assets in the stack (and Immich's "first-selected = primary"
     default) — purely mechanical.
   - *kind / which is the original* — provenance; only Peter knows it.
   - *which is displayed* in Gramps (the "current") — a deliberate choice.

   The first-added member may be a *derived* version; the newest may not be the
   wanted one. bifrost **never** guesses kind or current from order/recency.

2. **The Gramps base id and handle are frozen.** A version change only repoints
   the existing media's `path`/`mime` and its `"Immich ID"`/`"Immich URL"`
   attributes. Never mints a new id, never recreates (deletion-collision safety;
   the random-6 base id is written on physical versos — see `MEDIA_ID_SCHEME.md`).

3. **bifrost is the cockpit; Immich holds the durable state.** Peter picks the
   displayed version, marks the kind, and writes notes from bifrost's UI;
   bifrost *writes* the load-bearing facts into Immich and *reads* them back. A
   rebuild of bifrost's SQLite loses nothing important.

## 3. Where state lives

| Fact | Home (source of truth) | How bifrost touches it |
|------|------------------------|------------------------|
| Which assets are versions of one photo | **Immich stack** membership | `create_stack`, `get_stack`, `list_stacks` |
| Which version is **displayed** in Gramps | **Immich** `stack.primaryAssetId` | `set_stack_primary` (= `PUT /api/stacks/{id}`) |
| **Kind / original** of each member | **Immich tags** `Gramps/Role/{Original,AI,Crop,Duplicate,Verso}` | `tag_assets` / `untag_assets` (existing) |
| Base id, durable on the asset | **Immich tag** `Gramps/Base/<baseid>` on members | `tag_assets` |
| In-pipeline visibility | **Immich tag** `cfg.sync_tags` on every member | propagated by bifrost |
| Soft notes ("restored 2026", "crop for portrait") | **bifrost** `immich_version_members.label` | bifrost UI |
| Display order, sync cache | **bifrost** SQLite | — |

So everything needed to rebuild the version sets is recoverable from Immich
alone; bifrost owns only cosmetics.

## 4. SQLite (db.py migration #6, doc_versions/reserved_ids style)

```sql
CREATE TABLE immich_versions (
    gramps_id        TEXT PRIMARY KEY,   -- stable random-6 base id; the only real Gramps id
    stack_id         TEXT NOT NULL,      -- Immich stack uuid (lets us re-find the stack if the pointed asset is deleted)
    current_asset_id TEXT NOT NULL,      -- primaryAssetId we last repointed Gramps to
    current_checksum TEXT NOT NULL,      -- base64 SHA-1 of current asset; sanity/de-dup only, NOT the trigger
    member_count     INTEGER NOT NULL,   -- versions in the stack (UI "vN" badge)
    updated_at       TEXT NOT NULL
);

CREATE TABLE immich_version_members (
    gramps_id TEXT NOT NULL,             -- FK to the logical photo's base id
    asset_id  TEXT NOT NULL,             -- one stack member (distinct immutable asset)
    checksum  TEXT NOT NULL,
    role      TEXT,                       -- CACHE of the Gramps/Role/* Immich tag (source of truth is the tag)
    label     TEXT,                       -- bifrost-owned free-text note
    seq       INTEGER NOT NULL,          -- bifrost-owned display order
    PRIMARY KEY (gramps_id, asset_id)
);
```

`minted_media`, `reserved_ids`, and `idgen.py` are untouched — this feature only
repoints an existing base id.

## 5. Filing-suffix mapping (`MEDIA_ID_SCHEME.md`)

The suffix is **computed**, never inferred from position, and is filing-only
(for PC filenames / verso labels — never minted into Gramps):

- the **displayed** member (`= primaryAssetId`) → **bare** base id (`VGRN54`):
  "bare = what's on Gramps", which the repoint literally guarantees.
- a non-displayed member, by its `Gramps/Role/*` tag:
  `Original → _o`, `AI → _a##`, `Crop → _c##`, `Duplicate → _d##`, `Verso → _v##`.
- `##` is bifrost's 1-based index among same-role non-displayed members (by `seq`).

Promoting a different member swaps the roles automatically: the new primary
becomes bare; the member tagged `Original` (if not current) shows as `_o`.

## 6. Sync algorithm

A new **version phase** in `sync_immich.sync`, gated by `versions_only: bool`
(plumbed exactly like `sync_paperless.sync`). Preview (`apply=False`) emits
`would_update` / `baselined` and writes nothing; apply gates every write.

New `ImmichClient` methods (none exist today): `list_stacks` (`GET /api/stacks`),
`get_stack(id)` (`GET /api/stacks/{id}`), `set_stack_primary(stack_id, asset_id)`
(`PUT /api/stacks/{id}` `{primaryAssetId}`), `create_stack(asset_ids)`
(`POST /api/stacks`), and `create_tag(value)` (`POST /api/tags`, for minting the
`Gramps/Role/*` and `Gramps/Base/*` tags). Reuse `get_asset` (2.x returns nested
`stack` + `checksum`) and the existing `tag_assets`/`untag_assets`.

Per synced photo:

1. Build `synced = faces.synced_immich_media(gramps)` → `{asset_id: media}` keyed
   on the `"Immich ID"` attribute.
2. Resolve the stack: prefer the cached `immich_versions.stack_id` for this
   `gramps_id` (robust if the pointed asset was deleted); else `get_asset(asset_id)`
   and read `asset["stack"]`. If there is no stack → **skip** (single-asset media,
   out of scope, like an untracked Paperless doc). **Opt-in guard (see §11):** also
   skip a stack bifrost does not manage — no `immich_versions` row *and* no member
   carrying a `Gramps/Base/*` tag — so the ~256 pre-existing burst/RAW stacks are
   ignored until Peter opts the photo into versioning.
3. `primary = stack["primaryAssetId"]`. **Change signal = `primary` differs from
   the asset the Gramps media currently points at** (its `"Immich ID"` attr,
   i.e. the `asset_id` key) — *not* a checksum diff (Immich assets are immutable)
   and *not* recency.
   - **No divergence** (`primary == asset_id`): refresh the cache row + member
     list; no Gramps write. (First sight of an in-sync stack = baseline.)
   - **Divergence**: VERSION CHANGED → step 4.
4. **Repoint the SAME Gramps media** (mirrors `sync_paperless.py` phase 2):
   - `new = get_asset(primary)`; `new_path = translate_path(new["originalPath"], cfg.path_mappings)`;
     `new_mime = new.get("originalMimeType") or MIME_FALLBACKS[...]`.
   - **Guards (emit `failed`, do not write):** path-mapping fell through to the
     bare `immich/<file>` fallback (would 404 on the read-only mount); or
     `get_asset(primary)` 404s (deleted primary).
   - `media = gramps.get_media_by_gramps_id(gramps_id)` (GET-first). Missing →
     `failed` (never recreate).
   - In `media["attribute_list"]` set `"Immich ID" → primary` and `"Immich URL" →
     .../photos/{primary}`; set `path`/`mime` if changed; `media["change"] = int(utcnow)`;
     then **one** `gramps.update_media(media["handle"], media)` so attr + path never diverge.
5. **Face rects — clear honestly, re-derive best-effort:**
   - Port the Paperless clear: `gramps.get_media_backlinks(handle)` → for each
     backlinked object (`BACKLINK_OBJ_TYPES`) null the `mref["rect"]` where
     `ref == handle` → `update_object`. Count cleared.
   - Then attempt re-derive: for `face in immich.get_faces(primary)`, map person
     via `faces.list_links`, `pad = faces.effective_pad(...)`, `faces.apply_face(..., media_handle=handle)`.
     This refills faces of **named** people Immich re-recognized on the new asset
     (person id carries even though the face-instance id does not); the rest are
     **pending**. Report `faces: N cleared / M re-derived / K pending` — never
     leave a NULL whole-image rect silently.
6. On apply: `INSERT OR REPLACE` `immich_versions`; refresh `immich_version_members`
   from the stack (cache each member's `Gramps/Role/*` tag into `role`, keep
   `label`). Emit `SyncEvent(kind="item", entity="media", action="updated"/"would_update",
   gramps_id=..., data={"cols": {...}})` — the shape the Sync UI already renders.

### Tag propagation (the trap to avoid)

`sync_immich` builds its asset universe from `search_assets_by_tag(cfg.sync_tags)`,
and `faces.synced_immich_media` keys on `"Immich ID"`. A freshly stacked version
is **untagged**, so the full sync can't see it and the `TAG_SYNC_*` gates would
regress pads/dates/places. Therefore whenever bifrost touches a stack (detect,
adopt, or promote) it **propagates `cfg.sync_tags` and writes `Gramps/Base/<id>`
onto every member**. The sync follows the *stack*, not just the tagged seed.

## 7. Automation

`immich_versions_sync.sh` — a clone of `versions_sync.sh`: `flock` on its own
lock, `curl POST http://127.0.0.1:8800/sync/api/immich/apply -d '{"versions_only":true}'`,
append ISO-stamped lines to `immich_versions_sync.log` (tail-truncate to 500),
cron offset from Paperless (e.g. `3,13,23,33,43,53 * * * *` or every 30 min).
Plumbing: `versions_only` on `ImmichBody` (`web/routes/sync.py`), job name
`sync.immich.versions`, passed through to `sync_immich.sync`. The `versions_only`
path runs only the version phase (no create / date / place / description work),
so it is safe unattended — the trigger is the deliberate `primaryAssetId`, not an
auto-assignable field.

## 8. UI — VERSIONS strip (one surface, no button soup)

A photo whose asset has a non-null `stack` shows a `vN` badge in the Photos grid
(`faces.photo_listing`). Its detail panel gains a **VERSIONS** strip:

- member thumbnails (`immich.asset_thumbnail`) in `seq` order; the displayed one
  ringed and labelled "shown in Gramps".
- **Set displayed** per member → `set_stack_primary` **and** a scoped single-photo
  version apply inline (repoint + face refresh on the spot, like `paperless_resync_media`).
- **Kind** chip per member (Original / AI / Crop / Duplicate / Verso) → bifrost
  writes the `Gramps/Role/*` tag to Immich.
- **Label** inline free-text (bifrost-owned).
- **Adopt a version** folds an already-uploaded Immich asset into the stack (and
  tags it) — never an upload.
- One quiet note: *"changing the displayed version replaces the image; face boxes
  are re-detected — any that don't match need a quick look."*

## 9. Build plan (additive, strangler-fig)

Golden-master gate every step: snapshot a Gramps subset (media `path`/`mime`/
`gramps_id`/`handle`/attrs + backlinked rects); after each phase the **only**
permitted diff is `path`/`mime`/`Immich ID`/`Immich URL`/`change` + nulled rects
on photos whose primary actually changed. `gramps_id`/`handle` must never appear.
(Pi can't render web UIs headlessly — verify via curl/preview events + Peter looks.)

1. ✅ **Schema + client (read-only)** (June 21 2026). Migration #6; stack/tag
   client methods; `list_stacks`/`get_stack` exercised against the live v2.7.5
   server. See §11.
2. ✅ **Detect + baseline, preview-only** (June 21 2026). Version phase wired to
   `versions_only`; `_immich_job` + `ImmichBody.versions_only` plumbed through the
   route. Writes NOTHING regardless of `apply` (repoint lands in phase 3). The
   opt-in guard (`_stack_is_managed`) ignores unmanaged stacks; detection is the
   stack `primaryAssetId` vs the asset the Gramps media points at. See §12.
3. ✅ **Repoint apply** (June 21 2026). `immich_versions` persistence (baseline +
   on repoint) via `_set_iversion`; `update_media` repoint (base id/handle frozen,
   only path/mime + Immich ID/URL attrs change); face rects **cleared & left
   pending** (no re-derive). Guards: unmapped path + deleted primary → `failed`.
   See §13.
4. ✅ **Tag propagation + members** (June 21 2026). `_persist_stack` propagates
   `cfg.sync_tags` + `Gramps/Base/<id>` onto every member on baseline / repoint /
   membership-change, and fills `immich_version_members`. The "adopt" UI primitive
   (fold an existing asset into a managed stack) moves to phase 6 where it's wired.
   See §14.
5. ✅ **Best-effort face re-derive + cron** (June 21 2026). Re-derive layered
   over the clear (re-detect on the new primary → map to linked people →
   `apply_face`; report cleared/re-derived/pending). `immich_versions_sync.sh`
   shipped (clone of `versions_sync.sh`). See §15.
6. **UI.** Split:
   - ✅ **6a — version API** (June 21 2026). `modules/sync_immich.py`: `version_set`,
     `set_role`, `set_label`, `adopt`; `web/routes/versions.py` (prefix `/versions`):
     `GET /api/by-asset/{id}`, `POST /api/set-displayed`, `/set-role`, `/set-label`,
     `/adopt`. See §16.
   - ✅ **6b — frontend** (June 21 2026, awaiting visual review). `vN` badge in the
     Photos grid + a VERSIONS strip in the detail panel (per-member thumbnail,
     Set-displayed, role chips, Note field). Adopt UI deferred. See §18.

## 10. Decision log (June 21 2026)

- Displayed-version changes made in Immich flow back to Gramps on the next cron
  (bifrost-promote and Immich-cover-change are the same `primaryAssetId`).
- Face rects: auto best-effort re-derive on the timer, report cleared/re-derived/pending.
- Keep every version in the stack forever (no auto-prune).
- Peter stacks in the Immich web UI; bifrost auto-propagates the sync tag (no
  hand-tagging needed except a brand-new photo entering the pipeline).
- Kind/original = Immich tags `Gramps/Role/*` (bifrost writes them); soft notes =
  bifrost labels. bifrost is the cockpit; Immich holds the durable state.

## 11. Phase 1 verification (June 21 2026, against the live server)

Migration #6 + the read-only `ImmichClient` stack methods were exercised live.
All confirmed:

- **Migration #6 applies cleanly** — `schema_version` → 6; both tables created
  with the columns above.
- **Stack JSON shape** (`GET /stacks`, `GET /stacks/{id}`): `{id, primaryAssetId,
  assets: [{id, type, originalFileName, checksum, ...}]}`. So `primaryAssetId` is
  the displayed pointer and each member carries `id` + base64-SHA-1 `checksum`,
  exactly as the design assumes. (The OpenAPI lives at `/api/spec.json`; its path
  keys drop the `/api` prefix the client adds.)
- **Write DTOs confirmed** (not called in phase 1): `POST /stacks` `StackCreateDto
  {assetIds}` (first = primary); `PUT /stacks/{id}` `StackUpdateDto {primaryAssetId}`;
  `PUT /tags` `TagUpsertDto {tags}` (creates the `Gramps/Role/*` hierarchy). Bonus
  `DELETE /stacks/{id}/assets/{assetId}` removes a member without deleting the asset.

### Important finding — the server already has **256 stacks**

These pre-date the feature and are almost certainly bursts / sequential scans /
RAW+JPEG pairs, **not** deliberate genealogical version sets (first one seen:
`PB011.jpg` + `PB012.jpg`). Consequence: the version phase must NOT treat every
stack containing a synced photo as a version set, or it could repoint a Gramps
media to a burst sibling.

**Guard (added to §6):** a stack is a version set only if **bifrost manages it** —
i.e. a member carries the `Gramps/Base/<id>` tag (written when Peter opts the
photo into versioning from the VERSIONS strip) or there is an `immich_versions`
row for that `gramps_id`. Pre-existing burst/RAW stacks carry neither and are
silently ignored. Opting a photo in is a one-time action; thereafter bifrost
auto-discovers new members of that managed stack.

RESOLVED (Peter, June 21 2026): the 256 stacks are bursts / RAW / sequential
scans — **not** version sets. Phase 2 uses the opt-in marker and ignores all
existing stacks; no backfill helper needed.

## 12. Phase 2 verification (June 21 2026)

What landed (all additive; the running container is unaffected until rebuilt):

- `sync_immich.sync` gained `versions_only: bool = False`; the create loop, the
  refresh passes, and the place fetch are gated `not versions_only`. A new
  **version phase** runs in both modes (and is the only work in `versions_only`).
- Helpers `_get_iversion` and `_stack_is_managed` (opt-in guard); constant
  `TAG_GRAMPS_BASE_PREFIX = "gramps/base/"`.
- Route: `_immich_job` + `ImmichBody.versions_only`, plumbed through both
  `/api/immich/preview` and `/api/immich/apply` (job names `sync.immich.versions[.preview]`).
- **Detection only — writes nothing** even under `apply` (no `update_media`, no
  `immich_versions` rows). Phase 3 adds those behind `if apply:`.

Verified:

- **Live `versions_only` preview** against the real server: 61 synced photos, 0
  in any stack → `stacks_seen=0`, no events, no writes (touched a throwaway temp
  DB only). Confirms the 256 burst stacks are entirely unsynced and out of scope.
- **Stub-driven unit tests** (`tests/test_sync_immich.py`, run through the real
  generator, no live calls) cover every branch: unmanaged-stack skip, managed
  baseline, divergence → one `would_update` (with `from`/`to`/`gramps_id`),
  managed-via-DB-row without a tag, and non-stacked-photo ignored. 41 passed.
- A live fixture (temporarily stacking a real photo to exercise detection
  end-to-end) was intentionally NOT run — it writes to the production Immich,
  outside the preview-only scope; the stub tests cover the same branches.

NOTE: detection compares `stack.primaryAssetId` to the asset the Gramps media
points at (the `"Immich ID"` attr = the `synced` key). It works while that
pointed asset stays tagged + a stack member (true until repoint); the phase-4
tag propagation is what keeps it working after a repoint and on full syncs.
The deleted-primary / path-fallback guards belong to the phase-3 repoint.

## 13. Phase 3 verification (June 21 2026)

What landed (still additive; the running container is unaffected until rebuilt):

- Write helper `_set_iversion` (INSERT OR REPLACE, `doc_versions` style);
  `_set_media_attr` (in-place attr overwrite/append); `_path_mapping_matches`
  (fail fast rather than repoint to a path that 404s on the read-only mount);
  constant `BACKLINK_OBJ_TYPES`.
- The version phase now, under `apply`: persists the **baseline** row when a
  managed in-sync stack is first seen; on **divergence**, repoints the SAME
  Gramps media (`update_media` — base id + handle frozen; only `path`/`mime` +
  the `Immich ID`/`Immich URL` attrs change), clears every backlinked face
  `rect` (left pending; re-derive is phase 5), and writes the `immich_versions`
  row pointing at the new primary. Preview still writes nothing.
- Guards emit `failed` (no writes): primary unfetchable (deleted), or its
  `originalPath` under no configured mount.

Verified:

- **8 stub-driven tests** through the real generator (no live calls): baseline
  persists the row; divergence *preview* writes nothing; divergence *apply*
  repoints in place (handle frozen, `Immich ID`→new, path/mime swapped),
  clears the backlinked person's rect, and persists `current_asset_id`=new;
  unmapped-path and deleted-primary both `failed` with zero writes; managed-via
  -DB-row and unmanaged/non-stacked behave as before. Full suite 44 passed (the
  1 failure is the pre-existing stale `test_citations` schema test).
- **Live `versions_only` preview** against the real server runs the phase-3 code
  with no runtime errors: 0 item events, all counts zero (no synced photo is in
  a stack), no writes (temp DB only).

LIMITATION carried to phase 4: the repoint does not yet propagate `cfg.sync_tags`
to the new primary, so after a repoint a *full* (non-versions_only) sync won't
refresh that photo's date/place/description, and further promotions won't be
detected, until the new primary is tagged. Not deployed; safe to defer to phase 4.

## 14. Phase 4 verification (June 21 2026)

Resolves the phase-3 limitation above. New helper `_persist_stack(immich, conn,
cfg, gramps_id, stack_id, current_asset_id, current_checksum)` (apply-only),
called from the version phase on **baseline**, **repoint**, and **membership
change** (stored `member_count` ≠ live `assetCount`):

- `get_stack(stack_id)` → enumerate members; `upsert_tags(["Gramps/Base/<id>"])`;
  then `tag_assets` each of `cfg.sync_tags` + the base tag onto **every** member.
  This is the opt-in completion (one manually-tagged member → bifrost tags the
  rest), the post-repoint fix (the new primary is now in the full-sync universe),
  and the self-describing marker (rebuildable from Immich if the DB is lost).
- Refreshes `immich_version_members` (one row per member: `asset_id`, `checksum`,
  `seq`; `role`/`label` stay NULL until the phase-6 UI sets them) and upserts the
  `immich_versions` row.

Verified (stub tests, full suite **46 passed**):

- **Baseline apply** → row + members persisted; sync tag AND `Gramps/Base/<id>`
  propagated onto every member.
- **Divergence apply** → repoint in place (handle/base id frozen) + face rect
  cleared + row repointed to the new primary, AND the new primary is now tagged
  into the sync universe (regression fixed).
- **Member added** to a managed in-sync stack → re-propagation tags the new
  member, `member_count` and the members table refresh.
- Preview still writes nothing (no `tag_assets`, no rows); unmapped-path and
  deleted-primary still `fail` with zero writes/tags.

DEVIATION from the original plan: the "adopt a version" primitive (group an
existing asset into a managed stack from Bifrost) is deferred to phase 6, where
the UI that calls it lives — bootstrapping today is "stack in Immich + tag one
member `Gramps/Base/<id>`", which `_persist_stack` then completes.

NOT YET DEPLOYED: the running container has phase-3 code. A rebuild
(`docker compose build bifrost && up -d`) is needed for `_persist_stack` to run;
until then a baseline/repoint persists the row but does not propagate tags.

## 15. Phase 5 verification + deploy (June 21 2026)

**Best-effort face re-derivation** in the repoint branch (apply only): after
clearing the now-invalid rects, re-detect faces on the new primary via
`immich.get_faces(primary)`, map each to a linked person (`by_immich` from
`faces.list_links`), compute the per-asset pad (`faces.effective_pad`, default
unless the new primary carries `Sync/ManualFaces`), and `faces.apply_face`
re-draws the rect on the SAME person MediaRef. Failures are swallowed (left
pending). The event/summary report `N cleared / M re-derived / K pending`
(`pending = max(0, cleared − re_derived)`), with new counts `faces_cleared` /
`faces_rederived`. Honest contract: only faces of LINKED people that Immich
re-recognizes refill; everything else stays pending (never mis-placed).

**Cron** `immich_versions_sync.sh` (clone of `versions_sync.sh`): `flock`, curl
`POST /sync/api/immich/apply {versions_only:true}`, log
`versions_updated/faces_cleared/faces_rederived/errors` to
`immich_versions_sync.log` (tail-truncated to 500 lines). Route plumbing was done
in phase 2; only stacks Bifrost manages are ever touched.

Verified (stub tests, full suite **47 passed**): a linked person whose face
Immich still detects on the new primary is cleared then re-drawn to the new box
(pad 0.15 → `[7,7,33,33]`), reported `1 cleared / 1 re-derived / 0 pending`;
preview still does no re-derivation/writes; the script passes `bash -n`.

### Deploy (one step, when ready)

1. `cd /opt/stacks/bifrost && docker compose build bifrost && docker compose up -d bifrost`
   — bakes phases 1–5 into the running image.
2. Install the cron, offset from the Paperless one (`*/10`):
   `5,15,25,35,45,55 * * * * /opt/stacks/bifrost/immich_versions_sync.sh`
   Until a photo is opted in (a stack member tagged `Gramps/Base/<id>`), every
   run is a no-op (`stacks_managed=0`), so installing it early is safe.

The feature is only usable end-to-end once phase 6 (the VERSIONS strip + opt-in
/ promote / role-tag UI) lands — or, to bootstrap before then: stack versions in
Immich and manually tag one member `Gramps/Base/<the gramps id>`.

## 16. Phase 6a — version-management API (June 21 2026)

The backend the VERSIONS strip will call. `modules/sync_immich.py`:

- `version_set(immich, gramps, conn, cfg, asset_id)` → `{versioned, managed,
  gramps_id, stack_id, primary_asset_id, members:[{asset_id, filename,
  is_displayed, role, label, seq, thumb_url}]}`. Merges the live stack with the
  members cache. `versioned=False` when not in a stack.
- `set_role(immich, conn, gramps_id, asset_id, role)` — writes the durable
  `Gramps/Role/*` tag (removing any prior role tag) and mirrors it into the
  cache. `VERSION_ROLES = {original, ai, crop, duplicate, verso}`; `role=None`
  clears. `_persist_stack` now PRESERVES role/label across refreshes.
- `set_label(conn, gramps_id, asset_id, label)` — Bifrost-owned free-text note.
- `adopt(immich, conn, cfg, gramps_id, displayed_asset_id, add_asset_ids)` —
  `create_stack([displayed, *adds])` (displayed first = stays primary) then
  `_persist_stack` (tags + baseline). Assumes displayed isn't already stacked.

`web/routes/versions.py` (prefix `/versions`, registered in app.py): `GET
/api/by-asset/{asset_id}`, `POST /api/set-displayed` ({stack_id, member_id} →
`set_stack_primary` + a `versions_only` apply that repoints Gramps), `/set-role`,
`/set-label`, `/adopt`.

Verified: full suite **54 passed** — version_set merges live+cache; set_role
swaps the role tag + updates the cache and rejects unknown roles; set_label
trims/updates; adopt creates the stack, tags both members, and baselines.

NOTE: `set-displayed` runs the whole `versions_only` apply (all managed stacks),
not a single-photo scope — fine at this scale; a `single_asset` scope is a future
optimization. Endpoints are on the working tree, NOT deployed (need a rebuild).

## 17. Live proof + opt-in detection fix (June 21 2026)

First real opt-in (Gramps `AHRZ6Q`, stack of `36_a02.jpg` [displayed] + `36_a01.png`)
surfaced a detection bug: the `Gramps/Base/AHRZ6Q` tag was placed on the
NON-displayed member (`36_a01.png`), but `_stack_is_managed` only inspected the
displayed/synced asset's own tags → `managed=false`, photo skipped. The design
says "tag ANY member", so this was an implementation gap.

FIX: `_stack_is_managed` is now `async` and adds a third clause —
`await immich.resolve_tag_id(f"Gramps/Base/{gramps_id}") is not None`. The tag
value encodes the gramps id, so the tag *existing* is the opt-in signal,
independent of which member carries it. Both call sites (version phase,
`version_set`) now `await` it.

Verified live (read-only, working-tree code): `version_set` → `managed=true`;
`versions_only` preview → `stacks_seen=1, stacks_managed=1, baselined=1`, no
writes. Full suite **55 passed** (added `test_version_managed_via_optin_tag_on
_other_member`). The repoint is not yet proven end-to-end (needs a deployed
build + a promotion). LESSON: "prove on real data first" caught this before the
cron could silently skip every opted-in photo.

[UPDATE: repoint proven end-to-end same day — see the decision log / §15-17 notes.
Backend fully validated on Gramps `AHRZ6Q`: repointed to `36_a01.png`, base id +
handle frozen, face re-derived. Then 6b frontend was built.]

## 18. Phase 6b — frontend VERSIONS strip (June 21 2026, awaiting review)

All in the existing Faces page (`web/static/app/faces-page.js`) + `bifrost.css`;
no new components or npm build (uses `@material/web` already in the bundle).

- **Grid badge**: `photo_listing` now adds `version_count` per photo (one cheap
  `immich_versions` DB query, no Immich calls); `photoCard` shows `vN` when > 1.
- **VERSIONS strip** in the detail overlay (below the image/faces body): lazy
  `GET /versions/api/by-asset/{asset_id}` on open (`loadVersions`). If the photo
  is in a stack but unmanaged, shows the opt-in hint (`tag Gramps/Base/<id>`).
  If managed: one card per member — thumbnail, filename, the displayed one ringed
  + "● shown in Gramps", a "Set displayed" button on the others, a role
  `md-chip-set` (Original/AI/Crop/Duplicate/Verso, click active to clear), and a
  Note `md-outlined-text-field`.
- **Actions**: `setDisplayed` → `POST /set-displayed` then refresh strip + listing;
  `setRole` → `POST /set-role` (toggle); `setVersionLabel` → `POST /set-label`.
  `closeDetail` clears `versionSet`.

Verified: ES-module syntax check passes; full suite 55 passes. NOT visually
verified (Pi can't render headlessly) and NOT deployed — needs
`docker compose build bifrost && up -d`, then open Faces → Photos → click the
opted-in photo. Adopt-a-version UI and a single-photo `set-displayed` scope are
deferred follow-ups.
