// Record types as Bifrost holds them: edits laid over the shipped types, new types, versions, and template helpers.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { SHIPPED, RECORDS, recordById, setRecords } from '../src/records/index.js';
import { applyEdits, toDefinition, blankDefinition, typeAtVersion, sampleInputs, previewInputs, guideForm, printout } from '../src/registry.js';
import { draftFromExample, buildOutputs, newDraft } from '../src/engine.js';
import { fill, plain } from '../src/template.js';

const outputs = (type, claim) => buildOutputs(type, draftFromExample(type, claim));

test('a type saved unchanged builds exactly what the shipped type builds', () => {
  for (const type of SHIPPED) {
    const [saved] = applyEdits([type], [{ id: type.id, kind: 'override', definition: toDefinition(type), version: 3 }]);
    assert.equal(saved.version, 3);
    assert.equal(saved.edited, true);
    for (const claim of type.examples) {
      const want = outputs(type, claim), got = outputs(saved, claim);
      for (const key of Object.keys(want)) assert.deepEqual(got[key], want[key], `${type.id} ${claim.guide} ${key}`);
    }
  }
});

test('an edited template takes over and the type keeps its computed values', () => {
  const vital = recordById('us-vital');
  const definition = { ...toDefinition(vital) };
  definition.pageVariants = definition.pageVariants.map(v => (v.key === 'certificate' ? { ...v, page: 'cert. {cert}' } : v));
  definition.usual = { 'death certificate': 'death and burial' };
  const [edited] = applyEdits([vital], [{ id: vital.id, kind: 'override', definition }]);
  const o = outputs(edited, vital.examples[0]);
  assert.equal(o.page, 'cert. 1929-MN-XXXXXX (death and burial)');
  assert.equal(o.abbrev, outputs(vital, vital.examples[0]).abbrev, 'the state abbreviation still comes from the shipped code');
});

test('deleted types drop out, new types join with their sample as the preview example', () => {
  const definition = { ...blankDefinition('Deed'), sample: { creator: 'Marshall County Register of Deeds', place: 'Minnesota, Marshall County', collection: 'Deed Record, vol. 12', page: '45', platform: 'FamilySearch' } };
  const list = applyEdits(SHIPPED, [{ id: 'pp-letter', kind: 'override', deleted: true }, { id: 'my-deed', kind: 'custom', definition, version: 2 }]);
  assert.ok(!list.some(t => t.id === 'pp-letter'));
  const deed = list.find(t => t.id === 'my-deed');
  assert.equal(deed.custom, true);
  assert.equal(deed.name, 'Deed');
  assert.equal(deed.version, 2);
  const o = outputs(deed, deed.examples[0]);
  assert.equal(o.title, 'Minnesota, Marshall County, Deed Record, vol. 12');
  assert.equal(deed.tag, undefined, 'a new type is not tagged General form');
  assert.equal(o.pubinfo, 'Digital images, FamilySearch (https://www.familysearch.org).', 'a null Pubinfo is the standard form');
  assert.equal(plain(o.page), 'p. 45 ([Cited for])');
  assert.deepEqual(sampleInputs(deed), definition.sample);
});

test('a type started from a General form citation takes its values as the example and its noun', () => {
  const general = recordById('general');
  const draft = draftFromExample(general, { guide: 'A14', inputs: general.a14Example });
  draft.values.citedFor = 'power of attorney';
  const definition = blankDefinition('Power of attorney', draft);
  assert.equal(definition.sample.collection, 'Miscellaneous Record, vol. K');
  assert.equal(definition.sample.name, 'Peter L. Grund');
  assert.deepEqual(definition.nouns, ['power of attorney']);
  assert.equal(definition.freeNoun, false);
  assert.deepEqual(definition.usual, { 'power of attorney': 'power of attorney' });
  const [type] = applyEdits(SHIPPED, [{ id: 'my-poa', kind: 'custom', definition }]).filter(t => t.id === 'my-poa');
  const o = outputs(type, type.examples[0]);
  assert.equal(plain(o.page), 'image 32 (power of attorney)');
});

