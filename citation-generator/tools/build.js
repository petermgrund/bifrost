// Builds the citations bundle Bifrost serves: the engine, the record types, and the form rules as one ES module,
// with the guide excerpts the wizard shows on hover.
import { readFileSync, writeFileSync, mkdirSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join, relative, resolve } from 'node:path';
import { loadGuide, CHAPTERS } from './guide.js';

const ROOT = fileURLToPath(new URL('..', import.meta.url));
const SRC = join(ROOT, 'src');
export const OUT = resolve(ROOT, '../bifrost/web/static/citations/citations.js');
// The modules whose exports the bundle exports.
export const ENTRIES = ['records/index.js', 'engine.js', 'template.js', 'tables.js', 'checks.js', 'compare.js', 'store.js', 'form.js'];
const IMPORT_RE = /^import \{([^}]*)\} from '(\.{1,2}\/[^']+)';$/gm;

/**
 * Bundles the src/ ES modules into one ES module that exports every name the entries export. Supported syntax
 * (the check fails loudly otherwise): `import { a, b as c } from './x.js';` and `export function|const|let|class name`.
 */
export function bundle(entries = ENTRIES.map(e => join(SRC, e))) {
  const order = [];
  const seen = new Set();
  const visit = file => {
    if (seen.has(file)) return;
    seen.add(file);
    const code = readFileSync(file, 'utf8');
    for (const m of code.matchAll(IMPORT_RE)) visit(resolve(dirname(file), m[2]));
    order.push({ file, code });
  };
  entries.forEach(visit);
  const exportsOf = new Map();
  const parts = order.map(({ file, code }) => {
    const id = relative(SRC, file);
    let body = code.replace(IMPORT_RE, (_, names, spec) => {
      const dep = relative(SRC, resolve(dirname(file), spec));
      const depExports = exportsOf.get(dep) || [];
      const binding = names.split(',').map(s => s.trim()).filter(Boolean).map(s => {
        const asMatch = s.match(/^(\w+)\s+as\s+(\w+)$/);
        const name = asMatch ? asMatch[1] : s;
        if (!depExports.includes(name)) throw new Error(`${id}: '${name}' is not exported by ${dep}`);
        return asMatch ? `${asMatch[1]}: ${asMatch[2]}` : name;
      }).join(', ');
      return `const { ${binding} } = __modules[${JSON.stringify(dep)}];`;
    });
    if (/^\s*import\s/m.test(body)) throw new Error(`${id}: unsupported import syntax`);
    const exported = [];
    body = body.replace(/^export (async function|function|const|let|class) (\w+)/gm, (_, kind, name) => {
      exported.push(name);
      return `${kind} ${name}`;
    });
    if (/^\s*export\s/m.test(body)) throw new Error(`${id}: unsupported export syntax`);
    exportsOf.set(id, exported);
    return `__modules[${JSON.stringify(id)}] = (() => {\n${body}\nreturn { ${exported.join(', ')} };\n})();`;
  });
  const owner = new Map();
  const publics = entries.map(file => {
    const id = relative(SRC, file);
    const names = exportsOf.get(id);
    for (const name of names) {
      if (owner.has(name)) throw new Error(`${id}: '${name}' is also exported by ${owner.get(name)}`);
      owner.set(name, id);
    }
    return `export const { ${names.join(', ')} } = __modules[${JSON.stringify(id)}];`;
  });
  return `const __modules = {};\n${parts.join('\n')}\n${publics.join('\n')}\n`;
}

/** The guide excerpts the screen needs: section titles and first paragraphs, worked examples, Change log date. */
export function guideData(guide = loadGuide()) {
  const refs = [];
  for (let i = 1; i <= 13; i++) refs.push(`A${i}`);
  for (let i = 1; i <= 11; i++) refs.push(`C${i}`);
  for (const chapter of CHAPTERS) for (let i = 1; i <= 12; i++) refs.push(`${chapter} §${i}`);
  const sections = {};
  for (const ref of refs) {
    const s = guide.section(ref);
    if (s) sections[ref] = { title: s.title, text: guide.firstParagraph(ref) };
  }
  const examples = {};
  for (const e of guide.examples()) examples[e.id] = { expected: e.expected, confidence: e.confidence, citations: e.citations };
  return { changed: guide.changeLogDate(), refs: sections, examples };
}

/** The bundle with the guide excerpts as GUIDE. */
export function source() {
  return '// Built by citation-generator/tools/build.js from citation-generator/src and the style guide. Edit those, then run npm run build.\n'
    + `${bundle()}export const GUIDE = ${JSON.stringify(guideData())};\n`;
}

export function build(outFile = OUT) {
  const text = source();
  mkdirSync(dirname(outFile), { recursive: true });
  writeFileSync(outFile, text);
  return { outFile, bytes: Buffer.byteLength(text) };
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  const { outFile, bytes } = build(process.argv[2] ? resolve(process.argv[2]) : undefined);
  console.log(`Built ${relative(process.cwd(), outFile)} (${Math.round(bytes / 1024)} KB)`);
}
