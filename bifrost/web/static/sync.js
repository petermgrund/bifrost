/* Sync page — preview/apply panels for each source module. */
"use strict";

const esc = (s) => String(s ?? "").replace(/[&<>"']/g, c =>
  ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const api = async (path, body) => {
  const resp = await fetch(path, {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body || {}),
  });
  if (!resp.ok) throw new Error(`${resp.status}: ${await resp.text()}`);
  return resp.json();
};

const GROUP_LABELS = { doc: "Documents", media: "Media updates", note: "Transcriptions", face: "Faces", place: "Place links" };

function render(panel, payload) {
  const items = payload.events.filter(e => e.kind === "item");
  const summary = payload.events.find(e => e.kind === "summary");
  const errors = payload.events.filter(e => e.kind === "error");

  let html = "";
  for (const entity of Object.keys(GROUP_LABELS)) {
    const rows = items.filter(e => e.entity === entity);
    if (!rows.length) continue;
    html += `<h3>${GROUP_LABELS[entity]} <span class="hint">(${rows.length})</span></h3>
      <table class="results"><tr><th>action</th><th>what</th><th>detail</th></tr>` +
      rows.map(e => `<tr>
        <td class="action-${e.action}">${e.action.replace("_", " ")}</td>
        <td>${esc(e.title || e.source_id)}${e.gramps_id ? ` <span class="hint">${esc(e.gramps_id)}</span>` : ""}</td>
        <td class="hint">${esc(e.detail || "")}</td></tr>`).join("") +
      `</table>`;
  }
  if (errors.length) {
    html += `<h3 class="action-failed">Warnings / errors</h3>` +
      errors.map(e => `<div class="action-failed">${esc(e.detail)}</div>`).join("");
  }
  if (summary) {
    const verb = payload.apply ? "Done" : "Would do";
    html += `<div class="summary-line">${verb}: ${esc(JSON.stringify(summary.data))}</div>`;
  }
  panel.querySelector(".results").innerHTML =
    html || "<div class='hint'>Nothing to do — everything is in sync.</div>";
  return summary;
}

document.querySelectorAll(".syncpanel[data-source]").forEach(panel => {
  const source = panel.dataset.source;
  const previewBtn = panel.querySelector(".preview-btn");
  const applyBtn = panel.querySelector(".apply-btn");
  const status = panel.querySelector(".status");
  const forceTx = panel.querySelector(".force-tx");
  const body = () => forceTx ? { force_transcriptions: forceTx.checked } : {};

  previewBtn.addEventListener("click", async () => {
    previewBtn.disabled = true;
    status.textContent = "Previewing…";
    panel.querySelector(".results").innerHTML = "";
    try {
      const payload = await api(`/sync/api/${source}/preview`, body());
      const summary = render(panel, payload);
      const c = summary ? summary.data : {};
      const hasWork = Object.entries(c).some(([k, v]) =>
        !["skipped", "errors", "baselined"].includes(k) && v > 0);
      applyBtn.disabled = !hasWork;
      status.textContent = `Preview run #${payload.run_id}.` +
        (hasWork ? " Review above, then Apply." : "");
    } catch (e) {
      panel.querySelector(".results").innerHTML = `<div class="action-failed">${esc(e.message)}</div>`;
      status.textContent = "";
    } finally {
      previewBtn.disabled = false;
    }
  });

  applyBtn.addEventListener("click", async () => {
    applyBtn.disabled = true;
    status.textContent = "Applying…";
    try {
      const payload = await api(`/sync/api/${source}/apply`, body());
      render(panel, payload);
      status.textContent = `Applied (run #${payload.run_id}).`;
    } catch (e) {
      panel.querySelector(".results").innerHTML = `<div class="action-failed">${esc(e.message)}</div>`;
      status.textContent = "";
    }
  });
});
