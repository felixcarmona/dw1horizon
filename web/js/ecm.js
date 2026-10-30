// ECM (Error Code Modeler) -> the raw .bin it was made from. Written for this project from the format's description
// and the CD-ROM standard (ECMA-130), not from any other ECM program's code.
//
// The format. An ECM file stores a 2352-byte-sector image with the parts of each sector that can be computed from the
// rest (sync, mode byte, EDC, ECC) left out:
//   "ECM\0", then records, each a (type, count) number followed by `count` items of that type:
//     byte 0: bits 0-1 the type, bits 2-6 the low 5 bits of count - 1, bit 7 set when another byte follows;
//     each further byte: 7 more bits of count - 1 (low bits first), bit 7 set when another byte follows.
//   type 0: `count` bytes copied as they are (sync and headers of Mode 2 sectors, audio, anything else);
//   type 1: Mode 1 sectors, 3 address bytes + 2048 data bytes each -> 2352 bytes: sync (00, ten FF, 00), the
//           address, mode 1, the data, EDC over bytes 0-2063, 8 zero bytes, then ECC P and Q;
//   type 2: Mode 2 Form 1 sectors without their first 16 bytes (sync + header, stored as a type 0 record before),
//           4 subheader bytes + 2048 data bytes each -> 2336 bytes: the subheader twice, the data, EDC over the
//           subheader copies and data, ECC P and Q computed as if the 4 header bytes were zero;
//   type 3: Mode 2 Form 2 sectors likewise, 4 subheader bytes + 2324 data bytes -> 2336 bytes: the subheader twice,
//           the data, EDC over the subheader copies and data (no ECC in Form 2).
//   The end: a record whose count - 1 is 0xFFFFFFFF (type 0: FC FF FF FF 3F), then the EDC of the whole decoded image
//   (little-endian), which is checked.
//
// EDC (ECMA-130): a 32-bit CRC with the polynomial (x^16 + x^15 + x^2 + 1)(x^16 + x^2 + x + 1), processed
// least significant bit first: the reflected form is 0xD8018001, initial value 0, no final inversion, stored
// little-endian.
// ECC (ECMA-130 Annex A, RSPC): the 2064 bytes from the header (offset 12) to the EDC's zero padding are 1032 16-bit
// words; each byte plane (even bytes, odd bytes) is coded on its own, over GF(2^8) with x^8 + x^4 + x^3 + x^2 + 1
// (0x11D) and alpha = x. P: 43 columns of 24 words (word 43r + c is row r, column c), each with 2 parity words at
// 1032 + c and 1075 + c. Q: 26 diagonals over those 1118 words, diagonal i being words (43i + 44j) mod 1118 for j
// = 0..42, with 2 parity words at 1118 + i and 1144 + i. Every codeword c_0..c_(n-1), its two parity symbols last,
// satisfies sum c_i = 0 and sum alpha^(n-1-i) c_i = 0; with S0 = sum of the data symbols and S1 = sum of
// alpha^(n-1-i) times them, the parity is p0 = (S0 + S1) / (alpha + 1) and p1 = S0 + p0.

const SYNC = [0x00, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0x00];
const IN_CHUNK = 8 << 20;
const OUT_CHUNK = 4 << 20;

// ---------------------------------------------------------------- EDC: CRC-32/0xD8018001, eight bytes per step

const EDC = (() => {
  const t = new Int32Array(8 * 256);
  for (let i = 0; i < 256; i++) {
    let v = i;
    for (let k = 0; k < 8; k++) v = (v >>> 1) ^ (v & 1 ? 0xd8018001 : 0);
    t[i] = v;
  }
  // t[k*256 + i]: byte i followed by k zero bytes
  for (let k = 1; k < 8; k++) {
    for (let i = 0; i < 256; i++) {
      const v = t[(k - 1) * 256 + i];
      t[k * 256 + i] = (v >>> 8) ^ t[v & 255];
    }
  }
  return t;
})();

