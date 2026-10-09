import { test } from 'node:test';
import assert from 'node:assert/strict';
import { loadState, saveState, restoreDraft, STORE_KEY } from '../src/store.js';
import { recordById } from '../src/records/index.js';
import { newDraft, buildOutputs } from '../src/engine.js';

const memory = (initial = {}) => {
  const data = { ...initial };
  return { getItem: k => (k in data ? data[k] : null), setItem: (k, v) => { data[k] = String(v); }, data };
};

test('saves and loads the current type and its draft', () => {
  const storage = memory();
  const draft = newDraft(recordById('no-klokkerbok'));
  draft.values.parish = 'Eidsvoll';
  assert.equal(saveState(storage, { current: 'no-klokkerbok', drafts: { 'no-klokkerbok': draft }, filter: 'kirke' }), true);
  const state = loadState(storage, recordById);
  assert.equal(state.current, 'no-klokkerbok');
  assert.equal(state.filter, 'kirke');
  assert.equal(state.drafts['no-klokkerbok'].values.parish, 'Eidsvoll');
});

test('nothing usable saved gives null', () => {
  assert.equal(loadState(memory(), recordById), null);
  assert.equal(loadState(memory({ [STORE_KEY]: '{not json' }), recordById), null);
  assert.equal(loadState(memory({ [STORE_KEY]: JSON.stringify({ current: 'gone-type', drafts: {} }) }), recordById), null);
});

test('drafts for removed types and unknown fields are dropped', () => {
  const saved = {
    current: 'no-klokkerbok',
    drafts: {
      'gone-type': { values: { x: '1' } },
      'no-klokkerbok': { values: { parish: 'Eidsvoll', oldField: 'x' }, subject: { name: 7 }, overrides: { title: 'T', bad: 3 } },
    },
  };
  const state = loadState(memory({ [STORE_KEY]: JSON.stringify(saved) }), recordById);
  assert.deepEqual(Object.keys(state.drafts), ['no-klokkerbok']);
  const d = state.drafts['no-klokkerbok'];
  assert.equal(d.values.parish, 'Eidsvoll');
  assert.equal('oldField' in d.values, false);
  assert.equal(d.subject.name, '');
  assert.deepEqual(d.overrides, { title: 'T' });
});

test('a draft saved by the version with Holder & access loads; typed values survive and holder settings are dropped', () => {
  const saved = {
    current: 'no-klokkerbok',
    drafts: {
      'no-klokkerbok': {
        type: 'no-klokkerbok',
        values: { parish: 'Eidsvoll', vol: 'I 2', page: '57', url: 'https://example.org/x' },
        subject: { name: 'Thor Emil', noun: 'baptism entry' },
        holder: {
          heldBy: 'private', archive: 'Riksarkivet', custodian: 'Peter Grund', custodianPlace: 'Duluth', custodyWording: 'personal collection',
          keepPlatform: true, platform: 'FamilySearch', platformHome: 'https://x', medium: 'Database',
        },
        confidence: 'Normal', variant: '',
        overrides: { title: 'T', pubinfo: 'Digital images, FamilySearch.', repository: 'Riksarkivet', date: '' },
        example: '',
      },
    },
    filter: '',
  };
  const state = loadState(memory({ [STORE_KEY]: JSON.stringify(saved) }), recordById);
  const d = state.drafts['no-klokkerbok'];
  assert.equal('holder' in d, false);
  assert.deepEqual([d.values.parish, d.values.vol, d.values.page, d.values.url], ['Eidsvoll', 'I 2', '57', 'https://example.org/x']);
  assert.deepEqual([d.subject.name, d.subject.noun, d.confidence], ['Thor Emil', 'baptism entry', 'Normal']);
  assert.deepEqual([d.values.platform, d.values.archive], ['Digitalarkivet', 'Statsarkivet i Oslo']);
  assert.deepEqual(d.overrides, { title: 'T', pubinfo: 'Digital images, FamilySearch.' }, 'Pubinfo is an output again; Repository and Date are not');
  assert.equal(d.values.pubmedium, 'Digital images');
  assert.doesNotThrow(() => buildOutputs(recordById('no-klokkerbok'), d));
});

