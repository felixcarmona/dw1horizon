// web/test (not deployed): the discs remembered for next time (js/remember.js, js/app.js "remembered discs") in
// headless Chromium, no build. node web/test/remember.mjs URL [SHOTS_DIR]
// The browser's own picker cannot be driven and a synthetic drop gives no handles, so the handles are fakes
// (test.handles in localStorage switches them on, read before the page's scripts, as web/test/langs.mjs does): the
// picker gives one per file the test chose, IndexedDB keeps its stored form, and test.handles says what each does
// next time (queryPermission, requestPermission, a file gone or changed). The copies use the real OPFS.
//   1. handles: a disc chosen is remembered; next visit it is back unhashed (permission already granted, or after
//      one click on "Use my discs from last time"); permission refused, a click the browser does not count, the file
//      gone, the file changed (checked again), the release no longer accepted, × (forgotten), another disc for the
//      game without a handle (the old one forgotten)
//   2. copies (no picker, as in Firefox or Safari): the option with its size, the copy, next visit back unhashed from
//      OPFS; a build in another tab holding the lock (the copy waits), a copy cut short (empty with its reason),
//      "Forget them" (records and OPFS emptied), not enough room, a phone (no option), no IndexedDB (nothing at all)
// With SHOTS_DIR, the remembered slots and the option, in English and Spanish, desktop and phone width.
// The discs: SOURCE_ISOS (default build/isos), as web/test/ui.mjs.
import puppeteer from './browser.mjs';
import fs from 'node:fs';
import path from 'node:path';
const [url, shots] = process.argv.slice(2);
const I = process.env.SOURCE_ISOS || 'build/isos';
const DCB = path.resolve(`${I}/digital-card-battle/Digimon Digital Card Battle (USA).bin`);
const DCB_EU = path.resolve(`${I}/digital-card-battle/Digimon Digital Card Battle (Europe).bin`);
const BUILD = path.join(path.dirname(new URL(import.meta.url).pathname), '../../build');
fs.mkdirSync(BUILD, { recursive: true });
const fx = fs.mkdtempSync(path.join(BUILD, 'remember-'));
const b = await puppeteer.launch({ executablePath: process.env.CHROMIUM || '/snap/bin/chromium', headless: 'new',
  args: ['--no-sandbox', '--disable-gpu'], userDataDir: path.join(fx, 'profile'), protocolTimeout: 0 });
let failed = 0;
const ok = (cond, what) => { console.log(`${cond ? 'ok  ' : 'FAIL'} ${what}`); if (!cond) failed++; };

// Before the page's scripts: the fake handles and picker (test.handles), no picker at all (test.nopicker), a small
// quota (test.quota), no IndexedDB (test.noidb); every Worker made is counted (the hash worker: a disc hashed).
const hooks = () => {
  const get = (k) => { try { return JSON.parse(localStorage.getItem(k)); } catch { return null; } };
  const W = window.Worker;
  window.testWorkers = [];
  window.Worker = class extends W { constructor(u, o) { super(u, o); window.testWorkers.push(String(u)); } };
  if (get('test.nopicker')) window.showOpenFilePicker = undefined;
  if (get('test.noidb')) Object.defineProperty(window, 'indexedDB', { get() { throw new DOMException('no', 'SecurityError'); } });
  const quota = get('test.quota');
  if (quota) navigator.storage.estimate = async () => ({ quota, usage: 0 });
  if (!get('test.handles')) return;
  const files = new Map(), waiting = new Map();
  window.testGive = (id, file) => { files.set(id, file); for (const r of waiting.get(id) || []) r(file); };
  const fileOf = (id) => (files.has(id) ? Promise.resolve(files.get(id)) : new Promise((r) => waiting.set(id, [...(waiting.get(id) || []), r])));
  const permissions = new Map();  // successful requests affect later queries, as on real handles
  const conf = (id) => get('test.handles')?.[id] || {};
  window.testRequests = 0;
  const make = (id) => ({
    kind: 'file', name: id, stored: () => ({ fake: id }),
    async queryPermission() { return permissions.get(id) || conf(id).perm || 'granted'; },
    async requestPermission() {
      window.testRequests++;
      if (conf(id).activation) throw new DOMException('User activation is required', 'SecurityError');
      const permission = conf(id).request || 'granted';
      permissions.set(id, permission);
      return permission;
    },
    async getFile() {
      const c = conf(id);
      if (c.missing) throw new DOMException('A requested file could not be found', 'NotFoundError');
      const f = await fileOf(id);
      return c.lastModified ? new File([f], f.name, { lastModified: c.lastModified }) : f;
    },
  });
  window.testHandles = { revive: (s) => (s?.fake ? make(s.fake) : null) };
  window.showOpenFilePicker = async () => (window.testPick || []).map(make);
};