function edc(b, from, to, crc = 0) {
  const t = EDC;
  let i = from;
  for (const end = to - 7; i < end; i += 8) {
    const lo = crc ^ (b[i] | b[i + 1] << 8 | b[i + 2] << 16 | b[i + 3] << 24);
    crc = t[1792 + (lo & 255)] ^ t[1536 + ((lo >>> 8) & 255)] ^ t[1280 + ((lo >>> 16) & 255)] ^ t[1024 + (lo >>> 24)]
        ^ t[768 + b[i + 4]] ^ t[512 + b[i + 5]] ^ t[256 + b[i + 6]] ^ t[b[i + 7]];
  }
  for (; i < to; i++) crc = (crc >>> 8) ^ t[(crc ^ b[i]) & 255];
  return crc >>> 0;
}

function putEdc(s, from, to) {
  const e = edc(s, from, to);
  s[to] = e; s[to + 1] = e >>> 8; s[to + 2] = e >>> 16; s[to + 3] = e >>> 24;
}

// ---------------------------------------------------------------- ECC: RSPC P and Q

// GF(2^8) mod 0x11D: TIMES_A[v] = alpha v, TIMES_A2[v] = alpha^2 v, DIV_A1[v] = v / (alpha + 1)
const [TIMES_A, TIMES_A2, DIV_A1] = (() => {
  const exp = new Uint8Array(255), log = new Uint8Array(256);
  for (let i = 0, x = 1; i < 255; i++) {
    exp[i] = x; log[x] = i;
    x <<= 1;
    if (x & 0x100) x ^= 0x11d;
  }
  const mul = (a, b) => (a && b ? exp[(log[a] + log[b]) % 255] : 0);
  const a1 = 3;  // alpha + 1
  const a = new Uint8Array(256), a2 = new Uint8Array(256), d = new Uint8Array(256);
  for (let v = 0; v < 256; v++) {
    a[v] = mul(v, 2);
    a2[v] = mul(v, 4);
    d[v] = v ? exp[(log[v] - log[a1] + 255) % 255] : 0;
  }
  return [a, a2, d];
})();

// Byte offsets in the sector of each codeword's data symbols, and where its two parity bytes go.
function codewords(count, len, word, parity0, parity1) {
  const at = new Uint16Array(count * 2 * len), out = new Uint16Array(count * 4);
  let k = 0;
  for (let plane = 0; plane < 2; plane++) {
    for (let c = 0; c < count; c++) {
      const v = plane * count + c;
      for (let j = 0; j < len; j++) at[k++] = 12 + 2 * word(c, j) + plane;
      out[2 * v] = 12 + 2 * (parity0 + c) + plane;
      out[2 * v + 1] = 12 + 2 * (parity1 + c) + plane;
    }
  }
  return [at, out];
}

const P = codewords(43, 24, (c, r) => 43 * r + c, 1032, 1075);
const Q = codewords(26, 43, (i, j) => (43 * i + 44 * j) % 1118, 1118, 1144);

function rspc(s, [at, out], len) {
  const ta = TIMES_A;
  for (let v = 0, k = 0, n = out.length >> 1; v < n; v++) {
    let s0 = 0, s1 = 0;
    for (const end = k + len; k < end; k++) {
      const x = s[at[k]];
      s0 ^= x;
      s1 = ta[s1] ^ x;
    }
    const p0 = DIV_A1[s0 ^ TIMES_A2[s1]];
    s[out[2 * v]] = p0;
    s[out[2 * v + 1]] = s0 ^ p0;
  }
}

function ecc(s) {
  rspc(s, P, 24);
  rspc(s, Q, 43);
}

// ---------------------------------------------------------------- the sectors

const sector = new Uint8Array(2352);
sector.set(SYNC);

// type 1: 3 + 2048 bytes at `src[at]` -> sector[0..2352]
function mode1(src, at) {
  const s = sector;
  s[12] = src[at]; s[13] = src[at + 1]; s[14] = src[at + 2]; s[15] = 1;
  s.set(src.subarray(at + 3, at + 2051), 16);
  putEdc(s, 0, 2064);
  s.fill(0, 2068, 2076);
  ecc(s);
}

