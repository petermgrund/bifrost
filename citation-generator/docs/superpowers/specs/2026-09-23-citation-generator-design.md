# Citation Generator: Design

**Date:** 2026-09-23
**Status:** Approved in brainstorming; awaiting spec review
**Revised:** 2026-09-28 (image-only locators; Repository, Pubinfo, Date row, and Holder & access removed); 2026-10-04 (record nouns from each chapter's §9 list with an Original-or-copy form, per `2026-09-28-record-nouns-design.md`; `{medium}` and `{srnSubject}` tokens; C1 title variants pinned; Pubinfo back as a Source row, for creating a new Source); 2026-10-06 (Cited for ends the page string and SRN on every record type, and each FRN gives it as "(documenting …)"; the newspaper FRN names its item by the page string's subject)

## Summary

A form-based citation generator (no AI) that turns one record into finished Gramps fields, reference notes, and Paperless metadata, following the *Grund-Castellano Citation Style Guide*. The guide `.md` in this repository is the master copy. The generator's record-type templates are pinned to the guide by an automated check, so the guide and the generator can be revised together: after any guide edit, one command lists exactly where the two disagree. The tool ships as one self-contained HTML file with a dense "Workbench" look modeled on Gramps' own editors.

## Context

- The repository started with the guide (`Grund-Castellano Citation Style Guide.md`) and an earlier single-file builder (`citation-builder.html`, an 8-step wizard with 38 record types).
- A headless comparison of that builder against the guide's worked examples found 171 fields identical and 39 different. About 16 of the differences were placeholder wording only (`[N]` vs `[Petition / declaration no.]`). The rest were generator gaps, extra narrative in examples, and places where the guide contradicts itself (see the appendix).
- The Gramps Web API (JWT-protected, CORS off) was offered only so Claude could see examples of existing citations. The generator does not talk to Gramps.

## Decisions

| Question | Decision |
| --- | --- |
| Kind of tool | Form tool with deterministic templates. No AI. |
| What to change from the current builder | Look and feel. The flow can stay close; the presentation changes. |
| Visual direction | B · Workbench: dense, Gramps-editor-like, sidebar of record types, compact label-left fields, output table with copy buttons, no explanatory text on screen, guidance on hover. |
| Where the guide is edited | This repository's `.md` is the master copy. |
| Delivery | One self-contained HTML file; can also be published as a private claude.ai link. |
| Outputs besides Gramps fields and FRN/SRN | Paperless metadata only. |
| How the generator stays tied to the guide | Approach 1: record-type definitions in code, pinned to the guide by tests. |
| Evidence step (one-vs-two question, three-axes quiz) | Dropped. Confidence is a dropdown pre-set to the §8 default, with §8 guidance on hover. |
| Paperless fields | Title, Document type, Date meaning, Correspondent, Source URL. |
| Gramps fields (revised 2026-09-28, 2026-10-04) | Source: Title, Author, Abbrev, Pubinfo, Call number; the Source rows are what a new Source needs. Citation: Page, Confidence. Repository and the always-blank citation Date are not produced; the user keeps Repository on the Gramps Source. |
| Page with no number (revised 2026-09-28) | In the Norwegian and Swedish parish-style record types, the image number leads the page string (`image [I], [entry], [subject]`, lower case) and the reference notes say "image [I]" in place of "p. [P]". |

## Non-goals

- Reading from or writing to Gramps Web.
- Bibliography (A11) entries; abstract, transcription, and translation note parts; on-screen warnings for Pending review or Open rules.
- Paperless Date, Date qualifier, Source URL access, and Permalink fields.
- Repository, which the user keeps on the Gramps Source.
- AI drafting of any field.

## 1. The screen

Workbench layout. Approved mockup: [2026-09-23-citation-generator-workbench.png](2026-09-23-citation-generator-workbench.png) (predates the 2026-09-28 revision: it still shows the Holder & access group, the Pubinfo and Repository rows, the Date row, and four input groups; the text below describes the tool as it now is).

