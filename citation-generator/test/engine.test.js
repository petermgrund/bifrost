import { test } from 'node:test';
import assert from 'node:assert/strict';
import { newDraft, draftFromExample, subjectOf, srnSubjectOf, recordNoun, buildOutputs, inputFields, resolveType, usesDetails, usesToken, ruleRef, setVariant, labeler, pageLocators, nextCitationDraft, OUTPUT_GROUPS, TEMPLATE_KEYS } from '../src/engine.js';
import { plain, fill } from '../src/template.js';
import { RECORDS } from '../src/records/index.js';

// A small made-up record type, so the engine is tested on its own.
const PARISH = {
  id: 'test-parish', chapter: 'se', group: 'Test', name: 'Test parish register',
  source: [['parish', 'Parish'], ['vol', 'Volume'], ['call', 'Call number']],
  citation: [['page', 'Page'], ['image', 'Image']],
  note: [['citing', 'Citing']],
  nouns: ['household', 'census entry'],
  defaults: { platform: 'Riksarkivet', archive: 'Värmlandsarkiv' },
  confidence: 'High', doctype: 'enumeration',
  derive: v => ({ upper: String(v.parish || '').toUpperCase() }),
  title: 'Sweden, {parish}, {vol}',
  abbrev: '{upper} {vol}',
  author: '{parish} församling',
  page: 'p. {page}« (image {image})», {subject}',
  frn: '{author}, vol. {vol}, p. {page}, {entryof}«, {details}»; {medium}, {platform} ({url} : accessed {accessed}); citing {archive}«, {citing}».',
  srn: '{parish} {vol}, p. {page}, {subject}.',
  pageVariants: undefined,
  pins: {},
  examples: [],
};
const WITH_VARIANTS = {
  ...PARISH, id: 'test-vital',
  pageVariants: [
    { key: 'certificate', label: 'Certificate', citation: [['cert', 'Certificate no.']], nouns: ['death certificate'], page: 'certificate no. {cert}, {subject}' },
    { key: 'license', label: 'Marriage license', citation: [['license', 'License no.']], nouns: ['marriage license'], page: 'license no. {license}, {subject}' },
  ],
};
const filled = () => draftFromExample(PARISH, {
  guide: 'Test', inputs: {
    parish: 'Norra Ny', vol: 'AI:11', call: 'SE/VA/13398/A I/11', page: '8', image: '19',
    name: 'Per Persson', noun: 'household', url: 'https://sok.riksarkivet.se/x', accessed: '20 April 2026', eventYear: '1812–1820',
  },
});

test('a new draft takes its defaults from the record type', () => {
  const d = newDraft(PARISH);
  assert.equal('holder' in d, false);
  assert.equal(d.confidence, 'High');
  assert.equal(d.subject.noun, 'household');
  assert.deepEqual(Object.keys(d.values), [
    'parish', 'vol', 'call', 'page', 'image', 'citing', 'url', 'accessed', 'eventYear', 'details', 'comment', 'citedFor',
    'platform', 'pubmedium', 'archive', 'custodian', 'custplace',
  ]);
  assert.deepEqual([d.values.platform, d.values.pubmedium, d.values.archive, d.values.custodian, d.values.custplace], ['Riksarkivet', 'Digital images', 'Värmlandsarkiv', '', '']);
  assert.equal(newDraft({ ...PARISH, defaults: { pubmedium: 'Database' } }).values.pubmedium, 'Database');
  assert.equal(newDraft({ ...PARISH, defaults: undefined }).values.platform, '');
});

test('draftFromExample routes inputs to values, subject, confidence, and variant', () => {
  const d = draftFromExample(WITH_VARIANTS, { guide: 'X', citation: 2, inputs: { parish: 'P', name: 'N', archive: 'A', confidence: 'Low', variant: 'license' } });
  assert.equal(d.values.parish, 'P');
  assert.equal(d.subject.name, 'N');
  assert.equal(d.values.archive, 'A');
  assert.equal(d.confidence, 'Low');
  assert.equal(d.variant, 'license');
  assert.equal(d.example, 'X · citation 2');
});

