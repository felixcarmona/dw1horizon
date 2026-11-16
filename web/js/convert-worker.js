// ECM, PBP and CHD images -> the raw .bin they hold, off the main thread (js/ecm.js, js/pbp.js, js/chd.js).
//   in:  {kind: 'ecm' | 'pbp' | 'chd', file}
//   out: {progress: 0..1} ... then {file} (a File named like the input without .ecm / with .bin) or {error}

import { decodeEcm } from './ecm.js';
import { decodePbp } from './pbp.js';
import { decodeChd } from './chd.js';

let controller;

const COMPACT = 64 << 20;

self.onmessage = async ({ data: { kind, file, cancel, outputDir } }) => {
  if (cancel) { controller?.abort(); return; }
  controller = new AbortController();
  let access, outputName;
  try {
    let outputHandle;
    if (outputDir) {
      outputName = crypto.randomUUID() + '.bin';
      outputHandle = await outputDir.getFileHandle(outputName, { create: true });
      access = await outputHandle.createSyncAccessHandle();
    }
    const parts = [];
    let chunks = [], held = 0, last = -1;
    const emit = (b) => {
      if (access) {
        let at = 0;
        while (at < b.length) {
          const n = access.write(b.subarray(at));
          if (!n) throw new Error('CHD output write failed');
          at += n;
        }
        return;
      }
      chunks.push(b);
      held += b.length;
      if (held >= COMPACT) { parts.push(new Blob(chunks)); chunks = []; held = 0; }
    };
    const progress = (p) => {
      const q = Math.floor(p * 100);
      if (q !== last) { last = q; self.postMessage({ progress: q / 100 }); }
    };
    await ({ ecm: decodeEcm, pbp: decodePbp, chd: decodeChd })[kind](file, emit, progress, { signal: controller.signal });
    if (access) { access.flush(); access.close(); access = null; }
    if (!outputHandle) parts.push(new Blob(chunks));
    const name = kind === 'ecm' ? file.name.replace(/\.ecm$/i, '') : file.name.replace(/\.(pbp|chd)$/i, '') + '.bin';
    self.postMessage({ file: new File(outputHandle ? [await outputHandle.getFile()] : parts, /\.\w+$/.test(name) ? name : name + '.bin') });
  } catch (e) {
    try { access?.close(); } catch { /* already closed */ }
    if (outputName) await outputDir.removeEntry(outputName).catch(() => {});
    self.postMessage({ error: String(e && e.message || e) });
  }
};
