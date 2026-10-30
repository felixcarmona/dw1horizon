// Unpacks the disc images inside an archive, in the browser: 7-Zip 24.09 compiled to WebAssembly (7z-wasm, LGPL with
// the unRAR restriction), which reads zip, 7z, rar (4 and 5), tar, gz, bz2, xz and split archives. The archive is
// mounted read-only (WORKERFS: read straight from the File, never copied into memory) and each wanted entry is
// written by `7zz x -so` into a device that collects it as Blob parts, so a 700 MB image never sits in the wasm heap.
//   in:  {files: [File]}            every part of one archive (one file unless it is split)
//   out: {progress: 0..1, entry} ... then {files: [File]} or {error: 'encrypted' | 'parts' | 'open' | text}

const CDN = 'https://cdn.jsdelivr.net/npm/7z-wasm@1.2.0/';
// What can be a disc, or another archive to open in turn (a .tar inside a .tar.gz)
const WANTED = /\.(bin|cue|iso|img|mdf|ecm|chd|pbp|zip|7z|rar|tar|gz|tgz|bz2|xz)$/i;
const COMPACT = 64 << 20;      // rule: chunks become a Blob every 64 MB, so the browser may keep them out of memory

let factory, wasmBinary;
async function load() {
  if (!factory) {
    factory = (await import(CDN + '7zz.es6.js')).default;
    wasmBinary = await (await fetch(CDN + '7zz.wasm')).arrayBuffer();
  }
}

// Runs 7zz once (a fresh instance each time: 7-Zip's main is not meant to run twice). `sink(Uint8Array)` gets
// stdout as data; stderr is returned as text, and `onErr(text so far)` sees it grow (7-Zip's progress).
async function run(files, args, sink, onErr = () => {}) {
  let out = '', err = '';
  const m = await factory({ wasmBinary, print: (s) => { out += s + '\n'; }, printErr: (s) => { err += s + '\n'; } });
  const FS = m.FS;
  FS.mkdir('/in');
  FS.mount(m.WORKERFS, { files }, '/in');
  if (sink) {
    // 7-Zip refuses to write data to a terminal: stdout and stderr become devices of our own
    const dev = (n, fn) => {
      const id = FS.makedev(64, n);
      FS.registerDevice(id, {
        open() {}, close() {}, read() { return 0; }, llseek() { return 0; },
        write(st, buf, off, len) { fn(new Uint8Array(buf.buffer, buf.byteOffset + off, len)); return len; },
      });
      FS.mkdev('/dev/out' + n, id);
    };
    dev(0, (b) => sink(b.slice()));
    dev(1, (b) => { err += new TextDecoder().decode(b); onErr(err); });
    FS.close(FS.getStream(1));
    FS.close(FS.getStream(2));
    FS.open('/dev/out0', 'w');
    FS.open('/dev/out1', 'w');
  }
  let code = 0;
  try {
    m.callMain(args);
  } catch (e) {
    if (e && typeof e.status === 'number') code = e.status;
    else err += '\n' + String(e && e.message || e);
  }
  return { out, err, code };
}

function failure(err) {
  if (/wrong password|^Encrypted = \+/im.test(err)) return 'encrypted';
  if (/missing volume|unexpected end of archive|there are some data after the end/i.test(err)) return 'parts';
  if (/can ?not open the file as archive|is not archive/i.test(err)) return 'open';
  return null;
}

// The part to open: part1 of a .partN.rar set, the .rar of an old-style set, the .001 of a split archive
function firstPart(files) {
  const score = (n) => {
    let m;
    if ((m = n.match(/\.part0*(\d+)\.rar$/i))) return +m[1];
    if (/\.rar$/i.test(n)) return 0;
    if ((m = n.match(/\.(\d{3})$/))) return +m[1];
    if (/\.zip$/i.test(n)) return 0;
    return 1000;
  };
  return [...files].sort((a, b) => score(a.name) - score(b.name))[0];
}

const SPLIT = /\.part0*\d+\.rar$|\.r\d\d$|\.\d{3}$|\.z\d\d$/i;

// A split set given without its first part cannot be opened at all
function missingFirst(files) {
  const names = files.map((f) => f.name);
  if (names.some((n) => /\.part0*\d+\.rar$/i.test(n)) && !names.some((n) => /\.part0*1\.rar$/i.test(n))) return true;
  if (names.some((n) => /\.\d{3}$/.test(n)) && !names.some((n) => /\.0*1$/.test(n))) return true;
  if (names.some((n) => /\.r\d\d$/i.test(n)) && !names.some((n) => /\.rar$/i.test(n))) return true;
  return false;
}

self.onmessage = async ({ data: { files } }) => {
  try {
    if (missingFirst(files)) return self.postMessage({ error: 'parts' });
    await load();
    const first = '/in/' + firstPart(files).name;
    const list = await run(files, ['l', '-slt', '-pnone', '-y', first]);
    const bad = failure(list.err + list.out);
    if (bad) return self.postMessage({ error: bad });
    const entries = [];
    for (const block of list.out.split(/\n\n/)) {
      const path = block.match(/^Path = (.*)$/m), size = block.match(/^Size = (\d+)$/m);
      if (!path || !size || /^Folder = \+$/m.test(block) || /^Attributes = D/m.test(block)) continue;
      if (path[1] === first) continue;
      if (WANTED.test(path[1])) entries.push({ path: path[1], size: +size[1] });
    }
    const total = entries.reduce((a, e) => a + e.size, 0) || 1;
    let done = 0;
    const outFiles = [];
    for (const e of entries) {
      const parts = [];
      let chunks = [], held = 0, got = 0, last = -1;
      const x = await run(files, ['x', '-so', '-bsp2', '-pnone', '-y', '-spd', first, e.path], (b) => {
        chunks.push(b);
        held += b.length;
        got += b.length;
        if (held >= COMPACT) { parts.push(new Blob(chunks)); chunks = []; held = 0; }
        const p = Math.floor(((done + got) / total) * 100);
        if (p !== last) { last = p; self.postMessage({ progress: p / 100, entry: e.path }); }
      });
      const bad = failure(x.err);
      if (bad) return self.postMessage({ error: bad });
      // rule: an entry that comes out short is a missing volume in a split set, a damaged archive otherwise
      if (got !== e.size) return self.postMessage({ error: files.some((f) => SPLIT.test(f.name)) ? 'parts' : 'open' });
      parts.push(new Blob(chunks));
      done += e.size;
      outFiles.push(new File(parts, e.path.split('/').pop(), { type: 'application/octet-stream' }));
    }
    self.postMessage({ files: outFiles });
  } catch (e) {
    self.postMessage({ error: String(e && e.message || e) });
  }
};
