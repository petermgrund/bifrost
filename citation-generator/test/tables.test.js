import { test } from 'node:test';
import assert from 'node:assert/strict';
import { loadGuide } from '../tools/guide.js';
import { PLATFORMS, STATE_ABBREV, CHAPTER_CODE, MEDIA, isoDate, stateAbbrev, lastWord } from '../src/tables.js';
import { RECORDS } from '../src/records/index.js';

const guide = loadGuide();

test('platform homepages match the A10 platform table', () => {
  const table = guide.tables('A10').find(t => t.header[0] === 'Platform');
  assert.ok(table, 'A10 has no Platform table');
  const fromGuide = Object.fromEntries(table.rows.map(([name, url]) => [name.replace(/\s*\(.*\)$/, ''), url]));
  assert.deepEqual(PLATFORMS, fromGuide);
});

test('Pubinfo media and the genealogical form match A10', () => {
  const table = guide.tables('A10').find(t => t.header[0] === 'Medium');
  assert.ok(table, 'A10 has no Medium table');
  assert.deepEqual(MEDIA, table.rows.map(([medium]) => medium));
  assert.ok(guide.sectionText('A10').includes('Genealogical records: [medium], [platform] (homepage URL).'));
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

for (const [code, chapter] of Object.entries(CHAPTER_CODE)) {
  test(`${chapter} §9 Record nouns table matches the record types' noun lists`, () => {
    const table = guide.tables(`${chapter} §9`).find(t => t.header[0] === 'Record type' && t.header[1] === 'Record nouns');
    assert.ok(table, `${chapter} §9 has no Record nouns table`);
    const fromGuide = new Map(table.rows.map(([name, nouns]) => [name, nouns.split(' · ').map(n => (n === '(none)' ? '' : n))]));
    const ours = RECORDS.filter(r => r.chapter === code);
    for (const name of fromGuide.keys()) assert.ok(ours.some(r => r.name === name), `${chapter} §9 lists "${name}", which is not a ${chapter} record type`);
    for (const r of ours) assert.deepEqual(r.nouns, fromGuide.get(r.name) ?? [''], `${r.name}: nouns differ from ${chapter} §9`);
  });
}

test('helpers', () => {
  assert.equal(isoDate('14 March 1925'), '1925-03-14');
  assert.equal(isoDate('ca. 1890s'), '');
  assert.equal(stateAbbrev('Minnesota'), 'Minn.');
  assert.equal(stateAbbrev('Oregon'), 'Oregon');
  assert.equal(lastWord('Birger Kirkeby'), 'Kirkeby');
});
