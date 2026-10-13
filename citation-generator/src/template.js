import { stateAbbrev } from './tables.js';

// Template filling. {key} inserts a value; «…» is dropped when any key inside it is blank.
// A blank required value becomes a gap marker ⟦Label⟧: highlighted on screen, copied as [Label].
export const GAP_OPEN = '⟦';
export const GAP_CLOSE = '⟧';
const GAP_RE = /⟦([^⟧]*)⟧/g;

export function isBlank(value) {
  return value === undefined || value === null || String(value).trim() === '';
}

export function gap(label) {
  return GAP_OPEN + label + GAP_CLOSE;
}

export function hasGap(text) {
  return String(text ?? '').includes(GAP_OPEN);
}

export function plain(text) {
  return String(text ?? '').replace(GAP_RE, '[$1]');
}

export function gapLabels(text) {
  return [...String(text ?? '').matchAll(GAP_RE)].map(m => m[1]);
}

const TOKEN_RE = /\{(\w+)(?:\|(\w+))?\}/g;

// Helpers a template can apply to a value: {author|last}, {date|year}, {state|abbrev}, {title|first}, {noun|lower}.
export const FILTERS = {
  last: v => String(v).trim().split(/\s+/).pop(),
  first: v => String(v).split(',')[0].trim(),
  year: v => (String(v).match(/\d{4}/) || [''])[0],
  lower: v => String(v).toLowerCase(),
  abbrev: v => stateAbbrev(v),
};

export function templateKeys(template) {
  return [...String(template ?? '').matchAll(TOKEN_RE)].map(m => m[1]);
}

export function fill(template, values, labelOf = key => key) {
  if (!template) return '';
  const value = (key, filter) => {
    const v = values[key];
    return isBlank(v) || !FILTERS[filter] ? v : FILTERS[filter](v);
  };
  const kept = template.replace(/«([^»]*)»/g, (_, inner) =>
    [...inner.matchAll(TOKEN_RE)].some(m => isBlank(value(m[1], m[2]))) ? '' : inner);
  return kept.replace(TOKEN_RE, (_, k, f) => {
    const v = value(k, f);
    return isBlank(v) ? gap(labelOf(k)) : String(v);
  });
}
