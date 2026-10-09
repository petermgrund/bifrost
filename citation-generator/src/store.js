// Saves the work in progress in browser storage: the current record type and one draft per type.
import { newDraft, resolveType, usesDetails, OUTPUT_GROUPS } from './engine.js';
import { COPY_FORMS } from './tables.js';

export const STORE_KEY = 'gcCitationGenerator.v1';
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
export function loadState(storage, recordById) {
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

export function saveState(storage, state) {
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
