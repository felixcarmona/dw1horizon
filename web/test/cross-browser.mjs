// Full real-disc build in Playwright: node cross-browser.mjs URL ISO_ROOT BROWSER [SECONDS].
// Install playwright locally or set PLAYWRIGHT_MODULE to its module URL. BROWSER: webkit, chromium, firefox.
import assert from 'node:assert/strict';
import path from 'node:path';
const { webkit, chromium, firefox } = await import(process.env.PLAYWRIGHT_MODULE || 'playwright');
const [url, isoRoot, name = 'webkit', seconds = '7200'] = process.argv.slice(2);
const browser = await ({ webkit, chromium, firefox }[name]).launch({ headless: true,
  ...(name === 'chromium' && process.env.CHROMIUM ? { executablePath: process.env.CHROMIUM } : {}) });
let timer;
try {
  console.log(JSON.stringify({ browser: name, version: browser.version() }));
  const context = await browser.newContext();
  await context.addInitScript(() => {
    Object.defineProperty(navigator, 'hardwareConcurrency', { get: () => 4 });
    Object.defineProperty(navigator, 'deviceMemory', { get: () => undefined });
  });
  const page = await context.newPage();
  page.on('pageerror', e => console.log('pageerror:', e.message));
  const target = new URL(url); target.searchParams.set('test', '1'); target.searchParams.set('workers', '1');
  await page.goto(target.href);
  timer = setInterval(async () => {
    try { console.log(await page.locator('#patch-status').textContent(), '|', await page.locator('#build-phase').textContent()); } catch { /* closing */ }
  }, 30000);
  const discs = [
    'digimon-world/Digimon World (USA).bin',
    'digital-card-battle/Digimon Digital Card Battle (USA).bin',
    'digimon-world-2/Digimon World 2 (USA).bin',
    'digimon-world-2003/Digimon World 3 (USA).bin',
  ];
  // Add separately so WebKit's automation does not retain all picker snapshots at once.
  for (const disc of discs) {
    console.log('Selecting', disc);
    await page.locator('#add-input').setInputFiles(path.join(isoRoot, disc));
  }
  await page.waitForFunction(() => !document.querySelector('#patch-button').disabled, null, { timeout: 600000 })
    .catch(async error => {
      console.log(await page.locator('#patch-status').textContent());
      throw error;
    });
  await page.click('#patch-button');
  await page.waitForFunction(() => document.title === 'DONE', null, { timeout: Number(seconds) * 1000 });
  const result = await page.evaluate(async () => {
    const r = window.RESULTS;
    if (r.phase !== 'done') return r;
    const dir = await (await navigator.storage.getDirectory()).getDirectoryHandle('horizon-build');
    const file = await (await dir.getFileHandle('image.bin')).getFile();
    const hash = await new Promise((resolve, reject) => {
      const worker = new Worker('js/hash-worker.js');
      worker.onmessage = ({data}) => { if (data.progress == null) { worker.terminate(); resolve(data); } };
      worker.onerror = e => { worker.terminate(); reject(new Error(e.message)); };
      worker.postMessage({file});
    });
    return { ...r, independentHash: hash, imageSize: file.size };
  });
  console.log(JSON.stringify(result, null, 2));
  assert.equal(result.phase, 'done');
  assert.equal(result.workerCount, 1);
  assert.equal(result.independentHash.sha1, result.result.sha1);
  if (process.env.EXPECT_SHA1) assert.equal(result.independentHash.sha1, process.env.EXPECT_SHA1);
} finally {
  clearInterval(timer);
  await browser.close();
}
