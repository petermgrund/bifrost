// Paperless fields for real record types, checked against Part C's worked examples.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { newDraft, draftFromExample, buildOutputs, setVariant } from '../src/engine.js';
import { recordById } from '../src/records/index.js';

const outputsOf = (id, n = 0, fresh = false) => {
  const type = recordById(id);
  return buildOutputs(type, fresh || !type.examples[n] ? newDraft(type) : draftFromExample(type, type.examples[n]));
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
  assert.equal(outputsOf('pp-research').plTitle, 'Alfreddson Ambjörby research 2026-04-30');
});

test('C1 uses the page string\'s record noun, in its copy form', () => {
  assert.equal(outputsOf('no-folketelling').plTitle, 'Karen Indiana Evensdatter in Hansen household 1875');
  assert.equal(outputsOf('no-skifteprotokoll').plTitle, 'Anders Hansen estate entry 1822');
  assert.equal(outputsOf('pp-register').plTitle, 'Frithjof Siggerud directory entry 1950');
  const dop = recordById('se-dopbok');
  const d = newDraft(dop);
  Object.assign(d.subject, { name: 'Kjerstin Mattsdotter', noun: 'birth and baptism entry', copy: 'index entry' });
  d.values.eventYear = '1820';
  assert.equal(buildOutputs(dop, d).plTitle, 'Kjerstin Mattsdotter birth and baptism index entry 1820');
});

test('C1 variants: record types with titles of their own', () => {
  assert.equal(outputsOf('us-find-a-grave').plTitle, 'Per Larsson Grund Find a Grave memorial 1929');
  assert.equal(outputsOf('pp-funeral-program').plTitle, 'Thomas Emil Siggerud funeral program 1953');
  assert.equal(outputsOf('pp-video').plTitle, 'Norra Ny walking tour video clip 2025');
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
  for (const id of ['pp-interview', 'pp-research', 'pp-letter']) assert.equal(outputsOf(id, 0, true).plCorrespondent, '', `${id}: C6 leaves private items blank`);
  assert.equal(outputsOf('pp-book').plDateMeaning, 'publication');
});

test('final papers take their year from Date signed, not from a year left by another form', () => {
  const natz = recordById('us-naturalization');
  const d = draftFromExample(natz, natz.examples.find(c => c.guide === 'B.3 Example 3'));
  assert.equal(d.values.eventYear, '1894');
  setVariant(natz, d, 'final');
  Object.assign(d.values, { vol: 'C', page: '57', image: '62', signed: '12 March 1897' });
  d.subject.name = 'Peter L. Grund';
  const o = buildOutputs(natz, d);
  assert.equal(o.plTitle, 'Peter L. Grund naturalization petition 1897');
  assert.match(o.srn, /\(1897\), Peter L\. Grund\.$/);
  assert.match(o.frn, /p\. 57 \(12 March 1897\), Peter L\. Grund;/);
  assert.doesNotMatch(`${o.plTitle} ${o.srn} ${o.frn}`, /1894/);
});

test('censuses, the matrikkel, headstones, and directories take the Paperless year from their own date', () => {
  const yearAfterChange = (id, changes) => {
    const type = recordById(id);
    const d = draftFromExample(type, type.examples[0]);
    d.values.eventYear = '1700';
    Object.assign(d.values, changes);
    return buildOutputs(type, d).plTitle;
  };
  assert.match(yearAfterChange('us-federal-census', { year: '1930' }), / 1930$/);
  assert.match(yearAfterChange('no-folketelling', { year: '1900' }), / 1900$/);
  assert.match(yearAfterChange('se-folkrakning', { year: '1890' }), / 1890$/);
  assert.match(yearAfterChange('no-matrikkel', { year: '1886' }), / 1886$/);
  assert.match(yearAfterChange('us-headstone', { dyear: '1950' }), / 1950$/);
  assert.match(yearAfterChange('us-city-directory', { year: '1905' }), / 1905$/);
});