- **Top bar:** app name, breadcrumb (chapter › record type), and actions: *Load guide example*, *Next citation on this Source*, *Clear*, *Copy all*.
- **Sidebar:** every record type grouped by chapter (Norwegian, Swedish, US, Published & personal) with counts and a filter box.
- **Middle column:** only the inputs the selected record type needs, in three compact groups:
  - **Source:** chapter-specific fields (e.g. fylke, parish, volume, years, call number).
  - **Citation:** locators, subject name, record noun (a select of the record type's §9 nouns, hidden when it has none) and *Original or copy* (index entry, transcript, extract, abstract; hidden when the noun is empty), the three A7 parentheticals (1 which entry, 2 source says, 3 evidence) with suggestion lists, confidence, and **Cited for** (A7: what the citation is cited for, on every record type; when given, the engine ends the page string and the SRN with it in parentheses, and each FRN template places `« (documenting {citedFor})»` at the end of its item, before the image, film, or holding clause). In the eleven Norwegian and Swedish parish-style types, Page may be left blank for an unnumbered page; the image number then leads.
  - **Reference note:** pre-filled from the record type's defaults: **Platform** (every type; suggestions are the A10 platform names) and, where the Pubinfo uses it, **Pubinfo medium** (A10: Digital images, Database with images, or Database, defaulting to what the record type's examples use, plus Microfilm where the record type can cite the film itself), **Archive** (only when a template cites `{archive}`, or, where only the film's FRN cites it, as for a newspaper, only when Microfilm is chosen; suggestions are the chapter's archives), and **Held by** and **Place** (only when a template uses `{custodian}` / `{custplace}`, as in "privately held by …"). Then image URL, access date, event year, entry details, any record-type-specific extras (e.g. a citing clause), and a comment after the FRN.
- **Output table:** the finished fields in Gramps order, grouped Source (Title, Author, Abbrev, Pubinfo, Call number), Citation (Page, Confidence), Citation note (FRN, SRN), and Paperless scan (Title, Document type, Date meaning, Correspondent, Source URL). Each row has its rule reference and a copy button. Clicking a value (or pressing Enter on it) opens it for editing and overrides it; clicking elsewhere, Tab, or Escape saves the edit without spaces or line breaks around it, and an emptied value goes back to the built one. Overridden values are marked and can be reset.
- **Hover cards:** hovering a rule reference or a group heading shows the guide section's first paragraph plus this record type's pinned row for that field. Fields may declare their own guide reference for a label hover card. All text is taken from the guide at build time.
- **Status bar:** rule-check results, whether the current output matches the guide's worked example, and the date of the guide's latest Change log entry.
- **Unfilled parts** render as highlighted gaps such as `[Parish]`, copy out as `[Parish]`, and are counted in the status bar.
- **Copy all** copies the Gramps fields and the note as blocks: `SOURCE` with Title, Author, Abbrev, Pubinfo, Call number; a blank line; `CITATION` with Page, Confidence; a blank line; `FIRST REFERENCE NOTE:` and the FRN; a blank line; `SHORT REFERENCE NOTE:` and the SRN. The layout may change once the Gramps export shows how existing notes are laid out (see Open items). Paperless values are copied per field.
- **Next citation on this Source** keeps the Source inputs, the four reference values (platform, archive, held by, place, which describe the Source), the Source overrides (Title, Author, Abbrev, Call number), and the page form, and clears the citation, note, and Paperless inputs; the record noun resets to the page form's first noun.
- **Load guide example** fills the inputs from one of the record type's worked examples (a picker when there are several). It is disabled for record types without a worked example. A newly selected record type starts empty apart from its defaults (platform, archive, held by, place, confidence).
- **Deep link:** `#type=<id>&example=<n>` selects a record type and optionally loads an example (used by the smoke test; handy for bookmarks).

## 2. Record-type definitions

One file per chapter under `src/records/` (`norwegian.js`, `swedish.js`, `us.js`, `published.js`), each exporting a list of record types. A record type declares:

