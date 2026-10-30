// PBP (a PlayStation disc packed for PSP / PlayStation Classic by popstation and the like) -> the raw image inside.
// Layout: the PBP header points at DATA.PSAR; a one-disc PSAR starts "PSISOIMG0000", its table of contents (as the
// disc's Q subchannel: the lead-out, point 0xA2, gives the length) is at +0x800, its block index at +0x4000 (32 bytes
// per block: u32 offset, u16 length), the blocks from +0x100000. A block is 16 raw sectors (0x9300 bytes), deflated
// (raw deflate) or stored when its length is 0x9300. The sectors are the raw ones the PBP was made from, so a PBP
// made from the redump .bin gives that .bin back. PSN releases encrypt the PSAR: they cannot be read.

const BLOCK = 16 * 2352;

async function bytes(file, at, n) {
  return new Uint8Array(await file.slice(at, at + n).arrayBuffer());
}

const bcd = (x) => (x >> 4) * 10 + (x & 15);

async function inflate(b) {
  const ds = new DecompressionStream('deflate-raw');
  const w = ds.writable.getWriter();
  w.write(b).catch(() => {});
  w.close().catch(() => {});
  return new Uint8Array(await new Response(ds.readable).arrayBuffer());
}

// Decodes `file` (a Blob); `emit(Uint8Array)` gets the image in order. Throws Error('not PBP' | 'PBP multi-disc' |
// 'PBP encrypted').
export async function decodePbp(file, emit, progress = () => {}) {
  const head = await bytes(file, 0, 0x28);
  if (!(head[0] === 0 && String.fromCharCode(head[1], head[2], head[3]) === 'PBP')) throw new Error('not PBP');
  const psar = new DataView(head.buffer).getUint32(0x24, true);
  const tag = String.fromCharCode(...(await bytes(file, psar, 16)));
  if (tag.startsWith('PSTITLEIMG')) throw new Error('PBP multi-disc');
  if (!tag.startsWith('PSISOIMG0000')) throw new Error('PBP encrypted');
  const toc = await bytes(file, psar + 0x800, 0x400);
  let sectors = 0;
  for (let p = 0; p + 10 <= toc.length; p += 10) {
    if (toc[p + 2] === 0xa2) sectors = (bcd(toc[p + 7]) * 60 + bcd(toc[p + 8])) * 75 + bcd(toc[p + 9]) - 150;
  }
  if (sectors <= 0) throw new Error('PBP encrypted');
  const total = sectors * 2352;
  const blocks = Math.ceil(total / BLOCK);
  const index = await bytes(file, psar + 0x4000, blocks * 32);
  const dv = new DataView(index.buffer);
  for (let i = 0; i < blocks; i++) {
    const off = dv.getUint32(i * 32, true), len = dv.getUint16(i * 32 + 4, true);
    const raw = await bytes(file, psar + 0x100000 + off, len);
    let data;
    try {
      data = len === BLOCK ? raw : await inflate(raw);
    } catch {
      throw new Error('PBP encrypted');
    }
    const want = Math.min(BLOCK, total - i * BLOCK);
    if (data.length < want) throw new Error('PBP encrypted');
    emit(data.length === want ? data : data.slice(0, want));
    if (i % 64 === 0) progress(i / blocks);
  }
  progress(1);
}
