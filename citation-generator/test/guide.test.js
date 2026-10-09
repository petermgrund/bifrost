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
