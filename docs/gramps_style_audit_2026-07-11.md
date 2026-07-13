# Gramps Web source & citation audit — house-style consistency

**Date:** 11 July 2026 (rev. 2 — Nasjonalarkivet findings corrected same day) · **Reference:** `bifrost/house_style_master.md` (Parts 0, A, B.1–B.4) · **Scope:** all 74 sources, 70 citations, 25 repositories, 255 notes in the GDA tree

**Method:** deterministic field checks + multi-agent audit (per-domain source-field and citation-text auditors, catalog-wide consistency pass, To-Do hygiene pass), every finding adversarially verified against the style text; 17 over-reached findings refuted and dropped. One agent slice (Swedish source fields) re-done by hand after an API failure. Rev. 2: the original audit called Nasjonalarkivet a non-existent institution — wrong; per the new archive law, Arkivverket/Riksarkivet/statsarkivene merged into Nasjonalarkivet on 1 January 2026. Those findings are reframed as a catalog-vs-master naming decision.

**Result: 398 verified findings** — 85 major, 253 minor, 60 info — touching 73 of 74 sources. The catalog is in a *mid-migration* state: everything created recently (S0002, S0070, S0072, S0073, the five locality-led Norwegian censuses) conforms closely to the master style; everything older predates the harmonization and still carries the superseded forms the master explicitly replaces. On Norwegian archive naming the catalog is *ahead* of the master, which predates the 2026 merger.

**Fully conformant exemplars:** S0002 (Norra Ny vigselbok), S0070 (laga skifte), S0073 (flyttningslängd B:3) — use these as the pattern when fixing the rest.

---

## Systemic findings (fix these as batches)

### 1. Nasjonalarkivet vs. the written style guide — naming decision needed (decision)
Eight Norwegian sources (S0015, S0036, S0038, S0064, S0069, S0071, S0076, S0077) share repository R0009 “Nasjonalarkivet” — the unified agency name in force since 1 January 2026, when the new archive law merged Arkivverket, Riksarkivet and the statsarkivene. The house style master still prescribes the pre-merger names (bare “Riksarkivet”, “Statsarkivet i Oslo”), and its own §2 rationale — “we follow the current naming” — now argues against its written value. Real regardless of the decision: census authors written three ways, sibling FRNs citing two different agency names (C0080 vs C0041/C0079), the doubled “Nasjonalarkivet (Riksarkivet)” form, and R0009 carrying the digitalarkivet.no platform URL. (§2’s claim that Nasjonalarkivet was “briefly used 2010–2018” also doesn’t match the record — the name was recommended in 2019, adopted 2026.)
**Fix:** Recommended: update house_style_master.md B.1 §2/§3 + the §11–§12 worked examples to Nasjonalarkivet — the single unified R0009 then stands as-is. Alternative: keep historical naming and split R0009 by call-number prefix. Either way: one census author value, aligned FRN citing-clauses, platform URL off R0009.

### 2. Superseded title forms on ~24 sources (major)
Part A *Title philosophy* replaces collection-led and creating-body-led titles with EE locality-led ones; these still use the old forms:
- **Swedish parish/court volumes** (the guide’s own example class): S0001, S0008, S0027, S0029, S0030, S0031, S0035, S0046, S0051 → `Sweden, Värmland, Norra Ny, clerical survey (Husförhörslängder) AI:18, 1848–1853` etc.
- **Norwegian**: S0015 (klokkerbok), S0036 (1801 census — also carries machine-path fragment `L0009` in the Title), S0064 (Botsfengslet fangeprotokoll).
- **Danish**: S0065 → `Denmark, København, police register pages (Politiets registerblade), Station 4`.
- **US church records**: S0020, S0024 (old parenthetical body-led form; S0003 shows the correct locality-led pattern).
- **US county/state records**: S0000, S0004, S0021, S0048 (county-led / body-led / smallest-first).
- **Ancestry collection names pasted verbatim**: S0011, S0025, S0026, S0034 (the “, U.S.,” gives it away) — retitle locality-led, platform collection name moves to the FRN.
- **Census wording drift**: S0006, S0023 say “U.S. Census” where the canonical form is “U.S. Federal Census” (S0074/S0075 are right).

### 3. Citation dates set on 25 of 70 citations (minor, mass-fixable)
Part A: the citation date field is **always blank**. 25 citations carry event dates, access dates, or record dates that all have proper homes elsewhere. Mass-blank them (bifrost could do this via the API in one pass).

### 4. Pubinfo drift: deep URLs, citing-clauses, six spellings of Ancestry (major/minor)
The grammar is `[medium], [platform] (homepage URL).` — homepage **only**. Violations: collection-specific URLs on S0006, S0018, S0022, S0054; “citing …” clauses and machine paths appended on S0015, S0064, S0020; Ancestry written six different ways; FamilySearch four ways; S0005 MOMS missing the platform name; S0023 with no URL. Normalize every platform source to the canonical string; move collection names/deep URLs into the FRNs.

### 5. Call-number misuse, incl. one outright wrong value (major)
Call number = the archive’s machine path, nothing else. Found: granular locators (rolls on S0006/S0023, fiche on S0044, filmrulle on S0065), platform identifiers as call numbers (Folk_817085 on S0001, FamilySearch image groups on S0017/S0033/S0045/S0048, FHL film on S0021), a series span on S0072, and — worst — **S0020 carries the *Vistrorio, Italy* image group 007961680**, a copy-paste stray from S0017/S0033. Rolls/fiche move to page strings; platform IDs move to FRN URL parentheticals.

### 6. Platforms modeled as repositories + Find a Grave scoping (major)
S0019 (Find a Grave) and S0005 (MOMS/MACO) have platform repositories; the rule is platforms are *publishers* (Pubinfo), Repository stays blank. S0019 is also one flat source spanning two cemeteries — the house style explicitly scopes **one source per cemetery**: split into Elm Park (Baudette) and Pine Hill (Williams).

### 7. Six citations lack FRN/SRN; stray note types (major)
C0005, C0007, C0042, C0044, C0053, C0060 have no First/Short Reference Note block (C0005’s raw material sits in mis-typed “Source Note”/“Source Reference Note” notes). A handful of notes use ad-hoc types (`General`, `Reference`, `Transcript`, `Source Note`) for citation prose. Compose the missing FRN/SRNs (bifrost’s composer) and retype/merge the strays.

### 8. Abbrev drift: USPS codes, hyphens, ordering (minor)
USPS two-letter codes in six abbrevs (S0006, S0022, S0023, S0025, S0026, S0043) — the style mandates traditional forms (`Minn.`). Hyphen year-ranges instead of en-dashes in eight Swedish abbrevs + S0015/S0036. Census abbrevs ordered two ways — standardize county-first. Three real sources lack abbrevs entirely (S0004, S0018, S0040).

### 9. Index-database confidence spread (minor)
The same record class (no-image index databases) is rated High on S0005/S0010/S0022/S0034/S0043, Normal on S0025/S0026, Low on one MOMS citation. The confidence table anchors derivative no-image databases at **Normal at most**. Also §8 caps: husförhörslängd household entries rated Very High on S0008/S0030 should be High.

### 10. Fifteen To-Do/blog records living as sources (minor)
S0013, S0014, S0037, S0049, S0057–S0063, S0068 are research To-Dos — re-parent each note (they’re already type “To Do”) onto the relevant person and delete the source shell. S0012 (site welcome), S0039/S0056 (monthly updates) are blog posts — keep but tag for exclusion from the bibliography transform.

### 11. Page strings & FRN prose (the long tail: 109 findings)
Recurring: subjects missing the `[name] [record-noun]` shape, `entry for [name]` inversions, place names in the subject slot (C0073), viewer positions (“image 352 of 1292”) as locators, missing volume designators/petition numbers, “and”-couples instead of hyphenated couples, glosses missing on first use or repeated in SRNs, extracted facts in FRNs that belong in Abstracts, one FRN citing the wrong archive (C0032: “citing Riksarkivet” for a Värmlandsarkiv volume), one placeholder URL “(… : accessed …)” (C0066), and a whereabouts clause contradicting the repository (C0060). See the per-source table.

---

## Per-source findings

### S0000 — Marshall Co. naturalization petitions, 1894–1901
- **[major] title** (B.3 §4 Source title)
  - Title "Marshall Co. naturalization petitions, 1894–1901" does not follow the naturalization template `[Court], Naturalization Records, [year-range]`: it omits the court (the navigable archival unit), uses the abbreviation "Co." (abbreviations belong in Abbrev/SRN, not the Title), and substitutes an ad-hoc lowercase series name.
  - **Fix:** Marshall County District Court, Naturalization Records, 1894–1901
- **[major] title** (Part A — Title philosophy)
  - US county/state record titles written several non-locality-led ways: S0000 "Marshall Co. naturalization petitions, 1894–1901" (county-led, abbreviated "Co." in a Title), S0004 "Chisago County (Minnesota), Certificates of Birth" (EE-parenthetical body-led), S0021 "Ada County, Idaho, Marriage Records" (smallest-jurisdiction-first), S0048 "Beltrami County District Court, Naturalization Records, 1887-1956" (creating-body-led), S0066 "Idaho Birth Records, 1861-1924" (collection-name). Title philosophy requires largest jurisdiction first, then series, then years, and explicitly supersedes the body-led US-vital form.
  - **Fix:** S0000 → "Minnesota, Marshall County, naturalization petitions, 1894–1901"; S0004 → "Minnesota, Chisago County, birth certificates"; S0021 → "Idaho, Ada County, marriage records"; S0048 → "Minnesota, Beltrami County, naturalization records, 1887–1956"; S0066 → "Idaho, birth certificates, 1861–1924".
- **[minor] abbrev** (B.3 §10 Abbrev rule)
  - Abbrev "Marshall Co. naturalization petitions, 1894-1901" drifts from the prescribed pattern (`St. Louis Co. naturalizations, 1888–1955` / `Beltrami Co. naturalizations, 1887–1956`) and uses a hyphen instead of an en dash in the year range.
  - **Fix:** Marshall Co. naturalizations, 1894–1901
- **[minor] · C0000 date** (Part A — Citation date)
  - Citation date field is set; the house style says the citation date is always left blank (the event date lives on the event, access date in the FRN, record-creation range in the Title).
  - **Fix:** Blank the citation date field.
