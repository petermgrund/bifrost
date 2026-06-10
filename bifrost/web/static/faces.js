/* Faces — Photos (per-face padding, direct manipulation) + People (linking). */
"use strict";

const state = {
  gramps: [], immich: [], links: [], listing: { photos: [], pending_total: 0 },
  selGramps: null, selImmich: null,
  photoFilter: "all", openAsset: null,
};

const $ = (id) => document.getElementById(id);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, c =>
  ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const api = async (path, opts = {}) => {
  const resp = await fetch(path, { headers: { "Content-Type": "application/json" }, ...opts });
  if (!resp.ok) throw new Error(`${resp.status}: ${await resp.text()}`);
  return resp.json();
};

/* ---------------- tabs ---------------- */

document.querySelectorAll(".tab").forEach(t => t.addEventListener("click", () => {
  document.querySelectorAll(".tab").forEach(x => x.classList.remove("active"));
  t.classList.add("active");
  $("tab-photos").hidden = t.dataset.tab !== "photos";
  $("tab-people").hidden = t.dataset.tab !== "people";
}));

function showPeopleTab(immichPersonId) {
  document.querySelector('.tab[data-tab="people"]').click();
  if (immichPersonId) {
    state.selImmich = immichPersonId;
    $("immich-search").value = "";
    renderImmich(); renderPair();
  }
}

/* ---------------- photos grid ---------------- */

function renderPhotos() {
  const q = $("photo-search").value.toLowerCase();
  const rows = state.listing.photos
    .filter(p => !q || p.title.toLowerCase().includes(q))
    .filter(p => state.photoFilter === "all"
      || (state.photoFilter === "pending" && p.pending_count > 0)
      || (state.photoFilter === "manual" && p.is_manual))
    .map(p => {
      const badges = [
        p.pending_count ? `<span class="badge">${p.pending_count} pending</span>` : "",
        p.is_manual ? `<span class="badge warn" title="At least one face on this photo was drawn manually in Immich">⚠ manual</span>` : "",
        p.synced ? "" : `<span class="badge unlinked">not in Gramps yet</span>`,
      ].join("");
      const chips = p.faces
        .filter(f => f.status !== "unlinked")
        .map(f => `<span class="facechip s-${f.status}">${esc(f.label || f.immich_name)}</span>`).join("");
      return `<div class="photo-card${p.synced ? "" : " unsynced"}" data-asset="${p.asset_id}">
        <img loading="lazy" src="/faces/api/thumb/asset/${p.asset_id}" alt="">
        <div class="body">
          <div class="title" title="${esc(p.title)}">${esc(p.title)}</div>
          <div class="meta">${esc(p.gramps_id || "")} ${badges}</div>
          <div class="chips">${chips}</div>
        </div></div>`;
    });
  $("photo-grid").innerHTML = rows.join("") || "<div class='hint'>No photos match.</div>";
  $("photo-count").textContent = `${rows.length} photos · ${state.listing.pending_total} pending faces`;
  const ap = $("apply-pending");
  ap.hidden = state.listing.pending_total === 0;
  ap.textContent = `Apply pending (${state.listing.pending_total})`;
}

$("photo-grid").addEventListener("click", (ev) => {
  const card = ev.target.closest(".photo-card");
  if (card) openDetail(card.dataset.asset);
});

/* ---------------- photo detail ---------------- */

function photoByAsset(id) { return state.listing.photos.find(p => p.asset_id === id); }

function openDetail(assetId) {
  const p = photoByAsset(assetId);
  if (!p) return;
  state.openAsset = assetId;
  $("detail-title").textContent = p.title;
  $("detail-meta").textContent = p.synced ? p.gramps_id : "not in Gramps yet";
  $("detail-img").src = `/faces/api/thumb/asset/${assetId}?size=preview`;
  const alert = $("detail-alert");
  if (p.is_manual) {
    alert.hidden = false;
    alert.textContent = "⚠ At least one face on this photo was drawn manually in Immich " +
      "(not found by the ML model), so it may already include padding. Default pad here is 0%.";
  } else {
    alert.hidden = true;
  }
  renderDetail();
  $("detail").hidden = false;
}

function renderDetail() {
  const p = photoByAsset(state.openAsset);
  if (!p) return;

  // rect overlays (percent-based, so they scale with the image)
  const boxes = p.faces
    .filter(f => f.status !== "unlinked")
    .map(f => {
      const r = f.current_rect || f.expected_rect;
      if (!r) return "";
      const pendingCls = f.status === "applied" ? "" : " pending";
      return `<div class="facebox${pendingCls}" style="left:${r[0]}%;top:${r[1]}%;width:${r[2]-r[0]}%;height:${r[3]-r[1]}%">
        <span>${esc(f.label || f.immich_name)}</span></div>`;
    }).join("");
  $("detail-imgwrap").querySelectorAll(".facebox").forEach(b => b.remove());
  $("detail-imgwrap").insertAdjacentHTML("beforeend", boxes);

  // face rows
  const rows = p.faces.map((f, i) => {
    if (f.status === "unlinked") {
      return `<div class="facerow">
        <img src="/faces/api/thumb/person/${f.immich_person_id}" alt="">
        <div class="who"><div>${esc(f.immich_name)}</div><div class="hint">not linked to a Gramps person</div></div>
        <button class="linkjump" data-immich="${f.immich_person_id}">Link…</button></div>`;
    }
    const padPct = Math.round(f.pad * 100);
    const statusTxt = { applied: "applied", pending: "pending — not in Gramps yet", outdated: "outdated — box moved", differs: "differs — manual faces on this photo; apply only deliberately" }[f.status];
    return `<div class="facerow s-${f.status}">
      <img src="/faces/api/thumb/person/${f.immich_person_id}" alt="">
      <div class="who"><div>${esc(f.label || f.immich_name)}</div><div class="hint">${statusTxt}</div></div>
      <div class="padctl">
        <input type="range" min="0" max="50" step="5" value="${padPct}" data-idx="${i}">
        <span class="padval">${padPct}%</span>
        ${f.status === "applied" ? "" : `<button class="applyone" data-idx="${i}">Apply</button>`}
      </div></div>`;
  });
  $("detail-faces").innerHTML = rows.join("") ||
    "<div class='hint'>No identified faces on this photo.</div>";
}

