// Is there room for a build in this browser's storage? (js/engine/engine.js checkRoom). storage.estimate() cannot
// tell: Chromium reports a fixed quota (its usage + 10 GB) whatever the disk or a private window can hold. So this
// asks the storage itself: a file in OPFS (horizon-room/) made `bytes` long and removed at once. Making a file
// longer writes nothing (sparse on most systems) but must fit in the quota: an error means the build will not fit.
// A file that does not keep its length is storage held in memory (a private or incognito window).
//   in:  {bytes}
//   out: {ok: true} | {reason: 'quota' | 'blocked' | 'unkept' | 'error', msg}
const DIR = 'horizon-room';

self.onmessage = async ({ data: { bytes } }) => {
  let root, dir, access, out;
  try {
    root = await navigator.storage.getDirectory();
  } catch (e) {
    self.postMessage({ reason: 'blocked', msg: `${e && e.name}: ${e && e.message}` });
    return;
  }
  try {
    dir = await root.getDirectoryHandle(DIR, { create: true });
    access = await (await dir.getFileHandle('room.bin', { create: true })).createSyncAccessHandle();
    access.truncate(bytes);
    const size = access.getSize();
    out = size === bytes ? { ok: true } : { reason: 'unkept', msg: `${size} of ${bytes} bytes kept` };
  } catch (e) {
    const name = e && e.name;
    out = { reason: name === 'QuotaExceededError' ? 'quota' : name === 'SecurityError' || name === 'NotAllowedError' ? 'blocked' : 'error',
            msg: `${name || 'Error'}: ${e && e.message || e}` };
  } finally {
    try { access?.truncate(0); } catch { /* */ }
    try { access?.close(); } catch { /* */ }
    try { await root.removeEntry(DIR, { recursive: true }); } catch { /* */ }
  }
  self.postMessage(out);
};