test('a saved noun that was renamed loads under its new name for that record type', () => {
  const nounAfterLoad = (id, noun, variant = '') => {
    const saved = { current: id, drafts: { [id]: { subject: { name: 'X', noun }, variant } } };
    return loadState(memory({ [STORE_KEY]: JSON.stringify(saved) }), recordById).drafts[id].subject.noun;
  };
  assert.equal(nounAfterLoad('no-ministerialbok', 'marriage'), 'marriage entry');
  assert.equal(nounAfterLoad('se-vigselbok', 'marriage'), 'marriage entry');
  assert.equal(nounAfterLoad('us-vital', 'marriage', 'license'), 'marriage license');
  assert.equal(nounAfterLoad('no-skifteprotokoll', 'estate'), 'estate entry');
  assert.equal(nounAfterLoad('no-tingbok', 'land dispute'), 'land dispute entry');
  assert.equal(nounAfterLoad('no-tingbok', 'court matter'), 'court matter entry');
  assert.equal(nounAfterLoad('se-sockenstamma', 'parish meeting record'), 'parish meeting entry');
  assert.equal(nounAfterLoad('se-lantmateriet', 'croft transfer'), 'croft transfer entry');
  assert.equal(nounAfterLoad('se-lantmateriet', 'signatory'), 'signatory entry');
  assert.equal(nounAfterLoad('se-folkrakning', 'record'), 'census entry');
  assert.equal(nounAfterLoad('us-federal-census', 'record'), 'census entry');
  assert.equal(nounAfterLoad('se-husforhor', 'record'), 'household examination entry');
  assert.equal(nounAfterLoad('no-klokkerbok', 'baptism entry'), 'baptism entry', 'a current noun is kept');
});

test('a saved noun the record type no longer lists resets to its default; the copy form starts at original', () => {
  const saved = {
    current: 'se-dopbok',
    drafts: {
      'se-dopbok': { subject: { noun: 'christening' } },
      'pp-register': { subject: { noun: '' } },
      'se-dodbok': { subject: { noun: 'burial entry', copy: 'transcript' } },
      'se-husforhor': { subject: { noun: 'household', copy: 'photocopy' } },
    },
  };
  const { drafts } = loadState(memory({ [STORE_KEY]: JSON.stringify(saved) }), recordById);
  assert.equal(drafts['se-dopbok'].subject.noun, 'birth and baptism entry');
  assert.equal(drafts['se-dopbok'].subject.copy, '');
  assert.equal(drafts['pp-register'].subject.noun, 'directory entry');
  assert.deepEqual([drafts['se-dodbok'].subject.noun, drafts['se-dodbok'].subject.copy], ['burial entry', 'transcript']);
  assert.equal(drafts['se-husforhor'].subject.copy, '');
});

test('a newspaper draft\'s saved "What the item says" text loads as Cited for', () => {
  const saved = {
    current: 'us-newspaper',
    drafts: {
      'us-newspaper': { values: { paper: 'Warren Sheaf', details: 'marriage date and location' } },
      'us-church': { values: { details: 'death and burial of Emma Söderström' } },
    },
  };
  const { drafts } = loadState(memory({ [STORE_KEY]: JSON.stringify(saved) }), recordById);
  assert.deepEqual([drafts['us-newspaper'].values.citedFor, drafts['us-newspaper'].values.details], ['marriage date and location', '']);
  assert.deepEqual([drafts['us-church'].values.citedFor, drafts['us-church'].values.details], ['', 'death and burial of Emma Söderström'],
    'entry details stay where the record type still has them');
});

test('storage that throws is survivable', () => {
  const broken = { getItem() { throw new Error('denied'); }, setItem() { throw new Error('denied'); } };
  assert.equal(loadState(broken, recordById), null);
  assert.equal(saveState(broken, { current: 'no-klokkerbok', drafts: {} }), false);
  assert.equal(loadState(null, recordById), null);
});

test('a kept draft comes back with its inputs, without output edits, and with renamed nouns mapped', () => {
  const dop = recordById('se-dopbok');
  const kept = { values: { parish: 'Vimmerby', vol: 'C:8', page: '45', gone: 'x' }, subject: { name: 'Anders Johan', noun: 'birth and baptism entry', which: 'b. 1868' },
    confidence: 'Very High', variant: '', overrides: { page: 'edited' } };
  const d = restoreDraft(dop, kept);
  assert.equal(d.type, 'se-dopbok');
  assert.deepEqual([d.values.parish, d.values.vol, d.values.page, d.subject.name, d.subject.which, d.confidence], ['Vimmerby', 'C:8', '45', 'Anders Johan', 'b. 1868', 'Very High']);
  assert.equal('gone' in d.values, false);
  assert.deepEqual(d.overrides, {});
  assert.equal(buildOutputs(dop, d).page, 'p. 45, no. ⟦Entry no.⟧, Anders Johan (b. 1868) birth and baptism entry');
  const vital = recordById('us-vital');
  assert.equal(restoreDraft(vital, { subject: { noun: 'marriage' }, variant: 'license' }).subject.noun, 'marriage license');
});
