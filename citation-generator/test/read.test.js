import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readCitation, readByFrn, readLoosely } from '../src/read.js';
import { RECORDS as ALL_RECORDS, recordById } from '../src/records/index.js';
import { newDraft, draftFromExample, buildOutputs, setVariant, resolveType, usesDetails } from '../src/engine.js';
import { hasGap } from '../src/template.js';

const RECORDS = ALL_RECORDS.filter(r => r.chapter !== 'ge');
const built = (type, draft) => buildOutputs(type, draft, { legacy: true });
const cite = o => ({ page: o.page, frn: o.frn, srn: o.srn, title: o.title, abbrev: o.abbrev, author: o.author, pubinfo: o.pubinfo, call: o.callNumber });
const rebuilt = read => built(recordById(read.type), read.draft);
const same = (a, b) => ['page', 'frn', 'srn'].every(k => a[k] === b[k]);
const complete = o => !['page', 'frn', 'srn'].some(k => hasGap(o[k]));

/** A draft with every input of the page form filled, to read back. */
function filledDraft(type, variant) {
  const d = newDraft(type);
  if (variant) setVariant(type, d, variant);
  const t = resolveType(type, d);
  for (const [key] of [...type.source, ...(t.citation || []), ...(type.note || [])]) d.values[key] = `${key} Val 1901`;
  Object.assign(d.values, { page: '57', image: '62', eventYear: '1901', url: 'https://example.org/img/1', accessed: '1 May 2026', citedFor: 'her birth date' });
  if (usesDetails(type)) d.values.details = 'daughter of Per and Kari, born at Vik';
  for (const [key, value] of [['platform', 'Ancestry'], ['archive', 'Archive Val'], ['custodian', 'Holder Val'], ['custplace', 'Place Val']]) if (!d.values[key]) d.values[key] = value;
  Object.assign(d.subject, { name: 'Anna Maria Berg', which: 'b. 1801', says: 'widow' });
  return d;
}

test('every worked example reads back into a draft that rebuilds it', () => {
  let read = 0;
  for (const type of RECORDS) {
    for (const claim of type.examples) {
      const o = built(type, draftFromExample(type, claim));
      if (!complete(o)) continue;
      const got = readCitation(cite(o), type.id);
      assert.ok(got?.exact, `${type.id} ${claim.guide}`);
      assert.equal(got.type, type.id, `${type.id} ${claim.guide}`);
      assert.ok(same(rebuilt(got), o), `${type.id} ${claim.guide}`);
      read++;
    }
  }
  assert.ok(read >= 25, `only ${read} examples were complete`);
});

test('every record type and page form reads back, with page, image, subject, and access date', () => {
  for (const type of RECORDS) {
    for (const variant of type.pageVariants ? type.pageVariants.map(v => v.key) : ['']) {
      const d = filledDraft(type, variant);
      const o = built(type, d);
      const got = readCitation(cite(o), type.id);
      assert.ok(got?.exact, `${type.id} ${variant}`);
      assert.ok(same(rebuilt(got), o), `${type.id} ${variant}`);
      const g = got.draft;
      assert.equal(g.subject.name || '', d.subject.name && o.page.includes(d.subject.name) ? d.subject.name : g.subject.name || '', `${type.id} ${variant} name`);
      for (const key of ['page', 'image', 'accessed', 'url', 'citedFor']) {
        if (o.frn.includes(d.values[key]) || o.page.includes(d.values[key])) assert.equal(g.values[key], d.values[key], `${type.id} ${variant} ${key}`);
      }
    }
  }
});

test('without a hint the reader finds the record type itself', () => {
  const klokk = recordById('no-klokkerbok');
  const o = built(klokk, draftFromExample(klokk, klokk.examples[0]));
  const got = readCitation(cite(o));
  assert.equal(got.type, 'no-klokkerbok');
  assert.deepEqual([got.draft.values.page, got.draft.values.image, got.draft.values.entry, got.draft.subject.name, got.draft.values.accessed], ['57', '62', '21', 'Thor Emil', '17 April 2026']);
});

