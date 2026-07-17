/* Photos page: browse Immich assets, edit gda.date / gda.gramps metadata,
   pair recto/verso scans. Plain-DOM port of the former standalone urd app
   (not Lit — it predates the fold-in and works; everything else in app/ is
   Lit). Syncing to Gramps lives on the Sync section of the main page. */
'use strict';

const state = {
  vocab: null,
  albums: [],           // every Immich album, each with an `enabled` flag
  settingsDraft: null,  // Set of album ids being edited in the settings dialog
  page: 1,
  size: 60,
  nextPage: null,
  items: [],
  selectMode: false,
  selected: new Set(),
  current: null,   // asset id open in the editor (null in bulk mode)
  bulk: false,
  versoId: null,   // the open asset's linked verso, if any
  flipped: false,  // editor preview showing the verso side
  pairDraft: null, // {a, b, recto} while the pair dialog is open
  stackId: null,       // the open asset's stack, if any
  variants: [],        // [main, ...children] — cycled with the arrows
  variantId: null,     // stack variant being previewed (null = the main)
  total: null,         // total assets in the current view, when known
};

const el = (id) => document.getElementById(id);
const esc = (s) => String(s ?? '').replace(/[&<>"']/g,
  (c) => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[c]));

function snack(message) {
  el('snack-text').textContent = message;
  ui('#snack', 3000);
}

async function api(path, options = {}) {
  const resp = await fetch(path, {
    headers: {'Content-Type': 'application/json'},
    ...options,
  });
  if (!resp.ok) {
    let detail = resp.statusText;
    try { detail = (await resp.json()).detail || detail; } catch { /* keep statusText */ }
    throw new Error(detail);
  }
  return resp.json();
}

/* ---------- init ---------- */

async function init() {
  state.vocab = await api('/photos/api/config');

  fillSelect('d-quality', state.vocab.qualities.map((q) => [q, q]));
  fillSelect('d-modifier', state.vocab.modifiers.map((m) => [m, m]));
  const monthOpts = [['0', '—'], ...state.vocab.months.map((m, i) => [String(i + 1), m])];
  fillSelect('d-month', monthOpts);
  fillSelect('d-month2', monthOpts);

  // Bind before any Immich-backed fetch so one transient upstream error
  // can't leave the UI permanently inert.
  bindEvents();

  try {
    const [albums, people] = await Promise.all([api('/photos/api/albums'), api('/photos/api/people')]);
    state.albums = albums;
    populateAlbumDropdown();
    for (const p of people) addOption('f-person', p.id, p.name);
  } catch (err) {
    snack(`Filters unavailable: ${err.message}`);
  }
  ui();  // let BeerCSS re-sync field/label state after async population

  await loadAssets(1);
}

function fillSelect(id, pairs) {
  el(id).innerHTML = pairs
    .map(([v, label]) => `<option value="${esc(v)}">${esc(label)}</option>`)
    .join('');
}

function addOption(id, value, label) {
  const opt = document.createElement('option');
  opt.value = value;
  opt.textContent = label;
  el(id).appendChild(opt);
}

function populateAlbumDropdown() {
  const enabled = state.albums.filter((a) => a.enabled);
  const offered = enabled.length ? enabled : state.albums;
  const select = el('f-album');
  select.innerHTML = '';
  addOption('f-album', '', enabled.length ? 'All chosen albums' : 'All');
  for (const a of offered) addOption('f-album', a.id, `${a.name} (${a.count})`);
  select.value = '';
}

/* ---------- settings dialog ---------- */

function openSettings() {
  state.settingsDraft = new Set(state.albums.filter((a) => a.enabled).map((a) => a.id));
  el('set-filter').value = '';
  renderSettingsList();
  ui('#settings');
}

function renderSettingsList() {
  const needle = el('set-filter').value.trim().toLowerCase();
  const shown = needle
    ? state.albums.filter((a) => a.name.toLowerCase().includes(needle))
    : state.albums;
  el('set-list').innerHTML = shown.map((a) => `
    <div>
      <label class="checkbox">
        <input type="checkbox" data-id="${a.id}" ${state.settingsDraft.has(a.id) ? 'checked' : ''}>
        <span>${esc(a.name)} (${a.count})</span>
      </label>
    </div>`).join('');
  for (const box of el('set-list').querySelectorAll('input[type=checkbox]')) {
    box.addEventListener('change', () => {
      if (box.checked) state.settingsDraft.add(box.dataset.id);
      else state.settingsDraft.delete(box.dataset.id);
      syncSettingsCount();
    });
  }
  syncSettingsCount();
}

