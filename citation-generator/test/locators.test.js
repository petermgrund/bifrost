// Page locators for parish-style record types: image number when the page has no number.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { RECORDS, recordById } from '../src/records/index.js';
import { newDraft, draftFromExample, buildOutputs, inputFields } from '../src/engine.js';
import { plain } from '../src/template.js';

const IMAGE_ONLY_TYPES = [
  'no-ministerialbok', 'no-klokkerbok', 'no-confirmation', 'no-minutes',
  'se-husforhor', 'se-dopbok', 'se-vigselbok', 'se-dodbok', 'se-confirmation', 'se-sockenstamma', 'se-folkrakning',
];

const outputsFor = (id, inputs) => {
  const type = recordById(id);
  return buildOutputs(type, draftFromExample(type, { guide: 'test', inputs }));
};

const fromExample = (id, changes) => {
  const type = recordById(id);
  return outputsFor(id, { ...type.examples[0].inputs, ...changes });
};

test('se-dopbok: an unnumbered page leads with the image number', () => {
  const o = outputsFor('se-dopbok', {
    lan: 'Värmland', parish: 'Norra Ny', vol: 'C:4', years: '1812–1830', call: 'SE/VA/13398/C/4',
    page: '', image: '100', entry: '34', name: 'Lars Persson', noun: 'birth and baptism entry',
    url: 'https://app.arkivdigital.se/volume/v12345?image=100', accessed: '28 September 2026', eventYear: '1815',
  });
  assert.equal(o.page, 'image 100, no. 34, Lars Persson birth and baptism entry');
  assert.ok(o.srn.includes(', image 100, no. 34, Lars Persson birth and baptism entry.'), o.srn);
  assert.ok(o.frn.includes(', image 100, no. 34, birth and baptism entry of Lars Persson'), o.frn);
});

test('no-klokkerbok: image only', () => {
  const o = fromExample('no-klokkerbok', { page: '' });
  assert.equal(o.page, 'image 62, no. 21, Thor Emil birth and baptism entry');
  assert.ok(o.frn.includes(', 1866–1871, image 62, no. 21, Thor Emil'), o.frn);
  assert.ok(o.srn.endsWith(', image 62, no. 21, Thor Emil birth and baptism entry.'), o.srn);
});

test('no-confirmation: image only, inside the page string', () => {
  const o = fromExample('no-confirmation', { page: '' });
  assert.equal(o.page, 'confirmations, image 91, no. 14, Karen Indiana Evensdatter confirmation entry');
  assert.ok(o.frn.includes('confirmations section, image 91, no. 14, Karen Indiana Evensdatter'), o.frn);
  assert.ok(o.srn.endsWith(', confirmations, image 91, no. 14, Karen Indiana Evensdatter confirmation entry.'), o.srn);
});

test('us-naturalization final papers: an unnumbered page leads with the image number', () => {
  const claim = recordById('us-naturalization').examples.find(c => c.guide === 'B.3 Example 12');
  const o = outputsFor('us-naturalization', { ...claim.inputs, page: '', image: '62', platformRef: 'Image Group Number 101714756, image 62' });
  assert.equal(o.page, 'reel 4, final papers vol. C, image 62, Peter L. Grund naturalization petition');
  assert.ok(o.frn.includes(', final papers vol. C, image 62 (12 March 1897), Peter L. Grund; digital image, FamilySearch ('), o.frn);
  assert.ok(o.frn.endsWith('), Image Group Number 101714756, image 62; citing Minnesota Historical Society microfilm SAM 227, reel 4.'), o.frn);
  assert.equal(o.srn, 'Marshall Co. natz., final papers vol. C, image 62 (1897), Peter L. Grund.');
  const imagesOnly = outputsFor('us-naturalization', { ...claim.inputs, reel: '', call: '' });
  assert.equal(imagesOnly.page, 'final papers vol. C, p. 296 (image [I]), Peter L. Grund naturalization petition', 'with only the images, the reel is left out');
  assert.ok(imagesOnly.frn.endsWith('; citing Minnesota Historical Society.'), imagesOnly.frn);
});