test('the SRN tells which entry from what the source says', () => {
  const dop = recordById('se-dopbok');
  const d = filledDraft(dop, '');
  Object.assign(d.subject, { which: 'b. 1801, at Vik', says: 'widow', evidence: 'stated age 40' });
  const o = built(dop, d);
  const got = readCitation(cite(o), 'se-dopbok');
  assert.deepEqual([got.draft.subject.which, got.draft.subject.says], ['b. 1801, at Vik', 'widow, stated age 40']);
  assert.ok(same(rebuilt(got), o));
});

test('a citation with a note edited by hand reads closely; one written another way not at all', () => {
  const klokk = recordById('no-klokkerbok');
  const o = built(klokk, draftFromExample(klokk, klokk.examples[0]));
  const close = readCitation({ ...cite(o), srn: 'Eidsvoll klokkerbok, p. 57, edited by hand.' });
  assert.equal(readCitation({ ...cite(o), frn: 'Eidsvoll prestekontor, edited by hand.' }), null);
  assert.equal(close.exact, false);
  assert.equal(close.type, 'no-klokkerbok');
  assert.deepEqual([close.draft.values.page, close.draft.values.entry, close.draft.subject.name, close.draft.values.accessed], ['57', '21', 'Thor Emil', '17 April 2026']);
  assert.equal(readCitation(cite(o)).exact, true);
  assert.equal(readCitation({ ...cite(o), page: `${o.page}, edited`, srn: 'Edited.' }), null);
  assert.equal(readCitation({ page: 'Page 4', frn: 'Something.', srn: 'Else.' }), null);
  assert.equal(readCitation({ page: '', frn: '', srn: '' }), null);
});

test('loosely, a guide-shaped citation still gives its page, image, name, URL, and access date', () => {
  assert.deepEqual(readLoosely({ page: 'death, p. 5 (image 7), Mike death entry', frn: 'Church, register; digital image, Ancestry (https://www.ancestry.com/x : accessed 3 May 2026).' }),
    { page: '5', image: '7', name: 'Mike', url: 'https://www.ancestry.com/x', accessed: '3 May 2026' });
  assert.deepEqual(readLoosely({ page: 'image 12, no. 4, Per Ola Berg (b. 1801) household', frn: '' }), { page: '', image: '12', name: 'Per Ola Berg' });
  assert.deepEqual(readLoosely({ page: 'roll 1, ED 1, Ånes Åsmund in Berg household', frn: 'x' }), { name: 'Ånes Åsmund' });
  assert.deepEqual(readLoosely({ page: 'roll 1, ED 1', frn: 'x' }), {});
});

test('a citation whose page string was edited by hand still gives its record type and the FRN\'s and SRN\'s fields', () => {
  const church = recordById('us-church');
  const d = newDraft(church);
  Object.assign(d.values, { church: 'First Lutheran Church', town: 'Alma', county: 'Marshall', state: 'Minnesota', register: 'death and burial register',
    page: '5', image: '7', details: 'aged 80', url: 'https://www.ancestry.com/x', accessed: '9 October 2026' });
  Object.assign(d.subject, { name: 'Mike', noun: church.nouns[0] });
  const o = built(church, d);
  const edited = { ...cite(o), page: o.page.replace(church.nouns[0], 'death entry') };
  assert.equal(readCitation(edited), null);
  const got = readByFrn(edited);
  assert.equal(got.type, 'us-church');
  assert.equal(got.exact, false);
  assert.deepEqual([got.draft.values.register, got.draft.values.page, got.draft.values.image, got.draft.values.details, got.draft.values.accessed, got.draft.subject.name, got.draft.subject.noun],
    ['death and burial register', '5', '7', 'aged 80', '9 October 2026', 'Mike', church.nouns[0]]);
  assert.equal(readByFrn({ frn: 'Written some other way entirely.' }), null);
});