function syncSettingsCount() {
  const n = state.settingsDraft.size;
  el('set-count').textContent = n
    ? `${n} album${n === 1 ? '' : 's'} chosen`
    : 'Nothing chosen — every album is available';
}

async function saveSettings() {
  try {
    const res = await api('/photos/api/settings', {
      method: 'PUT',
      body: JSON.stringify({albumIds: [...state.settingsDraft]}),
    });
    const chosen = new Set(res.albumIds);
    for (const a of state.albums) a.enabled = chosen.has(a.id);
    populateAlbumDropdown();
    ui('#settings');
    snack(chosen.size ? `Photos now shows ${chosen.size} album${chosen.size === 1 ? '' : 's'}` : 'Album restriction removed');
    await loadAssets(1);
  } catch (err) {
    snack(`Save failed: ${err.message}`);
  }
}

/* ---------- browsing ---------- */

async function loadAssets(page) {
  const params = new URLSearchParams({
    page: String(page), size: String(state.size),
    order: el('f-order').value,
  });
  if (el('f-album').value) params.set('album', el('f-album').value);
  if (el('f-person').value) params.set('person', el('f-person').value);
  if (el('f-name').value.trim()) params.set('name', el('f-name').value.trim());
  try {
    const data = await api(`/photos/api/assets?${params}`);
    state.page = page;
    state.items = data.items;
    state.nextPage = data.nextPage;
    state.total = data.total;
    renderGrid();
  } catch (err) {
    snack(`Load failed: ${err.message}`);
  }
}

function visibleItems() {
  // Versos and stack children never render — the back of a photo lives
  // behind its recto's flip button, and a stack's variants behind its main
  // image. kvError assets are excluded from "undated": their metadata fetch
  // failed, so we don't know whether they carry a date.
  const items = state.items.filter(
    (a) => !a.pair?.recto && !(a.stack && !a.stack.primary));
  return el('f-undated').checked
    ? items.filter((a) => !a.date && !a.kvError)
    : items;
}

function dateChip(a) {
  if (a.kvError) {
    return `<a class="chip small error"><i>warning</i><span>metadata unavailable</span></a>`;
  }
  return a.date
    ? `<a class="chip small"><i>event</i><span class="truncate">${esc(a.date.display)}</span></a>`
    : `<a class="chip small" title="undated"><i>event_busy</i></a>`;
}

function scanChip(a) {
  return a.scan ? `<a class="chip small mono"><span class="truncate">${esc(a.scan.label)}</span></a>` : '';
}

function grampsChip(a) {
  return a.gramps?.gramps_id
    ? `<a class="chip small"><i>family_history</i><span class="truncate">${esc(a.gramps.gramps_id)}</span></a>`
    : '';
}

function chips(a) {
  return [
    dateChip(a),
    scanChip(a),
    grampsChip(a),
    a.pair?.verso ? `<a class="chip small" title="has a verso"><i>flip_to_front</i></a>` : '',
    a.stack ? `<a class="chip small" title="stack of ${a.stack.count} variants"><i>layers</i><span>${a.stack.count}</span></a>` : '',
  ].join('');
}

function renderGrid() {
  const items = visibleItems();
  el('grid').innerHTML = items.map((a) => `
    <div class="s6 m3 l2">
      <article class="no-padding thumb-cell ${state.selected.has(a.id) ? 'selected' : ''}" data-id="${a.id}">
        <img class="thumb" loading="lazy" src="/photos/thumb/${a.id}?size=thumbnail" alt="${esc(a.name)}">
        <i class="sel-mark">check_circle</i>
        <div class="thumb-chips row wrap tiny-space tiny-padding">
          ${chips(a)}
        </div>
      </article>
    </div>`).join('');

  // Total pages: exact for the merged whitelist view (server-counted), from
  // the album's asset count for a single-album view, unknown otherwise.
  let total = state.total;
  if (total == null && el('f-album').value && !el('f-name').value.trim() && !el('f-person').value) {
    total = state.albums.find((a) => a.id === el('f-album').value)?.count;
  }
  const pages = total != null ? Math.max(1, Math.ceil(total / state.size)) : null;
  el('page-label').textContent = pages ? `Page ${state.page} of ${pages}` : `Page ${state.page}`;
  el('btn-prev').disabled = state.page <= 1;
  el('btn-next').disabled = !state.nextPage;
  updateBulkbar();

  for (const cell of el('grid').querySelectorAll('.thumb-cell')) {
    cell.addEventListener('click', () => {
      const id = cell.dataset.id;
      if (state.selectMode) {
        toggleSelected(id, cell);
      } else {
        openEditor(id);
      }
    });
  }
}

