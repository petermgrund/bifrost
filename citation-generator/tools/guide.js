// Reads the style guide: sections, first paragraphs, tables, worked examples, and the
// Change log date. Used by the tests and the build; never shipped to the browser.
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

export const GUIDE_PATH = fileURLToPath(new URL('../Grund-Castellano Citation Style Guide.md', import.meta.url));
export const CHAPTERS = ['B.1', 'B.2', 'B.3', 'B.4'];
const LEVEL_RE = /\b(Very High|Very Low|High|Normal|Low)\b/;
const FIELD_KEYS = {
  title: 'title', abbrev: 'abbrev', author: 'author', pubinfo: 'pubinfo', 'call number': 'callNumber', 'citation page': 'page', confidence: 'confidence',
};

/** Markdown → comparable text: drop escapes, backticks and emphasis markers; collapse whitespace. */
export function normalize(text) {
  return String(text ?? '')
    .replace(/\\([[\]_*`\\|])/g, '$1')
    .replace(/[`*]/g, '')
    .replace(/\s+/g, ' ')
    .trim();
}

export function loadGuide(path = GUIDE_PATH) {
  return parseGuide(readFileSync(path, 'utf8'));
}

export function parseGuide(markdown) {
  const lines = markdown.split('\n');
  const heads = [];
  lines.forEach((line, i) => {
    const m = line.match(/^(#{2,4}) (.+)$/);
    if (m) heads.push({ level: m[1].length, text: m[2].trim(), line: i });
  });

  function find(ref) {
    let head;
    const sub = ref.match(/^(B\.\d) §(\d+)$/);
    if (sub) {
      const part = heads.findIndex(h => h.level === 2 && h.text.startsWith(`Part ${sub[1]}:`));
      if (part < 0) return null;
      const end = heads.findIndex((h, i) => i > part && h.level === 2);
      head = heads.slice(part + 1, end < 0 ? undefined : end)
        .find(h => h.level === 3 && h.text.startsWith(`§${sub[2]} `));
    } else if (ref === 'Change log') {
      head = heads.find(h => h.level === 2 && h.text === 'Change log');
    } else {
      head = heads.find(h => h.level === 3 && h.text.split(' ')[0] === ref);
    }
    if (!head) return null;
    const next = heads.find(h => h.line > head.line && h.level <= head.level);
    return { head, body: lines.slice(head.line + 1, next ? next.line : lines.length) };
  }

  return {
    /** { ref, title, body } or null. Refs: 'A8', 'C1', 'B.1 §4', 'Change log'. */
    section(ref) {
      const s = find(ref);
      if (!s) return null;
      const name = s.head.text.replace(/^§\d+ /, '').replace(/^[AC]\d+( to C\d+)? · /, '');
      return { ref, title: `${ref} · ${normalize(name)}`, body: s.body };
    },
    /** The section's text, normalized, for pin matching. */
    sectionText(ref) {
      const s = find(ref);
      return s ? normalize(s.body.join('\n')) : null;
    },
    /** The section's lines, normalized and non-empty, for "closest line" hints. */
    sectionLines(ref) {
      const s = find(ref);
      return s ? s.body.map(normalize).filter(Boolean) : [];
    },
    firstParagraph(ref) {
      const s = find(ref);
      return s ? firstParagraph(s.body) : '';
    },
    tables(ref) {
      const s = find(ref);
      return s ? tables(s.body) : [];
    },
    examples() {
      const out = [];
      for (const chapter of CHAPTERS) {
        const s = find(`${chapter} §12`);
        if (!s) continue;
        let heading = null, body = [];
        const flush = () => { if (heading) out.push(parseExample(chapter, heading, body)); };
        for (const line of s.body) {
          const m = line.match(/^#### (.+)$/);
          if (m) { flush(); heading = m[1].trim(); body = []; } else if (heading) body.push(line);
        }
        flush();
      }
      return out;
    },
    changeLogDate() {
      const s = find('Change log');
      return s ? (tables(s.body)[0]?.rows[0]?.[0] ?? '') : '';
    },
  };
}

function blocks(body) {
  const out = [];
  let cur = [];
  for (const line of body) {
    if (line.trim()) cur.push(line);
    else if (cur.length) { out.push(cur); cur = []; }
  }
  if (cur.length) out.push(cur);
  return out;
}

const isList = line => /^\s*(- |\d+\. )/.test(line);

function firstParagraph(body) {
  const [first, second] = blocks(body);
  if (!first || /^\s*(\||```|#|>)/.test(first[0]) || isList(first[0])) return '';
  let text = normalize(first.join(' '));
  if (text.endsWith(':') && second && isList(second[0])) {
    text += ' ' + second.slice(0, 3).map(l => normalize(l.replace(/^\s*(- |\d+\. )/, ''))).join(' ');
  }
  return text;
}

function tables(body) {
  const out = [];
  let cur = null;
  for (const line of body) {
    if (line.trim().startsWith('|')) {
      const cells = line.trim().replace(/^\|/, '').replace(/\|$/, '').split('|').map(c => c.trim());
      if (!cur) cur = { header: cells.map(normalize), raw: [], rows: [] };
      else if (cells.every(c => /^:?-{3,}:?$/.test(c))) continue;
      else { cur.raw.push(cells); cur.rows.push(cells.map(normalize)); }
    } else if (cur) {
      out.push(cur);
      cur = null;
    }
  }
  if (cur) out.push(cur);
  return out;
}

/** A value cell is comparable when it is one code span or "Blank"; anything else is conditional prose. */
function cellValue(raw) {
  const t = raw.trim();
  const code = t.match(/^`([^`]*)`$/);
  if (code) return { value: normalize(code[1]) };
  if (/^Blank(\s*\([^)]*\))?$/i.test(t)) return { value: '' };
  return { skip: normalize(t) };
}

function parseExample(chapter, heading, body) {
  const id = chapter === 'B.4'
    ? `B.4 ${normalize(heading.replace(/\s*\(.*$/, ''))}`
    : `${chapter} ${heading.match(/^Example \d+/)[0]}`;
  const ex = { id, chapter, heading: normalize(heading), expected: {}, skipped: {}, confidence: '', citations: [] };
  for (const table of tables(body)) {
    const [h0, h1] = table.header;
    if ((h0 === 'Source field' || h0 === 'Field') && h1 === 'Value') {
      for (const [rawKey, rawValue] of table.raw) {
        const keys = normalize(rawKey).toLowerCase().split(' / ').map(k => FIELD_KEYS[k]).filter(Boolean);
        for (const key of keys) {
          if (key === 'confidence') { ex.confidence = (normalize(rawValue).match(LEVEL_RE) || [''])[0]; continue; }
          const cell = cellValue(rawValue);
          if ('value' in cell) ex.expected[key] = cell.value; else ex.skipped[key] = cell.skip;
        }
      }
    } else if (h0 === 'Citation' && h1 === 'Page') {
      for (const [n, page, conf] of table.raw) {
        ex.citations[Number(normalize(n)) - 1] = {
          page: cellValue(page).value ?? '',
          confidence: (normalize(conf).match(LEVEL_RE) || [''])[0],
        };
      }
    }
  }
  for (const line of body) {
    const m = line.match(/^\*\*(FRN|SRN)(?: (\d+))?:\*\*\s*(.+)$/);
    if (!m) continue;
    const field = m[1].toLowerCase(), text = normalize(m[3]);
    if (m[2]) {
      const i = Number(m[2]) - 1;
      ex.citations[i] = { ...(ex.citations[i] || {}), [field]: text };
    } else {
      ex.expected[field] = text;
    }
  }
  return ex;
}
