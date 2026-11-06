// Disc-free generated-page checks, with isolated temporary fixtures and a private server.
// node web/test/changelog-browser.mjs SITE [SHOTS_DIR]
import puppeteer from './browser.mjs';
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import path from 'node:path';
import { spawn } from 'node:child_process';
import { once } from 'node:events';
import { LANGS, tag } from '../js/i18n.js';
const [site, shots] = process.argv.slice(2);
const temp = await fs.mkdtemp(path.resolve('build/changelog-browser-'));
let browser, server;
try {
  const root = path.join(temp, 'site');
  await fs.cp(site, root, { recursive: true, filter: (src) => src !== path.join(site, 'engine') });
  // Keep this regression independent of the served release and its growing history.
  const file = path.join(root, 'content/changelog.json');
  const source = JSON.parse(await fs.readFile(file, 'utf8'));
  const first = source.versions.find((entry) => entry.version === '0.0.1');
  await fs.writeFile(file, JSON.stringify({ versions: [first] }));
  const index = path.join(root, 'index.html');
  await fs.writeFile(index, (await fs.readFile(index, 'utf8')).replace(/<link[^>]+https:\/\/fonts\.[^>]+>/g, ''));
  server = spawn('python3', ['-u', '-c',
    'import http.server\nclass Handler(http.server.SimpleHTTPRequestHandler):\n def end_headers(self):\n  self.send_header("Cache-Control", "no-store")\n  super().end_headers()\ns=http.server.ThreadingHTTPServer(("127.0.0.1",0),Handler)\nprint(s.server_port,flush=True)\ns.serve_forever()'],
    { cwd: root, stdio: ['ignore', 'pipe', 'ignore'] });
  const [port] = await once(server.stdout, 'data');
  const url = `http://127.0.0.1:${String(port).trim()}/`;
  browser = await puppeteer.launch({ executablePath: process.env.CHROMIUM || '/snap/bin/chromium', headless: 'new',
    args: ['--no-sandbox', '--disable-gpu'], userDataDir: path.join(temp, 'profile') });
  const page = await browser.newPage();
  const errors = [];
  page.on('pageerror', (error) => errors.push(error.message));
  let currentRequests = 0;
  page.on('request', (request) => {
    if (request.url().endsWith('/engine/current.json')) currentRequests++;
  });
  // Remote box art must not make this disc-free regression depend on the network.
  const network = await page.createCDPSession();
  await network.send('Network.enable');
  await network.send('Network.setBlockedURLs', { urls: ['https://*'] });
  const visit = async () => {
    await page.goto(url, { waitUntil: 'load' });
    await page.waitForSelector('#changelog:not([hidden]) details');
  };
  await visit();
  // The storage cleanup independently checks the engine; label and changelog share the other request.
  assert.equal(currentRequests, 2, 'release label and changelog add no request beyond storage cleanup');
  const texts = { en: first.en.new[0], es: first.es.new[0] };
  for (const lang of ['en', 'es']) {
    await page.select('#lang', lang);
    await page.waitForFunction((text) => document.querySelector('#changelog li')?.textContent === text, {}, texts[lang]);
    const expectedDate = await page.evaluate(() => new Intl.DateTimeFormat(document.documentElement.lang,
      { day: 'numeric', month: 'long', year: 'numeric', timeZone: 'UTC' }).format(new Date('2026-10-31T00:00:00Z')));
    assert.equal(await page.$eval('#changelog time', (el) => el.textContent), expectedDate);
    for (const [size, width, height] of [['desktop', 1440, 1000], ['phone', 390, 844]]) {
      await page.setViewport({ width, height });
      await page.$eval('#changelog', (el) => el.scrollIntoView({ block: 'center', behavior: 'instant' }));
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), false, 'no horizontal overflow');
      if (shots) {
        await fs.mkdir(shots, { recursive: true });
        await page.screenshot({ path: path.join(shots, `changelog-${size}-${lang}.png`) });
      }
    }
  }
  console.log('ok: English/Spanish text, localized dates, desktop/phone layout, shared current.json request');
  const data = JSON.parse(await fs.readFile(file, 'utf8'));
  const extra = structuredClone(data.versions[0]);
  extra.version = '0.0.10';
  delete extra.es;
  data.versions.unshift(extra);
  await fs.writeFile(file, JSON.stringify(data));
  await visit();
  assert.equal(await page.$$eval('#changelog details', (els) => els.length), 2, 'preview shows every version');
  assert.deepEqual(await page.$$eval('#changelog details', (els) => els.map((el) => el.open)), [true, false]);
  assert.equal(await page.$eval('#changelog li', (el) => el.textContent), texts.en, 'missing language falls back to English');
  await fs.mkdir(path.join(root, 'engine'), { recursive: true });
  const current = path.join(root, 'engine/current.json');
  await fs.writeFile(current, JSON.stringify({ release_tag: 'v0.0.9' }));
  await visit();
  assert.equal(await page.$$eval('#changelog details', (els) => els.length), 1, 'numeric filter hides 0.0.10 above 0.0.9');
  assert.match(await page.$eval('#changelog summary', (el) => el.textContent), /^v0\.0\.1/);
  await fs.writeFile(current, '{}');
  await visit();
  assert.equal(await page.$$eval('#changelog details', (els) => els.length), 2, 'missing release_tag shows all');
  console.log('ok: preview, older details closed, English fallback, hide-newer, missing release_tag');
  // A closed older version must open after asynchronous loading, in every language.
  await browser.defaultBrowserContext().overridePermissions(url,
    ['clipboard-read', 'clipboard-write', 'clipboard-sanitized-write']);
  for (const lang of LANGS) {
    await page.select('#lang', lang);
    await page.waitForFunction((expected) => document.documentElement.lang === expected, {}, tag(lang));
    for (const [size, width, height] of [['desktop', 1440, 1000], ['phone', 390, 844]]) {
      await page.setViewport({ width, height });
      await page.goto('about:blank');
      await page.goto(`${url}#changelog-0.0.1`, { waitUntil: 'load' });
      await page.waitForSelector('#changelog-0\\.0\\.1[open]');
      assert.equal(await page.$eval('html', (el) => el.lang), tag(lang));
      assert.deepEqual(await page.$$eval('#changelog details', (els) => els.map((el) => el.open)), [true, true]);
      const visible = () => page.$eval('[id="changelog-0.0.1"] summary', (el) => {
        const rect = el.getBoundingClientRect();
        return rect.top >= 0 && rect.bottom <= innerHeight;
      });
      assert.equal(await visible(), true, `${lang}/${size}: first-load target visible`);
      assert.equal(await page.$eval('[id="changelog-0.0.1"]', (el) => {
        const rect = el.getBoundingClientRect();
        return rect.left >= 0 && rect.right <= innerWidth && el.scrollWidth <= el.clientWidth;
      }), true, `${lang}/${size}: changelog fits the viewport`);
      // Changing the hash opens only the target; other entries retain their state.
      await page.$$eval('#changelog details', (els) => els.forEach((el) => { el.open = false; }));
      await page.evaluate(() => { location.hash = '#features'; });
      await page.waitForFunction(() => location.hash === '#features');
      await page.evaluate(() => { location.hash = '#changelog-0.0.1'; });
      await page.waitForFunction(() => document.querySelector('[id="changelog-0.0.1"]').getBoundingClientRect().top >= 0);
      assert.equal(await visible(), true, `${lang}/${size}: hash-change target visible`);
      assert.deepEqual(await page.$$eval('#changelog details', (els) => els.map((el) => el.open)), [false, true]);
      // A link inside a summary also works with the keyboard and never collapses it.
      const link = '[id="changelog-0.0.1"] .changelog-link';
      await page.focus(link);
      await page.keyboard.press('Enter');
      await page.waitForFunction(async (expected) => (await navigator.clipboard.readText()) === expected,
        {}, `${url}#changelog-0.0.1`);
      assert.equal(await page.$eval('[id="changelog-0.0.1"]', (el) => el.open), true);
      assert.match(await page.$eval(link, (el) => el.getAttribute('aria-label')), /\S/);
      if (shots && ['en', 'ja'].includes(lang)) {
        await page.screenshot({ path: path.join(shots, `changelog-link-${size}-${lang}.png`) });
      }
    }
  }
  for (const hash of ['#features', '#changelog-9.9.9', '#changelog-%ZZ']) {
    await page.goto('about:blank');
    await page.goto(`${url}${hash}`, { waitUntil: 'load' });
    await page.waitForSelector('#changelog:not([hidden]) details');
    assert.deepEqual(await page.$$eval('#changelog details', (els) => els.map((el) => el.open)), [true, false]);
  }
  await page.evaluate(() => {
    navigator.clipboard.writeText = async () => { throw new Error('clipboard denied'); };
  });
  await page.click('[id="changelog-0.0.1"] .changelog-link');
  await page.waitForFunction(() => location.hash === '#changelog-0.0.1');
  assert.equal(await page.$eval('[id="changelog-0.0.1"]', (el) => el.open), true);
  assert.equal(await page.$$eval('.slot', (els) => els.length), 4, 'builder keeps its disc slots');
  console.log('ok: deep links, hash changes, keyboard copy, denied clipboard, unknown hashes, all languages and sizes');
  await fs.unlink(file);
  await page.reload({ waitUntil: 'load' });
  assert.equal(await page.$eval('#changelog', (el) => el.hidden), true);
  assert.equal(await page.$$eval('.slot', (els) => els.length), 4, 'patcher still initializes');
  assert.deepEqual(errors, []);
  console.log('ok: failed changelog hides section; patcher initializes; no page errors');
} finally {
  if (browser) await browser.close();
  if (server) { server.kill(); await once(server, 'exit'); }
  await fs.rm(temp, { recursive: true, force: true });
}
