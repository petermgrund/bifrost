# Record Nouns: Design

**Date:** 2026-09-28
**Status:** Implemented 2026-10-04, with the guide changes dated 2026-09-29. Added while building it: headstone applications end in their noun (`Axel O. Grund (d. 1948) headstone application`), Directory or register takes `directory entry · register entry`, and SRNs use a `{srnSubject}` token (B.1 §10).
**Builds on:** `2026-09-23-citation-generator-design.md`

## Summary

The record noun ends a page string's subject (`Lars Persson birth and baptism entry`). It becomes a controlled vocabulary that names the form of what was cited. Each chapter's §9 lists the nouns each record type may use, and the generator offers only those. A second choice, *Original or copy*, turns an original noun into an index entry, transcript, extract, or abstract by one A7 rule. The Paperless title uses the same noun.

## Decisions

| Question | Decision |
| --- | --- |
| Free text or a list | A list per record type, shown as a dropdown. The guide's §9 *Record nouns* tables are the list, and a check holds the generator to them. |
| What the form words mean | *entry*: an item in an original register or book. *record*: a standalone original document, which goes by its own name when it has one (`death certificate`). *index entry*: a line in an index or database made from the records. |
| Other forms | *transcript*: a full word-for-word copy made later. *extract*: a word-for-word copy of part of a record. *abstract*: a summary of a record's key facts. |
| Must every noun name its form | Yes, except census `household`. Named documents and newspaper items keep their names (`death certificate`, `obituary`). |
| How a copy is chosen | A second dropdown, *Original or copy*, on every record type that has a noun. The guide lists only original nouns; one A7 rule builds the rest. |
| FRN for an index entry or transcript | `database, [platform] (…)` in place of `digital image, [platform] (…)`. Extract and abstract keep `digital image`. |
| Paperless title | Uses the page string's noun. C1's own record-noun table goes. |
| Guide edits | Claude drafts them; the user reviews the guide diff before any code changes. |

## Guide changes

### A7 · Record nouns

A7's **Record-noun** bullet becomes a pointer ("says what was cited and in what form; see *Record nouns* below"), and A7 ends with this subsection (the draft may tighten the wording):

> **Record nouns.** The record noun comes from the record type's list in its chapter's §9 *Record nouns* table; the first noun listed is the default. A record type missing from that table takes no record noun. The noun names the form of what you cite:
>
> | Form | What it is | Noun |
> | --- | --- | --- |
> | entry | An item in an original register or book | `[event] entry`: `birth and baptism entry`, `marriage entry`, `estate entry` |
> | record | A standalone original document | Its own name when it has one (`death certificate`, `WWII draft card`, `obituary`); otherwise `[event] record` |
> | household | A census household, the one noun without a form word | `household` |
> | index entry | A line in an index or database made from the records | `birth and baptism index entry` |
> | transcript | A full word-for-word copy made later | `birth and baptism transcript` |
> | extract | A word-for-word copy of part of a record | `birth and baptism extract` |
> | abstract | A summary of a record's key facts | `death certificate abstract` |
>
> §9 lists original nouns only. For a copy or index, replace a final `entry` with the form (`birth and baptism entry` → `birth and baptism index entry`); after any other noun, add the form (`death certificate abstract`, `household transcript`). In the FRN, an index entry or transcript was read in a database: write `database, [platform] ([URL] : accessed [date])` in place of `digital image, …`.

A7's couples example becomes `Larsson-Söderström marriage entry`.

### §9 Record nouns tables

Each chapter's §9 opens with a *Record nouns* table. It has one row per record type that takes a noun, named exactly as the generator names it. Nouns are joined by ` · `, and `(none)` marks a noun that may be left off.

**B.1 §9**

