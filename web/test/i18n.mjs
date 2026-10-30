// web/test (not deployed): the page's translations, no browser. node web/test/i18n.mjs [LANG ...]
// Every i18n/<lang>.json of the page's languages (js/i18n.js LANGS) has exactly en.json's keys, in its order, none
// empty, and each string the same {placeholders} as the English one; content/features.json has a title and a body
// for every language and every feature (with the English one's placeholders), an alt for every medium, and the note.
import fs from 'node:fs';
import path from 'node:path';
const web = path.join(path.dirname(new URL(import.meta.url).pathname), '..');
const src = fs.readFileSync(path.join(web, 'js/i18n.js'), 'utf8');
const all = JSON.parse(src.match(/export const LANGS = (\[[^\]]*\])/)[1].replace(/'/g, '"'));
const langs = process.argv.slice(2).length ? process.argv.slice(2) : all;
const read = (p) => JSON.parse(fs.readFileSync(path.join(web, p), 'utf8'));
const holes = (s) => [...String(s).matchAll(/\{(\w+)\}/g)].map((m) => m[1]).sort().join();
let failed = 0;
const bad = (what) => { console.log(`FAIL ${what}`); failed++; };
const en = read('i18n/en.json');
for (const lang of langs) {
  let t;
  try { t = read(`i18n/${lang}.json`); } catch (e) { bad(`${lang}: i18n/${lang}.json: ${e.message}`); continue; }
  const missing = Object.keys(en).filter((k) => !(k in t)), extra = Object.keys(t).filter((k) => !(k in en));
  if (missing.length) bad(`${lang}: missing ${missing.join(', ')}`);
  if (extra.length) bad(`${lang}: not in en.json: ${extra.join(', ')}`);
  if (!missing.length && Object.keys(t).join('\n') !== Object.keys(en).join('\n')) bad(`${lang}: the keys are not in en.json's order`);
  for (const [k, v] of Object.entries(t)) {
    if (typeof v !== 'string' || !v.trim()) bad(`${lang}: ${k} is empty`);
    else if (k in en && holes(v) !== holes(en[k])) bad(`${lang}: ${k} has {${holes(v)}}, en has {${holes(en[k])}}`);
  }
}
const f = read('content/features.json');
for (const lang of langs) {
  if (!f.note?.[lang]) bad(`${lang}: features.json note`);
  for (const x of f.features) {
    const t = x[lang];
    if (!t?.title || !t?.body) { bad(`${lang}: feature ${x.id} has no title or body`); continue; }
    for (const k of ['title', 'body']) if (holes(t[k]) !== holes(x.en[k])) bad(`${lang}: feature ${x.id} ${k} has {${holes(t[k])}}, en has {${holes(x.en[k])}}`);
    x.media.forEach((m, i) => { if (typeof m.alt === 'object' && !m.alt[lang]) bad(`${lang}: feature ${x.id} medium ${i} has no alt`); });
  }
}
console.log(failed ? `${failed} FAILED` : `all ok: ${langs.join(' ')}`);
process.exit(failed ? 1 : 0);
