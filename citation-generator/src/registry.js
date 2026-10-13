// Record types as Bifrost holds them: the shipped ones with the saved edits laid over them, and new ones made in
// Bifrost. An edit is plain data (no code): a built-in type keeps its computed values and guide pins.
import { GENERAL } from './records/general.js';
import { CHAPTERS } from './tables.js';
import { plain } from './template.js';
import { labeler, resolveType, draftFromExample, buildOutputs, usualCitedFor } from './engine.js';

export const DATA_KEYS = ['name', 'group', 'chapter', 'hint', 'source', 'citation', 'note', 'nouns', 'freeNoun', 'usual',
  'defaults', 'confidence', 'doctype', 'title', 'abbrev', 'author', 'pubinfo', 'page', 'frn', 'frnMicrofilm', 'srn',
  'paperlessTitle', 'subjectLabel', 'eventYearLabel', 'detailsLabel', 'eventDate', 'optionalSubject', 'media', 'sample', 'pageVariants', 'tag', 'base'];
export const VARIANT_KEYS = ['key', 'label', 'eventDate', 'citation', 'nouns', 'page', 'frn', 'frnMicrofilm', 'srn'];
export const TEMPLATE_FIELDS = [['title', 'Title'], ['abbrev', 'Abbrev'], ['author', 'Author'], ['pubinfo', 'Pubinfo'],
  ['page', 'Page'], ['frn', 'FRN'], ['frnMicrofilm', 'FRN on film'], ['srn', 'SRN'], ['paperlessTitle', 'Paperless title']];
export const VARIANT_TEMPLATES = ['page', 'frn', 'frnMicrofilm', 'srn'];

const copy = value => (value === undefined ? undefined : JSON.parse(JSON.stringify(value)));

/** The example inputs a type's preview starts from: its own sample, else its first worked example. */
export function sampleInputs(type) {
  return { ...(type.examples?.[0]?.inputs || {}), ...(type.sample || {}) };
}

/** The inputs a preview builds from: the type's example on the page form given, with a record noun that form lists. */
export function previewInputs(type, variant = '') {
  const inputs = { ...sampleInputs(type), ...(variant ? { variant } : {}) };
  const t = resolveType(type, { variant });
  const nouns = t.nouns || [''];
  if (!t.freeNoun && !nouns.includes(inputs.noun)) inputs.noun = nouns[0];
  return inputs;
}

/** What the editor shows and saves of a record type: its data, no code. A standard Pubinfo is null. */
export function toDefinition(type) {
  const out = {};
  for (const key of DATA_KEYS) {
    if (key === 'pageVariants') continue;
    if (type[key] !== undefined) out[key] = copy(type[key]);
  }
  if (!Object.hasOwn(type, 'pubinfo') || type.pubinfo === undefined) out.pubinfo = null;
  if (type.pageVariants) {
    out.pageVariants = type.pageVariants.map(v => Object.fromEntries(VARIANT_KEYS.filter(k => v[k] !== undefined).map(k => [k, copy(v[k])])));
  }
  out.sample = sampleInputs(type);
  return out;
}

function laid(base, definition) {
  const out = { ...base };
  for (const key of DATA_KEYS) {
    if (key === 'pageVariants' || !Object.hasOwn(definition, key)) continue;
    if (key === 'pubinfo' && definition.pubinfo === null) delete out.pubinfo;
    else out[key] = copy(definition[key]);
  }
  if (Array.isArray(definition.pageVariants)) {
    out.pageVariants = definition.pageVariants.map((v) => {
      const shipped = (base.pageVariants || []).find(s => s.key === v.key) || {};
      const merged = { ...shipped };
      for (const key of VARIANT_KEYS) if (Object.hasOwn(v, key)) merged[key] = copy(v[key]);
      return merged;
    });
  }
  return out;
}

/** A new record type of one's own, in the General form's shape (A14), with a General form citation's values as its example. */
export function blankDefinition(name = 'New record type', from = null) {
  const out = { ...toDefinition(GENERAL[0]), name, group: 'My record types', hint: '', usual: {}, sample: {} };
  delete out.tag;
  if (from) {
    const typed = Object.entries(from.values || {}).filter(([, v]) => typeof v === 'string' && v.trim());
    out.sample = { ...Object.fromEntries(typed), name: from.subject?.name || '', noun: from.subject?.noun || '' };
    if (out.sample.noun) {
      out.nouns = [out.sample.noun];
      out.freeNoun = false;
      if (out.sample.citedFor) out.usual = { [out.sample.noun]: out.sample.citedFor };
    }
  }
  return out;
}

/** A shipped type's computed values, for a copy of it; a copy whose fields no longer fit computes nothing. */
function derivedFrom(shipped, id) {
  const derive = shipped.find(t => t.id === id)?.derive;
  if (!derive) return undefined;
  return (values) => {
    try {
      return derive(values) || {};
    } catch {
      return {};
    }
  };
}

/**
 * The record types Bifrost holds: shipped ones with their edits laid over them (kind 'override'), new ones (kind
 * 'custom'), deleted ones left out. Each carries its version (0 when never edited).
 */
