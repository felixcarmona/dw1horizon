// One build worker (a module Web Worker): one Pyodide, reused for every job the page gives it.
//
// The build tree is this worker's own memory file system at /horizon (the code pack, unpacked when the worker starts,
// then per job the files the job reads: the bundle's from the packs, the player's and the earlier jobs' from the
// browser's private file system, OPFS). What a job writes or removes there is noticed (the file system's open,
// rename, unlink... are watched) and copied back to OPFS; the page keeps the list of who wrote what (registry).
//
// Messages in: {kind: 'init', base, plan}, {kind: 'extract', file, ...}, {kind: 'job', job, inputs}, {kind: 'write', ...}
// Messages out: {kind: 'ready'|'done'|'progress'|'error', ...}

const ROOT = '/horizon';
const REL = `${ROOT}/.release`;
const OPFS_DIR = 'horizon-build';
const CACHE = 'horizon-engine';
const post = (m) => self.postMessage(m);
const said = [];                // Python's own prints (the last lines, for an error report)
const say = (line) => { said.push(line); if (said.length > 200) said.shift(); };

let py, FS, base, plan;
let files;                     // bundle path -> [path, pack, offset, stored, size, method]
const packBlobs = new Map();   // pack index -> Blob
const have = new Map();        // path in the tree -> what is there: 'b' (bundle), or the registry's token
const lru = new Map();         // path -> size (insertion order = last use), files that may be dropped
let lruBytes = 0;
let BUDGET = 24 * 2 ** 20;     // bundle and tree files kept between jobs (the page sets it: filesBudget)

// ---------------------------------------------------------------- assets (Cache API, else the network)
async function asset(url) {
  let c = null;
  try { c = await caches.open(CACHE); } catch { /* no Cache API (private windows): the network */ }
  if (c) {
    const r = await c.match(url);
    if (r) return r;
  }
  const r = await fetch(url);
  if (!r.ok) throw new Error(`${url}: HTTP ${r.status}`);
  if (c) { try { await c.put(url, r.clone()); } catch { /* quota: fine, not cached */ } }
  return r;
}

async function pack(n) {
  if (!packBlobs.has(n)) packBlobs.set(n, await (await asset(`${base}packs/${plan.packs[n].name}`)).blob());
  return packBlobs.get(n);
}

async function bundleFile(path) {
  const e = files.get(path);
  if (!e) throw new Error(`${path}: not in the bundle`);
  const [, n, off, stored, , method] = e;
  const part = (await pack(n)).slice(off, off + stored);
  if (method === 0) return new Uint8Array(await part.arrayBuffer());
  return new Uint8Array(await new Response(part.stream().pipeThrough(new DecompressionStream('deflate-raw'))).arrayBuffer());
}

// ---------------------------------------------------------------- OPFS (the shared tree, by path and version)
// A file of the tree is kept in OPFS under tree/ by who wrote it: the player's files (token 'x') at their path, a
// job's outputs under tree/@<token>/<path> (token j<id>). So a job that starts while another job writes the same path
// (the story passes edit the new screens' .MAP in place) still reads the version the page's registry gives it; the
// page removes a version once a newer one replaced it and no running job reads it.
const locOf = (path, token) => (token === 'x' ? path : `@${token}/${path}`);
const dirCache = new Map();
async function opfsDir(path, create) {
  // path: 'a/b/c' (folders)
  if (dirCache.has(path)) return dirCache.get(path);
  let d = await (await navigator.storage.getDirectory()).getDirectoryHandle(OPFS_DIR, { create: true });
  if (path) for (const part of path.split('/')) d = await d.getDirectoryHandle(part, { create });
  dirCache.set(path, d);
  return d;
}
const split = (p) => { const i = p.lastIndexOf('/'); return [i < 0 ? '' : p.slice(0, i), p.slice(i + 1)]; };

async function opfsRead(path) {
  const [dir, name] = split(path);
  const h = await (await opfsDir(`tree${dir ? '/' + dir : ''}`, false)).getFileHandle(name);
  return new Uint8Array(await (await h.getFile()).arrayBuffer());
}

async function opfsWrite(path, bytes) {
  const [dir, name] = split(path);
  const h = await (await opfsDir(`tree${dir ? '/' + dir : ''}`, true)).getFileHandle(name, { create: true });
  const w = await h.createWritable();
  await w.write(bytes);
  await w.close();
}

// ---------------------------------------------------------------- the memory file system
const abs = (p) => `${ROOT}/${p}`;
function exists(p) { try { FS.stat(p); return true; } catch { return false; } }
function isDir(p) { try { return FS.isDir(FS.stat(p).mode); } catch { return false; } }

