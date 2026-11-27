// The installers the page makes from the disc it built: the same four the desktop patcher makes (tools/patcher/apk.py,
// setup_exe.py, mac_app.py, linux_run.py), in the visitor's browser, with the disc never leaving it.
//
// Each is a Blob put together from the template (the empty Horizon Play of that system, served by the site from
// players/<tag>/, listed in engine/current.json `players`), the disc image File (in OPFS) and a few small parts made here. A Blob made of other
// Blobs refers to them, it does not copy them: the 900 MB disc is read only when the download is written to disk, and
// to compute the checksums the formats need (read in 1 MiB slices). The Linux .run is compressed, so it is the one
// written out (to a writable stream the caller gives: OPFS).
//
// Byte for byte with the Python makers where they can be (the .exe; the APK, given the same entry date: PKCS#1 v1.5
// signatures are deterministic); the Mac zip and the Linux tar hold the same files and modes (web/test/installers.mjs).
// No DOM: it runs in a worker, and in Node for the tests.

export const NAME = 'Digimon World Horizon';           // setup_exe.DISC_NAME
export const CUE = `FILE "${NAME}.bin" BINARY\r\n  TRACK 01 MODE2/2352\r\n    INDEX 01 00:00:00\r\n`;
const CHUNK = 1 << 20;
const enc = new TextEncoder();
const OCTET = 'application/octet-stream';

// ---------------------------------------------------------------- bytes
const u16 = (v) => { const b = new Uint8Array(2); new DataView(b.buffer).setUint16(0, v, true); return b; };
const u32 = (v) => { const b = new Uint8Array(4); new DataView(b.buffer).setUint32(0, v >>> 0, true); return b; };
const u64 = (v) => { const b = new Uint8Array(8); new DataView(b.buffer).setBigUint64(0, BigInt(v), true); return b; };
function cat(...parts) {
  const out = new Uint8Array(parts.reduce((n, p) => n + p.length, 0));
  let at = 0;
  for (const p of parts) { out.set(p, at); at += p.length; }
  return out;
}
const lp = (b) => cat(u32(b.length), b);              // apk.py _lp
const hex = (s) => Uint8Array.from(s.match(/../g) || [], (h) => parseInt(h, 16));
const bytesOf = async (blob, start = 0, end = blob.size) => new Uint8Array(await blob.slice(start, end).arrayBuffer());

const CRC_TABLE = (() => {
  const t = new Uint32Array(256);
  for (let n = 0; n < 256; n++) { let c = n; for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1; t[n] = c >>> 0; }
  return t;
})();
export function crc32(crc, bytes) {
  let c = ~crc >>> 0;
  for (let i = 0; i < bytes.length; i++) c = CRC_TABLE[(c ^ bytes[i]) & 0xff] ^ (c >>> 8);
  return ~c >>> 0;
}

// The CRC-32 of a whole Blob, read in slices. tick(n): bytes read.
export async function crcOf(blob, tick = () => {}, cancel = () => false) {
  let crc = 0;
  for (let at = 0; at < blob.size; at += CHUNK) {
    if (cancel()) throw new Error('cancelled');
    const b = await bytesOf(blob, at, Math.min(blob.size, at + CHUNK));
    crc = crc32(crc, b);
    tick(b.length);
  }
  return crc;
}

