// No discs or engine needed. PLAYWRIGHT_MODULE can point at a local Playwright installation.
import assert from 'node:assert/strict';
const { webkit, chromium, firefox } = await import(process.env.PLAYWRIGHT_MODULE || 'playwright');
for (const [name, type] of Object.entries({ webkit, chromium, firefox })) {
  const browser = await type.launch({ headless: true,
    ...(name === 'chromium' && process.env.CHROMIUM ? { executablePath: process.env.CHROMIUM } : {}) });
  try {
    for (const [agent, writable] of [
      ['iPhone OS 18_7 Version/26.6.1 Mobile Safari/604.1', true],
      ['iPhone OS 18_7 CriOS/141.0 Mobile Safari/604.1', false],
      ['iPad OS 18_7 Version/18.7 Mobile Safari/604.1', false],
    ]) {
      const context = await browser.newContext({ userAgent: agent, locale: 'en-US', viewport: { width: 390, height: 844 } });
      if (!writable) await context.addInitScript(() => { delete FileSystemFileHandle.prototype.createWritable; });
      const page = await context.newPage();
      await page.goto(process.argv[2]);
      await page.waitForFunction(() => document.querySelector('#patch-status').textContent.trim());
      const missing = await page.evaluate(async () => (await import('./js/engine/engine.js')).missingSupport());
      assert.equal(missing, writable ? null : 'engine.noWritable');
      if (!writable) {
        assert.match(await page.locator('#patch-status').textContent(), /iOS\/iPadOS 26/);
        assert.equal(await page.locator('#patch-button').isDisabled(), true);
        assert.equal(await page.locator('#patch-status').evaluate(node => {
          const box = node.getBoundingClientRect();
          return box.left >= 0 && box.right <= innerWidth && box.left + node.scrollWidth <= innerWidth + 1;
        }), true, 'upgrade message and diagnostics fit the phone width');
      }
      await context.close();
    }
    console.log(`${name} ${browser.version()}: capability gate passed`);
  } finally { await browser.close(); }
}