function put(path, bytes, token, keep = true) {
  const p = abs(path);
  FS.mkdirTree(split(p)[0]);
  FS.writeFile(p, bytes, { canOwn: true });
  have.set(path, token);
  if (keep) touchLru(path, bytes.length);
}

function touchLru(path, size) {
  if (lru.has(path)) { lruBytes -= lru.get(path); lru.delete(path); }
  lru.set(path, size); lruBytes += size;
}

function drop(path) {
  try { FS.unlink(abs(path)); } catch { /* gone */ }
  have.delete(path);
  if (lru.has(path)) { lruBytes -= lru.get(path); lru.delete(path); }
}

function rmTree(p) {
  if (!exists(p)) return;
  if (!isDir(p)) { FS.unlink(p); return; }
  for (const n of FS.readdir(p)) if (n !== '.' && n !== '..') rmTree(`${p}/${n}`);
  FS.rmdir(p);
}

// Watching what a job changes: the file system calls Python's writes go through.
const touched = new Map();      // absolute path -> 'w' | 'rm'
function normalize(p) {
  const out = [];
  for (const s of p.split('/')) {
    if (!s || s === '.') continue;
    if (s === '..') out.pop(); else out.push(s);
  }
  return '/' + out.join('/');
}
function filesUnder(p) {
  const out = [];
  const walk = (q) => {
    if (isDir(q)) { for (const n of FS.readdir(q)) if (n !== '.' && n !== '..') walk(`${q}/${n}`); } else out.push(q);
  };
  walk(p);
  return out;
}
function watch() {
  const o = { open: FS.open, rename: FS.rename, unlink: FS.unlink, rmdir: FS.rmdir, truncate: FS.truncate,
              ftruncate: FS.ftruncate, symlink: FS.symlink };
  FS.open = function (path, flags, mode) {
    const s = o.open.apply(this, arguments);
    const f = typeof flags === 'string' ? (/[wa+]/.test(flags) ? 1 : 0) : flags;
    if (f & 3 || f & 64 || f & 512) touched.set(normalize(s.path || String(path)), 'w');
    return s;
  };
  FS.rename = function (from, to) {
    const a = normalize(String(from)), b = normalize(String(to));
    const before = isDir(a) ? filesUnder(a) : [a];
    const r = o.rename.apply(this, arguments);
    for (const q of before) touched.set(q, 'rm');
    if (isDir(b)) for (const q of filesUnder(b)) touched.set(q, 'w'); else touched.set(b, 'w');
    return r;
  };
  FS.unlink = function (path) { const r = o.unlink.apply(this, arguments); touched.set(normalize(String(path)), 'rm'); return r; };
  FS.rmdir = function (path) { return o.rmdir.apply(this, arguments); };
  FS.truncate = function (path) { const r = o.truncate.apply(this, arguments); touched.set(normalize(String(path)), 'w'); return r; };
  FS.ftruncate = function (fd) {
    const r = o.ftruncate.apply(this, arguments);
    try { touched.set(normalize(FS.getStreamChecked ? FS.getStreamChecked(fd).path : FS.getStream(fd).path), 'w'); } catch { /* */ }
    return r;
  };
  FS.symlink = function (target, path) { const r = o.symlink.apply(this, arguments); touched.set(normalize(String(path)), 'w'); return r; };
}

// ---------------------------------------------------------------- start
async function init(m) {
  if (typeof FileSystemFileHandle === 'undefined' || !('createSyncAccessHandle' in FileSystemFileHandle.prototype)) {
    post({ kind: 'error', key: 'engine.noOpfs', msg: 'no FileSystemSyncAccessHandle in workers' });
    return;
  }
  base = m.base; plan = m.plan;
  if (m.filesBudget != null) BUDGET = m.filesBudget;
  files = new Map(plan.files.map((e) => [e[0], e]));
  const t0 = performance.now();
  const { loadPyodide } = await import(`${base}pyodide/pyodide.esm.js`);
  py = await loadPyodide({ indexURL: `${base}pyodide/`, env: { PYTHONDONTWRITEBYTECODE: '1' },
                          stdout: say, stderr: say });
  FS = py.FS;
  const tl = performance.now();
  // the code pack, whole
  const code = plan.files.filter((e) => e[1] === 0);
  const blob = await pack(0);
  for (const e of code) {
    const [path, , off, stored, , method] = e;
    const part = blob.slice(off, off + stored);
    const b = method === 0 ? new Uint8Array(await part.arrayBuffer())
      : new Uint8Array(await new Response(part.stream().pipeThrough(new DecompressionStream('deflate-raw'))).arrayBuffer());
    put(path, b, 'b', false);
  }
  for (const d of plan.dirs) FS.mkdirTree(abs(d));
  FS.symlink(ROOT, `${REL}/bundle`);          // (the release's bundle/ is this tree: jp1's localize tool runs from it)
  for (const d of new Set(plan.extract.map((q) => `extracted/${split(q)[0]}`))) FS.mkdirTree(abs(d));
  py.runPython(`
import os, sys
sys.dont_write_bytecode = True
os.chdir(${JSON.stringify(ROOT)})
sys.path.insert(0, ${JSON.stringify(ROOT)})
sys.path.insert(0, ${JSON.stringify(ROOT + '/.engine')})
`);
  watch();
  post({ kind: 'ready', load: (tl - t0) / 1000, code: (performance.now() - tl) / 1000, heap: heap() });
}