function toggleSelected(id, cell) {
  if (state.selected.has(id)) state.selected.delete(id);
  else state.selected.add(id);
  cell.classList.toggle('selected', state.selected.has(id));
  updateBulkbar();
}

function updateBulkbar() {
  el('bulkbar').classList.toggle('hidden', !state.selectMode);
  el('bulk-count').textContent = `${state.selected.size} selected`;
  el('btn-bulk-date').disabled = state.selected.size === 0;
  el('btn-pair').disabled = state.selected.size !== 2;
  el('btn-stack').disabled = state.selected.size < 2;
}

/* ---------- editor ---------- */

async function openEditor(assetId, viaLink = false) {
  try {
    const a = await api(`/photos/api/assets/${assetId}`);
    // Neither versos nor stack variants have metadata of their own — edit
    // the recto / the stack's main image instead (flip and the variant chips
    // show the other sides). One hop only, in case of corrupt links.
    if (a.pair?.recto && !viaLink) return openEditor(a.pair.recto, true);
    if (a.stack && !a.stack.primary && a.stackPrimaryId && !viaLink) {
      return openEditor(a.stackPrimaryId, true);
    }
    state.current = assetId;
    state.bulk = false;
    state.flipped = false;
    state.versoId = a.pair?.verso || null;
    state.stackId = a.stack?.id || null;
    state.variants = [
      {id: a.id, name: a.name, scan: a.scan},
      ...(a.stackChildren || []).map((c) => ({id: c.id, name: c.name, scan: c.scan})),
    ];
    state.variantId = null;
    el('ed-single').classList.remove('hidden');
    el('ed-gramps-section').classList.remove('hidden');
    el('ed-bulk-note').classList.add('hidden');
    el('ed-prev').classList.remove('hidden');
    el('ed-next').classList.remove('hidden');

    el('ed-name').textContent = a.name;
    el('ed-pair-bar').classList.toggle('hidden', !state.versoId);
    syncFlip();
    const meta = [];
    if (a.people.length) meta.push(a.people.join(', '));
    if (a.description) meta.push(a.description);
    el('ed-meta').textContent = meta.join(' · ');

    renderStackNav();

    el('btn-del-date').disabled = false;
    fillDateForm(a.date);
    fillGrampsForm(a.gramps);
    if (!el('editor').classList.contains('active')) ui('#editor');
  } catch (err) {
    snack(`Could not load asset: ${err.message}`);
  }
}

function openBulkEditor() {
  state.bulk = true;
  state.current = null;
  el('ed-single').classList.add('hidden');
  el('ed-gramps-section').classList.add('hidden');
  el('ed-bulk-note').classList.remove('hidden');
  el('ed-prev').classList.add('hidden');
  el('ed-next').classList.add('hidden');
  el('ed-name').textContent = 'Set date for selection';
  el('ed-bulk-note').textContent =
    `The date below will be written to all ${state.selected.size} selected assets.`;
  el('btn-del-date').disabled = true;  // remove-per-asset makes no sense in bulk
  fillDateForm(null);
  if (!el('editor').classList.contains('active')) ui('#editor');
}

function stepEditor(delta) {
  const items = visibleItems();
  const idx = items.findIndex((a) => a.id === state.current);
  // -1: filtered out (undated toggle) or opened via a stack/verso link.
  // Versos are never in the list, so no skip logic is needed here.
  if (idx === -1) return;
  const next = items[idx + delta];
  if (next) openEditor(next.id);
}

/* ---------- date form ---------- */

