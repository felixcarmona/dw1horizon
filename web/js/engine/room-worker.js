// Check that OPFS accepts a small real write, flushes it and keeps its length. This is an access check,
// not a promise that the full build fits. Single-file limits and sparse allocation make a build-sized
// truncate unreliable. The caller can override `bytes` for quota failure tests.
//   in: {bytes}; out: {ok: true} | {reason: 'quota' | 'blocked' | 'unkept' | 'error', msg}
const DIR = 'horizon-room';
const failure = (e) => ({
  reason: e?.name === 'QuotaExceededError' ? 'quota'
    : ['SecurityError', 'NotAllowedError'].includes(e?.name) ? 'blocked' : 'error',
  msg: `${e?.name || 'Error'}: ${e?.message || e}`,
});

self.onmessage = async ({ data: { bytes } }) => {
  let root, dir, access, out;
  try {
    root = await navigator.storage.getDirectory();
  } catch (e) {
    self.postMessage(failure(e));
    return;
  }
  try {
    dir = await root.getDirectoryHandle(DIR, { create: true });
    access = await (await dir.getFileHandle('room.bin', { create: true })).createSyncAccessHandle();
    access.truncate(bytes);
    const sample = new Uint8Array(Math.min(bytes, 1024 * 1024));
    const written = access.write(sample, { at: 0 });
    if (written !== sample.length) throw new DOMException('Incomplete storage probe write', 'QuotaExceededError');
    access.flush();
    const size = access.getSize();
    out = size === bytes ? { ok: true } : { reason: 'unkept', msg: `${size} of ${bytes} bytes kept` };
  } catch (e) {
    out = failure(e);
  } finally {
    try { access?.truncate(0); } catch { /* */ }
    try { access?.close(); } catch { /* */ }
    try { await root.removeEntry(DIR, { recursive: true }); } catch { /* */ }
  }
  self.postMessage(out);
};
