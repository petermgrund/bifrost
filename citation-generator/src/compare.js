// Compares generator output with a worked example from the guide.
import { plain } from './template.js';

export const COMPARED_FIELDS = ['title', 'abbrev', 'author', 'pubinfo', 'callNumber', 'page', 'frn', 'srn'];

/** The guide's expected values for one claim: the whole example, or one citation of a multi-citation example. */
export function expectedFor(example, claim) {
  if (claim.citation) {
    const c = example.citations[claim.citation - 1] || {};
    const fields = {};
    for (const key of ['page', 'frn', 'srn']) if (c[key] !== undefined) fields[key] = c[key];
    return { fields, confidence: c.confidence || '' };
  }
  return { fields: example.expected, confidence: example.confidence };
}

/** Fields whose output differs from the guide. */
export function diffOutputs(expectedFields, outputs) {
  return COMPARED_FIELDS
    .filter(field => field in expectedFields && expectedFields[field] !== plain(outputs[field]))
    .map(field => ({ field, want: expectedFields[field], got: plain(outputs[field]) }));
}
