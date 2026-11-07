// web/test (not deployed): what the page says when a build cannot have the room it needs, headless Chromium, the real
// page with an engine and the four discs. node web/test/errors.mjs URL DISC.bin [SHOTS_DIR]
// OTHERS / SOURCE_ISOS as in run.mjs. Scenarios (BASES-like: ONLY="estimate quota" runs those):
//   estimate  low advisory estimate: warning, then an attempted build; a forced job quota error stops it.
//   probe     the storage itself refuses a test allocation (?room=): warning and engine.noSpace.
//   private   incognito with a simulated low estimate: storage warning; the button stays usable.
//   quota     a job's output cannot be written (?quota=first: the worker throws the QuotaExceededError the player
//             saw): the build stops at the first one with engine.quota (no retries on other workers), the advice
//             listed, the details and the log open; the same error in Spanish after switching the menu
//   phone     a phone: the line that a phone takes hours
// With SHOTS_DIR, screenshots of the warning and of the error, English and Spanish.
import puppeteer from './browser.mjs';
import fs from 'node:fs';
import path from 'node:path';
const [url, disc, shots] = process.argv.slice(2);
const web = path.join(path.dirname(new URL(import.meta.url).pathname), '..');
const read = (p) => JSON.parse(fs.readFileSync(path.join(web, p), 'utf8'));
const en = read('i18n/en.json'), es = read('i18n/es.json');
const BUILD = path.join(web, '../build');   // (the snap Chromium cannot read /tmp)
fs.mkdirSync(BUILD, { recursive: true });
const profile = fs.mkdtempSync(path.join(BUILD, 'errors-profile-'));
if (shots) fs.mkdirSync(shots, { recursive: true });
const ISOS = process.env.SOURCE_ISOS || 'build/isos';
const OTHERS = process.env.OTHERS ?? [`dcb=${ISOS}/digital-card-battle/Digimon Digital Card Battle (USA).bin`,
  `dw2=${ISOS}/digimon-world-2/Digimon World 2 (USA).bin`,
  `dw2003=${ISOS}/digimon-world-2003/Digimon World 2003 (E) [SLES-03936].bin`].join(';');
const others = OTHERS.split(';').filter(Boolean).map((kv) => kv.slice(kv.indexOf('=') + 1));
const ONLY = (process.env.ONLY || 'estimate probe private quota phone').split(/\s+/);
const PHONE = 'Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Mobile Safari/537.36';
// a release with the desktop apps (v0.0.5 on): the advice then points at them
const DESKTOP = { windows: { name: 'Horizon-Patcher-Windows.zip', size: 24_903_221, sha256: 'a1'.repeat(32), signed: false },
                  macos: { name: 'Horizon-Patcher-macOS.zip', size: 41_220_118, sha256: 'b2'.repeat(32), notarized: false } };

const b = await puppeteer.launch({ executablePath: process.env.CHROMIUM || '/snap/bin/chromium', headless: 'new',
  args: ['--no-sandbox', '--disable-gpu'], userDataDir: profile, protocolTimeout: 0 });
let failed = 0;
const ok = (cond, what) => { console.log(`${cond ? 'ok  ' : 'FAIL'} ${what}`); if (!cond) failed++; };
const plain = (s) => s.replace(/\{\w+\}/g, '');
const has = (text, key, strings = en) => plain(strings[key]).split(/\s+/).slice(0, 6).every((w) => text.includes(w));

