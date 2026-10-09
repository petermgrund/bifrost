// Rule checks shown in the status bar. Each returns { rule, message } problems.
import { plain, hasGap } from './template.js';

const RAW_IMAGE_ID = /\b(kb|ft|pf)\d{8,}|\bC\d{7}_\d{3,}|\bFolk_\d+-\d+|\bv\d{4,}\.b\d+/;
const USPS = /(^|[\s,(])(AL|AK|AZ|AR|CA|CO|CT|DE|FL|GA|HI|ID|IL|IN|IA|KS|KY|LA|ME|MD|MA|MI|MN|MS|MO|MT|NE|NV|NH|NJ|NM|NY|NC|ND|OH|OK|OR|PA|RI|SC|SD|TN|TX|UT|VT|VA|WA|WV|WI|WY)([\s,.)]|$)/;
const FIELD_NAMES = {
  title: 'Title', abbrev: 'Abbrev', author: 'Author', pubinfo: 'Pubinfo', page: 'Page', frn: 'FRN', srn: 'SRN',
  plTitle: 'Paperless title', plCorrespondent: 'Correspondent', plSourceUrl: 'Source URL',
};
const escapeRe = s => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');

export function runChecks(type, draft, outputs) {
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
