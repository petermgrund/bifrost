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

export function templateKeys(template) {
  return [...String(template ?? '').matchAll(/\{(\w+)\}/g)].map(m => m[1]);
}

export function fill(template, values, labelOf = key => key) {
  if (!template) return '';
  const kept = template.replace(/«([^»]*)»/g, (_, inner) =>
    templateKeys(inner).some(k => isBlank(values[k])) ? '' : inner);
  return kept.replace(/\{(\w+)\}/g, (_, k) => isBlank(values[k]) ? gap(labelOf(k)) : String(values[k]));
}