// ---------------------------------------------------------------- zip (template entries copied as they are)
// The template's entries: {name, method, crc, csize, usize, time, date, attr (external), system (made by), data (Blob)}
export async function zipEntries(zip) {
  const tailStart = Math.max(0, zip.size - 65558);
  const tail = await bytesOf(zip, tailStart);
  let e = tail.length - 22;
  const dv = new DataView(tail.buffer);
  while (e >= 0 && dv.getUint32(e, true) !== 0x06054b50) e--;
  if (e < 0) throw new Error('template: not a zip');
  const count = dv.getUint16(e + 10, true), cdSize = dv.getUint32(e + 12, true), cdAt = dv.getUint32(e + 16, true);
  if (count === 0xffff || cdAt === 0xffffffff) throw new Error('template: zip64 is not expected');
  const cd = await bytesOf(zip, cdAt, cdAt + cdSize);
  const c = new DataView(cd.buffer);
  const out = [];
  for (let p = 0, i = 0; i < count; i++) {
    if (c.getUint32(p, true) !== 0x02014b50) throw new Error('template: bad central directory');
    const nlen = c.getUint16(p + 28, true), xlen = c.getUint16(p + 30, true), clen = c.getUint16(p + 32, true);
    const ent = {
      system: c.getUint8(p + 5), flags: c.getUint16(p + 8, true), method: c.getUint16(p + 10, true),
      time: c.getUint16(p + 12, true), date: c.getUint16(p + 14, true), crc: c.getUint32(p + 16, true),
      csize: c.getUint32(p + 20, true), usize: c.getUint32(p + 24, true), attr: c.getUint32(p + 38, true),
      offset: c.getUint32(p + 42, true), name: new TextDecoder().decode(cd.subarray(p + 46, p + 46 + nlen)),
    };
    if (ent.flags & 1) throw new Error('template: encrypted entry');
    out.push(ent);
    p += 46 + nlen + xlen + clen;
  }
  for (const ent of out) {
    const head = await bytesOf(zip, ent.offset, ent.offset + 30);
    const h = new DataView(head.buffer);
    if (h.getUint32(0, true) !== 0x04034b50) throw new Error('template: bad local header');
    const start = ent.offset + 30 + h.getUint16(26, true) + h.getUint16(28, true);
    ent.data = zip.slice(start, start + ent.csize);
  }
  return out;
}

// A zip writer that keeps every part as a Blob or bytes (nothing large is copied). Entries as apk.py _entry writes
// them (version 20, no flags, the padding in the extra field), or with Unix modes for the Mac zip (made by 3).
class ZipOut {
  constructor() { this.parts = []; this.at = 0; this.central = []; }
  push(p) { this.parts.push(p); this.at += p.size ?? p.length; }
  add(name, { method = 0, crc, csize, usize, time, date, align = 1, attr = 0, system = 0 }, data) {
    const n = enc.encode(name);
    if (csize >= 0xffffffff || this.at >= 0xffffffff) throw new Error('the disc is too large for a zip');
    const offset = this.at;
    const pad = (align - ((offset + 30 + n.length) % align)) % align;
    this.push(cat(u32(0x04034b50), u16(20), u16(0), u16(method), u16(time), u16(date), u32(crc), u32(csize),
                  u32(usize), u16(n.length), u16(pad), n, new Uint8Array(pad)));
    if (data) this.push(data);
    this.central.push(cat(u32(0x02014b50), u16(system << 8 | 20), u16(20), u16(0), u16(method), u16(time), u16(date),
                          u32(crc), u32(csize), u32(usize), u16(n.length), u16(0), u16(0), u16(0), u16(0), u32(attr),
                          u32(offset), n));
  }
  finish() {
    const cdAt = this.at;
    const central = cat(...this.central);
    const end = cat(u32(0x06054b50), u16(0), u16(0), u16(this.central.length), u16(this.central.length),
                    u32(central.length), u32(cdAt), u16(0));
    return { body: this.parts, cdAt, central, end };
  }
}

// A JS Date -> the DOS time and date of a zip entry (local time, as Python's time.localtime()).
export function dosTime(d = new Date()) {
  return { time: (d.getHours() << 11) | (d.getMinutes() << 5) | (d.getSeconds() >> 1),
           date: ((Math.max(d.getFullYear(), 1980) - 1980) << 9) | ((d.getMonth() + 1) << 5) | d.getDate() };
}

// ---------------------------------------------------------------- Windows: the setup with the disc appended
// setup_exe.py: TEMPLATE + image + cue + trailer <QII8s> (image size, cue size, version 1, HZSETUP1).
export function makeSetup(template, image) {
  const cue = enc.encode(CUE);
  const trailer = cat(u64(image.size), u32(cue.length), u32(1), enc.encode('HZSETUP1'));
  return new Blob([template, image, cue, trailer], { type: OCTET });
}

