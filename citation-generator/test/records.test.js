import { test } from 'node:test';
import assert from 'node:assert/strict';
import { RECORDS } from '../src/records/index.js';
import { inputFields, resolveType, usesToken, ENGINE_TOKENS, STANDARD_VALUES, REFERENCE_VALUES, TEMPLATE_KEYS, SUBJECT_KEYS } from '../src/engine.js';
import { templateKeys } from '../src/template.js';
import { CHAPTERS, LEVELS, DATE_MEANING } from '../src/tables.js';

test('record type ids are unique', () => {
  const ids = RECORDS.map(r => r.id);
  assert.deepEqual(ids.filter((id, i) => ids.indexOf(id) !== i), []);
});

for (const r of RECORDS) {
  const variants = r.pageVariants || [null];
  const derived = Object.keys(r.derive ? r.derive({ name: '', noun: '' }) : {});

  test(`${r.id}: required parts`, () => {
    assert.ok(CHAPTERS[r.chapter], 'unknown chapter');
    assert.ok(r.name && r.group, 'name and group');
    assert.ok(Array.isArray(r.source) && Array.isArray(r.nouns) && r.nouns.length, 'source and nouns');
    assert.ok(LEVELS.includes(r.confidence) || r.confidence === '', `confidence "${r.confidence}"`);
    assert.ok(r.doctype in DATE_MEANING, `document type "${r.doctype}"`);
    assert.equal(typeof r.title, 'string');
    assert.equal('holder' in r, false, 'holder settings were replaced by defaults');
    for (const key of Object.keys(r.defaults || {})) {
      assert.ok(REFERENCE_VALUES.includes(key), `default "${key}"`);
      // Platform also feeds the Paperless correspondent, and the engine builds a genealogical Pubinfo from
      // platform and medium when the record type has no Pubinfo template; every other default must reach a template.
      if (key === 'pubmedium') assert.ok(r.pubinfo === undefined || usesToken(r, key), 'default "pubmedium" is not used by the Pubinfo');
      else if (key !== 'platform') assert.ok(usesToken(r, key), `default "${key}" is not used by any template`);
    }
    for (const v of variants) {
      const t = resolveType(r, v ? { variant: v.key } : {});
      for (const key of ['page', 'frn', 'srn']) assert.equal(typeof t[key], 'string', `${v ? v.key + ': ' : ''}${key}`);
    }
    for (const field of Object.keys(r.pins || {})) assert.ok(field !== 'repository', `pin for ${field}`);
  });

  test(`${r.id}: input and derived names do not clash with engine names`, () => {
    for (const [key] of inputFields(r)) {
      assert.ok(!ENGINE_TOKENS.includes(key) && !STANDARD_VALUES.includes(key), `input "${key}"`);
    }
    for (const key of derived) assert.ok(!ENGINE_TOKENS.includes(key), `derived "${key}"`);
  });

  test(`${r.id}: every {token} in its templates is defined`, () => {
    const known = new Set([...inputFields(r).map(([key]) => key), ...STANDARD_VALUES, ...ENGINE_TOKENS, ...derived]);
    for (const t of [r, ...(r.pageVariants || [])]) {
      for (const key of TEMPLATE_KEYS) {
        for (const token of templateKeys(t[key])) assert.ok(known.has(token), `${key} uses unknown {${token}}`);
      }
    }
  });

  test(`${r.id}: every input field is used by a template or by derive`, () => {
    const templates = [r, ...(r.pageVariants || [])].flatMap(t => TEMPLATE_KEYS.map(key => t[key] || '')).join('\n');
    const derive = r.derive ? r.derive.toString() : '';
    // The engine reads two kinds of input itself: `call` is the Call number, and `page` and
    // `image` build the {pageLoc} and {pageRef} tokens.
    const readByEngine = key => key === 'call'
      || (['page', 'image'].includes(key) && ['{pageLoc}', '{pageRef}'].some(token => templates.includes(token)));
    for (const [key] of inputFields(r)) {
      const used = templates.includes(`{${key}}`) || new RegExp(`\\bv\\.${key}\\b`).test(derive) || readByEngine(key);
      assert.ok(used, `input "${key}" is not used by any template or by derive`);
    }
  });

  test(`${r.id}: page forms offer only nouns the record type lists, and examples use them`, () => {
    for (const v of r.pageVariants || []) {
      for (const noun of v.nouns || []) assert.ok(r.nouns.includes(noun), `${v.key}: "${noun}" is not in the record type's nouns`);
    }
    for (const claim of r.examples) {
      const nouns = resolveType(r, { variant: claim.inputs.variant }).nouns;
      assert.ok(nouns.includes(claim.inputs.noun ?? nouns[0]), `${claim.guide}: noun "${claim.inputs.noun}" is not offered for this form`);
    }
  });

  test(`${r.id}: a form's own date (eventDate) is one of that form's inputs`, () => {
    for (const v of variants) {
      const t = resolveType(r, v ? { variant: v.key } : {});
      if (!t.eventDate) continue;
      const fields = [...r.source, ...(t.citation || []), ...(r.note || [])].map(([key]) => key);
      assert.ok(fields.includes(t.eventDate), `${v ? v.key + ': ' : ''}eventDate "${t.eventDate}" is not an input of this form`);
    }
  });

  test(`${r.id}: example inputs name real fields`, () => {
    const known = new Set([...inputFields(r).map(([key]) => key), ...STANDARD_VALUES, ...SUBJECT_KEYS, 'confidence', 'variant']);
    for (const claim of r.examples) {
      for (const key of Object.keys(claim.inputs)) assert.ok(known.has(key), `${claim.guide}: unknown input "${key}"`);
    }
  });
}
