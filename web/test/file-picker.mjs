// Tiny chooser fixtures: production UI, no game discs or engine needed.
// node web/test/file-picker.mjs URL
import assert from 'node:assert/strict';
import puppeteer from './browser.mjs';
const browser = await puppeteer.launch({ executablePath: process.env.CHROMIUM || '/snap/bin/chromium',
  headless: 'new', args: ['--no-sandbox', '--disable-gpu'] });
try {
  for (const mobile of [true, false]) {
    const page = await browser.newPage();
    if (mobile) await page.setUserAgent('Mozilla/5.0 (Linux; Android 10) Chrome/156.0.0.0 Mobile Safari/537.36');
    await page.evaluateOnNewDocument(() => {
      localStorage.setItem('horizon.lang', 'en');
      window.pickerCalls = [];
      window.showOpenFilePicker = async () => {
        pickerCalls.push('picker');
        return [{
          async queryPermission() { pickerCalls.push('query'); return 'granted'; },
          async getFile() { pickerCalls.push('getFile'); throw new DOMException('platform refusal', 'NotAllowedError'); },
        }];
      };
    });
    await page.goto(process.argv[2], { waitUntil: 'networkidle0' });
    const chooser = page.waitForFileChooser();
    await page.click('#add-button');
    await (await chooser).cancel();
    if (mobile) {
      assert.deepEqual(await page.evaluate(() => pickerCalls), [], 'Android uses the plain file input even if a native picker is exposed');
    } else {
      assert.deepEqual(await page.evaluate(() => pickerCalls), ['picker', 'query', 'getFile', 'query', 'getFile']);
      assert.match(await page.$eval('#problems-list', el => el.textContent), /local device storage/);
      await page.evaluate(() => document.querySelector('#problems').close());
      const nextChooser = page.waitForFileChooser();
      await page.click('#add-button');
      await (await nextChooser).cancel();
      assert.equal(await page.evaluate(() => pickerCalls.filter(c => c === 'picker').length), 1,
        'next click retains the plain picker fallback when activation expired');
    }
    console.log(`ok ${mobile ? 'Android user agent' : 'refused native handle'}: plain file input fallback`);
    await page.close();
  }
  const page = await browser.newPage();
  await page.evaluateOnNewDocument(() => {
    window.showOpenFilePicker = async () => { throw new DOMException('cancelled', 'AbortError'); };
    window.inputClicks = 0;
    document.addEventListener('click', e => { if (e.target.id === 'add-input') inputClicks++; });
  });
  await page.goto(process.argv[2], { waitUntil: 'networkidle0' });
  await page.click('#add-button');
  assert.equal(await page.evaluate(() => inputClicks), 0, 'cancelled picker does not open another picker');
  console.log('ok cancelled picker stays cancelled');
} finally { await browser.close(); }
