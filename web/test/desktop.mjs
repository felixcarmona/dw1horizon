// web/test (not deployed): "Prefer an app?", the desktop patcher's downloads (js/desktop.js), headless Chromium, no
// discs. node web/test/desktop.mjs URL [SHOTS_DIR]
// engine/current.json is replaced by fixtures (release 0.0.5); a page without the source-repository meta (a local
// preview) gets one for the test.
//   1. hidden: no engine, a release without `desktop` (v0.0.4 and earlier, or desktop.yml not done yet), no repository
//   2. Windows visitor: Windows first and highlighted, macOS outlined; the links are the tag's own release assets with
//      the release and size; the first-start help Windows first; the SHA-256 of both; Linux and phone lines hidden
//   3. macOS visitor: macOS first; Gatekeeper steps while not notarized, one line once notarized
//   4. Linux: neither highlighted, the browser builder and dwpatch.py offered
//   5. phone: one line that the apps are for computers, no buttons
//   6. switching the language keeps an open help open and translates the section
// With SHOTS_DIR, screenshots of the section for the owner: Windows and macOS visitors, phone, English and Spanish,
// collapsed and with the help expanded.
import puppeteer from './browser.mjs';
import fs from 'node:fs';
import path from 'node:path';
const [url, shots] = process.argv.slice(2);
const web = path.join(path.dirname(new URL(import.meta.url).pathname), '..');
const read = (p) => JSON.parse(fs.readFileSync(path.join(web, p), 'utf8'));
const en = read('i18n/en.json'), es = read('i18n/es.json');
const BUILD = path.join(web, '../build');   // (the snap Chromium cannot read /tmp)
fs.mkdirSync(BUILD, { recursive: true });
const profile = fs.mkdtempSync(path.join(BUILD, 'desktop-profile-'));
if (shots) fs.mkdirSync(shots, { recursive: true });
const FAKE_REPO = 'https://github.com/example/dw1horizon';
const UA = {
  windows: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36',
  macos: 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36',
  linux: 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36',
  phone: 'Mozilla/5.0 (iPhone; CPU iPhone OS 18_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.6 Mobile/15E148 Safari/604.1',
};
const app = (name, size, flag, value) => ({ name, size, sha256: name.includes('Windows') ? 'a1'.repeat(32) : 'b2'.repeat(32), [flag]: value });
const release = (desktop) => ({
  version: '0123456789ab', release_version: '0.0.5', release_date: '2026-11-04', commit: 'c'.repeat(40), release_tag: 'v0.0.5',
  ...(desktop ? { desktop } : {}),
});
const DESKTOP = (notarized = false) => ({
  windows: app('Horizon-Patcher-Windows.zip', 24_903_221, 'signed', false),
  macos: app('Horizon-Patcher-macOS.zip', 41_220_118, 'notarized', notarized),
  run: 'https://github.com/example/dw1horizon/actions/runs/123',
});

const b = await puppeteer.launch({ executablePath: process.env.CHROMIUM || '/snap/bin/chromium', headless: 'new', args: ['--no-sandbox', '--disable-gpu'],
  userDataDir: profile });
let failed = 0;
const ok = (cond, what) => { console.log(`${cond ? 'ok  ' : 'FAIL'} ${what}`); if (!cond) failed++; };

