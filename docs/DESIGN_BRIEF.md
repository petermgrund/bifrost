# Bifrost — Design Brief (wireframe-first redesign)

A handoff brief for a UI/UX redesign. **Start with low-fidelity wireframes**
(structure, IA, component placement) before any visual polish. This is a
**UI/UX-only** effort — the backend, APIs and data flows are settled and stay
as-is; the output should be implementable in the existing front-end stack
(see Constraints).

---

## 1. What Bifrost is

Bifrost is a single self-hosted web app — the **curation console** for one
person's genealogy stack. It exists so that getting family-history records into
a **Gramps** family tree, and keeping that tree rich and well-cited, doesn't
require hand-jockeying three separate tools. It orchestrates flows between:

- **Gramps Web** — the family tree (people, events, places, sources, citations,
  media, notes). The source of truth.
- **Paperless-ngx** — the document archive (scanned records, certificates, books).
- **Immich** — the photo library (with facial recognition).

Bifrost reads from and writes to these via their APIs; it is the connective
tissue and the human review surface.

## 2. Who it's for

A single expert user: a technical genealogy hobbyist and self-hoster
(comfortable with Python/Docker/REST). It runs privately on a Raspberry Pi
(Tailscale-only). It is a **power tool for one expert**, used at a desk in a
desktop browser, in focused sessions — not a consumer app, not mobile-first.

Taste: **succinct, no filler, direct manipulation, one mental model, dense but
calm, and above all intuitive.** Things should be where you'd expect them.

Data scale is personal: ~150 people, ~280 events, ~240 media, ~100 places,
~65 sources/citations. Small enough that everything can be listed/searched;
no need for heavy pagination/virtualization.

## 3. Information architecture (current)

Top app bar (brand + theme toggle) over a **grouped left nav drawer**:

- **Overview** → Home
- **Add** → Upload · Transcribe · Sync  *(the ingest pipeline, in order)*
- **Curate** → Faces · Citations
- **Tools** → Places · Activity · IDs

The grouping mirrors the workflow: *bring records in → enrich the tree →
inspect/utility.* Active destination is indicated.

## 4. The surfaces (content inventory per page)

- **Home (Overview).** "Needs attention" — a short list of pending work across
  all surfaces (e.g. *12 faces to link*, *3 documents to sync*, *8 events with no
  citation*), each linking to the relevant page. Plus "Recent runs" — a log of
  recent operations (status · task · result · when).

- **Upload (Add).** A **multi-step wizard**: (1) *Start* — drop a new file OR pick
  an existing Paperless document; (2) *Edit* — a two-pane screen: live document
  preview on one side, a metadata form on the other, with an "autofill from house
  style" action; (3) *Citation* — describe the record, an LLM drafts a citation,
  review and save, optionally attaching it to an event.

- **Transcribe (Add).** Run Gemini OCR over tagged documents (image → text);
  plus two lower-emphasis "maintenance" tasks (resync one document's
  transcription; rewrite all transcription notes).

- **Sync (Add).** Two "preview → apply" panels: *Paperless → Gramps* and
  *Immich → Gramps*. Each previews a dry-run (a results table of would-create /
  update / skip rows), then applies. An optional "assign my own IDs" toggle.

- **Faces (Curate).** Link Immich-detected faces to Gramps people. A photo grid
  → a two-pane detail (the image with face boxes drawn on it + a list of faces to
  name/link), a per-face padding slider, and a single bulk "apply pending" action.

- **Citations (Curate).** Compose Evidence-Explained citations. A **wizard**: pick
  a media object or an uncited event → write a freeform description ("dump") →
  an LLM drafts the source + citation + notes (a full reference note, a short one,
  and a research abstract) → review/edit the draft → save into Gramps, attaching
  the media and (optionally) an event.

- **Places (Tools).** A table of Gramps places; for each, generate/regenerate an
  OpenStreetMap boundary overlay; a bulk "generate missing" action; status per row.

