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
    const { retryFile, snapshotDisc, discFile, buildDirectory, selectedFile, InputDiscError } = await import('./js/engine/storage.js');
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
    const refused = { async getFile() { sourceOpens++; throw new DOMException('platform refuses handle', 'NotAllowedError'); } };
    const retained = await snapshotDisc(current, 'retained', { handle: refused });
    check(sourceOpens === 0 && await (await discFile(retained)).text() === 'changed disc!',
      'readable selected File is copied without reopening a refused handle');
    const stale = { size: current.size, name: current.name, lastModified: current.lastModified,
      slice() { return { async arrayBuffer() { throw new DOMException('stale input', 'NotReadableError'); } }; } };
    const events = [];
    const permitted = {
      async queryPermission(options) { events.push(`query:${options.mode}`); return 'prompt'; },
      async requestPermission(options) { events.push(`request:${options.mode}`); return 'granted'; },
      async getFile() { events.push('getFile'); return current; },
    };
    const reopened = await snapshotDisc(stale, 'reopened', { handle: permitted });
    check(events.join() === 'query:read,request:read,getFile' && await (await discFile(reopened)).text() === 'changed disc!',
      'stale selected File is recovered with permission before handle read');
    let reads = 0;
    const transient = { size: current.size, name: current.name, lastModified: current.lastModified,
      slice(...args) { return { async arrayBuffer() {
        if (++reads === 1) throw new DOMException('provider refused read', 'NotAllowedError');
        return current.slice(...args).arrayBuffer();
      } }; } };
    const fallback = await snapshotDisc(transient, 'fallback', { handle: refused });
    check(reads === 2 && sourceOpens === 2 && await (await discFile(fallback)).text() === 'changed disc!',
      'refused handle falls back to retained File on the one copy retry');
    for (const name of ['NotAllowedError', 'NotReadableError', 'InvalidStateError', 'SecurityError', 'NotFoundError']) {
      let attempts = 0;
      const unreadable = { size: 1, name: 'disc.bin', slice() { return { async arrayBuffer() {
        attempts++; throw new DOMException('provider unavailable', name);
      } }; } };
      let failure;
      try { await snapshotDisc(unreadable, 'unreadable'); } catch (e) { failure = e; }
      check(attempts === 2 && failure instanceof InputDiscError && failure.message.includes(name),
        `${name}: input reads stop after one retry and preserve the cause`);
    }
    for (const permission of ['prompt', 'denied']) {
      const calls = [];
      try { await selectedFile({
        async queryPermission() { calls.push('query'); return permission; },
        async requestPermission() { calls.push('request'); return permission; },
        async getFile() { calls.push('getFile'); return current; },
      }); } catch { /* expected */ }
      check(calls.join() === 'query,request', `${permission}: refusal never calls getFile`);
    }
    let opens = 0;
    await selectedFile({ async queryPermission() { return 'granted'; }, async getFile() {
      if (++opens === 1) throw new DOMException('transient refusal', 'NotAllowedError');
      return current;
    } });
    check(opens === 2, 'picker handle refusal is retried once');
    let changed;
    try { await snapshotDisc(stale, 'changed', { handle: { async getFile() {
      return new File(['different!!!'], current.name, { lastModified: current.lastModified + 1 });
    } } }); } catch (e) { changed = e; }
    check(changed instanceof InputDiscError && /changed/.test(changed.message), 'changed disc is never silently substituted');
    const classified = new Build({ us: current }, { workers: 1 }).explain(new EngineError('engine.discLost', {}, 'NotAllowedError'));
    check(classified.key === 'engine.discLost' && classified.kind === 'file', 'input refusal has disc-specific guidance, not storage advice');
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
