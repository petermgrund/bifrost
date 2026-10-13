// A7 attributes, the usual cited-for, and the A14 General form.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { loadGuide, normalize } from '../tools/guide.js';
import { recordById } from '../src/records/index.js';
import { newDraft, draftFromExample, buildOutputs, usualCitedFor, attributesOf } from '../src/engine.js';
import { plain } from '../src/template.js';

const guide = loadGuide();

test('the parts that leave the page string become attributes, empty ones left out', () => {
  const folk = recordById('no-folketelling');
  const o = buildOutputs(folk, draftFromExample(folk, folk.examples[0]));
  assert.deepEqual(o.attributes, [
    ['Subject', 'Karen Indiana Evensdatter'], ['Record', 'household'], ['Household', 'Hansen household'],
    ['Source says', 'tjenestepige'], ['Evidence', 'stated age 14'], ['Record type', 'Census 1865 and later'],
  ]);
  const natz = recordById('us-naturalization');
  const claim = natz.examples.find(c => c.guide === 'B.3 Example 12');
  assert.deepEqual(attributesOf(natz, draftFromExample(natz, claim)).at(-1), ['Record type', 'Naturalization · Final papers (before 1906)']);
  const copy = draftFromExample(folk, folk.examples[0]);
  copy.subject.copy = 'transcript';
  assert.deepEqual(attributesOf(folk, copy)[1], ['Record', 'household transcript']);
});

test('a new citation is cited for its record noun\'s usual fact, and a different one reaches the notes', () => {
  const vital = recordById('us-vital');
  const d = draftFromExample(vital, vital.examples[0]);
  assert.equal(usualCitedFor(vital, d.subject), 'death');
  const usual = buildOutputs(vital, d);
  assert.equal(usual.page, 'certificate no. 1929-MN-XXXXXX (death)');
  assert.doesNotMatch(usual.frn + usual.srn, /documenting|\(death\)/);
  d.values.citedFor = "parents' names";
  const split = buildOutputs(vital, d);
  assert.equal(split.page, "certificate no. 1929-MN-XXXXXX (parents' names)");
  assert.match(split.frn, /\(documenting parents' names\);/);
  assert.match(split.srn, /\(parents' names\)\.$/);
  assert.equal(usualCitedFor(recordById('us-find-a-grave'), { noun: '' }), 'burial');
  assert.equal(usualCitedFor(recordById('us-newspaper'), { noun: 'news mention' }), '');
});

test('a record type with no locator has only what it is cited for', () => {
  const headstone = recordById('us-headstone');
  const o = buildOutputs(headstone, draftFromExample(headstone, headstone.examples[0]));
  assert.equal(o.page, '(burial)');
  const letter = recordById('pp-letter');
  assert.equal(plain(buildOutputs(letter, newDraft(letter)).page), '([Cited for])');
});

test('legacy builds the page string the way the rules before 2026-10-13 did', () => {
  const vital = recordById('us-vital');
  const d = draftFromExample(vital, vital.examples[0]);
  assert.equal(buildOutputs(vital, d, { legacy: true }).page, 'certificate no. 1929-MN-XXXXXX, Per Larsson Grund death certificate');
  d.values.citedFor = 'death';
  const old = buildOutputs(vital, d, { legacy: true });
  assert.equal(old.page, 'certificate no. 1929-MN-XXXXXX, Per Larsson Grund death certificate (death)');
  assert.match(old.srn, /\(death\)\.$/);
});

test('the General form reproduces the A14 example', () => {
  const general = recordById('general');
  const d = draftFromExample(general, { guide: 'A14', inputs: general.a14Example });
  const o = buildOutputs(general, d);
  const text = guide.sectionText('A14');
  for (const field of ['title', 'abbrev', 'author', 'pubinfo', 'page', 'frn', 'srn']) {
    assert.ok(text.includes(normalize(plain(o[field]))), `${field}: ${plain(o[field])}`);
  }
  assert.equal(general.tag, 'General form');
  assert.deepEqual(o.attributes, [['Subject', 'Peter L. Grund'], ['Record', 'power of attorney'], ['Record type', 'General form']]);
});
