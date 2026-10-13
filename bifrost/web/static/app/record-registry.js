import { api } from './core.js';
import { SHIPPED, applyEdits, setRecords } from '/static/citations/citations.js';

/** Lays the record types saved in Bifrost over the shipped ones, in the registry every lookup reads. */
export async function loadRecordTypes() {
  const { types } = await api('/citations/api/types');
  setRecords(applyEdits(SHIPPED, types));
  return types;
}