// One visit: this system, this current.json (null: none deployed), the repository meta kept, added or removed.
async function visit({ os = 'windows', current = release(DESKTOP()), repo = 'keep', lang = 'en', width = 1280 } = {}) {
  const p = await b.newPage();
  p.on('pageerror', (e) => { console.log('[pageerror]', e.message); failed++; });
  await p.setUserAgent(UA[os]);
  await p.setViewport(os === 'phone' ? { width: 390, height: 844, isMobile: true, hasTouch: true, deviceScaleFactor: 2 }
    : { width, height: 900, deviceScaleFactor: 2 });
  await p.setRequestInterception(true);
  p.on('request', async (r) => {
    const u = new URL(r.url());
    if (u.pathname.endsWith('/engine/current.json')) {
      return current ? r.respond({ contentType: 'application/json', body: JSON.stringify(current) }) : r.respond({ status: 404, body: '' });
    }
    if (r.resourceType() === 'document') {
      const html = await (await fetch(r.url())).text();
      const meta = /<meta name="source-repository"[^>]*>\n?/;
      let body = html;
      if (repo === 'none') body = html.replace(meta, '');
      else if (!meta.test(html)) body = html.replace('</head>', `  <meta name="source-repository" content="${FAKE_REPO}">\n</head>`);
      return r.respond({ contentType: 'text/html', body });
    }
    r.continue();
  });
  await p.evaluateOnNewDocument((l) => { localStorage.setItem('horizon.lang', l); }, lang);
  await p.goto(url, { waitUntil: 'networkidle0' });
  await new Promise((r) => setTimeout(r, 300));
  return p;
}
const state = (p) => p.evaluate(() => {
  const box = document.querySelector('#desktop');
  const shown = (e) => !!e && !e.hidden && e.getClientRects().length > 0;
  return {
    hidden: box.hidden, os: box.dataset.os,
    repo: document.querySelector('meta[name="source-repository"]')?.content || '',
    buttons: [...box.querySelectorAll('#desktop-buttons a')].map((a) => ({ os: a.dataset.os, href: a.href, primary: a.classList.contains('primary'),
      text: a.innerText.replace(/\s+/g, ' ').trim(), shown: shown(a) })),
    help: [...box.querySelectorAll('#desktop-help details')].map((d) => ({ os: d.dataset.os, open: d.open, text: d.textContent, shown: shown(d) })),
    why: box.querySelector('#desktop-why-body').textContent,
    linux: shown(box.querySelector('#desktop-linux')) ? box.querySelector('#desktop-linux').innerHTML : null,
    phone: shown(box.querySelector('#desktop-phone')),
  };
});
const strip = (s) => s.replace(/\*\*/g, '');
const shot = async (p, name, { open = false, context = false } = {}) => {
  if (!shots) return;
  await p.evaluate((open) => { for (const d of document.querySelectorAll('#desktop details')) d.open = open; document.activeElement?.blur(); }, open);
  await new Promise((r) => setTimeout(r, 300));
  const box = await p.evaluate((context) => {
    const r = document.querySelector('#desktop').getBoundingClientRect();
    const top = context ? document.querySelector('.patch-row').getBoundingClientRect().top : r.top;
    return { x: r.left + scrollX, y: top + scrollY, width: r.width, height: r.bottom - top };
  }, context);
  const pad = 20;
  const vw = await p.evaluate(() => document.documentElement.clientWidth);
  const x = Math.max(0, box.x - pad), top = context ? pad : 10;   // (the privacy card's shadow ends just above the section)
  const clip = { x, y: Math.max(0, box.y - top), width: Math.min(vw - x, box.width + 2 * pad), height: box.height + top + pad };
  await p.screenshot({ path: path.join(shots, name), clip, captureBeyondViewport: true });
  console.log(`shot ${name}`);
};

// 1. hidden
for (const [what, opts] of [['no engine', { current: null }], ['a release without desktop apps', { current: release(null) }],
  ['no repository known', { repo: 'none' }]]) {
  const p = await visit(opts);
  ok((await state(p)).hidden, `hidden: ${what}`);
  await p.close();
}