test('builds every Source, Citation, note, and Paperless field', () => {
  const o = buildOutputs(PARISH, filled());
  assert.deepEqual(Object.keys(o).sort(), OUTPUT_GROUPS.flatMap(g => g.fields.map(([key]) => key)).sort());
  assert.equal(o.title, 'Sweden, Norra Ny, AI:11');
  assert.equal(o.abbrev, 'NORRA NY AI:11');
  assert.equal(o.pubinfo, 'Digital images, Riksarkivet (https://sok.riksarkivet.se).');
  assert.equal(o.author, 'Norra Ny församling');
  assert.equal(o.callNumber, 'SE/VA/13398/A I/11');
  assert.equal(o.page, 'p. 8 (image 19), Per Persson household');
  assert.equal(o.confidence, 'High');
  assert.equal(o.frn, 'Norra Ny församling, vol. AI:11, p. 8, household of Per Persson; digital image, Riksarkivet (https://sok.riksarkivet.se/x : accessed 20 April 2026); citing Värmlandsarkiv.');
  assert.equal(o.srn, 'Norra Ny AI:11, p. 8, Per Persson household.');
  assert.equal(o.plTitle, 'Per Persson household 1812–1820');
  assert.equal(o.plDoctype, 'enumeration');
  assert.equal(o.plDateMeaning, 'event');
  assert.equal(o.plCorrespondent, 'Riksarkivet');
  assert.equal(o.plSourceUrl, 'https://sok.riksarkivet.se/x');
});

test('typed values are trimmed; missing ones become labelled gaps', () => {
  const d = filled();
  d.values.parish = '  Norra Ny  ';
  d.values.vol = '';
  const o = buildOutputs(PARISH, d);
  assert.equal(plain(o.title), 'Sweden, Norra Ny, [Volume]');
});

test('subject: parentheticals in 1-2-3 order inside one set of parentheses', () => {
  const s = { name: 'Per Persson', noun: 'household', which: 'b. 1773', says: 'retired soldier', evidence: 'birth year inferred from age' };
  assert.equal(subjectOf(PARISH, s), 'Per Persson (b. 1773, retired soldier, birth year inferred from age) household');
});

test('subject: a non-head household member', () => {
  assert.equal(subjectOf(PARISH, { name: 'Karen', noun: 'household', nonHead: true, head: 'Hansen' }), 'Karen in Hansen household');
  assert.equal(plain(subjectOf(PARISH, { name: 'Karen', noun: 'household', nonHead: true, head: '' })), 'Karen in [Head] household');
});

test('subject: parentheses after the record noun', () => {
  const s = { name: 'John Grund', noun: 'birth certificate', says: 'delayed registration, 1942', afterNoun: true };
  assert.equal(subjectOf(PARISH, s), 'John Grund birth certificate (delayed registration, 1942)');
});

test('subject: a missing name is a gap; an optional subject can be empty', () => {
  assert.equal(plain(subjectOf(PARISH, { name: '', noun: 'household' })), '[Name] household');
  assert.equal(subjectOf({ ...PARISH, optionalSubject: true }, { name: '', noun: '' }), '');
});

test('output fields: Source, Citation, Citation note, and Paperless scan', () => {
  assert.deepEqual(OUTPUT_GROUPS.map(g => [g.name, g.fields.map(([, label]) => label)]), [
    ['Source', ['Title', 'Author', 'Abbrev', 'Pubinfo', 'Call number']],
    ['Citation', ['Page', 'Confidence']],
    ['Citation note', ['FRN', 'SRN']],
    ['Paperless scan', ['Title', 'Document type', 'Date meaning', 'Correspondent', 'Source URL']],
  ]);
});

test('platform and archive are typed values: the FRN and Paperless correspondent use them', () => {
  const d = filled();
  d.values.platform = ' Svenska kyrkan ';
  d.values.archive = 'Riksarkivet';
  const o = buildOutputs(PARISH, d);
  assert.match(o.frn, /; digital image, Svenska kyrkan \(https:\/\/sok\.riksarkivet\.se\/x : accessed 20 April 2026\); citing Riksarkivet\.$/);
  assert.equal(o.plCorrespondent, 'Svenska kyrkan');
  d.values.platform = '';
  d.values.archive = '';
  assert.match(plain(buildOutputs(PARISH, d).frn), /digital image, \[Platform\] .*citing \[Archive\]\.$/);
  assert.equal(buildOutputs(PARISH, d).plCorrespondent, '');
});

