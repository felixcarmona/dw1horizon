// No discs or engine needed: real page, OPFS and room worker, with simulated estimates and tiny inputs.
// PLAYWRIGHT_MODULE selects a local Playwright installation. node web/test/storage.mjs URL [SHOTS_DIR]
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
const { chromium, firefox, webkit } = await import(process.env.PLAYWRIGHT_MODULE || 'playwright');
const [url, shots] = process.argv.slice(2);
if (shots) fs.mkdirSync(shots, { recursive: true });
fs.mkdirSync('build', { recursive: true });
const app = fs.readFileSync(new URL('../js/app.js', import.meta.url), 'utf8');
const plan = { paths: [], packs: [], jobs: [], source_discs: [], pyodide: { files: [] }, write_est: 1,
  release: { holes_bytes: 1.5 * 2 ** 30, outputs: { us: { size: 4 } } } };
const scenarios = [
  { name: 'low', estimate: { usage: 0, quota: 512 * 2 ** 20 }, warning: 'patch.lowSpace' },
  { name: 'zero', estimate: { usage: 0, quota: 0 }, warning: 'patch.lowSpace' },
  { name: 'usage-exceeds-quota', estimate: { usage: 200, quota: 100 }, warning: 'patch.lowSpace' },
  { name: 'unknown', estimate: {}, warning: 'patch.unknownSpace' },
  { name: 'missing-usage', estimate: { quota: 10 * 2 ** 30 }, warning: 'patch.unknownSpace' },
  { name: 'negative', estimate: { usage: -1, quota: 100 }, warning: 'patch.unknownSpace' },
  { name: 'estimate-rejected', rejectEstimate: true, warning: 'patch.unknownSpace' },
  { name: 'estimate-unavailable', noEstimate: true, warning: 'patch.unknownSpace' },
  { name: 'enough', estimate: { usage: 1, quota: 10 * 2 ** 30 } },
  { name: 'persist-granted', estimate: { usage: 0, quota: 100 }, warning: 'patch.lowSpace', grant: true },
  { name: 'persist-rejected', estimate: {}, warning: 'patch.unknownSpace', rejectPersist: true },
  { name: 'persist-unavailable', estimate: {}, warning: 'patch.unknownSpace', noPersist: true },
  { name: 'write-quota', estimate: { usage: 0, quota: 10 * 2 ** 30 }, failWrite: true, error: 'engine.quota' },
  { name: 'probe-quota', estimate: {}, probe: 'quota', warning: 'patch.lowSpace', error: 'engine.noSpace' },
  { name: 'probe-error', estimate: { usage: 0, quota: 10 * 2 ** 30 }, probe: 'error', warning: 'patch.unknownSpace' },
  { name: 'probe-blocked', estimate: {}, probe: 'blocked', warning: 'engine.storageBlocked', error: 'engine.storageBlocked' },
];
for (const [name, type] of Object.entries({ chromium, firefox, webkit })) {
  if (process.env.BROWSERS && !process.env.BROWSERS.split(',').includes(name)) continue;
  for (const scenario of scenarios) {
    const profile = fs.mkdtempSync(path.resolve(`build/storage-${name}-`));
    const context = await type.launchPersistentContext(profile, { headless: true, locale: 'en-US', serviceWorkers: 'block',
      ...(name === 'chromium' && process.env.CHROMIUM ? { executablePath: process.env.CHROMIUM } : {}) });
    const browser = context.browser();
    try {
      await context.addInitScript((s) => {
        localStorage.setItem('horizon.lang', 'en');
        window.storageEvents = [];
        // WebKit can return a fresh StorageManager wrapper on each access. Keep the mocked instance stable.
        Object.defineProperty(navigator, 'storage', { value: navigator.storage });
        const estimate = async () => {
          storageEvents.push('estimate');
          if (s.rejectEstimate) throw new Error('estimate unavailable');
          return s.grant && window.persistenceSettled ? { usage: 0, quota: 10 * 2 ** 30 } : s.estimate;
        };
        Object.defineProperty(navigator.storage, 'estimate', { value: s.noEstimate ? undefined : estimate });
        Object.defineProperty(navigator.storage, 'persist', { value: s.noPersist ? undefined : async () => {
          storageEvents.push('persist-request');
          await new Promise(r => setTimeout(r, 50));
          window.persistenceSettled = true;
          storageEvents.push('persist-settled');
          if (s.rejectPersist) throw new Error('permission unavailable');
          return !!s.grant;
        } });
        if (s.failWrite) FileSystemFileHandle.prototype.createWritable = async () => {
          throw new DOMException('test: disk is full', 'QuotaExceededError');
        };
      }, scenario);
      // Inject only the storage exception into the production worker, preserving classification and cleanup.
      if (scenario.probe) await context.route('**/js/engine/room-worker.js', async route => {
        const source = fs.readFileSync(new URL('../js/engine/room-worker.js', import.meta.url), 'utf8');
        const error = { quota: 'QuotaExceededError', blocked: 'SecurityError', error: 'UnknownError' }[scenario.probe];
        await route.fulfill({ contentType: 'text/javascript', body: source.replace('    access.truncate(bytes);',
          `    throw new DOMException('simulated probe refusal', '${error}');`) });
      });
      await context.route('**/engine/current.json', route => route.fulfill({ json: { version: 'storage-fixture' } }));
      await context.route('**/engine/storage-fixture/plan.json', route => route.fulfill({ json: plan }));
      await context.route('**/js/app.js', route => route.fulfill({ contentType: 'text/javascript', body: app + `
        window.storageFixture = async () => {
          const { EngineError } = await import('./engine/engine.js');
          Build.prototype.compileEngine = async function () { throw new EngineError('fixture.reachedBuilder'); };
          await navigator.locks.request('horizon-build', () => {});
          for (const g of games.values()) g.cur = { file: new File(['disc'], g.id + '.bin'),
            expect: { id: 'fixture', title: 'fixture' }, got: {}, from: {} };
          renderPatch();
        };
        window.storageWarning = () => room;
      ` }));
      const page = await context.newPage();
      page.on('pageerror', error => console.error(`${name}/${scenario.name}: ${error.message}`));
      await page.goto(url + '?test=1');
      await page.waitForFunction(() => window.storageFixture && document.querySelectorAll('.slot').length === 4);
      await page.evaluate(() => storageFixture());
      await page.waitForFunction(() => storageWarning());
      assert.equal(await page.locator('#patch-button').isEnabled(), true, `${name}/${scenario.name}: button usable`);
      const warning = page.locator('#patch-warning');
      if (scenario.warning) {
        assert.equal(await warning.isVisible(), true);
        const strings = await page.evaluate(async () => (await import('./js/i18n.js')).i18n.strings);
        assert.ok((await warning.textContent()).includes(strings[scenario.warning].split('{gb}')[0]),
          `${name}/${scenario.name}: ${await warning.textContent()} ${JSON.stringify(await page.evaluate(() => storageWarning()))}`);
        if (scenario.warning !== 'engine.storageBlocked') {
          assert.match(await warning.textContent(), /persistent storage/);
          assert.match(await warning.textContent(), /Chrome, Edge or Firefox/);
        }
      } else assert.equal(await warning.isVisible(), false);
      if (shots && name === 'chromium' && scenario.name === 'low') {
        await page.locator('.patch-row').screenshot({ path: path.join(shots, 'storage-low-en.png') });
        await page.selectOption('#lang', 'es');
        await page.waitForFunction(() => document.documentElement.lang === 'es');
        await page.locator('.patch-row').screenshot({ path: path.join(shots, 'storage-low-es.png') });
      }
      await page.evaluate(() => storageEvents.length = 0);
      await page.click('#patch-button');
      await page.waitForFunction(() => document.title === 'DONE');
      const result = await page.evaluate(() => ({ result: RESULTS, events: storageEvents }));
      assert.equal(result.result.error.key, scenario.error || 'fixture.reachedBuilder', `${name}/${scenario.name}: engine outcome`);
      if (!scenario.noPersist) {
        assert.ok(result.events.indexOf('persist-request') >= 0);
        if (!scenario.noEstimate) assert.ok(result.events.indexOf('estimate') > result.events.indexOf('persist-settled'),
          `${name}/${scenario.name}: persistence settled before quota recheck`);
      }
      if (scenario.grant) assert.ok(result.result.log.some(line => /room: .*; ok/.test(line)));
      assert.equal(await page.evaluate(async () => {
        const root = await navigator.storage.getDirectory();
        try { await root.getDirectoryHandle('horizon-room'); return false; } catch { return true; }
      }), true, 'probe files removed');
      console.log(`${name} ${browser.version()}: ${scenario.name} passed`);
    } finally {
      await context.close();
      fs.rmSync(profile, { recursive: true, force: true });
    }
  }
}
