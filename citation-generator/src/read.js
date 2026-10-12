// Reads a citation the wizard built (its page string, reference notes, and Gramps Source) back into a draft, for
// citations made before the wizard kept its drafts. A reading is exact when it rebuilds the same page string, FRN,
// and SRN; one whose page string and FRN rebuild is close (an SRN edited by hand); anything less is none.
import { RECORDS, recordById } from './records/index.js';
import { REFERENCE_VALUES, STANDARD_VALUES, ENGINE_TOKENS, newDraft, setVariant, resolveType, inputFields, recordNoun, subjectOf, srnSubjectOf, pageLocators, buildOutputs } from './engine.js';
import { COPY_FORMS, MEDIA, PLATFORMS } from './tables.js';
import { fill, hasGap } from './template.js';

const BLANK = { name: '', noun: '', copy: '', nonHead: false, head: '', which: '', says: '', evidence: '', afterNoun: false };
// Readings finished and checked per record type and page form before giving up on it.
const LIMIT = 240;
// What follows the FRN: Comment after FRN, a sentence after the FRN's own.
const COMMENT = '(?:(?<=[.?!]) (?<comment>\\p{Lu}.*))?';
const escapeRe = text => String(text).replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
const filled = value => String(value ?? '').trim() !== '';

/** The template once for each way its «optional» parts can be in or out (as written, when it has many). */
function shapes(template) {
  const parts = String(template ?? '').split(/(«[^»]*»)/);
  if (parts.filter(p => p.startsWith('«')).length > 6) return [String(template ?? '')];
  let out = [''];
  for (const part of parts) {
    if (part.startsWith('«')) out = out.flatMap(s => [s + part.slice(1, -1), s]);
    else out = out.map(s => s + part);
  }
  return out;
}

/** A pattern for a template: known values as their own text, every other key as a capture that repeats where it recurs. */
function pattern(template, known) {
  let src = '';
  const seen = new Set();
  for (const part of template.split(/(«|»|\{\w+\})/)) {
    if (part === '«') src += '(?:';
    else if (part === '»') src += ')?';
    else if (/^\{\w+\}$/.test(part)) {
      const key = part.slice(1, -1);
      if (filled(known[key])) src += escapeRe(known[key]);
      else if (seen.has(key)) src += `\\k<${key}>`;
      else {
        seen.add(key);
        src += `(?<${key}>.+?)`;
      }
    } else src += escapeRe(part);
  }
  return src;
}

/** Every reading of the text against the template's shapes: its unknown keys as the text gives them. */
function readings(template, known, text, tail = '') {
  if (!template || typeof text !== 'string' || !text) return [];
  const out = [], seen = new Set();
  for (const shape of shapes(template)) {
    let re;
    try { re = new RegExp(`^${pattern(shape, known)}${tail}$`, 'su'); } catch { continue; }
    const m = re.exec(text);
    if (!m) continue;
    const got = Object.fromEntries(Object.entries(m.groups || {}).filter(([, v]) => v !== undefined));
    const key = JSON.stringify(got);
    if (!seen.has(key)) {
      seen.add(key);
      out.push(got);
    }
  }
  return out;
}

/** The text as it was before endWith added what it is cited for, paired with that: the reading without it comes first. */
function citedOff(text) {
  const out = [[text, '']];
  const quoted = /^(.*)" \(([^()]+)\)\.$/s.exec(text);
  if (quoted) out.push([`${quoted[1]}."`, quoted[2]]);
  const dotted = /^(.*) \(([^()]+)\)\.$/s.exec(text);
  if (dotted) out.push([`${dotted[1]}.`, dotted[2]]);
  const bare = /^(.*) \(([^()]+)\)$/s.exec(text);
  if (bare) out.push([bare[1], bare[2]]);
  return out;
}

/** Page and image behind a page locator ("p. 57 (image 62)", "p. 57", "image 62"). */
function locatorsOf(text) {
  const forms = [[/^p\. (.+) \(image (.+)\)$/s, ['page', 'image']], [/^p\. (.+)$/s, ['page']], [/^image (.+)$/s, ['image']]];
  for (const [re, keys] of forms) {
    const m = re.exec(text);
    if (!m) continue;
    const loc = { page: '', image: '' };
    keys.forEach((key, i) => { loc[key] = m[i + 1]; });
    if (pageLocators(loc.page, loc.image).pageLoc === text) return loc;
  }
  return null;
}

const nounsOf = t => [...(t.nouns || [''])].sort((a, b) => b.length - a.length);
const formsOf = noun => (noun ? ['', ...COPY_FORMS] : ['']);