test('custodian and custplace fill the held-by clause', () => {
  const type = { ...PARISH, defaults: { custodian: 'Peter Grund', custplace: 'Duluth, Minnesota' }, frn: 'Letter; privately held by {custodian}«, {custplace}».' };
  const d = newDraft(type);
  assert.equal(buildOutputs(type, d).frn, 'Letter; privately held by Peter Grund, Duluth, Minnesota.');
  d.values.custplace = '';
  d.values.custodian = '';
  assert.equal(plain(buildOutputs(type, d).frn), 'Letter; privately held by [Held by].');
});

test("an empty custplace reads [Holder's place], apart from a record type's own Place input", () => {
  const type = {
    ...PARISH, source: [['city', 'Place']], citation: [], note: [], defaults: {},
    frn: '{name} ({city}), held by {custodian}, {custplace}.',
  };
  assert.equal(plain(buildOutputs(type, newDraft(type)).frn), "[Name] ([Place]), held by [Held by], [Holder's place].");
});

test('next citation keeps the Source inputs, the reference values, and Source overrides', () => {
  const d = filled();
  Object.assign(d.values, { platform: 'ArkivDigital', archive: 'Riksarkivet', custodian: 'Siw', custplace: 'Ambjörby', citing: 'x', details: 'y' });
  d.overrides = { title: 'T', author: 'A', abbrev: 'B', callNumber: 'C', page: 'P', frn: 'F', plTitle: 'PT' };
  d.confidence = 'Low';
  d.subject.which = 'b. 1773';
  const next = nextCitationDraft(PARISH, d);
  assert.deepEqual(
    [next.values.parish, next.values.vol, next.values.call, next.values.platform, next.values.archive, next.values.custodian, next.values.custplace],
    ['Norra Ny', 'AI:11', 'SE/VA/13398/A I/11', 'ArkivDigital', 'Riksarkivet', 'Siw', 'Ambjörby'],
  );
  assert.deepEqual([next.values.page, next.values.image, next.values.url, next.values.citing, next.values.details], ['', '', '', '', '']);
  assert.deepEqual(next.overrides, { title: 'T', author: 'A', abbrev: 'B', callNumber: 'C' });
  assert.equal(next.confidence, 'High');
  assert.equal(next.subject.name, '');
  assert.equal(next.subject.which, '');
  assert.equal(next.example, '');
  assert.equal(d.values.page, '8', 'the original draft is left alone');
});

test('next citation keeps the page form and takes the record noun from it', () => {
  const d = newDraft(WITH_VARIANTS);
  setVariant(WITH_VARIANTS, d, 'license');
  d.values.license = '12';
  d.subject.name = 'John Doe';
  const next = nextCitationDraft(WITH_VARIANTS, d);
  assert.equal(next.variant, 'license');
  assert.equal(next.subject.noun, 'marriage license');
  assert.equal(next.subject.name, '');
  assert.equal(nextCitationDraft(WITH_VARIANTS, newDraft(WITH_VARIANTS)).subject.noun, 'death certificate');
});

test('overrides replace built values, and an Author override flows into the FRN', () => {
  const d = filled();
  d.overrides.author = 'Norra Ny parish';
  d.overrides.title = 'My title';
  const o = buildOutputs(PARISH, d);
  assert.equal(o.title, 'My title');
  assert.match(o.frn, /^Norra Ny parish, vol\. AI:11/);
});

test('the comment is appended after the FRN', () => {
  const d = filled();
  d.values.comment = 'Two hands.';
  assert.match(buildOutputs(PARISH, d).frn, /citing Värmlandsarkiv\. Two hands\.$/);
});

test('newDraft takes its default noun from the first page variant', () => {
  assert.equal(newDraft(WITH_VARIANTS).subject.noun, 'death certificate');
});

test('setVariant resets the noun when it does not belong to the new form', () => {
  const d = newDraft(WITH_VARIANTS);
  assert.equal(d.subject.noun, 'death certificate');
  setVariant(WITH_VARIANTS, d, 'license');
  assert.equal(d.variant, 'license');
  assert.equal(d.subject.noun, 'marriage license');
});

