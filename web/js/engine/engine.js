// The web engine: builds the "everything" disc from the player's discs, here in the browser.
//
//   1. the engine's files (engine/<version>/: Pyodide, the bundle's packs, plan.json) into the Cache API, once
//   2. a worker reads the player's Digimon World disc and writes the files the build reads (extracted/) to OPFS, then
//      the files of the other three games the imported species' models are made from (build/everything/source-games/,
//      checked by SHA-1: tools/derive/importers/discs.py)
//   3. the jobs of plan.json (tools/derive's steps: prepare, units, finish, or build, finish) on a pool of workers,
//      each job when the jobs it waits for are done; one finish at a time (they share the manifest)
//   4. a worker checks every built file against the release's SHA-1 and writes the disc image to OPFS
// The page gets a state object on every change (onState) and, at the end, the image (a File) and its .cue.
//
// Storage does not grow: a build starts by removing the last one's image and tree (and the engine versions that are
// not the current one from the Cache API); a finished build leaves only the image (and done.json, its size and
// SHA-1); tidyStorage(), when the page loads, removes what a stopped or crashed build left. One build at a time
// across tabs (Web Locks: 'horizon-build').

const ENGINE = new URL('../../engine/', import.meta.url).href;
const OPFS_DIR = 'horizon-build';
const CACHE = 'horizon-engine';
const IMAGE = 'image.bin';
const DONE = 'done.json';
const LOCK = 'horizon-build';
export const OUTPUT_NAME = 'Digimon World Horizon';

// Memory (web/README.md "Memory"): a worker whose WebAssembly heap grew past RECYCLE_MB after a job is replaced by a
// fresh one (a heap never shrinks; a fresh Pyodide starts at 36 MB, ~3 s from the cache); each worker keeps at most
// FILES_MB of bundle and tree files between jobs.
const RECYCLE_MB = 110;
const FILES_MB = 24;
// A worker that has not started after this long never will: an out-of-memory in a worker's start may report nothing.
const START_SECS = 120;
// The estimates the overall bar starts from (seconds; measured, web/README.md), before the build measures its own
const EST = { download_rate: 4 * 2 ** 20, extract: 8, source: 4, start: 3, check: 6 };

export class EngineError extends Error {
  constructor(key, vars = {}, detail = '') { super(key); this.key = key; this.vars = vars; this.detail = detail; }
}

// What this browser lacks for a build (null: nothing).
export function missingSupport() {
  if (typeof Worker === 'undefined' || typeof WebAssembly === 'undefined') return 'engine.noWasm';
  if (!navigator.storage || !navigator.storage.getDirectory) return 'engine.noOpfs';
  // (createSyncAccessHandle exists in dedicated workers only: the worker checks it when it starts)
  if (typeof DecompressionStream === 'undefined') return 'engine.noStreams';
  try { new DecompressionStream('deflate-raw'); } catch { return 'engine.noStreams'; }
  return null;
}

// How many build workers (web/README.md "Workers"). A worker takes ~0.35 GB at its peak (its WebAssembly heap, its
// files and Pyodide itself); every worker shares the tab's process, so too many can take the whole tab down.
//  - cores: one is left to the page; past 6 workers the build gains little (the measured curve) for a lot of memory.
//  - memory known (navigator.deviceMemory, Chromium: GB, rounded down, at most 8): 2 GB for the system and the page,
//    then one worker per 0.5 GB of the rest; 2 with 4 GB or less.
//  - memory unknown (Firefox, Safari): 4, a size that fits any computer a build makes sense on (8 GB).
//  - phones and tablets: 2, or 1 under 8 GB (a tab killed for memory cannot be caught, so a phone stays well away).
// If a worker does not start, the build goes on with the ones that did. If a job fails on a worker (out of memory or
// anything else), it is given again to the others and the build goes on with one worker fewer (jobFailure in _run).
export const MAX_WORKERS = 6;
export function workerCount() {
  const hc = navigator.hardwareConcurrency || 4;
  let n = Math.max(1, Math.min(hc - 1, MAX_WORKERS));
  const mem = navigator.deviceMemory;
  if (mem) n = Math.min(n, mem <= 4 ? 2 : Math.floor((mem - 2) / 0.5));
  else n = Math.min(n, 4);
  if (isMobile()) n = Math.min(n, mem >= 8 ? 2 : 1);
  return Math.max(1, n);
}
// A phone or a tablet: little memory for the build, so nothing is copied for next time either (js/remember.js).
export const isMobile = () => /Android|iPhone|iPad|Mobile/i.test(navigator.userAgent);

async function json(url) {
  const r = await fetch(url, { cache: 'no-cache' });
  if (!r.ok) throw new EngineError('engine.notDeployed', {}, `${url}: HTTP ${r.status}`);
  return r.json();
}

export async function loadPlan() {
  const cur = await json(`${ENGINE}current.json`);
  const base = `${ENGINE}${cur.version}/`;
  let plan;
  try {
    plan = await (await cacheFirst(`${base}plan.json`)).json();
  } catch (e) { throw new EngineError('engine.notDeployed', {}, String(e)); }
  const P = plan.paths;
  for (const j of plan.jobs) {
    for (const k of ['tree', 'bundle', 'absent', 'mkdirs']) j[k] = j[k].map((i) => P[i]);
    j.lists = Object.fromEntries(j.lists.map(([i, n]) => [P[i], n]));
  }
  return { base, plan, version: cur.version };
}

async function openCache() { try { return await caches.open(CACHE); } catch { return null; } }

