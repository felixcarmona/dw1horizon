// Disc-free generated-page checks, with isolated temporary fixtures and a private server.
// node web/test/changelog-browser.mjs SITE [SHOTS_DIR]
import puppeteer from './browser.mjs';
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import path from 'node:path';
import { spawn } from 'node:child_process';
import { once } from 'node:events';
const [site, shots] = process.argv.slice(2);
const temp = await fs.mkdtemp(path.resolve('build/changelog-browser-'));
let browser, server;
try {
  const root = path.join(temp, 'site');
  await fs.cp(site, root, { recursive: true });
  server = spawn('python3', ['-u', '-c',
    'import http.server,sys; s=http.server.ThreadingHTTPServer(("127.0.0.1",0),http.server.SimpleHTTPRequestHandler); print(s.server_port,flush=True); s.serve_forever()'],
    { cwd: root, stdio: ['ignore', 'pipe', 'ignore'] });
  const [port] = await once(server.stdout, 'data');
  const url = `http://127.0.0.1:${String(port).trim()}/`;
  browser = await puppeteer.launch({ executablePath: process.env.CHROMIUM || '/snap/bin/chromium', headless: 'new',
    args: ['--no-sandbox', '--disable-gpu'], userDataDir: path.join(temp, 'profile') });
  const page = await browser.newPage();
  const errors = [];
  page.on('pageerror', (error) => errors.push(error.message));
  let currentRequests = 0;
  page.on('request', (request) => { if (request.url().endsWith('/engine/current.json')) currentRequests++; });
  const visit = async () => {
    await page.goto(url, { waitUntil: 'networkidle0' });
    await page.waitForSelector('#changelog:not([hidden]) details');
  };
  await visit();
  // The storage cleanup independently checks the engine; label and changelog share the other request.
  assert.equal(currentRequests, 2, 'release label and changelog add no request beyond storage cleanup');
  const texts = { en: 'First public release', es: 'Primera versión pública' };
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
  const file = path.join(root, 'content/changelog.json');
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
  await fs.unlink(file);
  await page.reload({ waitUntil: 'networkidle0' });
  assert.equal(await page.$eval('#changelog', (el) => el.hidden), true);
  assert.equal(await page.$$eval('.slot', (els) => els.length), 4, 'patcher still initializes');
  assert.deepEqual(errors, []);
  console.log('ok: failed changelog hides section; patcher initializes; no page errors');
} finally {
  if (browser) await browser.close();
  if (server) { server.kill(); await once(server, 'exit'); }
  await fs.rm(temp, { recursive: true, force: true });
}