| Part | Purpose |
| --- | --- |
| `id`, `name`, `group` | Stable identifier, sidebar label, sidebar group |
| `source`, `locators`, extra note inputs | Input fields in form order, each with a label and optional hint or guide reference |
| `nouns` | The record type's row of its chapter's §9 *Record nouns* table, in order (first is the default; `''` is "(none)") |
| `defaults` | Pre-filled reference values: `platform`, `archive`, `custodian`, `custplace` (e.g. `{ platform: 'Digitalarkivet', archive: 'Statsarkivet i Oslo' }`) |
| `confidence`, `doctype` | §8 default level; Paperless document type (C2) |
| `title`, `abbrev`, `author`, `pubinfo` (optional), `page`, `frn`, `srn`, `paperlessTitle` (optional variant) | Templates. Without a `pubinfo` template the engine builds A10's genealogical form, `[medium], [platform] (homepage URL).`; published and personal types give their imprint, and an empty one leaves Pubinfo blank (letters, the Family Bible). |
| `pageVariants` (optional) | Alternative page templates chosen in the Citation group, e.g. a book's pages / chapter / multi-volume / encyclopedia-headword forms |
| `derive(values)` (optional) | Computed values such as a traditional state abbreviation or a court's short name |
| `frnMicrofilm` (optional, also per page variant) | The FRN for film read in person at a library (Pubinfo medium Microfilm): the film takes the digital image's place and nothing is cited behind it (A10). The Pubinfo becomes `Microfilm, [archive].` and the Paperless correspondent is blank (C6). |
| `eventDate` (optional, also per page variant) | The input holding the record's own date (a census year, a date signed). The event year in templates and the Paperless title comes from it, and the form hides the Event year box, so a year typed for another form or citation cannot linger. |
| `pins` | For each template: guide section and the exact row text it follows |
| `examples` | Worked-example claims: guide heading plus the inputs that reproduce it |

**Template notation.** `{field}` inserts a value. `«…»` is dropped when any field inside it is blank. Everything else is literal, so bracketed glosses such as `[parish records]` are plain text. A required field left blank outside `«…»` renders as a gap.

**Standard tokens** for every record type. Computed by the engine: `{subject}` (A7 subject with parentheticals, or "[Subject] in [Head] household"), `{srnSubject}` (the same with only the which-entry parenthetical, for SRNs), `{name}`, `{noun}` (the record noun in its copy form: `birth and baptism index entry`, `death certificate abstract`), `{entryof}` ("[noun] of [name]"), `{medium}` (`database` for an index entry or transcript, else `digital image`, for the FRN's image clause), `{author}` (the built Author), `{home}` (the platform's homepage from the A10 table, or a gap when the platform is not listed), and two page locators built from the typed page and image:

| Token | Use | Page and image | Page only | Image only | Neither |
| --- | --- | --- | --- | --- | --- |
| `{pageLoc}` | Page string | `p. 57 (image 62)` | `p. 57` | `image 62` | gap `[Page or image]` |
| `{pageRef}` | FRN and SRN | `p. 57` | `p. 57` | `image 62` | gap |