// A page with the four discs added and checked. estimate: what navigator.storage.estimate() answers (null: the
// browser's own; {}: nothing known).
async function ready({ query = '', estimate = null, incognito = false, phone = false, lang = 'en' } = {}) {
  const ctx = incognito ? await b.createBrowserContext() : b.defaultBrowserContext();
  const p = await ctx.newPage();
  p.on('pageerror', (e) => { console.log('[pageerror]', e.message); failed++; });
  if (phone) {
    await p.setUserAgent(PHONE);
    await p.setViewport({ width: 390, height: 844, isMobile: true, hasTouch: true, deviceScaleFactor: 2 });
  } else await p.setViewport({ width: 1100, height: 900, deviceScaleFactor: 2 });
  // (in the page, not by request interception: that holds the build workers' own requests)
  await p.evaluateOnNewDocument((l, est, desktop) => {
    localStorage.setItem('horizon.lang', l);
    if (est) navigator.storage.estimate = async () => est;
    const fetch0 = window.fetch;
    window.fetch = async (input, init) => {
      const r = await fetch0(input, init);
      if (!String(input instanceof Request ? input.url : input).endsWith('/engine/current.json') || !r.ok) return r;
      const cur = await r.json();
      return new Response(JSON.stringify({ ...cur, desktop }), { headers: { 'content-type': 'application/json' } });
    };
    document.addEventListener('readystatechange', () => {
      if (document.readyState !== 'interactive' || document.querySelector('meta[name="source-repository"]')) return;
      document.head.append(Object.assign(document.createElement('meta'), { name: 'source-repository', content: 'https://github.com/example/dw1horizon' }));
    });
  }, lang, estimate, DESKTOP);
  await p.goto(`${url}?test=1${query}`, { waitUntil: 'networkidle0' });
  await (await p.waitForSelector('#add-input')).uploadFile(disc, ...others);
  await p.waitForFunction(() => !document.querySelector('#patch-button').disabled, { timeout: 300000, polling: 500 });
  return { p, ctx };
}
const warning = (p) => p.waitForFunction(() => !document.querySelector('#patch-warning').hidden && document.querySelector('#patch-warning').textContent,
  { timeout: 30000, polling: 200 }).then(() => p.evaluate(() => ({ text: document.querySelector('#patch-warning').innerText,
  kind: document.querySelector('#patch-warning').dataset.kind, fixes: document.querySelectorAll('#patch-warning .fixes li').length,
  button: !document.querySelector('#patch-button').disabled }))).catch(() => null);
const build = async (p) => {
  await p.click('#patch-button');
  await p.waitForFunction(() => document.title === 'DONE', { timeout: 1800000, polling: 1000 });
  return p.evaluate(() => {
    const err = document.querySelector('#build-error');
    return { ...window.RESULTS, errorText: err.innerText, detailsOpen: [...err.querySelectorAll('details')].every((d) => d.open),
             details: err.querySelectorAll('details').length, logOpen: document.querySelector('.build-log').open,
             fixes: [...err.querySelectorAll('.fixes li')].map((li) => li.innerText), desktopLink: !!err.querySelector('.fixes a[href="#desktop"]'),
             copy: !!err.querySelector('.build-copy') };
  });
};
const shot = async (p, sel, name) => {
  if (!shots) return;
  const e = await p.$(sel);
  await e.evaluate((n) => n.scrollIntoView({ block: 'center' }));
  await new Promise((r) => setTimeout(r, 300));
  await e.screenshot({ path: path.join(shots, `${name}.png`) });
};
const toSpanish = async (p) => {
  await p.select('#lang', 'es');
  await p.waitForFunction(() => document.documentElement.lang === 'es', { timeout: 10000 });
  await new Promise((r) => setTimeout(r, 300));
};