| Record type | Record nouns |
| --- | --- |
| Ministerialbok | birth and baptism entry · baptism entry · death entry · burial entry · marriage entry |
| Klokkerbok | birth and baptism entry · baptism entry · death entry · burial entry · marriage entry |
| Confirmation or communion | confirmation entry · communion entry |
| Parish meeting minutes | minute entry |
| Folketelling 1801 | household |
| Folketelling 1865 and later | household |
| Tingbok | land dispute entry · court matter entry |
| Skifteprotokoll | estate entry |
| Matrikkel | matrikkel entry |

**B.2 §9**

| Record type | Record nouns |
| --- | --- |
| Husförhörslängd | household · household examination entry |
| Födelse- och dopbok | birth and baptism entry · birth entry · baptism entry |
| Lysnings- och vigselbok | marriage entry |
| Dödbok | death entry · burial entry |
| Confirmation or communion | confirmation entry · communion entry |
| Sockenstämmoprotokoll | parish meeting entry |
| Bouppteckning | estate inventory |
| Folkräkning (SVAR) | household · census entry |
| Lantmäteriet survey act | land allotment entry · signatory entry · croft transfer entry |

**B.3 §9** (Passenger manifest and Find a Grave memorial take no noun: the list or memorial number says what it is.)

| Record type | Record nouns |
| --- | --- |
| Federal census | household · census entry |
| State census | household · census entry |
| State vital record | death certificate · birth certificate · marriage license |
| Church record | death and burial entry · baptism entry · confirmation entry · marriage entry · burial entry · membership entry |
| Naturalization | naturalization petition · declaration of intention |
| WWII draft card | WWII draft card |
| Headstone application | headstone application |
| Civil War pension | pension file |
| Compiled service record | compiled service record |
| Newspaper item | obituary · funeral notice · marriage announcement · news mention |
| City directory | directory entry |

**B.4 §9**

| Record type | Record nouns |
| --- | --- |
| Book or bygdebok | entry · (none) |
| Family Bible | birth entry · marriage entry · death entry |
| Family record | birth entry · marriage entry · death entry · (none) |
| Funeral program | funeral program · obituary |
| Photograph | portrait · (none) |

### Renamed nouns in existing guide text

| Where | Today | After |
| --- | --- | --- |
| B.1 §7 Skifteprotokoll row; B.1 §9 Skifte row; B.1 Example 3 page and SRN | `Anders Hansen estate` | `Anders Hansen estate entry`. Example 3's FRN keeps "estate inventory of Anders Hansen", which describes the entry's content. |
| B.1 §9 Marriage row | `Hansen-Olsen marriage` | `Hansen-Olsen marriage entry` |
| B.1 §9 Court matter row | `Hansen-Olsen land dispute` | `Hansen-Olsen land dispute entry` |
| B.2 §7 Banns and marriage row; B.2 §9 Marriage row | `Larsson-Söderström marriage` | `Larsson-Söderström marriage entry` |
| B.2 §7 and §9 Meeting minutes rows | `parish meeting record` | `parish meeting entry` |
| B.2 §7 Land survey row, the land-survey record-nouns line, and the land-survey worked example (page and SRN) | `land allotment`, `signatory`, `croft transfer` | `land allotment entry`, `signatory entry`, `croft transfer entry` |
| B.2 §9 parenthetical examples | `(servant) household entry` | `(servant) household examination entry` |
| B.3 §7 and §9 Marriage license rows | `Larsson-Söderström marriage` | `Larsson-Söderström marriage license` |
| B.3 §9 License vs. banns example | `Larsson-Söderström marriage (by license)` | `Larsson-Söderström marriage entry (by license)` |

### C1 · Title

- The record noun is the page string's (A7), including its copy form. The *Record-nouns* table and the *Entry vs. record* line go.
- Record types with their own Paperless title format keep it: C1's variant forms, plus the passenger manifest, Find a Grave, funeral program, and online video titles. Find a Grave's becomes `Find a Grave memorial` (was `Find a Grave entry`), since an entry is now a register item. The Review queue's C5 item (`cadastral act` vs. `laga skifte`) stays open.
- The same-surname divorce index variant becomes shared surname + `divorce index entry` (`Lang divorce index entry 1992`).