// type 2: 4 + 2048 bytes -> sector[16..2352]
function form1(src, at) {
  const s = sector;
  s[12] = s[13] = s[14] = s[15] = 0;
  s[16] = s[20] = src[at]; s[17] = s[21] = src[at + 1]; s[18] = s[22] = src[at + 2]; s[19] = s[23] = src[at + 3];
  s.set(src.subarray(at + 4, at + 2052), 24);
  putEdc(s, 16, 2072);
  ecc(s);
}

// type 3: 4 + 2324 bytes -> sector[16..2352]
function form2(src, at) {
  const s = sector;
  s[16] = s[20] = src[at]; s[17] = s[21] = src[at + 1]; s[18] = s[22] = src[at + 2]; s[19] = s[23] = src[at + 3];
  s.set(src.subarray(at + 4, at + 2328), 24);
  putEdc(s, 16, 2348);
}

const KIND = [null, [2051, mode1, 0], [2052, form1, 16], [2328, form2, 16]];  // [bytes in, build, first byte out]

// ---------------------------------------------------------------- the stream

// Decodes `file` (a Blob); `emit(Uint8Array)` gets the image in order, in fresh buffers of up to 4 MB.
// Throws Error('not ECM' | 'ECM file cut short' | 'ECM checksum').
export async function decodeEcm(file, emit, progress = () => {}) {
  const size = file.size;
  let buf = new Uint8Array(0), p = 0, pos = 0;  // buf holds file bytes [pos - buf.length + ..., pos)
  let ahead = null;

  const read = (at) => (at < size ? file.slice(at, Math.min(size, at + IN_CHUNK)).arrayBuffer() : null);
  // makes at least `n` unread bytes available in buf[p..]
  async function fill(n) {
    while (buf.length - p < n) {
      if (!ahead) throw new Error('ECM file cut short');
      const got = new Uint8Array(await ahead);
      pos += got.length;
      ahead = read(pos);
      const rest = buf.length - p, nb = new Uint8Array(rest + got.length);
      nb.set(buf.subarray(p));
      nb.set(got, rest);
      buf = nb; p = 0;
    }
  }

  let out = new Uint8Array(OUT_CHUNK), o = 0, total = 0;
  const flush = () => {
    if (!o) return;
    total = edc(out, 0, o, total);
    emit(o === out.length ? out : out.slice(0, o));
    out = new Uint8Array(OUT_CHUNK); o = 0;
    progress((pos - (buf.length - p)) / size);
  };

  ahead = read(0);
  await fill(4);
  if (buf[0] !== 0x45 || buf[1] !== 0x43 || buf[2] !== 0x4d || buf[3] !== 0) throw new Error('not ECM');
  p = 4;

  for (;;) {
    // the record's type and count - 1
    if (buf.length - p < 5) await fill(Math.min(5, size - (pos - (buf.length - p))) || 1);
    let c = buf[p++];
    const type = c & 3;
    let num = (c >> 2) & 31, shift = 5;
    while (c & 0x80) {
      if (shift > 26) throw new Error('ECM checksum');
      if (p >= buf.length) await fill(1);
      c = buf[p++];
      num += (c & 127) * 2 ** shift;
      shift += 7;
    }
    if (num === 0xffffffff) break;
    if (num >= 0x80000000) throw new Error('ECM checksum');
    let count = num + 1;

    if (type === 0) {
      while (count > 0) {
        if (p >= buf.length) await fill(1);
        const n = Math.min(count, buf.length - p, out.length - o);
        out.set(buf.subarray(p, p + n), o);
        p += n; o += n; count -= n;
        if (o === out.length) flush();
      }
      continue;
    }

    const [len, build, first] = KIND[type];
    const n = 2352 - first;
    for (; count > 0; count--) {
      if (buf.length - p < len) await fill(len);
      build(buf, p);
      p += len;
      if (out.length - o < n) {
        const k = out.length - o;
        out.set(sector.subarray(first, first + k), o);
        o += k;
        flush();
        out.set(sector.subarray(first + k), 0);
        o = n - k;
      } else {
        out.set(sector.subarray(first), o);
        o += n;
      }
    }
  }

  flush();
  await fill(4);
  const want = (buf[p] | buf[p + 1] << 8 | buf[p + 2] << 16 | buf[p + 3] << 24) >>> 0;
  if (want !== total) throw new Error('ECM checksum');
  progress(1);
}
