// The discs remembered for the next visit (web/README.md "Remembered discs"): one record per game in IndexedDB
// (horizon / discs), and, for the discs the player chose to keep in this browser, a copy in OPFS
// (horizon-discs/<game>/<the file's name>), apart from the build's own horizon-build that every build empties.
//
// record: {game, kind: 'handle' | 'copy', release (the release id it was accepted as), via ('files' or null),
//          name, size, lastModified (what the handle or the copy gives back: sameFile in js/app.js),
//          image: {crc32, sha1, size} (the checked image: a converted archive's, ECM's or PBP's output),
//          converted (the handle is an archive, ECM or PBP: it is converted again), handle (kind 'handle'), savedAt}
//
// Nothing here throws: without IndexedDB or OPFS (a private window, an old browser, storage turned off) nothing is
// remembered and the page works as it did. Copies and deletions in OPFS hold the build's Web Lock (withLock), so a
// copy never races a build in this or another tab; a deletion that cannot have it now is left to tidy().

import { withLock, isMobile } from './engine/engine.js';

const DB = 'horizon', STORE = 'discs', DIR = 'horizon-discs';

let dbp = null;
function db() {
  dbp ||= new Promise((res) => {
    try {
      const r = indexedDB.open(DB, 1);
      r.onupgradeneeded = () => r.result.createObjectStore(STORE, { keyPath: 'game' });
      r.onsuccess = () => res(r.result);
      r.onerror = r.onblocked = () => res(null);
    } catch { res(null); }
  });
  return dbp;
}
async function tx(mode, fn) {
  const d = await db();
  if (!d) return null;
  return new Promise((res) => {
    try {
      const t = d.transaction(STORE, mode);
      const out = fn(t.objectStore(STORE));
      t.oncomplete = () => res(out?.result ?? true);
      t.onerror = t.onabort = () => res(null);
    } catch { res(null); }
  });
}

// Handles go into IndexedDB as they are (structured clone). The tests' fake handles (web/test/remember.mjs) have no
// structured form: they give one (stored()) and are made again by the hook the test installs (self.testHandles).
const storable = (h) => (typeof h?.stored === 'function' ? h.stored() : h);
export const revive = (h) => (typeof h?.getFile === 'function' ? h : self.testHandles?.revive?.(h) || null);

async function opfs(create = false) {
  try { return await (await navigator.storage.getDirectory()).getDirectoryHandle(DIR, { create }); } catch { return null; }
}

export const store = {
  async all() { return (await tx('readonly', (s) => s.getAll())) || []; },
  async put(rec) {
    const r = { ...rec, savedAt: Date.now() };
    if (r.handle) r.handle = storable(r.handle);
    return !!await tx('readwrite', (s) => s.put(r));
  },
  async del(game) { await tx('readwrite', (s) => s.delete(game)); },
  async clear() { await tx('readwrite', (s) => s.clear()); },

  // Can this browser keep copies? Not on phones and tablets (the build counts them as short of memory, and their
  // storage is small), not without IndexedDB, OPFS or workers.
  async canCopy() {
    if (isMobile() || typeof Worker === 'undefined' || !navigator.storage?.getDirectory) return false;
    if (!await db()) return false;
    return !!await opfs(true);
  },

  // The copy of a record, as a File (null: gone, cut short, unreadable)
  async copyOf(rec) {
    try {
      const dir = await (await opfs())?.getDirectoryHandle(rec.game);
      const f = await (await dir.getFileHandle(rec.name)).getFile();
      return f.size === rec.size ? f : null;
    } catch { return null; }
  },

  // Copy `file` as game's disc. onProgress(0..1); returns {size} or {error, quota}, or {busy: true} when another tab
  // builds or copies (try again later). job.stop() stops it ({stopped: true}).
  copy(game, file, onProgress) {
    let worker = null, settle;
    const job = {
      stop() { if (worker) { worker.terminate(); worker = null; settle({ stopped: true }); } },
    };
    job.done = withLock(async (free) => {
      if (!free) return { busy: true };
      const out = await new Promise((res) => {
        settle = res;
        worker = new Worker(new URL('./keep-worker.js', import.meta.url));
        worker.onmessage = ({ data }) => {
          if (data.progress != null) { onProgress(data.progress); return; }
          worker?.terminate(); worker = null; res(data);
        };
        worker.onerror = (e) => { e.preventDefault(); worker?.terminate(); worker = null; res({ error: e.message || 'worker' }); };
        worker.postMessage({ file, game });
      });
      if (out.size == null) await removeDirs([game]);   // (a copy cut short or failed: nothing of it stays)
      else if (out.size !== file.size) { await removeDirs([game]); return { error: `copied ${out.size} of ${file.size} bytes` }; }
      return out;
    });
    return job;
  },

  // The copies of these games (all: null) out of OPFS, now if no build or copy runs anywhere, else at the next tidy()
  async removeCopies(games = null) {
    await withLock(async (free) => { if (free) await removeDirs(games); });
  },

  // What no record names (a copy cut short by a closed tab, a forgotten disc whose deletion had to wait), out of
  // OPFS; skipped while a build or a copy runs.
  async tidy() {
    const recs = await this.all();
    const keep = new Map(recs.filter((r) => r.kind === 'copy').map((r) => [r.game, r.name]));
    await withLock(async (free) => {
      if (!free) return;
      const root = await opfs();
      if (!root) return;
      for (const game of await names(root)) {
        if (!keep.has(game)) { await root.removeEntry(game, { recursive: true }).catch(() => {}); continue; }
        try {
          const dir = await root.getDirectoryHandle(game);
          for (const n of await names(dir)) if (n !== keep.get(game)) await dir.removeEntry(n, { recursive: true }).catch(() => {});
        } catch { /* a file, not a folder */ await root.removeEntry(game).catch(() => {}); }
      }
    });
  },

  // How much room is left for copies, in bytes (null: the browser does not say)
  async free() {
    try { const e = await navigator.storage.estimate(); return e.quota ? e.quota - e.usage : null; } catch { return null; }
  },
  async persist() { try { return await navigator.storage.persist(); } catch { return false; } },
};

async function names(dir) {
  const out = [];
  try { for await (const n of dir.keys()) out.push(n); } catch { /* gone */ }
  return out;
}
async function removeDirs(games) {
  const root = await opfs();
  if (!root) return;
  for (const g of games || await names(root)) await root.removeEntry(g, { recursive: true }).catch(() => {});
}