const p = await b.newPage();
p.on('pageerror', (e) => console.log('[pageerror]', e.message));
await p.evaluateOnNewDocument(hooks);
await p.setViewport({ width: 1280, height: 900 });

const setLocal = (kv) => p.evaluate((kv) => { for (const [k, v] of Object.entries(kv)) {
  if (v == null) localStorage.removeItem(k); else localStorage.setItem(k, JSON.stringify(v)); } }, kv);
// a visit: test.* set first (they are read before the page's scripts), then the page as a player opens it
const visit = async (kv = {}) => {
  await setLocal(kv);
  await p.reload({ waitUntil: 'networkidle0' });
  await p.waitForFunction(() => document.querySelector('.slot'));
};
// files into the page (a fixture <input>): [{name, file}] for the fake handles' getFile
const fixture = async (...files) => {
  await p.evaluate(() => { document.querySelector('#fixture')?.remove(); const i = Object.assign(document.createElement('input'), { type: 'file', multiple: true, id: 'fixture', hidden: true }); document.body.append(i); });
  await (await p.$('#fixture')).uploadFile(...files);
};
const give = async (...files) => { await fixture(...files); await p.evaluate(() => { for (const f of document.querySelector('#fixture').files) window.testGive(f.name, f); }); };
// the picker, as a click on the drop zone: fake handles to these files
const pick = async (...files) => {
  await give(...files);
  await p.evaluate(() => { window.testPick = [...document.querySelector('#fixture').files].map((f) => f.name); });
  await p.click('#add-button');
};
const add = async (...files) => { await (await p.$('#add-input')).uploadFile(...files); await new Promise((r) => setTimeout(r, 300)); };
const idle = () => p.waitForFunction(() => document.querySelector('#patch').dataset.batches === '0'
  && ![...document.querySelectorAll('.slot')].some((s) => s.dataset.state === 'busy'), { timeout: 600000, polling: 200 });