async function cacheFirst(url, onBytes) {
  const c = await openCache();
  if (c) { const r = await c.match(url); if (r) { if (onBytes) onBytes(Number(r.headers.get('content-length')) || 0, true); return r; } }
  const r = await fetch(url);
  if (!r.ok) throw new EngineError('engine.download', { file: url.split('/').pop() }, `HTTP ${r.status}`);
  if (!onBytes && !c) return r;
  // read it here (progress), keep it
  const reader = r.body.getReader();
  const parts = [];
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    parts.push(value);
    if (onBytes) onBytes(value.length, false);
  }
  const blob = new Blob(parts, { type: r.headers.get('content-type') || 'application/octet-stream' });
  const keep = new Response(blob, { headers: { 'content-type': blob.type, 'content-length': String(blob.size) } });
  if (c) { try { await c.put(url, keep.clone()); } catch { /* quota: not kept */ } }
  return keep;
}

// ---------------------------------------------------------------- storage

// The engine versions that are not `version` out of the Cache API.
async function dropOldEngines(version) {
  const c = await openCache();
  if (c) for (const req of await c.keys()) if (!req.url.includes(`/engine/${version}/`)) await c.delete(req);
}

// Runs fn(true) holding the build lock, fn(false) when another tab holds it (no Web Locks: fn(true)). The page's
// remembered discs (js/remember.js) copy and delete under it too, so a copy never races a build in any tab.
export function withLock(fn) {
  if (!navigator.locks) return fn(true);
  return navigator.locks.request(LOCK, { ifAvailable: true }, (lock) => fn(!!lock));
}

// When the page loads: the old engines out of the cache; in OPFS only a finished image stays (image.bin with its
// done.json, the size matching); the tree and anything else of a stopped or crashed build go. Nothing is shown.
export async function tidyStorage() {
  await withLock(async (free) => {
    if (!free) return;                                   // a build runs in another tab
    try {
      const cur = await json(`${ENGINE}current.json`);
      await dropOldEngines(cur.version);
    } catch { /* no engine here, or offline: the cache stays as it is */ }
    if (!navigator.storage || !navigator.storage.getDirectory) return;
    try { await (await navigator.storage.getDirectory()).removeEntry('horizon-room', { recursive: true }); } catch { /* none */ }
    let dir;
    try { dir = await (await navigator.storage.getDirectory()).getDirectoryHandle(OPFS_DIR); } catch { return; }
    let keepImage = false;
    try {
      const done = JSON.parse(await (await (await dir.getFileHandle(DONE)).getFile()).text());
      keepImage = (await (await dir.getFileHandle(IMAGE)).getFile()).size === done.size;
    } catch { /* no finished image */ }
    const names = [];
    for await (const name of dir.keys()) names.push(name);
    for (const name of names) {
      if (keepImage && (name === IMAGE || name === DONE)) continue;
      try { await dir.removeEntry(name, { recursive: true }); } catch { /* in use */ }
    }
  });
}

// The room a build needs in this browser's storage: the tree (twice the holes), the largest image, 256 MB for the rest.
const roomFor = (plan) => 2 * plan.release.holes_bytes + Math.max(...Object.values(plan.release.outputs).map((o) => o.size)) + 2 ** 28;
// The same for the page before a build (js/remember.js keeps that much free when it copies discs); without an engine
// here, about what the current release needs.
export async function buildRoom() {
  try { return roomFor((await loadPlan()).plan); } catch { return 2 * 2 ** 30; }
}

// Is there room for `need` bytes more in this browser's storage? {need, reason: null (it fits, as far as the browser
// says) | 'quota' (it does not) | 'blocked' (the page may not store files: a private window in Firefox, site data
// blocked) | 'unkept' (storage held in memory, a private or incognito window: it may not fit), free (bytes, when the
// browser's estimate is to be believed), msg}. storage.estimate() first: Firefox and Safari report their real
// quota; Chromium reports a fixed one (usage + 10 GB, in private windows too), so the storage is asked as well
// (js/engine/room-worker.js). `ask`: the bytes the probe asks for, when not `need` (tests).
export async function checkRoom(need, ask = need) {
  const out = { need, reason: null, free: null, msg: '' };
  if (!navigator.storage || !navigator.storage.getDirectory) return out;      // (missingSupport says it)
  try {
    const est = await navigator.storage.estimate();
    if (est.quota) out.free = est.quota - est.usage;
    if (out.free != null && out.free < ask) return { ...out, reason: 'quota', msg: `estimate: ${est.usage} used of ${est.quota}` };
  } catch { /* no estimate: the probe says */ }
  if (typeof Worker === 'undefined') return out;
  const r = await new Promise((res) => {
    let w;
    try { w = new Worker(new URL('./room-worker.js', import.meta.url)); } catch (e) { res({ reason: 'error', msg: String(e) }); return; }
    const end = (m) => { clearTimeout(late); w.terminate(); res(m); };
    const late = setTimeout(() => end({ reason: 'error', msg: 'no answer' }), 20000);
    w.onmessage = ({ data }) => end(data);
    w.onerror = (e) => { e.preventDefault(); end({ reason: 'error', msg: e.message || 'the worker did not load' }); };
    w.postMessage({ bytes: ask });
  });
  // (a probe that could not run says nothing: the build finds out)
  if (r.reason && r.reason !== 'error') return { ...out, reason: r.reason, msg: r.msg };
  if (r.reason) out.msg = r.msg;
  return out;
}

