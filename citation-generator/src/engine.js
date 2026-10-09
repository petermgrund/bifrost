// Turns one draft of one record type into every output field.
import { fill, gap } from './template.js';
import { DATE_MEANING, CHAPTER_CODE, PLATFORMS, MEDIA, yearOf } from './tables.js';

// Reference-note values that describe the Source, pre-filled from the record type's defaults.
export const REFERENCE_VALUES = ['platform', 'pubmedium', 'archive', 'custodian', 'custplace'];
export const STANDARD_VALUES = ['url', 'accessed', 'eventYear', 'details', 'comment', 'citedFor', ...REFERENCE_VALUES];
export const SUBJECT_KEYS = ['name', 'noun', 'copy', 'nonHead', 'head', 'which', 'says', 'evidence', 'afterNoun'];
export const ENGINE_TOKENS = ['name', 'noun', 'subject', 'srnSubject', 'entryof', 'medium', 'home', 'author', 'pageLoc', 'pageRef'];
export const TEMPLATE_KEYS = ['title', 'abbrev', 'author', 'pubinfo', 'page', 'frn', 'frnMicrofilm', 'srn', 'paperlessTitle'];

// Output fields in Gramps order, grouped as on screen. '§N' resolves to the record's chapter.
export const OUTPUT_GROUPS = [
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

export function ruleRef(type, rule) {
  return rule.startsWith('§') ? `${CHAPTER_CODE[type.chapter]} ${rule}` : rule;
}

/** The record type with the draft's page variant merged in. */
export function resolveType(type, draft) {
  if (!type.pageVariants) return type;
  const variant = type.pageVariants.find(v => v.key === draft?.variant) || type.pageVariants[0];
  return { ...type, ...variant };
}

/** Every input field the record type can show: [key, label, placeholder]. */
export function inputFields(type) {
  const fromVariants = (type.pageVariants || []).flatMap(v => v.citation || []);
  const seen = new Set();
  return [...type.source, ...(type.citation || []), ...fromVariants, ...(type.note || [])]
    .filter(([key]) => !seen.has(key) && seen.add(key));
}

export function labeler(type) {
  const labels = Object.fromEntries(inputFields(type).map(([key, label]) => [key, label]));
  if (type.eventYearLabel) labels.eventYear = type.eventYearLabel;
  if (type.detailsLabel) labels.details = type.detailsLabel;
  return key => labels[key] || STANDARD_LABELS[key] || key;
}

/** Whether any of the record type's templates (or only those named), including its page variants, uses {key}. */
export function usesToken(type, key, keys = TEMPLATE_KEYS) {
  const templates = [type, ...(type.pageVariants || [])].flatMap(t => keys.map(k => t[k] || ''));
  return templates.some(t => t.includes(`{${key}}`));
}

export function usesDetails(type) {
  return Boolean(type.detailsLabel) || usesToken(type, 'details');
}

export function newDraft(type) {
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
export function setVariant(type, draft, key) {
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
export function nextCitationDraft(type, draft) {
  const fresh = newDraft(type);
  const keep = [...type.source.map(([key]) => key), ...REFERENCE_VALUES];
  const values = { ...fresh.values };
  for (const key of keep) if (Object.hasOwn(draft.values, key)) values[key] = draft.values[key];
  const sourceFields = OUTPUT_GROUPS[0].fields.map(([key]) => key);
  const overrides = Object.fromEntries(Object.entries(draft.overrides).filter(([key]) => sourceFields.includes(key)));
  const subject = { ...fresh.subject, noun: (resolveType(type, draft).nouns || [''])[0] || '' };
  return { ...draft, values, subject, confidence: fresh.confidence, overrides, example: '' };
}

export function exampleLabel(claim) {
  return claim.citation ? `${claim.guide} · citation ${claim.citation}` : claim.guide;
}

export function draftFromExample(type, claim) {
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
export function recordNoun(noun, copy) {
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
export function subjectOf(type, subject) {
  return subjectWith(type, subject, [subject.which, subject.says, subject.evidence]);
}

/** The SRN's subject (B.1 §10): the page string's subject keeping only the which-entry disambiguator. */
export function srnSubjectOf(type, subject) {
  return subjectWith(type, subject, [subject.which]);
}

/**
 * Page locators built from the typed page and image: pageLoc is for the page string, pageRef for
 * the FRN and SRN. With no page number, the image number stands in ("image 62", lower case).
 */
export function pageLocators(page, image) {
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
export function endWith(text, citedFor) {
  if (!citedFor) return text;
  if (text.endsWith('."')) return `${text.slice(0, -2)}" (${citedFor}).`;
  if (text.endsWith('.')) return `${text.slice(0, -1)} (${citedFor}).`;
  return `${text} (${citedFor})`;
}

export function buildOutputs(type, draft) {
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