const slot = (game) => p.$eval(`.slot[data-game="${game}"]`, (e) => ({ state: e.dataset.state, store: e.dataset.store, release: e.dataset.release }));
const until = (fn, arg, timeout = 120000) => p.waitForFunction(fn, { timeout, polling: 200 }, arg);
const hashed = () => p.evaluate(() => window.testWorkers.filter((u) => u.includes('hash-worker')).length);
const records = () => p.evaluate(() => new Promise((res) => {
  const r = indexedDB.open('horizon');
  r.onsuccess = () => { try { const q = r.result.transaction('discs').objectStore('discs').getAll(); q.onsuccess = () => res(q.result.map((x) => ({ ...x, handle: x.handle && JSON.stringify(x.handle) }))); } catch { res([]); } };
  r.onerror = () => res(null);
}));
const opfs = () => p.evaluate(async () => {
  const out = [];
  try {
    const root = await (await navigator.storage.getDirectory()).getDirectoryHandle('horizon-discs');
    for await (const [g, d] of root.entries()) for await (const [n, f] of d.entries()) out.push(`${g}/${n}:${(await f.getFile()).size}`);
  } catch { /* none */ }
  return out;
});
const text = (sel) => p.$eval(sel, (e) => (e.closest('[hidden]') ? '' : e.innerText.replace(/\s+/g, ' ').trim()));
const shot = async (lang, name) => {
  if (!shots) return;
  for (const phone of [false, true]) {
    await p.setViewport(phone ? { width: 390, height: 844 } : { width: 1280, height: 900 });
    await p.evaluate(() => document.activeElement?.blur());
    await new Promise((r) => setTimeout(r, 400));
    // the slots, the drop zone and the remembered discs' lines
    const clip = await p.evaluate(() => {
      const top = document.querySelector('#slots').getBoundingClientRect(), r = document.querySelector('#remember');
      const bottom = (r.hidden ? document.querySelector('#add-button') : r).getBoundingClientRect();
      return { x: 0, y: top.top + window.scrollY - 16, width: document.documentElement.clientWidth, height: bottom.bottom - top.top + 32 };
    });
    const file = `${shots}/remember-${lang}-${name}${phone ? '-phone' : ''}.png`;
    await p.screenshot({ path: file, clip, captureBeyondViewport: true });
    console.log(file);
  }
  await p.setViewport({ width: 1280, height: 900 });
};
const NAME = path.basename(DCB);

await p.goto(url, { waitUntil: 'networkidle0' });

// ------------------------------------------------ 1. handles
await visit({ 'test.handles': {} });
await pick(DCB);
await idle();
let s = await slot('dcb'), recs = await records();
ok(s.state === 'ready' && s.store === 'handle', `picked: Card Battle ready, remembered by its handle (${s.state}, ${s.store})`);
ok(recs.length === 1 && recs[0].kind === 'handle' && recs[0].release === 'dcb' && recs[0].name === NAME && /fake/.test(recs[0].handle),
   `one record: ${JSON.stringify(recs.map((r) => [r.game, r.kind, r.release, r.name]))}`);
ok(/remember/.test(await text('#remember-status')) && !(await text('#remember-keep-row')), `the line says it is remembered, no copy offered: ${await text('#remember')}`);

await visit({ 'test.handles': { [NAME]: { perm: 'granted' } } });
await give(DCB);
await until(() => document.querySelector('.slot[data-game="dcb"]').dataset.state === 'ready');
ok((await slot('dcb')).store === 'handle' && await hashed() === 0, 'next visit, permission kept: ready at once, not hashed');

await visit({ 'test.handles': { [NAME]: { perm: 'prompt' } } });
await until(() => document.querySelector('.slot[data-game="dcb"]').dataset.state === 'remembered');
ok(/Digimon Digital Card Battle/.test(await text('#remember-ask')), `permission to ask: the slot waits, the button is offered: ${await text('#remember-ask')}`);
ok(await p.$eval('#patch-button', (x) => x.disabled), 'a remembered disc is not usable before the click');
for (const lang of shots ? ['en', 'es'] : []) { await p.select('#lang', lang); await shot(lang, 'waiting'); }
await p.select('#lang', 'en');
await give(DCB);
await p.click('#remember-use');
await until(() => document.querySelector('.slot[data-game="dcb"]').dataset.state === 'ready');
ok(await hashed() === 0 && await p.evaluate(() => window.testRequests) === 1 && !(await text('#remember-ask')), 'one click: allowed, ready, not hashed, the button gone');

await visit({ 'test.handles': { [NAME]: { perm: 'prompt', activation: true } } });
await until(() => document.querySelector('.slot[data-game="dcb"]').dataset.state === 'remembered');
await p.click('#remember-use');
await new Promise((r) => setTimeout(r, 500));
ok((await slot('dcb')).state === 'remembered' && !!(await text('#remember-ask')) && (await records()).length === 1,
   'a click the browser does not count: still waiting, the button stays, nothing forgotten');

