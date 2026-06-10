/* Sync page — preview/apply for the Immich → Gramps module. */
"use strict";

const $ = (id) => document.getElementById(id);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, c =>
  ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const api = async (path, opts = {}) => {
  const resp = await fetch(path, { headers: { "Content-Type": "application/json" }, ...opts });
  if (!resp.ok) throw new Error(`${resp.status}: ${await resp.text()}`);
  return resp.json();
};

const GROUPS = [
  ["media", "Media"],
  ["face", "Faces"],
  ["place", "Place links"],
];

function render(payload) {
  const items = payload.events.filter(e => e.kind === "item");
  const summary = payload.events.find(e => e.kind === "summary");
  const errors = payload.events.filter(e => e.kind === "error");

  let html = "";
  for (const [entity, label] of GROUPS) {
    const rows = items.filter(e => e.entity === entity);
    if (!rows.length) continue;
    html += `<h3>${label} <span class="hint">(${rows.length})</span></h3>
      <table class="results"><tr><th>action</th><th>what</th><th>detail</th></tr>` +
      rows.map(e => `<tr>
        <td class="action-${e.action}">${e.action.replace("_", " ")}</td>
        <td>${esc(e.title || e.source_id)}${e.gramps_id ? ` <span class="hint">${esc(e.gramps_id)}</span>` : ""}</td>
        <td class="hint">${esc(e.detail || "")}</td></tr>`).join("") +
      `</table>`;
  }
  if (errors.length) {
    html += `<h3 class="action-failed">Errors</h3>` +
      errors.map(e => `<div class="action-failed">${esc(e.detail)}</div>`).join("");
  }
  if (summary) {
    const verb = payload.apply ? "Done" : "Would do";
    html += `<div class="summary-line">${verb}: ${esc(JSON.stringify(summary.data))}</div>`;
  }
  $("sync-results").innerHTML = html || "<div class='hint'>Nothing to do — everything is in sync.</div>";
  return summary;
}

let previewHadWork = false;

$("preview-btn").addEventListener("click", async () => {
  $("preview-btn").disabled = true;
  $("sync-status").textContent = "Previewing…";
  try {
    const payload = await api("/sync/api/immich/preview", { method: "POST", body: "{}" });
    const summary = render(payload);
    const c = summary ? summary.data : {};
    previewHadWork = Object.entries(c).some(([k, v]) => k !== "skipped" && k !== "errors" && v > 0);
    $("apply-btn").disabled = !previewHadWork;
    $("sync-status").textContent = `Preview run #${payload.run_id}. ` +
      (previewHadWork ? "Review above, then Apply." : "");
  } catch (e) {
    $("sync-results").innerHTML = `<div class="action-failed">${esc(e.message)}</div>`;
    $("sync-status").textContent = "";
  } finally {
    $("preview-btn").disabled = false;
  }
});

$("apply-btn").addEventListener("click", async () => {
  $("apply-btn").disabled = true;
  $("sync-status").textContent = "Applying…";
  try {
    const payload = await api("/sync/api/immich/apply", { method: "POST", body: "{}" });
    render(payload);
    $("sync-status").textContent = `Applied (run #${payload.run_id}).`;
  } catch (e) {
    $("sync-results").innerHTML = `<div class="action-failed">${esc(e.message)}</div>`;
    $("sync-status").textContent = "";
  }
});