Typed values every record type has: `{platform}` (the FRN's "digital image, {platform}" clause and the Paperless correspondent), `{archive}` (FRN citing clauses), `{custodian}` and `{custplace}` ("privately held by {custodian}, {custplace}"), `{url}`, `{accessed}`, `{eventYear}`, `{details}`. The eleven Norwegian and Swedish parish-style types (ministerialbok, klokkerbok, confirmation, meeting minutes; husförhörslängd, dopbok, vigselbok, dödbok, confirmation, sockenstämmoprotokoll, folkräkning) use the page locators.

**Pins.** A pin is `[section, text]`, e.g. `['B.1 §4', '…, parish registers, Parish register (copy) [Roman] [Arabic], [years]']`. The check finds the section by heading (`A8` → "A8 · Title"; `B.1 §4` → "§4" under "Part B.1") and requires the text to appear there after removing backticks and markdown escapes and collapsing whitespace. Rewording trips the pin; reformatting does not. A template may pin several rows when one template serves them all (the newspaper page template pins the obituary, personals, and mixed-column rows of B.3 §7; the confirmation-or-communion page template pins both rows of B.1 §7). The page templates that use the page locators also pin the unpaginated-fallback line of B.1 §7 or B.2 §7.

**Unpinned templates.** A template with no guide row or example behind it (e.g. the tingbok FRN, drafted by analogy) has no pin. The check lists unpinned templates as gaps in the guide rather than failures.

**Shared engine** (`src/engine.js`): template filling; the A7 subject builder (parentheticals joined in 1-2-3 order inside one set of parentheses; non-head household wording) and record-noun rule for copies and indexes; the page locators; Paperless Title (C1 with the page string's noun, and its variants), Date meaning from document type (C4), Correspondent = platform (C6), Source URL = image URL (C8).

**Every input is used.** A structural test requires each input field of each record type (source, citation, page-variant, and note fields) to appear in some template as `{key}` or be read by its `derive` function; `call` (the Call number) and `page` and `image` (behind the page locators) are read by the engine itself.

**Shared tables** (`src/tables.js`): the A10 platform table (its names are the Platform suggestions), traditional state abbreviations (B.3 §10), archive lists per chapter (§3, the Archive suggestions), parenthetical suggestions per chapter (§9), and the A7 copy forms. The platform and state tables are pinned to the guide's own tables, and the record types' noun lists to each chapter's §9 *Record nouns* table.

**Rule checks** (`src/checks.js`), carried over from the current builder: raw image ID in the page string (A4); volume repeated in a Norwegian or Swedish page string (A4); archive machine path in the Title (A4); hyphen instead of en dash in a year-range (A8); USPS state codes (B.3 §10); image URL without an access date (A5); confidence not chosen when the type has no §8 default (A6); unfilled parts. The Pubinfo (A10) and Repository (A9) checks went with those fields.

## 3. The check

`npm test` runs Node's built-in test runner (`node --test`) with no packages installed. It verifies:

1. **Worked examples.** Every worked example in each chapter's §12 must be claimed by a record type (an unclaimed example fails). The claimed inputs are run through the generator, and each field the guide shows that the tool builds (Title, Abbrev, Author, Call number, Citation page, FRN, SRN) must match exactly after normalizing markdown escapes and backticks. The record type's default confidence must equal the first level named in the example's Confidence row. Values marked **Open:**, "Same as Example 1", or conditional ("blank if…", "allowed in Gramps", "(+ …)") are reported as *not compared*. Examples are identified by chapter and heading text (`B.1 Example 1`, `B.4 Family Bible`); an example with several citations (B.3 Ex. 10) names which one a claim reproduces.
2. **Pins.** Every pinned text appears in its section. On failure the report shows the closest current line in that section.
3. **Coverage.** Every row of each chapter's §4 title table and §7 page-string table is pinned by some record type's title or page template (including page variants) or listed in an explicit *not covered* list with a reason. One record type may cover several rows (Directory or register covers both Membership directory and School roster).
4. **Shared tables.** The platform table, state abbreviations, and each chapter's §9 *Record nouns* table match the code (a record type missing from §9 has only the empty noun).

The report prints only the differing region of each field, with some context on either side, and ends with the unpinned list:

```
✗ B.1 Example 2 · no-folketelling-1865 · FRN
    guide:     …Akershus fylke, Eidsvoll prestegjeld, Eidsvoll sokn, district 009 Blegstad…
    generator: …Akershus fylke, Eidsvoll prestegjeld, district 009 Blegstad…
✗ Pin no-klokkerbok.title not found in B.1 §4
    closest row now: …, parish registers, Parish register (copy) [Roman][Arabic], [years]
✗ Coverage: B.3 §4 "Passenger manifests" has no record type
• Unpinned (no guide row or example): no-tingbok.frn, no-tingbok.srn, …
```

**First run.** The check is expected to fail at first on:

- **Six record types the guide lists but the current builder lacks:** Civil War pension, compiled service record, passenger manifest (US); edited collection, family record, oral-history collection (Published & personal). They are added with titles and page strings from the guide and FRNs drafted by analogy (unpinned).
- **§7 rows the current builder handles only partly,** which become page variants: marriage license (State vital record), declaration of intention (Naturalization), book chapter, multi-volume work, and encyclopedia headword (Book or bygdebok).
- **About two dozen differences** (appendix), resolved three ways:
  - *Generator gaps:* fix the template.
  - *Extra narrative in an example:* add optional inputs (e.g. a trailing comment, a "copies held by" clause, a citing clause).
  - *Contradictions inside the guide:* one list of proposed guide edits goes to the user for approval. Each approved edit gets a Change log row, and any Review queue item it settles is marked Resolved.

## 4. Files and build

```
citation-generator/
  Grund-Castellano Citation Style Guide.md   master guide (unchanged location)
  citation-generator.html     built tool, committed
  citation-builder.html       old builder; removed once the new tool covers every record type
  src/
    page.html                 Workbench layout and CSS
    app.js                    sidebar, form, output table, hover cards, status bar, storage
    engine.js                 template filling, subject builder, page locators, Paperless
    checks.js                 rule checks for the status bar
    tables.js                 platforms, state abbreviations, archives, parenthetical suggestions
    records/                  norwegian.js · swedish.js · us.js · published.js
  tools/
    guide.js                  reads the .md: sections, rule text, worked examples, Change log date
    build.js                  combines src/ and guide excerpts into citation-generator.html
  test/                       the check (Section 3) and engine unit tests
  package.json                scripts: test, build. No dependencies.
  docs/superpowers/specs/     this design
```

- **Source code** is ES modules. Tests import them directly in Node 24. The build inlines them, the CSS, and the guide excerpts into one file with no network requests: system fonts only, so it works offline.
- **Guide excerpts embedded by the build:** first paragraph of each referenced section, every pinned row, the expected outputs of each worked example (for the status bar), and the date in the first Change log row.
- **Browser storage** keeps the current record type, inputs, and overrides across reloads.
- **Git.** The repository was initialized with a baseline commit of the guide and the old builder. `.gitignore` excludes `local.txt` (plaintext credentials) and `.superpowers/`. Guide edits and the matching generator changes are committed together.
- **`local.txt`:** no longer needed by the tool. Suggest the user delete it after running the Gramps export.

## 5. Workflow, errors, testing

**Changing a rule:**

1. Edit the rule, table row, or example in the `.md`; add a Change log row; mark any settled Review queue item.
2. `npm test` names every pin, example, or coverage row the edit touched.
3. Update the affected record definitions until the check passes (or correct the guide if the failure shows the guide is wrong).
4. `npm run build`; the status bar picks up the new Change log date.
5. Commit the guide and generator together; republish the private link if one is in use.

Gaps found while using the tool on real records (a missing record type, noun, or parenthetical) go into the guide's Review queue and then through the same loop.

**Errors:**

- Missing inputs appear as gaps, never silently dropped.
- Browser storage unavailable (e.g. a private window): the tool works without saving drafts.
- Clipboard blocked: fall back to selecting the text for manual copying.
- A saved draft for a removed record type is discarded. A draft saved by an older version keeps the values whose fields still exist; settings that no longer exist (such as the old Holder & access group) are dropped.

**Testing beyond the check:**

- Engine unit tests: optional segments and gaps; parenthetical order and household wording; the page locators (page and image, page only, image only, neither); Paperless title variants; each rule check fires on a bad value and stays quiet on a good one.
- Locator tests (`test/locators.test.js`): the image-only page string, FRN, and SRN for each of the eleven parish-style types.
- Build smoke test: open the built file in headless Chrome for every record type via the deep link (loading its first worked example when it has one) and confirm the output table renders with no console errors. Skipped when Chrome is not installed.
- Interaction tests (`test/interaction.test.js`): drive the built page in headless Chrome with real mouse, touch, and keyboard input: typing in a field and then clicking or tapping a value cell, editing one cell and then clicking another, Copy and Reset right after typing, double-clicks, Tab, Shift+Tab, and Escape out of an edit box, and opening a select right after typing. Skipped when Chrome is not installed.
- Manual pass: click through the built tool in a browser before calling the work done.

## Record types

44 in total: the current builder's 38 plus 6 new (marked ✚).

| Chapter | Record types |
| --- | --- |
| Norwegian (9) | Ministerialbok · Klokkerbok · Confirmation or communion · Parish meeting minutes · Folketelling 1801 · Folketelling 1865 and later · Tingbok · Skifteprotokoll · Matrikkel |
| Swedish (9) | Husförhörslängd · Födelse- och dopbok · Lysnings- och vigselbok · Dödbok · Confirmation or communion · Sockenstämmoprotokoll · Bouppteckning · Folkräkning (SVAR) · Lantmäteriet survey act |
| US (13) | Federal census · State census · State vital record · Church record · Naturalization · WWII draft card · Headstone application · Find a Grave memorial · Newspaper item · City directory · ✚ Civil War pension · ✚ Compiled service record · ✚ Passenger manifest |
| Published & personal (13) | Book or bygdebok · Periodical article · Directory or register · Online video · Family Bible · Funeral program · Photograph · Family letter · Audio interview · Another genealogist's research · ✚ Edited collection · ✚ Family record · ✚ Oral-history collection |

Page variants: State vital record (certificate, marriage license); Naturalization (petition, declaration of intention); Newspaper item (one template with optional column parts covering announcements and notices, personals, and mixed columns); Book or bygdebok (pages, chapter, multi-volume, encyclopedia headword).

Worked examples to claim (30): B.1 Ex. 1–5, B.2 Ex. 1–5, B.3 Ex. 1–11, and the nine B.4 examples (Family Bible, Funeral program, Photograph, Audio interview, Personal research, Published book, Membership directory, School enrollment register, Online video).

## Open items

- **Gramps export.** The user may run the one-off export script (kept outside the repository) to share existing sources, citations, and notes. When it arrives, set the *Copy all* layout to match how existing citation notes are formatted.
- **Guide contradictions** from the first run need the user's decisions (appendix, group C).

## Appendix: differences found at design time

From comparing the current builder's output with the guide's worked examples. Placeholder-only differences are omitted.

**A. Generator gaps (fix the template or add an input)**

| Example | Field | Difference |
| --- | --- | --- |
| B.1 Ex. 2 folketelling 1875 | FRN | Guide adds "Eidsvoll sokn" and a long citing clause (Statistisk sentralbyrå … source ID 52052; archive reference AV/RA-S-2231/E) |
| B.1 Ex. 4 matrikkel | SRN | Guide has "gård 234 Vinger"; builder "gård 234" |
| B.2 Ex. 5 land survey | FRN | Guide: "land allotment (Lott A) of the minor Marit Andersdotter, 64 öre 6 penningar skatt" |
| B.3 Ex. 11 church record | FRN, SRN | Guide uses "death and burial of…" (event, not "entry"), a fuller citing clause, and a death date in the SRN |
| B.4 Photograph | Page | Guide page string has a second element: "; inscription on mount, "Grandma's Grandpa"" |
| B.4 Personal research | FRN | Guide adds "with copies privately held by Peter Grund, Duluth, Minnesota" |

**B. Extra narrative in examples (optional inputs)**

B.2 Ex. 1 ("Ambjörby Torpare"), B.2 Ex. 3 ("Ambjörby"), B.2 Ex. 5 page parenthetical, B.4 Family Bible (two-hands sentences), B.4 Photograph (attribution sentence), B.4 Personal research (closing sentences).

**C. Contradictions inside the guide — settled 2026-09-24**

| Where | What was chosen |
| --- | --- |
| B.1 Ex. 1 | SRN uses the page's subject: "Thor Emil birth and baptism entry." |
| B.1 §7, Ex. 3; B.2 §7 | En dash everywhere in page ranges: "folio 145–148", "pp. 203–205" |
| B.2 Ex. 2 (Review queue C7) | FRN and bibliography cite the full volume path, Värmlandsarkiv, SE/VA/11047/F II/26 |
| B.2 Ex. 2 | SRN drops the trailing ", Ambjörbymon" |
| B.3 Ex. 8 | SRN uses the page's subject: "Per Larsson Grund obituary" |
| B.3 Ex. 11 | FRN keeps ", right"; SRN becomes "First Lutheran Church (Warren, Minn.), death and burial entry of Emma Söderström, p. 283." |
| B.4 Family Bible | Full name "Per Larsson Grund" everywhere in the FRN and SRN |
| B.4 Funeral program (Review queue C11) | Pubinfo follows the A10 imprint: "Williams, Minnesota: Helgeson Funeral Home, 16 February 1953." |
| B.4 Audio interview | One form everywhere: "Peter Grund" |
| B.4 Personal research | Page string uses the SRN's shorter form: "Ambmyra typed page, received 30 April 2026" |
| B.1 §4 | Norwegian name first: "menighetsmøteprotokoll [parish meeting minutes]" |
| B.3 §7 | City directory page string becomes "p. [N], [Name] directory entry" |
| B.3 §9 | Find a Grave and manifest/directory subject rows match §7: no record noun after a memorial or list number |

The Online video FRN wording and SRN channel name, and the Audio interview topic wording, turned out to be optional inputs rather than contradictions.
