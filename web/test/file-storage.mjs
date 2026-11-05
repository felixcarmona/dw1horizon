// Tiny real Chromium OPFS fixtures, including the production worker's read path. No engine or discs needed.
// node web/test/file-storage.mjs http://127.0.0.1:8767/
import puppeteer from './browser.mjs';
import fs from 'node:fs';
import path from 'node:path';
const profile = fs.mkdtempSync(path.resolve('build/file-storage-'));
const browser = await puppeteer.launch({ executablePath: process.env.CHROMIUM || '/snap/bin/chromium',
  headless: 'new', userDataDir: profile, args: ['--no-sandbox', '--disable-gpu'] });
let failures = 0;
try {
  const page = await browser.newPage();
  await page.goto(process.argv[2], { waitUntil: 'networkidle0' });
  const results = await page.evaluate(async () => {
    const { retryFile, snapshotDisc, discFile, buildDirectory } = await import('./js/engine/storage.js');
    const { Build, EngineError, failureKind } = await import('./js/engine/engine.js');
    const results = [];
    const check = (ok, name) => results.push({ ok, name });
    const root = await navigator.storage.getDirectory();
    const write = async (dir, name, text) => {
      const w = await (await dir.getFileHandle(name, { create: true })).createWritable();
      await w.write(text); await w.close();
    };
    const input = await root.getDirectoryHandle('fixture-input', { create: true });
    await write(input, 'disc.bin', 'original disc');
    const handle = await input.getFileHandle('disc.bin');
    const old = await handle.getFile();
    const copy = await snapshotDisc(old, 'us', { handle });
    await write(input, 'disc.bin', 'changed disc!');
    check(await (await discFile(copy)).text() === 'original disc', 'input snapshot survives changes to selected disc');
    let sourceOpens = 0;
    const current = await handle.getFile();
    const reopened = await snapshotDisc(current, 'reopened', { handle: { async getFile() {
      sourceOpens++;
      if (sourceOpens === 1) throw new DOMException('stale input', 'NotReadableError');
      return handle.getFile();
    } } });
    check(sourceOpens === 2 && await (await discFile(reopened)).text() === 'changed disc!',
      'input copy reopens the source handle once after invalidation');
    const large = new File([new Uint8Array((8 << 20) + 3), 'end'], 'large.bin');
    const largeCopy = await snapshotDisc(large, 'large');
    const largeFile = await discFile(largeCopy);
    check(largeFile.size === large.size && await largeFile.slice(-3).text() === 'end',
      'input copy preserves bytes across the 8 MB chunk boundary');
    const tree = await buildDirectory('tree', true);
    await write(tree, 'fixture', 'version one');
    const production = await (await fetch('./js/engine/worker.js')).text();
    // Run the production read function without loading Pyodide, and invalidate getFile in the worker.
    const script = production.replace("from './storage.js'", `from '${new URL('./js/engine/storage.js', location.href)}'`) + `
let attempts = 0, opens = 0;
const getFile = FileSystemFileHandle.prototype.getFile;
const getDirectory = navigator.storage.getDirectory.bind(navigator.storage);
navigator.storage.getDirectory = async () => { opens++; return getDirectory(); };
self.onmessage = async ({data: mode}) => {
  attempts = 0; opens = 0;
  FileSystemFileHandle.prototype.getFile = async function () {
    attempts++;
    if (mode === 'always' || (mode === 'once' && attempts === 1)) throw new DOMException('stale fixture', 'InvalidStateError');
    return getFile.call(this);
  };
  try { const b = await opfsRead('fixture'); post({ text: new TextDecoder().decode(b), attempts, opens }); }
  catch (e) { post({ error: String(e), attempts, opens }); }
};`;
    const url = URL.createObjectURL(new Blob([script], { type: 'text/javascript' }));
    const worker = new Worker(url, { type: 'module' });
    const ask = (mode) => new Promise((resolve, reject) => {
      worker.onerror = reject;
      worker.onmessage = ({ data }) => { if (data.kind !== 'progress') resolve(data); };
      worker.postMessage(mode);
    });
    try {
      let r = await ask('once');
      check(r.text === 'version one' && r.attempts === 2 && r.opens === 2, 'stale OPFS read reopens from storage root and succeeds once');
      await write(tree, 'fixture', 'version two');
      r = await ask('normal');
      check(r.text === 'version two' && r.attempts === 1, 'later reads obtain a fresh File after another writer');
      r = await ask('always');
      check(r.attempts === 2 && r.opens === 2 && /NotReadableError.*build file fixture/.test(r.error), 'persistent invalidation stops after one retry with file context');
      const build = new Build({ us: old }, { workers: 1 });
      const e = build.explain(new EngineError('engine.jobFailed', {}, r.error));
      check(e.key === 'engine.fileLost' && e.kind === 'file', 'persistent failure has actionable player error');
    } finally { worker.terminate(); URL.revokeObjectURL(url); }
    for (const name of ['NotReadableError', 'InvalidStateError', 'QuotaExceededError', 'SecurityError']) {
      let count = 0;
      try { await retryFile('fixture', () => { count++; throw new DOMException('fixture', name); }); } catch { /* expected */ }
      check(count === (/Readable|State/.test(name) ? 2 : 1), `${name}: bounded retry, no unrelated retries`);
    }
    check(failureKind('NotReadableError: fixture') === 'file', 'NotReadableError classification');
    let stopped = false;
    try { await snapshotDisc(new File(['x'], 'disc.bin'), 'cancel', { check() { throw new Error('cancelled'); } }); }
    catch (e) { stopped = e.message === 'cancelled'; }
    check(stopped, 'copy respects cancellation');
    await root.removeEntry('fixture-input', { recursive: true });
    await root.removeEntry('horizon-build', { recursive: true });
    return results;
  });
  for (const { ok, name } of results) { console.log(`${ok ? 'ok' : 'FAIL'} ${name}`); if (!ok) failures++; }
} finally {
  await browser.close();
  fs.rmSync(profile, { recursive: true, force: true });
}
process.exitCode = failures ? 1 : 0;
