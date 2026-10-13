// A14 · the General form: a record with no record type yet, cited from five questions and tagged until one exists.

const DIGITAL_IMAGE = '{medium}, {platform} ({url} : accessed {accessed})';

export const GENERAL = [
  {
    id: 'general', chapter: 'ge', group: 'No rule yet', name: 'General form', rules: 'A14', tag: 'General form',
    hint: 'A record with no record type yet; tagged General form until one exists',
    source: [
      ['creator', 'Creator', 'Marshall County Register of Deeds'], ['place', 'Place', 'Minnesota, Marshall County'],
      ['collection', 'Collection', 'Miscellaneous Record, vol. K'], ['years', 'Years', '1919–1927'], ['call', 'Call number'],
    ],
    citation: [['page', 'Page'], ['image', 'Image'], ['entry', 'Entry no.'], ['date', 'Date', '3 May 1919']],
    note: [['reference', 'Reference', 'Image Group Number 005537573']],
    nouns: [''], freeNoun: true,
    defaults: { pubmedium: 'Digital images' },
    confidence: '', doctype: 'legal',
    title: '{place}, {collection}«, {years}»',
    abbrev: '{collection}«, {years}»',
    author: '{creator}',
    page: '{pageLoc}«, no. {entry}»',
    frn: `{creator}, {collection}«, {years}», {pageRef}«, no. {entry}», {subject}« ({date})»« (documenting {citedFor})»; ${DIGITAL_IMAGE}«, {reference}»«; citing {archive}».`,
    srn: '{collection}«, {years}», {pageRef}«, no. {entry}», {srnSubject}.',
    pins: {
      title: [['A14', 'Title: [Place], [Collection], [years] (A8). Abbrev: [Collection], [years].']],
      page: [['A14', 'Page string: p. [P] (image [I]), no. [N] ([cited for])']],
      frn: [['A14', 'FRN: [Creator], [Collection], [years], p. [P], [Subject] [record noun] ([date]); digital image, [platform] ([URL] : accessed [date]), [reference]; citing [archive].']],
      srn: [['A14', 'SRN: [Abbrev], p. [P], [Subject] [record noun].']],
    },
    examples: [],
    a14Example: {
      creator: 'Marshall County Register of Deeds', place: 'Minnesota, Marshall County', collection: 'Miscellaneous Record, vol. K',
      years: '1919–1927', image: '32', date: '[date]', name: 'Peter L. Grund', noun: 'power of attorney',
      platform: 'FamilySearch', url: 'https://www.familysearch.org/ark:/61903/3:1:3QS7-L99T-2SDQ', accessed: '13 October 2026',
      reference: 'Image Group Number 005537573',
    },
  },
];