const heap = () => py._module.HEAP8.length / 2 ** 20;

// ---------------------------------------------------------------- a derive job
async function sync(job, inputs) {
  // inputs: [[path, token]] (token 'b': the bundle's); the folders it lists made as they were; what must not be there
  const want = new Set(inputs.map((x) => x[0]));
  let loaded = 0;
  for (const d of job.mkdirs) FS.mkdirTree(abs(d));
  for (const [path, token] of inputs) {
    if (have.get(path) === token && exists(abs(path))) { if (lru.has(path)) touchLru(path, lru.get(path)); continue; }
    const b = token === 'b' ? await bundleFile(path) : await opfsRead(locOf(path, token));
    put(path, b, token);
    loaded += b.length;
  }
  // a folder the job lists holds what it held natively: those files (inputs) and folders, nothing else of ours
  for (const [d, [fileNames, dirNames]] of Object.entries(job.lists)) {
    const p = abs(d);
    FS.mkdirTree(p);
    const keep = new Set([...fileNames, ...dirNames]);
    for (const n of FS.readdir(p)) {
      const q = `${d}/${n}`;
      if (n === '.' || n === '..' || keep.has(n) || want.has(q)) continue;
      if (isDir(abs(q))) {
        if (![...want].some((w) => w.startsWith(q + '/'))) { for (const f of filesUnder(abs(q))) drop(f.slice(ROOT.length + 1)); rmTree(abs(q)); }
      } else drop(q);
    }
    for (const n of dirNames) if (!exists(abs(`${d}/${n}`))) FS.mkdirTree(abs(`${d}/${n}`));
  }
  for (const a of job.absent) if (exists(abs(a)) && !isDir(abs(a))) drop(a);
  trim(want);
  return loaded;
}

// memory: the least recently used files (but those in `keep`) go until the kept ones fit the budget
function trim(keep = new Set(), budget = BUDGET) {
  for (const [path] of lru) {
    if (lruBytes <= budget) break;
    if (!keep.has(path)) drop(path);
  }
}

async function runJob(m) {
  const { job, inputs, token } = m;
  const t0 = performance.now();
  const loaded = await sync(job, inputs);
  const ts = performance.now();
  touched.clear();
  if (m.oom) py.runPython('raise MemoryError("test: this job runs out of memory (?oom)")');
  py.globals.set('ARGV', py.toPy(job.argv.map((a) => a.replaceAll('{ROOT}', ROOT))));
  const r = JSON.parse(py.runPython(`
import sys, io, contextlib, json, os
os.chdir(${JSON.stringify(ROOT)})
from tools.derive import __main__ as D
buf = io.StringIO(); code = 0
sys.argv = ['tools.derive'] + list(ARGV)
with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
    try:
        D.main()
    except SystemExit as e:
        code = e.code
    except BaseException:
        import traceback; traceback.print_exc(); code = 'exception'
json.dumps([str(code), buf.getvalue()[-6000:]])
`));
  const tr = performance.now();
  const [code, out] = r;
  if (code !== 'None' && code !== '0') {
    post({ kind: 'done', ok: false, code, out, secs: (tr - t0) / 1000 });
    return;
  }
  // what the job changed in the tree, to OPFS
  const written = [], removed = [];
  for (const [p, kind] of touched) {
    if (!p.startsWith(ROOT + '/') || p.includes('/__pycache__/') || p.startsWith(REL)) continue;
    const rel = p.slice(ROOT.length + 1);
    if (exists(p) && !isDir(p)) {
      const b = FS.readFile(p);
      await opfsWrite(locOf(rel, token), b);
      have.set(rel, token);
      touchLru(rel, b.length);
      written.push([rel, b.length]);
    } else if (kind === 'rm' || !exists(p)) {
      have.delete(rel);
      if (lru.has(rel)) { lruBytes -= lru.get(rel); lru.delete(rel); }
      removed.push(rel);
    }
  }
  touched.clear();
  trim();
  post({ kind: 'done', ok: true, out, written, removed, secs: (performance.now() - t0) / 1000,
         sync: (ts - t0) / 1000, run: (tr - ts) / 1000, loaded, heap: heap(), mem: lruBytes });
}

