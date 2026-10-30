// Malformed discs and failed validation workers must close their batch and free the slot.
// node web/test/odd-inputs.mjs http://127.0.0.1:18867/
import puppeteer from './browser.mjs';
import fs from 'node:fs';
import path from 'node:path';
const profile = fs.mkdtempSync(path.resolve('build/odd-inputs-'));
const browser = await puppeteer.launch({ executablePath: process.env.CHROMIUM || '/snap/bin/chromium', headless: 'new',
  userDataDir: profile, args: ['--no-sandbox', '--disable-gpu'] });
let failures = 0;
try {
  const page = await browser.newPage();
  if (process.env.APP_SOURCE) {
    await page.setRequestInterception(true);
    page.on('request', (r) => r.url().includes('/js/app.js')
      ? r.respond({ contentType: 'text/javascript', body: fs.readFileSync(process.env.APP_SOURCE, 'utf8') }) : r.continue());
  }
  const errors = [];
  page.on('pageerror', (e) => errors.push(e.message));
  await page.goto(process.argv[2], { waitUntil: 'networkidle0' });
  await page.waitForSelector('.slot');
  const results = await page.evaluate(async () => {
    const results = [];
    const drop = (files) => {
      const dt = new DataTransfer();
      for (const f of files) dt.items.add(f);
      const input = document.querySelector('#add-input');
      input.files = dt.files;
      input.dispatchEvent(new Event('change'));
    };
    const idle = async (limit = 2000) => {
      for (let i = 0; i < limit / 20; i++) {
        if (document.querySelector('#patch').dataset.batches === '0') return true;
        await new Promise((r) => setTimeout(r, 20));
      }
      return false;
    };
    const iso = (boot, badDirectory = false) => {
      const b = new Uint8Array(24 * 2048), v = new DataView(b.buffer);
      const text = (p, s) => b.set(new TextEncoder().encode(s), p);
      const record = (p, name, lba, size) => {
        b[p] = 34 + name.length; v.setUint32(p + 2, lba, true); v.setUint32(p + 10, size, true);
        b[p + 32] = name.length; text(p + 33, name);
      };
      const cnf = `BOOT = cdrom:\\${boot};1\r\n`;
      b[16 * 2048] = 1; text(16 * 2048 + 1, 'CD001');
      v.setUint32(16 * 2048 + 140, 18, true);
      let p = 18 * 2048;
      const names = badDirectory ? ['\0', 'AAA', '4.AAA', 'MODEL', 'MODEL100'] : ['\0'];
      names.forEach((name, i) => {
        b[p] = name.length; v.setUint32(p + 2, i === 4 ? 999 : 20, true);
        v.setUint16(p + 6, i || 1, true); text(p + 8, name); p += 8 + name.length + (name.length & 1);
      });
      v.setUint32(16 * 2048 + 132, p - 18 * 2048, true);
      record(20 * 2048, '\0', 20, 2048);
      record(20 * 2048 + 35, 'SYSTEM.CNF;1', 21, cnf.length);
      text(21 * 2048, cnf);
      return b;
    };
    drop([new File([iso('OTHER_000.00')], 'Mixed.BIN'),
      new File(['FILE "mixed.bin" BINARY\n'], 'mixed.cue')]);
    await idle();
    let problems = [...document.querySelectorAll('#problems-list li')];
    results.push({ ok: problems.length === 1 && problems[0].textContent.includes('Mixed.BIN'),
      name: 'case-different CUE filename pairs with its image; other game refused once' });
    document.querySelector('#problems').close();
    await new Promise((r) => setTimeout(r, 30));
    drop([new File([iso('SLUS_011.93', true)], 'broken.iso')]);
    const ended = await idle();
    results.push({ ok: ended && document.querySelector('.slot[data-game="dw2"]').dataset.state === 'empty',
      name: 'malformed cooked image ends its check and frees its slot' });
    results.push({ ok: !!document.querySelector('#problems[open]'), name: 'malformed image explains the read failure' });
    document.querySelector('#problems').close();
    await new Promise((r) => setTimeout(r, 30));
    const discs = await (await fetch('data/discs.json')).json();
    const size = discs.discs.find((d) => d.id === 'dcb').size;
    const cooked = iso('SLUS_013.28'), raw = new Uint8Array(24 * 2352);
    for (let i = 0; i < 24; i++) { raw[i * 2352 + 15] = 2; raw.set(cooked.subarray(i * 2048, (i + 1) * 2048), i * 2352 + 24); }
    const zero = new Blob([new Uint8Array(1 << 20)]), parts = [raw];
    for (let n = size - raw.length; n > 0; n -= zero.size) parts.push(zero.slice(0, Math.min(n, zero.size)));
    const Worker0 = window.Worker;
    const crash = URL.createObjectURL(new Blob(['throw new Error("validation worker crashed");'], { type: 'text/javascript' }));
    window.Worker = class extends Worker0 {
      constructor(url, opts) { super(String(url).includes('hash-worker.js') ? crash : url, opts); }
    };
    try {
      drop([new File(parts, 'worker-crash.bin')]);
      const ended = await idle();
      results.push({ ok: ended && document.querySelector('.slot[data-game="dcb"]').dataset.state === 'empty',
        name: 'hash worker crash ends its check and frees its slot' });
    } finally { window.Worker = Worker0; URL.revokeObjectURL(crash); }
    document.querySelector('#problems').close();
    await new Promise((r) => setTimeout(r, 30));
    // Use the same 7-Zip wasm as the production reader to create tiny real archive fixtures.
    for (const format of ['zip', '7z']) {
      const code = `import factory from 'https://cdn.jsdelivr.net/npm/7z-wasm@1.2.0/7zz.es6.js';
        self.onmessage = async ({data}) => { try {
          const m = await factory({print() {}, printErr() {}});
          m.FS.writeFile('/Other.BIN', data);
          m.FS.writeFile('/other.cue', 'FILE "other.bin" BINARY\\n');
          const args = ['a', '-t${format}', ${format === '7z' ? "'-v1k'," : ''} '/disc.${format}', '/Other.BIN', '/other.cue'];
          try { m.callMain(args); } catch(e) { if (e.status !== 0) throw e; }
          self.postMessage({files:m.FS.readdir('/').filter(n => n.startsWith('disc.')).sort().map(n => new File([m.FS.readFile('/'+n)],n))});
        } catch(e) { self.postMessage({error:String(e)}); } };`;
      const url = URL.createObjectURL(new Blob([code], { type: 'text/javascript' }));
      let made;
      try {
        made = await new Promise((resolve, reject) => {
          const w = new Worker(url, { type: 'module' });
          w.onmessage = ({ data }) => { w.terminate(); resolve(data); };
          w.onerror = (e) => { w.terminate(); reject(new Error(e.message)); };
          const data = iso('OTHER_000.00');
          // Incompressible unused sectors make the 7z span several real volumes.
          crypto.getRandomValues(data.subarray(0, 16 * 2048));
          w.postMessage(data);
        });
      } finally { URL.revokeObjectURL(url); }
      if (made.error) throw new Error(made.error);
      drop(made.files.reverse()); // the first file of a split drop need not be volume 001
      const ended = await idle(60000);
      const problems = [...document.querySelectorAll('#problems-list li')];
      results.push({ ok: ended && problems.length === 1 && problems[0].textContent.includes('Other.BIN') &&
        (format !== '7z' || made.files.length > 1), name: `${format}: archive cue + other game refused once (${made.files.length} volumes)` });
      document.querySelector('#problems').close();
      await new Promise((r) => setTimeout(r, 30));
    }
    return results;
  });
  for (const { ok, name } of results) { console.log(`${ok ? 'ok' : 'FAIL'} ${name}`); if (!ok) failures++; }
  console.log('page errors:', JSON.stringify(errors));
  if (errors.length) failures++;
} finally {
  await browser.close();
  fs.rmSync(profile, { recursive: true, force: true });
}
process.exitCode = failures ? 1 : 0;