test('us-naturalization final papers read on the film at the library', () => {
  const claim = recordById('us-naturalization').examples.find(c => c.guide === 'B.3 Example 12');
  const o = outputsFor('us-naturalization', { ...claim.inputs, pubmedium: 'Microfilm', image: '', url: '', accessed: '', platformRef: '' });
  assert.equal(o.pubinfo, 'Microfilm, Minnesota Historical Society.');
  assert.equal(o.page, 'reel 4, final papers vol. C, p. 296, Peter L. Grund naturalization petition');
  assert.equal(o.frn, 'Marshall County District Court (Warren, Minnesota), Naturalization Records, final papers vol. C, p. 296 (12 March 1897), Peter L. Grund; Minnesota Historical Society microfilm SAM 227, reel 4.');
  assert.equal(o.srn, 'Marshall Co. natz., final papers vol. C, p. 296 (1897), Peter L. Grund.');
  assert.deepEqual([o.plCorrespondent, o.plSourceUrl], ['', '']);
  const census = recordById('us-federal-census');
  const c = outputsFor('us-federal-census', { ...census.examples[0].inputs, pubmedium: 'Microfilm' });
  assert.ok(c.frn.endsWith(', Steve Maisuk household; National Archives microfilm publication T625, roll 859.'), c.frn);
  assert.equal(c.pubinfo, 'Microfilm, National Archives.');
});

test('us-newspaper: the same Source and page string on Newspapers.com and on a library\'s film', () => {
  const claim = recordById('us-newspaper').examples.find(c => c.guide === 'B.3 Example 9');
  const online = outputsFor('us-newspaper', claim.inputs);
  const film = outputsFor('us-newspaper', { ...claim.inputs, pubmedium: 'Microfilm', url: '', accessed: '' });
  for (const key of ['title', 'abbrev', 'author', 'callNumber', 'page', 'srn']) assert.equal(film[key], online[key], key);
  assert.equal(online.pubinfo, 'Digital images, Newspapers.com (https://www.newspapers.com).');
  assert.equal(film.pubinfo, 'Microfilm, Minnesota Historical Society.', 'the archive defaults to the Minnesota Historical Society');
  assert.equal(plain(film.frn), '"[Headline if present]," Warren Sheaf (Warren, Minnesota), 3 December 1908, p. 1, Grund-Hoiberg marriage announcement; Minnesota Historical Society microfilm.');
  assert.deepEqual([online.plCorrespondent, film.plCorrespondent, film.plSourceUrl], ['Newspapers.com', '', '']);
});

test('with both page and image the output is unchanged', () => {
  assert.equal(fromExample('no-klokkerbok', {}).page, 'p. 57 (image 62), no. 21, Thor Emil birth and baptism entry');
  assert.equal(fromExample('no-confirmation', {}).page, 'confirmations, p. 88 (image 91), no. 14, Karen Indiana Evensdatter confirmation entry');
  assert.equal(fromExample('se-confirmation', {}).page, 'p. 8 (image 19), Lars Persson confirmation entry');
});