function fillDateForm(d) {
  el('d-quality').value = d?.quality || 'regular';
  el('d-modifier').value = d?.modifier || 'regular';
  setPart('', d?.start);
  setPart('2', d?.stop);
  el('d-text').value = d?.text || '';
  syncDateRows();
  refreshPreview();
}

function setPart(suffix, part) {
  el(`d-year${suffix}`).value = part?.year || '';
  el(`d-month${suffix}`).value = String(part?.month || 0);
  el(`d-day${suffix}`).value = part?.day || '';
}

function readPart(suffix) {
  const num = (id) => {
    const v = el(id).value.trim();
    return v === '' ? 0 : parseInt(v, 10);
  };
  return {
    year: num(`d-year${suffix}`),
    month: parseInt(el(`d-month${suffix}`).value, 10) || 0,
    day: num(`d-day${suffix}`),
  };
}

function readDateForm() {
  const modifier = el('d-modifier').value;
  const payload = {
    modifier,
    quality: el('d-quality').value,
    text: el('d-text').value.trim(),
  };
  if (modifier !== 'textonly') {
    payload.start = readPart('');
    if (modifier === 'range' || modifier === 'span') payload.stop = readPart('2');
  }
  return payload;
}

function syncDateRows() {
  const modifier = el('d-modifier').value;
  el('d-start-row').classList.toggle('hidden', modifier === 'textonly');
  el('d-stop-row').classList.toggle('hidden', modifier !== 'range' && modifier !== 'span');
}

let previewTimer = null;
function refreshPreview() {
  clearTimeout(previewTimer);
  previewTimer = setTimeout(async () => {
    const payload = readDateForm();
    // A pristine form gets no nagging "a year is required" — errors only
    // once the user has typed something.
    const partEmpty = (p) => !p || (!p.year && !p.month && !p.day);
    if (!payload.text && partEmpty(payload.start) && partEmpty(payload.stop)) {
      el('d-preview').textContent = '';
      return;
    }
    try {
      const res = await api('/photos/api/date/preview', {method: 'POST', body: JSON.stringify(payload)});
      el('d-preview').textContent = res.error ? `⚠ ${res.error}` : `→ ${res.display}`;
    } catch {
      el('d-preview').textContent = '';
    }
  }, 250);
}

async function saveDate() {
  const payload = readDateForm();
  try {
    if (state.bulk) {
      const ids = [...state.selected];
      const res = await api('/photos/api/bulk/date', {method: 'POST', body: JSON.stringify({ids, date: payload})});
      for (const item of state.items) {
        if (state.selected.has(item.id) && !res.failed.some((f) => f.id === item.id)) {
          item.date = res.date;
        }
      }
      snack(res.failed.length ? `Saved ${res.ok}, failed ${res.failed.length}` : `Date saved to ${res.ok} assets`);
      ui('#editor');
    } else {
      const normalized = await api(`/photos/api/assets/${state.current}/date`, {method: 'PUT', body: JSON.stringify(payload)});
      const item = state.items.find((a) => a.id === state.current);
      if (item) item.date = normalized;
      snack(`Date saved: ${normalized.display}`);
    }
    renderGrid();
  } catch (err) {
    snack(`Save failed: ${err.message}`);
  }
}

async function deleteDate() {
  if (state.bulk || !state.current) return;
  try {
    await api(`/photos/api/assets/${state.current}/date`, {method: 'DELETE'});
    const item = state.items.find((a) => a.id === state.current);
    if (item) item.date = null;
    fillDateForm(null);
    renderGrid();
    snack('Date removed');
  } catch (err) {
    snack(`Remove failed: ${err.message}`);
  }
}

/* ---------- recto/verso + stack variants ---------- */

function syncFlip() {
  // Priority: verso (the back of the print) over a previewed stack variant.
  const showing = state.flipped && state.versoId
    ? state.versoId
    : (state.variantId || state.current);
  el('ed-img').src = `/photos/thumb/${showing}?size=preview`;
  el('flip-label').textContent = state.flipped ? 'Show front' : 'Show verso';
}

function flip() {
  if (!state.versoId) return;
  state.flipped = !state.flipped;
  if (state.flipped) state.variantId = null;
  syncFlip();
  renderStackNav();
}

/* Stack variants: the arrows cycle the preview through the stack's files;
   metadata always belongs to the main image (state.current). */
