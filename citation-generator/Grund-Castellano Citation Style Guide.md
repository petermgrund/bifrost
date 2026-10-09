# Grund-Castellano Citation Style Guide

## Start here

Every source and citation in the Grund-Castellano tree is built from a formula, based primarily on *Evidence Explained* (EE). Part A of this guide holds rules shared by all sources; each Part B chapter adds what is specific to one domain; Part C covers filing scans in Paperless.

### Draft a citation in five steps

1. **Find the record type.** Open the Part B chapter for the domain (Norwegian, Swedish, US, Published & personal). Not sure which? Use the Cross-walk near the end.
2. **Scope the Source.** One Source per navigable unit (A1). Reuse an existing Source if one already covers this volume, county-year, cemetery, book, newspaper, or artifact, even if you read this item on another platform or on film.
3. **Fill the Source fields** from the chapter's tables: Author (section 2), Repository (3), Title (4), Call number (5), Pubinfo (6), Abbrev (10).
4. **Build the Citation.** Page string from the chapter's section 7, subject and parentheticals per A7, confidence from section 8, Citation date left blank (A2). Split into two citations if evidence quality differs (A3).
5. **Write the notes.** First Reference Note and Short Reference Note (A5), modeled on the chapter's worked example (section 12).

### How each chapter is laid out

Every Part B chapter uses the same 12 numbered sections, so the same question always lives in the same place:

| § | Answers | § | Answers |
| --- | --- | --- | --- |
| 1 | What is one Source? | 7 | What goes in the page string? |
| 2 | Who is the Author? | 8 | What confidence level? |
| 3 | What is the Repository? | 9 | Which record-nouns and parentheticals? |
| 4 | How is the Title built? | 10 | How is the Abbrev built? |
| 5 | Where do volume identifiers go? | 11 | How does it appear in the bibliography? |
| 6 | What goes in Pubinfo? | 12 | Worked examples |

### Rule IDs and status labels

Shared rules carry IDs (A1 to A13) so chapters, comments, and the change log can point to them exactly. Rules are either settled, or carry one of two labels:

- **Pending review**: drafted by analogy, not yet confirmed. Use it, but expect it may change.
- **Open**: a question or missing value that needs a decision.

Every labeled item also appears in the Review queue, so you can audit everything unsettled from one table.

### How to revise this guide

1. Edit the rule in place, or leave a comment on it and ask me to make the change.
2. Add a row to the top of the Change log: date, rule ID, what changed, and why.
3. If the change settles a Review queue item, set its status to Resolved and note the decision.

## Gramps field map

Every EE citation concept has exactly one Gramps field, in all four domains.

| EE concept | Gramps field | What it holds | Rule |
| --- | --- | --- | --- |
| Creating body / author | Source **Author** | The parish, court, agency, or person who created the record. No country or umbrella prefix. Blank when the source is cited by title. | Each chapter §2 |
| Holding institution | Source **Repository** | The archive, courthouse, or family custodian holding the original. Blank for publications and online-only platforms. | A9 |
| Human-readable identifier | Source **Title** | Locality-led title that lets a future reader find the collection from the title alone. | A8 |
| Short cite | Source **Abbrev** | Short, readable identifier for Gramps source-list views. | Each chapter §10 |
| Publication statement | Source **Pubinfo** | Medium + platform (+ homepage URL), or `[City]: [Publisher], year.` for published works. | A10 |
| Archival machine path | Source **Call number** | The archive's machine reference (NAD `AV/…` or `SE/VA/…`, NARA publication number, state series ID). | A4 |
| Locator within the source | Citation **Page** | Granular locator + subject pointing to one entry. | A4, A7 |
| Reference-note prose | Citation **Notes** | First Reference Note, Short Reference Note, optional Abstract / Transcription / Translation. | A5 |
| Date | Citation **Date** | Always blank. | A2 |
| Evidence appraisal | Citation **Confidence** | The 5-level Gramps scale. | A6 |

## Part A: Shared rules

These 13 rules apply to every source in every domain. Chapters refer to them by ID.

| ID | Rule | One-line summary |
| --- | --- | --- |
| A1 | Source scoping | One Source = one navigable unit; everything finer goes in the page string. |
| A2 | Citation date | Always blank. |
| A3 | One citation vs. two | Split when facts differ in evidence quality. |
| A4 | Locators | Human label in Title/Abbrev, machine path in Call number, granular locator in Page. |
| A5 | Citation notes | Every citation gets an FRN and an SRN. |
| A6 | Confidence | 5-level scale anchored to EE's three evidence axes. |
| A7 | Page-string subject | `[locators], [name] [record-noun]` + ordered parentheticals. |
| A8 | Title | Locality-led, largest jurisdiction first. |
| A9 | Repository | Archive, then private custodian, else blank. |
| A10 | Pubinfo | `[medium], [platform] (homepage URL).` or an imprint. |
| A11 | Bibliography | Transform fields to EE Source List form; do not print the Title. |
| A12 | Privacy | Living informants' addresses are never published. |
| A13 | Abbreviations | p., pp., vol., col., no., fol. |

### A1 · Source scoping

A Source is the natural unit a researcher browses or pulls off the shelf. Scope down to that unit, and push everything more granular (rolls, pages, entries, memorial numbers) into the Citation page string.

| Domain | One Source is... |
| --- | --- |
| Norwegian | One archival volume / fond: a parish-office volume series, a sorenskriveri's tingbok or skifteprotokoll series, a folketelling for a jurisdiction, a matrikkel volume. |
| Swedish | One archival volume / fond: a parish kyrkoarkiv volume series (each is a discrete NAD fond), a häradsrätt series, a centrally published SVAR database. |
| US | One geographic/archival unit: per county-state-year (federal/state census), per state-collection (state vitals), per county-collection (county vitals). |
| Published & personal | One bibliographic unit or artifact: per book, periodical title, work (any medium), artifact, interview event, or third-party research compilation. |

**Why the roll is not the Source.** A federal-census roll can span several counties and a county can span several rolls, so the roll number lives in the page string. Two county-Sources may share a publication number in Call number.

**Find a Grave.** While EE 11.42 treats all of Find a Grave as one Source, this guide scopes one Source per cemetery, for the same reason as census-by-county. The cemetery is the natural unit, and one flat Source would force every citation to repeat the cemetery's details.

**Where you read it does not make a Source.** A newspaper read on Newspapers.com and on a library's microfilm, or a parish volume on both Digitalarkivet and FamilySearch, is one Source. Pubinfo names one of its homes, and each citation's FRN names the home its own item was read in (A10).

**Artifacts that could scope two ways**:

- **Per artifact** (preferred) when it is the only memorabilia in the tree for that person, or its provenance is distinct.
- **Grouped** under `Family memorabilia, [Name] family` when several artifacts share one provenance and custodian (a relative hands over a binder at once).

### A2 · Citation date

**Leave the Citation date blank.** The field is ambiguous (event, record creation, or access?). Every meaning already has a home below:

| Meaning | Where it lives |
| --- | --- |
| Event date | The Gramps event |
| Record-creation date | The volume year-range in the Title |
| Access date | FRN URL parenthetical (`accessed 21 April 2026`) |
| Publication year | Pubinfo |
| Interview or letter date | FRN prose (`recorded interview, 12 March 2024`) |

### A3 · One citation vs. two

Use one citation when all attached facts share the same evidence quality; use separate citations when they do not. The principle is Mills (EE 1.16): each piece of information in a source is appraised separately. Her example is a colonial South Carolina memorial covering the landowner's own acquisition (primary) and a hundred-year chain of title (secondary).

**One citation**, same quality, recorded directly at the time:

- A marriage entry naming both spouses.
- A household entry listing head, wife, and children, attached to all their residence events.
- A baptism entry supplying a child's birth and baptism dates.
- A naturalization petition's birth and arrival dates, if both were given at the same hearing under oath.

**Two or more citations**, different quality:

- A baptism entry that also gives the mother's age: child's birth/baptism (Very High) and mother's birth year (Normal at most), each with its own page-string subject and FRN.
- A death certificate: death (Very High) and parentage (Normal or Low).
- An obituary giving a death date and a birth date 80 years earlier.

When split citations share a page-string subject, as the obituary's two do, each page string ends with what it is cited for (A7).

### A4 · Locators

A volume has two identifiers answering different questions. Keep each in its home and never mix them.

| Form | Examples | Home | Purpose |
| --- | --- | --- | --- |
| Human-readable locator | `AI:11`, `I 5`, `A I 5`, NARA `T625` | Title and Abbrev | Identifies the volume to a reader |
| Archive machine path | `SE/VA/13398/A I/11`, `AV/SAO-A-10888/G/Ga/L0002`, `AV/RA-S-2231/E` | Call number | Locates it in the archive's catalog |
| Granular locator | page, image, folio, roll, ED, sheet, dwelling, family, certificate/memorial/serial no., entry/household/person no. | Citation page | Points to one entry |

Example: the Title says `AI:11`, the Call number says `SE/VA/13398/A I/11`. Same volume.

**Volume in the page string:** only when the Source spans more than one volume (a US census county across several rolls, a periodical run, a multi-volume book set). When the Source is one volume or one act, the Title already names it, so the page string starts at the page, folio, or entry. The reference notes still name the volume, since they must stand alone outside Gramps.

**Two hard rules for the page string:**

1. **No raw image IDs or URL parameters** (`kb20060313011115`, `ft20110110330371`, `C0038409_00019`, `Folk_817085-004`). They go only in the FRN URL. An image number is different: it is the number you enter in the platform's viewer, so it stays in the page string as `(image [I])` whenever it differs from the page number. Leave it out when it matches the page, or when there is no image viewer.
2. **No place name in the subject slot.** Place lives on the Gramps event and in the FRN prose. The page string locates the entry in the volume; place locates the event in the world.

### A5 · Citation notes

Source-level notes are optional; the Source fields carry the bibliographic data. Each Citation note holds:

| Part | Required? | Content |
| --- | --- | --- |
| First Reference Note (FRN) | Yes | Full EE-style citation, including, for an online source, the URL with access date in parentheses |
| Short Reference Note (SRN) | Yes | Subsequent-reference form, just enough to identify the source |
| Abstract | Optional | Your own summary of the record |
| Transcription | Optional | Verbatim entry text (handwritten or foreign-language material) |
| Translation | Optional, non-English sources only | English translation of the transcription |

**Citing** in an FRN introduces only the source behind an image or film: `…; citing Minnesota Historical Society microfilm SAM 227, reel 4.` What a citation is cited for reads `(documenting …)` instead (A7).

### A6 · Confidence

Use the 5-level Gramps scale, anchored to EE's three axes: original vs. derivative source, primary vs. secondary information, direct vs. indirect evidence.

| Level | Anchored to | Example |
| --- | --- | --- |
| Very High | Original, primary, direct | Death entry written by the minister days after the event; death certificate by the attending physician, for the death itself |
| High | Original, primary, indirect; or a clean contemporaneous derivative | Digital image of an original; a duplicate-original made within days |
| Normal | Derivative with primary information; or original with secondary information | Compiled database with images; census facts about members other than the informant |
| Low | Derivative with secondary information | Databases without images; uncited published genealogies |
| Very Low | Hearsay | Family lore, undocumented oral history, online trees used as fact sources |

Per-record-type levels live in each chapter's §8.

### A7 · Page-string subject

The page string ends in a subject: `[locators], [name] [record-noun]`. Locator words are lower case, even at the start of the page string (`p. 57`, `image 62`, `certificate no. 1929-MN-XXXXXX`, `district 009 Blegstad`); names keep their capitals.

- **Record-noun** says what was cited and in what form; see *Record nouns* below.
- **Non-head household member:** `[Subject] in [Head-surname] household`.
- **Couples:** hyphenated surnames (`Larsson-Söderström marriage entry`), not "and". Full given names go in the FRN, except a newspaper item's FRN, which repeats the page string's subject (B.3 §7).

**Parenthetical categories.** Each answers one question:

| Category | Question | Patterns |
| --- | --- | --- |
| 1 Disambiguator | Which entry on the page? | `(b. YYYY)`, `(d. YYYY)`, `(at PLACE)`, `(senior)` / `(junior)`, household role |
| 2 Source-state | What state did the source actively record? | `(widow)`, `(unmarried)`, `(both in first marriage)`, `(boarder)`, `(naturalized YYYY)`, occupation |
| 3 Evidence-quality flag | Why is this evidence not direct? | `(KIND inferred from CONTEXT)`, `(stated age N)`, `(named at OTHER-PERSON's EVENT)` |

- Use a **disambiguator** only when more than one entry could match.
- A **source-state** note records something the source states, never an inference.
- An **evidence-quality flag** explains a lower confidence, or why the subject differs from the entry's own subject (a relative, informant, witness, next of kin, or beneficiary named in someone else's record).

**Combining.** One set of parentheses, comma-separated, always in the order 1, 2, 3:

- `Per Persson (b. 1773, retired soldier, birth year inferred from age)`
- `Per Larsson (b. 1848, naturalized 1894, birth year inferred from age)`
- `John Grund (junior, son, stated age 14)`
- `Anna Larsson (widow, informant on Per Larsson's death certificate)`

**Placement.** The parentheses follow the name. They follow the record noun instead when they describe the record itself (`Per Larsson death certificate (amended)`, `Larsson-Söderström marriage entry (by license)`) or everyone the subject covers, such as a couple or a whole household (`Steve Maisuk household (birth years inferred from ages)`).

**What it is cited for.** A page string may end with what the citation is cited for, in parentheses after everything else, lower case except for names: `11 July 1917, p. 3, col. 1, Olaf Nygren household news mention (date and attendees)`. Add it when one item gives several citations that nothing else in the page string tells apart (A3), or when the citation is for something its record noun does not say; leave it out otherwise. The SRN ends the same way, and the FRN gives it as `(documenting …)` at the end of the item it describes, before the image, film, or holding clause: `…, Olaf Nygren household news mention (documenting date and attendees); digital image, …` (B.3 Example 14).

**Record nouns.** The record noun comes from the record type's list in its chapter's §9 *Record nouns* table; the first noun listed is the default. A record type missing from that table takes no record noun. The noun names the form of what you cite:

| Form | What it is | Noun |
| --- | --- | --- |
| entry | An item in an original register or book | `[event] entry`: `birth and baptism entry`, `marriage entry`, `estate entry` |
| record | A standalone original document | Its own name when it has one (`death certificate`, `WWII draft card`, `obituary`); otherwise `[event] record` |
| household | A census household, the one noun without a form word | `household` |
| index entry | A line in an index or database made from the records | `birth and baptism index entry` |
| transcript | A full word-for-word copy made later | `birth and baptism transcript` |
| extract | A word-for-word copy of part of a record | `birth and baptism extract` |
| abstract | A summary of a record's key facts | `death certificate abstract` |

§9 lists original nouns only. For a copy or index, replace a final `entry` with the form (`birth and baptism entry` → `birth and baptism index entry`); after any other noun, add the form (`death certificate abstract`, `household transcript`). In the FRN, an index entry or transcript was read in a database: write `database, [platform] ([URL] : accessed [date])` in place of `digital image, …`.

### A8 · Title

Titles are EE locality-led: largest jurisdiction first, then record series/type and identifier, then year-range. A formal collection name may follow but never leads.

```
[Country], [Province/State], [Locality], [record series/type] [identifier], [year-range]
```

A Norwegian or Swedish series keeps its own name, followed by a bracketed English gloss (EE 2.28), the same gloss the FRN uses: `Klokkerbok [parish register (copy)] I 2`, `Husförhörslängder [household examinations] AI:11`.

| Domain | Old form | Current form |
| --- | --- | --- |
| Norwegian parish | `Eidsvoll prestekontor Kirkebøker, Ministerialbok no. I 5, 1862–1869` | `Norway, Akershus, Eidsvoll, Ministerialbok [parish register] I 5, 1862–1869` |
| Swedish parish | `Norra Ny kyrkoarkiv, Husförhörslängder, AI:11` | `Sweden, Värmland, Norra Ny, Husförhörslängder [household examinations] AI:11` |
| US state vital | `Minnesota. Dept. of Health…` | `Minnesota, death certificates, 1908–2002` |

Allowed variations:

- **US federal census** leads year first (`1920 U.S. Federal Census, St. Louis County, Minnesota`); EE 6.10 permits this.
- **Series records** (headstone applications, naturalizations): the series name leads, after the locality and court when the series has them (`Minnesota, St. Louis County, District Court, Naturalization Records, 1888–1955`; the national headstone series has neither).
- **Periodicals** (directories, newspapers): publication identity leads, year placed for the specific issue.

The machine path never goes in the Title (A4).

### A9 · Repository

Decide in this order:

1. **A physical archive holds the original** → name it (`Statsarkivet i Oslo`, `Riksarkivet`, `Värmlandsarkiv`, `National Archives`, `[State] Historical Society`, `[County] County Courthouse`, `Family History Library` when a microfilm number applies). A specific NARA facility goes in the FRN, not here.
2. **A family member or private party holds it** → `[Custodian], private collection` (EE 4.24 to 4.29).
3. **It is a publication or online-only platform** → blank. A website is a publication, not a repository (EE 2.34); the same holds for library-held books.

Find a Grave, Ancestry, FamilySearch, Newspapers.com and similar platforms are **publishers**: name them in Pubinfo. When a record lives in a physical archive but was accessed through a platform, Repository names the archive and Pubinfo names the platform.

### A10 · Pubinfo

**Genealogical records:** `[medium], [platform] (homepage URL).`

| Medium | Use for |
| --- | --- |
| `Digital images` | Image-based platforms |
| `Database with images` | Transcribed databases with image links |
| `Database` | Index-only databases |
| `Microfilm` | Film read on a reader at a library or archive. The Pubinfo names the film's maker, with no URL: `Microfilm, Minnesota Historical Society.` |

Only the platform homepage goes here; collection and image URLs go in the FRN. Examples: `Digital images, Digitalarkivet (https://www.digitalarkivet.no).` · `Database with images, Find a Grave (https://www.findagrave.com).`

**Film read in person** has no URL or access date, so the FRN names the film where it would name a digital image, and cites nothing behind it: `…, Peter L. Grund; Minnesota Historical Society microfilm SAM 227, reel 4.` A copy you print or photograph from the reader is your working copy, not another layer: cite the film.

**Published works (imprint variant):**

| Type | Pubinfo |
| --- | --- |
| Print book | `[City]: [Publisher], year.` |
| E-book / audiobook / CD-DVD | `[City]: [Publisher], year. [Format].` Never omit the format; editions differ (EE 13.60). |
| Online book via a library platform | `[City]: [Publisher], year. Digital images, [Platform] (URL).` |
| Funeral program | `[City]: [Funeral home], date.` |
| Audio interview | `Recorded interview, [city], date.` |
| Online video | `Online video, [Platform] (URL), year.` |
| Personal research | `Unpublished research, [location], [year-range].` |

Punctuation: in FRN prose the publication parenthetical follows the title with no preceding punctuation, `(City: Publisher, year),` (EE 13.2). The Source List Entry uses `City: Publisher, year.`

**Platforms:**

| Platform | Homepage URL |
| --- | --- |
| Digitalarkivet | `https://www.digitalarkivet.no` |
| Riksarkivet (incl. SVAR) | `https://sok.riksarkivet.se` |
| ArkivDigital | `https://www.arkivdigital.se` |
| Nasjonalbiblioteket | `https://www.nb.no` |
| Ancestry | `https://www.ancestry.com` |
| FamilySearch | `https://www.familysearch.org` |
| Find a Grave | `https://www.findagrave.com` |
| Newspapers.com | `https://www.newspapers.com` |
| Fold3 | `https://www.fold3.com` |
| Chronicling America | `https://chroniclingamerica.loc.gov` |
| GenealogyBank | `https://www.genealogybank.com` |
| YouTube | `https://www.youtube.com` |
| Lantmäteriet | `https://historiskakartor.lantmateriet.se` |