// ---------------------------------------------------------------- the player's disc -> extracted/ (OPFS)
function mountDisc(file, mount = '/disc') {
  FS.mkdirTree(mount);
  try { FS.unmount(mount); } catch { /* not mounted */ }
  FS.mount(FS.filesystems.WORKERFS, { files: [file] }, mount);
  return `${mount}/${file.name}`;
}

function mountSources(sources) {
  return (plan.source_discs || []).map((game) => {
    if (!sources?.[game]) throw new Error(`source disc required: ${game}`);
    return `${game}=${mountDisc(sources[game], `/source-disc-${game}`)}`;
  });
}

async function extract(m) {
  const disc = mountDisc(m.file);
  py.globals.set('SOURCE_DISCS', py.toPy(mountSources(m.sources)));
  for (const p of plan.extract_inputs || []) if (!exists(abs(p))) put(p, await bundleFile(p), 'b', false);
  const t0 = performance.now();
  py.globals.set('DISC', disc);
  py.globals.set('REL_DIR', REL);
  let n = 0, bytes = 0;
  const putFile = async (q, b) => {
    const data = b.toJs();
    await opfsWrite(`extracted/${q}`, data);
    n++; bytes += data.length;
  };
  py.globals.set('put_file', putFile);
  py.globals.set('put_loc', async (q, b) => { await opfsWrite(`localized/${q}`, b.toJs()); });
  py.globals.set('progress', (i, total) => post({ kind: 'progress', what: 'extract', done: i, total }));
  try {
    const r = await py.runPythonAsync(`
import glue, os, shutil, json
from glue import dwpatch
P = dwpatch(REL_DIR)
key, title = glue.identify(REL_DIR, DISC)
m = glue.manifest(REL_DIR)
work = '/tmp/extract'
base = glue.base_disc(REL_DIR, DISC, key, work, SOURCE_DISCS)
P.subprocess.run = glue.run_tool
n = len(m['extract'])
for i, q in enumerate(m['extract']):
    await put_file(q, base.data(q))
    if i % 20 == 0 or i == n - 1:
        progress(i + 1, n)
loc = []
if base._loc:
    for dp, _, fs in os.walk(base._loc):
        for f in fs:
            q = os.path.join(dp, f)
            loc.append(os.path.relpath(q, base._loc))
            await put_loc(os.path.relpath(q, base._loc), open(q, 'rb').read())
shutil.rmtree(work, ignore_errors=True)
json.dumps([key, title, loc])
`);
    const [key, title, localized] = JSON.parse(r);
    const sourceFiles = [];
    py.globals.set('put_source', async (q, b) => {
      const path = `${plan.out}/source-games/${q}`;
      const data = b.toJs();
      await opfsWrite(path, data);
      sourceFiles.push(path); n++; bytes += data.length;
    });
    // the other three games: the files the imports read, checked by SHA-1 (tools/derive/importers/discs.py)
    const ts = performance.now();
    for (const game of plan.source_discs || []) {
      try {
        if (!m.sources?.[game]) throw new Error(`source disc required: ${game}`);
        py.globals.set('SOURCE_DISC', mountDisc(m.sources[game], `/source-disc-${game}`));
        py.globals.set('SOURCE_GAME', game);
        await py.runPythonAsync(`
from tools.derive.importers.discs import extract as extract_source
for q, data in extract_source(SOURCE_GAME, SOURCE_DISC):
    await put_source(q, data)
`);
      } catch (e) {
        post({ kind: 'done', ok: false, code: 'source', game, out: patchError(e) });
        return;
      }
    }
    post({ kind: 'done', ok: true, key, title, localized, sourceFiles, sourceSecs: (performance.now() - ts) / 1000,
           files: n, bytes, secs: (performance.now() - t0) / 1000, heap: heap() });
  } catch (e) {
    post({ kind: 'done', ok: false, code: 'exception', out: patchError(e) });
  }
}

function patchError(e) {
  const s = String(e && e.message || e);
  const m = s.match(/PatchError: ([\s\S]*?)\n*$/);
  return m ? m[1].trim() : s.slice(-3000);
}

