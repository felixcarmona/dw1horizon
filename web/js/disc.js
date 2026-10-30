// What a dropped file is, read straight from its bytes: an archive, an ECM/PBP/CHD image, a cue sheet, or a disc
// image whose ISO 9660 file system tells the game (the boot file named in SYSTEM.CNF) before any checksum is taken.
// Also reads single files off an image (checkFiles), so an image whose whole-image checksum cannot match redump
// (a 2048-byte .iso, another rip) can be checked by the files the import reads.

const DATA = 2048;
// Sector layouts an image may have: [bytes per sector, where the 2048 user data starts]. 'raw' sectors carry the
// sync and header, and their mode byte says where the data is (mode 1: 16, mode 2: 24). 2352 is the redump form.
const LAYOUTS = [[2352, 'raw'], [2448, 'raw'], [2336, 8], [2048, 0]];

const ARCHIVE_EXT = ['zip', '7z', 'rar', 'tar', 'gz', 'tgz', 'bz2', 'tbz', 'tbz2', 'xz', 'txz', 'zst', 'lzma', 'cab'];

async function bytes(file, at, n) {
  return new Uint8Array(await file.slice(at, at + n).arrayBuffer());
}

const ascii = (b) => String.fromCharCode(...b);

// The part of a split archive a name is, or null: {base, n} (n: 1 for the part to open)
export function partOf(name) {
  let m;
  if ((m = name.match(/^(.*)\.part0*(\d+)\.rar$/i))) return { base: m[1] + '.rar', n: +m[2] };
  if ((m = name.match(/^(.*)\.r(\d\d)$/i))) return { base: m[1] + '.rar', n: +m[2] + 2 };
  if (/\.rar$/i.test(name)) return { base: name, n: 1 };            // the first volume of an old-style set (or alone)
  if ((m = name.match(/^(.*\.(?:7z|zip|rar|tar|gz))\.(\d{3})$/i))) return { base: m[1], n: +m[2] };
  if ((m = name.match(/^(.*)\.z(\d\d)$/i))) return { base: m[1] + '.zip', n: +m[2] };
  if (/\.zip$/i.test(name)) return { base: name, n: 0 };            // a split zip's last part (or a whole zip)
  return null;
}

function magic(b) {
  if (b[0] === 0x37 && b[1] === 0x7a && b[2] === 0xbc && b[3] === 0xaf) return '7z';
  if (b[0] === 0x50 && b[1] === 0x4b && (b[2] === 3 || b[2] === 5 || b[2] === 7)) return 'zip';
  if (ascii(b.subarray(0, 4)) === 'Rar!') return 'rar';
  if (b[0] === 0x1f && b[1] === 0x8b) return 'gz';
  if (ascii(b.subarray(0, 3)) === 'BZh') return 'bz2';
  if (b[0] === 0xfd && ascii(b.subarray(1, 5)) === '7zXZ') return 'xz';
  if (b[0] === 0x28 && b[1] === 0xb5 && b[2] === 0x2f && b[3] === 0xfd) return 'zst';
  if (ascii(b.subarray(0, 4)) === 'ECM\0') return 'ecm';
  if (b[0] === 0 && ascii(b.subarray(1, 4)) === 'PBP') return 'pbp';
  if (ascii(b.subarray(0, 8)) === 'MComprHD') return 'chd';
  return null;
}

// The image's sectors: {size, raw, sector(lba) -> 2048 bytes, read(lba, n) -> n bytes of consecutive data}, or null
export async function openImage(file) {
  for (const [size, at] of LAYOUTS) {
    if (file.size < 17 * size) continue;
    const s = await bytes(file, 16 * size, size);
    const off = at === 'raw' ? (s[15] === 2 ? 24 : 16) : at;
    if (!(s[off] === 1 && ascii(s.subarray(off + 1, off + 6)) === 'CD001')) continue;
    const dataAt = (sec) => (at === 'raw' ? (sec[15] === 2 ? 24 : 16) : at);
    const read = async (lba, n) => {
      const count = Math.ceil(n / DATA);
      if (size === DATA) return bytes(file, lba * DATA, n);
      const raw = await bytes(file, lba * size, count * size);
      const out = new Uint8Array(count * DATA);
      for (let i = 0; i < count; i++) {
        const sec = raw.subarray(i * size, (i + 1) * size);
        out.set(sec.subarray(dataAt(sec), dataAt(sec) + DATA), i * DATA);
      }
      return out.subarray(0, n);
    };
    return { size, raw: size === 2352, read, sector: (lba) => read(lba, DATA) };
  }
  return null;
}

