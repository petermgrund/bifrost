/* Inbox — pending work counts + recent runs. */
"use strict";

const $ = (id) => document.getElementById(id);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, c =>
  ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

async function load() {
  const [listing, runs] = await Promise.all([
    fetch("/faces/api/photos").then(r => r.json()),
    fetch("/api/runs?limit=8").then(r => r.json()),
  ]);

  const photos = listing.photos;
  const unsynced = photos.filter(p => !p.synced).length;
  const faces = photos.flatMap(p => p.faces);
  const unlinked = faces.filter(f => f.status === "unlinked").length;
  const differs = faces.filter(f => f.status === "differs").length;

  const cards = [
    { n: unsynced, label: "photos tagged for sync, not in Gramps yet", href: "/sync", verb: "Sync" },
    { n: listing.pending_total, label: "faces pending in Gramps", href: "/faces", verb: "Review" },
    { n: unlinked, label: "detected faces with no person link", href: "/faces", verb: "Link" },
    { n: differs, label: "manual-faces rects differing from Immich", href: "/faces", verb: "Inspect" },
  ];
  $("inbox-cards").innerHTML = cards.map(c => `
    <a class="inbox-card${c.n ? "" : " done"}" href="${c.href}">
      <span class="count">${c.n}</span>
      <span class="label">${c.label}</span>
      <span class="verb">${c.n ? c.verb + " →" : "✓ all clear"}</span>
    </a>`).join("");

  $("runs-list").innerHTML = runs.length ? `<table class="results">
    <tr><th>#</th><th>job</th><th>status</th><th>started</th><th>summary</th></tr>` +
    runs.map(r => `<tr>
      <td>${r.id}</td><td>${esc(r.job)}</td>
      <td class="${r.status === "ok" ? "action-created" : "action-failed"}">${esc(r.status)}</td>
      <td class="hint">${esc(r.started_at)}</td>
      <td class="hint">${esc(r.summary ? JSON.parse(r.summary).data ? JSON.stringify(JSON.parse(r.summary).data) : r.summary : "")}</td>
      </tr>`).join("") + `</table>` : "<div class='hint'>No runs yet.</div>";
}

load().catch(e => { $("inbox-cards").textContent = e.message; });
