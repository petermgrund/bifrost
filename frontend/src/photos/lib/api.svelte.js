export const activity = $state({ running: 0 });

async function failure(resp) {
  const text = await resp.text();
  try {
    const { detail } = JSON.parse(text);
    if (typeof detail === 'string') return detail;
    if (Array.isArray(detail)) return detail.map((d) => d.msg).join('; ');
  } catch {
    return text || `${resp.status} ${resp.statusText}`;
  }
  return text;
}

async function request(path, opts = {}) {
  const resp = await fetch(path, { headers: { 'Content-Type': 'application/json' }, ...opts });
  if (!resp.ok) throw new Error(await failure(resp));
  return resp.json();
}

async function tracked(path, opts) {
  let counted = false;
  const grace = setTimeout(() => {
    counted = true;
    activity.running += 1;
  }, 400);
  try {
    return await request(path, opts);
  } finally {
    clearTimeout(grace);
    if (counted) activity.running -= 1;
  }
}

export const get = (path) => request(path);
export const post = (path, body) => tracked(path, { method: 'POST', body: JSON.stringify(body ?? {}) });
export const put = (path, body) => tracked(path, { method: 'PUT', body: JSON.stringify(body ?? {}) });
export const del = (path) => tracked(path, { method: 'DELETE' });
export const upload = (path, file) =>
  tracked(path, { method: 'POST', body: file, headers: { 'Content-Type': 'application/octet-stream' } });

export function qs(params) {
  const kept = Object.entries(params).filter(([, v]) => v !== '' && v !== null && v !== undefined);
  return new URLSearchParams(kept.map(([k, v]) => [k, String(v)])).toString();
}