// ---------------------------------------------------------------- the disc writer: holes from OPFS, the image to OPFS
// m.holes: [[disc path, its file's place in OPFS under tree/]]
async function writeDisc(m) {
  trim(new Set(), 0);
  const disc = mountDisc(m.file);
  py.globals.set('SOURCE_DISCS', py.toPy(mountSources(m.sources)));
  const t0 = performance.now();
  const root = await navigator.storage.getDirectory();
  const top = await root.getDirectoryHandle(OPFS_DIR, { create: true });
  // every hole's file opened for synchronous reads
  const handles = new Map();
  for (const [disc_path, rel] of m.holes) {
    const [dir, name] = split(rel);
    const h = await (await opfsDir(`tree${dir ? '/' + dir : ''}`, false)).getFileHandle(name);
    handles.set(disc_path, await h.createSyncAccessHandle());
  }
  for (const q of m.localized || []) {
    const b = await opfsRead(`localized/${q}`);
    FS.mkdirTree(split(`/tmp/localized/${q}`)[0]);
    FS.writeFile(`/tmp/localized/${q}`, b);
  }
  for (const p of plan.extract_inputs || []) if (!exists(abs(p))) put(p, await bundleFile(p), 'b', false);
  const outH = await (await top.getFileHandle(m.image, { create: true })).createSyncAccessHandle();
  outH.truncate(0);
  let at = 0, lastPost = 0;
  const total = m.size;
  let checked = 0;
  const readHole = (p) => {
    const h = handles.get(p);
    const b = new Uint8Array(h.getSize());
    h.read(b, { at: 0 });
    return b;
  };
  const holeSize = (p) => handles.get(p).getSize();
  const write = (proxy) => {
    const buf = proxy.getBuffer('u8');
    try {
      outH.write(buf.data, { at });
      at += buf.data.length;
    } finally { buf.release(); }
    if (at - lastPost > 8 * 2 ** 20 || at === total) { lastPost = at; post({ kind: 'progress', what: 'write', done: at, total }); }
  };
  py.globals.set('DISC', disc);
  py.globals.set('REL_DIR', REL);
  py.globals.set('KEY', m.key);
  py.globals.set('LOCALIZED', (m.localized || []).length > 0);
  py.globals.set('HOLES', py.toPy(m.holes.map((x) => x[0])));
  py.globals.set('read_hole', readHole);
  py.globals.set('hole_size', holeSize);
  py.globals.set('js_write', write);
  py.globals.set('checked_one', () => {
    checked++;
    if (checked % 20 === 0 || checked === m.holes.length) post({ kind: 'progress', what: 'check', done: checked, total: m.holes.length });
  });
  try {
    const r = py.runPython(`
import glue, json, hashlib
glue.dwpatch(REL_DIR)
import isowriter as iw

class Hole(iw.Source):
    """A hole's file in OPFS, read when it is used."""
    def __init__(self, path):
        self.path = path
        super().__init__(hole_size(path), self._get)
    def _get(self):
        return read_hole(self.path).to_bytes()
    def __getitem__(self, s):
        return self._get()[s]

class Out:
    """The image, in 8 MB writes."""
    def __init__(self):
        self.buf = bytearray()
    def write(self, b):
        self.buf += b
        if len(self.buf) >= 8 << 20:
            self.flush()
    def flush(self):
        if self.buf:
            js_write(self.buf); self.buf = bytearray()

holes = {p: Hole(p) for p in HOLES}
def check_read(p):
    b = holes[p].read()
    checked_one()
    return b
bad = glue.check_holes(REL_DIR, KEY, check_read)
if bad:
    res = {'bad': bad}
else:
    out = Out()
    sha, want, size = glue.write_disc(REL_DIR, DISC, KEY, holes, out, '/tmp/write', '/tmp/localized' if LOCALIZED else None, SOURCE_DISCS)
    out.flush()
    res = {'sha1': sha, 'want': want, 'size': size}
json.dumps(res)
`);
    const res = JSON.parse(r);
    outH.flush();
    res.written = at;
    post({ kind: 'done', ok: !res.bad && (!res.want || res.sha1 === res.want), ...res,
           secs: (performance.now() - t0) / 1000, heap: heap() });
  } catch (e) {
    post({ kind: 'done', ok: false, code: 'exception', out: patchError(e) });
  } finally {
    for (const h of handles.values()) h.close();
    outH.close();
  }
}

self.onmessage = async ({ data: m }) => {
  try {
    if (m.kind === 'init') await init(m);
    else if (m.kind === 'job') await runJob(m);
    else if (m.kind === 'extract') await extract(m);
    else if (m.kind === 'write') await writeDisc(m);
  } catch (e) {
    post({ kind: 'error', key: e && e.key, msg: String(e && e.stack || e).slice(-3000) });
  }
};
