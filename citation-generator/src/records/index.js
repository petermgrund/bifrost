// Every record type, in sidebar order.
import { NORWEGIAN } from './norwegian.js';
import { SWEDISH } from './swedish.js';
import { US } from './us.js';
import { PUBLISHED } from './published.js';

export const RECORDS = [...NORWEGIAN, ...SWEDISH, ...US, ...PUBLISHED];

export function recordById(id) {
  return RECORDS.find(r => r.id === id) || null;
}
