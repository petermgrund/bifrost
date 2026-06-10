/* Faces page — two-pane linker, face sync actions, synced-media browser. */
"use strict";

const state = {
  gramps: [], immich: [], links: [], media: [],
  selGramps: null, selImmich: null, mediaFilter: "all",
};

const $ = (id) => document.getElementById(id);
const api = async (path, opts = {}) => {
  const resp = await fetch(path, {
    headers: { "Content-Type": "application/json" }, ...opts,
  });
  if (!resp.ok) throw new Error(`${path} → ${resp.status}: ${await resp.text()}`);
  return resp.json();
};

const linkByHandle = () => Object.fromEntries(state.links.map(l => [l.gramps_handle, l]));
const linkByImmich = () => Object.fromEntries(state.links.map(l => [l.immich_person_id, l]));

/* ---- rendering ---- */

function renderGramps() {
  const q = $("gramps-search").value.toLowerCase();
  const links = linkByHandle();
  const rows = state.gramps
    .filter(p => !q || p.name.toLowerCase().includes(q) || p.gramps_id.toLowerCase().includes(q))
    .map(p => {
      const link = links[p.handle];
      const sel = state.selGramps === p.handle ? " selected" : "";
      const badge = link
        ? `<span class="badge" title="${link.immich_person_id}">${esc(link.label || "linked")}</span>
           <button class="unlink" data-handle="${p.handle}">unlink</button>`
        : `<span class="badge unlinked">–</span>`;
      return `<div class="card${sel}" data-handle="${p.handle}">
        <span class="name">${esc(p.name)}</span>
        <span class="meta">${esc(p.gramps_id)} · ${p.media_count}m/${p.rect_count}f</span>
        ${badge}</div>`;
    });
  $("gramps-list").innerHTML = rows.join("") || "<div class='hint'>No matches</div>";
}

function renderImmich() {
  const q = $("immich-search").value.toLowerCase();
  const links = linkByImmich();
  const rows = state.immich
    .filter(p => !q || (p.name || "").toLowerCase().includes(q))
    .map(p => {
      const sel = state.selImmich === p.id ? " selected" : "";
      const linked = links[p.id] ? `<span class="badge">linked</span>` : "";
      return `<div class="card${sel}" data-id="${p.id}">
        <img loading="lazy" src="/faces/api/thumb/person/${p.id}" alt="">
        <span class="name">${esc(p.name || "(unnamed)")}</span>${linked}</div>`;
    });
  $("immich-list").innerHTML = rows.join("") || "<div class='hint'>No matches</div>";
}

function renderPair() {
  const both = state.selGramps && state.selImmich;
  $("link-btn").disabled = !both;
  const g = state.gramps.find(p => p.handle === state.selGramps);
  const i = state.immich.find(p => p.id === state.selImmich);
  $("pair-hint").textContent = both
    ? `${g.name} ↔ ${i.name || "(unnamed)"}`
    : "Select one person on each side";
}

function renderMedia() {
  const q = $("media-search").value.toLowerCase();
  const rows = state.media
    .filter(m => !q || m.title.toLowerCase().includes(q))
    .filter(m => state.mediaFilter === "all"
      || (state.mediaFilter === "locked") === m.is_manual)
    .map(m => `<div class="media-card${m.is_manual ? " locked" : ""}">
      <img loading="lazy" src="/faces/api/thumb/asset/${m.immich_asset_id}" alt="">
      <div class="body">
        <div class="title" title="${esc(m.title)}">${esc(m.title)} <span class="meta">${esc(m.gramps_id)}</span></div>
        <div class="chips">${m.face_links.map(f => `<span class="facechip">${esc(f.label)}</span>`).join("")}</div>
        <button class="lockbtn" data-asset="${m.immich_asset_id}" data-locked="${m.is_manual}">
          ${m.is_manual ? "🔒 locked (tight) — unlock" : "lock faces (tight crop)"}</button>
      </div></div>`);
  $("media-list").innerHTML = rows.join("") || "<div class='hint'>No synced media</div>";
}

