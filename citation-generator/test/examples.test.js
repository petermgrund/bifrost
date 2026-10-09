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
        const entry = PENDING[label]?.[field];
        const name = `${label} · ${record.id} · ${field}`;
        if (entry) {
          test(`${name} (pending)`, t => {
            t.diagnostic('Differs from the guide: ' + entry.reason);
            const got = plain(out[field]);
            assert.ok(got === entry.generator, differsMessage(name, entry.generator, got));
          });
        } else {
          test(name, () => {
            const got = plain(out[field]);
            assert.ok(got === fields[field], differsMessage(name, fields[field], got));
          });
        }
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
  for (const [label, entries] of Object.entries(PENDING)) {
    const [id, citation] = label.split(' · citation ');
    const ex = examples.find(e => e.id === id);
    assert.ok(ex, `Pending entry for unknown example "${label}"`);
    const { record, claim } = claims.find(c => c.claim.guide === id && (c.claim.citation || 0) === Number(citation || 0)) || {};
    assert.ok(record, `Pending entry "${label}" has no claim`);
    const out = buildOutputs(record, draftFromExample(record, claim));
    const expected = expectedFor(ex, claim).fields;
    for (const [field, entry] of Object.entries(entries)) {
      assert.equal(plain(out[field]), entry.generator, `${label} · ${field}: the generator's output no longer matches the pinned "generator" value; update it`);
      assert.notEqual(entry.generator, expected[field], `${label} · ${field} now matches the guide: remove it from test/support/pending.js`);
    }
  }
});