// ---------------------------------------------------------------- Mac: the app in a zip, the disc inside
// mac_app.py: the template's "Horizon Play.app" as "Digimon World Horizon.app", Info.plist naming it so, the disc and
// its cue in Contents/Resources. Entries are copied as they are (their compression, modes and symlinks); the new
// ones stored. Nothing can be signed here: the app runs after right-click, Open (or xattr -cr), as from mac_app.py
// on Windows or Linux.
export async function makeMac(template, image, { crc, date = new Date(), tick } = {}) {
  const entries = await zipEntries(template);
  const top = entries.map((e) => e.name.split('/')[0]).find((n) => n.endsWith('.app'));
  if (!top || entries.some((e) => !e.name.startsWith(top + '/') && !e.name.startsWith('__MACOSX/'))) {
    throw new Error('template: no single .app inside');
  }
  const app = `${NAME}.app`;
  const res = `${app}/Contents/Resources/`;
  const when = dosTime(date);
  const out = new ZipOut();
  const fileAttr = (mode) => ((0o100000 | mode) << 16) >>> 0;
  let plist = null;
  for (const e of entries) {
    if (e.name.startsWith('__MACOSX/')) continue;
    const name = app + e.name.slice(top.length);
    if (name === `${app}/Contents/Info.plist`) { plist = e; continue; }
    if (name === res + `${NAME}.bin` || name === res + `${NAME}.cue`) continue;
    out.add(name, { ...e, align: 1 }, e.data);
  }
  if (!plist) throw new Error('template: not a Horizon Play .app (no Contents/Info.plist)');
  const text = await inflate(plist);
  const named = enc.encode(renamePlist(text));
  out.add(`${app}/Contents/Info.plist`, { crc: crc32(0, named), csize: named.length, usize: named.length, ...when,
                                          attr: fileAttr(0o644), system: 3 }, named);
  const cue = enc.encode(CUE);
  out.add(res + `${NAME}.cue`, { crc: crc32(0, cue), csize: cue.length, usize: cue.length, ...when,
                                 attr: fileAttr(0o644), system: 3 }, cue);
  const discCrc = crc ?? await crcOf(image, tick);
  out.add(res + `${NAME}.bin`, { crc: discCrc, csize: image.size, usize: image.size, ...when,
                                 attr: fileAttr(0o644), system: 3 }, image);
  const { body, central, end } = out.finish();
  return new Blob([...body, central, end], { type: OCTET });
}

// The plist's CFBundleName and CFBundleDisplayName set to NAME (an XML plist, as the template's is).
export function renamePlist(xml) {
  if (!/^<\?xml/.test(xml.trimStart())) throw new Error('template: Info.plist is not XML');
  let s = xml;
  for (const key of ['CFBundleName', 'CFBundleDisplayName']) {
    const re = new RegExp(`(<key>${key}</key>\\s*<string>)[^<]*(</string>)`);
    if (re.test(s)) s = s.replace(re, `$1${NAME}$2`);
    else s = s.replace(/(<dict>)/, `$1\n\t<key>${key}</key>\n\t<string>${NAME}</string>`);
  }
  return s;
}

async function inflate(e) {
  if (e.method === 0) return new TextDecoder().decode(await bytesOf(e.data));
  if (e.method !== 8) throw new Error(`template: compression method ${e.method}`);
  const stream = e.data.stream().pipeThrough(new DecompressionStream('deflate-raw'));
  return new TextDecoder().decode(new Uint8Array(await new Response(stream).arrayBuffer()));
}

// ---------------------------------------------------------------- Android: the APK with the disc, signed (v2)
// apk.py: the template's entries copied raw (META-INF/ dropped), aligned (stored 4, stored .so 16384), the disc
// stored at assets/horizon.bin aligned to 4096, then APK Signature Scheme v2 with the shared key (the same as the
// desktop patcher's: an APK made on either installs over the other).
const DISC_ENTRY = 'assets/horizon.bin';
const SHA256_PREFIX = hex('3031300d060960864801650304020105000420');

