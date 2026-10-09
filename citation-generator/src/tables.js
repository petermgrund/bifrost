// Lookup tables shared by every record type. PLATFORMS and STATE_ABBREV are pinned to the
// guide's own tables (A10, B.3 §10) by test/tables.test.js.

export const CHAPTERS = { no: 'Norwegian', se: 'Swedish', us: 'US', pp: 'Published & personal' };
export const CHAPTER_CODE = { no: 'B.1', se: 'B.2', us: 'B.3', pp: 'B.4' };

export const LEVELS = ['Very High', 'High', 'Normal', 'Low', 'Very Low'];

// A10 · Platforms: homepage URLs.
export const PLATFORMS = {
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
export const STATE_ABBREV = {
  'Minnesota': 'Minn.', 'Wisconsin': 'Wis.', 'Iowa': 'Iowa', 'South Dakota': 'S. Dak.',
  'North Dakota': 'N. Dak.', 'New York': 'N.Y.', 'Massachusetts': 'Mass.', 'Connecticut': 'Conn.',
  'California': 'Cal.', 'Illinois': 'Ill.', 'Michigan': 'Mich.', 'Virginia': 'Va.', 'Pennsylvania': 'Pa.',
};

// Archive suggestions per chapter (each chapter's §3).
export const ARCHIVES = {
  no: ['Statsarkivet i Oslo', 'Statsarkivet i Hamar', 'Riksarkivet'],
  se: ['Värmlandsarkiv', 'Riksarkivet'],
  us: ['National Archives', 'Minnesota Historical Society', 'Swenson Swedish Immigration Research Center', 'Family History Library'],
  pp: ['Minnesota Historical Society', 'Library of Virginia'],
};

// A7 parenthetical suggestions per chapter (§9): 1 which entry, 2 source says, 3 evidence.
export const SUGGESTIONS = {
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
export const DATE_MEANING = {
  'vital record': 'event', 'enumeration': 'event', 'legal': 'event', 'immigration': 'event',
  'military': 'event', 'religious': 'event', 'correspondence': 'creation', 'ephemera': 'event',
  'publication': 'publication', 'artifact': 'creation', 'research': 'creation', 'interview': 'event',
};

// A10 · the medium that opens a genealogical record's Pubinfo; the first is the default. Microfilm is film
// read on a reader at a library or archive.
export const MEDIA = ['Digital images', 'Database with images', 'Database', 'Microfilm'];

// A7 · the forms a cited copy or index takes; an original has none ('').
export const COPY_FORMS = ['index entry', 'transcript', 'extract', 'abstract'];

const MONTHS = ['january', 'february', 'march', 'april', 'may', 'june', 'july', 'august', 'september', 'october', 'november', 'december'];

/** '14 March 1925' → '1925-03-14'; anything else → ''. */
export function isoDate(text) {
  const m = String(text ?? '').trim().match(/^(\d{1,2}) ([A-Za-z]+) (\d{4})$/);
  if (!m) return '';
  const month = MONTHS.indexOf(m[2].toLowerCase()) + 1;
  return month ? `${m[3]}-${String(month).padStart(2, '0')}-${m[1].padStart(2, '0')}` : '';
}

/** The first four-digit year in a date ('12 March 1897' → '1897'); '' when there is none. */
export function yearOf(text) {
  return (String(text ?? '').match(/\d{4}/) || [''])[0];
}

export function lastWord(text) {
  return String(text ?? '').trim().split(/\s+/).pop() || '';
}

export function allButLastWord(text) {
  return String(text ?? '').trim().split(/\s+/).slice(0, -1).join(' ');
}

export function stateAbbrev(state) {
  return STATE_ABBREV[String(state ?? '').trim()] || String(state ?? '').trim();
}