/** Ways a subject could have been built: name, parentheses, record noun and its form, a non-head's household. Longer nouns first. */
function subjects(t, text) {
  const out = t.optionalSubject && !text ? [{ ...BLANK }] : [];
  for (const noun of nounsOf(t)) {
    for (const copy of formsOf(noun)) {
      const full = recordNoun(noun, copy);
      for (const nonHead of noun === 'household' ? [false, true] : [false]) {
        const tail = nonHead ? ` in (?<head>.+?) ${escapeRe(full)}` : full ? ` ${escapeRe(full)}` : '';
        for (const afterNoun of full ? [false, true] : [false]) {
          const re = afterNoun ? `^(?<name>.+?)${tail}(?: \\((?<par>.+)\\))?$` : `^(?<name>.+?)(?: \\((?<par>.+)\\))?${tail}$`;
          const m = new RegExp(re, 's').exec(text);
          if (!m) continue;
          const s = { ...BLANK, name: m.groups.name, noun, copy, nonHead, head: m.groups.head || '', which: m.groups.par || '', afterNoun };
          if (subjectOf(t, s) === text) out.push(s);
        }
      }
    }
  }
  return out;
}

/** Ways "[noun] of [name]" could have been built. */
function entryofs(t, text) {
  const out = [];
  for (const noun of nounsOf(t)) {
    for (const copy of formsOf(noun)) {
      const full = recordNoun(noun, copy);
      if (!full) out.push({ ...BLANK, name: text });
      else if (text.startsWith(`${full} of `)) out.push({ ...BLANK, name: text.slice(full.length + 4), noun, copy });
    }
  }
  return out;
}

/**
 * What the draft already gives a template: its values, and what the engine builds from them (name, noun, subject,
 * "[noun] of [name]", medium, locators, the platform's homepage, an Author with no part missing).
 */
function knownOf(t, d) {
  const out = Object.fromEntries(Object.entries(d.values).filter(([, v]) => filled(v)).map(([k, v]) => [k, String(v).trim()]));
  const s = d.subject, name = String(s.name ?? '').trim(), noun = recordNoun(s.noun, s.copy);
  if (name) Object.assign(out, { name, subject: subjectOf(t, s), entryof: noun ? `${noun} of ${name}` : name });
  if (noun) out.noun = noun;
  out.medium = noun && ['index entry', 'transcript'].includes(s.copy) ? 'database' : 'digital image';
  if (filled(out.page) || filled(out.image)) Object.assign(out, pageLocators(out.page, out.image));
  if (PLATFORMS[out.platform]) out.home = PLATFORMS[out.platform];
  const author = fill(t.author, out);
  if (author && !hasGap(author)) out.author = author;
  return out;
}

/** Splits the page subject's parentheses into which entry, the part the SRN keeps (B.1 §10), and the rest. */
function whichFrom(t, d, srnSubject) {
  if (!filled(d.subject.name)) {
    const [s] = subjects(t, srnSubject);
    if (s) d.subject = { ...d.subject, ...s };
    return Boolean(s);
  }
  const parts = d.subject.which ? d.subject.which.split(', ') : [];
  for (let i = parts.length; i >= 0; i--) {
    const s = { ...d.subject, which: parts.slice(0, i).join(', '), says: parts.slice(i).join(', '), evidence: '' };
    if (srnSubjectOf(t, s) === srnSubject) {
      d.subject = s;
      return true;
    }
  }
  return false;
}

/** The person a template's {subject}, {entryof}, or {name} gives, when the draft has none yet. */
function personFrom(t, d, got) {
  if (filled(d.subject.name)) return;
  const [s] = got.subject !== undefined ? subjects(t, got.subject) : got.entryof !== undefined ? entryofs(t, got.entryof) : [];
  if (s) d.subject = { ...d.subject, ...s };
  else if (got.name !== undefined) d.subject.name = got.name;
}

function* search(candidate, stages, i = 0) {
  if (i === stages.length) {
    yield candidate;
    return;
  }
  for (const next of stages[i](candidate)) yield* search(next, stages, i + 1);
}