export async function makeApk(template, image, key, { crc, date = new Date(), tick = () => {}, cancel } = {}) {
  if (image.size === 0 || image.size % 2352) throw new Error('the disc is not a raw image (2352-byte sectors)');
  const out = new ZipOut();
  for (const e of await zipEntries(template)) {
    if (e.name.startsWith('META-INF/') || e.name === DISC_ENTRY) continue;
    const align = e.method === 0 ? (e.name.endsWith('.so') ? 16384 : 4) : 1;
    out.add(e.name, { ...e, attr: 0, system: 0, align }, e.data);
  }
  const discCrc = crc ?? await crcOf(image, tick, cancel);
  out.add(DISC_ENTRY, { crc: discCrc, csize: image.size, usize: image.size, ...dosTime(date), align: 4096 }, image);
  const { body, cdAt, central, end } = out.finish();
  const before = new Blob(body);
  // the v2 digest: 1 MiB chunks of the entries, then of the central directory, then of the end record
  const chunks = [];
  const add = async (b) => chunks.push(new Uint8Array(await crypto.subtle.digest('SHA-256', cat(Uint8Array.of(0xa5), u32(b.length), b))));
  for (let at = 0; at < cdAt; at += CHUNK) {
    if (cancel && cancel()) throw new Error('cancelled');
    const b = await bytesOf(before, at, Math.min(cdAt, at + CHUNK));
    await add(b);
    tick(b.length);
  }
  for (const part of [central, end]) for (let at = 0; at < part.length; at += CHUNK) await add(part.subarray(at, at + CHUNK));
  const digest = new Uint8Array(await crypto.subtle.digest('SHA-256', cat(Uint8Array.of(0x5a), u32(chunks.length), ...chunks)));
  const k = { n: BigInt('0x' + key.n), e: BigInt(key.e), d: BigInt('0x' + key.d), cert: hex(key.cert) };
  const algo = u32(0x0103);
  const signed = cat(lp(lp(cat(algo, lp(digest)))), lp(lp(k.cert)), lp(new Uint8Array(0)));
  const signer = cat(lp(signed), lp(lp(cat(algo, lp(await rsaSign(k, signed))))), lp(publicKeyDer(k)));
  const value = lp(lp(signer));
  const pair = cat(u64(4 + value.length), u32(0x7109871a), value);
  const size = pair.length + 8 + 16;
  const block = cat(u64(size), pair, u64(size), enc.encode('APK Sig Block 42'));
  const end2 = end.slice();
  end2.set(u32(cdAt + block.length), 16);
  return new Blob([...body, block, central, end2], { type: 'application/vnd.android.package-archive' });
}

// RSASSA-PKCS1-v1_5 with SHA-256 (apk.py _sign): the shared key holds n, e and d only, which WebCrypto cannot import.
async function rsaSign(key, message) {
  const k = (key.n.toString(16).length + 1) >> 1;
  const t = cat(SHA256_PREFIX, new Uint8Array(await crypto.subtle.digest('SHA-256', message)));
  const em = cat(Uint8Array.of(0, 1), new Uint8Array(k - t.length - 3).fill(0xff), Uint8Array.of(0), t);
  const s = modPow(toBig(em), key.d, key.n);
  return fromBig(s, k);
}
const toBig = (b) => BigInt('0x' + (Array.from(b, (x) => x.toString(16).padStart(2, '0')).join('') || '0'));
function fromBig(v, len) {
  const h = v.toString(16).padStart(len * 2, '0');
  return hex(h);
}
function modPow(b, e, m) {
  let r = 1n; b %= m;
  while (e > 0n) { if (e & 1n) r = (r * b) % m; b = (b * b) % m; e >>= 1n; }
  return r;
}
// DER (apk.py _der, _int, _seq): the SubjectPublicKeyInfo of the key.
function der(tag, body) {
  const n = body.length;
  if (n < 0x80) return cat(Uint8Array.of(tag, n), body);
  const len = []; for (let v = n; v; v >>= 8) len.unshift(v & 0xff);
  return cat(Uint8Array.of(tag, 0x80 | len.length, ...len), body);
}
const derInt = (v) => { const bits = v.toString(2).length; return der(0x02, fromBig(v, (bits >> 3) + 1)); };
const seq = (...p) => der(0x30, cat(...p));
const RSA_ALG = seq(hex('06092a864886f70d010101'), Uint8Array.of(5, 0));
const publicKeyDer = (k) => seq(RSA_ALG, der(0x03, cat(Uint8Array.of(0), seq(derInt(k.n), derInt(k.e)))));