function variantIdx() {
  const idx = state.variants.findIndex((v) => v.id === (state.variantId || state.current));
  return idx === -1 ? 0 : idx;
}

function cycleVariant(delta) {
  const n = state.variants.length;
  if (n < 2) return;
  const idx = (variantIdx() + delta + n) % n;
  state.variantId = idx === 0 ? null : state.variants[idx].id;
  state.flipped = false;
  syncFlip();
  renderStackNav();
}

function renderStackNav() {
  const n = state.variants.length;
  el('ed-stack-nav').classList.toggle('hidden', n < 2);
  if (n < 2) return;
  const idx = variantIdx();
  el('variant-label').textContent = `${idx + 1}/${n}`;
  el('btn-make-main').classList.toggle('hidden', idx === 0);
  el('btn-unstack').classList.toggle('hidden', idx === 0);
}

async function unstack() {
  if (!state.variantId) return;
  try {
    await api(`/photos/api/stacks/assets/${state.variantId}`, {method: 'DELETE'});
    snack('Removed from the stack');
    await loadAssets(state.page);
    await openEditor(state.current, true);
  } catch (err) {
    snack(`Remove failed: ${err.message}`);
  }
}

async function stackSelection() {
  if (state.selected.size < 2) return;
  try {
    await api('/photos/api/stacks', {
      method: 'POST',
      body: JSON.stringify({asset_ids: [...state.selected]}),
    });
    state.selected.clear();
    state.selectMode = false;
    el('btn-select').classList.remove('fill');
    snack('Stacked — variants hide behind the main image');
    await loadAssets(state.page);
  } catch (err) {
    snack(`Stacking failed: ${err.message}`);
  }
}

async function makeMain() {
  if (!state.stackId || !state.variantId) return;
  const newMain = state.variantId;
  try {
    await api(`/photos/api/stacks/${state.stackId}/primary`, {
      method: 'PUT',
      body: JSON.stringify({asset_id: newMain}),
    });
    snack('Main image changed — the metadata moved with it');
    await loadAssets(state.page);
    await openEditor(newMain, true);
  } catch (err) {
    snack(`Could not change the main image: ${err.message}`);
  }
}

async function unpair() {
  if (!state.current || !state.versoId) return;
  try {
    await api(`/photos/api/pair/${state.current}`, {method: 'DELETE'});
    state.versoId = null;
    state.flipped = false;
    el('ed-pair-bar').classList.add('hidden');
    syncFlip();
    snack('Verso unlinked');
    await loadAssets(state.page);
  } catch (err) {
    snack(`Unlink failed: ${err.message}`);
  }
}

function openPairDialog() {
  const picked = [...state.selected]
    .map((id) => state.items.find((x) => x.id === id))
    .filter(Boolean);
  if (picked.length !== 2) {
    snack('Pairing works within one page — select both photos on the same page');
    return;
  }
  state.pairDraft = {a: picked[0].id, b: picked[1].id, recto: null};
  el('pair-choices').innerHTML = picked.map((x) => `
    <div class="s6">
      <img class="responsive round pair-choice" data-id="${x.id}"
        src="/photos/thumb/${x.id}?size=preview" alt="${esc(x.name)}">
      <p class="small-text center-align truncate">${esc(x.name)}</p>
    </div>`).join('');
  for (const img of el('pair-choices').querySelectorAll('.pair-choice')) {
    img.addEventListener('click', () => {
      state.pairDraft.recto = img.dataset.id;
      for (const i of el('pair-choices').querySelectorAll('.pair-choice')) {
        i.classList.toggle('chosen', i.dataset.id === state.pairDraft.recto);
      }
      el('btn-save-pair').disabled = false;
      syncPairNote();
    });
  }
  el('btn-save-pair').disabled = true;
  syncPairNote();
  ui('#pair');
}

function syncPairNote() {
  const d = state.pairDraft;
  if (!d.recto) {
    el('pair-note').textContent = '';
    return;
  }
  const versoId = d.recto === d.a ? d.b : d.a;
  const v = state.items.find((x) => x.id === versoId);
  const warn = v && (v.date || v.scan || v.gramps?.title)
    ? ' Note: the back photo has metadata of its own, which will be ignored.'
    : '';
  el('pair-note').textContent = `The other photo becomes the verso.${warn}`;
}

