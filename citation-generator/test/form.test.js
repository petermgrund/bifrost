import { test } from 'node:test';
import assert from 'node:assert/strict';
import { recordGroups, sourceRows, referenceRows, citationRows, noteRows, outputRows, exampleNote, copyAllText, repositoryName, paperlessMatch } from '../src/form.js';
import { RECORDS, recordById } from '../src/records/index.js';
import { newDraft, draftFromExample, buildOutputs } from '../src/engine.js';

const klokk = recordById('no-klokkerbok');
const example = () => draftFromExample(klokk, klokk.examples[0]);
const paths = rows => rows.map(r => r.path);
const row = (rows, path) => rows.find(r => r.path === path);
const allRows = (type, draft) => [...sourceRows(type, draft), ...referenceRows(type, draft), ...citationRows(type, draft), ...noteRows(type, draft)];

test('record types group by chapter and filter by name or group', () => {
  const groups = recordGroups(RECORDS);
  assert.deepEqual(groups.map(g => [g.label, g.records.length]), [['Norwegian', 9], ['Swedish', 9], ['US', 13], ['Published & personal', 13]]);
  const census = recordGroups(RECORDS, 'census').flatMap(g => g.records.map(r => r.name));
  assert.ok(census.includes('Federal census'));
  assert.ok(!census.includes('Klokkerbok'));
  assert.deepEqual(recordGroups(RECORDS, 'zzzz'), []);
});

test('the Source step asks for every source field; entry details appear only where the FRN has them', () => {
  assert.deepEqual(paths(sourceRows(klokk, newDraft(klokk))), klokk.source.map(([key]) => `values.${key}`));
  assert.equal(row(sourceRows(klokk, newDraft(klokk)), 'values.call').mono, true);
  assert.ok(paths(noteRows(klokk, newDraft(klokk))).includes('values.details'));
  const card = recordById('us-draft-card');
  assert.ok(!paths(noteRows(card, newDraft(card))).includes('values.details'));
});

test('the reference values are pre-filled and offer the platform and archive lists', () => {
  const rows = referenceRows(klokk, newDraft(klokk));
  assert.deepEqual(paths(rows), ['values.platform', 'values.pubmedium', 'values.archive']);
  assert.equal(row(rows, 'values.platform').value, 'Digitalarkivet');
  assert.ok(row(rows, 'values.platform').list.includes('Digitalarkivet'));
  assert.equal(row(rows, 'values.archive').value, 'Statsarkivet i Oslo');
  assert.ok(row(rows, 'values.archive').list.includes('Statsarkivet i Oslo'));
});

test('Archive shows only when a template uses {archive}, and Held by and Place only for {custodian} and {custplace}', () => {
  const folk = recordById('se-folkrakning');
  const folkRows = referenceRows(folk, newDraft(folk));
  assert.equal(row(folkRows, 'values.platform').value, 'Riksarkivet');
  assert.equal(row(folkRows, 'values.archive'), undefined);
  const bible = recordById('pp-bible');
  const bibleRows = referenceRows(bible, newDraft(bible));
  assert.equal(row(bibleRows, 'values.platform').value, '');
  assert.equal(row(bibleRows, 'values.archive'), undefined);
  assert.equal(row(bibleRows, 'values.custodian').label, 'Held by');
  assert.equal(row(bibleRows, 'values.custodian').value, 'Peter Grund');
  assert.equal(row(bibleRows, 'values.custplace').label, 'Place');
  assert.equal(row(bibleRows, 'values.custplace').value, 'Duluth, Minnesota');
  for (const r of RECORDS) assert.ok(row(referenceRows(r, newDraft(r)), 'values.platform'), r.id);
});

