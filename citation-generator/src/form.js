// Describes what each wizard step asks for and shows, as plain rows the screen draws.
import { CHAPTERS, LEVELS, PLATFORMS, ARCHIVES, SUGGESTIONS, COPY_FORMS, MEDIA } from './tables.js';
import { OUTPUT_GROUPS, TEMPLATE_KEYS, resolveType, usesDetails, usesToken, ruleRef, exampleLabel } from './engine.js';
import { expectedFor, diffOutputs } from './compare.js';
import { plain } from './template.js';

export const EDITABLE = ['title', 'author', 'abbrev', 'pubinfo', 'callNumber', 'page', 'frn', 'srn',
  'plTitle', 'plDoctype', 'plDateMeaning', 'plCorrespondent', 'plSourceUrl'];
const MONO_KEYS = ['call', 'url', 'turl'];
const FIELD_NAMES = { title: 'Title', abbrev: 'Abbrev', author: 'Author', pubinfo: 'Pubinfo', callNumber: 'Call number', page: 'Page', frn: 'FRN', srn: 'SRN' };

const text = (path, label, value, extra = {}) => ({ path, label, kind: 'text', value: value ?? '', placeholder: '', ...extra });
const area = (path, label, value, placeholder = '') => ({ path, label, kind: 'area', value: value ?? '', placeholder });
const select = (path, label, value, options) => ({ path, label, kind: 'select', value: value ?? '', options });
const check = (path, label, value) => ({ path, label, kind: 'check', value: Boolean(value) });
const capital = word => word[0].toUpperCase() + word.slice(1);

/** The value the record type's worked examples give a key, shown as an example of what goes there. */
export function sampleOf(type, key) {
  for (const claim of type.examples || []) {
    const value = claim.inputs?.[key];
    if (typeof value === 'string' && value.trim()) return value.trim();
  }
  return '';
}

const field = (type, [key, label, placeholder], values) =>
  text(`values.${key}`, label, values[key], { placeholder: placeholder || sampleOf(type, key), mono: MONO_KEYS.includes(key) });

/** Record types by chapter, filtered by name or group. */
export function recordGroups(records, filter = '') {
  const q = filter.trim().toLowerCase();
  return Object.entries(CHAPTERS)
    .map(([code, label]) => ({ code, label, records: records.filter(r => r.chapter === code && (!q || `${r.name} ${r.group}`.toLowerCase().includes(q))) }))
    .filter(g => g.records.length);
}

/** The Source inputs, in the order the record type lists them. */
export function sourceRows(type, draft) {
  return type.source.map(f => field(type, f, draft.values));
}

/**
 * The reference values that describe the Source. The medium opens a genealogical record's Pubinfo (A10), with
 * Microfilm only where the record type can cite the film itself; Archive shows where an FRN names it (a newspaper
 * names it only on film); Held by and Place only where a template says "privately held by".
 */
export function referenceRows(type, draft) {
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
export function citationRows(type, draft) {
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
export function noteRows(type, draft) {
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
export function outputRows(type, draft, outputs) {
  return OUTPUT_GROUPS.map(g => ({
    name: g.name,
    rows: g.fields.map(([key, label, rule]) => ({
      key, label, ref: ruleRef(type, rule), value: outputs[key] ?? '', text: plain(outputs[key] ?? ''),
      edited: Object.hasOwn(draft.overrides, key), editable: EDITABLE.includes(key),
    })),
  }));
}

/** Whether the outputs still match the guide's worked example the draft was loaded from. */
export function exampleNote(type, draft, outputs, guide) {
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
export function repositoryName(type, draft) {
  const v = draft.values;
  const archive = String(v.archive ?? '').trim(), custodian = String(v.custodian ?? '').trim();
  if (archive && usesToken(type, 'archive', TEMPLATE_KEYS.filter(k => k !== 'frnMicrofilm'))) return archive;
  if (custodian && usesToken(type, 'custodian')) return `${custodian}, private collection`;
  return '';
}

const nameKey = name => String(name ?? '').toLowerCase().replace(/\.com\b/g, '').replace(/[^\p{L}\p{N}]+/gu, ' ').trim();

/** The id of the Paperless row named like the value (Ancestry → Ancestry.com, immigration → Immigration/naturalization), or null. */
export function paperlessMatch(value, rows) {
  const want = nameKey(value);
  if (!want) return null;
  const keyed = rows.map(r => [r.id, nameKey(r.name)]);
  const hit = keyed.find(([, k]) => k === want) || keyed.find(([, k]) => k.startsWith(`${want} `));
  return hit ? hit[0] : null;
}

export function copyAllText(o) {
  const p = x => plain(x ?? '');
  return [
    'SOURCE', `Title: ${p(o.title)}`, `Author: ${p(o.author)}`, `Abbrev: ${p(o.abbrev)}`, `Pubinfo: ${p(o.pubinfo)}`, `Call number: ${p(o.callNumber)}`, '',
    'CITATION', `Page: ${p(o.page)}`, `Confidence: ${o.confidence || ''}`, '',
    'FIRST REFERENCE NOTE:', p(o.frn), '', 'SHORT REFERENCE NOTE:', p(o.srn),
  ].join('\n');
}
