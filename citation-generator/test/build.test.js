import { test } from 'node:test';
import assert from 'node:assert/strict';
import { existsSync, readFileSync, writeFileSync, mkdtempSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join, relative } from 'node:path';
import { pathToFileURL, fileURLToPath } from 'node:url';
import { bundle, guideData, source, OUT } from '../tools/build.js';
import { RECORDS, recordById } from '../src/records/index.js';
import { buildOutputs, draftFromExample } from '../src/engine.js';

const SRC = join(fileURLToPath(new URL('..', import.meta.url)), 'src');

test('the bundle is one ES module exporting the engine, the record types, the form rules, and the guide', async () => {
  const file = join(mkdtempSync(join(tmpdir(), 'citations-bundle-')), 'citations.js');
  writeFileSync(file, source());
  const m = await import(pathToFileURL(file).href);
  assert.equal(m.RECORDS.length, RECORDS.length);
  for (const name of ['buildOutputs', 'newDraft', 'nextCitationDraft', 'runChecks', 'loadState', 'saveState', 'citationRows', 'outputRows', 'plain', 'recordGroups']) {
    assert.equal(typeof m[name], 'function', name);
  }
  const type = m.recordById('no-klokkerbok');
  const local = recordById('no-klokkerbok');
  assert.deepEqual(m.buildOutputs(type, m.draftFromExample(type, type.examples[0])), buildOutputs(local, draftFromExample(local, local.examples[0])));
  assert.match(m.GUIDE.changed, /^\d{4}-\d{2}-\d{2}$/);
});

test('bundle throws when an import name is not exported by its dependency', () => {
  const dir = mkdtempSync(join(tmpdir(), 'citation-bundle-'));
  const depFile = join(dir, 'dep.js');
  const entryFile = join(dir, 'entry.js');
  writeFileSync(depFile, 'export function real() { return 1; }\n');
  writeFileSync(entryFile, "import { missing } from './dep.js';\nmissing();\n");
  assert.throws(() => bundle([entryFile]), err => err.message === `${relative(SRC, entryFile)}: 'missing' is not exported by ${relative(SRC, depFile)}`);
});

test('bundle throws when two entries export the same name', () => {
  const dir = mkdtempSync(join(tmpdir(), 'citation-bundle-'));
  const a = join(dir, 'a.js'), b = join(dir, 'b.js');
  writeFileSync(a, 'export const same = 1;\n');
  writeFileSync(b, 'export const same = 2;\n');
  assert.throws(() => bundle([a, b]), err => err.message === `${relative(SRC, b)}: 'same' is also exported by ${relative(SRC, a)}`);
});

test('guide data carries section text, examples, and the Change log date', () => {
  const data = guideData();
  assert.match(data.changed, /^\d{4}-\d{2}-\d{2}$/);
  assert.match(data.refs.A8.title, /^A8 · Title$/);
  assert.ok(data.refs['B.1 §4'].text.length > 0);
  assert.ok(data.examples['B.1 Example 1'].expected.title);
});

test('Bifrost serves the current build', () => {
  assert.ok(existsSync(OUT), 'run npm run build');
  assert.ok(readFileSync(OUT, 'utf8') === source(), 'bifrost/web/static/citations/citations.js is out of date: run npm run build');
});
