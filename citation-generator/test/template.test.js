import { test } from 'node:test';
import assert from 'node:assert/strict';
import { fill, gap, plain, hasGap, gapLabels, isBlank, templateKeys } from '../src/template.js';

test('fill inserts values', () => {
  assert.equal(fill('{a}, {b}', { a: 'x', b: 'y' }), 'x, y');
});

test('a blank required value becomes a labelled gap', () => {
  assert.equal(fill('p. {page}', { page: '' }, key => ({ page: 'Page' })[key]), 'p. ⟦Page⟧');
});

test('an optional segment drops out when any value inside it is blank', () => {
  assert.equal(fill('p. {page}« (image {image})»', { page: '57', image: '' }), 'p. 57');
  assert.equal(fill('p. {page}« (image {image})»', { page: '57', image: '62' }), 'p. 57 (image 62)');
});

test('bracketed glosses are plain text', () => {
  assert.equal(fill('Kirkebøker [parish records], {vol}', { vol: 'I 2' }), 'Kirkebøker [parish records], I 2');
});

test('values keep their own spacing', () => {
  assert.equal(fill('{lead}{name}', { lead: 'entry for ', name: 'Ola' }), 'entry for Ola');
});

test('gap helpers', () => {
  assert.equal(gap('X'), '⟦X⟧');
  assert.equal(plain('p. ⟦Page⟧'), 'p. [Page]');
  assert.equal(hasGap('p. ⟦Page⟧'), true);
  assert.equal(hasGap('p. 57'), false);
  assert.deepEqual(gapLabels('⟦A⟧ and ⟦B⟧'), ['A', 'B']);
});

test('isBlank and templateKeys', () => {
  assert.equal(isBlank('  '), true);
  assert.equal(isBlank('0'), false);
  assert.deepEqual(templateKeys('{a}«, {b}»'), ['a', 'b']);
});