$("detail-close").addEventListener("click", () => { $("detail").hidden = true; state.openAsset = null; });
$("detail").addEventListener("click", (ev) => { if (ev.target === $("detail")) $("detail-close").click(); });

$("detail-faces").addEventListener("input", (ev) => {
  const slider = ev.target.closest("input[type=range]");
  if (!slider) return;
  slider.parentElement.querySelector(".padval").textContent = `${slider.value}%`;
});

$("detail-faces").addEventListener("change", (ev) => {
  const slider = ev.target.closest("input[type=range]");
  if (slider) applyFace(Number(slider.dataset.idx), Number(slider.value) / 100);
});

$("detail-faces").addEventListener("click", (ev) => {
  const jump = ev.target.closest(".linkjump");
  if (jump) { $("detail-close").click(); showPeopleTab(jump.dataset.immich); return; }
  const one = ev.target.closest(".applyone");
  if (one) {
    const f = photoByAsset(state.openAsset).faces[Number(one.dataset.idx)];
    applyFace(Number(one.dataset.idx), f.pad);
  }
});

async function applyFace(idx, pad) {
  const p = photoByAsset(state.openAsset);
  const f = p.faces[idx];
  try {
    const result = await api("/faces/api/face", {
      method: "POST",
      body: JSON.stringify({ gramps_handle: f.gramps_handle, asset_id: p.asset_id, pad }),
    });
    Object.assign(f, result);
    p.pending_count = p.faces.filter(x => ["pending", "outdated"].includes(x.status)).length;
    state.listing.pending_total = state.listing.photos.reduce((n, x) => n + x.pending_count, 0);
    renderDetail(); renderPhotos();
  } catch (e) { alert(e.message); }
}

$("apply-pending").addEventListener("click", async (ev) => {
  ev.target.disabled = true;
  ev.target.textContent = "Applying…";
  try {
    const r = await api("/faces/api/apply-pending", { method: "POST", body: "{}" });
    const sum = r.events.find(e => e.kind === "summary");
    await loadPhotos(true);
    ev.target.textContent = sum ? `Done: ${JSON.stringify(sum.data)}` : "Done";
    setTimeout(renderPhotos, 2500);
  } catch (e) { alert(e.message); }
  finally { ev.target.disabled = false; }
});

/* ---------------- people tab (linking) ---------------- */

const linkByHandle = () => Object.fromEntries(state.links.map(l => [l.gramps_handle, l]));
const linkByImmich = () => Object.fromEntries(state.links.map(l => [l.immich_person_id, l]));

function renderGramps() {
  const q = $("gramps-search").value.toLowerCase();
  const links = linkByHandle();
  const rows = state.gramps
    .filter(p => !q || p.name.toLowerCase().includes(q) || p.gramps_id.toLowerCase().includes(q))
    .map(p => {
      const link = links[p.handle];
      const sel = state.selGramps === p.handle ? " selected" : "";
      const badge = link
        ? `<span class="badge">${esc(link.label || "linked")}</span>
           <button class="unlink" data-handle="${p.handle}">unlink</button>`
        : `<span class="badge unlinked">–</span>`;
      return `<div class="card${sel}" data-handle="${p.handle}">
        <span class="name">${esc(p.name)}</span>
        <span class="meta">${esc(p.gramps_id)} · ${p.rect_count}f</span>
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

$("gramps-list").addEventListener("click", async (ev) => {
  const un = ev.target.closest(".unlink");
  if (un) {
    state.links = await api(`/faces/api/links/${un.dataset.handle}`, { method: "DELETE" });
    renderGramps(); renderImmich(); loadPhotos(false);
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
  await loadPhotos(false);
  if (state.listing.pending_total > 0) {
    $("pair-hint").textContent =
      `Linked. ${state.listing.pending_total} pending face(s) — see the Photos tab.`;
  }
});

/* ---------------- search & load ---------------- */

$("photo-search").addEventListener("input", renderPhotos);
$("gramps-search").addEventListener("input", renderGramps);
$("immich-search").addEventListener("input", renderImmich);
document.querySelectorAll(".chip").forEach(chip => chip.addEventListener("click", () => {
  document.querySelectorAll(".chip").forEach(c => c.classList.remove("active"));
  chip.classList.add("active");
  state.photoFilter = chip.dataset.filter;
  renderPhotos();
}));

async function loadPhotos(refresh = false) {
  state.listing = await api(`/faces/api/photos${refresh ? "?refresh=1" : ""}`);
  renderPhotos();
}

async function loadAll(refresh = false) {
  const r = refresh ? "?refresh=1" : "";
  [state.gramps, state.immich, state.links] = await Promise.all([
    api(`/faces/api/gramps-people${r}`),
    api(`/faces/api/immich-people${r}`),
    api(`/faces/api/links`),
  ]);
  renderGramps(); renderImmich(); renderPair();
  await loadPhotos(refresh);
}

$("refresh-btn").addEventListener("click", () => loadAll(true));
loadAll().catch(e => { $("photo-grid").textContent = e.message; });
