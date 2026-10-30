// Real Chromium OPFS and Web Locks with tiny scripted worker outputs: no game build.
// node web/test/lifecycle.mjs http://127.0.0.1:8767/
import puppeteer from './browser.mjs';
import fs from 'node:fs';
import path from 'node:path';
const profile = fs.mkdtempSync(path.resolve('build/lifecycle-'));
const browser = await puppeteer.launch({ executablePath: process.env.CHROMIUM || '/snap/bin/chromium', headless: 'new',
  userDataDir: profile, args: ['--no-sandbox', '--disable-gpu'] });
let failures = 0;
try {
  const page = await browser.newPage();
  if (process.env.ENGINE_SOURCE) {
    await page.setRequestInterception(true);
    page.on('request', (r) => r.url().includes('/js/engine/engine.js')
      ? r.respond({ contentType: 'text/javascript', body: fs.readFileSync(process.env.ENGINE_SOURCE, 'utf8') }) : r.continue());
  }
  await page.goto(process.argv[2], { waitUntil: 'networkidle0' });
  const results = await page.evaluate(async () => {
    const { Build, tidyStorage } = await import('./js/engine/engine.js');
    // Preserve the deployed engine; only this page's fetch is replaced for the tiny plan.
    const fetch0 = window.fetch;
    const results = [];
    const check = (ok, name) => results.push({ ok, name });
    const root = await navigator.storage.getDirectory();
    const put = async (dir, name, text) => {
      const w = await (await dir.getFileHandle(name, { create: true })).createWritable();
      await w.write(text); await w.close();
    };
    const dir = async () => root.getDirectoryHandle('horizon-build', { create: true });
    const exists = async (name) => { try { await (await dir()).getFileHandle(name); return true; } catch { return false; } };
    const plan = { paths: [], packs: [], files: [], dirs: [], extract: [], source_discs: [],
      pyodide: { files: [] }, out: 'out', manifest: 'out/manifest.json', write_est: 1,
      release: { holes_bytes: 0, outputs: { us: { size: 4 } }, version: 'fixture' },
      steps: [{ name: 'fixture', jobs: 1 }], jobs: [{ id: 0, step: 'fixture', name: 'fixture',
        part: 'build', deps: [], bundle: [], tree: [], globs: [], absent: [], mkdirs: [], lists: [], est: 1, prio: 1 }] };
    let gate = null;
    window.fetch = async (url, ...args) => {
      if (String(url).endsWith('/current.json')) {
        if (gate) await gate;
        return Response.json({ version: 'lifecycle-fixture' });
      }
      if (String(url).includes('/lifecycle-fixture/plan.json')) return Response.json(plan);
      return fetch0(url, ...args);
    };
    class TinyBuild extends Build {
      spawn(id, route) {
        const s = { id, load: { load: 0, code: 0, heap: 1 }, busy: false, dead: false };
        s.w = { terminate() { s.dead = true; }, postMessage(m) {
          setTimeout(async () => {
            if (s.dead) return;
            if (m.kind === 'extract') route(s, { kind: 'done', ok: true, key: 'us', title: 'fixture', files: 0, bytes: 0, secs: 0, heap: 1 });
            if (m.kind === 'job') {
              if (s.owner.oomTest && !s.owner.retried) {
                s.owner.retried = true;
                route(s, { kind: 'error', msg: 'MemoryError' }); return;
              }
              const tree = await (await dir()).getDirectoryHandle('tree', { create: true });
              const j = await tree.getDirectoryHandle('@j0', { create: true });
              const out = await j.getDirectoryHandle('out', { create: true });
              await put(out, 'manifest.json', '{"files":{}}');
              route(s, { kind: 'done', ok: true, written: [['out/manifest.json']], removed: [],
                secs: 0.01, sync: 0, run: 0, loaded: 0, heap: 1, mem: 0 });
            }
            if (m.kind === 'write') {
              await put(await dir(), 'image.bin', 'test');
              route(s, { kind: 'done', ok: true, size: 4, sha1: 'fixture', secs: 0, heap: 1 });
            }
          }, 0);
        } };
        s.owner = this;
        s.ready = Promise.resolve(s);
        return s;
      }
    }
    try {
      const build = new TinyBuild({ us: new File([], 'fixture.bin') }, { workers: 1 });
      build.oomTest = 'fixture';
      await build.run();
      check(build.state.phase === 'done' && build.state.memoryRetries === 1, 'OOM job retries and finishes');
      check(await exists('done.json'), 'completion marker is at OPFS root');
      await tidyStorage();
      check(await exists('image.bin'), 'page-load cleanup preserves completed image');

      let releaseFetch;
      gate = new Promise((r) => { releaseFetch = r; });
      const old = new TinyBuild({ us: new File([], 'fixture.bin') }, { workers: 1 });
      const run = old.run().catch((e) => e.key);
      // Wait until run has acquired its lock and started the plan fetch.
      await new Promise((r) => setTimeout(r, 30));
      old.cancel();
      let settled = false;
      run.then(() => { settled = true; });
      await new Promise((r) => setTimeout(r, 30));
      check(!settled, 'cancel holds lock until outstanding plan read settles');
      gate = null;
      releaseFetch();
      check(await run === 'build.cancelled', 'cancel reports its error');
      // A subsequent build must not race any work left by the canceled run.
      await put(await dir(), 'sentinel', 'next build');
      await new Promise((r) => setTimeout(r, 100));
      check(await exists('sentinel') && old.state.phase === 'error', 'canceled run cannot delete next build files');
      const stopped = new TinyBuild({ us: new File([], 'fixture.bin') }, { workers: 1 });
      stopped.onState = (st) => { if (st.phase === 'extract') queueMicrotask(() => stopped.cancel()); };
      const canceled = await Promise.race([stopped.run().catch((e) => e.key),
        new Promise((r) => setTimeout(() => r('timeout'), 2000))]);
      check(canceled === 'build.cancelled' && stopped.slots.length === 0, 'cancel during worker startup settles and terminates workers');
      const again = new TinyBuild({ us: new File([], 'fixture.bin') }, { workers: 1 });
      await again.run();
      check(again.state.phase === 'done', 'a new build finishes after worker cancellation');

      const other = await browserLockProbe();
      check(other, 'a second build refuses an occupied Web Lock');
    } finally {
      window.fetch = fetch0;
      await root.removeEntry('horizon-build', { recursive: true }).catch(() => {});
      const cache = await caches.open('horizon-engine');
      for (const req of await cache.keys()) if (req.url.includes('/lifecycle-fixture/')) await cache.delete(req);
    }
    return results;

    async function browserLockProbe() {
      let release, entered;
      const acquired = new Promise((r) => { entered = r; });
      const lock = navigator.locks.request('horizon-build', async () => {
        entered(); await new Promise((r) => { release = r; });
      });
      await acquired;
      try {
        return await new TinyBuild({ us: new File([], 'fixture.bin') }).run().then(() => false, (e) => e.key === 'engine.otherTab');
      } finally { release(); await lock; }
    }
  });
  // A second tab opening after deployment must leave the running tab's old engine cache alone.
  await page.evaluate(async () => {
    const cache = await caches.open('horizon-engine');
    await cache.put(new URL('engine/previous/fixture', location.href), new Response('running engine'));
    await new Promise((entered) => {
      window.heldLock = navigator.locks.request('horizon-build', async () => {
        entered(); await new Promise((r) => { window.releaseLock = r; });
      });
    });
  });
  try {
    const second = await browser.newPage();
    if (process.env.ENGINE_SOURCE) {
      await second.setRequestInterception(true);
      second.on('request', (r) => r.url().includes('/js/engine/engine.js')
        ? r.respond({ contentType: 'text/javascript', body: fs.readFileSync(process.env.ENGINE_SOURCE, 'utf8') }) : r.continue());
    }
    await second.goto(new URL('test/', process.argv[2]).href);
    const crossTab = await second.evaluate(async () => {
      const { Build, tidyStorage } = await import('/js/engine/engine.js');
      const refused = await new Build({ us: new File([], 'fixture') }).run().then(() => false, (e) => e.key === 'engine.otherTab');
      await tidyStorage();
      const cache = await caches.open('horizon-engine');
      return { refused, kept: !!await cache.match(new URL('/engine/previous/fixture', location.href)) };
    });
    results.push({ ok: crossTab.refused, name: 'second tab cannot start while first tab holds lock' },
      { ok: crossTab.kept, name: 'second tab cleanup preserves running tab engine cache' });
    await second.close();
  } finally { await page.evaluate(async () => { window.releaseLock(); await window.heldLock; }); }
  for (const { ok, name } of results) { console.log(`${ok ? 'ok' : 'FAIL'} ${name}`); if (!ok) failures++; }
} finally {
  await browser.close();
  fs.rmSync(profile, { recursive: true, force: true });
}
process.exitCode = failures ? 1 : 0;