test('setVariant keeps the noun when it is still valid for the new form', () => {
  const type = { ...WITH_VARIANTS, pageVariants: [
    WITH_VARIANTS.pageVariants[0],
    { ...WITH_VARIANTS.pageVariants[1], nouns: ['marriage license', 'death certificate'] },
  ] };
  const d = newDraft(type);
  d.subject.noun = 'death certificate';
  setVariant(type, d, 'license');
  assert.equal(d.variant, 'license');
  assert.equal(d.subject.noun, 'death certificate');
});

test('page variants switch the page template, nouns, and inputs', () => {
  const d = newDraft(WITH_VARIANTS);
  assert.equal(d.variant, 'certificate');
  d.variant = 'license';
  d.values.license = '12';
  Object.assign(d.subject, { name: 'Larsson-Söderström', noun: 'marriage license' });
  assert.equal(buildOutputs(WITH_VARIANTS, d).page, 'license no. 12, Larsson-Söderström marriage license');
  assert.deepEqual(resolveType(WITH_VARIANTS, d).nouns, ['marriage license']);
  assert.deepEqual(inputFields(WITH_VARIANTS).map(([key]) => key), ['parish', 'vol', 'call', 'page', 'image', 'cert', 'license', 'citing']);
});

test('Paperless title: disambiguator, non-head, and the page string\'s record noun', () => {
  const d = filled();
  d.subject.which = 'b. 1773';
  assert.equal(buildOutputs(PARISH, d).plTitle, 'Per Persson (b. 1773) household 1812–1820');
  Object.assign(d.subject, { which: '', nonHead: true, head: 'Hansen' });
  assert.equal(buildOutputs(PARISH, d).plTitle, 'Per Persson in Hansen household 1812–1820');
  d.subject.copy = 'transcript';
  assert.equal(buildOutputs(PARISH, d).plTitle, 'Per Persson in Hansen household transcript 1812–1820');
  Object.assign(d.subject, { nonHead: false, copy: '', noun: 'marriage entry', name: 'Larsson-Söderström' });
  d.values.eventYear = '1877';
  assert.equal(buildOutputs(PARISH, d).plTitle, 'Larsson-Söderström marriage entry 1877');
  assert.equal(buildOutputs({ ...PARISH, paperlessTitle: '{parish} scan' }, d).plTitle, 'Norra Ny scan');
});

test('labeler uses eventYearLabel and detailsLabel for the eventYear and details gaps', () => {
  const L = labeler({ ...PARISH, eventYearLabel: 'Received (Paperless)' });
  assert.equal(fill('{eventYear}', {}, L), '⟦Received (Paperless)⟧');
});

test('page locators: page and image', () => {
  assert.deepEqual(pageLocators('57', '62'), { pageLoc: 'p. 57 (image 62)', pageRef: 'p. 57' });
});

test('page locators: page only', () => {
  assert.deepEqual(pageLocators('57', ''), { pageLoc: 'p. 57', pageRef: 'p. 57' });
});

test('page locators: image only gives the image number, in lower case', () => {
  assert.deepEqual(pageLocators('', '62'), { pageLoc: 'image 62', pageRef: 'image 62' });
});

test('page locators: neither page nor image is a gap', () => {
  const gapText = '⟦Page or image⟧';
  assert.deepEqual(pageLocators('', ''), { pageLoc: gapText, pageRef: gapText });
  assert.deepEqual(pageLocators(undefined, undefined), { pageLoc: gapText, pageRef: gapText });
});

test('page locator tokens are available to every template and use the trimmed values', () => {
  const type = { ...PARISH, page: '{pageLoc}, {subject}', frn: '{pageLoc}; {pageRef}.', srn: '{pageRef}.' };
  const d = filled();
  d.values.page = '  ';
  d.values.image = ' 19 ';
  const o = buildOutputs(type, d);
  assert.equal(o.page, 'image 19, Per Persson household');
  assert.equal(o.frn, 'image 19; image 19.');
  assert.equal(o.srn, 'image 19.');
  d.values.image = '';
  assert.equal(plain(buildOutputs(type, d).page), '[Page or image], Per Persson household');
});

test('usesToken looks through every template, including page variants', () => {
  assert.equal(usesToken(PARISH, 'archive'), true);
  assert.equal(usesToken(PARISH, 'custodian'), false);
  assert.equal(usesToken(PARISH, 'arch'), false);
  const variantOnly = { ...WITH_VARIANTS, pageVariants: [...WITH_VARIANTS.pageVariants, { key: 'x', label: 'X', page: 'held by {custodian}' }] };
  assert.equal(usesToken(variantOnly, 'custodian'), true);
});