for (const id of IMAGE_ONLY_TYPES) {
  const type = recordById(id);
  const draftWith = (page, image) => {
    const d = newDraft(type);
    for (const [key] of inputFields(type)) d.values[key] = key;
    Object.assign(d.values, { page, image, url: 'https://example.org/x', accessed: '28 September 2026', eventYear: '1850' });
    d.subject.name = 'Lars Persson';
    return d;
  };
  const lead = id === 'no-confirmation' ? 'section, ' : '';

  test(`${id}: page, image, or both in the page string, FRN, and SRN`, () => {
    const both = buildOutputs(type, draftWith('8', '19'));
    assert.ok(both.page.startsWith(`${lead}p. 8 (image 19), `), both.page);
    for (const field of ['frn', 'srn']) {
      assert.ok(both[field].includes(', p. 8, '), `${field}: ${both[field]}`);
      assert.ok(!both[field].includes('image 19'), `${field}: ${both[field]}`);
    }

    const pageOnly = buildOutputs(type, draftWith('8', ''));
    assert.ok(pageOnly.page.startsWith(`${lead}p. 8, `), pageOnly.page);

    const imageOnly = buildOutputs(type, draftWith('', '19'));
    assert.ok(imageOnly.page.startsWith(`${lead}image 19, `), imageOnly.page);
    for (const field of ['page', 'frn', 'srn']) {
      assert.ok(!imageOnly[field].includes('p. '), `${field}: ${imageOnly[field]}`);
      assert.ok(!imageOnly[field].includes('⟦'), `${field}: ${plain(imageOnly[field])}`);
    }
    for (const field of ['frn', 'srn']) assert.ok(imageOnly[field].includes(', image 19, '), `${field}: ${imageOnly[field]}`);

    const neither = buildOutputs(type, draftWith('', ''));
    for (const field of ['page', 'frn', 'srn']) assert.ok(plain(neither[field]).includes('[Page or image]'), `${field}: ${plain(neither[field])}`);
  });

  test(`${id}: pins the unpaginated fallback`, () => {
    const section = id.startsWith('no-') ? 'B.1 §7' : 'B.2 §7';
    const pins = (type.pins?.page || []).filter(([, text]) => text.startsWith('Unpaginated fallback'));
    assert.deepEqual(pins.map(([s]) => s), [section]);
  });

  test(`${id}: page and image field labels`, () => {
    const fields = Object.fromEntries(inputFields(type).map(([key, label, placeholder]) => [key, [label, placeholder]]));
    assert.deepEqual(fields.page, ['Page', 'blank if unnumbered']);
    assert.deepEqual(fields.image, ['Image', 'if not the page, or if unnumbered']);
  });
}

test('us-newspaper: the FRN names the item and what it is cited for; the SRN keeps the column', () => {
  const o = outputsFor('us-newspaper', {
    paper: 'Warren Sheaf', city: 'Warren', state: 'Minnesota', date: '16 November 1899', page: '5', col: '1',
    name: 'Minne and Merton', noun: 'marriage announcement', citedFor: 'marriage date and location',
    url: 'https://www.newspapers.com/image/84091981/', accessed: '4 October 2026',
  });
  assert.equal(o.frn, 'Warren Sheaf (Warren, Minnesota), 16 November 1899, p. 5, col. 1, Minne and Merton marriage announcement (documenting marriage date and location); digital image, Newspapers.com (https://www.newspapers.com/image/84091981/ : accessed 4 October 2026).');
  assert.equal(o.srn, 'Warren Sheaf, 16 November 1899, p. 5, col. 1, Minne and Merton marriage announcement (marriage date and location).');
  assert.equal(o.page, '16 November 1899, p. 5, col. 1, Minne and Merton marriage announcement (marriage date and location)');
  const bare = outputsFor('us-newspaper', { paper: 'Warren Sheaf', city: 'Warren', state: 'Minnesota', date: '16 November 1899', page: '5', name: 'Minne and Merton', noun: 'marriage announcement' });
  assert.match(plain(bare.frn), /, p\. 5, Minne and Merton marriage announcement; digital image/, 'no column and nothing cited for: both drop out');
  assert.equal(plain(bare.srn), 'Warren Sheaf, 16 November 1899, p. 5, Minne and Merton marriage announcement.');
});

