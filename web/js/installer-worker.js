// Makes one installer (js/installers.js) from the disc the page built, off the page's thread, into OPFS beside the
// disc (horizon-build/installers/: tidyStorage removes it when the page loads again, a new build removes it with the
// rest). Only one installer is kept at a time: each holds the whole disc.
//
// In:  {kind: 'apk'|'setup'|'mac'|'linux', image: Blob (the disc), file: the name to give it, crc?: the disc's CRC-32,
//       template: {url, size, sha256}, key?: url (apk), header?: url, icon?: url (linux)}  (urls absolute)
// Out: {progress: 0..1, phase: 'fetch'|'read'|'write'} while it works, then {done: File, crc} or {error, kind?}.
// The page stops it with terminate() and then removes the half-written file (removeInstallers()).
import { makeApk, makeSetup, makeMac, writeLinuxRun, crcOf } from './installers.js';
import { failureKind } from './engine/engine.js';

const DIR = 'installers';

async function fetchChecked(url, want = null) {
  const r = await fetch(url);
  if (!r.ok) throw new Error(`${url.split('/').pop()}: HTTP ${r.status}`);
  const blob = await r.blob();
  if (want) {
    const sum = Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256', await blob.arrayBuffer())),
                           (b) => b.toString(16).padStart(2, '0')).join('');
    if (blob.size !== want.size || sum !== want.sha256) throw new Error(`${url.split('/').pop()}: not the release's file (SHA-256)`);
  }
  return blob;
}

self.onmessage = async ({ data: m }) => {
  try {
    const { image, kind } = m;
    let done = 0;
    // the work, in bytes: what is read to compute checksums, then what is written
    const needCrc = (kind === 'apk' || kind === 'mac') && m.crc == null;
    const reads = (needCrc ? image.size : 0) + (kind === 'apk' ? image.size : 0);
    const total = reads + image.size + (m.template.size || 0);
    let last = -1;
    const tick = (n, phase) => {
      done += n;
      const f = Math.min(1, done / total);
      if (f - last >= 0.002 || f === 1) { last = f; postMessage({ progress: f, phase }); }
    };
    postMessage({ progress: 0, phase: 'fetch' });
    const template = await fetchChecked(m.template.url, m.template);
    const extra = {
      key: m.key ? await (await fetchChecked(m.key)).text().then(JSON.parse) : null,
      header: m.header ? await (await fetchChecked(m.header)).text() : null,
      icon: m.icon ? new Uint8Array(await (await fetchChecked(m.icon)).arrayBuffer()) : null,
    };
    const root = await (await navigator.storage.getDirectory()).getDirectoryHandle('horizon-build', { create: true });
    try { await root.removeEntry(DIR, { recursive: true }); } catch { /* none */ }
    const dir = await root.getDirectoryHandle(DIR, { create: true });
    const handle = await dir.getFileHandle(m.file, { create: true });
    const writable = await handle.createWritable();
    let crc = m.crc;
    const read = (n) => tick(n, 'read');
    if (kind === 'linux') {
      await writeLinuxRun(template, image, extra.header, extra.icon, writable, { tick: (n) => tick(n, 'write') });
    } else {
      if (needCrc) crc = await crcOf(image, read);
      const blob = kind === 'apk' ? await makeApk(template, image, extra.key, { crc, tick: read })
        : kind === 'mac' ? await makeMac(template, image, { crc })
        : makeSetup(template, image);
      const count = new TransformStream({ transform(chunk, c) { tick(chunk.length, 'write'); c.enqueue(chunk); } });
      await blob.stream().pipeThrough(count).pipeTo(writable);
    }
    postMessage({ progress: 1, phase: 'write' });
    postMessage({ done: await handle.getFile(), crc });
  } catch (e) {
    postMessage({ error: String(e?.message || e), kind: failureKind(`${e?.name || ''} ${e?.message || e}`) });
  }
};
