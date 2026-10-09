// Built by citation-generator/tools/build.js from citation-generator/src and the style guide. Edit those, then run npm run build.
const __modules = {};
__modules["records/norwegian.js"] = (() => {
// B.1 · Norwegian sources.
const DIGITAL_IMAGE = '{medium}, {platform} ({url} : accessed {accessed})';
const OSLO = { platform: 'Digitalarkivet', archive: 'Statsarkivet i Oslo' };
const RIKSARKIVET = { platform: 'Digitalarkivet', pubmedium: 'Database with images', archive: 'Riksarkivet' };

const PARISH_SOURCE = [
  ['fylke', 'Fylke / amt', 'Akershus'], ['parish', 'Parish', 'Eidsvoll'], ['vol', 'Volume', 'I 5'],
  ['years', 'Years', '1862–1869'], ['call', 'Call number', 'AV/SAO-A-10888/A/Aa/L0005'],
];
const PAGE = ['page', 'Page', 'blank if unnumbered'];
const IMAGE = ['image', 'Image', 'if not the page, or if unnumbered'];
const PARISH_LOCATORS = [PAGE, IMAGE, ['entry', 'Entry no.']];
const PARISH_NOUNS = ['birth and baptism entry', 'baptism entry', 'death entry', 'burial entry', 'marriage entry'];
const PARISH_PAGE_PIN = ['B.1 §7', 'Parish | p. [P] (image [I]), [entry], [subject]'];
const UNPAGINATED_PIN = ['B.1 §7', 'Unpaginated fallback: when the page has no number, lead with the image number: image [I], [entry], [subject]'];
/** Eidsvoll sorenskriveri → Eidsvoll, for the court's gloss. */
const courtPlace = court => String(court || '').replace(/\s+sorenskriveri$/i, '').trim();

const NORWEGIAN = [
  {
    id: 'no-ministerialbok', chapter: 'no', group: 'Parish registers (kirkebøker)', name: 'Ministerialbok',
    hint: "The minister's original register",
    source: PARISH_SOURCE, citation: PARISH_LOCATORS, nouns: PARISH_NOUNS,
    defaults: OSLO, confidence: 'Very High', doctype: 'vital record',
    title: 'Norway, {fylke}, {parish}, Ministerialbok [parish register] {vol}, {years}',
    abbrev: '{parish} kirkebok {vol} ({years})',
    author: '{parish} prestekontor',
    page: '{pageLoc}, no. {entry}, {subject}',
    frn: `{parish} prestekontor, Ministerialbok [parish register] no. {vol}, {years}, {pageRef}, no. {entry}, {name}« {details}»« (documenting {citedFor})»; ${DIGITAL_IMAGE}; citing {archive}, {call}.`,
    srn: '{parish} kirkebok {vol} ({years}), {pageRef}, no. {entry}, {srnSubject}.',
    detailsLabel: 'Entry details (dates, parents, church)',
    pins: {
      title: [['B.1 §4', "Parish, minister's original | Norway, [Fylke/Amt], [Parish], Ministerialbok [parish register] [Roman] [Arabic], [years]"]],
      page: [PARISH_PAGE_PIN, UNPAGINATED_PIN],
      author: [['B.1 §2', 'Parish records | [Parish] prestekontor']],
      abbrev: [['B.1 §10', 'Ministerialbok I 5 | kirkebok I 5']],
      confidence: [['B.1 §8', 'Ministerialbok | Very High for an entry written by the minister within days']],
    },
    examples: [],
  },
  {
    id: 'no-klokkerbok', chapter: 'no', group: 'Parish registers (kirkebøker)', name: 'Klokkerbok',
    hint: "The sacristan's duplicate (parish register copy). Prefer the ministerialbok when you can reach it.",
    source: PARISH_SOURCE, citation: PARISH_LOCATORS, nouns: PARISH_NOUNS,
    defaults: OSLO, confidence: 'High', doctype: 'vital record',
    title: 'Norway, {fylke}, {parish}, Klokkerbok [parish register (copy)] {vol}, {years}',
    abbrev: '{parish} klokkerbok {vol} ({years})',
    author: '{parish} prestekontor',
    page: '{pageLoc}, no. {entry}, {subject}',
    frn: `{parish} prestekontor, Klokkerbok [parish register (copy)] no. {vol}, {years}, {pageRef}, no. {entry}, {name}« {details}»« (documenting {citedFor})»; ${DIGITAL_IMAGE}; citing {archive}, {call}.`,
    srn: '{parish} klokkerbok {vol} ({years}), {pageRef}, no. {entry}, {srnSubject}.',
    detailsLabel: 'Entry details (dates, parents, church)',
    pins: {
      title: [['B.1 §4', 'Parish, klokkerbok | …, Klokkerbok [parish register (copy)] [Roman] [Arabic], [years]']],
      page: [PARISH_PAGE_PIN, UNPAGINATED_PIN],
      author: [['B.1 §2', 'Parish records | [Parish] prestekontor']],
      abbrev: [['B.1 §10', 'Klokkerbok I 2 | klokkerbok I 2']],
      confidence: [['B.1 §8', 'Klokkerbok | High by default (contemporaneous duplicate)']],
    },
    examples: [{
      guide: 'B.1 Example 1',
      inputs: {
        fylke: 'Akershus', parish: 'Eidsvoll', vol: 'I 2', years: '1866–1871', call: 'AV/SAO-A-10888/G/Ga/L0002',
        page: '57', image: '62', entry: '21', name: 'Thor Emil', noun: 'birth and baptism entry',
        url: 'https://urn.digitalarkivet.no/URN:NBN:no-a1450-kb20060313011115.jpg', accessed: '17 April 2026', eventYear: '1869',
        details: '(born 1 September 1869; baptized 16 January 1870), son of Christian Henningsen and Anne Marthe Bergersdatter, baptized at Eidsvoll church',
      },
    }],
  },
  {
    id: 'no-confirmation', chapter: 'no', group: 'Parish registers (kirkebøker)', name: 'Confirmation or communion',
    hint: "Recorded inside the kirkebok; cite it under that volume's Source.",
    source: [
      ['fylke', 'Fylke / amt', 'Akershus'], ['parish', 'Parish', 'Eidsvoll'],
      ['book', 'Book', 'Ministerialbok or Klokkerbok'], ['vol', 'Volume', 'I 2'],
      ['years', 'Years', '1866–1871'], ['call', 'Call number', 'AV/SAO-A-10888/G/Ga/L0002'],
    ],
    citation: [['section', 'Section', 'confirmations or communicants'], PAGE, IMAGE, ['entry', 'Entry no.']],
    nouns: ['confirmation entry', 'communion entry'],
    defaults: OSLO, confidence: 'High', doctype: 'religious',
    derive: v => {
      const minister = /^minist/i.test(String(v.book || '').trim());
      return {
        kb: minister ? 'kirkebok' : 'klokkerbok',
        bookName: minister ? 'Ministerialbok' : 'Klokkerbok',
        bookGloss: minister ? 'parish register' : 'parish register (copy)',
      };
    },
    title: 'Norway, {fylke}, {parish}, {bookName} [{bookGloss}] {vol}, {years}',
    abbrev: '{parish} {kb} {vol} ({years})',
    author: '{parish} prestekontor',
    page: '{section}, {pageLoc}«, no. {entry}», {subject}',
    frn: `{parish} prestekontor, {bookName} [{bookGloss}] no. {vol}, {years}, {section} section, {pageRef}«, no. {entry}», {name}« {details}»« (documenting {citedFor})»; ${DIGITAL_IMAGE}; citing {archive}, {call}.`,
    srn: '{parish} {kb} {vol} ({years}), {section}, {pageRef}«, no. {entry}», {srnSubject}.',
    detailsLabel: 'Entry details (parents, church, year)',
    pins: {
      title: [['B.1 §4', "Confirmation and communion have no Title of their own; they use the kirkebok's Title."]],
      page: [
        ['B.1 §7', 'Confirmation Pending review | confirmations, p. [P] (image [I]), no. [N], [Subject] confirmation entry'],
        ['B.1 §7', 'Communion Pending review | communicants, p. [P] (image [I]), [Subject] communion entry'],
        UNPAGINATED_PIN,
      ],
      author: [['B.1 §2', 'Confirmation, communion | [Parish] prestekontor']],
      confidence: [['B.1 §8', 'Confirmation entry Pending review | High for the confirmation']],
    },
    examples: [{
      guide: 'B.1 Example 5',
      inputs: {
        fylke: 'Akershus', parish: 'Eidsvoll', book: 'Klokkerbok', vol: 'I 2', years: '1866–1871',
        call: 'AV/SAO-A-10888/G/Ga/L0002', section: 'confirmations', page: '88', image: '91', entry: '14',
        name: 'Karen Indiana Evensdatter', noun: 'confirmation entry',
        url: 'https://www.digitalarkivet.no/...', accessed: '15 June 2026', eventYear: '1869',
        details: '(daughter of Even Hansen), confirmed at Eidsvoll church 1869',
      },
    }],
  },
  {
    id: 'no-minutes', chapter: 'no', group: 'Parish registers (kirkebøker)', name: 'Parish meeting minutes',
    hint: 'Menighetsmøteprotokoll, a series of its own',
    source: [
      ['fylke', 'Fylke / amt', 'Akershus'], ['parish', 'Parish', 'Eidsvoll'], ['vol', 'Volume', '1'],
      ['years', 'Years', '1870–1895'], ['call', 'Call number'],
    ],
    citation: [PAGE, IMAGE, ['date', 'Meeting date']],
    nouns: ['minute entry'],
    defaults: OSLO, confidence: 'High', doctype: 'religious',
    title: 'Norway, {fylke}, {parish}, Menighetsmøteprotokoll [parish meeting minutes] {vol}, {years}',
    abbrev: '{parish} menighetsmøteprotokoll {vol} ({years})',
    author: '{parish} prestekontor',
    page: '{pageLoc}, {date}, {subject}',
    frn: `{parish} prestekontor, Menighetsmøteprotokoll [parish meeting minutes] no. {vol}, {years}, {pageRef}, {date}, {subject}«, {details}»« (documenting {citedFor})»; ${DIGITAL_IMAGE}; citing {archive}«, {call}».`,
    srn: '{parish} menighetsmøteprotokoll {vol} ({years}), {pageRef}, {srnSubject}.',
    subjectLabel: 'Meeting subject',
    pins: {
      title: [['B.1 §4', 'Meeting minutes | Norway, [Fylke/Amt], [Parish], Menighetsmøteprotokoll [parish meeting minutes] [vol], [years]']],
      page: [['B.1 §7', 'Meeting minutes Pending review | p. [P] (image [I]), [date], [subject] minute entry'], UNPAGINATED_PIN],
      abbrev: [['B.1 §10', 'Menighetsmøteprotokoll 1 Pending review | menighetsmøteprotokoll 1 | Eidsvoll menighetsmøteprotokoll 1 (1870–1895)']],
      confidence: [['B.1 §8', 'Meeting minutes Pending review | High for the recorded act or attendance']],
    },
    examples: [],
  },
  {
    id: 'no-folketelling-1801', chapter: 'no', group: 'Census (folketelling)', name: 'Folketelling 1801',
    hint: 'Nominal census, organized by gård',
    source: [['amt', 'Amt', 'Akershus'], ['prestegjeld', 'Prestegjeld', 'Eidsvoll'], ['ref', 'Reference (if needed)', 'L0009'], ['call', 'Call number']],
    citation: [['gard', 'Gård no.'], ['gardname', 'Gård name'], ['hh', 'Household'], ['person', 'Person']],
    nouns: ['household'],
    defaults: RIKSARKIVET, confidence: 'Very High', doctype: 'enumeration',
    title: 'Norway, {amt}, {prestegjeld}, Folketelling [census] 1801«, {ref}»',
    abbrev: '{prestegjeld} folketelling 1801',
    author: 'Riksarkivet',
    page: 'gård {gard} ({gardname}), household {hh}, person {person}, {subject}',
    frn: `Folketelling [census] 1801, {amt}, {prestegjeld} prestegjeld, gård {gard} ({gardname}), household no. {hh}, person no. {person}, {name}«, {details}»« (documenting {citedFor})»; ${DIGITAL_IMAGE}; citing {archive}«, {call}».`,
    srn: '{prestegjeld} folketelling 1801, gård {gard}, household {hh}, {srnSubject}.',
    pins: {
      title: [['B.1 §4', 'Folketelling 1801 | Norway, [Amt], [Prestegjeld], Folketelling [census] 1801, [reference if needed]']],
      page: [['B.1 §7', 'Folketelling 1801 | gård [N] ([name]), household [N], person [N], [Head] household']],
      author: [['B.1 §2', 'Folketelling | Riksarkivet (preferred)']],
      abbrev: [['B.1 §10', 'Folketelling YYYY | folketelling YYYY']],
      confidence: [['B.1 §8', 'Folketelling 1801 | Very High for residence (enumerator visited each gård); Normal for ages']],
    },
    examples: [],
  },
  {
    id: 'no-folketelling', chapter: 'no', group: 'Census (folketelling)', name: 'Folketelling 1865 and later',
    hint: 'Decennial census, by sokn and district. Use the jurisdiction names the census itself uses.',
    source: [['amt', 'Amt or fylke', 'Akershus'], ['prestegjeld', 'Prestegjeld or herred', 'Eidsvoll'], ['year', 'Census year', '1875'], ['call', 'Call number', 'AV/RA-S-2231/E']],
    citation: [['district', 'District (tellekrets)', '009 Blegstad'], ['page', 'Page'], ['hh', 'Household'], ['person', 'Person']],
    note: [['sokn', 'Sokn (FRN)'], ['turl', 'Transcribed entry URL'], ['citing', 'Citing, after the archive']],
    nouns: ['household'],
    defaults: RIKSARKIVET, confidence: 'High', doctype: 'enumeration', eventDate: 'year',
    title: 'Norway, {amt}, {prestegjeld}, Folketelling [census] {year}',
    abbrev: '{prestegjeld} folketelling {year}',
    author: 'Riksarkivet',
    page: 'district {district}, p. {page}, household {hh}, person {person}, {subject}',
    frn: `Folketelling [census] {year}, {amt} fylke, {prestegjeld} prestegjeld«, {sokn} sokn», district {district}, p. {page}, household no. {hh}, person no. {person}, {name}« ({details})»« (documenting {citedFor})»; ${DIGITAL_IMAGE}«; transcribed entry at {turl}»; citing {archive}«, {citing}»; archive reference {call}.`,
    srn: '{prestegjeld} folketelling {year}, p. {page}, household {hh}, {srnSubject}.',
    detailsLabel: 'Entry details (role, age, household)',
    pins: {
      title: [['B.1 §4', 'Folketelling 1865+ | Norway, [Amt or fylke], [Prestegjeld or herred], Folketelling [census] [year]']],
      page: [['B.1 §7', 'Folketelling 1865+ | district [N] [name], p. [N], household [N], person [N], [Head] household']],
      author: [['B.1 §2', 'Folketelling | Riksarkivet (preferred)']],
      abbrev: [['B.1 §10', 'Folketelling YYYY | folketelling YYYY']],
      confidence: [['B.1 §8', 'Folketelling 1865+ | High for residence and household; Normal for ages and birthplaces']],
    },
    examples: [{
      guide: 'B.1 Example 2',
      inputs: {
        amt: 'Akershus', prestegjeld: 'Eidsvoll', year: '1875', call: 'AV/RA-S-2231/E',
        district: '009 Blegstad', page: '1270', hh: '01', person: '006',
        name: 'Karen Indiana Evensdatter', noun: 'household', says: 'tjenestepige', evidence: 'stated age 14', nonHead: true, head: 'Hansen',
        sokn: 'Eidsvoll', url: 'https://www.digitalarkivet.no/ft20110110330371', accessed: '26 April 2026',
        turl: 'https://www.digitalarkivet.no/pf01052052005225',
        citing: 'Statistisk sentralbyrå, Sosioøkonomiske emner, Folketellinger, boliger og boforhold, E: Folketellinger, source ID 52052',
        details: "tjenestepige, stated age 14, in Jens Hansen's household",
      },
    }],
  },
  {
    id: 'no-tingbok', chapter: 'no', group: 'Court and land', name: 'Tingbok',
    hint: 'District court journal (sorenskriverarkiv)',
    source: [['fylke', 'Fylke / amt', 'Akershus'], ['court', 'Sorenskriveri', 'Eidsvoll sorenskriveri'], ['series', 'Series', 'A I 5'], ['years', 'Years', '1820–1830'], ['call', 'Call number']],
    citation: [['folio', 'Folio'], ['session', 'Date or session']],
    nouns: ['land dispute entry', 'court matter entry'],
    defaults: OSLO, confidence: '', doctype: 'legal',
    derive: v => ({ cs: courtPlace(v.court) }),
    title: 'Norway, {fylke}, {court}, Tingbok [court journal] {series}, {years}',
    abbrev: '{court} tingbok {series} ({years})',
    author: '{court}',
    page: 'folio {folio}, {session}, {subject}',
    frn: `{court} [{cs} district court], Tingbok [court journal] {series}, {years}, fol. {folio}, {session}, {subject}«, {details}»« (documenting {citedFor})»; ${DIGITAL_IMAGE}; citing {archive}«, {call}».`,
    srn: '{court} tingbok {series} ({years}), fol. {folio}, {srnSubject}.',
    subjectLabel: 'Parties or subject',
    pins: {
      title: [['B.1 §4', 'Court (tingbok) | Norway, [Fylke/Amt], [Sorenskriveri], Tingbok [court journal] [series], [years]']],
      page: [['B.1 §7', 'Tingbok | folio [F], [date or session], [parties or subject]']],
      author: [['B.1 §2', 'Court records | The creating body, e.g. Eidsvoll sorenskriveri']],
      abbrev: [['B.1 §10', 'Tingbok A I 5 | tingbok A I 5 | Eidsvoll sorenskriveri tingbok A I 5 (1820–1830)']],
    },
    examples: [],
  },
  {
    id: 'no-skifteprotokoll', chapter: 'no', group: 'Court and land', name: 'Skifteprotokoll',
    hint: 'Probate register; folios for the whole skifte go in the page string',
    source: [['fylke', 'Fylke / amt', 'Akershus'], ['court', 'Sorenskriveri', 'Eidsvoll sorenskriveri'], ['series', 'Series', 'II 3'], ['years', 'Years', '1815–1825'], ['call', 'Call number', 'AV/SAO-A-10063/H/Hb/L0003']],
    citation: [['folio', 'Folio range', '145–148']],
    nouns: ['estate entry'],
    defaults: OSLO, confidence: 'High', doctype: 'legal',
    derive: v => ({ cs: courtPlace(v.court) }),
    title: 'Norway, {fylke}, {court}, Skifteprotokoll [probate register] {series}, {years}',
    abbrev: '{court} skifteprotokoll {series} ({years})',
    author: '{court}',
    page: 'folio {folio}, {subject}',
    frn: `{court} [{cs} district court], Skifteprotokoll [probate register] {series}, {years}, fol. {folio}, estate inventory of {name}«, {details}»« (documenting {citedFor})»; ${DIGITAL_IMAGE}; citing {archive}, {call}.`,
    srn: '{court} skifteprotokoll {series} ({years}), fol. {folio}, {srnSubject}.',
    subjectLabel: 'Deceased',
    detailsLabel: 'Entry details (farm, death)',
    pins: {
      title: [['B.1 §4', 'Probate | Norway, [Fylke/Amt], [Sorenskriveri], Skifteprotokoll [probate register] [series], [years]']],
      page: [['B.1 §7', 'Skifteprotokoll | folio [F]–[F], [Deceased] estate entry']],
      author: [['B.1 §2', 'Probate | The court that conducted it, usually [District] sorenskriveri']],
      abbrev: [['B.1 §10', 'Skifteprotokoll II 3 | skifteprotokoll II 3 | Eidsvoll sorenskriveri skifteprotokoll II 3 (1815–1825)']],
      confidence: [['B.1 §8', 'Skifteprotokoller | High for the death and primary heirs']],
    },
    examples: [{
      guide: 'B.1 Example 3',
      inputs: {
        fylke: 'Akershus', court: 'Eidsvoll sorenskriveri', series: 'II 3', years: '1815–1825', call: 'AV/SAO-A-10063/H/Hb/L0003',
        folio: '145–148', name: 'Anders Hansen', noun: 'estate entry',
        url: 'https://www.digitalarkivet.no/...', accessed: '9 May 2026', eventYear: '1822',
        details: 'Vinger gård, died 1822',
      },
    }],
  },
  {
    id: 'no-matrikkel', chapter: 'no', group: 'Court and land', name: 'Matrikkel',
    hint: 'Cadastral register; one Source per revision (1665, 1723, 1838, 1886/1904…)',
    source: [
      ['amt', 'Amt or fylke (as written)', 'Akershus amt'], ['prestegjeld', 'Prestegjeld or herred (as written)', 'Eidsvoll prestegjeld'],
      ['year', 'Matrikkel year', '1838'], ['protocol', 'Protocol (if needed)'], ['call', 'Call number'],
    ],
    citation: [['gard', 'Gård no.'], ['gardname', 'Gård name', 'Vinger gård'], ['lnr', 'Løpenummer']],
    nouns: ['matrikkel entry'],
    defaults: RIKSARKIVET, confidence: 'High', doctype: 'legal', eventDate: 'year',
    derive: v => ({
      short: String(v.prestegjeld || '').replace(/\s+(prestegjeld|herred)$/i, '').trim(),
      gardshort: String(v.gardname || '').replace(/\s+gård$/i, '').trim(),
    }),
    title: 'Norway, {amt}, {prestegjeld}, Matrikkel [land register] {year}«, {protocol}»',
    abbrev: '{short} matrikkel {year}',
    author: 'Riksarkivet',
    page: 'gård no. {gard}, {gardname}«, løpenummer {lnr}», {subject}',
    frn: `Matrikkel [land register] {year}, {amt}, {prestegjeld}, gård no. {gard}, {gardname}«, løpenummer {lnr}», listed owner {name}«, {details}»« (documenting {citedFor})»; ${DIGITAL_IMAGE}; citing {archive}«, {call}».`,
    srn: '{short} matrikkel {year}, gård {gard} {gardshort}«, løpenr. {lnr}», {srnSubject}.',
    subjectLabel: 'Owner or topic',
    pins: {
      title: [['B.1 §4', 'Matrikkel | Norway, [Fylke or amt], [Prestegjeld or herred], Matrikkel [land register] [year], [protocol if needed]']],
      page: [['B.1 §7', 'Matrikkel | gård no. [matrikkelnr.], [gård name], [løpenummer if specific], [owner or topic]']],
      author: [['B.1 §2', 'Matrikkel | Riksarkivet for centrally held volumes']],
      abbrev: [['B.1 §10', 'Matrikkel 1838 | matrikkel 1838']],
      confidence: [['B.1 §8', 'Matrikkel | High for the cadastral fact; Low for any genealogical inference']],
    },
    examples: [{
      guide: 'B.1 Example 4',
      inputs: {
        amt: 'Akershus amt', prestegjeld: 'Eidsvoll prestegjeld', year: '1838',
        gard: '234', gardname: 'Vinger gård', lnr: '12', name: 'Anders Hansen', noun: 'matrikkel entry',
        url: 'https://www.digitalarkivet.no/...', accessed: '9 May 2026',
      },
    }],
  },
];

return { NORWEGIAN };
})();
__modules["template.js"] = (() => {
// Template filling. {key} inserts a value; «…» is dropped when any key inside it is blank.
// A blank required value becomes a gap marker ⟦Label⟧: highlighted on screen, copied as [Label].
const GAP_OPEN = '⟦';
const GAP_CLOSE = '⟧';
const GAP_RE = /⟦([^⟧]*)⟧/g;

function isBlank(value) {
  return value === undefined || value === null || String(value).trim() === '';
}

function gap(label) {
  return GAP_OPEN + label + GAP_CLOSE;
}

function hasGap(text) {
  return String(text ?? '').includes(GAP_OPEN);
}

function plain(text) {
  return String(text ?? '').replace(GAP_RE, '[$1]');
}

function gapLabels(text) {
  return [...String(text ?? '').matchAll(GAP_RE)].map(m => m[1]);
}

function templateKeys(template) {
  return [...String(template ?? '').matchAll(/\{(\w+)\}/g)].map(m => m[1]);
}

function fill(template, values, labelOf = key => key) {
  if (!template) return '';
  const kept = template.replace(/«([^»]*)»/g, (_, inner) =>
    templateKeys(inner).some(k => isBlank(values[k])) ? '' : inner);
  return kept.replace(/\{(\w+)\}/g, (_, k) => isBlank(values[k]) ? gap(labelOf(k)) : String(values[k]));
}

return { GAP_OPEN, GAP_CLOSE, isBlank, gap, hasGap, plain, gapLabels, templateKeys, fill };
})();
__modules["records/swedish.js"] = (() => {
// B.2 · Swedish sources.
const { gap } = __modules["template.js"];
const DIGITAL_IMAGE = '{medium}, {platform} ({url} : accessed {accessed})';
const VARMLAND_RA = { platform: 'Riksarkivet', archive: 'Värmlandsarkiv' };
const VARMLAND_AD = { platform: 'ArkivDigital', archive: 'Värmlandsarkiv' };

const PARISH_SOURCE = [
  ['lan', 'Län', 'Värmland'], ['parish', 'Parish', 'Norra Ny'], ['vol', 'Volume', 'AI:11'],
  ['years', 'Years', '1812–1820'], ['call', 'Call number', 'SE/VA/13398/A I/11'],
];
const PAGE_IMAGE = [['page', 'Page', 'blank if unnumbered'], ['image', 'Image', 'if not the page, or if unnumbered']];
const PAGE_IMAGE_ENTRY = [...PAGE_IMAGE, ['entry', 'Entry no.']];
const PARISH_AUTHOR_PIN = ['B.2 §2', 'Parish records, incl. confirmation, communion, minutes | [Parish] församling'];
const UNPAGINATED_PIN = ['B.2 §7', 'Unpaginated fallback is image [I], [entry], [subject]'];

/** Värmland → Värmlands län (Swedish genitive). */
const lanFull = lan => {
  const l = String(lan || '').trim();
  return l ? `${l.endsWith('s') ? l : l + 's'} län` : '';
};

const SWEDISH = [
  {
    id: 'se-husforhor', chapter: 'se', group: 'Parish records (kyrkoarkiv)', name: 'Husförhörslängd',
    hint: 'Clerical survey (household examination); one Source per volume',
    source: PARISH_SOURCE, citation: PAGE_IMAGE, nouns: ['household', 'household examination entry'],
    defaults: VARMLAND_RA, confidence: 'High', doctype: 'enumeration',
    title: 'Sweden, {lan}, {parish}, Husförhörslängder [household examinations] {vol}, {years}',
    abbrev: '{parish} husförhörslängd {vol} ({years})',
    author: '{parish} församling',
    page: '{pageLoc}, {subject}',
    frn: `{parish} församling, Husförhörslängder [household examinations], vol. {vol} ({years}), {pageRef}, {entryof}«, {details}»« (documenting {citedFor})»; ${DIGITAL_IMAGE}; citing {archive}, {call}.`,
    srn: '{parish} husförhörslängd {vol} ({years}), {pageRef}, {srnSubject}.',
    pins: {
      title: [['B.2 §4', 'Clerical survey | Sweden, [län], [parish], Husförhörslängder [household examinations] [vol], [years]']],
      page: [['B.2 §7', 'Husförhörslängd household | p. [P] (image [I]), [Head] household'], UNPAGINATED_PIN],
      author: [PARISH_AUTHOR_PIN],
      abbrev: [['B.2 §10', 'Husförhörslängder | husförhörslängd']],
      confidence: [['B.2 §8', 'Husförhörslängd household | High residence; Normal stated age']],
    },
    examples: [{
      guide: 'B.2 Example 1',
      inputs: {
        lan: 'Värmland', parish: 'Norra Ny', vol: 'AI:11', years: '1812–1820', call: 'SE/VA/13398/A I/11',
        page: '8', image: '19', name: 'Per Persson', noun: 'household',
        url: 'https://sok.riksarkivet.se/bildvisning/C0038409_00019', accessed: '20 April 2026', eventYear: '1812–1820',
        details: 'Ambjörby Torpare',
      },
    }],
  },
  {
    id: 'se-dopbok', chapter: 'se', group: 'Parish records (kyrkoarkiv)', name: 'Födelse- och dopbok',
    hint: 'Birth and baptism book',
    source: PARISH_SOURCE, citation: PAGE_IMAGE_ENTRY, nouns: ['birth and baptism entry', 'birth entry', 'baptism entry'],
    defaults: VARMLAND_AD, confidence: 'Very High', doctype: 'vital record',
    title: 'Sweden, {lan}, {parish}, Födelse- och dopböcker [birth and baptism books] {vol}, {years}',
    abbrev: '{parish} dopbok {vol} ({years})',
    author: '{parish} församling',
    page: '{pageLoc}, no. {entry}, {subject}',
    frn: `{parish} församling, Födelse- och dopböcker [birth and baptism books], vol. {vol} ({years}), {pageRef}, no. {entry}, {entryof}«, {details}»« (documenting {citedFor})»; ${DIGITAL_IMAGE}; citing {archive}, {call}.`,
    srn: '{parish} dopbok {vol} ({years}), {pageRef}, no. {entry}, {srnSubject}.',
    pins: {
      title: [['B.2 §4', 'Birth and baptism | …, Födelse- och dopböcker [birth and baptism books] [vol], [years]']],
      page: [['B.2 §7', 'Birth and baptism | p. [P] (image [I]), no. [N], [Name] birth and baptism entry'], UNPAGINATED_PIN],
      author: [PARISH_AUTHOR_PIN],
      abbrev: [['B.2 §10', 'Födelse- och dopböcker | dopbok']],
      confidence: [['B.2 §8', "Birth and baptism | Very High (child's birth/baptism)"]],
    },
    examples: [],
  },
  {
    id: 'se-vigselbok', chapter: 'se', group: 'Parish records (kyrkoarkiv)', name: 'Lysnings- och vigselbok',
    hint: 'Banns and marriage book',
    source: PARISH_SOURCE, citation: PAGE_IMAGE_ENTRY, nouns: ['marriage entry'],
    defaults: VARMLAND_AD, confidence: 'High', doctype: 'vital record',
    title: 'Sweden, {lan}, {parish}, Lysnings- och Vigselbok [banns and marriage book] {vol}, {years}',
    abbrev: '{parish} vigselbok {vol} ({years})',
    author: '{parish} församling',
    page: '{pageLoc}, no. {entry}, {subject}',
    frn: `{parish} församling, Lysnings- och Vigselbok [banns and marriage book], vol. {vol} ({years}), {pageRef}, no. {entry}, {entryof}«, {details}»« (documenting {citedFor})»; ${DIGITAL_IMAGE}; citing {archive}«, {call}».`,
    srn: '{parish} vigselbok {vol} ({years}), {pageRef}, no. {entry}, {srnSubject}.',
    subjectLabel: 'Couple (Surname-Surname)',
    pins: {
      title: [['B.2 §4', 'Banns and marriage | …, Lysnings- och Vigselbok [banns and marriage book] [vol], [years]']],
      page: [['B.2 §7', 'Banns and marriage | p. [P] (image [I]), no. [N], [Surname]-[Surname] marriage entry'], UNPAGINATED_PIN],
      author: [PARISH_AUTHOR_PIN],
      abbrev: [['B.2 §10', 'Lysnings- och Vigselbok | vigselbok']],
      confidence: [['B.2 §8', 'Banns and marriage | High to Very High']],
    },
    examples: [],
  },
  {
    id: 'se-dodbok', chapter: 'se', group: 'Parish records (kyrkoarkiv)', name: 'Dödbok',
    hint: 'Death and burial book',
    source: PARISH_SOURCE, citation: PAGE_IMAGE_ENTRY, nouns: ['death entry', 'burial entry'],
    defaults: VARMLAND_AD, confidence: 'Very High', doctype: 'vital record',
    title: 'Sweden, {lan}, {parish}, Dödbok [death book] {vol}, {years}',
    abbrev: '{parish} dödbok {vol} ({years})',
    author: '{parish} församling',
    page: '{pageLoc}, no. {entry}, {subject}',
    frn: `{parish} församling, Dödbok [death book], vol. {vol} ({years}), {pageRef}, no. {entry}, {entryof}«, {details}»« (documenting {citedFor})»; ${DIGITAL_IMAGE}; citing {archive}«, {call}».`,
    srn: '{parish} dödbok {vol} ({years}), {pageRef}, no. {entry}, {srnSubject}.',
    pins: {
      title: [['B.2 §4', 'Death / burial | …, Dödbok [death book] [vol], [years]']],
      page: [['B.2 §7', 'Death / burial | p. [P] (image [I]), no. [N], [Name] death entry'], UNPAGINATED_PIN],
      author: [PARISH_AUTHOR_PIN],
      abbrev: [['B.2 §10', 'Dödbok | dödbok']],
      confidence: [['B.2 §8', 'Death/burial entry near the event | Very High']],
    },
    examples: [],
  },
  {
    id: 'se-confirmation', chapter: 'se', group: 'Parish records (kyrkoarkiv)', name: 'Confirmation or communion',
    hint: 'Recorded inside the husförhörslängd; cite it under that volume\'s Source.',
    source: PARISH_SOURCE, citation: PAGE_IMAGE, nouns: ['confirmation entry', 'communion entry'],
    defaults: VARMLAND_RA, confidence: 'High', doctype: 'religious',
    title: 'Sweden, {lan}, {parish}, Husförhörslängder [household examinations] {vol}, {years}',
    abbrev: '{parish} husförhörslängd {vol} ({years})',
    author: '{parish} församling',
    page: '{pageLoc}, {subject}',
    frn: `{parish} församling, Husförhörslängder [household examinations], vol. {vol} ({years}), {pageRef}, {entryof}«, {details}»« (documenting {citedFor})»; ${DIGITAL_IMAGE}; citing {archive}, {call}.`,
    srn: '{parish} husförhörslängd {vol} ({years}), {pageRef}, {srnSubject}.',
    pins: {
      title: [['B.2 §4', "Confirmation and communion use the husförhörslängd's Title."]],
      page: [['B.2 §7', 'Confirmation / communion Pending review | p. [P] (image [I]), [Name] confirmation entry / communion entry'], UNPAGINATED_PIN],
      author: [PARISH_AUTHOR_PIN],
      confidence: [['B.2 §8', 'Confirmation Pending review | High']],
    },
    examples: [{
      guide: 'B.2 Example 4',
      inputs: {
        lan: 'Värmland', parish: 'Norra Ny', vol: 'AI:11', years: '1812–1820', call: 'SE/VA/13398/A I/11',
        page: '8', image: '19', name: 'Lars Persson', noun: 'confirmation entry',
        url: 'https://sok.riksarkivet.se/...', accessed: '20 April 2026',
      },
    }],
  },
  {
    id: 'se-sockenstamma', chapter: 'se', group: 'Parish records (kyrkoarkiv)', name: 'Sockenstämmoprotokoll',
    hint: 'Parish meeting minutes, a series of its own',
    source: PARISH_SOURCE,
    citation: [...PAGE_IMAGE, ['date', 'Meeting date or item no.', 'meeting of 3 May 1850']],
    nouns: ['parish meeting entry'],
    defaults: VARMLAND_AD, confidence: 'High', doctype: 'religious',
    title: 'Sweden, {lan}, {parish}, Sockenstämmoprotokoll [parish meeting minutes] {vol}, {years}',
    abbrev: '{parish} sockenstämmoprotokoll {vol} ({years})',
    author: '{parish} församling',
    page: '{pageLoc}, {date}, {subject}',
    frn: `{parish} församling, Sockenstämmoprotokoll [parish meeting minutes], vol. {vol} ({years}), {pageRef}, {date}, {entryof}«, {details}»« (documenting {citedFor})»; ${DIGITAL_IMAGE}; citing {archive}«, {call}».`,
    srn: '{parish} sockenstämmoprotokoll {vol} ({years}), {pageRef}, {srnSubject}.',
    pins: {
      title: [['B.2 §4', 'Meeting minutes Pending review | …, Sockenstämmoprotokoll [parish meeting minutes] [vol], [years]']],
      page: [['B.2 §7', 'Meeting minutes Pending review | p. [P] (image [I]), [date or item no.], [Name] parish meeting entry'], UNPAGINATED_PIN],
      author: [PARISH_AUTHOR_PIN],
      abbrev: [['B.2 §10', 'Sockenstämmoprotokoll Pending review | sockenstämmoprotokoll']],
      confidence: [['B.2 §8', "Meeting minutes Pending review | High for the meeting's business"]],
    },
    examples: [],
  },
  {
    id: 'se-bouppteckning', chapter: 'se', group: 'Court, census and land', name: 'Bouppteckning',
    hint: 'Estate inventory (häradsrätt); the locality is the härad, not the parish',
    source: [
      ['lan', 'Län', 'Värmland'], ['harad', 'Härad', 'Älvdals härad'], ['court', 'Court (creating body)', 'Älvdals häradsrätt'],
      ['cgloss', 'Court gloss', 'Älvdal district court'], ['vol', 'Volume', 'FII:26'], ['years', 'Years', '1832–1833'],
      ['call', 'Call number', 'SE/VA/11047/F II/26'],
    ],
    citation: [['pages', 'Pages', '203–205']],
    nouns: ['estate inventory'],
    defaults: VARMLAND_AD, confidence: 'High', doctype: 'legal',
    title: 'Sweden, {lan}, {harad}, Bouppteckningar [estate inventories] {vol}, {years}',
    abbrev: '{court} bouppteckning {vol} ({years})',
    author: '{court}',
    page: 'pp. {pages}, {subject}',
    frn: `{court} [{cgloss}], Bouppteckningar [estate inventories], vol. {vol} ({years}), pp. {pages}, {entryof}«, {details}»« (documenting {citedFor})»; ${DIGITAL_IMAGE}; citing {archive}, {call}.`,
    srn: '{court} bouppteckning {vol} ({years}), pp. {pages}, {srnSubject}.',
    subjectLabel: 'Deceased',
    detailsLabel: 'Entry details (farm, parish, death)',
    pins: {
      title: [['B.2 §4', 'Estate inventory | Sweden, [län], [härad], Bouppteckningar [estate inventories] [vol], [years]']],
      page: [['B.2 §7', 'Estate inventory | pp. [P]–[P], [Deceased] estate inventory']],
      author: [['B.2 §2', 'Court and other state bodies | The creating body, e.g. Älvdals häradsrätt']],
      abbrev: [['B.2 §10', 'Bouppteckningar | bouppteckning | Älvdals häradsrätt bouppteckning FII:26 (1832–1833)']],
      confidence: [['B.2 §8', 'Bouppteckning | High']],
    },
    examples: [{
      guide: 'B.2 Example 2',
      inputs: {
        lan: 'Värmland', harad: 'Älvdals härad', court: 'Älvdals häradsrätt', cgloss: 'Älvdal district court',
        vol: 'FII:26', years: '1832–1833', call: 'SE/VA/11047/F II/26', pages: '203–205',
        name: 'Per Persson', noun: 'estate inventory',
        url: 'https://app.arkivdigital.se/volume/v48177?image=104', accessed: '20 April 2026', eventYear: '1832',
        details: 'Ambjörbymon, Norra Ny parish, died 5 May 1832',
      },
    }],
  },
  {
    id: 'se-folkrakning', chapter: 'se', group: 'Court, census and land', name: 'Folkräkning (SVAR)',
    hint: 'Census database; one Source per parish per count year',
    source: [['lan', 'Län', 'Värmland'], ['parish', 'Parish', 'Norra Ny'], ['year', 'Count year', '1880'], ['call', 'Call number', 'Folk_817085']],
    citation: [...PAGE_IMAGE, ['row', 'Row'], ['fam', 'Family no.']],
    nouns: ['household', 'census entry'],
    defaults: { platform: 'Riksarkivet', pubmedium: 'Database with images' },
    confidence: 'High', doctype: 'enumeration', eventDate: 'year',
    derive: v => ({ lanfull: lanFull(v.lan) }),
    title: 'Sweden, {lan}, {parish}, Folkräkning [census] {year}',
    abbrev: '{parish} folkräkning {year}',
    author: 'Riksarkivet',
    page: '{pageLoc}, row {row}, family no. {fam}, {subject}',
    frn: `Sveriges folkräkning {year} [Swedish census {year}], {parish} församling, {lanfull}, {pageRef}, row {row}, family no. {fam}, {entryof}«, {details}»« (documenting {citedFor})»; ${DIGITAL_IMAGE}.`,
    srn: '{parish} folkräkning {year}, {pageRef}, row {row}, {srnSubject}.',
    pins: {
      title: [['B.2 §4', 'SVAR census | Sweden, [län], [parish], Folkräkning [census] [year]']],
      page: [['B.2 §7', 'SVAR census | p. [P] (image [I]), row [R], family no. [F], [Head] household'], UNPAGINATED_PIN],
      author: [['B.2 §2', 'SVAR databases and other central records | Riksarkivet (covers SVAR)']],
      abbrev: [['B.2 §10', 'Folkräkning | folkräkning']],
      confidence: [['B.2 §8', 'SVAR with images | High residence; Normal ages']],
    },
    examples: [{
      guide: 'B.2 Example 3',
      inputs: {
        lan: 'Värmland', parish: 'Norra Ny', year: '1880', call: 'Folk_817085',
        page: '4', row: '33', fam: '1', name: 'Lars Persson Ambjörn', noun: 'household',
        url: 'https://sok.riksarkivet.se/bildvisning/Folk_817085-004', accessed: '21 April 2026',
        details: 'Ambjörby',
      },
    }],
  },
  {
    id: 'se-lantmateriet', chapter: 'se', group: 'Court, census and land', name: 'Lantmäteriet survey act',
    hint: 'Laga skifte, storskifte, ägodelning…; one numbered act = one Source',
    source: [
      ['lan', 'Län', 'Värmland'], ['parish', 'Parish', 'Norra Ny'], ['farm', 'Farm', 'Ambjörby'],
      ['stype', 'Survey type', 'laga skifte'], ['stgloss', 'Survey type gloss', 'statutory land enclosure'],
      ['act', 'Act number', '17-NON-148'], ['years', 'Years', '1856–1862'], ['call', 'Call number'],
    ],
    citation: [['protocol', 'Protocol locator', 'delningsbeskrivning p. 40']],
    note: [['survey', 'Survey details (FRN)', 'surveyed … by …, confirmed by … on …']],
    nouns: ['land allotment entry', 'signatory entry', 'croft transfer entry'],
    defaults: { platform: 'Lantmäteriet' },
    confidence: 'High', doctype: 'legal',
    derive: v => ({
      surveyAuthor: /^R/i.test(String(v.act || '').trim()) ? 'Lantmäteristyrelsen' : `Lantmäterimyndigheten i ${lanFull(v.lan) || gap('Län')}`,
    }),
    title: 'Sweden, {lan}, {parish}, {stype} [{stgloss}], act {act}, {years}',
    abbrev: '{parish} {stype} {act} ({years})',
    author: '{surveyAuthor}',
    page: '{protocol}, {subject}',
    frn: `{author}, {stype} [{stgloss}], {farm}, {parish} socken, act {act}«, {survey}»; {protocol}, {details}« (documenting {citedFor})»; ${DIGITAL_IMAGE}.`,
    srn: '{parish} {stype} {act} ({years}), {protocol}, {srnSubject}.',
    detailsLabel: 'Entry description (FRN)',
    paperlessTitle: '{farm} {stype} {eventYear}',
    pins: {
      title: [['B.2 §4', 'Land survey Pending review | Sweden, [län], [parish], [survey type] [English gloss], act [act-no], [years]']],
      page: [['B.2 §7', 'Land survey Pending review | [protocol locator], [name] [record-noun]']],
      author: [['B.2 §2', 'Land survey, NN-XXX-NNN county series (e.g. 17-NON-148) Pending review | Lantmäterimyndigheten i Värmlands län']],
      abbrev: [['B.2 §10', 'Land survey Pending review | ägodelning / storskifte / laga skifte / enskifte / gränsbestämning / avvittring']],
      confidence: [['B.2 §8', 'Land survey Pending review | High for what the surveyor recorded']],
      plTitle: [['C1', 'Land survey Pending review | Farm-led: [Farm] [survey type] [completion year]']],
    },
    examples: [{
      guide: 'B.2 Example 5',
      inputs: {
        lan: 'Värmland', parish: 'Norra Ny', farm: 'Ambjörby', stype: 'laga skifte', stgloss: 'statutory land enclosure',
        act: '17-NON-148', years: '1856–1862', protocol: 'delningsbeskrivning p. 40',
        name: 'Marit Andersdotter', noun: 'land allotment entry', says: 'Lott A, 64 öre 6 penningar', afterNoun: true,
        survey: 'surveyed 1856–1862 by O. Ignelius, confirmed by Älvdals övre tingslags egodelningsrätt 3 October 1863',
        details: 'land allotment (Lott A) of the minor Marit Andersdotter, 64 öre 6 penningar skatt',
        url: 'https://historiskakartor.lantmateriet.se', accessed: '16 June 2026', eventYear: '1862',
      },
    }],
  },
];

return { SWEDISH };
})();
__modules["tables.js"] = (() => {
// Lookup tables shared by every record type. PLATFORMS and STATE_ABBREV are pinned to the
// guide's own tables (A10, B.3 §10) by test/tables.test.js.

const CHAPTERS = { no: 'Norwegian', se: 'Swedish', us: 'US', pp: 'Published & personal' };
const CHAPTER_CODE = { no: 'B.1', se: 'B.2', us: 'B.3', pp: 'B.4' };

const LEVELS = ['Very High', 'High', 'Normal', 'Low', 'Very Low'];

// A10 · Platforms: homepage URLs.
const PLATFORMS = {
  'Digitalarkivet': 'https://www.digitalarkivet.no',
  'Riksarkivet': 'https://sok.riksarkivet.se',
  'ArkivDigital': 'https://www.arkivdigital.se',
  'Nasjonalbiblioteket': 'https://www.nb.no',
  'Ancestry': 'https://www.ancestry.com',
  'FamilySearch': 'https://www.familysearch.org',
  'Find a Grave': 'https://www.findagrave.com',
  'Newspapers.com': 'https://www.newspapers.com',
  'Fold3': 'https://www.fold3.com',
  'Chronicling America': 'https://chroniclingamerica.loc.gov',
  'GenealogyBank': 'https://www.genealogybank.com',
  'YouTube': 'https://www.youtube.com',
  'Lantmäteriet': 'https://historiskakartor.lantmateriet.se',
};

// B.3 §10 · traditional state abbreviations (never USPS codes).
const STATE_ABBREV = {
  'Minnesota': 'Minn.', 'Wisconsin': 'Wis.', 'Iowa': 'Iowa', 'South Dakota': 'S. Dak.',
  'North Dakota': 'N. Dak.', 'New York': 'N.Y.', 'Massachusetts': 'Mass.', 'Connecticut': 'Conn.',
  'California': 'Cal.', 'Illinois': 'Ill.', 'Michigan': 'Mich.', 'Virginia': 'Va.', 'Pennsylvania': 'Pa.',
};

// Archive suggestions per chapter (each chapter's §3).
const ARCHIVES = {
  no: ['Statsarkivet i Oslo', 'Statsarkivet i Hamar', 'Riksarkivet'],
  se: ['Värmlandsarkiv', 'Riksarkivet'],
  us: ['National Archives', 'Minnesota Historical Society', 'Swenson Swedish Immigration Research Center', 'Family History Library'],
  pp: ['Minnesota Historical Society', 'Library of Virginia'],
};

// A7 parenthetical suggestions per chapter (§9): 1 which entry, 2 source says, 3 evidence.
const SUGGESTIONS = {
  no: { which: ['daughter of ', 'son of ', 'at ', 'b. ', 'd. ', 'senior', 'junior'],
    says: ['tjenestepige', 'tjenestedreng', 'fattigdreng', 'tyende', 'inderst', 'husmand', 'enke', 'enkemann', 'første ekteskap', 'annen ekteskap'],
    evidence: ['stated age ', 'birth year inferred from age', 'named at '] },
  se: { which: ['b. ', 'd. ', 'at ', 'junior', 'servant'],
    says: ['widower', 'widow', 'both in first marriage', 'retired soldier', 'unmarried'],
    evidence: ['birth year inferred from age', 'stated age ', 'named at ', 'witness at '] },
  us: { which: ['b. ', 'd. ', 'of  Co.', 'senior', 'junior', 'ED '],
    says: ['head', 'wife of head', 'son', 'daughter', 'boarder', 'lodger', 'servant', 'widow', 'widower', 'declared', 'naturalized ', 'both in first marriage', 'by license', 'by banns', 'delayed registration', 'amended', 'discharged', 'laborer'],
    evidence: ['birth year inferred from age', 'birth years inferred from ages', 'stated age ', 'named at ', 'parents named at ', 'informant on ', 'next of kin on ', 'witness at ', 'identified by initials only', 'birthplace inferred from naturalization'] },
  pp: { which: ['b. ', 'd. ', 'at ', 'senior', 'junior'],
    says: ['written contemporaneously', 'compiled later', 'damaged page', 'in unrelated handwriting'],
    evidence: ['reported by ', 'handwritten by ', 'uncited claim in published work', 'second-hand'] },
};

// C2 document types and their default C4 date meaning.
const DATE_MEANING = {
  'vital record': 'event', 'enumeration': 'event', 'legal': 'event', 'immigration': 'event',
  'military': 'event', 'religious': 'event', 'correspondence': 'creation', 'ephemera': 'event',
  'publication': 'publication', 'artifact': 'creation', 'research': 'creation', 'interview': 'event',
};

// A10 · the medium that opens a genealogical record's Pubinfo; the first is the default. Microfilm is film
// read on a reader at a library or archive.
const MEDIA = ['Digital images', 'Database with images', 'Database', 'Microfilm'];

// A7 · the forms a cited copy or index takes; an original has none ('').
const COPY_FORMS = ['index entry', 'transcript', 'extract', 'abstract'];

const MONTHS = ['january', 'february', 'march', 'april', 'may', 'june', 'july', 'august', 'september', 'october', 'november', 'december'];

/** '14 March 1925' → '1925-03-14'; anything else → ''. */
function isoDate(text) {
  const m = String(text ?? '').trim().match(/^(\d{1,2}) ([A-Za-z]+) (\d{4})$/);
  if (!m) return '';
  const month = MONTHS.indexOf(m[2].toLowerCase()) + 1;
  return month ? `${m[3]}-${String(month).padStart(2, '0')}-${m[1].padStart(2, '0')}` : '';
}

/** The first four-digit year in a date ('12 March 1897' → '1897'); '' when there is none. */
function yearOf(text) {
  return (String(text ?? '').match(/\d{4}/) || [''])[0];
}

function lastWord(text) {
  return String(text ?? '').trim().split(/\s+/).pop() || '';
}

function allButLastWord(text) {
  return String(text ?? '').trim().split(/\s+/).slice(0, -1).join(' ');
}

function stateAbbrev(state) {
  return STATE_ABBREV[String(state ?? '').trim()] || String(state ?? '').trim();
}

return { CHAPTERS, CHAPTER_CODE, LEVELS, PLATFORMS, STATE_ABBREV, ARCHIVES, SUGGESTIONS, DATE_MEANING, MEDIA, COPY_FORMS, isoDate, yearOf, lastWord, allButLastWord, stateAbbrev };
})();
__modules["records/us.js"] = (() => {
// B.3 · US sources.
const { stateAbbrev } = __modules["tables.js"];
const { gap } = __modules["template.js"];

const DIGITAL_IMAGE = '{medium}, {platform} ({url} : accessed {accessed})';
const NARA_ANCESTRY = { platform: 'Ancestry', archive: 'National Archives' };
const NARA_FS = { platform: 'FamilySearch', archive: 'National Archives' };
const NARA_FOLD3 = { platform: 'Fold3', archive: 'National Archives' };
const MHS_ANCESTRY = { platform: 'Ancestry', archive: 'Minnesota Historical Society' };

const US = [
  {
    id: 'us-federal-census', chapter: 'us', group: 'Census', name: 'Federal census',
    hint: 'One Source per county, state, and year; the roll goes in the page string',
    source: [['year', 'Census year', '1920'], ['county', 'County', 'St. Louis'], ['state', 'State', 'Minnesota'], ['call', 'NARA publication', 'T625']],
    citation: [['roll', 'Roll'], ['ed', 'ED'], ['sheet', 'Sheet', '8A'], ['dwelling', 'Dwelling'], ['family', 'Family']],
    note: [['locality', 'Locality (FRN)', 'Duluth']],
    nouns: ['household', 'census entry'],
    defaults: NARA_ANCESTRY, confidence: 'High', doctype: 'enumeration', eventDate: 'year',
    derive: v => ({ stab: stateAbbrev(v.state) }),
    title: '{year} U.S. Federal Census, {county} County, {state}',
    abbrev: '{county} Co., {stab}, {year} census',
    author: 'Bureau of the Census',
    page: 'roll {roll}, ED {ed}, sheet {sheet}, dwelling {dwelling}, family {family}, {subject}',
    frn: `{year} U.S. census, {county} County, {state}, population schedule, {locality}, enumeration district {ed}, sheet {sheet}, dwelling {dwelling}, family {family}, {subject}« (documenting {citedFor})»; ${DIGITAL_IMAGE}; citing {archive} microfilm publication {call}, roll {roll}.`,
    frnMicrofilm: '{year} U.S. census, {county} County, {state}, population schedule, {locality}, enumeration district {ed}, sheet {sheet}, dwelling {dwelling}, family {family}, {subject}« (documenting {citedFor})»; {archive} microfilm publication {call}, roll {roll}.',
    srn: '{year} U.S. census, {county} Co., {stab}, pop. sched., {locality}, ED {ed}, sheet {sheet}, {subject}.',
    subjectLabel: 'Head (or person)',
    pins: {
      title: [['B.3 §4', 'Federal census | [year] U.S. Federal Census, [county] County, [state]']],
      page: [['B.3 §7', 'Federal census | roll [N], ED [N], sheet [N]A/B, dwelling [N], family [N], [Head] household']],
      author: [['B.3 §2', 'Federal census | Bureau of the Census']],
      confidence: [['B.3 §8', 'Federal census | High for residence and household; Normal for ages, birthplaces']],
    },
    examples: [{
      guide: 'B.3 Example 1',
      inputs: {
        year: '1920', county: 'St. Louis', state: 'Minnesota', call: 'T625',
        roll: '859', ed: '139', sheet: '8A', dwelling: '[N]', family: '[N]', name: 'Steve Maisuk', noun: 'household',
        locality: 'Duluth', url: 'https://www.ancestry.com/...', accessed: '6 May 2026',
      },
    }],
  },
  {
    id: 'us-state-census', chapter: 'us', group: 'Census', name: 'State census',
    hint: 'One Source per county, state, and year',
    source: [['year', 'Census year', '1905'], ['state', 'State', 'Minnesota'], ['county', 'County', 'St. Louis'], ['call', 'Call number']],
    citation: [['ward', 'Ward or township'], ['page', 'Page'], ['line', 'Line']],
    nouns: ['household', 'census entry'],
    defaults: MHS_ANCESTRY, confidence: 'High', doctype: 'enumeration', eventDate: 'year',
    derive: v => ({ stab: stateAbbrev(v.state) }),
    title: '{year} {state} State Census, {county} County',
    abbrev: '{county} Co., {stab}, {year} state census',
    author: '{state} Population Census Office',
    page: '{ward}, p. {page}, line {line}, {subject}',
    frn: `{year} {state} state census, {county} County, {ward}, p. {page}, line {line}, {subject}« (documenting {citedFor})»; ${DIGITAL_IMAGE}; citing {archive}.`,
    srn: '{year} {stab} state census, {county} Co., {ward}, p. {page}, {subject}.',
    subjectLabel: 'Head (or person)',
    pins: {
      title: [['B.3 §4', 'State census | [year] [state] State Census, [county] County']],
      page: [['B.3 §7', 'State census | [ward or township], p. [N], line [N], [Head] household']],
      author: [['B.3 §2', 'State census | [State] Population Census Office']],
    },
    examples: [],
  },
  {
    id: 'us-vital', chapter: 'us', group: 'Vital records', name: 'State vital record',
    hint: 'Death, birth, or marriage record; one Source per state collection',
    source: [['state', 'State', 'Minnesota'], ['series', 'Record series', 'death certificates'], ['years', 'Years', '1908–2002'], ['call', 'Call number (often blank)']],
    citation: [],
    pageVariants: [
      {
        key: 'certificate', label: 'Certificate',
        citation: [['cert', 'Certificate no.']],
        nouns: ['death certificate', 'birth certificate'],
        page: 'certificate no. {cert}, {subject}',
        frn: `{state}, {kind} no. {cert} ({eventYear}), {name}« (documenting {citedFor})»; {author}; ${DIGITAL_IMAGE}; citing {archive}.`,
        srn: '{stab} {kindShort} {cert} ({eventYear}), {name}.',
      },
      {
        key: 'license', label: 'Marriage license',
        citation: [['license', 'License no.']],
        nouns: ['marriage license'],
        page: 'license no. {license}, {subject}',
        frn: `{state}, marriage license no. {license} ({eventYear}), {name}« (documenting {citedFor})»; {author}; ${DIGITAL_IMAGE}; citing {archive}.`,
        srn: '{stab} marriage license {license} ({eventYear}), {name}.',
      },
    ],
    nouns: ['death certificate', 'birth certificate', 'marriage license'],
    defaults: { platform: 'FamilySearch', pubmedium: 'Database with images', archive: 'Minnesota Historical Society' },
    confidence: 'Very High', doctype: 'vital record',
    derive: v => {
      const series = String(v.series || '').toLowerCase();
      const kind = /birth/.test(series) ? 'birth certificate' : /marr/.test(series) ? 'marriage certificate' : 'death certificate';
      return {
        stab: stateAbbrev(v.state),
        kind,
        kindShort: { 'birth certificate': 'birth cert.', 'marriage certificate': 'marr. cert.', 'death certificate': 'death cert.' }[kind],
      };
    },
    title: '{state}, {series}, {years}',
    abbrev: '{stab} {series}, {years}',
    author: '{state} Department of Health, Vital Records',
    pins: {
      title: [['B.3 §4', 'State vital records | [State], [record series], [years]']],
      page: [
        ['B.3 §7', 'Death / birth certificate | certificate no. [N], [Name] death certificate / birth certificate'],
        ['B.3 §7', 'Marriage license | license no. [N], [Surname]-[Surname] marriage license'],
      ],
      author: [['B.3 §2', 'State vital records | [State] Department of Health, Vital Records']],
      confidence: [['B.3 §8', 'State death certificate (post-1900) | Very High for the death']],
    },
    examples: [{
      guide: 'B.3 Example 2',
      inputs: {
        state: 'Minnesota', series: 'death certificates', years: '1908–2002', variant: 'certificate',
        cert: '1929-MN-XXXXXX', name: 'Per Larsson Grund', noun: 'death certificate',
        url: 'https://www.familysearch.org/...', accessed: '6 May 2026', eventYear: '1929',
      },
    }],
  },
  {
    id: 'us-church', chapter: 'us', group: 'Vital records', name: 'Church record',
    hint: "Baptism, confirmation, marriage, burial; one Source per congregation's record set",
    source: [
      ['state', 'State', 'Minnesota'], ['county', 'County', 'Marshall'], ['town', 'Town', 'Warren'],
      ['church', 'Church', 'First Lutheran Church'], ['years', 'Years (Abbrev)', '1800–1952'], ['call', 'Archive reference'],
    ],
    citation: [['register', 'Register', 'death and burial register'], ['page', 'Page'], ['image', 'Image', 'if not the page']],
    note: [['collection', 'Digitized collection name'], ['citing', 'Citing, after the archive']],
    nouns: ['death and burial entry', 'baptism entry', 'confirmation entry', 'marriage entry', 'burial entry', 'membership entry'],
    defaults: { platform: 'Ancestry', archive: 'Swenson Swedish Immigration Research Center' },
    confidence: 'Very High', doctype: 'religious',
    derive: v => ({ stab: stateAbbrev(v.state) }),
    title: '{state}, {county} County, {town}, {church} records',
    abbrev: '{church}, {town}, {stab}, records«, {years}»',
    author: '{church}, {town}',
    page: '{register}, p. {page}« (image {image})», {subject}',
    frn: `{church} ({town}, {county} County, {state}), {register}, p. {page}« (image {image})», {details}« (documenting {citedFor})»; ${DIGITAL_IMAGE}«, "{collection}"»; citing {archive}«, {citing}».`,
    srn: '{church} ({town}, {stab}), {entryof}, p. {page}.',
    detailsLabel: 'Entry description (FRN)',
    pins: {
      title: [['B.3 §4', 'Church records Pending review | [State], [county], [town], [Church name] records']],
      page: [['B.3 §7', 'Church record Pending review | [register], p. [P] (image [I]), [Name] [record-noun]']],
      author: [['B.3 §2', 'Church records Pending review | [Church name], [town]']],
      confidence: [['B.3 §8', 'Church register Pending review | Very High for the recorded event']],
    },
    examples: [{
      guide: 'B.3 Example 11',
      inputs: {
        state: 'Minnesota', county: 'Marshall', town: 'Warren', church: 'First Lutheran Church', years: '1800–1952',
        register: 'death and burial register', page: '283', image: '496, right',
        name: 'Emma Söderström', noun: 'death and burial entry',
        details: 'death and burial of Emma Söderström, died 7 May 1914, buried 9 May 1914',
        url: 'https://www.ancestry.com/search/collections/61584/records/63230716', accessed: '16 June 2026', eventYear: '1914',
        collection: 'U.S., Evangelical Lutheran Church in America, Swedish American Church Records, 1800–1952',
        citing: 'Augustana College, Rock Island, Illinois',
      },
    }],
  },
  {
    id: 'us-naturalization', chapter: 'us', group: 'Immigration and military', name: 'Naturalization',
    hint: 'Petition or declaration of intention; one Source per court collection',
    source: [
      ['state', 'State', 'Minnesota'], ['county', 'County', 'St. Louis'], ['court', 'Court', 'St. Louis County District Court'],
      ['years', 'Years', '1888–1955'], ['call', 'Call number (microfilm)', 'SAM 227'],
    ],
    citation: [],
    note: [['courtplace', 'Court seat (FRN)', 'Duluth, Minnesota'], ['platformRef', 'Image group or collection ID (FRN)', 'Image Group Number 101714756, image 62']],
    pageVariants: [
      {
        key: 'petition', label: 'Petition',
        citation: [['pet', 'Petition no.']],
        nouns: ['naturalization petition'],
        page: 'petition no. {pet}, {subject}',
        frn: `{court} ({courtplace}), Naturalization Records, petition no. {pet} ({eventYear}), {name}« (documenting {citedFor})»; ${DIGITAL_IMAGE}«, {platformRef}»; citing {archive}« microfilm {call}».`,
        frnMicrofilm: '{court} ({courtplace}), Naturalization Records, petition no. {pet} ({eventYear}), {name}« (documenting {citedFor})»; {archive} microfilm {call}.',
        srn: '{county} Co. natz., pet. no. {pet} ({eventYear}), {name}.',
      },
      {
        key: 'declaration', label: 'Declaration of intention',
        citation: [['decl', 'Declaration no.']],
        nouns: ['declaration of intention'],
        page: 'declaration no. {decl}, {subject}',
        frn: `{court} ({courtplace}), Naturalization Records, declaration of intention no. {decl} ({eventYear}), {name}« (documenting {citedFor})»; ${DIGITAL_IMAGE}«, {platformRef}»; citing {archive}« microfilm {call}».`,
        frnMicrofilm: '{court} ({courtplace}), Naturalization Records, declaration of intention no. {decl} ({eventYear}), {name}« (documenting {citedFor})»; {archive} microfilm {call}.',
        srn: '{county} Co. natz., decl. no. {decl} ({eventYear}), {name}.',
      },
      {
        // Before 1906 a county court bound final papers in lettered volumes, usually without petition numbers.
        key: 'final', label: 'Final papers (before 1906)', eventDate: 'signed',
        citation: [
          ['reel', 'Microfilm reel', 'if known'], ['vol', 'Volume', 'C'], ['page', 'Page', 'blank if unnumbered'],
          ['image', 'Image', 'if not the page, or if unnumbered'], ['signed', 'Date signed', '12 March 1897'],
        ],
        nouns: ['naturalization petition'],
        page: '«reel {reel}, »final papers vol. {vol}, {pageLoc}, {subject}',
        frn: `{court} ({courtplace}), Naturalization Records, final papers vol. {vol}, {pageRef} ({signed}), {name}« (documenting {citedFor})»; ${DIGITAL_IMAGE}«, {platformRef}»; citing {archive}« microfilm {call}»«, reel {reel}».`,
        frnMicrofilm: '{court} ({courtplace}), Naturalization Records, final papers vol. {vol}, {pageRef} ({signed}), {name}« (documenting {citedFor})»; {archive} microfilm {call}«, reel {reel}».',
        srn: '{county} Co. natz., final papers vol. {vol}, {pageRef} ({eventYear}), {name}.',
      },
    ],
    nouns: ['naturalization petition', 'declaration of intention'],
    defaults: MHS_ANCESTRY, confidence: 'High', doctype: 'immigration',
    // The court takes the locality slot after its county: St. Louis County District Court → District Court.
    derive: v => {
      const court = String(v.court || '').trim(), county = `${String(v.county || '').trim()} County `;
      return { courtShort: !court ? gap('Court') : court.startsWith(county) ? court.slice(county.length) : court };
    },
    title: '{state}, {county} County, {courtShort}, Naturalization Records, {years}',
    abbrev: '{county} Co. naturalizations, {years}',
    author: '{court}',
    pins: {
      title: [['B.3 §4', 'Naturalization | [State], [county] County, [court], Naturalization Records, [years]']],
      page: [
        ['B.3 §7', 'Naturalization petition | petition no. [N], [Name] naturalization petition'],
        ['B.3 §7', 'Declaration of intention | declaration no. [N], [Name] declaration of intention'],
        ['B.3 §7', 'Final papers volume (before 1906) | reel [N], final papers vol. [V], p. [P] (image [I]), [Name] naturalization petition'],
        ['B.3 §7', 'With no page number, the image number takes the page\'s place: final papers vol. [V], image [I], [Name] naturalization petition'],
      ],
      author: [['B.3 §2', 'State/county court naturalization | [Court name]']],
      callNumber: [['B.3 §5', 'State archives microfilm (Minnesota Historical Society SAM 227) | Call number']],
      frnMicrofilm: [['B.3 §12', 'an FRN that ends with the film: …, Peter L. Grund; Minnesota Historical Society microfilm SAM 227, reel 4.'], ['A10', 'Film read in person has no URL or access date']],
      confidence: [['B.3 §8', 'Naturalization (declaration, petition, final papers) | High for the act recorded']],
    },
    examples: [{
      guide: 'B.3 Example 3',
      inputs: {
        state: 'Minnesota', court: 'St. Louis County District Court', county: 'St. Louis', years: '1888–1955', variant: 'petition',
        pet: '[N]', name: 'Per Larsson', noun: 'naturalization petition', courtplace: 'Duluth, Minnesota',
        url: 'https://www.ancestry.com/...', accessed: '6 May 2026', eventYear: '1894',
      },
    }, {
      guide: 'B.3 Example 12',
      inputs: {
        state: 'Minnesota', county: 'Marshall', court: 'Marshall County District Court', years: '1853–1967', call: 'SAM 227', variant: 'final',
        reel: '4', vol: 'C', page: '296', image: '[I]', signed: '12 March 1897', name: 'Peter L. Grund', noun: 'naturalization petition',
        courtplace: 'Warren, Minnesota', platform: 'FamilySearch', url: 'https://www.familysearch.org/ark:/61903/3:1:...', accessed: '[date]',
        platformRef: 'Image Group Number 101714756, image [I]',
      },
    }],
  },
  {
    id: 'us-draft-card', chapter: 'us', group: 'Immigration and military', name: 'WWII draft card',
    hint: 'Selective Service registration; one Source per state series',
    source: [['state', 'State', 'Minnesota'], ['call', 'Record group', 'RG 147']],
    citation: [['serial', 'Serial no.']],
    nouns: ['WWII draft card'],
    defaults: NARA_FS, confidence: 'High', doctype: 'military',
    derive: v => ({ stab: stateAbbrev(v.state), recordGroup: String(v.call || '').trim().replace(/^RG\s*/, 'Record Group ') }),
    title: 'World War II Draft Registration Cards, {state}',
    abbrev: 'WWII draft cards, {stab}',
    author: 'Selective Service System',
    page: 'serial no. {serial}, {subject}',
    frn: `{author}, World War II Draft Registration Cards, {state}, serial no. {serial}, {name} ({eventYear})« (documenting {citedFor})»; ${DIGITAL_IMAGE}; citing {recordGroup}, {archive}.`,
    srn: 'WWII draft card, {stab}, {name}.',
    pins: {
      title: [['B.3 §4', 'WWII draft cards | World War II Draft Registration Cards, [state]']],
      page: [['B.3 §7', 'WWII draft card | serial no. [N], [Name] WWII draft card']],
      author: [['B.3 §2', 'WWII draft cards | Selective Service System']],
    },
    examples: [{
      guide: 'B.3 Example 5',
      inputs: {
        state: 'Minnesota', call: 'RG 147', serial: '[N]', name: 'Axel O. Grund', noun: 'WWII draft card',
        url: 'https://www.familysearch.org/...', accessed: '6 May 2026', eventYear: '1942',
      },
    }],
  },
  {
    id: 'us-headstone', chapter: 'us', group: 'Immigration and military', name: 'Headstone application',
    hint: 'Applications for Headstones series',
    source: [['years', 'Series years', '1925–1941'], ['call', 'Record group', 'RG 92']],
    citation: [['dyear', 'Death year']],
    note: [['citing', 'Citing clause', 'NAID …, Record Group 92, National Archives at …']],
    nouns: ['headstone application'],
    defaults: { platform: 'Ancestry' }, confidence: 'Normal', doctype: 'military', eventDate: 'dyear',
    title: 'Applications for Headstones for U.S. Military Veterans, {years}',
    abbrev: 'Headstone applications, {years}',
    author: 'Office of the Quartermaster General',
    page: '{name} (d. {dyear}) {noun}',
    frn: `{author}, "Applications for Headstones for U.S. Military Veterans, {years}," application for {name}«, {details}»« (documenting {citedFor})»; ${DIGITAL_IMAGE}; citing {citing}.`,
    srn: 'Headstone app., {name} (d. {dyear}).',
    detailsLabel: 'Application details (death date)',
    pins: {
      title: [['B.3 §4', 'Headstone applications | Applications for Headstones for U.S. Military Veterans, [years]']],
      page: [['B.3 §7', 'Headstone application | [Name] (d. [year]) headstone application']],
      author: [['B.3 §2', 'Headstone applications | Office of the Quartermaster General']],
      confidence: [['B.3 §8', 'Headstone application | Normal for death date; High for military service']],
    },
    examples: [{
      guide: 'B.3 Example 6',
      inputs: {
        years: '1925–1941', call: 'RG 92', dyear: '1948', name: 'Axel O. Grund', noun: 'headstone application',
        details: 'died 31 October 1948', url: 'https://www.ancestry.com/search/collections/2375/records/45037', accessed: '6 May 2026',
        citing: 'NAID 596118, Record Group 92, National Archives at Washington, DC',
      },
    }],
  },
  {
    id: 'us-civil-war-pension', chapter: 'us', group: 'Immigration and military', name: 'Civil War pension',
    hint: 'Civil War Pension Application Files (NARA RG 15)',
    source: [['call', 'Call number', 'RG 15']],
    citation: [['app', 'Application no.'], ['cert', 'Certificate no.']],
    nouns: ['pension file'],
    defaults: NARA_FOLD3, confidence: '', doctype: 'military',
    title: 'Civil War Pension Application Files',
    abbrev: 'Civil War pension files',
    author: 'Bureau of Pensions',
    page: 'application no. {app}, certificate no. {cert}, {subject}',
    frn: `{author}, Civil War Pension Application Files, application no. {app}, certificate no. {cert}, {name}«, {details}»« (documenting {citedFor})»; ${DIGITAL_IMAGE}; citing {archive}«, {call}».`,
    srn: 'Civil War pension, app. {app}, {name}.',
    pins: {
      title: [['B.3 §4', 'Civil War pensions | Civil War Pension Application Files']],
      page: [['B.3 §7', 'Civil War pension | application no. [N], certificate no. [N], [Name] pension file']],
      author: [['B.3 §2', 'Civil War pensions | Bureau of Pensions']],
    },
    examples: [],
  },
  {
    id: 'us-service-record', chapter: 'us', group: 'Immigration and military', name: 'Compiled service record',
    hint: 'Compiled military service records; one Source per series',
    source: [['series', 'Series title', 'Compiled Service Records of Volunteer Union Soldiers, Minnesota'], ['short', 'Short title (Abbrev)'], ['call', 'Call number']],
    citation: [['unit', 'Unit', 'Co. B, 1st Minnesota Infantry']],
    nouns: ['compiled service record'],
    defaults: NARA_FOLD3, confidence: '', doctype: 'military',
    title: '{series}',
    abbrev: '{short}',
    author: "War Department, Adjutant General's Office",
    page: '{unit}, {subject}',
    frn: `{author}, {series}, {unit}, {name}«, {details}»« (documenting {citedFor})»; ${DIGITAL_IMAGE}; citing {archive}«, {call}».`,
    srn: '{short}, {unit}, {name}.',
    pins: {
      page: [['B.3 §7', 'Compiled service record | [Unit], [Name] compiled service record']],
      author: [['B.3 §2', "Compiled service records | War Department, Adjutant General's Office"]],
    },
    examples: [],
  },
  {
    id: 'us-passenger-manifest', chapter: 'us', group: 'Immigration and military', name: 'Passenger manifest',
    hint: 'One Source per arrival port and year-range series',
    source: [['port', 'Arrival port', 'New York'], ['years', 'Years', '1820–1957'], ['agency', 'Creating agency (Author)'], ['call', 'NARA publication']],
    citation: [['list', 'List'], ['line', 'Line']],
    nouns: [''],
    defaults: NARA_ANCESTRY, confidence: '', doctype: 'immigration',
    title: 'Passenger Lists of Vessels Arriving at {port}, {years}',
    abbrev: 'Passenger lists, {port}, {years}',
    author: '«{agency}»',
    page: 'list {list}, line {line}, {subject}',
    frn: `«{agency}, »"Passenger Lists of Vessels Arriving at {port}, {years}," list {list}, line {line}, {name}«, {details}»« (documenting {citedFor})»; ${DIGITAL_IMAGE}; citing {archive}«, microfilm publication {call}».`,
    srn: 'Passenger lists, {port}, list {list}, line {line}, {name}.',
    paperlessTitle: '{name} passenger manifest entry« {eventYear}»',
    pins: {
      title: [['B.3 §4', 'Passenger manifests | Passenger Lists of Vessels Arriving at [port], [years]']],
      page: [['B.3 §7', 'Passenger manifest | list [N], line [N], [Name]']],
      plTitle: [['C1', 'Passenger manifest | [Name] passenger manifest entry [year]']],
    },
    examples: [],
  },
  {
    id: 'us-find-a-grave', chapter: 'us', group: 'Cemeteries and publications', name: 'Find a Grave memorial',
    hint: 'One Source per cemetery; the memorial number goes in the page string',
    source: [['state', 'State', 'Minnesota'], ['county', 'County', 'St. Louis'], ['cemetery', 'Cemetery', 'Forest Hill Cemetery'], ['city', 'City', 'Duluth']],
    citation: [['memorial', 'Memorial no.']],
    note: [['life', 'Life dates (FRN)', '1848–1929'], ['photographer', 'Marker photo by, date (FRN)']],
    nouns: [''],
    defaults: { platform: 'Find a Grave', pubmedium: 'Database with images' },
    confidence: 'High', doctype: 'vital record',
    derive: v => ({ cemeteryShort: String(v.cemetery || '').replace(/\s+Cemetery$/i, '').trim() }),
    title: '{state}, {county} County, {cemetery}, Find a Grave Memorials',
    abbrev: '{cemeteryShort}, {city}, FAG',
    author: '',
    page: 'memorial no. {memorial}, {subject}',
    frn: 'Find a Grave, memorial no. {memorial}, {name}« ({life})», {cemetery}, {city}, {county} County, {state}« (documenting {citedFor})»; database with images, {platform} ({url} : accessed {accessed})«; marker photograph by {photographer}».',
    srn: 'FAG memorial {memorial}, {name}, {cemetery}.',
    paperlessTitle: '{name} Find a Grave memorial« {eventYear}»',
    pins: {
      title: [['B.3 §4', 'Find a Grave | [State], [county], [cemetery], Find a Grave Memorials']],
      page: [['B.3 §7', 'Find a Grave | memorial no. [N], [Name]']],
      author: [['B.3 §2', 'Newspapers, Find a Grave | Blank']],
      confidence: [['B.3 §8', 'Find a Grave with marker photo | High for burial and inscribed dates']],
      plTitle: [['C1', 'Find a Grave | [Name] Find a Grave memorial [year]']],
    },
    examples: [{
      guide: 'B.3 Example 4',
      inputs: {
        state: 'Minnesota', county: 'St. Louis', cemetery: 'Forest Hill Cemetery', city: 'Duluth',
        memorial: '[N]', name: 'Per Larsson Grund', noun: '', life: '1848–1929', photographer: '[contributor name], [date]',
        url: 'https://www.findagrave.com/memorial/[N]', accessed: '6 May 2026', eventYear: '1929',
      },
    }],
  },
  {
    id: 'us-newspaper', chapter: 'us', group: 'Cemeteries and publications', name: 'Newspaper item',
    hint: 'Obituary, funeral notice, announcement, or mention; one Source per newspaper title',
    source: [['paper', 'Newspaper', 'Warren Sheaf'], ['city', 'City', 'Warren'], ['state', 'State', 'Minnesota']],
    citation: [['date', 'Issue date', '3 December 1908'], ['page', 'Page'], ['col', 'Column no. (if given)'], ['column', 'Column name (a recurring column, not the headline)', 'Alma']],
    note: [['headline', 'Headline (FRN)', "The article's title, if it has one"]],
    nouns: ['obituary', 'funeral notice', 'marriage announcement', 'news mention'],
    defaults: { platform: 'Newspapers.com', archive: 'Minnesota Historical Society' },
    confidence: 'Normal', doctype: 'publication',
    title: '{paper}, {city}, {state}',
    abbrev: '{paper}',
    author: '',
    page: '{date}, p. {page}«, col. {col}»«, {column} column», {subject}',
    // An item can report many things, so the FRN names it by the page string's subject and says what it is
    // cited for, as the page string does (B.3 §7). The SRN is the paper and the page string.
    frn: `«"{headline}," »«"{column}" [column], »{paper} ({city}, {state}), {date}, p. {page}«, col. {col}», {subject}« (documenting {citedFor})»; ${DIGITAL_IMAGE}.`,
    // Read on a library's film, the issue date finds the reel, so the film is named without one.
    frnMicrofilm: '«"{headline}," »«"{column}" [column], »{paper} ({city}, {state}), {date}, p. {page}«, col. {col}», {subject}« (documenting {citedFor})»; {archive} microfilm.',
    srn: '{paper}, {date}, p. {page}«, col. {col}»«, {column} column», {subject}.',
    pins: {
      title: [['B.3 §4', 'Newspaper | [Title], [city, state]']],
      page: [
        ['B.3 §7', 'Newspaper wedding / funeral / obituary | [date], p. [N], col. [N], [Name] obituary (or marriage announcement, funeral notice)'],
        ['B.3 §7', 'Newspaper personals | [date], p. [N], col. [N], [Name] news mention'],
        ['B.3 §7', 'Mixed-subject column | [date], p. [N], col. [N], [Column name], [Name] news mention'],
      ],
      author: [['B.3 §2', 'Newspapers, Find a Grave | Blank']],
      pubinfo: [['B.3 §6', 'Newspapers read on a library\'s film use Microfilm, Minnesota Historical Society.']],
      citedFor: [['A7', 'A page string may end with what the citation is cited for, in parentheses after everything else'], ['A7', 'the FRN gives it as (documenting …) at the end of the item it describes, before the image, film, or holding clause'], ['A5', 'Citing in an FRN introduces only the source behind an image or film']],
      confidence: [['B.3 §8', 'Obituary | Normal at best']],
    },
    examples: [
      {
        guide: 'B.3 Example 8',
        inputs: {
          paper: 'Duluth Herald', city: 'Duluth', state: 'Minnesota', date: '14 July 1929', page: '7', col: '3',
          name: 'Per Larsson Grund', noun: 'obituary', headline: 'Per L. Grund, Duluth Pioneer, Dies at Williams Farm',
          url: 'https://www.newspapers.com/...', accessed: '6 May 2026', eventYear: '1929',
        },
      },
      {
        guide: 'B.3 Example 9',
        inputs: {
          paper: 'Warren Sheaf', city: 'Warren', state: 'Minnesota', date: '3 December 1908', page: '1',
          name: 'Grund-Hoiberg', noun: 'marriage announcement', headline: '[Headline if present]', confidence: 'High',
          url: 'https://www.newspapers.com/image/[N]', accessed: '6 May 2026', eventYear: '1908',
        },
      },
      {
        guide: 'B.3 Example 14',
        inputs: {
          paper: 'Warren Sheaf', city: 'Warren', state: 'Minnesota', date: '11 July 1917', page: '3', col: '1',
          name: 'Olaf Nygren household', noun: 'news mention', headline: 'This Honored Couple Celebrate Golden Wedding',
          citedFor: 'date and attendees', url: 'https://www.newspapers.com/article/warren-sheaf-mr-mrs-olaf-nygren-50th/12517574/',
          accessed: '4 October 2026', eventYear: '1917',
        },
      },
      {
        guide: 'B.3 Example 10', citation: 1,
        inputs: {
          paper: 'Warren Sheaf', city: 'Warren', state: 'Minnesota', date: '17 May 1916', page: '7', column: 'Alma',
          name: 'Peter Grund', noun: 'news mention',
          url: 'https://www.newspapers.com/image/64259642', accessed: '6 May 2026', eventYear: '1916',
        },
      },
      {
        guide: 'B.3 Example 10', citation: 2,
        inputs: {
          paper: 'Warren Sheaf', city: 'Warren', state: 'Minnesota', date: '17 May 1916', page: '7', column: 'Alma',
          name: 'John Olson', noun: 'news mention',
          url: 'https://www.newspapers.com/image/64259642', accessed: '6 May 2026', eventYear: '1916',
        },
      },
      {
        guide: 'B.3 Example 13', citation: 1,
        inputs: {
          paper: 'Warren Sheaf', city: 'Warren', state: 'Minnesota', date: '3 December 1908', page: '1',
          name: 'Grund-Hoiberg', noun: 'marriage announcement', headline: '[Headline if present]', confidence: 'High',
          url: 'https://www.newspapers.com/image/[N]', accessed: '6 May 2026', eventYear: '1908',
        },
      },
      {
        guide: 'B.3 Example 13', citation: 2,
        inputs: {
          paper: 'Warren Sheaf', city: 'Warren', state: 'Minnesota', date: '[date]', page: '[N]', col: '[N]',
          name: '[Name]', noun: 'obituary', headline: '[Headline]', pubmedium: 'Microfilm', archive: 'Minnesota Historical Society',
        },
      },
    ],
  },
  {
    id: 'us-city-directory', chapter: 'us', group: 'Cemeteries and publications', name: 'City directory',
    hint: 'One Source per annual directory; a publication, so Repository stays blank',
    source: [['dtitle', 'Directory title', "Polk's Duluth City Directory"], ['year', 'Year', '1900'], ['publisher', 'Publisher', 'R. L. Polk & Co.'], ['city', 'Place of publication', 'Duluth']],
    citation: [['page', 'Page']],
    nouns: ['directory entry'],
    defaults: { platform: 'Ancestry' },
    confidence: 'Normal', doctype: 'enumeration', eventDate: 'year',
    derive: v => {
      const title = String(v.dtitle || '').trim();
      return { dabbr: title.replace(/\s*City Directory$/i, ' directory'), dshort: title.replace(/\s*City Directory$/i, ' dir.') };
    },
    title: '{dtitle}, {year}',
    abbrev: '{dabbr}, {year}',
    author: '{publisher}',
    pubinfo: '{city}: {publisher}, {year}.« {pubmedium}, {platform} ({home}).»',
    page: 'p. {page}, {subject}',
    frn: '{publisher}, {dtitle}, {year} ({city}: {publisher}, {year}), p. {page}, {name}« (documenting {citedFor})»«; {medium}, {platform} ({url} : accessed {accessed})».',
    srn: '{dshort}, {year}, p. {page}, {name}.',
    pins: {
      title: [['B.3 §4', 'City directory | [Publisher] [city] City Directory, [year]']],
      page: [['B.3 §7', 'City directory | p. [N], [Name] directory entry']],
      author: [['B.3 §2', 'City directories | [Publisher]']],
      pubinfo: [['B.3 §6', 'Published directories use the imprint variant (Example 7).']],
      confidence: [['B.3 §8', 'City directory | Normal for residence']],
    },
    examples: [{
      guide: 'B.3 Example 7',
      inputs: {
        dtitle: "Polk's Duluth City Directory", year: '1900', publisher: 'R. L. Polk & Co.', city: 'Duluth',
        page: '412', name: 'Per Larsson Grund', noun: 'directory entry',
        url: 'https://www.ancestry.com/...', accessed: '6 May 2026',
      },
    }],
  },
];

return { US };
})();
__modules["records/published.js"] = (() => {
// B.4 · Published and personal sources.
const { isoDate, lastWord, yearOf } = __modules["tables.js"];

const PRIVATE = { custodian: 'Peter Grund', custplace: 'Duluth, Minnesota' };
const HELD_BY = 'privately held by {custodian}«, {custplace}»';

const pagesLabel = pages => (/[–\-,]/.test(String(pages || '')) ? 'pp.' : 'p.');

const PUBLISHED = [
  {
    id: 'pp-book', chapter: 'pp', group: 'Published works', name: 'Book or bygdebok',
    hint: 'One Source per book (or multi-volume set cited as a unit)',
    source: [
      ['bookAuthor', 'Author', 'Birger Kirkeby'], ['btitle', 'Title'], ['gloss', 'English gloss (foreign titles)'],
      ['vol', 'Volume / part (as cited)', 'vol. 2, pt. 2'], ['city', 'City', 'Oslo'], ['publisher', 'Publisher'],
      ['year', 'Year'], ['format', 'Format (e-book, audiobook…)'], ['abbr', 'Abbrev', 'Eidsvoll bygdebok 2:2'],
    ],
    citation: [],
    pageVariants: [
      {
        key: 'pages', label: 'Pages',
        citation: [['pages', 'Pages', '432–440']],
        page: '{pl} {pages}«, {subject}»',
        frn: '{author}, {btitle}« [{gloss}]»«, {vol}» ({city}: {publisher}, {year}«. {format}»), {pl} {pages}{frnEnd}',
        srn: '{surname}, {abbr}, {pl} {pages}.',
      },
      {
        key: 'chapter', label: 'Chapter',
        citation: [['chapter', 'Chapter title'], ['pages', 'Pages']],
        page: '{chapter}, {pl} {pages}',
        frn: '{author}, "{chapter}," in {btitle}« [{gloss}]»«, {vol}» ({city}: {publisher}, {year}«. {format}»), {pl} {pages}« (documenting {citedFor})».',
        srn: '{surname}, "{chapter}," {pl} {pages}.',
      },
      {
        key: 'volume', label: 'Multi-volume work',
        citation: [['volume', 'Volume'], ['pages', 'Pages']],
        page: 'vol. {volume}, {pl} {pages}«, {subject}»',
        frn: '{author}, {btitle}« [{gloss}]», vol. {volume} ({city}: {publisher}, {year}«. {format}»), {pl} {pages}{frnEnd}',
        srn: '{surname}, {abbr}, vol. {volume}, {pl} {pages}.',
      },
      {
        key: 'encyclopedia', label: 'Encyclopedia entry',
        citation: [['headword', 'Entry headword']],
        page: '{headword}',
        frn: '{author}, {btitle}« [{gloss}]»«, {vol}» ({city}: {publisher}, {year}«. {format}»), s.v. "{headword}{hwClose}',
        srn: '{surname}, {abbr}, s.v. "{headword}."',
      },
    ],
    nouns: ['entry', ''],
    optionalSubject: true,
    defaults: {}, confidence: 'Normal', doctype: 'publication',
    derive: v => ({
      pl: pagesLabel(v.pages),
      surname: lastWord(v.bookAuthor),
      volCap: String(v.vol || '').trim().replace(/^./, ch => ch.toUpperCase()),
      // The FRN ends on the quoted section, if any, then what it is cited for (A7): , "Vinger gård" (documenting …).
      frnEnd: (v.name ? `, "${v.name}${v.citedFor ? '"' : '."'}` : v.citedFor ? '' : '.') + (v.citedFor ? ` (documenting ${v.citedFor}).` : ''),
      hwClose: v.citedFor ? `" (documenting ${v.citedFor}).` : '."',
    }),
    title: '{btitle}',
    abbrev: '{abbr}',
    author: '{bookAuthor}',
    pubinfo: '«{volCap}. »{city}: {publisher}, {year}.« {format}.»« {pubmedium}, {platform} ({home}).»',
    paperlessTitle: '{name} {abbr} {pl} {pages} ({year})',
    subjectLabel: 'Topic or section',
    pins: {
      title: [['B.4 §4', 'Book | [Title]']],
      page: [
        ['B.4 §7', 'Book | p. [N] or pp. [N]–[N], plus subject if relevant'],
        ['B.4 §7', 'Book chapter | [Chapter title], pp. [N]–[N]'],
        ['B.4 §7', 'Multi-volume work | vol. [N], pp. [N]–[N]'],
        ['B.4 §7', 'Encyclopedia | [entry headword]'],
      ],
      author: [['B.4 §2', "Book, one author | Author's name (Birger Kirkeby)"]],
      abbrev: [['B.4 §10', 'Book | Eidsvoll bygdebok 2:2']],
      pubinfo: [
        ['B.4 §6', 'Print book | [City]: [Publisher], year.'],
        ['B.4 §6', 'E-book / audiobook / CD-DVD | [City]: [Publisher], year. [Format].'],
        ['B.4 §6', 'Online book via a library platform | [City]: [Publisher], year. Digital images, [Platform] (URL).'],
      ],
      confidence: [['B.4 §8', 'Normal | Genealogies citing primary records']],
      plTitle: [['C1', 'Published work (book, periodical) | [Topic] [book identifier] [vol] pp. [range] ([pub. year])']],
    },
    examples: [{
      guide: 'B.4 Published book',
      inputs: {
        bookAuthor: 'Birger Kirkeby', btitle: 'Eidsvoll Bygds Historie: Gardene på vestside av Vorma',
        gloss: 'Eidsvoll Parish History: The Farms on the West Side of the Vorma River', vol: 'vol. 2, pt. 2',
        city: 'Oslo', publisher: 'Eidsvoll Bygdebokkomite', year: '1959', abbr: 'Eidsvoll bygdebok 2:2',
        variant: 'pages', pages: '432–440', name: 'Vinger gård', noun: 'entry',
      },
    }],
  },
  {
    id: 'pp-edited-collection', chapter: 'pp', group: 'Published works', name: 'Edited collection',
    hint: 'A book with chapters by different authors (EE 13.65)',
    source: [
      ['editor', 'Editor(s)', 'Sarah L. Wilkerson Freeman and Beverly Greene Bond'], ['btitle', 'Title', 'Tennessee Women: Their Lives and Times'],
      ['city', 'City', 'Athens'], ['publisher', 'Publisher', 'University of Georgia Press'], ['year', 'Year', '2009'], ['abbr', 'Abbrev', 'Tennessee Women 2009'],
    ],
    citation: [['chapterAuthor', 'Chapter author'], ['chapter', 'Chapter title'], ['pages', 'Pages']],
    nouns: [''],
    optionalSubject: true,
    defaults: {}, confidence: 'Normal', doctype: 'publication',
    derive: v => ({ pl: pagesLabel(v.pages), chapterSurname: lastWord(v.chapterAuthor) }),
    title: '{btitle}',
    abbrev: '{abbr}',
    author: '{editor}, editor',
    pubinfo: '{city}: {publisher}, {year}.« {pubmedium}, {platform} ({home}).»',
    page: '{chapter}, {pl} {pages}«, {subject}»',
    frn: '{chapterAuthor}, "{chapter}," in {btitle}, ed. {editor} ({city}: {publisher}, {year}), {pl} {pages}« (documenting {citedFor})».',
    srn: '{chapterSurname}, "{chapter}," {pl} {pages}.',
    subjectLabel: 'Topic (optional)',
    pins: {
      title: [['B.4 §4', 'Edited collection | [Title]']],
      page: [['B.4 §7', 'Book chapter | [Chapter title], pp. [N]–[N]']],
      author: [['B.4 §2', 'Edited collection | [Name], editor (EE 13.65)']],
      abbrev: [['B.4 §10', 'Book | Eidsvoll bygdebok 2:2 · Tennessee Women 2009']],
    },
    examples: [],
  },
  {
    id: 'pp-periodical', chapter: 'pp', group: 'Published works', name: 'Periodical article',
    hint: 'One Source per periodical title; the issue goes in the page string',
    source: [['periodical', 'Periodical', 'American Genealogist'], ['pcity', 'City, state', 'New Haven, Connecticut']],
    citation: [['aauthor', 'Article author'], ['atitle', 'Article title'], ['volume', 'Volume'], ['issue', 'Issue no.'], ['ayear', 'Year'], ['pages', 'Pages']],
    nouns: [''],
    optionalSubject: true,
    defaults: {}, confidence: 'Normal', doctype: 'publication',
    derive: v => ({ pl: pagesLabel(v.pages), articleSurname: lastWord(v.aauthor) }),
    title: '{periodical}, {pcity}',
    abbrev: '{periodical}',
    author: '',
    pubinfo: '{pcity}.',
    page: 'vol. {volume}, no. {issue} ({ayear}), {pl} {pages}«, {subject}»',
    frn: '{aauthor}, "{atitle}," {periodical} {volume} ({ayear}): {pages}« (documenting {citedFor})».',
    srn: '{articleSurname}, "{atitle}," {pages}.',
    subjectLabel: 'Topic (optional)',
    pins: {
      title: [['B.4 §4', 'Periodical | [Title], [city, state]']],
      page: [['B.4 §7', 'Periodical article | vol. [N], no. [N] ([year]), pp. [N]–[N]']],
      author: [['B.4 §2', 'Periodical | Blank']],
      pubinfo: [['B.4 §6', 'Periodical | [City], [State if needed], [Publisher].']],
      abbrev: [['B.4 §10', 'Periodical | American Genealogist']],
    },
    examples: [],
  },
  {
    id: 'pp-register', chapter: 'pp', group: 'Published works', name: 'Directory or register',
    hint: 'Membership roster or school register; one Source per annual issue or volume',
    source: [
      ['issuer', 'Issuing body or compiler', 'Den norske sakførerforening'], ['rtitle', 'Title'], ['gloss', 'English gloss'],
      ['city', 'City', 'Oslo'], ['publisher', 'Publisher'], ['year', 'Year'], ['abbr', 'Abbrev'],
      ['srnAuthor', 'Author in SRN (surname, if a person)', 'Langangen'],
    ],
    citation: [['page', 'Page'], ['image', 'Image', 'if not the page'], ['entry', 'Entry no. (if any)']],
    nouns: ['directory entry', 'register entry'],
    defaults: { platform: 'Nasjonalbiblioteket' }, confidence: 'Normal', doctype: 'publication',
    derive: v => ({ entryLead: String(v.entry || '').trim() ? `entry no. ${String(v.entry).trim()}, ` : 'entry for ' }),
    title: '{rtitle}',
    abbrev: '{abbr}',
    author: '{issuer}',
    pubinfo: '{city}: {publisher}, {year}.« {pubmedium}, {platform} ({home}).»',
    page: 'p. {page}« (image {image})»«, entry no. {entry}», {subject}',
    frn: '{author}, {rtitle}« [{gloss}]» ({city}: {publisher}, {year}), p. {page}, {entryLead}{name}« (documenting {citedFor})»«; {medium}, {platform} ({url} : accessed {accessed})».',
    srn: '«{srnAuthor}, »{abbr}, p. {page}«, no. {entry}», {name}.',
    pins: {
      title: [['B.4 §4', 'Membership directory | [Title with year]'], ['B.4 §4', 'School roster | [Title with years]']],
      page: [['B.4 §7', 'Directory or register | p. [P] (image [I]), entry no. [N], [Name] directory entry (or register entry)']],
      author: [['B.4 §2', 'Membership directory / organizational publication | Issuing body (Den norske sakførerforening)']],
      pubinfo: [['B.4 §6', 'Membership directory | [City]: [Issuing organization], year.']],
      abbrev: [['B.4 §10', 'Register | Sakførerforening medlemmer 1950 · Kristiania katedralskole 1891–1901']],
      confidence: [['B.4 §8', 'Normal | Genealogies citing primary records; biographical and membership directories; school records']],
    },
    examples: [
      {
        guide: 'B.4 Membership directory',
        inputs: {
          issuer: 'Den norske sakførerforening', rtitle: 'Medlemmer av Den norske sakførerforening 1. juli 1950',
          gloss: 'Members of the Norwegian Bar Association as of 1 July 1950', city: 'Oslo', publisher: 'Den norske sakførerforening',
          year: '1951', abbr: 'Sakførerforening medlemmer 1950', page: '440', image: '443', name: 'Frithjof Siggerud', noun: 'directory entry',
          url: 'https://www.nb.no/items/b3f9413b2125c7f26063abb8896d95bf?page=443', accessed: '26 April 2026', eventYear: '1950',
        },
      },
      {
        guide: 'B.4 School enrollment register',
        inputs: {
          issuer: 'Anders Langangen', rtitle: 'Elever ved Kristiania katedralskole som begynte på skolen i årene 1891–1901, hefte 8',
          gloss: 'Pupils at Kristiania Cathedral School Who Began in the Years 1891–1901, Booklet 8', city: '[Place]', publisher: '[Publisher]',
          year: '[year]', abbr: 'Kristiania katedralskole 1891–1901', srnAuthor: 'Langangen',
          page: '112', image: '111', entry: '498', name: 'Erling Frithjof Siggerud', noun: 'register entry',
          url: 'https://www.nb.no', accessed: '26 April 2026',
        },
      },
    ],
  },
  {
    id: 'pp-video', chapter: 'pp', group: 'Published works', name: 'Online video',
    hint: 'Use video only for context, never as the source for a date, name, or relationship',
    source: [
      ['channel', 'Channel or producer', 'Värmland Local History Channel'], ['vtitle', 'Video title'],
      ['vshort', 'Short title (Abbrev)'], ['channelShort', 'Channel in SRN (if shorter)'], ['year', 'Year'],
    ],
    citation: [['range', 'Minute range', '12:30–14:15']],
    nouns: [''],
    defaults: { platform: 'YouTube' }, confidence: 'Low', doctype: 'publication',
    derive: v => ({ topic: String(v.details || '').trim() || v.name, srnChannel: String(v.channelShort || '').trim() || v.channel }),
    title: '{vtitle}',
    abbrev: '{vshort}',
    author: '{channel}',
    pubinfo: 'Online video, {platform} ({home}), {year}.',
    page: 'minute {range}, {subject}',
    frn: '{channel}, "{vtitle}," {platform} video ({url} : accessed {accessed}), minute {range}, on {topic}« (documenting {citedFor})».',
    srn: '{srnChannel}, "{vshort}," minute {range}.',
    subjectLabel: 'Topic',
    detailsLabel: 'Topic as worded in the FRN (if different)',
    paperlessTitle: '{vshort} video clip {year}',
    pins: {
      title: [['B.4 §4', 'Online video | [Title]']],
      page: [['B.4 §7', 'Audio interview / video | minute [N]:[NN], [topic] (or transcript p. [N], [topic])']],
      author: [['B.4 §2', 'Online video | Channel or production company']],
      pubinfo: [['B.4 §6', 'Online video | Online video, [Platform] (homepage URL), year.'], ['A10', 'Online video | Online video, [Platform] (URL), year.']],
      abbrev: [['B.4 §10', 'Online video | Norra Ny walking tour (the SRN may lead with the channel)']],
      plTitle: [['C1', 'Online video | [Short title] video clip [year]']],
    },
    examples: [{
      guide: 'B.4 Online video',
      inputs: {
        channel: 'Värmland Local History Channel', vtitle: 'Norra Ny parish history walking tour', vshort: 'Norra Ny walking tour',
        channelShort: 'Värmland History YouTube', year: '2025', range: '12:30–14:15', name: 'Ambjörby torpare landscape', noun: '',
        details: 'the Ambjörby torpare landscape', url: 'https://www.youtube.com/watch?v=[ID]', accessed: '9 May 2026',
      },
    }],
  },
  {
    id: 'pp-bible', chapter: 'pp', group: 'Family artifacts', name: 'Family Bible',
    hint: 'Photograph the cover, title page, and all family pages before judging confidence',
    source: [
      ['surname', 'Family surname', 'Grund'], ['years', 'Years of entries', '1848–1932'], ['compiler', 'Inferred compiler', 'Per Larsson Grund'],
      ['btitle', 'Bible title', 'The Holy Bible Containing the Old and New Testaments'], ['city', 'Place of publication'],
      ['publisher', 'Bible publisher'], ['year', 'Bible year'],
    ],
    citation: [['pagelabel', 'Page', 'family page 2']],
    nouns: ['birth entry', 'marriage entry', 'death entry'],
    defaults: PRIVATE, confidence: 'High', doctype: 'artifact',
    title: '{surname} Family Bible Records, {years}',
    abbrev: '{surname} Family Bible',
    author: '[{compiler}]',
    pubinfo: '',
    page: '{pagelabel}, {subject}',
    frn: `[{compiler}], compiler, {surname} Family Bible Records, {years}, in {btitle} ({city}: {publisher}, {year}), {pagelabel}, entry for {name}« {details}»« (documenting {citedFor})»; ${HELD_BY}.`,
    srn: '{surname} Family Bible, {pagelabel}, {subject}.',
    detailsLabel: 'Entry details (dates, places)',
    pins: {
      title: [['B.4 §4', 'Family Bible | [Surname] Family Bible Records, [years]']],
      page: [['B.4 §7', 'Family Bible | [record-type] page, [event] (family page, Per Larsson Grund birth entry)']],
      author: [['B.4 §2', 'Family Bible | Inferred compiler in brackets ([Per Larsson Grund]), or blank.']],
      pubinfo: [['B.4 §6', 'Family Bible | Blank']],
      abbrev: [['B.4 §10', 'Family Bible | Grund Family Bible']],
    },
    examples: [{
      guide: 'B.4 Family Bible',
      inputs: {
        surname: 'Grund', years: '1848–1932', compiler: 'Per Larsson Grund', btitle: 'The Holy Bible Containing the Old and New Testaments',
        city: 'Stockholm', publisher: '[Bible publisher]', year: '[year]', pagelabel: 'family page 2',
        name: 'Per Larsson Grund', noun: 'birth entry', details: 'born 14 January 1848 at Ambjörby, Norra Ny parish',
        comment: "Entries appear in two distinct hands: an early hand for events 1848–1880, a later hand for events 1881–1932. The earliest entries appear to have been copied into this Bible from an earlier family record after the Bible's purchase.",
      },
    }],
  },
  {
    id: 'pp-family-record', chapter: 'pp', group: 'Family artifacts', name: 'Family record',
    hint: 'A family record other than a Bible (notes, registers, histories)',
    source: [['family', 'Family or compiler', 'Grund'], ['rtype', 'Record type', 'Family Record'], ['compiler', 'Compiler (if known)']],
    citation: [['pagelabel', 'Page or section']],
    nouns: ['birth entry', 'marriage entry', 'death entry', ''],
    defaults: PRIVATE, confidence: '', doctype: 'artifact',
    title: '{family} {rtype}',
    abbrev: '{family} {rtype}',
    author: '«[{compiler}]»',
    page: '{pagelabel}, {subject}',
    frn: `«[{compiler}], compiler, »{family} {rtype}, {pagelabel}, entry for {name}« {details}»« (documenting {citedFor})»; ${HELD_BY}.`,
    srn: '{family} {rtype}, {pagelabel}, {subject}.',
    pins: {
      title: [['B.4 §4', 'Family record | [Family/compiler] [record type]']],
      author: [['B.4 §2', 'Family record (non-Bible) | Blank, or compiler in brackets']],
    },
    examples: [],
  },
  {
    id: 'pp-funeral-program', chapter: 'pp', group: 'Family artifacts', name: 'Funeral program',
    hint: 'One Source per program unless several artifacts share one provenance (A1)',
    source: [
      ['dname', 'Deceased', 'Thomas Emil Siggerud'], ['funeralHome', 'Funeral home', 'Helgeson Funeral Home'], ['fcity', 'Funeral home city', 'Williams, Minnesota'],
      ['date', 'Service date', '16 February 1953'], ['ptitle', 'Printed title', 'In Memory of Thomas Emil Siggerud'],
    ],
    citation: [],
    nouns: ['funeral program', 'obituary'],
    defaults: PRIVATE, confidence: 'High', doctype: 'ephemera',
    derive: v => ({ surname: lastWord(v.dname), year: yearOf(v.date) }),
    title: 'Funeral program, {dname}',
    abbrev: '{surname} funeral program {year}',
    author: '{funeralHome}',
    pubinfo: '{fcity}: {funeralHome}, {date}.',
    page: '{subject}',
    frn: `{funeralHome}, "{ptitle}," funeral program for services held {date}« {details}»« (documenting {citedFor})»; ${HELD_BY}.`,
    srn: '{surname} funeral program {year}.',
    detailsLabel: 'Service details (church, officiant, burial)',
    paperlessTitle: '{dname} funeral program {year}',
    pins: {
      title: [['B.4 §4', 'Funeral program | Funeral program, [Subject]']],
      page: [['B.4 §7', 'Funeral program | [subject] (short enough to need no page)']],
      author: [['B.4 §2', 'Funeral program | Funeral home (Helgeson Funeral Home)']],
      pubinfo: [['B.4 §6', 'Funeral program | [City]: [Funeral home], date.'], ['A10', 'Funeral program | [City]: [Funeral home], date.']],
      abbrev: [['B.4 §10', 'Artifact | Siggerud funeral program 1953']],
      plTitle: [['C1', 'Funeral program | [Deceased] funeral program [year]']],
    },
    examples: [{
      guide: 'B.4 Funeral program',
      inputs: {
        dname: 'Thomas Emil Siggerud', funeralHome: 'Helgeson Funeral Home', fcity: 'Williams, Minnesota', date: '16 February 1953',
        ptitle: 'In Memory of Thomas Emil Siggerud', name: 'Thomas Emil Siggerud', noun: 'funeral program',
        details: 'at Lutheran Church, Williams, Minnesota; Rev. Edstrom officiating; burial at Pine Hill Cemetery, Williams, Minnesota',
      },
    }],
  },
  {
    id: 'pp-photograph', chapter: 'pp', group: 'Family artifacts', name: 'Photograph',
    hint: 'When the photo itself is the evidence; otherwise attach it to the relevant citation',
    source: [
      ['pname', 'Subject', 'Per Larsson Grund'], ['ptype', 'Photo type', 'cabinet card'], ['pdate', 'Date', 'ca. 1890s'],
      ['photographer', 'Photographer (Author, if known)'], ['studio', 'Studio'], ['scity', 'Studio city'],
    ],
    citation: [['element', 'Image element', 'cabinet card front'], ['element2', 'Second element (optional)']],
    nouns: ['portrait', ''],
    defaults: PRIVATE, confidence: 'High', doctype: 'artifact',
    derive: v => ({ surname: lastWord(v.pname), decade: String(v.pdate || '').replace(/^ca\.\s*/, '').trim() }),
    title: '{pname} {ptype}, {pdate}',
    abbrev: '{surname} {ptype} {decade}',
    author: '«{photographer}»',
    pubinfo: '«{studio}, {scity}, {pdate}.»« {pubmedium}, {platform} ({home}).»',
    page: '{element}, {subject}«; {element2}»',
    frn: `{pname} {ptype} portrait, {pdate}«, taken at {studio}, {scity}»«; {details}»« (documenting {citedFor})»; ${HELD_BY}.`,
    srn: '{pname} {ptype}, {pdate}.',
    detailsLabel: 'Inscriptions and marks (FRN)',
    paperlessTitle: '{pname} photograph {decade}',
    pins: {
      title: [['B.4 §4', 'Photograph | [Subject] [photo type], [year or range]']],
      page: [['B.4 §7', 'Photograph | [image element], [subject], then ; [second element] if needed (cabinet card front, Per Larsson Grund portrait; inscription on mount, "Grandma\'s Grandpa")']],
      author: [['B.4 §2', 'Photograph | Photographer or studio if known']],
      pubinfo: [['B.4 §6', 'Photograph from a studio | [Studio], [city], [year or circa]. if known']],
      abbrev: [['B.4 §10', 'Artifact | Siggerud funeral program 1953 · Grund cabinet card 1890s']],
      plTitle: [['C1', 'Photograph | [Subject] photograph [decade or year]']],
    },
    examples: [{
      guide: 'B.4 Photograph',
      inputs: {
        pname: 'Per Larsson Grund', ptype: 'cabinet card', pdate: 'ca. 1890s', studio: 'Miller Studio', scity: 'St. Cloud, Minnesota',
        element: 'cabinet card front', element2: 'inscription on mount, "Grandma\'s Grandpa"', name: 'Per Larsson Grund', noun: 'portrait',
        details: 'inscription on top of mount in cursive: "Grandma\'s Grandpa"; printed studio mark on bottom of mount: "Miller" (with M-M monogram), "ST. CLOUD, MINN."',
        comment: 'Subject identification is family attribution by inscription rather than caption with full name.',
      },
    }],
  },
  {
    id: 'pp-letter', chapter: 'pp', group: 'Family artifacts', name: 'Family letter',
    hint: 'One letter cited substantively; one collection when the collection is cited',
    source: [['sender', 'Writer', 'Per Larsson Grund'], ['recipient', 'Recipient', 'John Edwin Grund'], ['date', 'Date', '14 March 1925']],
    citation: [],
    nouns: [''],
    defaults: PRIVATE, confidence: 'High', doctype: 'correspondence',
    derive: v => ({ senderSurname: lastWord(v.sender), recipientSurname: lastWord(v.recipient), iso: isoDate(v.date) }),
    title: '{sender} to {recipient}, {date}, letter',
    abbrev: '{senderSurname} to {recipientSurname} letter {iso}',
    author: '{sender}',
    pubinfo: '',
    page: '{subject}',
    frn: `{sender} to {recipient}, letter, {date}«, {details}»« (documenting {citedFor})»; ${HELD_BY}.`,
    srn: '{sender} to {recipient}, {date}.',
    subjectLabel: 'Topic, subject (e.g. report of a death, Name)',
    detailsLabel: 'Content for the FRN',
    paperlessTitle: '{sender} to {recipient} letter {iso}',
    pins: {
      title: [['B.4 §4', 'Letter | [Sender] to [Recipient], [date], letter']],
      author: [['B.4 §2', 'Letter | Writer']],
      pubinfo: [['B.4 §6', 'Letter | Blank']],
      plTitle: [['C1', 'Family letter | [Sender] to [Recipient] letter [YYYY-MM-DD]']],
    },
    examples: [],
  },
  {
    id: 'pp-interview', chapter: 'pp', group: 'People', name: 'Audio interview',
    hint: "The interviewee is the Author (EE 4.31). Never publish a living informant's address (A12).",
    source: [['interviewee', 'Interviewee', 'Tom Grund'], ['interviewer', 'Interviewer', 'Peter Grund'], ['city', 'Place', 'Duluth, Minnesota'], ['date', 'Date', '12 March 2024']],
    citation: [['minute', 'Timestamp', '23:15']],
    nouns: [''],
    defaults: PRIVATE, confidence: 'Normal', doctype: 'interview',
    derive: v => ({ iso: isoDate(v.date), topic: String(v.details || '').trim() || v.name }),
    title: '{interviewee} interview by {interviewer}, {date}',
    abbrev: '{interviewee} interview {iso}',
    author: '{interviewee}',
    pubinfo: 'Recorded interview, {city}, {date}.',
    page: 'minute {minute}, {subject}',
    frn: '{interviewee} ({city}), recorded interview by {interviewer}, {date}; audio recording and transcript privately held by {custodian}, [ADDRESS FOR PRIVATE USE,] {custplace}; minute {minute}, on {topic}« (documenting {citedFor})».',
    srn: '{interviewee} interview, {date}, minute {minute}.',
    subjectLabel: 'Topic',
    detailsLabel: 'Topic as worded in the FRN (if different)',
    paperlessTitle: '{interviewee} interview {iso}',
    pins: {
      title: [['B.4 §4', 'Audio interview | [Interviewee] interview by [Interviewer], [date]']],
      page: [['B.4 §7', 'Audio interview / video | minute [N]:[NN], [topic] (or transcript p. [N], [topic])']],
      author: [['B.4 §2', 'Audio interview | The interviewee (EE 4.31)']],
      pubinfo: [['B.4 §6', 'Audio interview | Recorded interview, [city], date.'], ['A10', 'Audio interview | Recorded interview, [city], date.']],
      abbrev: [['B.4 §10', 'Interview | Tom Grund interview 2024-03-12']],
      plTitle: [['C1', 'Audio interview | [Interviewee] interview [YYYY-MM-DD]']],
    },
    examples: [{
      guide: 'B.4 Audio interview',
      inputs: {
        interviewee: 'Tom Grund', interviewer: 'Peter Grund', city: 'Duluth, Minnesota', date: '12 March 2024',
        minute: '23:15', name: "Edmund Gene Grund's military service in WWII", noun: '', details: "Edmund Gene Grund's WWII service",
        comment: 'Tom is a son of Edmund Gene Grund and reports here on events he learned of from his parents (he was born after the war).',
      },
    }],
  },
  {
    id: 'pp-oral-history', chapter: 'pp', group: 'People', name: 'Oral-history collection',
    hint: 'A collection of interviews cited as a whole',
    source: [['collection', 'Collection title', 'Cane River Oral History Collection'], ['call', 'Call number']],
    citation: [['interviewee', 'Interviewee'], ['interviewer', 'Interviewer'], ['date', 'Interview date'], ['locator', 'Minute or transcript page', 'minute 12:30']],
    nouns: [''],
    defaults: {}, confidence: '', doctype: 'interview',
    derive: v => ({ topic: String(v.details || '').trim() || v.name }),
    title: '{collection}',
    abbrev: '{collection}',
    author: '{collection}',
    page: '{locator}, {subject}',
    frn: '{interviewee}, interview by {interviewer}, {date}, {collection}; {locator}, on {topic}« (documenting {citedFor})»; citing {archive}«, {call}».',
    srn: '{collection}, {interviewee}, {locator}.',
    subjectLabel: 'Topic',
    detailsLabel: 'Topic as worded in the FRN (if different)',
    pins: {
      title: [['B.4 §4', 'Oral-history collection | [Collection title]']],
      page: [['B.4 §7', 'Audio interview / video | minute [N]:[NN], [topic] (or transcript p. [N], [topic])']],
      author: [['B.4 §2', 'Oral-history collection | Collection name']],
    },
    examples: [],
  },
  {
    id: 'pp-research', chapter: 'pp', group: 'People', name: "Another genealogist's research",
    hint: "Their conclusion isn't evidence; their cited sources are. Prefer the primary record.",
    source: [
      ['researcher', 'Researcher', 'Siw Alfreddson'], ['topic', 'Topic (Title)', 'Ambjörby, Sweden'],
      ['rtopic', 'Topic (FRN)', 'the Grund family of Ambjörby, Sweden'], ['years', 'Years', '2024–2026'],
    ],
    citation: [['section', 'Section or item', 'Ambmyra typed page, received 30 April 2026']],
    note: [['copies', 'Copies held by (FRN)', 'Peter Grund, Duluth, Minnesota']],
    nouns: [''],
    optionalSubject: true,
    defaults: { custodian: 'Siw Alfreddson', custplace: 'Ambjörby, Sweden' },
    confidence: 'Normal', doctype: 'research',
    derive: v => ({ surname: lastWord(v.researcher), topicShort: String(v.topic || '').split(',')[0].trim() }),
    title: 'Personal research of {researcher}, {topic}',
    abbrev: '{surname} research',
    author: '{researcher}',
    pubinfo: 'Unpublished research, {custplace}, {years}.',
    page: '{section}«, {subject}»',
    frn: `{researcher}, personal research on {rtopic}, accumulated {years}, {details}« (documenting {citedFor})»; ${HELD_BY}«, with copies privately held by {copies}».`,
    srn: '{surname} research, {section}.',
    subjectLabel: 'Topic, subject (optional)',
    detailsLabel: 'Item description (FRN)',
    eventYearLabel: 'Received (Paperless)',
    paperlessTitle: '{surname} {topicShort} research {eventYear}',
    pins: {
      title: [['B.4 §4', 'Personal research | Personal research of [Researcher], [topic]']],
      page: [['B.4 §7', 'Personal research | [topic or section], [page if compiled]']],
      author: [['B.4 §2', 'Personal research | Researcher (Siw Alfreddson)']],
      pubinfo: [['B.4 §6', 'Personal research | Unpublished research, [location], [year-range].'], ['A10', 'Personal research | Unpublished research, [location], [year-range].']],
      abbrev: [['B.4 §10', 'Personal research | Alfreddson research']],
      plTitle: [['C1', 'Personal research | [Researcher surname] [topic] research [YYYY-MM-DD, YYYY, or range]']],
    },
    examples: [{
      guide: 'B.4 Personal research',
      inputs: {
        researcher: 'Siw Alfreddson', topic: 'Ambjörby, Sweden', rtopic: 'the Grund family of Ambjörby, Sweden',
        years: '2024–2026', section: 'Ambmyra typed page, received 30 April 2026',
        details: 'typed page on Ambmyra torpare holdings, received by Peter Grund via email 30 April 2026',
        copies: 'Peter Grund, Duluth, Minnesota', eventYear: '2026-04-30',
        comment: "Siw's notes cite Norra Ny kyrkoarkiv volumes for each fact she records; for facts she draws from those primary records, the underlying primary record should also be cited directly when used in narrative.",
      },
    }],
  },
];

return { PUBLISHED };
})();
__modules["records/index.js"] = (() => {
// Every record type, in sidebar order.
const { NORWEGIAN } = __modules["records/norwegian.js"];
const { SWEDISH } = __modules["records/swedish.js"];
const { US } = __modules["records/us.js"];
const { PUBLISHED } = __modules["records/published.js"];

const RECORDS = [...NORWEGIAN, ...SWEDISH, ...US, ...PUBLISHED];

function recordById(id) {
  return RECORDS.find(r => r.id === id) || null;
}

return { RECORDS, recordById };
})();
__modules["engine.js"] = (() => {
// Turns one draft of one record type into every output field.
const { fill, gap } = __modules["template.js"];
const { DATE_MEANING, CHAPTER_CODE, PLATFORMS, MEDIA, yearOf } = __modules["tables.js"];

// Reference-note values that describe the Source, pre-filled from the record type's defaults.
const REFERENCE_VALUES = ['platform', 'pubmedium', 'archive', 'custodian', 'custplace'];
const STANDARD_VALUES = ['url', 'accessed', 'eventYear', 'details', 'comment', 'citedFor', ...REFERENCE_VALUES];
const SUBJECT_KEYS = ['name', 'noun', 'copy', 'nonHead', 'head', 'which', 'says', 'evidence', 'afterNoun'];
const ENGINE_TOKENS = ['name', 'noun', 'subject', 'srnSubject', 'entryof', 'medium', 'home', 'author', 'pageLoc', 'pageRef'];
const TEMPLATE_KEYS = ['title', 'abbrev', 'author', 'pubinfo', 'page', 'frn', 'frnMicrofilm', 'srn', 'paperlessTitle'];

// Output fields in Gramps order, grouped as on screen. '§N' resolves to the record's chapter.
const OUTPUT_GROUPS = [
  { name: 'Source', fields: [['title', 'Title', 'A8'], ['author', 'Author', '§2'], ['abbrev', 'Abbrev', '§10'], ['pubinfo', 'Pubinfo', 'A10'], ['callNumber', 'Call number', 'A4']] },
  { name: 'Citation', fields: [['page', 'Page', 'A7'], ['confidence', 'Confidence', '§8']] },
  { name: 'Citation note', fields: [['frn', 'FRN', 'A5'], ['srn', 'SRN', 'A5']] },
  { name: 'Paperless scan', fields: [['plTitle', 'Title', 'C1'], ['plDoctype', 'Document type', 'C2'], ['plDateMeaning', 'Date meaning', 'C4'], ['plCorrespondent', 'Correspondent', 'C6'], ['plSourceUrl', 'Source URL', 'C8']] },
];

const STANDARD_LABELS = {
  url: 'Image URL', accessed: 'Access date', eventYear: 'Event year', details: 'Entry details', comment: 'Comment', citedFor: 'Cited for',
  name: 'Name', noun: 'Record noun', subject: 'Subject', srnSubject: 'Subject', entryof: 'Name', author: 'Author',
  // The form row for custplace reads "Place"; its gap is distinct from a record type's own Place input.
  platform: 'Platform', archive: 'Archive', custodian: 'Held by', custplace: "Holder's place",
  pubmedium: 'Pubinfo medium', home: 'Platform homepage',
};

function ruleRef(type, rule) {
  return rule.startsWith('§') ? `${CHAPTER_CODE[type.chapter]} ${rule}` : rule;
}

/** The record type with the draft's page variant merged in. */
function resolveType(type, draft) {
  if (!type.pageVariants) return type;
  const variant = type.pageVariants.find(v => v.key === draft?.variant) || type.pageVariants[0];
  return { ...type, ...variant };
}

/** Every input field the record type can show: [key, label, placeholder]. */
function inputFields(type) {
  const fromVariants = (type.pageVariants || []).flatMap(v => v.citation || []);
  const seen = new Set();
  return [...type.source, ...(type.citation || []), ...fromVariants, ...(type.note || [])]
    .filter(([key]) => !seen.has(key) && seen.add(key));
}

function labeler(type) {
  const labels = Object.fromEntries(inputFields(type).map(([key, label]) => [key, label]));
  if (type.eventYearLabel) labels.eventYear = type.eventYearLabel;
  if (type.detailsLabel) labels.details = type.detailsLabel;
  return key => labels[key] || STANDARD_LABELS[key] || key;
}

/** Whether any of the record type's templates (or only those named), including its page variants, uses {key}. */
function usesToken(type, key, keys = TEMPLATE_KEYS) {
  const templates = [type, ...(type.pageVariants || [])].flatMap(t => keys.map(k => t[k] || ''));
  return templates.some(t => t.includes(`{${key}}`));
}

function usesDetails(type) {
  return Boolean(type.detailsLabel) || usesToken(type, 'details');
}

function newDraft(type) {
  const values = {};
  for (const [key] of inputFields(type)) values[key] = '';
  for (const key of STANDARD_VALUES) values[key] = '';
  for (const key of REFERENCE_VALUES) values[key] = type.defaults?.[key] || '';
  values.pubmedium ||= MEDIA[0];
  const variant = type.pageVariants ? type.pageVariants[0].key : '';
  const resolved = resolveType(type, { variant });
  return {
    type: type.id,
    values,
    subject: { name: '', noun: (resolved.nouns || [''])[0] || '', copy: '', nonHead: false, head: '', which: '', says: '', evidence: '', afterNoun: false },
    confidence: type.confidence || '',
    variant,
    overrides: {},
    example: '',
  };
}

/** Switches the page form; if the current record noun does not belong to the new form, resets it. */
function setVariant(type, draft, key) {
  draft.variant = key;
  const resolved = resolveType(type, draft);
  if (!(resolved.nouns || []).includes(draft.subject.noun)) {
    draft.subject.noun = (resolved.nouns || [''])[0] || '';
  }
}

/**
 * Next citation on this Source: keeps the Source inputs, the reference values, the Source overrides,
 * and the page form; the record noun resets to the first noun of that form, as an original.
 */
function nextCitationDraft(type, draft) {
  const fresh = newDraft(type);
  const keep = [...type.source.map(([key]) => key), ...REFERENCE_VALUES];
  const values = { ...fresh.values };
  for (const key of keep) if (Object.hasOwn(draft.values, key)) values[key] = draft.values[key];
  const sourceFields = OUTPUT_GROUPS[0].fields.map(([key]) => key);
  const overrides = Object.fromEntries(Object.entries(draft.overrides).filter(([key]) => sourceFields.includes(key)));
  const subject = { ...fresh.subject, noun: (resolveType(type, draft).nouns || [''])[0] || '' };
  return { ...draft, values, subject, confidence: fresh.confidence, overrides, example: '' };
}

function exampleLabel(claim) {
  return claim.citation ? `${claim.guide} · citation ${claim.citation}` : claim.guide;
}

function draftFromExample(type, claim) {
  const draft = newDraft(type);
  for (const [key, value] of Object.entries(claim.inputs)) {
    if (SUBJECT_KEYS.includes(key)) draft.subject[key] = value;
    else if (key === 'confidence') draft.confidence = value;
    else if (key === 'variant') draft.variant = value;
    else draft.values[key] = value;
  }
  draft.example = exampleLabel(claim);
  return draft;
}

/**
 * A7 record noun in the form cited: a copy or index replaces a final "entry" with its form
 * (birth and baptism entry → birth and baptism index entry) and follows any other noun
 * (death certificate abstract). With no noun, the form is ignored.
 */
function recordNoun(noun, copy) {
  const n = String(noun ?? '').trim(), form = String(copy ?? '').trim();
  if (!n || !form) return n;
  return /(^|\s)entry$/.test(n) ? n.replace(/entry$/, form) : `${n} ${form}`;
}

/** An index entry or transcript was read in a database; everything else is a digital image of the record. */
function mediumOf(subject) {
  return (subject.noun || '').trim() && ['index entry', 'transcript'].includes((subject.copy || '').trim()) ? 'database' : 'digital image';
}

/** The record noun after the name, as the non-head wording for a household member. */
function nounTail(subject) {
  const base = (subject.noun || '').trim();
  const noun = recordNoun(base, subject.copy);
  if (subject.nonHead && base === 'household') return ` in ${(subject.head || '').trim() || gap('Head')} ${noun}`;
  return noun ? ` ${noun}` : '';
}

function subjectWith(type, subject, parentheticals) {
  const name = (subject.name || '').trim();
  const tail = nounTail(subject);
  const par = parentheticals.map(x => (x || '').trim()).filter(Boolean).join(', ');
  if (type.optionalSubject && !name && !tail && !par) return '';
  const parens = par ? ` (${par})` : '';
  const who = name || gap('Name');
  return subject.afterNoun ? `${who}${tail}${parens}` : `${who}${parens}${tail}`;
}

/** A7 subject: name, then parentheticals (1 which, 2 says, 3 evidence) in one set, then the record noun. */
function subjectOf(type, subject) {
  return subjectWith(type, subject, [subject.which, subject.says, subject.evidence]);
}

/** The SRN's subject (B.1 §10): the page string's subject keeping only the which-entry disambiguator. */
function srnSubjectOf(type, subject) {
  return subjectWith(type, subject, [subject.which]);
}

/**
 * Page locators built from the typed page and image: pageLoc is for the page string, pageRef for
 * the FRN and SRN. With no page number, the image number stands in ("image 62", lower case).
 */
function pageLocators(page, image) {
  const p = String(page ?? '').trim(), i = String(image ?? '').trim();
  if (p) return { pageLoc: i ? `p. ${p} (image ${i})` : `p. ${p}`, pageRef: `p. ${p}` };
  if (i) return { pageLoc: `image ${i}`, pageRef: `image ${i}` };
  const missing = gap('Page or image');
  return { pageLoc: missing, pageRef: missing };
}

/** C1 · default Paperless title: [Subject] [record-noun] [year], with the page string's noun in its form. */
function paperlessTitle(draft, c) {
  const s = draft.subject;
  const which = (s.which || '').trim();
  const out = (c.name || gap('Name')) + (which ? ` (${which})` : '') + nounTail(s);
  const year = String(c.eventYear ?? '').trim();
  return year ? `${out} ${year}` : out;
}

/** Ends a page string or SRN with (what it is cited for), before a closing period or quoted period. */
function endWith(text, citedFor) {
  if (!citedFor) return text;
  if (text.endsWith('."')) return `${text.slice(0, -2)}" (${citedFor}).`;
  if (text.endsWith('.')) return `${text.slice(0, -1)} (${citedFor}).`;
  return `${text} (${citedFor})`;
}

function buildOutputs(type, draft) {
  const t = resolveType(type, draft);
  const L = labeler(type);
  const v = draft.values, s = draft.subject;
  const overrides = draft.overrides || {};
  const pick = (key, built) => (Object.hasOwn(overrides, key) ? overrides[key] : built);

  const name = (s.name || '').trim();
  const noun = recordNoun(s.noun, s.copy);
  const typed = Object.fromEntries(Object.entries(v).map(([k, x]) => [k, typeof x === 'string' ? x.trim() : x]));
  const c = { ...typed, ...(t.derive ? t.derive({ ...typed, name, noun }) : {}), ...pageLocators(typed.page, typed.image) };
  c.name = name;
  c.noun = noun;
  c.subject = subjectOf(t, s);
  c.srnSubject = srnSubjectOf(t, s);
  c.medium = mediumOf(s);
  c.entryof = noun ? `${noun} of ${name || gap(L('name'))}` : (name || gap(L('name')));
  // A form whose own input holds the record's date (eventDate) takes the event year from it, so a
  // year typed for another form or another citation cannot linger in the SRN or the Paperless title.
  if (t.eventDate) c.eventYear = yearOf(c[t.eventDate]) || gap(L(t.eventDate));

  const o = {};
  o.author = pick('author', fill(t.author, c, L));
  c.author = o.author;
  o.title = pick('title', fill(t.title, c, L));
  o.abbrev = pick('abbrev', fill(t.abbrev, c, L));
  // A10 · an online medium names the platform and its homepage from the A10 table; film read in person names
  // its maker, the archive, with no URL. A record type's own template gives an imprint instead.
  const microfilm = c.pubmedium === 'Microfilm';
  c.home = c.platform ? PLATFORMS[c.platform] || gap(L('home')) : '';
  const genealogical = microfilm ? `Microfilm, ${c.archive || gap(L('archive'))}.`
    : c.platform ? `${c.pubmedium || MEDIA[0]}, ${c.platform} (${c.home}).` : '';
  o.pubinfo = pick('pubinfo', t.pubinfo === undefined ? genealogical : fill(t.pubinfo, c, L).trim());
  o.callNumber = pick('callNumber', typed.call || '');
  const page = fill(t.page, c, L);
  // A7 · what the citation is cited for, when given, ends the page string and the SRN, so Gramps lists apart
  // the citations one item gives; each FRN template says "(documenting …)" after its item.
  o.page = pick('page', endWith(page, typed.citedFor));
  o.confidence = draft.confidence;
  // Film read in person takes the digital image's place in the FRN (A10), where the record type has that form.
  const frn = fill(microfilm && t.frnMicrofilm ? t.frnMicrofilm : t.frn, c, L);
  const comment = typed.comment || '';
  o.frn = pick('frn', comment ? `${frn} ${comment}` : frn);
  o.srn = pick('srn', endWith(fill(t.srn, c, L), typed.citedFor));
  o.plTitle = pick('plTitle', t.paperlessTitle ? fill(t.paperlessTitle, c, L) : paperlessTitle(draft, c));
  o.plDoctype = pick('plDoctype', t.doctype);
  o.plDateMeaning = pick('plDateMeaning', DATE_MEANING[t.doctype] || 'event');
  o.plCorrespondent = pick('plCorrespondent', microfilm ? '' : typed.platform || '');
  o.plSourceUrl = pick('plSourceUrl', typed.url || '');
  return o;
}

return { REFERENCE_VALUES, STANDARD_VALUES, SUBJECT_KEYS, ENGINE_TOKENS, TEMPLATE_KEYS, OUTPUT_GROUPS, ruleRef, resolveType, inputFields, labeler, usesToken, usesDetails, newDraft, setVariant, nextCitationDraft, exampleLabel, draftFromExample, recordNoun, subjectOf, srnSubjectOf, pageLocators, endWith, buildOutputs };
})();
__modules["checks.js"] = (() => {
// Rule checks shown in the status bar. Each returns { rule, message } problems.
const { plain, hasGap } = __modules["template.js"];

const RAW_IMAGE_ID = /\b(kb|ft|pf)\d{8,}|\bC\d{7}_\d{3,}|\bFolk_\d+-\d+|\bv\d{4,}\.b\d+/;
const USPS = /(^|[\s,(])(AL|AK|AZ|AR|CA|CO|CT|DE|FL|GA|HI|ID|IL|IN|IA|KS|KY|LA|ME|MD|MA|MI|MN|MS|MO|MT|NE|NV|NH|NJ|NM|NY|NC|ND|OH|OK|OR|PA|RI|SC|SD|TN|TX|UT|VT|VA|WA|WV|WI|WY)([\s,.)]|$)/;
const FIELD_NAMES = {
  title: 'Title', abbrev: 'Abbrev', author: 'Author', pubinfo: 'Pubinfo', page: 'Page', frn: 'FRN', srn: 'SRN',
  plTitle: 'Paperless title', plCorrespondent: 'Correspondent', plSourceUrl: 'Source URL',
};
const escapeRe = s => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');

function runChecks(type, draft, outputs) {
  const o = Object.fromEntries(Object.entries(outputs).map(([k, v]) => [k, plain(v)]));
  const problems = [];
  const add = (rule, message) => problems.push({ rule, message });

  if (RAW_IMAGE_ID.test(o.page)) add('A4', 'The page string contains a raw image ID. Image IDs go only in the FRN URL.');

  const vol = String(draft.values.vol || draft.values.series || '').trim();
  if (['no', 'se'].includes(type.chapter) && vol && !/^\d+$/.test(vol)
    && new RegExp(`(^|[\\s,(])${escapeRe(vol)}([\\s,)]|$)`).test(o.page)) {
    add('A4', `The page string repeats the volume (${vol}). The Source is one volume, so start at the page or entry.`);
  }

  if (/\bAV\/|\bSE\/VA\//.test(o.title)) add('A4', 'The Title contains an archive machine path. Keep it in Call number only.');

  if (/\b\d{4}-\d{4}\b/.test(`${o.title} ${o.abbrev}`)) add('A8', 'Use an en dash in year-ranges (1862–1869), not a hyphen.');

  if (type.chapter === 'us' && USPS.test(`${o.abbrev} ${o.srn}`)) add('B.3 §10', 'Use traditional state abbreviations (Minn., Wis.), never USPS codes.');

  if (String(draft.values.url || '').trim() && !String(draft.values.accessed || '').trim()) add('A5', 'The image URL has no access date.');

  if (!draft.confidence) add('A6', 'Choose a confidence level.');

  const gaps = Object.keys(FIELD_NAMES).filter(k => hasGap(outputs[k]));
  if (gaps.length) add('Fill', `Unfilled parts in: ${gaps.map(k => FIELD_NAMES[k]).join(', ')}.`);

  return problems;
}

return { runChecks };
})();
__modules["compare.js"] = (() => {
// Compares generator output with a worked example from the guide.
const { plain } = __modules["template.js"];

const COMPARED_FIELDS = ['title', 'abbrev', 'author', 'pubinfo', 'callNumber', 'page', 'frn', 'srn'];

/** The guide's expected values for one claim: the whole example, or one citation of a multi-citation example. */
function expectedFor(example, claim) {
  if (claim.citation) {
    const c = example.citations[claim.citation - 1] || {};
    const fields = {};
    for (const key of ['page', 'frn', 'srn']) if (c[key] !== undefined) fields[key] = c[key];
    return { fields, confidence: c.confidence || '' };
  }
  return { fields: example.expected, confidence: example.confidence };
}

/** Fields whose output differs from the guide. */
function diffOutputs(expectedFields, outputs) {
  return COMPARED_FIELDS
    .filter(field => field in expectedFields && expectedFields[field] !== plain(outputs[field]))
    .map(field => ({ field, want: expectedFields[field], got: plain(outputs[field]) }));
}

return { COMPARED_FIELDS, expectedFor, diffOutputs };
})();
__modules["store.js"] = (() => {
// Saves the work in progress in browser storage: the current record type and one draft per type.
const { newDraft, resolveType, usesDetails, OUTPUT_GROUPS } = __modules["engine.js"];
const { COPY_FORMS } = __modules["tables.js"];

const STORE_KEY = 'gcCitationGenerator.v1';
const OUTPUT_KEYS = new Set(OUTPUT_GROUPS.flatMap(g => g.fields.map(([key]) => key)));

// Record nouns renamed when they began to name their form (A7, 2026-09-29), with the record types
// where the new name differs.
const RENAMED_NOUNS = {
  'marriage': 'marriage entry', 'estate': 'estate entry', 'land dispute': 'land dispute entry',
  'court matter': 'court matter entry', 'parish meeting record': 'parish meeting entry',
  'land allotment': 'land allotment entry', 'signatory': 'signatory entry', 'croft transfer': 'croft transfer entry',
  'record': 'census entry',
};
const RENAMED_FOR = { 'us-vital': { 'marriage': 'marriage license' }, 'se-husforhor': { 'record': 'household examination entry' } };

/** A saved noun under its current name; a noun the record type no longer lists gives way to its default. */
function knownNoun(type, draft, saved) {
  const nouns = resolveType(type, draft).nouns || [''];
  const noun = RENAMED_FOR[type.id]?.[saved] ?? RENAMED_NOUNS[saved] ?? saved;
  return nouns.includes(noun) ? noun : nouns[0] || '';
}

/** Returns { current, drafts, filter } or null when nothing usable is saved. */
function loadState(storage, recordById) {
  let saved;
  try {
    saved = JSON.parse(storage?.getItem(STORE_KEY) ?? 'null');
  } catch {
    return null;
  }
  if (!saved || typeof saved !== 'object' || !recordById(saved.current)) return null;
  const drafts = {};
  for (const [id, draft] of Object.entries(saved.drafts || {})) {
    const type = recordById(id);
    if (!type || !draft || typeof draft !== 'object') continue;
    drafts[id] = mergeDraft(type, newDraft(type), draft);
  }
  return { current: saved.current, drafts, filter: typeof saved.filter === 'string' ? saved.filter : '' };
}

function saveState(storage, state) {
  try {
    storage?.setItem(STORE_KEY, JSON.stringify(state));
    return true;
  } catch {
    return false;
  }
}

/**
 * Keeps saved values only where the current version still has the same field (older drafts' holder settings
 * are dropped), maps renamed record nouns, moves retired entry details to Cited for, and drops a copy form
 * the tool no longer offers.
 */
function mergeDraft(type, fresh, saved) {
  const pickKnown = (base, from) => {
    const out = { ...base };
    for (const key of Object.keys(base)) {
      if (from && typeof from[key] === typeof base[key]) out[key] = from[key];
    }
    return out;
  };
  const overrides = {};
  for (const [key, value] of Object.entries(saved.overrides || {})) if (typeof value === 'string' && OUTPUT_KEYS.has(key)) overrides[key] = value;
  const draft = {
    ...fresh,
    values: pickKnown(fresh.values, saved.values),
    subject: pickKnown(fresh.subject, saved.subject),
    confidence: typeof saved.confidence === 'string' ? saved.confidence : fresh.confidence,
    variant: typeof saved.variant === 'string' ? saved.variant : fresh.variant,
    overrides,
    example: '',
  };
  draft.subject.noun = knownNoun(type, draft, draft.subject.noun);
  // The newspaper's "What the item says" box became Cited for (A5, 2026-10-06): a record type without
  // entry details carries a saved value over.
  if (!usesDetails(type) && draft.values.details && !draft.values.citedFor) {
    draft.values.citedFor = draft.values.details;
    draft.values.details = '';
  }
  if (!COPY_FORMS.includes(draft.subject.copy)) draft.subject.copy = '';
  return draft;
}

return { STORE_KEY, loadState, saveState };
})();
__modules["form.js"] = (() => {
// Describes what each wizard step asks for and shows, as plain rows the screen draws.
const { CHAPTERS, LEVELS, PLATFORMS, ARCHIVES, SUGGESTIONS, COPY_FORMS, MEDIA } = __modules["tables.js"];
const { OUTPUT_GROUPS, TEMPLATE_KEYS, resolveType, usesDetails, usesToken, ruleRef, exampleLabel } = __modules["engine.js"];
const { expectedFor, diffOutputs } = __modules["compare.js"];
const { plain } = __modules["template.js"];

const EDITABLE = ['title', 'author', 'abbrev', 'pubinfo', 'callNumber', 'page', 'frn', 'srn',
  'plTitle', 'plDoctype', 'plDateMeaning', 'plCorrespondent', 'plSourceUrl'];
const MONO_KEYS = ['call', 'url', 'turl'];
const FIELD_NAMES = { title: 'Title', abbrev: 'Abbrev', author: 'Author', pubinfo: 'Pubinfo', callNumber: 'Call number', page: 'Page', frn: 'FRN', srn: 'SRN' };

const text = (path, label, value, extra = {}) => ({ path, label, kind: 'text', value: value ?? '', placeholder: '', ...extra });
const area = (path, label, value, placeholder = '') => ({ path, label, kind: 'area', value: value ?? '', placeholder });
const select = (path, label, value, options) => ({ path, label, kind: 'select', value: value ?? '', options });
const check = (path, label, value) => ({ path, label, kind: 'check', value: Boolean(value) });
const capital = word => word[0].toUpperCase() + word.slice(1);

/** The value the record type's worked examples give a key, shown as an example of what goes there. */
function sampleOf(type, key) {
  for (const claim of type.examples || []) {
    const value = claim.inputs?.[key];
    if (typeof value === 'string' && value.trim()) return value.trim();
  }
  return '';
}

const field = (type, [key, label, placeholder], values) =>
  text(`values.${key}`, label, values[key], { placeholder: placeholder || sampleOf(type, key), mono: MONO_KEYS.includes(key) });

/** Record types by chapter, filtered by name or group. */
function recordGroups(records, filter = '') {
  const q = filter.trim().toLowerCase();
  return Object.entries(CHAPTERS)
    .map(([code, label]) => ({ code, label, records: records.filter(r => r.chapter === code && (!q || `${r.name} ${r.group}`.toLowerCase().includes(q))) }))
    .filter(g => g.records.length);
}

/** The Source inputs, in the order the record type lists them. */
function sourceRows(type, draft) {
  return type.source.map(f => field(type, f, draft.values));
}

/**
 * The reference values that describe the Source. The medium opens a genealogical record's Pubinfo (A10), with
 * Microfilm only where the record type can cite the film itself; Archive shows where an FRN names it (a newspaper
 * names it only on film); Held by and Place only where a template says "privately held by".
 */
function referenceRows(type, draft) {
  const v = draft.values;
  const rows = [text('values.platform', 'Platform', v.platform, { list: Object.keys(PLATFORMS) })];
  const film = [type, ...(type.pageVariants || [])].some(x => x.frnMicrofilm);
  if (type.pubinfo === undefined || usesToken(type, 'pubmedium')) {
    rows.push(select('values.pubmedium', 'Pubinfo medium', v.pubmedium, MEDIA.filter(m => film || m !== 'Microfilm').map(m => [m, m])));
  }
  const online = usesToken(type, 'archive', TEMPLATE_KEYS.filter(k => k !== 'frnMicrofilm'));
  if (online || (film && v.pubmedium === 'Microfilm')) rows.push(text('values.archive', 'Archive', v.archive, { list: ARCHIVES[type.chapter] }));
  if (usesToken(type, 'custodian')) rows.push(text('values.custodian', 'Held by', v.custodian, { placeholder: sampleOf(type, 'custodian') }));
  if (usesToken(type, 'custplace')) rows.push(text('values.custplace', 'Place', v.custplace, { placeholder: sampleOf(type, 'custplace') }));
  return rows;
}

/** Page form, locators, the A7 subject with its record noun and parentheticals, confidence, and Cited for. */
function citationRows(type, draft) {
  const t = resolveType(type, draft);
  const v = draft.values, s = draft.subject;
  const sug = SUGGESTIONS[type.chapter];
  const rows = [];
  if (type.pageVariants) rows.push(select('variant', 'Form', draft.variant, type.pageVariants.map(x => [x.key, x.label])));
  rows.push(...(t.citation || []).map(f => field(type, f, v)));
  rows.push(text('subject.name', t.subjectLabel || 'Subject', s.name, { placeholder: sampleOf(type, 'name') }));
  const nouns = t.nouns || [''];
  if (nouns.some(Boolean)) rows.push(select('subject.noun', 'Record noun', s.noun, nouns.map(n => [n, n || '(none)'])));
  if (s.noun.trim()) rows.push(select('subject.copy', 'Original or copy', s.copy, [['', 'Original'], ...COPY_FORMS.map(f => [f, capital(f)])]));
  if (s.noun.trim() === 'household') {
    rows.push(check('subject.nonHead', 'Not the head of household', s.nonHead));
    if (s.nonHead) rows.push(text('subject.head', "Head's surname", s.head, { placeholder: sampleOf(type, 'head') }));
  }
  rows.push(
    text('subject.which', 'Which entry', s.which, { num: 1, list: sug.which, placeholder: sampleOf(type, 'which') || 'b. YYYY, at PLACE…' }),
    text('subject.says', 'Source says', s.says, { num: 2, list: sug.says, placeholder: sampleOf(type, 'says') || sug.says.slice(0, 2).join(', ') + '…' }),
    text('subject.evidence', 'Evidence', s.evidence, { num: 3, list: sug.evidence, placeholder: sampleOf(type, 'evidence') || 'stated age N, named at…' }),
    check('subject.afterNoun', 'Parentheses after noun', s.afterNoun),
    select('confidence', 'Confidence', draft.confidence, [['', 'Choose…'], ...LEVELS.map(l => [l, l])]),
    text('values.citedFor', 'Cited for', v.citedFor, { placeholder: sampleOf(type, 'citedFor') }),
  );
  return rows;
}

/** Image URL and access date, the event year unless the form's own date gives it, extra note inputs, details, comment. */
function noteRows(type, draft) {
  const t = resolveType(type, draft);
  const v = draft.values;
  const rows = [
    text('values.url', 'Image URL', v.url, { mono: true, placeholder: sampleOf(type, 'url') }),
    text('values.accessed', 'Accessed', v.accessed, { placeholder: sampleOf(type, 'accessed') || '21 April 2026' }),
  ];
  if (!t.eventDate) rows.push(text('values.eventYear', type.eventYearLabel || 'Event year', v.eventYear, { placeholder: sampleOf(type, 'eventYear') }));
  rows.push(...(type.note || []).map(f => field(type, f, v)));
  if (usesDetails(type)) rows.push(area('values.details', type.detailsLabel || 'Entry details', v.details, sampleOf(type, 'details')));
  rows.push(area('values.comment', 'Comment after FRN', v.comment, sampleOf(type, 'comment')));
  return rows;
}

/** The output groups (Source, Citation, Citation note, Paperless scan) with each value, its rule, and whether it was edited. */
function outputRows(type, draft, outputs) {
  return OUTPUT_GROUPS.map(g => ({
    name: g.name,
    rows: g.fields.map(([key, label, rule]) => ({
      key, label, ref: ruleRef(type, rule), value: outputs[key] ?? '', text: plain(outputs[key] ?? ''),
      edited: Object.hasOwn(draft.overrides, key), editable: EDITABLE.includes(key),
    })),
  }));
}

/** Whether the outputs still match the guide's worked example the draft was loaded from. */
function exampleNote(type, draft, outputs, guide) {
  if (!draft.example) return '';
  const claim = type.examples.find(c => exampleLabel(c) === draft.example);
  const example = claim && guide?.examples?.[claim.guide];
  if (!example) return `Loaded guide example ${draft.example}`;
  const diffs = diffOutputs(expectedFor(example, claim).fields, outputs);
  return diffs.length
    ? `Differs from guide example ${draft.example}: ${diffs.map(x => FIELD_NAMES[x.field]).join(', ')}`
    : `Matches guide example ${draft.example}`;
}

/**
 * The Repository a new Source names (A9): the archive an FRN cites for the item itself, or a private holder.
 * An archive named only for film read in person (a newspaper's library film) is not the Repository.
 */
function repositoryName(type, draft) {
  const v = draft.values;
  const archive = String(v.archive ?? '').trim(), custodian = String(v.custodian ?? '').trim();
  if (archive && usesToken(type, 'archive', TEMPLATE_KEYS.filter(k => k !== 'frnMicrofilm'))) return archive;
  if (custodian && usesToken(type, 'custodian')) return `${custodian}, private collection`;
  return '';
}

const nameKey = name => String(name ?? '').toLowerCase().replace(/\.com\b/g, '').replace(/[^\p{L}\p{N}]+/gu, ' ').trim();

/** The id of the Paperless row named like the value (Ancestry → Ancestry.com, immigration → Immigration/naturalization), or null. */
function paperlessMatch(value, rows) {
  const want = nameKey(value);
  if (!want) return null;
  const keyed = rows.map(r => [r.id, nameKey(r.name)]);
  const hit = keyed.find(([, k]) => k === want) || keyed.find(([, k]) => k.startsWith(`${want} `));
  return hit ? hit[0] : null;
}

function copyAllText(o) {
  const p = x => plain(x ?? '');
  return [
    'SOURCE', `Title: ${p(o.title)}`, `Author: ${p(o.author)}`, `Abbrev: ${p(o.abbrev)}`, `Pubinfo: ${p(o.pubinfo)}`, `Call number: ${p(o.callNumber)}`, '',
    'CITATION', `Page: ${p(o.page)}`, `Confidence: ${o.confidence || ''}`, '',
    'FIRST REFERENCE NOTE:', p(o.frn), '', 'SHORT REFERENCE NOTE:', p(o.srn),
  ].join('\n');
}

return { EDITABLE, sampleOf, recordGroups, sourceRows, referenceRows, citationRows, noteRows, outputRows, exampleNote, repositoryName, paperlessMatch, copyAllText };
})();
export const { RECORDS, recordById } = __modules["records/index.js"];
export const { REFERENCE_VALUES, STANDARD_VALUES, SUBJECT_KEYS, ENGINE_TOKENS, TEMPLATE_KEYS, OUTPUT_GROUPS, ruleRef, resolveType, inputFields, labeler, usesToken, usesDetails, newDraft, setVariant, nextCitationDraft, exampleLabel, draftFromExample, recordNoun, subjectOf, srnSubjectOf, pageLocators, endWith, buildOutputs } = __modules["engine.js"];
export const { GAP_OPEN, GAP_CLOSE, isBlank, gap, hasGap, plain, gapLabels, templateKeys, fill } = __modules["template.js"];
export const { CHAPTERS, CHAPTER_CODE, LEVELS, PLATFORMS, STATE_ABBREV, ARCHIVES, SUGGESTIONS, DATE_MEANING, MEDIA, COPY_FORMS, isoDate, yearOf, lastWord, allButLastWord, stateAbbrev } = __modules["tables.js"];
export const { runChecks } = __modules["checks.js"];
export const { COMPARED_FIELDS, expectedFor, diffOutputs } = __modules["compare.js"];
export const { STORE_KEY, loadState, saveState } = __modules["store.js"];
export const { EDITABLE, sampleOf, recordGroups, sourceRows, referenceRows, citationRows, noteRows, outputRows, exampleNote, repositoryName, paperlessMatch, copyAllText } = __modules["form.js"];
export const GUIDE = {"changed":"2026-10-06","refs":{"A1":{"title":"A1 · Source scoping","text":"A Source is the natural unit a researcher browses or pulls off the shelf. Scope down to that unit, and push everything more granular (rolls, pages, entries, memorial numbers) into the Citation page string."},"A2":{"title":"A2 · Citation date","text":"Leave the Citation date blank. The field is ambiguous (event, record creation, or access?). Every meaning already has a home below:"},"A3":{"title":"A3 · One citation vs. two","text":"Use one citation when all attached facts share the same evidence quality; use separate citations when they do not. The principle is Mills (EE 1.16): each piece of information in a source is appraised separately. Her example is a colonial South Carolina memorial covering the landowner's own acquisition (primary) and a hundred-year chain of title (secondary)."},"A4":{"title":"A4 · Locators","text":"A volume has two identifiers answering different questions. Keep each in its home and never mix them."},"A5":{"title":"A5 · Citation notes","text":"Source-level notes are optional; the Source fields carry the bibliographic data. Each Citation note holds:"},"A6":{"title":"A6 · Confidence","text":"Use the 5-level Gramps scale, anchored to EE's three axes: original vs. derivative source, primary vs. secondary information, direct vs. indirect evidence."},"A7":{"title":"A7 · Page-string subject","text":"The page string ends in a subject: [locators], [name] [record-noun]. Locator words are lower case, even at the start of the page string (p. 57, image 62, certificate no. 1929-MN-XXXXXX, district 009 Blegstad); names keep their capitals."},"A8":{"title":"A8 · Title","text":"Titles are EE locality-led: largest jurisdiction first, then record series/type and identifier, then year-range. A formal collection name may follow but never leads."},"A9":{"title":"A9 · Repository","text":"Decide in this order: A physical archive holds the original → name it (Statsarkivet i Oslo, Riksarkivet, Värmlandsarkiv, National Archives, [State] Historical Society, [County] County Courthouse, Family History Library when a microfilm number applies). A specific NARA facility goes in the FRN, not here. A family member or private party holds it → [Custodian], private collection (EE 4.24 to 4.29). It is a publication or online-only platform → blank. A website is a publication, not a repository (EE 2.34); the same holds for library-held books."},"A10":{"title":"A10 · Pubinfo","text":"Genealogical records: [medium], [platform] (homepage URL)."},"A11":{"title":"A11 · Bibliography","text":"Gramps fields are built for in-app display. For the book's bibliography, transform them into EE Source List Entries; never print the Title field directly."},"A12":{"title":"A12 · Privacy","text":"Apply EE 4.31 to living informants (interviewees, correspondents, custodians): keep their street address in working files, never in a published citation, while they are alive."},"A13":{"title":"A13 · Universal abbreviations","text":"Used in FRN, SRN, and Abbrev wherever a locator is needed (EE 2.53):"},"C1":{"title":"C1 · Title","text":"Format: [Subject] [record-noun] [year]"},"C2":{"title":"C2 · Document type","text":"Classified by genealogical content, not by issuer."},"C3":{"title":"C3 · Date","text":"The underlying event's date when there is one; otherwise when the document was created or issued (C4 says which). Year only: use 1 January + qualifier year only (1 January is then a placeholder, never a real date). A range: use the start year; the range can go in the Title. This is separate from the Gramps Citation date, which stays blank (A2)."},"C4":{"title":"C4 · Date meaning","text":""},"C5":{"title":"C5 · Date qualifier","text":""},"C6":{"title":"C6 · Correspondent","text":"The digital provider hosting the image: a small, stable list matching the A10 platforms (FamilySearch, Ancestry, Digitalarkivet, Riksarkivet, ArkivDigital, Newspapers.com, Nasjonalbiblioteket, Lantmäteriet). A platform, never a physical archive or a person. Blank when the document did not come from a digital provider: microfilm read at a library, interviews, personal research, letters, and family-held artifacts."},"C7":{"title":"C7 · Tags","text":"Open (TBD). The worked examples use person, place, date, format, and status tags such as attributed."},"C8":{"title":"C8 · Source URL","text":"The canonical link that takes you back to the image or its indexed record. This deep link differs from Gramps Pubinfo, which holds only the homepage. Film read at a library has no link, so its Source URL is blank."},"C9":{"title":"C9 · Source URL access","text":""},"C10":{"title":"C10 · Permalink","text":"An alternative URL with a persistent identifier, only when the site advertises it as one: https://urn.digitalarkivet.no/URN:NBN:no-a1450-ft20101203340184.jpg · https://goto.digitalarkivet.no/kb20060926010303."},"C11":{"title":"C11 · Family group, Provenance, Physical location","text":""},"B.1 §1":{"title":"B.1 §1 · Scope","text":"One Source per archival volume / fond (A1). Record types covered: Parish records (kirkebøker): ministerialbok and klokkerbok; baptisms, confirmations, marriages, burials. Census (folketelling): the 1801 nominal census and the decennial 1865+ censuses. Court records (sorenskriverarkiv): tingbøker (court journals)."},"B.1 §2":{"title":"B.1 §2 · Source author","text":"Parish or court name alone, no country or umbrella prefix."},"B.1 §3":{"title":"B.1 §3 · Repository","text":""},"B.1 §4":{"title":"B.1 §4 · Source title","text":"Locality-led (A8), with the series in its Norwegian name followed by an English gloss in square brackets (EE 2.28), as in B.2 §4: Norway, [fylke or amt], [parish or court], [Norwegian series name] [English gloss] [volume], [year-range]. Capitalize the series name, and use the same gloss in the FRN and bibliography. Year-ranges follow the volume identifier with no parentheses (Digitalarkivet's own form), using en dashes."},"B.1 §5":{"title":"B.1 §5 · Locator tokens","text":""},"B.1 §6":{"title":"B.1 §6 · Pubinfo","text":""},"B.1 §7":{"title":"B.1 §7 · Page-string templates","text":""},"B.1 §8":{"title":"B.1 §8 · Confidence","text":""},"B.1 §9":{"title":"B.1 §9 · Subject vocabulary","text":"Record nouns (A7); the first is the default:"},"B.1 §10":{"title":"B.1 §10 · Abbrev","text":"House variation: the record-type word is lowercased (EE 2.29 keeps original capitals; lowercase gives visual contrast with the Title), and the Abbrev drops the gloss. Parish format: [Parish] [kirkebok|klokkerbok] [vol] ([year-range]). Court format: [Sorenskriveri] [tingbok|skifteprotokoll] [vol] ([year-range]). Unlike the Title, the Abbrev puts the year-range in parentheses."},"B.1 §11":{"title":"B.1 §11 · Bibliography","text":"A11 geographic form (EE 2.48): country, fylke, prestegjeld/herred, series + bracketed English gloss (EE 2.28), volume + years, repository + call number, medium, publisher, URL : year. Group under Norway:, alphabetize by fylke then prestegjeld."},"B.1 §12":{"title":"B.1 §12 · Worked examples","text":""},"B.2 §1":{"title":"B.2 §1 · Scope","text":"One Source per discrete NAD fond: each parish kyrkoarkiv volume series, each häradsrätt series, each SVAR database (A1). Record types covered: Parish records (kyrkoarkiv): Husförhörslängder (clerical survey), Lysnings- och Vigselbok (banns and marriage), Födelse- och dopböcker (birth and baptism), Dödbok (death/burial). Court records: Bouppteckningar (estate inventories) and other häradsrätt series. SVAR databases: Folkräkning (census) and other Riksarkivet databases."},"B.2 §2":{"title":"B.2 §2 · Source author","text":""},"B.2 §3":{"title":"B.2 §3 · Repository","text":""},"B.2 §4":{"title":"B.2 §4 · Source title","text":"Locality-led (A8), with the series in its original Swedish name followed by an English gloss in square brackets (EE 2.28): Sweden, [län], [parish or härad], [Swedish series name] [English gloss] [volume], [year-range]. Keep the series name's original capitalization, and use the same gloss as the FRN."},"B.2 §5":{"title":"B.2 §5 · Locator tokens","text":""},"B.2 §6":{"title":"B.2 §6 · Pubinfo","text":""},"B.2 §7":{"title":"B.2 §7 · Page-string templates","text":"Standard: p. [P] (image [I]), [entry], [subject]. Unpaginated fallback is image [I], [entry], [subject]. Each Source is one volume, so the volume is not repeated here (A4)."},"B.2 §8":{"title":"B.2 §8 · Confidence","text":""},"B.2 §9":{"title":"B.2 §9 · Subject vocabulary","text":"Record nouns (A7); the first is the default:"},"B.2 §10":{"title":"B.2 §10 · Abbrev","text":"Record-type word lowercased (Scandinavian house variation, see B.1 §10). Parish: [Parish] [record-type] [vol] ([years]). Court and other state records: [Creating body] [record-type] [vol] ([years]). Land survey: [Parish] [survey type] [act-no] ([years]). The SRN is built as in B.1 §10: the Abbrev, then the locators, then the subject."},"B.2 §11":{"title":"B.2 §11 · Bibliography","text":"A11 geographic form (EE 2.48) with bracketed English glosses (EE 2.28). Group under Sweden:, alphabetize by län then parish or härad. SVAR databases go in a trailing Online databases group by title, with no repository (EE 2.34, 11.53)."},"B.2 §12":{"title":"B.2 §12 · Worked examples","text":"Glosses (in the Title and at the series' first mention in the FRN; the Abbrev and SRN drop them): Husförhörslängder [household examinations] · Lysnings- och Vigselbok [banns and marriage book] · Födelse- och dopböcker [birth and baptism books] · Dödbok [death book] · Bouppteckningar [estate inventories] · Folkräkning [census] · laga skifte [statutory land enclosure]. These match EE 11.47, 11.50, 11.56."},"B.3 §1":{"title":"B.3 §1 · Scope","text":"One Source per unit a researcher browses on Ancestry/FamilySearch or pulls from an archive (A1)."},"B.3 §2":{"title":"B.3 §2 · Source author","text":"Bare body name: Bureau of the Census, never U.S. Bureau of the Census."},"B.3 §3":{"title":"B.3 §3 · Repository","text":""},"B.3 §4":{"title":"B.3 §4 · Source title","text":""},"B.3 §5":{"title":"B.3 §5 · Locator tokens","text":""},"B.3 §6":{"title":"B.3 §6 · Pubinfo","text":"[medium], [platform] (homepage URL). per A10. Examples: Digital images, Ancestry (https://www.ancestry.com). · Database with images, FamilySearch (https://www.familysearch.org). Published directories use the imprint variant (Example 7). Newspapers read on a library's film use Microfilm, Minnesota Historical Society.; a title read both there and online is one Source, and A10 picks its Pubinfo (Example 13). For church records, the named digitized collection (e.g. \"U.S., Evangelical Lutheran Church in America, Swedish American Church Records, 1800–1952\") goes in the FRN, not Pubinfo."},"B.3 §7":{"title":"B.3 §7 · Page-string templates","text":""},"B.3 §8":{"title":"B.3 §8 · Confidence","text":""},"B.3 §9":{"title":"B.3 §9 · Subject vocabulary","text":"Record nouns (A7); the first is the default. Passenger manifest and Find a Grave memorial take no noun: the list or memorial number says what it is."},"B.3 §10":{"title":"B.3 §10 · Abbrev","text":"The US Abbrev keeps whole readable words (St. Louis Co. naturalizations, 1888–1955); heavier abbreviation belongs in the SRN (St. Louis Co. natz.)."},"B.3 §11":{"title":"B.3 §11 · Bibliography","text":"A11 geographic form: [State]. [County]. [Locality/series]. [Series] [volume] ([years]). [Repository], [call number]. [Medium]. [Publisher]. [URL] : [year]. Group under a state header, alphabetize by county. Directories go by publisher (EE 2.46); online-only databases in a trailing group by title."},"B.3 §12":{"title":"B.3 §12 · Worked examples","text":""},"B.4 §1":{"title":"B.4 §1 · Scope","text":"Published works scope by bibliographic unit, artifacts by physical thing, interviews by event (A1)."},"B.4 §2":{"title":"B.4 §2 · Source author","text":""},"B.4 §3":{"title":"B.4 §3 · Repository","text":""},"B.4 §4":{"title":"B.4 §4 · Source title","text":"Most titles here are author-led or artifact-led, not locality-led, because these sources are arranged by author, collection, or custodian (A11). A place-focused history shelved with locality material may use the A8 form. Foreign titles take a bracketed English gloss in the FRN (EE 2.28)."},"B.4 §5":{"title":"B.4 §5 · Locator tokens","text":""},"B.4 §6":{"title":"B.4 §6 · Pubinfo","text":""},"B.4 §7":{"title":"B.4 §7 · Page-string templates","text":""},"B.4 §8":{"title":"B.4 §8 · Confidence","text":""},"B.4 §9":{"title":"B.4 §9 · Subject vocabulary","text":"Record nouns (A7); the first is the default, and (none) means the noun may be left off:"},"B.4 §10":{"title":"B.4 §10 · Abbrev Pending review","text":"Shortest unambiguous work title or artifact identity + year or volume, whole words (heavier abbreviation goes in the SRN):"},"B.4 §11":{"title":"B.4 §11 · Bibliography","text":"Arranged by author (EE 2.46), collection (EE 2.47), or custodian (EE 4.24 to 4.29), not by locality. Authored publications sit alphabetically in the main body; artifacts, interviews, and personal research get trailing headings."},"B.4 §12":{"title":"B.4 §12 · Worked examples","text":"Ordered by EE chapter (4 artifacts, then 13 published works)."}},"examples":{"B.1 Example 1":{"expected":{"title":"Norway, Akershus, Eidsvoll, Klokkerbok [parish register (copy)] I 2, 1866–1871","abbrev":"Eidsvoll klokkerbok I 2 (1866–1871)","author":"Eidsvoll prestekontor","pubinfo":"Digital images, Digitalarkivet (https://www.digitalarkivet.no).","callNumber":"AV/SAO-A-10888/G/Ga/L0002","page":"p. 57 (image 62), no. 21, Thor Emil birth and baptism entry","frn":"Eidsvoll prestekontor, Klokkerbok [parish register (copy)] no. I 2, 1866–1871, p. 57, no. 21, Thor Emil (born 1 September 1869; baptized 16 January 1870), son of Christian Henningsen and Anne Marthe Bergersdatter, baptized at Eidsvoll church; digital image, Digitalarkivet (https://urn.digitalarkivet.no/URN:NBN:no-a1450-kb20060313011115.jpg : accessed 17 April 2026); citing Statsarkivet i Oslo, AV/SAO-A-10888/G/Ga/L0002.","srn":"Eidsvoll klokkerbok I 2 (1866–1871), p. 57, no. 21, Thor Emil birth and baptism entry."},"confidence":"High","citations":[]},"B.1 Example 2":{"expected":{"title":"Norway, Akershus, Eidsvoll, Folketelling [census] 1875","abbrev":"Eidsvoll folketelling 1875","author":"Riksarkivet","pubinfo":"Database with images, Digitalarkivet (https://www.digitalarkivet.no).","callNumber":"AV/RA-S-2231/E","page":"district 009 Blegstad, p. 1270, household 01, person 006, Karen Indiana Evensdatter (tjenestepige, stated age 14) in Hansen household","frn":"Folketelling [census] 1875, Akershus fylke, Eidsvoll prestegjeld, Eidsvoll sokn, district 009 Blegstad, p. 1270, household no. 01, person no. 006, Karen Indiana Evensdatter (tjenestepige, stated age 14, in Jens Hansen's household); digital image, Digitalarkivet (https://www.digitalarkivet.no/ft20110110330371 : accessed 26 April 2026); transcribed entry at https://www.digitalarkivet.no/pf01052052005225; citing Riksarkivet, Statistisk sentralbyrå, Sosioøkonomiske emner, Folketellinger, boliger og boforhold, E: Folketellinger, source ID 52052; archive reference AV/RA-S-2231/E.","srn":"Eidsvoll folketelling 1875, p. 1270, household 01, Karen Indiana Evensdatter in Hansen household."},"confidence":"High","citations":[]},"B.1 Example 3":{"expected":{"title":"Norway, Akershus, Eidsvoll sorenskriveri, Skifteprotokoll [probate register] II 3, 1815–1825","abbrev":"Eidsvoll sorenskriveri skifteprotokoll II 3 (1815–1825)","author":"Eidsvoll sorenskriveri","pubinfo":"Digital images, Digitalarkivet (https://www.digitalarkivet.no).","callNumber":"AV/SAO-A-10063/H/Hb/L0003","page":"folio 145–148, Anders Hansen estate entry","frn":"Eidsvoll sorenskriveri [Eidsvoll district court], Skifteprotokoll [probate register] II 3, 1815–1825, fol. 145–148, estate inventory of Anders Hansen, Vinger gård, died 1822; digital image, Digitalarkivet (https://www.digitalarkivet.no/... : accessed 9 May 2026); citing Statsarkivet i Oslo, AV/SAO-A-10063/H/Hb/L0003.","srn":"Eidsvoll sorenskriveri skifteprotokoll II 3 (1815–1825), fol. 145–148, Anders Hansen estate entry."},"confidence":"High","citations":[]},"B.1 Example 4":{"expected":{"title":"Norway, Akershus amt, Eidsvoll prestegjeld, Matrikkel [land register] 1838","abbrev":"Eidsvoll matrikkel 1838","author":"Riksarkivet","pubinfo":"Database with images, Digitalarkivet (https://www.digitalarkivet.no).","page":"gård no. 234, Vinger gård, løpenummer 12, Anders Hansen matrikkel entry","frn":"Matrikkel [land register] 1838, Akershus amt, Eidsvoll prestegjeld, gård no. 234, Vinger gård, løpenummer 12, listed owner Anders Hansen; digital image, Digitalarkivet (https://www.digitalarkivet.no/... : accessed 9 May 2026); citing Riksarkivet.","srn":"Eidsvoll matrikkel 1838, gård 234 Vinger, løpenr. 12, Anders Hansen matrikkel entry."},"confidence":"High","citations":[]},"B.1 Example 5":{"expected":{"page":"confirmations, p. 88 (image 91), no. 14, Karen Indiana Evensdatter confirmation entry","frn":"Eidsvoll prestekontor, Klokkerbok [parish register (copy)] no. I 2, 1866–1871, confirmations section, p. 88, no. 14, Karen Indiana Evensdatter (daughter of Even Hansen), confirmed at Eidsvoll church 1869; digital image, Digitalarkivet (https://www.digitalarkivet.no/... : accessed 15 June 2026); citing Statsarkivet i Oslo, AV/SAO-A-10888/G/Ga/L0002.","srn":"Eidsvoll klokkerbok I 2 (1866–1871), confirmations, p. 88, no. 14, Karen Indiana Evensdatter confirmation entry."},"confidence":"High","citations":[]},"B.2 Example 1":{"expected":{"title":"Sweden, Värmland, Norra Ny, Husförhörslängder [household examinations] AI:11, 1812–1820","abbrev":"Norra Ny husförhörslängd AI:11 (1812–1820)","author":"Norra Ny församling","pubinfo":"Digital images, Riksarkivet (https://sok.riksarkivet.se).","callNumber":"SE/VA/13398/A I/11","page":"p. 8 (image 19), Per Persson household","frn":"Norra Ny församling, Husförhörslängder [household examinations], vol. AI:11 (1812–1820), p. 8, household of Per Persson, Ambjörby Torpare; digital image, Riksarkivet (https://sok.riksarkivet.se/bildvisning/C0038409_00019 : accessed 20 April 2026); citing Värmlandsarkiv, SE/VA/13398/A I/11.","srn":"Norra Ny husförhörslängd AI:11 (1812–1820), p. 8, Per Persson household."},"confidence":"High","citations":[]},"B.2 Example 2":{"expected":{"title":"Sweden, Värmland, Älvdals härad, Bouppteckningar [estate inventories] FII:26, 1832–1833","abbrev":"Älvdals häradsrätt bouppteckning FII:26 (1832–1833)","author":"Älvdals häradsrätt","pubinfo":"Digital images, ArkivDigital (https://www.arkivdigital.se).","callNumber":"SE/VA/11047/F II/26","page":"pp. 203–205, Per Persson estate inventory","frn":"Älvdals häradsrätt [Älvdal district court], Bouppteckningar [estate inventories], vol. FII:26 (1832–1833), pp. 203–205, estate inventory of Per Persson, Ambjörbymon, Norra Ny parish, died 5 May 1832; digital image, ArkivDigital (https://app.arkivdigital.se/volume/v48177?image=104 : accessed 20 April 2026); citing Värmlandsarkiv, SE/VA/11047/F II/26.","srn":"Älvdals häradsrätt bouppteckning FII:26 (1832–1833), pp. 203–205, Per Persson estate inventory."},"confidence":"High","citations":[]},"B.2 Example 3":{"expected":{"title":"Sweden, Värmland, Norra Ny, Folkräkning [census] 1880","abbrev":"Norra Ny folkräkning 1880","author":"Riksarkivet","pubinfo":"Database with images, Riksarkivet (https://sok.riksarkivet.se).","callNumber":"Folk_817085","page":"p. 4, row 33, family no. 1, Lars Persson Ambjörn household","frn":"Sveriges folkräkning 1880 [Swedish census 1880], Norra Ny församling, Värmlands län, p. 4, row 33, family no. 1, household of Lars Persson Ambjörn, Ambjörby; digital image, Riksarkivet (https://sok.riksarkivet.se/bildvisning/Folk_817085-004 : accessed 21 April 2026).","srn":"Norra Ny folkräkning 1880, p. 4, row 33, Lars Persson Ambjörn household."},"confidence":"High","citations":[]},"B.2 Example 4":{"expected":{"page":"p. 8 (image 19), Lars Persson confirmation entry","frn":"Norra Ny församling, Husförhörslängder [household examinations], vol. AI:11 (1812–1820), p. 8, confirmation entry of Lars Persson; digital image, Riksarkivet (https://sok.riksarkivet.se/... : accessed 20 April 2026); citing Värmlandsarkiv, SE/VA/13398/A I/11.","srn":"Norra Ny husförhörslängd AI:11 (1812–1820), p. 8, Lars Persson confirmation entry."},"confidence":"High","citations":[]},"B.2 Example 5":{"expected":{"title":"Sweden, Värmland, Norra Ny, laga skifte [statutory land enclosure], act 17-NON-148, 1856–1862","abbrev":"Norra Ny laga skifte 17-NON-148 (1856–1862)","author":"Lantmäterimyndigheten i Värmlands län","pubinfo":"Digital images, Lantmäteriet (https://historiskakartor.lantmateriet.se).","page":"delningsbeskrivning p. 40, Marit Andersdotter land allotment entry (Lott A, 64 öre 6 penningar)","frn":"Lantmäterimyndigheten i Värmlands län, laga skifte [statutory land enclosure], Ambjörby, Norra Ny socken, act 17-NON-148, surveyed 1856–1862 by O. Ignelius, confirmed by Älvdals övre tingslags egodelningsrätt 3 October 1863; delningsbeskrivning p. 40, land allotment (Lott A) of the minor Marit Andersdotter, 64 öre 6 penningar skatt; digital image, Lantmäteriet (https://historiskakartor.lantmateriet.se : accessed 16 June 2026).","srn":"Norra Ny laga skifte 17-NON-148 (1856–1862), delningsbeskrivning p. 40, Marit Andersdotter land allotment entry."},"confidence":"High","citations":[]},"B.3 Example 1":{"expected":{"title":"1920 U.S. Federal Census, St. Louis County, Minnesota","abbrev":"St. Louis Co., Minn., 1920 census","author":"Bureau of the Census","pubinfo":"Digital images, Ancestry (https://www.ancestry.com).","callNumber":"T625","page":"roll 859, ED 139, sheet 8A, dwelling [N], family [N], Steve Maisuk household","frn":"1920 U.S. census, St. Louis County, Minnesota, population schedule, Duluth, enumeration district 139, sheet 8A, dwelling [N], family [N], Steve Maisuk household; digital image, Ancestry (https://www.ancestry.com/... : accessed 6 May 2026); citing National Archives microfilm publication T625, roll 859.","srn":"1920 U.S. census, St. Louis Co., Minn., pop. sched., Duluth, ED 139, sheet 8A, Steve Maisuk household."},"confidence":"High","citations":[]},"B.3 Example 2":{"expected":{"title":"Minnesota, death certificates, 1908–2002","abbrev":"Minn. death certificates, 1908–2002","author":"Minnesota Department of Health, Vital Records","pubinfo":"Database with images, FamilySearch (https://www.familysearch.org).","callNumber":"","page":"certificate no. 1929-MN-XXXXXX, Per Larsson Grund death certificate","frn":"Minnesota, death certificate no. 1929-MN-XXXXXX (1929), Per Larsson Grund; Minnesota Department of Health, Vital Records; digital image, FamilySearch (https://www.familysearch.org/... : accessed 6 May 2026); citing Minnesota Historical Society.","srn":"Minn. death cert. 1929-MN-XXXXXX (1929), Per Larsson Grund."},"confidence":"Very High","citations":[]},"B.3 Example 3":{"expected":{"title":"Minnesota, St. Louis County, District Court, Naturalization Records, 1888–1955","abbrev":"St. Louis Co. naturalizations, 1888–1955","author":"St. Louis County District Court","pubinfo":"Digital images, Ancestry (https://www.ancestry.com).","page":"petition no. [N], Per Larsson naturalization petition","frn":"St. Louis County District Court (Duluth, Minnesota), Naturalization Records, petition no. [N] (1894), Per Larsson; digital image, Ancestry (https://www.ancestry.com/... : accessed 6 May 2026); citing Minnesota Historical Society.","srn":"St. Louis Co. natz., pet. no. [N] (1894), Per Larsson."},"confidence":"High","citations":[]},"B.3 Example 4":{"expected":{"title":"Minnesota, St. Louis County, Forest Hill Cemetery, Find a Grave Memorials","abbrev":"Forest Hill, Duluth, FAG","author":"","callNumber":"","pubinfo":"Database with images, Find a Grave (https://www.findagrave.com).","page":"memorial no. [N], Per Larsson Grund","frn":"Find a Grave, memorial no. [N], Per Larsson Grund (1848–1929), Forest Hill Cemetery, Duluth, St. Louis County, Minnesota; database with images, Find a Grave (https://www.findagrave.com/memorial/[N] : accessed 6 May 2026); marker photograph by [contributor name], [date].","srn":"FAG memorial [N], Per Larsson Grund, Forest Hill Cemetery."},"confidence":"High","citations":[]},"B.3 Example 5":{"expected":{"title":"World War II Draft Registration Cards, Minnesota","abbrev":"WWII draft cards, Minn.","author":"Selective Service System","pubinfo":"Digital images, FamilySearch (https://www.familysearch.org).","callNumber":"RG 147","page":"serial no. [N], Axel O. Grund WWII draft card","frn":"Selective Service System, World War II Draft Registration Cards, Minnesota, serial no. [N], Axel O. Grund (1942); digital image, FamilySearch (https://www.familysearch.org/... : accessed 6 May 2026); citing Record Group 147, National Archives.","srn":"WWII draft card, Minn., Axel O. Grund."},"confidence":"High","citations":[]},"B.3 Example 6":{"expected":{"title":"Applications for Headstones for U.S. Military Veterans, 1925–1941","abbrev":"Headstone applications, 1925–1941","author":"Office of the Quartermaster General","pubinfo":"Digital images, Ancestry (https://www.ancestry.com).","callNumber":"RG 92","page":"Axel O. Grund (d. 1948) headstone application","frn":"Office of the Quartermaster General, \"Applications for Headstones for U.S. Military Veterans, 1925–1941,\" application for Axel O. Grund, died 31 October 1948; digital image, Ancestry (https://www.ancestry.com/search/collections/2375/records/45037 : accessed 6 May 2026); citing NAID 596118, Record Group 92, National Archives at Washington, DC.","srn":"Headstone app., Axel O. Grund (d. 1948)."},"confidence":"Normal","citations":[]},"B.3 Example 7":{"expected":{"title":"Polk's Duluth City Directory, 1900","abbrev":"Polk's Duluth directory, 1900","author":"R. L. Polk & Co.","pubinfo":"Duluth: R. L. Polk & Co., 1900. Digital images, Ancestry (https://www.ancestry.com).","page":"p. 412, Per Larsson Grund directory entry","frn":"R. L. Polk & Co., Polk's Duluth City Directory, 1900 (Duluth: R. L. Polk & Co., 1900), p. 412, Per Larsson Grund; digital image, Ancestry (https://www.ancestry.com/... : accessed 6 May 2026).","srn":"Polk's Duluth dir., 1900, p. 412, Per Larsson Grund."},"confidence":"Normal","citations":[]},"B.3 Example 8":{"expected":{"title":"Duluth Herald, Duluth, Minnesota","abbrev":"Duluth Herald","pubinfo":"Digital images, Newspapers.com (https://www.newspapers.com).","author":"","callNumber":"","page":"14 July 1929, p. 7, col. 3, Per Larsson Grund obituary","frn":"\"Per L. Grund, Duluth Pioneer, Dies at Williams Farm,\" Duluth Herald (Duluth, Minnesota), 14 July 1929, p. 7, col. 3, Per Larsson Grund obituary; digital image, Newspapers.com (https://www.newspapers.com/... : accessed 6 May 2026).","srn":"Duluth Herald, 14 July 1929, p. 7, col. 3, Per Larsson Grund obituary."},"confidence":"Normal","citations":[]},"B.3 Example 9":{"expected":{"title":"Warren Sheaf, Warren, Minnesota","abbrev":"Warren Sheaf","pubinfo":"Digital images, Newspapers.com (https://www.newspapers.com).","page":"3 December 1908, p. 1, Grund-Hoiberg marriage announcement","frn":"\"[Headline if present],\" Warren Sheaf (Warren, Minnesota), 3 December 1908, p. 1, Grund-Hoiberg marriage announcement; digital image, Newspapers.com (https://www.newspapers.com/image/[N] : accessed 6 May 2026).","srn":"Warren Sheaf, 3 December 1908, p. 1, Grund-Hoiberg marriage announcement."},"confidence":"High","citations":[]},"B.3 Example 10":{"expected":{},"confidence":"","citations":[{"page":"17 May 1916, p. 7, Alma column, Peter Grund news mention","confidence":"Normal","frn":"\"Alma\" [column], Warren Sheaf (Warren, Minnesota), 17 May 1916, p. 7, Peter Grund news mention; digital image, Newspapers.com (https://www.newspapers.com/image/64259642 : accessed 6 May 2026).","srn":"Warren Sheaf, 17 May 1916, p. 7, Alma column, Peter Grund news mention."},{"page":"17 May 1916, p. 7, Alma column, John Olson news mention","confidence":"Normal","frn":"\"Alma\" [column], Warren Sheaf (Warren, Minnesota), 17 May 1916, p. 7, John Olson news mention; digital image, Newspapers.com (https://www.newspapers.com/image/64259642 : accessed 6 May 2026).","srn":"Warren Sheaf, 17 May 1916, p. 7, Alma column, John Olson news mention."}]},"B.3 Example 11":{"expected":{"title":"Minnesota, Marshall County, Warren, First Lutheran Church records","abbrev":"First Lutheran Church, Warren, Minn., records, 1800–1952","author":"First Lutheran Church, Warren","pubinfo":"Digital images, Ancestry (https://www.ancestry.com).","page":"death and burial register, p. 283 (image 496, right), Emma Söderström death and burial entry","frn":"First Lutheran Church (Warren, Marshall County, Minnesota), death and burial register, p. 283 (image 496, right), death and burial of Emma Söderström, died 7 May 1914, buried 9 May 1914; digital image, Ancestry (https://www.ancestry.com/search/collections/61584/records/63230716 : accessed 16 June 2026), \"U.S., Evangelical Lutheran Church in America, Swedish American Church Records, 1800–1952\"; citing Swenson Swedish Immigration Research Center, Augustana College, Rock Island, Illinois.","srn":"First Lutheran Church (Warren, Minn.), death and burial entry of Emma Söderström, p. 283."},"confidence":"Very High","citations":[]},"B.3 Example 12":{"expected":{"title":"Minnesota, Marshall County, District Court, Naturalization Records, 1853–1967","abbrev":"Marshall Co. naturalizations, 1853–1967","author":"Marshall County District Court","pubinfo":"Digital images, FamilySearch (https://www.familysearch.org).","callNumber":"SAM 227","page":"reel 4, final papers vol. C, p. 296 (image [I]), Peter L. Grund naturalization petition","frn":"Marshall County District Court (Warren, Minnesota), Naturalization Records, final papers vol. C, p. 296 (12 March 1897), Peter L. Grund; digital image, FamilySearch (https://www.familysearch.org/ark:/61903/3:1:... : accessed [date]), Image Group Number 101714756, image [I]; citing Minnesota Historical Society microfilm SAM 227, reel 4.","srn":"Marshall Co. natz., final papers vol. C, p. 296 (1897), Peter L. Grund."},"confidence":"High","citations":[]},"B.3 Example 13":{"expected":{"title":"Warren Sheaf, Warren, Minnesota","abbrev":"Warren Sheaf","pubinfo":"Digital images, Newspapers.com (https://www.newspapers.com).","author":"","callNumber":""},"confidence":"","citations":[{"page":"3 December 1908, p. 1, Grund-Hoiberg marriage announcement","confidence":"High","frn":"\"[Headline if present],\" Warren Sheaf (Warren, Minnesota), 3 December 1908, p. 1, Grund-Hoiberg marriage announcement; digital image, Newspapers.com (https://www.newspapers.com/image/[N] : accessed 6 May 2026).","srn":"Warren Sheaf, 3 December 1908, p. 1, Grund-Hoiberg marriage announcement."},{"page":"[date], p. [N], col. [N], [Name] obituary","confidence":"Normal","frn":"\"[Headline],\" Warren Sheaf (Warren, Minnesota), [date], p. [N], col. [N], [Name] obituary; Minnesota Historical Society microfilm.","srn":"Warren Sheaf, [date], p. [N], col. [N], [Name] obituary."}]},"B.3 Example 14":{"expected":{"title":"Warren Sheaf, Warren, Minnesota","abbrev":"Warren Sheaf","pubinfo":"Digital images, Newspapers.com (https://www.newspapers.com).","author":"","callNumber":"","page":"11 July 1917, p. 3, col. 1, Olaf Nygren household news mention (date and attendees)","frn":"\"This Honored Couple Celebrate Golden Wedding,\" Warren Sheaf (Warren, Minnesota), 11 July 1917, p. 3, col. 1, Olaf Nygren household news mention (documenting date and attendees); digital image, Newspapers.com (https://www.newspapers.com/article/warren-sheaf-mr-mrs-olaf-nygren-50th/12517574/ : accessed 4 October 2026).","srn":"Warren Sheaf, 11 July 1917, p. 3, col. 1, Olaf Nygren household news mention (date and attendees)."},"confidence":"Normal","citations":[]},"B.4 Family Bible":{"expected":{"title":"Grund Family Bible Records, 1848–1932","abbrev":"Grund Family Bible","author":"[Per Larsson Grund]","pubinfo":"","page":"family page 2, Per Larsson Grund birth entry","frn":"[Per Larsson Grund], compiler, Grund Family Bible Records, 1848–1932, in The Holy Bible Containing the Old and New Testaments (Stockholm: [Bible publisher], [year]), family page 2, entry for Per Larsson Grund born 14 January 1848 at Ambjörby, Norra Ny parish; privately held by Peter Grund, Duluth, Minnesota. Entries appear in two distinct hands: an early hand for events 1848–1880, a later hand for events 1881–1932. The earliest entries appear to have been copied into this Bible from an earlier family record after the Bible's purchase.","srn":"Grund Family Bible, family page 2, Per Larsson Grund birth entry."},"confidence":"High","citations":[]},"B.4 Funeral program":{"expected":{"title":"Funeral program, Thomas Emil Siggerud","abbrev":"Siggerud funeral program 1953","author":"Helgeson Funeral Home","pubinfo":"Williams, Minnesota: Helgeson Funeral Home, 16 February 1953.","page":"Thomas Emil Siggerud funeral program","frn":"Helgeson Funeral Home, \"In Memory of Thomas Emil Siggerud,\" funeral program for services held 16 February 1953 at Lutheran Church, Williams, Minnesota; Rev. Edstrom officiating; burial at Pine Hill Cemetery, Williams, Minnesota; privately held by Peter Grund, Duluth, Minnesota.","srn":"Siggerud funeral program 1953."},"confidence":"High","citations":[]},"B.4 Photograph":{"expected":{"title":"Per Larsson Grund cabinet card, ca. 1890s","abbrev":"Grund cabinet card 1890s","author":"","page":"cabinet card front, Per Larsson Grund portrait; inscription on mount, \"Grandma's Grandpa\"","frn":"Per Larsson Grund cabinet card portrait, ca. 1890s, taken at Miller Studio, St. Cloud, Minnesota; inscription on top of mount in cursive: \"Grandma's Grandpa\"; printed studio mark on bottom of mount: \"Miller\" (with M-M monogram), \"ST. CLOUD, MINN.\"; privately held by Peter Grund, Duluth, Minnesota. Subject identification is family attribution by inscription rather than caption with full name.","srn":"Per Larsson Grund cabinet card, ca. 1890s."},"confidence":"High","citations":[]},"B.4 Audio interview":{"expected":{"title":"Tom Grund interview by Peter Grund, 12 March 2024","abbrev":"Tom Grund interview 2024-03-12","author":"Tom Grund","pubinfo":"Recorded interview, Duluth, Minnesota, 12 March 2024.","page":"minute 23:15, Edmund Gene Grund's military service in WWII","frn":"Tom Grund (Duluth, Minnesota), recorded interview by Peter Grund, 12 March 2024; audio recording and transcript privately held by Peter Grund, [ADDRESS FOR PRIVATE USE,] Duluth, Minnesota; minute 23:15, on Edmund Gene Grund's WWII service. Tom is a son of Edmund Gene Grund and reports here on events he learned of from his parents (he was born after the war).","srn":"Tom Grund interview, 12 March 2024, minute 23:15."},"confidence":"Normal","citations":[]},"B.4 Personal research":{"expected":{"title":"Personal research of Siw Alfreddson, Ambjörby, Sweden","abbrev":"Alfreddson research","author":"Siw Alfreddson","pubinfo":"Unpublished research, Ambjörby, Sweden, 2024–2026.","page":"Ambmyra typed page, received 30 April 2026","frn":"Siw Alfreddson, personal research on the Grund family of Ambjörby, Sweden, accumulated 2024–2026, typed page on Ambmyra torpare holdings, received by Peter Grund via email 30 April 2026; privately held by Siw Alfreddson, Ambjörby, Sweden, with copies privately held by Peter Grund, Duluth, Minnesota. Siw's notes cite Norra Ny kyrkoarkiv volumes for each fact she records; for facts she draws from those primary records, the underlying primary record should also be cited directly when used in narrative.","srn":"Alfreddson research, Ambmyra typed page, received 30 April 2026."},"confidence":"Normal","citations":[]},"B.4 Published book":{"expected":{"title":"Eidsvoll Bygds Historie: Gardene på vestside av Vorma","abbrev":"Eidsvoll bygdebok 2:2","author":"Birger Kirkeby","pubinfo":"Vol. 2, pt. 2. Oslo: Eidsvoll Bygdebokkomite, 1959.","page":"pp. 432–440, Vinger gård entry","frn":"Birger Kirkeby, Eidsvoll Bygds Historie: Gardene på vestside av Vorma [Eidsvoll Parish History: The Farms on the West Side of the Vorma River], vol. 2, pt. 2 (Oslo: Eidsvoll Bygdebokkomite, 1959), pp. 432–440, \"Vinger gård.\"","srn":"Kirkeby, Eidsvoll bygdebok 2:2, pp. 432–440."},"confidence":"Normal","citations":[]},"B.4 Membership directory":{"expected":{"title":"Medlemmer av Den norske sakførerforening 1. juli 1950","abbrev":"Sakførerforening medlemmer 1950","author":"Den norske sakførerforening","pubinfo":"Oslo: Den norske sakførerforening, 1951. Digital images, Nasjonalbiblioteket (https://www.nb.no).","page":"p. 440 (image 443), Frithjof Siggerud directory entry","frn":"Den norske sakførerforening, Medlemmer av Den norske sakførerforening 1. juli 1950 [Members of the Norwegian Bar Association as of 1 July 1950] (Oslo: Den norske sakførerforening, 1951), p. 440, entry for Frithjof Siggerud; digital image, Nasjonalbiblioteket (https://www.nb.no/items/b3f9413b2125c7f26063abb8896d95bf?page=443 : accessed 26 April 2026).","srn":"Sakførerforening medlemmer 1950, p. 440, Frithjof Siggerud."},"confidence":"Normal","citations":[]},"B.4 School enrollment register":{"expected":{"title":"Elever ved Kristiania katedralskole som begynte på skolen i årene 1891–1901, hefte 8","abbrev":"Kristiania katedralskole 1891–1901","author":"Anders Langangen","pubinfo":"[Place]: [Publisher], [year]. Digital images, Nasjonalbiblioteket (https://www.nb.no).","page":"p. 112 (image 111), entry no. 498, Erling Frithjof Siggerud register entry","frn":"Anders Langangen, Elever ved Kristiania katedralskole som begynte på skolen i årene 1891–1901, hefte 8 [Pupils at Kristiania Cathedral School Who Began in the Years 1891–1901, Booklet 8] ([Place]: [Publisher], [year]), p. 112, entry no. 498, Erling Frithjof Siggerud; digital image, Nasjonalbiblioteket (https://www.nb.no : accessed 26 April 2026).","srn":"Langangen, Kristiania katedralskole 1891–1901, p. 112, no. 498, Erling Frithjof Siggerud."},"confidence":"Normal","citations":[]},"B.4 Online video":{"expected":{"title":"Norra Ny parish history walking tour","abbrev":"Norra Ny walking tour","author":"Värmland Local History Channel","pubinfo":"Online video, YouTube (https://www.youtube.com), 2025.","page":"minute 12:30–14:15, Ambjörby torpare landscape","frn":"Värmland Local History Channel, \"Norra Ny parish history walking tour,\" YouTube video (https://www.youtube.com/watch?v=[ID] : accessed 9 May 2026), minute 12:30–14:15, on the Ambjörby torpare landscape.","srn":"Värmland History YouTube, \"Norra Ny walking tour,\" minute 12:30–14:15."},"confidence":"Low","citations":[]}}};
