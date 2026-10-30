// web/test (not deployed): js/ecm.js in headless Chromium, through the page's own js/convert-worker.js and
// js/hash-worker.js. puppeteer-core from build/stage9/node/node_modules, /snap/bin/chromium (as run.mjs).
// node ecm-browser.mjs IMAGE.ecm SHA1 [IMAGE2.ecm SHA1 ...]: serves web/ (python3 -m http.server, port 8819 or
// $PORT), gives each .ecm to the convert worker, hashes the File it returns with the hash worker and compares the
// SHA-1; then the first .ecm with a byte flipped in the middle and with a bad magic must come back as
// {error: 'ECM checksum'} and {error: 'not ECM'}.
import puppeteer from './browser.mjs';
import { spawn } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

const args = process.argv.slice(2);
if (args.length < 2 || args.length % 2) {
  console.error('usage: node ecm-browser.mjs IMAGE.ecm SHA1 [...]');
  process.exit(2);
}
const port = process.env.PORT || '8819';
const web = path.join(path.dirname(fileURLToPath(import.meta.url)), '..');
const server = spawn('python3', ['-m', 'http.server', '-b', '127.0.0.1', '-d', web, port], { stdio: 'ignore' });
await new Promise((r) => setTimeout(r, 1000));

const b = await puppeteer.launch({ executablePath: process.env.CHROMIUM || '/snap/bin/chromium', headless: 'new',
  args: ['--no-sandbox', '--disable-gpu'], protocolTimeout: 0 });
let bad = 0;
try {
  const p = await b.newPage();
  p.on('pageerror', (e) => console.log('[pageerror]', e.message));
  await p.goto(`http://127.0.0.1:${port}/test/`);
  await p.evaluate(() => {
    const i = document.createElement('input');
    i.type = 'file'; i.id = 'ecm'; document.body.append(i);
    window.run = (script, message) => new Promise((res) => {
      const w = new Worker(`/js/${script}`, { type: 'module' });
      w.onmessage = ({ data }) => { if (data.progress == null) { w.terminate(); res(data); } };
      w.onerror = (e) => { w.terminate(); res({ error: e.message || 'worker' }); };
      w.postMessage(message);
    });
  });
  const input = await p.$('#ecm');
  for (let i = 0; i < args.length; i += 2) {
    await input.uploadFile(path.resolve(args[i]));
    const r = await p.evaluate(async () => {
      const file = document.querySelector('#ecm').files[0];
      const t = performance.now();
      const out = await window.run('convert-worker.js', { kind: 'ecm', file });
      const s = (performance.now() - t) / 1000;
      if (out.error) return { error: out.error, s };
      const h = await window.run('hash-worker.js', { file: out.file });
      return { name: out.file.name, size: out.file.size, sha1: h.sha1, s };
    });
    const ok = r.sha1 === args[i + 1].toLowerCase();
    if (!ok) bad++;
    console.log(`${ok ? 'ok  ' : 'FAIL'} ${args[i]}: ${r.error ? 'error ' + r.error : `${r.name} ${r.sha1}, ${r.size} bytes`}` +
                `, decoded in ${r.s.toFixed(2)} s${r.size ? `, ${(r.size / 1048576 / r.s).toFixed(0)} MB/s` : ''}`);
  }
  await input.uploadFile(path.resolve(args[0]));
  const errors = await p.evaluate(async () => {
    const file = document.querySelector('#ecm').files[0];
    const mid = Math.floor(file.size / 2);
    const flip = new Uint8Array(await file.slice(mid, mid + 1).arrayBuffer());
    flip[0] ^= 0x10;
    const damaged = new File([file.slice(0, mid), flip, file.slice(mid + 1)], 'damaged.ecm');
    const magic = new File([new Uint8Array([0x45, 0x43, 0x58, 0]), file.slice(4)], 'magic.ecm');
    return [(await window.run('convert-worker.js', { kind: 'ecm', file: damaged })).error,
            (await window.run('convert-worker.js', { kind: 'ecm', file: magic })).error];
  });
  for (const [got, want] of [[errors[0], 'ECM checksum'], [errors[1], 'not ECM']]) {
    if (got !== want) bad++;
    console.log(`${got === want ? 'ok  ' : 'FAIL'} damaged: ${JSON.stringify(got)} (${want} expected)`);
  }
} finally {
  await b.close();
  server.kill();
}
process.exit(bad ? 1 : 0);