// What kind of failure an error's text is: 'storage' (the browser's storage is full: QuotaExceededError, a disk with
// no room), 'blocked' (storage not allowed), 'memory', 'network' or null.
const STORAGE = /QuotaExceededError|exceed(s|ed)? (its|the) (storage )?quota|quota (has been|was) exceeded|No space (available|left)|NS_ERROR_FILE_NO_DEVICE_SPACE|disk is full|not enough space/i;
const BLOCKED = /SecurityError|The operation is insecure|NS_ERROR_DOM_SECURITY_ERR/;
const NETWORK = /Failed to fetch|NetworkError|Load failed|network error|ERR_INTERNET_DISCONNECTED|ERR_NETWORK_CHANGED/i;
export function failureKind(text) {
  text = String(text || '');
  if (STORAGE.test(text)) return 'storage';
  if (BLOCKED.test(text)) return 'blocked';
  if (MEMORY.test(text)) return 'memory';
  if (NETWORK.test(text)) return 'network';
  return null;
}

async function opfsRoot() {
  return (await navigator.storage.getDirectory()).getDirectoryHandle(OPFS_DIR, { create: true });
}

async function opfsDir(path) {
  let d = await opfsRoot();
  for (const p of path.split('/').filter(Boolean)) d = await d.getDirectoryHandle(p, { create: true });
  return d;
}

async function opfsText(path) {
  let d = await opfsRoot();
  const parts = path.split('/');
  for (const p of parts.slice(0, -1)) d = await d.getDirectoryHandle(p);
  return (await (await d.getFileHandle(parts.at(-1))).getFile()).text();
}

async function opfsPut(path, data) {
  const i = path.lastIndexOf('/');
  const d = await opfsDir(i < 0 ? '' : path.slice(0, i));
  const w = await (await d.getFileHandle(path.slice(i + 1), { create: true })).createWritable();
  await w.write(data);
  await w.close();
}

// Where a tree file of `token` is in OPFS under tree/ (worker.js locOf): the player's files at their path, a job's
// outputs under @<token>/
const locOf = (path, token) => (token === 'x' ? path : `@${token}/${path}`);

const sleep = (ms) => new Promise((res) => setTimeout(res, ms));
// What a terminated worker held is given back a moment later: a start that failed gets one more try after this.
const SETTLE_MS = 2000;

const norm = (p) => { const o = []; for (const s of p.split('/')) { if (s === '..') o.pop(); else if (s && s !== '.') o.push(s); } return o.join('/'); };

