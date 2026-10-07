// Grids in page fractions: a frame quad, column lines [top, bottom] and row lines [left, right] along it

const sub = (a, b) => [a[0] - b[0], a[1] - b[1]];
const cross = (a, b) => a[0] * b[1] - a[1] * b[0];
const side = ([a, b], p) => cross(sub(b, a), sub(p, a));

export const lerp = (a, b, t) => [a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t];
export const clamp = (x, lo, hi) => Math.min(hi, Math.max(lo, x));
export const clamp01 = (p) => [clamp(p[0], 0, 1), clamp(p[1], 0, 1)];
export const EPS = 0.002;

export function colSeg(frame, u) {
  const [tl, tr, br, bl] = frame;
  return [lerp(tl, tr, u[0]), lerp(bl, br, u[1])];
}

export function rowSeg(frame, v) {
  const [tl, tr, br, bl] = frame;
  return [lerp(tl, bl, v[0]), lerp(tr, br, v[1])];
}

export function meet([p1, p2], [p3, p4]) {
  const r = sub(p2, p1);
  const s = sub(p4, p3);
  const d = cross(r, s);
  if (Math.abs(d) < 1e-12) return lerp(p1, p2, 0.5);
  const t = cross(sub(p3, p1), s) / d;
  return [p1[0] + r[0] * t, p1[1] + r[1] * t];
}

export const colEdges = (g) => [...g.cols.map((c) => c.u), [1, 1]];
export const rowEdges = (g) => [...g.rows.map((r) => r.v), [1, 1]];

const center = (frame) => lerp(lerp(frame[0], frame[2], 0.5), lerp(frame[1], frame[3], 0.5), 0.5);
const colSign = (frame) => Math.sign(side(colSeg(frame, [0, 0]), center(frame))) || 1;
const rowSign = (frame) => Math.sign(side(rowSeg(frame, [0, 0]), center(frame))) || 1;

const cache = new WeakMap();

export function points(g) {
  let pts = cache.get(g);
  if (!pts) {
    const cs = colEdges(g).map((u) => colSeg(g.frame, u));
    pts = rowEdges(g).map((v) => {
      const rs = rowSeg(g.frame, v);
      return cs.map((c) => meet(c, rs));
    });
    cache.set(g, pts);
  }
  return pts;
}

export function locate(g, p) {
  const cs = colEdges(g).map((u) => colSeg(g.frame, u));
  const sx = colSign(g.frame);
  let col = -1;
  while (col + 1 < cs.length && side(cs[col + 1], p) * sx > 0) col++;
  if (col < 0 || col >= cs.length - 1) return null;
  const rs = rowEdges(g).map((v) => rowSeg(g.frame, v));
  const sy = rowSign(g.frame);
  let row = -1;
  while (row + 1 < rs.length && side(rs[row + 1], p) * sy > 0) row++;
  if (row < 0 || row >= rs.length - 1) return null;
  return { row, col };
}

function bisect(f, lo, hi) {
  let flo = f(lo);
  for (let i = 0; i < 40; i++) {
    const m = (lo + hi) / 2;
    const fm = f(m);
    if ((fm > 0) === (flo > 0)) { lo = m; flo = fm; } else hi = m;
  }
  return (lo + hi) / 2;
}

const kindOf = (kind) => (kind === 'col'
  ? { seg: colSeg, sign: colSign, edges: colEdges }
  : { seg: rowSeg, sign: rowSign, edges: rowEdges });

// a new line through p inside cell span i, tilted between its two neighbours
export function split(g, kind, i, p) {
  const { seg, sign, edges } = kindOf(kind);
  const es = edges(g);
  const [a, b] = [es[i], es[i + 1]];
  const sg = sign(g.frame);
  const t = bisect((x) => side(seg(g.frame, lerp(a, b, x)), p) * sg, 0, 1);
  return lerp(a, b, clamp(t, 0.02, 0.98));
}

function bounds(es, k) {
  return [es[k - 1].map((x) => x + EPS), es[k + 1].map((x) => x - EPS)];
}

// line k moved through p, keeping its tilt, between its neighbours
export function slide(g, kind, k, p) {
  const { seg, sign, edges } = kindOf(kind);
  const es = edges(g);
  const cur = es[k];
  const [lo2, hi2] = bounds(es, k);
  const lo = Math.max(lo2[0] - cur[0], lo2[1] - cur[1]);
  const hi = Math.min(hi2[0] - cur[0], hi2[1] - cur[1]);
  if (lo >= hi) return cur;
  const sg = sign(g.frame);
  const f = (d) => side(seg(g.frame, [cur[0] + d, cur[1] + d]), p) * sg;
  const d = f(lo) <= 0 ? lo : f(hi) >= 0 ? hi : bisect(f, lo, hi);
  return [cur[0] + d, cur[1] + d];
}

const along = ([a, b], x) => {
  const d = sub(b, a);
  const n = d[0] * d[0] + d[1] * d[1];
  return n ? ((x[0] - a[0]) * d[0] + (x[1] - a[1]) * d[1]) / n : 0;
};

// line k with one end (0: top/left, 1: bottom/right) moved toward p, pivoting on the other
export function pivot(g, kind, k, end, p) {
  const { seg, edges } = kindOf(kind);
  const es = edges(g);
  const s = seg(g.frame, es[k]);
  const [tl, tr, br, bl] = g.frame;
  const rim = kind === 'col' ? (end === 0 ? [tl, tr] : [bl, br]) : (end === 0 ? [tl, bl] : [tr, br]);
  const [lo, hi] = bounds(es, k);
  const out = [...es[k]];
  out[end] = clamp(along(rim, meet([s[1 - end], p], rim)), lo[end], hi[end]);
  return out;
}

export function distToSeg(p, a, b) {
  const d = sub(b, a);
  const n = d[0] * d[0] + d[1] * d[1];
  const t = n ? clamp(((p[0] - a[0]) * d[0] + (p[1] - a[1]) * d[1]) / n, 0, 1) : 0;
  return Math.hypot(p[0] - a[0] - t * d[0], p[1] - a[1] - t * d[1]);
}

// x where a line through a and b crosses height y, or y where it crosses x
export function xAt(a, b, y) {
  return Math.abs(b[1] - a[1]) < 1e-9 ? a[0] : a[0] + ((y - a[1]) * (b[0] - a[0])) / (b[1] - a[1]);
}

export function yAt(a, b, x) {
  return Math.abs(b[0] - a[0]) < 1e-9 ? a[1] : a[1] + ((x - a[0]) * (b[1] - a[1])) / (b[0] - a[0]);
}
