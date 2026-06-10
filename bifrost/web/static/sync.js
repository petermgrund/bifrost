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

/* Human phrasing for summary counters. quiet:true keys are muted context,
   not actions. */
const COUNT_PHRASES = {
  created: { one: "create %n item", many: "create %n items", done_one: "created %n item", done_many: "created %n items" },
  versions_updated: { many: "update %n changed version(s)", done_many: "updated %n changed version(s)" },
  titles_updated: { many: "update %n title(s)", done_many: "updated %n title(s)" },
  dates_updated: { many: "update %n date(s)", done_many: "updated %n date(s)" },
  descs_updated: { many: "update %n description(s)", done_many: "updated %n description(s)" },
  faces_linked: { many: "link %n face(s)", done_many: "linked %n face(s)" },
  places_linked: { many: "link %n place(s)", done_many: "linked %n place(s)" },
  tx_created: { many: "create %n transcription note(s)", done_many: "created %n transcription note(s)" },
  tx_updated: { many: "update %n transcription note(s)", done_many: "updated %n transcription note(s)" },
  skipped: { quiet: true, many: "%n already in sync" },
  tx_skipped: { quiet: true, many: "%n transcription(s) unchanged" },
  baselined: { quiet: true, many: "%n version baseline(s) recorded" },
  errors: { error: true, many: "%n error(s)" },
};

function summaryText(counts, applied) {
  const actions = [], quiet = [], errors = [];
  for (const [key, n] of Object.entries(counts)) {
    if (!n) continue;
    const p = COUNT_PHRASES[key];
    if (!p) { actions.push(`${key}: ${n}`); continue; }
    const tmpl = applied ? (n === 1 && p.done_one ? p.done_one : p.done_many || p.many)
                         : (n === 1 && p.one ? p.one : p.many);
    const text = tmpl.replace("%n", n);
    if (p.error) errors.push(text);
    else if (p.quiet) quiet.push(text);
    else actions.push(text);
  }
  return { actions, quiet, errors };
}

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
    const s = summaryText(summary.data, payload.apply);
    const lead = s.actions.length
      ? `<strong>${payload.apply ? "Done" : "This will"}:</strong> ${esc(s.actions.join(", "))}.`
      : (payload.apply ? "Done — nothing needed changing." : "Nothing to do — everything is in sync.");
    const quiet = s.quiet.length ? ` <span class="hint">(${esc(s.quiet.join(" · "))})</span>` : "";
    const errs = s.errors.length ? ` <span class="action-failed">${esc(s.errors.join(", "))}</span>` : "";
    html += `<div class="summary-line">${lead}${quiet}${errs}</div>`;
  }
  panel.querySelector(".results").innerHTML =
    html || "<div class='hint'>Nothing to do — everything is in sync.</div>";
  return summary;
}

document.querySelectorAll(".syncpanel[data-source]").forEach(panel => {
  const source = panel.dataset.source;
  const extraBody = panel.dataset.body ? JSON.parse(panel.dataset.body) : {};
  const previewBtn = panel.querySelector(".preview-btn");
  const applyBtn = panel.querySelector(".apply-btn");
  const status = panel.querySelector(".status");

  const setPrimary = (btn) => {
    [previewBtn, applyBtn].forEach(b => b.classList.remove("primary"));
    if (btn) btn.classList.add("primary");
  };

  previewBtn.addEventListener("click", async () => {
    previewBtn.disabled = true;
    status.textContent = "Previewing…";
    panel.querySelector(".results").innerHTML = "";
    try {
      const payload = await api(`/sync/api/${source}/preview`, extraBody);
      const summary = render(panel, payload);
      const c = summary ? summary.data : {};
      const hasWork = Object.entries(c).some(([k, v]) =>
        !["skipped", "errors", "baselined", "tx_skipped"].includes(k) && v > 0);
      applyBtn.disabled = !hasWork;
      if (hasWork) {
        setPrimary(applyBtn);
        applyBtn.textContent = "Apply these changes";
        status.textContent = "Reviewed? Then apply.";
      } else {
        setPrimary(panel.classList.contains("maintenance") ? null : previewBtn);
        status.textContent = "";
      }
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
      const payload = await api(`/sync/api/${source}/apply`, extraBody);
      render(panel, payload);
      status.textContent = `Applied (run #${payload.run_id}).`;
      applyBtn.textContent = "Apply";
      setPrimary(panel.classList.contains("maintenance") ? null : previewBtn);
    } catch (e) {
      panel.querySelector(".results").innerHTML = `<div class="action-failed">${esc(e.message)}</div>`;
      status.textContent = "";
    }
  });
});

/* Single-object transcription resync — keyed on a typed Gramps media ID. */
(() => {
  const panel = document.getElementById("resync-media");
  if (!panel) return;
  const input = panel.querySelector("#resync-id");
  const previewBtn = panel.querySelector(".preview-btn");
  const applyBtn = panel.querySelector(".apply-btn");
  const status = panel.querySelector(".status");
  const setPrimary = (btn) => {
    [previewBtn, applyBtn].forEach(b => b.classList.remove("primary"));
    if (btn) btn.classList.add("primary");
  };

  const run = async (apply) => {
    const media_id = input.value.trim();
    if (!media_id) { status.textContent = "Enter a media ID first."; return; }
    (apply ? applyBtn : previewBtn).disabled = true;
    status.textContent = apply ? "Applying…" : "Previewing…";
    if (!apply) panel.querySelector(".results").innerHTML = "";
    try {
      const payload = await api("/sync/api/paperless/resync-media", { media_id, apply });
      render(panel, { ...payload, apply });
      if (apply) {
        status.textContent = `Applied to ${payload.media_id} (Paperless #${payload.doc_id}, run #${payload.run_id}).`;
        applyBtn.disabled = true;
        setPrimary(null);
      } else {
        const c = (payload.events.find(e => e.kind === "summary") || {}).data || {};
        const hasWork = (c.tx_created || 0) + (c.tx_updated || 0) > 0;
        applyBtn.disabled = !hasWork;
        setPrimary(hasWork ? applyBtn : null);
        status.textContent = `${payload.media_id} → Paperless #${payload.doc_id}.` +
          (hasWork ? " Reviewed? Then apply." : " Nothing to rewrite.");
      }
    } catch (e) {
      panel.querySelector(".results").innerHTML = `<div class="action-failed">${esc(e.message)}</div>`;
      status.textContent = "";
    } finally {
      previewBtn.disabled = false;
    }
  };

  previewBtn.addEventListener("click", () => run(false));
  applyBtn.addEventListener("click", () => run(true));
  // Typing a new ID invalidates a prior preview's apply.
  input.addEventListener("input", () => { applyBtn.disabled = true; setPrimary(null); });
  input.addEventListener("keydown", (e) => { if (e.key === "Enter") run(false); });
})();