test('usesDetails and ruleRef', () => {
  assert.equal(usesDetails(PARISH), true);
  assert.equal(usesDetails({ ...PARISH, frn: 'No details here.' }), false);
  assert.equal(usesDetails({ ...PARISH, frn: 'x', detailsLabel: 'Topic' }), true);
  assert.equal(ruleRef(PARISH, '§4'), 'B.2 §4');
  assert.equal(ruleRef(PARISH, 'A8'), 'A8');
});

test('record noun: a copy or index replaces a final "entry", follows any other noun, and needs a noun', () => {
  assert.equal(recordNoun('birth and baptism entry', ''), 'birth and baptism entry');
  assert.equal(recordNoun('birth and baptism entry', 'index entry'), 'birth and baptism index entry');
  assert.equal(recordNoun('birth and baptism entry', 'transcript'), 'birth and baptism transcript');
  assert.equal(recordNoun('household examination entry', 'extract'), 'household examination extract');
  assert.equal(recordNoun('death certificate', 'abstract'), 'death certificate abstract');
  assert.equal(recordNoun('WWII draft card', 'index entry'), 'WWII draft card index entry');
  assert.equal(recordNoun('household', 'transcript'), 'household transcript');
  assert.equal(recordNoun('entry', 'transcript'), 'transcript');
  assert.equal(recordNoun('entry', 'index entry'), 'index entry');
  assert.equal(recordNoun('', 'transcript'), '');
  assert.equal(recordNoun(' household ', undefined), 'household');
});

test('subject: the record noun in its copy form, and the non-head wording with one', () => {
  assert.equal(subjectOf(PARISH, { name: 'Per Persson', noun: 'household', copy: 'transcript' }), 'Per Persson household transcript');
  assert.equal(subjectOf(PARISH, { name: 'Karen', noun: 'household', copy: 'transcript', nonHead: true, head: 'Hansen' }), 'Karen in Hansen household transcript');
  assert.equal(subjectOf(PARISH, { name: 'Per Persson', noun: '', copy: 'transcript' }), 'Per Persson');
});

test('SRN subject: keeps only the which-entry disambiguator', () => {
  const s = { name: 'Per Persson', noun: 'household', which: 'b. 1773', says: 'retired soldier', evidence: 'birth year inferred from age' };
  assert.equal(srnSubjectOf(PARISH, s), 'Per Persson (b. 1773) household');
  assert.equal(srnSubjectOf(PARISH, { ...s, which: '' }), 'Per Persson household');
  assert.equal(srnSubjectOf(PARISH, { name: 'Karen', noun: 'household', says: 'tjenestepige', nonHead: true, head: 'Hansen' }), 'Karen in Hansen household');
  const allotment = { name: 'Marit Andersdotter', noun: 'land allotment entry', says: 'Lott A', afterNoun: true };
  assert.equal(subjectOf(PARISH, allotment), 'Marit Andersdotter land allotment entry (Lott A)');
  assert.equal(srnSubjectOf(PARISH, allotment), 'Marit Andersdotter land allotment entry');
});

test('{medium}: a database for an index entry or transcript, else a digital image', () => {
  const type = { ...PARISH, srn: '{medium}; {noun}; {entryof}.' };
  const d = filled();
  const srnWith = (noun, copy) => { Object.assign(d.subject, { noun, copy }); return buildOutputs(type, d).srn; };
  assert.equal(srnWith('household', ''), 'digital image; household; household of Per Persson.');
  assert.equal(srnWith('household', 'index entry'), 'database; household index entry; household index entry of Per Persson.');
  assert.equal(srnWith('household', 'transcript'), 'database; household transcript; household transcript of Per Persson.');
  assert.equal(srnWith('household', 'extract'), 'digital image; household extract; household extract of Per Persson.');
  assert.equal(srnWith('household', 'abstract'), 'digital image; household abstract; household abstract of Per Persson.');
  assert.match(plain(srnWith('', 'transcript')), /^digital image; \[Record noun\]; Per Persson\.$/);
  Object.assign(d.subject, { noun: 'census entry', copy: 'transcript' });
  assert.match(buildOutputs(PARISH, d).frn, /; database, Riksarkivet \(https:\/\/sok\.riksarkivet\.se\/x : accessed 20 April 2026\);/);
});