- **[minor] · C0000 frn** (B.3 §12 Worked example 3)
  - FRN opens "Marshall County naturalization records, Petitions for Naturalization, 1894-1901, Final Papers, vol. C, F, petition of Peter L. Grund" — it leads with the record set instead of the creating court, unlike the house form which leads "St. Louis County District Court (Duluth, Minnesota), Naturalization Records, petition no. [N] (1894), Per Larsson; …".
  - **Fix:** Marshall County District Court (Warren, Minnesota), Naturalization Records, 1894–1901, Final Papers, vol. C, F, petition no. [N] (1897), Peter L. Grund; digital image, FamilySearch (https://www.familysearch.org/ark:/61903/3:1:3Q9M-CS3H-QLLB, image 352 of 1292, image group 101714756 : accessed 12 March 2026); citing Minnesota Historical Society, St. Paul, Minnesota.
- **[minor] · C0000 page** (B.3 §7 Citation page templates; Part A — Two-forms-two-homes locator)
  - Page string "Final Papers, vol. C, F, image 352 of 1292, Peter L. Grund naturalization petition" omits the petition number required by the naturalization template and carries the viewer position "image 352 of 1292", which belongs only in the FRN's URL parenthetical, not the page string.
  - **Fix:** Final Papers, vol. C, F, petition no. [N], Peter L. Grund naturalization petition
  - *Verifier adjustment:* Half right. The missing petition number is real: B.3 §7 requires 'Petition no. [N], [Name] naturalization petition' and the record's page string has no petition number. But the claim that 'image 352 of 1292' belongs ONLY in the FRN URL parenthetical is not supported: Part A 'Two-forms-two-homes locator' explicitly homes image numbers among the granular locators that live in the Citation page string, and the §7 church template models '(image [I])' in the page string; only raw/opaque image IDs and URL parameters (e.g. 'image group 101714756', 'kb2006…') are FRN-only. Corrected issue: page string omits the required petition number. Corrected fix: 'Final Papers, vol. C, F, petition no. [N] (image 352 of 1292), Peter L. Grund naturalization petition' — dropping the image locator (as originally proposed) is permitted but not mandated by the style.
- **[minor] · C0000 srn** (B.3 §10 Abbrev rule)
  - SRN "Marshall Co. naturalization records, Petitions for Naturalization, 1894-1901, petition of Peter L. Grund, 12 March 1897; FamilySearch image 352." is uncompressed (should use natz. and pet. no.) and carries an image number, which does not belong in the subsequent-reference form.
  - **Fix:** Marshall Co. natz., pet. no. [N] (1897), Peter L. Grund.

### S0001 — Folkräkning 1880, Norra Ny församling, Värmland
- **[major] title** (Part A — Title philosophy; B.2 §4)
  - Title "Folkräkning 1880, Norra Ny församling, Värmland" is record-type-led and smallest-jurisdiction-first with no country; the B.2 §4 template is "Sweden, [län], [parish], population count (Folkräkning) [year]".
  - **Fix:** Sweden, Värmland, Norra Ny, population count (Folkräkning) 1880
- **[minor] call_number** (Part 0 — Gramps field map (Source Call number); Part A — Two-forms-two-homes locator)
  - Platform identifiers used as Call numbers instead of archive machine paths: S0001 "Folk_817085" (the guide's own list of opaque URL parameters includes "Folk_817085-004"), S0017 "FamilySearch image group 007961680", S0033 "Image group number 007961680" (same value, different wording), S0045 "image group 004437194", S0048 "film 101513828". S0021's call# "FHL film 1509771" also mismatches its stated repository (Ada County Recorder).
  - **Fix:** Reserve Call number for the holding archive's machine reference (NAD path, county volume ref, etc.); move FamilySearch image-group/film numbers and SVAR Folk_ identifiers into the FRN URL parentheticals. For S0021 either name FHL as repository for the film or record the county's own volume reference.
- **[minor] note_type** (Part A — Citation notes structure (source-level notes not required; legacy SOURCE LIST ENTRY blocks can be deleted))
  - Source-level note N0074 (type "Source Note") is a legacy source-list entry: "Sveriges folkräkning 1880, Norra Ny församling, Värmlands län. Digital images. Riksarkivet, https://sok.riksarkivet.se." — it duplicates the Title/Pubinfo fields.
  - **Fix:** Delete note N0074; the Source fields carry the bibliographic information and the bibliography is generated by transform.
- **[info] · C0001 abstract** (Part A — Citation notes structure (Abstract = summary of what the record contains))
  - Abstract N0065 ends with an inference, not record content: "Per Larsson is Lars's son based on the patronymic and birth year matching." The census does not state the relationship; analysis belongs with the existing Analysis note (N0021).
  - **Fix:** Move the sentence to the Analysis note N0021 and keep the Abstract to what the record states.
- **[info] · C0001 frn** (B.2 §12 Worked example (SVAR Folkräkning): gloss offered on first use; droppable by authorial judgement)
  - FRN opens "Sveriges folkräkning 1880, Norra Ny församling..." without the bracketed English gloss; the §12 model for this exact database opens "Sveriges folkräkning 1880 [Swedish population count 1880], ...". The guide allows dropping it by authorial judgement, but this stored FRN is the first-use form.
  - **Fix:** Optionally insert the gloss: "Sveriges folkräkning 1880 [Swedish population count 1880], Norra Ny församling, ...".

### S0002 — Sweden, Värmland, Norra Ny, banns and marriage book (Lysnings- och Vigselbok) E:5, 1861–1884
- **[minor] · C0031 frn** (Part A — Citation notes structure (FRN/SRN block form))
  - The label is duplicated in note N0056: "FIRST REFERENCE NOTE:\nFIRST REFERENCE NOTE: Norra Ny församling, ..." — the header appears twice in a row.
  - **Fix:** Delete the second "FIRST REFERENCE NOTE: " so the note reads "FIRST REFERENCE NOTE:\nNorra Ny församling, Lysnings- och Vigselbok...".
- **[minor] · C0031 frn** (Part A — Pubinfo grammar (image-specific URLs go inside the FRN); B.2 §12 Worked examples)
  - FRN gives only the app homepage "(https://app.arkivdigital.se : accessed 19 April 2026), Norra Ny (S) E:5, image 62" — the image reference is left as loose prose instead of a deep URL; every other ArkivDigital deep-linked citation in the group (C0033, C0034, C0038, C0039, C0075) carries the image-specific link inside the parenthetical.
  - **Fix:** Replace with the deep link for E:5 image 62, e.g. "digital image, ArkivDigital (https://www.arkivdigital.se/aid/show/v[...].b62.s57 : accessed 19 April 2026)" and drop the trailing "Norra Ny (S) E:5, image 62" clause.
- **[info] · C0031 abstract** (Part A — Citation notes structure (Abstract optional, encouraged for primary records))
  - C0031 cites an original marriage entry with a fact-rich FRN ("marriage of Per Larsson (dräng, Ambjörby) and Emma Söderström (piga, Ambjörby), 26 December 1877") but has no Abstract note.
  - **Fix:** Add an Abstract-type note summarizing the marriage entry (parties, occupations, residences, banns/marriage dates as recorded).

### S0003 — Minnesota, Marshall County, Warren, First Lutheran Church records, 1883-1952
- **[minor] abbrev** (B.3 §10 Abbrev rule — Church (congregational) records)
  - Abbrev "First Lutheran, Warren, church records, 1883-1952" deviates from the prescribed church form `[Church], [town], [state abbr.], records[, year-range]`: it truncates the church name ("First Lutheran" not "First Lutheran Church"), omits the state abbreviation "Minn.", says "church records" instead of "records", and uses a hyphen for the range.
  - **Fix:** First Lutheran Church, Warren, Minn., records, 1883–1952
- **[minor] · C0004 page** (B.3 §7 Citation page templates (church records); B.3 §9 Subject vocabulary)
  - Page string "p. 283 (image 496), Emma Söderström death entry" omits the register/volume component required by the church template and uses record-noun "death entry" although the entry (per the FRN) records both death and burial — worked example 11 models this exact record.
  - **Fix:** death and burial register, p. 283 (image 496, right), Emma Söderström death and burial entry
- **[minor] title** (Part A — Title philosophy)
  - Year range "1883-1952" uses a hyphen; every house template and worked example writes year-ranges with an en dash (e.g. "1888–1955", "1925–1941").
  - **Fix:** Minnesota, Marshall County, Warren, First Lutheran Church records, 1883–1952

### S0004 — Chisago County (Minnesota), Certificates of Birth
- **[major] · C0005 frn** (Part A — Citation notes structure)
  - No FIRST REFERENCE NOTE / SHORT REFERENCE NOTE block (raw material sits in mis-typed notes ('Source Note'/'Source Reference Note')). FRN and SRN are required for every citation.
  - **Fix:** Compose the FRN/SRN per the domain chapter (bifrost's citation composer can draft it) and store in a Citation-type note.
- **[major] title** (Part A — Title philosophy)
  - Title "Chisago County (Minnesota), Certificates of Birth" is county-led with a parenthetical state; the house form is locality-led with the largest jurisdiction first, lowercase series, and a year-range (cf. B.3 §4 vitals pattern `[State], [record series], [year-range]`).
  - **Fix:** Minnesota, Chisago County, birth certificates, [year-range] (add the collection's year-range when known)
- **[minor] abbrev** (Part 0 — Gramps field map; domain §10)
  - Source has no Abbrev; every real source needs the short identifier for Gramps source-list views.
  - **Fix:** Add the domain §10-form abbrev.
- **[minor] author** (B.3 §2 Source author)
  - Author "Chisago County Register of Deeds" is not one of the two prescribed county-vitals author values (`[County] County Clerk` or `[County] County Recorder`).
  - **Fix:** Chisago County Recorder
- **[minor] · C0005 date** (Part A — Citation date)
  - Citation date field is set; the house style says the citation date is always left blank (the event date lives on the event, access date in the FRN, record-creation range in the Title).
  - **Fix:** Blank the citation date field.
- **[minor] · C0005 note_type** (Part A — Citation notes structure)
  - Citation carries five notes typed "Source Note" / "Source Reference Note" (N0009–N0014) holding record-content statements (e.g. "Certificate lists John Michael Grund as father and Carol Ann Grund (Maisuk) as mother."); the sanctioned citation-note structure is FRN + SRN plus optional Abstract/Transcription/Translation.
  - **Fix:** Consolidate N0011–N0014 into a single Abstract note; move the provenance sentence of N0009 ("certified copy issued 2004-10-14 in Chisago County; held by Peter Michael Grund") into the First Reference Note prose when the missing FRN/SRN block is written
- **[minor] · C0005 note_type** (Part A — Citation notes structure)
  - Notes N0011–N0014 (type "Source Reference Note", an odd label) each hold extracted record facts ("Certificate records birth date as 2000-01-25 08:58 CST…", parents' names, sex, parents' birthplaces) — this is abstract content spread across four mis-typed notes.
  - **Fix:** Consolidate N0011–N0014 into ONE note of type Abstract summarizing the certificate's contents, and delete the four Source Reference Note notes.
- **[minor] · C0005 page** (B.3 §7 Citation page templates)
  - Page string "Certificate no. S22-002169064" has a locator but no subject; the birth-certificate template requires "Certificate no. [N], [Name] birth certificate".
  - **Fix:** Certificate no. S22-002169064, Peter Michael Grund birth certificate
- **[minor] pubinfo** (Part A — Pubinfo grammar)
  - Pubinfo "Chisago County, Minnesota" is a bare jurisdiction — it is neither the `[medium], [platform] (homepage URL).` form nor the published-works imprint `[City]: [Publisher], year.`; this is an unpublished certificate consulted as a paper certified copy, so no publication statement applies.
  - **Fix:** Leave Pubinfo blank
- **[info] repository** (Part A — Repository decision tree)
  - No repository is attached although note N0009 records "held by Peter Michael Grund"; Part A step 2 prescribes `[Custodian], private collection` for family-held originals, while B.3 §3's table instead says blank with the holder transcribed into FRN prose — the two texts conflict, so this cannot be scored higher than info.
  - **Fix:** Either attach repository `Peter Michael Grund, private collection` (Part A form) or keep Repository blank and state the custodian in the FRN once a proper FRN is written (B.3 §3 form); pick one convention tree-wide
  - *Verifier adjustment:* Issue is real (family-held item, empty Repository), but the guide is not an unresolved tie: Part 0 front matter makes Part A authoritative ('If a rule appears in Part A, do not restate or contradict it inside a chapter'), B.3 §3's own opening sentence restates the Part A tree including the family-custodian step, and Part A step 2's worked example is literally 'Peter Michael Grund, private collection'. The §3 blank-row clause for family-held records is the contradicting, losing text. Corrected fix: attach Repository 'Peter Michael Grund, private collection' per Part A step 2 (with the custodian also named in FRN prose); severity minor rather than info, and no 'pick one convention' choice is needed.

### S0005 — Minnesota Official Marriage System (MOMS)
- **[major] · C0007 frn** (Part A — Citation notes structure)
  - No FIRST REFERENCE NOTE / SHORT REFERENCE NOTE block (citation has no notes at all). FRN and SRN are required for every citation.
  - **Fix:** Compose the FRN/SRN per the domain chapter (bifrost's citation composer can draft it) and store in a Citation-type note.
- **[major] · C0019 page** (Part A — Two-forms-two-homes locator (hard rule 2); B.3 §7 Citation page templates)
  - Page string "Certificate no. 32700160, Mayme R Castellano and Edmund G Grund, St. Louis County, Minnesota" carries a place name ("St. Louis County, Minnesota") in the page string — place belongs on the event and in the FRN prose — and uses full names instead of couple shorthand + record-noun.
  - **Fix:** Certificate no. 32700160, Castellano-Grund marriage
- **[major] · C0020 page** (Part A — Two-forms-two-homes locator (hard rule 2); B.3 §7 Citation page templates)
  - Page string "Certificate no. U3-029, Emma Mollo and Mike Castellano, St. Louis County, Minnesota" carries a place name in the page string and uses full names instead of couple shorthand + record-noun.
  - **Fix:** Certificate no. U3-029, Mollo-Castellano marriage
- **[major] · C0021 page** (Part A — Two-forms-two-homes locator (hard rule 2); B.3 §7 Citation page templates)
  - Page string "Certificate no. M341, Douglas Clyde Grund and Genell Alyce C Bagne, Pope County, Minnesota" carries a place name in the page string and uses full names instead of couple shorthand + record-noun.
  - **Fix:** Certificate no. M341, Grund-Bagne marriage
- **[major] · C0023 page** (Part A — Two-forms-two-homes locator (hard rule 2); B.3 §7 Citation page templates)
  - Page string "Certificate no. D-22, Anna Grund and Theodore Peterson, Marshall County, Minnesota" carries a place name in the page string and uses full names instead of couple shorthand + record-noun.
  - **Fix:** Certificate no. D-22, Grund-Peterson marriage
- **[major] · C0027 page** (Part A — Two-forms-two-homes locator (hard rule 2); B.3 §7 Citation page templates)
  - Page string "Certificate no. 000d-430, Thomas Siggarud and Kari Halvorson, Clay County, Minnesota" carries a place name in the page string and uses full names instead of couple shorthand + record-noun.
  - **Fix:** Certificate no. 000d-430, Siggarud-Halvorson marriage
- **[major] · C0059 page** (Part A — Two-forms-two-homes locator (hard rule 2))
  - Page string "Certificate no. C-369, Marshall Co., Cook-Grund marriage" carries the place name "Marshall Co." in the page string; place lives on the event and in the FRN prose (the couple shorthand itself is correct).
  - **Fix:** Certificate no. C-369, Cook-Grund marriage
- **[major] repository** (Part A — Repository decision tree)
  - Repository "Minnesota Association of County Officers" (R0004) names the platform owner of an online-only database; step 3 of the decision tree says online-only platforms are publishers, not repositories — the platform name goes to Pubinfo and Repository is left blank (also B.3 §3).
  - **Fix:** Remove the repository link; leave Repository blank (MACO appears as publisher in Pubinfo and in the FRN)
- **[minor] · C0019 confidence** (Part A — Confidence)
  - MOMS is an index-only database (Pubinfo "Database", no images); Part A anchors "compiled databases without source images" at Low, yet C0019, C0020, C0021, C0023, and C0027 are set to 3 (High) and C0059 to 2 (Normal), while C0007 is 1 (Low) — mostly too high and internally inconsistent across identical entry types.
  - **Fix:** Set all MOMS citations (C0019, C0020, C0021, C0023, C0027, C0059) to 1 (Low), matching C0007.
- **[minor] confidence** (Part A — Confidence)
  - Index-only databases carry wildly different confidence for the same record class: conf=3/High on S0005 (C0019, C0020, C0021, C0023, C0027), S0010 (C0006), S0022 (C0024), S0034 (C0037), S0043 (C0045), but conf=2/Normal on S0025 (C0028), S0026 (C0029) and S0005's own C0059, and conf=1/Low on S0005 C0007. The Confidence table anchors derivative indexes at Normal at best and "compiled databases without source images" at Low.
  - **Fix:** Normalize index-database citations to one level per the table — Normal (2) at most for these no-image indexes, or Low (1) if treated strictly as compiled databases without images — and document any deliberate exception in the citation.
- **[minor] · C0007 date** (Part A — Citation date)
  - Citation date field is set; the house style says the citation date is always left blank (the event date lives on the event, access date in the FRN, record-creation range in the Title).
  - **Fix:** Blank the citation date field.
- **[minor] · C0019 date** (Part A — Citation date)
  - Citation date field is set; the house style says the citation date is always left blank (the event date lives on the event, access date in the FRN, record-creation range in the Title).
  - **Fix:** Blank the citation date field.
- **[minor] · C0020 date** (Part A — Citation date)
  - Citation date field is set; the house style says the citation date is always left blank (the event date lives on the event, access date in the FRN, record-creation range in the Title).
  - **Fix:** Blank the citation date field.
- **[minor] · C0021 date** (Part A — Citation date)
  - Citation date field is set; the house style says the citation date is always left blank (the event date lives on the event, access date in the FRN, record-creation range in the Title).
  - **Fix:** Blank the citation date field.
- **[minor] · C0023 date** (Part A — Citation date)
  - Citation date field is set; the house style says the citation date is always left blank (the event date lives on the event, access date in the FRN, record-creation range in the Title).
  - **Fix:** Blank the citation date field.
- **[minor] · C0027 date** (Part A — Citation date)
  - Citation date field is set; the house style says the citation date is always left blank (the event date lives on the event, access date in the FRN, record-creation range in the Title).
  - **Fix:** Blank the citation date field.
- **[minor] · C0019 frn** (Part A — Citation notes structure (FRN access-date form per B.3 §12 worked examples))
  - FRN access date is ISO-formatted: "(https://moms.mn.gov/ : accessed 2026-04-17)" — every house worked example and the sibling MOMS citations (C0020/C0021/C0023/C0027) use day-Month-year form.
  - **Fix:** (https://moms.mn.gov/ : accessed 17 April 2026)
- **[minor] · C0059 frn** (Part A — Citation notes structure; cross-citation consistency (B.3 §12 database FRN form))
  - FRN has the typo "marriage of Merton R Cookand Minnie Grund" (missing space), names the database twice ("Minnesota Official Marriage System (MOMS), certificate no. C-369 … database, Minnesota Official Marriage System (MOMS)"), and deviates from the lead form used by the other six MOMS citations.
  - **Fix:** "Minnesota Official Marriage System," database, Minnesota Association of County Officers (https://moms.mn.gov/ : accessed 17 May 2026), entry for Merton R. Cook and Minnie Grund, 14 November 1899, Marshall County, Minnesota, certificate no. C-369.
  - *Verifier adjustment:* All three defects are real in N0101 (the 'Cookand' typo, the database named twice, and the author-led lead form) and the proposed fix correctly mirrors the sibling FRN structure with the original 17 May 2026 access date. Corrected wording: the standard quoted-title lead form is used by the FIVE sibling MOMS FRNs (C0019, C0020, C0021, C0023, C0027) — not 'the other six'; the sixth sibling, C0007, has no FRN note at all (a separate mechanical-pass finding).
- **[minor] · C0007 page** (Part A — Subject formatting in the page string; B.3 §7 Citation page templates)
  - Page string "Entry for John Grund and Carol Maisuk, marriage date 1998-10-17, certificate no. M64600230" puts the locator last instead of first, duplicates the event date (which lives on the event) in ISO form, and uses full names instead of the hyphenated-couple shorthand with record-noun.
  - **Fix:** Certificate no. M64600230, Grund-Maisuk marriage
- **[minor] pubinfo** (Part A — Pubinfo grammar)
  - Pubinfo "Database, https://moms.mn.gov/" omits the publisher/platform name and the parenthesized-homepage form `[medium], [platform] (homepage URL).`
  - **Fix:** Database, Minnesota Association of County Officers (https://moms.mn.gov).
- **[minor] pubinfo** (Part A — Pubinfo grammar; Part A — Pubinfo grammar (Published-works imprint variant))
  - Pubinfo strings not in any sanctioned grammar form: S0005 "Database, https://moms.mn.gov/" (missing platform name before the URL), S0007 "Williams, Minnesota, 1953" (funeral program missing "[City]: [Funeral home], date"), S0016 "Ca. May 1952" (a date, not a production statement), S0040 "Unpublished research" (missing "[location], [year-range]" vs S0050's complete form), S0044 "Northwestern Bell, Minneapolis, December 1984; reproduced..." (imprint order reversed, no colon), and online books S0041/S0042 give only "Digital images, Nasjonalbiblioteket (...)" without the required "[City]: [Publisher], year." imprint.
  - **Fix:** S0005 → "Database, Minnesota Official Marriage System (https://moms.mn.gov)."; S0007 → "Williams, Minnesota: Helgeson Funeral Home, 1953."; S0016 → move "ca. May 1952" into the FRN; S0040 → "Unpublished research, Ambjörby, Sweden, [year-range]."; S0044 → "Minneapolis: Northwestern Bell, December 1984. Microfiche, Bell & Howell PhoneFiche."; S0041/S0042 → prepend the print imprint, then "Digital images, Nasjonalbiblioteket (https://www.nb.no)."
- **[minor] · C0059 srn** (B.3 §10 Abbrev rule; cross-citation consistency)
  - SRN form is inconsistent within the source: C0059 uses "MOMS cert. C-369, Cook-Grund marriage." while C0019–C0027 use the long form "\"Minnesota Official Marriage System,\" Castellano-Grund marriage, 1950, cert. no. 32700160." — same record series, two SRN styles.
  - **Fix:** Standardize all MOMS SRNs on the compact abbrev-based form, e.g. "MOMS, cert. no. 32700160, Castellano-Grund marriage (1950)." (§10: the SRN compresses further than the Abbrev, and "MOMS" is the established short identifier).
  - *Verifier adjustment:* The inconsistency is real (C0059 'MOMS cert. C-369, Cook-Grund marriage.' vs the long quoted-title form in C0019–C0027) and §10 supports standardizing on the compact Abbrev-based form ('MOMS' is the Source Abbrev; the SRN compresses further than the Abbrev). But the proposed fix misplaces the year: house SRNs put the year in parentheses after the locator, not after the subject — cf. §10's worked compression 'pet. no. [N] (1920), Louis Grund' and worked example 2's SRN 'Minn. death cert. 1929-MN-XXXXXX (1929), Per Larsson Grund.' Corrected fix: 'MOMS, cert. no. 32700160 (1950), Castellano-Grund marriage.' (and the same pattern for the other MOMS SRNs).
- **[info] abbrev** (B.3 §10 Abbrev rule)
  - Abbrev "MOMS" is an acronym only; the US convention "keeps whole readable words" for the source-list view, and MOMS is not among the sanctioned collection abbreviations (FAG/ED/RG/NAID).
  - **Fix:** Minn. Official Marriage System (MOMS)

### S0006 — 1940 U.S. Census, St. Louis County, Minnesota
- **[major] abbrev** (Part A — Universal SRN abbreviations)
  - USPS two-letter state codes in abbrevs despite "traditional pre-USPS form: Minn., Wis., S. Dak., never USPS two-letter codes": S0006 "1940 Census, St. Louis Co., MN", S0023 "1920 Census, Beltrami Co., MN", S0022 "MN Divorce Index, 1970-1995", S0025 "MN Naturalization Records Index", S0026 "MN Death Index", S0043 "MN Death Index 1944-1953".
  - **Fix:** Replace MN with Minn.: e.g. "St. Louis Co., Minn., 1940 census", "Beltrami Co., Minn., 1920 census", "Minn. Divorce Index, 1970–1995", "Minn. Naturalization Records Index", "Minn. Death Index, 1908–2017", "Minn. Death Index, 1944–1953".
- **[major] call_number** (B.3 §5 Locator / volume notation tokens)
  - Call number "T627, roll [NEEDED: roll number]" includes the roll; "the roll number is citation-level, not source-level, because a Source (county-state-year) can span multiple rolls" — the Call number is the publication identifier alone.
  - **Fix:** T627 (move the roll number, once known, into citation C0008's page string)
- **[major] call_number** (Part A — Source scoping (Granular identifiers stay at citation level); Part A — Two-forms-two-homes locator)
  - Granular locators on the Source: S0006 call# "T627, roll [NEEDED: roll number]" (roll also in pubinfo), S0023 call# "T625, roll 823" (roll also in pubinfo, and missing from C0025's page string), S0044 call# "Bell & Howell PhoneFiche 38472, fiche 7 of 19", S0065 call# "...Station 4, filmrulle 0005" — rolls/fiche are granular locators that "live in the page string, not on the Source." S0074 (call# "T623", roll in page string) and S0075 ("T626") show the correct split.
  - **Fix:** S0006 → call# "T627" with the roll number in C0008's page string; S0023 → call# "T625" and add "roll 823" to C0025's page string; S0044 → call# "Bell & Howell PhoneFiche 38472" (fiche is already in the page strings); S0065 → drop "filmrulle 0005" from call# (already in C0078's page string).
- **[major] pubinfo** (Part A — Pubinfo grammar)
  - Pubinfo "Ancestry (https://www.ancestry.com/search/collections/2442/); NARA microfilm publication T627, roll [NEEDED: roll number]" carries a deep collection URL (homepage only is allowed on the Source), omits the medium, and embeds the NARA publication and roll number — the machine path belongs in Call number and the roll in the citation page string (Part A Two-forms-two-homes locator; B.3 §5).
  - **Fix:** Digital images, Ancestry (https://www.ancestry.com).
- **[major] pubinfo** (Part A — Pubinfo grammar)
  - Deep, collection-specific URLs on Sources despite "URL — the platform homepage only. Collection-specific and image-specific URLs go inside the citation's First Reference Note, never on the Source": S0006 "https://www.ancestry.com/search/collections/2442/", S0018 "https://www.ancestry.com/search/collections/2375", S0022 "https://www.ancestry.com/search/collections/1081/", S0054 "https://sanbartolomeovistrorio.jimdofree.com/pubblicazioni-e-archivio/".
  - **Fix:** Replace with homepage URLs ("https://www.ancestry.com"; for S0054 "https://sanbartolomeovistrorio.jimdofree.com") and move the collection/deep URLs into each citation's FRN parenthetical.
- **[minor] abbrev** (B.3 §10 Abbrev rule — State abbreviations)
  - Abbrev "1940 Census, St. Louis Co., MN" uses the USPS two-letter code "MN"; the style uses traditional pre-USPS forms ("Minn.") and never USPS codes; worked example 1's pattern is `St. Louis Co., Minn., 1920 census`.
  - **Fix:** St. Louis Co., Minn., 1940 census
- **[minor] abbrev** (Part A — Universal SRN abbreviations)
  - Census abbrevs ordered two ways: year-first on S0006 "1940 Census, St. Louis Co., MN" and S0023 "1920 Census, Beltrami Co., MN" vs county-first on S0045 "Benton Co., Minn., 1885 state census", S0074 "Marshall Co., Minn., 1900 census", S0075 "Lake of the Woods Co., Minn., 1930 census".
  - **Fix:** Standardize on the majority county-first pattern: "St. Louis Co., Minn., 1940 census" and "Beltrami Co., Minn., 1920 census".
  - *Verifier adjustment:* The guide contains no rule on census-abbrev element order: Part A 'Universal SRN abbreviations' covers only the locator abbreviations (p., pp., vol., col., no., fol.) and defers domain abbrev tables to the chapters, and Title philosophy explicitly tolerates the date-first census form (EE 6.10). So year-first vs county-first drift is unregulated, not a violation. The rule-backed defect in these same abbrev strings is the USPS two-letter code: Part A mandates traditional pre-USPS state forms ('Minn.', 'Wis.', 'S. Dak.', never USPS codes), and S0006 ('...St. Louis Co., MN') and S0023 ('...Beltrami Co., MN') use 'MN'. Corrected fix: 'MN' → 'Minn.' in both abbrevs (e.g. '1940 Census, St. Louis Co., Minn.'); harmonizing the ordering is optional editorial preference the style does not require.
- **[minor] · C0008 date** (Part A — Citation date)
  - Citation date field is set; the house style says the citation date is always left blank (the event date lives on the event, access date in the FRN, record-creation range in the Title).
  - **Fix:** Blank the citation date field.
- **[minor] · C0008 frn** (Part A — Citation notes structure (FRN access-date form per B.3 §12 worked examples))
  - FRN access date is ISO-formatted: "(… : accessed 2026-03-03)" instead of the day-Month-year form used in every house worked example.
  - **Fix:** (https://www.ancestry.com/search/collections/2442/records/98907175 : accessed 3 March 2026)
- **[minor] · C0008 page** (B.3 §7 Citation page templates; B.3 §5 Locator / volume notation tokens)
  - Page string "Virginia, ED 69-137B, sheet 7A, dwelling 185, family 185, John Grund household" leads with the enumeration locality (place belongs in the FRN prose, not the page string — cf. worked example 1, which has no city) and omits the roll number, which per §5 lives in the citation page string, not on the Source.
  - **Fix:** roll [N], ED 69-137B, sheet 7A, dwelling 185, family 185, John Grund household
- **[minor] pubinfo** (Part A — Pubinfo grammar)
  - Ancestry platform statement written at least six ways: canonical "Digital images, Ancestry (https://www.ancestry.com)." on S0003/S0055/S0066/S0072/S0074/S0075, but S0006 omits the medium ("Ancestry (https://...); NARA microfilm publication T627..."), S0018/S0024/S0025/S0026 drop the parentheses ("...Ancestry, https://www.ancestry.com"), S0023 has no URL at all ("Imaged as \"1920 United States Federal Census,\" Ancestry; citing..."), and S0021/S0023/S0024 use an "Imaged as \"[collection]\"" preamble not in the grammar. S0010 uses a bare agency imprint ("Washington, D.C.: U.S. Department of Veterans Affairs") for what is an online database.
  - **Fix:** Normalize all Ancestry sources to "[medium], Ancestry (https://www.ancestry.com)." with the collection name and "citing ..." detail moved into FRNs; S0010 → "Database, Ancestry (https://www.ancestry.com)." if that is the access platform.
- **[minor] · C0008 srn** (B.3 §10 Abbrev rule; B.3 §12 Worked example 1)
  - SRN "1940 U.S. census, St. Louis Co., Minn., Virginia, ED 69-137B, sheet 7A, dwell. 185, John Grund household." omits "pop. sched." and uses "dwell.", which is not in the sanctioned abbreviation tables; the house SRN form drops dwelling/family entirely.
  - **Fix:** 1940 U.S. census, St. Louis Co., Minn., pop. sched., Virginia, ED 69-137B, sheet 7A, John Grund household.
- **[minor] title** (B.3 §4 Source title)
  - Title "1940 U.S. Census, St. Louis County, Minnesota" drops the word "Federal"; the template is `[year] U.S. Federal Census, [county] County, [state]`.
  - **Fix:** 1940 U.S. Federal Census, St. Louis County, Minnesota
- **[minor] title** (Part A — Title philosophy)
  - US federal-census titles written two ways: S0006 "1940 U.S. Census, St. Louis County, Minnesota" and S0023 "1920 U.S. Census, Beltrami County, Minnesota" vs S0074 "1900 U.S. Federal Census, Marshall County, Minnesota" and S0075 "1930 U.S. Federal Census, ...". The guide's canonical wording is "1920 U.S. Federal Census, St. Louis County, Minnesota".
  - **Fix:** Rename S0006 → "1940 U.S. Federal Census, St. Louis County, Minnesota" and S0023 → "1920 U.S. Federal Census, Beltrami County, Minnesota".
- **[info] · C0008 frn** (B.3 §5 Locator / volume notation tokens)
  - FRN ends "…microfilm publication T627, roll [NEEDED: roll number]" — the citation is incomplete until the T627 roll for ED 69-137B is looked up (the same placeholder sits in the Source Pubinfo/Call number, which is the source auditor's territory).
  - **Fix:** Look up the T627 roll for St. Louis County ED 69-137B and replace the placeholder in the FRN and page string.

### S0007 — Funeral program, Thomas Emil Siggerud
- **[minor] · C0009 abstract** (Part A — Citation notes structure (Abstract, encouraged for primary records) / B.4 §12 Worked examples — A funeral program (house FRN carries no biographical facts; birth-date detail handled separately))
  - The FRN embeds extracted facts — "program states date of birth as 1 September 1869 in Norway and date of death as 12 February 1953 in Baudette, Minnesota" — and the citation has no Abstract note. The worked-example FRN for this exact source omits the biographical detail from the FRN.
  - **Fix:** Strip the fact clause from the FRN and add a note of type Abstract summarizing the program's contents (birth 1 September 1869 in Norway; death 12 February 1953 at Baudette, Minnesota; funeral 16 February 1953, Rev. Edstrom; burial Pine Hill Cemetery, Williams).
  - *Verifier adjustment:* The FRN half is real: N0018 embeds "program states date of birth as 1 September 1869 ... date of death as 12 February 1953 ...", which the worked-example FRN for this exact source omits. But the missing-Abstract half is not a defect — Part A lists Abstract as "Optional, encouraged", so its absence violates nothing — and the style's prescribed home for the birth-date detail is a separate Normal-confidence citation (worked-example analysis: "treat as Normal at most, on a separate citation"), not an Abstract. Corrected fix: strip the fact clause from the FRN (already achieved by finding 0's rewrite) and carry the biographical detail on the separate citation from finding 3; an Abstract note may optionally be added but is not required.
- **[minor] · C0009 confidence** (B.4 §8 Confidence guidance (funeral-program facts about the funeral itself = High; biographical detail = Normal; "Mixed-evidence artifacts … use separate citations") / Part A — One citation vs. two)
  - Confidence is 2 (Normal) on a single citation whose FRN covers both the funeral event itself ("services held 16 February 1953 … burial at Pine Hill Cemetery") — prescribed High — and informant-supplied biographical detail ("date of birth as 1 September 1869") — prescribed Normal. Mixed evidence quality in one citation, with the funeral-event facts underrated.
  - **Fix:** Split into two citations: one for the funeral/death-event facts at High (3), one for the biographical detail (birth 1869 in Norway) at Normal (2).
- **[minor] · C0009 date** (Part A — Citation date)
  - Citation date field is set; the house style says the citation date is always left blank (the event date lives on the event, access date in the FRN, record-creation range in the Title).
  - **Fix:** Blank the citation date field.
- **[minor] · C0009 frn** (B.4 §12 Worked examples — A funeral program (FRN leads with the author, per §2 author = issuing funeral home))
  - The FRN leads "Funeral program, \"In Memory of Thomas Emil Siggerud,\" prepared by Helgeson Funeral Home (Williams, Minnesota), for funeral services held…" — the house form leads with the creating funeral home, and the custodian clause omits the locality ("Privately held by Peter Michael Grund.").
  - **Fix:** Helgeson Funeral Home, "In Memory of Thomas Emil Siggerud," funeral program for services held 16 February 1953 at Lutheran Church, Williams, Minnesota; Rev. Edstrom officiating; burial at Pine Hill Cemetery, Williams, Minnesota; privately held by Peter Michael Grund, Duluth, Minnesota.
- **[minor] · C0009 page** (B.4 §7 Citation page templates — Funeral program (`[subject]`) / Part A — Subject formatting in the page string)
  - The page string is empty (""). The funeral-program template requires a subject even though no page number is needed; the worked example uses "Thomas Emil Siggerud funeral program".
  - **Fix:** Thomas Emil Siggerud funeral program
- **[minor] pubinfo** (B.4 §6 Pubinfo (funeral program takes a full `date`); B.4 §12 Worked examples — A funeral program (Pubinfo: `Williams, Minnesota, 16 February 1953.`))
  - Pubinfo is "Williams, Minnesota, 1953" — year only, no terminal period. The §12 worked example for this exact program prescribes the full service date, which the C0009 FRN confirms as 16 February 1953.
  - **Fix:** Williams, Minnesota, 16 February 1953.
- **[minor] repository** (Part A — Repository decision tree step 2 (`[Custodian], private collection`, example `Peter Michael Grund, private collection`); B.4 §12 Worked examples — A funeral program)
  - Repository R0001 is named "Peter Grund, private collection"; the style's custodian string for family-held artifacts is consistently "Peter Michael Grund, private collection" (§3 table, §12 funeral-program worked example).
  - **Fix:** Rename repository R0001 to "Peter Michael Grund, private collection" (note: R0001 is shared with S0050, so the rename propagates there).
- **[minor] · C0009 srn** (Part A — Citation notes structure (SRN is compact) / B.4 §12 Worked examples — A funeral program (SRN: "Siggerud funeral program, 1953."))
  - The SRN reads "Funeral program, Thomas Emil Siggerud (1869–1953); privately held by Peter Michael Grund." — it carries a lifespan and repeats the custodian, which belong to the FRN, instead of the compact prescribed form.
  - **Fix:** Siggerud funeral program, 1953.

### S0008 — Norra Ny kyrkoarkiv, Husförhörslängder, AI:18 (1848-1853)
- **[major] · C0010 confidence** (B.2 §8 Confidence guidance (per record type))
  - Confidence is 4 (Very High) on a husförhörslängd household citation. §8 caps clerical-survey entries at High for residence and Normal for stated ages/birth years. The note's own SOURCE QUALITY argument ("The parish minister compiled birth data from the födelsebok into this household register") actually makes the birth data derivative, undermining Very High.
  - **Fix:** Set confidence to 3 (High) if this citation supports residence; if it is being used for the birth years of Lars, Kjerstin, Per, Olof, or Marit, split per Part A One-citation-vs-two and rate the birth-year citation 2 (Normal).
- **[major] title** (Part A — Title philosophy)
  - Swedish parish/court volumes still in the superseded collection-led form: S0008 "Norra Ny kyrkoarkiv, Husförhörslängder, AI:18 (1848-1853)", S0027 "...AI:25 (1876-1880)", S0030 "...AI:11 (1812-1820)" (the guide's own example transform uses exactly this AI:11 volume), S0031 "Norra Ny kyrkoarkiv, Födelse- och dopböcker, C:4 (1773-1825)", S0035 "...AI:12 (1820-1832)", S0046 "Norra Ny kyrkoarkiv, Död- och begravningsbok, F:1 (1765-1838)", S0051 "Norra Ny kyrkoarkiv, Flyttningslängder, B:2 (1861-1883)", S0029 "Älvdals häradsrätt, Bouppteckningar, FII:26 (1832-1833)", plus census S0001 "Folkräkning 1880, Norra Ny församling, Värmland". Correct locality-led form already used by S0002, S0070, S0072, S0073 (e.g. "Sweden, Värmland, Norra Ny, moving register (Flyttningslängder) B:3, 1884–1894").
  - **Fix:** Retitle to the locality-led pattern: S0008/S0027/S0030/S0035 → "Sweden, Värmland, Norra Ny, clerical survey (Husförhörslängder) AI:NN, YYYY–YYYY"; S0031 → "Sweden, Värmland, Norra Ny, birth and baptism book (Födelse- och dopböcker) C:4, 1773–1825"; S0046 → "Sweden, Värmland, Norra Ny, death and burial book (Död- och begravningsbok) F:1, 1765–1838"; S0051 → "Sweden, Värmland, Norra Ny, moving register (Flyttningslängder) B:2, 1861–1883" (matching S0073); S0029 → "Sweden, Värmland, Älvdals häradsrätt, estate inventories (Bouppteckningar) FII:26, 1832–1833"; S0001 → "Sweden, Värmland, Norra Ny, folkräkning 1880".
- **[minor] abbrev** (B.2 §10 Abbrev rule)
  - Abbrev year-ranges use hyphens on S0008, S0027, S0029, S0030, S0031, S0035, S0046, S0051 (e.g. "Norra Ny husförhörslängd AI:18 (1848-1853)"); §10's examples all use en-dashes (cf. conformant S0002/S0073).
  - **Fix:** Replace hyphen with en-dash in the eight abbrevs: (1848–1853), (1876–1880), (1832–1833), (1812–1820), (1773–1825), (1820–1832), (1765–1838), (1861–1883).
- **[minor] · C0010 frn** (B.2 §4 Source title (old collection-led note); B.2 §12 Worked examples; Part A — Citation notes structure)
  - FRN/SRN follow the superseded collection-led form: "Norra Ny kyrkoarkiv, husförhörslängd, 1848-1853, vol. AI:18..." — leads with the kyrkoarkiv collection instead of the creating body, has no bracketed English gloss, no "citing Värmlandsarkiv..." clause, subject is a bare given-name list ("entries for Lars, Kjerstin, Per, Olof, and Marit") instead of a named household, hyphen year-range, and the SRN ("Norra Ny husförhörslängd, 1848-1853, vol. AI:18, p. 268.") lacks the subject.
  - **Fix:** FRN: "Norra Ny församling, Husförhörslängder [household examinations], vol. AI:18 (1848–1853), p. 268, household of Lars Persson Ambjörn (begins about halfway down the page); digital image, Riksarkivet (https://sok.riksarkivet.se/bildvisning/C0038416_00287 : accessed 11 March 2026); citing Värmlandsarkiv, SE/VA/13398/A I/18." SRN: "Norra Ny husförhörslängd AI:18 (1848–1853), p. 268, Lars Persson Ambjörn household."
- **[minor] note_type** (Part A — Citation notes structure (source-level notes not required; legacy SOURCE LIST ENTRY blocks can be deleted))
  - Source-level note N0075 (type "Source Note") is a legacy source-list entry: "Norra Ny kyrkoarkiv. Husförhörslängd, 1848-1853. Vol. AI:18. Digital images. Riksarkivet, \"Bildvisning.\" sok.riksarkivet.se." — it duplicates the Source fields in the superseded collection-led form.
  - **Fix:** Delete note N0075.
- **[info] · C0010 abstract** (Part A — Citation notes structure (Abstract optional, encouraged for primary records))
  - C0010 cites an original husförhörslängd household (naming Lars, Kjerstin, Per, Olof, and Marit) but has no Abstract note; the sibling husförhörslängd citations C0030 and C0033 both carry rich Abstracts.
  - **Fix:** Add an Abstract-type note summarizing the household entry (members, recorded birth data, notations).
- **[info] · C0010 note_type** (Part A — Citation notes structure; Part A — Confidence (appraisal lives in the confidence field))
  - Note N0019 embeds a non-canonical "SOURCE QUALITY:" block ("Original source, primary information, direct evidence...") inside the citation note; the note structure defines only FRN/SRN (+ Abstract/Transcription/Translation), and evidence appraisal is carried by the confidence field.
  - **Fix:** Remove the SOURCE QUALITY block from the Citation note; if the reasoning is worth keeping, move it to a separate Analysis-type note.
- **[info] pubinfo** (Part A — Tiebreaks when a source has more than one digital home)
  - The Norra Ny husförhörslängd series is split between platforms: AI:18/AI:25/AI:11 cite Riksarkivet, AI:12 cites ArkivDigital. If the same volumes are on both, the tiebreak (image edition → system of record → platform most used) suggests one consistent publisher across the series.
  - **Fix:** Pick one platform for the husförhörslängd series where both host the images, and note the other in the FRNs.

### S0010 — Beneficiary Identification Records Locator Subsystem (BIRLS) Death File
- **[major] repository** (B.3 §3 Repository)
  - Repository "U.S. Department of Veterans Affairs" is not an institution the chapter prescribes (National Archives, state historical society/archives, county courthouse, FHL, or blank); BIRLS as used here is an online-only database, and the creating agency is already the Author — repeating it as Repository puts the record's creator in the holder slot.
  - **Fix:** Remove the repository link; leave Repository blank (online-only database; the VA stays in Author and in FRN prose)
- **[minor] · C0006 confidence** (Part A — Confidence)
  - Confidence is 3 (High) but BIRLS is an index-only database with no source images; Part A anchors "compiled databases without source images" at Low.
  - **Fix:** Set confidence to 1 (Low).
- **[minor] · C0006 date** (Part A — Citation date)
  - Citation date field is set; the house style says the citation date is always left blank (the event date lives on the event, access date in the FRN, record-creation range in the Title).
  - **Fix:** Blank the citation date field.
- **[minor] · C0006 frn** (Part A — Citation notes structure)
  - FRN access parenthetical "(https://www.va.gov : accessed January 2025)" names a URL that was not the access point and gives only month-year, while the real platform dangles outside it as "Accessed via https://www.birls.org/." — the FRN requires one parenthetical with the deep URL actually used plus a full access date.
  - **Fix:** …entry for Edmund G Grund, p. 2; database, BIRLS.org (https://www.birls.org/[record-path] : accessed [day] January 2025); citing U.S. Department of Veterans Affairs, Washington, D.C.
- **[minor] · C0006 page** (Part A — Subject formatting in the page string; Part A — Universal SRN abbreviations)
  - Page string "Entry for Edmund G Grund, page 2" trails the locator instead of leading with it, spells out "page" instead of the token "p.", and lacks a record-noun on the subject.
  - **Fix:** p. 2, Edmund G. Grund BIRLS death file entry
- **[minor] pubinfo** (Part A — Pubinfo grammar)
  - Pubinfo "Washington, D.C.: U.S. Department of Veterans Affairs" uses the published-works imprint variant (and even then lacks the year); this source is a database, which takes `[medium], [platform] (homepage URL).`
  - **Fix:** Database, BIRLS.org (https://www.birls.org). (the platform through which the file was accessed per the FRN)

### S0011 — WWII Draft Registration Cards for Minnesota, 1940-1947
- **[major] pubinfo** (Part A — Pubinfo grammar)
  - Pubinfo "Records of the Selective Service System, Record Group 147; National Archives at St. Louis, St. Louis, Missouri" is archival identification, not a publication statement: the RG belongs in Call number, and "If a specific NARA facility matters, put that detail inside the First Reference Note prose" (B.3 §3) — the FRN already carries both.
  - **Fix:** Leave Pubinfo blank (record cited from the NARA original; if the image actually came from a platform, use `Digital images, [Platform] (homepage URL).`)
- **[major] title** (Part A — Title philosophy)
  - Platform collection names copied verbatim as Source Titles (Ancestry's ", U.S.," naming convention betrays the origin): S0011 "WWII Draft Registration Cards for Minnesota, 1940-1947", S0025 "Minnesota, U.S., Naturalization Records Index, 1854-1957", S0026 "Minnesota, U.S., Death Index, 1908-2017", S0034 "U.S., Social Security Death Index, 1935-2014". These are collection-led titles, superseded by the locality-led house form.
  - **Fix:** Retitle locality-led and move the platform collection name into the FRN's "imaged as"/database clause: S0011 → "Minnesota, WWII draft registration cards, 1940–1947"; S0025 → "Minnesota, naturalization records index, 1854–1957"; S0026 → "Minnesota, death index, 1908–2017"; S0034 → "United States, Social Security Death Index, 1935–2014".
- **[minor] abbrev** (B.3 §10 Abbrev rule)
  - Abbrev "WWII Draft Card, Minnesota, RG 147" carries the archive machine reference "RG 147" (Call-number content, not a readable identifier) and drifts from worked example 5's form `WWII draft cards, Minn.` (singular "Card", unabbreviated "Minnesota").
  - **Fix:** WWII draft cards, Minn.
- **[minor] call_number** (B.3 §5 Locator / volume notation tokens)
  - Call number "Record Group 147, Box 79" spells out Record Group (house abbreviation is `RG`, cf. worked example 5's `RG 147`) and includes the box, a granular locator that belongs at citation level / in the FRN (Part A Two-forms-two-homes locator) — the FRN already cites Box 79.
  - **Fix:** RG 147
- **[minor] · C0011 date** (Part A — Citation date)
  - Citation date field is set; the house style says the citation date is always left blank (the event date lives on the event, access date in the FRN, record-creation range in the Title).
  - **Fix:** Blank the citation date field.
- **[minor] · C0011 frn** (Part A — Citation notes structure; B.3 §12 Worked example 5)
  - FRN embeds the extracted fact "(11 September 1927)" — the registrant's birth date — which belongs in the Abstract note, not the FRN; worked example 5's FRN carries only the registration year.
  - **Fix:** Move the birth date to an Abstract note; FRN identifies the card as "…serial no. [N], Edmund Gene Grund (1946)…".
  - *Verifier adjustment:* Real deviation, wrong rationale: worked example 5 models the parenthetical as the registration year, so the FRN should read 'Edmund Gene Grund (1946)' rather than '(11 September 1927)'. But 'extracted facts belong in the Abstract note, not the FRN' is not a house rule — Part A makes Abstract optional, and worked examples 6 and 11 embed record dates in FRN prose. Corrected fix: replace the birth-date parenthetical with the registration year (1946); the birth date may optionally move to an Abstract note.
- **[minor] · C0011 frn** (Part A — Citation notes structure; B.3 §12 Worked example 5)
  - FRN leads with the record ("World War II Draft Registration Card for Edmund Gene Grund…") instead of the creating body, and contains no digital-access clause (URL + access date) although an image is attached (n_media=1), suggesting online access.
  - **Fix:** Selective Service System, World War II Draft Registration Cards, Minnesota, serial no. [N], Edmund Gene Grund (1946), Eveleth, St. Louis County, Minnesota; digital image, [platform] ([deep URL] : accessed [date]); citing Record Group 147, Box 79, National Archives at St. Louis, St. Louis, Missouri.
  - *Verifier adjustment:* The lead defect is confirmed (worked example 5 leads with the creating body 'Selective Service System, World War II Draft Registration Cards, Minnesota, …'; the record leads with the record noun). But the missing digital-access clause is only a defect if the image was accessed via an online platform — n_media=1 does not establish that, and the style requires no URL when no platform was used (cf. the S0016 clipping FRN). Corrected fix: restructure the FRN to lead with Selective Service System per worked example 5; add a digital-access clause only if a platform was actually used, otherwise citing the physical archive directly is correct.
- **[minor] · C0011 note_type** (Part A — Citation notes structure)
  - Note N0028 is typed "General" but holds record-content summary ("Was aged 18 at the time of registration. Height recorded as 5 feet 6 inches. Weight recorded as 150."); the sanctioned optional citation-note type for a summary of what the record contains is Abstract.
  - **Fix:** Retype/reformat N0028 as an Abstract note
- **[minor] · C0011 note_type** (Part A — Citation notes structure)
  - Note N0028 (type "General") holds abstract content: "Was aged 18 at the time of registration. Height recorded as 5 feet 6 inches. Weight recorded as 150." — extracted facts belong in a note of type Abstract.
  - **Fix:** Retype/move N0028's content into an Abstract note for this citation (together with the birth date currently in the FRN).
- **[minor] · C0011 page** (B.3 §7 Citation page templates)
  - Page string "Draft Registration Card for Edmund Gene Grund" omits the serial number and inverts the template shape "Serial no. [N], [Name] WWII draft card".
  - **Fix:** Serial no. [N], Edmund Gene Grund WWII draft card
- **[minor] · C0011 srn** (B.3 §12 Worked example 5; Part A — Citation notes structure)
  - SRN "WWII Draft Registration Card, Edmund Gene Grund (1946), RG 147, Box 79; NARA St. Louis." carries archival detail (RG, box, facility) beyond the compact subsequent-reference form modeled as "WWII draft card, Minn., Axel O. Grund."
  - **Fix:** WWII draft card, Minn., Edmund Gene Grund (1946).
- **[minor] title** (B.3 §4 Source title)
  - Title "WWII Draft Registration Cards for Minnesota, 1940-1947" deviates from the template `World War II Draft Registration Cards, [state]`: "WWII" is an abbreviation (SRN-level), "for" is not in the template, and the template carries no year-range.
  - **Fix:** World War II Draft Registration Cards, Minnesota
- **[info] · C0011 confidence** (B.3 §8 Confidence guidance (per record type))
  - Confidence is 4 (Very High); worked example 5 prescribes High for the card's facts (birth date, residence, next-of-kin), reserving Very High for the registration event itself.
  - **Fix:** If this citation supports biographical facts (birth, residence), drop to 3 (High); keep 4 only if attached solely to the registration event.
  - *Verifier adjustment:* Issue real but mis-cited: B.3 §8 contains no draft-card entry — the High-for-card-facts / Very-High-for-registration-event split comes from §12 worked example 5's closing prose (1942 Fourth Registration, applied analogously to this 1946 card). Fix stands as stated with the corrected citation: B.3 §12 worked example 5.

### S0012 — Welcome to the GDA
- **[minor] scoping** (Part A — Source scoping)
  - "Welcome to the GDA" is a website welcome letter ("If you are reading this, you have successfully logged into our new family history website..."), not a source: it matches no unit in the Source-scoping table, wraps no future source, and has zero citations. It likely exists as a Source only because Gramps Web's blog feature renders Source+Note records as posts. Under Part A Bibliography mapping it would surface as a bogus bibliography line ("Grund, Peter. Welcome to the GDA.").
  - **Fix:** If it powers the Gramps Web blog, keep the record but tag it (e.g. 'blog' or 'no-biblio') and exclude tagged Sources from the bibliography transform; otherwise delete the Source and keep N0029 as a standalone General note or site content.
- **[minor] scoping** (Part A — Bibliography mapping)
  - Cross-cutting (all 15 records in this group: S0012–S0014, S0037, S0039, S0049, S0056–S0063, S0068): 12 research To-Dos, 2 monthly research updates, and 1 website welcome note are stored as Gramps Source records with zero citations and empty pubinfo/abbrev/repository. Part 0 states the Source List must "transform cleanly into an EE-style bibliography for the book", and Part A Bibliography mapping transforms every Source into a Source List Entry — these 15 would emit 15 garbage bibliography lines and none matches any unit in the Part A Source-scoping table. The style is silent on where research tasks live, so the mechanism below is a recommendation, not a stated rule.
  - **Fix:** Adopt a standing convention: (1) research To-Dos live as Gramps native To Do notes attached to the relevant person/family/citation (the 12 notes already carry type "To Do" — re-parent them and delete the emptied Source shells; Gramps's To Do gramplet then aggregates them); (2) any Source records that must remain for Gramps Web's blog feature (S0012, S0039, S0056) get a dedicated tag (e.g. 'blog') and the bibliography transform excludes tagged Sources; (3) never create new Sources for tasks — a Source is created only when a record matching a scoping-table unit is actually cited.
- **[minor] scoping** (Part A — Source scoping)
  - Fifteen zero-citation placeholder/task records stored as Sources are not "discrete navigable units": S0012 "Welcome to the GDA", S0013 "Naturalization and immigrant paperwork for Emma Söderström", S0014, S0037 "Check in on status of the St. Louis Co. marriage record case", S0039 "April Research Update", S0049 "Descendants of Grace Haack", S0056 "May Research Update", S0057, S0058 "Eidsvoll klokkerbøker" (which also overlaps S0015's unit), S0059, S0060, S0061, S0062, S0063, S0068. S0012/S0039/S0056 look like Gramps Web blog posts; the rest are research to-dos.
  - **Fix:** Keep genuine blog-post sources (S0012, S0039, S0056) tagged/segregated from the citation catalog; move the task notes (S0013, S0014, S0037, S0057–S0063, S0068) to research notes or a to-do list and delete the placeholder Sources; fold S0058 into S0015 or a properly scoped Eidsvoll volume source.
  - *Verifier adjustment:* Issue and rule check out — all 15 listed records verify as n_citations=0 placeholders/tasks that are not discrete navigable units (and the finding correctly excludes the legitimate zero-citation S0036 and S0067) — but the fix drops S0049 "Descendants of Grace Haack": it appears in the issue list yet in neither fix bucket (blog posts S0012/S0039/S0056; task notes S0013/S0014/S0037/S0057–S0063/S0068). Corrected fix: additionally disposition S0049 — fold it into the existing Grace Haack research source S0050 if it is her compiled report, otherwise delete it with the other placeholders.

### S0013 — Naturalization and immigrant paperwork for Emma Söderström
- **[minor] scoping** (Part A — Source scoping)
  - "Naturalization and immigrant paperwork for Emma Söderström" is a research To-Do ("Check U.S. District Court naturalization indexes for Minnesota..."), not a discrete navigable unit. It wraps genuine FUTURE sources — U.S. District Court naturalization indexes and Marshall County naturalization records, which B.3 scopes per court-collection — but the task itself is not a source and adds a garbage line under Part A Bibliography mapping.
  - **Fix:** Re-parent note N0030 (already type "To Do") to Emma Söderström's person record and delete the Source; when records are found, create one Source per court-collection per B.3 scoping.

### S0014 — Naturalization packet review for Peter Grund
- **[minor] scoping** (Part A — Source scoping)
  - "Naturalization packet review for Peter Grund" is a research To-Do ("Use the cited GID (247344:70800) to pull the exact naturalization index entry..."), not a source. It wraps genuine future court-collection naturalization Sources (Minnesota district court petition and declaration of intention) but itself matches no scoping unit and pollutes the bibliography.
  - **Fix:** Re-parent note N0031 as a To Do note on the ancestor Peter Grund's person record (the Ancestry GID stays in the note as working data) and delete the Source; create per-court-collection Sources when the packet is located.

### S0015 — Eidsvoll prestekontor Kirkebøker, Parish register (copy) no. I 2, 1866-1871
- **[major] · C0012 page** (B.2-analog B.1 §7 Citation page templates — Parish records; Part A — Subject formatting in the page string)
  - Page string is only "p. 57, no. 21" — it lacks the volume designator, the image number, and the required [name] [record-noun] subject that the parish-record template `[Original-or-copy designator] [vol], p. [P] (image [I]), [entry identifier], [subject]` prescribes.
  - **Fix:** Parish register (copy) I 2, p. 57 (image 62), no. 21, Thor Emil birth and baptism entry — the image number 62 comes from B.1 §12 Worked example 1, which documents this same volume and page; verify against Digitalarkivet before saving.
- **[major] pubinfo** (Part A — Pubinfo grammar; Part A — Two-forms-two-homes locator; B.1 §6 Pubinfo)
  - Pubinfo "Digital images, Digitalarkivet (https://www.digitalarkivet.no); citing Arkivverket (National Archives of Norway), Oslo, archive ref. AV/SAO-A-10888/G/Ga/L0002" appends a citing clause and duplicates the archive machine path, which belongs in Call number only; the grammar is strictly "[medium], [platform] (homepage URL)."
  - **Fix:** Digital images, Digitalarkivet (https://www.digitalarkivet.no).
- **[major] repository** (B.1 §2/§3 vs. the 2026 archive-law merger — DECISION NEEDED)
  - Naming conflict between the catalog and the written master: eight Norwegian sources (S0015, S0036, S0038, S0064, S0069, S0071, S0076, S0077) share repository R0009 "Nasjonalarkivet" — the unified agency name in force since 1 January 2026, when the new archive law merged Arkivverket, Riksarkivet and the statsarkivene. The master still prescribes the pre-merger names (bare "Riksarkivet", "Statsarkivet i Oslo") and its own §2 rationale — "we follow the current naming" — now argues against its written value. Real regardless of the decision: three author spellings across the six censuses, disagreeing FRN citing-clauses (C0080 vs C0041/C0079), and R0009 carrying the digitalarkivet.no platform URL.
  - **Fix:** Recommended: update house_style_master.md B.1 §2 (naming note), §3 (repository table), and the §11–§12 worked examples to Nasjonalarkivet — the single unified R0009 then stands as-is. Alternative: keep historical naming in the master and split R0009 by call-number prefix (Riksarkivet / Statsarkivet i Oslo / Statsarkivet i Kongsberg). Either way: one census author value, aligned FRN citing-clauses, platform URL off R0009.
  - *Verifier adjustment:* Issue and repository renames confirmed: 'Nasjonalarkivet' is not a real Norwegian archive, the decision tree names 'Statsarkivet i Oslo'/'Riksarkivet', and the SAO/SAKO/RA call-number prefixes support the proposed mapping (S0015 → Statsarkivet i Oslo; S0069 → Statsarkivet i Kongsberg; the six RA-prefixed → Riksarkivet), plus removing '(Nasjonalarkivet)' from S0064's pubinfo. But the fix is incomplete against its own issue statement: it must also rename the author fields — S0036 and S0076 author 'Nasjonalarkivet' → 'Riksarkivet' (matching siblings S0069/S0071/S0077 and S0001), and additionally S0038's author 'Nasjonalarkivet (Riksarkivet)' → 'Riksarkivet', which the finding missed.
- **[major] title** (Part A — Title philosophy; B.1 §4 Source title (Parish records))
  - Title "Eidsvoll prestekontor Kirkebøker, Parish register (copy) no. I 2, 1866-1871" is the old collection-led form the master explicitly replaces (§4 normalization note quotes this exact shape as the superseded form); it also uses a hyphen instead of an en dash in the year-range.
  - **Fix:** Norway, Akershus, Eidsvoll, parish registers, Parish register (copy) I 2, 1866–1871
- **[major] title** (Part A — Title philosophy)
  - Creating-body/collection-led titles remain on non-census Scandinavian sources: S0015 "Eidsvoll prestekontor Kirkebøker, Parish register (copy) no. I 2, 1866-1871" — the guide's transform table names this exact class (old "Eidsvoll prestekontor Kirkebøker..." → new "Norway, Akershus, Eidsvoll, parish registers, ..."); S0064 "Botsfengslet (Kristiania), Fangeprotokoll nr. 36 (1901-1902)"; S0065 "Københavns Politi, Politiets registerblade, Station 4".
  - **Fix:** S0015 → "Norway, Akershus, Eidsvoll, parish registers, Klokkerbok I 2, 1866–1871"; S0064 → "Norway, Kristiania, Botsfengslet, prison register (Fangeprotokoll) no. 36, 1901–1902"; S0065 → "Denmark, København, police registry cards (Politiets registerblade), Station 4".
- **[minor] abbrev** (B.1 §10 Abbrev rule)
  - Abbrev "Eidsvoll klokkerbok I 2, 1866-1871" uses a comma-separated year-range with a hyphen; §10 requires the parenthetical year-range with an en dash (example: "Eidsvoll klokkerbok I 2 (1866–1871)").
  - **Fix:** Eidsvoll klokkerbok I 2 (1866–1871)
- **[minor] · C0012 date** (Part A — Citation date)
  - Citation date field is set; the house style says the citation date is always left blank (the event date lives on the event, access date in the FRN, record-creation range in the Title).
  - **Fix:** Blank the citation date field.
- **[minor] · C0012 frn** (B.1 §12 Worked example 1 (bracketed English gloss, EE 2.28))
  - FRN in N0046 opens "Eidsvoll prestekontor Kirkebøker, parish register (copy) no. I 2" without the bracketed English gloss required on first use of a foreign series name in the FRN.
  - **Fix:** Eidsvoll prestekontor Kirkebøker [parish records], parish register (copy) no. I 2, 1866–1871, …
- **[minor] · C0012 frn** (B.1 §12 Worked example 1; Part A — Pubinfo grammar (medium vocabulary))
  - FRN uses "imaged, Digitalarkivet (…)" where the house form for the medium clause is "digital image, Digitalarkivet (…)" as in every B.1 worked example.
  - **Fix:** …; digital image, Digitalarkivet (https://urn.digitalarkivet.no/URN:NBN:no-a1450-kb20060313011115.jpg : accessed 17 April 2026); …
- **[minor] · C0012 frn** (B.1 §4 Source title (en dashes in year-ranges) and §12 worked examples)
  - Year-range "1866-1871" is written with a hyphen in both the FRN and SRN of N0046; the house style uses en dashes in year-ranges throughout.
  - **Fix:** 1866–1871 (en dash) in both the FRN and SRN.
- **[minor] note_type** (Part A — Citation notes structure)
  - Source-level note N0032 (type "Source Note") holds FIRST REFERENCE NOTE / SHORT REFERENCE NOTE / SOURCE LIST ENTRY blocks. Part A: source-level bibliographic notes are unnecessary (the Source fields carry this) and "legacy SOURCE LIST ENTRY blocks … can be deleted"; the FRN/SRN already exist at citation level (N0046). The embedded SLE also carries a deep URL (https://www.digitalarkivet.no/kb20060313011115), which never belongs on the Source.
  - **Fix:** Delete note N0032. Before deleting, move the two useful locators (indexed record https://www.digitalarkivet.no/en/view/255/pd00000004766218 and permalink https://urn.digitalarkivet.no/URN:NBN:no-a1450-kb20060313011115.jpg) into citation C0012's FRN if not already covered there.
- **[minor] note_type** (Part A — Citation notes structure)
  - Source-level note N0032 of type "Source Note" holds a full "FIRST REFERENCE NOTE: … SHORT REFERENCE NOTE: … SOURCE LIST ENTRY: …" block — citation prose plus a legacy SLE living at source level; Part A says source-level notes are not required, FRN/SRN belong in citation notes, and legacy SOURCE LIST ENTRY blocks can be deleted.
  - **Fix:** Delete N0032 after folding its unique content into C0012's Citation note: the parentage clause "son of Christian Thoresen and Indiana Marie Evensdatter Lerberg" into the FRN prose, and the indexed-record URL (https://www.digitalarkivet.no/en/view/255/pd00000004766218) as a "transcribed entry at …" clause; the SOURCE LIST ENTRY block is deletable outright.
- **[minor] pubinfo** (Part A — Pubinfo grammar; Part A — Two-forms-two-homes locator)
  - Digitalarkivet pubinfo drift: the six census sources use the canonical "Database with images, Digitalarkivet (https://www.digitalarkivet.no)." but S0015 appends "; citing Arkivverket (National Archives of Norway), Oslo, archive ref. AV/SAO-A-10888/G/Ga/L0002" — duplicating the machine path whose home is "Source Call number only" — and S0064 appends "; citing Arkivverket (Nasjonalarkivet), Oslo."
  - **Fix:** Trim S0015 and S0064 pubinfo to "Digital images, Digitalarkivet (https://www.digitalarkivet.no)."; the archive is named in Repository and the machine path stays only in Call number; any citing-prose belongs in the FRN.
- **[minor] · C0012 srn** (Part A — Citation notes structure (SRN is compact); B.1 §12 Worked example 1)
  - SRN "Eidsvoll prestekontor Kirkebøker, parish register (copy) no. I 2, 1866-1871, p. 57, no. 21, Thor Emil." repeats the full formal FRN heading instead of the compact klokkerbok short form, and the subject lacks its record-noun.
  - **Fix:** Eidsvoll klokkerbok I 2 (1866–1871), p. 57, no. 21, Thor Emil baptism entry.
- **[info] repository** (B.1 §2/§3 vs. the 2026 archive-law merger)
  - Repository "Nasjonalarkivet" conflicts with the pre-merger institution names the written master (B.1 §2/§3) prescribes for this volume's AV/… call-number prefix. Pending the Nasjonalarkivet naming decision (see the catalog-wide repository finding): on 1 January 2026 the new archive law merged Arkivverket, Riksarkivet and the statsarkivene into one agency, Nasjonalarkivet — so the master's pre-merger names are stale on its own "follow the current naming" rationale.
  - **Fix:** Recommended: update house_style_master.md B.1 §2/§3 and the §11–§12 worked examples to Nasjonalarkivet — this field then already conforms. Either way, remove the digitalarkivet.no platform URL from repository record R0009 (platform ≠ repository).

### S0016 — Unidentified newspaper, Williams or Baudette, Minnesota
- **[major] author** (B.3 §2 Source author)
  - Author "Mrs. Theo. R. Dopp" — newspapers are "(blank — newspapers are cited by title, not author)"; Mrs. Dopp is the obituary's byline author, which belongs in the FRN prose (where it already appears: "by Mrs. Theo. R. Dopp").
  - **Fix:** Leave Author blank
- **[minor] abbrev** (B.3 §10 Abbrev rule)
  - Abbrev "Unid. newspaper, obit. Karin Siggerud, 1952" uses aggressive abbreviations ("Unid.", "obit.") contrary to the whole-readable-words convention (record-type abbreviations are SRN-only, and "obit." is not even in the table), and names a single obituary — citation-level content — rather than identifying the source.
  - **Fix:** Unidentified newspaper, Williams or Baudette, Minn.
- **[minor] author** (Part 0 — Gramps field map)
  - Newspaper sources handled inconsistently: S0052 (Star Tribune) correctly leaves author blank per the field map ("Blank where the source is cited by title (periodicals, newspapers...)"), but S0016 carries author "Mrs. Theo. R. Dopp" — the obituary's byline, which belongs in the FRN, not the Source author.
  - **Fix:** Blank S0016's author field and credit Mrs. Theo. R. Dopp in the citation's First Reference Note as the item's author.
- **[minor] · C0013 date** (Part A — Citation date)
  - Citation date field is set; the house style says the citation date is always left blank (the event date lives on the event, access date in the FRN, record-creation range in the Title).
  - **Fix:** Blank the citation date field.
- **[minor] · C0013 page** (B.3 §7 Citation page templates; Part A — Subject formatting in the page string)
  - Page string is only the headline "\"Williams Woman Is Dead at Baudette at Great Age of 87\"" — no locators and no [name] [record-noun] subject; the obituary template is "[date], p. [N], col. [N], [Name] obituary" (the headline belongs in the FRN, where it already appears).
  - **Fix:** ca. May 1952, Karin (Halvorson) Siggerud obituary
- **[minor] pubinfo** (Part A — Pubinfo grammar)
  - Pubinfo "Ca. May 1952" is a date, not a publication/production statement; the issue date is a citation-level locator (it leads the newspaper page string and appears in the FRN), and no sanctioned Pubinfo form applies to a privately-held clipping of an unidentified paper.
  - **Fix:** Leave Pubinfo blank (issue date stays in the citation page string and FRN)
  - *Verifier adjustment:* Issue and blank-Pubinfo fix are correct (Part A Pubinfo grammar has no date-only form, and neither the platform form nor the imprint variant fits a privately-held clipping of an unidentified paper). But the fix's parenthetical is wrong about the record: C0013's page string is only the headline and does not carry the date — the issue date currently survives only in the FRN ('ca. May 1952'). Corrected fix: leave Pubinfo blank; the issue date remains in the FRN, and per §7's newspaper template the page string should lead with it (a separate page-string correction, not something that 'stays' there).
- **[info] · C0013 abstract** (Part A — Citation notes structure)
  - Abstract note N0109 contains only an analytical comment ("Marriage year printed as 1867 is almost certainly a typo for 1897.") rather than a paragraph summary, in your own words, of what the obituary contains.
  - **Fix:** Expand N0109 into a true abstract of the obituary (death at Baudette aged 87, residence at Williams, survivors, marriage as printed), retaining the 1867/1897 typo comment within it.

### S0017 — Chiesa cattolica, Parrocchia di Vistrorio (Torino), Baptismal register
- **[major] author** (Part 0 — Gramps field map (Source author row: creating body, "No country or umbrella prefix"))
  - Author "Chiesa cattolica, Parrocchia di Vistrorio (Torino)" carries the umbrella-body prefix "Chiesa cattolica," which the field map forbids; the creating body is the parish alone. The parish is also named differently from sister source S0033, whose title calls it "Parrocchia di San Bartolomeo".
  - **Fix:** Drop the umbrella prefix and use one canonical parish name on both sources, e.g. "Parrocchia di San Bartolomeo (Vistrorio, Torino)" if San Bartolomeo is the verified parish dedication, otherwise "Parrocchia di Vistrorio (Torino)" on both.
- **[major] call_number** (Part A — Two-forms-two-homes locator (Call number = the archive's machine reference only))
  - Call number "FamilySearch image group 007961680" is a platform identifier, not the holding archive's catalog reference; Part A restricts Call number to the archive machine path (its examples are NAD/NARA-style archive references), and the image group number already lives in the citation FRN parenthetical where platform identifiers belong.
  - **Fix:** Remove the FamilySearch image group number from Call number (it stays in the FRN) and enter the holding archive's own reference for the register (e.g. the Archivio di Stato di Torino fondo/serie designation), or leave Call number blank until that reference is known.
- **[major] repository** (Part A — Repository decision tree (step 1: name the physical archive that holds the original))
  - Repository R0011 "Parrocchia di Vistrorio (Torino)" conflicts with sister source S0033, which attaches the same filmed material (both sources claim image group 007961680) to R0021 "Archivio di Stato di Torino"; the C0036 FIRST REFERENCE NOTE also says FamilySearch is "citing Archivio di Stato di Torino". The same filmed register set cannot be physically held by two different institutions, so at least one repository name is wrong.
  - **Fix:** Verify the holding institution in the FamilySearch catalog entry for the image group; per the FRN evidence, repoint S0017 to R0021 "Archivio di Stato di Torino" (or, if the parish genuinely retains the originals, correct S0033 instead) — both sources must name the same, verified holder.
  - *Verifier adjustment:* The conflict is real and the rule citation is correct: both records claim image group 007961680 (S0017 call number 'FamilySearch image group 007961680', S0033 call number 'Image group number 007961680') yet name different repositories (R0011 parish vs R0021 Archivio di Stato di Torino), and C0036's FRN does say 'citing Archivio di Stato di Torino'. But the fix overreaches: given the image-count mismatch flagged in idx 7 (811 vs 617 images for the 'same' group), the erroneous datum may be one source's image-group attribution rather than a repository, in which case the two registers could legitimately have different physical holders. Corrected fix: verify each register's FamilySearch catalog entry independently and set each source's Repository to that register's verified physical holder (FRN evidence supports Archivio di Stato di Torino for S0033); unify the two repositories only if verification shows both registers are the same filmed unit with one holder — do not mandate 'both sources must name the same holder' up front.
- **[major] title** (Part A — Title philosophy)
  - Title "Chiesa cattolica, Parrocchia di Vistrorio (Torino), Baptismal register" is in the old creating-body-led form (umbrella church body, then parish, then record type) and carries no year-range. Part A requires EE locality-led titles, largest jurisdiction first, then series/type and identifier, then year-range, and explicitly says this "replaces the older collection-led (Scandinavian) and creating-body-led (US state-vital) title forms" — the same principle applies to every domain.
  - **Fix:** Italy, Piedmont, Turin, Vistrorio, parish registers, baptisms (Atti di Battesimo), [year-range] — determine the register's actual year-range from the FamilySearch image group / archive catalog and use an en-dash; keep the series-name language and gloss pattern identical to the corrected S0033 title.
- **[minor] · C0014 confidence** (Part A — Confidence)
  - Confidence is 4 (Very High), but the record was consulted as a digital image ("digital image, ... FamilySearch"), and Part A anchors "a digital image of an original" at High, reserving Very High for the original itself. It is also internally inconsistent: C0036, the same parish's registers on the same FamilySearch filming, is rated 3 (High).
  - **Fix:** Set confidence to 3 (High).
- **[minor] · C0014 date** (Part A — Citation date)
  - Citation date field is set; the house style says the citation date is always left blank (the event date lives on the event, access date in the FRN, record-creation range in the Title).
  - **Fix:** Blank the citation date field.
- **[minor] · C0014 frn** (Part 0 — Gramps field map (author: no country or umbrella prefix))
  - The FRN creator carries the umbrella prefix and names the parish differently from the sibling source: C0014 opens "Chiesa cattolica, Parrocchia di Vistrorio (Torino), baptismal register..." while C0036 opens "Parrocchia di San Bartolomeo (Vistrorio, Turin, Italy), Atti di Matrimonio...". Part 0 bans umbrella prefixes such as "Chiesa cattolica" for the creating body, and the same parish should be named one way across the group.
  - **Fix:** Adopt one canonical creator form without the umbrella prefix in both citations' FRN/SRN prose, e.g. "Parrocchia di San Bartolomeo (Vistrorio, Torino)".
  - *Verifier adjustment:* Issue is real — C0014's FRN opens "Chiesa cattolica, Parrocchia di Vistrorio (Torino)" and Part 0's field map does ban country/umbrella prefixes for the creating body — but the cited rule attaches to the EE 'Creating body / author' concept via the Source author field, and both sources violate it there directly (S0017 author = "Chiesa cattolica, Parrocchia di Vistrorio (Torino)"; S0033 author = "Chiesa cattolica. Parrocchia di Vistrorio (Torino)"). The fix as written is incomplete: strip "Chiesa cattolica" from both Sources' author fields as well as the FRN/SRN prose, and verify against the images which parish form is canonical (S0033's "Parrocchia di San Bartolomeo (Vistrorio…)" vs S0017's "Parrocchia di Vistrorio") before adopting one form group-wide.
- **[minor] · C0014 page** (Part A — Subject formatting in the page string)
  - Subject is inverted and lacks a record-noun: "Image 694 of 811, entry for Michele Iginio Giovanni Battista Castellano". The shared shape is [locators], [name] [record-noun]; "entry for [name]" reverses it and never says what kind of entry it is (the record-noun is what tells a future reader, from the page string alone, what document they are looking at).
  - **Fix:** image 694 of 811, Michele Iginio Giovanni Battista Castellano birth and baptism entry
- **[minor] pubinfo** (Part A — Pubinfo grammar ('[medium], [platform] (homepage URL).'; collection-specific identifiers belong in the FRN, never on the Source))
  - Pubinfo "Digital images, \"Vistrorio, Turin, Piedmont, Italy records,\" FamilySearch (https://www.familysearch.org), image group no. 007961680" carries a collection title and a trailing collection-specific identifier ("image group no. 007961680") for which the grammar has no slot, and lacks the terminal period; the grammar is medium + platform + homepage URL only, with collection-specific detail confined to the First Reference Note.
  - **Fix:** Digital images, FamilySearch (https://www.familysearch.org).
  - *Verifier adjustment:* Issue and fix are correct: the Pubinfo grammar is '[medium], [platform] (homepage URL).' with no slot for a collection title or a trailing identifier, and the terminal period is required (all Part A examples carry it). But the rule gloss misquotes the guide: the never-on-the-Source sentence covers collection-specific and image-specific URLs, not identifiers. The image-group number's sanctioned homes in this catalog are the FRN (C0014's FRN already says 'image group number 007961680') and the Call number field (R0011 link already holds 'FamilySearch image group 007961680'), so it does legitimately appear on the Source record — just not in Pubinfo. Corrected rule wording: 'Part A — Pubinfo grammar: [medium], [platform] (homepage URL). — grammar has no slot for a collection title or collection identifier; the identifier already lives in the FRN and Call number.' Fix stands as written.
- **[minor] pubinfo** (Part A — Pubinfo grammar)
  - FamilySearch pubinfo drift: canonical "Digital images, FamilySearch (https://www.familysearch.org)." on S0000/S0045/S0048, but S0017 embeds a collection name and image-group locator ("Digital images, \"Vistrorio, Turin, Piedmont, Italy records,\" FamilySearch (...), image group no. 007961680"), S0020 embeds collection name plus "citing Archives of the ELCA...", and S0033 is period-separated with no URL ("Digital images. \"Vistrorio, Turin, Piedmont, Italy records.\" FamilySearch.").
  - **Fix:** Normalize S0017, S0020, S0033 to "Digital images, FamilySearch (https://www.familysearch.org)." and move collection names, image-group numbers, and citing-clauses into the FRNs.
- **[minor] repository** (Part A — Repository decision tree)
  - Same Vistrorio parish registers (both citing FamilySearch image group 007961680) claim two different custodians: S0017 repo "Parrocchia di Vistrorio (Torino) [Archive]" vs S0033 repo "Archivio di Stato di Torino [Archive]". The parish is also named three ways across the pair: "Chiesa cattolica, Parrocchia di Vistrorio (Torino)" (S0017 author), "Chiesa cattolica. Parrocchia di Vistrorio (Torino)" (S0033 author, period-separated), "Parrocchia di San Bartolomeo (Vistrorio, Turin, Italy)" (S0033 title).
  - **Fix:** Determine the actual holder of the filmed originals and use the same repository on both sources; standardize one institution name (e.g. "Parrocchia di San Bartolomeo, Vistrorio") across author, title, and repo.
- **[info] abbrev** (Part 0 — Gramps field map (Source Abbrev row); no Italian chapter §10 exists — internal-consistency check under Part 0 Purpose ("the same predictable treatment"))
  - Abbrev "Vistrorio baptismal register" uses an English record noun with no comma, while sister source S0033 uses the Italian native form with a comma ("Vistrorio, Atti di Matrimonio") — the two Italian sources do not treat the abbrev form the same way.
  - **Fix:** Align both to one pattern, e.g. "Vistrorio, Atti di Battesimo" to match S0033 (or convert both to English record nouns) — pick one convention and apply it to both sources.
- **[info] · C0014 abstract** (Part A — Citation notes structure (Abstract / Transcription / Translation, encouraged for primary records))
  - Citation on an original (imaged) baptism record has a fact-rich FRN — "(born 11 January 1888), son of Bartolomeo Castellano and Maria Formento-Doot" — but no Abstract note; extracted facts belong in the Abstract, and this foreign-language entry also has no Transcription/Translation notes, which Part A specifically encourages for foreign-language material.
  - **Fix:** Add a note of type Abstract carrying the extracted facts (birth 11 January 1888, baptism 12 January 1888, parents' names); optionally add Transcription and Translation notes for the Italian/Latin entry; slim the FRN to identifying elements.
  - *Verifier adjustment:* The rule and record check out (Part A encourages Abstract/Transcription/Translation for primary records, expects Translation for non-English sources; C0014 has only the FRN/SRN note), and info severity fits an optional-but-encouraged element. But the guide nowhere says extracted facts 'belong in the Abstract' or that the FRN should be slimmed — EE-style FRN prose legitimately carries identifying facts like "(born 11 January 1888), son of…". Corrected fix: add Abstract (and optionally Transcription/Translation) notes; drop the 'slim the FRN to identifying elements' instruction.
- **[info] · C0014 frn** (Part A — Subject formatting in the page string (hyphenated-couple shorthand; guide otherwise silent — internal consistency))
  - The mother is rendered "Maria Formento-Doot" in C0014's FRN but "Formento Maria" in C0036 (her own marriage record); besides the factual mismatch, the hyphenated form risks being misread as the house couple-shorthand ("Castellano-Formento marriage") which reserves hyphenation for couples.
  - **Fix:** Verify the mother's name against the record images and render it identically in both citations (e.g. "Maria Formento" or, if the compound surname is genuine, the same compound form in both), preferably avoiding a bare hyphen form in subject positions.
  - *Verifier adjustment:* The name mismatch is real ("Maria Formento-Doot" in C0014's FRN vs "Formento Maria" in C0036) and should be verified and harmonized, but the cited couple-shorthand rule governs page-string subjects only — neither citation's page string contains the hyphenated form, FRN prose with a full given name cannot be misread as couple shorthand, and the guide does not reserve hyphens for couples. Corrected fix: verify the mother's surname against the record images and render the same form (compound-with-hyphen if genuine, e.g. Formento-Doot as a Piedmontese double surname) in both FRNs; drop the 'preferably avoiding a bare hyphen form' clause.
- **[info] scoping** (Part 0 — Front matter (Scope))
  - S0017 and S0033 are Italian parish records, and the house style's four Part B domains (Norwegian, Swedish, US, Published & Personal) cover none of them — there is no chapter supplying the title template, locator tokens, record-noun vocabulary, or per-record-type confidence for Italian parish registers, which is exactly where the two sources have drifted apart (English vs Italian series naming, leading vs trailing image locators, differing confidence).
  - **Fix:** Add a Part B.5 Italy chapter (modeled on EE 11.50's Italian foreign-language register template, which Part 0 already names as the closest EE pattern); until then, keep S0017 and S0033 mutually consistent under Part A.
- **[info] scoping** (Part 0 — Front matter (Scope))
  - Sources outside the four house domains (Norwegian, Swedish, US, Published & Personal): Italian parish records S0017, S0033 and Italian compiled transcription S0054; Danish police registry S0065 "Københavns Politi, Politiets registerblade, Station 4". No domain chapter governs their author/repository/page vocabulary.
  - **Fix:** Extend the house style (or add an appendix) covering Italian parish and Danish civil records, or explicitly assimilate them to the closest chapter's patterns so they stop drifting.
  - *Verifier adjustment:* Correct for S0017, S0033 (Italian parish registers) and S0065 (Danish police registerblade) — none fits the four scoped domains and no chapter governs them. But S0054 is wrongly included: Part B.4 Published & Personal explicitly covers 'other genealogists' research' with source-scoping 'per third-party-researcher compilation', which is exactly what Marisa Lova's published transcription is. Corrected issue/fix: drop S0054 from the list; extend or assimilate only for the Italian parish records (S0017, S0033) and the Danish civil record (S0065).

### S0018 — Applications for Headstones for U.S. Military Veterans, 1925-1941
- **[major] · C0053 frn** (Part A — Citation notes structure)
  - No FIRST REFERENCE NOTE / SHORT REFERENCE NOTE block (citation has no notes at all). FRN and SRN are required for every citation.
  - **Fix:** Compose the FRN/SRN per the domain chapter (bifrost's citation composer can draft it) and store in a Citation-type note.
- **[major] pubinfo** (Part A — Pubinfo grammar)
  - Pubinfo "Database with images, Ancestry, https://www.ancestry.com/search/collections/2375" carries a deep collection URL — the Source takes the platform homepage only, with collection URLs in the FRN — and lacks the parenthesized-URL/period form; worked example 6 for this exact series uses medium `Digital images`.
  - **Fix:** Digital images, Ancestry (https://www.ancestry.com).
- **[minor] abbrev** (Part 0 — Gramps field map; domain §10)
  - Source has no Abbrev; every real source needs the short identifier for Gramps source-list views.
  - **Fix:** Add the domain §10-form abbrev.
- **[minor] author** (B.3 §2 Source author)
  - Author "War Department, Office of the Quartermaster General" carries an umbrella prefix; the prescribed value for headstone applications is the bare body name `Office of the Quartermaster General` ("Use the bare body name… no country or umbrella prefix").
  - **Fix:** Office of the Quartermaster General
- **[minor] call_number** (B.3 §5 Locator / volume notation tokens)
  - Call number is empty; for NARA records the Call number holds the publication/record-group identifier, and worked example 6 for this exact series prescribes `RG 92`.
  - **Fix:** RG 92
- **[minor] · C0053 page** (B.3 §7 Citation page templates)
  - Page string "entry for Axel O. Grund" does not follow the headstone-application template "Application for [Name] (d. [year])".
  - **Fix:** Application for Axel O. Grund (d. 1948)
- **[minor] title** (B.3 §4 Source title)
  - Year range "1925-1941" uses a hyphen; the template writes `Applications for Headstones for U.S. Military Veterans, 1925–1941` with an en dash.
  - **Fix:** Applications for Headstones for U.S. Military Veterans, 1925–1941

### S0019 — Find a Grave, database with images
- **[major] · C0016 page** (Part A — Two-forms-two-homes locator (hard rule 2); B.3 §7 Citation page templates; B.3 §10 State abbreviations)
  - Page string "Memorial 153349341, \"Ida Marie Siggerud Beauchamp\" (1904-1965), Elm Park Cemetery, Baudette, Lake of the Woods Co., MN" carries place names in the page string, uses the banned USPS code "MN", omits "no." after Memorial, and quotes the name with a life-dates parenthetical that matches no sanctioned parenthetical category.
  - **Fix:** Memorial no. 153349341, Ida Marie Siggerud Beauchamp — with the cemetery identity carried by the per-cemetery Source title.
- **[major] · C0017 page** (Part A — Two-forms-two-homes locator (hard rule 2); B.3 §7 Citation page templates; B.3 §10 State abbreviations)
  - Page string "Memorial 134903199, \"Karin Siggerud\" (1864-1952), Pine Hill Cemetery, Williams, Lake of the Woods Co., MN" carries place names in the page string, uses the banned USPS code "MN", and omits "no." after Memorial.
  - **Fix:** Memorial no. 134903199, Karin Siggerud — with the cemetery identity carried by the per-cemetery Source title.
- **[major] repository** (B.3 §3 Repository)
  - Repository "Find a Grave" (R0012, type Web site) is platform-as-repository; "Find a Grave and other online-only platforms are publishers, not repositories… (This changes the earlier US convention that named Find a Grave in Repository.)"
  - **Fix:** Remove the repository link; leave Repository blank (Find a Grave goes in Pubinfo as publisher)
- **[major] repository** (Part A — Repository decision tree)
  - Online-only platforms recorded as repositories: S0019 has repo "Find a Grave [Web site]" despite the explicit rule "Find a Grave and other online-only platforms are publishers, not repositories"; S0005 has repo "Minnesota Association of County Officers [Association]" for the online MOMS database (MACO is the platform publisher, not a holding institution).
  - **Fix:** Blank the Repository on S0019 and S0005; carry the platform in Pubinfo instead ("Database with images, Find a Grave (https://www.findagrave.com)." / "Database, Minnesota Official Marriage System (https://moms.mn.gov).").
- **[major] scoping** (B.3 §1 Scope & record types covered)
  - One flat Find a Grave Source covers memorials in two cemeteries (C0016: Elm Park Cemetery, Baudette; C0017: Pine Hill Cemetery, Williams); the house style explicitly supersedes EE 11.42's single-Source treatment — "Find a Grave is scoped one Source per cemetery."
  - **Fix:** Split into two Sources — one for Elm Park Cemetery (Baudette) and one for Pine Hill Cemetery (Williams), Lake of the Woods County — and reattach C0016/C0017 accordingly
- **[major] scoping** (B.3 §1 Scope & record types covered)
  - Source "Find a Grave, database with images" is the superseded platform-wide EE 11.42 scoping; the house style explicitly scopes one Source per cemetery, and this flat scope is what forces cemetery and place names into both citations' page strings.
  - **Fix:** Split into per-cemetery Sources — "Minnesota, Lake of the Woods County, Elm Park Cemetery, Find a Grave Memorials" (for C0016) and "Minnesota, Lake of the Woods County, Pine Hill Cemetery, Find a Grave Memorials" (for C0017) — and reattach the citations.
- **[major] scoping** (Part A — Source scoping)
  - S0019 "Find a Grave, database with images" is one flat Find a Grave source whose citations span two cemeteries (C0016 Elm Park Cemetery, Baudette; C0017 Pine Hill Cemetery, Williams). The house style explicitly rejects EE 11.42's one-source-for-all approach: "this house style instead scopes one Source per cemetery." The title also embeds the medium ("database with images") and pubinfo uses the bibliography access-year form "https://www.findagrave.com : 2026" instead of Pubinfo grammar.
  - **Fix:** Split into two per-cemetery sources, e.g. "Minnesota, Lake of the Woods County, Baudette, Elm Park Cemetery, Find a Grave memorials" and "Minnesota, Lake of the Woods County, Williams, Pine Hill Cemetery, Find a Grave memorials"; pubinfo "Database with images, Find a Grave (https://www.findagrave.com)."; repo blank; reassign C0016/C0017 accordingly.
- **[major] title** (B.3 §4 Source title)
  - Title "Find a Grave, database with images" is the old EE-flat form; the template is `[State], [county], [cemetery], Find a Grave Memorials` (locality-led, per Part A Title philosophy).
  - **Fix:** Minnesota, Lake of the Woods County, Elm Park Cemetery, Find a Grave Memorials (and, after the scoping split, Minnesota, Lake of the Woods County, Pine Hill Cemetery, Find a Grave Memorials)
- **[minor] abbrev** (B.3 §10 Abbrev rule)
  - Abbrev "Find a Grave" identifies the platform, not the cemetery-scoped source; worked example 4's pattern is `Forest Hill, Duluth, FAG`.
  - **Fix:** Elm Park, Baudette, FAG (and Pine Hill, Williams, FAG for the second post-split Source)
- **[minor] · C0016 date** (Part A — Citation date)
  - Citation date field is set; the house style says the citation date is always left blank (the event date lives on the event, access date in the FRN, record-creation range in the Title).
  - **Fix:** Blank the citation date field.
- **[minor] · C0017 date** (Part A — Citation date)
  - Citation date field is set; the house style says the citation date is always left blank (the event date lives on the event, access date in the FRN, record-creation range in the Title).
  - **Fix:** Blank the citation date field.
- **[minor] · C0016 frn** (B.3 §12 Worked example 4; B.3 §10 Abbrev rule (FAG))
  - FRN uses the old platform-led EE 11.42 form ("Find a Grave, database with images (URL…), \"Ida Marie Siggerud Beauchamp\" (1904-1965) memorial; citing Elm Park Cemetery…") and omits the marker-photograph credit; SRN "Find a Grave, \"Ida Marie Siggerud Beauchamp\" (1904-1965), Elm Park Cemetery, Baudette, Minnesota." is not compressed with "FAG".
  - **Fix:** FRN: "Find a Grave, memorial no. 153349341, Ida Marie Siggerud Beauchamp (1904–1965), Elm Park Cemetery, Baudette, Lake of the Woods County, Minnesota; database with images, Find a Grave (https://www.findagrave.com/memorial/153349341/ida-marie-beauchamp : accessed 16 April 2026); marker photograph by [contributor], [date]." SRN: "FAG memorial 153349341, Ida Marie Siggerud Beauchamp, Elm Park Cemetery."
  - *Verifier adjustment:* FRN form and SRN compression defects are real: the FRN uses the superseded platform-led EE 11.42 shape instead of the memorial-no-led worked-example-4 form, and the SRN must compress to 'FAG memorial 153349341, Ida Marie Siggerud Beauchamp, Elm Park Cemetery.' per §10. However, the proposed FRN unconditionally adds 'marker photograph by [contributor], [date]' — worked example 4's commentary contemplates photo-less memorials (Low, typed data only), and whether this memorial has a marker photograph is unverified (the citation currently sits at Low; see the companion confidence finding). Corrected fix: recast the FRN to the worked-example-4 shape (memorial no., name with life dates, cemetery/city/county/state prose, then database-with-images URL clause with access date), appending the marker-photograph credit only if verification confirms a marker photo.
- **[minor] · C0017 frn** (B.3 §12 Worked example 4; B.3 §10 Abbrev rule (FAG))
  - FRN uses the old platform-led EE 11.42 form and omits the marker-photograph credit; SRN "Find a Grave, \"Karin Siggerud\" (1864-1952), Pine Hill Cemetery, Williams, Minnesota." is not compressed with "FAG".
  - **Fix:** FRN: "Find a Grave, memorial no. 134903199, Karin Siggerud (1864–1952), Pine Hill Cemetery, Williams, Lake of the Woods County, Minnesota; database with images, Find a Grave (https://www.findagrave.com/memorial/134903199/karin-siggerud : accessed 16 April 2026); marker photograph by [contributor], [date]." SRN: "FAG memorial 134903199, Karin Siggerud, Pine Hill Cemetery."
  - *Verifier adjustment:* FRN form and SRN compression defects are real: platform-led FRN violates the worked-example-4 house form, and the SRN must compress to 'FAG memorial 134903199, Karin Siggerud, Pine Hill Cemetery.' per §10. But the proposed fix unconditionally adds the marker-photograph credit, which the style attaches only to memorials that actually include a marker photo — unverified here (citation is at Low, the no-photo level). Corrected fix: recast FRN to the worked-example-4 shape and append 'marker photograph by [contributor], [date]' only if verification confirms a marker photograph exists.
- **[minor] pubinfo** (Part A — Pubinfo grammar)
  - Pubinfo "https://www.findagrave.com : 2026" is the bibliography access-year form, not the Source Pubinfo grammar — it omits the medium and platform name and appends ": 2026", which belongs only to the generated Source List Entry.
  - **Fix:** Database with images, Find a Grave (https://www.findagrave.com).
- **[info] · C0016 confidence** (B.3 §8 Confidence guidance (per record type))
  - C0016 and C0017 are both 1 (Low), the no-photograph level, yet each has an attached media object (n_media=1); §8 prescribes High when the memorial includes a marker photograph.
  - **Fix:** Verify whether the attached images are marker photographs; if so, raise both citations to 3 (High) and credit the photographer in the FRN.

### S0020 — First Lutheran Church (Brainerd, Crow Wing County, Minnesota), Baptismal register
- **[major] call_number** (Part 0 — Gramps field map (Source Call number))
  - S0020 (First Lutheran Church, Brainerd — ELCA films M97/E-97) carries "FamilySearch image group 007961680" in its call number — but 007961680 is the Vistrorio, Italy image group used on S0017/S0033. This is stray wrong content, almost certainly a copy-paste from the Italian sources.
  - **Fix:** Delete "FamilySearch image group 007961680" from S0020's call number, leaving "ELCA film M97; SSIRC film E-97" (and move any FamilySearch access detail for the Brainerd records to the FRN).
- **[major] pubinfo** (B.3 §6 Pubinfo)
  - Pubinfo "Digital images, \"U.S., Evangelical Lutheran Church in America, Swedish American Church Records, 1800-1947,\" FamilySearch (https://www.familysearch.org); citing Archives of the ELCA…, ELCA film M97 (SSIRC film E-97)" embeds the named digitized collection (which "goes in the FRN, not Pubinfo") plus a citing-clause duplicating Repository/Call number; it also names FamilySearch while the Source's only citation (C0018) was accessed on Ancestry — Part A's tiebreak 3 says use the platform the citations actually use.
  - **Fix:** Digital images, Ancestry (https://www.ancestry.com).
- **[major] title** (B.3 §4 Source title)
  - Title "First Lutheran Church (Brainerd, Crow Wing County, Minnesota), Baptismal register" is creating-body-led; the church-records template is locality-led `[State], [county], [town], [Church name] records`, and the specific register is citation-level (it leads the page string per §7, e.g. `baptism register, p. …`).
  - **Fix:** Minnesota, Crow Wing County, Brainerd, First Lutheran Church records (move "baptismal register" into the citation page string)
- **[major] title** (Part A — Title philosophy)
  - US church-record titles in the old creating-body-led parenthetical form: S0020 "First Lutheran Church (Brainerd, Crow Wing County, Minnesota), Baptismal register" and S0024 "Bethesda Lutheran Church (Moorhead, Minnesota), Marriage register", while S0003 "Minnesota, Marshall County, Warren, First Lutheran Church records, 1883-1952" already uses the correct locality-led form. The Italian pair S0017/S0033 uses the same superseded parenthetical pattern.
  - **Fix:** S0020 → "Minnesota, Crow Wing County, Brainerd, First Lutheran Church baptismal register"; S0024 → "Minnesota, Clay County, Moorhead, Bethesda Lutheran Church marriage register"; apply the same locality-led transform to S0017/S0033 (e.g. "Italy, Piedmont, Torino, Vistrorio, Parrocchia di San Bartolomeo, baptismal register").
- **[minor] author** (B.3 §2 Source author)
  - Author "First Lutheran Church (Brainerd, Minnesota)" uses a parenthetical place and state; the prescribed form is `[Church name], [town]` (e.g. `First Lutheran Church, Warren`).
  - **Fix:** First Lutheran Church, Brainerd
- **[minor] call_number** (B.3 §5 Locator / volume notation tokens)
  - Call number "ELCA film M97; SSIRC film E-97; FamilySearch image group 007961680" is not "the holding archive's reference" and nothing else: the FamilySearch image group is a platform ID ("The platform's collection ID… is not a call number; it appears only in the FRN's digital-access clause"), and the SSIRC cross-reference belongs in FRN prose since the Repository is the ELCA Archives.
  - **Fix:** ELCA film M97 (keep "SSIRC film E-97" and the FamilySearch image group inside the FRN only)
- **[minor] · C0018 confidence** (B.3 §8 Confidence guidance (per record type); Part A — One citation vs. two)
  - Confidence is 3 (High); §8 prescribes Very High for a baptism recorded contemporaneously by the pastor in an original register, while the birth date the entry reports (18 December 1898, sixteen years before the 1915 baptism) is secondhand and Normal — evidence qualities differ, so they must not share one appraisal.
  - **Fix:** Set this citation to 4 (Very High) for the baptism event; create a separate citation at 2 (Normal) with an evidence-quality flag for the 1898 birth date.
- **[minor] · C0018 date** (Part A — Citation date)
  - Citation date field is set; the house style says the citation date is always left blank (the event date lives on the event, access date in the FRN, record-creation range in the Title).
  - **Fix:** Blank the citation date field.
- **[minor] · C0018 frn** (Part A — Citation notes structure; B.3 §12 Worked example 11)
  - FRN embeds extracted facts "(born 18 December 1898, baptized age 16)" which belong in the Abstract note, spells the name "Marrie Edna Siggerud" (page and SRN spell "Marie" — mark [sic] if the register itself reads Marrie), and lacks the p./image locator that the house church-record FRN carries.
  - **Fix:** First Lutheran Church (Brainerd, Crow Wing County, Minnesota), baptismal register, p. [P] (image [I]), baptism of Marie Edna Siggerud, 20 June 1915; digital image, Ancestry (… : accessed 15 April 2026), "U.S., Evangelical Lutheran Church in America, Swedish American Church Records, 1800–1952"; citing Archives of the Evangelical Lutheran Church in America, Elk Grove Village, Illinois, ELCA film M97 (SSIRC film E-97) — with the birth date and age moved to an Abstract note.
- **[minor] · C0018 frn** (Part A — Pubinfo grammar (tiebreaks); B.3 §6 Pubinfo)
  - FRN pairs the collection title "U.S., Evangelical Lutheran Church in America, Swedish American Church Records, 1800-1947" with Ancestry (dbid=61584), but 1800-1947 is the FamilySearch edition named in the Source Pubinfo — Ancestry collection 61584 is titled "…, 1800–1952"; the citation also accesses Ancestry while the Source Pubinfo names FamilySearch (Part A tiebreak: use the platform the citations actually use).
  - **Fix:** In the FRN cite the Ancestry collection under its own title, "U.S., Evangelical Lutheran Church in America, Swedish American Church Records, 1800–1952" (and have the source auditor align Pubinfo to Ancestry).
- **[minor] · C0018 page** (B.3 §7 Citation page templates (church records); Part A — Parenthetical annotations)
  - Page string "Entry for Marie Edna Siggerud (b. 18 Dec 1898, bapt. 20 Jun 1915)" has no register/page/image locators, no record-noun, and a parenthetical carrying full dates — the sanctioned disambiguator form is year-only "(b. 1898)"; it is also inconsistent with the church-record locator style used on S0003/C0004 ("p. 283 (image 496), …") for the same digitized series.
  - **Fix:** baptismal register, p. [P] (image [I]), Marie Edna Siggerud baptism entry
- **[minor] · C0018 srn** (B.3 §10 State abbreviations; B.3 §12 Worked example 11)
  - SRN "First Lutheran Church (Brainerd, Minnesota), baptismal register, 20 June 1915, Marie Edna Siggerud; Ancestry, \"Swedish American Church Records.\"" spells out "Minnesota" instead of the traditional "Minn." and carries a platform clause beyond the compact house form.
  - **Fix:** First Lutheran Church (Brainerd, Minn.), baptismal register, 20 June 1915, Marie Edna Siggerud, p. [P].
- **[info] · C0018 abstract** (Part A — Citation notes structure)
  - This is an original primary church register with a fact-rich FRN (birth date, baptism age) but the citation has no Abstract note.
  - **Fix:** Add a note of type Abstract summarizing the baptism entry (child, parents if named, birth 18 December 1898, baptism 20 June 1915 at age 16).

### S0021 — Ada County, Idaho, Marriage Records
- **[major] · C0022 page** (Part A — Two-forms-two-homes locator (hard rule 2); B.3 §7 Citation page templates)
  - Page string "John Edwin Grund and Marie Edna Siggerund, 26 August 1922, Ada County, Idaho" carries a place name ("Ada County, Idaho") in the page string, has no leading locator, duplicates the event date, and uses full names instead of couple shorthand + record-noun.
  - **Fix:** [License/vol. and p. or record no.], Grund-Siggerund marriage
- **[major] repository** (B.3 §3 Repository)
  - Repository "Ada County Recorder, Boise, Idaho" is not an institution form the chapter prescribes (`[County] County Courthouse` for locally-held county records, or `Family History Library` "when a physical microfilm number applies"), and it is inconsistent with the attached call number, which is FHL's machine reference ("FHL film 1509771").
  - **Fix:** Family History Library (keeping call number `FHL film 1509771`); alternatively `Ada County Courthouse` if citing the original register, in which case the FHL film reference moves to the FRN
- **[major] title** (Part A — Title philosophy)
  - Title "Ada County, Idaho, Marriage Records" leads with the county; the locality-led form puts the largest jurisdiction first with a lowercase series and year-range (cf. B.3 §4 vitals pattern `[State], [record series], [year-range]`).
  - **Fix:** Idaho, Ada County, marriage records, [year-range] (use the county series' own range if known)
- **[minor] author** (B.3 §2 Source author)
  - Author "Ada County, Idaho" is a jurisdiction, not a creating body; county vital records take `[County] County Clerk` or `[County] County Recorder`.
  - **Fix:** Ada County Recorder
- **[minor] · C0022 date** (Part A — Citation date)
  - Citation date field is set; the house style says the citation date is always left blank (the event date lives on the event, access date in the FRN, record-creation range in the Title).
  - **Fix:** Blank the citation date field.
- **[minor] · C0022 frn** (Part A — Two-forms-two-homes locator (hard rule 1); Part A — Citation notes structure)
  - FRN places the opaque waypoint identifiers outside the URL parenthetical — "(https://www.ancestry.com/search/collections/61379/ : accessed 17 April 2026) > 4533338 > image 591 of 811" — such IDs belong only inside the FRN's URL parenthetical; the medium "imaged," also deviates from the house "digital image,".
  - **Fix:** …; digital image, "Idaho, U.S., County Marriages, 1864-1950," Ancestry (https://www.ancestry.com/search/collections/61379/, image group 4533338, image 591 of 811 : accessed 17 April 2026); citing FHL film 1509771.
- **[minor] pubinfo** (Part A — Pubinfo grammar)
  - Pubinfo "Imaged as \"Idaho, U.S., County Marriages, 1864-1950,\" Ancestry (https://www.ancestry.com); citing FHL film 1509771" — "Imaged as" is not a sanctioned medium, the named platform collection belongs in the FRN (not Pubinfo), and "citing FHL film 1509771" duplicates the Call number.
  - **Fix:** Digital images, Ancestry (https://www.ancestry.com).

### S0022 — Minnesota Statewide Divorce Index, 1970-1995
- **[major] · C0024 page** (Part A — Two-forms-two-homes locator (hard rule 2); Part A — Subject formatting in the page string)
  - Page string "Marie E Prada and Marion Prada, 10 August 1981, St. Louis County" carries a place name ("St. Louis County") in the page string, duplicates the event date, and lacks the couple-shorthand subject with record-noun.
  - **Fix:** Prada-Prada divorce entry
- **[major] pubinfo** (Part A — Pubinfo grammar)
  - Pubinfo "Database, Ancestry (https://www.ancestry.com/search/collections/1081/); citing Minnesota Department of Health, St. Paul, Minnesota" carries a deep collection URL (homepage only on the Source; collection URLs go in the FRN) and a citing-clause that belongs in the FRN.
  - **Fix:** Database, Ancestry (https://www.ancestry.com).
- **[major] repository** (B.3 §3 Repository)
  - Repository "Minnesota Department of Health" (R0016) is the creating agency, not an institution the chapter prescribes as a repository; the source is an index-only Ancestry database, so Repository should be blank (the MDH attribution already lives in Author and in the FRN's "citing Minnesota Department of Health, St. Paul").
  - **Fix:** Remove the repository link; leave Repository blank
- **[minor] abbrev** (B.3 §10 Abbrev rule — State abbreviations)
  - Abbrev "MN Divorce Index, 1970-1995" uses the USPS two-letter code "MN" (the style uses traditional forms, "never USPS two-letter codes") and a hyphenated year range.
  - **Fix:** Minn. divorce index, 1970–1995
- **[minor] · C0024 confidence** (Part A — Confidence)
  - Confidence is 3 (High) but the Minnesota Statewide Divorce Index is an index-only database (Pubinfo "Database", no images); Part A anchors "compiled databases without source images" at Low.
  - **Fix:** Set confidence to 1 (Low).
- **[minor] · C0024 date** (Part A — Citation date)
  - Citation date field is set; the house style says the citation date is always left blank (the event date lives on the event, access date in the FRN, record-creation range in the Title).
  - **Fix:** Blank the citation date field.
- **[minor] title** (Part A — Title philosophy)
  - Year range "1970-1995" uses a hyphen; house year-ranges use an en dash. (Database-title-led form is acceptable for an online-only index database per Part A Bibliography mapping, so only the dash needs fixing.)
  - **Fix:** Minnesota Statewide Divorce Index, 1970–1995

### S0023 — 1920 U.S. Census, Beltrami County, Minnesota
- **[major] call_number** (B.3 §5 Locator / volume notation tokens)
  - Call number is "T625, roll 823" — the roll number is citation-level, not source-level ("the Call number is the publication identifier alone"; a county Source can span multiple rolls). Roll 823 already lives in the citation page string and FRN.
  - **Fix:** T625
  - *Verifier adjustment:* Issue is real and rule/fix are correct (§5: Call number is the publication identifier alone; fix 'T625'), but the claim that roll 823 'already lives in the citation page string and FRN' is wrong on the record: C0025's page string ('Myhre, Beltrami Co., MN, ED 22, sheet 11A, lines 13-18, Thomas E Siggerud household') carries no roll number — roll 823 appears only in the FRN's citing clause. Corrected wording: 'Roll 823 is citation-level and already lives in the FRN; note the page string itself is missing the roll (a separate §7 defect).'
- **[major] pubinfo** (Part A — Pubinfo grammar)
  - Pubinfo is a legacy citing-clause form: "Imaged as \"1920 United States Federal Census,\" Ancestry; citing NARA microfilm publication T625, roll 823". The named collection, the citing clause, and the roll number all belong in the FRN / page string, not on the Source; Pubinfo must be "[medium], [platform] (homepage URL)."
  - **Fix:** Digital images, Ancestry (https://www.ancestry.com).
- **[minor] abbrev** (B.3 §10 Abbrev rule — State abbreviations)
  - Abbrev "1920 Census, Beltrami Co., MN" uses the USPS two-letter code "MN" (house style: never USPS codes, use "Minn.") and inverts the worked-example order "St. Louis Co., Minn., 1920 census".
  - **Fix:** Beltrami Co., Minn., 1920 census
- **[minor] · C0025 date** (Part A — Citation date)
  - Citation date field is set; the house style says the citation date is always left blank (the event date lives on the event, access date in the FRN, record-creation range in the Title).
  - **Fix:** Blank the citation date field.
- **[minor] · C0025 frn** (B.3 §12 Worked example 1: a federal census)
  - FRN drifts from the worked-example form: it omits "population schedule"; uses "imaged, \"1920 United States Federal Census,\" Ancestry" instead of "digital image, Ancestry"; keeps "lines 13-18" instead of dwelling/family; and writes "NARA microfilm publication" instead of "National Archives microfilm publication".
  - **Fix:** 1920 U.S. census, Beltrami County, Minnesota, population schedule, Myhre, enumeration district (ED) 22, sheet 11A, dwelling [N], family [N], Thomas E Siggerud household; digital image, Ancestry (https://search.ancestry.com/cgi-bin/sse.dll?indiv=1&dbid=6061&h=26442259 : accessed 17 April 2026); citing National Archives microfilm publication T625, roll 823.
- **[minor] · C0025 page** (B.3 §7 Citation page templates (Federal census))
  - Page string "Myhre, Beltrami Co., MN, ED 22, sheet 11A, lines 13-18, Thomas E Siggerud household" is in an old non-template form: it leads with place/county/state (the federal-census template has no place tokens — place belongs in the FRN prose and on the event; "MN" is also a USPS code), lacks the roll/dwelling/family tokens, and uses "lines 13-18" where the template prescribes dwelling and family. Inconsistent with sibling federal-census citations C0076/C0077, which follow the template.
  - **Fix:** roll 823, ED 22, sheet 11A, dwelling [N], family [N], Thomas E Siggerud household
- **[minor] · C0025 srn** (B.3 §10 Abbrev rule — State abbreviations (traditional pre-USPS form))
  - SRN "1920 U.S. census, Beltrami Co., MN, Myhre, ED 22, sheet 11A, Thomas E Siggerud." uses USPS "MN" (the style says never USPS two-letter codes), omits "pop. sched.", and drops the record-noun "household" (cf. Worked example 1 SRN).
  - **Fix:** 1920 U.S. census, Beltrami Co., Minn., pop. sched., Myhre, ED 22, sheet 11A, Thomas E Siggerud household.
- **[minor] title** (B.3 §4 Source title)
  - Title reads "1920 U.S. Census, Beltrami County, Minnesota" — omits "Federal"; the federal-census template is "[year] U.S. Federal Census, [county] County, [state]" (cf. conformant S0074/S0075).
  - **Fix:** 1920 U.S. Federal Census, Beltrami County, Minnesota

### S0024 — Bethesda Lutheran Church (Moorhead, Minnesota), Marriage register
- **[major] pubinfo** (B.3 §6 Pubinfo)
  - Pubinfo reads "Imaged as \"U.S., Evangelical Lutheran Church in America, Swedish American Church Records, 1800-1952,\" Ancestry, https://www.ancestry.com" — the named digitized collection "goes in the FRN, not Pubinfo", and the form must be "Digital images, [Platform] (homepage URL)."
  - **Fix:** Digital images, Ancestry (https://www.ancestry.com).
- **[major] repository** (B.3 §3 Repository)
  - Repository is "Archives of the Evangelical Lutheran Church in America", but the chapter prescribes "the Swenson Swedish Immigration Research Center, Augustana College, for ELCA Swedish-American records" — this source is exactly that Ancestry collection, and the citation's own FRN cites "(SSIRC film S-289)", i.e. a Swenson film.
  - **Fix:** Swenson Swedish Immigration Research Center
- **[major] title** (Part A — Title philosophy)
  - Title "Bethesda Lutheran Church (Moorhead, Minnesota), Marriage register" is the old creating-body-led form; church records take the locality-led template "[State], [county], [town], [Church name] records" (B.3 §4), largest jurisdiction first.
  - **Fix:** Minnesota, Clay County, Moorhead, Bethesda Lutheran Church records
- **[minor] abbrev** (B.3 §10 Abbrev rule — Church (congregational) records)
  - Abbrev "Bethesda Luth. Church, Moorhead, marriage register" abbreviates "Luth." (US Abbrev keeps whole readable words), omits the state abbreviation, and says "marriage register" instead of "records"; the prescribed form is "[Church], [town], [state abbr.], records[, year-range]".
  - **Fix:** Bethesda Lutheran Church, Moorhead, Minn., records
- **[minor] author** (B.3 §2 Source author)
  - Author is "Bethesda Lutheran Church"; the church-records author form is "[Church name], [town]" (e.g. "First Lutheran Church, Warren").
  - **Fix:** Bethesda Lutheran Church, Moorhead
- **[minor] call_number** (B.3 §5 Locator / volume notation tokens)
  - Call number "ELCA film S288-289" is the other institution's film reference; with Swenson as repository, "the Call number is the holding archive's reference" — the FRN identifies it as "SSIRC film S-289". The ELCA film cross-reference stays in the FRN prose.
  - **Fix:** S-289
- **[minor] · C0026 confidence** (B.3 §8 Confidence guidance (Church records))
  - Confidence is High (3), but §8 prescribes "Very High for the recorded event ... recorded contemporaneously by the pastor in an original register — a digital image of the original register is still an original source carrying primary, direct evidence" for a church marriage entry.
  - **Fix:** Set confidence to 4 (Very High) for the marriage event
- **[minor] · C0026 frn** (B.3 §12 Worked example 11: a church (congregational) record)
  - FRN uses "imaged, \"U.S., Evangelical Lutheran Church in America, Swedish American Church Records, 1800-1952,\" Ancestry (URL : accessed ...)" — the model form is "digital image, Ancestry (URL : accessed date), \"[collection]\"" with the quoted collection name after the URL parenthetical; the FRN also gives no p./image locator and no marriage date to identify the entry.
  - **Fix:** Bethesda Lutheran Church (Moorhead, Clay County, Minnesota), marriage register, p. [P] (image [I]), marriage of Thomas Siggerud and Kari Halvorson, [date]; digital image, Ancestry (https://www.ancestry.com/imageviewer/collections/61584/images/48258_555132-00932 : accessed 19 April 2026), "U.S., Evangelical Lutheran Church in America, Swedish American Church Records, 1800-1952"; citing Archives of the Evangelical Lutheran Church in America, ELCA film S288-289 (SSIRC film S-289).
- **[minor] · C0026 page** (B.3 §7 Citation page templates (Church records))
  - Page string "Thomas Siggerud and Kari Halvorson marriage entry" carries no locators at all — the church template is "[register/volume], p. [P] (image [I]), [subject]" and no page/image number appears in the page string, FRN, or SRN. The couple should also use the hyphenated shorthand rather than "and" (Part A, Subject formatting in the page string; §9 "[Surname]-[Surname] marriage").
  - **Fix:** marriage register, p. [P] (image [I]), Siggerud-Halvorson marriage entry — capture the page/image from the Ancestry image and carry "p. [P]" into the FRN and SRN as well
- **[info] · C0026 abstract** (Part A — Citation notes structure)
  - This original church register entry (primary record, image attached) has no Abstract note — Abstract is "optional, encouraged for primary records", and since the FRN carries no marriage date, the entry's content is currently captured nowhere.
  - **Fix:** Add an Abstract note (type Abstract) summarizing the entry: marriage date, parties, officiant, witnesses
- **[info] scoping** (B.3 §1 Scope & record types covered)
  - Source is scoped to the "Marriage register" alone; the default church-record scope is one Source per congregation's record set — "the entry type is carried by the page-string record-noun, not by separate Sources" — with per-volume scoping only where volumes are catalogued/digitized separately.
  - **Fix:** Rescope to the Bethesda Lutheran Church record set (title as above) and move "marriage register" into the citation page string as the register/volume locator, unless the ELCA films genuinely catalog the marriage register as a separate volume.

### S0025 — Minnesota, U.S., Naturalization Records Index, 1854-1957
- **[major] author** (B.3 §2 Source author)
  - Author is "Conrad Peterzen, ed." — an index editor, not the creating body; state/county court naturalization takes "[Court name]" as author. The editor belongs in the FRN's index clause (where he already appears).
  - **Fix:** Crow Wing County District Court
- **[major] scoping** (Part A — Source scoping)
  - Source is the statewide platform index "Minnesota, U.S., Naturalization Records Index, 1854-1957", but B.3 §1 scopes naturalization "One Source per court-collection"; the citation itself is a Crow Wing County District Court Declaration (the FRN leads "Crow Wing County, Minnesota, naturalization records...").
  - **Fix:** Rescope as a court-collection Source, "Crow Wing County District Court, Naturalization Records, [year-range]"; the Peterzen/Ancestry index stays in the FRN's "indexed in" clause.
- **[major] title** (B.3 §4 Source title)
  - Title "Minnesota, U.S., Naturalization Records Index, 1854-1957" is the Ancestry database title, not the naturalization template "[Court], Naturalization Records, [year-range]" (series leads after locality because the court series is the navigable archival unit).
  - **Fix:** Crow Wing County District Court, Naturalization Records, [year-range]
- **[minor] abbrev** (B.3 §10 Abbrev rule — State abbreviations)
  - Abbrev "MN Naturalization Records Index" uses the USPS code "MN" (never USPS two-letter codes) and names the platform index rather than the court collection.
  - **Fix:** Crow Wing Co. naturalizations
  - *Verifier adjustment:* Issue and rule check out: §10 forbids USPS two-letter codes ('MN', 'WI') and the abbrev names the platform index rather than the court collection. But the proposed fix drops the year-range that every in-style naturalization Abbrev carries — §10's lead example ('St. Louis Co. naturalizations, 1888–1955'), the §10 worked SRN example ('Beltrami Co. naturalizations, 1887–1956'), and sibling source S0048 all include it. Corrected fix: 'Crow Wing Co. naturalizations, [year-range]' (year-range matching the rescoped court-collection title from idx 3/4).
- **[minor] · C0028 date** (Part A — Citation date)
  - Citation date field is set; the house style says the citation date is always left blank (the event date lives on the event, access date in the FRN, record-creation range in the Title).
  - **Fix:** Blank the citation date field.
- **[minor] · C0028 page** (Part A — Subject formatting in the page string)
  - Page string "Volume C, page 185, Declaration, Thomas E. Siggerud" spells out locators ("Volume", "page") instead of the universal "vol."/"p." forms (Part A, Universal SRN abbreviations — used in all citation forms), and inverts the subject: the record-noun must follow the name per "[locators], [name] [record-noun]" and §9 ("[Given Surname] declaration of intention"). The FRN's "volume C, page 185" should compress the same way.
  - **Fix:** vol. C, p. 185, Thomas E. Siggerud declaration of intention
- **[minor] pubinfo** (Part A — Pubinfo grammar)
  - Pubinfo "Database, Ancestry, https://www.ancestry.com" drops the required parentheses and terminal period of "[medium], [platform] (homepage URL)."
  - **Fix:** Database, Ancestry (https://www.ancestry.com).
- **[minor] · C0028 srn** (B.3 §10 Abbrev rule — State abbreviations / Record-type abbreviations (SRN only))
  - SRN "Crow Wing Co., MN, naturalization Declaration, vol. C, p. 185, Thomas E. Siggerud." uses USPS "MN" instead of "Minn." and leaves "naturalization Declaration" uncompressed where the SRN-only abbreviations "natz." and "decl." exist.
  - **Fix:** Crow Wing Co., Minn., natz. decl., vol. C, p. 185, Thomas E. Siggerud.
  - *Verifier adjustment:* Real issue: "MN" violates §10 (traditional forms only, "Minn.", never USPS codes) and "naturalization" should compress to "natz." in the SRN. But the SRN-only table defines no standalone "decl." — only "decl. no." (declaration number), and this index entry has no declaration number — so the proposed "natz. decl." is not a guide-supported abbreviation. Corrected fix: "Crow Wing Co., Minn., natz., declaration, vol. C, p. 185, Thomas E. Siggerud." (keep "declaration" spelled out).
- **[info] · C0028 confidence** (Part A — Confidence)
  - Confidence Normal (2) for an entry in an index-only compiled database ("Database, Ancestry", no images). Part A's Normal row ("derivative source carrying primary information") supports it, but the Low row explicitly names "compiled databases without source images" — the two anchors conflict for this record type and §8 has no naturalization-index row.
  - **Fix:** Either keep Normal with the derivative-carrying-primary rationale documented, or lower to 1 (Low) per the compiled-database anchor — and apply the same choice to C0029

### S0026 — Minnesota, U.S., Death Index, 1908-2017
- **[major] · C0029 page** (Part A — Two-forms-two-homes locator (hard rules for the page string))
  - Page string "Certificate no. 008051, record no. 1206708, Thomas Emil Siggerud, Lake of the Woods County" violates both hard rules: "Lake of the Woods County" is a place name attached to the subject slot (place lives on the event and in the FRN prose), and "record no. 1206708" is an apparent Ancestry database record identifier (the same number class as the /records/ URL paths seen elsewhere in this group), i.e. a URL parameter that belongs only inside the FRN's URL parenthetical. The subject also lacks a record-noun.
  - **Fix:** Certificate no. 008051, Thomas Emil Siggerud death index entry — move the place to the event/FRN prose and put the Ancestry record id into the FRN's deep URL
- **[minor] abbrev** (B.3 §10 Abbrev rule — State abbreviations)
  - Abbrev "MN Death Index" uses the USPS code "MN" and drops the year-range.
  - **Fix:** Minn. death index, 1908–2017
- **[minor] author** (B.3 §2 Source author)
  - Author "Minnesota Department of Health" omits the unit; the state-vital author value is "[State] Department of Health, Vital Records" (e.g. "Minnesota Department of Health, Vital Records").
  - **Fix:** Minnesota Department of Health, Vital Records
- **[minor] · C0029 date** (Part A — Citation date)
  - Citation date field is set; the house style says the citation date is always left blank (the event date lives on the event, access date in the FRN, record-creation range in the Title).
  - **Fix:** Blank the citation date field.
- **[minor] · C0029 frn** (Part A — Citation notes structure (FIRST REFERENCE NOTE))
  - FRN's URL parenthetical carries only the platform homepage: "Ancestry (https://www.ancestry.com : accessed 19 April 2026)". The FRN is the designated home for the deep, record-specific URL (the homepage belongs in Source Pubinfo; collection/record URLs "go inside the citation's First Reference Note").
  - **Fix:** Replace with the record's deep URL, e.g. (https://www.ancestry.com/search/collections/[dbid]/records/1206708 : accessed 19 April 2026)
- **[minor] pubinfo** (Part A — Pubinfo grammar)
  - Pubinfo "Database, Ancestry, https://www.ancestry.com" drops the required parentheses and terminal period.
  - **Fix:** Database, Ancestry (https://www.ancestry.com).
- **[minor] repository** (Part A — Repository decision tree)
  - Repository "Minnesota Department of Health" duplicates the creating agency on an online-only index database; step 3 of the decision tree says publications/online-only databases leave Repository blank (the FRN already carries "citing Minnesota Department of Health"). MDH is not one of the archives §3 prescribes (the chapter's prescribed holder for MN vitals is Minnesota Historical Society, worked example 2).
  - **Fix:** Leave Repository blank; keep "citing Minnesota Department of Health" in the FRN.
- **[minor] title** (B.3 §4 Source title)
  - Title "Minnesota, U.S., Death Index, 1908-2017" carries Ancestry's ", U.S.," branding inside an otherwise locality-led title; the state-vital pattern is "[State], [record series], [year-range]" with the series lowercased (cf. "Minnesota, death certificates, 1908–2002").
  - **Fix:** Minnesota, death index, 1908–2017

### S0027 — Norra Ny kyrkoarkiv, Husförhörslängder, AI:25 (1876-1880)
- **[minor] · C0030 frn** (B.2 §12 Worked examples; Part A — Universal SRN abbreviations; B.2 §3 Repository)
  - FRN/SRN use a US-census-style form: "1876-1880 husförhörslängd, Värmland, Sweden, Norra Ny församling, page 24..." — year-range-first and general-to-specific jurisdiction instead of creating-body lead, no vol. AI:25 designator, no bracketed gloss, "page 24" instead of "p. 24", "imaged" instead of "digital image", and "citing Norra Ny kyrkoarkiv" names the fond rather than the repository Värmlandsarkiv. SRN ("1876-1880 husförhörslängd, Norra Ny, Värmland, p. 24, Lars Persson Ambjörn.") has the same shape and lacks the record-noun.
  - **Fix:** FRN: "Norra Ny församling, Husförhörslängder [household examinations], vol. AI:25 (1876–1880), p. 24, household of Lars Persson Ambjörn [abbreviated \"Amb.\" in register]; digital image, Riksarkivet (https://sok.riksarkivet.se/bildvisning/C0038423_00036 : accessed 19 April 2026); citing Värmlandsarkiv, SE/VA/13398/A I/25." SRN: "Norra Ny husförhörslängd AI:25 (1876–1880), p. 24, Lars Persson Ambjörn household."

### S0029 — Älvdals häradsrätt, Bouppteckningar, FII:26 (1832-1833)
- **[major] · C0032 frn** (B.2 §3 Repository; B.2 §12 Worked examples (häradsrätt estate inventory))
  - FRN ends "citing Riksarkivet, SE/VA/11047" — the wrong archive. The SE/VA prefix is Värmlandsarkiv (the source's own repository record says Värmlandsarkiv), and the §12 worked example for this exact volume reads "citing Värmlandsarkiv, SE/VA/11047."
  - **Fix:** Change the citing clause to: citing Värmlandsarkiv, SE/VA/11047.
- **[minor] · C0032 frn** (B.2 §12 Worked examples; Part A — Universal SRN abbreviations)
  - FRN format drift against the §12 model for this very volume: gloss is inverted English-led ("estate inventories (bouppteckningar)") instead of "Bouppteckningar [estate inventories]", the "[Älvdal district court]" gloss after the author is missing, "pages 203-205" instead of "pp. 203–205", "imaged" instead of "digital image", and "vol." is missing before FII:26. SRN keeps "estate inventories" (subsequent notes drop the gloss) and its subject lacks the record-noun ("Per Persson, Ambjörbymon").
  - **Fix:** FRN: "Älvdals häradsrätt [Älvdal district court], Bouppteckningar [estate inventories], vol. FII:26 (1832–1833), pp. 203–205, estate inventory of Per Persson, Ambjörbymon, Norra Ny parish, died 5 May 1832; digital image, ArkivDigital (https://app.arkivdigital.se/volume/v48177?image=104 : accessed 20 April 2026); citing Värmlandsarkiv, SE/VA/11047." SRN: "Älvdals häradsrätt FII:26 (1832–1833), pp. 203–205, Per Persson estate inventory, Ambjörbymon."

### S0030 — Norra Ny kyrkoarkiv, Husförhörslängder, AI:11 (1812-1820)
- **[minor] · C0033 frn** (B.2 §12 Worked examples; B.2 §4 Source title (old collection-led note))
  - This citation is the §12 worked-example record but the FRN still uses the old form: leads "Norra Ny kyrkoarkiv, Husförhörslängder" instead of "Norra Ny församling, Husförhörslängder [household examinations]", omits the gloss, and the citing clause "citing SE/VA/13398/A I/11" omits the repository name. SRN ("Norra Ny kyrkoarkiv, Husförhörslängder, AI:11 (1812-1820), p. 8, Per Persson household.") uses the long collection form instead of the abbrev-style short form.
  - **Fix:** FRN: "Norra Ny församling, Husförhörslängder [household examinations], vol. AI:11 (1812–1820), p. 8, household of Per Persson, Ambjörby Torpare; digital image, Riksarkivet (https://sok.riksarkivet.se/bildvisning/C0038409_00019 : accessed 20 April 2026); also available as digital image, ArkivDigital (https://www.arkivdigital.se/aid/show/v12887.b15.s8 : accessed 20 April 2026); citing Värmlandsarkiv, SE/VA/13398/A I/11." SRN: "Norra Ny husförhörslängd AI:11 (1812–1820), p. 8, Per Persson household."

### S0031 — Norra Ny kyrkoarkiv, Födelse- och dopböcker, C:4 (1773-1825)
- **[minor] · C0039 confidence** (B.2 §8 Confidence guidance (per record type))
  - Confidence is 3 (High) on the child's own birth-and-baptism entry ("Cherstin Mattsdotter"). §8 prescribes "Very High for the child's birth/baptism"; the mother's secondary information is already split out into C0040. This is a conservative under-rating but off the prescribed level.
  - **Fix:** Set confidence to 4 (Very High).
- **[minor] · C0034 frn** (B.2 §12 Worked examples; B.2 §4 Source title (old collection-led note); B.2 §10 Abbrev rule)
  - FRN leads "Norra Ny kyrkoarkiv, Födelse- och dopböcker" (collection-led, no "[birth and baptism books]" gloss), subject is "Lars Persson, born 3 May 1819" without the record-noun phrase, and "citing SE/VA/13398" is truncated (no repository name, no volume path). SRN uses the long form ("Norra Ny kyrkoarkiv, Födelse- och dopböcker, C:4...") while sibling citations C0039/C0040 on the same source use the correct short "Norra Ny dopbok C:4" — inconsistent within one source.
  - **Fix:** FRN: "Norra Ny församling, Födelse- och dopböcker [birth and baptism books], vol. C:4 (1773–1825), p. 191, no. 34, birth and baptism entry for Lars Persson, born 3 May 1819; digital image, ArkivDigital (https://app.arkivdigital.se/volume/v5947?image=100&page=191 : accessed 21 April 2026); citing Värmlandsarkiv, SE/VA/13398/C/4." SRN: "Norra Ny dopbok C:4 (1773–1825), p. 191, no. 34, Lars Persson birth and baptism entry."
- **[minor] · C0039 frn** (B.2 §12 Worked examples; B.2 §4 Source title (old collection-led note))
  - FRN leads "Norra Ny kyrkoarkiv, Födelse- och dopböcker" — collection-led lead instead of the creating body, and no bracketed English gloss on first use. (Deep URL, access date, and citing clause are otherwise conformant.)
  - **Fix:** Open the FRN with: "Norra Ny församling, Födelse- och dopböcker [birth and baptism books], vol. C:4 (1773–1825), ..." (rest unchanged).
- **[minor] · C0040 frn** (B.2 §12 Worked examples; B.2 §4 Source title (old collection-led note))
  - FRN leads "Norra Ny kyrkoarkiv, Födelse- och dopböcker" — collection-led lead and no bracketed gloss on first use. (The relationship-only naming and evidence explanation "mother Marit Jonsdotter's birth date stated in the parents' column" are otherwise good.)
  - **Fix:** Open the FRN with: "Norra Ny församling, Födelse- och dopböcker [birth and baptism books], vol. C:4 (1773–1825), ..." (rest unchanged).
- **[minor] · C0034 page** (B.2 §7 Citation page templates; Part A — Subject formatting in the page string)
  - Page string "Vol. C:4, p. 191 (image 100), no. 34, Lars Persson" ends in a bare name — the required record-noun is missing; the §7 template for this record type is literally this entry ("no. 34, Lars Persson birth and baptism entry").
  - **Fix:** Page: "Vol. C:4, p. 191 (image 100), no. 34, Lars Persson birth and baptism entry"
- **[minor] · C0039 page** (B.2 §7 Citation page templates; Part A — Subject formatting in the page string)
  - Page string "Vol. C:4, p. 197 (image 103), no. 11, Cherstin Mattsdotter" and SRN subject "no. 11, Cherstin Mattsdotter." both lack the record-noun ("birth and baptism entry").
  - **Fix:** Page: "Vol. C:4, p. 197 (image 103), no. 11, Cherstin Mattsdotter birth and baptism entry"; SRN: "Norra Ny dopbok C:4 (1773–1825), p. 197, no. 11, Cherstin Mattsdotter birth and baptism entry."
- **[minor] · C0040 page** (B.2 §9 Subject vocabulary; Part A — Subject formatting in the page string (Parenthetical annotations))
  - Page-string parenthetical "Marit Jonsdotter (mother named)" does not follow the evidence-quality flag pattern "(named at OTHER-PERSON's EVENT)"; §9 gives the exact model for this case: "Marit Jonsdotter (named at daughter Cherstin's birth and baptism)".
  - **Fix:** Page: "Vol. C:4, p. 197 (image 103), no. 11, Marit Jonsdotter (named at daughter Cherstin's birth and baptism)"

### S0033 — Parrocchia di San Bartolomeo (Vistrorio, Turin, Italy), Atti di Matrimonio, 1582-1899
- **[major] author** (Part 0 — Gramps field map (Source author row: creating body, "No country or umbrella prefix"))
  - Author "Chiesa cattolica. Parrocchia di Vistrorio (Torino)" carries the forbidden umbrella prefix "Chiesa cattolica." and additionally contradicts this source's own title, which names the creating parish "Parrocchia di San Bartolomeo" — the author and title name two different parishes for the same register.
  - **Fix:** Use the same canonical parish-only author as S0017 after correction, e.g. "Parrocchia di San Bartolomeo (Vistrorio, Torino)".
- **[major] call_number** (Part A — Two-forms-two-homes locator (Call number = the archive's machine reference only))
  - Call number "Image group number 007961680" is a FamilySearch platform identifier stored as the call number of "Archivio di Stato di Torino" — it is not that archive's machine reference, and it is also formatted differently from S0017's version of the same value ("FamilySearch image group 007961680").
  - **Fix:** Replace with the Archivio di Stato di Torino's own catalog reference for the Vistrorio parish registers (or leave blank if unknown); keep the image group number only in the citation First Reference Notes.
- **[major] title** (Part A — Title philosophy)
  - Title "Parrocchia di San Bartolomeo (Vistrorio, Turin, Italy), Atti di Matrimonio, 1582-1899" is creating-body-led (parish leads) rather than locality-led with largest jurisdiction first; it also uses a hyphen instead of an en-dash in the year-range, unlike every Part A worked example (e.g. "1862–1869").
  - **Fix:** Italy, Piedmont, Turin, Vistrorio, parish registers, marriage acts (Atti di Matrimonio), 1582–1899
- **[minor] call_number** (Part A — Two-forms-two-homes locator (each identifier form has one home) — internal consistency check, no Italian chapter)
  - Both sources claim the identical image group 007961680, yet their citations report incompatible image totals — C0014 cites "Image 694 of 811" and C0036 cites "image 499 of 617". A single FamilySearch image group has one fixed image count, so at most one source's image-group attribution can be correct.
  - **Fix:** Open both ark URLs in the FRNs, read the actual image group (DGS) number for each register from the FamilySearch viewer, and record the correct group number for each source in its FRN (and correct whichever source-level reference was copied wrongly).
  - *Verifier adjustment:* The contradiction is real and verified in the records — C0014 cites 'Image 694 of 811' and C0036 'image 499 of 617' while both sources claim group 007961680, and one image group has one fixed count — but the cited rule does not support it: Two-forms-two-homes governs WHERE identifier forms live, not whether identifier values are accurate or mutually consistent; no Part A rule covers cross-source factual consistency. Re-cite as a factual-accuracy / internal-consistency finding without a Part A rule anchor (severity minor stands). The proposed fix (open both ark URLs, read each register's actual DGS/image-group number from the viewer, correct the wrong attribution in FRN and source-level fields) is sound and stands.
- **[minor] · C0036 date** (Part A — Citation date)
  - Citation date field is set; the house style says the citation date is always left blank (the event date lives on the event, access date in the FRN, record-creation range in the Title).
  - **Fix:** Blank the citation date field.
- **[minor] · C0036 page** (Part A — Subject formatting in the page string)
  - Subject "Castellano Bartolomeo and Formento Maria" uses the "and"-couple form instead of the preferred hyphenated-couple shorthand, has no record-noun, and the image locator trails after the subject ("; image 499 of 617") instead of preceding it in the [locators], [name] [record-noun] shape. Also inconsistent with C0014, which leads with the image locator ("Image 694 of 811, ...").
  - **Fix:** 1871, no. 1, image 499 of 617, Castellano-Formento marriage
- **[minor] pubinfo** (Part A — Pubinfo grammar ('[medium], [platform] (homepage URL).'))
  - Pubinfo "Digital images. \"Vistrorio, Turin, Piedmont, Italy records.\" FamilySearch." is period-separated instead of comma-separated, includes a collection title the grammar has no slot for, and omits the required platform homepage URL (Platform/URL table gives FamilySearch = https://www.familysearch.org); it is also punctuated differently from S0017's pubinfo for the same platform.
  - **Fix:** Digital images, FamilySearch (https://www.familysearch.org).
- **[info] · C0036 frn** (Part A — Citation notes structure (guide otherwise silent — internal consistency))
  - Both citations cite "image group number 007961680" but with irreconcilable totals — C0014 says "image 694 of 811", C0036 says "image 499 of 617"; one FamilySearch image group has a single fixed image count, so at least one citation's group number or total is wrong. The provenance layer also differs: C0036 has "citing Archivio di Stato di Torino, image group number 007961680" while C0014 appends the bare "image group number 007961680" with no citing layer.
  - **Fix:** Verify both entries on FamilySearch and correct whichever image group number or image total is wrong; then use the same provenance phrasing in both FRNs, e.g. "; citing Archivio di Stato di Torino, image group number NNNNNNNNN".
- **[info] · C0036 srn** (Part A — Citation notes structure (SRN: repeats just enough to identify))
  - SRN locator style is inconsistent within the group: C0014's SRN ends with an image locator ("; FamilySearch image 694") while C0036's SRN ("Parrocchia di San Bartolomeo (Vistrorio), Atti di Matrimonio, 1871, no. 1, Castellano Bartolomeo and Formento Maria.") carries no image locator at all. Guide is silent on which is right; the two sources should treat it the same way.
  - **Fix:** Pick one convention for the group: either append "; FamilySearch image 499" to C0036's SRN, or drop "; FamilySearch image 694" from C0014's (C0036's "no. 1" already identifies the entry, so dropping is the more compact choice).

### S0034 — U.S., Social Security Death Index, 1935-2014
- **[minor] abbrev** (B.3 §10 Abbrev rule)
  - Abbrev "SSDI" is an aggressive acronym; "The US Abbrev convention keeps whole readable words, pushing aggressive abbreviation to the SRN", and SSDI is not in the sanctioned collection-abbreviation table (unlike FAG).
  - **Fix:** Social Security Death Index
- **[minor] · C0037 confidence** (Part A — Confidence)
  - Confidence High (3) for an index-only database entry. Part A anchors High to originals or a "clean, contemporaneous derivative of an original (e.g. a digital image of an original)"; a no-image database entry is at best "derivative source carrying primary information" (Normal), and "compiled databases without source images" anchor at Low.
  - **Fix:** Set confidence to 2 (Normal)
- **[minor] · C0037 date** (Part A — Citation date)
  - Citation date field is set; the house style says the citation date is always left blank (the event date lives on the event, access date in the FRN, record-creation range in the Title).
  - **Fix:** Blank the citation date field.
- **[minor] · C0037 frn** (Part A — Citation notes structure (FIRST REFERENCE NOTE))
  - FRN contains the unresolved placeholder "accessed [date]" where the access date is required, and carries extracted facts ("born 11 January 1889 ... last residence Eveleth, Saint Louis County, Minnesota") that belong in an Abstract note — no Abstract note exists on this citation.
  - **Fix:** Fill in the actual access date; trim the FRN to the entry-identifying data (entry for Mike Castellano, SSN 469-05-0388, died December 1977) and move the birth date and last residence into a new Abstract note
  - *Verifier adjustment:* The unresolved "accessed [date]" placeholder is a genuine violation — Part A requires the FRN to include the URL with access date. But the extracted-facts half is unsupported: Part A explicitly places place "inside the First Reference Note prose," the house model FRNs themselves carry birth/death data (worked example 4 "(1848–1929)", example 6 "died 31 October 1948", example 11 "died 7 May 1914, buried 9 May 1914"), and the Abstract note is optional, not a required home. Corrected fix: fill in the actual access date; the entry-identifying data (birth date, last residence) may remain in the FRN.
- **[minor] · C0037 page** (Part A — Subject formatting in the page string)
  - Page string "Mike Castellano, SSN 469-05-0388, b. 11 January 1889, d. December 1977" does not follow "[locators], [name] [record-noun]": the locator (SSN) trails the name, there is no record-noun, and full birth/death dates are extracted facts carried as trailing data rather than, at most, a "(b. 1889)" disambiguator parenthetical.
  - **Fix:** SSN 469-05-0388, Mike Castellano Social Security Death Index entry
- **[minor] repository** (Part A — Repository decision tree)
  - Repository "Social Security Administration" (with call number "Death Master File") is the creating agency on an online-only database, not a physical archive; step 3 says leave Repository blank for online-only platforms/databases. The FRN already carries "citing Social Security Administration, Death Master File".
  - **Fix:** Remove the repository link (blank Repository, blank call number); the Death Master File citing clause stays in the FRN.
- **[info] pubinfo** (Part A — Pubinfo grammar)
  - Pubinfo "Database, Ancestry (https://www.ancestry.com)" is missing the terminal period of the "[medium], [platform] (homepage URL)." form.
  - **Fix:** Database, Ancestry (https://www.ancestry.com).

### S0035 — Norra Ny kyrkoarkiv, Husförhörslängder, AI:12 (1820-1832)
- **[minor] · C0038 frn** (B.2 §12 Worked examples; Part A — Two-forms-two-homes locator (no place as subject); Part A — Universal SRN abbreviations)
  - FRN reads "Norra Ny parish, Värmland, Sweden, husförhörslängd AI:12 (1820-1832), p. 427, Ambjörby; imaged, ...; citing Värmlandsarkiv, NAD SE/VA/13398." — place-led opening instead of the creating body, no gloss, no subject at all (the entry is identified only by the place name "Ambjörby"), "imaged" instead of "digital image", and a truncated call number with a stray "NAD" prefix. SRN ("Norra Ny husförhörslängd AI:12, p. 427, Ambjörby.") likewise omits the year-range and uses a place name as the subject.
  - **Fix:** FRN: "Norra Ny församling, Husförhörslängder [household examinations], vol. AI:12 (1820–1832), p. 427, Marit Jonsdotter in [head-name] household, Ambjörby; digital image, ArkivDigital (https://www.arkivdigital.se/aid/show/v12888.b219.s427 : accessed 26 April 2026); citing Värmlandsarkiv, SE/VA/13398/A I/12." SRN: "Norra Ny husförhörslängd AI:12 (1820–1832), p. 427, Marit Jonsdotter household."
  - *Verifier adjustment:* All cited defects are real and verified in N0071 (place-led opening, no gloss, no personal subject — only 'Ambjörby', 'imaged' instead of 'digital image', stray 'NAD' prefix and truncated call number vs. SE/VA/13398/A I/12, SRN missing year-range and using a place as subject). But the proposed fix is internally inconsistent: the FRN uses the non-head form 'Marit Jonsdotter in [head-name] household' while the SRN asserts the head form 'Marit Jonsdotter household' — under either headship resolution one half violates Part A's role-visible rule (or resolves absurdly to 'Marit Jonsdotter in Marit Jonsdotter household'). Corrected fix: verify headship first; if head, FRN '...p. 427, household of Marit Jonsdotter, Ambjörby...' and SRN '...p. 427, Marit Jonsdotter household.'; if not head, use 'Marit Jonsdotter in [Head-surname] household' in BOTH FRN and SRN. Also the 'Universal SRN abbreviations' citation is inapt — the operative anchors are §12 worked examples and Part A subject formatting.
- **[minor] · C0038 note_type** (Part A — Citation notes structure)
  - Note N0077 (type "General") holds extracted record content: "Her mother is listed as Marit Jonsdotter, b. 16 Aug 1797, Dahlby." This is abstract material (a fact the record states), not a general comment, and the referent "Her" is not self-contained.
  - **Fix:** Convert N0077 to an Abstract-type note and make it self-contained, e.g. "ABSTRACT: The household entry at Ambjörby lists [daughter's name]'s mother Marit Jonsdotter, born 16 Aug 1797 at Dahlby."
- **[minor] · C0038 page** (Part A — Subject formatting in the page string (Parenthetical annotations; role-visible form))
  - Page string "Vol. AI:12, p. 427 (image 219), Marit Jonsdotter household" carries no evidence-quality flag although the citation is rated Normal and (per note N0077) supports Marit Jonsdotter's stated birth date — secondary information. Also verify she is actually the household head in 1820–1832; if not, the role-visible form "Marit Jonsdotter in [Head-surname] household" is required.
  - **Fix:** Page: "Vol. AI:12, p. 427 (image 219), Marit Jonsdotter (stated birth date 16 Aug 1797) household" — or, if she is not the head: "Vol. AI:12, p. 427 (image 219), Marit Jonsdotter (stated birth date 16 Aug 1797) in [Head-surname] household".
- **[info] repository** (Part A — Repository decision tree)
  - S0035 carries the identical repository link twice: "Värmlandsarkiv [Archive] call#=SE/VA/13398/A I/12; Värmlandsarkiv [Archive] call#=SE/VA/13398/A I/12" — a duplicated repo attachment.
  - **Fix:** Remove the duplicate Värmlandsarkiv repository link, keeping one with call# SE/VA/13398/A I/12.

### S0036 — Folketelling 1801, Eidsvoll prestegjeld, Akershus, L0009
- **[major] title** (Part A — Title philosophy; B.1 §4 Source title (Census records))
  - Title "Folketelling 1801, Eidsvoll prestegjeld, Akershus, L0009" leads with the record type and runs smallest-jurisdiction-first, missing the country; the locality-led template is "Norway, [Amt], [Prestegjeld], folketelling 1801, [reference if needed]" with worked example "Norway, Akershus, Eidsvoll, folketelling 1801, L0009".
  - **Fix:** Norway, Akershus, Eidsvoll, folketelling 1801, L0009
- **[major] title** (Part A — Title philosophy; Part A — Two-forms-two-homes locator)
  - Norwegian censuses in two styles: S0036 "Folketelling 1801, Eidsvoll prestegjeld, Akershus, L0009" is census-year-led AND carries the machine-path fragment "L0009" (part of call# AV/RA-EA-4070/J/Jd/L0009) in the Title, violating "The archival machine path is never put in the Title." The other five censuses (S0038, S0069, S0071, S0076, S0077) already use the correct locality-led form, e.g. "Norway, Akershus, Eidsvoll, folketelling 1875".
  - **Fix:** Retitle S0036 to "Norway, Akershus, Eidsvoll, folketelling 1801"; L0009 stays only in the Call number (AV/RA-EA-4070/J/Jd/L0009). Update abbrev "Folketelling 1801 Eidsvoll L0009" → "Eidsvoll folketelling 1801" to match sibling abbrevs.
- **[minor] abbrev** (B.1 §10 Abbrev rule)
  - Abbrev "Folketelling 1801 Eidsvoll L0009" is record-type-led and carries the volume token L0009; the §10 form is "[Place] folketelling YYYY" (examples: "Eidsvoll folketelling 1875"), with the L-reference living in Title/Call number, not the Abbrev.
  - **Fix:** Eidsvoll folketelling 1801
- **[minor] author** (B.1 §2 Source author (naming decision pending))
  - Author "Nasjonalarkivet" vs. the master's "Riksarkivet (preferred)" — a naming-decision conflict, but the drift is real regardless: the six folketelling sources carry three different author spellings (Nasjonalarkivet / "Nasjonalarkivet (Riksarkivet)" / Riksarkivet).
  - **Fix:** Standardize all six census authors on the single value the naming decision selects.
- **[minor] author** (Part 0 — Gramps field map)
  - Norwegian census authors written three ways for the same record class: S0036 and S0076 "Nasjonalarkivet", S0038 "Nasjonalarkivet (Riksarkivet)", S0069/S0071/S0077 "Riksarkivet". The field map defines author as the creating body, stated one way.
  - **Fix:** Standardize all six folketelling sources on the author value the naming decision selects; eliminate the doubled "Nasjonalarkivet (Riksarkivet)" form.
- **[info] repository** (B.1 §2/§3 vs. the 2026 archive-law merger)
  - Repository "Nasjonalarkivet" conflicts with the pre-merger institution names the written master (B.1 §2/§3) prescribes for this volume's AV/… call-number prefix. Pending the Nasjonalarkivet naming decision (see the catalog-wide repository finding): on 1 January 2026 the new archive law merged Arkivverket, Riksarkivet and the statsarkivene into one agency, Nasjonalarkivet — so the master's pre-merger names are stale on its own "follow the current naming" rationale.
  - **Fix:** Recommended: update house_style_master.md B.1 §2/§3 and the §11–§12 worked examples to Nasjonalarkivet — this field then already conforms. Either way, remove the digitalarkivet.no platform URL from repository record R0009 (platform ≠ repository).

### S0037 — Check in on status of the St. Louis Co. marriage record case
- **[minor] scoping** (Part A — Source scoping)
  - "Check in on status of the St. Louis Co. marriage record case" is an access-status tracking log quoting reclaimtherecords.org ("St. Louis county marriage records are not accessible... no update as of 2026-05-16"). It is not a source and wraps only a conditional future source (a St. Louis County marriage-certificate collection, county-collection scoped under B.3, once access opens). As a Source it emits a nonsense bibliography line.
  - **Fix:** Re-parent note N0079 as a general research To Do note (person-independent, e.g. attached to a research-log person or the relevant family) and delete the Source; create the county-collection marriage Source only when records become citable.

### S0038 — Norway, Akershus, Eidsvoll, folketelling 1875
- **[minor] author** (B.1 §2 Source author)
  - Author "Nasjonalarkivet (Riksarkivet)" is the doubled form the master forbids — and it is wrong under either naming outcome; the agency name is written bare.
  - **Fix:** Use the single decided name bare (post-2026 merger: Nasjonalarkivet).
- **[minor] · C0041 frn** (B.1 §12 Worked example 2 (bracketed English gloss, EE 2.28))
  - FRN in N0082 opens "Folketelling 1875, Akershus fylke, …" without the bracketed English gloss on first use of the foreign series name.
  - **Fix:** Folketelling 1875 [population census 1875], Akershus fylke, Eidsvoll prestegjeld, …
- **[minor] · C0041 frn** (B.1 §12 Worked example 2; Part A — Subject formatting in the page string (relationship phrasing))
  - FRN names the subject as "Karen Indiana Evensdatter, tyende;" — the household-role descriptor floats outside a parenthetical and the household head/relationship is never named, unlike the worked-example form "(tjenestepige, stated age 14, in Jens Hansen's household)" for this same record.
  - **Fix:** …, person no. 006, Karen Indiana Evensdatter (tyende, in [head]'s household); … — name the head and her relationship to the household in the parenthetical.
- **[minor] · C0041 page** (Part A — Subject formatting in the page string (role-visible form for non-head household members); B.1 §12 Worked example 2)
  - Page subject is bare "Karen Indiana Evensdatter" although she is a non-head servant in the household; the prescribed role-visible form (shown for this exact record in Worked example 2) is `[Subject] (source-state, evidence-quality) in [Head-surname] household`.
  - **Fix:** District 009 Blegstad, p. 1270, household 01, person 006, Karen Indiana Evensdatter (tjenestepige, stated age 14) in Hansen household — use the record's own role term (the FRN records "tyende") if that is what the entry says.
- **[info] · C0041 abstract** (Part A — Citation notes structure (Abstract optional, encouraged for primary records))
  - Citation on an original census record has no Abstract note, while every other census citation in the group (C0073, C0079, C0080) carries one.
  - **Fix:** Add a note of type Abstract summarizing the household entry (head, members, roles, stated ages, birthplaces) so extracted facts have a home outside the FRN.
- **[info] repository** (B.1 §2/§3 vs. the 2026 archive-law merger)
  - Repository "Nasjonalarkivet" conflicts with the pre-merger institution names the written master (B.1 §2/§3) prescribes for this volume's AV/… call-number prefix. Pending the Nasjonalarkivet naming decision (see the catalog-wide repository finding): on 1 January 2026 the new archive law merged Arkivverket, Riksarkivet and the statsarkivene into one agency, Nasjonalarkivet — so the master's pre-merger names are stale on its own "follow the current naming" rationale.
  - **Fix:** Recommended: update house_style_master.md B.1 §2/§3 and the §11–§12 worked examples to Nasjonalarkivet — this field then already conforms. Either way, remove the digitalarkivet.no platform URL from repository record R0009 (platform ≠ repository).

### S0039 — April Research Update
- **[minor] scoping** (Part A — Source scoping)
  - "April Research Update" is a monthly research-progress narrative ("Big month on the Norwegian side: I finally tracked down..."), i.e. a blog post, not a source. It matches no scoping unit and has zero citations, but under Part A Bibliography mapping it would emit a false authored-work line ("Grund, Peter. April Research Update."). It does mention genuine sources (Eidsvoll bygdebok, 1801/1875 folketellinger, the purchased Ambjörby local-history book) — those belong as their own properly scoped Sources (the Ambjörby book as a B.4 per-book Source), not inside this record.
  - **Fix:** Keep as a Gramps Web blog post if that is its function, but tag it for exclusion from the bibliography transform; verify the sources it mentions (esp. the Ambjörby history book) exist as real per-book/per-volume Sources.

### S0040 — Personal research of Siw Alfreddson, Ambjörby, Sweden
- **[major] · C0042 frn** (Part A — Citation notes structure)
  - No FIRST REFERENCE NOTE / SHORT REFERENCE NOTE block (has 'Reference' and 'Translation' notes but no FRN/SRN block). FRN and SRN are required for every citation.
  - **Fix:** Compose the FRN/SRN per the domain chapter (bifrost's citation composer can draft it) and store in a Citation-type note.
- **[minor] abbrev** (Part 0 — Gramps field map; domain §10)
  - Source has no Abbrev; every real source needs the short identifier for Gramps source-list views.
  - **Fix:** Add the domain §10-form abbrev.
- **[minor] · C0042 note_type** (Part A — Citation notes structure (Transcription = the verbatim text of the record entry))
  - Note N0085 is typed "Reference" but its content is the verbatim Swedish text of Siw Alfreddson's typed page ("5 HULTTÄPPA … 6 AMBMYRA …") — i.e. a Transcription, the counterpart of the correctly-typed Translation note N0086.
  - **Fix:** Change note N0085's type from Reference to Transcription.
- **[minor] pubinfo** (B.4 §6 Pubinfo (personal research: `Unpublished research, [location], [year-range].`); B.4 §12 Worked examples — Personal research from another genealogist)
  - Pubinfo is "Unpublished research" — missing the location and year-range (and terminal period). The §12 worked example for this exact source is `Unpublished research, Ambjörby, Sweden, 2024–2026.`
  - **Fix:** Unpublished research, Ambjörby, Sweden, 2024–2026.

### S0041 — Medlemmer av Den norske sakførerforening 1. juli 1950
- **[major] pubinfo** (Part A — Pubinfo grammar, Published-works imprint variant (online book via a library platform); B.4 §6 Pubinfo; B.4 §12 Worked examples — A membership directory or annual publication)
  - Pubinfo is "Digital images, Nasjonalbiblioteket (https://www.nb.no)." — the digital-provider clause only. For a published work accessed online the form is `[City]: [Publisher], year. Digital images, [Platform] (URL).`; the entire imprint layer (Oslo: Den norske sakførerforening, 1951 — confirmed by the C0043 FRN) is missing from the Source.
  - **Fix:** Oslo: Den norske sakførerforening, 1951. Digital images, Nasjonalbiblioteket (https://www.nb.no).
- **[major] repository** (Part A — Repository decision tree; B.4 §3 Repository; B.4 §12 Worked examples — A membership directory or annual publication)
  - Repository is "Nasjonalbiblioteket" (R0024, with a URN call number). This is a published book accessed via an online platform; decision-tree step 3 says publications and online platforms get a BLANK Repository ("a website is a publication, not a repository", EE 2.34), and the §12 worked example for this exact source shows Repository (blank). Nasjonalbiblioteket is the digital provider and already appears in Pubinfo where it belongs.
  - **Fix:** Remove the R0024 repository link from S0041 — leave Repository blank; Nasjonalbiblioteket stays in Pubinfo as the platform-publisher.
- **[minor] call_number** (Part A — Two-forms-two-homes locator; B.4 §12 Worked examples — A membership directory or annual publication (Call number: blank))
  - Call number is "URN:NBN:no-nb_digibok_2013071008075" — a platform digital-object identifier, not a physical archive machine reference. The worked example for this source shows Call number blank, and the URN already appears in the C0043 FRN's "citing http://urn.nb.no/…" clause, its proper home.
  - **Fix:** Blank the call number (the URN is preserved in the FRN citing clause).
- **[minor] · C0043 frn** (B.4 §2 Source author (membership directories = issuing organization) / B.4 §12 Worked examples — A membership directory or annual publication)
  - The FRN opens with the bare title — "Medlemmer av Den norske sakførerforening 1. juli 1950 (Oslo: Den norske sakførerforening, 1951)…" — omitting the organizational author lead that the house FRN form requires.
  - **Fix:** Prepend the author: "Den norske sakførerforening, Medlemmer av Den norske sakførerforening 1. juli 1950 [gloss] (Oslo: Den norske sakførerforening, 1951), p. 440, entry for Frithjof Siggerud; …"
- **[minor] · C0043 srn** (Part A — Citation notes structure (SRN is compact) / B.4 §12 Worked examples — A membership directory (SRN: "Sakførerforening medlemmer 1950, p. 440, Frithjof Siggerud."))
  - The SRN reads "Den norske sakførerforening medlemmer 1950, p. 440, Frithjof Siggerud." — longer than the prescribed compact short form, which drops the organization's full name.
  - **Fix:** Sakførerforening medlemmer 1950, p. 440, Frithjof Siggerud.
- **[info] · C0043 frn** (B.4 §4 Source title (EE 2.28: bracketed English gloss "encouraged in the FRN") / B.4 §12 worked example FRN)
  - The FRN gives the Norwegian title "Medlemmer av Den norske sakførerforening 1. juli 1950" with no bracketed English gloss on first use; the worked example for this very source includes one.
  - **Fix:** Insert "[Members of the Norwegian Bar Association as of 1 July 1950]" after the title in the FRN (FRN only; the SRN correctly drops it).

### S0042 — Elever ved Kristiania katedralskole som begynte på skolen i årene 1891-1901, hefte 8
- **[major] · C0044 frn** (Part A — Citation notes structure)
  - No FIRST REFERENCE NOTE / SHORT REFERENCE NOTE block (citation has no notes at all). FRN and SRN are required for every citation.
  - **Fix:** Compose the FRN/SRN per the domain chapter (bifrost's citation composer can draft it) and store in a Citation-type note.
- **[major] pubinfo** (Part A — Pubinfo grammar, Published-works imprint variant (online book via a library platform); B.4 §6 Pubinfo; B.4 §12 Worked examples — A school enrollment register)
  - Pubinfo is "Digital images, Nasjonalbiblioteket (https://www.nb.no)." — digital-provider clause only, missing the imprint layer. The §12 worked example for this exact source prescribes `[Place]: [Publisher], [year]. Digital images, Nasjonalbiblioteket (https://www.nb.no).` with bracketed placeholders until the imprint is established.
  - **Fix:** [Place]: [Publisher], [year]. Digital images, Nasjonalbiblioteket (https://www.nb.no). — replace the bracketed placeholders with the actual imprint if known.
- **[major] repository** (Part A — Repository decision tree; B.4 §3 Repository; B.4 §12 Worked examples — A school enrollment register)
  - Repository is "Nasjonalbiblioteket" (R0024). Same violation as S0041: this is a published institutional roster accessed via the NB digital platform; the §12 worked example for this exact source shows Repository (blank), and step 3 of the decision tree assigns platforms to Pubinfo, never Repository.
  - **Fix:** Remove the R0024 repository link from S0042 — leave Repository blank; Nasjonalbiblioteket stays in Pubinfo as the platform-publisher.
- **[minor] abbrev** (B.4 §10 Abbrev rule (example: `Kristiania katedralskole 1891–1901`))
  - Abbrev "Kristiania katedralskole 1891-1901" uses a hyphen where §10's example for this exact source uses an en-dash.
  - **Fix:** Kristiania katedralskole 1891–1901
- **[minor] call_number** (Part A — Two-forms-two-homes locator; B.4 §12 Worked examples — A school enrollment register (Call number: blank))
  - Call number is "URN:NBN:no-nb_digibok_2022072548161" — a platform digital-object identifier, not an archive machine reference; the worked example shows Call number blank.
  - **Fix:** Blank the call number; carry the URN inside the FRN's citing clause when C0044's missing FRN/SRN block is written.
- **[minor] title** (B.4 §12 Worked examples — A school enrollment register (title uses en-dash year-range); Part A — Title philosophy (year-range form))
  - Title year-range uses a hyphen: "i årene 1891-1901, hefte 8"; the house form throughout (and the §12 worked example for this exact source) is the en-dash: "1891–1901".
  - **Fix:** Elever ved Kristiania katedralskole som begynte på skolen i årene 1891–1901, hefte 8

### S0043 — Minnesota Death Index, 1944-1953
- **[minor] abbrev** (B.3 §10 Abbrev rule — State abbreviations)
  - Abbrev "MN Death Index 1944-1953" uses the USPS code "MN" and is missing the comma before the year-range.
  - **Fix:** Minn. death index, 1944–1953
- **[minor] author** (B.3 §2 Source author)
  - Author "Minnesota Department of Health" omits the unit; the state-vital author value is "Minnesota Department of Health, Vital Records".
  - **Fix:** Minnesota Department of Health, Vital Records
- **[minor] call_number** (Part A — Two-forms-two-homes locator)
  - Call number reads "microfilm, item code \"SOM/H07/009\"" — the Call number holds "the archive's machine reference only", without descriptive verbiage or quotation marks.
  - **Fix:** SOM/H07/009
- **[minor] · C0045 page** (Part A — Subject formatting in the page string)
  - Page string "Card entry, \"GRUND LOUIS. BAUDET LAKE OF WOOD 06/10/52. 73\", Louis Grund" embeds the verbatim card text — which already lives in the transcription note N0091 and drags place text ("BAUDET LAKE OF WOOD") into the page string — and the subject lacks a record-noun.
  - **Fix:** Card entry, Louis Grund death index entry (d. 1952)
- **[minor] title** (B.3 §4 Source title)
  - Title "Minnesota Death Index, 1944-1953" lacks the locality-led comma form; state-vital series titles are "[State], [record series], [year-range]" with the series lowercased.
  - **Fix:** Minnesota, death index, 1944–1953
- **[info] · C0045 confidence** (Part A — Confidence)
  - Confidence High (3) for a card in the state-compiled death index — a derivative of the certificates. Part A puts derivative-carrying-primary at Normal; High requires a "clean, contemporaneous derivative of an original" reading. It is also inconsistent with C0029, where the same Minnesota Department of Health death-index content is rated Normal (2).
  - **Fix:** Consider 2 (Normal) to match C0029, or document why the physically-consulted card index rates the clean-contemporaneous-derivative High
  - *Verifier adjustment:* Core issue real: C0045 is rated 3 (High) for a state-compiled card-index derivative, which Part A sustains only via the High row's "clean, contemporaneous derivative of an original" reading — and that rationale is undocumented. But the inconsistency-with-C0029 claim is overstated: the two are not "the same content" evidentially — C0045 is a microfilm image of the state's own contemporaneous card index (one derivative step), C0029 is Ancestry's index-only re-database (deeper derivative, no images) — so a one-level rating difference is defensible, not contradictory. Corrected wording: "High (3) for the physically-consulted card index is sustainable only under Part A's clean-contemporaneous-derivative anchor; either document that reading or lower to 2 (Normal) per the default derivative-carrying-primary row." Fix and info severity otherwise stand.
- **[info] repository** (Part A — Repository decision tree)
  - Repository "Minneapolis Central Library" holds a microfilm copy, not the original index (step 1 names the institution holding the original); the closest sanctioned analog is the Family History Library row ("when a physical microfilm number applies"), so the library is defensible, but the FRN already carries "consulted at Hennepin County Library, Minneapolis Central Library".
  - **Fix:** Either keep Minneapolis Central Library on the FHL film-holder analogy, or name the holder of the original index (Minnesota Historical Society / Office of the State Registrar) and leave the consultation venue in the FRN.

### S0044 — Minneapolis Telephone Directory, White Pages, December 1984
- **[major] repository** (Part A — Repository decision tree)
  - Repository "Minneapolis Central Library" is attached to a published directory; step 3 is explicit that publications get no repository — "the same logic applies to library-held published works" — and worked example 7 leaves the directory's Repository blank. The consultation venue is already in the FRN ("consulted at Hennepin County Library, Minneapolis Central Library").
  - **Fix:** Remove the repository link (blank Repository); keep the consulted-at clause in the FRN.
- **[minor] call_number** (Part A — Two-forms-two-homes locator)
  - Call number "Bell & Howell PhoneFiche 38472, fiche 7 of 19" carries the granular locator "fiche 7 of 19", which is citation-level (it already leads both citations' page strings); with Repository blank there is no source-level call number, and the PhoneFiche item number belongs in the Pubinfo production statement.
  - **Fix:** Blank (PhoneFiche 38472 moves to Pubinfo; fiche 7 of 19 stays in the citation page strings).
  - *Verifier adjustment:* Issue and end state are correct (Call number should be blank: 'fiche 7 of 19' is a granular locator already leading both citation page strings, and with Repository blank a publication has no archive machine reference — cf. worked example 7 and §5's no-source-level-call-number principle), but the fix's 'PhoneFiche 38472 moves to Pubinfo' is wrong in one detail: S0044's Pubinfo already reads 'reproduced on microfiche by Bell & Howell, PhoneFiche series, item no. 38472', so nothing moves — simply blank the Call number and leave the page strings as they are.
- **[minor] · C0046 page** (B.3 §7 Citation page templates (City directory))
  - Page string "Fiche 7 of 19 (pp. 563-656), entry for Marie E. Grund" gives only the fiche and its page range — no exact page for the entry appears in the page string, FRN, or SRN. The directory template is "p. [N], entry for [Name]"; the fiche detail already lives in the Call number and the FRN's microfiche clause.
  - **Fix:** p. [N], entry for Marie E. Grund — read the exact page from the fiche and add "p. [N]" to the FRN and SRN as well
- **[minor] · C0047 page** (B.3 §7 Citation page templates (City directory))
  - Same as C0046: "Fiche 7 of 19 (pp. 563-656), entry for Thomas M. Grund" lacks the exact page in page string, FRN, and SRN; the FRN also quotes the verbatim entry "\"Grund Thomas M 3240 Fremont Av S...823-5723\"", which belongs in a Transcription note.
  - **Fix:** p. [N], entry for Thomas M. Grund — add "p. [N]" to FRN/SRN and move the quoted directory line to a Transcription note
  - *Verifier adjustment:* The missing-exact-page issue is confirmed (identical to C0046): replace the page string with 'p. [N], entry for Thomas M. Grund' and add 'p. [N]' to FRN and SRN. However, the claim that the FRN's quoted directory line must move to a Transcription note is unsupported: §7 governs the page string only, and Part A makes Transcription notes optional with no rule barring verbatim entry text inside FRN prose (C0046's FRN quotes its entry the same way and was not flagged). Drop the quote-relocation portion; it is at most an optional improvement, not a style violation.
- **[minor] pubinfo** (Part A — Pubinfo grammar — Published-works imprint variant)
  - Pubinfo "Northwestern Bell, Minneapolis, December 1984; reproduced on microfiche by Bell & Howell, PhoneFiche series, item no. 38472." inverts the imprint form; published works take "[City]: [Publisher], year." with an appended format/reproduction clause.
  - **Fix:** Minneapolis: Northwestern Bell, December 1984. Microfiche reproduction, Bell & Howell PhoneFiche 38472.
- **[info] abbrev** (B.3 §10 Abbrev rule)
  - Abbrev "Minneapolis Phone Directory Dec 1984" is missing the comma before the issue date; the directory abbrev pattern (worked example 7, "Polk's Duluth dir., 1900") uses "dir." plus a comma-separated date.
  - **Fix:** Minneapolis phone dir., Dec. 1984
- **[info] · C0046 frn** (Part A — Citation notes structure)
  - FRN quotes the verbatim directory line "\"Grund Marie E 1707 3 Av S...870-4542\"" — verbatim record text belongs in a Transcription note; the worked directory example's FRN names the entry only ("p. 412, Per Larsson Grund").
  - **Fix:** Move the quoted line to a Transcription note and have the FRN read "p. [N], entry for Marie E. Grund"

### S0045 — 1885 Minnesota State Census, Benton County
- **[minor] call_number** (B.3 §5 Locator / volume notation tokens)
  - Call number "image group 004437194" is FamilySearch's platform digitization ID, not Minnesota Historical Society's machine reference; per §5 a platform's collection/image-group ID "is not a call number" and "appears only in the FRN's digital-access clause" — it is already in the FRN ("Image Group 004437194").
  - **Fix:** Blank (or MHS's own microfilm reel reference if known); keep the image group number in the FRN only.
- **[info] · C0055 abstract** (Part A — Citation notes structure)
  - The 1885 state-census household citation (original record, "Par Larsson household") has no Abstract note, while every other census citation in the group (C0025, C0076, C0077) carries one — Abstract is encouraged for primary records.
  - **Fix:** Add an Abstract note (type Abstract) summarizing the Par Larsson household entry
- **[info] author** (B.3 §2 Source author)
  - Author "Minnesota Census Bureau" does not match the template default "[State] Population Census Office" and may not be the body that actually conducted the 1885 Minnesota census (historically run under the Secretary of State); the template permits "the body that conducted that state's census", so this needs verification rather than a mechanical fix.
  - **Fix:** Verify the creating body for the 1885 Minnesota state census; if unverifiable, use the template form "Minnesota Population Census Office".

### S0046 — Norra Ny kyrkoarkiv, Död- och begravningsbok, F:1 (1765-1838)
- **[minor] · C0056 frn** (B.2 §12 Worked examples; Part A — Pubinfo grammar (image-specific URLs go inside the FRN))
  - FRN leads "Norra Ny kyrkoarkiv, Dödbok" — collection-led lead, no "[death book]" gloss, and the series name "Dödbok" contradicts the source's own series "Död- och begravningsbok"; the URL "https://www.arkivdigital.se" is the platform homepage, not the image-specific deep link the FRN must carry (compare the AID deep links in C0033, C0038, C0075).
  - **Fix:** FRN: "Norra Ny församling, Död- och begravningsbok [death and burial book], vol. F:1 (1765–1838), p. 119, death entry for Per Persson, Ambjörbymon; digital image, ArkivDigital ([AID deep link to F:1 p. 119] : accessed 6 May 2026); citing Värmlandsarkiv, SE/VA/13398/F/1."
  - *Verifier adjustment:* The collection-led lead, missing gloss, and homepage-only URL are real defects, but the series-name claim is inverted: B.2 §4 fixes 'Dödbok' as the canonical series name (§12 gloss 'Dödbok [death book]', §10 abbrev 'dödbok'), so the FRN's 'Dödbok' is correct house vocabulary and the legacy Title's 'Död- och begravningsbok' does not override it. Corrected fix: FRN 'Norra Ny församling, Dödbok [death book], vol. F:1 (1765–1838), p. 119, death entry for Per Persson, Ambjörbymon; digital image, ArkivDigital ([AID deep link to F:1 p. 119] : accessed 6 May 2026); citing Värmlandsarkiv, SE/VA/13398/F/1.'

### S0047 — Lake of the Woods County: A History of People, Places, and Events
- **[info] abbrev** (B.4 §10 Abbrev rule (published book: short title + year, examples `Tennessee Women 2009`, `Eidsvoll bygdebok 2:2` — no comma before the disambiguating year))
  - Abbrev "Lake of the Woods County history, 1997" places a comma before the year; the §10 book examples append the year without a comma (comma form is used only for artifact abbrevs like `Siggerud funeral program, 1953`).
  - **Fix:** Lake of the Woods County history 1997
- **[info] · C0048 page** (Part A — Subject formatting in the page string, Parenthetical annotations (parentheticals answer one of three questions: disambiguator / source-state / evidence-quality))
  - The page-string parenthetical "(citing 1915 history in Spooner Northern News)" is layered-source provenance, which is none of the three sanctioned parenthetical categories; the same detail already lives in the FRN ("citing a 1915 history of Pitt published in the Spooner Northern News").
  - **Fix:** Drop the parenthetical from the page string: 'p. 79, "The Pitt Community," Grund boys' sawmill and cedar yards' — the FRN keeps the citing-clause.
- **[info] · C0049 page** (B.4 §7 Citation page templates (chapter template `[Chapter title], pp. [N]–[N]` — en dash in ranges throughout the guide's templates and examples))
  - Page string "\"The Pitt Community,\" pp. 76-82" (and the FRN/SRN in N0099) uses a hyphen in the page range where all house templates and worked examples use an en dash (e.g. "pp. 432–440").
  - **Fix:** "The Pitt Community," pp. 76–82 (also update "pp. 76-82" in the FRN and SRN of note N0099).

### S0048 — Beltrami County District Court, Naturalization Records, 1887-1956
- **[minor] call_number** (B.3 §5 Locator / volume notation tokens)
  - Call number "film 101513828" is the FamilySearch Image Group Number (the FRN says "FamilySearch Image Group Number 101513828"), a platform digitization ID rather than the Minnesota Historical Society's own reference; platform IDs belong only in the FRN's digital-access clause.
  - **Fix:** Blank (or MHS's own microfilm reference if known); keep the Image Group Number in the FRN only.
- **[minor] · C0057 page** (B.3 §7 Citation page templates (Naturalization petition))
  - Page string "Petition no. 961178 vol. 2, p. 77. Louis Grund (witness at Jeppe Mauritz Olsson's naturalization)" runs locators together without a comma ("961178 vol. 2") and separates locators from the subject with a period instead of a comma; the shape is "[locators], [name] ..." with comma-separated locator tokens.
  - **Fix:** Petition no. 961178, vol. 2, p. 77, Louis Grund (witness at Jeppe Mauritz Olsson's naturalization)
- **[minor] · C0058 page** (B.3 §7 Citation page templates (Naturalization petition))
  - Page string "Petition no. 961178 vol. 2, p. 77. Peter L. Grund (witness at Jeppe Mauritz Olsson's naturalization)" has the same punctuation drift as C0057: missing comma before "vol. 2" and a period, not a comma, before the subject.
  - **Fix:** Petition no. 961178, vol. 2, p. 77, Peter L. Grund (witness at Jeppe Mauritz Olsson's naturalization)

### S0049 — Descendants of Grace Haack
- **[minor] scoping** (Part A — Source scoping)
  - "Descendants of Grace Haack" is a contact-tracing To-Do plus contact log ("connected w/ Linda Haack Lomker on Facebook 2026-05-16... she sent me a few stories over facebook messanger"). Not a source, but it wraps two genuine future sources: the Legacy.com obituary (B.3 newspaper/online) and the Lomker correspondence/stories, which B.4 would scope as personal correspondence with Repository "[Custodian], private collection". The note also contains stray test text ("- itesting").
  - **Fix:** Re-parent note N0096 as a To Do note on Grace Haack's person record, delete the stray "itesting" line, delete the Source, and create real Sources for the Legacy.com obituary and the Lomker correspondence when cited.

### S0050 — Personal research of Grace Haack, Grund Family History
- **[major] · C0060 frn** (B.4 §3 Repository (EE 4.24 provenance sentence in the FRN) / Part A — Repository decision tree)
  - The FRN's whereabouts clause says "Grace Haack personal collection", but the Source's repository is R0001 "Peter Grund, private collection" (call number TBD). The current-whereabouts statement in the FRN contradicts the recorded custodian — one of the two is wrong content.
  - **Fix:** End the FRN with the custodian the Source actually records: "…compiled July 1974; typescript privately held by Peter Grund, Duluth, Minnesota." (If Grace Haack's family genuinely holds the original and Peter holds only a copy, say both — "original privately held by [Haack custodian]; copy privately held by Peter Grund" — and fix the repository to match.)
- **[major] · C0060 frn** (Part A — Citation notes structure)
  - No FIRST REFERENCE NOTE / SHORT REFERENCE NOTE block ('Citation' + 'General' notes present but no FRN/SRN block). FRN and SRN are required for every citation.
  - **Fix:** Compose the FRN/SRN per the domain chapter (bifrost's citation composer can draft it) and store in a Citation-type note.
- **[minor] call_number** (Part 0 — Gramps field map (Call number = "The archive's machine reference only"); Part A — Two-forms-two-homes locator)
  - Call number is "TBD" — a placeholder, not an archive machine reference; the field must hold the machine reference and nothing else.
  - **Fix:** Replace with the actual private-archive object/scan ID once assigned, or leave the call number blank until then.
- **[minor] · C0060 frn** (Part A — Citation notes structure (Required for every citation: FIRST REFERENCE NOTE (FRN)))
  - Note N0102 labels the block "FULL REFERENCE NOTE:" — a nonstandard heading; every other citation in the group and the house style use "FIRST REFERENCE NOTE:".
  - **Fix:** Rename the heading to "FIRST REFERENCE NOTE:".
- **[minor] · C0060 frn** (B.4 §12 Worked examples — Personal research from another genealogist (prose-form dates: "accumulated 2024–2026", "received … 30 April 2026"))
  - The FRN reads "Grace Haack, personal research on Grund Family History, Axel Grund, Marshall, 1974-07; …" — an ISO date fragment ("1974-07") in citation prose, and a comma-spliced string in which "Axel Grund" floats without a role. House FRNs use prose dates and full sentences.
  - **Fix:** Grace Haack, "Grund Family History," unpublished typescript compiled July 1974, Marshall, Minnesota; Axel Grund entry, pp. 1–2; typescript privately held by Peter Grund, Duluth, Minnesota.
- **[minor] · C0060 note_type** (Part A — Citation notes structure (Transcription = "the verbatim text of the record entry"))
  - Note N0002 is typed "General" but its content is the full transcription of Haack's 1974 typescript ("GRUND FAMILY HISTORY / original written July 1974 by Grace Haack / Transcribed January 2026 by Peter Michael Grund…"). Its header also admits "Minor grammatical changes made", so it is not strictly verbatim.
  - **Fix:** Change note N0002's type from General to Transcription, and keep the text verbatim with any editorial emendations marked in [square brackets].
- **[minor] · C0060 page** (B.4 §7 Citation page templates — Personal research (`[topic or section], [page if compiled into a document]`))
  - Page string "pp. 1-2, Grund Family History, compiled July 1974" is page-first with no subject, uses the source's own title as the topic, and duplicates the compile date (which lives in Pubinfo/FRN). It is also inconsistent with the group-mate C0042 ("Entry for Ambmyra, typed page, received 30 April 2026"), which correctly leads with the topic. The FRN/SRN show the actual topic is Axel Grund.
  - **Fix:** Axel Grund entry, pp. 1–2
- **[minor] pubinfo** (B.4 §6 Pubinfo (personal research: `Unpublished research, [location], [year-range].`; all Pubinfo dates in the chapter's templates and worked examples use prose form, e.g. `16 February 1953`, `12 March 2024`))
  - Pubinfo is "Unpublished research, Marshall, 1974-07." — the date is in ISO `1974-07` form where the house Pubinfo forms use prose dates, and "Marshall" is an incomplete location (city vs. Marshall County, and no state).
  - **Fix:** Unpublished research, Marshall County, Minnesota, July 1974. — confirm whether "Marshall" means the city or Marshall County before finalizing.
- **[minor] repository** (B.4 §3 Repository ("Personal research from another genealogist → The researcher", e.g. `Siw Alfreddson, personal collection`); Part A — Repository decision tree step 2)
  - Repository is "Peter Grund, private collection", but §3 assigns personal-research compilations to the researcher's collection, and the source's own C0060 FRN says "Grace Haack personal collection" — the Source and its citation prose currently name different custodians.
  - **Fix:** Link the repository "Grace Haack, personal collection"; if Peter in fact now holds the original 1974 document (he transcribed it in January 2026), use "Peter Michael Grund, private collection" instead and reconcile the FRN — either way the Source and FRN must agree.

### S0051 — Norra Ny kyrkoarkiv, Flyttningslängder, B:2 (1861-1883)
- **[minor] · C0061 frn** (B.2 §12 Worked examples; B.2 §4 Source title (old collection-led note))
  - FRN leads "Norra Ny kyrkoarkiv, Flyttningslängder [migration registers]" — collection-led lead. The sibling citation on the same series, C0075 (S0073, B:3), correctly leads "Norra Ny församling, Flyttningslängder [migration registers]"; the same series is cited two different ways within the group.
  - **Fix:** Change the FRN opening to "Norra Ny församling, Flyttningslängder [migration registers], vol. B:2 (1861–1883), ..." (rest unchanged).
- **[minor] · C0061 frn** (Part A — Pubinfo grammar (collection/image-specific URLs go inside the FRN))
  - FRN URL "https://www.arkivdigital.se : accessed 19 May 2026" is the platform homepage; the FRN should carry the image-specific deep URL (as C0075 does for the same series: an /aid/show/ link).
  - **Fix:** Replace with the ArkivDigital deep link for B:2 p. 220 image 117, e.g. "digital image, ArkivDigital (https://www.arkivdigital.se/aid/show/v[...].b117.s220 : accessed 19 May 2026)".

### S0052 — Star Tribune, Minneapolis, Minnesota
- **[major] · C0062 confidence** (B.3 §8 Confidence guidance (per record type))
  - Confidence is Very High (4) for a newspaper death notice. §8: "Newspaper funeral notices = High for the death and funeral; Normal for any biographical detail" and "Newspaper obituaries = Normal at best ... family-supplied and unverified by the newspaper." Very High is not available for either reading of this item.
  - **Fix:** Set confidence to 3 (High) if treated as a funeral notice supporting the death/funeral facts, or 2 (Normal) if treated as an obituary
- **[minor] · C0062 frn** (B.3 §12 Worked example 8: a newspaper obituary)
  - FRN "\"Funeral Notices\", Star Tribune (Minneapolis, Minnesota), 3 June 1987, p. 22; digital image, ..." never names Marie Siggerud — nothing identifies which notice on the page — and omits the column number; the worked examples always identify the subject in the FRN ("marriage announcement of Louis Grund and Anna Amelia Hoiberg", "Peter Grund mention").
  - **Fix:** "Funeral Notices," Star Tribune (Minneapolis, Minnesota), 3 June 1987, p. 22, col. [N], funeral notice for Marie Siggerud; digital image, Newspapers.com (https://www.newspapers.com/image/191502533/ : accessed 20 May 2026).
- **[minor] · C0062 page** (B.3 §7 Citation page templates (Newspaper funeral notice / obituary))
  - Page string "3 June 1987, p. 22, Marie Siggerud obituary" omits the "col. [N]" token required by every newspaper template, and the record-noun "obituary" conflicts with the FRN's own quoted column title "Funeral Notices" — a funeral notice takes the record-noun "funeral notice" (§9).
  - **Fix:** 3 June 1987, p. 22, col. [N], Marie Siggerud funeral notice — keep "obituary" only if the item is genuinely an obituary, and align the SRN noun to match

### S0054 — Marisa Lova, "Battesimi dal 1880 al 1889" (trascrizione integrata), Parrocchia di San Bartolomeo, Vistrorio
- **[major] · C0066 frn** (Part A — Citation notes structure (FRN = "the full citation in EE-style prose, including the URL with access date in parentheses"))
  - The FRN's URL parenthetical is a literal placeholder: "PDF (... : accessed 2026-05-31)". The deep URL was elided with "...", so the note is not a self-contained full citation.
  - **Fix:** Replace with the actual URL and a prose-form date: "PDF (https://sanbartolomeovistrorio.jimdofree.com/pubblicazioni-e-archivio/ : accessed 31 May 2026)".
- **[major] pubinfo** (Part A — Pubinfo grammar ("URL — the platform homepage only. Collection-specific and image-specific URLs go inside the citation's First Reference Note, never on the Source."))
  - Pubinfo carries a deep URL: "(https://sanbartolomeovistrorio.jimdofree.com/pubblicazioni-e-archivio/)" — a collection-specific page, not the platform homepage. Deep URLs on the Source are a hard-rule violation; the page-specific URL already lives in the C0065/C0066 FRNs.
  - **Fix:** Trascrizione online (PDF), Parrocchia di San Bartolomeo (https://sanbartolomeovistrorio.jimdofree.com).
- **[major] title** (Part 0 — Gramps field map (author lives in Source author); B.4 §4 Source title (authored works are cited by `[Title]`))
  - Title is "Marisa Lova, \"Battesimi dal 1880 al 1889\" (trascrizione integrata), Parrocchia di San Bartolomeo, Vistrorio" — it leads with the author's name, duplicating the Author field ("Marisa Lova"). The field map puts the creator in Source author only; §4 titles for authored works are the work title itself (author-led titles are the same defect as the superseded creating-body-led forms).
  - **Fix:** Battesimi dal 1880 al 1889 (trascrizione integrata), Parrocchia di San Bartolomeo, Vistrorio
- **[minor] abbrev** (B.4 §10 Abbrev rule ("short, readable, work-title-led short cite"; author-led forms are for the SRN, "the Abbrev stays title-only"))
  - Abbrev is "Lova, Battesimi Vistrorio 1880-1889" — author-surname-led. §10 requires the Abbrev to lead with the work title (cf. `Eidsvoll bygdebok 2:2`, `Tennessee Women 2009`); the author-led form belongs in the SRN, which already uses it. Year-range also uses a hyphen instead of an en-dash.
  - **Fix:** Battesimi Vistrorio 1880–1889
- **[minor] · C0065 confidence** (B.4 §8 Confidence guidance (Normal: "personal-research compilations citing primary records"; Low only "without sources") / Part A — Confidence (Normal: derivative source carrying primary information))
  - Confidence is 1 (Low), but the FRN itself records that the compiler cites her primary source: "transcribed from the parish baptismal register, original at Archivio di Stato di Torino". A derivative transcription that names its primary record is prescribed Normal, not Low.
  - **Fix:** Set confidence to 2 (Normal).
- **[minor] · C0065 frn** (Part A — Citation date (access-date form "accessed 21 April 2026") / B.4 §12 worked examples (all dates in prose form, e.g. "accessed 26 April 2026", "born 14 January 1848"))
  - The FRN uses ISO and abbreviated dates: "accessed 2026-05-31" and "born 11 Jan 1888". Every house example writes dates in prose form, and group-mate C0043 already uses "accessed 26 April 2026" — inconsistent within the group.
  - **Fix:** Use "accessed 31 May 2026" and "born 11 January 1888".
- **[minor] · C0066 page** (Part A — Combining parentheticals (unified order): "combine them into a single set of parentheses, comma-separated, in this order: disambiguator → source-state → evidence-quality")
  - The page string carries two separate parentheses: "Castellano (Michele b. 1888) entry, parents' birth and death dates and marriage (compiler's augmentation from other parish registers)" — a disambiguator and an evidence-quality flag that must be combined into one parenthesis.
  - **Fix:** ANNO 1888, PDF p. 66, Castellano parents' vitals annotation (Michele b. 1888 baptism entry, compiler's augmentation from other parish registers)
- **[minor] title** (Part 0 — Gramps field map)
  - S0054's Title embeds the author: "Marisa Lova, \"Battesimi dal 1880 al 1889\" (trascrizione integrata), Parrocchia di San Bartolomeo, Vistrorio" while author="Marisa Lova" is already in the Author field — unlike other authored works (S0042, S0047) whose titles carry the title only.
  - **Fix:** Trim the Title to "\"Battesimi dal 1880 al 1889\" (trascrizione integrata), Parrocchia di San Bartolomeo, Vistrorio", leaving Marisa Lova in the Author field only.
- **[info] · C0065 frn** (B.4 §4 Source title (EE 2.28: bracketed English gloss "encouraged in the FRN"))
  - The FRN gives the Italian title "Battesimi dal 1880 al 1889" with no bracketed English gloss on first use (same omission in C0066's FRN).
  - **Fix:** Insert "[Baptisms from 1880 to 1889]" after the title in the FRN: "Battesimi dal 1880 al 1889\" [Baptisms from 1880 to 1889] (augmented transcription), …"
- **[info] pubinfo** (Part A — Pubinfo grammar (medium vocabulary: `Digital images` / `Database with images` / `Database`))
  - The medium descriptor "Trascrizione online (PDF)" is in Italian; Part A's medium vocabulary is English, though it lists no term for an online transcription PDF, so the guide is silent on this exact medium.
  - **Fix:** Consider the English descriptor "Online transcription (PDF), Parrocchia di San Bartolomeo (https://sanbartolomeovistrorio.jimdofree.com)." for consistency with the Part A medium vocabulary.

### S0055 — Boise City Directory, 1923
- **[minor] pubinfo** (B.3 §6 Pubinfo)
  - Pubinfo "Digital images, Ancestry (https://www.ancestry.com)." omits the required imprint; for city directories "Pubinfo takes the imprint variant '[City]: [Publisher], year. Digital images, [Platform] (URL).'" (worked example 7).
  - **Fix:** Boise: R. L. Polk & Co., 1923. Digital images, Ancestry (https://www.ancestry.com).
- **[minor] title** (B.3 §4 Source title)
  - Title "Boise City Directory, 1923" omits the publisher lead; the city-directory template is "[Publisher] [city] City Directory, [year]" and the citation's own FRN reads "Polk's Boise City Directory, 1923".
  - **Fix:** Polk's Boise City Directory, 1923
- **[info] abbrev** (B.3 §10 Abbrev rule)
  - Abbrev "Boise dir., 1923" drops the publisher that the worked-example pattern keeps ("Polk's Duluth dir., 1900").
  - **Fix:** Polk's Boise dir., 1923
- **[info] · C0067 page** (B.3 §7 Citation page templates (City directory))
  - Directory page strings use two different subject styles within the group: C0067 has "p. 146, J. Edwin Grund directory entry" (the §9 subject-vocabulary form) while the S0044 directory citations use §7's template form "entry for [Name]" — same record type, two styles (the §7 page template prescribes "p. [N], entry for [Name]"; the style itself shows both forms, so this is a consistency call).
  - **Fix:** Standardize directory page strings on one form group-wide, preferably §7's "p. 146, entry for J. Edwin Grund"
  - *Verifier adjustment:* The inconsistency is real (C0067 'p. 146, J. Edwin Grund directory entry' vs. S0044's 'entry for Marie E. Grund'/'entry for Thomas M. Grund', and the style does show both forms), but the fix prefers the wrong form. Part A's shared subject grammar is '[locators], [name] [record-noun]', B.3 §9 explicitly prescribes '[Given Surname] directory entry' for city directories, and Worked example 7's page string is 'p. 412, Per Larsson Grund directory entry'. Since Part 0 says chapters must not contradict Part A, the §7 table row 'p. [N], entry for [Name]' is the internal outlier. Corrected fix: standardize group-wide on the Part A/§9/example-7 form — change S0044's C0046/C0047 to '..., Marie E. Grund directory entry' / '..., Thomas M. Grund directory entry' and keep C0067 as-is; do NOT rewrite C0067 to 'entry for J. Edwin Grund'.

### S0056 — May Research Update
- **[minor] scoping** (Part A — Source scoping)
  - "May Research Update" is a database-statistics narrative ("May was a busy month on the tree: I added 404 new records total..."), a blog post rather than a source; it matches no unit in the scoping table, has zero citations, and would pollute the bibliography per Part A Bibliography mapping.
  - **Fix:** Keep as a Gramps Web blog post but tag it (e.g. 'blog'/'no-biblio') and exclude tagged Sources from the bibliography transform.

### S0057 — FT 1885 dwelling pages for Sofiegade 12
- **[minor] scoping** (Part A — Source scoping)
  - "FT 1885 dwelling pages for Sofiegade 12" is a research To-Do ("Read the scanned FT 1885 dwelling pages... apartment by apartment; then run citywide sweeps for Thor..."). It wraps genuine future sources — the 1885 folketelling for Kristiania and for Kongsberg, each one Source per jurisdiction under Norwegian scoping ("a folketelling for a jurisdiction") — and its source-like title risks being mistaken for the census Source itself.
  - **Fix:** Re-parent note N0126 as a To Do note on the relevant persons (Thor, Indiana) and delete the Source; create locality-led folketelling Sources (e.g. "Norway, ..., Kristiania, folketelling 1885") when citing.

### S0058 — Eidsvoll klokkerbøker
- **[minor] scoping** (Part A — Source scoping)
  - "Eidsvoll klokkerbøker" is a To-Do ("Confirmations 1862-76 (Indiana, if b. 1848-51)... utflytting lists 1866-77...") masquerading under a title in the superseded collection-led Scandinavian form — it reads exactly like a real (old-style) source and is the most confusable record in this group. The genuine future sources are the individual Eidsvoll klokkerbok volumes, one Source per volume, titled locality-led per Part A Title philosophy (e.g. "Norway, Akershus, Eidsvoll, parish registers, Klokkerbok I 2, [years]").
  - **Fix:** Re-parent note N0127 as a To Do note on Indiana's person record and delete the Source; create one locality-led Source per klokkerbok volume when citing.

### S0059 — Kommunikantbok confirmand lists
- **[minor] scoping** (Part A — Source scoping)
  - "Kommunikantbok confirmand lists" is a To-Do ("Kommunikantbok confirmand lists 1834-1880 via the Thingvold photographs..."). It wraps a genuine future source — the Eidsvoll kommunikantbok volume(s), a parish-office volume series under Norwegian scoping, possibly with the Thingvold photograph set as access medium in Pubinfo/FRN — but the task record itself is not a source and pollutes the bibliography.
  - **Fix:** Re-parent note N0128 as a To Do note (person or family level) and delete the Source; create the per-volume kommunikantbok Source with locality-led title when the lists are consulted.

### S0060 — Siggerud farm paper trail
- **[minor] scoping** (Part A — Source scoping)
  - "Siggerud farm paper trail" is a To-Do ("Panteregister and pantebok entries for the 1845 deed, 1855 reconveyance... dødsfallsprotokoll 1863-1910"). It wraps several genuine future sources — panteregister, pantebok, auction protocol, overformynderi case files, dødsfallsprotokoll — each a sorenskriveri volume series that Norwegian scoping makes its own Source. The umbrella task record matches no unit and pollutes the bibliography.
  - **Fix:** Re-parent note N0129 as a To Do note on the Siggerud farm/family records and delete the Source; create one Source per court volume series when the records are found.

### S0061 — Kristiania burials and deaths
- **[minor] scoping** (Part A — Source scoping)
  - "Kristiania burials and deaths" is a To-Do ("Sweep Kristiania burials and deaths for Indiana, 1875-1900, east-side parishes first..."). The genuine future sources are the individual Kristiania parish burial registers and skifte protocols (one Source per parish-office volume under Norwegian scoping); the sweep task itself is not a source.
  - **Fix:** Re-parent note N0130 as a To Do note on Indiana's (and Even's/Marte's) person records and delete the Source.
  - *Verifier adjustment:* Issue and fix are real (S0061 is a To Do wrapped as a Source; re-parent N0130 and delete), but the scoping parenthetical is wrong: only the Kristiania parish burial registers are parish-office volumes; skifte protocols scope as court (skifterett/byskriver, the scoping table's skifteprotokoll-series) volume series, not parish-office volumes. Corrected issue wording: 'the genuine future sources are the individual Kristiania parish burial registers (one Source per parish-office volume) and the Kristiania skifterett skifteprotokoll series (one Source per court volume series under Norwegian scoping)'.

### S0062 — Gulbrand Evensen in Australia
- **[minor] scoping** (Part A — Source scoping)
  - "Gulbrand Evensen in Australia" is a To-Do ("Trace Gulbrand Evensen in Australia: state BDM indexes, NAA naturalization index, Trove newspapers."). It wraps genuine future sources, but note that Australian records fall outside all four domains of the house style (Norwegian, Swedish, US, Published & Personal) — when these are found, the master has no chapter for them and will need extension (an info-level gap).
  - **Fix:** Re-parent note N0131 as a To Do note on Gulbrand Evensen's person record and delete the Source; when Australian records are cited, extend the house style (or apply Part A conventions with EE general principles) rather than forcing them into an existing chapter.

### S0063 — Karine's marriage
- **[minor] scoping** (Part A — Source scoping)
  - "Karine's marriage" is a To-Do ("Karine's marriage (gives Christiane's surname), then the 1900 and 1910 censuses including institutions; Johan Peter via military rolls..."). It wraps genuine future sources spanning two domains (Norwegian marriage register and military rolls; US censuses for the Killingmo search), but as a title-only Source it would emit the meaningless bibliography line "Karine's marriage."
  - **Fix:** Re-parent note N0132 as a To Do note on Karine's person record and delete the Source; create per-volume/per-county Sources in the appropriate domain when each record is found.

### S0064 — Botsfengslet (Kristiania), Fangeprotokoll nr. 36 (1901-1902)
- **[major] pubinfo** (Part A — Pubinfo grammar; B.1 §6 Pubinfo)
  - Pubinfo "Digital images, Digitalarkivet (https://www.digitalarkivet.no); citing Arkivverket (Nasjonalarkivet), Oslo." appends a citing clause (with the rejected Nasjonalarkivet name); the grammar is strictly "[medium], [platform] (homepage URL)." — the holding archive belongs in the Repository field and the FRN, not Pubinfo.
  - **Fix:** Digital images, Digitalarkivet (https://www.digitalarkivet.no).
- **[major] title** (Part A — Title philosophy; B.1 §4 Source title)
  - Title "Botsfengslet (Kristiania), Fangeprotokoll nr. 36 (1901-1902)" is creating-body-led, not locality-led largest-jurisdiction-first, and puts the year-range in parentheses with a hyphen — §4 requires the year-range directly after the volume identifier without parentheses, with an en dash.
  - **Fix:** Norway, Kristiania, Botsfengslet, Fangeprotokoll 36, 1901–1902 (derived by analogy to the §4 court-records template "Norway, [Fylke/Amt], [creating body], [series] [identifier], [year-range]")
- **[minor] abbrev** (B.1 §10 Abbrev rule; Part A — Universal SRN abbreviations)
  - Abbrev "Botsfengslet fangeprotokoll nr. 36 (1901-1902)" uses a hyphen instead of an en dash in the year-range, and "nr." instead of the universal locator abbreviation "no." (Part A table) — the §10 patterns cite bare volume identifiers ("tingbok A I 5").
  - **Fix:** Botsfengslet fangeprotokoll 36 (1901–1902)
- **[minor] author** (B.1 §2 Source author (no-prefix principle, Part 0 Gramps field map))
  - Author "Botsfengslet (Kristiania, Norway)" carries a country marker; the field map prescribes the creating body alone with "No country or umbrella prefix" (compare §2 court example "Eidsvoll sorenskriveri" with no parenthetical). Locality context moves to the locality-led Title.
  - **Fix:** Botsfengslet
- **[minor] · C0069 frn** (B.1 §11 Bibliography specifics / §12 worked examples (bracketed English gloss on first use, EE 2.28))
  - FRN in N0136 cites "Fangeprotokoll nr. 36 (30 August 1901 – 26 May 1902)" with no bracketed English gloss on first use of the foreign series name.
  - **Fix:** Fangeprotokoll [prison register] no. 36 (30 August 1901 – 26 May 1902), …
- **[minor] · C0069 frn** (B.1 §2 Source author ("Riksarkivet is written bare, not Nasjonalarkivet (Riksarkivet)"); §12 worked examples' citing-clause form)
  - FRN citing clause reads "citing Arkivverket (Nasjonalarkivet), Oslo, archive reference AV/RA-S-1539/D/Db/Dbb/L0036" — a doubled agency name, wrong under either naming outcome.
  - **Fix:** Cite the single decided name: "citing Nasjonalarkivet, Oslo, archive reference AV/RA-S-1539/D/Db/Dbb/L0036" (or the pre-merger form if the master keeps historical naming).
- **[minor] · C0069 page** (Part A — Universal SRN abbreviations (p. = page); Part A — Subject formatting in the page string)
  - Page string "side 175, entry for Thomas Wilhelm Samuelsen Killingland" uses the Norwegian locator token "side" instead of the universal "p.", and reverses the subject shape ("entry for [name]" instead of `[name] [record-noun]`).
  - **Fix:** p. 175, Thomas Wilhelm Samuelsen Killingland prisoner entry — apply the same s/side/p./ correction inside the FRN prose of N0136; B.1 prescribes no record-noun for prison protocols, so mark the chosen noun pending review.
- **[minor] · C0069 srn** (Part A — Universal SRN abbreviations)
  - SRN "Botsfengslet fangeprotokoll nr. 36, side 175, Thomas Wilhelm Samuelsen Killingland." uses Norwegian tokens "nr." and "side" where the universal abbreviations table prescribes "no." and "p." in all citation forms.
  - **Fix:** Botsfengslet fangeprotokoll no. 36, p. 175, Thomas Wilhelm Samuelsen Killingland.
- **[info] · C0069 abstract** (Part A — Citation notes structure (Abstract optional, encouraged for primary records))
  - Citation on an original prison protocol has no Abstract note; the record detail (the mother named as "pige Indiana Evensen Sigerud") is carried only inside the FRN.
  - **Fix:** Add a note of type Abstract summarizing the protocol entry (admission details and the mother's name as recorded), keeping the FRN to citation prose plus the evidence-quality explanation.
- **[info] repository** (B.1 §2/§3 vs. the 2026 archive-law merger)
  - Repository "Nasjonalarkivet" conflicts with the pre-merger institution names the written master (B.1 §2/§3) prescribes for this volume's AV/… call-number prefix. Pending the Nasjonalarkivet naming decision (see the catalog-wide repository finding): on 1 January 2026 the new archive law merged Arkivverket, Riksarkivet and the statsarkivene into one agency, Nasjonalarkivet — so the master's pre-merger names are stale on its own "follow the current naming" rationale.
  - **Fix:** Recommended: update house_style_master.md B.1 §2/§3 and the §11–§12 worked examples to Nasjonalarkivet — this field then already conforms. Either way, remove the digitalarkivet.no platform URL from repository record R0009 (platform ≠ repository).
- **[info] scoping** (B.1 §1 Scope & record types covered)
  - A prison protocol (fangeprotokoll) is not among the record types B.1 covers (parish, census, court, probate, land, religious-practice). It is still a Norwegian archival volume, so B.1 is the right domain chapter — no other domain guide fits — but no title/page/confidence template exists for it.
  - **Fix:** Keep the source under B.1 and derive a fangeprotokoll template by analogy to the court-records (§4/§7) pattern, marked "(newly derived — pending review)" as the chapter does for religious-practice records.
- **[info] scoping** (B.1 §1 Scope & record types covered)
  - Botsfengslet fangeprotokoll (prison protocol) is a Norwegian record correctly under Part B.1, but B.1 §1/§7 cover only parish, folketelling, tingbok, skifteprotokoll, matrikkel, and religious-practice records — there is no template or confidence guidance for prison protocols, so C0069's forms can only be audited against Part A generics.
  - **Fix:** Add a pending-review fangeprotokoll record-type row to B.1 (author, page template with p./entry tokens and a prescribed record-noun, §8 confidence guidance) so future prison-record citations have an anchor.

### S0065 — Københavns Politi, Politiets registerblade, Station 4
- **[minor] author** (B.2 §2 Source author (Swedish-guide principles for Danish records))
  - Author "Københavns Politi (Copenhagen Police)" carries a parenthetical English gloss; §2: "No parentheticals … The parish or court name alone is the author." The gloss belongs in the FRN on first use.
  - **Fix:** Københavns Politi
- **[minor] · C0078 page** (Part A — Subject formatting in the page string)
  - Page string "filmrulle 0005, registerblad 795 (unikt id 114962), Indiana Marie Evensen" ends in a bare name; the subject must be "[name] [record-noun]". The SRN subject ("registerblad 795, Indiana Marie Evensen.") has the same gap.
  - **Fix:** Page: "filmrulle 0005, registerblad 795 (unikt id 114962), Indiana Marie Evensen police register card"; SRN: "Politiets registerblade, Station 4, registerblad 795, Indiana Marie Evensen police register card."
- **[minor] pubinfo** (Part A — Pubinfo grammar)
  - Pubinfo "Database with images, Københavns Stadsarkiv, KBHarkiv (https://kbharkiv.dk)." names two platforms; the grammar is "[medium], [platform] (homepage URL)." — the Stadsarkiv is the repository (already in the Repository field), the platform is KBHarkiv.
  - **Fix:** Database with images, KBHarkiv (https://kbharkiv.dk).
- **[info] · C0078 frn** (B.2 §12 Worked examples (bracketed glosses per EE 2.28))
  - FRN glosses the author in parentheses — "Københavns Politi (Copenhagen Police)" — while the same FRN glosses the series in house-style square brackets ("Politiets registerblade [police register pages]"); glosses are inconsistent within one note.
  - **Fix:** Use square brackets for both: "Københavns Politi [Copenhagen Police], ...".
- **[info] scoping** (Part 0 — Front matter (Scope: four domains); house rule — Nordic records without a dedicated guide follow the Swedish guide principles)
  - S0065 (Københavns Politi registerblade) is Danish; no Part B chapter covers Denmark, so B.2 §7/§8 per-record-type templates cannot strictly apply (there is no registerblad page template or confidence row). The citation was audited for Part A conformance and Swedish-guide principles and is largely conformant (creating-body lead, gloss, deep permalink with access date, facts confined to the Abstract).
  - **Fix:** No action needed beyond the specific findings; consider adding a short Danish record-type row (registerblade page template, default confidence) to the master if more Danish records are expected.
  - *Verifier adjustment:* The scoping observation is real: S0065 is Danish (Københavns Politi registerblade), Part 0 scopes exactly four domains with no Danish chapter, so B.2 §7/§8 templates cannot strictly apply; the C0078 conformance observations check out (creating-body lead, '[police register pages]' gloss, permalink with access date, facts in Abstract N0255). But the cited 'house rule — Nordic records without a dedicated guide follow the Swedish guide principles' does not exist anywhere in the master or B.2; the correct citation is Part 0 Scope plus Part A common conventions only, with Swedish-guide analogy being auditor's discretion, not a house rule. The no-action outcome and the suggestion to add a Danish record-type row stand.

### S0066 — Idaho Birth Records, 1861-1924
- **[major] · C0070 frn** (B.3 §4 Source title — state-vitals lead form (title and FRN both lead with the state))
  - FRN uses the explicitly superseded body-led lead: "Idaho Department of Health, certificate of birth no. 00115862 (1923), Douglas Clyde Grund; digital image, ...". §4 sets the body-led form aside: "the title and FRN both lead with the state (the largest jurisdiction)" — cf. Worked example 2 ("Minnesota, death certificate no. ... ; Minnesota Department of Health, Vital Records; ...").
  - **Fix:** Idaho, birth certificate no. 00115862 (1923), Douglas Clyde Grund; Idaho Department of Health, Vital Records; digital image, Ancestry (https://www.ancestry.com/search/collections/8973/records/105815887 : accessed 12 June 2026), "Idaho, U.S., Birth Records, 1861-1924, Stillbirth Index, 1872-1974," image 1703 of 2846; citing Idaho Department of Health and Welfare, Boise.
- **[minor] title** (B.3 §4 Source title)
  - Title "Idaho Birth Records, 1861-1924" lacks the locality-led comma form; state birth collections are "[State], [record series], [year-range]" with the series lowercased (template example "Minnesota, birth records, 1900–1934").
  - **Fix:** Idaho, birth records, 1861–1924
- **[info] · C0070 abstract** (Part A — Citation notes structure)
  - An original state birth certificate (Very High confidence, image attached) has no Abstract note; Abstract is encouraged for primary records and the certificate's content (parents, birthplace, exact dates) is captured nowhere in the notes.
  - **Fix:** Add an Abstract note summarizing the certificate: child, birth date/place, parents, informant/attendant

### S0067 — John C. Grund narration of family photograph album, February 2003
- **[minor] pubinfo** (B.4 §6 Pubinfo (audio interview: `Recorded interview, [city], date.`; online video: `Online video, [Platform] (homepage URL), year.`); Part A — Pubinfo grammar (layered digital-provider clause; provenance detail belongs in the FRN))
  - Pubinfo is "Audio recording, February 2003; online video, YouTube (https://www.youtube.com), uploaded by Jeff Grund 1 September 2023." — the recording layer omits the city required by the §6 template, and the uploader-plus-full-upload-date prose ("uploaded by Jeff Grund 1 September 2023") is FRN-level detail; the video layer's template slot is a year.
  - **Fix:** Recorded narration, [city], February 2003. Online video, YouTube (https://www.youtube.com), 2023. — move "uploaded by Jeff Grund 1 September 2023" into the FRN when citations are added.
- **[minor] repository** (B.4 §3 Repository ("Audio interviews → The recording/transcript custodian"); Part A — Repository decision tree step 2)
  - Repository is blank for an audio recording of a family informant. §3 assigns audio recordings the recording custodian (`[Custodian], private collection`); the blank-Repository exception applies only when the material is cited solely from an online platform.
  - **Fix:** Add the recording custodian as Repository, e.g. "Jeff Grund, private collection" (he holds/uploaded the 2003 recording); leave blank only if the source is cited exclusively from the YouTube upload.

### S0068 — Emma S. birth date confirmation
- **[minor] scoping** (Part A — Source scoping)
  - "Emma S. birth date confirmation" is a conflict-resolution To-Do ("Was Emma S. born on 23 or 28 Dec 1855? Ancestry says 28 but I need to check Arkivdigital"). The genuine future source is the Swedish parish birth/baptism book accessed via ArkivDigital (one Source per kyrkoarkiv volume under Swedish scoping); the question itself is not a source, and the eventual conflict analysis belongs in the citation's FRN prose or Abstract per Part A Citation notes structure.
  - **Fix:** Re-parent note N0218 as a To Do note on Emma Söderström's person record and delete the Source; when resolved, cite the Swedish födelsebok volume as a proper Source and record the 23-vs-28 Dec discrepancy analysis in that citation's notes.

### S0069 — Norway, Buskerud, Kongsberg, folketelling 1875
- **[minor] call_number** (B.1 §3 Repository (prefix table); B.1 §5 Locator / volume notation tokens)
  - Call number "AV/SAKO-A-1102/F/Fb" is a Statsarkivet i Kongsberg parish-fond-shaped reference on a folketelling Source, contradicting the §3 mapping of folketelling to Riksarkivet with an AV/RA- prefix (the sibling 1875 censuses S0038/S0077 carry AV/RA-S-2231/E).
  - **Fix:** Verify the fond in Digitalarkivet's NAD entry for the 1875 Kongsberg census; expected value is AV/RA-S-2231/E (with Repository "Riksarkivet"). If AV/SAKO-A-1102/F/Fb was copied from a Kongsberg parish-register fond, replace it.
  - *Verifier adjustment:* Issue and fix are correct: a folketelling Source carrying AV/SAKO-A-1102/F/Fb conflicts with the §3/§5/§11 folketelling form AV/RA-S-2231/E used by siblings S0038/S0077, and NAD verification is the right remedy. But 'parish-fond-shaped' is unsupported: the style's own examples show the A-####/F/Fx shape on a sorenskriveri (court) fond (AV/SAO-A-10063/F/Fa/L0005), and citation C0071's FRN itself cites 'Statsarkivet i Kongsberg, AV/SAKO-A-1102/F/Fb', so the reference may be a deliberate regional-holding claim rather than a parish-fond copy error. Corrected wording: regional SAKO fond reference of undetermined series type on a folketelling Source; verify in NAD and reconcile with the repository finding.
- **[minor] · C0071 note_type** (Part A — Citation notes structure (Abstract = a summary of what the record contains))
  - Note N0232 (type "General") is headed "ABSTRACT:" but its content — "The old address Ekermogade 379 corresponds to the modern-day street named Eikerveien in Kongsberg." — is modern-address commentary, not an abstract of the census entry.
  - **Fix:** Remove the "ABSTRACT:" heading and keep the address equivalence as a plain research note; if an Abstract is wanted, add a separate note of type Abstract that actually summarizes the household entry (members, ages, occupations as recorded).
- **[minor] · C0071 page** (B.1 §7 Citation page templates — Folketelling (decennial 1865+); scope cross-citation consistency)
  - Page string "District 005, Ekermogade 379 (urban residence 0407), household 03, …" substitutes a street address for the template's `p. [N] … person [N]` tokens; sibling folketelling-1875 citations (C0041 on S0038, C0080 on S0077) keep the p./person tokens and put the street address in the FRN only.
  - **Fix:** District 005, p. [P], household 03, person [N], Even Juul Jørgensen Siggerud household — move "Ekermogade 379 (urban residence 0407)" out of the page string; the address is already in the FRN.
  - *Verifier adjustment:* Issue is real and the rule citation is correct: C0071's page string drops the B.1 §7 decennial template's 'p. [N]' and 'person [N]' tokens and inserts a street address, while siblings C0041 and C0080 keep the tokens and C0080 puts its urban address ('urban residence 1321 Incognitogade 33') in the FRN only. But the fix's premise 'the address is already in the FRN' is only half-true: N0226 contains 'Ekermogade 379' but NOT the residence number '0407', so simply deleting '(urban residence 0407)' from the page string would lose that locator. Corrected fix: page → 'District 005, p. [P], household 03, person [N], Even Juul Jørgensen Siggerud household', and move the residence number into the FRN alongside the street address, mirroring C0080's 'urban residence 1321 Incognitogade 33' phrasing (e.g. 'census district 005, urban residence 0407 Ekermogade 379, …').
- **[minor] · C0071 srn** (B.1 §12 Worked example 2 SRN form; scope cross-citation consistency)
  - SRN opens "Kongsberg folketelling 1875, district 005, …" while every other folketelling SRN in the group (S0038, S0076, S0077, S0071) uses the "Folketelling [year], [locality], …" order from Worked example 2.
  - **Fix:** Folketelling 1875, Kongsberg, district 005, household 03, Even Juul Jørgensen Siggerud household.
- **[info] repository** (B.1 §2/§3 vs. the 2026 archive-law merger)
  - Repository "Nasjonalarkivet" conflicts with the pre-merger institution names the written master (B.1 §2/§3) prescribes for this volume's AV/… call-number prefix. Pending the Nasjonalarkivet naming decision (see the catalog-wide repository finding): on 1 January 2026 the new archive law merged Arkivverket, Riksarkivet and the statsarkivene into one agency, Nasjonalarkivet — so the master's pre-merger names are stale on its own "follow the current naming" rationale.
  - **Fix:** Recommended: update house_style_master.md B.1 §2/§3 and the §11–§12 worked examples to Nasjonalarkivet — this field then already conforms. Either way, remove the digitalarkivet.no platform URL from repository record R0009 (platform ≠ repository).

### S0071 — Norway, Kristiania kjøpstad, folketelling 1920
- **[major] · C0073 page** (Part A — Subject formatting in the page string; Part A — Two-forms-two-homes locator (hard rule 2: no place name))
  - Page string "Kristiania kjøpstad, pp. 300835-300836" leads with a jurisdiction place name, omits the granular locators that the FRN itself carries (husliste no. 2, husholdningsliste no. 2, personseddel no. 4), and has no [name] [record-noun] subject at all.
  - **Fix:** pp. 300835–300836, husliste no. 2, husholdningsliste no. 2, personseddel no. 4, Janna Marie Siggerud (lodger) — drop "Kristiania kjøpstad" (place lives on the event and in the FRN), use an en dash in the range.
  - *Verifier adjustment:* Issue is real (C0073 page string leads with "Kristiania kjøpstad", omits husliste/husholdningsliste/personseddel locators that N0241's FRN carries, and has no subject), but two corrections: (1) the en-dash instruction for the page range is NOT a house rule — B.1 §4 mandates en dashes for year-ranges only, and the style's own Worked example 3 page string uses a hyphen in a locator range ("folio 145-148"), so "pp. 300835-300836" may keep its hyphen; (2) hard rule 2 governs the subject slot specifically — the correct anchors for dropping the leading jurisdiction are Part A Subject formatting ([locators], [name] [record-noun]) and the two-forms-two-homes granular-locators rule (jurisdiction already lives in the Source Title). Corrected fix: "pp. 300835-300836, husliste no. 2, husholdningsliste no. 2, personseddel no. 4, Janna Marie Siggerud (lodger)" — the (lodger) source-state parenthetical is supported since the personseddel actively records it.
- **[minor] abbrev** (B.1 §10 Abbrev rule)
  - Abbrev "Kristiania kjøpstad folketelling 1920" carries the administrative suffix "kjøpstad"; the §10 folketelling examples use the bare place name ("Eidsvoll folketelling 1875"), and the sibling Source S0077 already uses "Kristiania folketelling 1875" — inconsistent forms for the same place.
  - **Fix:** Kristiania folketelling 1920
- **[info] repository** (B.1 §2/§3 vs. the 2026 archive-law merger)
  - Repository "Nasjonalarkivet" conflicts with the pre-merger institution names the written master (B.1 §2/§3) prescribes for this volume's AV/… call-number prefix. Pending the Nasjonalarkivet naming decision (see the catalog-wide repository finding): on 1 January 2026 the new archive law merged Arkivverket, Riksarkivet and the statsarkivene into one agency, Nasjonalarkivet — so the master's pre-merger names are stale on its own "follow the current naming" rationale.
  - **Fix:** Recommended: update house_style_master.md B.1 §2/§3 and the §11–§12 worked examples to Nasjonalarkivet — this field then already conforms. Either way, remove the digitalarkivet.no platform URL from repository record R0009 (platform ≠ repository).

### S0072 — Sweden, Göteborg och Bohus, Göteborg, emigrant passenger lists (Göteborgs poliskammare) EIX, 1869–1951
- **[minor] call_number** (Part A — Two-forms-two-homes locator)
  - Call number "Göteborgs poliskammare E IX:1–143" is a series description/span, not the archive machine path; the call number holds the archive's machine reference only (a SE/GLA/… NAD path for Landsarkivet i Göteborg holdings).
  - **Fix:** Replace with the NAD reference for the cited volume (SE/GLA/12703/E IX/…); the series span can be mentioned in the FRN.
- **[minor] · C0074 srn** (B.2 §12 Worked examples (gloss appears in the FRN only; subsequent notes drop it))
  - SRN retains an English gloss: "Göteborgs poliskammare EIX (Göteborg passenger lists), 1886, ..." — the SRN is the compact subsequent-reference form and drops the gloss.
  - **Fix:** SRN: "Göteborgs poliskammare EIX, 1886, S.S. Orlando, image 16, Karin Grund passenger manifest entry."
- **[info] abbrev** (B.2 §10 Abbrev rule)
  - Abbrev "Göteborg passenger lists, EIX (1869–1951)" uses place + English record type; the §10 state-record form is "[Creating body] [volume] ([year-range])".
  - **Fix:** Göteborgs poliskammare EIX (1869–1951)
- **[info] · C0074 abstract** (Part A — Citation notes structure (Abstract = summary of what the record contains))
  - Abstract N0244 includes an inference: "listed with a departure age of 21, implying a birth year of about 1865" — the implied birth year is analysis, not record content.
  - **Fix:** Keep "departure age 21" in the Abstract and move the birth-year inference to an Analysis note (or express it on the relevant citation as an evidence-quality parenthetical, "(stated age 21, birth year inferred from age)").
- **[info] · C0074 page** (B.2 §5 Locator / volume notation tokens; Part A — Two-forms-two-homes locator)
  - Page string says "Vol. EIX" (closed up) but the FRN says "vol. E IX" (spaced) — inconsistent token forms for the same designator; also neither identifies the specific volume number within the E IX:1–143 series (navigation relies on year/month/ship instead), which the guide does not explicitly address for this record type.
  - **Fix:** Pick one form (house convention closes up spaces in citation-facing text: "EIX") and, if determinable from the ArkivDigital/Ancestry image, add the specific volume number (e.g. "Vol. EIX:34") to page and FRN.

### S0073 — Sweden, Värmland, Norra Ny, moving register (Flyttningslängder) B:3, 1884–1894
- **[minor] · C0075 frn** (Part A — Citation notes structure (Abstract holds record content); B.2 §12 Worked examples)
  - FRN carries extracted record content about a second person named outright: "the same page records Lars Larsson departing the same day" — co-entries belong in the Abstract (N0246 already records this), and persons other than the subject are named by relationship in FRN prose, not by name.
  - **Fix:** Delete the clause "; the same page records Lars Larsson departing the same day" from the FRN (the Abstract already covers it); if the link matters evidentially, cite him with his own citation or name him by relationship.
  - *Verifier adjustment:* Issue real: N0245's FRN clause '; the same page records Lars Larsson departing the same day' is extracted record content about a co-entry that duplicates Abstract N0246, and Part A defines the FRN as citation prose vs the Abstract as record content (all §12 worked FRNs stick to citation elements). But the cited sub-rule 'persons other than the subject are named by relationship in FRN prose, not by name' does not exist — Part A's relationship remark concerns parenthetical mechanics for informants/witnesses — and the record states no relationship between Karin Larsdotter and Lars Larsson, so 'name him by relationship' is not executable. Corrected fix: delete the clause (Abstract already covers it); if the joint departure matters evidentially, give Lars Larsson his own citation.
- **[minor] · C0075 page** (B.2 §9 Subject vocabulary; cross-citation consistency within the group)
  - Same record series, two record-noun styles: C0075 uses "Karin Larsdotter moving-out entry" while C0061 (Flyttningslängder B:2, S0051) uses "Per Larsson emigration entry" for the same kind of out-migration-to-North-America entry.
  - **Fix:** Standardize one record-noun for Flyttningslängder out-migrations across both sources — e.g. "emigration entry" — and update page, FRN, and SRN of whichever citation is changed ("Vol. B:3, p. 11 (image 12), Karin Larsdotter emigration entry").
  - *Verifier adjustment:* Issue real: both citations are Flyttningslängder out-migrations to North America with different record-nouns (C0075 'moving-out entry' vs C0061 'emigration entry'). But the rule citation overreaches: B.2 §9 has no Flyttningslängder record-noun (the series is absent from §1's covered types) and no written 'cross-citation consistency' rule — the supportable basis is §9's one-record-noun-per-event-type vocabulary pattern via its open '[Given Surname] [record-noun]' migration row. Corrected fix: choose one record-noun (e.g. 'emigration entry'), add it to §9 as a newly-derived Flyttningslängder row, and update the page and SRN of the changed citation only — both FRNs already use 'out-migration', so FRN prose needs no change.
- **[info] · C0075 confidence** (Part A — Confidence; B.2 §8 (silent on Flyttningslängder); cross-citation consistency within the group)
  - Same series, different confidence for the same kind of fact: C0075 (B:3 out-migration) is 4 (Very High) while C0061 (B:2 out-migration, S0051) is 3 (High). The guide has no Flyttningslängder row, but the two should not diverge.
  - **Fix:** Harmonize both citations to one level (High or Very High — an original parish register recording the migration event contemporaneously supports Very High) and, if desired, add a Flyttningslängder row to §8.

### S0074 — 1900 U.S. Federal Census, Marshall County, Minnesota
- **[info] · C0076 abstract** (Part A — Citation notes structure)
  - Abstract note N0248 (and N0253 on S0075/C0077) begins directly with prose, while the group's other Abstract notes (N0052 on C0025, N0121 on C0067) open with an "ABSTRACT:" block label — inconsistent labeling within the same note type; the style is silent on the header, so this is consistency-only.
  - **Fix:** Standardize: add the "ABSTRACT:" header to N0248 and N0253, or drop it from N0052 and N0121

### S0075 — 1930 U.S. Federal Census, Lake of the Woods County, Minnesota
- **[minor] · C0077 page** (B.3 §7 Citation page templates (Federal census))
  - Unresolved placeholder "roll [NEEDED: NARA T626 roll number]" sits in the page string and again in the FRN's citing clause ("citing National Archives microfilm publication T626, roll [NEEDED: NARA T626 roll number]").
  - **Fix:** Look up the NARA T626 roll number for Lake of the Woods County, Minnesota (ED 39-29) and insert it in both the page string and the FRN

### S0076 — Norway, Akershus, Nannestad, folketelling 1865
- **[minor] author** (B.1 §2 Source author (naming decision pending))
  - Author "Nasjonalarkivet" vs. the master's "Riksarkivet (preferred)" — a naming-decision conflict, but the drift is real regardless: the six folketelling sources carry three different author spellings (Nasjonalarkivet / "Nasjonalarkivet (Riksarkivet)" / Riksarkivet).
  - **Fix:** Standardize all six census authors on the single value the naming decision selects.
- **[minor] call_number** (B.1 §5 Locator / volume notation tokens; B.1 §3 Repository)
  - Call number "AV/RA-S-2231" is truncated — it stops at the fond and omits the sub-series; the §3/§11 folketelling reference form is "AV/RA-S-2231/E" (sub-series E: Folketellinger), which the citation's own FRN structure ("E: Folketellinger") confirms for this fond.
  - **Fix:** AV/RA-S-2231/E
  - *Verifier adjustment:* Truncation is real and the fix AV/RA-S-2231/E is correct per the §5 decoding ('sub-series E (folketellinger)') and the §11 folketelling entries, but the corroboration claim is wrong: S0076's FRN (C0079) reads 'Folketellinger, boliger og boforhold, protokoll nr. 059; archive reference AV/RA-S-2231' and never contains 'E: Folketellinger' — that token appears only in the style guide's Worked example 2. Corrected wording: call number stops at the fond; the /E sub-series is established by §5/§11 and the sibling folketelling Sources (S0038, S0071, S0077), not by this record's FRN.
- **[info] repository** (B.1 §2/§3 vs. the 2026 archive-law merger)
  - Repository "Nasjonalarkivet" conflicts with the pre-merger institution names the written master (B.1 §2/§3) prescribes for this volume's AV/… call-number prefix. Pending the Nasjonalarkivet naming decision (see the catalog-wide repository finding): on 1 January 2026 the new archive law merged Arkivverket, Riksarkivet and the statsarkivene into one agency, Nasjonalarkivet — so the master's pre-merger names are stale on its own "follow the current naming" rationale.
  - **Fix:** Recommended: update house_style_master.md B.1 §2/§3 and the §11–§12 worked examples to Nasjonalarkivet — this field then already conforms. Either way, remove the digitalarkivet.no platform URL from repository record R0009 (platform ≠ repository).

### S0077 — Norway, Kristiania kjøpstad, folketelling 1875
- **[minor] · C0080 frn** (B.1 §2 Source author ("Riksarkivet is written bare, not Nasjonalarkivet (Riksarkivet)"); §12 worked examples' citing-clause form)
  - Sibling census FRNs disagree on the archive name: C0080 says "citing Nasjonalarkivet, source ID 52055…" while C0041/C0079 say "citing Riksarkivet…" — same record class, two agency names.
  - **Fix:** Normalize all census FRN citing-clauses to the name the naming decision selects.
- **[info] repository** (B.1 §2/§3 vs. the 2026 archive-law merger)
  - Repository "Nasjonalarkivet" conflicts with the pre-merger institution names the written master (B.1 §2/§3) prescribes for this volume's AV/… call-number prefix. Pending the Nasjonalarkivet naming decision (see the catalog-wide repository finding): on 1 January 2026 the new archive law merged Arkivverket, Riksarkivet and the statsarkivene into one agency, Nasjonalarkivet — so the master's pre-merger names are stale on its own "follow the current naming" rationale.
  - **Fix:** Recommended: update house_style_master.md B.1 §2/§3 and the §11–§12 worked examples to Nasjonalarkivet — this field then already conforms. Either way, remove the digitalarkivet.no platform URL from repository record R0009 (platform ≠ repository).

### house_style_master.md — 
- **[info] rule-text** (B.1 §2 Source author — naming note)
  - B.1 §2 justifies bare "Riksarkivet" with the claim that Norway's National Archives "briefly used the Nasjonalarkivet name 2010–2018." That doesn't match the record: the name was recommended by the Archive Law Committee in 2019 and adopted on 1 January 2026, when the new archive law merged Arkivverket, Riksarkivet and the statsarkivene into one agency.
  - **Fix:** When updating §2, rewrite the naming note around the 2026 merger (and drop or re-verify the 2010–2018 claim).