test('record noun is a select of the nouns for the page form, with (none) for the empty noun', () => {
  const nouns = (type, draft = newDraft(type)) => row(citationRows(type, draft), 'subject.noun')?.options ?? null;
  const dop = recordById('se-dopbok');
  assert.equal(row(citationRows(dop, newDraft(dop)), 'subject.noun').label, 'Record noun');
  assert.deepEqual(nouns(dop).map(([value]) => value), ['birth and baptism entry', 'birth entry', 'baptism entry']);
  assert.deepEqual(nouns(recordById('pp-book')), [['entry', 'entry'], ['', '(none)']]);
  const vital = recordById('us-vital');
  const license = newDraft(vital);
  license.variant = 'license';
  license.subject.noun = 'marriage license';
  assert.deepEqual(nouns(vital, license).map(([value]) => value), ['marriage license']);
  for (const id of ['us-find-a-grave', 'us-passenger-manifest', 'pp-letter', 'pp-interview']) {
    assert.equal(nouns(recordById(id)), null, `${id} has no record noun`);
  }
});

test('Original or copy follows the record noun and is hidden when the noun is empty', () => {
  const dop = recordById('se-dopbok');
  const d = newDraft(dop);
  const copy = row(citationRows(dop, d), 'subject.copy');
  assert.equal(copy.label, 'Original or copy');
  assert.equal(copy.value, '');
  assert.deepEqual(copy.options, [['', 'Original'], ['index entry', 'Index entry'], ['transcript', 'Transcript'], ['extract', 'Extract'], ['abstract', 'Abstract']]);
  const book = recordById('pp-book');
  const none = newDraft(book);
  none.subject.noun = '';
  assert.equal(row(citationRows(book, none), 'subject.copy'), undefined);
  const letter = recordById('pp-letter');
  assert.equal(row(citationRows(letter, newDraft(letter)), 'subject.copy'), undefined);
});

test('the Event year box is hidden where the form\'s own date gives the year', () => {
  const natz = recordById('us-naturalization');
  const d = newDraft(natz);
  assert.ok(row(noteRows(natz, d), 'values.eventYear'), 'the petition form asks for the year');
  d.variant = 'final';
  assert.equal(row(noteRows(natz, d), 'values.eventYear'), undefined, 'final papers take it from Date signed');
  const census = recordById('us-federal-census');
  assert.equal(row(noteRows(census, newDraft(census)), 'values.eventYear'), undefined);
});

test('the Pubinfo medium is chosen under Platform where the Pubinfo uses it', () => {
  const medium = type => row(referenceRows(type, newDraft(type)), 'values.pubmedium') ?? null;
  const folk = medium(recordById('se-folkrakning'));
  assert.deepEqual(folk.options.map(([value]) => value), ['Digital images', 'Database with images', 'Database']);
  assert.equal(folk.value, 'Database with images');
  assert.notEqual(medium(recordById('pp-book')), null, 'an online book appends the medium');
  assert.equal(medium(recordById('pp-interview')), null, 'a recorded interview has its own imprint');
});

test('Microfilm is a Pubinfo medium only where the record type can cite the film itself', () => {
  const media = type => (row(referenceRows(type, newDraft(type)), 'values.pubmedium')?.options ?? []).map(([value]) => value);
  assert.deepEqual(media(recordById('us-naturalization')), ['Digital images', 'Database with images', 'Database', 'Microfilm']);
  assert.ok(media(recordById('us-federal-census')).includes('Microfilm'));
  assert.ok(media(recordById('us-newspaper')).includes('Microfilm'));
  assert.ok(!media(recordById('se-dopbok')).includes('Microfilm'));
});

test('Archive shows where an FRN names it; a newspaper names it only on film, so shows it only then', () => {
  const paper = recordById('us-newspaper');
  const d = newDraft(paper);
  assert.equal(row(referenceRows(paper, d), 'values.archive'), undefined, 'read on Newspapers.com');
  d.values.pubmedium = 'Microfilm';
  assert.ok(row(referenceRows(paper, d), 'values.archive'), 'read on film');
  const natz = recordById('us-naturalization');
  assert.ok(row(referenceRows(natz, newDraft(natz)), 'values.archive'), 'its online FRN cites the archive too');
});

