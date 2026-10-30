// Checksums of a disc image, off the main thread: CRC-32 and SHA-1 (the two redump lists per track), streamed
// over File.slice so a 700 MB image never sits in memory whole. crypto.subtle.digest cannot stream, hence our own.
//   in:  {file}
//   out: {progress: 0..1} ... then {crc32, sha1} or {error}

const CHUNK = 8 << 20;

const CRC_TABLE = (() => {
  const t = new Uint32Array(256);
  for (let n = 0; n < 256; n++) {
    let c = n;
    for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1;
    t[n] = c >>> 0;
  }
  return t;
})();

function crc32(crc, bytes) {
  let c = ~crc >>> 0;
  for (let i = 0; i < bytes.length; i++) c = CRC_TABLE[(c ^ bytes[i]) & 0xff] ^ (c >>> 8);
  return ~c >>> 0;
}

class Sha1 {
  constructor() {
    this.h = new Int32Array([0x67452301, 0xefcdab89, 0x98badcfe, 0x10325476, 0xc3d2e1f0]);
    this.w = new Int32Array(80);
    this.tail = new Uint8Array(64);
    this.tailLen = 0;
    this.length = 0;
  }

  block(b, o) {
    const w = this.w;
    for (let i = 0; i < 16; i++, o += 4) w[i] = (b[o] << 24) | (b[o + 1] << 16) | (b[o + 2] << 8) | b[o + 3];
    for (let i = 16; i < 80; i++) {
      const x = w[i - 3] ^ w[i - 8] ^ w[i - 14] ^ w[i - 16];
      w[i] = (x << 1) | (x >>> 31);
    }
    let [a, bb, c, d, e] = this.h;
    for (let i = 0; i < 80; i++) {
      let f, k;
      if (i < 20) { f = (bb & c) | (~bb & d); k = 0x5a827999; }
      else if (i < 40) { f = bb ^ c ^ d; k = 0x6ed9eba1; }
      else if (i < 60) { f = (bb & c) | (bb & d) | (c & d); k = 0x8f1bbcdc; }
      else { f = bb ^ c ^ d; k = 0xca62c1d6; }
      const t = (((a << 5) | (a >>> 27)) + f + e + k + w[i]) | 0;
      e = d; d = c; c = (bb << 30) | (bb >>> 2); bb = a; a = t;
    }
    const h = this.h;
    h[0] += a; h[1] += bb; h[2] += c; h[3] += d; h[4] += e;
  }

  update(bytes) {
    this.length += bytes.length;
    let i = 0;
    if (this.tailLen) {
      const n = Math.min(64 - this.tailLen, bytes.length);
      this.tail.set(bytes.subarray(0, n), this.tailLen);
      this.tailLen += n; i = n;
      if (this.tailLen < 64) return;
      this.block(this.tail, 0); this.tailLen = 0;
    }
    for (; i + 64 <= bytes.length; i += 64) this.block(bytes, i);
    this.tail.set(bytes.subarray(i)); this.tailLen = bytes.length - i;
  }

  hex() {
    const bits = this.length * 8;
    const pad = new Uint8Array((this.tailLen < 56 ? 64 : 128) - this.tailLen);
    pad[0] = 0x80;
    const dv = new DataView(pad.buffer);
    dv.setUint32(pad.length - 8, Math.floor(bits / 2 ** 32));
    dv.setUint32(pad.length - 4, bits >>> 0);
    this.update(pad);
    return Array.from(this.h, (x) => (x >>> 0).toString(16).padStart(8, '0')).join('');
  }
}

self.onmessage = async ({ data: { file } }) => {
  try {
    const sha = new Sha1();
    let crc = 0;
    for (let at = 0; at < file.size; at += CHUNK) {
      const bytes = new Uint8Array(await file.slice(at, at + CHUNK).arrayBuffer());
      crc = crc32(crc, bytes);
      sha.update(bytes);
      self.postMessage({ progress: Math.min(1, (at + bytes.length) / file.size) });
    }
    self.postMessage({ crc32: crc.toString(16).padStart(8, '0'), sha1: sha.hex() });
  } catch (e) {
    self.postMessage({ error: String(e && e.message || e) });
  }
};