await visit({ 'test.handles': { [NAME]: { perm: 'prompt', request: 'denied' } } });
await until(() => document.querySelector('.slot[data-game="dcb"]').dataset.state === 'remembered');
await p.click('#remember-use');
await until(() => document.querySelector('.slot[data-game="dcb"]').dataset.state === 'empty');
ok(/not allowed/.test(await text('#remember-notes')) && !(await records()).length, `permission refused: empty, said, forgotten: ${await text('#remember-notes')}`);
for (const lang of shots ? ['en', 'es'] : []) { await p.select('#lang', lang); await shot(lang, 'refused'); }
await p.select('#lang', 'en');

await visit({ 'test.handles': {} });
await pick(DCB);
await idle();
await visit({ 'test.handles': { [NAME]: { missing: true } } });
await until(() => document.querySelector('#remember-notes').children.length > 0);
ok((await slot('dcb')).state === 'empty' && /no longer where/.test(await text('#remember-notes')) && !(await records()).length,
   `the file gone: empty, said, forgotten: ${await text('#remember-notes')}`);

await visit({ 'test.handles': {} });
await pick(DCB);
await idle();
await visit({ 'test.handles': { [NAME]: { lastModified: 1e12 } } });
await give(DCB);
await idle();
await until(() => document.querySelector('.slot[data-game="dcb"]').dataset.state === 'ready');
recs = await records();
ok(await hashed() === 1 && (await slot('dcb')).store === 'handle' && recs[0]?.lastModified === 1e12 && !(await text('#remember-notes')),
   'the file changed: checked again, ready, remembered with its new date');

await p.evaluate(() => new Promise((res) => {
  const r = indexedDB.open('horizon');
  r.onsuccess = () => { const st = r.result.transaction('discs', 'readwrite').objectStore('discs'); const q = st.get('dcb');
    q.onsuccess = () => { st.put({ ...q.result, image: { ...q.result.image, sha1: '0'.repeat(40) } }).onsuccess = res; }; };
}));
await visit({ 'test.handles': { [NAME]: { lastModified: 1e12 } } });
await until(() => document.querySelector('#remember-notes').children.length > 0);
ok((await slot('dcb')).state === 'empty' && /no longer accepts/.test(await text('#remember-notes')) && !(await records()).length,
   `a release this version no longer accepts: dropped, said: ${await text('#remember-notes')}`);

await visit({ 'test.handles': {} });
await pick(DCB);
await idle();
await p.click('.slot[data-game="dcb"] .disc-remove');
await new Promise((r) => setTimeout(r, 300));
ok((await slot('dcb')).state === 'empty' && !(await records()).length, '× empties the slot and forgets the disc');
await visit({ 'test.handles': { [NAME]: {} } });
await new Promise((r) => setTimeout(r, 500));
ok((await slot('dcb')).state === 'empty' && !(await text('#remember')), 'next visit: nothing comes back, nothing said');

await pick(DCB);
await idle();
await add(DCB_EU);
await idle();
ok((await slot('dcb')).release === 'dcb-eu' && !(await records()).length, 'another disc for the game, without a handle: the remembered one is forgotten');

// ------------------------------------------------ 2. copies
await p.evaluate(() => indexedDB.deleteDatabase('horizon'));
await visit({ 'test.handles': null, 'test.nopicker': true });
await add(DCB);
await idle();
const keepText = await text('#remember-keep-row');
ok(/Keep these discs.*0[.,]2 GB/.test(keepText) && !(await p.$eval('#remember-keep', (x) => x.checked)), `no handles: the copy is offered, off, with its size: ${keepText}`);
for (const lang of shots ? ['en', 'es'] : []) { await p.select('#lang', lang); await shot(lang, 'offered'); }
await p.select('#lang', 'en');
await p.click('#remember-keep');
await until(() => document.querySelector('.slot[data-game="dcb"]').dataset.store === 'copy');
recs = await records();
let kept = await opfs();
ok(recs.length === 1 && recs[0].kind === 'copy' && kept.length === 1 && kept[0] === `dcb/${NAME}:${fs.statSync(DCB).size}`,
   `copied: ${kept}, ${JSON.stringify(recs.map((r) => [r.game, r.kind]))}`);