async function savePair() {
  const d = state.pairDraft;
  if (!d?.recto) return;
  const verso = d.recto === d.a ? d.b : d.a;
  try {
    await api('/photos/api/pair', {method: 'PUT', body: JSON.stringify({recto: d.recto, verso})});
    ui('#pair');
    state.selected.clear();
    state.selectMode = false;
    el('btn-select').classList.remove('fill');
    snack('Paired — the verso now lives behind its recto (flip in the editor)');
    await loadAssets(state.page);
  } catch (err) {
    snack(`Pairing failed: ${err.message}`);
  }
}

/* ---------- gramps form ---------- */

function fillGrampsForm(g) {
  el('g-title').value = g?.title || '';
  el('g-state').textContent = g?.gramps_id
    ? `Synced to Gramps as ${g.gramps_id}${g.synced_at ? ` on ${g.synced_at.slice(0, 10)}` : ''}`
    : '';
}

async function saveTitle() {
  if (state.bulk || !state.current) return;
  try {
    const g = await api(`/photos/api/assets/${state.current}/gramps`, {
      method: 'PUT',
      body: JSON.stringify({title: el('g-title').value}),
    });
    const item = state.items.find((a) => a.id === state.current);
    if (item) item.gramps = g;
    fillGrampsForm(g);
    renderGrid();
    snack(g?.title ? `Title saved: ${g.title}` : 'Title cleared');
  } catch (err) {
    snack(`Save failed: ${err.message}`);
  }
}

/* ---------- events ---------- */

function bindEvents() {
  for (const id of ['f-album', 'f-person', 'f-order']) {
    el(id).addEventListener('change', () => loadAssets(1));
  }
  let nameTimer = null;
  el('f-name').addEventListener('input', () => {
    clearTimeout(nameTimer);
    nameTimer = setTimeout(() => loadAssets(1), 400);
  });
  el('f-undated').addEventListener('change', renderGrid);

  el('btn-prev').addEventListener('click', () => loadAssets(state.page - 1));
  // state.nextPage is an opaque token in the spec — only its truthiness is
  // meaningful (enables the button); the page number itself just increments.
  el('btn-next').addEventListener('click', () => loadAssets(state.page + 1));

  el('btn-select').addEventListener('click', () => {
    state.selectMode = !state.selectMode;
    if (!state.selectMode) state.selected.clear();
    el('btn-select').classList.toggle('fill', state.selectMode);
    renderGrid();
  });
  el('btn-select-page').addEventListener('click', () => {
    for (const a of visibleItems()) state.selected.add(a.id);
    renderGrid();
  });
  el('btn-clear-sel').addEventListener('click', () => {
    state.selected.clear();
    renderGrid();
  });
  el('btn-bulk-date').addEventListener('click', openBulkEditor);
  el('btn-pair').addEventListener('click', openPairDialog);
  el('btn-save-pair').addEventListener('click', savePair);
  el('btn-stack').addEventListener('click', stackSelection);

  el('ed-prev').addEventListener('click', () => stepEditor(-1));
  el('ed-next').addEventListener('click', () => stepEditor(1));
  el('btn-flip').addEventListener('click', flip);
  el('btn-unpair').addEventListener('click', unpair);
  el('btn-variant-prev').addEventListener('click', () => cycleVariant(-1));
  el('btn-variant-next').addEventListener('click', () => cycleVariant(1));
  el('btn-make-main').addEventListener('click', makeMain);
  el('btn-unstack').addEventListener('click', unstack);

  el('d-modifier').addEventListener('change', () => { syncDateRows(); refreshPreview(); });
  for (const id of ['d-quality', 'd-month', 'd-month2']) {
    el(id).addEventListener('change', refreshPreview);
  }
  for (const id of ['d-year', 'd-day', 'd-year2', 'd-day2', 'd-text']) {
    el(id).addEventListener('input', refreshPreview);
  }
  el('btn-save-date').addEventListener('click', saveDate);
  el('btn-del-date').addEventListener('click', deleteDate);

  el('btn-save-title').addEventListener('click', saveTitle);

  el('btn-settings').addEventListener('click', openSettings);
  el('set-filter').addEventListener('input', renderSettingsList);
  el('btn-save-settings').addEventListener('click', saveSettings);
}

init().catch((err) => snack(`Init failed: ${err.message}`));