// ---------------------------------------------------------------- Linux: the .run (a shell header, then a tar.gz)
// linux_run.py: the header (served beside the template: players/<tag>/linux-run-header.sh, made by
// linux_run.header()), then gzip of a tar: the player's files out of its folder ("Horizon Play/"), owners 0, then
// the disc, its cue, icon.png and .manifest (the top-level names the uninstaller removes). The tar bytes differ from
// Python's tarfile (headers are written here); what is in it is the same.
export async function writeLinuxRun(template, image, header, icon, writable, { tick = () => {}, cancel } = {}) {
  const writer = writable.getWriter();
  await writer.write(enc.encode(header));
  const gz = new CompressionStream('gzip');
  const pump = gz.readable.pipeTo(new WritableStream({ write: (c) => writer.write(c) }));
  const tw = gz.writable.getWriter();
  const seen = new Set();
  const player = await untar(new Uint8Array(await new Response(template.stream().pipeThrough(new DecompressionStream('gzip'))).arrayBuffer()));
  let top = null;
  for (const m of player) {
    let name = m.name.startsWith('./') ? m.name.slice(2) : m.name;
    if (top === null) top = name.includes('/') || m.type === '5' ? name.split('/')[0] : '';
    if (top) name = name.slice(top.length).replace(/^\/+/, '');
    if (!name) continue;
    seen.add(name.split('/')[0]);
    await tw.write(tarHeader({ ...m, name }));
    if (m.type === '0' && m.data.length) await tw.write(m.data), await tw.write(new Uint8Array(pad512(m.data.length)));
  }
  if (!seen.has('horizon-play')) throw new Error('template: no horizon-play inside');
  await tw.write(tarHeader({ name: `${NAME}.bin`, mode: 0o644, size: image.size, type: '0' }));
  for (let at = 0; at < image.size; at += CHUNK) {
    if (cancel && cancel()) { await tw.abort('cancelled'); throw new Error('cancelled'); }
    const b = await bytesOf(image, at, Math.min(image.size, at + CHUNK));
    await tw.write(b);
    tick(b.length);
  }
  await tw.write(new Uint8Array(pad512(image.size)));
  seen.add(`${NAME}.bin`);
  const small = async (name, data) => {
    await tw.write(tarHeader({ name, mode: 0o644, size: data.length, type: '0' }));
    await tw.write(data); await tw.write(new Uint8Array(pad512(data.length)));
    seen.add(name);
  };
  await small(`${NAME}.cue`, enc.encode(CUE));
  await small('icon.png', icon);
  const manifest = enc.encode([...seen].sort(pyOrder).join('\n') + '\n');
  await tw.write(tarHeader({ name: '.manifest', mode: 0o644, size: manifest.length, type: '0' }));
  await tw.write(manifest); await tw.write(new Uint8Array(pad512(manifest.length)));
  await tw.write(new Uint8Array(1024));            // the end of the archive
  await tw.close();
  await pump;
  await writer.close();
}
const pad512 = (n) => (512 - (n % 512)) % 512;
const pyOrder = (a, b) => (a < b ? -1 : a > b ? 1 : 0);   // Python's sorted(): by code point, as JS compares strings