test('every record type asks what the citation is cited for, right after Confidence', () => {
  for (const type of RECORDS) {
    const p = paths(citationRows(type, newDraft(type)));
    assert.equal(p.indexOf('values.citedFor'), p.indexOf('confidence') + 1, type.id);
  }
  const e = example();
  e.values.citedFor = 'birth date';
  const o = buildOutputs(klokk, e);
  assert.equal('citedFor' in o, false);
  assert.ok(!outputRows(klokk, e, o).flatMap(g => g.rows).some(r => r.label === 'Cited for'));
  assert.doesNotMatch(copyAllText(o), /CITED FOR/);
});

test('the non-head checkbox shows only for a household', () => {
  const hfl = recordById('se-husforhor');
  const d = newDraft(hfl);
  assert.ok(row(citationRows(hfl, d), 'subject.nonHead'));
  assert.equal(row(citationRows(hfl, d), 'subject.head'), undefined);
  d.subject.nonHead = true;
  assert.equal(row(citationRows(hfl, d), 'subject.head').label, "Head's surname");
  d.subject.noun = 'household examination entry';
  assert.equal(row(citationRows(hfl, d), 'subject.nonHead'), undefined);
});

test('the parentheticals are numbered 1 to 3 and offer the chapter\'s suggestions', () => {
  const rows = citationRows(klokk, newDraft(klokk));
  assert.deepEqual(['subject.which', 'subject.says', 'subject.evidence'].map(p => row(rows, p).num), [1, 2, 3]);
  assert.ok(row(rows, 'subject.says').list.includes('tjenestepige'));
});

test('every input of every record type has one row', () => {
  for (const type of RECORDS) {
    const p = paths(allRows(type, newDraft(type)));
    assert.equal(new Set(p).size, p.length, type.id);
  }
});

test('placeholders show what the guide\'s worked examples put there, not explanations', () => {
  const rows = allRows(klokk, newDraft(klokk));
  assert.equal(row(rows, 'subject.name').placeholder, 'Thor Emil');
  assert.match(row(rows, 'values.details').placeholder, /^\(born 1 September 1869; baptized 16 January 1870\)/);
  assert.equal(row(rows, 'values.fylke').placeholder, 'Akershus');
  assert.equal(row(rows, 'values.accessed').placeholder, '17 April 2026');
  assert.equal(row(rows, 'values.eventYear').placeholder, '1869');
  assert.equal(row(rows, 'values.citedFor').placeholder, '');
  for (const type of RECORDS) {
    for (const r of allRows(type, newDraft(type))) {
      assert.doesNotMatch(r.placeholder ?? '', /\(A\d+\)|ends the page string|Paperless title|appended after/, `${type.id} ${r.path}`);
    }
  }
});

test('outputs keep Gramps order, with no Repository or Date rows, and mark edits', () => {
  const e = example();
  e.overrides.title = 'My title';
  const groups = outputRows(klokk, e, buildOutputs(klokk, e));
  assert.deepEqual(groups.map(g => g.name), ['Source', 'Citation', 'Citation note', 'Paperless scan']);
  const rows = groups.flatMap(g => g.rows);
  assert.deepEqual(rows.map(r => r.label), ['Title', 'Author', 'Abbrev', 'Pubinfo', 'Call number', 'Page', 'Confidence', 'FRN', 'SRN',
    'Title', 'Document type', 'Date meaning', 'Correspondent', 'Source URL']);
  const title = rows.find(r => r.key === 'title');
  assert.equal(title.text, 'My title');
  assert.equal(title.edited, true);
  assert.equal(title.ref, 'A8');
  assert.equal(rows.find(r => r.key === 'abbrev').ref, 'B.1 §10');
  assert.equal(rows.find(r => r.key === 'confidence').editable, false);
  assert.equal(rows.find(r => r.key === 'pubinfo').text, 'Digital images, Digitalarkivet (https://www.digitalarkivet.no).');
});