**When a record has more than one home** (two platforms, or a platform and a library's film), it is still one Source (A1). Pick the home Pubinfo names in this order:

1. The image edition over the index-only edition.
2. Between platforms, the system of record (e.g. Digitalarkivet for Norwegian parish and census images, even when FamilySearch has the same scans).
3. The home most used by citations on this Source.

Each FRN names the home its own item was read in, even one Pubinfo does not name: an item read on film ends with the film, and an item read online ends with its platform (B.3 Example 13).

### A11 · Bibliography

Gramps fields are built for in-app display. For the book's bibliography, transform them into EE Source List Entries; never print the Title field directly.

**Locality-based sources** (parish, civil, court, land, census, cemetery, county/state) use EE 2.48, By Geographic Locale:

```
[Country]. [Province/State]. [Locality]. [Series] [English gloss], [volume] ([year-range]). [Repository], [call number]. [Medium]. [Publisher]. [URL] : [access year].
```

> Sweden. Värmland. Norra Ny församling. Husförhörslängder \[household examinations\], AI:11 (1812–1820). Värmlandsarkiv, SE/VA/13398/A I/11. Digital images. Riksarkivet. https://sok.riksarkivet.se : 2026.

> Minnesota. St. Louis County. Forest Hill Cemetery. Find a Grave Memorials. Database with images. https://www.findagrave.com : 2026.

**Arrangement:**

- Group under a country (or state) header, then alphabetize by locality.
- Online-only databases go in their own group at the end, alphabetized by title, with no repository (EE 2.34).
- Authored works are arranged by author surname (EE 2.46), manuscript collections by collection name (EE 2.47), privately held artifacts by custodian (EE 4.24 to 4.29).
- Use the access year only (`: 2026`); the FRN has the full date.

**EE anchors (verified against `book.txt`):** 2.45 Arrangement options, 2.46 By Author-Title, 2.47 By Collection, 2.48 By Geographic Locale, 2.49 By Repository.

### A12 · Privacy

Apply EE 4.31 to living informants (interviewees, correspondents, custodians): keep their street address in working files, never in a published citation, while they are alive.

- In the FRN, write `[ADDRESS FOR PRIVATE USE]` or give only the locality ("Duluth, Minnesota").
- After the person's death the address may be published as historical data.
- The interviewee, not the interviewer, is the Source author. The FRN names both, plus their relationship when relevant (`son-in-law of the deceased`).

### A13 · Universal abbreviations

Used in FRN, SRN, and Abbrev wherever a locator is needed (EE 2.53):

| Abbrev. | Meaning |
| --- | --- |
| `p.` | page |
| `pp.` | pages / range |
| `vol.` | volume |
| `col.` | column |
| `no.` | number |
| `fol.` | folio |

`p.` can be dropped for a single bare page number in a book or article, but is kept whenever two numbers share a field (page + column). Domain abbreviations (US geographic, state, record-type, archive; Scandinavian short forms) are in each chapter's §10.

## Part B.1: Norwegian sources

Norwegian church, civil, court, and land records. EE covers Norway thinly (11.53 lumps all Scandinavia into one FamilySearch example), so this chapter adapts EE Chapter 2 and the foreign-register templates 11.47 Germany, 11.50 Italy, and 11.56 Switzerland.

**Four features of the Norwegian system drive the rules below:**

- **Two parallel parish books.** The *ministerialbok* is the minister's original; the *klokkerbok* is the sacristan's duplicate. Both are citable (see §9, which to cite).
- **Regional archives.** Riksarkivet (Oslo) holds national records; nine Statsarkiver hold regional ones. Eidsvoll parish records are at Statsarkivet i Oslo (SAO).
- **One platform.** Digitalarkivet hosts both, with permalinks like `https://urn.digitalarkivet.no/URN:NBN:no-...`.
- **Patronymics** through the late 1800s (`Karen Indiana Evensdatter` = daughter of Even), so the patronymic disambiguator matters (§9).

### §1 Scope

One Source per archival volume / fond (A1). Record types covered:

- **Parish records (kirkebøker):** ministerialbok and klokkerbok; baptisms, confirmations, marriages, burials.
- **Census (folketelling):** the 1801 nominal census and the decennial 1865+ censuses.
- **Court records (sorenskriverarkiv):** tingbøker (court journals).
- **Probate (skifteprotokoller):** estate inventories and distributions.
- **Land (matrikkel):** cadastral tax-assessment registers.
- **Religious-practice records:** confirmation and communion are cited *within* the kirkebok Source (no Source of their own); parish meeting minutes (*menighetsmøteprotokoll*) are a separate series with their own Source.

### §2 Source author

Parish or court name alone, no country or umbrella prefix.

| Record type | Author |
| --- | --- |
| Parish records | `[Parish] prestekontor` (e.g. `Eidsvoll prestekontor`) |
| Pre-1850 parish records (older term applies) | `[Prestegjeld] prestegjeld` |
| Folketelling | `Riksarkivet` (preferred), or `Statistisk sentralbyrå` for post-1875 censuses processed by SSB |
| Court records | The creating body, e.g. `Eidsvoll sorenskriveri` |
| Probate | The court that conducted it, usually `[District] sorenskriveri` |
| Matrikkel | `Riksarkivet` for centrally held volumes; `Statens kartverk` for modern data |
| Confirmation, communion | `[Parish] prestekontor` |

Write bare `Riksarkivet`, not `Nasjonalarkivet (Riksarkivet)`; the Nasjonalarkivet name was used only briefly (2010 to 2018).

### §3 Repository

| Repository | Use for |
| --- | --- |
| `Statsarkivet i Oslo` | Regional records with NAD prefix `AV/SAO-...` (Eidsvoll parish, Akershus courts) |
| `Statsarkivet i Hamar` | Hedmark records with NAD prefix `AV/SAH-...` |
| `Riksarkivet` | Centrally held records: folketelling, some national court records, matrikkel (`AV/RA-...`) |

For other regional archives use `Statsarkivet i [city]` (list at arkivverket.no) and add them here as research expands. Digitalarkivet is a platform, never a Repository (A9).

### §4 Source title

Locality-led (A8), with the series in its Norwegian name followed by an English gloss in square brackets (EE 2.28), as in B.2 §4: `Norway, [fylke or amt], [parish or court], [Norwegian series name] [English gloss] [volume], [year-range]`. Capitalize the series name, and use the same gloss in the FRN and bibliography. Year-ranges follow the volume identifier with no parentheses (Digitalarkivet's own form), using en dashes.

| Record type | Title template | Example |
| --- | --- | --- |
| Parish, minister's original | `Norway, [Fylke/Amt], [Parish], Ministerialbok [parish register] [Roman] [Arabic], [years]` | `Norway, Akershus, Eidsvoll, Ministerialbok [parish register] I 5, 1862–1869` |
| Parish, klokkerbok | `…, Klokkerbok [parish register (copy)] [Roman] [Arabic], [years]` | `Norway, Akershus, Eidsvoll, Klokkerbok [parish register (copy)] I 2, 1866–1871` |
| Folketelling 1801 | `Norway, [Amt], [Prestegjeld], Folketelling [census] 1801, [reference if needed]` | `Norway, Akershus, Eidsvoll, Folketelling [census] 1801, L0009` |
| Folketelling 1865+ | `Norway, [Amt or fylke], [Prestegjeld or herred], Folketelling [census] [year]` | `Norway, Akershus, Eidsvoll, Folketelling [census] 1875` |
| Court (tingbok) | `Norway, [Fylke/Amt], [Sorenskriveri], Tingbok [court journal] [series], [years]` | `Norway, Akershus, Eidsvoll sorenskriveri, Tingbok [court journal] A I 5, 1820–1830` |
| Probate | `Norway, [Fylke/Amt], [Sorenskriveri], Skifteprotokoll [probate register] [series], [years]` | `Norway, Akershus, Eidsvoll sorenskriveri, Skifteprotokoll [probate register] II 3, 1815–1825` |
| Matrikkel | `Norway, [Fylke or amt], [Prestegjeld or herred], Matrikkel [land register] [year], [protocol if needed]` | `Norway, Akershus amt, Eidsvoll prestegjeld, Matrikkel [land register] 1838` |
| Meeting minutes | `Norway, [Fylke/Amt], [Parish], Menighetsmøteprotokoll [parish meeting minutes] [vol], [years]` | `Norway, Akershus, Eidsvoll, Menighetsmøteprotokoll [parish meeting minutes] 1, 1870–1895` |

Notes:

- **Volume numbers:** the Roman numeral is the series within the parish archive; the Arabic is the volume in that series.
- **Jurisdiction names:** use whatever the source uses. Pre-1900 forms use *prestegjeld* and *amt*; the 1900 census uses *herred* and *fylke* (e.g. `Norway, Akershus fylke, Eidsvoll herred, Folketelling [census] 1900`).
- **Court archives:** each sorenskriveri kept tingbøker and skifteprotokoller as separate series; the series prefix (A I, II…) identifies which.
- **Matrikkel years:** 1665 (Skattematrikkelen, first systematic register), 1723 (draft revision), 1838 (reform), 1886/1904 (begun 1886, published 1904), then the GAB register (1980s) and digital Matrikkelen (2010+). Matrikkelnummer and løpenummer are citation-level.
- **Confirmation and communion** have no Title of their own; they use the kirkebok's Title. If a parish kept a *kommunikantprotokoll* catalogued as its own volume, treat it like meeting minutes.

### §5 Locator tokens

| Form | Home |
| --- | --- |
| `I 5` (parish), `A I 5` (tingbok), bare year (folketelling) | Title and Abbrev |
| NAD path `AV/SAO-A-10888/G/Ga/L0002` | Call number only |

Reading a NAD path: `AV/[archive code]-[series prefix]-[fond]/[sub-series]/[item]/[volume]`.

- `AV/SAO-A-10888/G/Ga/L0002` = Arkivverket / Statsarkivet i Oslo / fond A-10888 (Eidsvoll prestekontor) / G (kirkebøker) / Ga (klokkerbøker) / volume L0002.
- `AV/RA-S-2231/E` = Arkivverket / Riksarkivet / series S-2231 (folketelling-related) / E (folketellinger).

### §6 Pubinfo

- Parish image scans: `Digital images, Digitalarkivet (https://www.digitalarkivet.no).`
- Folketelling and other transcribed databases: `Database with images, Digitalarkivet (https://www.digitalarkivet.no).`

Digitalarkivet is the system of record; cite it even when FamilySearch has the same scans, and mention FamilySearch only in the FRN (A10).

### §7 Page-string templates

| Record type | Template | Example |
| --- | --- | --- |
| Parish | `p. [P] (image [I]), [entry], [subject]` | `p. 12 (image 24), no. 8, Karen Indiana Evensdatter baptism entry` |
| Folketelling 1801 | `gård [N] ([name]), household [N], person [N], [Head] household` | `gård 234 (Vinger), household 1, person 1, Anders Hansen household` |
| Folketelling 1865+ | `district [N] [name], p. [N], household [N], person [N], [Head] household` | `district 009 Blegstad, p. 1270, household 01, person 006, Karen Indiana Evensdatter in Hansen household` |
| Tingbok | `folio [F], [date or session], [parties or subject]` |  |
| Skifteprotokoll | `folio [F]–[F], [Deceased] estate entry` | `folio 145–148, Anders Hansen estate entry` |
| Matrikkel | `gård no. [matrikkelnr.], [gård name], [løpenummer if specific], [owner or topic]` | `gård no. 234, Vinger gård, løpenummer 12, Anders Hansen matrikkel entry` |
| Confirmation **Pending review** | `confirmations, p. [P] (image [I]), no. [N], [Subject] confirmation entry` | `confirmations, p. 88 (image 91), no. 14, Karen Indiana Evensdatter confirmation entry` |
| Communion **Pending review** | `communicants, p. [P] (image [I]), [Subject] communion entry` | `communicants, p. 204 (image 210), Anders Hansen communion entry` |
| Meeting minutes **Pending review** | `p. [P] (image [I]), [date], [subject] minute entry` |  |

- *District* in 1865+ censuses is Digitalarkivet's *tellekrets*; household and person numbers are its assigned IDs.
- Skifteprotokoller use **folio** numbering (both sides of a leaf together) and span the whole skifte.
- **Unpaginated fallback:** when the page has no number, lead with the image number: `image [I], [entry], [subject]` (as in B.2 §7).

### §8 Confidence

| Record type | Confidence |
| --- | --- |
| Ministerialbok | Very High for an entry written by the minister within days; High for primary information given as indirect evidence |
| Klokkerbok | High by default (contemporaneous duplicate); Normal if clearly copied years later (inconsistent inks, batch-style entries) |
| Folketelling 1801 | Very High for residence (enumerator visited each gård); Normal for ages |
| Folketelling 1865+ | High for residence and household; Normal for ages and birthplaces |
| Skifteprotokoller | High for the death and primary heirs; Normal for inferred relationships |
| Matrikkel | High for the cadastral fact; Low for any genealogical inference between successive owners |
| Confirmation entry **Pending review** | High for the confirmation; Normal for stated age / implied birth year |
| Communion entry **Pending review** | High for residence/membership at that date; Normal for inferred detail |
| Meeting minutes **Pending review** | High for the recorded act or attendance; Normal for inferences |

The klokkerbok rests on EE 1.30 (Duplicate Originals): a contemporaneous duplicate, not a derivative. Differences between the two books are themselves evidence.

### §9 Subject vocabulary

**Record nouns** (A7); the first is the default:

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

| Event | Subject format | Example |
| --- | --- | --- |
| Birth and baptism | `[Given Surname] birth and baptism entry` | `Karen Indiana Evensdatter birth and baptism entry` |
| Baptism only | `[Given Surname] baptism entry` | `Thor Emil baptism entry` |
| Death / burial | `[Given Surname] death entry` / `burial entry` | `Anders Hansen burial entry` |
| Marriage | `[Surname]-[Surname] marriage entry` | `Hansen-Olsen marriage entry` |
| Census head | `[Head] household` | `Anders Hansen household` |
| Census non-head | `[Subject] in [Head-surname] household` | `Karen Indiana Evensdatter in Hansen household` |
| Skifte | `[Deceased] estate entry` | `Anders Hansen estate entry` |
| Court matter | `[Parties or subject] [event type] entry` | `Hansen-Olsen land dispute entry` |
| Matrikkel | `[Gård], [owner] matrikkel entry` | `Vinger gård, Anders Hansen matrikkel entry` |
| Confirmation / communion **Pending review** | `[Given Surname] confirmation entry` / `communion entry` | `Anders Hansen communion entry` |
| Meeting minute **Pending review** | `[meeting subject] minute entry` | `church building fund minute entry` |

**Norwegian parentheticals** (categories per A7). Patronymics make father and son look unrelated (`Anders Hansen`, `Anders Pedersen`), so the relationship must be stated.

| Situation | Cat. | Phrasing | Example |
| --- | --- | --- | --- |
| Patronymic | 1 | `(son of [Father])` / `(daughter of [Father])` | `Karen Evensdatter (daughter of Even Hansen)` |
| Same name, by farm | 1 | `(at [Gård])` | `Anders Hansen (at Vinger gård) household` |
| Female / male servant | 2 | `(tjenestepige)` / `(tjenestedreng)` | `Karen Indiana Evensdatter (tjenestepige) in Hansen household` |
| Poor-relief boarder | 2 | `(fattigdreng)` |  |
| General servant / dependent | 2 | `(tyende)` |  |
| Lodger with no plot | 2 | `(inderst)` |  |
| Cottager renting a plot | 2 | `(husmand)` |  |
| Widow / widower | 2 | `(enke)` / `(enkemann)` | `Anders Hansen (enkemann) household` |
| First / second marriage | 2 | `(første ekteskap)` / `(annen ekteskap)` |  |
| Stated census age | 3 | `(stated age N)` | `Karen Indiana Evensdatter (stated age 14)` |
| Named only in another's record | 3 | `(named at OTHER-PERSON's EVENT)` | `Even Hansen (named at daughter Karen's baptism)` |

For a couple in one household, cite the head; list the spouse as a sub-citation if needed.

**Ministerialbok or klokkerbok?** Prefer the ministerialbok. Klokkerbøker were copied at intervals and may contain errors or omissions. If you cite a klokkerbok because the ministerialbok is unavailable or damaged, say so in the FRN.

**One vs. two citations, Norwegian cases (A3):**

- Baptism naming both parents: one citation if both were present; separate if the father is only `(named at child's baptism)` because he was dead or absent.
- Folketelling household: one citation for the household's residence; separate for anyone whose evidence is inferred (e.g. recently *flyttet til byen*).
- Skifte listing heirs: one citation for the death; separate for any heir whose relationship is the thing being established.

### §10 Abbrev

House variation: the record-type word is lowercased (EE 2.29 keeps original capitals; lowercase gives visual contrast with the Title), and the Abbrev drops the gloss. Parish format: `[Parish] [kirkebok|klokkerbok] [vol] ([year-range])`. Court format: `[Sorenskriveri] [tingbok|skifteprotokoll] [vol] ([year-range])`. Unlike the Title, the Abbrev puts the year-range in parentheses.

| Title series | Abbrev word | Example |
| --- | --- | --- |
| Ministerialbok I 5 | `kirkebok I 5` | `Eidsvoll kirkebok I 5 (1862–1869)` |
| Klokkerbok I 2 | `klokkerbok I 2` | `Eidsvoll klokkerbok I 2 (1866–1871)` |
| Folketelling YYYY | `folketelling YYYY` | `Eidsvoll folketelling 1875` |
| Tingbok A I 5 | `tingbok A I 5` | `Eidsvoll sorenskriveri tingbok A I 5 (1820–1830)` |
| Skifteprotokoll II 3 | `skifteprotokoll II 3` | `Eidsvoll sorenskriveri skifteprotokoll II 3 (1815–1825)` |
| Matrikkel 1838 | `matrikkel 1838` | `Eidsvoll matrikkel 1838` |
| Menighetsmøteprotokoll 1 **Pending review** | `menighetsmøteprotokoll 1` | `Eidsvoll menighetsmøteprotokoll 1 (1870–1895)` |

**SRN:** the Abbrev, then enough locators to find the entry, then the page string's subject: `Eidsvoll klokkerbok I 2 (1866–1871), p. 57, no. 21, Thor Emil birth and baptism entry.` Locators may take short forms (A13, `løpenr.`). The subject keeps only a category-1 disambiguator (A7) such as `(b. 1773)`; source-state notes and evidence flags stay in the page string.

### §11 Bibliography

A11 geographic form (EE 2.48): country, fylke, prestegjeld/herred, series + bracketed English gloss (EE 2.28), volume + years, repository + call number, medium, publisher, URL : year. Group under `Norway:`, alphabetize by fylke then prestegjeld.

| Record type | Source List Entry |
| --- | --- |
| Parish | Norway. Akershus. Eidsvoll prestegjeld. Klokkerbok \[parish register (copy)\], I 2 (1866–1871). Statsarkivet i Oslo, AV/SAO-A-10888/G/Ga/L0002. Digital images. Digitalarkivet. https://www.digitalarkivet.no : 2026. |
| Folketelling | Norway. Akershus. Eidsvoll prestegjeld. Folketelling \[census\] 1875. Riksarkivet, AV/RA-S-2231/E. Database with images. Digitalarkivet. https://www.digitalarkivet.no : 2026. |
| Tingbok | Norway. Akershus. Eidsvoll sorenskriveri \[Eidsvoll district court\], Tingbok \[court journal\], A I 5 (1820–1830). Statsarkivet i Oslo, AV/SAO-A-10063/F/Fa/L0005. Digital images. Digitalarkivet. https://www.digitalarkivet.no : 2026. |
| Skifteprotokoll | Norway. Akershus. Eidsvoll sorenskriveri \[Eidsvoll district court\], Skifteprotokoll \[probate register\], II 3 (1815–1825). Statsarkivet i Oslo, AV/SAO-A-10063/H/Hb/L0003. Digital images. Digitalarkivet. https://www.digitalarkivet.no : 2026. |
| Matrikkel | Norway. Akershus. Eidsvoll prestegjeld. Matrikkel \[land register\] 1838. Riksarkivet. Database with images. Digitalarkivet. https://www.digitalarkivet.no : 2026. |
| Meeting minutes **Pending review** | Norway. Akershus. Eidsvoll prestegjeld. Menighetsmøteprotokoll \[parish meeting minutes\], 1 (1870–1895). Statsarkivet i Oslo. Digital images. Digitalarkivet. https://www.digitalarkivet.no : 2026. |

Compare EE 11.50 Italy: `Italy. Palermo. Gratteri. Registri degli Atti di Nascita [Registers of the Acts of Birth], 1862–1910. Ufficio dello Stato Civile, Gratteri.` Confirmation and communion have no entry of their own. Bygdebøker are arranged author-led (Part B.4). A bibliography script can branch on Repository (`Statsarkivet i …` / `Riksarkivet` → Norway form) and add glosses from §4.

### §12 Worked examples

#### Example 1: Parish record (klokkerbok)

Thor Emil, born 1 September 1869 in Eidsvoll, baptized 16 January 1870. EE analogues: 11.56 Switzerland, 11.50 Italy.

| Source field | Value |
| --- | --- |
| Title | `Norway, Akershus, Eidsvoll, Klokkerbok [parish register (copy)] I 2, 1866–1871` |
| Abbrev | `Eidsvoll klokkerbok I 2 (1866–1871)` |
| Author | `Eidsvoll prestekontor` |
| Pubinfo | `Digital images, Digitalarkivet (https://www.digitalarkivet.no).` |
| Repository | `Statsarkivet i Oslo` |
| Call number | `AV/SAO-A-10888/G/Ga/L0002` |
| **Citation** page | `p. 57 (image 62), no. 21, Thor Emil birth and baptism entry` |
| Confidence | High (klokkerbok, primary, direct) |

**FRN:** Eidsvoll prestekontor, Klokkerbok \[parish register (copy)\] no. I 2, 1866–1871, p. 57, no. 21, Thor Emil (born 1 September 1869; baptized 16 January 1870), son of Christian Henningsen and Anne Marthe Bergersdatter, baptized at Eidsvoll church; digital image, Digitalarkivet (https://urn.digitalarkivet.no/URN:NBN:no-a1450-kb20060313011115.jpg : accessed 17 April 2026); citing Statsarkivet i Oslo, AV/SAO-A-10888/G/Ga/L0002.

**SRN:** Eidsvoll klokkerbok I 2 (1866–1871), p. 57, no. 21, Thor Emil birth and baptism entry.

High, not Very High, because this is the duplicate (EE 1.30). If the ministerialbok is also consulted and agrees, the combined citation can rise to Very High.

#### Example 2: 1875 folketelling

Karen Indiana Evensdatter, 14, tjenestepige in Jens Hansen's household at Blegstad, Eidsvoll sokn. EE analogues: 11.53, 11.47.

| Source field | Value |
| --- | --- |
| Title | `Norway, Akershus, Eidsvoll, Folketelling [census] 1875` |
| Abbrev | `Eidsvoll folketelling 1875` |
| Author | `Riksarkivet` |
| Pubinfo | `Database with images, Digitalarkivet (https://www.digitalarkivet.no).` |
| Repository | `Riksarkivet` |
| Call number | `AV/RA-S-2231/E` |
| **Citation** page | `district 009 Blegstad, p. 1270, household 01, person 006, Karen Indiana Evensdatter (tjenestepige, stated age 14) in Hansen household` |
| Confidence | High (residence); Normal (stated age) |

**FRN:** Folketelling \[census\] 1875, Akershus fylke, Eidsvoll prestegjeld, Eidsvoll sokn, district 009 Blegstad, p. 1270, household no. 01, person no. 006, Karen Indiana Evensdatter (tjenestepige, stated age 14, in Jens Hansen's household); digital image, Digitalarkivet (https://www.digitalarkivet.no/ft20110110330371 : accessed 26 April 2026); transcribed entry at https://www.digitalarkivet.no/pf01052052005225; citing Riksarkivet, Statistisk sentralbyrå, Sosioøkonomiske emner, Folketellinger, boliger og boforhold, E: Folketellinger, source ID 52052; archive reference AV/RA-S-2231/E.

**SRN:** Eidsvoll folketelling 1875, p. 1270, household 01, Karen Indiana Evensdatter in Hansen household.

The parenthetical combines a source-state note (her role) and an evidence flag (stated age), in A7 order. Both URLs are given because the transcript is searchable in ways the image is not.

#### Example 3: Probate (skifteprotokoll)

Hypothetical: Anders Hansen, died 1822 at Vinger gård. EE analogues: 11.50 Italy, 9.32.

| Source field | Value |
| --- | --- |
| Title | `Norway, Akershus, Eidsvoll sorenskriveri, Skifteprotokoll [probate register] II 3, 1815–1825` |
| Abbrev | `Eidsvoll sorenskriveri skifteprotokoll II 3 (1815–1825)` |
| Author | `Eidsvoll sorenskriveri` |
| Pubinfo | `Digital images, Digitalarkivet (https://www.digitalarkivet.no).` |
| Repository | `Statsarkivet i Oslo` |
| Call number | `AV/SAO-A-10063/H/Hb/L0003` |
| **Citation** page | `folio 145–148, Anders Hansen estate entry` |
| Confidence | High (death); Normal (inferred heir relationships) |

**FRN:** Eidsvoll sorenskriveri \[Eidsvoll district court\], Skifteprotokoll \[probate register\] II 3, 1815–1825, fol. 145–148, estate inventory of Anders Hansen, Vinger gård, died 1822; digital image, Digitalarkivet (https://www.digitalarkivet.no/... : accessed 9 May 2026); citing Statsarkivet i Oslo, AV/SAO-A-10063/H/Hb/L0003.

**SRN:** Eidsvoll sorenskriveri skifteprotokoll II 3 (1815–1825), fol. 145–148, Anders Hansen estate entry.

Two glosses per EE 2.28. Heirs whose relationship is being established get their own citations with evidence flags.

#### Example 4: Matrikkel

Hypothetical: Vinger gård listed in the 1838 matrikkel under Anders Hansen. EE: geographic form, 2.48.

| Source field | Value |
| --- | --- |
| Title | `Norway, Akershus amt, Eidsvoll prestegjeld, Matrikkel [land register] 1838` |
| Abbrev | `Eidsvoll matrikkel 1838` |
| Author | `Riksarkivet` |
| Pubinfo | `Database with images, Digitalarkivet (https://www.digitalarkivet.no).` |
| Repository | `Riksarkivet` |
| Call number | **Open:** varies by volume; check Digitalarkivet's NAD entry |
| **Citation** page | `gård no. 234, Vinger gård, løpenummer 12, Anders Hansen matrikkel entry` |
| Confidence | High (cadastral assessment); Low (genealogical inference) |

**FRN:** Matrikkel \[land register\] 1838, Akershus amt, Eidsvoll prestegjeld, gård no. 234, Vinger gård, løpenummer 12, listed owner Anders Hansen; digital image, Digitalarkivet (https://www.digitalarkivet.no/... : accessed 9 May 2026); citing Riksarkivet.

**SRN:** Eidsvoll matrikkel 1838, gård 234 Vinger, løpenr. 12, Anders Hansen matrikkel entry.

Owner of record can lag actual occupancy and inheritance by years, so pair the matrikkel with a parish record or skifte for a firm claim. Gård numbers do not always carry across revisions; trace continuity by name and locality. Norway renamed *amt* to *fylke* in 1919.

#### Example 5: Confirmation **Pending review**

Hypothetical: Karen Indiana Evensdatter, confirmed 1869 at Eidsvoll church. Cited under the same klokkerbok Source as Example 1.

| Field | Value |
| --- | --- |
| Source | Same as Example 1 |
| **Citation** page | `confirmations, p. 88 (image 91), no. 14, Karen Indiana Evensdatter confirmation entry` |
| Confidence | High (confirmation); Normal (stated age / implied birth year) |

**FRN:** Eidsvoll prestekontor, Klokkerbok \[parish register (copy)\] no. I 2, 1866–1871, confirmations section, p. 88, no. 14, Karen Indiana Evensdatter (daughter of Even Hansen), confirmed at Eidsvoll church 1869; digital image, Digitalarkivet (https://www.digitalarkivet.no/... : accessed 15 June 2026); citing Statsarkivet i Oslo, AV/SAO-A-10888/G/Ga/L0002.

**SRN:** Eidsvoll klokkerbok I 2 (1866–1871), confirmations, p. 88, no. 14, Karen Indiana Evensdatter confirmation entry.

## Part B.2: Swedish sources

Swedish church, court, census, and land-survey records. EE coverage is thin (11.53), so this chapter adapts EE Chapter 2 and the foreign-register templates 11.47 Germany, 11.50 Italy, and 11.56 Switzerland.

### §1 Scope

One Source per discrete NAD fond: each parish kyrkoarkiv volume series, each häradsrätt series, each SVAR database (A1). Record types covered:

- **Parish records (kyrkoarkiv):** Husförhörslängder (clerical survey), Lysnings- och Vigselbok (banns and marriage), Födelse- och dopböcker (birth and baptism), Dödbok (death/burial).
- **Court records:** Bouppteckningar (estate inventories) and other häradsrätt series.
- **SVAR databases:** Folkräkning (census) and other Riksarkivet databases.
- **Religious records** **Pending review:** confirmation and communion cited *within* the husförhörslängd; parish meeting minutes (*Sockenstämmoprotokoll*) are a separate series with their own Source.
- **Land-survey acts (Lantmäteriet)** **Pending review:** *lantmäteriförrättningar* (ägodelning, skogsdelning, storskifte, laga skifte, enskifte, gränsbestämning, avvittring). One numbered act = one Source, even when it spans years (17-NON-148: opened 1856, concluded 1862, confirmed 1863). Session, signing, and confirmation dates go in the FRN; a landowner's lott, protocol page, or ägofigur goes in the page string.

### §2 Source author

| Record type | Author |
| --- | --- |
| Parish records, incl. confirmation, communion, minutes | `[Parish] församling` |
| SVAR databases and other central records | `Riksarkivet` (covers SVAR) |
| Court and other state bodies | The creating body, e.g. `Älvdals häradsrätt` |
| Land survey, `R`-numbered national series **Pending review** | `Lantmäteristyrelsen` |
| Land survey, `NN-XXX-NNN` county series (e.g. `17-NON-148`) **Pending review** | `Lantmäterimyndigheten i Värmlands län` |

No parentheticals (no "Värmland, Sweden", no "Church of Sweden, …"). The surveyor (Brunn, Bradsberg, Jusberg, Ignelius) is never the Author; like an officiating minister, he is named only in the FRN.

### §3 Repository

| Repository | Use for |
| --- | --- |
| `Värmlandsarkiv` | Regional records with NAD prefix `SE/VA/...` (Norra Ny kyrkoarkiv, Älvdals häradsrätt) |
| `Riksarkivet` | Records held centrally in Stockholm |

**Dual treatment for platforms** (confirmed for SVAR; **Pending review** for Lantmäteriet): the platform is a publisher, so the bibliography entry has no repository. The Gramps Repository field may still hold `Riksarkivet` or `Lantmäteriet` for in-app navigation. If you cite a physical survey original rather than the platform, Repository names that archive.

### §4 Source title

Locality-led (A8), with the series in its original Swedish name followed by an English gloss in square brackets (EE 2.28): `Sweden, [län], [parish or härad], [Swedish series name] [English gloss] [volume], [year-range]`. Keep the series name's original capitalization, and use the same gloss as the FRN.

| Record type | Title template | Example |
| --- | --- | --- |
| Clerical survey | `Sweden, [län], [parish], Husförhörslängder [household examinations] [vol], [years]` | `Sweden, Värmland, Norra Ny, Husförhörslängder [household examinations] AI:11, 1812–1820` |
| Banns and marriage | `…, Lysnings- och Vigselbok [banns and marriage book] [vol], [years]` | `Sweden, Värmland, Norra Ny, Lysnings- och Vigselbok [banns and marriage book] E:5, 1861–1884` |
| Birth and baptism | `…, Födelse- och dopböcker [birth and baptism books] [vol], [years]` | `Sweden, Värmland, Norra Ny, Födelse- och dopböcker [birth and baptism books] C:4, 1773–1825` |
| Death / burial | `…, Dödbok [death book] [vol], [years]` | **Open:** no real volume yet |
| Estate inventory | `Sweden, [län], [härad], Bouppteckningar [estate inventories] [vol], [years]` | `Sweden, Värmland, Älvdals härad, Bouppteckningar [estate inventories] FII:26, 1832–1833` |
| SVAR census | `Sweden, [län], [parish], Folkräkning [census] [year]` | `Sweden, Värmland, Norra Ny, Folkräkning [census] 1880` |
| Meeting minutes **Pending review** | `…, Sockenstämmoprotokoll [parish meeting minutes] [vol], [years]` |  |
| Land survey **Pending review** | `Sweden, [län], [parish], [survey type] [English gloss], act [act-no], [years]` | `Sweden, Värmland, Norra Ny, laga skifte [statutory land enclosure], act 17-NON-148, 1856–1862` |

Confirmation and communion use the husförhörslängd's Title. The old collection-led lead (`Norra Ny kyrkoarkiv, …`) is retired; *kyrkoarkiv* may still appear in FRN prose, and the parish stays the Author.

### §5 Locator tokens

| Form | Home |
| --- | --- |
| `AI:11` (colon, no spaces) | Title and Abbrev |
| `SE/VA/13398/A I/11` (NAD, slashes and spaces) | Call number |

Series letters: `A I` husförhörslängder, `C` födelse- och dopböcker, `E` lysnings- och vigselbok, `F II` bouppteckningar. Title/Abbrev close the spaces (`AI:11`, `FII:26`); the NAD path keeps them (`A I/11`, `F II/26`).

### §6 Pubinfo

| Platform | Pubinfo |
| --- | --- |
| Riksarkivet (images) | `Digital images, Riksarkivet (https://sok.riksarkivet.se).` |
| ArkivDigital | `Digital images, ArkivDigital (https://www.arkivdigital.se).` |
| SVAR index only | `Database, Riksarkivet (https://sok.riksarkivet.se).` |
| Lantmäteriet **Pending review** | `Digital images, Lantmäteriet (https://historiskakartor.lantmateriet.se).` |

Some Norra Ny volumes are on both Riksarkivet and ArkivDigital. Each volume is still one Source, with its Pubinfo chosen per the A10 tiebreaks, and each FRN names the platform its item was read on.

### §7 Page-string templates

Standard: `p. [P] (image [I]), [entry], [subject]`. Unpaginated fallback is `image [I], [entry], [subject]`. Each Source is one volume, so the volume is not repeated here (A4).

| Record type | Template | Example |
| --- | --- | --- |
| Husförhörslängd household | `p. [P] (image [I]), [Head] household` | `p. 8 (image 19), Per Persson household` |
| Birth and baptism | `p. [P] (image [I]), no. [N], [Name] birth and baptism entry` | `p. 191 (image 100), no. 34, Lars Persson birth and baptism entry` |
| Banns and marriage | `p. [P] (image [I]), no. [N], [Surname]-[Surname] marriage entry` | `p. 57 (image 62), no. 21, Larsson-Söderström marriage entry` |
| Death / burial | `p. [P] (image [I]), no. [N], [Name] death entry` | `…, Kjerstin Mattsdotter death entry` |
| Estate inventory | `pp. [P]–[P], [Deceased] estate inventory` | `pp. 203–205, Per Persson estate inventory` |
| SVAR census | `p. [P] (image [I]), row [R], family no. [F], [Head] household` | `p. 4, row 33, family no. 1, Lars Persson Ambjörn household` |
| Confirmation / communion **Pending review** | `p. [P] (image [I]), [Name] confirmation entry` / `communion entry` | `p. 8 (image 19), Lars Persson confirmation entry` |
| Meeting minutes **Pending review** | `p. [P] (image [I]), [date or item no.], [Name] parish meeting entry` | `…, meeting of 3 May 1850, Per Persson parish meeting entry` |
| Land survey **Pending review** | `[protocol locator], [name] [record-noun]` | `delningsbeskrivning p. 40, Marit Andersdotter land allotment entry` |

Land-survey record-nouns: `land allotment entry` (a named owner's lott), `signatory entry` (in the signature/owner list), `croft transfer entry` (a torpare's holding changing hands). The act is the Source, so its number is not repeated. More examples: `p. 26, §26, Olof Persson croft transfer entry` (act 17-NON-148) · `signatures p. 8, Olof Halvardsson signatory entry` (act 17-NON-51) · `skiftesläggning, Olof Halvarsson land allotment entry` (act R66).

### §8 Confidence

| Record type | Default | Why |
| --- | --- | --- |
| Death/burial entry near the event | Very High | Original, primary, direct |
| Birth and baptism | Very High (child's birth/baptism) | Original, primary, direct |
| Banns and marriage | High to Very High | Minister recorded the event |
| Husförhörslängd household | High residence; Normal stated age | Ages are reported; split per A3 |
| Bouppteckning | High | Original court record; relationships in it may be secondary |
| SVAR with images | High residence; Normal ages | Derivative database, primary census information |
| SVAR index only | Low | Derivative, no images |
| Confirmation **Pending review** | High | Implied birth year is secondary; split per A3 |
| Communion **Pending review** | High presence/residence; Normal age | Observed by the minister |
| Meeting minutes **Pending review** | High for the meeting's business; Normal/Low for incidental detail |  |
| Land survey **Pending review** | High for what the surveyor recorded (allotments, measurements, signatories, dated proceedings); Normal for secondhand extracts (an embedded 1830 skarförteckning, a back-reference) | Original, contemporaneous state record |

### §9 Subject vocabulary

**Record nouns** (A7); the first is the default:

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

| Event | Subject format | Example |
| --- | --- | --- |
| Birth and baptism (combined volume) | `[Name] birth and baptism entry` | `Lars Persson birth and baptism entry` |
| Baptism only (separate register) | `[Name] baptism entry` | `Lars Persson baptism entry` |
| Death / burial | `[Name] death entry` / `burial entry` | `Kjerstin Mattsdotter death entry` |
| Marriage | `[Surname]-[Surname] marriage entry` | `Larsson-Söderström marriage entry` |
| Household / census | `[Head] household` | `Lars Persson Ambjörn household` |
| Estate inventory | `[Deceased] estate inventory` | `Per Persson estate inventory` |
| Confirmation / communion **Pending review** | `[Name] confirmation entry` / `communion entry` | `Lars Persson communion entry` |
| Meeting minutes **Pending review** | `[Name] parish meeting entry` | `Per Persson parish meeting entry` |

Most parishes used combined Födelse- och dopböcker; where they were kept separately, use `birth entry` or `baptism entry` to match.

**Swedish parenthetical examples** (order per A7):

- **Disambiguator:** `Per Persson (b. 1773) household` · `(d. 1850) estate inventory` · `(at Ambjörby) household` · `(junior) baptism entry` · `(servant) household examination entry`
- **Source-state:** `Lars Persson Ambjörn (widower) household` · `Larsson-Söderström marriage entry (both in first marriage)` · `Per Persson (retired soldier) household` · `Berthe Poulsdatter (unmarried)`
- **Evidence-quality:** `Marit Jonsdotter (birth year inferred from age)` · `(stated age 23)` · `(named at daughter Cherstin's birth and baptism)` · `Nils Persson (witness at Lars Persson's baptism)`
- **Combined:** `Per Persson (b. 1773, retired soldier, birth year inferred from age)`

### §10 Abbrev

Record-type word lowercased (Scandinavian house variation, see B.1 §10). Parish: `[Parish] [record-type] [vol] ([years])`. Court and other state records: `[Creating body] [record-type] [vol] ([years])`. Land survey: `[Parish] [survey type] [act-no] ([years])`. The SRN is built as in B.1 §10: the Abbrev, then the locators, then the subject.

| Title series | Abbrev word | Example |
| --- | --- | --- |
| Husförhörslängder | husförhörslängd | `Norra Ny husförhörslängd AI:11 (1812–1820)` |
| Lysnings- och Vigselbok | vigselbok | `Norra Ny vigselbok E:5 (1861–1884)` |
| Födelse- och dopböcker | dopbok | `Norra Ny dopbok C:4 (1773–1825)` |
| Dödbok | dödbok | `Norra Ny dödbok [vol] ([years])` |
| Bouppteckningar | bouppteckning | `Älvdals häradsrätt bouppteckning FII:26 (1832–1833)` |
| Folkräkning | folkräkning | `Norra Ny folkräkning 1880` |
| Sockenstämmoprotokoll **Pending review** | sockenstämmoprotokoll |  |
| Land survey **Pending review** | ägodelning / storskifte / laga skifte / enskifte / gränsbestämning / avvittring | `Norra Ny ägodelning 17-NON-51 (1803–1804)` · `Norra Ny ägodelning 17-NON-52 (1810)` · `Norra Ny storskifte R66 (1826)` · `Norra Ny laga skifte 17-NON-148 (1856–1862)` |

### §11 Bibliography

A11 geographic form (EE 2.48) with bracketed English glosses (EE 2.28). Group under `Sweden:`, alphabetize by län then parish or härad. SVAR databases go in a trailing **Online databases** group by title, with no repository (EE 2.34, 11.53).

| Record type | Source List Entry |
| --- | --- |
| Parish | Sweden. Värmland. Norra Ny församling. Husförhörslängder \[household examinations\], AI:11 (1812–1820). Värmlandsarkiv, SE/VA/13398/A I/11. Digital images. Riksarkivet. https://sok.riksarkivet.se : 2026. |
| Court (locality is the härad; years may lead when the volume ID is cryptic) | Sweden. Värmland. Älvdals härad. Älvdals häradsrätt \[Älvdal district court\], Bouppteckningar \[estate inventories\], 1832–1833 (FII:26). Värmlandsarkiv, SE/VA/11047/F II/26. Digital images. ArkivDigital. https://www.arkivdigital.se : 2026. |
| SVAR database | "Sveriges folkräkning 1880" \[Swedish census 1880\]. Database with images. Riksarkivet. https://sok.riksarkivet.se : 2026. |
| Land survey **Pending review** | Sweden. Värmland. Norra Ny socken. Laga skifte \[statutory land enclosure\], act 17-NON-148, 1856–1862. Digital images. Lantmäteriet. https://historiskakartor.lantmateriet.se : 2026. |

Arrangement sample:

```
Sweden:

  Värmland. Älvdals härad. Älvdals häradsrätt [Älvdal district court], Bouppteckningar [estate inventories], 1832–1833 (FII:26). …
  Värmland. Norra Ny församling. Födelse- och dopböcker [birth and baptism books], C:4 (1773–1825). Värmlandsarkiv, SE/VA/13398/C/4. Digital images. ArkivDigital. https://www.arkivdigital.se : 2026.
  Värmland. Norra Ny församling. Husförhörslängder [household examinations], AI:11 (1812–1820). …

Online databases:

  "Sveriges folkräkning 1880" [Swedish census 1880]. Database with images. Riksarkivet. https://sok.riksarkivet.se : 2026.
```

Preferred workflow: a small script walks the Gramps sqlite Source table and emits these entries, keeping Gramps as the source of truth.

### §12 Worked examples

**Glosses** (in the Title and at the series' first mention in the FRN; the Abbrev and SRN drop them): Husförhörslängder \[household examinations\] · Lysnings- och Vigselbok \[banns and marriage book\] · Födelse- och dopböcker \[birth and baptism books\] · Dödbok \[death book\] · Bouppteckningar \[estate inventories\] · Folkräkning \[census\] · laga skifte \[statutory land enclosure\]. These match EE 11.47, 11.50, 11.56.

#### Example 1: Husförhörslängd

| Source field | Value |
| --- | --- |
| Title | `Sweden, Värmland, Norra Ny, Husförhörslängder [household examinations] AI:11, 1812–1820` |
| Abbrev | `Norra Ny husförhörslängd AI:11 (1812–1820)` |
| Author | `Norra Ny församling` |
| Pubinfo | `Digital images, Riksarkivet (https://sok.riksarkivet.se).` |
| Repository | `Värmlandsarkiv` |
| Call number | `SE/VA/13398/A I/11` |
| **Citation** page | `p. 8 (image 19), Per Persson household` |
| Confidence | High |

**FRN:** Norra Ny församling, Husförhörslängder \[household examinations\], vol. AI:11 (1812–1820), p. 8, household of Per Persson, Ambjörby Torpare; digital image, Riksarkivet (https://sok.riksarkivet.se/bildvisning/C0038409\_00019 : accessed 20 April 2026); citing Värmlandsarkiv, SE/VA/13398/A I/11.

**SRN:** Norra Ny husförhörslängd AI:11 (1812–1820), p. 8, Per Persson household.

#### Example 2: Estate inventory (häradsrätt)

| Source field | Value |
| --- | --- |
| Title | `Sweden, Värmland, Älvdals härad, Bouppteckningar [estate inventories] FII:26, 1832–1833` |
| Abbrev | `Älvdals häradsrätt bouppteckning FII:26 (1832–1833)` |
| Author | `Älvdals häradsrätt` |
| Pubinfo | `Digital images, ArkivDigital (https://www.arkivdigital.se).` |
| Repository | `Värmlandsarkiv` |
| Call number | `SE/VA/11047/F II/26` |
| **Citation** page | `pp. 203–205, Per Persson estate inventory` |
| Confidence | High |

**FRN:** Älvdals häradsrätt \[Älvdal district court\], Bouppteckningar \[estate inventories\], vol. FII:26 (1832–1833), pp. 203–205, estate inventory of Per Persson, Ambjörbymon, Norra Ny parish, died 5 May 1832; digital image, ArkivDigital (https://app.arkivdigital.se/volume/v48177?image=104 : accessed 20 April 2026); citing Värmlandsarkiv, SE/VA/11047/F II/26.

**SRN:** Älvdals häradsrätt bouppteckning FII:26 (1832–1833), pp. 203–205, Per Persson estate inventory.

#### Example 3: SVAR folkräkning

| Source field | Value |
| --- | --- |
| Title | `Sweden, Värmland, Norra Ny, Folkräkning [census] 1880` |
| Abbrev | `Norra Ny folkräkning 1880` |
| Author | `Riksarkivet` |
| Pubinfo | `Database with images, Riksarkivet (https://sok.riksarkivet.se).` |
| Repository | Blank for the bibliography (`Riksarkivet` allowed in Gramps, see §3) |
| Call number | `Folk_817085` |
| **Citation** page | `p. 4, row 33, family no. 1, Lars Persson Ambjörn household` |
| Confidence | High |

**FRN:** Sveriges folkräkning 1880 \[Swedish census 1880\], Norra Ny församling, Värmlands län, p. 4, row 33, family no. 1, household of Lars Persson Ambjörn, Ambjörby; digital image, Riksarkivet (https://sok.riksarkivet.se/bildvisning/Folk\_817085-004 : accessed 21 April 2026).

**SRN:** Norra Ny folkräkning 1880, p. 4, row 33, Lars Persson Ambjörn household.

The gloss may be dropped where the surrounding prose has already established the 1880 Swedish census (author's judgement).

#### Example 4: Confirmation **Pending review**

| Field | Value |
| --- | --- |
| Source | Same as Example 1 (the husförhörslängd) |
| **Citation** page | `p. 8 (image 19), Lars Persson confirmation entry` |
| Confidence | High |

**FRN:** Norra Ny församling, Husförhörslängder \[household examinations\], vol. AI:11 (1812–1820), p. 8, confirmation entry of Lars Persson; digital image, Riksarkivet (https://sok.riksarkivet.se/... : accessed 20 April 2026); citing Värmlandsarkiv, SE/VA/13398/A I/11.

**SRN:** Norra Ny husförhörslängd AI:11 (1812–1820), p. 8, Lars Persson confirmation entry.

#### Example 5: Land-survey act **Pending review**

17-NON-148, the Ambjörby laga skifte: Marit Andersdotter's allotment.

| Source field | Value |
| --- | --- |
| Title | `Sweden, Värmland, Norra Ny, laga skifte [statutory land enclosure], act 17-NON-148, 1856–1862` |
| Abbrev | `Norra Ny laga skifte 17-NON-148 (1856–1862)` |
| Author | `Lantmäterimyndigheten i Värmlands län` |
| Pubinfo | `Digital images, Lantmäteriet (https://historiskakartor.lantmateriet.se).` |
| Repository | Blank for the bibliography (`Lantmäteriet` allowed in Gramps) |
| Call number | **Open:** full Lantmäteriet act reference; confirm against the catalogue |
| **Citation** page | `delningsbeskrivning p. 40, Marit Andersdotter land allotment entry (Lott A, 64 öre 6 penningar)` |
| Confidence | High |

**FRN:** Lantmäterimyndigheten i Värmlands län, laga skifte \[statutory land enclosure\], Ambjörby, Norra Ny socken, act 17-NON-148, surveyed 1856–1862 by O. Ignelius, confirmed by Älvdals övre tingslags egodelningsrätt 3 October 1863; delningsbeskrivning p. 40, land allotment (Lott A) of the minor Marit Andersdotter, 64 öre 6 penningar skatt; digital image, Lantmäteriet (https://historiskakartor.lantmateriet.se : accessed 16 June 2026).

**SRN:** Norra Ny laga skifte 17-NON-148 (1856–1862), delningsbeskrivning p. 40, Marit Andersdotter land allotment entry.

## Part B.3: US sources

US federal, state, county, court, cemetery, newspaper, directory, church, and online-platform records.

### §1 Scope

One Source per unit a researcher browses on Ancestry/FamilySearch or pulls from an archive (A1).

| Record type | One Source = |
| --- | --- |
| Federal census | County-state-year (e.g. 1920 St. Louis Co., Minn.) |
| State / territorial census | County-state-year |
| State vital records | State collection (`Minnesota, death certificates, 1908–2002`) |
| County vital records | County collection |
| Naturalization | Court collection |
| Military service files / pensions | Series |
| Cemetery / Find a Grave | One cemetery (house variation, see A1) |
| Newspapers | One title |
| City directories | City-publisher-year (reissued annually) |
| Passenger manifests | Arrival port + year-range series |
| Church (congregational) records **Pending review** | Congregation's record set, or one register volume if catalogued separately |

Rolls, EDs, sheets, and certificate numbers are citation-level (A4). A single congregational register covers several event types; the record-noun distinguishes them, not separate Sources.

### §2 Source author

Bare body name: `Bureau of the Census`, never `U.S. Bureau of the Census`.

| Record type | Author |
| --- | --- |
| Federal census | `Bureau of the Census` |
| State census | `[State] Population Census Office` (or the body that ran it) |
| State vital records | `[State] Department of Health, Vital Records` |
| County vital records | `[County] County Clerk` or `[County] County Recorder` |
| Federal court naturalization | `U.S. District Court, [District]` |
| State/county court naturalization | `[Court name]` (e.g. `St. Louis County District Court`) |
| Headstone applications | `Office of the Quartermaster General` |
| WWII draft cards | `Selective Service System` |
| Civil War pensions | `Bureau of Pensions` |
| Later pensions | `Veterans Administration` (`Department of Veterans Affairs` after 1989) |
| Compiled service records | `War Department, Adjutant General's Office` |
| Newspapers, Find a Grave | Blank |
| Cemetery records (institutional) | `[Cemetery name]` |
| City directories | `[Publisher]` (e.g. `R. L. Polk & Co.`) |
| Manuscripts | Family or individual name if known, else blank |
| Church records **Pending review** | `[Church name], [town]` (e.g. `First Lutheran Church, Warren`); the pastor is named in the FRN |

### §3 Repository

| Repository | Use for |
| --- | --- |
| `National Archives` | Federal records: census, military, federal-court naturalization, manifests, headstone applications, pensions. A specific facility goes in the FRN. |
| `[State] Historical Society` / `[State] State Archives` | State records held there |
| `[County] County Courthouse` | Local court, deed, probate |
| `Family History Library` | FamilySearch microfilm, when a physical film number applies |
| Blank | Publications and online-only platforms (Find a Grave, Ancestry, FamilySearch, Newspapers.com), including a newspaper read on a library's film (A9) |
| `[Custodian], private collection` | Family-held originals (A9) |

**Church records** **Pending review**: often deposited in a denominational archive (e.g. the Swenson Swedish Immigration Research Center, Augustana College) and accessed on Ancestry or FamilySearch. Repository names the archive, Pubinfo names the platform. If the register is still at the church, Repository names the church.

### §4 Source title

| Record type | Title format | Example |
| --- | --- | --- |
| Federal census | `[year] U.S. Federal Census, [county] County, [state]` | `1920 U.S. Federal Census, St. Louis County, Minnesota` |
| State census | `[year] [state] State Census, [county] County` | `1905 Minnesota State Census, St. Louis County` |
| State vital records | `[State], [record series], [years]` | `Minnesota, death certificates, 1908–2002` · `Minnesota, birth records, 1900–1934` · `Minnesota, marriage records, 1849–1950` |
| Naturalization | `[State], [county] County, [court], Naturalization Records, [years]` | `Minnesota, St. Louis County, District Court, Naturalization Records, 1888–1955` |
| Headstone applications | `Applications for Headstones for U.S. Military Veterans, [years]` | `…, 1925–1941` |
| WWII draft cards | `World War II Draft Registration Cards, [state]` | `World War II Draft Registration Cards, Minnesota` |
| Civil War pensions | `Civil War Pension Application Files` | As named in NARA RG 15 |
| City directory | `[Publisher] [city] City Directory, [year]` | `Polk's Duluth City Directory, 1920` |
| Newspaper | `[Title], [city, state]` | `Duluth Herald, Duluth, Minnesota` |
| Find a Grave | `[State], [county], [cemetery], Find a Grave Memorials` | `Minnesota, St. Louis County, Forest Hill Cemetery, Find a Grave Memorials` |
| Passenger manifests | `Passenger Lists of Vessels Arriving at [port], [years]` | `… New York, 1820–1957` |
| Church records **Pending review** | `[State], [county], [town], [Church name] records` | `Minnesota, Marshall County, Warren, First Lutheran Church records` |

Why these leads (all within A8):

- **Federal census** leads year-first, as EE 6.10 permits.
- **State vitals** lead with the state, and the FRN leads with the state too, as EE 11.30 leads with locality. The older body-led form was set aside for consistency (confirmed).
- **Series records** lead with the series, after the locality and court when the series belongs to one (naturalizations, like Norwegian court titles); **periodicals** lead with the publication, year placed for the issue.

### §5 Locator tokens

| Form | Home |
| --- | --- |
| NARA publication (`T625`, `M1916`, `M1378`) | Call number (no "NARA" prefix; Repository already says it) |
| State archives microfilm (Minnesota Historical Society `SAM 227`) | Call number |
| Roll or reel, ED, sheet, dwelling, family, certificate no. | Page string |

State vital collections: Call number is the state's series ID or microfilm number, often blank. Find a Grave and born-digital sources: no Call number; the memorial number goes in the page string. Church records: Call number is the holding archive's reference, if any. A platform's own ID (an Ancestry collection ID such as `61584`, a FamilySearch image group number such as `101714756`) is never a call number: it goes only in the FRN, after the platform's URL.

### §6 Pubinfo

`[medium], [platform] (homepage URL).` per A10. Examples: `Digital images, Ancestry (https://www.ancestry.com).` · `Database with images, FamilySearch (https://www.familysearch.org).` Published directories use the imprint variant (Example 7). Newspapers read on a library's film use `Microfilm, Minnesota Historical Society.`; a title read both there and online is one Source, and A10 picks its Pubinfo (Example 13). For church records, the named digitized collection (e.g. "U.S., Evangelical Lutheran Church in America, Swedish American Church Records, 1800–1952") goes in the FRN, not Pubinfo.

### §7 Page-string templates

| Record type | Page string |
| --- | --- |
| Federal census | `roll [N], ED [N], sheet [N]A/B, dwelling [N], family [N], [Head] household` |
| State census | `[ward or township], p. [N], line [N], [Head] household` |
| Death / birth certificate | `certificate no. [N], [Name] death certificate` / `birth certificate` |
| Marriage license | `license no. [N], [Surname]-[Surname] marriage license` |
| Naturalization petition | `petition no. [N], [Name] naturalization petition` |
| Declaration of intention | `declaration no. [N], [Name] declaration of intention` |
| Final papers volume (before 1906) | `reel [N], final papers vol. [V], p. [P] (image [I]), [Name] naturalization petition` |
| Headstone application | `[Name] (d. [year]) headstone application` |
| WWII draft card | `serial no. [N], [Name] WWII draft card` |
| Civil War pension | `application no. [N], certificate no. [N], [Name] pension file` |
| Compiled service record | `[Unit], [Name] compiled service record` |
| Newspaper wedding / funeral / obituary | `[date], p. [N], col. [N], [Name] obituary` (or `marriage announcement`, `funeral notice`) |
| Newspaper personals | `[date], p. [N], col. [N], [Name] news mention` |
| Mixed-subject column | `[date], p. [N], col. [N], [Column name], [Name] news mention` |
| Find a Grave | `memorial no. [N], [Name]` |
| City directory | `p. [N], [Name] directory entry` |
| Passenger manifest | `list [N], line [N], [Name]` |
| Church record **Pending review** | `[register], p. [P] (image [I]), [Name] [record-noun]` |

Church record-nouns are in §9 (`death and burial entry`, `baptism entry`, …). Examples: `death and burial register, p. 283 (image 496, right), Emma Söderström death and burial entry` · `baptism register, p. 12 (image 30), Anna Larsson baptism entry`.

**Final papers before 1906.** County courts bound each applicant's final papers (the petition and the court's record of admission; the Minnesota Historical Society files them as Final Papers [second papers], and from 1906 as Petition and Record) in lettered volumes, usually without petition numbers. The Source is still the court's whole collection (§1), so the page string names the volume (A4), and the noun is `naturalization petition`. When you know the archive's microfilm, its call number is the Source's Call number and its reel leads the page string (§5), as a census roll does; leave the reel out when you have only the images. With no page number, the image number takes the page's place: `final papers vol. [V], image [I], [Name] naturalization petition`.

**Newspaper reference notes.** An item can report many things, so its FRN names it by the page string's subject and record noun, after the column. The SRN is the newspaper's title and the whole page string, column included: `Duluth Herald, 14 July 1929, p. 7, col. 3, Per Larsson Grund obituary.` What an item is cited for ends both, as for any record (A7, Example 14).

**Newspapers on film.** An item read on a library's microfilm keeps its page string, with no reel, because the issue date finds the reel (the Minnesota Historical Society lists its newspaper film by date range). Only the FRN's ending changes (Example 13).

### §8 Confidence

| Record type | Confidence |
| --- | --- |
| Federal census | High for residence and household; Normal for ages, birthplaces |
| State death certificate (post-1900) | Very High for the death; Normal at most for informant-supplied parents and birth date |
| Naturalization (declaration, petition, final papers) | High for the act recorded (declaring intent, admission to citizenship); Normal for biographical facts the applicant reported |
| Headstone application | Normal for death date; High for military service |
| Find a Grave with marker photo | High for burial and inscribed dates |
| Find a Grave without marker photo | Low: a database entry without images (A6) |
| Wedding announcement | High for the marriage; Normal for detail about spouses and attendants |
| Funeral notice | High for death and funeral; Normal for biography |
| Obituary | Normal at best (family-supplied, unverified); High only when corroborating primary records |
| Personals / community columns | Normal or Low (stringers relying on family and gossip); useful for residence patterns |
| City directory | Normal for residence |
| Compiled trees (Ancestry trees, FamilySearch Tree, WikiTree) | Very Low; starting points, not cited sources |
| Church register **Pending review** | Very High for the recorded event; Normal for secondhand facts (birthplace, parents) |

### §9 Subject vocabulary

**Record nouns** (A7); the first is the default. Passenger manifest and Find a Grave memorial take no noun: the list or memorial number says what it is.

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

| Event | Subject format | Example |
| --- | --- | --- |
| Birth (state) / baptism (church) | `[Name] birth certificate` / `baptism entry` | `Axel Olof Grund birth certificate` |
| Death (state) / (church) | `[Name] death certificate` / `death entry` | `Per Larsson Grund death certificate` |
| Burial | `[Name] burial entry` |  |
| Confirmation, death and burial, membership (church) **Pending review** | `[Name] confirmation entry` / `death and burial entry` / `membership entry` | `Emma Söderström death and burial entry` |
| Marriage license | `[Surname]-[Surname] marriage license` | `Larsson-Söderström marriage license` |
| Census head / non-head | `[Head] household` / `[Subject] in [Head-surname] household` | `Helen Maisuk in Maisuk household` |
| Naturalization / declaration | `[Name] naturalization petition` / `declaration of intention` | `Per Larsson declaration of intention` |
| Headstone application | `[Name] headstone application` | `Axel O. Grund headstone application` |
| WWII draft card | `[Name] WWII draft card` | `Axel O. Grund WWII draft card` |
| Pension / service record | `[Name] pension file` / `compiled service record` | `John Grund pension file` |
| Find a Grave | `[Name]` (the memorial number already says what it is) | `Per Larsson Grund` |
| Wedding announcement | `[Surname]-[Surname] marriage announcement` | `Grund-Hoiberg marriage announcement` |
| Funeral notice / obituary | `[Name] funeral notice` / `obituary` | `Hilda Grund funeral notice` |
| Personals / mixed column | `[Name] news mention` / `[Column], [Name] news mention` | `Alma column, Peter Grund news mention` |
| Manifest / directory | `[Name]` (manifest) / `[Name] directory entry` | `Per Larsson Grund directory entry` |

**Disambiguators (category 1):**

| Situation | Phrasing | Example |
| --- | --- | --- |
| Birth / death year | `(b. YYYY)` / `(d. YYYY)` | `Per Larsson (b. 1848) naturalization petition` |
| Birthplace | `(b. PLACE)` | `John Olson (b. Sweden) household` |
| County | `(of [County])` | `Per Larsson (of Marshall Co.) declaration of intention` |
| Generations | `(senior)` / `(junior)` | `John Grund (junior) WWII draft card` |
| Household role | role in parens | `John Grund (boarder) in Smith household` |
| Enumeration district | `(ED N)` | `Olaf Anderson (ED 22) household` |

**Source-state notes (category 2).** Naturalization is especially rich: between declaration, petition, and final order the person is in a different legal state, and the document records it.

| Situation | Phrasing | Example |
| --- | --- | --- |
| Household role | `(head)`, `(wife of head)`, `(son)`, `(daughter)` (usually omittable for the head) | `John Grund (son) in Grund household` |
| Boarder, lodger, servant | `(boarder)` / `(lodger)` / `(servant)` | `Per Larsson (boarder) in Smith household` |
| Widow / widower | `(widow)` / `(widower)` | `Anna Larsson (widow) household` |
| Declared, not yet petitioned | `(alien)` or `(declared)` | `Per Larsson (declared) household` |
| Naturalized | `(naturalized)` / `(naturalized YYYY)` | `Per Larsson (naturalized 1894) household` |
| First marriage | `(both in first marriage)` |  |
| License vs. banns | `(by license)` / `(by banns)` | `Larsson-Söderström marriage entry (by license)` |
| Delayed birth registration | `(delayed registration)` | `John Grund birth certificate (delayed registration, 1942)` |
| Amended certificate | `(amended)` | `Per Larsson death certificate (amended)` |
| Military status | `(discharged)` / `(deceased in service)` / `(deserted)` | `John Grund pension file (discharged)` |
| Occupation | brief descriptor | `Per Larsson (laborer) household` |

**Evidence-quality flags (category 3):**

| Situation | Phrasing | Example |
| --- | --- | --- |
| Birth year from census age | `(birth year inferred from age)` | `Steve Maisuk (birth year inferred from age in 1920 census)` |
| Several household members | `(birth years inferred from ages)` | `Steve Maisuk household (birth years inferred from ages)` |
| Relative named in another's record | `(named at OTHER-PERSON's EVENT)` | `Anna Larsson (named at son Per's naturalization)` |
| Parents in a child's record | `(parents named at CHILD's EVENT)` | `Per Larsson and Emma Söderström (parents named at son Axel's birth certificate)` |
| Death-certificate informant | `(informant on OTHER-PERSON's death certificate)` | `Marie Edna Siggerud (informant on Per Larsson's death certificate)` |
| Draft-card next of kin | `(next of kin on OTHER-PERSON's draft card)` | `Marie Grund (next of kin on Edmund Grund's WWII draft card)` |
| Pension beneficiary | `(beneficiary on OTHER-PERSON's pension file)` | `Hilda Grund (widow's beneficiary on John Grund's pension file)` |
| Witness | `(witness at OTHER-PERSON's EVENT)` | `Wille Engen (best man at Grund-Hoiberg marriage)` |
| Age only | `(stated age N)` | `John Grund (stated age 38)` |
| Birthplace from naturalization | `(birthplace inferred from naturalization)` | `Per Larsson (birthplace inferred from declaration of intention)` |
| Initials only | `(identified by initials only)` | `J. E. Grund (identified by initials only)` |

### §10 Abbrev

The US Abbrev keeps whole readable words (`St. Louis Co. naturalizations, 1888–1955`); heavier abbreviation belongs in the SRN (`St. Louis Co. natz.`).

| Type | Abbreviations |
| --- | --- |
| Geographic | `Co.` County · `Twp.` Township · `Dist.` District |
| States (traditional, never USPS codes) | `Minn.`, `Wis.`, `Iowa`, `S. Dak.`, `N. Dak.`, `N.Y.`, `Mass.`, `Conn.`, `Cal.` |
| Record types (SRN only) | `natz.` naturalization · `pet. no.` · `decl. no.` · `pop. sched.` · `agri. sched.` · `mort. sched.` · `death cert.` · `birth cert.` · `marr. cert.` · `app.` application · `dir.` directory |
| Collections / archives | `FAG` Find a Grave · `ED` enumeration district · `RG` Record Group · `NAID` National Archives Identifier |

How it compresses: Title `Minnesota, Beltrami County, District Court, Naturalization Records, 1887–1956` → Abbrev `Beltrami Co. naturalizations, 1887–1956` → SRN `Beltrami Co. natz., pet. no. [N] (1920), Louis Grund (witness at Olsson's naturalization).`

Church records **Pending review**: `[Church], [town], [state abbr.], records[, years]`, e.g. `First Lutheran Church, Warren, Minn., records, 1800–1952`.

### §11 Bibliography

A11 geographic form: `[State]. [County]. [Locality/series]. [Series] [volume] ([years]). [Repository], [call number]. [Medium]. [Publisher]. [URL] : [year].` Group under a state header, alphabetize by county. Directories go by publisher (EE 2.46); online-only databases in a trailing group by title.

| Source | Source List Entry |
| --- | --- |
| Find a Grave cemetery | Minnesota. St. Louis County. Forest Hill Cemetery. Find a Grave Memorials. Database with images. https://www.findagrave.com : 2026. |
| State vital | Minnesota. Death certificates, 1908–2002. Minnesota Historical Society. Database with images. FamilySearch. https://www.familysearch.org : 2026. |
| Federal census | Minnesota. St. Louis County. 1920 U.S. Federal Census. National Archives, microfilm publication T625. Digital images. Ancestry. https://www.ancestry.com : 2026. |
| Church **Pending review** | Minnesota. Marshall County. Warren. First Lutheran Church. Death and burial register. Swenson Swedish Immigration Research Center, Augustana College. Digital images. Ancestry. https://www.ancestry.com : 2026. |

### §12 Worked examples

#### Example 1: Federal census (EE 6.10)

Steve Maisuk household, 1920, Duluth. Ancestry image of NARA film.

| Field | Value |
| --- | --- |
| Title | `1920 U.S. Federal Census, St. Louis County, Minnesota` |
| Abbrev | `St. Louis Co., Minn., 1920 census` |
| Author | `Bureau of the Census` |
| Pubinfo | `Digital images, Ancestry (https://www.ancestry.com).` |
| Repository | `National Archives` |
| Call number | `T625` |
| **Citation** page | `roll 859, ED 139, sheet 8A, dwelling [N], family [N], Steve Maisuk household` |
| Confidence | High (residence); Normal (individual facts) |

**FRN:** 1920 U.S. census, St. Louis County, Minnesota, population schedule, Duluth, enumeration district 139, sheet 8A, dwelling \[N\], family \[N\], Steve Maisuk household; digital image, Ancestry (https://www.ancestry.com/... : accessed 6 May 2026); citing National Archives microfilm publication T625, roll 859.

**SRN:** 1920 U.S. census, St. Louis Co., Minn., pop. sched., Duluth, ED 139, sheet 8A, Steve Maisuk household.

#### Example 2: State death certificate (EE 11.30 to 11.31)

Per Larsson Grund, died Williams, Lake of the Woods County, 12 July 1929. FamilySearch.

| Field | Value |
| --- | --- |
| Title | `Minnesota, death certificates, 1908–2002` |
| Abbrev | `Minn. death certificates, 1908–2002` |
| Author | `Minnesota Department of Health, Vital Records` |
| Pubinfo | `Database with images, FamilySearch (https://www.familysearch.org).` |
| Repository | `Minnesota Historical Society` |
| Call number | Blank |
| **Citation** page | `certificate no. 1929-MN-XXXXXX, Per Larsson Grund death certificate` |
| Confidence | Very High (death); Normal (parents' names, separate citation per A3) |

**FRN:** Minnesota, death certificate no. 1929-MN-XXXXXX (1929), Per Larsson Grund; Minnesota Department of Health, Vital Records; digital image, FamilySearch (https://www.familysearch.org/... : accessed 6 May 2026); citing Minnesota Historical Society.

**SRN:** Minn. death cert. 1929-MN-XXXXXX (1929), Per Larsson Grund.

#### Example 3: Naturalization petition (EE 9.32, 12.45)

Per Larsson, St. Louis County District Court, 1894. Ancestry.

| Field | Value |
| --- | --- |
| Title | `Minnesota, St. Louis County, District Court, Naturalization Records, 1888–1955` |
| Abbrev | `St. Louis Co. naturalizations, 1888–1955` |
| Author | `St. Louis County District Court` |
| Pubinfo | `Digital images, Ancestry (https://www.ancestry.com).` |
| Repository | `Minnesota Historical Society` |
| **Citation** page | `petition no. [N], Per Larsson naturalization petition` |
| Confidence | High (citizenship); Normal (biographical facts) |

**FRN:** St. Louis County District Court (Duluth, Minnesota), Naturalization Records, petition no. \[N\] (1894), Per Larsson; digital image, Ancestry (https://www.ancestry.com/... : accessed 6 May 2026); citing Minnesota Historical Society.

**SRN:** St. Louis Co. natz., pet. no. \[N\] (1894), Per Larsson.

#### Example 4: Find a Grave (EE 11.42, per-cemetery scope)

| Field | Value |
| --- | --- |
| Title | `Minnesota, St. Louis County, Forest Hill Cemetery, Find a Grave Memorials` |
| Abbrev | `Forest Hill, Duluth, FAG` |
| Author / Repository / Call number | Blank |
| Pubinfo | `Database with images, Find a Grave (https://www.findagrave.com).` |
| **Citation** page | `memorial no. [N], Per Larsson Grund` |
| Confidence | High with a clear marker photo; Low without |

**FRN:** Find a Grave, memorial no. \[N\], Per Larsson Grund (1848–1929), Forest Hill Cemetery, Duluth, St. Louis County, Minnesota; database with images, Find a Grave (https://www.findagrave.com/memorial/\[N\] : accessed 6 May 2026); marker photograph by \[contributor name\], \[date\].

**SRN:** FAG memorial \[N\], Per Larsson Grund, Forest Hill Cemetery.

#### Example 5: WWII draft card (EE 12.28)

Axel O. Grund, 1942 "Old Man's Draft". FamilySearch.

| Field | Value |
| --- | --- |
| Title | `World War II Draft Registration Cards, Minnesota` |
| Abbrev | `WWII draft cards, Minn.` |
| Author | `Selective Service System` |
| Pubinfo | `Digital images, FamilySearch (https://www.familysearch.org).` |
| Repository | `National Archives` |
| Call number | `RG 147` |
| **Citation** page | `serial no. [N], Axel O. Grund WWII draft card` |
| Confidence | High (self-reported facts); Very High (registration event) |

**FRN:** Selective Service System, World War II Draft Registration Cards, Minnesota, serial no. \[N\], Axel O. Grund (1942); digital image, FamilySearch (https://www.familysearch.org/... : accessed 6 May 2026); citing Record Group 147, National Archives.

**SRN:** WWII draft card, Minn., Axel O. Grund.

Fourth Registration cards (April 1942) were filled out by the registrant, so birth date, residence, employer, and next of kin are primary information.

#### Example 6: Headstone application (EE 12.31 to 12.32)

Axel O. Grund, died 31 October 1948. Ancestry.

| Field | Value |
| --- | --- |
| Title | `Applications for Headstones for U.S. Military Veterans, 1925–1941` |
| Abbrev | `Headstone applications, 1925–1941` |
| Author | `Office of the Quartermaster General` |
| Pubinfo | `Digital images, Ancestry (https://www.ancestry.com).` |
| Repository | `National Archives` |
| Call number | `RG 92` |
| **Citation** page | `Axel O. Grund (d. 1948) headstone application` |
| Confidence | Normal (death date); High (military service) |

**FRN:** Office of the Quartermaster General, "Applications for Headstones for U.S. Military Veterans, 1925–1941," application for Axel O. Grund, died 31 October 1948; digital image, Ancestry (https://www.ancestry.com/search/collections/2375/records/45037 : accessed 6 May 2026); citing NAID 596118, Record Group 92, National Archives at Washington, DC.

**SRN:** Headstone app., Axel O. Grund (d. 1948).

#### Example 7: City directory (EE 13.56 to 13.58)

| Field | Value |
| --- | --- |
| Title | `Polk's Duluth City Directory, 1900` |
| Abbrev | `Polk's Duluth directory, 1900` |
| Author | `R. L. Polk & Co.` |
| Pubinfo | `Duluth: R. L. Polk & Co., 1900. Digital images, Ancestry (https://www.ancestry.com).` |
| Repository | Blank (a publication) |
| **Citation** page | `p. 412, Per Larsson Grund directory entry` |
| Confidence | Normal |

**FRN:** R. L. Polk & Co., Polk's Duluth City Directory, 1900 (Duluth: R. L. Polk & Co., 1900), p. 412, Per Larsson Grund; digital image, Ancestry (https://www.ancestry.com/... : accessed 6 May 2026).

**SRN:** Polk's Duluth dir., 1900, p. 412, Per Larsson Grund.

House variation: EE allows one composite citation for a multi-year run; this guide scopes each annual volume separately.

#### Example 8: Newspaper obituary (EE 14.41)

| Field | Value |
| --- | --- |
| Title | `Duluth Herald, Duluth, Minnesota` |
| Abbrev | `Duluth Herald` |
| Pubinfo | `Digital images, Newspapers.com (https://www.newspapers.com).` |
| Author / Repository / Call number | Blank |
| **Citation** page | `14 July 1929, p. 7, col. 3, Per Larsson Grund obituary` |
| Confidence | Normal (even when it matches the death certificate) |

**FRN:** "Per L. Grund, Duluth Pioneer, Dies at Williams Farm," Duluth Herald (Duluth, Minnesota), 14 July 1929, p. 7, col. 3, Per Larsson Grund obituary; digital image, Newspapers.com (https://www.newspapers.com/... : accessed 6 May 2026).

**SRN:** Duluth Herald, 14 July 1929, p. 7, col. 3, Per Larsson Grund obituary.

#### Example 9: Wedding announcement (EE 14.41)

Louis Grund and Anna Amelia Hoiberg, married at Foldahl by Rev. E. O. Chelzren of Warren.

| Field | Value |
| --- | --- |
| Title | `Warren Sheaf, Warren, Minnesota` |
| Abbrev | `Warren Sheaf` |
| Pubinfo | `Digital images, Newspapers.com (https://www.newspapers.com).` |
| **Citation** page | `3 December 1908, p. 1, Grund-Hoiberg marriage announcement` |
| Confidence | High (marriage); Normal (attendants, family claims) |

**FRN:** "\[Headline if present\]," Warren Sheaf (Warren, Minnesota), 3 December 1908, p. 1, Grund-Hoiberg marriage announcement; digital image, Newspapers.com (https://www.newspapers.com/image/\[N\] : accessed 6 May 2026).

**SRN:** Warren Sheaf, 3 December 1908, p. 1, Grund-Hoiberg marriage announcement.

If the announcement is the only evidence of an attendant's relationship, cite that person separately: `Wille Engen (best man at Grund-Hoiberg marriage)`.

#### Example 10: Mixed-subject column (EE 14.41)

Warren Sheaf "Alma" column, 17 May 1916, p. 7: John Olson visiting John Nilson, and Peter Grund losing a horse. One Source (the Warren Sheaf, as in Example 9), two citations.

| Citation | Page | Confidence |
| --- | --- | --- |
| 1 | `17 May 1916, p. 7, Alma column, Peter Grund news mention` | Normal |
| 2 | `17 May 1916, p. 7, Alma column, John Olson news mention` | Normal |

**FRN 1:** "Alma" \[column\], Warren Sheaf (Warren, Minnesota), 17 May 1916, p. 7, Peter Grund news mention; digital image, Newspapers.com (https://www.newspapers.com/image/64259642 : accessed 6 May 2026).

**SRN 1:** Warren Sheaf, 17 May 1916, p. 7, Alma column, Peter Grund news mention.

**FRN 2:** "Alma" \[column\], Warren Sheaf (Warren, Minnesota), 17 May 1916, p. 7, John Olson news mention; digital image, Newspapers.com (https://www.newspapers.com/image/64259642 : accessed 6 May 2026).

**SRN 2:** Warren Sheaf, 17 May 1916, p. 7, Alma column, John Olson news mention.

#### Example 11: Church record **Pending review**

Emma Söderström, died 7 May 1914, buried 9 May 1914, First Lutheran Church, Warren (S0003 / C0004).

| Field | Value |
| --- | --- |
| Title | `Minnesota, Marshall County, Warren, First Lutheran Church records` |
| Abbrev | `First Lutheran Church, Warren, Minn., records, 1800–1952` |
| Author | `First Lutheran Church, Warren` |
| Pubinfo | `Digital images, Ancestry (https://www.ancestry.com).` |
| Repository | `Swenson Swedish Immigration Research Center` |
| Call number | **Open:** Swenson collection/volume ref if known |
| **Citation** page | `death and burial register, p. 283 (image 496, right), Emma Söderström death and burial entry` |
| Confidence | Very High (one citation for both death and burial) |

**FRN:** First Lutheran Church (Warren, Marshall County, Minnesota), death and burial register, p. 283 (image 496, right), death and burial of Emma Söderström, died 7 May 1914, buried 9 May 1914; digital image, Ancestry (https://www.ancestry.com/search/collections/61584/records/63230716 : accessed 16 June 2026), "U.S., Evangelical Lutheran Church in America, Swedish American Church Records, 1800–1952"; citing Swenson Swedish Immigration Research Center, Augustana College, Rock Island, Illinois.

**SRN:** First Lutheran Church (Warren, Minn.), death and burial entry of Emma Söderström, p. 283.

#### Example 12: Naturalization final papers before 1906 (EE 9.32, 12.45)

Peter L. Grund, admitted to citizenship by the Marshall County District Court; his final papers are signed 12 March 1897. The Minnesota Historical Society's microfilm SAM 227, reel 4, holds Final Papers vol. C (1894–1897) and vol. F (1898–1901); FamilySearch's image group 101714756 is that reel.

| Field | Value |
| --- | --- |
| Title | `Minnesota, Marshall County, District Court, Naturalization Records, 1853–1967` |
| Abbrev | `Marshall Co. naturalizations, 1853–1967` |
| Author | `Marshall County District Court` |
| Pubinfo | `Digital images, FamilySearch (https://www.familysearch.org).` |
| Repository | `Minnesota Historical Society` |
| Call number | `SAM 227` |
| **Citation** page | `reel 4, final papers vol. C, p. 296 (image [I]), Peter L. Grund naturalization petition` |
| Confidence | High (citizenship); Normal (biographical facts) |

**FRN:** Marshall County District Court (Warren, Minnesota), Naturalization Records, final papers vol. C, p. 296 (12 March 1897), Peter L. Grund; digital image, FamilySearch (https://www.familysearch.org/ark:/61903/3:1:... : accessed \[date\]), Image Group Number 101714756, image \[I\]; citing Minnesota Historical Society microfilm SAM 227, reel 4.

**SRN:** Marshall Co. natz., final papers vol. C, p. 296 (1897), Peter L. Grund.

Read on reel 4 itself at the Gale Family Library, the same citation has Pubinfo `Microfilm, Minnesota Historical Society.`, no image number, and an FRN that ends with the film: `…, Peter L. Grund; Minnesota Historical Society microfilm SAM 227, reel 4.` The years and the reel's contents come from MHS's finding aid for SAM 227. MHS finds a record by SAM number, reel, volume, and page, so an index's own codes (the Iron Range Research Center's "Code") stay out of the citation. A birth date, birthplace, or arrival the papers give is the applicant's own report: cite it separately at Normal (A3).

#### Example 13: One newspaper, read online and on film (A10)

The Warren Sheaf is on Newspapers.com and on the Minnesota Historical Society's microfilm. Citation 1 is Example 9's announcement, read on Newspapers.com; citation 2 is an obituary read on the film at the Gale Family Library. The newspaper is one Source (§1). Its Pubinfo names the home most of its citations were read in, here Newspapers.com (A10), and each FRN names the home its own item was read in.

| Field | Value |
| --- | --- |
| Title | `Warren Sheaf, Warren, Minnesota` |
| Abbrev | `Warren Sheaf` |
| Pubinfo | `Digital images, Newspapers.com (https://www.newspapers.com).` |
| Author / Repository / Call number | Blank |

| Citation | Page | Confidence |
| --- | --- | --- |
| 1 | `3 December 1908, p. 1, Grund-Hoiberg marriage announcement` | High |
| 2 | `[date], p. [N], col. [N], [Name] obituary` | Normal |

**FRN 1:** "\[Headline if present\]," Warren Sheaf (Warren, Minnesota), 3 December 1908, p. 1, Grund-Hoiberg marriage announcement; digital image, Newspapers.com (https://www.newspapers.com/image/\[N\] : accessed 6 May 2026).

**SRN 1:** Warren Sheaf, 3 December 1908, p. 1, Grund-Hoiberg marriage announcement.

**FRN 2:** "\[Headline\]," Warren Sheaf (Warren, Minnesota), \[date\], p. \[N\], col. \[N\], \[Name\] obituary; Minnesota Historical Society microfilm.

**SRN 2:** Warren Sheaf, \[date\], p. \[N\], col. \[N\], \[Name\] obituary.

Film has no URL or access date, so FRN 2 ends with the library that made the film, and its page string adds no reel (§7). Repository stays blank, because the film is a copy of a publication (A9). In Paperless, citation 2's scan has a blank Correspondent and Source URL (C6, C8). Had most of the Source's citations been read on the film, its Pubinfo would be `Microfilm, Minnesota Historical Society.`

#### Example 14: Newspaper item cited for part of what it says (A7)

Olaf and Gertrude Nygren's golden wedding, reported in the Warren Sheaf. This citation is for the date and the attendees, which its record noun does not say, so its page string and SRN end with them, and the FRN says `(documenting …)` (A7).

| Field | Value |
| --- | --- |
| Title | `Warren Sheaf, Warren, Minnesota` |
| Abbrev | `Warren Sheaf` |
| Pubinfo | `Digital images, Newspapers.com (https://www.newspapers.com).` |
| Author / Repository / Call number | Blank |
| **Citation** page | `11 July 1917, p. 3, col. 1, Olaf Nygren household news mention (date and attendees)` |
| Confidence | Normal |

**FRN:** "This Honored Couple Celebrate Golden Wedding," Warren Sheaf (Warren, Minnesota), 11 July 1917, p. 3, col. 1, Olaf Nygren household news mention (documenting date and attendees); digital image, Newspapers.com (https://www.newspapers.com/article/warren-sheaf-mr-mrs-olaf-nygren-50th/12517574/ : accessed 4 October 2026).

**SRN:** Warren Sheaf, 11 July 1917, p. 3, col. 1, Olaf Nygren household news mention (date and attendees).

The subject is the household, as C1 names a news item about one household. The URL is a Newspapers.com clipping, which anyone can open without a subscription.

## Part B.4: Published & personal sources

Sources that are neither civil nor church records: books, periodicals, registers, recordings, family artifacts, interviews, and other researchers' work. EE Chapter 4 (Archives & Artifacts) and Chapter 13 (Books, CDs, Maps, Leaflets & Videos) are the anchors, with Templates 1 (Basic Publication), 2 (Book with Parts by Different Authors), 6 (Basic Manuscript), 7 (Private Holdings), 8 (Formal Archives), and 10 (Online Image).

### §1 Scope

Published works scope by bibliographic unit, artifacts by physical thing, interviews by event (A1).

| Category | One Source = |
| --- | --- |
| Books | One book (or a multi-volume set cited as a unit, EE 13.5) |
| Book sections | The book; chapters go in the page string |
| Periodicals | The whole run of one title; issues at citation level |
| E-books, audiobooks | One work regardless of medium; medium in Pubinfo |
| Membership directories, annual publications | One annual issue when the year matters; the run when used as a research tool |
| Yearbooks, enrollment registers | One annual volume |
| City and telephone directories | See B.3 (one per annual volume) |
| Family Bible | One Bible |
| Family records (non-Bible) | One record set |
| Funeral program | One program (per-artifact default, A1) |
| Photograph | One photo when it is the subject of analysis; otherwise attach to the relevant citation |
| Letters | One letter when cited substantively; one collection when the collection is cited |
| Audio interview | One interview (each is a discrete event) |
| Oral-history collection | The collection, when cited as a whole |
| Online video | One video |
| Another genealogist's research | One compilation |
| Correspondence with the researcher | All correspondence with one person (e.g. all of Siw Alfreddson's emails, letters, shared notes) |

### §2 Source author

| Category | Author |
| --- | --- |
| Book, one author | Author's name (`Birger Kirkeby`) |
| Book, several authors | First author; others in Pubinfo or descriptor |
| Edited collection | `[Name], editor` (EE 13.65) |
| Periodical | Blank |
| Membership directory / organizational publication | Issuing body (`Den norske sakførerforening`) |
| Family Bible | Inferred compiler in brackets (`[Per Larsson Grund]`), or blank. The record-collection name goes in the Title. |
| Family record (non-Bible) | Blank, or compiler in brackets |
| Funeral program | Funeral home (`Helgeson Funeral Home`) |
| Photograph | Photographer or studio if known |
| Letter | Writer |
| Audio interview | **The interviewee** (EE 4.31); the interviewer is named in the FRN |
| Oral-history collection | Collection name |
| Online video | Channel or production company |
| Personal research | Researcher (`Siw Alfreddson`) |

Names read `Given Surname` in FRNs and `Surname, Given` in Source List Entries (EE 2.46).

### §3 Repository

| Category | Repository |
| --- | --- |
| Books (incl. library-held) | Blank (EE 2.34) |
| Manuscripts in archives | The archive (`Library of Virginia`, `Minnesota Historical Society`) |
| Family-held artifacts, photos, recordings | `[Custodian], private collection` (EE 4.24 to 4.29) |
| Photo seen only on an online platform | Blank; platform in Pubinfo. If the original is family-held, Repository names the custodian (confirmed dual treatment). |
| Personal research | `[Researcher], personal collection` |

Family-artifact provenance usually needs its own sentence in the FRN (EE 4.24). Custodians' addresses follow A12.

### §4 Source title

Most titles here are author-led or artifact-led, not locality-led, because these sources are arranged by author, collection, or custodian (A11). A place-focused history shelved with locality material may use the A8 form. Foreign titles take a bracketed English gloss in the FRN (EE 2.28).

| Category | Format | Example |
| --- | --- | --- |
| Book | `[Title]` | `Eidsvoll Bygds Historie: Gardene på vestside av Vorma` |
| Edited collection | `[Title]` | `Tennessee Women: Their Lives and Times` |
| Periodical | `[Title], [city, state]` | `American Genealogist, New Haven, Connecticut` |
| Membership directory | `[Title with year]` | `Medlemmer av Den norske sakførerforening 1. juli 1950` |
| School roster | `[Title with years]` | `Elever ved Kristiania katedralskole som begynte på skolen i årene 1891–1901, hefte 8` |
| Family Bible | `[Surname] Family Bible Records, [years]` | `Grund Family Bible Records, 1848–1932` |
| Family record | `[Family/compiler] [record type]` | `Grund Family Record` · `Mollo-Castellano Family History Notes` |
| Funeral program | `Funeral program, [Subject]` | `Funeral program, Thomas Emil Siggerud` |
| Photograph | `[Subject] [photo type], [year or range]` | `Per Larsson Grund cabinet card, ca. 1890s` |
| Letter | `[Sender] to [Recipient], [date], letter` | `Per Larsson Grund to John Edwin Grund, 14 March 1925, letter` |
| Audio interview | `[Interviewee] interview by [Interviewer], [date]` | `Tom Grund interview by Peter Grund, 12 March 2024` |
| Oral-history collection | `[Collection title]` | `Cane River Oral History Collection` |
| Online video | `[Title]` | `Norra Ny parish history walking tour` |
| Personal research | `Personal research of [Researcher], [topic]` | `Personal research of Siw Alfreddson, Ambjörby, Sweden` |

### §5 Locator tokens

| Item | Home |
| --- | --- |
| Edition or format (`2nd ed.`, `Kindle format`, `Audio cassette edition`, `CD-ROM edition`) | Pubinfo |
| Volume of a multi-volume set | Title (`Vol. 2, pt. 2`) when the volume has its own focus; otherwise page string |
| Series identifier (`hefte 8`, `vol. 22`) | Title |
| Pages, chapter or section heading | Page string |
| Interview medium (audio, video, transcript) | Pubinfo or page string (EE 4.31) |

Never drop an e-book's format: e-book and print content often differ (EE 13.60).

### §6 Pubinfo

| Category | Pubinfo |
| --- | --- |
| Print book | `[City]: [Publisher], year.` |
| E-book / audiobook / CD-DVD | `[City]: [Publisher], year. [Format].` |
| Online book via a library platform | `[City]: [Publisher], year. Digital images, [Platform] (URL).` |
| Periodical | `[City], [State if needed], [Publisher].` (publisher often the title; usually omittable) |
| Membership directory | `[City]: [Issuing organization], year.` |
| Family Bible | Blank |
| Funeral program | `[City]: [Funeral home], date.` |
| Photograph from a studio | `[Studio], [city], [year or circa].` if known |
| Letter | Blank |
| Audio interview | `Recorded interview, [city], date.` |
| Online video | `Online video, [Platform] (homepage URL), year.` |
| Personal research | `Unpublished research, [location], [year-range].` |

### §7 Page-string templates

| Category | Page string |
| --- | --- |
| Book | `p. [N]` or `pp. [N]–[N]`, plus subject if relevant |
| Book chapter | `[Chapter title], pp. [N]–[N]` |
| Multi-volume work | `vol. [N], pp. [N]–[N]` |
| Periodical article | `vol. [N], no. [N] ([year]), pp. [N]–[N]` |
| Directory or register | `p. [P] (image [I]), entry no. [N], [Name] directory entry` (or `register entry`) |
| Encyclopedia | `[entry headword]` |
| Family Bible | `[record-type] page, [event]` (`family page, Per Larsson Grund birth entry`) |
| Funeral program | `[subject]` (short enough to need no page) |
| Photograph | `[image element], [subject]`, then `; [second element]` if needed (`cabinet card front, Per Larsson Grund portrait; inscription on mount, "Grandma's Grandpa"`) |
| Audio interview / video | `minute [N]:[NN], [topic]` (or `transcript p. [N], [topic]`) |
| Personal research | `[topic or section], [page if compiled]` |

### §8 Confidence

| Level | Use for |
| --- | --- |
| Very High | Bible entries made at the time by someone with firsthand knowledge (rare; check ink and hand); an eyewitness interview about a recent event |
| High | Bible entries within a few years; funeral-program facts about the funeral; interviews or letters about events the person experienced |
| Normal | Genealogies citing primary records; biographical and membership directories; school records; funeral-program biography; research compilations citing sources |
| Low | Uncited genealogies; encyclopedias; Bibles with later-compiled entries; interviews about events not experienced; uncited research |
| Very Low | Compiled trees; online encyclopedias for genealogy facts; tertiary biographical entries on non-prominent people |

- **Another researcher's work** is Normal if they cite primary sources, Low if not. Their conclusion is not evidence; their sources are.
- **Family Bibles:** check the printing date (an 1850 Bible cannot record pre-1850 births at the time) and hand/ink consistency. Photograph cover, title page, and all family pages first (EE 4.13).
- **Photographs:** High for what they show and their inscriptions; Low to Very Low for identification beyond the inscription.
- **Interviews:** High for the informant's own experience; Normal at best for events before their birth (EE 4.31).
- **Mixed-evidence artifacts** (Bibles, funeral programs) almost always need separate citations (A3).

### §9 Subject vocabulary

**Record nouns** (A7); the first is the default, and `(none)` means the noun may be left off:

| Record type | Record nouns |
| --- | --- |
| Book or bygdebok | entry · (none) |
| Directory or register | directory entry · register entry |
| Family Bible | birth entry · marriage entry · death entry |
| Family record | birth entry · marriage entry · death entry · (none) |
| Funeral program | funeral program · obituary |
| Photograph | portrait · (none) |

| Source | Subject format | Example |
| --- | --- | --- |
| Bible page | `[record-type] page, [Subject] [event]` | `family page, Per Larsson Grund birth entry` |
| Directory or register | `[Name] directory entry` / `register entry` | `Frithjof Siggerud directory entry` |
| Funeral program | `[Subject] [section]` | `Per Larsson Grund obituary` |
| Audio interview | `[topic], [Subject]` | `Grund family migration story, Per Larsson and Emma Söderström` |
| Letter | `[topic], [Subject]` | `report of Marit Jonsdotter's death, Marit Jonsdotter` |
| Photograph | `[image element], [Subject] portrait` | `cabinet card front, Per Larsson Grund portrait` |
| Personal research | `[topic], [Subject]` | `Ambjörby torpare landholdings, Per Persson` |
| Book section | `[topic] entry` | `Vinger gård entry` |

Parentheticals (A7 order):

- **Disambiguator:** `(b. YYYY)`, `(d. YYYY)`, `(at PLACE)`, `(senior)` / `(junior)`; needed less often, since these sources name subjects precisely.
- **Source-state:** `(written contemporaneously)`, `(compiled later)`, `(damaged page)`, `(in unrelated handwriting)`.
- **Evidence-quality:** `(reported by INFORMANT)`, `(handwritten by COMPILER)`, `(uncited claim in published work)`, `(reporting on grandfather's emigration story, second-hand)`.

### §10 Abbrev **Pending review**

Shortest unambiguous work title or artifact identity + year or volume, whole words (heavier abbreviation goes in the SRN):

| Category | Abbrev |
| --- | --- |
| Book | `Eidsvoll bygdebok 2:2` · `Tennessee Women 2009` |
| Periodical | `American Genealogist` |
| Register | `Sakførerforening medlemmer 1950` · `Kristiania katedralskole 1891–1901` |
| Family Bible | `Grund Family Bible` |
| Artifact | `Siggerud funeral program 1953` · `Grund cabinet card 1890s` |
| Interview | `Tom Grund interview 2024-03-12` |
| Personal research | `Alfreddson research` |
| Online video | `Norra Ny walking tour` (the SRN may lead with the channel) |

### §11 Bibliography

Arranged by author (EE 2.46), collection (EE 2.47), or custodian (EE 4.24 to 4.29), not by locality. Authored publications sit alphabetically in the main body; artifacts, interviews, and personal research get trailing headings.

| Type | Source List Entry |
| --- | --- |
| Book | Kirkeby, Birger. Eidsvoll Bygds Historie: Gardene på vestside av Vorma. Vol. 2, pt. 2. Oslo: Eidsvoll Bygdebokkomite, 1959. |
| Edited collection (EE 13.65) | Freeman, Sarah L. Wilkerson, and Beverly Greene Bond, editors. Tennessee Women: Their Lives and Times. Athens: University of Georgia Press, 2009. |
| Periodical run | American Genealogist. New Haven, Connecticut. |
| Periodical article | Mills, Elizabeth Shown. "FAN + GPS + DNA: The Problem-Solver's Great Trifecta." American Genealogist (https://www.americangenealogist.com/fan-gps-dna : 2023). |
| Membership directory | Den norske sakførerforening. Medlemmer av Den norske sakførerforening 1. juli 1950 \[Members of the Norwegian Bar Association as of 1 July 1950\]. Oslo: Den norske sakførerforening, 1951. |
| Family Bible (EE 4.13, 4.24) | \[Per Larsson Grund\], compiler. Grund Family Bible Records, 1848–1932. In The Holy Bible Containing the Old and New Testaments. Stockholm: \[Bible publisher\], \[year\]. Privately held by Peter Grund, Duluth, Minnesota. |
| Funeral program | Helgeson Funeral Home. Funeral program, Thomas Emil Siggerud. Williams, Minnesota, 16 February 1953. Privately held by Peter Grund. |
| Interview, single (EE 4.31) | Grund, Tom (Duluth, Minnesota). Interview by Peter Grund. 12 March 2024. Audio recording. Privately held by Peter Grund, Duluth, Minnesota. |
| Interviews, same informant | Grund, Tom (Duluth, Minnesota). Interviews by Peter Grund. 2024–2025. Audio recordings. Privately held by Peter Grund, Duluth, Minnesota. |
| Personal research | Alfreddson, Siw. Personal research on the Grund family of Ambjörby. Unpublished. Ambjörby, Sweden, 2025–2026. |

```
… (authored works, A to Z by surname) …

Manuscripts and family artifacts:
  [Per Larsson Grund], compiler. Grund Family Bible Records, 1848–1932. …
  Helgeson Funeral Home. Funeral program, Thomas Emil Siggerud. …
  Per Larsson Grund cabinet card, ca. 1890s. Miller Studio, St. Cloud, Minnesota. Privately held by Peter Grund.

Interviews:
  Grund, Tom (Duluth, Minnesota). Interviews by Peter Grund. 2024–2025. …
  Castellano, Mike (Eveleth, Minnesota). Interview by Peter Grund. [date]. Audio recording. …

Personal research:
  Alfreddson, Siw. Personal research on the Grund family of Ambjörby. Unpublished. …
```

### §12 Worked examples

Ordered by EE chapter (4 artifacts, then 13 published works).

#### Family Bible (EE 4.13)

Two layers: the published Bible (Template 1) and the family entries in it (custodian per EE 4.24).

| Field | Value |
| --- | --- |
| Title | `Grund Family Bible Records, 1848–1932` |
| Abbrev | `Grund Family Bible` |
| Author | `[Per Larsson Grund]` |
| Pubinfo | Blank |
| Repository | `Peter Grund, private collection` |
| **Citation** page | `family page 2, Per Larsson Grund birth entry` |
| Confidence | High (entries contemporaneous with later events); Normal (events before purchase) |

**FRN:** \[Per Larsson Grund\], compiler, Grund Family Bible Records, 1848–1932, in The Holy Bible Containing the Old and New Testaments (Stockholm: \[Bible publisher\], \[year\]), family page 2, entry for Per Larsson Grund born 14 January 1848 at Ambjörby, Norra Ny parish; privately held by Peter Grund, Duluth, Minnesota. Entries appear in two distinct hands: an early hand for events 1848–1880, a later hand for events 1881–1932. The earliest entries appear to have been copied into this Bible from an earlier family record after the Bible's purchase.

**SRN:** Grund Family Bible, family page 2, Per Larsson Grund birth entry.

EE 4.13 folds the bracketed name into the title (`[John C.] Phillips Family Bible Records`); this guide splits it into Author + Title and renders `[Author], compiler, Title` in the FRN. The two hands drive the split: 1848 to 1880 is Normal, 1881 to 1932 may be High.

#### Funeral program (EE 4.24, Template 7)

| Field | Value |
| --- | --- |
| Title | `Funeral program, Thomas Emil Siggerud` |
| Abbrev | `Siggerud funeral program 1953` |
| Author | `Helgeson Funeral Home` |
| Pubinfo | `Williams, Minnesota: Helgeson Funeral Home, 16 February 1953.` |
| Repository | `Peter Grund, private collection` |
| **Citation** page | `Thomas Emil Siggerud funeral program` |
| Confidence | High (funeral event); Normal (biography, separate citation) |

**FRN:** Helgeson Funeral Home, "In Memory of Thomas Emil Siggerud," funeral program for services held 16 February 1953 at Lutheran Church, Williams, Minnesota; Rev. Edstrom officiating; burial at Pine Hill Cemetery, Williams, Minnesota; privately held by Peter Grund, Duluth, Minnesota.

**SRN:** Siggerud funeral program 1953.

Family would have corrected funeral details before printing. The birth date (1 September 1869 in Norway) is informant-supplied and appears beside a marriage year that conflicts with parish records.

#### Photograph (EE 4.19, 4.24)

Cabinet card of Per Larsson Grund, Miller studio, St. Cloud; mount inscribed "Grandma's Grandpa"; found as an Ancestry Member-Tree upload, originally family-held.

| Field | Value |
| --- | --- |
| Title | `Per Larsson Grund cabinet card, ca. 1890s` |
| Abbrev | `Grund cabinet card 1890s` |
| Author | Blank |
| Pubinfo | `Miller Studio, St. Cloud, Minnesota, ca. 1890s.` (+ `Digital images, Ancestry (https://www.ancestry.com).` if cited from the Member Tree) |
| Repository | `Peter Grund, private collection` (blank if cited only from Ancestry) |
| **Citation** page | `cabinet card front, Per Larsson Grund portrait; inscription on mount, "Grandma's Grandpa"` |
| Confidence | High (image and inscription); Normal at best (identity) |

**FRN:** Per Larsson Grund cabinet card portrait, ca. 1890s, taken at Miller Studio, St. Cloud, Minnesota; inscription on top of mount in cursive: "Grandma's Grandpa"; printed studio mark on bottom of mount: "Miller" (with M-M monogram), "ST. CLOUD, MINN."; privately held by Peter Grund, Duluth, Minnesota. Subject identification is family attribution by inscription rather than caption with full name.

**SRN:** Per Larsson Grund cabinet card, ca. 1890s.

Tag the scan `attributed` in Paperless and revisit if another image or document confirms the identity.

#### Audio interview (EE 4.31)

EE requires six pieces: informant and interviewer, contact (working files only), date and place, format, whereabouts, relationship.

| Field | Value |
| --- | --- |
| Title | `Tom Grund interview by Peter Grund, 12 March 2024` |
| Abbrev | `Tom Grund interview 2024-03-12` |
| Author | `Tom Grund` |
| Pubinfo | `Recorded interview, Duluth, Minnesota, 12 March 2024.` |
| Repository | `Peter Grund, private collection` |
| **Citation** page | `minute 23:15, Edmund Gene Grund's military service in WWII` |
| Confidence | Normal (adult experience); Low (childhood or earlier) |

**FRN:** Tom Grund (Duluth, Minnesota), recorded interview by Peter Grund, 12 March 2024; audio recording and transcript privately held by Peter Grund, \[ADDRESS FOR PRIVATE USE,\] Duluth, Minnesota; minute 23:15, on Edmund Gene Grund's WWII service. Tom is a son of Edmund Gene Grund and reports here on events he learned of from his parents (he was born after the war).

**SRN:** Tom Grund interview, 12 March 2024, minute 23:15.

Tom (born 1955) did not witness the war, so this is secondhand. Cite Edmund's service itself to a primary record (A3).

#### Personal research (EE 4.29, Template 7)

| Field | Value |
| --- | --- |
| Title | `Personal research of Siw Alfreddson, Ambjörby, Sweden` |
| Abbrev | `Alfreddson research` |
| Author | `Siw Alfreddson` |
| Pubinfo | `Unpublished research, Ambjörby, Sweden, 2024–2026.` |
| Repository | `Siw Alfreddson, personal collection` |
| **Citation** page | `Ambmyra typed page, received 30 April 2026` |
| Confidence | Normal (cited facts); Low (uncited claims) |

**FRN:** Siw Alfreddson, personal research on the Grund family of Ambjörby, Sweden, accumulated 2024–2026, typed page on Ambmyra torpare holdings, received by Peter Grund via email 30 April 2026; privately held by Siw Alfreddson, Ambjörby, Sweden, with copies privately held by Peter Grund, Duluth, Minnesota. Siw's notes cite Norra Ny kyrkoarkiv volumes for each fact she records; for facts she draws from those primary records, the underlying primary record should also be cited directly when used in narrative.

**SRN:** Alfreddson research, Ambmyra typed page, received 30 April 2026.

Prefer the primary record when one exists. Cite Siw directly for (a) things she observed that no record holds, (b) her analysis, or (c) records readers cannot access.

#### Published book (Template 1, EE 13.5)

| Field | Value |
| --- | --- |
| Title | `Eidsvoll Bygds Historie: Gardene på vestside av Vorma` |
| Abbrev | `Eidsvoll bygdebok 2:2` |
| Author | `Birger Kirkeby` |
| Pubinfo | `Vol. 2, pt. 2. Oslo: Eidsvoll Bygdebokkomite, 1959.` |
| Repository | Blank |
| **Citation** page | `pp. 432–440, Vinger gård entry` |
| Confidence | Normal (cites primary records); Low (uncited claims) |

**FRN:** Birger Kirkeby, Eidsvoll Bygds Historie: Gardene på vestside av Vorma \[Eidsvoll Parish History: The Farms on the West Side of the Vorma River\], vol. 2, pt. 2 (Oslo: Eidsvoll Bygdebokkomite, 1959), pp. 432–440, "Vinger gård."

**SRN:** Kirkeby, Eidsvoll bygdebok 2:2, pp. 432–440.

When a fact is also in a primary record, cite that instead.

#### Membership directory (Template 1, EE 13.6)

| Field | Value |
| --- | --- |
| Title | `Medlemmer av Den norske sakførerforening 1. juli 1950` |
| Abbrev | `Sakførerforening medlemmer 1950` |
| Author | `Den norske sakførerforening` |
| Pubinfo | `Oslo: Den norske sakførerforening, 1951. Digital images, Nasjonalbiblioteket (https://www.nb.no).` |
| **Citation** page | `p. 440 (image 443), Frithjof Siggerud directory entry` |
| Confidence | Normal |

**FRN:** Den norske sakførerforening, Medlemmer av Den norske sakførerforening 1. juli 1950 \[Members of the Norwegian Bar Association as of 1 July 1950\] (Oslo: Den norske sakførerforening, 1951), p. 440, entry for Frithjof Siggerud; digital image, Nasjonalbiblioteket (https://www.nb.no/items/b3f9413b2125c7f26063abb8896d95bf?page=443 : accessed 26 April 2026).

**SRN:** Sakførerforening medlemmer 1950, p. 440, Frithjof Siggerud.

Inclusion is direct evidence of membership; printed biographical detail is member-supplied.

#### School enrollment register (Template 1, EE 13.6)

| Field | Value |
| --- | --- |
| Title | `Elever ved Kristiania katedralskole som begynte på skolen i årene 1891–1901, hefte 8` |
| Abbrev | `Kristiania katedralskole 1891–1901` |
| Author | `Anders Langangen` |
| Pubinfo | `[Place]: [Publisher], [year]. Digital images, Nasjonalbiblioteket (https://www.nb.no).` |
| **Citation** page | `p. 112 (image 111), entry no. 498, Erling Frithjof Siggerud register entry` |
| Confidence | Normal (enrollment); Low (detail Langangen adds) |

**FRN:** Anders Langangen, Elever ved Kristiania katedralskole som begynte på skolen i årene 1891–1901, hefte 8 \[Pupils at Kristiania Cathedral School Who Began in the Years 1891–1901, Booklet 8\] (\[Place\]: \[Publisher\], \[year\]), p. 112, entry no. 498, Erling Frithjof Siggerud; digital image, Nasjonalbiblioteket (https://www.nb.no : accessed 26 April 2026).

**SRN:** Langangen, Kristiania katedralskole 1891–1901, p. 112, no. 498, Erling Frithjof Siggerud.

#### Online video (EE Ch. 13, Template 1)

Hypothetical YouTube walking tour of Norra Ny, used to corroborate the geography of Per Persson's Ambjörby torp.

| Field | Value |
| --- | --- |
| Title | `Norra Ny parish history walking tour` |
| Abbrev | `Norra Ny walking tour` |
| Author | `Värmland Local History Channel` |
| Pubinfo | `Online video, YouTube (https://www.youtube.com), 2025.` |
| **Citation** page | `minute 12:30–14:15, Ambjörby torpare landscape` |
| Confidence | Low (footage); Very Low (uncaptioned identifications) |

**FRN:** Värmland Local History Channel, "Norra Ny parish history walking tour," YouTube video (https://www.youtube.com/watch?v=\[ID\] : accessed 9 May 2026), minute 12:30–14:15, on the Ambjörby torpare landscape.

**SRN:** Värmland History YouTube, "Norra Ny walking tour," minute 12:30–14:15.

Use video only as context (geography, visual triangulation), never as the source for a date, name, or relationship.

## Part C: Paperless scan metadata

Paperless metadata makes a scan easy to find and browse; the EE citation itself lives in Gramps. Paperless borrows the A7 subject rules so a scan's title lines up with its Gramps citation. The citation rule for any scan is in the Part B chapter for its content (see the Cross-walk).

### Fields at a glance

| # | Field | Holds | Status |
| --- | --- | --- | --- |
| C1 | Title | `[Subject] [record-noun] [year]` | Settled |
| C2 | Document type | One of the doctype categories | Settled |
| C3 | Date | Event date, else creation/issue date | Settled |
| C4 | Date meaning | event / creation / issuance / publication / scan | Settled |
| C5 | Date qualifier | exact / circa / before / after / year only / decade only | Settled |
| C6 | Correspondent | The digital provider hosting the image | Settled |
| C7 | Tags |  | **Open** (TBD) |
| C8 | Source URL | Link back to the image or indexed record | Settled |
| C9 | Source URL access | Free / Paywall / Geolocked / Unavailable | Settled |
| C10 | Permalink | Advertised persistent identifier | Settled |
| C11 | Family group | e.g. `Grund` | **Open** (TBD) |
| C12 | Provenance | Holder of a physical original, if someone other than you | Settled |
| C13 | Physical location | Where a physical original sits in your library | Settled |

### C1 · Title

**Format:** `[Subject] [record-noun] [year]`

The record noun is the page string's (A7), including its copy form (`Kjerstin Mattsdotter birth and baptism index entry 1820`). Record types with a format of their own are under *Variant forms* below.

| Event | Subject | Example |
| --- | --- | --- |
| Birth, baptism, death, burial | `Given Surname` | `Kjerstin Mattsdotter` |
| Marriage | `[Surname]-[Surname]` | `Larsson-Söderström` |
| Census, residence, husförhörslängd | `[Head's recorded name]` | `Lars Persson Ambjörn` |
| Estate inventory | `[Deceased]` | `Per Persson` |
| Naturalization, military, immigration | `Given Surname` | `Per Larsson` |

**Year:** a 4-digit suffix, no comma, the event year when known. Use a range (`1876–1880`) for documents covering a span. Omit only when no year can be assigned. Examples:

- `Kjerstin Mattsdotter birth and baptism entry 1820`
- `Larsson-Söderström marriage entry 1877`
- `Per Persson estate inventory 1832`
- `Lars Persson Ambjörn household 1880` (folkräkning) · `Lars Persson Ambjörn household 1876–1880` (husförhörslängd)
- `Per Larsson naturalization petition 1894`
- `Thomas Emil Siggerud funeral program 1953`

Same name twice on a page: `Per Persson (b. 1773) household 1812–1820`.

**Variant forms:**

| Situation | Format | Example |
| --- | --- | --- |
| Published work (book, periodical) | `[Topic] [book identifier] [vol] pp. [range] ([pub. year])` | `Vinger gård Eidsvoll bygdebok 2:2 pp. 432–440 (1959)` · `Berge family Slekt Berge familiehistorie pp. 14–22 (1987)` |
| Published work, pages span unrelated topics | Lead with the book | `Kirkeby Eidsvoll bygdebok 2:2 pp. 432–440 (1959)` |
| Non-head household member | `[Subject] in [Head's surname] household [year]` | `Karen Indiana Evensdatter in Hansen household 1875` |
| Non-head, head shares the surname | Use the head's full name | `Berthe Poulsdatter in Poul Jensen household 1801` |
| Newspaper item naming several members of one household | `[Head] household news mention [year]` | `P. L. Grund household news mention 1905` · `Grund household news mention 1884` |
| Passenger manifest | `[Name] passenger manifest entry [year]` |  |
| Find a Grave | `[Name] Find a Grave memorial [year]` | `Per Larsson Grund Find a Grave memorial 1929` |
| Funeral program | `[Deceased] funeral program [year]` | `Thomas Emil Siggerud funeral program 1953` |
| Photograph | `[Subject] photograph [decade or year]` | `Per Larsson Grund photograph 1890s` |
| Audio interview | `[Interviewee] interview [YYYY-MM-DD]` | `Tom Grund interview 2024-03-12` |
| Family letter | `[Sender] to [Recipient] letter [YYYY-MM-DD]` | `Per Larsson Grund to John Edwin Grund letter 1925-03-14` · `Hilda Grund to Anna Larsson letter 1929-08-22` |
| Personal research | `[Researcher surname] [topic] research [YYYY-MM-DD, YYYY, or range]` | `Alfreddson Ambjörby research 2026-04-30` · `Grund Castellano research 2024–2025` · `Volpe Castellano-Vistrorio research 2023` |
| Online video | `[Short title] video clip [year]` | `Norra Ny walking tour video clip 2025` |
| Same-surname divorce index **Pending review** | Shared surname + `divorce index entry` | `Lang divorce index entry 1992` |
| Land survey **Pending review** | Farm-led: `[Farm] [survey type] [completion year]` | `Ambjörby laga skifte 1862` |

Notes on the variants:

- **Published works:** `p.` for one page or article, `pp.` for a range (A13). The year in parentheses signals a publication year. Newspaper items take the standard format (`Per Larsson Grund obituary 1929`).
- **Household news items:** add an initial only to separate plausible same-surname households. Gramps citations still split per person (A3). For a column naming unrelated households, see B.3 Example 10.
- **Research:** the date is when the batch was compiled or received (its full date when it has one), not when events happened.
- **Divorce:** disambiguate by year, then by an inline `(given name)`.

### C2 · Document type

Classified by genealogical content, not by issuer.

| Doctype | Use for |
| --- | --- |
| vital record | Births, deaths, marriages, baptisms, burials (parish or government) |
| enumeration | Folkräkning, husförhörslängd, mantalslängd; US federal and state censuses; tax lists; city directories |
| legal | Court records, estate inventories, probate, deeds, wills, divorce files, civil suits, land records |
| immigration | Naturalization, declarations of intent, passenger lists, ship manifests, alien registration |
| military | Draft cards, service records, pensions, VA BIRLS, military headstones, unit rosters |
| religious | Non-vital church records: confirmation, communion, meeting minutes, religious correspondence |
| correspondence | Letters, emails, telegrams with genealogical content |
| ephemera | Funeral programs, prayer cards, mementos, family-made memorabilia |
| publication | Newspapers, obituaries, books, periodicals, published genealogies, directories, yearbooks, rosters |
| artifact | Images, objects |
| research | Another genealogist's compiled research |
| interview | Audio interviews, oral histories, and their transcripts |

Edge cases:

- **Church and state as one body** (Scandinavian parishes): parish baptisms, marriages, burials are `vital record`. **Separate bodies** (Minnesota Department of Health vs. the ELCA): state records are `vital record`; ELCA records are `religious`.
- **Husförhörslängd** is `enumeration`: parish-made, but it functions as a population register.
- **Genuinely cross-category** (a naturalization court order): pick the genealogical purpose, here `immigration`.

### C3 · Date

The underlying event's date when there is one; otherwise when the document was created or issued (C4 says which). Year only: use 1 January + qualifier `year only` (1 January is then a placeholder, never a real date). A range: use the start year; the range can go in the Title. This is separate from the Gramps Citation date, which stays blank (A2).

### C4 · Date meaning

| Value | Use for |
| --- | --- |
| event | When the underlying event happened. Also parish records (even if written days later) and censuses (being enumerated is the event). |
| creation | The document itself is the thing of interest: letters, emails, family histories, photographs |
| issuance | Document generated some time after the event |
| publication | Newspapers, obituaries, books, magazines, directories, yearbooks, bygdebøker |
| scan | Rare: the only meaningful date is digitization |

### C5 · Date qualifier

| Value | Use for |
| --- | --- |
| exact | Day, month, and year on the record |
| circa | Inferred, give or take a few years |
| before / after | Bounded above / below |
| year only | Only the year; pair with 1 January |
| decade only | Only the decade; pair with 1 January of its first year |

### C6 · Correspondent

The digital provider hosting the image: a small, stable list matching the A10 platforms (FamilySearch, Ancestry, Digitalarkivet, Riksarkivet, ArkivDigital, Newspapers.com, Nasjonalbiblioteket, Lantmäteriet). A platform, never a physical archive or a person. Blank when the document did not come from a digital provider: microfilm read at a library, interviews, personal research, letters, and family-held artifacts.

### C7 · Tags

**Open** (TBD). The worked examples use person, place, date, format, and status tags such as `attributed`.

### C8 · Source URL

The canonical link that takes you back to the image or its indexed record. This deep link differs from Gramps Pubinfo, which holds only the homepage. Film read at a library has no link, so its Source URL is blank.

| Provider | URL form |
| --- | --- |
| ArkivDigital | `https://www.arkivdigital.se/aid/show/v[volume].b[image].s[page]` or `https://app.arkivdigital.se/volume/v[volume]?image=[image]&page=[page]` |
| Riksarkivet | `https://sok.riksarkivet.se/bildvisning/[image_id]` |
| FamilySearch | `https://www.familysearch.org/ark:/...` |
| Ancestry | `https://www.ancestry.com/search/collections/[id]/records/[id]` |
| Find a Grave | `https://www.findagrave.com/memorial/[id]` |
| Newspapers.com | `https://www.newspapers.com/image/[id]`, or a clipping: `https://www.newspapers.com/article/[title]/[id]/` |
| Lantmäteriet **Open** | Historiska kartor deep link per act; reliable share-URL form not yet confirmed |

### C9 · Source URL access

| Value | Meaning |
| --- | --- |
| Free | Freely accessible (may need a login) |
| Paywall | Needs an active subscription |
| Geolocked | Needs a certain country or locality |
| Unavailable | Dead link |

### C10 · Permalink

An alternative URL with a persistent identifier, only when the site advertises it as one: `https://urn.digitalarkivet.no/URN:NBN:no-a1450-ft20101203340184.jpg` · `https://goto.digitalarkivet.no/kb20060926010303`.

### C11 to C13 · Family group, Provenance, Physical location

- **Family group:** **Open** (TBD); examples use `Grund`.
- **Provenance:** only for physical originals held by someone other than you.
- **Physical location:** only for physical originals in your own library.

### Worked examples

In the original examples the URL field is labeled "Original source"; it is shown here as Source URL (C8).

| Scan | Title | Date | Meaning | Qualifier | Correspondent | Doctype | Source URL |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Parish birth, Norra Ny C:4 p. 197 | `Kjerstin Mattsdotter birth and baptism entry 1820` | 1820-06-11 | event | exact | ArkivDigital | vital record | `https://www.arkivdigital.se/aid/show/v5947.b103.s197` (paywall) |
| Estate inventory, Älvdal FII:26 | `Per Persson estate inventory 1832` | 1832-07-17 | event | exact | ArkivDigital | legal | `https://www.arkivdigital.se/aid/show/v48177.b104.s203` |
| Folkräkning 1880 | `Lars Persson Ambjörn household 1880` | 1880-01-01 | event | year only | Riksarkivet | enumeration | `https://sok.riksarkivet.se/bildvisning/Folk_817085-004` |
| Husförhörslängd AI:11 | `Per Persson household 1812–1820` | 1812-01-01 | event | year only | Riksarkivet | enumeration | `https://sok.riksarkivet.se/bildvisning/C0038409_00019` |
| Bygdebok excerpt | `Vinger gård Eidsvoll bygdebok 2:2 pp. 432–440 (1959)` | 1959-01-01 | publication | year only | Nasjonalbiblioteket (blank if self-scanned) | publication | `https://www.nb.no/items/[bookid]?page=[page]` or blank |
| Cabinet card | `Per Larsson Grund photograph 1890s` | 1890-01-01 | creation | decade only | Ancestry | artifact | Ancestry image page |
| Audio interview | `Tom Grund interview 2024-03-12` | 2024-03-12 | event | exact | Blank | interview | Blank (private) |
| Personal research | `Alfreddson Ambjörby research 2026-04-30` | 2026-04-30 | creation | exact | Blank | research | Blank (private) |
| Land survey **Pending review** | `Ambjörby laga skifte 1862` | 1862-09-17 | event | exact | Lantmäteriet | legal | Historiska kartor link to act 17-NON-148 |

Why these values:

- **Parish birth:** the title uses the tree's spelling (Kjerstin), not the register's (Cherstin). Family group `Grund`.
- **Estate inventory:** the date is the inventory (17 July), not the death (5 May 1832); meaning is `event` because the death is the underlying fact. Record the other date in a Paperless note or the Gramps page string.
- **Folkräkning:** records a household as of a year, so 1 January + `year only`. The title uses the head's full recorded name (**Open:** confirm `Ambjörn` is the 1880 recorded form; the original example said `Lars Amb`).
- **Husförhörslängd:** title range matches the volume; date is the start year, the cleanest default.
- **Bygdebok:** leads with the farm so it clusters with other Vinger gård scans. Bygdebøker are derivative: confidence Normal at most (B.4 §8).
- **Cabinet card:** meaning is `creation` because a photo documents its own moment, not a birth or census. Tags `Per Larsson Grund`, `1890s`, `cabinet card`, `Miller studio`, `St. Cloud Minnesota`, `attributed`. Notes transcribe the mount: `Top of mount, cursive: "Grandma's Grandpa" (faded; reading is likely but not certain)` and `Bottom of mount, printed: "Miller" (with M-M monogram), "ST. CLOUD, MINN."` Researching Miller studio's operating years (directories, Stearns History Museum) could upgrade the qualifier to `circa`.
- **Audio interview:** tags cover subjects, interviewer, format, transcript, relationship, and firsthand scope. Notes record place and time (Tom's residence, Duluth, 14:30 to 16:15), that Tom (born 1955) reports pre-1955 events secondhand, storage, the privacy placeholder for his address (A12), and timestamped topics (migration 00:00 to 12:30; WWII 12:30 to 25:00; Eveleth childhood 25:00 to 45:00; Marshall County land 45:00 to 60:00; memorabilia 60:00 to end). The transcript is a separate document, `Tom Grund interview transcript 2024-03-12`, with the same correspondent, doctype, and date.
- **Personal research:** covers Ambmyra, Ambjörbymon, and neighboring torpare holdings 1773 to 1932, with cited volumes and verbatim transcriptions; her landmark photos are direct evidence of current physical features. Each new batch gets its own document (`Alfreddson Ambjörby research 2026-09-15`); a cumulative document can come later.
- **Land survey:** farm-led title; date is the surveyor's final signing (17 September 1862), not the 1856 opening or 1863 confirmation, which go in the Gramps FRN. The act number stays out of the title and travels in the URL.

## Cross-walk: Paperless doctype to citation rule

Every Paperless doctype has a citation rule. Because doctypes group by content and chapters group by country or source type, several doctypes route to more than one chapter; that is expected, not a gap.

| Doctype | Record types | Where the citation rule lives | Status |
| --- | --- | --- | --- |
| vital record | Norwegian kirkebøker BMD; Swedish Födelse- och dopböcker, Vigselbok, Dödbok; US state/county certificates; US church-performed events; Find a Grave death data | B.1 §4, §7, Ex. 1 · B.2 §4, §7, §12 · B.3 §4, §7, Ex. 2, Ex. 11 | Covered (US church **Pending review**) |
| enumeration | Folketelling 1801 and 1865+; husförhörslängd; folkräkning; mantalslängd; US federal and state census; tax lists; city directories | B.1 §4, §7, §8, Ex. 2 · B.2 §4, §7, §8, §12 · B.3 §4, §7, Ex. 1, Ex. 7 | Covered |
| legal | Tingbøker; skifteprotokoller; matrikkel; bouppteckningar; Lantmäteriet survey acts; deeds, wills, suits; divorce files | B.1 Ex. 3, Ex. 4 · B.2 §4, §7, Ex. 2, Ex. 5 · C1 (divorce, survey titles) | Covered (surveys, divorce **Pending review**) |
| immigration | Naturalization; passenger and ship manifests; alien registration | B.3 §4, §7, §9, §10, Ex. 3, Ex. 12 | Covered |
| military | Draft cards; service records; pensions; headstone applications; VA BIRLS; rosters | B.3 §4, §7, §9, Ex. 5, Ex. 6 | Covered |
| religious | Confirmation and communion (within the parent register); meeting minutes (own series); US congregational membership and confirmation; religious correspondence | B.1 §4, §7, §8, §10, §11, Ex. 5 · B.2 §4, §7, §8, §10, Ex. 4 · B.3 church rows | Covered, all **Pending review** |
| correspondence | Family letters; correspondence with the researcher | B.4 §2, §4, §7, §11 | Covered |
| ephemera | Funeral programs, prayer cards, mementos | B.4 §4, §7, §12 funeral program | Covered |
| publication | Books incl. bygdebøker; edited collections; periodicals; directories and registers; e-books, audiobooks; online video; newspapers | B.4 §4, §6, §7, §10, §11, §12 · B.3 Ex. 7 to 10 | Covered |
| artifact | Photographs; family Bibles; family records; headstones; inscribed objects | B.4 §2 to §4, §7, §10, §11, §12 Bible and photo | Covered |
| interview | Audio interviews, oral histories, transcripts | B.4 §2, §4, §7, §11, §12 interview | Covered |
| research | Other genealogists' compilations and notes | B.4 §2, §3, §4, §7, §10, §11, §12 | Covered |

Paperless fields are filing identifiers, not EE citations. Each scanned item is cited under the Part B chapter for its content; for example, a newspaper household-mention item cites under B.3, and a bygdebok excerpt under B.4.

## Review queue

22 of 34 items need a decision: 13 drafted rules awaiting approval, 7 open values, and 2 of the 14 inconsistencies found while reorganizing (12 resolved). Set the status as you work through them, and record the decision in the last column and in the Change log.

### Drafted rules awaiting approval

| ID | Item | Where | Status | Decision |
| --- | --- | --- | --- | --- |
| R1 | Norwegian religious records: confirmation/communion within the kirkebok, minutes as their own series. Verify the minutes volume pattern and English glosses against Digitalarkivet. | B.1 | Needs decision |  |
| R2 | Swedish religious records: same model within the husförhörslängd. Verify the minutes locator (meeting date or item no.), NAD series letter, and gloss. | B.2 | Needs decision |  |
| R3 | Published & personal Abbrev rule (newly written; the original had none). | B.4 §10 | Needs decision |  |
| R4 | Same-surname divorce title (`Lang divorce index entry 1992`), reconstructed from a truncated bullet. | C1 | Needs decision |  |
| R5 | Land surveys overall: title, date, and author conventions. | B.2, C1 | Needs decision |  |
| R6 | Land surveys: expansion of the `NON` district code for Norra Ny (drives Author, call number, disambiguator). | B.2 §2 | Needs decision |  |
| R7 | Land surveys: exact call-number string (`R` series and `NN-XXX-NNN` series may differ). | B.2 Ex. 5 | Needs decision |  |
| R8 | Land surveys: spell out `Lantmäterimyndigheten i Värmlands län` or adopt a shorter house form? | B.2 §2 | Needs decision |  |
| R9 | Land surveys: the 1826 R66 act's confirmation date, if a citation anchors to it. | B.2 | Needs decision |  |
| R10 | Land surveys: a reliable Historiska kartor share-URL pattern per act. | C8 | Needs decision |  |
| R11 | US church records overall: author, title, repository conventions. | B.3 | Needs decision |  |
| R12 | US church records: one Source per congregation or per register volume? And the holding archive's call-number form. | B.3 §1, §5 | Needs decision |  |
| R13 | US church records: include membership/communicant records, or only baptism, confirmation, marriage, death-burial? | B.3 §7 | Needs decision |  |

### Open values

| ID | Item | Where | Status | Decision |
| --- | --- | --- | --- | --- |
| O1 | US bibliography shape was derived by analogy (original sections 12 and 13 were repealed). Confirm the state-vital and census lines. | B.3 §11 | Needs decision |  |
| O2 | Real headline for the Warren Sheaf wedding announcement. | B.3 Ex. 9 | Needs decision |  |
| O3 | Real volume and years for a Dödbok Source. | B.2 §4 | Needs decision |  |
| O4 | Matrikkel 1838 call number (NAD path). | B.1 Ex. 4 | Needs decision |  |
| O5 | Placeholders: Bible publisher and year; Kristiania register imprint; YouTube video ID; Mike Castellano interview date. | B.4 | Needs decision |  |
| O6 | EE template number for books: the original said "Template 7 (Books)", but Template 7 is Private Holdings and books use Template 1. | B.4 | Needs decision |  |
| O7 | Is `Ambjörn` the surname actually recorded in the 1880 folkräkning? | C worked examples | Needs decision |  |

### Found while reorganizing

These are inconsistencies in the original text. The guide keeps the original rule and flags the conflict; none were silently changed except C6.

| ID | Item | Where | Status | Decision |
| --- | --- | --- | --- | --- |
| C1 | Part C said it has eight fields but defines 13, and its intro names a "Related" field that is never defined. | C | Resolved | The reorganized Part C defines 13 fields and no Related field (2026-09-29) |
| C2 | C2 said "twelve categories" but listed 11; `interview` is used by examples and the Cross-walk but missing from the list. A naturalization example also says `immigration/naturalization`. | C2 | Resolved | `interview` is in the C2 list; the count and the `immigration/naturalization` example are gone (2026-09-29) |
| C3 | Correspondent is defined as the digital provider, but the interview and research examples set it to a person, and the research title rule says leave it blank. | C6 | Resolved | Platform only; private items leave Correspondent blank, and the two examples now do (2026-09-29) |
| C4 | Photograph and interview Paperless titles are TBD, though worked examples already use forms for both. | C1 | Resolved | The worked-example forms are the rule: `[Subject] photograph [decade or year]`, `[Interviewee] interview [YYYY-MM-DD]` (2026-09-29) |
| C5 | Survey record-noun `cadastral act` vs. example title `Ambjörby laga skifte 1862`. The change log also mentions a land-survey title subsection and completion-date rule that were never written into Part C. (C1's record-noun table, which held `cadastral act`, was removed on 2026-09-29; the survey title is the farm-led variant.) | C1 | Needs decision |  |
| C6 | The folkräkning Paperless example still read `Lars Amb household 1880`, though the change log says it was fixed. Shown fixed here. | C worked examples | Resolved | Applied the fix the change log describes |
| C7 | Swedish estate example: Call number `SE/VA/11047/F II/26`, but FRN and bibliography cite `SE/VA/11047`. | B.2 Ex. 2 | Resolved | FRN and bibliography cite the full volume path SE/VA/11047/F II/26 (2026-09-24) |
| C8 | Find a Grave without a photo: the rules said both Normal (typed entry) and Low. | B.3 §8 | Resolved | Low: a database entry without images (A6) (2026-09-29) |
| C9 | A8 shows US vitals as `Minnesota, [county], death certificates…`, but B.3 titles omit the county. | A8, B.3 §4 | Resolved | A8's example drops the county, matching B.3's state-collection scope (2026-09-29) |
| C10 | B.1 contrasted its unparenthesized title years with a "Swedish parenthetical-year style", but Swedish titles now also use unparenthesized years (only Abbrevs use parentheses). The line was dropped. | B.1 §4 | Resolved | Nothing left to decide once the line was dropped (2026-09-29) |
| C11 | Funeral-program Pubinfo in the example omits the funeral home that the A10 imprint (`[City]: [Funeral home], date.`) requires. | B.4 Ex. | Resolved | Pubinfo follows the A10 imprint: Williams, Minnesota: Helgeson Funeral Home, 16 February 1953. (2026-09-24) |
| C12 | Personal-research title format says `YYYY or year-range`, but the example uses a full date (`2026-04-30`). | C1 | Resolved | A dated batch takes its full date: `[YYYY-MM-DD, YYYY, or range]` (2026-09-29) |
| C13 | Folkräkning Call number `Folk_817085` looks like the image-ID family A4 keeps out of fields. Confirm it is the volume reference. | B.2 Ex. 3 | Needs decision |  |
| C14 | Naturalization Titles are court-led (`St. Louis County District Court, Naturalization Records…`) rather than locality-led. Keep as a series-record exception? | B.3 §4 | Resolved | Locality-led, per A8: `Minnesota, St. Louis County, District Court, Naturalization Records, 1888–1955` (2026-09-29) |

Also dropped: Part 0 pointed to a "Note on EE coverage of foreign records" that did not exist; each chapter's intro now states the EE coverage directly.

## Change log

Newest first. Add a row for every rule change: date, rule ID or section, what changed, and why.

| Date | Rule / section | Change | Why |
| --- | --- | --- | --- |
| 2026-10-06 | A5; A7; B.3 §7, Ex. 14 | What a citation is cited for now reaches every record type: it ends the page string and the SRN in parentheses, and the FRN gives it as `(documenting …)` at the end of the item, before the image, film, or holding clause. `Citing` is reserved for the source behind an image or film. | User decision: one verb for what a citation documents, so it cannot be read as the source behind the image |
| 2026-10-06 | Start here; Gramps field map; A5; A7; B.3 §7, Ex. 9, 13, 14; C8 | Cited for is no longer a note of its own. When given, it ends the page string in parentheses (no longer only for split citations), and a newspaper item's FRN gives it as `(citing …)` and its SRN as `(…)`. Add it when one item gives several citations or the record noun does not say what it is cited for. Examples 9 and 13 drop it; Example 14 shows it. C8 lists the Newspapers.com clipping URL. | User decision: carry what a citation is cited for in its page string and notes, not in a separate section |
| 2026-10-06 | A3; A5; A7; B.3 §7 | When one item gives several citations (A3) that the page string cannot otherwise tell apart, each page string ends with what it is cited for, in parentheses (`… Per Larsson Grund obituary (death date)`), and a newspaper SRN follows its page string. Cited for keeps the capitals of names. | Telling apart three citations of one Warren Sheaf item in Gramps |
| 2026-10-06 | Start here; Gramps field map; A5; A7; B.3 §7, Ex. 8, 9, 10, 13 | A citation can carry a Cited for note, below the SRN, saying what it is cited for (`marriage date and location`). A newspaper item's FRN names the item by the page string's subject and record noun, with what it is cited for in parentheses, in place of a free description (`marriage announcement of …`); so a couple's full given names no longer go in a newspaper FRN. A newspaper SRN carries the whole page string, column included (`col. 3`, `Alma column`). | User decision: record what each citation is cited for, and name a newspaper item in the FRN as the SRN does |
| 2026-10-06 | Start here; A1; A10; B.2 §6; B.3 §3, §6, §7, Ex. 13; C8 | A record read in more than one home (two platforms, or a platform and a library's film) is one Source. Pubinfo names one home (the system of record now decides only between platforms), and each FRN names the home its own item was read in, replacing "Mention the other platforms in the FRN." A newspaper read on a library's film has Pubinfo `Microfilm, Minnesota Historical Society.`, an FRN that ends `; Minnesota Historical Society microfilm.`, no reel in its page string, a blank Repository, and a blank Paperless Source URL. | Citing one newspaper from both Newspapers.com and Minnesota Historical Society microfilm |
| 2026-10-04 | A5; A10; C6; B.3 Ex. 12 | Microfilm is a Pubinfo medium (`Microfilm, [film's maker].`, no URL). Film read in person takes the digital image's place in the FRN and cites nothing behind it; a copy printed or photographed from the reader is a working copy, not a layer; its Paperless Correspondent is blank. | Citing film read at the Gale Family Library, which the online media did not cover |
| 2026-10-04 | B.3 §5, §7, Ex. 12 | A state archive's microfilm is a layer of its own: its call number (Minnesota Historical Society `SAM 227`) is the Source's Call number, and its reel leads the final-papers page string and ends the FRN's citing clause (`citing Minnesota Historical Society microfilm SAM 227, reel 4`), as a census roll does. Example 12 carries Peter L. Grund's real locators (reel 4, vol. C, p. 296) and the collection's span from MHS's finding aid (1853–1967). | Recording the microfilm behind a FamilySearch image group |
| 2026-10-04 | B.4 §6, Family Bible | The Family Bible Pubinfo is left blank, as a letter's is; the Bible's title and imprint stay in the FRN. | User decision: the field is never used (its row and worked example had also disagreed) |
| 2026-10-04 | B.3 §5, §7, §8, Ex. 12; Cross-walk | Final papers bound in lettered volumes before 1906 (the Minnesota Historical Society's Final Papers, or Petition and Record) are cited by volume and page: `final papers vol. [V], p. [P] (image [I]), [Name] naturalization petition`. Naturalization gets a §8 confidence row; a platform's own ID, such as a FamilySearch image group number, goes only in the FRN; Example 12 cites Peter L. Grund's 1897 final papers. | Citing a Marshall County final-papers volume, which the guide did not cover |
| 2026-09-29 | A7; B.1–B.4 §9; C1 | Record nouns are a controlled list per record type (§9 Record nouns tables) and name their form: entry, record (or the document's own name), household, index entry, transcript, extract, abstract. Renamed: marriage → marriage entry (parish) or marriage license (US vital); estate → estate entry; land dispute, court matter, and the land-survey nouns gain "entry"; parish meeting record → parish meeting entry; one person in a census → census entry (household examination entry in a husförhörslängd). Headstone applications end in their noun (`Axel O. Grund (d. 1948) headstone application`), and directories and registers take `directory entry` or `register entry`. C1 uses the page string's noun and lists the record types with titles of their own; Find a Grave entry → Find a Grave memorial; divorce entry → divorce index entry. An index entry or transcript cites a database in the FRN. | User decision: tell entries, records, indexes, and copies apart |
| 2026-09-29 | A7; B.1 §7, §12; B.3 §7, §12 | Page strings start in lower case, record-number labels included: `certificate no.`, `license no.`, `petition no.`, `declaration no.`, `serial no.`, `application no.`, `memorial no.`, `list`, `district`, `gård`. | User decision: one rule for every page string, following "image" (2026-09-28) |
| 2026-09-29 | A8; B.1 §4, §10 to §12 | Norwegian Titles name the series in Norwegian with a bracketed English gloss, as Swedish Titles do: `Ministerialbok [parish register]`, `Klokkerbok [parish register (copy)]`, `Folketelling [census]`, `Tingbok [court journal]`, `Skifteprotokoll [probate register]`, `Matrikkel [land register]`, `Menighetsmøteprotokoll [parish meeting minutes]`. The FRN and bibliography use the same glosses, retiring `Kirkebøker [parish records]`, "parish registers", and the English "Parish register (copy)" label. Norwegian bibliography entries take the A11 `[volume] ([years])` form, and court glosses read `[Eidsvoll district court]` everywhere. | User decision: one title pattern for all Scandinavian Sources |
| 2026-09-29 | B.1 §10, §12; B.2 §10, §12 | Scandinavian SRNs are the Abbrev, then the locators, then the page string's subject, which keeps only a category-1 disambiguator. Census SRNs now lead with the Abbrev (`Eidsvoll folketelling 1875`, `Norra Ny folkräkning 1880`), court SRNs keep their years, and the matrikkel SRN keeps its record noun. | User decision: write down the pattern most SRNs already followed |
| 2026-09-29 | B.1 §10, §12; B.2 §10, §12 | Court-record Abbrevs are `[court] [record word] [vol] ([years])`: `Eidsvoll sorenskriveri skifteprotokoll II 3 (1815–1825)`, `Älvdals häradsrätt bouppteckning FII:26 (1832–1833)`. | User decision: one pattern for court records |
| 2026-09-29 | B.3 §12 | US Abbrevs spell out their words, as §10 requires: `Minn. death certificates`, `Headstone applications`, `Polk's Duluth directory`. SRNs keep the short forms. | User decision: follow §10 |
| 2026-09-29 | A8; B.3 §4, §10, Ex. 3 | Naturalization Titles are locality-led: `Minnesota, St. Louis County, District Court, Naturalization Records, 1888–1955`. A8 now says a series name leads after the locality and court when the series has them. | User decision (Review queue C14) |
| 2026-09-29 | C6; C worked examples | Correspondent is the platform only. Interviews, personal research, letters, and family-held artifacts leave it blank; the interview and research examples no longer name a person. | User decision (Review queue C3) |
| 2026-09-29 | A7; A8; B.1 §10, §12; B.2 §9, §12; B.3 §8, Ex. 10; B.4 §7, §9, §10, §12 | Consistency fixes: A7 says when parentheticals follow the record noun; A8 states the Scandinavian gloss rule, and its US vital example drops the county (C9); B.1 FRNs write `fol.` per A13, and the minutes Abbrev gains its years; B.2 §12's glosses note matches the Titles; B.2 §9 drops a US naturalization row and writes its couple example per A7; B.3 §8 settles Find a Grave without a photo at Low (C8); B.3 Ex. 10 gains its SRNs, and its FRNs read "news mention of"; B.4 §7 gains a Directory or register row; B.4 photograph, letter, and book-section examples match the worked examples; B.4 Abbrevs drop the comma before the year. | Found in a full read of the guide |
| 2026-09-29 | C1; C2; Cross-walk | C1 settles the photograph and interview titles (C4) and full dates for dated research batches (C12), drops the census "short form" alternative, keeps newspaper items in the standard format, and lists the passenger manifest, Find a Grave, funeral program, and online video titles among its variants. C2 lists `interview` (C2). | Found in a full read of the guide |
| 2026-09-28 | B.1 §7, B.2 §7 | The unpaginated fallback starts with a lowercase "image": `image [I], [entry], [subject]`. | User decision: "image" is not capitalized in a page string |
| 2026-09-28 | B.1 §7 | Added the unpaginated fallback (`Image [I], [entry], [subject]`), matching B.2 §7. Reference notes then say "image [I]" in place of "p. [P]". | Some volumes have image numbers but no page numbers |
| 2026-09-24 | B.1 Ex. 1 | SRN changed to "Thor Emil birth and baptism entry" to match the page string's subject. | Contradiction found by the generator's check; user decision |
| 2026-09-24 | B.1 §7, Ex. 3; B.2 §7 | Page ranges use an en dash everywhere: "folio 145–148" and "pp. 203–205", matching the FRN and SRN. | Contradiction found by the generator's check; user decision |
| 2026-09-24 | B.2 §11, Ex. 2 | FRN and bibliography now cite the full volume path, Värmlandsarkiv, SE/VA/11047/F II/26, matching the call number. | Contradiction found by the generator's check; user decision |
| 2026-09-24 | B.2 Ex. 2 | SRN drops the trailing ", Ambjörbymon"; no other Swedish SRN carries a place. | Contradiction found by the generator's check; user decision |
| 2026-09-24 | B.3 Ex. 8 | SRN changed to "Per Larsson Grund obituary" to match the page string's subject. | Contradiction found by the generator's check; user decision |
| 2026-09-24 | B.3 Ex. 11 | FRN keeps ", right" after the image number; SRN changed to "First Lutheran Church (Warren, Minn.), death and burial entry of Emma Söderström, p. 283." | Contradiction found by the generator's check; user decision |
| 2026-09-24 | B.4 §7, §9, Family Bible | FRN and SRN use the full name "Per Larsson Grund" throughout the Family Bible example. | Contradiction found by the generator's check; user decision |
| 2026-09-24 | B.4 Funeral program | Pubinfo now follows the A10 imprint: "Williams, Minnesota: Helgeson Funeral Home, 16 February 1953." | Contradiction found by the generator's check; user decision |
| 2026-09-24 | B.4 §11, examples | Custodian name standardized to Peter Grund across B.4 examples and bibliography. | Contradiction found by the generator's check; user decision |
| 2026-09-24 | B.4 Personal research | Citation page string shortened to "Ambmyra typed page, received 30 April 2026," matching the SRN. | Contradiction found by the generator's check; user decision |
| 2026-09-24 | B.1 §4 | Meeting-minutes title template leads with the Norwegian name: "menighetsmøteprotokoll [parish meeting minutes]"; also repairs broken backticks in the example cell. | Contradiction found by the generator's check; user decision |
| 2026-09-24 | B.3 §7 | City directory page template changed to "p. [N], [Name] directory entry" to match Ex. 7. | Contradiction found by the generator's check; user decision |
| 2026-09-24 | B.3 §9 | Find a Grave and manifest/directory subject rows drop the record noun after a memorial or list number, matching §7. | Contradiction found by the generator's check; user decision |
| 2026-09-23 | A4; B.1 §7, §12; B.2 §7, §12 | The page string names a volume only when the Source spans more than one (US census rolls, periodicals, multi-volume sets). Norwegian and Swedish page strings drop the volume (Ministerialbok I 5, Parish register (copy) I 2, Vol. AI:11, Vol. II 3) and land-survey page strings drop the act number. Reference notes still name the volume. | The Source is scoped to one volume (A1) and its Title already names it (A4); repeating it invites mismatches |
| 2026-09-23 | A4; B.2 §7 | Image numbers belong in the page string, as (image \[I\]), when they differ from the page number; raw image IDs still go only in the FRN URL. Folkräkning page template now p. \[P\] (image \[I\]), row \[R\], family no. \[F\]. | Folkräkning images can differ from page numbers (p. 4 on image 112); the image number is the fastest way back to the scan |
| 2026-09-23 | B.2 §4, §11, §12; A8 | Swedish Titles now lead with the Swedish series name and put the English gloss in square brackets (Husförhörslängder \[household examinations\] AI:11), replacing the English-first form with the Swedish name in parentheses. Titles use the same glosses as the FRN. Folkräkning is glossed as \[census\] everywhere (was population count). | Follows EE 2.28; matches the Norwegian minutes title; leads with the name catalogs use |
| 2026-09-23 | Whole guide | Reorganized into this living doc: Start here, rule IDs A1 to A13 and C1 to C13, uniform 12-section chapters, one Review queue, this log. Rule substance unchanged except the C6 fix. | Easier to navigate, audit, and revise |
| Before 2026-09 | Whole guide | Five house-style documents consolidated into one master (details below). | One formula for every source |

### Consolidation history

What the master changed from the five original documents (tags: NO Norwegian, SE Swedish, US, PP Published & personal, PL Paperless).

**Deliberate normalizations**

| Change | Chapters | Detail |
| --- | --- | --- |
| Locality-led Titles | NO, SE, US | Parish, census, court, probate, and matrikkel titles now lead with country; `no.` dropped before volume designators; the NO "collection-led vs. locality-led" section removed; SE worked examples retitled and FRNs lead with the parish author; US state vitals and Find a Grave titles made locality-led. Call numbers untouched. |
| Online platforms to Pubinfo | US, SE, PP, NO | Find a Grave, SVAR, Ancestry Member Tree now in Pubinfo with Repository blank; custodian kept for family-held originals; Digitalarkivet rationale made explicit. City directory uses the imprint variant; online-video Pubinfo keeps homepage only. |
| US bibliography reinstated | US | Built from the A11 transform, with state-vital and census examples. |
| Unified parenthetical order | All | Disambiguator, source-state, evidence-quality; NO phrasings sorted into categories. |
| Shared rules centralized | All | Restatements replaced by references to Part A; Scandinavian scoping made explicit; every Part B chapter restructured into the same 12 sections. |
| Abbrev conventions kept | SE, US | Scandinavian lowercase record-type word; US whole-word Abbrev with its own SRN tables. |
| NO additions | NO | Ministerialbok vs. klokkerbok rule; matrikkel revision years; 1801 vs. 1865+ census distinctions. |
| PP bibliography buckets | PP | Author / collection / custodian arrangement with four buckets; interviewee-as-author (EE 4.31). |
| Paperless reframed as Part C | PL | Cross-references to Parts A and B instead of sibling files; per-document "last updated" lines removed. |
| En-dash year-ranges | All | Titles, Abbrevs, FRN/SRN, bibliography. |

**Error fixes**

| Fix | Chapters |
| --- | --- |
| "1–4 confidence scale" replaced by the 5-level Gramps scale | NO, PP; SE confidence gathered into §8 |
| "Worked example8" heading typo | US |
| Truncated examples completed (Find a Grave confidence, wedding-announcement rationale, second mixed-column FRN); stale section pointers updated | US |
| `Lars Persson Amb` example corrected to the full recorded name (applied here on 2026-09-23, see C6) | PL |
| Truncated divorce "Decisions" bullet completed; `p.` vs `pp.` clarified | PL |
| Translation note marked as non-English only | Part A |
| Swedish series names in Title parentheses capitalized consistently (`Husförhörslängder`, `Folkräkning`) | SE |
| EE anchors verified against `book.txt`: geographic locale is 2.48 (not 2.46 or 2.47); author-title 2.46; collection 2.47 | NO, SE, PP |

**Decisions confirmed by you**

- State vital records stay locality-led; the old body-led rationale is set aside.
- Folkräkning dual treatment: Repository blank in the bibliography, `Riksarkivet` allowed in Gramps.
- Photograph dual treatment: custodian when family-held, blank when cited only from the Ancestry Member Tree.
- Confirmation and communion cited within the parent register; meeting minutes as their own series.