test('a copy of a built-in type keeps its computed values', () => {
  const census = recordById('us-federal-census');
  const definition = { ...toDefinition(census), name: 'My census', base: 'us-federal-census' };
  const [copy] = applyEdits(SHIPPED, [{ id: 'my-census', kind: 'custom', definition }]).filter(t => t.id === 'my-census');
  const claim = census.examples[0];
  const want = outputs(census, claim);
  assert.deepEqual({ ...outputs(copy, claim), attributes: [] }, { ...want, attributes: [] });
  assert.equal(toDefinition(copy).base, 'us-federal-census');
  const [bare] = applyEdits(SHIPPED, [{ id: 'my-census', kind: 'custom', definition: { ...definition, base: undefined } }]).filter(t => t.id === 'my-census');
  assert.notEqual(outputs(bare, claim).srn, want.srn, 'without its base the computed values are gaps');
});

test('the registry every lookup reads can be replaced and restored', () => {
  const list = applyEdits(SHIPPED, [{ id: 'my-deed', kind: 'custom', definition: blankDefinition('Deed') }]);
  setRecords(list);
  try {
    assert.equal(recordById('my-deed').name, 'Deed');
    assert.equal(RECORDS.length, SHIPPED.length + 1);
  } finally {
    setRecords(SHIPPED);
  }
  assert.equal(recordById('my-deed'), null);
});

test('a type at an old version is the shipped type with that version\'s edit', () => {
  const vital = recordById('us-vital');
  const old = { ...toDefinition(vital), abbrev: 'Old abbrev' };
  assert.equal(typeAtVersion(SHIPPED, 'us-vital', old, 'override').abbrev, 'Old abbrev');
  assert.equal(typeAtVersion(SHIPPED, 'us-vital', null, 'override').abbrev, vital.abbrev);
  const custom = typeAtVersion(SHIPPED, 'my-deed', blankDefinition('Deed'), 'custom');
  assert.equal(custom.name, 'Deed');
});

test('template helpers: last word, year, state abbreviation, first part, lower case', () => {
  const v = { author: 'Birger Kirkeby', date: '3 May 1919', state: 'Minnesota', place: 'Warren, Minnesota', noun: 'Deed' };
  assert.equal(fill('{author|last}, {date|year}, {state|abbrev}, {place|first}, {noun|lower}', v), 'Kirkeby, 1919, Minn., Warren, deed');
  assert.equal(fill('A«, {missing|year}»', v), 'A');
  assert.equal(plain(fill('{missing|last}', v, k => k)), '[missing]');
  assert.equal(fill('{author|nope}', v), 'Birger Kirkeby', 'an unknown helper leaves the value as it is');
  assert.ok(newDraft(blankDefinition()));
});

test('a preview on another page form takes a record noun that form lists', () => {
  const vital = recordById('us-vital');
  assert.equal(previewInputs(vital).noun, sampleInputs(vital).noun);
  assert.equal(previewInputs(vital, 'license').noun, vital.pageVariants.find(v => v.key === 'license').nouns[0]);
  assert.equal(previewInputs(vital, 'license').variant, 'license');
});

test('templates print in the guide\'s notation', () => {
  const general = recordById('general');
  assert.equal(guideForm(general, '{pageLoc}«, no. {entry}»'), 'p. [P] (image [I]), no. [Entry no.]');
  assert.equal(guideForm(general, '{creator|last}, {date|year}'), '[Creator, last word], [Date, year]');
});

test('the printout has each chapter\'s tables with Bifrost\'s own types and edits', () => {
  const vital = recordById('us-vital');
  const definition = { ...toDefinition(vital), abbrev: '{state|abbrev} vital records' };
  const types = applyEdits(SHIPPED, [{ id: 'us-vital', kind: 'override', definition },
    { id: 'my-deed', kind: 'custom', definition: { ...blankDefinition('Deed'), sample: { place: 'Minnesota, Marshall County', collection: 'Deed Record, vol. 12' } } }]);
  const md = printout(types, '13 October 2026');
  assert.match(md, /^# Record types\n\nPrinted from Bifrost, 13 October 2026\./);
  for (const chapter of ['## Norwegian', '## Swedish', '## US', '## Published & personal', '## General']) assert.ok(md.includes(chapter), chapter);
  assert.ok(md.includes('| State vital record | `[State, abbreviated] vital records` | `Minn. vital records` |'));
  assert.ok(md.includes('| State vital record · Marriage license | `license no. [License no.]` |'));
  assert.ok(md.includes('| Deed | `[Place], [Collection], [Years]` | `Minnesota, Marshall County, Deed Record, vol. 12` |'));
  assert.ok(md.includes('| State census | `[Census year] [State] State Census, [County] County` |  |'), 'a type with no example prints none');
});
