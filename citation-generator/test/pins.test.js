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