test('us-newspaper: three citations from one item end their page strings and SRNs with what each is cited for', () => {
  const item = {
    paper: 'Warren Sheaf', city: 'Warren', state: 'Minnesota', date: '11 July 1898', page: '3',
    name: 'Olaf and Gertrude Nygren', noun: 'news mention',
  };
  const three = ["Olaf's immigration date", 'marriage date', 'attendee list'].map(citedFor => outputsFor('us-newspaper', { ...item, citedFor }));
  assert.deepEqual(three.map(o => o.page), [
    "11 July 1898, p. 3, Olaf and Gertrude Nygren news mention (Olaf's immigration date)",
    '11 July 1898, p. 3, Olaf and Gertrude Nygren news mention (marriage date)',
    '11 July 1898, p. 3, Olaf and Gertrude Nygren news mention (attendee list)',
  ]);
  assert.equal(three[1].srn, 'Warren Sheaf, 11 July 1898, p. 3, Olaf and Gertrude Nygren news mention (marriage date).');
  assert.match(plain(three[1].frn), /, p\. 3, Olaf and Gertrude Nygren news mention \(documenting marriage date\); digital image/, 'the FRN says it once');
  const none = outputsFor('us-newspaper', item);
  assert.equal(none.page, '11 July 1898, p. 3, Olaf and Gertrude Nygren news mention', 'left blank, it drops out');
  assert.equal(none.srn, 'Warren Sheaf, 11 July 1898, p. 3, Olaf and Gertrude Nygren news mention.');
  assert.match(plain(none.frn), /news mention; digital image/);
});

test('any record type: what it is cited for ends the page string', () => {
  const o = fromExample('no-klokkerbok', { citedFor: "mother's age" });
  assert.equal(o.page, "p. 57 (image 62), no. 21, Thor Emil birth and baptism entry (mother's age)");
  assert.equal(o.srn, "Eidsvoll klokkerbok I 2 (1866–1871), p. 57, no. 21, Thor Emil birth and baptism entry (mother's age).");
  assert.match(o.frn, /, baptized at Eidsvoll church \(documenting mother's age\); digital image, Digitalarkivet/);
  const plainKlokk = fromExample('no-klokkerbok', {});
  assert.equal(plainKlokk.page, 'p. 57 (image 62), no. 21, Thor Emil birth and baptism entry');
  assert.doesNotMatch(plainKlokk.frn, /documenting/);
});

test('every record type, form, and medium: one (documenting …) in the FRN, before any image or holding clause; the SRN and page string end with it', () => {
  for (const type of RECORDS) {
    const forms = type.pageVariants ? type.pageVariants.map(v => v.key) : [''];
    const media = ['', ...([type, ...(type.pageVariants || [])].some(x => x.frnMicrofilm) ? ['Microfilm'] : [])];
    for (const variant of forms) for (const pubmedium of media) {
      const label = [type.id, variant, pubmedium].filter(Boolean).join(' · ');
      const claim = type.examples.find(c => !variant || (c.inputs.variant || type.pageVariants[0].key) === variant) || { inputs: {} };
      const inputs = { ...claim.inputs, variant, ...(pubmedium ? { pubmedium } : {}) };
      const o = outputsFor(type.id, { ...inputs, citedFor: 'XYZ' });
      const frn = plain(o.frn);
      assert.equal(frn.split('(documenting XYZ)').length, 2, `${label}: FRN ${frn}`);
      const [before, after] = frn.split('(documenting XYZ)');
      assert.match(after, /^(;|\.|$)/, `${label}: it ends the item: ${frn}`);
      // An interview names its holder before the minute it cites, so only there does a holding clause come first.
      if (type.id !== 'pp-interview') assert.doesNotMatch(before, /digital image|database|privately held|microfilm/, `${label}: before the image or holding clause: ${frn}`);
      assert.match(plain(o.srn), /\(XYZ\)\.$/, `${label}: SRN ${plain(o.srn)}`);
      assert.match(plain(o.page), /\(XYZ\)$/, `${label}: page ${plain(o.page)}`);
      assert.doesNotMatch(plain(outputsFor(type.id, inputs).frn), /documenting/, `${label}: only when given`);
    }
  }
});
