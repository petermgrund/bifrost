# Grund-Castellano Citation Generator

The rules behind Bifrost's Citations page. It turns one record into finished Gramps fields (Source, Citation, reference notes) and Paperless metadata by following `Grund-Castellano Citation Style Guide.md`, the master copy of the guide.

## Use it

Open Citations in Bifrost (`/citations`). Pick a Paperless document, a record type, then fill in the Source, Citation, and Note steps; the last step creates the Source (or uses an existing one), the Citation with its note on the document's Gramps media, and files the scan in Paperless. Hover a rule reference to read that rule.

## Change a rule

1. Edit the rule, table row, or example in the guide; add a Change log row; mark any Review queue item it settles.
2. Run `npm test`. The report names every pinned row, worked example, or §4/§7 row the edit touched.
3. Update the affected record definitions in `src/records/` until the check passes (or fix the guide if the failure shows the guide is wrong).
4. Run `npm run build`.
5. Commit the guide, the code, and `bifrost/web/static/citations/citations.js` together.

## Commands

- `npm test`: unit tests plus the guide checks (worked examples, pins, coverage, shared tables), and a check that Bifrost serves the current build. Needs Node 24; nothing to install.
- `npm run build`: writes `../bifrost/web/static/citations/citations.js`, one ES module with the engine, the record types, the form rules, and the guide excerpts.

## Where things live

- `src/records/`: one file per guide chapter; each record type lists its inputs, templates, the guide rows it follows (pins), and the inputs that reproduce its worked examples.
- `src/form.js`: what each wizard step asks for and shows.
- `test/support/pending.js`: worked-example fields that differ because the guide contradicts itself.
- `test/support/not-covered.js`: guide rows deliberately without a record type.
- `docs/superpowers/`: the original design and implementation plan (for the earlier standalone Workbench).
