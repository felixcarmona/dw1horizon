// A disc image copied into this browser's private storage (OPFS horizon-discs/<game>/<name>) for the next visit
// (js/remember.js), off the main thread: File.slice in 8 MB pieces through a synchronous access handle, so a 700 MB
// image never sits in memory whole and every browser with OPFS can do it (Safari has no createWritable on the page).
// The game's folder is emptied first: one disc per game.
//   in:  {file, game}
//   out: {progress: 0..1} ... then {size} or {error, quota}

const CHUNK = 8 << 20;
const DIR = 'horizon-discs';

self.onmessage = async ({ data: { file, game } }) => {
  let access;
  try {
    const root = await (await navigator.storage.getDirectory()).getDirectoryHandle(DIR, { create: true });
    const dir = await root.getDirectoryHandle(game, { create: true });
    const names = [];
    for await (const name of dir.keys()) names.push(name);
    for (const name of names) await dir.removeEntry(name, { recursive: true });
    access = await (await dir.getFileHandle(file.name, { create: true })).createSyncAccessHandle();
    access.truncate(0);
    for (let at = 0; at < file.size; at += CHUNK) {
      const bytes = new Uint8Array(await file.slice(at, at + CHUNK).arrayBuffer());
      let done = 0;
      while (done < bytes.length) {
        const n = access.write(bytes.subarray(done), { at: at + done });
        if (!n) throw new DOMException('nothing written', 'QuotaExceededError');
        done += n;
      }
      self.postMessage({ progress: Math.min(1, (at + bytes.length) / file.size) });
    }
    access.flush();
    const size = access.getSize();
    access.close();
    access = null;
    self.postMessage({ size });
  } catch (e) {
    try { access?.close(); } catch { /* closed */ }
    self.postMessage({ error: `${e && e.name || 'Error'}: ${e && e.message || e}`, quota: e && e.name === 'QuotaExceededError' });
  }
};
