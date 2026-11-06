// No discs or engine bundle needed. Test the production output helper and page download controls.
// node web/test/downloads.mjs URL
// CHROMIUM=path or FIREFOX=path selects a browser; Chromium also runs with Android emulation.
import puppeteer from './browser.mjs';
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import path from 'node:path';
import { setTimeout as delay } from 'node:timers/promises';

const url = process.argv[2] || 'http://127.0.0.1:8799/';
const firefox = process.env.FIREFOX;
await fs.mkdir('build', { recursive: true });
const root = await fs.mkdtemp(path.resolve('build/downloads-'));
const app = await fs.readFile(new URL('../js/app.js', import.meta.url), 'utf8');
const browser = await puppeteer.launch(firefox
  ? { browser: 'firefox', executablePath: firefox, headless: true, userDataDir: path.join(root, 'profile') }
  : { executablePath: process.env.CHROMIUM || '/snap/bin/chromium', headless: true,
      args: ['--no-sandbox', '--disable-gpu'], userDataDir: path.join(root, 'profile') });
try {
  console.log(await browser.version());
  for (const mobile of firefox ? [false] : [false, true]) {
    for (const combined of [false, true]) {
      const label = `${firefox ? 'Firefox' : mobile ? 'Chromium Android' : 'Chromium'} ${combined ? 'both' : 'separate'}`;
      const dir = path.join(root, label.replaceAll(' ', '-'));
      await fs.mkdir(dir);
      const ctx = await browser.createBrowserContext({ downloadBehavior: { policy: 'allow', downloadPath: dir } });
      try {
        const page = await ctx.newPage();
        const errors = [];
        page.on('pageerror', (e) => errors.push(e.message));
        if (mobile) {
          await page.setUserAgent('Mozilla/5.0 (Linux; Android 14; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/150.0.0.0 Mobile Safari/537.36');
          await page.setViewport({ width: 393, height: 851, deviceScaleFactor: 2, isMobile: true, hasTouch: true });
        }
        // Inject only the completed-build state; use the real engine's output helper and page renderer.
        await page.setRequestInterception(true);
        page.on('request', (r) => r.url().endsWith('/js/app.js')
          ? r.respond({ contentType: 'text/javascript', body: `${app}\nwindow.downloadFixture = (result) => {
              last = { phase: 'done', result, steps: [], workers: [], log: [], elapsed: 1 };
              renderBuild();
            };` }) : r.continue());
        await page.goto(url);
        await page.waitForFunction(() => window.downloadFixture && document.querySelector('#add-button').textContent.trim());
        const metadata = await page.evaluate(async () => {
          const { discDownloads } = await import('./js/engine/engine.js');
          // Simulate an OPFS File with no MIME, and verify that explicit text MIME is overridden too.
          const bytes = new Uint8Array([0, 255, 128, 13, 10, 1]);
          const result = discDownloads(new File([bytes], 'image.bin'));
          if (discDownloads(new Blob([bytes], { type: 'text/plain' })).bin.type !== 'application/octet-stream')
            throw new Error('image MIME was not overridden');
          window.downloadFixture({ ...result, size: bytes.length, sha1: 'fixture', holes: 0 });
          return Promise.all(['bin', 'cue'].map(async (ext) => {
            const a = document.querySelector(`#dl-${ext}`), blob = await (await fetch(a.href)).blob();
            return { ext, name: a.download, type: blob.type };
          }));
        });
        for (const { ext, name, type } of metadata) {
          assert.equal(name, `Digimon World Horizon.${ext}`);
          assert.equal(type, 'application/octet-stream');
        }
        if (combined) await page.click('#dl-all');
        else {
          await page.click('#dl-bin');
          await page.click('#dl-cue');
        }
        const names = ['Digimon World Horizon.bin', 'Digimon World Horizon.cue'];
        const deadline = Date.now() + 15000;
        while (Date.now() < deadline) {
          const files = await fs.readdir(dir);
          if (names.every((n) => files.includes(n)) && files.length === 2) break;
          await delay(100);
        }
        assert.deepEqual((await fs.readdir(dir)).sort(), names);
        assert.deepEqual(await fs.readFile(path.join(dir, names[0])), Buffer.from([0, 255, 128, 13, 10, 1]));
        assert.equal(await fs.readFile(path.join(dir, names[1]), 'utf8'),
          'FILE "Digimon World Horizon.bin" BINARY\r\n  TRACK 01 MODE2/2352\r\n    INDEX 01 00:00:00\r\n');
        assert.deepEqual(errors, []);
        console.log(`ok ${label}: exact filenames, binary MIME, unchanged bytes and matching CUE reference`);
      } finally { await ctx.close(); }
    }
  }
} finally {
  await browser.close();
  await fs.rm(root, { recursive: true, force: true });
}