ok(/kept in this browser.*0[.,]2 GB/.test(await text('#remember-status')), `the line says what is kept: ${await text('#remember-status')}`);
await visit();
await until(() => document.querySelector('.slot[data-game="dcb"]').dataset.state === 'ready');
ok((await slot('dcb')).store === 'copy' && await hashed() === 0, 'next visit: ready from the copy, not hashed');
for (const lang of shots ? ['en', 'es'] : []) { await p.select('#lang', lang); await shot(lang, 'kept'); }
await p.select('#lang', 'en');

// another tab building: the copy waits for the lock
await p.click('#remember-forget');
await new Promise((r) => setTimeout(r, 300));
ok((await slot('dcb')).state === 'empty' && !(await records()).length && !(await opfs()).length && !(await p.evaluate(() => localStorage.getItem('horizon.keepDiscs'))),
   '"Forget them": the slot empty, no record, no copy, the option off');
const other = await b.newPage();
await other.goto(url, { waitUntil: 'networkidle0' });
await other.evaluate(() => new Promise((held) => { window.lock = navigator.locks.request('horizon-build', () => { held(); return new Promise((r) => { window.unlock = r; }); }); }));
await p.bringToFront();                    // (a tab in the background polls once a minute)
await add(DCB);
await idle();
await p.click('#remember-keep');
await until(() => /another tab/.test(document.querySelector('#remember-line').textContent));
ok(!(await opfs()).length, `a build in another tab: the copy waits (${await text('#remember-line')})`);
await other.evaluate(() => window.unlock());
await until(() => document.querySelector('.slot[data-game="dcb"]').dataset.store === 'copy', null, 60000);
ok((await opfs()).length === 1, 'the other tab done: copied');
await other.close();
await p.bringToFront();

// a copy cut short (the browser cleared part of it)
await p.evaluate(async () => {
  const d = await (await (await navigator.storage.getDirectory()).getDirectoryHandle('horizon-discs')).getDirectoryHandle('dcb');
  for await (const [, f] of d.entries()) { const w = await f.createWritable({ keepExistingData: true }); await w.truncate(1000); await w.close(); }
});
await visit();
await until(() => document.querySelector('#remember-notes').children.length > 0);
ok((await slot('dcb')).state === 'empty' && /cleared the copy/.test(await text('#remember-notes')) && !(await records()).length && !(await opfs()).length,
   `a copy cut short: empty, said, record and copy gone: ${await text('#remember-notes')}`);

// not enough room
await visit({ 'test.quota': 300 * 2 ** 20 });
await add(DCB);
await idle();
await p.click('#remember-keep');
await until(() => /not enough room/.test(document.querySelector('#remember-line').textContent));
ok(!(await p.$eval('#remember-keep', (x) => x.checked)) && !(await opfs()).length && !(await records()).length,
   `not enough room for it and a build: said, nothing copied, the option off: ${await text('#remember-line')}`);
await setLocal({ 'test.quota': null });

// a phone: no copy offered
await p.setUserAgent('Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Mobile Safari/537.36');
await visit();
await add(DCB);
await idle();
ok(!(await text('#remember')), 'a phone: no copy offered');
await p.setUserAgent(await b.userAgent());

// no IndexedDB (a private window, storage blocked): the page as before
await visit({ 'test.noidb': true });
await add(DCB);
await idle();
ok((await slot('dcb')).state === 'ready' && !(await text('#remember')), 'no IndexedDB: the disc is used, nothing remembered or offered');

await b.close();
fs.rmSync(fx, { recursive: true, force: true });
console.log(failed ? `${failed} FAILED` : 'all ok');
process.exit(failed ? 1 : 0);