// A worker's message is about memory: Python's MemoryError, a WebAssembly memory that could not grow, an abort.
const MEMORY = /MemoryError|out of memory|Memory\.grow|Cannot enlarge memory|Aborted\(|could not allocate|RangeError: Array buffer allocation|memory access out of bounds/i;

// ---------------------------------------------------------------- the build

export class Build {
  // discs: {us: File (Digimon World), sources: {dcb, dw2, dw2003: File} (the three games the imported species' models
  // are made from: plan.source_discs), titles: {game: its title} (for the messages)}
  constructor(discs, { onState, workers = workerCount() } = {}) {
    if (discs instanceof Blob) discs = { us: discs };   // (a page from before the four discs, still in a cache)
    this.file = discs.us;
    this.sources = discs.sources || {};
    this.titles = discs.titles || {};
    this.n = workers;
    this.onState = onState || (() => {});
    this.state = { phase: 'start', workers: [], steps: [], units: { done: 0, total: 0 }, download: { done: 0, total: 0 },
                   extract: { done: 0, total: 0 }, check: { done: 0, total: 0 }, write: { done: 0, total: 0 },
                   t0: performance.now(), eta: null, progress: 0, now: [], log: [], times: {}, workerCount: workers };
    this.stopped = false;
    this.slots = [];                           // the build workers: {id, w, busy, job, ready, load, dead}
    this.oomTest = null;                       // (tests: a job name whose first run fails as out of memory)
    this.quotaTest = null;                     // (tests: a job name, or 'first', that fails as the storage being full)
    this.roomTest = 0;                         // (tests: the bytes the room check asks for instead of the build's)
    this.need = 0;                             // the room the build needs (bytes), once the plan is read
    this.recycleMB = RECYCLE_MB;
  }

  emit() {
    const st = this.state;
    st.elapsed = (performance.now() - st.t0) / 1000;
    const left = this.remaining();
    if (left != null) {
      st.eta = left;
      // the overall bar: time spent over time spent and left, never going back
      if (st.phase === 'done') st.progress = 1;
      else if (st.phase !== 'error') st.progress = Math.max(st.progress, Math.min(0.99, st.elapsed / (st.elapsed + left)));
    }
    this.onState(st);
  }
  log(s) { this.state.log.push(s); if (this.state.log.length > 1024) this.state.log.shift(); }

  // Seconds left: what is left of this phase, and the estimates of the ones after it.
  remaining() {
    const st = this.state;
    const plan = this.plan;
    if (!plan) return null;
    const speed = this.speed || 1;
    const write = plan.write_est * speed;
    const jobs = this.jobsLeft ? this.jobsLeft() : speed * this.jobsEstimate(plan.jobs, this.n);
    const extract = EST.extract + (plan.source_discs || []).length * EST.source + EST.start;
    switch (st.phase) {
      case 'start': return null;
      case 'download': {
        const t = (performance.now() - this.td0) / 1000;
        const rate = st.download.fresh > 2 ** 20 && t > 1 ? st.download.fresh / t : EST.download_rate;
        return (st.download.total - st.download.done) / rate + extract + jobs + write;
      }
      case 'extract': {
        const f = st.extract.total ? st.extract.done / st.extract.total : 0;
        return extract * (1 - f) + jobs + write;
      }
      case 'build': return jobs + write;
      case 'check': return write * (1 - (EST.check / plan.write_est) * (st.check.total ? st.check.done / st.check.total : 0));
      case 'write': return write * (1 - EST.check / plan.write_est) * (1 - (st.write.total ? st.write.done / st.write.total : 0));
      default: return 0;
    }
  }

  // Seconds the jobs take with n workers: the longer of the critical path and the work shared out.
  jobsEstimate(jobs, n) {
    if (!jobs.length) return 0;
    return Math.max(Math.max(...jobs.map((j) => j.prio)), jobs.reduce((a, j) => a + j.est, 0) / n);
  }

  cancel() {
    this.stopped = true;
    for (const s of this.slots) { s.dead = true; s.w.terminate(); }
    this.slots = [];
    if (this.extractor) { this.extractor.dead = true; this.extractor.w.terminate(); }
    if (this._abort) this._abort(new EngineError('build.cancelled'));
  }

  checkStopped() {
    if (this.stopped) throw new EngineError('build.cancelled');
  }

  // Terminating a worker does not settle its message promise. Race those waits with cancellation;
  // filesystem/network operations must finish under the lock, then checkStopped before continuing.
  waitWorker(promise) { return Promise.race([promise, this.aborted]); }

  async run() {
    const r = await withLock(async (free) => {
      if (!free) {
        this.state.phase = 'error';
        this.state.error = { key: 'engine.otherTab', vars: {} };
        this.emit();
        throw new EngineError('engine.otherTab');
      }
      this.aborted = new Promise((_, rej) => { this._abort = rej; });
      // Cancellation may arrive during a network read, before any worker waits on this promise.
      this.aborted.catch(() => {});
      try {
        this.checkStopped();
        return await this._run();
      } catch (e) {
        this.cancel();
        const err = this.explain(e instanceof EngineError ? e : new EngineError('engine.failed', {}, String(e && e.stack || e)));
        this.state.phase = 'error';
        this.state.error = { key: err.key, vars: err.vars, detail: err.detail, kind: err.kind };
        this.emit();
        // what the build left goes now (the image of the last build went when this one started)
        try { await (await navigator.storage.getDirectory()).removeEntry(OPFS_DIR, { recursive: true }); } catch { /* */ }
        throw err;
      } finally {
        this._abort = null;
      }
    });
    return r;
  }

  // An error in the player's words: whatever step it came from, a full storage, storage not allowed, a lost
  // connection or a lack of memory says so; the original text stays in its detail. kind: what the page suggests
  // (js/app.js FIXES): 'storage', 'blocked', 'memory', 'network', or null.
  explain(err) {
    const KEEP = new Set(['build.cancelled', 'engine.otherTab', 'engine.noWasm', 'engine.noOpfs', 'engine.noStreams',
                          'engine.sourceDiffers', 'engine.holesDiffer', 'engine.imageDiffers', 'engine.notDeployed']);
    const OWN = { 'engine.noSpace': 'storage', 'engine.quota': 'storage', 'engine.storageBlocked': 'blocked',
                  'engine.outOfMemory': 'memory', 'engine.workerFailed': 'memory', 'engine.download': 'network' };
    const vars = { ...err.vars, bytes: err.vars.bytes || this.need || 0 };
    if (OWN[err.key]) return Object.assign(new EngineError(err.key, vars, err.detail), { kind: OWN[err.key] });
    if (KEEP.has(err.key)) return Object.assign(err, { kind: null });
    const kind = failureKind(`${err.detail}\n${err.message}`);
    const key = { storage: 'engine.quota', blocked: 'engine.storageBlocked', network: 'engine.network',
                  memory: 'engine.outOfMemory' }[kind] || err.key;
    if (key === 'engine.outOfMemory') vars.job ||= this.state.now?.[0] || '';
    return Object.assign(new EngineError(key, vars, err.detail), { kind });
  }

  // A build worker: Pyodide, the code pack. onMsg(slot, message) gets its messages once it is ready.
  spawn(id, onMsg) {
    const w = new Worker(new URL(`./worker.js?v=${this.version}`, import.meta.url), { type: 'module' });
    const slot = { id, w, busy: true, job: null, ready: null, load: null, dead: false };
    slot.ready = new Promise((res, rej) => {
      const late = setTimeout(() => rej(new EngineError('engine.workerFailed', {}, `no answer in ${START_SECS} s`)), START_SECS * 1000);
      slot.started = () => clearTimeout(late);
      w.onmessage = ({ data }) => {
        if (slot.dead) return;
        if (data.kind === 'ready') { slot.started(); slot.busy = false; slot.load = data; res(slot); return; }
        if (data.kind === 'error' && !slot.load) { rej(new EngineError(data.key || 'engine.workerFailed', {}, data.msg)); return; }
        onMsg(slot, data);
      };
      w.onerror = (e) => {
        if (slot.dead) return;
        // (before it is ready: it could not start; after: it died in a job, out of memory most likely)
        const where = e.filename ? ` (${e.filename}:${e.lineno})` : '';
        if (!slot.load) rej(new EngineError('engine.workerFailed', {}, `${e.message || 'the worker did not load'}${where}`));
        else onMsg(slot, { kind: 'error', died: true, msg: e.message || 'the worker stopped' });
      };
    });
    const p = this.plan;
    w.postMessage({ kind: 'init', base: this.base, filesBudget: FILES_MB * 2 ** 20, wasm: this.wasm,
                    plan: { packs: p.packs, files: p.files, dirs: p.dirs, extract: p.extract, extract_inputs: p.extract_inputs,
                            source_discs: p.source_discs, out: p.out } });
    return slot;
  }

  // Pyodide's WebAssembly module compiled once, for every worker: compiled code is the largest part of a worker's
  // start (Firefox's 32-bit Windows build starts 2 workers with one compilation each, 3 sharing it). If it cannot be
  // compiled here, each worker compiles its own.
  async compileEngine() {
    try {
      const r = await cacheFirst(`${this.base}pyodide/pyodide.asm.wasm`);
      this.wasm = await WebAssembly.compile(await r.arrayBuffer());
    } catch (e) { this.log(`Pyodide not compiled ahead (${e && e.message || e})`); this.wasm = undefined; }
  }

  // Stop a worker that did not start.
  drop(slot) { slot.dead = true; slot.started(); slot.w.terminate(); }

  async _run() {
    const st = this.state;
    this.log(`browser: ${navigator.userAgent}; ${navigator.hardwareConcurrency || '?'} cores, ${navigator.deviceMemory || '?'} GB, ${this.n} workers`);
    const why = missingSupport();
    if (why) throw new EngineError(why);
    const { base, plan, version } = await loadPlan();
    this.checkStopped();
    plan.version = version;
    this.plan = plan; this.base = base; this.version = version;
    if ((plan.source_discs || []).some((game) => !this.sources[game])) throw new EngineError('patch.needSources');
    st.version = version;
    st.release = plan.release;
    // the last build's image and tree, the old engines
    await dropOldEngines(version);
    this.checkStopped();
    try { await (await navigator.storage.getDirectory()).removeEntry(OPFS_DIR, { recursive: true }); } catch { /* none */ }
    this.checkStopped();
    // room: the tree (~0.5 GB), the image and the engine's files. The discs the page keeps for next time
    // (OPFS horizon-discs, js/remember.js) are already in `usage` and are read in place: they need nothing more.
    // Asked before anything is downloaded or built (checkRoom: the browser's estimate, then the storage itself).
    this.need = roomFor(plan);
    const room = await checkRoom(this.need, this.roomTest || this.need);
    this.checkStopped();
    this.log(`room: ${(this.need / 2 ** 30).toFixed(2)} GB needed; ${room.reason || 'ok'}${room.free != null ? `, browser estimate ${(room.free / 2 ** 30).toFixed(1)} GB free` : ''}${room.msg ? ` (${room.msg})` : ''}`);
    if (room.reason === 'quota') throw new EngineError('engine.noSpace', { bytes: this.need }, `room: ${room.msg}`);
    if (room.reason === 'blocked') throw new EngineError('engine.storageBlocked', {}, room.msg);
    st.room = room.reason;                 // 'unkept': a private window, most likely; the build tries anyway

    // 1. the engine's files
    st.phase = 'download';
    const urls = [...plan.pyodide.files.map(([f, n]) => [`${base}pyodide/${f}`, n]),
                  ...plan.packs.map((p) => [`${base}packs/${p.name}`, p.size])];
    st.download.total = urls.reduce((a, [, n]) => a + n, 0);
    st.download.fresh = 0;
    this.td0 = performance.now();
    for (const [u] of urls) {
      await cacheFirst(u, (n, cached) => { st.download.done += n; if (!cached) st.download.fresh += n; this.emit(); });
      this.checkStopped();
    }
    st.times.download = (performance.now() - this.td0) / 1000;
    this.log(`engine ${version}: ${(st.download.total / 2 ** 20).toFixed(1)} MB, ${(st.download.fresh / 2 ** 20).toFixed(1)} MB downloaded, ${st.times.download.toFixed(1)} s`);

    await this.compileEngine();
    this.checkStopped();

    // 2. one worker reads the disc and the other games' files, alone: the build workers start after it (on a phone
    // this takes minutes, and every idle Pyodide is memory the tab may not have)
    st.phase = 'extract';
    const jobs = plan.jobs;
    if (this.shuffle) {
      // (tests: another order each seed, any order the jobs' waits allow must give the same disc)
      let x = this.shuffle >>> 0 || 1;
      const rnd = () => { x ^= x << 13; x >>>= 0; x ^= x >>> 17; x ^= x << 5; x >>>= 0; return x / 2 ** 32; };
      for (const j of jobs) j.prio = rnd() * 1000;
      this.log(`test: jobs in a random order (seed ${this.shuffle})`);
    }
    this.registry = new Map();
    const onJob = new Map();
    const route = (slot, m) => { const f = onJob.get(slot); if (f) f(m); };
    let extracted = null;
    const reader = () => this.spawn(-1, (slot, m) => {
      if (m.kind === 'progress') { st.extract.done = m.done; st.extract.total = m.total; this.emit(); }
      else if (m.kind === 'done' || m.kind === 'error') this._extractDone(m);
    });
    this.extractor = reader();
    st.workers = Array.from({ length: this.n }, (_, i) => ({ id: i, job: null, state: 'loading' }));
    this.emit();
    const tx = performance.now();
    let ex;
    try {
      ex = await this.waitWorker(this.extractor.ready);
    } catch (e) {
      // (a worker that could not start is given a second chance, once)
      if (this.stopped || e.key === 'build.cancelled' || e.key === 'engine.noOpfs') throw e;
      this.log(`the disc reader did not start (${e.detail}); trying again`);
      this.drop(this.extractor);
      await sleep(SETTLE_MS);
      this.checkStopped();
      this.extractor = reader();
      ex = await this.waitWorker(this.extractor.ready);
    }
    extracted = await this.waitWorker(new Promise((res) => { this._extractDone = res; ex.w.postMessage({ kind: 'extract', file: this.file, sources: this.sources }); }));
    ex.dead = true; ex.w.terminate(); this.extractor = null;
    if (!extracted.ok && extracted.game) {
      throw new EngineError('engine.sourceDiffers', { title: this.titles[extracted.game] || extracted.game }, extracted.out);
    }
    if (!extracted.ok) throw new EngineError('engine.discRefused', {}, extracted.out || extracted.msg);
    st.base = { key: extracted.key, title: extracted.title };
    this.localized = extracted.localized || [];
    st.times.extract = (performance.now() - tx) / 1000;
    this.log(`disc: ${extracted.title}, ${extracted.files} files (${(extracted.bytes / 2 ** 20).toFixed(0)} MB), ${extracted.secs.toFixed(1)} s, heap ${extracted.heap.toFixed(0)} MB`);
    if (extracted.sourceFiles?.length) this.log(`other games: ${extracted.sourceFiles.length} files (${(extracted.sourceSecs || 0).toFixed(1)} s) to ${plan.out}/source-games/`);
    for (const p of plan.extract) this.registry.set(`extracted/${p}`, 'x');
    for (const p of extracted.sourceFiles || []) this.registry.set(p, 'x');

    // 3. the jobs
    st.phase = 'build';
    const steps = new Map(plan.steps.map((s) => [s.name, { name: s.name, done: 0, total: s.jobs }]));
    st.steps = [...steps.values()];
    st.units = { done: 0, total: jobs.length };
    const done = new Set();
    const running = new Map();               // job id -> slot
    // the versions of tree files a running job was given (`${token} ${path}`: count), and the replaced versions
    // (removed from OPFS once no running job reads them)
    const holders = new Map();
    const garbage = new Set();
    const removedBy = new Map();             // path -> the job that removed it last
    const byId = new Map(jobs.map((x) => [x.id, x]));
    const hold = (inputs, d) => { for (const [p, t] of inputs) if (t !== 'b') { const k = `${t} ${p}`; holders.set(k, (holders.get(k) || 0) + d); if (!holders.get(k)) holders.delete(k); } };
    const replaced = (p) => { const t = this.registry.get(p); if (t && t !== 'x') garbage.add(`${t} ${p}`); };
    let sweeping = Promise.resolve();
    const sweep = () => {
      const go = [...garbage].filter((k) => !holders.has(k));
      for (const k of go) garbage.delete(k);
      if (!go.length) return;
      sweeping = sweeping.then(async () => {
        for (const k of go) {
          const i = k.indexOf(' ');
          const loc = locOf(k.slice(i + 1), k.slice(0, i));
          const at = loc.lastIndexOf('/');
          try { await (await opfsDir(`tree/${loc.slice(0, at)}`)).removeEntry(loc.slice(at + 1)); } catch { /* gone */ }
        }
      });
    };
    let finishing = false;
    const tb = performance.now();
    let estDone = 0, realDone = 0;
    this.speed = 1;                          // measured / estimated, of the jobs done
    this.jobsLeft = () => {
      const left = jobs.filter((j) => !done.has(j.id));
      return this.speed * this.jobsEstimate(left, Math.max(1, this.slots.length));
    };
    const ready = (s) => {
      st.workers[st.workers.findIndex((x) => x.id === s.id)] = { id: s.id, job: null, state: 'idle' };
      this.log(`worker ${s.id}: Pyodide ${s.load.load.toFixed(1)} s, code ${s.load.code.toFixed(1)} s, heap ${s.load.heap.toFixed(0)} MB`);
      this.emit();
    };
    // One after another, so that their start does not add up; the build goes on with the ones that started.
    for (let i = 0, tries = 1; i < this.n; i++) {
      const slot = this.spawn(i, route);
      this.slots.push(slot);
      try {
        ready(await this.waitWorker(slot.ready));
      } catch (e) {
        if (this.stopped || e.key === 'build.cancelled') throw e;
        this.slots.pop();
        this.drop(slot);
        if (this.slots.length) {
          this.log(`worker ${i} did not start (${e.detail}); ${this.slots.length} workers go on`);
          break;
        }
        if (tries-- <= 0) throw e;
        this.log(`worker ${i} did not start (${e.detail}); trying again`);
        await sleep(SETTLE_MS);
        this.checkStopped();
        i--;
      }
    }
    st.workers = st.workers.slice(0, this.slots.length);
    st.workerCount = this.slots.length;
    const readyJobs = () => jobs.filter((j) => !done.has(j.id) && !running.has(j.id) && j.deps.every((d) => done.has(d))
                                         && !(j.part === 'finish' && finishing)).sort((a, b) => b.prio - a.prio);
    st.times.peakHeap = {};
    let recycled = 0;
    const nowSteps = () => {
      // the steps being worked on now, most workers first (the plain line)
      const c = new Map();
      for (const slot of running.values()) { const s = slot.job.step; c.set(s, (c.get(s) || 0) + 1); }
      st.now = [...c.entries()].sort((a, b) => b[1] - a[1]).map(([s]) => s);
    };
    try {
      await this.waitWorker(new Promise((resolve, reject) => {
      const fail = (e) => { this.stopped = true; reject(e); };
      const pump = () => {
        if (this.stopped) return;
        if (done.size === jobs.length) { resolve(); return; }
        for (const slot of this.slots) {
          if (slot.busy) continue;
          const j = readyJobs()[0];
          if (!j) break;
          start(slot, j);
        }
        nowSteps();
        const starting = this.slots.some((s) => !s.load);
        if (this.slots.length && !running.size && !starting && done.size < jobs.length && !readyJobs().length) fail(new EngineError('engine.failed', {}, 'no job can start'));
      };
      const showSlots = () => {
        st.workers = this.slots.map((s) => ({ id: s.id, job: s.job ? s.job.name : null, state: s.job ? 'busy' : s.load ? 'idle' : 'loading' }));
        st.workerCount = this.slots.length;
      };
      // A fresh worker; if it does not start, the others go on, and with none left it is tried again a few times.
      const startFresh = (id, tries = 3) => {
        const fresh = this.spawn(id, route);
        this.slots.push(fresh);
        showSlots();
        fresh.ready.then(() => { if (!this.stopped) { showSlots(); this.emit(); pump(); } }, (e) => {
          if (this.stopped) return;
          this.drop(fresh);
          this.slots.splice(this.slots.indexOf(fresh), 1);
          this.log(`a replacement worker did not start (${e.detail}); ${this.slots.length} workers go on`);
          if (!this.slots.length) {
            if (tries <= 1) { fail(e); return; }
            setTimeout(() => { if (!this.stopped) startFresh(id, tries - 1); }, SETTLE_MS);
            return;
          }
          showSlots(); this.emit(); pump();
        });
      };
      // A fresh worker in the place of `slot` (its heap grew too much), ready for the next job.
      const recycle = (slot) => {
        slot.dead = true; slot.w.terminate();
        this.slots.splice(this.slots.indexOf(slot), 1);
        recycled++;
        startFresh(slot.id);
      };
      // A job failed on a worker (out of memory, a browser's file read that gave up, anything): the job goes back to
      // the others, the build goes on with one worker fewer (with none left, one fresh worker); a job that fails three
      // times stops the build. The job's own files were not written: they go to OPFS only when it succeeds.
      const jobFailure = (slot, j, msg, memory) => {
        onJob.delete(slot);
        running.delete(j.id);
        hold(slot.inputs, -1);
        if (j.part === 'finish') finishing = false;
        slot.dead = true; slot.w.terminate();
        this.slots.splice(this.slots.indexOf(slot), 1);
        j.memoryFailures = (j.memoryFailures || 0) + 1;
        const why = String(msg).split('\n').filter((l) => MEMORY.test(l) || STORAGE.test(l)).pop() || String(msg).split('\n').filter(Boolean).pop();
        // the browser's storage is full: another worker would only fail the same way
        if (STORAGE.test(String(msg))) {
          this.log(`w${slot.id} ${j.name}: no room left in this browser's storage (${(why || '').trim()})`);
          fail(new EngineError('engine.quota', { job: j.name, bytes: this.need }, msg));
          return;
        }
        this.log(`w${slot.id} ${j.name}: ${memory ? 'out of memory' : 'failed'} (${(why || '').trim()}); ${this.slots.length} workers go on`);
        if (j.memoryFailures >= 3) { fail(new EngineError(memory ? 'engine.outOfMemory' : 'engine.jobFailed', { job: j.name }, msg)); return; }
        if (!this.slots.length) setTimeout(() => { if (!this.stopped) startFresh(slot.id); }, SETTLE_MS);
        st.memoryRetries = (st.memoryRetries || 0) + 1;
        showSlots();
        this.emit();
        pump();
      };
      const start = (slot, j) => {
        const inputs = j.bundle.map((p) => [p, 'b']);
        const notThere = [];  // (a file a step's units write in place, before the first one did; the first manifest)
        for (const p of j.tree) {
          const t = this.registry.get(p);
          if (t) inputs.push([p, t]); else notThere.push(p);
        }
        if (notThere.length) this.log(`${j.name}: not made yet: ${notThere.slice(0, 3).join(' ')}${notThere.length > 3 ? ` (+${notThere.length - 3})` : ''}`);
        if (j.globs.length) {
          // (a path under a temporary folder of an earlier job: any such folder's file)
          const res = j.globs.map((g) => new RegExp(`^${g.split('*').map((x) => x.replace(/[.+?^${}()|[\]\\]/g, '\\$&')).join('[^/]+')}$`));
          for (const [p, t] of this.registry) if (res.some((r) => r.test(p))) inputs.push([p, t]);
        }
        slot.busy = true; slot.job = j;
        slot.inputs = inputs;
        hold(inputs, 1);
        running.set(j.id, slot);
        if (j.part === 'finish') finishing = true;
        showSlots();
        this.emit();
        onJob.set(slot, (m) => {
          if (m.kind === 'progress') return;
          if (m.kind === 'error') {
            jobFailure(slot, j, m.msg, m.died || MEMORY.test(m.msg || ''));
            return;
          }
          if (m.kind !== 'done') return;
          if (!m.ok) { jobFailure(slot, j, m.out, MEMORY.test(m.out || '')); return; }
          onJob.delete(slot);
          running.delete(j.id);
          hold(slot.inputs, -1);
          if (j.part === 'finish') finishing = false;
          // A path several units of a step write (the story passes edit the new screens' .MAP in place: not the
          // same bytes from each) ends as the last of them in the recorded order wrote it, as natively, not as the
          // last to finish here: a unit's write or removal does not replace a later unit's of its step. (The jobs'
          // waits order every other path's writers; the finishes' manifest is the last one written.)
          const sibling = (id) => { const w = byId.get(id); return w && w.part === 'unit' && j.part === 'unit' && w.step === j.step && w.id > j.id; };
          const later = (p) => {
            const t = this.registry.get(p);
            return !(t && t !== 'x' && sibling(Number(t.slice(1)))) && !(removedBy.has(p) && sibling(removedBy.get(p)));
          };
          for (const [p] of m.written) {
            if (later(p)) { replaced(p); this.registry.set(p, `j${j.id}`); removedBy.delete(p); } else garbage.add(`j${j.id} ${p}`);
          }
          for (const p of m.removed) if (later(p)) { replaced(p); this.registry.delete(p); removedBy.set(p, j.id); }
          sweep();
          done.add(j.id);
          estDone += j.est; realDone += m.secs; this.speed = Math.max(0.3, Math.min(5, realDone / estDone));
          steps.get(j.step).done++;
          st.units.done = done.size;
          st.times.peakHeap[slot.id] = Math.max(st.times.peakHeap[slot.id] || 0, m.heap);
          this.log(`w${slot.id} ${j.name}: ${m.secs.toFixed(1)} s (sync ${m.sync.toFixed(1)} s, ${(m.loaded / 2 ** 20).toFixed(1)} MB in), run ${m.run.toFixed(1)} s, output ${(m.secs - m.sync - m.run).toFixed(1)} s, heap ${m.heap.toFixed(0)} MB, files ${(m.mem / 2 ** 20).toFixed(0)} MB, ${m.written.length} files out`);
          slot.busy = false; slot.job = null;
          if (m.heap > this.recycleMB && done.size < jobs.length) recycle(slot);
          showSlots();
          this.emit();
          pump();
        });
        const oom = this.oomTest && j.name === this.oomTest && !j.memoryFailures;
        const quota = !!this.quotaTest && (this.quotaTest === 'first' || j.name === this.quotaTest);
        slot.w.postMessage({ kind: 'job', job: { argv: j.argv, lists: j.lists, absent: j.absent, mkdirs: j.mkdirs }, inputs,
                             token: `j${j.id}`, oom, quota });
      };
      pump();
      }));
    } finally {
      // A queued OPFS sweep must also finish before run() releases the build lock.
      await sweeping;
    }
    this.checkStopped();
    st.times.jobs = (performance.now() - tb) / 1000;
    st.times.recycled = recycled;
    this.jobsLeft = () => 0;
    st.now = [];

    // 4. the built files checked, the disc written: on a fresh worker (the others' memory is given back first)
    st.phase = 'check';
    for (const s of this.slots) { s.dead = true; s.w.terminate(); }
    this.slots = [];
    await sleep(SETTLE_MS);
    this.checkStopped();
    let writer = this.spawn(0, route);
    this.slots = [writer];
    st.workers = [{ id: 0, job: 'disc', state: 'busy' }];
    const where = (p) => { const t = this.registry.get(p); if (!t) throw new EngineError('engine.failed', {}, `${p}: not built`); return locOf(p, t); };
    const man = JSON.parse(await opfsText(`tree/${where(plan.manifest)}`));
    this.checkStopped();
    const holes = Object.entries(man.files).map(([d, e]) => [d, where(norm(`${plan.out}/${e.file}`))]);
    const key = st.base.key;
    const out = plan.release.outputs[key] || {};
    st.check.total = holes.length;
    st.write.total = out.size || 0;
    this.emit();
    try {
      await this.waitWorker(writer.ready);
    } catch (e) {
      if (this.stopped || e.key === 'build.cancelled') throw e;
      this.log(`the disc writer did not start (${e.detail}); trying again`);
      this.drop(writer);
      await sleep(SETTLE_MS);
      this.checkStopped();
      writer = this.spawn(0, route);
      this.slots = [writer];
      await this.waitWorker(writer.ready);
    }
    const tw = performance.now();
    const w = await this.waitWorker(new Promise((res) => {
      onJob.set(writer, (m) => {
        if (m.kind === 'progress' && m.what === 'check') { st.check.done = m.done; this.emit(); return; }
        if (m.kind === 'progress') {
          if (st.phase === 'check') { st.times.check = (performance.now() - tw) / 1000; st.phase = 'write'; }
          st.write.done = m.done; st.write.total = m.total || st.write.total; this.emit(); return;
        }
        if (m.kind === 'error') { res({ ok: false, out: m.msg }); return; }
        if (m.kind === 'done') res(m);
      });
      writer.w.postMessage({ kind: 'write', file: this.file, key, holes, image: IMAGE, size: out.size || 0,
                             localized: this.localized, sources: this.sources });
    }));
    for (const s of this.slots) { s.dead = true; s.w.terminate(); }
    this.slots = [];
    this.wasm = undefined;
    st.times.write = (performance.now() - tw) / 1000;
    if (w.bad && w.bad.length) {
      this.log(`built files that differ from the release: ${w.bad.join(' ')}`);
      throw new EngineError('engine.holesDiffer', { n: w.bad.length, files: w.bad.slice(0, 8).join(', ') });
    }
    if (!w.ok) {
      if (w.sha1 && w.want && w.sha1 !== w.want) throw new EngineError('engine.imageDiffers', { sha1: w.sha1, want: w.want });
      throw new EngineError('engine.writeFailed', {}, w.out);
    }
    this.log(`disc: ${w.size} bytes, SHA-1 ${w.sha1} (${w.want ? (w.sha1 === w.want ? 'the release\'s' : 'NOT the release\'s') : 'no release checksum for this base'}), check ${(st.times.check || 0).toFixed(1)} s, ${w.secs.toFixed(1)} s, heap ${w.heap.toFixed(0)} MB`);
    // the tree is no longer needed; the image stays until the next build (done.json: it is whole)
    const root = await opfsRoot();
    this.checkStopped();
    if (!this.keepTree) { try { await root.removeEntry('tree', { recursive: true }); } catch { /* */ } }
    else await opfsPut('tree/registry.json', JSON.stringify(Object.fromEntries([...this.registry].map(([p, t]) => [p, locOf(p, t)]))));
    this.checkStopped();
    await opfsPut(DONE, JSON.stringify({ size: w.size, sha1: w.sha1, base: key, release: plan.release.version }));
    this.checkStopped();
    const bin = await (await root.getFileHandle(IMAGE)).getFile();
    this.checkStopped();
    const cue = new Blob([`FILE "${OUTPUT_NAME}.bin" BINARY\r\n  TRACK 01 MODE2/2352\r\n    INDEX 01 00:00:00\r\n`], { type: 'text/plain' });
    st.phase = 'done';
    st.eta = 0;
    st.result = { bin, cue, name: OUTPUT_NAME, sha1: w.sha1, want: w.want, size: w.size, holes: holes.length };
    st.times.total = (performance.now() - st.t0) / 1000;
    this.emit();
    return st.result;
  }
}
