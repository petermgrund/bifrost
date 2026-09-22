import { mdiMapMarker, mdiMapMarkerOff, mdiMapMarkerOutline } from '@mdi/js';

export const MODIFIER = [
  { value: 'regular', label: 'Regular' },
  { value: 'about', label: 'About' },
  { value: 'before', label: 'Before' },
  { value: 'after', label: 'After' },
];
export const QUALITY = [
  { value: 'regular', label: 'Regular' },
  { value: 'estimated', label: 'Estimated' },
  { value: 'calculated', label: 'Calculated' },
];
export const MONTHS = [
  'January', 'February', 'March', 'April', 'May', 'June',
  'July', 'August', 'September', 'October', 'November', 'December',
];
export const MONTH_OPTIONS = [{ value: '0', label: '—' }, ...MONTHS.map((label, i) => ({ value: String(i + 1), label }))];

export const plural = (n, word) => `${n} ${word}${n === 1 ? '' : 's'}`;

export function dateParts(d) {
  return {
    year: d ? d.value.slice(0, 4) : '',
    month: d && d.precision !== 'year' ? String(Number(d.value.slice(5, 7))) : '0',
    day: d && d.precision === 'exact' ? String(Number(d.value.slice(8, 10))) : '',
    modifier: d?.modifier || 'regular',
    quality: d?.quality || 'regular',
  };
}

export function dateProblem(p) {
  const year = p.year.trim();
  const day = p.day.trim();
  if (!year) return day || p.month !== '0' ? 'Add a year' : '';
  if (!/^\d{4}$/.test(year) || +year < 1) return 'The year needs four digits';
  if (!day) return '';
  const last = new Date(+year, +p.month, 0).getDate();
  if (!/^\d{1,2}$/.test(day) || +day < 1 || +day > last) return `${MONTHS[+p.month - 1]} ${year} has no day ${day}`;
  return '';
}

export function dateOf(p) {
  const year = p.year.trim();
  if (!year || dateProblem(p)) return null;
  const month = +p.month;
  const day = month && p.modifier !== 'about' ? +(p.day.trim() || 0) : 0;
  const pad = (n) => String(n || 1).padStart(2, '0');
  return {
    value: `${year}-${pad(month)}-${pad(day)}`,
    precision: day ? 'exact' : month ? 'month' : 'year',
    modifier: p.modifier,
    quality: p.quality,
  };
}

export function grampsDate(d) {
  if (!d) return '';
  const [y, m] = d.value.split('-');
  const date = d.precision === 'year' ? y : d.precision === 'month' ? `${y}-${m}` : d.value;
  const mod = { before: 'Before ', after: 'After ', about: 'About ' }[d.modifier] || '';
  const qual = { estimated: 'Est. ', calculated: 'Calc. ' }[d.quality] || '';
  return `${qual}${mod}${date}`;
}

export function sizeText(m) {
  const dims = m.width ? `${m.width}×${m.height}` : '';
  const kb = m.size / 1024;
  const bytes = !m.size ? '' : kb < 1024 ? `${Math.max(1, Math.round(kb))} KB` : `${(kb / 1024).toFixed(1)} MB`;
  return [dims, bytes].filter(Boolean).join(' · ');
}

export function placeItem(p) {
  const parents = (p.hierarchy || []).slice(1).join(', ');
  return {
    id: p.gramps_id,
    label: p.name || p.gramps_id,
    sub: [parents, p.gramps_id].filter(Boolean).join(' · '),
    icon: p.known === false ? mdiMapMarkerOff : p.tagged ? mdiMapMarker : mdiMapMarkerOutline,
  };
}

export function formFrom(rec, suggest = true) {
  const fresh = suggest && !rec.sync.media && !rec.gramps;
  return {
    title: rec.title || '',
    date: dateParts(rec.date),
    place: rec.place ? placeItem(rec.place) : null,
    notes: rec.notes || '',
    sync: fresh
      ? { media: true, title: true, date: true, note: false }
      : { media: rec.sync.media, title: rec.sync.title, date: rec.sync.date, note: rec.sync.note },
  };
}

export function savedForm(rec) {
  return { ...formFrom(rec, false), date: dateParts(rec.tagged_date) };
}

export function formKey(f) {
  const d = f.date;
  const date = [d.year.trim(), d.month, d.day.trim(), d.modifier, d.quality];
  return JSON.stringify([f.title.trim(), f.notes.trim(), f.place?.id || null, date, f.sync]);
}

export function payload(f) {
  const date = dateOf(f.date);
  return {
    title: f.title,
    notes: f.notes,
    place_gramps_id: f.place?.id || null,
    date,
    sync: { ...f.sync, date: !!date && f.sync.date },
  };
}

export function cardFrom(rec) {
  return {
    asset_id: rec.asset_id,
    filename: rec.filename,
    title: rec.title,
    type: rec.type,
    thumb: rec.thumb,
    gramps_id: rec.gramps?.gramps_id || null,
    versions: rec.versions?.members?.length || 1,
    is_child: false,
    missing: false,
  };
}

export function assetItem(card) {
  return {
    id: card.asset_id,
    label: card.title || card.filename,
    sub: [card.title && card.filename, card.gramps_id].filter(Boolean).join(' · '),
    thumb: card.thumb,
  };
}