// 2. Windows
{
  const p = await visit({ os: 'windows' });
  const s = await state(p);
  const repo = s.repo;
  ok(!s.hidden && s.os === 'windows', 'Windows visitor: shown');
  ok(s.buttons.map((x) => x.os).join() === 'windows,macos', 'Windows first');
  ok(s.buttons[0].primary && !s.buttons[1].primary, 'Windows highlighted, macOS not');
  ok(s.buttons[0].href === `${repo}/releases/download/v0.0.5/Horizon-Patcher-Windows.zip`
     && s.buttons[1].href === `${repo}/releases/download/v0.0.5/Horizon-Patcher-macOS.zip`, 'links: the tag\'s own release assets');
  ok(s.buttons[0].text === 'Download for Windows v0.0.5 · 24 MB' && s.buttons[1].text === 'Download for macOS v0.0.5 · 39 MB',
     `release and size on the buttons (${s.buttons.map((x) => x.text).join(' | ')})`);
  ok(s.help.map((x) => x.os).join() === 'windows,macos' && s.help.every((x) => !x.open), 'first-start help: Windows first, collapsed');
  ok(s.help[0].text.includes(strip(en['desktop.win2'])), 'SmartScreen steps');
  ok(s.help[1].text.includes(strip(en['desktop.mac2'])) && !s.help[1].text.includes(en['desktop.macNotarized']),
     'Gatekeeper steps while the macOS app is not notarized');
  ok(s.why.includes('a1'.repeat(32)) && s.why.includes('b2'.repeat(32)) && s.why.includes(en['desktop.unsigned']), 'why it is safe: both SHA-256, not signed yet');
  ok(s.linux === null && !s.phone, 'no Linux or phone line');
  await shot(p, '1-desktop-windows-en.png', { context: true });
  await shot(p, '2-desktop-windows-en-help.png', { open: true });
  // 6. the language: an open help stays open
  await p.evaluate(() => {
    for (const d of document.querySelectorAll('#desktop details')) d.open = false;
    document.querySelector('#desktop-help details').open = true;
  });
  await p.select('#lang', 'es');
  await new Promise((r) => setTimeout(r, 300));
  const t = await state(p);
  ok(t.buttons[0].text.startsWith(es['desktop.download'].replace('{os}', 'Windows')) && t.help[0].open && !t.help[1].open,
     'Spanish: translated, the open help still open');
  await shot(p, '3-escritorio-windows-es.png', { context: true });
  await shot(p, '4-escritorio-windows-es-ayuda.png', { open: true });
  await p.close();
}

// 3. macOS
for (const lang of ['en', 'es']) {
  const p = await visit({ os: 'macos', lang });
  const s = await state(p);
  ok(s.os === 'macos' && s.buttons.map((x) => x.os).join() === 'macos,windows' && s.buttons[0].primary && !s.buttons[1].primary,
     `macOS visitor (${lang}): macOS first and highlighted`);
  ok(s.help.map((x) => x.os).join() === 'macos,windows', `macOS visitor (${lang}): Gatekeeper help first`);
  await shot(p, lang === 'en' ? '5-desktop-mac-en.png' : '7-escritorio-mac-es.png', { context: true });
  await shot(p, lang === 'en' ? '6-desktop-mac-en-help.png' : '8-escritorio-mac-es-ayuda.png', { open: true });
  await p.close();
}
{
  const p = await visit({ os: 'macos', current: release(DESKTOP(true)) });
  const s = await state(p);
  ok(s.help[0].text.includes(en['desktop.macNotarized']) && !s.help[0].text.includes(strip(en['desktop.mac2'])),
     'notarized: one line, no Gatekeeper steps');
  ok(s.why.includes(en['desktop.unsigned']), 'the Windows app still unsigned: the note stays');
  await p.close();
}

// 4. Linux
{
  const p = await visit({ os: 'linux' });
  const s = await state(p);
  ok(s.os === 'linux' && s.buttons.length === 2 && s.buttons.every((x) => !x.primary), 'Linux: both offered, neither highlighted');
  ok(s.linux?.includes('README-players.md') && s.linux.includes('dwpatch.py'), 'Linux: the browser builder and dwpatch.py');
  await p.close();
}

// 5. phone
for (const lang of ['en', 'es']) {
  const p = await visit({ os: 'phone', lang });
  const s = await state(p);
  ok(!s.hidden && s.os === 'phone' && s.phone && s.buttons.every((x) => !x.shown) && s.help.every((x) => !x.shown),
     `phone (${lang}): one line, no buttons`);
  await shot(p, lang === 'en' ? '9-phone-en.png' : '10-movil-es.png');
  await p.close();
}

await b.close();
fs.rmSync(profile, { recursive: true, force: true });
console.log(failed ? `${failed} FAILED` : 'all ok');
process.exit(failed ? 1 : 0);
