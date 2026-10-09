// Readable failure messages for the guide checks.

/** The differing region of two strings, with some context either side. */
export function diffExcerpt(want, got, context = 40) {
  let start = 0;
  while (start < want.length && start < got.length && want[start] === got[start]) start++;
  let end = 0;
  while (end < want.length - start && end < got.length - start && want[want.length - 1 - end] === got[got.length - 1 - end]) end++;
  const clip = text => {
    const from = Math.max(0, start - context);
    const to = Math.min(text.length, text.length - end + context);
    return (from > 0 ? '…' : '') + text.slice(from, to) + (to < text.length ? '…' : '');
  };
  return { want: clip(want), got: clip(got) };
}

export function differsMessage(label, want, got) {
  const d = diffExcerpt(want, got);
  return `${label}\n    guide:     ${d.want}\n    generator: ${d.got}`;
}

/** The line in `lines` most similar to `text` (character bigram overlap). */
export function closestLine(text, lines) {
  const grams = s => {
    const out = new Map();
    for (let i = 0; i < s.length - 1; i++) out.set(s.slice(i, i + 2), (out.get(s.slice(i, i + 2)) || 0) + 1);
    return out;
  };
  const a = grams(text);
  let best = '', bestScore = -1;
  for (const line of lines) {
    const b = grams(line);
    let shared = 0;
    for (const [g, n] of a) shared += Math.min(n, b.get(g) || 0);
    const score = (2 * shared) / (text.length + line.length || 1);
    if (score > bestScore) { best = line; bestScore = score; }
  }
  return best;
}