// The members of an uncompressed tar: {name, mode, mtime, type, linkname, size, data}. GNU long names (L, K) and
// pax headers (x: path, linkpath) are folded into the member that follows.
export function untar(b) {
  const out = [];
  const str = (o, n) => { let e = o; while (e < o + n && b[e]) e++; return new TextDecoder().decode(b.subarray(o, e)); };
  const oct = (o, n) => {
    if (b[o] & 0x80) { let v = 0; for (let i = o + 1; i < o + n; i++) v = v * 256 + b[i]; return v; }
    return parseInt(str(o, n).trim() || '0', 8);
  };
  let long = null, longLink = null, pax = {};
  for (let at = 0; at + 512 <= b.length;) {
    if (b.subarray(at, at + 512).every((x) => x === 0)) break;
    const size = oct(at + 124, 12), type = String.fromCharCode(b[at + 156] || 48);
    const data = b.subarray(at + 512, at + 512 + size);
    at += 512 + size + pad512(size);
    if (type === 'L') { long = str(at - size - pad512(size), size); continue; }
    if (type === 'K') { longLink = new TextDecoder().decode(data).replace(/\0+$/, ''); continue; }
    if (type === 'x') {
      for (const line of new TextDecoder().decode(data).split('\n')) {
        const m = line.match(/^\d+ (path|linkpath)=(.*)$/);
        if (m) pax[m[1]] = m[2];
      }
      continue;
    }
    if (type === 'g') continue;
    const prefix = str(at - size - pad512(size) - 512 + 345, 155);
    let name = str(at - size - pad512(size) - 512, 100);
    if (prefix && b[at - size - pad512(size) - 512 + 257] === 0x75) name = `${prefix}/${name}`;   // ustar prefix
    const h = at - size - pad512(size) - 512;
    out.push({ name: pax.path || long || name, mode: oct(h + 100, 8) & 0o7777, mtime: oct(h + 136, 12), type: type === '\0' ? '0' : type,
               linkname: pax.linkpath || longLink || str(h + 157, 100), size: type === '0' ? size : 0, data: type === '0' ? data : new Uint8Array(0) });
    long = longLink = null; pax = {};
  }
  return out;
}

// One ustar header (owners 0, no user or group names, as linux_run.py _add_member); a name or link past 100 bytes gets
// a GNU long-name member first (as Python's GNU_FORMAT).
function tarHeader({ name, mode, size = 0, mtime = 0, type = '0', linkname = '' }) {
  const parts = [];
  const nb = enc.encode(name), lb = enc.encode(linkname);
  if (nb.length > 99) parts.push(raw('././@LongLink', 0, nb.length + 1, 'L', ''), cat(nb, new Uint8Array(1 + pad512(nb.length + 1))));
  if (lb.length > 99) parts.push(raw('././@LongLink', 0, lb.length + 1, 'K', ''), cat(lb, new Uint8Array(1 + pad512(lb.length + 1))));
  parts.push(raw(name, mode, type === '0' ? size : 0, type, linkname, mtime));
  return cat(...parts);
}
function raw(name, mode, size, type, linkname, mtime = 0) {
  const h = new Uint8Array(512);
  const put = (o, s, n) => h.set(enc.encode(s).subarray(0, n), o);
  const octal = (o, v, n) => put(o, v.toString(8).padStart(n - 1, '0') + '\0', n);
  put(0, name, 100);
  octal(100, mode, 8); octal(108, 0, 8); octal(116, 0, 8);
  if (size > 0o77777777777) { h[124] = 0x80; let v = BigInt(size); for (let i = 135; i > 124; i--) { h[i] = Number(v & 0xffn); v >>= 8n; } }
  else octal(124, size, 12);
  octal(136, mtime, 12);
  h.fill(0x20, 148, 156);
  h[156] = type.charCodeAt(0);
  put(157, linkname, 100);
  put(257, 'ustar  \0', 8);       // GNU magic, as Python's GNU_FORMAT
  let sum = 0; for (const x of h) sum += x;
  put(148, sum.toString(8).padStart(6, '0') + '\0 ', 8);
  return h;
}
