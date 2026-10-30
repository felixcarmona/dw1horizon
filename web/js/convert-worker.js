// ECM and PBP images -> the raw .bin they hold, off the main thread (js/ecm.js, js/pbp.js).
//   in:  {kind: 'ecm' | 'pbp', file}
//   out: {progress: 0..1} ... then {file} (a File named like the input without .ecm / with .bin) or {error}

import { decodeEcm } from './ecm.js';
import { decodePbp } from './pbp.js';

const COMPACT = 64 << 20;

self.onmessage = async ({ data: { kind, file } }) => {
  try {
    const parts = [];
    let chunks = [], held = 0, last = -1;
    const emit = (b) => {
      chunks.push(b);
      held += b.length;
      if (held >= COMPACT) { parts.push(new Blob(chunks)); chunks = []; held = 0; }
    };
    const progress = (p) => {
      const q = Math.floor(p * 100);
      if (q !== last) { last = q; self.postMessage({ progress: q / 100 }); }
    };
    await (kind === 'ecm' ? decodeEcm : decodePbp)(file, emit, progress);
    parts.push(new Blob(chunks));
    const name = kind === 'ecm' ? file.name.replace(/\.ecm$/i, '') : file.name.replace(/\.pbp$/i, '') + '.bin';
    self.postMessage({ file: new File(parts, /\.\w+$/.test(name) ? name : name + '.bin') });
  } catch (e) {
    self.postMessage({ error: String(e && e.message || e) });
  }
};