- **Activity (Tools).** A read-only dashboard: weekly object-change charts, an
  event-citation-coverage chart, database-size sparklines, and a "this week"
  detail list. Has its own sub-tabs.

- **IDs (Tools).** Mint and track random-6 media IDs through a lifecycle
  (reserved → assigned → minted), for labelling physical photos. A generator
  control + a filterable table with per-row actions.

## 5. Recurring interaction patterns (design these as reusable parts)

1. **Preview → Apply.** The dominant write pattern: a dry-run preview renders a
   **results table** (rows grouped by entity: *action · what · columns · detail*,
   then a one-line summary), and only then can the user Apply. Used on Sync,
   Transcribe, Places, etc.
2. **Multi-step wizard** (Upload, Citations): a step indicator + back/next; each
   step is a focused screen.
3. **Two-pane review** (Faces, Upload-Edit): media/preview on one side, the thing
   you act on (faces / a form) on the other.
4. **Filterable list + per-row actions** (IDs, Places, Faces grid, the
   existing-document picker).
5. **Empty / loading / error / "all caught up"** states — every async surface
   needs them.

## 6. Constraints (the design must be implementable in these — non-negotiable)

- **No build step.** Plain ES modules + vendored **Lit** web components, served
  static. No React, no bundler, no npm component library to install. Whatever the
  design specifies must be expressible as hand-written semantic HTML + CSS.
- **One global stylesheet** of CSS custom-property **tokens** (`bifrost.css`);
  components are light-DOM and styled by shared class names. The design should
  define a **token set + a class-based component kit**, not bespoke per-page CSS.
- **Self-hosted, private, offline.** No runtime CDNs. Fonts are self-hosted
  (currently **Space Grotesk** for headings, **Space Mono** for body — keep these
  unless there's a strong reason; a previous switch to Roboto was rejected).
- **Light + dark themes**, driven by tokens (system preference + a manual toggle).
- **Desktop-first.** Responsive down to a tablet is a bonus, not the goal.
- Icons are small inline SVGs (no icon-font dependency).

## 7. Already decided (use as the starting point, not constraints to relitigate)

- A **Material 3 *appearance*** — M3 color roles, tonal surfaces, rounded shapes,
  pill buttons, the M3 type scale — but **appearance only**: no spring/physics
  motion, no shape-morphing, no official component library. Open to refinement.
- **Design principles to enforce on every page:**
  1. Fixed **card anatomy**: title → description → content → **action row**.
  2. **Actions cluster** (bottom-left); exactly one filled *primary* action;
     nothing flung to the opposite edge.
  3. **Options ≠ actions**: an on/off setting is a labelled checkbox grouped with
     what it affects — never a stray button.
  4. **One component per concept**: segmented control = choose-one-of-N;
     checkbox = option; chips = multi-select filter; filled button = the single
     primary action.
  5. Consistent spacing rhythm and left alignment.

## 8. Problems to solve (why we're redesigning)

The app works, but its **composition is ad hoc** — pages were laid out
independently, so controls land by habit (an option pill orphaned below a drop
zone; an option button flung to a card's far edge), and the same idea looks
different on different pages. It doesn't feel like one intuitive product. The
redesign should impose a **consistent system**: one page template, one component
kit, predictable action/option placement, and clear visual hierarchy — while
keeping the data density an expert wants.

## 9. The ask

1. **Wireframes first** — low-fidelity layouts that nail the page template, the
   component kit, and where things go, before any visual styling.
2. A **component library** spec: cards + action rows, preview-result tables,
   wizard/step pattern, two-pane review, filterable lists, chips/filters, option
   toggles, forms, and empty/loading/error states.
3. The **navigation** model (the grouped drawer + app bar).
4. Then the **visual layer** (M3-flavoured) expressed as the token set + classes,
   so it drops into the no-build Lit/CSS stack.