test('outputs keep gap markers for display and plain text for copying', () => {
  const d = newDraft(klokk);
  const title = outputRows(klokk, d, buildOutputs(klokk, d))[0].rows[0];
  assert.match(title.value, /⟦Parish⟧/);
  assert.match(title.text, /\[Parish\]/);
});

test('the example note says whether the outputs still match the guide', () => {
  const e = example();
  const guide = { examples: { 'B.1 Example 1': { expected: { page: 'p. 57 (image 62), no. 21, Thor Emil birth and baptism entry' }, confidence: 'High' } } };
  assert.equal(exampleNote(klokk, e, buildOutputs(klokk, e), guide), 'Matches guide example B.1 Example 1');
  e.overrides.page = 'other';
  assert.equal(exampleNote(klokk, e, buildOutputs(klokk, e), guide), 'Differs from guide example B.1 Example 1: Page');
  assert.equal(exampleNote(klokk, newDraft(klokk), {}, guide), '');
});

test('a new Source names the archive the FRN cites, or the private holder, as its Repository', () => {
  assert.equal(repositoryName(klokk, newDraft(klokk)), 'Statsarkivet i Oslo');
  const census = recordById('us-federal-census');
  assert.equal(repositoryName(census, newDraft(census)), 'National Archives');
  const bible = recordById('pp-bible');
  assert.equal(repositoryName(bible, newDraft(bible)), 'Peter Grund, private collection');
  const paper = recordById('us-newspaper');
  const film = newDraft(paper);
  film.values.pubmedium = 'Microfilm';
  film.values.archive = 'Minnesota Historical Society';
  assert.equal(repositoryName(paper, film), '', 'a newspaper read on film has no Repository (B.3 §3)');
  const folk = recordById('se-folkrakning');
  assert.equal(repositoryName(folk, newDraft(folk)), '');
  const blank = newDraft(klokk);
  blank.values.archive = ' ';
  assert.equal(repositoryName(klokk, blank), '');
});

test('Paperless names match the guide\'s doctypes and platforms loosely', () => {
  const types = [{ id: 25, name: 'Vital record' }, { id: 28, name: 'Immigration/naturalization' }, { id: 30, name: 'Publication' }];
  assert.equal(paperlessMatch('vital record', types), 25);
  assert.equal(paperlessMatch('immigration', types), 28);
  assert.equal(paperlessMatch('interview', types), null);
  assert.equal(paperlessMatch('', types), null);
  const people = [{ id: 28, name: 'Ancestry.com' }, { id: 30, name: 'Find A Grave' }, { id: 42, name: 'Newspapers.com' }, { id: 50, name: 'Lantmäteriet' }];
  assert.equal(paperlessMatch('Ancestry', people), 28);
  assert.equal(paperlessMatch('Find a Grave', people), 30);
  assert.equal(paperlessMatch('Newspapers.com', people), 42);
  assert.equal(paperlessMatch('Lantmäteriet', people), 50);
  assert.equal(paperlessMatch('Fold3', people), null);
});

test('copy all uses the Gramps block layout', () => {
  const o = buildOutputs(klokk, example());
  assert.equal(copyAllText(o), [
    'SOURCE',
    'Title: Norway, Akershus, Eidsvoll, Klokkerbok [parish register (copy)] I 2, 1866–1871',
    'Author: Eidsvoll prestekontor',
    'Abbrev: Eidsvoll klokkerbok I 2 (1866–1871)',
    'Pubinfo: Digital images, Digitalarkivet (https://www.digitalarkivet.no).',
    'Call number: AV/SAO-A-10888/G/Ga/L0002',
    '',
    'CITATION',
    'Page: p. 57 (image 62), no. 21, Thor Emil birth and baptism entry',
    'Confidence: High',
    '',
    'FIRST REFERENCE NOTE:',
    o.frn,
    '',
    'SHORT REFERENCE NOTE:',
    'Eidsvoll klokkerbok I 2 (1866–1871), p. 57, no. 21, Thor Emil birth and baptism entry.',
  ].join('\n'));
});