function renderResults(payload) {
  const items = payload.events.filter(e => e.kind === "item" || e.kind === "error");
  const summary = payload.events.find(e => e.kind === "summary");
  const head = `<tr><th>action</th><th>what</th><th>detail</th></tr>`;
  const rows = items.map(e => `<tr>
    <td class="action-${e.action || "failed"}">${e.action || e.kind}</td>
    <td>${esc(e.title || e.source_id || "")}</td>
    <td class="hint">${e.data && e.data.rect ? "rect " + JSON.stringify(e.data.rect) : ""}${esc(e.detail || "")}</td>
    </tr>`);
  const sum = summary ? `<div class="summary-line">Summary: ${esc(JSON.stringify(summary.data))}`
    + (payload.dry_run ? " (dry run — nothing written)" : "") + `</div>` : "";
  $("op-results").innerHTML =
    (rows.length ? `<table class="results">${head}${rows.join("")}</table>` : "<div class='hint'>Nothing to do.</div>") + sum;
}

const esc = (s) => String(s ?? "").replace(/[&<>"']/g, c =>
  ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

/* ---- data loading ---- */

async function loadAll(refresh = false) {
  const r = refresh ? "?refresh=1" : "";
  [state.gramps, state.immich, state.links, state.media] = await Promise.all([
    api(`/faces/api/gramps-people${r}`),
    api(`/faces/api/immich-people${r}`),
    api(`/faces/api/links`),
    api(`/faces/api/synced-media${r}`),
  ]);
  renderGramps(); renderImmich(); renderPair(); renderMedia();
}

/* ---- events ---- */

$("gramps-list").addEventListener("click", async (ev) => {
  const un = ev.target.closest(".unlink");
  if (un) {
    state.links = await api(`/faces/api/links/${un.dataset.handle}`, { method: "DELETE" });
    renderGramps(); renderImmich();
    return;
  }
  const card = ev.target.closest(".card");
  if (!card) return;
  state.selGramps = state.selGramps === card.dataset.handle ? null : card.dataset.handle;
  renderGramps(); renderPair();
});

$("immich-list").addEventListener("click", (ev) => {
  const card = ev.target.closest(".card");
  if (!card) return;
  state.selImmich = state.selImmich === card.dataset.id ? null : card.dataset.id;
  renderImmich(); renderPair();
});

$("link-btn").addEventListener("click", async () => {
  state.links = await api("/faces/api/links", {
    method: "POST",
    body: JSON.stringify({
      gramps_handle: state.selGramps,
      immich_person_id: state.selImmich,
      label: $("link-label").value || null,
    }),
  });
  state.selGramps = state.selImmich = null;
  $("link-label").value = "";
  renderGramps(); renderImmich(); renderPair();
});

async function runOp(path, btn) {
  const dry = $("dry-run").checked;
  btn.disabled = true;
  $("op-status").textContent = "Running…";
  $("op-results").innerHTML = "";
  try {
    const payload = await api(path, { method: "POST", body: JSON.stringify({ dry_run: dry }) });
    $("op-status").textContent = `Run #${payload.run_id} done.`;
    renderResults(payload);
  } catch (e) {
    $("op-status").textContent = "";
    $("op-results").innerHTML = `<div class="action-failed">${esc(e.message)}</div>`;
  } finally {
    btn.disabled = false;
  }
}
$("sync-btn").addEventListener("click", (e) => runOp("/faces/api/sync", e.target));
$("repad-btn").addEventListener("click", (e) => runOp("/faces/api/repad", e.target));

$("media-list").addEventListener("click", async (ev) => {
  const btn = ev.target.closest(".lockbtn");
  if (!btn) return;
  btn.disabled = true;
  try {
    const result = await api("/faces/api/lock", {
      method: "POST",
      body: JSON.stringify({ asset_id: btn.dataset.asset, locked: btn.dataset.locked !== "true" }),
    });
    const row = state.media.find(m => m.immich_asset_id === result.asset_id);
    if (row) row.is_manual = result.is_manual;
    renderMedia();
  } catch (e) {
    alert(e.message);
    btn.disabled = false;
  }
});

document.querySelectorAll(".chip").forEach(chip => chip.addEventListener("click", () => {
  document.querySelectorAll(".chip").forEach(c => c.classList.remove("active"));
  chip.classList.add("active");
  state.mediaFilter = chip.dataset.filter;
  renderMedia();
}));

$("gramps-search").addEventListener("input", renderGramps);
$("immich-search").addEventListener("input", renderImmich);
$("media-search").addEventListener("input", renderMedia);
$("refresh-btn").addEventListener("click", () => loadAll(true));

loadAll().catch(e => { $("gramps-list").textContent = e.message; });