/** The stages that read one record type and page form from a citation, and settle, which finishes a candidate's draft. */
function readerFor(type, variant, cited) {
  const base = newDraft(type);
  if (variant) setVariant(type, base, variant);
  const defaults = { ...base.values };
  for (const key of REFERENCE_VALUES) base.values[key] = '';
  const t = resolveType(type, base);
  const typed = new Set([...inputFields(type).map(([key]) => key), ...STANDARD_VALUES]);
  const engine = new Set(ENGINE_TOKENS);
  // A copy of the candidate with a reading's inputs filled where still blank, and its derived values kept for probe.
  const taking = (c, got) => {
    const d = structuredClone(c.d), derived = { ...c.derived };
    for (const [key, value] of Object.entries(got || {})) {
      if (typed.has(key)) {
        if (!filled(d.values[key])) d.values[key] = value;
      } else if (!engine.has(key) && !(key in derived)) derived[key] = value;
    }
    return { d, derived };
  };

  // What the FRN says the citation documents ends the page string too, so that reading goes first.
  const documented = /\(documenting ([^()]+)\)/.exec(cited.frn)?.[1];
  const pageTexts = citedOff(cited.page).sort((a, b) => (b[1] === documented) - (a[1] === documented));
  const page = c => pageTexts.flatMap(([text, citedFor]) => readings(t.page, {}, text).flatMap((got) => {
    const loc = got.pageLoc === undefined ? {} : locatorsOf(got.pageLoc);
    if (!loc) return [];
    const people = got.subject !== undefined ? subjects(t, got.subject)
      : got.entryof !== undefined ? entryofs(t, got.entryof) : [got.name !== undefined ? { ...c.d.subject, name: got.name } : { ...c.d.subject }];
    return people.flatMap((person) => {
      const n = taking(c, got);
      Object.assign(n.d.values, loc, { citedFor });
      n.d.subject = { ...n.d.subject, ...person };
      if (got.noun !== undefined) {
        const form = nounsOf(t).flatMap(noun => formsOf(noun).map(copy => ({ noun, copy }))).find(f => recordNoun(f.noun, f.copy) === got.noun);
        if (!form) return [];
        Object.assign(n.d.subject, form);
      }
      return [n];
    });
  }));

  const pubinfo = (c) => {
    const text = cited.pubinfo;
    if (!text) return c;
    if (t.pubinfo !== undefined) {
      const [got] = readings(t.pubinfo, knownOf(t, c.d), text);
      return got ? taking(c, got) : c;
    }
    const film = /^Microfilm, (.+)\.$/s.exec(text);
    if (film) {
      const n = taking(c, { archive: film[1] });
      if (!filled(n.d.values.pubmedium)) n.d.values.pubmedium = 'Microfilm';
      return n;
    }
    const online = /^(.+?), (.+) \((\S+)\)\.$/s.exec(text);
    if (!online || !MEDIA.includes(online[1])) return c;
    const n = taking(c, { platform: online[2] });
    if (!filled(n.d.values.pubmedium)) n.d.values.pubmedium = online[1];
    return n;
  };

  // The Source fields, read once early (they pin dates and names the FRN runs together) and once at the end.
  const source = (c) => {
    let n = c;
    for (const key of ['title', 'abbrev', 'author']) {
      if (!cited[key] || !t[key]) continue;
      const [got] = readings(t[key], knownOf(t, n.d), cited[key]);
      if (got) n = taking(n, got);
    }
    n = pubinfo(n);
    if (cited.call && typed.has('call') && !filled(n.d.values.call)) n = taking(n, { call: cited.call });
    return n === c ? [c] : [n, c];
  };

  const forms = [[t.frn, '']];
  if (t.frnMicrofilm) forms.push([t.frnMicrofilm, 'Microfilm']);
  const frn = c => forms.flatMap(([template, medium]) => {
    const chosen = String(c.d.values.pubmedium ?? '');
    if (medium ? filled(chosen) && chosen !== medium : chosen === 'Microfilm' && t.frnMicrofilm) return [];
    const start = medium ? taking(c, { pubmedium: medium }) : c;
    const known = knownOf(t, start.d);
    const all = [...readings(template, known, cited.frn, COMMENT), ...readings(template, known, cited.frn)];
    return all.filter((got, i) => all.findIndex(other => JSON.stringify(other) === JSON.stringify(got)) === i).map((got) => {
      const n = taking(start, got);
      personFrom(t, n.d, got);
      return n;
    });
  });
  const frnOrNot = (c) => {
    const out = frn(c);
    return out.length ? out : [c];
  };

  const srn = (c) => {
    const out = citedOff(cited.srn).filter(([, citedFor]) => citedFor === c.d.values.citedFor).flatMap(([text]) =>
      readings(t.srn, knownOf(t, c.d), text).flatMap((got) => {
        const n = taking(c, got);
        personFrom(t, n.d, got);
        return got.srnSubject !== undefined && !whichFrom(t, n.d, got.srnSubject) ? [] : [n];
      }));
    return out.length ? out : [c];
  };

  // Derived values the inputs don't give yet (a topic that is the entry details, a short channel name) go to the blank input that gives them.
  const probe = (c) => {
    if (!t.derive) return;
    const v = c.d.values;
    const derivedOf = () => {
      const trimmed = Object.fromEntries(Object.entries(v).map(([k, x]) => [k, typeof x === 'string' ? x.trim() : x]));
      return t.derive({ ...trimmed, name: String(c.d.subject.name ?? '').trim(), noun: recordNoun(c.d.subject.noun, c.d.subject.copy) });
    };
    for (const [token, value] of Object.entries(c.derived)) {
      if (derivedOf()[token] === value) continue;
      for (const key of typed) {
        if (filled(v[key]) || REFERENCE_VALUES.includes(key)) continue;
        v[key] = value;
        if (derivedOf()[token] === value) break;
        v[key] = '';
      }
    }
  };

  const settle = (c) => {
    const d = structuredClone(c.d);
    probe({ d, derived: c.derived });
    for (const key of REFERENCE_VALUES) if (!filled(d.values[key])) d.values[key] = defaults[key];
    return d;
  };
  return { t, start: { d: base, derived: {} }, page, source, frn, frnOrNot, srn, settle };
}