### Change log

One row at the top:

> | 2026-09-28 | A7; B.1–B.4 §9; C1 | Record nouns are a controlled list per record type (§9 Record nouns tables) and name their form: entry, record (or the document's own name), household, index entry, transcript, extract, abstract. Renamed: marriage → marriage entry (parish) or marriage license (US vital); estate → estate entry; land dispute, court matter, and the land-survey nouns gain "entry"; parish meeting record → parish meeting entry; one person in a census → census entry (household examination entry in a husförhörslängd). C1 uses the page string's noun; Find a Grave entry → Find a Grave memorial. An index entry or transcript cites a database in the FRN. | User decision: tell entries, records, indexes, and copies apart |

## Generator changes

### Record definitions

- `nouns` lists match the §9 tables. In State vital record's *Marriage license* variant, the noun is `marriage license`.
- Worked-example inputs and pins follow the renamed guide text.
- `us-find-a-grave` Paperless title: `{name} Find a Grave memorial« {eventYear}»`.

### Engine (`src/engine.js`, `src/tables.js`)

- New subject key `copy`: `''` (original, the default), `index entry`, `transcript`, `extract`, or `abstract`, from a shared `COPY_FORMS` list in `tables.js`. The screen already calls page variants the *Form*, hence the separate name.
- `recordNoun(noun, copy)` applies the A7 rule. A bare `entry` becomes the form alone; with no noun, the copy form is ignored. `{noun}`, `{subject}`, `{entryof}`, and the default Paperless title use its result. The non-head household wording keeps working: `Karen Indiana Evensdatter in Hansen household transcript`.
- New engine token `{medium}`: `database` when the noun is not empty and `copy` is `index entry` or `transcript`; otherwise `digital image`. Every `digital image, {platform} (…)` clause in the record definitions becomes `{medium}, {platform} (…)`.
- `PAPERLESS_NOUN` goes.
- `newDraft` and *Next citation on this Source* start `copy` at original; switching page variants keeps it.

### Screen (`src/view.js`)

- *Record noun* is a select of the record type's nouns (resolved for the page variant), with `(none)` for the empty noun. It is hidden when the only noun is empty.
- *Original or copy* is a select beside it (Original, Index entry, Transcript, Extract, Abstract). It is hidden when the noun is empty.
- Both re-render the output.

### Saved drafts (`src/store.js`)

- A saved noun that this change renamed maps to its new noun for that record type: `marriage` → `marriage entry` (or `marriage license` in State vital record), `estate` → `estate entry`, `land dispute` → `land dispute entry`, `court matter` → `court matter entry`, `parish meeting record` → `parish meeting entry`, the land-survey nouns → `… entry`, and `record` → `census entry` (or `household examination entry` in Husförhörslängd).
- Any other noun that is not in the record type's list resets to the default. `copy` starts at original.

### Tests

- New shared-table check, like PLATFORMS vs A10: each chapter's §9 *Record nouns* table equals the record types' `nouns` lists, in order. A record type missing from the table has only the empty noun.
- Engine: `recordNoun` for each form (a final `entry` replaced; a named document, `household`, and a bare `entry`), the non-head household wording with a copy form, `{medium}` for each form and for an empty noun, and no record definition left with a literal "digital image, {platform}".
- Worked examples still reproduce with the updated nouns. Screen tests cover both dropdowns (visibility, options, re-render), and store tests cover renamed and unknown nouns.
- `npm test` passes with `fail 0` and `todo 0`.

### Docs

- Main spec: a *Revised* line, and updates where it describes the noun input, the tokens, and the Paperless title.
- README: only if it mentions the free-text noun.

## Out of scope

- Record types for standalone indexes and databases (e.g. SSDI), whose Source is the index itself.
- Setting Confidence from the copy form. A6 grades derivatives lower, but Confidence stays the §8 default.
