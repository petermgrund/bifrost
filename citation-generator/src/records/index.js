// Every record type, in sidebar order: the shipped ones, and the registry every lookup reads, which Bifrost's
// saved edits replace (setRecords).
import { NORWEGIAN } from './norwegian.js';
import { SWEDISH } from './swedish.js';
import { US } from './us.js';
import { PUBLISHED } from './published.js';
import { GENERAL } from './general.js';

export const SHIPPED = [...NORWEGIAN, ...SWEDISH, ...US, ...PUBLISHED, ...GENERAL];
export const RECORDS = [...SHIPPED];

export function recordById(id) {
  return RECORDS.find(r => r.id === id) || null;
}

/** Makes every lookup see these record types. */
export function setRecords(list) {
  RECORDS.splice(0, RECORDS.length, ...list);
}