/** The first reading of one record type and page form that rebuilds the citation: exact, or else close. */
function readAs(type, variant, cited) {
  const { start, page, source, frnOrNot, srn, settle } = readerFor(type, variant, cited);
  let tried = 0, close = null;
  for (const c of search(start, [page, source, frnOrNot, srn, source])) {
    const d = settle(c);
    const o = buildOutputs(type, d);
    if (o.page === cited.page) {
      if (o.frn === cited.frn && o.srn === cited.srn) return { draft: d, exact: true };
      if (!close && o.frn === cited.frn) close = { draft: d, exact: false };
    }
    if (++tried >= LIMIT) break;
  }
  return close;
}

/**
 * The record type and draft that rebuild a citation ({ page, frn, srn } plus its Source's title, abbrev, author,
 * pubinfo, call), trying the preferred record type first: { type, draft, exact }, the first exact reading or else the
 * first close one; null when there is neither.
 */
export function readCitation(cited, preferred = '') {
  if (!cited?.page || !cited.frn || !cited.srn) return null;
  const order = [recordById(preferred), ...RECORDS.filter(r => r.id !== preferred)].filter(Boolean);
  let close = null;
  for (const type of order) {
    for (const variant of type.pageVariants ? type.pageVariants.map(v => v.key) : ['']) {
      const got = readAs(type, variant, cited);
      if (!got) continue;
      const reading = { type: type.id, draft: { ...got.draft, overrides: {}, example: '' }, exact: got.exact };
      if (got.exact) return reading;
      close ||= reading;
    }
  }
  return close;
}

/** The fixed text of a template, which tells how surely a text that fits it was built from it. */
const fixedText = template => String(template ?? '').replace(/\{\w+\}|«|»/g, '').length;

/**
 * For a citation whose page string was edited by hand: the record type whose FRN (with at least 20 characters of
 * fixed text) the FRN fits with the most fixed text, and what that FRN, the Source, and the SRN give; null when none fits.
 */
export function readByFrn(cited, preferred = '') {
  if (!cited?.frn) return null;
  const order = [recordById(preferred), ...RECORDS.filter(r => r.id !== preferred)].filter(Boolean);
  let best = null;
  for (const type of order) {
    for (const variant of type.pageVariants ? type.pageVariants.map(v => v.key) : ['']) {
      const reader = readerFor(type, variant, cited);
      const weight = Math.max(fixedText(reader.t.frn), fixedText(reader.t.frnMicrofilm));
      if (weight < 20 || (best && weight <= best.weight)) continue;
      const [c] = search(reader.start, [reader.frn, reader.source, reader.srn]);
      if (c) best = { weight, reading: { type: type.id, draft: { ...reader.settle(c), overrides: {}, example: '' }, exact: false } };
    }
  }
  return best?.reading || null;
}

/**
 * What any guide-shaped citation gives without its record type: page and image, and the name that leads the last part
 * of the page string, and the URL and access date from the FRN.
 */
export function readLoosely(cited) {
  const out = {};
  const page = cited?.page || '';
  const loc = /(?:^|, )(?:p\. ([^\s,()]+)(?: \(image ([^\s,()]+)\))?|image ([^\s,()]+))(?=,|$)/.exec(page);
  if (loc) Object.assign(out, { page: loc[1] || '', image: loc[2] || loc[3] || '' });
  const last = page.replace(/\([^()]*\)/g, '').split(', ').pop().trim();
  const name = /^(?:\p{Lu}[\p{L}'’.-]*(?: |$))+/u.exec(last)?.[0].trim();
  if (name && !/^\d/.test(last.slice(name.length).trim())) out.name = name;
  const link = /\((https?:\/\/\S+) : accessed ([^)]+)\)/.exec(cited?.frn || '');
  if (link) Object.assign(out, { url: link[1], accessed: link[2] });
  return out;
}