if (ONLY.includes('estimate')) {
  const { p } = await ready({ estimate: { usage: 0, quota: 1.5 * 2 ** 30 }, query: '&quota=first' });
  const w = await warning(p);
  ok(w && w.kind === 'storage' && has(w.text, 'patch.lowSpace') && w.fixes >= 3 && w.button, `estimate: a warning before the build, with ${w?.fixes} things to do, the button usable`);
  await shot(p, '.patch-row', 'warning-no-room-en');
  const r = await build(p);
  ok(r.phase === 'error' && r.error.key === 'engine.quota' && has(r.errorText, 'engine.quota'), `estimate: the build tries and stops on a real write failure with engine.quota (${r.error?.key})`);
  ok(r.log.some((line) => /copying input disc/.test(line)), 'estimate: input copying started despite the low estimate');
  ok(r.detailsOpen && r.details >= 1 && r.logOpen && r.copy, 'estimate: the details and the log open, the copy button there');
  ok(r.desktopLink && r.fixes.some((f) => has(f, 'fix.private')) && r.fixes.some((f) => has(f, 'fix.freeDisk')), 'estimate: private window, free space and the desktop app suggested');
  await shot(p, '#build', 'error-no-room-en');
  await toSpanish(p);
  await shot(p, '.patch-row', 'warning-no-room-es');
  await shot(p, '#build', 'error-no-room-es');
  ok(has(await p.$eval('#build-error', (e) => e.innerText), 'engine.quota', es), 'estimate: the error in Spanish after switching the menu');
  await p.close();
}

if (ONLY.includes('probe')) {
  const { p } = await ready({ estimate: {}, query: `&room=${2 ** 50}` });
  const w = await warning(p);
  ok(w && w.kind === 'storage' && has(w.text, 'patch.lowSpace'), 'probe: the storage refuses the room: the warning');
  const r = await build(p);
  ok(r.phase === 'error' && r.error.key === 'engine.noSpace' && /QuotaExceededError/.test(r.error.detail), `probe: the build stops with engine.noSpace from a real QuotaExceededError (${r.error?.detail})`);
  await p.close();
}

if (ONLY.includes('private')) {
  const { p, ctx } = await ready({ incognito: true, estimate: { usage: 0, quota: 1.5 * 2 ** 30 } });
  const w = await warning(p);
  ok(w && ['storage', 'private'].includes(w.kind) && (has(w.text, 'patch.lowSpace') || has(w.text, 'patch.private')) && w.button, 'private: a storage warning, the button usable');
  await shot(p, '.patch-row', 'warning-private-en');
  await toSpanish(p);
  await shot(p, '.patch-row', 'warning-private-es');
  await ctx.close();
}

if (ONLY.includes('quota')) {
  const { p } = await ready({ query: '&quota=first&workers=2' });
  ok(!await warning(p), 'quota: no warning before (there is room)');
  const r = await build(p);
  if (r.error?.key !== 'engine.quota') console.log(r.log.join('\n'), '\n', r.error);
  const lines = r.log.filter((l) => /imports|no room left|workers go on/.test(l) && /no room left|failed/.test(l));
  ok(r.phase === 'error' && r.error.key === 'engine.quota' && has(r.errorText, 'engine.quota'), `quota: the build stops with engine.quota (${r.error?.key})`);
  ok(lines.length === 1 && /no room left/.test(lines[0]) && !r.log.some((l) => /workers go on/.test(l)), `quota: stopped at the first failure, no retries (${lines.length} lines)`);
  ok(r.detailsOpen && r.logOpen && r.copy && r.desktopLink, 'quota: the details and the log open, the copy button and the desktop app there');
  ok(/Chrome|Chromium/.test(r.errorText), 'quota: the browser line is in the error details');
  await shot(p, '#build', 'error-quota-en');
  await toSpanish(p);
  ok(has(await p.$eval('#build-error', (e) => e.innerText), 'engine.quota', es), 'quota: the error in Spanish after switching the menu');
  await shot(p, '#build', 'error-quota-es');
  await p.close();
}

if (ONLY.includes('phone')) {
  const { p } = await ready({ phone: true });
  const w = await warning(p);
  ok(w && w.kind === 'phone' && has(w.text, 'patch.phone'), 'phone: the line that a phone takes hours');
  await shot(p, '.patch-row', 'warning-phone-en');
  await p.close();
}

await b.close();
fs.rmSync(profile, { recursive: true, force: true });
console.log(failed ? `${failed} FAILED` : 'all ok');
process.exit(failed ? 1 : 0);