export function applyEdits(shipped, edits = []) {
  const byId = new Map(edits.map(e => [e.id, e]));
  const out = [];
  for (const type of shipped) {
    const edit = byId.get(type.id);
    if (edit?.deleted) continue;
    out.push(edit?.kind === 'override' ? { ...laid(type, edit.definition || {}), version: edit.version || 0, edited: true }
      : { ...type, version: edit?.version || 0 });
  }
  for (const edit of edits) {
    if (edit.kind !== 'custom' || edit.deleted || shipped.some(t => t.id === edit.id)) continue;
    const base = { id: edit.id, chapter: 'ge', group: 'My record types', nouns: [''], source: [], citation: [], note: [], examples: [] };
    const type = laid(base, edit.definition || {});
    const derive = derivedFrom(shipped, edit.definition?.base);
    if (derive) type.derive = derive;
    out.push({ ...type, id: edit.id, examples: [{ guide: 'Example', inputs: sampleInputs(type) }], version: edit.version || 0, custom: true });
  }
  return out;
}

/** A record type as it was at one saved version: the shipped type with that version's edit, or the edit alone. */
export function typeAtVersion(shipped, id, definition, kind) {
  const edits = definition ? [{ id, kind, definition, version: 0 }] : [];
  return applyEdits(shipped, edits).find(t => t.id === id) || null;
}

// What the values the wizard builds read as in the guide's notation.
const BUILT_FORMS = {
  pageLoc: 'p. [P] (image [I])', pageRef: 'p. [P]', subject: '[Subject] [record noun]', srnSubject: '[Subject] [record noun]',
  entryof: '[record noun] of [Name]', medium: 'digital image', name: '[Name]', noun: '[record noun]', home: '[homepage]',
};
const HELPER_NAMES = { last: 'last word', first: 'first part', year: 'year', lower: 'lower case', abbrev: 'abbreviated' };

/** A template in the guide's notation: each {token} as [Label], a helper named after it, optional parts unmarked. */
export function guideForm(type, template) {
  const L = labeler(type);
  return String(template ?? '').replace(/[«»]/g, '').replace(/\{(\w+)(?:\|(\w+))?\}/g, (_, key, helper) => {
    if (BUILT_FORMS[key] && !helper) return BUILT_FORMS[key];
    return `[${L(key)}${helper ? `, ${HELPER_NAMES[helper] || helper}` : ''}]`;
  });
}

/** The guide's record-type tables, by chapter, as Markdown: what Bifrost holds now. */
export function printout(types, date = '') {
  const row = cells => `| ${cells.map(c => String(c ?? '').replace(/\|/g, '\\|').replace(/\s*\n\s*/g, ' ')).join(' | ')} |`;
  const code = text => (String(text ?? '').trim() ? `\`${text}\`` : '');
  const table = (heads, rows) => [row(heads), row(heads.map(() => '---')), ...rows.map(row)].join('\n');
  const out = ['# Record types', ''];
  if (date) out.push(`Printed from Bifrost, ${date}.`, '');
  for (const [chapter, label] of Object.entries(CHAPTERS)) {
    const list = types.filter(t => (CHAPTERS[t.chapter] ? t.chapter : 'ge') === chapter);
    if (!list.length) continue;
    const forms = list.flatMap(type => (type.pageVariants?.length
      ? type.pageVariants.map(v => ({ type, variant: v.key, name: `${type.name} · ${v.label}` }))
      : [{ type, variant: '', name: type.name }]));
    for (const f of forms) {
      f.t = resolveType(f.type, { variant: f.variant });
      const o = buildOutputs(f.type, draftFromExample(f.type, { guide: 'Example', inputs: previewInputs(f.type, f.variant) }));
      const shown = Object.keys(sampleInputs(f.type)).length > 0;
      f.o = Object.fromEntries(Object.entries(o).map(([k, v]) => [k, shown && typeof v === 'string' ? plain(v) : '']));
    }
    const first = list.map(type => forms.find(f => f.type === type));
    const nouns = forms.flatMap(f => (f.t.freeNoun ? [[f.name, 'typed freely', usualCitedFor(f.t, { noun: '' })]]
      : (f.t.nouns || ['']).map((noun, i) => [i ? '' : f.name, noun || '(none)', usualCitedFor(f.t, { noun })])));
    out.push(`## ${label}`, '',
      '### Source title', '', table(['Record type', 'Title format', 'Example'], first.map(f => [f.type.name, code(guideForm(f.t, f.t.title)), code(f.o.title)])), '',
      '### Abbrev', '', table(['Record type', 'Abbrev', 'Example'], first.map(f => [f.type.name, code(guideForm(f.t, f.t.abbrev)), code(f.o.abbrev)])), '',
      '### Page-string templates', '', table(['Record type', 'Page string', 'Example'], forms.map(f => [f.name, f.t.page ? code(guideForm(f.t, f.t.page)) : 'none: only what it is cited for', code(f.o.page)])), '',
      '### Record nouns', '', table(['Record type', 'Record noun', 'Usual cited for'], nouns), '',
      '### Reference notes', '', table(['Record type', 'FRN', 'SRN'], forms.map(f => [f.name, code(guideForm(f.t, f.t.frn)), code(guideForm(f.t, f.t.srn))])), '');
  }
  return out.join('\n');
}
