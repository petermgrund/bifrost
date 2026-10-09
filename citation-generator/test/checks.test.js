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

test('no Repository or Pubinfo checks: a platform or deep URL in the note is fine', () => {
  const d = clean();
  d.values.archive = 'Ancestry';
  d.values.platform = 'Ancestry';
  assert.deepEqual(rulesFor(klokk, d), []);
});

test('Fill: unfilled parts are listed by field', () => {
  const problems = runChecks(klokk, newDraft(klokk), buildOutputs(klokk, newDraft(klokk)));
  const fill = problems.find(p => p.rule === 'Fill');
  assert.equal(fill.message, 'Unfilled parts in: Title, Abbrev, Author, Page, FRN, SRN, Paperless title.');
});
