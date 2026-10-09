# Citation Generator Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a form-based citation generator that turns one record into Gramps fields, reference notes, and Paperless metadata by following the Grund-Castellano Citation Style Guide, with an automated check that keeps the generator tied to the guide.

**Architecture:** Plain ES modules in `src/` (template engine, draft engine, 44 record-type definitions, rule checks, pure HTML renderers, app wiring) are tested directly by Node's built-in test runner and combined by a zero-dependency build script into one self-contained `citation-generator.html`. A guide reader in `tools/` parses the style guide markdown so the tests can rebuild every worked example, confirm every pinned template row still exists, and confirm every §4/§7 row is covered.

**Tech Stack:** JavaScript (ES2022 modules), Node 24 (`node --test`, no npm packages), HTML/CSS, headless Chrome for the smoke test (optional).

**Spec:** `docs/superpowers/specs/2026-09-23-citation-generator-design.md` (approved mockup: `docs/superpowers/specs/2026-09-23-citation-generator-workbench.png`)

## Global Constraints

- No AI anywhere: every output comes from deterministic templates.
- The master guide is `Grund-Castellano Citation Style Guide.md` at the repository root. Never move or rename it.
- No npm dependencies. Commands are `npm test` (`node --test test/*.test.js`) and `npm run build` (`node tools/build.js`).
- The deliverable is one self-contained file, `citation-generator.html`, committed at the repository root: no external scripts, stylesheets, or fonts (system fonts only); works offline.
- Outputs, in Gramps order: Source (Title, Author, Abbrev, Pubinfo, Repository, Call number); Citation (Page, Date "blank, always", Confidence); Citation note (FRN, SRN); Paperless scan (Title, Document type, Date meaning, Correspondent, Source URL).
- Look: the approved Workbench mockup (sidebar of record types, compact label-left form, output table with rule references and copy buttons, status bar, hover cards with guide text). Light and dark themes.
- No Evidence step: confidence is a dropdown pre-set to the record type's §8 default.
- *Copy all* uses the current builder's block format (SOURCE / CITATION / FIRST REFERENCE NOTE / SHORT REFERENCE NOTE).
- When the guide contradicts itself, the generator follows the worked example and the difference is listed in `test/support/pending.js` until the user decides (Task 13).
- Never commit `local.txt` or `.superpowers/` (both are already in `.gitignore`).
- Work on the `citation-generator` branch. End every commit message with the trailer `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- Expected test counts below are for the guide as of its 2026-09-23 Change log entry. If the guide has changed since, counts differ; the pass/fail/todo pattern is what matters.

## File structure

| File | Responsibility |
| --- | --- |
| `package.json` | The two npm scripts; `"type": "module"` |
| `src/template.js` | `{field}` / `«optional»` template filling and gap markers `⟦Label⟧` |
| `src/tables.js` | Shared lookup tables (platforms, states, archives, suggestions, document types) and small text helpers |
| `src/engine.js` | Drafts (the user's inputs) → every output field; subject builder (A7); Repository/Pubinfo (A9/A10); Paperless (C1–C8) |
| `src/compare.js` | Compares outputs with a guide worked example (used by tests and the status bar) |
| `src/records/norwegian.js`, `swedish.js`, `us.js`, `published.js` | The 44 record-type definitions: inputs, templates, pins, worked-example inputs |
| `src/records/index.js` | `RECORDS` in sidebar order and `recordById` |
| `src/checks.js` | Rule checks shown in the status bar |
| `src/store.js` | Saving and loading drafts in browser storage |
| `src/view.js` | Pure HTML-string renderers for the sidebar, form, output table, status bar, hover card |
| `src/app.js` | Browser wiring: state, events, clipboard, hover cards, deep links, smoke mode |
| `src/page.html` | Page shell and Workbench CSS; `<!--GUIDE-->` and `<!--APP-->` placeholders |
| `tools/guide.js` | Reads the guide markdown: sections, first paragraphs, tables, worked examples, Change log date (Node only) |
| `tools/build.js` | Bundles `src/` and guide excerpts into `citation-generator.html` |
| `test/*.test.js` | Unit tests and the four guide checks; `test/support/` holds the pending list, the not-covered list, and report helpers |

---

### Task 1: Project scaffold and template engine

**Files:**
- Create: `package.json`
- Create: `src/template.js`
- Test: `test/template.test.js`

**Interfaces:**
- Produces: `fill(template, values, labelOf?) → string`, `gap(label)`, `plain(text)`, `hasGap(text)`, `gapLabels(text)`, `isBlank(value)`, `templateKeys(template)`, constants `GAP_OPEN = '⟦'`, `GAP_CLOSE = '⟧'` (all from `src/template.js`).

- [ ] **Step 1: Create `package.json`**

```json
{
  "name": "citation-generator",
  "private": true,
  "type": "module",
  "scripts": {
    "test": "node --test test/*.test.js",
    "build": "node tools/build.js"
  }
}
```

- [ ] **Step 2: Write the failing test** `test/template.test.js`

````js
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { fill, gap, plain, hasGap, gapLabels, isBlank, templateKeys } from '../src/template.js';

test('fill inserts values', () => {
  assert.equal(fill('{a}, {b}', { a: 'x', b: 'y' }), 'x, y');
});

test('a blank required value becomes a labelled gap', () => {
  assert.equal(fill('p. {page}', { page: '' }, key => ({ page: 'Page' })[key]), 'p. ⟦Page⟧');
});

test('an optional segment drops out when any value inside it is blank', () => {
  assert.equal(fill('p. {page}« (image {image})»', { page: '57', image: '' }), 'p. 57');
  assert.equal(fill('p. {page}« (image {image})»', { page: '57', image: '62' }), 'p. 57 (image 62)');
});

test('bracketed glosses are plain text', () => {
  assert.equal(fill('Kirkebøker [parish records], {vol}', { vol: 'I 2' }), 'Kirkebøker [parish records], I 2');
});

test('values keep their own spacing', () => {
  assert.equal(fill('{lead}{name}', { lead: 'entry for ', name: 'Ola' }), 'entry for Ola');
});

test('gap helpers', () => {
  assert.equal(gap('X'), '⟦X⟧');
  assert.equal(plain('p. ⟦Page⟧'), 'p. [Page]');
  assert.equal(hasGap('p. ⟦Page⟧'), true);
  assert.equal(hasGap('p. 57'), false);
  assert.deepEqual(gapLabels('⟦A⟧ and ⟦B⟧'), ['A', 'B']);
});

test('isBlank and templateKeys', () => {
  assert.equal(isBlank('  '), true);
  assert.equal(isBlank('0'), false);
  assert.deepEqual(templateKeys('{a}«, {b}»'), ['a', 'b']);
});
````

- [ ] **Step 3: Run it to confirm it fails**

Run: `node --test test/template.test.js`
Expected: FAIL with `ERR_MODULE_NOT_FOUND` for `src/template.js`.

- [ ] **Step 4: Implement** `src/template.js`

````js
// Template filling. {key} inserts a value; «…» is dropped when any key inside it is blank.
// A blank required value becomes a gap marker ⟦Label⟧: highlighted on screen, copied as [Label].
export const GAP_OPEN = '⟦';
export const GAP_CLOSE = '⟧';
const GAP_RE = /⟦([^⟧]*)⟧/g;

export function isBlank(value) {
  return value === undefined || value === null || String(value).trim() === '';
}

export function gap(label) {
  return GAP_OPEN + label + GAP_CLOSE;
}

export function hasGap(text) {
  return String(text ?? '').includes(GAP_OPEN);
}

export function plain(text) {
  return String(text ?? '').replace(GAP_RE, '[$1]');
}

export function gapLabels(text) {
  return [...String(text ?? '').matchAll(GAP_RE)].map(m => m[1]);
}

export function templateKeys(template) {
  return [...String(template ?? '').matchAll(/\{(\w+)\}/g)].map(m => m[1]);
}

export function fill(template, values, labelOf = key => key) {
  if (!template) return '';
  const kept = template.replace(/«([^»]*)»/g, (_, inner) =>
    templateKeys(inner).some(k => isBlank(values[k])) ? '' : inner);
  return kept.replace(/\{(\w+)\}/g, (_, k) => isBlank(values[k]) ? gap(labelOf(k)) : String(values[k]));
}
````

- [ ] **Step 5: Run the test to confirm it passes**

Run: `node --test test/template.test.js`
Expected: `tests 7`, `pass 7`, `fail 0`.

- [ ] **Step 6: Commit**

```bash
git add package.json src/template.js test/template.test.js
git commit -m "Add template engine" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 2: Guide reader

**Files:**
- Create: `tools/guide.js`
- Test: `test/guide.test.js`

**Interfaces:**
- Produces (from `tools/guide.js`): `GUIDE_PATH`, `CHAPTERS = ['B.1','B.2','B.3','B.4']`, `normalize(text) → string`, `loadGuide(path?) → Guide`, `parseGuide(markdown) → Guide`.
- `Guide` methods: `section(ref) → { ref, title, body } | null` (refs: `'A8'`, `'C1'`, `'B.1 §4'`, `'Change log'`), `sectionText(ref) → string | null` (normalized), `sectionLines(ref) → string[]`, `firstParagraph(ref) → string`, `tables(ref) → [{ header, raw, rows }]`, `examples() → Example[]`, `changeLogDate() → 'YYYY-MM-DD'`.
- `Example`: `{ id, chapter, heading, expected: { title?, abbrev?, author?, pubinfo?, repository?, callNumber?, page?, frn?, srn? }, skipped: { field: reason }, confidence, citations: [{ page, confidence, frn, srn }] }`. Ids look like `'B.1 Example 1'` (chapters B.1–B.3) or `'B.4 Family Bible'` (B.4, heading text before any parenthesis).

- [ ] **Step 1: Write the failing test** `test/guide.test.js`

````js
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { loadGuide, parseGuide, normalize } from '../tools/guide.js';

const MINI = `# Guide

## Part A: Shared rules

### A1 · Source scoping

One Source per volume.

### A9 · Repository

Decide in this order:

1. **An archive** holds it.
2. A family member holds it.

## Part B.1: Norwegian sources

### §4 Source title

| Record type | Title template | Example |
| --- | --- | --- |
| Parish | \`Norway, [Fylke], [Parish]\` | \`Norway, Akershus, Eidsvoll\` |

### §12 Worked examples

#### Example 1: Parish record

| Source field | Value |
| --- | --- |
| Title | \`Norway, Akershus, Eidsvoll\` |
| Author | Blank |
| Call number | **Open:** check the catalog |
| **Citation** page | \`p. 57, Thor Emil baptism entry\` |
| Confidence | High (primary, direct) |

**FRN:** Eidsvoll \\[parish records\\], p. 57.

**SRN:** Eidsvoll, p. 57.

## Change log

| Date | Rule / section | Change | Why |
| --- | --- | --- | --- |
| 2026-01-02 | A1 | Added | Test |
`;

const mini = parseGuide(MINI);

test('normalize drops escapes, backticks and emphasis and collapses spaces', () => {
  assert.equal(normalize('`Husförhörslängder \\[household examinations\\]`  **bold**'), 'Husförhörslängder [household examinations] bold');
});

test('finds rule and chapter sections by reference', () => {
  assert.equal(mini.section('A1').title, 'A1 · Source scoping');
  assert.equal(mini.section('B.1 §4').title, 'B.1 §4 · Source title');
  assert.equal(mini.section('B.2 §4'), null);
  assert.equal(mini.sectionText('B.1 §4').includes('Parish | Norway, [Fylke], [Parish] |'), true);
});

test('first paragraph, with the first list items when it introduces a list', () => {
  assert.equal(mini.firstParagraph('A1'), 'One Source per volume.');
  assert.equal(mini.firstParagraph('A9'), 'Decide in this order: An archive holds it. A family member holds it.');
  assert.equal(mini.firstParagraph('B.1 §4'), '');
});

test('reads a table as normalized rows', () => {
  const [table] = mini.tables('B.1 §4');
  assert.deepEqual(table.header, ['Record type', 'Title template', 'Example']);
  assert.deepEqual(table.rows[0], ['Parish', 'Norway, [Fylke], [Parish]', 'Norway, Akershus, Eidsvoll']);
});

test('parses a worked example into compared, skipped, and note fields', () => {
  const [ex] = mini.examples();
  assert.equal(ex.id, 'B.1 Example 1');
  assert.deepEqual(ex.expected, {
    title: 'Norway, Akershus, Eidsvoll', author: '', page: 'p. 57, Thor Emil baptism entry',
    frn: 'Eidsvoll [parish records], p. 57.', srn: 'Eidsvoll, p. 57.',
  });
  assert.deepEqual(ex.skipped, { callNumber: 'Open: check the catalog' });
  assert.equal(ex.confidence, 'High');
});

test('reads the latest Change log date', () => {
  assert.equal(mini.changeLogDate(), '2026-01-02');
});

test('the real guide parses', () => {
  const guide = loadGuide();
  const examples = guide.examples();
  assert.ok(examples.length > 0);
  assert.ok(examples.every(e => /^B\.[1-4] /.test(e.id)));
  assert.match(guide.changeLogDate(), /^\d{4}-\d{2}-\d{2}$/);
  assert.ok(guide.section('A8'));
});
````

- [ ] **Step 2: Run it to confirm it fails**

Run: `node --test test/guide.test.js`
Expected: FAIL with `ERR_MODULE_NOT_FOUND` for `tools/guide.js`.

- [ ] **Step 3: Implement** `tools/guide.js`

````js
// Reads the style guide: sections, first paragraphs, tables, worked examples, and the
// Change log date. Used by the tests and the build; never shipped to the browser.
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

export const GUIDE_PATH = fileURLToPath(new URL('../Grund-Castellano Citation Style Guide.md', import.meta.url));
export const CHAPTERS = ['B.1', 'B.2', 'B.3', 'B.4'];
const LEVEL_RE = /\b(Very High|Very Low|High|Normal|Low)\b/;
const FIELD_KEYS = {
  title: 'title', abbrev: 'abbrev', author: 'author', pubinfo: 'pubinfo', repository: 'repository',
  'call number': 'callNumber', 'citation page': 'page', confidence: 'confidence',
};

/** Markdown → comparable text: drop escapes, backticks and emphasis markers; collapse whitespace. */
export function normalize(text) {
  return String(text ?? '')
    .replace(/\\([[\]_*`\\|])/g, '$1')
    .replace(/[`*]/g, '')
    .replace(/\s+/g, ' ')
    .trim();
}

export function loadGuide(path = GUIDE_PATH) {
  return parseGuide(readFileSync(path, 'utf8'));
}

export function parseGuide(markdown) {
  const lines = markdown.split('\n');
  const heads = [];
  lines.forEach((line, i) => {
    const m = line.match(/^(#{2,4}) (.+)$/);
    if (m) heads.push({ level: m[1].length, text: m[2].trim(), line: i });
  });

  function find(ref) {
    let head;
    const sub = ref.match(/^(B\.\d) §(\d+)$/);
    if (sub) {
      const part = heads.findIndex(h => h.level === 2 && h.text.startsWith(`Part ${sub[1]}:`));
      if (part < 0) return null;
      const end = heads.findIndex((h, i) => i > part && h.level === 2);
      head = heads.slice(part + 1, end < 0 ? undefined : end)
        .find(h => h.level === 3 && h.text.startsWith(`§${sub[2]} `));
    } else if (ref === 'Change log') {
      head = heads.find(h => h.level === 2 && h.text === 'Change log');
    } else {
      head = heads.find(h => h.level === 3 && h.text.split(' ')[0] === ref);
    }
    if (!head) return null;
    const next = heads.find(h => h.line > head.line && h.level <= head.level);
    return { head, body: lines.slice(head.line + 1, next ? next.line : lines.length) };
  }

  return {
    /** { ref, title, body } or null. Refs: 'A8', 'C1', 'B.1 §4', 'Change log'. */
    section(ref) {
      const s = find(ref);
      if (!s) return null;
      const name = s.head.text.replace(/^§\d+ /, '').replace(/^[AC]\d+( to C\d+)? · /, '');
      return { ref, title: `${ref} · ${normalize(name)}`, body: s.body };
    },
    /** The section's text, normalized, for pin matching. */
    sectionText(ref) {
      const s = find(ref);
      return s ? normalize(s.body.join('\n')) : null;
    },
    /** The section's lines, normalized and non-empty, for "closest line" hints. */
    sectionLines(ref) {
      const s = find(ref);
      return s ? s.body.map(normalize).filter(Boolean) : [];
    },
    firstParagraph(ref) {
      const s = find(ref);
      return s ? firstParagraph(s.body) : '';
    },
    tables(ref) {
      const s = find(ref);
      return s ? tables(s.body) : [];
    },
    examples() {
      const out = [];
      for (const chapter of CHAPTERS) {
        const s = find(`${chapter} §12`);
        if (!s) continue;
        let heading = null, body = [];
        const flush = () => { if (heading) out.push(parseExample(chapter, heading, body)); };
        for (const line of s.body) {
          const m = line.match(/^#### (.+)$/);
          if (m) { flush(); heading = m[1].trim(); body = []; } else if (heading) body.push(line);
        }
        flush();
      }
      return out;
    },
    changeLogDate() {
      const s = find('Change log');
      return s ? (tables(s.body)[0]?.rows[0]?.[0] ?? '') : '';
    },
  };
}

function blocks(body) {
  const out = [];
  let cur = [];
  for (const line of body) {
    if (line.trim()) cur.push(line);
    else if (cur.length) { out.push(cur); cur = []; }
  }
  if (cur.length) out.push(cur);
  return out;
}

const isList = line => /^\s*(- |\d+\. )/.test(line);

function firstParagraph(body) {
  const [first, second] = blocks(body);
  if (!first || /^\s*(\||```|#|>)/.test(first[0]) || isList(first[0])) return '';
  let text = normalize(first.join(' '));
  if (text.endsWith(':') && second && isList(second[0])) {
    text += ' ' + second.slice(0, 3).map(l => normalize(l.replace(/^\s*(- |\d+\. )/, ''))).join(' ');
  }
  return text;
}

function tables(body) {
  const out = [];
  let cur = null;
  for (const line of body) {
    if (line.trim().startsWith('|')) {
      const cells = line.trim().replace(/^\|/, '').replace(/\|$/, '').split('|').map(c => c.trim());
      if (!cur) cur = { header: cells.map(normalize), raw: [], rows: [] };
      else if (cells.every(c => /^:?-{3,}:?$/.test(c))) continue;
      else { cur.raw.push(cells); cur.rows.push(cells.map(normalize)); }
    } else if (cur) {
      out.push(cur);
      cur = null;
    }
  }
  if (cur) out.push(cur);
  return out;
}

/** A value cell is comparable when it is one code span or "Blank"; anything else is conditional prose. */
function cellValue(raw) {
  const t = raw.trim();
  const code = t.match(/^`([^`]*)`$/);
  if (code) return { value: normalize(code[1]) };
  if (/^Blank(\s*\([^)]*\))?$/i.test(t)) return { value: '' };
  return { skip: normalize(t) };
}

function parseExample(chapter, heading, body) {
  const id = chapter === 'B.4'
    ? `B.4 ${normalize(heading.replace(/\s*\(.*$/, ''))}`
    : `${chapter} ${heading.match(/^Example \d+/)[0]}`;
  const ex = { id, chapter, heading: normalize(heading), expected: {}, skipped: {}, confidence: '', citations: [] };
  for (const table of tables(body)) {
    const [h0, h1] = table.header;
    if ((h0 === 'Source field' || h0 === 'Field') && h1 === 'Value') {
      for (const [rawKey, rawValue] of table.raw) {
        const keys = normalize(rawKey).toLowerCase().split(' / ').map(k => FIELD_KEYS[k]).filter(Boolean);
        for (const key of keys) {
          if (key === 'confidence') { ex.confidence = (normalize(rawValue).match(LEVEL_RE) || [''])[0]; continue; }
          const cell = cellValue(rawValue);
          if ('value' in cell) ex.expected[key] = cell.value; else ex.skipped[key] = cell.skip;
        }
      }
    } else if (h0 === 'Citation' && h1 === 'Page') {
      for (const [n, page, conf] of table.raw) {
        ex.citations[Number(normalize(n)) - 1] = {
          page: cellValue(page).value ?? '',
          confidence: (normalize(conf).match(LEVEL_RE) || [''])[0],
        };
      }
    }
  }
  for (const line of body) {
    const m = line.match(/^\*\*(FRN|SRN)(?: (\d+))?:\*\*\s*(.+)$/);
    if (!m) continue;
    const field = m[1].toLowerCase(), text = normalize(m[3]);
    if (m[2]) {
      const i = Number(m[2]) - 1;
      ex.citations[i] = { ...(ex.citations[i] || {}), [field]: text };
    } else {
      ex.expected[field] = text;
    }
  }
  return ex;
}
````

- [ ] **Step 4: Run the test to confirm it passes**

Run: `node --test test/guide.test.js`
Expected: `tests 7`, `pass 7`, `fail 0`.

- [ ] **Step 5: Commit**

```bash
git add tools/guide.js test/guide.test.js
git commit -m "Add style guide reader" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: Shared tables

**Files:**
- Create: `src/tables.js`
- Test: `test/tables.test.js`

**Interfaces:**
- Consumes: `loadGuide` (Task 2).
- Produces (from `src/tables.js`): `CHAPTERS` (`{ no, se, us, pp }` → display names), `CHAPTER_CODE` (`{ no: 'B.1', se: 'B.2', us: 'B.3', pp: 'B.4' }`), `LEVELS`, `MEDIA`, `PLATFORMS` (name → homepage), `PLATFORM_ARCHIVES`, `STATE_ABBREV`, `ARCHIVES` (per chapter), `SUGGESTIONS` (per chapter: `{ which, says, evidence }`), `DATE_MEANING` (document type → C4 meaning), `PAPERLESS_NOUN`, `isoDate(text)`, `lastWord(text)`, `allButLastWord(text)`, `stateAbbrev(state)`.

- [ ] **Step 1: Write the failing test** `test/tables.test.js`

````js
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { loadGuide } from '../tools/guide.js';
import { PLATFORMS, STATE_ABBREV, isoDate, stateAbbrev, lastWord } from '../src/tables.js';

const guide = loadGuide();

test('platform homepages match the A10 platform table', () => {
  const table = guide.tables('A10').find(t => t.header[0] === 'Platform');
  assert.ok(table, 'A10 has no Platform table');
  const fromGuide = Object.fromEntries(table.rows.map(([name, url]) => [name.replace(/\s*\(.*\)$/, ''), url]));
  assert.deepEqual(PLATFORMS, fromGuide);
});

test('every state abbreviation in B.3 §10 is in STATE_ABBREV', t => {
  const row = guide.tables('B.3 §10')[0].rows.find(r => r[0].startsWith('States'));
  assert.ok(row, 'B.3 §10 has no States row');
  const listed = row[1].split(',').map(s => s.trim());
  const ours = Object.values(STATE_ABBREV);
  for (const abbrev of listed) assert.ok(ours.includes(abbrev), `${abbrev} is missing from STATE_ABBREV`);
  const extra = ours.filter(a => !listed.includes(a));
  if (extra.length) t.diagnostic(`In STATE_ABBREV but not yet in the guide: ${extra.join(', ')}`);
});

test('helpers', () => {
  assert.equal(isoDate('14 March 1925'), '1925-03-14');
  assert.equal(isoDate('ca. 1890s'), '');
  assert.equal(stateAbbrev('Minnesota'), 'Minn.');
  assert.equal(stateAbbrev('Oregon'), 'Oregon');
  assert.equal(lastWord('Birger Kirkeby'), 'Kirkeby');
});
````

- [ ] **Step 2: Run it to confirm it fails**

Run: `node --test test/tables.test.js`
Expected: FAIL with `ERR_MODULE_NOT_FOUND` for `src/tables.js`.

- [ ] **Step 3: Implement** `src/tables.js`

````js
// Lookup tables shared by every record type. PLATFORMS and STATE_ABBREV are pinned to the
// guide's own tables (A10, B.3 §10) by test/tables.test.js.

export const CHAPTERS = { no: 'Norwegian', se: 'Swedish', us: 'US', pp: 'Published & personal' };
export const CHAPTER_CODE = { no: 'B.1', se: 'B.2', us: 'B.3', pp: 'B.4' };

export const LEVELS = ['Very High', 'High', 'Normal', 'Low', 'Very Low'];
export const MEDIA = ['Digital images', 'Database with images', 'Database'];

// A10 · Platforms: homepage URLs.
export const PLATFORMS = {
  'Digitalarkivet': 'https://www.digitalarkivet.no',
  'Riksarkivet': 'https://sok.riksarkivet.se',
  'ArkivDigital': 'https://www.arkivdigital.se',
  'Nasjonalbiblioteket': 'https://www.nb.no',
  'Ancestry': 'https://www.ancestry.com',
  'FamilySearch': 'https://www.familysearch.org',
  'Find a Grave': 'https://www.findagrave.com',
  'Newspapers.com': 'https://www.newspapers.com',
  'Fold3': 'https://www.fold3.com',
  'Chronicling America': 'https://chroniclingamerica.loc.gov',
  'GenealogyBank': 'https://www.genealogybank.com',
  'YouTube': 'https://www.youtube.com',
  'Lantmäteriet': 'https://historiskakartor.lantmateriet.se',
};

// Platforms that are also archives, so naming them as Repository is not an A9 problem.
export const PLATFORM_ARCHIVES = ['Riksarkivet', 'Lantmäteriet', 'Nasjonalbiblioteket'];

// B.3 §10 · traditional state abbreviations (never USPS codes).
export const STATE_ABBREV = {
  'Minnesota': 'Minn.', 'Wisconsin': 'Wis.', 'Iowa': 'Iowa', 'South Dakota': 'S. Dak.',
  'North Dakota': 'N. Dak.', 'New York': 'N.Y.', 'Massachusetts': 'Mass.', 'Connecticut': 'Conn.',
  'California': 'Cal.', 'Illinois': 'Ill.', 'Michigan': 'Mich.', 'Virginia': 'Va.', 'Pennsylvania': 'Pa.',
};

// Archive suggestions per chapter (each chapter's §3).
export const ARCHIVES = {
  no: ['Statsarkivet i Oslo', 'Statsarkivet i Hamar', 'Riksarkivet'],
  se: ['Värmlandsarkiv', 'Riksarkivet'],
  us: ['National Archives', 'Minnesota Historical Society', 'Swenson Swedish Immigration Research Center', 'Family History Library'],
  pp: ['Minnesota Historical Society', 'Library of Virginia'],
};

// A7 parenthetical suggestions per chapter (§9): 1 which entry, 2 source says, 3 evidence.
export const SUGGESTIONS = {
  no: { which: ['daughter of ', 'son of ', 'at ', 'b. ', 'd. ', 'senior', 'junior'],
    says: ['tjenestepige', 'tjenestedreng', 'fattigdreng', 'tyende', 'inderst', 'husmand', 'enke', 'enkemann', 'første ekteskap', 'annen ekteskap'],
    evidence: ['stated age ', 'birth year inferred from age', 'named at '] },
  se: { which: ['b. ', 'd. ', 'at ', 'junior', 'servant'],
    says: ['widower', 'widow', 'both in first marriage', 'retired soldier', 'unmarried'],
    evidence: ['birth year inferred from age', 'stated age ', 'named at ', 'witness at '] },
  us: { which: ['b. ', 'd. ', 'of  Co.', 'senior', 'junior', 'ED '],
    says: ['head', 'wife of head', 'son', 'daughter', 'boarder', 'lodger', 'servant', 'widow', 'widower', 'declared', 'naturalized ', 'both in first marriage', 'by license', 'by banns', 'delayed registration', 'amended', 'discharged', 'laborer'],
    evidence: ['birth year inferred from age', 'birth years inferred from ages', 'stated age ', 'named at ', 'parents named at ', 'informant on ', 'next of kin on ', 'witness at ', 'identified by initials only', 'birthplace inferred from naturalization'] },
  pp: { which: ['b. ', 'd. ', 'at ', 'senior', 'junior'],
    says: ['written contemporaneously', 'compiled later', 'damaged page', 'in unrelated handwriting'],
    evidence: ['reported by ', 'handwritten by ', 'uncited claim in published work', 'second-hand'] },
};

// C2 document types and their default C4 date meaning.
export const DATE_MEANING = {
  'vital record': 'event', 'enumeration': 'event', 'legal': 'event', 'immigration': 'event',
  'military': 'event', 'religious': 'event', 'correspondence': 'creation', 'ephemera': 'event',
  'publication': 'publication', 'artifact': 'creation', 'research': 'creation', 'interview': 'event',
};

// C1 · the Paperless record-noun when it differs from the citation's record noun.
export const PAPERLESS_NOUN = { 'marriage': 'marriage entry', 'estate': 'estate inventory' };

const MONTHS = ['january', 'february', 'march', 'april', 'may', 'june', 'july', 'august', 'september', 'october', 'november', 'december'];

/** '14 March 1925' → '1925-03-14'; anything else → ''. */
export function isoDate(text) {
  const m = String(text ?? '').trim().match(/^(\d{1,2}) ([A-Za-z]+) (\d{4})$/);
  if (!m) return '';
  const month = MONTHS.indexOf(m[2].toLowerCase()) + 1;
  return month ? `${m[3]}-${String(month).padStart(2, '0')}-${m[1].padStart(2, '0')}` : '';
}

export function lastWord(text) {
  return String(text ?? '').trim().split(/\s+/).pop() || '';
}

export function allButLastWord(text) {
  return String(text ?? '').trim().split(/\s+/).slice(0, -1).join(' ');
}

export function stateAbbrev(state) {
  return STATE_ABBREV[String(state ?? '').trim()] || String(state ?? '').trim();
}
````

- [ ] **Step 4: Run the test to confirm it passes**

Run: `node --test test/tables.test.js`
Expected: `tests 3`, `pass 3`, `fail 0`, and a diagnostic line `In STATE_ABBREV but not yet in the guide: Ill., Mich., Va., Pa.`

- [ ] **Step 5: Commit**

```bash
git add src/tables.js test/tables.test.js
git commit -m "Add shared lookup tables pinned to A10 and B.3 §10" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 4: Draft engine and example comparison

**Files:**
- Create: `src/engine.js`
- Create: `src/compare.js`
- Test: `test/engine.test.js`

**Interfaces:**
- Consumes: `fill`, `gap`, `plain` (Task 1); `PLATFORMS`, `DATE_MEANING`, `PAPERLESS_NOUN`, `CHAPTER_CODE` (Task 3).
- Produces (from `src/engine.js`):
  - Constants `STANDARD_VALUES = ['url','accessed','eventYear','details','comment']`, `SUBJECT_KEYS`, `HOLDER_KEYS`, `ENGINE_TOKENS`, `TEMPLATE_KEYS`, `OUTPUT_GROUPS` (`[{ name, fields: [[key, label, rule]] }]`).
  - `newDraft(type) → Draft`, `draftFromExample(type, claim) → Draft`, `exampleLabel(claim) → string`, `buildOutputs(type, draft) → Outputs`, `subjectOf(type, subject)`, `repositoryOf(holder)`, `homepageOf(holder)`, `resolveType(type, draft)`, `inputFields(type) → [key, label, placeholder][]`, `labeler(type)`, `usesDetails(type)`, `ruleRef(type, rule)`.
  - `Draft`: `{ type, values: { [inputKey|standard]: string }, subject: { name, noun, nonHead, head, which, says, evidence, afterNoun }, holder: { heldBy: 'archive'|'private'|'publication', archive, custodian, custodianPlace, custodyWording, keepPlatform, platform, platformHome, medium }, confidence, variant, overrides: { [outputKey]: string }, example }`.
  - `Outputs`: `{ title, author, abbrev, pubinfo, repository, callNumber, page, date, confidence, frn, srn, plTitle, plDoctype, plDateMeaning, plCorrespondent, plSourceUrl }` (strings; may contain gap markers).
  - Record type shape (used from Task 5 on): `{ id, chapter, group, name, hint?, source, citation?, note?, nouns, holder, confidence, doctype, derive?(values), title, abbrev, author, pubinfo?, page, frn, srn, paperlessTitle?, pageVariants?, optionalSubject?, subjectLabel?, detailsLabel?, eventYearLabel?, pins, examples }`.
- Produces (from `src/compare.js`): `COMPARED_FIELDS`, `expectedFor(example, claim) → { fields, confidence }`, `diffOutputs(expectedFields, outputs) → [{ field, want, got }]`.

- [ ] **Step 1: Write the failing test** `test/engine.test.js`

````js
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { newDraft, draftFromExample, subjectOf, repositoryOf, buildOutputs, inputFields, resolveType, usesDetails, ruleRef } from '../src/engine.js';
import { plain } from '../src/template.js';

// A small made-up record type, so the engine is tested on its own.
const PARISH = {
  id: 'test-parish', chapter: 'se', group: 'Test', name: 'Test parish register',
  source: [['parish', 'Parish'], ['vol', 'Volume'], ['call', 'Call number']],
  citation: [['page', 'Page'], ['image', 'Image']],
  note: [['citing', 'Citing']],
  nouns: ['household', 'record'],
  holder: { heldBy: 'archive', archive: 'Värmlandsarkiv', platform: 'Riksarkivet', medium: 'Digital images' },
  confidence: 'High', doctype: 'enumeration',
  derive: v => ({ upper: String(v.parish || '').toUpperCase() }),
  title: 'Sweden, {parish}, {vol}',
  abbrev: '{upper} {vol}',
  author: '{parish} församling',
  page: 'p. {page}« (image {image})», {subject}',
  frn: '{author}, vol. {vol}, p. {page}, {entryof}«, {details}»; digital image, {platform} ({url} : accessed {accessed}); citing {repository}«, {citing}».',
  srn: '{parish} {vol}, p. {page}, {subject}.',
  pageVariants: undefined,
  pins: {},
  examples: [],
};
const WITH_VARIANTS = {
  ...PARISH, id: 'test-vital',
  pageVariants: [
    { key: 'certificate', label: 'Certificate', citation: [['cert', 'Certificate no.']], nouns: ['death certificate'], page: 'Certificate no. {cert}, {subject}' },
    { key: 'license', label: 'Marriage license', citation: [['license', 'License no.']], nouns: ['marriage'], page: 'License no. {license}, {subject}' },
  ],
};
const filled = () => draftFromExample(PARISH, {
  guide: 'Test', inputs: {
    parish: 'Norra Ny', vol: 'AI:11', call: 'SE/VA/13398/A I/11', page: '8', image: '19',
    name: 'Per Persson', noun: 'household', url: 'https://sok.riksarkivet.se/x', accessed: '20 April 2026', eventYear: '1812–1820',
  },
});

test('a new draft takes its defaults from the record type', () => {
  const d = newDraft(PARISH);
  assert.deepEqual(d.holder, {
    heldBy: 'archive', archive: 'Värmlandsarkiv', custodian: '', custodianPlace: '', custodyWording: 'private collection',
    keepPlatform: false, platform: 'Riksarkivet', platformHome: '', medium: 'Digital images',
  });
  assert.equal(d.confidence, 'High');
  assert.equal(d.subject.noun, 'household');
  assert.deepEqual(Object.keys(d.values), ['parish', 'vol', 'call', 'page', 'image', 'citing', 'url', 'accessed', 'eventYear', 'details', 'comment']);
});

test('draftFromExample routes inputs to values, subject, holder, confidence, and variant', () => {
  const d = draftFromExample(WITH_VARIANTS, { guide: 'X', citation: 2, inputs: { parish: 'P', name: 'N', archive: 'A', confidence: 'Low', variant: 'license' } });
  assert.equal(d.values.parish, 'P');
  assert.equal(d.subject.name, 'N');
  assert.equal(d.holder.archive, 'A');
  assert.equal(d.confidence, 'Low');
  assert.equal(d.variant, 'license');
  assert.equal(d.example, 'X · citation 2');
});

test('builds every Source, Citation, note, and Paperless field', () => {
  const o = buildOutputs(PARISH, filled());
  assert.equal(o.title, 'Sweden, Norra Ny, AI:11');
  assert.equal(o.abbrev, 'NORRA NY AI:11');
  assert.equal(o.author, 'Norra Ny församling');
  assert.equal(o.pubinfo, 'Digital images, Riksarkivet (https://sok.riksarkivet.se).');
  assert.equal(o.repository, 'Värmlandsarkiv');
  assert.equal(o.callNumber, 'SE/VA/13398/A I/11');
  assert.equal(o.page, 'p. 8 (image 19), Per Persson household');
  assert.equal(o.date, '');
  assert.equal(o.confidence, 'High');
  assert.equal(o.frn, 'Norra Ny församling, vol. AI:11, p. 8, household of Per Persson; digital image, Riksarkivet (https://sok.riksarkivet.se/x : accessed 20 April 2026); citing Värmlandsarkiv.');
  assert.equal(o.srn, 'Norra Ny AI:11, p. 8, Per Persson household.');
  assert.equal(o.plTitle, 'Per Persson household 1812–1820');
  assert.equal(o.plDoctype, 'enumeration');
  assert.equal(o.plDateMeaning, 'event');
  assert.equal(o.plCorrespondent, 'Riksarkivet');
  assert.equal(o.plSourceUrl, 'https://sok.riksarkivet.se/x');
});

test('typed values are trimmed; missing ones become labelled gaps', () => {
  const d = filled();
  d.values.parish = '  Norra Ny  ';
  d.values.vol = '';
  const o = buildOutputs(PARISH, d);
  assert.equal(plain(o.title), 'Sweden, Norra Ny, [Volume]');
});

test('subject: parentheticals in 1-2-3 order inside one set of parentheses', () => {
  const s = { name: 'Per Persson', noun: 'household', which: 'b. 1773', says: 'retired soldier', evidence: 'birth year inferred from age' };
  assert.equal(subjectOf(PARISH, s), 'Per Persson (b. 1773, retired soldier, birth year inferred from age) household');
});

test('subject: a non-head household member', () => {
  assert.equal(subjectOf(PARISH, { name: 'Karen', noun: 'household', nonHead: true, head: 'Hansen' }), 'Karen in Hansen household');
  assert.equal(plain(subjectOf(PARISH, { name: 'Karen', noun: 'household', nonHead: true, head: '' })), 'Karen in [Head] household');
});

test('subject: parentheses after the record noun', () => {
  const s = { name: 'John Grund', noun: 'birth certificate', says: 'delayed registration, 1942', afterNoun: true };
  assert.equal(subjectOf(PARISH, s), 'John Grund birth certificate (delayed registration, 1942)');
});

test('subject: a missing name is a gap; an optional subject can be empty', () => {
  assert.equal(plain(subjectOf(PARISH, { name: '', noun: 'household' })), '[Name] household');
  assert.equal(subjectOf({ ...PARISH, optionalSubject: true }, { name: '', noun: '' }), '');
});

test('repository for each held-by mode (A9)', () => {
  assert.equal(repositoryOf({ heldBy: 'archive', archive: 'Värmlandsarkiv' }), 'Värmlandsarkiv');
  assert.equal(plain(repositoryOf({ heldBy: 'archive', archive: '' })), '[Archive]');
  assert.equal(repositoryOf({ heldBy: 'private', custodian: 'Siw Alfreddson', custodyWording: 'personal collection' }), 'Siw Alfreddson, personal collection');
  assert.equal(repositoryOf({ heldBy: 'publication', platform: 'Riksarkivet', keepPlatform: false }), '');
  assert.equal(repositoryOf({ heldBy: 'publication', platform: 'Riksarkivet', keepPlatform: true }), 'Riksarkivet');
});

test('Pubinfo for a listed, an unlisted, and no platform (A10)', () => {
  const d = filled();
  d.holder.platform = 'Svenska kyrkan';
  assert.equal(plain(buildOutputs(PARISH, d).pubinfo), 'Digital images, Svenska kyrkan ([Platform homepage]).');
  d.holder.platformHome = 'https://www.svenskakyrkan.se';
  assert.equal(buildOutputs(PARISH, d).pubinfo, 'Digital images, Svenska kyrkan (https://www.svenskakyrkan.se).');
  d.holder.platform = '';
  assert.equal(buildOutputs(PARISH, d).pubinfo, '');
  assert.equal(buildOutputs({ ...PARISH, pubinfo: 'Oslo: Press, {vol}.' }, filled()).pubinfo, 'Oslo: Press, AI:11.');
});

test('overrides replace built values, and an Author override flows into the FRN', () => {
  const d = filled();
  d.overrides.author = 'Norra Ny parish';
  d.overrides.title = 'My title';
  const o = buildOutputs(PARISH, d);
  assert.equal(o.title, 'My title');
  assert.match(o.frn, /^Norra Ny parish, vol\. AI:11/);
});

test('the comment is appended after the FRN', () => {
  const d = filled();
  d.values.comment = 'Two hands.';
  assert.match(buildOutputs(PARISH, d).frn, /citing Värmlandsarkiv\. Two hands\.$/);
});

test('page variants switch the page template, nouns, and inputs', () => {
  const d = newDraft(WITH_VARIANTS);
  assert.equal(d.variant, 'certificate');
  d.variant = 'license';
  d.values.license = '12';
  Object.assign(d.subject, { name: 'Larsson-Söderström', noun: 'marriage' });
  assert.equal(buildOutputs(WITH_VARIANTS, d).page, 'License no. 12, Larsson-Söderström marriage');
  assert.deepEqual(resolveType(WITH_VARIANTS, d).nouns, ['marriage']);
  assert.deepEqual(inputFields(WITH_VARIANTS).map(([key]) => key), ['parish', 'vol', 'call', 'page', 'image', 'cert', 'license', 'citing']);
});

test('Paperless title: disambiguator, non-head, and C1 record nouns', () => {
  const d = filled();
  d.subject.which = 'b. 1773';
  assert.equal(buildOutputs(PARISH, d).plTitle, 'Per Persson (b. 1773) household 1812–1820');
  Object.assign(d.subject, { which: '', nonHead: true, head: 'Hansen' });
  assert.equal(buildOutputs(PARISH, d).plTitle, 'Per Persson in Hansen household 1812–1820');
  Object.assign(d.subject, { nonHead: false, noun: 'marriage', name: 'Larsson-Söderström' });
  d.values.eventYear = '1877';
  assert.equal(buildOutputs(PARISH, d).plTitle, 'Larsson-Söderström marriage entry 1877');
  assert.equal(buildOutputs({ ...PARISH, paperlessTitle: '{parish} scan' }, d).plTitle, 'Norra Ny scan');
});

test('usesDetails and ruleRef', () => {
  assert.equal(usesDetails(PARISH), true);
  assert.equal(usesDetails({ ...PARISH, frn: 'No details here.' }), false);
  assert.equal(usesDetails({ ...PARISH, frn: 'x', detailsLabel: 'Topic' }), true);
  assert.equal(ruleRef(PARISH, '§4'), 'B.2 §4');
  assert.equal(ruleRef(PARISH, 'A8'), 'A8');
});
````

- [ ] **Step 2: Run it to confirm it fails**

Run: `node --test test/engine.test.js`
Expected: FAIL with `ERR_MODULE_NOT_FOUND` for `src/engine.js`.

- [ ] **Step 3: Implement** `src/engine.js`

````js
// Turns one draft of one record type into every output field.
import { fill, gap } from './template.js';
import { PLATFORMS, DATE_MEANING, PAPERLESS_NOUN, CHAPTER_CODE } from './tables.js';

export const STANDARD_VALUES = ['url', 'accessed', 'eventYear', 'details', 'comment'];
export const SUBJECT_KEYS = ['name', 'noun', 'nonHead', 'head', 'which', 'says', 'evidence', 'afterNoun'];
export const HOLDER_KEYS = ['heldBy', 'archive', 'custodian', 'custodianPlace', 'custodyWording', 'keepPlatform', 'platform', 'platformHome', 'medium'];
export const ENGINE_TOKENS = ['name', 'noun', 'subject', 'entryof', 'repository', 'author', 'platform', 'home', 'medium', 'custodian', 'custplace'];
export const TEMPLATE_KEYS = ['title', 'abbrev', 'author', 'pubinfo', 'page', 'frn', 'srn', 'paperlessTitle'];

// Output fields in Gramps order, grouped as on screen. '§N' resolves to the record's chapter.
export const OUTPUT_GROUPS = [
  { name: 'Source', fields: [['title', 'Title', 'A8'], ['author', 'Author', '§2'], ['abbrev', 'Abbrev', '§10'], ['pubinfo', 'Pubinfo', 'A10'], ['repository', 'Repository', 'A9'], ['callNumber', 'Call number', 'A4']] },
  { name: 'Citation', fields: [['page', 'Page', 'A7'], ['date', 'Date', 'A2'], ['confidence', 'Confidence', '§8']] },
  { name: 'Citation note', fields: [['frn', 'FRN', 'A5'], ['srn', 'SRN', 'A5']] },
  { name: 'Paperless scan', fields: [['plTitle', 'Title', 'C1'], ['plDoctype', 'Document type', 'C2'], ['plDateMeaning', 'Date meaning', 'C4'], ['plCorrespondent', 'Correspondent', 'C6'], ['plSourceUrl', 'Source URL', 'C8']] },
];

const STANDARD_LABELS = {
  url: 'Image URL', accessed: 'Access date', eventYear: 'Event year', details: 'Entry details', comment: 'Comment',
  name: 'Name', noun: 'Record noun', subject: 'Subject', entryof: 'Name', repository: 'Repository', author: 'Author',
  platform: 'Platform', home: 'Platform homepage', medium: 'Medium', custodian: 'Custodian', custplace: 'Custodian place',
};

export function ruleRef(type, rule) {
  return rule.startsWith('§') ? `${CHAPTER_CODE[type.chapter]} ${rule}` : rule;
}

/** The record type with the draft's page variant merged in. */
export function resolveType(type, draft) {
  if (!type.pageVariants) return type;
  const variant = type.pageVariants.find(v => v.key === draft?.variant) || type.pageVariants[0];
  return { ...type, ...variant };
}

/** Every input field the record type can show: [key, label, placeholder]. */
export function inputFields(type) {
  const fromVariants = (type.pageVariants || []).flatMap(v => v.citation || []);
  const seen = new Set();
  return [...type.source, ...(type.citation || []), ...fromVariants, ...(type.note || [])]
    .filter(([key]) => !seen.has(key) && seen.add(key));
}

export function labeler(type) {
  const labels = Object.fromEntries(inputFields(type).map(([key, label]) => [key, label]));
  return key => labels[key] || STANDARD_LABELS[key] || key;
}

export function usesDetails(type) {
  if (type.detailsLabel) return true;
  const templates = [type, ...(type.pageVariants || [])].flatMap(t => TEMPLATE_KEYS.map(k => t[k] || ''));
  return templates.some(t => t.includes('{details}'));
}

export function newDraft(type) {
  const values = {};
  for (const [key] of inputFields(type)) values[key] = '';
  for (const key of STANDARD_VALUES) values[key] = '';
  const h = type.holder || {};
  return {
    type: type.id,
    values,
    subject: { name: '', noun: (type.nouns || [''])[0], nonHead: false, head: '', which: '', says: '', evidence: '', afterNoun: false },
    holder: {
      heldBy: h.heldBy || 'publication',
      archive: h.archive || '',
      custodian: h.custodian || '',
      custodianPlace: h.custodianPlace || '',
      custodyWording: h.custodyWording || 'private collection',
      keepPlatform: false,
      platform: h.platform || '',
      platformHome: '',
      medium: h.medium || 'Digital images',
    },
    confidence: type.confidence || '',
    variant: type.pageVariants ? type.pageVariants[0].key : '',
    overrides: {},
    example: '',
  };
}

export function exampleLabel(claim) {
  return claim.citation ? `${claim.guide} · citation ${claim.citation}` : claim.guide;
}

export function draftFromExample(type, claim) {
  const draft = newDraft(type);
  for (const [key, value] of Object.entries(claim.inputs)) {
    if (SUBJECT_KEYS.includes(key)) draft.subject[key] = value;
    else if (HOLDER_KEYS.includes(key)) draft.holder[key] = value;
    else if (key === 'confidence') draft.confidence = value;
    else if (key === 'variant') draft.variant = value;
    else draft.values[key] = value;
  }
  draft.example = exampleLabel(claim);
  return draft;
}

/** A7 subject: name, then parentheticals (1 which, 2 says, 3 evidence) in one set, then the record noun. */
export function subjectOf(type, subject) {
  const name = (subject.name || '').trim();
  const noun = (subject.noun || '').trim();
  const par = [subject.which, subject.says, subject.evidence].map(x => (x || '').trim()).filter(Boolean).join(', ');
  if (type.optionalSubject && !name && !noun && !par) return '';
  const parens = par ? ` (${par})` : '';
  let tail = '';
  if (subject.nonHead && noun === 'household') tail = ` in ${(subject.head || '').trim() || gap('Head')} household`;
  else if (noun) tail = ` ${noun}`;
  const who = name || gap('Name');
  return subject.afterNoun ? `${who}${tail}${parens}` : `${who}${parens}${tail}`;
}

/** A9 · Repository from the holder settings. */
export function repositoryOf(holder) {
  if (holder.heldBy === 'archive') return (holder.archive || '').trim() || gap('Archive');
  if (holder.heldBy === 'private') return `${(holder.custodian || '').trim() || gap('Custodian')}, ${holder.custodyWording || 'private collection'}`;
  return holder.keepPlatform ? (holder.platform || '').trim() : '';
}

export function homepageOf(holder) {
  const platform = (holder.platform || '').trim();
  return PLATFORMS[platform] || (holder.platformHome || '').trim();
}

/** C1 · default Paperless title: [Subject] [record-noun] [year]. */
function paperlessTitle(draft, c) {
  const s = draft.subject;
  const noun = PAPERLESS_NOUN[c.noun] ?? c.noun;
  let out = c.name || gap('Name');
  if ((s.which || '').trim()) out += ` (${s.which.trim()})`;
  if (s.nonHead && c.noun === 'household') out += ` in ${(s.head || '').trim() || gap('Head')} household`;
  else if (noun) out += ` ${noun}`;
  const year = (draft.values.eventYear || '').trim();
  return year ? `${out} ${year}` : out;
}

export function buildOutputs(type, draft) {
  const t = resolveType(type, draft);
  const L = labeler(type);
  const v = draft.values, h = draft.holder, s = draft.subject;
  const overrides = draft.overrides || {};
  const pick = (key, built) => (Object.hasOwn(overrides, key) ? overrides[key] : built);

  const name = (s.name || '').trim();
  const noun = (s.noun || '').trim();
  const typed = Object.fromEntries(Object.entries(v).map(([k, x]) => [k, typeof x === 'string' ? x.trim() : x]));
  const c = { ...typed, ...(t.derive ? t.derive({ ...typed, name, noun }) : {}) };
  const platform = (h.platform || '').trim();
  c.platform = platform;
  c.home = platform ? homepageOf(h) : '';
  c.medium = h.medium;
  c.custodian = (h.custodian || '').trim();
  c.custplace = (h.custodianPlace || '').trim();
  c.name = name;
  c.noun = noun;
  c.subject = subjectOf(t, s);
  c.entryof = noun ? `${noun} of ${name || gap(L('name'))}` : (name || gap(L('name')));

  const o = {};
  o.repository = pick('repository', repositoryOf(h));
  c.repository = o.repository;
  o.author = pick('author', fill(t.author, c, L));
  c.author = o.author;
  o.title = pick('title', fill(t.title, c, L));
  o.abbrev = pick('abbrev', fill(t.abbrev, c, L));
  o.pubinfo = pick('pubinfo', t.pubinfo !== undefined
    ? fill(t.pubinfo, c, L)
    : platform ? `${c.medium}, ${platform} (${c.home || gap(L('home'))}).` : '');
  o.callNumber = pick('callNumber', typed.call || '');
  o.page = pick('page', fill(t.page, c, L));
  o.date = '';
  o.confidence = draft.confidence;
  const frn = fill(t.frn, c, L);
  const comment = typed.comment || '';
  o.frn = pick('frn', comment ? `${frn} ${comment}` : frn);
  o.srn = pick('srn', fill(t.srn, c, L));
  o.plTitle = pick('plTitle', t.paperlessTitle ? fill(t.paperlessTitle, c, L) : paperlessTitle(draft, c));
  o.plDoctype = pick('plDoctype', t.doctype);
  o.plDateMeaning = pick('plDateMeaning', DATE_MEANING[t.doctype] || 'event');
  o.plCorrespondent = pick('plCorrespondent', platform);
  o.plSourceUrl = pick('plSourceUrl', typed.url || '');
  return o;
}
````

- [ ] **Step 4: Implement** `src/compare.js`

````js
// Compares generator output with a worked example from the guide.
import { plain } from './template.js';

export const COMPARED_FIELDS = ['title', 'abbrev', 'author', 'pubinfo', 'repository', 'callNumber', 'page', 'frn', 'srn'];

/** The guide's expected values for one claim: the whole example, or one citation of a multi-citation example. */
export function expectedFor(example, claim) {
  if (claim.citation) {
    const c = example.citations[claim.citation - 1] || {};
    const fields = {};
    for (const key of ['page', 'frn', 'srn']) if (c[key] !== undefined) fields[key] = c[key];
    return { fields, confidence: c.confidence || '' };
  }
  return { fields: example.expected, confidence: example.confidence };
}

/** Fields whose output differs from the guide. */
export function diffOutputs(expectedFields, outputs) {
  return COMPARED_FIELDS
    .filter(field => field in expectedFields && expectedFields[field] !== plain(outputs[field]))
    .map(field => ({ field, want: expectedFields[field], got: plain(outputs[field]) }));
}
````

- [ ] **Step 5: Run the test to confirm it passes**

Run: `node --test test/engine.test.js`
Expected: `tests 15`, `pass 15`, `fail 0`.

- [ ] **Step 6: Commit**

```bash
git add src/engine.js src/compare.js test/engine.test.js
git commit -m "Add draft engine and example comparison" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 5: Guide checks and the Norwegian record types

The four guide checks from the spec (worked examples, pins, coverage, plus structural checks on every record type) arrive here with the first chapter. Until all four chapters exist, run the checks filtered to the chapter you are working on; the full suite goes green in Task 8.

**Files:**
- Create: `test/support/report.js`, `test/support/pending.js`, `test/support/not-covered.js`
- Create: `test/records.test.js`, `test/examples.test.js`, `test/pins.test.js`, `test/coverage.test.js`
- Create: `src/records/index.js` (Norwegian only for now)
- Create: `src/records/norwegian.js`

**Interfaces:**
- Consumes: `loadGuide`, `normalize`, `CHAPTERS` (Task 2); engine and compare exports (Task 4); `templateKeys` (Task 1); `CHAPTERS`, `LEVELS`, `DATE_MEANING` (Task 3).
- Produces: `RECORDS`, `recordById(id)` (from `src/records/index.js`); `NORWEGIAN` (9 record types: `no-ministerialbok`, `no-klokkerbok`, `no-confirmation`, `no-minutes`, `no-folketelling-1801`, `no-folketelling`, `no-tingbok`, `no-skifteprotokoll`, `no-matrikkel`); `PENDING`, `NOT_COVERED`, `diffExcerpt`, `differsMessage`, `closestLine` (test support).

- [ ] **Step 1: Add the test support files**

`test/support/report.js`:

````js
// Readable failure messages for the guide checks.

/** The differing region of two strings, with some context either side. */
export function diffExcerpt(want, got, context = 40) {
  let start = 0;
  while (start < want.length && start < got.length && want[start] === got[start]) start++;
  let end = 0;
  while (end < want.length - start && end < got.length - start && want[want.length - 1 - end] === got[got.length - 1 - end]) end++;
  const clip = text => {
    const from = Math.max(0, start - context);
    const to = Math.min(text.length, text.length - end + context);
    return (from > 0 ? '…' : '') + text.slice(from, to) + (to < text.length ? '…' : '');
  };
  return { want: clip(want), got: clip(got) };
}

export function differsMessage(label, want, got) {
  const d = diffExcerpt(want, got);
  return `${label}\n    guide:     ${d.want}\n    generator: ${d.got}`;
}

/** The line in `lines` most similar to `text` (character bigram overlap). */
export function closestLine(text, lines) {
  const grams = s => {
    const out = new Map();
    for (let i = 0; i < s.length - 1; i++) out.set(s.slice(i, i + 2), (out.get(s.slice(i, i + 2)) || 0) + 1);
    return out;
  };
  const a = grams(text);
  let best = '', bestScore = -1;
  for (const line of lines) {
    const b = grams(line);
    let shared = 0;
    for (const [g, n] of a) shared += Math.min(n, b.get(g) || 0);
    const score = (2 * shared) / (text.length + line.length || 1);
    if (score > bestScore) { best = line; bestScore = score; }
  }
  return best;
}
````

`test/support/pending.js` (the guide contradictions found at design time, all chapters):

````js
// Worked-example fields that differ because the guide contradicts itself. Each stays a TODO
// (reported, not failed) until the guide is corrected; then delete its entry.
// Key: example id, plus " · citation N" for one citation of a multi-citation example.
export const PENDING = {
  'B.1 Example 1': { srn: 'Page string says "Thor Emil birth and baptism entry"; the SRN says "baptism entry".' },
  'B.1 Example 3': {
    frn: 'Page string writes "folio 145-148" (hyphen); the FRN writes "145–148" (en dash).',
    srn: 'Page string writes "folio 145-148" (hyphen); the SRN writes "145–148" (en dash).',
  },
  'B.2 Example 2': {
    frn: 'Review queue C7: Call number is SE/VA/11047/F II/26 but the FRN cites SE/VA/11047.',
    srn: 'The SRN ends ", Ambjörbymon"; other SRNs carry no place.',
  },
  'B.3 Example 8': { srn: 'The SRN names "Per L. Grund"; the page string names "Per Larsson Grund".' },
  'B.3 Example 11': {
    frn: 'Page string says "(image 496, right)"; the FRN says "(image 496)".',
    srn: 'The SRN uses "death and burial of … died 7 May 1914"; other SRNs use the subject without dates.',
  },
  'B.4 Family Bible': {
    frn: 'Page string names "Per Larsson Grund"; the FRN says "entry for Per Larsson".',
    srn: 'Page string names "Per Larsson Grund"; the SRN says "Per Larsson birth entry".',
  },
  'B.4 Funeral program': { pubinfo: 'Review queue C11: the example omits the funeral home that A10 requires.' },
  'B.4 Audio interview': { frn: 'Repository says "Peter Michael Grund"; the FRN says "privately held by Peter Grund".' },
  'B.4 Personal research': { srn: 'Page string says "Entry for Ambmyra, typed page…"; the SRN says "Ambmyra typed page…".' },
};
````

`test/support/not-covered.js`:

````js
// §4 and §7 table rows deliberately without a record type, with the reason.
// Format: { section: 'B.3 §7', row: 'Label | template', reason: '…' }. Empty: every row is covered.
export const NOT_COVERED = [];
````

- [ ] **Step 2: Write the four guide checks**

`test/records.test.js`:

````js
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { RECORDS } from '../src/records/index.js';
import { inputFields, resolveType, ENGINE_TOKENS, STANDARD_VALUES, TEMPLATE_KEYS, SUBJECT_KEYS, HOLDER_KEYS } from '../src/engine.js';
import { templateKeys } from '../src/template.js';
import { CHAPTERS, LEVELS, DATE_MEANING } from '../src/tables.js';

test('record type ids are unique', () => {
  const ids = RECORDS.map(r => r.id);
  assert.deepEqual(ids.filter((id, i) => ids.indexOf(id) !== i), []);
});

for (const r of RECORDS) {
  const variants = r.pageVariants || [null];
  const derived = Object.keys(r.derive ? r.derive({ name: '', noun: '' }) : {});

  test(`${r.id}: required parts`, () => {
    assert.ok(CHAPTERS[r.chapter], 'unknown chapter');
    assert.ok(r.name && r.group, 'name and group');
    assert.ok(Array.isArray(r.source) && Array.isArray(r.nouns) && r.nouns.length, 'source and nouns');
    assert.ok(LEVELS.includes(r.confidence) || r.confidence === '', `confidence "${r.confidence}"`);
    assert.ok(r.doctype in DATE_MEANING, `document type "${r.doctype}"`);
    assert.equal(typeof r.title, 'string');
    for (const v of variants) {
      const t = resolveType(r, v ? { variant: v.key } : {});
      for (const key of ['page', 'frn', 'srn']) assert.equal(typeof t[key], 'string', `${v ? v.key + ': ' : ''}${key}`);
    }
  });

  test(`${r.id}: input and derived names do not clash with engine names`, () => {
    for (const [key] of inputFields(r)) {
      assert.ok(!ENGINE_TOKENS.includes(key) && !STANDARD_VALUES.includes(key), `input "${key}"`);
    }
    for (const key of derived) assert.ok(!ENGINE_TOKENS.includes(key), `derived "${key}"`);
  });

  test(`${r.id}: every {token} in its templates is defined`, () => {
    const known = new Set([...inputFields(r).map(([key]) => key), ...STANDARD_VALUES, ...ENGINE_TOKENS, ...derived]);
    for (const t of [r, ...(r.pageVariants || [])]) {
      for (const key of TEMPLATE_KEYS) {
        for (const token of templateKeys(t[key])) assert.ok(known.has(token), `${key} uses unknown {${token}}`);
      }
    }
  });

  test(`${r.id}: example inputs name real fields`, () => {
    const known = new Set([...inputFields(r).map(([key]) => key), ...STANDARD_VALUES, ...SUBJECT_KEYS, ...HOLDER_KEYS, 'confidence', 'variant']);
    for (const claim of r.examples) {
      for (const key of Object.keys(claim.inputs)) assert.ok(known.has(key), `${claim.guide}: unknown input "${key}"`);
    }
  });
}
````

`test/examples.test.js`:

````js
// Check 1: every worked example in the guide is claimed by a record type and reproduced exactly.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { loadGuide } from '../tools/guide.js';
import { RECORDS } from '../src/records/index.js';
import { draftFromExample, buildOutputs } from '../src/engine.js';
import { expectedFor, COMPARED_FIELDS } from '../src/compare.js';
import { plain } from '../src/template.js';
import { PENDING } from './support/pending.js';
import { differsMessage } from './support/report.js';

const examples = loadGuide().examples();
const claims = RECORDS.flatMap(record => record.examples.map(claim => ({ record, claim })));

for (const ex of examples) {
  const citations = ex.citations.length ? ex.citations.map((_, i) => i + 1) : [0];
  for (const n of citations) {
    const label = n ? `${ex.id} · citation ${n}` : ex.id;
    const mine = claims.filter(({ claim }) => claim.guide === ex.id && (claim.citation || 0) === n);

    test(`${label} is claimed by a record type`, () => {
      assert.ok(mine.length, `No record type claims ${label}. Add it to a record type's examples.`);
    });

    for (const { record, claim } of mine) {
      const out = buildOutputs(record, draftFromExample(record, claim));
      const { fields, confidence } = expectedFor(ex, claim);
      for (const field of COMPARED_FIELDS.filter(f => f in fields)) {
        const reason = PENDING[label]?.[field];
        const name = `${label} · ${record.id} · ${field}`;
        test(name, reason ? { todo: reason } : {}, () => {
          const got = plain(out[field]);
          assert.ok(got === fields[field], differsMessage(name, fields[field], got));
        });
      }
      if (confidence) {
        test(`${label} · ${record.id} · confidence`, () => assert.equal(out.confidence, confidence));
      }
      for (const [field, why] of Object.entries(ex.skipped)) {
        test(`${label} · ${field} not compared`, { skip: why }, () => {});
      }
    }
  }
}

test('every claim points at a real worked example', () => {
  const ids = new Set(examples.map(e => e.id));
  for (const { record, claim } of claims) assert.ok(ids.has(claim.guide), `${record.id} claims unknown example "${claim.guide}"`);
});

test('every pending entry is still a real difference', () => {
  for (const [label, fields] of Object.entries(PENDING)) {
    const [id, citation] = label.split(' · citation ');
    const ex = examples.find(e => e.id === id);
    assert.ok(ex, `Pending entry for unknown example "${label}"`);
    const { record, claim } = claims.find(c => c.claim.guide === id && (c.claim.citation || 0) === Number(citation || 0)) || {};
    assert.ok(record, `Pending entry "${label}" has no claim`);
    const out = buildOutputs(record, draftFromExample(record, claim));
    const expected = expectedFor(ex, claim).fields;
    for (const field of Object.keys(fields)) {
      assert.notEqual(plain(out[field]), expected[field], `${label} · ${field} now matches the guide: remove it from test/support/pending.js`);
    }
  }
});
````

`test/pins.test.js`:

````js
// Check 2: every pinned row still appears, word for word, in its guide section.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { loadGuide, normalize } from '../tools/guide.js';
import { RECORDS } from '../src/records/index.js';
import { closestLine } from './support/report.js';

const guide = loadGuide();

for (const r of RECORDS) {
  for (const [field, pins] of Object.entries(r.pins || {})) {
    pins.forEach(([section, text], i) => {
      test(`pin ${r.id}.${field}${pins.length > 1 ? ` #${i + 1}` : ''} · ${section}`, () => {
        const body = guide.sectionText(section);
        assert.ok(body !== null, `Section ${section} is not in the guide`);
        const pinned = normalize(text);
        if (!body.includes(pinned)) {
          assert.fail(`Pinned text is no longer in ${section}.\n    pinned:      ${pinned}\n    closest now: ${closestLine(pinned, guide.sectionLines(section))}`);
        }
      });
    });
  }
}

test('unpinned templates (places where the guide has no row or example yet)', t => {
  const unpinned = [];
  for (const r of RECORDS) {
    if (r.examples.length) continue;
    for (const key of ['title', 'abbrev', 'author', 'page', 'frn', 'srn']) {
      if (!r.pins?.[key]?.length) unpinned.push(`${r.id}.${key}`);
    }
  }
  t.diagnostic(`Unpinned: ${unpinned.join(', ') || 'none'}`);
});
````

`test/coverage.test.js`:

````js
// Check 3: every row of each chapter's §4 title table and §7 page-string table is covered.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { loadGuide, normalize, CHAPTERS } from '../tools/guide.js';
import { RECORDS } from '../src/records/index.js';
import { NOT_COVERED } from './support/not-covered.js';

const guide = loadGuide();
const pins = RECORDS.flatMap(r => Object.values(r.pins || {}).flat()).map(([section, text]) => [section, normalize(text)]);

for (const chapter of CHAPTERS) {
  for (const s of ['§4', '§7']) {
    const section = `${chapter} ${s}`;
    const [table] = guide.tables(section);
    test(`${section} has a table`, () => assert.ok(table, `No table in ${section}`));
    for (const row of table?.rows || []) {
      const key = `${row[0]} | ${row[1]}`;
      test(`coverage ${section} · ${row[0]}`, () => {
        const pinned = pins.some(([sec, text]) => sec === section && text === key);
        const excused = NOT_COVERED.some(n => n.section === section && normalize(n.row) === key);
        assert.ok(pinned || excused, `No record type covers ${section} "${key}". Pin it from a record type or list it in test/support/not-covered.js.`);
      });
    }
  }
}

test('not-covered entries name real rows', () => {
  for (const n of NOT_COVERED) {
    const rows = guide.tables(n.section)[0]?.rows || [];
    assert.ok(rows.some(row => `${row[0]} | ${row[1]}` === normalize(n.row)), `${n.section} "${n.row}" is not a row any more`);
  }
});
````

- [ ] **Step 3: Create `src/records/index.js` with the Norwegian chapter only**

```js
// Every record type, in sidebar order.
import { NORWEGIAN } from './norwegian.js';

export const RECORDS = [...NORWEGIAN];

export function recordById(id) {
  return RECORDS.find(r => r.id === id) || null;
}
```

- [ ] **Step 4: Run the Norwegian checks to confirm they fail**

Run: `node --test --test-name-pattern="B\.1|no-" test/records.test.js test/examples.test.js test/pins.test.js test/coverage.test.js`
Expected: FAIL with `ERR_MODULE_NOT_FOUND` for `src/records/norwegian.js`.

- [ ] **Step 5: Implement** `src/records/norwegian.js`

````js
// B.1 · Norwegian sources.
const DIGITAL_IMAGE = 'digital image, {platform} ({url} : accessed {accessed})';
const OSLO = { heldBy: 'archive', archive: 'Statsarkivet i Oslo', platform: 'Digitalarkivet', medium: 'Digital images' };
const RIKSARKIVET = { heldBy: 'archive', archive: 'Riksarkivet', platform: 'Digitalarkivet', medium: 'Database with images' };

const PARISH_SOURCE = [
  ['fylke', 'Fylke / amt', 'Akershus'], ['parish', 'Parish', 'Eidsvoll'], ['vol', 'Volume', 'I 5'],
  ['years', 'Years', '1862–1869'], ['call', 'Call number', 'AV/SAO-A-10888/A/Aa/L0005'],
];
const PARISH_LOCATORS = [['page', 'Page'], ['image', 'Image', 'if not the page'], ['entry', 'Entry no.']];
const PARISH_NOUNS = ['birth and baptism entry', 'baptism entry', 'death entry', 'burial entry', 'marriage'];
const PARISH_PAGE_PIN = ['B.1 §7', 'Parish | p. [P] (image [I]), [entry], [subject]'];

export const NORWEGIAN = [
  {
    id: 'no-ministerialbok', chapter: 'no', group: 'Parish registers (kirkebøker)', name: 'Ministerialbok',
    hint: "The minister's original register",
    source: PARISH_SOURCE, citation: PARISH_LOCATORS, nouns: PARISH_NOUNS,
    holder: OSLO, confidence: 'Very High', doctype: 'vital record',
    title: 'Norway, {fylke}, {parish}, parish registers, Ministerialbok {vol}, {years}',
    abbrev: '{parish} kirkebok {vol} ({years})',
    author: '{parish} prestekontor',
    page: 'p. {page}« (image {image})», no. {entry}, {subject}',
    frn: `{parish} prestekontor Kirkebøker [parish records], ministerialbok no. {vol}, {years}, p. {page}, no. {entry}, {name}« {details}»; ${DIGITAL_IMAGE}; citing {repository}, {call}.`,
    srn: '{parish} kirkebok {vol} ({years}), p. {page}, no. {entry}, {subject}.',
    detailsLabel: 'Entry details (dates, parents, church)',
    pins: {
      title: [['B.1 §4', "Parish, minister's original | Norway, [Fylke/Amt], [Parish], parish registers, Ministerialbok [Roman] [Arabic], [years]"]],
      page: [PARISH_PAGE_PIN],
      author: [['B.1 §2', 'Parish records | [Parish] prestekontor']],
      abbrev: [['B.1 §10', 'Ministerialbok I 5 | kirkebok I 5']],
      confidence: [['B.1 §8', 'Ministerialbok | Very High for an entry written by the minister within days']],
    },
    examples: [],
  },
  {
    id: 'no-klokkerbok', chapter: 'no', group: 'Parish registers (kirkebøker)', name: 'Klokkerbok',
    hint: "The sacristan's duplicate (parish register copy). Prefer the ministerialbok when you can reach it.",
    source: PARISH_SOURCE, citation: PARISH_LOCATORS, nouns: PARISH_NOUNS,
    holder: OSLO, confidence: 'High', doctype: 'vital record',
    title: 'Norway, {fylke}, {parish}, parish registers, Parish register (copy) {vol}, {years}',
    abbrev: '{parish} klokkerbok {vol} ({years})',
    author: '{parish} prestekontor',
    page: 'p. {page}« (image {image})», no. {entry}, {subject}',
    frn: `{parish} prestekontor Kirkebøker [parish records], parish register (copy) no. {vol}, {years}, p. {page}, no. {entry}, {name}« {details}»; ${DIGITAL_IMAGE}; citing {repository}, {call}.`,
    srn: '{parish} klokkerbok {vol} ({years}), p. {page}, no. {entry}, {subject}.',
    detailsLabel: 'Entry details (dates, parents, church)',
    pins: {
      title: [['B.1 §4', 'Parish, klokkerbok | …, parish registers, Parish register (copy) [Roman] [Arabic], [years]']],
      page: [PARISH_PAGE_PIN],
      author: [['B.1 §2', 'Parish records | [Parish] prestekontor']],
      abbrev: [['B.1 §10', 'Parish register (copy) I 2 | klokkerbok I 2']],
      confidence: [['B.1 §8', 'Klokkerbok | High by default (contemporaneous duplicate)']],
    },
    examples: [{
      guide: 'B.1 Example 1',
      inputs: {
        fylke: 'Akershus', parish: 'Eidsvoll', vol: 'I 2', years: '1866–1871', call: 'AV/SAO-A-10888/G/Ga/L0002',
        page: '57', image: '62', entry: '21', name: 'Thor Emil', noun: 'birth and baptism entry',
        url: 'https://urn.digitalarkivet.no/URN:NBN:no-a1450-kb20060313011115.jpg', accessed: '17 April 2026', eventYear: '1869',
        details: '(born 1 September 1869; baptized 16 January 1870), son of Christian Henningsen and Anne Marthe Bergersdatter, baptized at Eidsvoll church',
      },
    }],
  },
  {
    id: 'no-confirmation', chapter: 'no', group: 'Parish registers (kirkebøker)', name: 'Confirmation or communion',
    hint: 'Recorded inside the kirkebok; cite it under that volume’s Source.',
    source: [
      ['fylke', 'Fylke / amt', 'Akershus'], ['parish', 'Parish', 'Eidsvoll'],
      ['book', 'Book', 'Ministerialbok or Parish register (copy)'], ['vol', 'Volume', 'I 2'],
      ['years', 'Years', '1866–1871'], ['call', 'Call number', 'AV/SAO-A-10888/G/Ga/L0002'],
    ],
    citation: [['section', 'Section', 'confirmations or communicants'], ['page', 'Page'], ['image', 'Image', 'if not the page'], ['entry', 'Entry no.']],
    nouns: ['confirmation entry', 'communion entry'],
    holder: OSLO, confidence: 'High', doctype: 'religious',
    derive: v => {
      const minister = /^minist/i.test(v.book || '');
      return { kb: minister ? 'kirkebok' : 'klokkerbok', kbl: minister ? 'ministerialbok' : 'parish register (copy)' };
    },
    title: 'Norway, {fylke}, {parish}, parish registers, {book} {vol}, {years}',
    abbrev: '{parish} {kb} {vol} ({years})',
    author: '{parish} prestekontor',
    page: '{section}, p. {page}« (image {image})»«, no. {entry}», {subject}',
    frn: `{parish} prestekontor Kirkebøker [parish records], {kbl} no. {vol}, {years}, {section} section, p. {page}«, no. {entry}», {name}« {details}»; ${DIGITAL_IMAGE}; citing {repository}, {call}.`,
    srn: '{parish} {kb} {vol} ({years}), {section}, p. {page}«, no. {entry}», {subject}.',
    detailsLabel: 'Entry details (parents, church, year)',
    pins: {
      title: [['B.1 §4', "Confirmation and communion have no Title of their own; they use the kirkebok's Title."]],
      page: [
        ['B.1 §7', 'Confirmation Pending review | confirmations, p. [P] (image [I]), no. [N], [Subject] confirmation entry'],
        ['B.1 §7', 'Communion Pending review | communicants, p. [P] (image [I]), [Subject] communion entry'],
      ],
      author: [['B.1 §2', 'Confirmation, communion | [Parish] prestekontor']],
      confidence: [['B.1 §8', 'Confirmation entry Pending review | High for the confirmation']],
    },
    examples: [{
      guide: 'B.1 Example 5',
      inputs: {
        fylke: 'Akershus', parish: 'Eidsvoll', book: 'Parish register (copy)', vol: 'I 2', years: '1866–1871',
        call: 'AV/SAO-A-10888/G/Ga/L0002', section: 'confirmations', page: '88', image: '91', entry: '14',
        name: 'Karen Indiana Evensdatter', noun: 'confirmation entry',
        url: 'https://www.digitalarkivet.no/...', accessed: '15 June 2026', eventYear: '1869',
        details: '(daughter of Even Hansen), confirmed at Eidsvoll church 1869',
      },
    }],
  },
  {
    id: 'no-minutes', chapter: 'no', group: 'Parish registers (kirkebøker)', name: 'Parish meeting minutes',
    hint: 'Menighetsmøteprotokoll, a series of its own',
    source: [
      ['fylke', 'Fylke / amt', 'Akershus'], ['parish', 'Parish', 'Eidsvoll'], ['vol', 'Volume', '1'],
      ['years', 'Years', '1870–1895'], ['call', 'Call number'],
    ],
    citation: [['page', 'Page'], ['image', 'Image', 'if not the page'], ['date', 'Meeting date']],
    nouns: ['minute entry'],
    holder: OSLO, confidence: 'High', doctype: 'religious',
    title: 'Norway, {fylke}, {parish}, menighetsmøteprotokoll [parish meeting minutes], {vol}, {years}',
    abbrev: '{parish} menighetsmøteprotokoll {vol}',
    author: '{parish} prestekontor',
    page: 'p. {page}« (image {image})», {date}, {subject}',
    frn: `{parish} prestekontor, menighetsmøteprotokoll [parish meeting minutes] no. {vol}, {years}, p. {page}, {date}, {subject}«, {details}»; ${DIGITAL_IMAGE}; citing {repository}«, {call}».`,
    srn: '{parish} menighetsmøteprotokoll {vol}, p. {page}, {subject}.',
    subjectLabel: 'Meeting subject',
    pins: {
      title: [['B.1 §4', 'Meeting minutes | Norway, [Fylke/Amt], [Parish], parish meeting minutes (menighetsmøteprotokoll), [vol], [years]']],
      page: [['B.1 §7', 'Meeting minutes Pending review | p. [P] (image [I]), [date], [subject] minute entry']],
      abbrev: [['B.1 §10', 'Meeting minutes 1 Pending review | menighetsmøteprotokoll 1']],
      confidence: [['B.1 §8', 'Meeting minutes Pending review | High for the recorded act or attendance']],
    },
    examples: [],
  },
  {
    id: 'no-folketelling-1801', chapter: 'no', group: 'Census (folketelling)', name: 'Folketelling 1801',
    hint: 'Nominal census, organized by gård',
    source: [['amt', 'Amt', 'Akershus'], ['prestegjeld', 'Prestegjeld', 'Eidsvoll'], ['ref', 'Reference (if needed)', 'L0009'], ['call', 'Call number']],
    citation: [['gard', 'Gård no.'], ['gardname', 'Gård name'], ['hh', 'Household'], ['person', 'Person']],
    nouns: ['household'],
    holder: RIKSARKIVET, confidence: 'Very High', doctype: 'enumeration',
    title: 'Norway, {amt}, {prestegjeld}, folketelling 1801«, {ref}»',
    abbrev: '{prestegjeld} folketelling 1801',
    author: 'Riksarkivet',
    page: 'Gård {gard} ({gardname}), household {hh}, person {person}, {subject}',
    frn: `Folketelling 1801 [population census 1801], {amt}, {prestegjeld} prestegjeld, gård {gard} ({gardname}), household no. {hh}, person no. {person}, {name}«, {details}»; ${DIGITAL_IMAGE}; citing {repository}«, {call}».`,
    srn: '{prestegjeld} folketelling 1801, gård {gard}, household {hh}, {subject}.',
    pins: {
      title: [['B.1 §4', 'Folketelling 1801 | Norway, [Amt], [Prestegjeld], folketelling 1801, [reference if needed]']],
      page: [['B.1 §7', 'Folketelling 1801 | Gård [N] ([name]), household [N], person [N], [Subject] household']],
      author: [['B.1 §2', 'Folketelling | Riksarkivet (preferred)']],
      abbrev: [['B.1 §10', 'folketelling YYYY | folketelling YYYY']],
      confidence: [['B.1 §8', 'Folketelling 1801 | Very High for residence (enumerator visited each gård); Normal for ages']],
    },
    examples: [],
  },
  {
    id: 'no-folketelling', chapter: 'no', group: 'Census (folketelling)', name: 'Folketelling 1865 and later',
    hint: 'Decennial census, by sokn and district. Use the jurisdiction names the census itself uses.',
    source: [['amt', 'Amt or fylke', 'Akershus'], ['prestegjeld', 'Prestegjeld or herred', 'Eidsvoll'], ['year', 'Census year', '1875'], ['call', 'Call number', 'AV/RA-S-2231/E']],
    citation: [['district', 'District (tellekrets)', '009 Blegstad'], ['page', 'Page'], ['hh', 'Household'], ['person', 'Person']],
    note: [['sokn', 'Sokn (FRN)'], ['turl', 'Transcribed entry URL'], ['citing', 'Citing, after the repository']],
    nouns: ['household'],
    holder: RIKSARKIVET, confidence: 'High', doctype: 'enumeration',
    title: 'Norway, {amt}, {prestegjeld}, folketelling {year}',
    abbrev: '{prestegjeld} folketelling {year}',
    author: 'Riksarkivet',
    page: 'District {district}, p. {page}, household {hh}, person {person}, {subject}',
    frn: `Folketelling {year} [population census {year}], {amt} fylke, {prestegjeld} prestegjeld«, {sokn} sokn», district {district}, p. {page}, household no. {hh}, person no. {person}, {name}« ({details})»; ${DIGITAL_IMAGE}«; transcribed entry at {turl}»; citing {repository}«, {citing}»; archive reference {call}.`,
    srn: 'Folketelling {year}, {prestegjeld}, p. {page}, household {hh}, {name}.',
    detailsLabel: 'Entry details (role, age, household)',
    pins: {
      title: [['B.1 §4', 'Folketelling 1865+ | Norway, [Amt or fylke], [Prestegjeld or herred], folketelling [year]']],
      page: [['B.1 §7', 'Folketelling 1865+ | District [N] [name], p. [N], household [N], person [N], [Subject]']],
      author: [['B.1 §2', 'Folketelling | Riksarkivet (preferred)']],
      abbrev: [['B.1 §10', 'folketelling YYYY | folketelling YYYY']],
      confidence: [['B.1 §8', 'Folketelling 1865+ | High for residence and household; Normal for ages and birthplaces']],
    },
    examples: [{
      guide: 'B.1 Example 2',
      inputs: {
        amt: 'Akershus', prestegjeld: 'Eidsvoll', year: '1875', call: 'AV/RA-S-2231/E',
        district: '009 Blegstad', page: '1270', hh: '01', person: '006',
        name: 'Karen Indiana Evensdatter', noun: 'household', says: 'tjenestepige', evidence: 'stated age 14', nonHead: true, head: 'Hansen',
        sokn: 'Eidsvoll', url: 'https://www.digitalarkivet.no/ft20110110330371', accessed: '26 April 2026', eventYear: '1875',
        turl: 'https://www.digitalarkivet.no/pf01052052005225',
        citing: 'Statistisk sentralbyrå, Sosioøkonomiske emner, Folketellinger, boliger og boforhold, E: Folketellinger, source ID 52052',
        details: "tjenestepige, stated age 14, in Jens Hansen's household",
      },
    }],
  },
  {
    id: 'no-tingbok', chapter: 'no', group: 'Court and land', name: 'Tingbok',
    hint: 'District court journal (sorenskriverarkiv)',
    source: [['fylke', 'Fylke / amt', 'Akershus'], ['court', 'Sorenskriveri', 'Eidsvoll sorenskriveri'], ['series', 'Series', 'A I 5'], ['years', 'Years', '1820–1830'], ['call', 'Call number']],
    citation: [['folio', 'Folio'], ['session', 'Date or session']],
    nouns: ['land dispute', 'court matter'],
    holder: OSLO, confidence: '', doctype: 'legal',
    title: 'Norway, {fylke}, {court}, Tingbok {series}, {years}',
    abbrev: '{court} tingbok {series} ({years})',
    author: '{court}',
    page: 'folio {folio}, {session}, {subject}',
    frn: `{court} [district court], Tingbok [court journal] {series}, {years}, folio {folio}, {session}, {subject}«, {details}»; ${DIGITAL_IMAGE}; citing {repository}«, {call}».`,
    srn: '{court} tingbok {series}, fol. {folio}, {subject}.',
    subjectLabel: 'Parties or subject',
    pins: {
      title: [['B.1 §4', 'Court (tingbok) | Norway, [Fylke/Amt], [Sorenskriveri], Tingbok [series], [years]']],
      page: [['B.1 §7', 'Tingbok | folio [F], [date or session], [parties or subject]']],
      author: [['B.1 §2', 'Court records | The creating body, e.g. Eidsvoll sorenskriveri']],
      abbrev: [['B.1 §10', 'Tingbok A I 5 | tingbok A I 5']],
    },
    examples: [],
  },
  {
    id: 'no-skifteprotokoll', chapter: 'no', group: 'Court and land', name: 'Skifteprotokoll',
    hint: 'Probate register; folios for the whole skifte go in the page string',
    source: [['fylke', 'Fylke / amt', 'Akershus'], ['court', 'Sorenskriveri', 'Eidsvoll sorenskriveri'], ['series', 'Series', 'II 3'], ['years', 'Years', '1815–1825'], ['call', 'Call number', 'AV/SAO-A-10063/H/Hb/L0003']],
    citation: [['folio', 'Folio range', '145–148']],
    nouns: ['estate'],
    holder: OSLO, confidence: 'High', doctype: 'legal',
    derive: v => ({ cs: String(v.court || '').replace(/\s+sorenskriveri$/i, '').trim() }),
    title: 'Norway, {fylke}, {court}, Skifteprotokoll {series}, {years}',
    abbrev: '{cs} skifteprotokoll {series} ({years})',
    author: '{court}',
    page: 'folio {folio}, {subject}',
    frn: `{court} [{cs} district court], Skifteprotokoll [probate register] {series}, {years}, folio {folio}, estate inventory of {name}«, {details}»; ${DIGITAL_IMAGE}; citing {repository}, {call}.`,
    srn: '{cs} skifteprotokoll {series}, fol. {folio}, {subject}.',
    subjectLabel: 'Deceased',
    detailsLabel: 'Entry details (farm, death)',
    pins: {
      title: [['B.1 §4', 'Probate | Norway, [Fylke/Amt], [Sorenskriveri], Skifteprotokoll [series], [years]']],
      page: [['B.1 §7', 'Skifteprotokoll | folio [F]-[F], [Deceased] estate']],
      author: [['B.1 §2', 'Probate | The court that conducted it, usually [District] sorenskriveri']],
      abbrev: [['B.1 §10', 'Skifteprotokoll II 3 | skifteprotokoll II 3']],
      confidence: [['B.1 §8', 'Skifteprotokoller | High for the death and primary heirs']],
    },
    examples: [{
      guide: 'B.1 Example 3',
      inputs: {
        fylke: 'Akershus', court: 'Eidsvoll sorenskriveri', series: 'II 3', years: '1815–1825', call: 'AV/SAO-A-10063/H/Hb/L0003',
        folio: '145-148', name: 'Anders Hansen', noun: 'estate',
        url: 'https://www.digitalarkivet.no/...', accessed: '9 May 2026', eventYear: '1822',
        details: 'Vinger gård, died 1822',
      },
    }],
  },
  {
    id: 'no-matrikkel', chapter: 'no', group: 'Court and land', name: 'Matrikkel',
    hint: 'Cadastral register; one Source per revision (1665, 1723, 1838, 1886/1904…)',
    source: [
      ['amt', 'Amt or fylke (as written)', 'Akershus amt'], ['prestegjeld', 'Prestegjeld or herred (as written)', 'Eidsvoll prestegjeld'],
      ['year', 'Matrikkel year', '1838'], ['protocol', 'Protocol (if needed)'], ['call', 'Call number'],
    ],
    citation: [['gard', 'Gård no.'], ['gardname', 'Gård name', 'Vinger gård'], ['lnr', 'Løpenummer']],
    nouns: ['matrikkel entry'],
    holder: RIKSARKIVET, confidence: 'High', doctype: 'legal',
    derive: v => ({
      short: String(v.prestegjeld || '').replace(/\s+(prestegjeld|herred)$/i, '').trim(),
      gardshort: String(v.gardname || '').replace(/\s+gård$/i, '').trim(),
    }),
    title: 'Norway, {amt}, {prestegjeld}, matrikkel {year}«, {protocol}»',
    abbrev: '{short} matrikkel {year}',
    author: 'Riksarkivet',
    page: 'Gård no. {gard}, {gardname}«, løpenummer {lnr}», {subject}',
    frn: `Matrikkel {year} [land register {year}], {amt}, {prestegjeld}, gård no. {gard}, {gardname}«, løpenummer {lnr}», listed owner {name}«, {details}»; ${DIGITAL_IMAGE}; citing {repository}«, {call}».`,
    srn: '{short} matrikkel {year}, gård {gard} {gardshort}«, løpenr. {lnr}», {name}.',
    subjectLabel: 'Owner or topic',
    pins: {
      title: [['B.1 §4', 'Matrikkel | Norway, [Fylke or amt], [Prestegjeld or herred], matrikkel [year], [protocol if needed]']],
      page: [['B.1 §7', 'Matrikkel | Gård no. [matrikkelnr.], [gård name], [løpenummer if specific], [owner or topic]']],
      author: [['B.1 §2', 'Matrikkel | Riksarkivet for centrally held volumes']],
      abbrev: [['B.1 §10', 'matrikkel 1838 | matrikkel 1838']],
      confidence: [['B.1 §8', 'Matrikkel | High for the cadastral fact; Low for any genealogical inference']],
    },
    examples: [{
      guide: 'B.1 Example 4',
      inputs: {
        amt: 'Akershus amt', prestegjeld: 'Eidsvoll prestegjeld', year: '1838',
        gard: '234', gardname: 'Vinger gård', lnr: '12', name: 'Anders Hansen', noun: 'matrikkel entry',
        url: 'https://www.digitalarkivet.no/...', accessed: '9 May 2026', eventYear: '1838',
      },
    }],
  },
];

````

- [ ] **Step 6: Run the Norwegian checks to confirm they pass**

Run: `node --test --test-name-pattern="B\.1|no-" test/records.test.js test/examples.test.js test/pins.test.js test/coverage.test.js`
Expected: `tests 147`, `pass 143`, `fail 0`, `skipped 1` (B.1 Ex. 4's Open call number), `todo 3` (B.1 Ex. 1 SRN; B.1 Ex. 3 FRN and SRN).

- [ ] **Step 7: Commit**

```bash
git add test/support test/records.test.js test/examples.test.js test/pins.test.js test/coverage.test.js src/records/index.js src/records/norwegian.js
git commit -m "Add guide checks and Norwegian record types" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 6: Swedish record types

**Files:**
- Modify: `src/records/index.js`
- Create: `src/records/swedish.js`

**Interfaces:**
- Consumes: the record type shape (Task 4) and the checks (Task 5).
- Produces: `SWEDISH` (9 record types: `se-husforhor`, `se-dopbok`, `se-vigselbok`, `se-dodbok`, `se-confirmation`, `se-sockenstamma`, `se-bouppteckning`, `se-folkrakning`, `se-lantmateriet`).

- [ ] **Step 1: Register the chapter in `src/records/index.js`**

```js
// Every record type, in sidebar order.
import { NORWEGIAN } from './norwegian.js';
import { SWEDISH } from './swedish.js';

export const RECORDS = [...NORWEGIAN, ...SWEDISH];

export function recordById(id) {
  return RECORDS.find(r => r.id === id) || null;
}
```

- [ ] **Step 2: Run the Swedish checks to confirm they fail**

Run: `node --test --test-name-pattern="B\.2|se-" test/records.test.js test/examples.test.js test/pins.test.js test/coverage.test.js`
Expected: FAIL with `ERR_MODULE_NOT_FOUND` for `src/records/swedish.js`.

- [ ] **Step 3: Implement** `src/records/swedish.js`

````js
// B.2 · Swedish sources.
const DIGITAL_IMAGE = 'digital image, {platform} ({url} : accessed {accessed})';
const VARMLAND_RA = { heldBy: 'archive', archive: 'Värmlandsarkiv', platform: 'Riksarkivet', medium: 'Digital images' };
const VARMLAND_AD = { heldBy: 'archive', archive: 'Värmlandsarkiv', platform: 'ArkivDigital', medium: 'Digital images' };

const PARISH_SOURCE = [
  ['lan', 'Län', 'Värmland'], ['parish', 'Parish', 'Norra Ny'], ['vol', 'Volume', 'AI:11'],
  ['years', 'Years', '1812–1820'], ['call', 'Call number', 'SE/VA/13398/A I/11'],
];
const PAGE_IMAGE = [['page', 'Page'], ['image', 'Image', 'if not the page']];
const PAGE_IMAGE_ENTRY = [...PAGE_IMAGE, ['entry', 'Entry no.']];
const PARISH_AUTHOR_PIN = ['B.2 §2', 'Parish records, incl. confirmation, communion, minutes | [Parish] församling'];

/** Värmland → Värmlands län (Swedish genitive). */
const lanFull = lan => {
  const l = String(lan || '').trim();
  return l ? `${l.endsWith('s') ? l : l + 's'} län` : '';
};

export const SWEDISH = [
  {
    id: 'se-husforhor', chapter: 'se', group: 'Parish records (kyrkoarkiv)', name: 'Husförhörslängd',
    hint: 'Clerical survey (household examination); one Source per volume',
    source: PARISH_SOURCE, citation: PAGE_IMAGE, nouns: ['household', 'record'],
    holder: VARMLAND_RA, confidence: 'High', doctype: 'enumeration',
    title: 'Sweden, {lan}, {parish}, Husförhörslängder [household examinations] {vol}, {years}',
    abbrev: '{parish} husförhörslängd {vol} ({years})',
    author: '{parish} församling',
    page: 'p. {page}« (image {image})», {subject}',
    frn: `{parish} församling, Husförhörslängder [household examinations], vol. {vol} ({years}), p. {page}, {entryof}«, {details}»; ${DIGITAL_IMAGE}; citing {repository}, {call}.`,
    srn: '{parish} husförhörslängd {vol} ({years}), p. {page}, {subject}.',
    pins: {
      title: [['B.2 §4', 'Clerical survey | Sweden, [län], [parish], Husförhörslängder [household examinations] [vol], [years]']],
      page: [['B.2 §7', 'Husförhörslängd household | p. [P] (image [I]), [Head] household']],
      author: [PARISH_AUTHOR_PIN],
      abbrev: [['B.2 §10', 'Husförhörslängder | husförhörslängd']],
      confidence: [['B.2 §8', 'Husförhörslängd household | High residence; Normal stated age']],
    },
    examples: [{
      guide: 'B.2 Example 1',
      inputs: {
        lan: 'Värmland', parish: 'Norra Ny', vol: 'AI:11', years: '1812–1820', call: 'SE/VA/13398/A I/11',
        page: '8', image: '19', name: 'Per Persson', noun: 'household',
        url: 'https://sok.riksarkivet.se/bildvisning/C0038409_00019', accessed: '20 April 2026', eventYear: '1812–1820',
        details: 'Ambjörby Torpare',
      },
    }],
  },
  {
    id: 'se-dopbok', chapter: 'se', group: 'Parish records (kyrkoarkiv)', name: 'Födelse- och dopbok',
    hint: 'Birth and baptism book',
    source: PARISH_SOURCE, citation: PAGE_IMAGE_ENTRY, nouns: ['birth and baptism entry', 'birth entry', 'baptism entry'],
    holder: VARMLAND_AD, confidence: 'Very High', doctype: 'vital record',
    title: 'Sweden, {lan}, {parish}, Födelse- och dopböcker [birth and baptism books] {vol}, {years}',
    abbrev: '{parish} dopbok {vol} ({years})',
    author: '{parish} församling',
    page: 'p. {page}« (image {image})», no. {entry}, {subject}',
    frn: `{parish} församling, Födelse- och dopböcker [birth and baptism books], vol. {vol} ({years}), p. {page}, no. {entry}, {entryof}«, {details}»; ${DIGITAL_IMAGE}; citing {repository}, {call}.`,
    srn: '{parish} dopbok {vol} ({years}), p. {page}, no. {entry}, {subject}.',
    pins: {
      title: [['B.2 §4', 'Birth and baptism | …, Födelse- och dopböcker [birth and baptism books] [vol], [years]']],
      page: [['B.2 §7', 'Birth and baptism | p. [P] (image [I]), no. [N], [Name] birth and baptism entry']],
      author: [PARISH_AUTHOR_PIN],
      abbrev: [['B.2 §10', 'Födelse- och dopböcker | dopbok']],
      confidence: [['B.2 §8', "Birth and baptism | Very High (child's birth/baptism)"]],
    },
    examples: [],
  },
  {
    id: 'se-vigselbok', chapter: 'se', group: 'Parish records (kyrkoarkiv)', name: 'Lysnings- och vigselbok',
    hint: 'Banns and marriage book',
    source: PARISH_SOURCE, citation: PAGE_IMAGE_ENTRY, nouns: ['marriage'],
    holder: VARMLAND_AD, confidence: 'High', doctype: 'vital record',
    title: 'Sweden, {lan}, {parish}, Lysnings- och Vigselbok [banns and marriage book] {vol}, {years}',
    abbrev: '{parish} vigselbok {vol} ({years})',
    author: '{parish} församling',
    page: 'p. {page}« (image {image})», no. {entry}, {subject}',
    frn: `{parish} församling, Lysnings- och Vigselbok [banns and marriage book], vol. {vol} ({years}), p. {page}, no. {entry}, {entryof}«, {details}»; ${DIGITAL_IMAGE}; citing {repository}«, {call}».`,
    srn: '{parish} vigselbok {vol} ({years}), p. {page}, no. {entry}, {subject}.',
    subjectLabel: 'Couple (Surname-Surname)',
    pins: {
      title: [['B.2 §4', 'Banns and marriage | …, Lysnings- och Vigselbok [banns and marriage book] [vol], [years]']],
      page: [['B.2 §7', 'Banns and marriage | p. [P] (image [I]), no. [N], [Surname]-[Surname] marriage']],
      author: [PARISH_AUTHOR_PIN],
      abbrev: [['B.2 §10', 'Lysnings- och Vigselbok | vigselbok']],
      confidence: [['B.2 §8', 'Banns and marriage | High to Very High']],
    },
    examples: [],
  },
  {
    id: 'se-dodbok', chapter: 'se', group: 'Parish records (kyrkoarkiv)', name: 'Dödbok',
    hint: 'Death and burial book',
    source: PARISH_SOURCE, citation: PAGE_IMAGE_ENTRY, nouns: ['death entry', 'burial entry'],
    holder: VARMLAND_AD, confidence: 'Very High', doctype: 'vital record',
    title: 'Sweden, {lan}, {parish}, Dödbok [death book] {vol}, {years}',
    abbrev: '{parish} dödbok {vol} ({years})',
    author: '{parish} församling',
    page: 'p. {page}« (image {image})», no. {entry}, {subject}',
    frn: `{parish} församling, Dödbok [death book], vol. {vol} ({years}), p. {page}, no. {entry}, {entryof}«, {details}»; ${DIGITAL_IMAGE}; citing {repository}«, {call}».`,
    srn: '{parish} dödbok {vol} ({years}), p. {page}, no. {entry}, {subject}.',
    pins: {
      title: [['B.2 §4', 'Death / burial | …, Dödbok [death book] [vol], [years]']],
      page: [['B.2 §7', 'Death / burial | p. [P] (image [I]), no. [N], [Name] death entry']],
      author: [PARISH_AUTHOR_PIN],
      abbrev: [['B.2 §10', 'Dödbok | dödbok']],
      confidence: [['B.2 §8', 'Death/burial entry near the event | Very High']],
    },
    examples: [],
  },
  {
    id: 'se-confirmation', chapter: 'se', group: 'Parish records (kyrkoarkiv)', name: 'Confirmation or communion',
    hint: 'Recorded inside the husförhörslängd; cite it under that volume’s Source.',
    source: PARISH_SOURCE, citation: PAGE_IMAGE, nouns: ['confirmation entry', 'communion entry'],
    holder: VARMLAND_RA, confidence: 'High', doctype: 'religious',
    title: 'Sweden, {lan}, {parish}, Husförhörslängder [household examinations] {vol}, {years}',
    abbrev: '{parish} husförhörslängd {vol} ({years})',
    author: '{parish} församling',
    page: 'p. {page}« (image {image})», {subject}',
    frn: `{parish} församling, Husförhörslängder [household examinations], vol. {vol} ({years}), p. {page}, {entryof}«, {details}»; ${DIGITAL_IMAGE}; citing {repository}, {call}.`,
    srn: '{parish} husförhörslängd {vol} ({years}), p. {page}, {subject}.',
    pins: {
      title: [['B.2 §4', "Confirmation and communion use the husförhörslängd's Title."]],
      page: [['B.2 §7', 'Confirmation / communion Pending review | p. [P] (image [I]), [Name] confirmation entry / communion entry']],
      author: [PARISH_AUTHOR_PIN],
      confidence: [['B.2 §8', 'Confirmation Pending review | High']],
    },
    examples: [{
      guide: 'B.2 Example 4',
      inputs: {
        lan: 'Värmland', parish: 'Norra Ny', vol: 'AI:11', years: '1812–1820', call: 'SE/VA/13398/A I/11',
        page: '8', image: '19', name: 'Lars Persson', noun: 'confirmation entry',
        url: 'https://sok.riksarkivet.se/...', accessed: '20 April 2026',
      },
    }],
  },
  {
    id: 'se-sockenstamma', chapter: 'se', group: 'Parish records (kyrkoarkiv)', name: 'Sockenstämmoprotokoll',
    hint: 'Parish meeting minutes, a series of its own',
    source: PARISH_SOURCE,
    citation: [...PAGE_IMAGE, ['date', 'Meeting date or item no.', 'meeting of 3 May 1850']],
    nouns: ['parish meeting record'],
    holder: VARMLAND_AD, confidence: 'High', doctype: 'religious',
    title: 'Sweden, {lan}, {parish}, Sockenstämmoprotokoll [parish meeting minutes] {vol}, {years}',
    abbrev: '{parish} sockenstämmoprotokoll {vol} ({years})',
    author: '{parish} församling',
    page: 'p. {page}« (image {image})», {date}, {subject}',
    frn: `{parish} församling, Sockenstämmoprotokoll [parish meeting minutes], vol. {vol} ({years}), p. {page}, {date}, {entryof}«, {details}»; ${DIGITAL_IMAGE}; citing {repository}«, {call}».`,
    srn: '{parish} sockenstämmoprotokoll {vol} ({years}), p. {page}, {subject}.',
    pins: {
      title: [['B.2 §4', 'Meeting minutes Pending review | …, Sockenstämmoprotokoll [parish meeting minutes] [vol], [years]']],
      page: [['B.2 §7', 'Meeting minutes Pending review | p. [P] (image [I]), [date or item no.], [Name] parish meeting record']],
      author: [PARISH_AUTHOR_PIN],
      abbrev: [['B.2 §10', 'Sockenstämmoprotokoll Pending review | sockenstämmoprotokoll']],
      confidence: [['B.2 §8', "Meeting minutes Pending review | High for the meeting's business"]],
    },
    examples: [],
  },
  {
    id: 'se-bouppteckning', chapter: 'se', group: 'Court, census and land', name: 'Bouppteckning',
    hint: 'Estate inventory (häradsrätt); the locality is the härad, not the parish',
    source: [
      ['lan', 'Län', 'Värmland'], ['harad', 'Härad', 'Älvdals härad'], ['court', 'Court (creating body)', 'Älvdals häradsrätt'],
      ['cgloss', 'Court gloss', 'Älvdal district court'], ['vol', 'Volume', 'FII:26'], ['years', 'Years', '1832–1833'],
      ['call', 'Call number', 'SE/VA/11047/F II/26'],
    ],
    citation: [['pages', 'Pages', '203–205']],
    nouns: ['estate inventory'],
    holder: VARMLAND_AD, confidence: 'High', doctype: 'legal',
    title: 'Sweden, {lan}, {harad}, Bouppteckningar [estate inventories] {vol}, {years}',
    abbrev: '{court} {vol} ({years})',
    author: '{court}',
    page: 'pp. {pages}, {subject}',
    frn: `{court} [{cgloss}], Bouppteckningar [estate inventories], vol. {vol} ({years}), pp. {pages}, {entryof}«, {details}»; ${DIGITAL_IMAGE}; citing {repository}, {call}.`,
    srn: '{court} {vol} ({years}), pp. {pages}, {subject}.',
    subjectLabel: 'Deceased',
    detailsLabel: 'Entry details (farm, parish, death)',
    pins: {
      title: [['B.2 §4', 'Estate inventory | Sweden, [län], [härad], Bouppteckningar [estate inventories] [vol], [years]']],
      page: [['B.2 §7', 'Estate inventory | pp. [P]-[P], [Deceased] estate inventory']],
      author: [['B.2 §2', 'Court and other state bodies | The creating body, e.g. Älvdals häradsrätt']],
      abbrev: [['B.2 §10', 'Bouppteckningar | (creating body)']],
      confidence: [['B.2 §8', 'Bouppteckning | High']],
    },
    examples: [{
      guide: 'B.2 Example 2',
      inputs: {
        lan: 'Värmland', harad: 'Älvdals härad', court: 'Älvdals häradsrätt', cgloss: 'Älvdal district court',
        vol: 'FII:26', years: '1832–1833', call: 'SE/VA/11047/F II/26', pages: '203–205',
        name: 'Per Persson', noun: 'estate inventory',
        url: 'https://app.arkivdigital.se/volume/v48177?image=104', accessed: '20 April 2026', eventYear: '1832',
        details: 'Ambjörbymon, Norra Ny parish, died 5 May 1832',
      },
    }],
  },
  {
    id: 'se-folkrakning', chapter: 'se', group: 'Court, census and land', name: 'Folkräkning (SVAR)',
    hint: 'Census database; one Source per parish per count year',
    source: [['lan', 'Län', 'Värmland'], ['parish', 'Parish', 'Norra Ny'], ['year', 'Count year', '1880'], ['call', 'Call number', 'Folk_817085']],
    citation: [['page', 'Page'], ['image', 'Image', 'if not the page'], ['row', 'Row'], ['fam', 'Family no.']],
    nouns: ['household', 'record'],
    holder: { heldBy: 'publication', platform: 'Riksarkivet', medium: 'Database with images' },
    confidence: 'High', doctype: 'enumeration',
    derive: v => ({ lanfull: lanFull(v.lan) }),
    title: 'Sweden, {lan}, {parish}, Folkräkning [census] {year}',
    abbrev: '{parish} folkräkning {year}',
    author: 'Riksarkivet',
    page: 'p. {page}« (image {image})», row {row}, family no. {fam}, {subject}',
    frn: `Sveriges folkräkning {year} [Swedish census {year}], {parish} församling, {lanfull}, p. {page}, row {row}, family no. {fam}, {entryof}«, {details}»; ${DIGITAL_IMAGE}.`,
    srn: 'Folkräkning {year}, {parish} församling, p. {page}, row {row}, {subject}.',
    pins: {
      title: [['B.2 §4', 'SVAR census | Sweden, [län], [parish], Folkräkning [census] [year]']],
      page: [['B.2 §7', 'SVAR census | p. [P] (image [I]), row [R], family no. [F], [Head] household']],
      author: [['B.2 §2', 'SVAR databases and other central records | Riksarkivet (covers SVAR)']],
      abbrev: [['B.2 §10', 'Folkräkning | folkräkning']],
      confidence: [['B.2 §8', 'SVAR with images | High residence; Normal ages']],
    },
    examples: [{
      guide: 'B.2 Example 3',
      inputs: {
        lan: 'Värmland', parish: 'Norra Ny', year: '1880', call: 'Folk_817085',
        page: '4', row: '33', fam: '1', name: 'Lars Persson Ambjörn', noun: 'household',
        url: 'https://sok.riksarkivet.se/bildvisning/Folk_817085-004', accessed: '21 April 2026', eventYear: '1880',
        details: 'Ambjörby',
      },
    }],
  },
  {
    id: 'se-lantmateriet', chapter: 'se', group: 'Court, census and land', name: 'Lantmäteriet survey act',
    hint: 'Laga skifte, storskifte, ägodelning…; one numbered act = one Source',
    source: [
      ['lan', 'Län', 'Värmland'], ['parish', 'Parish', 'Norra Ny'], ['farm', 'Farm', 'Ambjörby'],
      ['stype', 'Survey type', 'laga skifte'], ['stgloss', 'Survey type gloss', 'statutory land enclosure'],
      ['act', 'Act number', '17-NON-148'], ['years', 'Years', '1856–1862'], ['call', 'Call number'],
    ],
    citation: [['protocol', 'Protocol locator', 'delningsbeskrivning p. 40']],
    note: [['survey', 'Survey details (FRN)', 'surveyed … by …, confirmed by … on …']],
    nouns: ['land allotment', 'signatory', 'croft transfer'],
    holder: { heldBy: 'publication', platform: 'Lantmäteriet', medium: 'Digital images' },
    confidence: 'High', doctype: 'legal',
    derive: v => ({
      surveyAuthor: /^R/i.test(String(v.act || '').trim()) ? 'Lantmäteristyrelsen' : `Lantmäterimyndigheten i ${lanFull(v.lan) || '[län]'}`,
    }),
    title: 'Sweden, {lan}, {parish}, {stype} [{stgloss}], act {act}, {years}',
    abbrev: '{parish} {stype} {act} ({years})',
    author: '{surveyAuthor}',
    page: '{protocol}, {subject}',
    frn: `{author}, {stype} [{stgloss}], {farm}, {parish} socken, act {act}«, {survey}»; {protocol}, {details}; ${DIGITAL_IMAGE}.`,
    srn: '{parish} {stype} {act} ({years}), {protocol}, {name} {noun}.',
    detailsLabel: 'Entry description (FRN)',
    paperlessTitle: '{farm} {stype} {eventYear}',
    pins: {
      title: [['B.2 §4', 'Land survey Pending review | Sweden, [län], [parish], [survey type] [English gloss], act [act-no], [years]']],
      page: [['B.2 §7', 'Land survey Pending review | [protocol locator], [name] [record-noun]']],
      author: [['B.2 §2', 'Land survey, NN-XXX-NNN county series (e.g. 17-NON-148) Pending review | Lantmäterimyndigheten i Värmlands län']],
      abbrev: [['B.2 §10', 'Land survey Pending review | ägodelning / storskifte / laga skifte / enskifte / gränsbestämning / avvittring']],
      confidence: [['B.2 §8', 'Land survey Pending review | High for what the surveyor recorded']],
    },
    examples: [{
      guide: 'B.2 Example 5',
      inputs: {
        lan: 'Värmland', parish: 'Norra Ny', farm: 'Ambjörby', stype: 'laga skifte', stgloss: 'statutory land enclosure',
        act: '17-NON-148', years: '1856–1862', protocol: 'delningsbeskrivning p. 40',
        name: 'Marit Andersdotter', noun: 'land allotment', says: 'Lott A, 64 öre 6 penningar', afterNoun: true,
        survey: 'surveyed 1856–1862 by O. Ignelius, confirmed by Älvdals övre tingslags egodelningsrätt 3 October 1863',
        details: 'land allotment (Lott A) of the minor Marit Andersdotter, 64 öre 6 penningar skatt',
        url: 'https://historiskakartor.lantmateriet.se', accessed: '16 June 2026', eventYear: '1862',
      },
    }],
  },
];
````

- [ ] **Step 4: Run the Swedish checks to confirm they pass**

Run: `node --test --test-name-pattern="B\.2|se-" test/records.test.js test/examples.test.js test/pins.test.js test/coverage.test.js`
Expected: `tests 148`, `pass 142`, `fail 0`, `skipped 4`, `todo 2` (B.2 Ex. 2 FRN and SRN).

- [ ] **Step 5: Commit**

```bash
git add src/records/index.js src/records/swedish.js
git commit -m "Add Swedish record types" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 7: US record types

**Files:**
- Modify: `src/records/index.js`
- Create: `src/records/us.js`

**Interfaces:**
- Consumes: `stateAbbrev` (Task 3), the record type shape (Task 4), the checks (Task 5).
- Produces: `US` (13 record types: `us-federal-census`, `us-state-census`, `us-vital` (page variants `certificate`, `license`), `us-church`, `us-naturalization` (variants `petition`, `declaration`), `us-draft-card`, `us-headstone`, `us-civil-war-pension`, `us-service-record`, `us-passenger-manifest`, `us-find-a-grave`, `us-newspaper`, `us-city-directory`).

- [ ] **Step 1: Register the chapter in `src/records/index.js`**

```js
// Every record type, in sidebar order.
import { NORWEGIAN } from './norwegian.js';
import { SWEDISH } from './swedish.js';
import { US } from './us.js';

export const RECORDS = [...NORWEGIAN, ...SWEDISH, ...US];

export function recordById(id) {
  return RECORDS.find(r => r.id === id) || null;
}
```

- [ ] **Step 2: Run the US checks to confirm they fail**

Run: `node --test --test-name-pattern="B\.3|us-" test/records.test.js test/examples.test.js test/pins.test.js test/coverage.test.js`
Expected: FAIL with `ERR_MODULE_NOT_FOUND` for `src/records/us.js`.

- [ ] **Step 3: Implement** `src/records/us.js`

````js
// B.3 · US sources.
import { stateAbbrev } from '../tables.js';

const DIGITAL_IMAGE = 'digital image, {platform} ({url} : accessed {accessed})';
const NARA_ANCESTRY = { heldBy: 'archive', archive: 'National Archives', platform: 'Ancestry', medium: 'Digital images' };
const NARA_FS = { heldBy: 'archive', archive: 'National Archives', platform: 'FamilySearch', medium: 'Digital images' };
const NARA_FOLD3 = { heldBy: 'archive', archive: 'National Archives', platform: 'Fold3', medium: 'Digital images' };
const MHS_ANCESTRY = { heldBy: 'archive', archive: 'Minnesota Historical Society', platform: 'Ancestry', medium: 'Digital images' };

export const US = [
  {
    id: 'us-federal-census', chapter: 'us', group: 'Census', name: 'Federal census',
    hint: 'One Source per county, state, and year; the roll goes in the page string',
    source: [['year', 'Census year', '1920'], ['county', 'County', 'St. Louis'], ['state', 'State', 'Minnesota'], ['call', 'NARA publication', 'T625']],
    citation: [['roll', 'Roll'], ['ed', 'ED'], ['sheet', 'Sheet', '8A'], ['dwelling', 'Dwelling'], ['family', 'Family']],
    note: [['locality', 'Locality (FRN)', 'Duluth']],
    nouns: ['household', 'record'],
    holder: NARA_ANCESTRY, confidence: 'High', doctype: 'enumeration',
    derive: v => ({ stab: stateAbbrev(v.state) }),
    title: '{year} U.S. Federal Census, {county} County, {state}',
    abbrev: '{county} Co., {stab}, {year} census',
    author: 'Bureau of the Census',
    page: 'roll {roll}, ED {ed}, sheet {sheet}, dwelling {dwelling}, family {family}, {subject}',
    frn: `{year} U.S. census, {county} County, {state}, population schedule, {locality}, enumeration district {ed}, sheet {sheet}, dwelling {dwelling}, family {family}, {subject}; ${DIGITAL_IMAGE}; citing {repository} microfilm publication {call}, roll {roll}.`,
    srn: '{year} U.S. census, {county} Co., {stab}, pop. sched., {locality}, ED {ed}, sheet {sheet}, {subject}.',
    subjectLabel: 'Head (or person)',
    pins: {
      title: [['B.3 §4', 'Federal census | [year] U.S. Federal Census, [county] County, [state]']],
      page: [['B.3 §7', 'Federal census | roll [N], ED [N], sheet [N]A/B, dwelling [N], family [N], [Head] household']],
      author: [['B.3 §2', 'Federal census | Bureau of the Census']],
      confidence: [['B.3 §8', 'Federal census | High for residence and household; Normal for ages, birthplaces']],
    },
    examples: [{
      guide: 'B.3 Example 1',
      inputs: {
        year: '1920', county: 'St. Louis', state: 'Minnesota', call: 'T625',
        roll: '859', ed: '139', sheet: '8A', dwelling: '[N]', family: '[N]', name: 'Steve Maisuk', noun: 'household',
        locality: 'Duluth', url: 'https://www.ancestry.com/...', accessed: '6 May 2026', eventYear: '1920',
      },
    }],
  },
  {
    id: 'us-state-census', chapter: 'us', group: 'Census', name: 'State census',
    hint: 'One Source per county, state, and year',
    source: [['year', 'Census year', '1905'], ['state', 'State', 'Minnesota'], ['county', 'County', 'St. Louis'], ['call', 'Call number']],
    citation: [['ward', 'Ward or township'], ['page', 'Page'], ['line', 'Line']],
    nouns: ['household', 'record'],
    holder: MHS_ANCESTRY, confidence: 'High', doctype: 'enumeration',
    derive: v => ({ stab: stateAbbrev(v.state) }),
    title: '{year} {state} State Census, {county} County',
    abbrev: '{county} Co., {stab}, {year} state census',
    author: '{state} Population Census Office',
    page: '{ward}, p. {page}, line {line}, {subject}',
    frn: `{year} {state} state census, {county} County, {ward}, p. {page}, line {line}, {subject}; ${DIGITAL_IMAGE}; citing {repository}.`,
    srn: '{year} {stab} state census, {county} Co., {ward}, p. {page}, {subject}.',
    subjectLabel: 'Head (or person)',
    pins: {
      title: [['B.3 §4', 'State census | [year] [state] State Census, [county] County']],
      page: [['B.3 §7', 'State census | [ward or township], p. [N], line [N], [Head] household']],
      author: [['B.3 §2', 'State census | [State] Population Census Office']],
    },
    examples: [],
  },
  {
    id: 'us-vital', chapter: 'us', group: 'Vital records', name: 'State vital record',
    hint: 'Death, birth, or marriage record; one Source per state collection',
    source: [['state', 'State', 'Minnesota'], ['series', 'Record series', 'death certificates'], ['years', 'Years', '1908–2002'], ['call', 'Call number (often blank)']],
    citation: [],
    pageVariants: [
      {
        key: 'certificate', label: 'Certificate',
        citation: [['cert', 'Certificate no.']],
        nouns: ['death certificate', 'birth certificate'],
        page: 'Certificate no. {cert}, {subject}',
        frn: `{state}, {kind} no. {cert} ({eventYear}), {name}; {author}; ${DIGITAL_IMAGE}; citing {repository}.`,
        srn: '{stab} {kindShort} {cert} ({eventYear}), {name}.',
      },
      {
        key: 'license', label: 'Marriage license',
        citation: [['license', 'License no.']],
        nouns: ['marriage'],
        page: 'License no. {license}, {subject}',
        frn: `{state}, marriage license no. {license} ({eventYear}), {name}; {author}; ${DIGITAL_IMAGE}; citing {repository}.`,
        srn: '{stab} marriage license {license} ({eventYear}), {name}.',
      },
    ],
    nouns: ['death certificate', 'birth certificate', 'marriage'],
    holder: { heldBy: 'archive', archive: 'Minnesota Historical Society', platform: 'FamilySearch', medium: 'Database with images' },
    confidence: 'Very High', doctype: 'vital record',
    derive: v => {
      const series = String(v.series || '').toLowerCase();
      const kind = /birth/.test(series) ? 'birth certificate' : /marr/.test(series) ? 'marriage certificate' : 'death certificate';
      return {
        stab: stateAbbrev(v.state),
        kind,
        kindShort: { 'birth certificate': 'birth cert.', 'marriage certificate': 'marr. cert.', 'death certificate': 'death cert.' }[kind],
        seriesShort: String(v.series || '').trim().replace(/certificates/, 'certs'),
      };
    },
    title: '{state}, {series}, {years}',
    abbrev: '{stab} {seriesShort}, {years}',
    author: '{state} Department of Health, Vital Records',
    pins: {
      title: [['B.3 §4', 'State vital records | [State], [record series], [years]']],
      page: [
        ['B.3 §7', 'Death / birth certificate | Certificate no. [N], [Name] death certificate / birth certificate'],
        ['B.3 §7', 'Marriage license | License no. [N], [Surname]-[Surname] marriage'],
      ],
      author: [['B.3 §2', 'State vital records | [State] Department of Health, Vital Records']],
      confidence: [['B.3 §8', 'State death certificate (post-1900) | Very High for the death']],
    },
    examples: [{
      guide: 'B.3 Example 2',
      inputs: {
        state: 'Minnesota', series: 'death certificates', years: '1908–2002', variant: 'certificate',
        cert: '1929-MN-XXXXXX', name: 'Per Larsson Grund', noun: 'death certificate',
        url: 'https://www.familysearch.org/...', accessed: '6 May 2026', eventYear: '1929',
      },
    }],
  },
  {
    id: 'us-church', chapter: 'us', group: 'Vital records', name: 'Church record',
    hint: "Baptism, confirmation, marriage, burial; one Source per congregation's record set",
    source: [
      ['state', 'State', 'Minnesota'], ['county', 'County', 'Marshall'], ['town', 'Town', 'Warren'],
      ['church', 'Church', 'First Lutheran Church'], ['years', 'Years (Abbrev)', '1800–1952'], ['call', 'Archive reference'],
    ],
    citation: [['register', 'Register', 'death and burial register'], ['page', 'Page'], ['image', 'Image', 'if not the page']],
    note: [['collection', 'Digitized collection name'], ['citing', 'Citing, after the repository']],
    nouns: ['death and burial entry', 'baptism entry', 'confirmation entry', 'marriage entry', 'burial entry', 'membership entry'],
    holder: { heldBy: 'archive', archive: 'Swenson Swedish Immigration Research Center', platform: 'Ancestry', medium: 'Digital images' },
    confidence: 'Very High', doctype: 'religious',
    derive: v => ({ stab: stateAbbrev(v.state) }),
    title: '{state}, {county} County, {town}, {church} records',
    abbrev: '{church}, {town}, {stab}, records, {years}',
    author: '{church}, {town}',
    page: '{register}, p. {page}« (image {image})», {subject}',
    frn: `{church} ({town}, {county} County, {state}), {register}, p. {page}« (image {image})», {details}; ${DIGITAL_IMAGE}«, "{collection}"»; citing {repository}«, {citing}».`,
    srn: '{church} ({town}, {stab}), {entryof}, p. {page}.',
    detailsLabel: 'Entry description (FRN)',
    pins: {
      title: [['B.3 §4', 'Church records Pending review | [State], [county], [town], [Church name] records']],
      page: [['B.3 §7', 'Church record Pending review | [register], p. [P] (image [I]), [Name] [record-noun] entry']],
      author: [['B.3 §2', 'Church records Pending review | [Church name], [town]']],
      confidence: [['B.3 §8', 'Church register Pending review | Very High for the recorded event']],
    },
    examples: [{
      guide: 'B.3 Example 11',
      inputs: {
        state: 'Minnesota', county: 'Marshall', town: 'Warren', church: 'First Lutheran Church', years: '1800–1952',
        register: 'death and burial register', page: '283', image: '496, right',
        name: 'Emma Söderström', noun: 'death and burial entry',
        details: 'death and burial of Emma Söderström, died 7 May 1914, buried 9 May 1914',
        url: 'https://www.ancestry.com/search/collections/61584/records/63230716', accessed: '16 June 2026', eventYear: '1914',
        collection: 'U.S., Evangelical Lutheran Church in America, Swedish American Church Records, 1800–1952',
        citing: 'Augustana College, Rock Island, Illinois',
      },
    }],
  },
  {
    id: 'us-naturalization', chapter: 'us', group: 'Immigration and military', name: 'Naturalization',
    hint: 'Petition or declaration of intention; one Source per court collection',
    source: [['court', 'Court', 'St. Louis County District Court'], ['county', 'County (Abbrev)', 'St. Louis'], ['years', 'Years', '1888–1955'], ['call', 'Call number']],
    citation: [],
    note: [['courtplace', 'Court seat (FRN)', 'Duluth, Minnesota']],
    pageVariants: [
      {
        key: 'petition', label: 'Petition',
        citation: [['pet', 'Petition no.']],
        nouns: ['naturalization petition'],
        page: 'Petition no. {pet}, {subject}',
        frn: `{court} ({courtplace}), Naturalization Records, petition no. {pet} ({eventYear}), {name}; ${DIGITAL_IMAGE}; citing {repository}.`,
        srn: '{county} Co. natz., pet. no. {pet} ({eventYear}), {name}.',
      },
      {
        key: 'declaration', label: 'Declaration of intention',
        citation: [['decl', 'Declaration no.']],
        nouns: ['declaration of intention'],
        page: 'Declaration no. {decl}, {subject}',
        frn: `{court} ({courtplace}), Naturalization Records, declaration of intention no. {decl} ({eventYear}), {name}; ${DIGITAL_IMAGE}; citing {repository}.`,
        srn: '{county} Co. natz., decl. no. {decl} ({eventYear}), {name}.',
      },
    ],
    nouns: ['naturalization petition', 'declaration of intention'],
    holder: MHS_ANCESTRY, confidence: 'High', doctype: 'immigration',
    title: '{court}, Naturalization Records, {years}',
    abbrev: '{county} Co. naturalizations, {years}',
    author: '{court}',
    pins: {
      title: [['B.3 §4', 'Naturalization | [Court], Naturalization Records, [years]']],
      page: [
        ['B.3 §7', 'Naturalization petition | Petition no. [N], [Name] naturalization petition'],
        ['B.3 §7', 'Declaration of intention | Declaration no. [N], [Name] declaration of intention'],
      ],
      author: [['B.3 §2', 'State/county court naturalization | [Court name]']],
    },
    examples: [{
      guide: 'B.3 Example 3',
      inputs: {
        court: 'St. Louis County District Court', county: 'St. Louis', years: '1888–1955', variant: 'petition',
        pet: '[N]', name: 'Per Larsson', noun: 'naturalization petition', courtplace: 'Duluth, Minnesota',
        url: 'https://www.ancestry.com/...', accessed: '6 May 2026', eventYear: '1894',
      },
    }],
  },
  {
    id: 'us-draft-card', chapter: 'us', group: 'Immigration and military', name: 'WWII draft card',
    hint: 'Selective Service registration; one Source per state series',
    source: [['state', 'State', 'Minnesota'], ['call', 'Record group', 'RG 147']],
    citation: [['serial', 'Serial no.']],
    nouns: ['WWII draft card'],
    holder: NARA_FS, confidence: 'High', doctype: 'military',
    derive: v => ({ stab: stateAbbrev(v.state), recordGroup: String(v.call || '').trim().replace(/^RG\s*/, 'Record Group ') }),
    title: 'World War II Draft Registration Cards, {state}',
    abbrev: 'WWII draft cards, {stab}',
    author: 'Selective Service System',
    page: 'Serial no. {serial}, {subject}',
    frn: `{author}, World War II Draft Registration Cards, {state}, serial no. {serial}, {name} ({eventYear}); ${DIGITAL_IMAGE}; citing {recordGroup}, {repository}.`,
    srn: 'WWII draft card, {stab}, {name}.',
    pins: {
      title: [['B.3 §4', 'WWII draft cards | World War II Draft Registration Cards, [state]']],
      page: [['B.3 §7', 'WWII draft card | Serial no. [N], [Name] WWII draft card']],
      author: [['B.3 §2', 'WWII draft cards | Selective Service System']],
    },
    examples: [{
      guide: 'B.3 Example 5',
      inputs: {
        state: 'Minnesota', call: 'RG 147', serial: '[N]', name: 'Axel O. Grund', noun: 'WWII draft card',
        url: 'https://www.familysearch.org/...', accessed: '6 May 2026', eventYear: '1942',
      },
    }],
  },
  {
    id: 'us-headstone', chapter: 'us', group: 'Immigration and military', name: 'Headstone application',
    hint: 'Applications for Headstones series',
    source: [['years', 'Series years', '1925–1941'], ['call', 'Record group', 'RG 92']],
    citation: [['dyear', 'Death year']],
    note: [['citing', 'Citing clause', 'NAID …, Record Group 92, National Archives at …']],
    nouns: ['headstone application'],
    holder: NARA_ANCESTRY, confidence: 'Normal', doctype: 'military',
    title: 'Applications for Headstones for U.S. Military Veterans, {years}',
    abbrev: 'Headstone apps, {years}',
    author: 'Office of the Quartermaster General',
    page: 'Application for {name} (d. {dyear})',
    frn: `{author}, "Applications for Headstones for U.S. Military Veterans, {years}," application for {name}«, {details}»; ${DIGITAL_IMAGE}; citing {citing}.`,
    srn: 'Headstone app., {name} (d. {dyear}).',
    detailsLabel: 'Application details (death date)',
    pins: {
      title: [['B.3 §4', 'Headstone applications | Applications for Headstones for U.S. Military Veterans, [years]']],
      page: [['B.3 §7', 'Headstone application | Application for [Name] (d. [year])']],
      author: [['B.3 §2', 'Headstone applications | Office of the Quartermaster General']],
      confidence: [['B.3 §8', 'Headstone application | Normal for death date; High for military service']],
    },
    examples: [{
      guide: 'B.3 Example 6',
      inputs: {
        years: '1925–1941', call: 'RG 92', dyear: '1948', name: 'Axel O. Grund', noun: 'headstone application',
        details: 'died 31 October 1948', url: 'https://www.ancestry.com/search/collections/2375/records/45037', accessed: '6 May 2026',
        eventYear: '1948', citing: 'NAID 596118, Record Group 92, National Archives at Washington, DC',
      },
    }],
  },
  {
    id: 'us-civil-war-pension', chapter: 'us', group: 'Immigration and military', name: 'Civil War pension',
    hint: 'Civil War Pension Application Files (NARA RG 15)',
    source: [['call', 'Call number', 'RG 15']],
    citation: [['app', 'Application no.'], ['cert', 'Certificate no.']],
    nouns: ['pension file'],
    holder: NARA_FOLD3, confidence: '', doctype: 'military',
    title: 'Civil War Pension Application Files',
    abbrev: 'Civil War pension files',
    author: 'Bureau of Pensions',
    page: 'Application no. {app}, certificate no. {cert}, {subject}',
    frn: `{author}, Civil War Pension Application Files, application no. {app}, certificate no. {cert}, {name}«, {details}»; ${DIGITAL_IMAGE}; citing {repository}«, {call}».`,
    srn: 'Civil War pension, app. {app}, {name}.',
    pins: {
      title: [['B.3 §4', 'Civil War pensions | Civil War Pension Application Files']],
      page: [['B.3 §7', 'Civil War pension | Application no. [N], certificate no. [N], [Name] pension file']],
      author: [['B.3 §2', 'Civil War pensions | Bureau of Pensions']],
    },
    examples: [],
  },
  {
    id: 'us-service-record', chapter: 'us', group: 'Immigration and military', name: 'Compiled service record',
    hint: 'Compiled military service records; one Source per series',
    source: [['series', 'Series title', 'Compiled Service Records of Volunteer Union Soldiers, Minnesota'], ['short', 'Short title (Abbrev)'], ['call', 'Call number']],
    citation: [['unit', 'Unit', 'Co. B, 1st Minnesota Infantry']],
    nouns: ['compiled service record'],
    holder: NARA_FOLD3, confidence: '', doctype: 'military',
    title: '{series}',
    abbrev: '{short}',
    author: "War Department, Adjutant General's Office",
    page: '{unit}, {subject}',
    frn: `{author}, {series}, {unit}, {name}«, {details}»; ${DIGITAL_IMAGE}; citing {repository}«, {call}».`,
    srn: '{short}, {unit}, {name}.',
    pins: {
      page: [['B.3 §7', 'Compiled service record | [Unit], [Name] compiled service record']],
      author: [['B.3 §2', "Compiled service records | War Department, Adjutant General's Office"]],
    },
    examples: [],
  },
  {
    id: 'us-passenger-manifest', chapter: 'us', group: 'Immigration and military', name: 'Passenger manifest',
    hint: 'One Source per arrival port and year-range series',
    source: [['port', 'Arrival port', 'New York'], ['years', 'Years', '1820–1957'], ['agency', 'Creating agency (Author)'], ['call', 'NARA publication']],
    citation: [['list', 'List'], ['line', 'Line']],
    nouns: ['', 'passenger manifest entry'],
    holder: NARA_ANCESTRY, confidence: '', doctype: 'immigration',
    title: 'Passenger Lists of Vessels Arriving at {port}, {years}',
    abbrev: 'Passenger lists, {port}, {years}',
    author: '«{agency}»',
    page: 'List {list}, line {line}, {subject}',
    frn: `«{agency}, »"Passenger Lists of Vessels Arriving at {port}, {years}," list {list}, line {line}, {name}«, {details}»; ${DIGITAL_IMAGE}; citing {repository}«, microfilm publication {call}».`,
    srn: 'Passenger lists, {port}, list {list}, line {line}, {name}.',
    pins: {
      title: [['B.3 §4', 'Passenger manifests | Passenger Lists of Vessels Arriving at [port], [years]']],
      page: [['B.3 §7', 'Passenger manifest | List [N], line [N], [Name]']],
    },
    examples: [],
  },
  {
    id: 'us-find-a-grave', chapter: 'us', group: 'Cemeteries and publications', name: 'Find a Grave memorial',
    hint: 'One Source per cemetery; the memorial number goes in the page string',
    source: [['state', 'State', 'Minnesota'], ['county', 'County', 'St. Louis'], ['cemetery', 'Cemetery', 'Forest Hill Cemetery'], ['city', 'City', 'Duluth']],
    citation: [['memorial', 'Memorial no.']],
    note: [['life', 'Life dates (FRN)', '1848–1929'], ['photographer', 'Marker photo by, date (FRN)']],
    nouns: ['', 'Find a Grave entry'],
    holder: { heldBy: 'publication', platform: 'Find a Grave', medium: 'Database with images' },
    confidence: 'High', doctype: 'vital record',
    derive: v => ({ cemeteryShort: String(v.cemetery || '').replace(/\s+Cemetery$/i, '').trim() }),
    title: '{state}, {county} County, {cemetery}, Find a Grave Memorials',
    abbrev: '{cemeteryShort}, {city}, FAG',
    author: '',
    page: 'Memorial no. {memorial}, {subject}',
    frn: 'Find a Grave, memorial no. {memorial}, {name}« ({life})», {cemetery}, {city}, {county} County, {state}; database with images, {platform} ({url} : accessed {accessed})«; marker photograph by {photographer}».',
    srn: 'FAG memorial {memorial}, {name}, {cemetery}.',
    paperlessTitle: '{name} Find a Grave entry« {eventYear}»',
    pins: {
      title: [['B.3 §4', 'Find a Grave | [State], [county], [cemetery], Find a Grave Memorials']],
      page: [['B.3 §7', 'Find a Grave | Memorial no. [N], [Name]']],
      author: [['B.3 §2', 'Newspapers, Find a Grave | Blank']],
      confidence: [['B.3 §8', 'Find a Grave with marker photo | High for burial and inscribed dates']],
    },
    examples: [{
      guide: 'B.3 Example 4',
      inputs: {
        state: 'Minnesota', county: 'St. Louis', cemetery: 'Forest Hill Cemetery', city: 'Duluth',
        memorial: '[N]', name: 'Per Larsson Grund', noun: '', life: '1848–1929', photographer: '[contributor name], [date]',
        url: 'https://www.findagrave.com/memorial/[N]', accessed: '6 May 2026', eventYear: '1929',
      },
    }],
  },
  {
    id: 'us-newspaper', chapter: 'us', group: 'Cemeteries and publications', name: 'Newspaper item',
    hint: 'Obituary, funeral notice, announcement, or mention; one Source per newspaper title',
    source: [['paper', 'Newspaper', 'Warren Sheaf'], ['city', 'City', 'Warren'], ['state', 'State', 'Minnesota']],
    citation: [['date', 'Issue date', '3 December 1908'], ['page', 'Page'], ['col', 'Column no. (if given)'], ['column', 'Named column (if any)', 'Alma']],
    note: [['headline', 'Headline (FRN)']],
    nouns: ['obituary', 'funeral notice', 'marriage announcement', 'news mention'],
    holder: { heldBy: 'publication', platform: 'Newspapers.com', medium: 'Digital images' },
    confidence: 'Normal', doctype: 'publication',
    title: '{paper}, {city}, {state}',
    abbrev: '{paper}',
    author: '',
    page: '{date}, p. {page}«, col. {col}»«, {column} column», {subject}',
    frn: `«"{headline}," »«"{column}" [column], »{paper} ({city}, {state}), {date}, p. {page}«, col. {col}»«, {details}»; ${DIGITAL_IMAGE}.`,
    srn: '{paper}, {date}, p. {page}, {subject}.',
    detailsLabel: 'What the item says, for the FRN (e.g. "marriage announcement of …")',
    pins: {
      title: [['B.3 §4', 'Newspaper | [Title], [city, state]']],
      page: [
        ['B.3 §7', 'Newspaper wedding / funeral / obituary | [date], p. [N], col. [N], [Name] obituary (or marriage announcement, funeral notice)'],
        ['B.3 §7', 'Newspaper personals | [date], p. [N], col. [N], [Name] news mention'],
        ['B.3 §7', 'Mixed-subject column | [date], p. [N], col. [N], [Column name], [Name] news mention'],
      ],
      author: [['B.3 §2', 'Newspapers, Find a Grave | Blank']],
      confidence: [['B.3 §8', 'Obituary | Normal at best']],
    },
    examples: [
      {
        guide: 'B.3 Example 8',
        inputs: {
          paper: 'Duluth Herald', city: 'Duluth', state: 'Minnesota', date: '14 July 1929', page: '7', col: '3',
          name: 'Per Larsson Grund', noun: 'obituary', headline: 'Per L. Grund, Duluth Pioneer, Dies at Williams Farm',
          url: 'https://www.newspapers.com/...', accessed: '6 May 2026', eventYear: '1929',
        },
      },
      {
        guide: 'B.3 Example 9',
        inputs: {
          paper: 'Warren Sheaf', city: 'Warren', state: 'Minnesota', date: '3 December 1908', page: '1',
          name: 'Grund-Hoiberg', noun: 'marriage announcement', headline: '[Headline if present]', confidence: 'High',
          details: 'marriage announcement of Louis Grund and Anna Amelia Hoiberg',
          url: 'https://www.newspapers.com/image/[N]', accessed: '6 May 2026', eventYear: '1908',
        },
      },
      {
        guide: 'B.3 Example 10', citation: 1,
        inputs: {
          paper: 'Warren Sheaf', city: 'Warren', state: 'Minnesota', date: '17 May 1916', page: '7', column: 'Alma',
          name: 'Peter Grund', noun: 'news mention', details: 'Peter Grund mention',
          url: 'https://www.newspapers.com/image/64259642', accessed: '6 May 2026', eventYear: '1916',
        },
      },
      {
        guide: 'B.3 Example 10', citation: 2,
        inputs: {
          paper: 'Warren Sheaf', city: 'Warren', state: 'Minnesota', date: '17 May 1916', page: '7', column: 'Alma',
          name: 'John Olson', noun: 'news mention', details: 'John Olson mention',
          url: 'https://www.newspapers.com/image/64259642', accessed: '6 May 2026', eventYear: '1916',
        },
      },
    ],
  },
  {
    id: 'us-city-directory', chapter: 'us', group: 'Cemeteries and publications', name: 'City directory',
    hint: 'One Source per annual directory; a publication, so Repository stays blank',
    source: [['dtitle', 'Directory title', "Polk's Duluth City Directory"], ['year', 'Year', '1900'], ['publisher', 'Publisher', 'R. L. Polk & Co.'], ['city', 'Place of publication', 'Duluth']],
    citation: [['page', 'Page']],
    nouns: ['directory entry'],
    holder: { heldBy: 'publication', platform: 'Ancestry', medium: 'Digital images' },
    confidence: 'Normal', doctype: 'enumeration',
    derive: v => ({ dshort: String(v.dtitle || '').trim().replace(/\s*City Directory$/i, ' dir.') }),
    title: '{dtitle}, {year}',
    abbrev: '{dshort}, {year}',
    author: '{publisher}',
    pubinfo: '{city}: {publisher}, {year}.« Digital images, {platform} ({home}).»',
    page: 'p. {page}, {subject}',
    frn: '{publisher}, {dtitle}, {year} ({city}: {publisher}, {year}), p. {page}, {name}«; digital image, {platform} ({url} : accessed {accessed})».',
    srn: '{dshort}, {year}, p. {page}, {name}.',
    pins: {
      title: [['B.3 §4', 'City directory | [Publisher] [city] City Directory, [year]']],
      page: [['B.3 §7', 'City directory | p. [N], entry for [Name]']],
      author: [['B.3 §2', 'City directories | [Publisher]']],
      confidence: [['B.3 §8', 'City directory | Normal for residence']],
    },
    examples: [{
      guide: 'B.3 Example 7',
      inputs: {
        dtitle: "Polk's Duluth City Directory", year: '1900', publisher: 'R. L. Polk & Co.', city: 'Duluth',
        page: '412', name: 'Per Larsson Grund', noun: 'directory entry',
        url: 'https://www.ancestry.com/...', accessed: '6 May 2026', eventYear: '1900',
      },
    }],
  },
];
````

- [ ] **Step 4: Run the US checks to confirm they pass**

Run: `node --test --test-name-pattern="B\.3|us-" test/records.test.js test/examples.test.js test/pins.test.js test/coverage.test.js`
Expected: `tests 244`, `pass 240`, `fail 0`, `skipped 1`, `todo 3` (B.3 Ex. 8 SRN; B.3 Ex. 11 FRN and SRN).

- [ ] **Step 5: Commit**

```bash
git add src/records/index.js src/records/us.js
git commit -m "Add US record types, including pensions, service records, and manifests" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 8: Published and personal record types

**Files:**
- Modify: `src/records/index.js`
- Create: `src/records/published.js`
- Test: `test/paperless.test.js`

**Interfaces:**
- Consumes: `isoDate`, `lastWord` (Task 3), the record type shape (Task 4), the checks (Task 5).
- Produces: `PUBLISHED` (13 record types: `pp-book` (variants `pages`, `chapter`, `volume`, `encyclopedia`), `pp-edited-collection`, `pp-periodical`, `pp-register`, `pp-video`, `pp-bible`, `pp-family-record`, `pp-funeral-program`, `pp-photograph`, `pp-letter`, `pp-interview`, `pp-oral-history`, `pp-research`). After this task `RECORDS` holds all 44 record types.

- [ ] **Step 1: Register the last chapter in `src/records/index.js`**

````js
// Every record type, in sidebar order.
import { NORWEGIAN } from './norwegian.js';
import { SWEDISH } from './swedish.js';
import { US } from './us.js';
import { PUBLISHED } from './published.js';

export const RECORDS = [...NORWEGIAN, ...SWEDISH, ...US, ...PUBLISHED];

export function recordById(id) {
  return RECORDS.find(r => r.id === id) || null;
}
````

- [ ] **Step 2: Write the Paperless test** `test/paperless.test.js` (checks C1 titles against Part C's worked examples; needs all four chapters)

````js
// Paperless fields for real record types, checked against Part C's worked examples.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { newDraft, draftFromExample, buildOutputs } from '../src/engine.js';
import { recordById } from '../src/records/index.js';

const outputsOf = (id, n = 0) => {
  const type = recordById(id);
  return buildOutputs(type, draftFromExample(type, type.examples[n]));
};

test('C1 titles from Part C worked examples', () => {
  const dop = recordById('se-dopbok');
  const d = newDraft(dop);
  Object.assign(d.subject, { name: 'Kjerstin Mattsdotter', noun: 'birth and baptism entry' });
  d.values.eventYear = '1820';
  assert.equal(buildOutputs(dop, d).plTitle, 'Kjerstin Mattsdotter birth and baptism entry 1820');
  assert.equal(outputsOf('se-bouppteckning').plTitle, 'Per Persson estate inventory 1832');
  assert.equal(outputsOf('se-folkrakning').plTitle, 'Lars Persson Ambjörn household 1880');
  assert.equal(outputsOf('se-husforhor').plTitle, 'Per Persson household 1812–1820');
  assert.equal(outputsOf('pp-book').plTitle, 'Vinger gård Eidsvoll bygdebok 2:2 pp. 432–440 (1959)');
  assert.equal(outputsOf('pp-photograph').plTitle, 'Per Larsson Grund photograph 1890s');
  assert.equal(outputsOf('pp-interview').plTitle, 'Tom Grund interview 2024-03-12');
  assert.equal(outputsOf('se-lantmateriet').plTitle, 'Ambjörby laga skifte 1862');
});

test('C1 variants for household members and estates', () => {
  assert.equal(outputsOf('no-folketelling').plTitle, 'Karen Indiana Evensdatter in Hansen household 1875');
  assert.equal(outputsOf('no-skifteprotokoll').plTitle, 'Anders Hansen estate inventory 1822');
});

test('document type, date meaning, and correspondent', () => {
  assert.deepEqual(
    ['plDoctype', 'plDateMeaning', 'plCorrespondent'].map(k => outputsOf('se-folkrakning')[k]),
    ['enumeration', 'event', 'Riksarkivet'],
  );
  assert.deepEqual(
    ['plDoctype', 'plDateMeaning', 'plCorrespondent'].map(k => outputsOf('pp-photograph')[k]),
    ['artifact', 'creation', ''],
  );
  assert.equal(outputsOf('pp-book').plDateMeaning, 'publication');
});
````

- [ ] **Step 3: Run the chapter checks to confirm they fail**

Run: `node --test --test-name-pattern="B\.4|pp-" test/records.test.js test/examples.test.js test/pins.test.js test/coverage.test.js`
Expected: FAIL with `ERR_MODULE_NOT_FOUND` for `src/records/published.js`.

- [ ] **Step 4: Implement** `src/records/published.js`

````js
// B.4 · Published and personal sources.
import { isoDate, lastWord } from '../tables.js';

const PRIVATE = { heldBy: 'private', custodian: 'Peter Michael Grund', custodianPlace: 'Duluth, Minnesota' };
const PUBLICATION = { heldBy: 'publication', platform: '' };
const HELD_BY = 'privately held by {custodian}«, {custplace}»';

const capitalize = s => (s ? s.charAt(0).toUpperCase() + s.slice(1) : '');
const pagesLabel = pages => (/[–\-,]/.test(String(pages || '')) ? 'pp.' : 'p.');
const yearOf = text => (String(text || '').match(/\d{4}/) || [''])[0];

export const PUBLISHED = [
  {
    id: 'pp-book', chapter: 'pp', group: 'Published works', name: 'Book or bygdebok',
    hint: 'One Source per book (or multi-volume set cited as a unit)',
    source: [
      ['bookAuthor', 'Author', 'Birger Kirkeby'], ['btitle', 'Title'], ['gloss', 'English gloss (foreign titles)'],
      ['vol', 'Volume / part (as cited)', 'vol. 2, pt. 2'], ['city', 'City', 'Oslo'], ['publisher', 'Publisher'],
      ['year', 'Year'], ['format', 'Format (e-book, audiobook…)'], ['abbr', 'Abbrev', 'Eidsvoll bygdebok 2:2'],
    ],
    citation: [],
    pageVariants: [
      {
        key: 'pages', label: 'Pages',
        citation: [['pages', 'Pages', '432–440']],
        page: '{pl} {pages}«, {subject}»',
        frn: '{author}, {btitle}« [{gloss}]»«, {vol}» ({city}: {publisher}, {year}«. {format}»), {pl} {pages}{frnEnd}',
        srn: '{surname}, {abbr}, {pl} {pages}.',
      },
      {
        key: 'chapter', label: 'Chapter',
        citation: [['chapter', 'Chapter title'], ['pages', 'Pages']],
        page: '{chapter}, {pl} {pages}',
        frn: '{author}, "{chapter}," in {btitle}« [{gloss}]»«, {vol}» ({city}: {publisher}, {year}«. {format}»), {pl} {pages}.',
        srn: '{surname}, "{chapter}," {pl} {pages}.',
      },
      {
        key: 'volume', label: 'Multi-volume work',
        citation: [['volume', 'Volume'], ['pages', 'Pages']],
        page: 'vol. {volume}, {pl} {pages}«, {subject}»',
        frn: '{author}, {btitle}« [{gloss}]», vol. {volume} ({city}: {publisher}, {year}«. {format}»), {pl} {pages}{frnEnd}',
        srn: '{surname}, {abbr}, vol. {volume}, {pl} {pages}.',
      },
      {
        key: 'encyclopedia', label: 'Encyclopedia entry',
        citation: [['headword', 'Entry headword']],
        page: '{headword}',
        frn: '{author}, {btitle}« [{gloss}]»«, {vol}» ({city}: {publisher}, {year}«. {format}»), s.v. "{headword}."',
        srn: '{surname}, {abbr}, s.v. "{headword}."',
      },
    ],
    nouns: ['entry', ''],
    optionalSubject: true,
    holder: PUBLICATION, confidence: 'Normal', doctype: 'publication',
    derive: v => ({
      pl: pagesLabel(v.pages),
      surname: lastWord(v.bookAuthor),
      volCap: capitalize(String(v.vol || '').trim()),
      frnEnd: v.name ? `, "${v.name}."` : '.',
    }),
    title: '{btitle}',
    abbrev: '{abbr}',
    author: '{bookAuthor}',
    pubinfo: '«{volCap}. »{city}: {publisher}, {year}.« {format}.»« Digital images, {platform} ({home}).»',
    paperlessTitle: '{name} {abbr} {pl} {pages} ({year})',
    subjectLabel: 'Topic or section',
    pins: {
      title: [['B.4 §4', 'Book | [Title]']],
      page: [
        ['B.4 §7', 'Book | p. [N] or pp. [N]–[N], plus subject if relevant'],
        ['B.4 §7', 'Book chapter | [Chapter title], pp. [N]–[N]'],
        ['B.4 §7', 'Multi-volume work | vol. [N], pp. [N]–[N]'],
        ['B.4 §7', 'Encyclopedia | [entry headword]'],
      ],
      author: [['B.4 §2', "Book, one author | Author's name (Birger Kirkeby)"]],
      abbrev: [['B.4 §10', 'Book | Eidsvoll bygdebok 2:2']],
      confidence: [['B.4 §8', 'Normal | Genealogies citing primary records']],
    },
    examples: [{
      guide: 'B.4 Published book',
      inputs: {
        bookAuthor: 'Birger Kirkeby', btitle: 'Eidsvoll Bygds Historie: Gardene på vestside av Vorma',
        gloss: 'Eidsvoll Parish History: The Farms on the West Side of the Vorma River', vol: 'vol. 2, pt. 2',
        city: 'Oslo', publisher: 'Eidsvoll Bygdebokkomite', year: '1959', abbr: 'Eidsvoll bygdebok 2:2',
        variant: 'pages', pages: '432–440', name: 'Vinger gård', noun: 'entry',
      },
    }],
  },
  {
    id: 'pp-edited-collection', chapter: 'pp', group: 'Published works', name: 'Edited collection',
    hint: 'A book with chapters by different authors (EE 13.65)',
    source: [
      ['editor', 'Editor(s)', 'Sarah L. Wilkerson Freeman and Beverly Greene Bond'], ['btitle', 'Title', 'Tennessee Women: Their Lives and Times'],
      ['city', 'City', 'Athens'], ['publisher', 'Publisher', 'University of Georgia Press'], ['year', 'Year', '2009'], ['abbr', 'Abbrev', 'Tennessee Women 2009'],
    ],
    citation: [['chapterAuthor', 'Chapter author'], ['chapter', 'Chapter title'], ['pages', 'Pages']],
    nouns: [''],
    optionalSubject: true,
    holder: PUBLICATION, confidence: 'Normal', doctype: 'publication',
    derive: v => ({ pl: pagesLabel(v.pages), chapterSurname: lastWord(v.chapterAuthor) }),
    title: '{btitle}',
    abbrev: '{abbr}',
    author: '{editor}, editor',
    pubinfo: '{city}: {publisher}, {year}.« Digital images, {platform} ({home}).»',
    page: '{chapter}, {pl} {pages}«, {subject}»',
    frn: '{chapterAuthor}, "{chapter}," in {btitle}, ed. {editor} ({city}: {publisher}, {year}), {pl} {pages}.',
    srn: '{chapterSurname}, "{chapter}," {pl} {pages}.',
    subjectLabel: 'Topic (optional)',
    pins: {
      title: [['B.4 §4', 'Edited collection | [Title]']],
      page: [['B.4 §7', 'Book chapter | [Chapter title], pp. [N]–[N]']],
      author: [['B.4 §2', 'Edited collection | [Name], editor (EE 13.65)']],
      abbrev: [['B.4 §10', 'Book | Eidsvoll bygdebok 2:2 · Tennessee Women 2009']],
    },
    examples: [],
  },
  {
    id: 'pp-periodical', chapter: 'pp', group: 'Published works', name: 'Periodical article',
    hint: 'One Source per periodical title; the issue goes in the page string',
    source: [['periodical', 'Periodical', 'American Genealogist'], ['pcity', 'City, state', 'New Haven, Connecticut']],
    citation: [['aauthor', 'Article author'], ['atitle', 'Article title'], ['volume', 'Volume'], ['issue', 'Issue no.'], ['ayear', 'Year'], ['pages', 'Pages']],
    nouns: [''],
    optionalSubject: true,
    holder: PUBLICATION, confidence: 'Normal', doctype: 'publication',
    derive: v => ({ pl: pagesLabel(v.pages), articleSurname: lastWord(v.aauthor) }),
    title: '{periodical}, {pcity}',
    abbrev: '{periodical}',
    author: '',
    pubinfo: '{pcity}.',
    page: 'vol. {volume}, no. {issue} ({ayear}), {pl} {pages}«, {subject}»',
    frn: '{aauthor}, "{atitle}," {periodical} {volume} ({ayear}): {pages}.',
    srn: '{articleSurname}, "{atitle}," {pages}.',
    subjectLabel: 'Topic (optional)',
    pins: {
      title: [['B.4 §4', 'Periodical | [Title], [city, state]']],
      page: [['B.4 §7', 'Periodical article | vol. [N], no. [N] ([year]), pp. [N]–[N]']],
      author: [['B.4 §2', 'Periodical | Blank']],
      abbrev: [['B.4 §10', 'Periodical | American Genealogist']],
    },
    examples: [],
  },
  {
    id: 'pp-register', chapter: 'pp', group: 'Published works', name: 'Directory or register',
    hint: 'Membership roster or school register; one Source per annual issue or volume',
    source: [
      ['issuer', 'Issuing body or compiler', 'Den norske sakførerforening'], ['rtitle', 'Title'], ['gloss', 'English gloss'],
      ['city', 'City', 'Oslo'], ['publisher', 'Publisher'], ['year', 'Year'], ['abbr', 'Abbrev'],
      ['srnAuthor', 'Author in SRN (surname, if a person)', 'Langangen'],
    ],
    citation: [['page', 'Page'], ['image', 'Image', 'if not the page'], ['entry', 'Entry no. (if any)']],
    nouns: [''],
    holder: { heldBy: 'publication', platform: 'Nasjonalbiblioteket' }, confidence: 'Normal', doctype: 'publication',
    derive: v => ({ entryLead: String(v.entry || '').trim() ? `entry no. ${String(v.entry).trim()}, ` : 'entry for ' }),
    title: '{rtitle}',
    abbrev: '{abbr}',
    author: '{issuer}',
    pubinfo: '{city}: {publisher}, {year}.« Digital images, {platform} ({home}).»',
    page: 'p. {page}« (image {image})»«, entry no. {entry}», {subject}',
    frn: '{author}, {rtitle}« [{gloss}]» ({city}: {publisher}, {year}), p. {page}, {entryLead}{name}«; digital image, {platform} ({url} : accessed {accessed})».',
    srn: '«{srnAuthor}, »{abbr}, p. {page}«, no. {entry}», {name}.',
    pins: {
      title: [['B.4 §4', 'Membership directory | [Title with year]'], ['B.4 §4', 'School roster | [Title with years]']],
      author: [['B.4 §2', 'Membership directory / organizational publication | Issuing body (Den norske sakførerforening)']],
      abbrev: [['B.4 §10', 'Register | Sakførerforening medlemmer 1950 · Kristiania katedralskole 1891–1901']],
      confidence: [['B.4 §8', 'Normal | Genealogies citing primary records; biographical and membership directories; school records']],
    },
    examples: [
      {
        guide: 'B.4 Membership directory',
        inputs: {
          issuer: 'Den norske sakførerforening', rtitle: 'Medlemmer av Den norske sakførerforening 1. juli 1950',
          gloss: 'Members of the Norwegian Bar Association as of 1 July 1950', city: 'Oslo', publisher: 'Den norske sakførerforening',
          year: '1951', abbr: 'Sakførerforening medlemmer 1950', page: '440', image: '443', name: 'Frithjof Siggerud', noun: '',
          url: 'https://www.nb.no/items/b3f9413b2125c7f26063abb8896d95bf?page=443', accessed: '26 April 2026', eventYear: '1950',
        },
      },
      {
        guide: 'B.4 School enrollment register',
        inputs: {
          issuer: 'Anders Langangen', rtitle: 'Elever ved Kristiania katedralskole som begynte på skolen i årene 1891–1901, hefte 8',
          gloss: 'Pupils at Kristiania Cathedral School Who Began in the Years 1891–1901, Booklet 8', city: '[Place]', publisher: '[Publisher]',
          year: '[year]', abbr: 'Kristiania katedralskole 1891–1901', srnAuthor: 'Langangen',
          page: '112', image: '111', entry: '498', name: 'Erling Frithjof Siggerud', noun: '',
          url: 'https://www.nb.no', accessed: '26 April 2026',
        },
      },
    ],
  },
  {
    id: 'pp-video', chapter: 'pp', group: 'Published works', name: 'Online video',
    hint: 'Use video only for context, never as the source for a date, name, or relationship',
    source: [
      ['channel', 'Channel or producer', 'Värmland Local History Channel'], ['vtitle', 'Video title'],
      ['vshort', 'Short title (Abbrev)'], ['channelShort', 'Channel in SRN (if shorter)'], ['year', 'Year'],
    ],
    citation: [['range', 'Minute range', '12:30–14:15']],
    nouns: [''],
    holder: { heldBy: 'publication', platform: 'YouTube' }, confidence: 'Low', doctype: 'publication',
    derive: v => ({ topic: String(v.details || '').trim() || v.name, srnChannel: String(v.channelShort || '').trim() || v.channel }),
    title: '{vtitle}',
    abbrev: '{vshort}',
    author: '{channel}',
    pubinfo: 'Online video, {platform} ({home}), {year}.',
    page: 'minute {range}, {subject}',
    frn: '{channel}, "{vtitle}," {platform} video ({url} : accessed {accessed}), minute {range}, on {topic}.',
    srn: '{srnChannel}, "{vshort}," minute {range}.',
    subjectLabel: 'Topic',
    detailsLabel: 'Topic as worded in the FRN (if different)',
    paperlessTitle: '{vshort} video clip {year}',
    pins: {
      title: [['B.4 §4', 'Online video | [Title]']],
      page: [['B.4 §7', 'Audio interview / video | minute [N]:[NN], [topic] (or transcript p. [N], [topic])']],
      author: [['B.4 §2', 'Online video | Channel or production company']],
      abbrev: [['B.4 §10', 'Online video | Norra Ny walking tour (the SRN may lead with the channel)']],
    },
    examples: [{
      guide: 'B.4 Online video',
      inputs: {
        channel: 'Värmland Local History Channel', vtitle: 'Norra Ny parish history walking tour', vshort: 'Norra Ny walking tour',
        channelShort: 'Värmland History YouTube', year: '2025', range: '12:30–14:15', name: 'Ambjörby torpare landscape', noun: '',
        details: 'the Ambjörby torpare landscape', url: 'https://www.youtube.com/watch?v=[ID]', accessed: '9 May 2026',
      },
    }],
  },
  {
    id: 'pp-bible', chapter: 'pp', group: 'Family artifacts', name: 'Family Bible',
    hint: 'Photograph the cover, title page, and all family pages before judging confidence',
    source: [
      ['surname', 'Family surname', 'Grund'], ['years', 'Years of entries', '1848–1932'], ['compiler', 'Inferred compiler', 'Per Larsson Grund'],
      ['btitle', 'Bible title', 'The Holy Bible Containing the Old and New Testaments'], ['city', 'Place of publication'],
      ['publisher', 'Bible publisher'], ['year', 'Bible year'],
    ],
    citation: [['pagelabel', 'Page', 'family page 2']],
    nouns: ['birth entry', 'marriage entry', 'death entry'],
    holder: PRIVATE, confidence: 'High', doctype: 'artifact',
    title: '{surname} Family Bible Records, {years}',
    abbrev: '{surname} Family Bible',
    author: '[{compiler}]',
    pubinfo: '{btitle}. {city}: {publisher}, {year}.',
    page: '{pagelabel}, {subject}',
    frn: `[{compiler}], compiler, {surname} Family Bible Records, {years}, in {btitle} ({city}: {publisher}, {year}), {pagelabel}, entry for {name}« {details}»; ${HELD_BY}.`,
    srn: '{surname} Family Bible, {pagelabel}, {subject}.',
    detailsLabel: 'Entry details (dates, places)',
    pins: {
      title: [['B.4 §4', 'Family Bible | [Surname] Family Bible Records, [years]']],
      page: [['B.4 §7', 'Family Bible | [record-type] page, [event] (family page, Per Larsson birth entry)']],
      author: [['B.4 §2', 'Family Bible | Inferred compiler in brackets ([Per Larsson Grund]), or blank.']],
      abbrev: [['B.4 §10', 'Family Bible | Grund Family Bible']],
    },
    examples: [{
      guide: 'B.4 Family Bible',
      inputs: {
        surname: 'Grund', years: '1848–1932', compiler: 'Per Larsson Grund', btitle: 'The Holy Bible Containing the Old and New Testaments',
        city: 'Stockholm', publisher: '[Bible publisher]', year: '[year]', pagelabel: 'family page 2',
        name: 'Per Larsson Grund', noun: 'birth entry', details: 'born 14 January 1848 at Ambjörby, Norra Ny parish',
        comment: "Entries appear in two distinct hands: an early hand for events 1848–1880, a later hand for events 1881–1932. The earliest entries appear to have been copied into this Bible from an earlier family record after the Bible's purchase.",
      },
    }],
  },
  {
    id: 'pp-family-record', chapter: 'pp', group: 'Family artifacts', name: 'Family record',
    hint: 'A family record other than a Bible (notes, registers, histories)',
    source: [['family', 'Family or compiler', 'Grund'], ['rtype', 'Record type', 'Family Record'], ['compiler', 'Compiler (if known)']],
    citation: [['pagelabel', 'Page or section']],
    nouns: ['birth entry', 'marriage entry', 'death entry', ''],
    holder: PRIVATE, confidence: '', doctype: 'artifact',
    title: '{family} {rtype}',
    abbrev: '{family} {rtype}',
    author: '«[{compiler}]»',
    page: '{pagelabel}, {subject}',
    frn: `«[{compiler}], compiler, »{family} {rtype}, {pagelabel}, entry for {name}« {details}»; ${HELD_BY}.`,
    srn: '{family} {rtype}, {pagelabel}, {subject}.',
    pins: {
      title: [['B.4 §4', 'Family record | [Family/compiler] [record type]']],
      author: [['B.4 §2', 'Family record (non-Bible) | Blank, or compiler in brackets']],
    },
    examples: [],
  },
  {
    id: 'pp-funeral-program', chapter: 'pp', group: 'Family artifacts', name: 'Funeral program',
    hint: 'One Source per program unless several artifacts share one provenance (A1)',
    source: [
      ['dname', 'Deceased', 'Thomas Emil Siggerud'], ['funeralHome', 'Funeral home', 'Helgeson Funeral Home'],
      ['city', 'City', 'Williams, Minnesota'], ['date', 'Service date', '16 February 1953'], ['ptitle', 'Printed title', 'In Memory of Thomas Emil Siggerud'],
    ],
    citation: [],
    nouns: ['funeral program', 'obituary'],
    holder: PRIVATE, confidence: 'High', doctype: 'ephemera',
    derive: v => ({ surname: lastWord(v.dname), year: yearOf(v.date) }),
    title: 'Funeral program, {dname}',
    abbrev: '{surname} funeral program, {year}',
    author: '{funeralHome}',
    pubinfo: '{city}: {funeralHome}, {date}.',
    page: '{subject}',
    frn: `{funeralHome}, "{ptitle}," funeral program for services held {date}« {details}»; ${HELD_BY}.`,
    srn: '{surname} funeral program, {year}.',
    detailsLabel: 'Service details (church, officiant, burial)',
    paperlessTitle: '{dname} funeral program {year}',
    pins: {
      title: [['B.4 §4', 'Funeral program | Funeral program, [Subject]']],
      page: [['B.4 §7', 'Funeral program | [subject] (short enough to need no page)']],
      author: [['B.4 §2', 'Funeral program | Funeral home (Helgeson Funeral Home)']],
      abbrev: [['B.4 §10', 'Artifact | Siggerud funeral program, 1953']],
      pubinfo: [['A10', 'Funeral program | [City]: [Funeral home], date.']],
    },
    examples: [{
      guide: 'B.4 Funeral program',
      inputs: {
        dname: 'Thomas Emil Siggerud', funeralHome: 'Helgeson Funeral Home', city: 'Williams, Minnesota', date: '16 February 1953',
        ptitle: 'In Memory of Thomas Emil Siggerud', name: 'Thomas Emil Siggerud', noun: 'funeral program',
        details: 'at Lutheran Church, Williams, Minnesota; Rev. Edstrom officiating; burial at Pine Hill Cemetery, Williams, Minnesota',
      },
    }],
  },
  {
    id: 'pp-photograph', chapter: 'pp', group: 'Family artifacts', name: 'Photograph',
    hint: 'When the photo itself is the evidence; otherwise attach it to the relevant citation',
    source: [
      ['pname', 'Subject', 'Per Larsson Grund'], ['ptype', 'Photo type', 'cabinet card'], ['pdate', 'Date', 'ca. 1890s'],
      ['photographer', 'Photographer (Author, if known)'], ['studio', 'Studio'], ['scity', 'Studio city'],
    ],
    citation: [['element', 'Image element', 'cabinet card front'], ['element2', 'Second element (optional)']],
    nouns: ['portrait', ''],
    holder: PRIVATE, confidence: 'High', doctype: 'artifact',
    derive: v => ({ surname: lastWord(v.pname), decade: String(v.pdate || '').replace(/^ca\.\s*/, '').trim() }),
    title: '{pname} {ptype}, {pdate}',
    abbrev: '{surname} {ptype} {decade}',
    author: '«{photographer}»',
    pubinfo: '«{studio}, {scity}, {pdate}.»« Digital images, {platform} ({home}).»',
    page: '{element}, {subject}«; {element2}»',
    frn: `{pname} {ptype} portrait, {pdate}«, taken at {studio}, {scity}»«; {details}»; ${HELD_BY}.`,
    srn: '{pname} {ptype}, {pdate}.',
    detailsLabel: 'Inscriptions and marks (FRN)',
    paperlessTitle: '{pname} photograph {decade}',
    pins: {
      title: [['B.4 §4', 'Photograph | [Subject] [photo type], [year or range]']],
      page: [['B.4 §7', 'Photograph | [image element], [subject] (top of mount inscription, "Grandma\'s Grandpa")']],
      author: [['B.4 §2', 'Photograph | Photographer or studio if known']],
      abbrev: [['B.4 §10', 'Artifact | Siggerud funeral program, 1953 · Grund cabinet card 1890s']],
    },
    examples: [{
      guide: 'B.4 Photograph',
      inputs: {
        pname: 'Per Larsson Grund', ptype: 'cabinet card', pdate: 'ca. 1890s', studio: 'Miller Studio', scity: 'St. Cloud, Minnesota',
        element: 'cabinet card front', element2: 'inscription on mount, "Grandma\'s Grandpa"', name: 'Per Larsson Grund', noun: 'portrait',
        details: 'inscription on top of mount in cursive: "Grandma\'s Grandpa"; printed studio mark on bottom of mount: "Miller" (with M-M monogram), "ST. CLOUD, MINN."',
        comment: 'Subject identification is family attribution by inscription rather than caption with full name.',
      },
    }],
  },
  {
    id: 'pp-letter', chapter: 'pp', group: 'Family artifacts', name: 'Family letter',
    hint: 'One letter cited substantively; one collection when the collection is cited',
    source: [['sender', 'Writer', 'Per Larsson Grund'], ['recipient', 'Recipient', 'John Edwin Grund'], ['date', 'Date', '14 March 1925']],
    citation: [],
    nouns: [''],
    holder: PRIVATE, confidence: 'High', doctype: 'correspondence',
    derive: v => ({ senderSurname: lastWord(v.sender), recipientSurname: lastWord(v.recipient), iso: isoDate(v.date) }),
    title: '{sender} to {recipient}, {date}, letter',
    abbrev: '{senderSurname} to {recipientSurname} letter, {date}',
    author: '{sender}',
    pubinfo: '',
    page: '{subject}',
    frn: `{sender} to {recipient}, letter, {date}«, {details}»; ${HELD_BY}.`,
    srn: '{sender} to {recipient}, {date}.',
    subjectLabel: 'Topic, subject (e.g. report of a death, Name death entry)',
    detailsLabel: 'Content for the FRN',
    paperlessTitle: '{sender} to {recipient} letter {iso}',
    pins: {
      title: [['B.4 §4', 'Letter | [Sender] to [Recipient], [date], letter']],
      author: [['B.4 §2', 'Letter | Writer']],
    },
    examples: [],
  },
  {
    id: 'pp-interview', chapter: 'pp', group: 'People', name: 'Audio interview',
    hint: "The interviewee is the Author (EE 4.31). Never publish a living informant's address (A12).",
    source: [['interviewee', 'Interviewee', 'Tom Grund'], ['interviewer', 'Interviewer', 'Peter Grund'], ['city', 'Place', 'Duluth, Minnesota'], ['date', 'Date', '12 March 2024']],
    citation: [['minute', 'Timestamp', '23:15']],
    nouns: [''],
    holder: PRIVATE, confidence: 'Normal', doctype: 'interview',
    derive: v => ({ iso: isoDate(v.date), topic: String(v.details || '').trim() || v.name }),
    title: '{interviewee} interview by {interviewer}, {date}',
    abbrev: '{interviewee} interview, {iso}',
    author: '{interviewee}',
    pubinfo: 'Recorded interview, {city}, {date}.',
    page: 'minute {minute}, {subject}',
    frn: '{interviewee} ({city}), recorded interview by {interviewer}, {date}; audio recording and transcript privately held by {custodian}, [ADDRESS FOR PRIVATE USE,] {custplace}; minute {minute}, on {topic}.',
    srn: '{interviewee} interview, {date}, minute {minute}.',
    subjectLabel: 'Topic',
    detailsLabel: 'Topic as worded in the FRN (if different)',
    paperlessTitle: '{interviewee} interview {iso}',
    pins: {
      title: [['B.4 §4', 'Audio interview | [Interviewee] interview by [Interviewer], [date]']],
      page: [['B.4 §7', 'Audio interview / video | minute [N]:[NN], [topic] (or transcript p. [N], [topic])']],
      author: [['B.4 §2', 'Audio interview | The interviewee (EE 4.31)']],
      abbrev: [['B.4 §10', 'Interview | Tom Grund interview, 2024-03-12']],
      pubinfo: [['A10', 'Audio interview | Recorded interview, [city], date.']],
    },
    examples: [{
      guide: 'B.4 Audio interview',
      inputs: {
        interviewee: 'Tom Grund', interviewer: 'Peter Grund', city: 'Duluth, Minnesota', date: '12 March 2024',
        minute: '23:15', name: "Edmund Gene Grund's military service in WWII", noun: '', details: "Edmund Gene Grund's WWII service",
        comment: 'Tom is a son of Edmund Gene Grund and reports here on events he learned of from his parents (he was born after the war).',
      },
    }],
  },
  {
    id: 'pp-oral-history', chapter: 'pp', group: 'People', name: 'Oral-history collection',
    hint: 'A collection of interviews cited as a whole',
    source: [['collection', 'Collection title', 'Cane River Oral History Collection'], ['call', 'Call number']],
    citation: [['interviewee', 'Interviewee'], ['interviewer', 'Interviewer'], ['date', 'Interview date'], ['locator', 'Minute or transcript page', 'minute 12:30']],
    nouns: [''],
    holder: { heldBy: 'archive', archive: '', platform: '' }, confidence: '', doctype: 'interview',
    derive: v => ({ topic: String(v.details || '').trim() || v.name }),
    title: '{collection}',
    abbrev: '{collection}',
    author: '{collection}',
    page: '{locator}, {subject}',
    frn: '{interviewee}, interview by {interviewer}, {date}, {collection}; {locator}, on {topic}; citing {repository}«, {call}».',
    srn: '{collection}, {interviewee}, {locator}.',
    subjectLabel: 'Topic',
    detailsLabel: 'Topic as worded in the FRN (if different)',
    pins: {
      title: [['B.4 §4', 'Oral-history collection | [Collection title]']],
      page: [['B.4 §7', 'Audio interview / video | minute [N]:[NN], [topic] (or transcript p. [N], [topic])']],
      author: [['B.4 §2', 'Oral-history collection | Collection name']],
    },
    examples: [],
  },
  {
    id: 'pp-research', chapter: 'pp', group: 'People', name: "Another genealogist's research",
    hint: "Their conclusion isn't evidence; their cited sources are. Prefer the primary record.",
    source: [
      ['researcher', 'Researcher', 'Siw Alfreddson'], ['topic', 'Topic (Title)', 'Ambjörby, Sweden'],
      ['rtopic', 'Topic (FRN)', 'the Grund family of Ambjörby, Sweden'], ['place', 'Place', 'Ambjörby, Sweden'], ['years', 'Years', '2024–2026'],
    ],
    citation: [['section', 'Section or item', 'Entry for Ambmyra, typed page, received 30 April 2026']],
    note: [['copies', 'Copies held by (FRN)', 'Peter Grund, Duluth, Minnesota']],
    nouns: [''],
    optionalSubject: true,
    holder: { heldBy: 'private', custodian: 'Siw Alfreddson', custodianPlace: 'Ambjörby, Sweden', custodyWording: 'personal collection' },
    confidence: 'Normal', doctype: 'research',
    derive: v => ({ surname: lastWord(v.researcher), topicShort: String(v.topic || '').split(',')[0].trim() }),
    title: 'Personal research of {researcher}, {topic}',
    abbrev: '{surname} research',
    author: '{researcher}',
    pubinfo: 'Unpublished research, {place}, {years}.',
    page: '{section}«, {subject}»',
    frn: `{researcher}, personal research on {rtopic}, accumulated {years}, {details}; ${HELD_BY}«, with copies privately held by {copies}».`,
    srn: '{surname} research, {section}.',
    subjectLabel: 'Topic, subject (optional)',
    detailsLabel: 'Item description (FRN)',
    eventYearLabel: 'Received (Paperless)',
    paperlessTitle: '{surname} {topicShort} research {eventYear}',
    pins: {
      title: [['B.4 §4', 'Personal research | Personal research of [Researcher], [topic]']],
      page: [['B.4 §7', 'Personal research | [topic or section], [page if compiled]']],
      author: [['B.4 §2', 'Personal research | Researcher (Siw Alfreddson)']],
      abbrev: [['B.4 §10', 'Personal research | Alfreddson research']],
      pubinfo: [['A10', 'Personal research | Unpublished research, [location], [year-range].']],
    },
    examples: [{
      guide: 'B.4 Personal research',
      inputs: {
        researcher: 'Siw Alfreddson', topic: 'Ambjörby, Sweden', rtopic: 'the Grund family of Ambjörby, Sweden',
        place: 'Ambjörby, Sweden', years: '2024–2026', section: 'Entry for Ambmyra, typed page, received 30 April 2026',
        details: 'typed page on Ambmyra torpare holdings, received by Peter Grund via email 30 April 2026',
        copies: 'Peter Grund, Duluth, Minnesota',
        comment: "Siw's notes cite Norra Ny kyrkoarkiv volumes for each fact she records; for facts she draws from those primary records, the underlying primary record should also be cited directly when used in narrative.",
      },
    }],
  },
];
````

- [ ] **Step 5: Run the chapter checks, then everything so far**

Run: `node --test --test-name-pattern="B\.4|pp-" test/records.test.js test/examples.test.js test/pins.test.js test/coverage.test.js`
Expected: `tests 220`, `pass 213`, `fail 0`, `skipped 2`, `todo 5`.

Run: `npm test`
Expected: `tests 799`, `pass 778`, `fail 0`, `skipped 8`, `todo 13`, and a diagnostic `Unpinned: no-ministerialbok.frn, …` listing the templates the guide has no row or example for.

- [ ] **Step 6: Commit**

```bash
git add src/records/index.js src/records/published.js test/paperless.test.js
git commit -m "Add published and personal record types" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 9: Rule checks

**Files:**
- Create: `src/checks.js`
- Test: `test/checks.test.js`

**Interfaces:**
- Consumes: `plain`, `hasGap` (Task 1); `PLATFORMS`, `PLATFORM_ARCHIVES` (Task 3); `buildOutputs`, `draftFromExample`, `newDraft` (Task 4); `recordById` (Task 8).
- Produces: `runChecks(type, draft, outputs) → [{ rule, message }]` where `rule` is a guide reference (`'A4'`, `'A10'`, `'B.3 §10'`, …) or `'Fill'`.

- [ ] **Step 1: Write the failing test** `test/checks.test.js`

````js
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { runChecks } from '../src/checks.js';
import { draftFromExample, buildOutputs, newDraft } from '../src/engine.js';
import { recordById } from '../src/records/index.js';

const klokk = recordById('no-klokkerbok');
const clean = () => draftFromExample(klokk, klokk.examples[0]);
const rulesFor = (type, draft) => runChecks(type, draft, buildOutputs(type, draft)).map(p => p.rule);

test('a complete worked example has no problems', () => {
  assert.deepEqual(rulesFor(klokk, clean()), []);
});

test('A4: a raw image ID in the page string', () => {
  const d = clean();
  d.overrides.page = 'p. 57, kb20060313011115, Thor Emil baptism entry';
  assert.deepEqual(rulesFor(klokk, d), ['A4']);
});

test('A4: the volume repeated in a Norwegian page string, but not a bare number', () => {
  const d = clean();
  d.overrides.page = 'I 2, p. 57, no. 21, Thor Emil baptism entry';
  assert.deepEqual(rulesFor(klokk, d), ['A4']);
  const minutes = recordById('no-minutes');
  const m = newDraft(minutes);
  Object.assign(m.values, { fylke: 'Akershus', parish: 'Eidsvoll', vol: '1', years: '1870–1895', page: '1', date: '3 May 1880' });
  m.subject.name = 'church building fund';
  assert.ok(!rulesFor(minutes, m).includes('A4'));
});

test('A4: a machine path in the Title', () => {
  const d = clean();
  d.overrides.title = 'Norway, Akershus, Eidsvoll, AV/SAO-A-10888/G/Ga/L0002';
  assert.deepEqual(rulesFor(klokk, d), ['A4']);
});

test('A10: a deep URL in Pubinfo', () => {
  const d = clean();
  d.overrides.pubinfo = 'Digital images, Digitalarkivet (https://www.digitalarkivet.no/view/255).';
  assert.deepEqual(rulesFor(klokk, d), ['A10']);
});

test('A9: a publisher named as Repository, but not an archive platform', () => {
  const d = clean();
  d.overrides.repository = 'Ancestry';
  assert.deepEqual(rulesFor(klokk, d), ['A9']);
  d.overrides.repository = 'Riksarkivet';
  assert.deepEqual(rulesFor(klokk, d), []);
});

test('A8: a hyphen in a year-range', () => {
  const d = clean();
  d.values.years = '1866-1871';
  assert.deepEqual(rulesFor(klokk, d), ['A8']);
});

test('B.3 §10: a USPS state code', () => {
  const census = recordById('us-federal-census');
  const d = draftFromExample(census, census.examples[0]);
  d.overrides.abbrev = 'St. Louis Co., MN, 1920 census';
  assert.deepEqual(rulesFor(census, d), ['B.3 §10']);
});

test('A5: an image URL without an access date', () => {
  const d = clean();
  d.values.accessed = '';
  assert.deepEqual(rulesFor(klokk, d), ['A5', 'Fill']);
});

test('A6: no confidence chosen', () => {
  const d = clean();
  d.confidence = '';
  assert.deepEqual(rulesFor(klokk, d), ['A6']);
});

test('Fill: unfilled parts are listed by field', () => {
  const problems = runChecks(klokk, newDraft(klokk), buildOutputs(klokk, newDraft(klokk)));
  const fill = problems.find(p => p.rule === 'Fill');
  assert.equal(fill.message, 'Unfilled parts in: Title, Abbrev, Author, Page, FRN, SRN.');
});
````

- [ ] **Step 2: Run it to confirm it fails**

Run: `node --test test/checks.test.js`
Expected: FAIL with `ERR_MODULE_NOT_FOUND` for `src/checks.js`.

- [ ] **Step 3: Implement** `src/checks.js`

````js
// Rule checks shown in the status bar. Each returns { rule, message } problems.
import { plain, hasGap } from './template.js';
import { PLATFORMS, PLATFORM_ARCHIVES } from './tables.js';

const RAW_IMAGE_ID = /\b(kb|ft|pf)\d{8,}|\bC\d{7}_\d{3,}|\bFolk_\d+-\d+|\bv\d{4,}\.b\d+/;
const USPS = /(^|[\s,(])(AL|AK|AZ|AR|CA|CO|CT|DE|FL|GA|HI|ID|IL|IN|IA|KS|KY|LA|ME|MD|MA|MI|MN|MS|MO|MT|NE|NV|NH|NJ|NM|NY|NC|ND|OH|OK|OR|PA|RI|SC|SD|TN|TX|UT|VT|VA|WA|WV|WI|WY)([\s,.)]|$)/;
const FIELD_NAMES = { title: 'Title', abbrev: 'Abbrev', author: 'Author', pubinfo: 'Pubinfo', repository: 'Repository', page: 'Page', frn: 'FRN', srn: 'SRN' };
const escapeRe = s => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');

export function runChecks(type, draft, outputs) {
  const o = Object.fromEntries(Object.entries(outputs).map(([k, v]) => [k, plain(v)]));
  const problems = [];
  const add = (rule, message) => problems.push({ rule, message });

  if (RAW_IMAGE_ID.test(o.page)) add('A4', 'The page string contains a raw image ID. Image IDs go only in the FRN URL.');

  const vol = String(draft.values.vol || draft.values.series || '').trim();
  if (['no', 'se'].includes(type.chapter) && vol && !/^\d+$/.test(vol)
    && new RegExp(`(^|[\\s,(])${escapeRe(vol)}([\\s,)]|$)`).test(o.page)) {
    add('A4', `The page string repeats the volume (${vol}). The Source is one volume, so start at the page or entry.`);
  }

  if (/\bAV\/|\bSE\/VA\//.test(o.title)) add('A4', 'The Title contains an archive machine path. Keep it in Call number only.');

  const deepUrl = (o.pubinfo.match(/https?:\/\/[^\s)]+/g) || []).some(u => /^https?:\/\/[^/]+\/\S+/.test(u));
  if (deepUrl) add('A10', 'Pubinfo holds a deep URL. Pubinfo takes the platform homepage only; the image link goes in the FRN.');

  if (PLATFORMS[o.repository] && !PLATFORM_ARCHIVES.includes(o.repository)) {
    add('A9', `${o.repository} is a publisher, not a repository. Leave Repository blank and name it in Pubinfo.`);
  }

  if (/\b\d{4}-\d{4}\b/.test(`${o.title} ${o.abbrev}`)) add('A8', 'Use an en dash in year-ranges (1862–1869), not a hyphen.');

  if (type.chapter === 'us' && USPS.test(`${o.abbrev} ${o.srn}`)) add('B.3 §10', 'Use traditional state abbreviations (Minn., Wis.), never USPS codes.');

  if (String(draft.values.url || '').trim() && !String(draft.values.accessed || '').trim()) add('A5', 'The image URL has no access date.');

  if (!draft.confidence) add('A6', 'Choose a confidence level.');

  const gaps = Object.keys(FIELD_NAMES).filter(k => hasGap(outputs[k]));
  if (gaps.length) add('Fill', `Unfilled parts in: ${gaps.map(k => FIELD_NAMES[k]).join(', ')}.`);

  return problems;
}
````

- [ ] **Step 4: Run the test to confirm it passes**

Run: `node --test test/checks.test.js`
Expected: `tests 11`, `pass 11`, `fail 0`.

- [ ] **Step 5: Commit**

```bash
git add src/checks.js test/checks.test.js
git commit -m "Add rule checks for the status bar" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 10: Draft storage

**Files:**
- Create: `src/store.js`
- Test: `test/store.test.js`

**Interfaces:**
- Consumes: `newDraft` (Task 4); `recordById` (Task 8).
- Produces: `STORE_KEY = 'gcCitationGenerator.v1'`, `loadState(storage, recordById) → { current, drafts, filter } | null`, `saveState(storage, state) → boolean`. `storage` is anything with `getItem`/`setItem` (or `null`).

- [ ] **Step 1: Write the failing test** `test/store.test.js`

````js
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { loadState, saveState, STORE_KEY } from '../src/store.js';
import { recordById } from '../src/records/index.js';
import { newDraft } from '../src/engine.js';

const memory = (initial = {}) => {
  const data = { ...initial };
  return { getItem: k => (k in data ? data[k] : null), setItem: (k, v) => { data[k] = String(v); }, data };
};

test('saves and loads the current type and its draft', () => {
  const storage = memory();
  const draft = newDraft(recordById('no-klokkerbok'));
  draft.values.parish = 'Eidsvoll';
  assert.equal(saveState(storage, { current: 'no-klokkerbok', drafts: { 'no-klokkerbok': draft }, filter: 'kirke' }), true);
  const state = loadState(storage, recordById);
  assert.equal(state.current, 'no-klokkerbok');
  assert.equal(state.filter, 'kirke');
  assert.equal(state.drafts['no-klokkerbok'].values.parish, 'Eidsvoll');
});

test('nothing usable saved gives null', () => {
  assert.equal(loadState(memory(), recordById), null);
  assert.equal(loadState(memory({ [STORE_KEY]: '{not json' }), recordById), null);
  assert.equal(loadState(memory({ [STORE_KEY]: JSON.stringify({ current: 'gone-type', drafts: {} }) }), recordById), null);
});

test('drafts for removed types and unknown fields are dropped', () => {
  const saved = {
    current: 'no-klokkerbok',
    drafts: {
      'gone-type': { values: { x: '1' } },
      'no-klokkerbok': { values: { parish: 'Eidsvoll', oldField: 'x' }, subject: { name: 7 }, overrides: { title: 'T', bad: 3 } },
    },
  };
  const state = loadState(memory({ [STORE_KEY]: JSON.stringify(saved) }), recordById);
  assert.deepEqual(Object.keys(state.drafts), ['no-klokkerbok']);
  const d = state.drafts['no-klokkerbok'];
  assert.equal(d.values.parish, 'Eidsvoll');
  assert.equal('oldField' in d.values, false);
  assert.equal(d.subject.name, '');
  assert.deepEqual(d.overrides, { title: 'T' });
});

test('storage that throws is survivable', () => {
  const broken = { getItem() { throw new Error('denied'); }, setItem() { throw new Error('denied'); } };
  assert.equal(loadState(broken, recordById), null);
  assert.equal(saveState(broken, { current: 'no-klokkerbok', drafts: {} }), false);
  assert.equal(loadState(null, recordById), null);
});
````

- [ ] **Step 2: Run it to confirm it fails**

Run: `node --test test/store.test.js`
Expected: FAIL with `ERR_MODULE_NOT_FOUND` for `src/store.js`.

- [ ] **Step 3: Implement** `src/store.js`

````js
// Saves the work in progress in browser storage: the current record type and one draft per type.
import { newDraft } from './engine.js';

export const STORE_KEY = 'gcCitationGenerator.v1';

/** Returns { current, drafts, filter } or null when nothing usable is saved. */
export function loadState(storage, recordById) {
  let saved;
  try {
    saved = JSON.parse(storage?.getItem(STORE_KEY) ?? 'null');
  } catch {
    return null;
  }
  if (!saved || typeof saved !== 'object' || !recordById(saved.current)) return null;
  const drafts = {};
  for (const [id, draft] of Object.entries(saved.drafts || {})) {
    const type = recordById(id);
    if (!type || !draft || typeof draft !== 'object') continue;
    drafts[id] = mergeDraft(newDraft(type), draft);
  }
  return { current: saved.current, drafts, filter: typeof saved.filter === 'string' ? saved.filter : '' };
}

export function saveState(storage, state) {
  try {
    storage?.setItem(STORE_KEY, JSON.stringify(state));
    return true;
  } catch {
    return false;
  }
}

/** Keeps saved values only where the current version still has the same field. */
function mergeDraft(fresh, saved) {
  const pickKnown = (base, from) => {
    const out = { ...base };
    for (const key of Object.keys(base)) {
      if (from && typeof from[key] === typeof base[key]) out[key] = from[key];
    }
    return out;
  };
  const overrides = {};
  for (const [key, value] of Object.entries(saved.overrides || {})) if (typeof value === 'string') overrides[key] = value;
  return {
    ...fresh,
    values: pickKnown(fresh.values, saved.values),
    subject: pickKnown(fresh.subject, saved.subject),
    holder: pickKnown(fresh.holder, saved.holder),
    confidence: typeof saved.confidence === 'string' ? saved.confidence : fresh.confidence,
    variant: typeof saved.variant === 'string' ? saved.variant : fresh.variant,
    overrides,
    example: '',
  };
}
````

- [ ] **Step 4: Run the test to confirm it passes**

Run: `node --test test/store.test.js`
Expected: `tests 4`, `pass 4`, `fail 0`.

- [ ] **Step 5: Commit**

```bash
git add src/store.js test/store.test.js
git commit -m "Add draft storage" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 11: Screen renderers

**Files:**
- Create: `src/view.js`
- Test: `test/view.test.js`

**Interfaces:**
- Consumes: tables (Task 3), `OUTPUT_GROUPS`, `resolveType`, `usesDetails`, `ruleRef`, `exampleLabel` (Task 4), `plain` (Task 1).
- Produces (all return HTML strings): `esc(text)`, `display(text)`, `renderSidebar(records, currentId, filter)`, `renderExamplePicker(type)`, `renderForm(type, draft)`, `renderOutput(type, draft, outputs, editing?)`, `renderStatus(problems, exampleNote?, changed?)`, `renderHover(ref, info, pins)`; plus `copyAllText(outputs) → string`.
- DOM contract used by Task 12: form controls carry `data-path` (`values.x`, `subject.x`, `holder.x`, `confidence`, `variant`) and optional `data-rerender`; the held-by buttons carry `data-set`/`data-value`; output cells carry `data-field`; buttons carry `data-copy` / `data-reset`; rule references carry `data-ref` (and `data-field` in the output table); sidebar buttons carry `data-type`; the edit box is `textarea[data-edit]`.

- [ ] **Step 1: Write the failing test** `test/view.test.js`

````js
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { esc, display, renderSidebar, renderForm, renderOutput, renderStatus, renderHover, renderExamplePicker, copyAllText } from '../src/view.js';
import { RECORDS, recordById } from '../src/records/index.js';
import { newDraft, draftFromExample, buildOutputs } from '../src/engine.js';

const klokk = recordById('no-klokkerbok');
const example = () => draftFromExample(klokk, klokk.examples[0]);

test('escaping and gap highlighting', () => {
  assert.equal(esc('<a href="x">&\'</a>'), '&lt;a href=&quot;x&quot;&gt;&amp;&#39;&lt;/a&gt;');
  assert.equal(display('p. ⟦Page⟧ <b>'), 'p. <span class="gap">Page</span> &lt;b&gt;');
});

test('sidebar groups record types, marks the current one, and filters', () => {
  const html = renderSidebar(RECORDS, 'no-klokkerbok');
  assert.match(html, /Norwegian <span>9<\/span>/);
  assert.match(html, /class="i on" data-type="no-klokkerbok"/);
  const filtered = renderSidebar(RECORDS, 'no-klokkerbok', 'census');
  assert.match(filtered, /Federal census/);
  assert.doesNotMatch(filtered, /Klokkerbok/);
  assert.match(renderSidebar(RECORDS, 'x', 'zzzz'), /No record type matches/);
});

test('form shows every source field and hides entry details when the FRN has none', () => {
  const html = renderForm(klokk, newDraft(klokk));
  for (const [key] of klokk.source) assert.match(html, new RegExp(`data-path="values\\.${key}"`));
  assert.match(html, /data-path="values\.details"/);
  const card = recordById('us-draft-card');
  assert.doesNotMatch(renderForm(card, newDraft(card)), /data-path="values\.details"/);
});

test('form shows the non-head checkbox only for a household', () => {
  const hfl = recordById('se-husforhor');
  const d = newDraft(hfl);
  assert.match(renderForm(hfl, d), /data-path="subject\.nonHead"/);
  d.subject.noun = 'record';
  assert.doesNotMatch(renderForm(hfl, d), /data-path="subject\.nonHead"/);
});

test('output marks gaps, edited values, and offers copy and reset', () => {
  const d = newDraft(klokk);
  assert.match(renderOutput(klokk, d, buildOutputs(klokk, d)), /<span class="gap">Parish<\/span>/);
  const e = example();
  e.overrides.title = 'My title';
  const html = renderOutput(klokk, e, buildOutputs(klokk, e));
  assert.match(html, /class="v edited" data-field="title"/);
  assert.match(html, /data-reset="title"/);
  assert.match(html, /data-copy="frn"/);
  assert.match(renderOutput(klokk, e, buildOutputs(klokk, e), 'frn'), /<textarea data-edit="frn"/);
});

test('status lists problems or says all clear', () => {
  assert.match(renderStatus([], 'Matches guide example B.1 Example 1', '2026-09-23'), /No rule problems.*Matches guide example.*Guide last changed 2026-09-23/);
  const html = renderStatus([{ rule: 'A4', message: 'Raw image ID.' }, { rule: 'Fill', message: 'Gaps.' }]);
  assert.match(html, /2 to check/);
  assert.match(html, /data-ref="A4"/);
  assert.match(html, /<span class="ref-plain">Fill<\/span>/);
});

test('hover card shows the rule text and pinned rows', () => {
  const html = renderHover('A8', { title: 'A8 · Title', text: 'Locality-led.' }, [['B.1 §4', 'Parish | Norway, [Fylke]']]);
  assert.match(html, /A8 · Title/);
  assert.match(html, /Locality-led\./);
  assert.match(html, /B\.1 §4 · Parish \| Norway, \[Fylke\]/);
});

test('example picker lists claims or says there are none', () => {
  assert.match(renderExamplePicker(klokk), /<option value="0">B\.1 Example 1<\/option>/);
  assert.match(renderExamplePicker(recordById('no-tingbok')), /No guide example/);
});

test('copy all uses the Gramps block layout', () => {
  const text = copyAllText(buildOutputs(klokk, example()));
  assert.match(text, /^SOURCE\nTitle: Norway, Akershus, Eidsvoll/);
  assert.match(text, /\n\nCITATION\nPage: p\. 57 \(image 62\)/);
  assert.match(text, /\nDate: \(blank\)\nConfidence: High\n/);
  assert.match(text, /\n\nSHORT REFERENCE NOTE:\nEidsvoll klokkerbok I 2/);
});
````

- [ ] **Step 2: Run it to confirm it fails**

Run: `node --test test/view.test.js`
Expected: FAIL with `ERR_MODULE_NOT_FOUND` for `src/view.js`.

- [ ] **Step 3: Implement** `src/view.js`

````js
// Renders the screen's parts as HTML strings. Pure: app.js puts them in the page.
import { CHAPTERS, CHAPTER_CODE, LEVELS, MEDIA, PLATFORMS, ARCHIVES, SUGGESTIONS } from './tables.js';
import { OUTPUT_GROUPS, resolveType, usesDetails, ruleRef, exampleLabel } from './engine.js';
import { plain } from './template.js';

const EDITABLE = new Set(['title', 'author', 'abbrev', 'pubinfo', 'repository', 'callNumber', 'page', 'frn', 'srn',
  'plTitle', 'plDoctype', 'plDateMeaning', 'plCorrespondent', 'plSourceUrl']);
const HELD_BY = { archive: 'Archive', private: 'Private', publication: 'Publication' };
const MONO_KEYS = new Set(['call', 'url', 'turl']);

export function esc(text) {
  return String(text ?? '').replace(/[&<>"']/g, ch => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[ch]);
}

/** Escaped text with gap markers turned into highlighted spans. */
export function display(text) {
  return esc(text).replace(/⟦([^⟧]*)⟧/g, '<span class="gap">$1</span>');
}

const idFor = path => `f-${path.replace(/\./g, '-')}`;
const refTag = ref => (/^(A\d+|C\d+|B\.\d §\d+)$/.test(ref)
  ? `<span class="ref" data-ref="${esc(ref)}" tabindex="0">${esc(ref)}</span>`
  : `<span class="ref-plain">${esc(ref)}</span>`);

function row(label, control, path = '') {
  return `<div class="f"><label${path ? ` for="${idFor(path)}"` : ''}>${label}</label>${control}</div>`;
}

function input(path, value, { placeholder = '', list = '', mono = false, rerender = false } = {}) {
  return `<input id="${idFor(path)}" data-path="${path}" value="${esc(value)}" placeholder="${esc(placeholder)}"`
    + `${list ? ` list="${list}"` : ''}${mono ? ' class="m"' : ''}${rerender ? ' data-rerender' : ''} autocomplete="off" spellcheck="false">`;
}

function area(path, value, placeholder = '') {
  return `<textarea id="${idFor(path)}" data-path="${path}" rows="3" placeholder="${esc(placeholder)}">${esc(value)}</textarea>`;
}

function select(path, value, options, { rerender = false } = {}) {
  const opts = options.map(o => (Array.isArray(o) ? o : [o, o]))
    .map(([v, label]) => `<option value="${esc(v)}"${v === value ? ' selected' : ''}>${esc(label)}</option>`).join('');
  return `<select id="${idFor(path)}" data-path="${path}"${rerender ? ' data-rerender' : ''}>${opts}</select>`;
}

function check(path, checked, label) {
  return `<label class="check"><input type="checkbox" id="${idFor(path)}" data-path="${path}" data-rerender${checked ? ' checked' : ''}> ${esc(label)}</label>`;
}

const datalist = (id, options) => `<datalist id="${id}">${options.map(o => `<option value="${esc(o)}"></option>`).join('')}</datalist>`;
const field = ([key, label, placeholder], values) => row(esc(label), input(`values.${key}`, values[key] ?? '', { placeholder, mono: MONO_KEYS.has(key) }), `values.${key}`);
const group = (name, refs, body) => `<fieldset class="fs"><div class="lg"><span>${esc(name)}</span><span class="refs">${refs.map(refTag).join(' · ')}</span></div>${body}</fieldset>`;

export function renderSidebar(records, currentId, filter = '') {
  const q = filter.trim().toLowerCase();
  const html = [];
  for (const [code, label] of Object.entries(CHAPTERS)) {
    const list = records.filter(r => r.chapter === code && (!q || `${r.name} ${r.group}`.toLowerCase().includes(q)));
    if (!list.length) continue;
    html.push(`<div class="g">${esc(label)} <span>${list.length}</span></div>`);
    for (const r of list) {
      const on = r.id === currentId;
      html.push(`<button type="button" class="i${on ? ' on' : ''}" data-type="${esc(r.id)}" title="${esc(r.hint || r.group)}"${on ? ' aria-current="true"' : ''}>${esc(r.name)}</button>`);
    }
  }
  return html.join('') || '<p class="none">No record type matches.</p>';
}

export function renderExamplePicker(type) {
  if (!type.examples.length) return '<option value="">No guide example</option>';
  return '<option value="">Load guide example…</option>'
    + type.examples.map((claim, i) => `<option value="${i}">${esc(exampleLabel(claim))}</option>`).join('');
}

export function renderForm(type, draft) {
  const code = CHAPTER_CODE[type.chapter];
  const t = resolveType(type, draft);
  const v = draft.values, h = draft.holder, s = draft.subject;

  const source = group('Source', [`${code} §4`], type.source.map(f => field(f, v)).join(''));

  let holder = row('Held by', `<div class="seg" role="group" aria-label="Held by">${Object.entries(HELD_BY)
    .map(([mode, label]) => `<button type="button" class="${h.heldBy === mode ? 'on' : ''}" data-set="holder.heldBy" data-value="${mode}" aria-pressed="${h.heldBy === mode}">${label}</button>`).join('')}</div>`);
  if (h.heldBy === 'archive') holder += row('Archive', input('holder.archive', h.archive, { list: `archives-${type.chapter}` }), 'holder.archive');
  if (h.heldBy === 'private') {
    holder += row('Custodian', input('holder.custodian', h.custodian), 'holder.custodian')
      + row('Place', input('holder.custodianPlace', h.custodianPlace, { placeholder: 'Locality only (A12)' }), 'holder.custodianPlace')
      + row('Wording', select('holder.custodyWording', h.custodyWording, ['private collection', 'personal collection']), 'holder.custodyWording');
  }
  holder += row('Platform', input('holder.platform', h.platform, { list: 'platforms', placeholder: 'None', rerender: true }), 'holder.platform');
  const platform = h.platform.trim();
  if (platform && !PLATFORMS[platform]) holder += row('Homepage', input('holder.platformHome', h.platformHome, { placeholder: 'https://…', mono: true }), 'holder.platformHome');
  if (h.heldBy === 'publication' && ['Riksarkivet', 'Lantmäteriet'].includes(platform)) {
    holder += `<div class="f">${check('holder.keepPlatform', h.keepPlatform, `Keep ${platform} in Repository`)}</div>`;
  }
  if (type.pubinfo === undefined) holder += row('Medium', select('holder.medium', h.medium, MEDIA), 'holder.medium');
  holder += datalist(`archives-${type.chapter}`, ARCHIVES[type.chapter]) + datalist('platforms', Object.keys(PLATFORMS));

  const sug = SUGGESTIONS[type.chapter];
  let citation = '';
  if (type.pageVariants) citation += row('Form', select('variant', draft.variant, type.pageVariants.map(x => [x.key, x.label]), { rerender: true }), 'variant');
  citation += (t.citation || []).map(f => field(f, v)).join('');
  citation += row(esc(t.subjectLabel || 'Subject'), input('subject.name', s.name, { placeholder: 'No place names (A4)' }), 'subject.name');
  citation += row('Record noun', input('subject.noun', s.noun, { list: `nouns-${type.id}`, rerender: true }), 'subject.noun')
    + datalist(`nouns-${type.id}`, (t.nouns || []).filter(Boolean));
  if (s.noun.trim() === 'household') {
    citation += `<div class="f">${check('subject.nonHead', s.nonHead, 'Not the head of household')}</div>`;
    if (s.nonHead) citation += row("Head's surname", input('subject.head', s.head), 'subject.head');
  }
  citation += row('<span class="num">1</span>Which entry', input('subject.which', s.which, { list: `sug-which-${type.chapter}`, placeholder: 'b. YYYY, at PLACE…' }), 'subject.which')
    + row('<span class="num">2</span>Source says', input('subject.says', s.says, { list: `sug-says-${type.chapter}`, placeholder: sug.says.slice(0, 2).join(', ') + '…' }), 'subject.says')
    + row('<span class="num">3</span>Evidence', input('subject.evidence', s.evidence, { list: `sug-evidence-${type.chapter}`, placeholder: 'stated age N, named at…' }), 'subject.evidence')
    + `<div class="f">${check('subject.afterNoun', s.afterNoun, 'Parentheses after noun')}</div>`
    + datalist(`sug-which-${type.chapter}`, sug.which) + datalist(`sug-says-${type.chapter}`, sug.says) + datalist(`sug-evidence-${type.chapter}`, sug.evidence);
  citation += row('Confidence', select('confidence', draft.confidence, [['', 'Choose…'], ...LEVELS]), 'confidence');

  let note = row('Image URL', input('values.url', v.url, { mono: true }), 'values.url')
    + row('Accessed', input('values.accessed', v.accessed, { placeholder: '21 April 2026' }), 'values.accessed')
    + row(esc(type.eventYearLabel || 'Event year'), input('values.eventYear', v.eventYear, { placeholder: 'For the Paperless title' }), 'values.eventYear')
    + (type.note || []).map(f => field(f, v)).join('');
  if (usesDetails(type)) note += row(esc(type.detailsLabel || 'Entry details'), area('values.details', v.details), 'values.details');
  note += row('Comment after FRN', area('values.comment', v.comment, 'Sentences appended after the FRN'), 'values.comment');

  return source
    + group('Holder & access', ['A9', 'A10'], holder)
    + group('Citation', [`${code} §7`, 'A7'], citation)
    + group('Reference note', ['A5'], note);
}

export function renderOutput(type, draft, outputs, editing = '') {
  const rows = ['<table class="t"><thead><tr><th>Field</th><th>Value</th><th>Rule</th><th></th></tr></thead>'];
  for (const g of OUTPUT_GROUPS) {
    rows.push(`<tbody><tr class="sec"><td colspan="4">${esc(g.name)}</td></tr>`);
    for (const [key, label, rule] of g.fields) {
      const ref = ruleRef(type, rule);
      const refCell = `<td class="r"><span class="ref" data-ref="${esc(ref)}" data-field="${key}" tabindex="0">${esc(ref)}</span></td>`;
      if (key === 'date') {
        rows.push(`<tr><td class="k">${label}</td><td class="v"><span class="blank">blank, always</span></td>${refCell}<td class="c"></td></tr>`);
        continue;
      }
      const value = outputs[key] ?? '';
      const text = plain(value);
      const edited = Object.hasOwn(draft.overrides, key);
      const editable = EDITABLE.has(key);
      let cell;
      if (editing === key) cell = `<textarea data-edit="${key}" rows="${key === 'frn' ? 6 : 2}" aria-label="Edit ${esc(label)}">${esc(text)}</textarea>`;
      else cell = text ? display(value) : '<span class="blank">(blank)</span>';
      const actions = (text ? `<button type="button" class="icon" data-copy="${key}" title="Copy ${esc(label)}" aria-label="Copy ${esc(label)}">⧉</button>` : '')
        + (edited ? `<button type="button" class="icon" data-reset="${key}" title="Reset to the built value" aria-label="Reset ${esc(label)}">↺</button>` : '');
      rows.push(`<tr><td class="k">${label}</td><td class="v${edited ? ' edited' : ''}" data-field="${key}"`
        + `${editable && editing !== key ? ' tabindex="0" title="Click to edit"' : ''}>${cell}</td>${refCell}<td class="c">${actions}</td></tr>`);
    }
    rows.push('</tbody>');
  }
  rows.push('</table>');
  return rows.join('');
}

export function renderStatus(problems, exampleNote = '', changed = '') {
  const summary = problems.length
    ? `<span class="warn">▲ ${problems.length} to check</span>`
    : '<span class="ok">● No rule problems</span>';
  const parts = [summary];
  if (exampleNote) parts.push(`<span>${esc(exampleNote)}</span>`);
  if (changed) parts.push(`<span>Guide last changed ${esc(changed)}</span>`);
  const list = problems.length
    ? `<ul class="problems">${problems.map(p => `<li>${refTag(p.rule)} ${esc(p.message)}</li>`).join('')}</ul>`
    : '';
  return `<div class="sline">${parts.join('')}</div>${list}`;
}

export function renderHover(ref, info, pins) {
  return `<div class="h">${esc(info?.title || ref)}</div>`
    + (info?.text ? `<p>${esc(info.text)}</p>` : '')
    + pins.map(([section, text]) => `<div class="tpl">${esc(section)} · ${esc(text)}</div>`).join('')
    + '<div class="src">From the style guide</div>';
}

export function copyAllText(o) {
  const p = x => plain(x ?? '');
  return [
    'SOURCE', `Title: ${p(o.title)}`, `Author: ${p(o.author)}`, `Abbrev: ${p(o.abbrev)}`, `Pubinfo: ${p(o.pubinfo)}`,
    `Repository: ${p(o.repository)}`, `Call number: ${p(o.callNumber)}`, '',
    'CITATION', `Page: ${p(o.page)}`, 'Date: (blank)', `Confidence: ${o.confidence || ''}`, '',
    'FIRST REFERENCE NOTE:', p(o.frn), '', 'SHORT REFERENCE NOTE:', p(o.srn),
  ].join('\n');
}
````

- [ ] **Step 4: Run the test to confirm it passes**

Run: `node --test test/view.test.js`
Expected: `tests 9`, `pass 9`, `fail 0`.

- [ ] **Step 5: Commit**

```bash
git add src/view.js test/view.test.js
git commit -m "Add screen renderers" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 12: Page, app wiring, and build

**Files:**
- Create: `src/page.html`
- Create: `src/app.js`
- Create: `tools/build.js`
- Test: `test/build.test.js`
- Create (generated): `citation-generator.html`

**Interfaces:**
- Consumes: everything above. `tools/build.js` reads `src/page.html` and replaces `<!--GUIDE-->` with `<script>window.GUIDE_DATA = …</script>` and `<!--APP-->` with the bundled code.
- Produces (from `tools/build.js`): `bundle(entry?) → string` (supports only `import { a, b as c } from './x.js';` and `export function|const|let|class`), `guideData(guide?) → { changed, refs: { [ref]: { title, text } }, examples: { [id]: { expected, confidence, citations } } }`, `build(outFile?) → { outFile, bytes }`. Run directly: `node tools/build.js [outFile]`.
- `src/app.js` behaviour: sidebar selection; per-type drafts saved in browser storage; *Load guide example*; *Next citation on this Source* (keeps Source inputs and Source overrides); *Clear* (second click within 3 s); *Copy all*; per-field copy, click-to-edit overrides, reset; hover cards; deep link `#type=<id>&example=<n>`; smoke mode `#smoke` renders every type and writes `<pre id="smoke-result">{"total":…,"failures":[…]}</pre>`; sets `document.body.dataset.ready = 'ok'` after start-up.

- [ ] **Step 1: Write the failing test** `test/build.test.js`

````js
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { existsSync, readFileSync, mkdtempSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { execFileSync } from 'node:child_process';
import { pathToFileURL } from 'node:url';
import vm from 'node:vm';
import { bundle, build, guideData } from '../tools/build.js';
import { RECORDS } from '../src/records/index.js';

const CHROME = [process.env.CHROME_PATH, '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome', '/usr/bin/google-chrome', '/usr/bin/chromium']
  .find(p => p && existsSync(p));
const out = join(mkdtempSync(join(tmpdir(), 'citation-build-')), 'citation-generator.html');

test('the bundle has no module syntax left and compiles', () => {
  const code = bundle();
  assert.doesNotMatch(code, /^\s*(import|export)\s/m);
  assert.doesNotThrow(() => new vm.Script(code));
  assert.match(code, /__modules\["engine\.js"\]/);
});

test('guide data carries section text, examples, and the Change log date', () => {
  const data = guideData();
  assert.match(data.changed, /^\d{4}-\d{2}-\d{2}$/);
  assert.match(data.refs.A8.title, /^A8 · Title$/);
  assert.ok(data.refs['B.1 §4'].text.length > 0);
  assert.ok(data.examples['B.1 Example 1'].expected.title);
});

test('build writes one self-contained file', () => {
  const { bytes } = build(out);
  const html = readFileSync(out, 'utf8');
  assert.ok(bytes > 50_000);
  assert.match(html, /window\.GUIDE_DATA = \{/);
  assert.doesNotMatch(html, /<script[^>]+src=/i);
  assert.doesNotMatch(html, /<link[^>]+href=/i);
  assert.doesNotMatch(html, /<!--(GUIDE|APP)-->/);
});

test('every record type renders in a real browser', { skip: CHROME ? false : 'Chrome not found' }, () => {
  build(out);
  const dom = execFileSync(CHROME, ['--headless=new', '--disable-gpu', '--virtual-time-budget=8000', '--dump-dom', `${pathToFileURL(out).href}#smoke`],
    { encoding: 'utf8', stdio: ['ignore', 'pipe', 'ignore'], timeout: 60_000 });
  assert.match(dom, /data-ready="ok"/, 'the page did not finish starting');
  const json = dom.match(/<pre id="smoke-result"[^>]*>([^<]*)<\/pre>/);
  assert.ok(json, 'no smoke result in the page');
  const result = JSON.parse(json[1].replace(/&quot;/g, '"').replace(/&amp;/g, '&'));
  assert.equal(result.total, RECORDS.length);
  assert.deepEqual(result.failures, []);
});
````

- [ ] **Step 2: Run it to confirm it fails**

Run: `node --test test/build.test.js`
Expected: FAIL with `ERR_MODULE_NOT_FOUND` for `tools/build.js`.

- [ ] **Step 3: Create the page shell** `src/page.html`

````html
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Citation Generator</title>
<style>
:root {
  --bg: #E6E6E9; --pane: #FFFFFF; --side: #F1F1F3; --bar1: #F7F7F8; --bar2: #EAEAED;
  --ink: #1C1C1E; --muted: #6E6E73; --faint: #9A9AA0; --line: #D0D0D6; --line2: #EDEDF0;
  --field: #FFFFFF; --field-line: #C7C7CC; --acc: #2D6BDF; --acc-ink: #FFFFFF; --sel: #DBE7FB;
  --gap-bg: #FFF1D6; --gap-ink: #8A5300; --warn: #B25E09; --ok: #248A3D; --edited: #FFF7E6;
  --shadow: 0 10px 28px rgba(0, 0, 0, .18);
  --sans: -apple-system, BlinkMacSystemFont, "SF Pro Text", system-ui, "Segoe UI", sans-serif;
  --mono: ui-monospace, "SF Mono", Menlo, Consolas, monospace;
  color-scheme: light;
}
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {
    --bg: #1B1B1D; --pane: #242427; --side: #1F1F22; --bar1: #2B2B2F; --bar2: #242427;
    --ink: #ECECEF; --muted: #A1A1A8; --faint: #77777E; --line: #3A3A3F; --line2: #2E2E33;
    --field: #1B1B1E; --field-line: #4A4A50; --acc: #5B8DEF; --acc-ink: #0B0B0C; --sel: #26344F;
    --gap-bg: #3D2E12; --gap-ink: #F2C572; --warn: #F0A54A; --ok: #5CC878; --edited: #33291A;
    --shadow: 0 10px 28px rgba(0, 0, 0, .5);
    color-scheme: dark;
  }
}
:root[data-theme="dark"] {
  --bg: #1B1B1D; --pane: #242427; --side: #1F1F22; --bar1: #2B2B2F; --bar2: #242427;
  --ink: #ECECEF; --muted: #A1A1A8; --faint: #77777E; --line: #3A3A3F; --line2: #2E2E33;
  --field: #1B1B1E; --field-line: #4A4A50; --acc: #5B8DEF; --acc-ink: #0B0B0C; --sel: #26344F;
  --gap-bg: #3D2E12; --gap-ink: #F2C572; --warn: #F0A54A; --ok: #5CC878; --edited: #33291A;
  --shadow: 0 10px 28px rgba(0, 0, 0, .5);
  color-scheme: dark;
}
* { box-sizing: border-box; }
html, body { margin: 0; height: 100%; }
body { background: var(--bg); color: var(--ink); font: 12.5px/1.4 var(--sans); }
button, select, input, textarea { font: inherit; color: inherit; }
[hidden] { display: none !important; }
:focus-visible { outline: 2px solid var(--acc); outline-offset: 1px; }

.app { display: grid; grid-template-rows: auto minmax(0, 1fr) auto; height: 100vh; }
.bar { display: flex; align-items: center; flex-wrap: wrap; gap: 8px 10px; min-height: 40px; padding: 5px 12px;
  background: linear-gradient(var(--bar1), var(--bar2)); border-bottom: 1px solid var(--line); }
.bar .app-name { font-weight: 600; }
.bar .crumb { color: var(--muted); }
.bar .crumb b { color: var(--ink); font-weight: 600; }
.bar .sp { flex: 1; }
.btn { border: 1px solid var(--field-line); background: var(--pane); border-radius: 5px; padding: 3px 10px; cursor: pointer; }
.btn:hover { border-color: var(--acc); }
.btn.pri { background: var(--acc); border-color: var(--acc); color: var(--acc-ink); }
select.btn { padding: 3px 6px; }

.main { display: grid; grid-template-columns: 184px minmax(290px, 340px) minmax(0, 1fr); min-height: 0; }
.side { background: var(--side); border-right: 1px solid var(--line); overflow: auto; padding: 8px 0 16px; }
.side .filter { display: block; margin: 0 8px 6px; width: calc(100% - 16px); border: 1px solid var(--field-line);
  border-radius: 5px; background: var(--field); padding: 3px 7px; }
.side .g { display: flex; justify-content: space-between; font-size: 10.5px; font-weight: 600; color: var(--muted);
  text-transform: uppercase; letter-spacing: .04em; padding: 10px 12px 3px; }
.side .g span { font-weight: 400; }
.side .i { display: block; width: calc(100% - 12px); margin: 0 6px; text-align: left; border: 0; background: none;
  padding: 3px 8px 3px 12px; border-radius: 4px; cursor: pointer; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.side .i:hover { background: var(--sel); }
.side .i.on { background: var(--acc); color: var(--acc-ink); }
.side .none { color: var(--muted); padding: 0 12px; }

.form { overflow: auto; padding: 10px; border-right: 1px solid var(--line); }
.fs { border: 1px solid var(--line); border-radius: 6px; background: var(--pane); padding: 5px 8px 8px; margin: 0 0 10px; min-width: 0; }
.fs .lg { display: flex; justify-content: space-between; gap: 8px; font-weight: 600; font-size: 11px; margin: 2px 0 5px; }
.fs .lg .refs { font-weight: 400; }
.f { display: grid; grid-template-columns: 96px minmax(0, 1fr); align-items: center; gap: 6px; margin: 4px 0; }
.f > label { color: var(--muted); text-align: right; font-size: 11.5px; }
.f input:not([type=checkbox]), .f select, .f textarea { width: 100%; min-width: 0; border: 1px solid var(--field-line);
  border-radius: 4px; background: var(--field); padding: 2px 6px; min-height: 22px; }
.f textarea { resize: vertical; line-height: 1.35; }
.f .check { grid-column: 2; display: flex; gap: 6px; align-items: center; font-size: 11.5px; color: var(--muted); text-align: left; }
.m { font-family: var(--mono); font-size: 11.5px; }
.seg { display: flex; border: 1px solid var(--field-line); border-radius: 5px; overflow: hidden; }
.seg button { flex: 1; border: 0; border-left: 1px solid var(--field-line); background: var(--field); padding: 2px 0; cursor: pointer; }
.seg button:first-child { border-left: 0; }
.seg button.on { background: var(--acc); color: var(--acc-ink); }
.num { display: inline-grid; place-items: center; width: 14px; height: 14px; border-radius: 50%; background: var(--line2);
  color: var(--muted); font-size: 9.5px; font-weight: 600; margin-right: 4px; }

.out { overflow: auto; padding: 10px 12px 16px; }
.t { width: 100%; border-collapse: collapse; background: var(--pane); border: 1px solid var(--line); }
.t th { text-align: left; font-weight: 600; font-size: 10.5px; color: var(--muted); background: var(--side); padding: 4px 8px;
  border-bottom: 1px solid var(--line); text-transform: uppercase; letter-spacing: .03em; }
.t td { border-top: 1px solid var(--line2); padding: 5px 8px; vertical-align: top; }
.t tr.sec td { background: var(--side); font-weight: 600; font-size: 11px; padding: 3px 8px; }
.t td.k { color: var(--muted); width: 104px; white-space: nowrap; }
.t td.v { font-family: var(--mono); font-size: 11.5px; overflow-wrap: anywhere; white-space: pre-wrap; }
.t td.v[tabindex] { cursor: text; }
.t td.v[tabindex]:hover { background: var(--line2); }
.t td.v.edited { background: var(--edited); }
.t td.v textarea { width: 100%; font: inherit; border: 1px solid var(--acc); border-radius: 4px; padding: 3px 5px; background: var(--field); resize: vertical; }
.t td.r { width: 64px; white-space: nowrap; }
.t td.c { width: 50px; text-align: right; white-space: nowrap; }
.ref { color: var(--acc); border-bottom: 1px dotted currentColor; cursor: help; font-size: 10.5px; }
.ref-plain { color: var(--muted); font-size: 10.5px; }
.gap { background: var(--gap-bg); color: var(--gap-ink); border-radius: 3px; padding: 0 3px; }
.blank { font-family: var(--sans); font-style: italic; color: var(--faint); }
.icon { border: 0; background: none; color: var(--faint); cursor: pointer; padding: 0 3px; font-size: 13px; }
.icon:hover { color: var(--acc); }

.status { border-top: 1px solid var(--line); background: var(--side); padding: 4px 12px; color: var(--muted); font-size: 11px; max-height: 30vh; overflow: auto; }
.status .sline { display: flex; gap: 18px; flex-wrap: wrap; }
.status .ok { color: var(--ok); }
.status .warn { color: var(--warn); font-weight: 600; }
.status .problems { margin: 4px 0 2px; padding: 0 0 0 16px; }

.pop { position: fixed; z-index: 10; width: min(380px, calc(100vw - 24px)); background: var(--pane); border: 1px solid var(--line);
  border-radius: 8px; box-shadow: var(--shadow); padding: 9px 11px 10px; font-size: 11.5px; line-height: 1.45; pointer-events: none; }
.pop .h { font-weight: 600; margin-bottom: 3px; }
.pop p { margin: 0 0 4px; }
.pop .tpl { font-family: var(--mono); font-size: 10.5px; background: var(--side); border-radius: 4px; padding: 4px 6px; margin: 5px 0 0; overflow-wrap: anywhere; }
.pop .src { color: var(--faint); font-size: 10px; margin-top: 6px; }
.toast { position: fixed; left: 50%; bottom: 44px; transform: translateX(-50%); background: var(--ink); color: var(--pane);
  padding: 6px 12px; border-radius: 6px; font-size: 12px; z-index: 20; }

@media (max-width: 900px) {
  .app { height: auto; min-height: 100vh; }
  .main { grid-template-columns: minmax(0, 1fr); }
  .side { max-height: 34vh; border-right: 0; border-bottom: 1px solid var(--line); }
  .form { border-right: 0; }
}
</style>
</head>
<body>
<div class="app">
  <header class="bar">
    <span class="app-name">Citations</span>
    <span class="crumb" id="crumb"></span>
    <span class="sp"></span>
    <select id="example" class="btn" aria-label="Load guide example"></select>
    <button type="button" class="btn" data-act="next">Next citation on this Source</button>
    <button type="button" class="btn" data-act="clear">Clear</button>
    <button type="button" class="btn pri" data-act="copyall">Copy all</button>
  </header>
  <div class="main">
    <nav class="side" aria-label="Record types">
      <input class="filter" id="filter" type="search" placeholder="Filter record types…" aria-label="Filter record types">
      <div id="sideList"></div>
    </nav>
    <form class="form" id="form" autocomplete="off" onsubmit="return false" aria-label="Record inputs"></form>
    <section class="out" id="out" aria-label="Gramps fields"></section>
  </div>
  <footer class="status" id="status" aria-live="polite"></footer>
</div>
<div class="pop" id="pop" role="tooltip" hidden></div>
<div class="toast" id="toast" role="status" hidden></div>
<!--GUIDE-->
<!--APP-->
</body>
</html>
````

- [ ] **Step 4: Implement the app wiring** `src/app.js`

````js
// Wires the screen: state, events, storage, clipboard, hover cards, and deep links.
import { RECORDS, recordById } from './records/index.js';
import { newDraft, draftFromExample, buildOutputs, exampleLabel } from './engine.js';
import { runChecks } from './checks.js';
import { expectedFor, diffOutputs } from './compare.js';
import { plain } from './template.js';
import { CHAPTERS } from './tables.js';
import { renderSidebar, renderForm, renderOutput, renderStatus, renderHover, renderExamplePicker, copyAllText, esc } from './view.js';
import { loadState, saveState } from './store.js';

const GUIDE = globalThis.GUIDE_DATA || { changed: '', refs: {}, examples: {} };
const SOURCE_FIELDS = ['title', 'author', 'abbrev', 'pubinfo', 'repository', 'callNumber'];
const FIELD_NAMES = { title: 'Title', abbrev: 'Abbrev', author: 'Author', pubinfo: 'Pubinfo', repository: 'Repository', callNumber: 'Call number', page: 'Page', frn: 'FRN', srn: 'SRN' };
const storage = (() => { try { return globalThis.localStorage; } catch { return null; } })();
const $ = selector => document.querySelector(selector);

let state = loadState(storage, recordById) || { current: RECORDS[0].id, drafts: {}, filter: '' };
let editing = '';

const type = () => recordById(state.current);
const draft = () => (state.drafts[state.current] ||= newDraft(type()));
const outputs = () => buildOutputs(type(), draft());
const save = () => saveState(storage, state);

function exampleNote(outs) {
  const d = draft();
  if (!d.example) return '';
  const claim = type().examples.find(c => exampleLabel(c) === d.example);
  const example = claim && GUIDE.examples[claim.guide];
  if (!example) return `Loaded guide example ${d.example}`;
  const diffs = diffOutputs(expectedFor(example, claim).fields, outs);
  return diffs.length
    ? `Differs from guide example ${d.example}: ${diffs.map(x => FIELD_NAMES[x.field]).join(', ')}`
    : `Matches guide example ${d.example}`;
}

function renderSide() {
  $('#sideList').innerHTML = renderSidebar(RECORDS, state.current, state.filter);
}

function renderFormArea() {
  const active = document.activeElement;
  const focusId = active && $('#form').contains(active) ? active.id : '';
  const caret = focusId && 'selectionStart' in active ? active.selectionStart : null;
  $('#form').innerHTML = renderForm(type(), draft());
  const again = focusId && document.getElementById(focusId);
  if (again) {
    again.focus();
    if (caret !== null && 'setSelectionRange' in again) { try { again.setSelectionRange(caret, caret); } catch { /* not a text input */ } }
  }
}

function renderResults() {
  const outs = outputs();
  $('#out').innerHTML = renderOutput(type(), draft(), outs, editing);
  $('#status').innerHTML = renderStatus(runChecks(type(), draft(), outs), exampleNote(outs), GUIDE.changed);
  if (editing) {
    const box = $(`[data-edit="${editing}"]`);
    if (box) { box.focus(); box.setSelectionRange(box.value.length, box.value.length); }
  }
}

function renderAll() {
  const t = type();
  $('#crumb').innerHTML = `${esc(CHAPTERS[t.chapter])} › <b>${esc(t.name)}</b>`;
  $('#example').innerHTML = renderExamplePicker(t);
  $('#example').disabled = !t.examples.length;
  $('#filter').value = state.filter;
  renderSide();
  renderFormArea();
  renderResults();
  save();
}

function setPath(path, value) {
  const d = draft();
  const [head, key] = path.split('.');
  if (key === undefined) d[head] = value;
  else d[head][key] = value;
  d.example = '';
}

function selectType(id) {
  if (!recordById(id)) return;
  state.current = id;
  editing = '';
  history.replaceState(null, '', `#type=${encodeURIComponent(id)}`);
  renderAll();
}

function loadExample(index) {
  const claim = type().examples[index];
  if (!claim) return;
  state.drafts[state.current] = draftFromExample(type(), claim);
  editing = '';
  renderAll();
}

function nextCitation() {
  const t = type(), d = draft(), fresh = newDraft(t);
  const keep = new Set(t.source.map(([key]) => key));
  for (const key of Object.keys(d.values)) if (!keep.has(key)) d.values[key] = fresh.values[key];
  d.subject = fresh.subject;
  d.confidence = fresh.confidence;
  d.overrides = Object.fromEntries(Object.entries(d.overrides).filter(([key]) => SOURCE_FIELDS.includes(key)));
  d.example = '';
  editing = '';
  renderAll();
  toast('Source kept. Build the next citation.');
}

let clearArmed = null;
/** Clearing needs a second click within three seconds. */
function clearDraft(button) {
  if (!clearArmed) {
    button.textContent = 'Click again to clear';
    clearArmed = setTimeout(() => { clearArmed = null; button.textContent = 'Clear'; }, 3000);
    return;
  }
  clearTimeout(clearArmed);
  clearArmed = null;
  button.textContent = 'Clear';
  state.drafts[state.current] = newDraft(type());
  editing = '';
  renderAll();
}

async function copy(text) {
  try {
    await navigator.clipboard.writeText(text);
    toast('Copied');
    return;
  } catch { /* fall back below */ }
  const box = document.createElement('textarea');
  box.value = text;
  box.style.cssText = 'position:fixed;opacity:0';
  document.body.append(box);
  box.select();
  let ok = false;
  try { ok = document.execCommand('copy'); } catch { /* blocked */ }
  box.remove();
  toast(ok ? 'Copied' : 'Copying is blocked here: select the text and copy it yourself');
}

let toastTimer;
function toast(message) {
  const el = $('#toast');
  el.textContent = message;
  el.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { el.hidden = true; }, 1800);
}

function pinsFor(ref, field) {
  const pins = type().pins || {};
  if (field) return pins[field] || [];
  return Object.values(pins).flat().filter(([section]) => section === ref);
}

function showHover(el) {
  const pop = $('#pop');
  pop.innerHTML = renderHover(el.dataset.ref, GUIDE.refs[el.dataset.ref], pinsFor(el.dataset.ref, el.dataset.field));
  pop.hidden = false;
  const box = el.getBoundingClientRect(), width = pop.offsetWidth, height = pop.offsetHeight;
  const left = Math.max(12, Math.min(box.right - width, window.innerWidth - width - 12));
  const below = box.bottom + 8 + height < window.innerHeight;
  pop.style.left = `${left}px`;
  pop.style.top = `${below ? box.bottom + 8 : Math.max(12, box.top - height - 8)}px`;
}

function applyHash() {
  const params = new URLSearchParams(location.hash.slice(1));
  const id = params.get('type');
  if (id && recordById(id)) {
    state.current = id;
    const claim = recordById(id).examples[Number(params.get('example')) - 1];
    if (claim) state.drafts[id] = draftFromExample(recordById(id), claim);
    history.replaceState(null, '', `#type=${encodeURIComponent(id)}`);
  }
  return params.has('smoke');
}

/** Renders every record type once (with its first example) and reports any errors. Used by the build test. */
function runSmoke() {
  const saved = JSON.stringify(state);
  const failures = [];
  for (const t of RECORDS) {
    try {
      state.current = t.id;
      state.drafts[t.id] = t.examples[0] ? draftFromExample(t, t.examples[0]) : newDraft(t);
      renderAll();
      if (!$('#out .t') || !$('#form .fs')) throw new Error('screen did not render');
    } catch (err) {
      failures.push({ id: t.id, error: String(err && err.message || err) });
    }
  }
  state = JSON.parse(saved);
  renderAll();
  const out = document.createElement('pre');
  out.id = 'smoke-result';
  out.hidden = true;
  out.textContent = JSON.stringify({ total: RECORDS.length, failures });
  document.body.append(out);
}

document.addEventListener('input', e => {
  const el = e.target;
  if (el.id === 'filter') { state.filter = el.value; renderSide(); save(); return; }
  if (el.dataset.edit) { draft().overrides[el.dataset.edit] = el.value; save(); return; }
  if (el.dataset.path && el.type !== 'checkbox' && el.tagName !== 'SELECT') {
    setPath(el.dataset.path, el.value);
    renderResults();
    save();
  }
});

document.addEventListener('change', e => {
  const el = e.target;
  if (el.id === 'example') { if (el.value !== '') loadExample(Number(el.value)); return; }
  if (!el.dataset.path) return;
  if (el.type === 'checkbox' || el.tagName === 'SELECT') setPath(el.dataset.path, el.type === 'checkbox' ? el.checked : el.value);
  if (el.dataset.rerender !== undefined || el.tagName === 'SELECT' || el.type === 'checkbox') renderFormArea();
  renderResults();
  save();
});

document.addEventListener('click', e => {
  const el = e.target.closest('button, td.v[tabindex]');
  if (!el) return;
  if (el.dataset.type) { selectType(el.dataset.type); return; }
  if (el.dataset.set) { setPath(el.dataset.set, el.dataset.value); renderFormArea(); renderResults(); save(); return; }
  if (el.dataset.copy) { copy(plain(outputs()[el.dataset.copy])); return; }
  if (el.dataset.reset) { delete draft().overrides[el.dataset.reset]; editing = ''; renderResults(); save(); return; }
  if (el.dataset.field) { editing = el.dataset.field; renderResults(); return; }
  const act = el.dataset.act;
  if (act === 'next') nextCitation();
  else if (act === 'clear') clearDraft(el);
  else if (act === 'copyall') copy(copyAllText(outputs()));
});

document.addEventListener('keydown', e => {
  const el = e.target;
  if (e.key === 'Enter' && el.matches?.('td.v[tabindex]')) { e.preventDefault(); editing = el.dataset.field; renderResults(); }
  if (e.key === 'Escape' && el.dataset?.edit) el.blur();
});

document.addEventListener('focusout', e => {
  if (e.target.dataset?.edit && editing) {
    const field = editing;
    editing = '';
    if (!e.target.value.trim()) delete draft().overrides[field];
    renderResults();
    save();
  }
});

document.addEventListener('mouseover', e => { const el = e.target.closest('[data-ref]'); if (el) showHover(el); });
document.addEventListener('mouseout', e => { if (e.target.closest('[data-ref]')) $('#pop').hidden = true; });
document.addEventListener('focusin', e => { if (e.target.dataset?.ref) showHover(e.target); });
document.addEventListener('focusout', e => { if (e.target.dataset?.ref) $('#pop').hidden = true; });

const smoke = applyHash();
renderAll();
document.body.dataset.ready = 'ok';
if (smoke) runSmoke();
````

- [ ] **Step 5: Implement the build** `tools/build.js`

````js
// Builds citation-generator.html: the page, the bundled code, and the guide excerpts in one file.
import { readFileSync, writeFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join, relative, resolve } from 'node:path';
import { loadGuide, CHAPTERS } from './guide.js';

const ROOT = fileURLToPath(new URL('..', import.meta.url));
const SRC = join(ROOT, 'src');
const IMPORT_RE = /^import \{([^}]*)\} from '(\.{1,2}\/[^']+)';$/gm;

/**
 * Bundles the src/ ES modules into one classic script. Supported syntax (the check fails loudly
 * otherwise): `import { a, b as c } from './x.js';` and `export function|const|let|class name`.
 */
export function bundle(entry = join(SRC, 'app.js')) {
  const order = [];
  const seen = new Set();
  const visit = file => {
    if (seen.has(file)) return;
    seen.add(file);
    const code = readFileSync(file, 'utf8');
    for (const m of code.matchAll(IMPORT_RE)) visit(resolve(dirname(file), m[2]));
    order.push({ file, code });
  };
  visit(entry);
  const parts = order.map(({ file, code }) => {
    const id = relative(SRC, file);
    let body = code.replace(IMPORT_RE, (_, names, spec) => {
      const dep = relative(SRC, resolve(dirname(file), spec));
      const binding = names.split(',').map(s => s.trim()).filter(Boolean).map(s => s.replace(/\s+as\s+/, ': ')).join(', ');
      return `const { ${binding} } = __modules[${JSON.stringify(dep)}];`;
    });
    if (/^\s*import\s/m.test(body)) throw new Error(`${id}: unsupported import syntax`);
    const exported = [];
    body = body.replace(/^export (async function|function|const|let|class) (\w+)/gm, (_, kind, name) => {
      exported.push(name);
      return `${kind} ${name}`;
    });
    if (/^\s*export\s/m.test(body)) throw new Error(`${id}: unsupported export syntax`);
    return `__modules[${JSON.stringify(id)}] = (() => {\n${body}\nreturn { ${exported.join(', ')} };\n})();`;
  });
  return `'use strict';\nconst __modules = {};\n${parts.join('\n')}\n`;
}

/** The guide excerpts the screen needs: section titles and first paragraphs, worked examples, Change log date. */
export function guideData(guide = loadGuide()) {
  const refs = [];
  for (let i = 1; i <= 13; i++) refs.push(`A${i}`);
  for (let i = 1; i <= 11; i++) refs.push(`C${i}`);
  for (const chapter of CHAPTERS) for (let i = 1; i <= 12; i++) refs.push(`${chapter} §${i}`);
  const sections = {};
  for (const ref of refs) {
    const s = guide.section(ref);
    if (s) sections[ref] = { title: s.title, text: guide.firstParagraph(ref) };
  }
  const examples = {};
  for (const e of guide.examples()) examples[e.id] = { expected: e.expected, confidence: e.confidence, citations: e.citations };
  return { changed: guide.changeLogDate(), refs: sections, examples };
}

export function build(outFile = join(ROOT, 'citation-generator.html')) {
  const page = readFileSync(join(SRC, 'page.html'), 'utf8');
  const data = JSON.stringify(guideData()).replace(/</g, '\\u003c');
  const code = bundle().replace(/<\/script/gi, '<\\/script');
  const html = page
    .replace('<!--GUIDE-->', () => `<script>window.GUIDE_DATA = ${data};</script>`)
    .replace('<!--APP-->', () => `<script>\n${code}</script>`);
  writeFileSync(outFile, html);
  return { outFile, bytes: Buffer.byteLength(html) };
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  const { outFile, bytes } = build(process.argv[2] ? resolve(process.argv[2]) : undefined);
  console.log(`Built ${relative(process.cwd(), outFile)} (${Math.round(bytes / 1024)} KB)`);
}
````

- [ ] **Step 6: Run the build test, build, and run everything**

Run: `node --test test/build.test.js`
Expected: `tests 4`, `pass 4`, `fail 0` (the browser test is skipped, not failed, if Chrome is missing).

Run: `npm run build`
Expected: `Built citation-generator.html (…KB)` at about 175 KB.

Run: `npm test`
Expected: `tests 827`, `pass 806`, `fail 0`, `skipped 8`, `todo 13`.

- [ ] **Step 7: Check the screen by hand**

Open `citation-generator.html#type=no-klokkerbok&example=1` in a browser (in the Claude desktop app: the Browser pane; otherwise `open citation-generator.html`). Confirm each item:
- The layout matches the approved mockup: sidebar, four input groups, output table, status bar.
- Status bar reads "Differs from guide example B.1 Example 1: SRN" (the pending contradiction) and "Guide last changed 2026-09-23".
- Hovering `A8` in the Title row shows the A8 text and the pinned B.1 §4 row.
- Typing in Parish updates Title, Abbrev, Author, FRN, and SRN immediately.
- Clicking the Title value opens an editor; typing and leaving marks it edited; ↺ restores it.
- ⧉ copies one field; *Copy all* copies the SOURCE/CITATION block.
- *Next citation on this Source* keeps the Source fields and empties the citation.
- *Clear* asks for a second click.
- Selecting *Federal census* and *Book or bygdebok* (switch Form to *Chapter*) renders without errors.
- The dark theme (system dark mode) is readable.
- At a narrow window (under 900 px) the columns stack.

- [ ] **Step 8: Commit**

```bash
git add src/page.html src/app.js tools/build.js test/build.test.js citation-generator.html
git commit -m "Add the Workbench screen, app wiring, and single-file build" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 13: Settle the guide's contradictions (user checkpoint)

This task edits the master guide, so **stop and get the user's decisions before changing anything.** Present the list below (one message, or a short doc), with the recommended option first, and wait for answers. For every decision, apply the listed edits, then run the check.

**Files:**
- Modify: `Grund-Castellano Citation Style Guide.md` (rule text, examples, Change log, Review queue)
- Modify: the affected `src/records/*.js` definitions (templates, pins, example inputs)
- Modify: `test/support/pending.js` (delete each settled entry)
- Modify: `docs/superpowers/specs/2026-09-23-citation-generator-design.md` (appendix)
- Regenerate: `citation-generator.html`

**Decisions to present** (the generator currently follows the worked example in every case):

| # | Where | Contradiction | Recommended | Alternative |
| --- | --- | --- | --- | --- |
| 1 | B.1 Ex. 1 | Page string "Thor Emil birth and baptism entry"; SRN "Thor Emil baptism entry" | SRN uses the page's subject: edit the guide's SRN to "…Thor Emil birth and baptism entry." | Page uses "baptism entry": change the example page string and the example's `noun` input |
| 2 | B.1 §7 + Ex. 3 | "folio 145-148" (hyphen) vs "145–148" (en dash) | En dash everywhere: edit §7 row to `folio [F]–[F], [Deceased] estate` and Ex. 3 page to `folio 145–148, …`; update the `no-skifteprotokoll` page pin and example `folio` input to `145–148` | Hyphen everywhere: edit the Ex. 3 FRN and SRN |
| 3 | B.2 Ex. 2 (Review queue C7) | Call number `SE/VA/11047/F II/26`; FRN cites `SE/VA/11047` | FRN cites the full volume path: edit the Ex. 2 FRN; mark C7 Resolved | Call number becomes `SE/VA/11047`: edit the Ex. 2 table and the example `call` input |
| 4 | B.2 Ex. 2 | SRN ends ", Ambjörbymon"; no other SRN carries a place | Drop the place: edit the Ex. 2 SRN | Keep it: add an optional SRN place to Swedish court records |
| 5 | B.3 Ex. 8 | SRN "Per L. Grund obituary"; page "Per Larsson Grund obituary" | SRN uses the page's subject | Keep the newspaper's own name form: add an optional "Name in SRN" input to `us-newspaper` |
| 6 | B.3 Ex. 11 | FRN "(image 496)" vs page "(image 496, right)"; SRN "death and burial of Emma Söderström, died 7 May 1914, p. 283" | FRN keeps ", right"; SRN becomes "First Lutheran Church (Warren, Minn.), death and burial entry of Emma Söderström, p. 283." | Keep the dated SRN: add an optional "Entry in SRN" input to `us-church` |
| 7 | B.4 Family Bible | Page "Per Larsson Grund birth entry"; FRN "entry for Per Larsson"; SRN "Per Larsson birth entry" | Full name everywhere: edit the FRN and SRN | Short name in notes: add an optional "Name in notes" input to `pp-bible` |
| 8 | B.4 Funeral program (Review queue C11) | Pubinfo omits the funeral home A10 requires | Follow A10: Pubinfo becomes "Williams, Minnesota: Helgeson Funeral Home, 16 February 1953."; mark C11 Resolved | Change A10's funeral-program row to omit the funeral home, and the `pp-funeral-program` pubinfo template to `{city}, {date}.` |
| 9 | B.4 Audio interview | Repository "Peter Michael Grund, private collection"; FRN "privately held by Peter Grund" | One form everywhere; the user picks which (edit the FRN, or the Repository and every custodian default in `published.js`) | — |
| 10 | B.4 Personal research | Page "Entry for Ambmyra, typed page, received 30 April 2026"; SRN "Ambmyra typed page, received 30 April 2026" | Use the SRN's shorter form in the page string too (edit the example table and the example `section` input) | Keep both: add an optional "Locator in SRN" input to `pp-research` |
| 11 | B.1 §4 | Meeting-minutes template "parish meeting minutes (menighetsmøteprotokoll)" vs its example "menighetsmøteprotokoll [parish meeting minutes]" | Norwegian first, as in the 2026-09-23 Change log: edit the §4 template to `Norway, [Fylke/Amt], [Parish], menighetsmøteprotokoll [parish meeting minutes], [vol], [years]` and re-pin `no-minutes.title` | English first: change the `no-minutes` title template |
| 12 | B.3 §7 | City directory template "p. [N], entry for [Name]" vs Ex. 7 "p. 412, Per Larsson Grund directory entry" | Edit §7 to `p. [N], [Name] directory entry` and re-pin `us-city-directory.page` | Change Ex. 7 and the `us-city-directory` page template |
| 13 | B.3 §9 vs §7 | §9 gives "[Name] Find a Grave entry" and "[Name] passenger manifest entry"; §7 and Ex. 4 end at the name | Edit §9 to match §7 (no record noun after a memorial or list number) | Edit §7 and Ex. 4 to add the noun; set the default noun in `us-find-a-grave` and `us-passenger-manifest` |

- [ ] **Step 1: Present the decisions and wait for answers.** Do not edit the guide before the user answers.

- [ ] **Step 2: Apply each decision.** For each one: edit the guide text; edit the record definition if the chosen option changes a template, pin, or example input; delete the matching entry in `test/support/pending.js`.

- [ ] **Step 3: Record the decisions in the guide.** Add one Change log row per decision (today's date, rule/section, what changed, why), newest first. Set Review queue items C7 and C11 to Resolved with the decision if decisions 3 and 8 settled them.

- [ ] **Step 4: Update the spec appendix.** In `docs/superpowers/specs/2026-09-23-citation-generator-design.md`, replace group C of the appendix with a line per decision stating what was chosen. Also note that the Online video FRN wording and SRN channel, and the Audio interview topic wording, turned out to be inputs rather than contradictions.

- [ ] **Step 5: Run the check**

Run: `npm test`
Expected: `fail 0`, `todo` equal to the number of pending entries left (0 if every decision was applied). If a pin fails, the report shows the closest current row: copy that row into the pin.

- [ ] **Step 6: Rebuild and commit together**

```bash
npm run build
git add "Grund-Castellano Citation Style Guide.md" src/records test/support/pending.js docs/superpowers/specs/2026-09-23-citation-generator-design.md citation-generator.html
git commit -m "Settle guide contradictions found by the generator check" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 14: README, retire the old builder, final verification

**Files:**
- Create: `README.md`
- Delete: `citation-builder.html` (git history keeps it; the approved spec retires it once all 44 record types are covered, which Task 8 made true)

- [ ] **Step 1: Write `README.md`**

````markdown
# Grund-Castellano Citation Generator

Turns one record into finished Gramps fields (Source, Citation, reference notes) and Paperless metadata by following `Grund-Castellano Citation Style Guide.md`, the master copy of the guide.

## Use it

Open `citation-generator.html` in a browser. Pick a record type in the sidebar, fill in the inputs, and copy the fields from the table on the right. Hover a rule reference to read that rule. Your work in progress is saved in the browser.

## Change a rule

1. Edit the rule, table row, or example in the guide; add a Change log row; mark any Review queue item it settles.
2. Run `npm test`. The report names every pinned row, worked example, or §4/§7 row the edit touched.
3. Update the affected record definitions in `src/records/` until the check passes (or fix the guide if the failure shows the guide is wrong).
4. Run `npm run build`.
5. Commit the guide, the code, and `citation-generator.html` together.

## Commands

- `npm test`: unit tests plus the guide checks (worked examples, pins, coverage, shared tables). Needs Node 24; nothing to install.
- `npm run build`: writes `citation-generator.html`.

## Where things live

- `src/records/`: one file per guide chapter; each record type lists its inputs, templates, the guide rows it follows (pins), and the inputs that reproduce its worked examples.
- `test/support/pending.js`: worked-example fields that differ because the guide contradicts itself.
- `test/support/not-covered.js`: guide rows deliberately without a record type.
- `docs/superpowers/`: the design and this plan.
````

- [ ] **Step 2: Retire the old builder**

Run: `git rm citation-builder.html`

- [ ] **Step 3: Final verification**

Run: `npm test && npm run build && git status --short`
Expected: `fail 0`; the build succeeds; `git status` shows only `README.md` and the deleted `citation-builder.html` (and `citation-generator.html` only if it changed).

- [ ] **Step 4: Commit**

```bash
git add README.md citation-generator.html
git commit -m "Add README and retire the old citation builder" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

## Self-review against the spec

| Spec section | Task(s) |
| --- | --- |
| Decisions: form tool, Workbench look, one HTML file, guide master, Paperless only | 11, 12 (look, delivery); 1–8 (templates); Global Constraints |
| 1. The screen: sidebar, four groups, output table, hover cards, status bar, gaps, Copy all, Next citation, Load guide example, deep link, starts empty | 11, 12 |
| 2. Record-type definitions: fields, templates, `«…»`, tokens, pins (multi-row), page variants, derive, examples, unpinned | 4 (engine and shape), 5–8 (definitions), 5 (unpinned report) |
| 3. The check: worked examples, pins, §4 + §7 coverage with not-covered list, shared tables, readable report, first-run pending list | 3 (tables), 5 (examples, pins, coverage, report), 8 (full run) |
| 3. Six new record types and the §7 page variants | 7 (pension, service record, manifest; vital and naturalization variants), 8 (edited collection, family record, oral history; book variants) |
| 4. Files and build: layout, no dependencies, offline single file, guide excerpts, browser storage, git | 1, 10, 12 |
| 5. Workflow, errors (gaps, storage, clipboard, stale drafts), testing (unit, smoke, manual) | 9, 10, 12, 14 (README) |
| Appendix contradictions and Review queue C7/C11 | 5 (pending list), 13 |
| Open item: Copy all layout after the Gramps export | Not scheduled: waits for the export; `copyAllText` in `src/view.js` is the one place to change |
| Section 1: "Fields may declare their own guide reference for a label hover card" | Deliberately not built: no record type needs one yet. Group headings and every output rule reference have hover cards. Add a `rule` entry to a field tuple and a `data-ref` on its label in `src/view.js` if one is ever needed |
