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
