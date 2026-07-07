# Bifrost — Project Overview

A complete description of what Bifrost is, the services it connects to your
Gramps tree, how it works, and why you'd use it. This is written for someone who
knows **Gramps** but not the other tools involved — each is introduced below.
For deeper build notes see `DESIGN.md`; for the photo labelling convention see
`MEDIA_ID_SCHEME.md`.

---

## 1. What Bifrost is, in one paragraph

Bifrost is a companion web app for your **Gramps Web** family tree — a
switchboard between Gramps and the other services your research material lives
in. On its own, Gramps holds people, families, events, places, sources, and
media — but the *material* for those records usually lives elsewhere: your
scanned documents, maps, and so on. Bifrost connects those services to Gramps
and lets you bring their content in cleanly: scanned records become media with
transcriptions and citations, places get real map boundaries, and so on.
Everything works the same way — **preview what would change, then apply it** —
so you always see the result before it touches your tree. It runs as a single
small web app you open in a browser.

---

## 2. The services Bifrost connects (introduced)

You only need to know Gramps to use Bifrost; here's what the other pieces are and
what each one contributes.

- **Gramps Web** — the web/server edition of Gramps: your family tree, in a
  browser. This is the **destination** for everything Bifrost does.
- **Paperless-ngx** — a self-hosted document archive. You scan or upload
  documents (vital records, letters, certificates, deeds), and it stores, tags,
  and text-searches them. Bifrost turns tagged Paperless documents into Gramps
  media, brings their text in as transcription notes, and keeps them current.
- **OpenStreetMap boundaries** — a small rendering service fetches the real
  geographic *outline* of a place (a county, a parish, even a single building)
  from OpenStreetMap. Bifrost uses it so a place's minimap in Gramps shows its
  actual shape instead of just a single pin.
- **Anthropic Claude** — an AI language model. Bifrost uses it to draft properly
  formatted genealogical source citations.
- **Google Gemini** — an AI model that can *read images*. Bifrost uses it to
  transcribe handwriting, old print, and photographed records that ordinary OCR
  can't make sense of.

You don't have to use all of them — each surface in Bifrost simply lights up the
services it needs.

---

## 3. The core idea: preview, then apply

Every operation in Bifrost can be run in two modes from the same screen:

- **Preview** shows exactly what *would* happen — which media would be created,
  which dates would change, which documents would be transcribed — and changes
  nothing.
- **Apply** performs it.

This means you're never surprised: you review a clear, itemized list, and only
then commit. Each run is also recorded, so there's a history of what was done.

A second design rule keeps your data safe: **Bifrost remembers what it's already
done by writing a marker into Gramps and the source systems themselves** — for
example, a Gramps media object records which Paperless document it came from,
and a Paperless document records its Gramps id. Because the "memory" lives in
those systems, Bifrost's own small database is just a cache and an audit log
that can be rebuilt if needed.

---

## 4. The surfaces (what each section does)

The UI is one page: a stack of expandable sections, one per operation.

- **Sync** — the Paperless → Gramps import engine, with the preview→apply flow:
  tagged documents become Gramps media; their versions, titles, dates, and
  transcription text are kept up to date.
- **Transcribe** — Gemini OCR for documents ordinary OCR can't read: point it at
  a media object and the document is transcribed in place, with the text flowing
  on into a Gramps note. Small tools re-run a single document's transcription or
  rebuild all transcription notes.
- **Citations** — an assistant for building genealogical source citations. Start
  from a media object; describe the record in free text; Claude drafts the
  citation in a consistent house style (or start from a blank manual draft); you
  review and edit; saving creates the source, repository, note, and citation and
  links them up — all following Gramps' conventions.
- **Places** — gives your places real map boundaries. Paste an OpenStreetMap link
  for a place (a county, parish, or building) and Bifrost fetches its outline so
  the place's minimap in Gramps shows the actual shape.

---

## 5. How material flows in (an example)

**A handwritten record.** You upload a scan to Paperless and tag it. Ordinary OCR
can't read the handwriting, so you also tag it for Gemini OCR; Bifrost has Gemini
transcribe it and writes the text back into the document. On the next Paperless
sync, that document becomes a Gramps media object and its transcription becomes a
note attached to it. Then, from the Citations screen, you build a proper source
citation for it.

---

## 6. Conventions Bifrost keeps

- **Media ids.** Media objects get a short random 6-character id (from an
  unambiguous alphabet) so the code is safe to handwrite on the back of a
  physical photo. Other new objects (citations, sources, repositories, notes)
  are numbered in Gramps' normal sequential style (C0001, S0001, …).
- **Photo copies & versos.** Copies, crops, and scans of a photo's back are named
  off that base id with a short suffix (`_o` original, `_c##` crop, `_d##`
  duplicate, `_v##` verso scan, `_a##` AI-edited). See `MEDIA_ID_SCHEME.md`.
- **Citation style.** Citations follow a fixed house style (two reference-note
  layers, no source-list entry, blank citation date, bracketed English glosses on
  foreign-language record names, a confidence rating, and `[NEEDED: …]` markers
  for anything missing).
- **Transcriptions & translations.** A document's text becomes a "Transcription"
  note; when an English translation is included it's separated by a clear
  delimiter line.

---

## 7. Under the hood

Bifrost is a single web application (FastAPI) with a small browser UI (Lit web
components on BeerCSS, no build step). Internally it has three tidy layers: a
**client** for each external service (Gramps, Paperless, the boundary renderer,
Claude, Gemini); **domain modules** that do the actual work (document sync,
boundaries, citations, OCR); and the **web layer** that exposes each as a
section. Every module produces a stream of typed events, and the very same code
runs a preview or a real apply by toggling one flag — which is why the two
always agree.

A small local database keeps a few working tables (document versions,
transcription state, OCR history, and a full run log; tables from removed
features stay dormant). None of it is the authoritative copy of anything — the
authoritative markers live in Gramps and the source systems — so it can be
rebuilt.

A few integration details worth knowing:

- **Document versions.** Paperless lets a document have multiple versions and
  serve whichever you select. Bifrost notices when the selected version changes
  and repoints the Gramps media to it, so Gramps always shows the version you
  picked. A small scheduled job keeps this current automatically.
- **In-place OCR.** Gemini's transcription is written straight back into the same
  Paperless document (same document, no duplicate), so it shows up in Paperless
  search and flows on to a Gramps note with no extra step.
- **Map boundaries.** The boundary outline is rendered to a small geometry file
  that Gramps reads, so the place minimap draws the polygon.

---

## 8. Running it

- It runs as one container you open in a browser, reachable only over the
  private network — it is not exposed to the public internet.
- All settings and service credentials live in one config file (which keys to use
  for Gramps, Paperless, Claude, Gemini; which tags to watch; the place service
  address). The file is read at startup, so a change takes effect after a
  restart.
- A scheduled job runs periodically to keep selected document versions in sync.
- A built-in `doctor` check verifies it can reach and authenticate to every
  connected service.

---

## 9. Why use it

- **One place** to review and approve every change before it touches your tree.
- **Better records with less effort:** AI reads documents ordinary OCR can't; AI
  drafts citations in a consistent style; places show real map boundaries — each
  as a simple preview→apply step.
- **Safe by design:** it never overwrites — a clash is flagged and skipped, not
  clobbered; mistakes are easy to see; and because its memory lives in Gramps and
  the source systems, nothing important depends on Bifrost's own database.
- **One consistent experience** instead of juggling several separate tools.

In short, Bifrost is the place you *curate* your family history: it gathers the
documents, places, transcriptions, and citations from the services where they
live and gets them into Gramps correctly, with you reviewing every step.