test('a new draft and the next citation start as an original; switching the page form keeps the copy form', () => {
  assert.equal(newDraft(PARISH).subject.copy, '');
  const d = newDraft(WITH_VARIANTS);
  d.subject.copy = 'abstract';
  setVariant(WITH_VARIANTS, d, 'license');
  assert.equal(d.subject.copy, 'abstract');
  assert.equal(nextCitationDraft(WITH_VARIANTS, d).subject.copy, '');
});

test('every record type cites its image as {medium}, never as a literal "digital image"', () => {
  for (const r of RECORDS) {
    for (const t of [r, ...(r.pageVariants || [])]) {
      for (const key of TEMPLATE_KEYS) assert.doesNotMatch(t[key] || '', /digital image, \{platform\}/, `${r.id}.${key}`);
    }
  }
});

test("a form's own date gives the event year, so a year typed earlier cannot linger", () => {
  const type = { ...PARISH, source: [...PARISH.source, ['signed', 'Date signed']], eventDate: 'signed', srn: '{parish} ({eventYear}).' };
  const d = filled();
  d.values.eventYear = '1894';
  d.values.signed = '12 March 1897';
  const o = buildOutputs(type, d);
  assert.equal(o.srn, 'Norra Ny (1897).');
  assert.equal(o.plTitle, 'Per Persson household 1897');
  d.values.signed = '';
  assert.equal(plain(buildOutputs(type, d).plTitle), 'Per Persson household [Date signed]');
  assert.equal(buildOutputs(PARISH, d).plTitle, 'Per Persson household 1894', 'without eventDate the typed Event year is used');
});

test('Pubinfo: medium, platform, and the A10 homepage, or the record type\'s own imprint', () => {
  const d = filled();
  d.values.pubmedium = 'Database with images';
  assert.equal(buildOutputs(PARISH, d).pubinfo, 'Database with images, Riksarkivet (https://sok.riksarkivet.se).');
  d.values.platform = 'Svenska kyrkan';
  assert.equal(plain(buildOutputs(PARISH, d).pubinfo), 'Database with images, Svenska kyrkan ([Platform homepage]).');
  d.values.platform = '';
  assert.equal(buildOutputs(PARISH, d).pubinfo, '', 'no platform, no genealogical Pubinfo');
  const imprint = { ...PARISH, pubinfo: '{parish}: Self, 1900.« {pubmedium}, {platform} ({home}).»' };
  assert.equal(buildOutputs(imprint, d).pubinfo, 'Norra Ny: Self, 1900.');
  d.values.platform = 'Riksarkivet';
  assert.equal(buildOutputs(imprint, d).pubinfo, 'Norra Ny: Self, 1900. Database with images, Riksarkivet (https://sok.riksarkivet.se).');
  assert.equal(buildOutputs({ ...PARISH, pubinfo: '' }, d).pubinfo, '', 'an empty template leaves Pubinfo blank');
  d.overrides.pubinfo = 'My imprint.';
  assert.equal(buildOutputs(PARISH, d).pubinfo, 'My imprint.');
});

test('Microfilm: the film\'s maker in Pubinfo, the film in place of the digital image, and no correspondent', () => {
  const type = { ...PARISH, frnMicrofilm: '{author}, vol. {vol}, p. {page}, {entryof}; {archive} microfilm {call}.' };
  const d = filled();
  d.values.pubmedium = 'Microfilm';
  const o = buildOutputs(type, d);
  assert.equal(o.pubinfo, 'Microfilm, Värmlandsarkiv.');
  assert.equal(o.frn, 'Norra Ny församling, vol. AI:11, p. 8, household of Per Persson; Värmlandsarkiv microfilm SE/VA/13398/A I/11.');
  assert.equal(o.plCorrespondent, '');
  d.values.archive = '';
  assert.equal(plain(buildOutputs(type, d).pubinfo), 'Microfilm, [Archive].');
  assert.match(buildOutputs(PARISH, { ...d, values: { ...d.values, archive: 'Värmlandsarkiv' } }).frn, /; digital image, Riksarkivet \(/, 'without a film form the FRN keeps the digital image');
});