// Files by path, through the path table: some discs (Digimon World 2 and 2003) hide AAA/ from the root directory.
async function fileSystem(img) {
  const pvd = await img.sector(16);
  const dv = new DataView(pvd.buffer, pvd.byteOffset);
  const pt = await img.read(dv.getUint32(140, true), dv.getUint32(132, true));
  const dirs = [];
  for (let p = 0; p + 8 <= pt.length;) {
    const n = pt[p];
    if (!n) break;
    const lba = pt[p + 2] | pt[p + 3] << 8 | pt[p + 4] << 16 | pt[p + 5] << 24;
    const parent = pt[p + 6] | pt[p + 7] << 8;
    const name = ascii(pt.subarray(p + 8, p + 8 + n));
    dirs.push({ lba, parent, name });
    p += 8 + n + (n & 1);
  }
  const pathOf = (i) => (i === 0 ? '' : (dirs[i].parent - 1 === 0 ? '' : pathOf(dirs[i].parent - 1) + '/') + dirs[i].name);
  const dirLba = new Map(dirs.map((d, i) => [pathOf(i).toUpperCase(), d.lba]));
  const listings = new Map();
  async function listing(lba) {
    if (!listings.has(lba)) {
      const first = await img.sector(lba);
      const size = new DataView(first.buffer, first.byteOffset).getUint32(10, true);
      const d = await img.read(lba, size);
      const v = new DataView(d.buffer, d.byteOffset);
      const map = new Map();
      for (let p = 0; p < d.length;) {
        const n = d[p];
        if (n === 0) { p = (Math.floor(p / DATA) + 1) * DATA; continue; }
        const id = ascii(d.subarray(p + 33, p + 33 + d[p + 32])).split(';')[0].toUpperCase();
        map.set(id, { lba: v.getUint32(p + 2, true), size: v.getUint32(p + 10, true) });
        p += n;
      }
      listings.set(lba, map);
    }
    return listings.get(lba);
  }
  return {
    async get(path) {
      const k = path.toUpperCase().lastIndexOf('/');
      const lba = dirLba.get(k < 0 ? '' : path.toUpperCase().slice(0, k));
      if (lba == null) return null;
      const f = (await listing(lba)).get(path.toUpperCase().slice(k + 1));
      return f ? img.read(f.lba, f.size) : null;
    },
  };
}

const hex = (buf) => Array.from(new Uint8Array(buf), (x) => x.toString(16).padStart(2, '0')).join('');

// Checks `list` {path on the disc: SHA-1} against the image's files: {bad: [paths], missing: [paths]}
export async function checkFiles(file, list, onProgress = () => {}) {
  const img = await openImage(file);
  if (!img) return { bad: [], missing: Object.keys(list) };
  const fs = await fileSystem(img);
  const out = { bad: [], missing: [] };
  const paths = Object.keys(list);
  for (const [i, path] of paths.entries()) {
    const data = await fs.get(path);
    if (!data) out.missing.push(path);
    else if (hex(await crypto.subtle.digest('SHA-1', data)) !== list[path]) out.bad.push(path);
    onProgress((i + 1) / paths.length);
  }
  return out;
}

// {kind: 'image', boot, raw, size} | {kind: 'cue', files} | {kind: 'archive' | 'ecm' | 'pbp' | 'chd', format}
// | {kind: 'unsupported', format}
export async function inspect(file) {
  const ext = file.name.toLowerCase().split('.').pop();
  if (ext === 'cue') {
    const text = await file.text();
    const files = [...text.matchAll(/^\s*FILE\s+(?:"([^"]+)"|(\S+))/gim)].map((m) => m[1] || m[2]);
    return { kind: 'cue', files };
  }
  const head = await bytes(file, 0, 16);
  const m = magic(head) || (partOf(file.name) ? 'part' : null);
  if (m === 'ecm' || m === 'pbp' || m === 'chd') return { kind: m, format: m };
  if (m || ARCHIVE_EXT.includes(ext)) return { kind: 'archive', format: m === 'part' || !m ? ext : m };
  const img = await openImage(file);
  if (!img) return { kind: 'unsupported', format: ext || 'unknown' };
  const fs = await fileSystem(img);
  const cnf = await fs.get('SYSTEM.CNF');
  const b = cnf && new TextDecoder('latin1').decode(cnf).match(/BOOT\s*=\s*cdrom:\\?([A-Z0-9_.]+)/i);
  return { kind: 'image', boot: b ? b[1].toUpperCase() : null, raw: img.raw, size: img.size };
}
