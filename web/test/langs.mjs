// web/test (not deployed): the page in each of its languages, headless Chromium, no discs. puppeteer-core from
// build/stage9/node/node_modules. node web/test/langs.mjs URL [SHOTS_DIR]
//   1. the first visit follows the browser's languages (de-DE -> de, pt-PT -> pt-br, ca-ES -> ca, nl -> en) and a
//      remembered choice wins over them
//   2. the menu lists the eight by their own names; choosing each one switches the page: <html lang>, every
//      data-i18n string and attribute is that language's (none left as its key), the cards' titles are that
//      language's (with {n} and {languages} filled; a hidden card is not shown)
//   3. the choice is remembered after a reload
// With SHOTS_DIR, the hero and the four slots in Japanese, German and Brazilian Portuguese, desktop and phone width.
import puppeteer from './browser.mjs';
import fs from 'node:fs';
import path from 'node:path';
const [url, shots] = process.argv.slice(2);
const web = path.join(path.dirname(new URL(import.meta.url).pathname), '..');
const read = (p) => JSON.parse(fs.readFileSync(path.join(web, p), 'utf8'));
const { LANGS, NAMES } = await import(path.join(web, 'js/i18n.js'));
const discs = read('data/discs.json'), features = read('content/features.json'), en = read('i18n/en.json');
const BUILD = path.join(web, '../build');   // (the snap Chromium cannot read /tmp)
fs.mkdirSync(BUILD, { recursive: true });
const profile = fs.mkdtempSync(path.join(BUILD, 'langs-profile-'));
const b = await puppeteer.launch({ executablePath: process.env.CHROMIUM || '/snap/bin/chromium', headless: 'new', args: ['--no-sandbox', '--disable-gpu'],
  userDataDir: profile });
const p = await b.newPage();
p.on('pageerror', (e) => console.log('[pageerror]', e.message));
let failed = 0;
const ok = (cond, what) => { console.log(`${cond ? 'ok  ' : 'FAIL'} ${what}`); if (!cond) failed++; };
// the browser's languages, as the test sets them (test.navlangs in localStorage, read before the page's scripts)
await p.evaluateOnNewDocument(() => {
  let l = null;
  try { l = JSON.parse(localStorage.getItem('test.navlangs')); } catch { /* not this origin */ }
  if (l) {
    Object.defineProperty(navigator, 'languages', { get: () => l });
    Object.defineProperty(navigator, 'language', { get: () => l[0] });
  }
});
// a visit with these browser languages; nothing remembered unless keep
const visit = async (langs, keep = false) => {
  await p.goto(url, { waitUntil: 'networkidle0' });
  await p.evaluate((l, keep) => { if (!keep) localStorage.removeItem('horizon.lang'); localStorage.setItem('test.navlangs', JSON.stringify(l)); }, langs, keep);
  await p.reload({ waitUntil: 'networkidle0' });
  await p.waitForFunction(() => document.querySelector('h1').textContent !== '');
};
const page = () => p.evaluate(() => ({ lang: document.documentElement.lang, menu: document.querySelector('#lang').value }));

// 1. the browser's language
for (const [langs, want] of [[['de-DE', 'en'], 'de'], [['pt-PT'], 'pt-br'], [['ca-ES', 'es'], 'ca'], [['ja'], 'ja'], [['nl-NL', 'nl'], 'en'], [['es-MX'], 'es']]) {
  await visit(langs);
  const s = await page();
  ok(s.menu === want, `browser ${langs}: the page in ${want}: ${s.menu} (html lang ${s.lang})`);
}
await p.select('#lang', 'it');
await visit(['de-DE'], true);
ok((await page()).menu === 'it', 'a remembered choice (it) wins over the browser (de)');

// 2. each language
await visit(['en-US']);
const opts = await p.$$eval('#lang option', (os) => os.map((o) => [o.value, o.textContent, o.lang]));
ok(JSON.stringify(opts.map((o) => o[0])) === JSON.stringify(LANGS) && opts.every(([v, t]) => t === NAMES[v]),
   `the menu: ${opts.map((o) => o[1]).join(', ')}`);
ok(await p.$eval('#lang', (s) => !!s.getAttribute('aria-label')), 'the menu has its label');
for (const lang of LANGS) {
  await p.select('#lang', lang);
  await p.waitForFunction((t) => document.documentElement.lang === t, {}, lang.replace(/-(\w+)$/, (m, r) => `-${r.toUpperCase()}`));
  const t = read(`i18n/${lang}.json`);
  const got = await p.evaluate(() => ({
    texts: [...document.querySelectorAll('[data-i18n]')].map((e) => [e.dataset.i18n, e.textContent]),
    attrs: [...document.querySelectorAll('[data-i18n-attr]')].map((e) => { const [a, k] = e.dataset.i18nAttr.split(':'); return [k, e.getAttribute(a)]; }),
    cards: [...document.querySelectorAll('.feature h3')].map((h) => h.textContent),
    braces: /\{\w+\}/.test(document.querySelector('main').innerText),
  }));
  const wrong = [...got.texts, ...got.attrs].filter(([k, v]) => v !== t[k]);
  ok(!wrong.length, `${lang}: every string is this language's (${got.texts.length + got.attrs.length})${wrong.length ? ': ' + wrong.slice(0, 3).map(([k, v]) => `${k}=${v}`).join('; ') : ''}`);
  ok(lang === 'en' || t['hero.title'] !== en['hero.title'], `${lang}: the title is translated: ${t['hero.title']}`);
  const want = features.features.filter((f) => !f.hidden).map((f) => (f[lang] || f.en).title);
  ok(got.cards.length === want.length && got.cards.every((c, i) => !want[i].includes('{') ? c === want[i] : !/\{/.test(c)),
     `${lang}: the cards are this language's: ${got.cards.find((c) => /\d/.test(c)) || got.cards[0]}`);
  ok(!got.braces, `${lang}: no {placeholder} left in the page`);
}

// 3. remembered
await p.select('#lang', 'ja');
await p.reload({ waitUntil: 'networkidle0' });
ok((await page()).menu === 'ja', 'the choice is remembered after a reload');

// screenshots: the hero and the slots
if (shots) {
  fs.mkdirSync(shots, { recursive: true });
  for (const lang of ['ja', 'de', 'pt-br']) {
    await p.select('#lang', lang);
    for (const phone of [false, true]) {
      await p.setViewport(phone ? { width: 390, height: 844, deviceScaleFactor: 2 } : { width: 1280, height: 900 });
      await p.evaluate(() => { document.activeElement?.blur(); window.scrollTo(0, 0); });
      await new Promise((r) => setTimeout(r, 500));
      const box = await p.$eval('#add-button', (e) => { const r = e.getBoundingClientRect(); return r.bottom + window.scrollY; });
      const file = `${shots}/${lang}-hero-slots${phone ? '-phone' : ''}.png`;
      await p.screenshot({ path: file, clip: { x: 0, y: 0, width: phone ? 390 : 1280, height: Math.ceil(box + 24) }, captureBeyondViewport: true });
      console.log(file);
    }
  }
}
await b.close();
fs.rmSync(profile, { recursive: true, force: true });
console.log(failed ? `${failed} FAILED` : 'all ok');
process.exit(failed ? 1 : 0);
