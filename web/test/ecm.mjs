// web/test (not deployed): js/ecm.js in Node.
// node ecm.mjs IMAGE.ecm IMAGE.bin [IMAGE2.ecm IMAGE2.bin ...]: each .ecm (made from the .bin with any ECM encoder,
// e.g. `ecm-compress e IMAGE.bin IMAGE.ecm`) decoded and its SHA-1 compared with the .bin's; then the first .ecm
// damaged four ways (bad magic, cut in the middle, cut before its last bytes, one byte flipped in the middle) must
// throw 'not ECM', 'ECM file cut short', 'ECM file cut short', 'ECM checksum'. Prints times and MB/s.
import fs from 'node:fs';
import crypto from 'node:crypto';
import { decodeEcm } from '../js/ecm.js';

const args = process.argv.slice(2);
if (args.length < 2 || args.length % 2) {
  console.error('usage: node ecm.mjs IMAGE.ecm IMAGE.bin [...]');
  process.exit(2);
}

async function decode(blob) {
  const h = crypto.createHash('sha1');
  let n = 0;
  const t = performance.now();
  await decodeEcm(blob, (b) => { h.update(b); n += b.length; }, () => {});
  return { sha1: h.digest('hex'), size: n, s: (performance.now() - t) / 1000 };
}

async function sha1(path) {
  const h = crypto.createHash('sha1');
  for await (const b of fs.createReadStream(path, { highWaterMark: 8 << 20 })) h.update(b);
  return h.digest('hex');
}

let bad = 0;
for (let i = 0; i < args.length; i += 2) {
  const [ecm, bin] = [args[i], args[i + 1]];
  const [want, got] = await Promise.all([sha1(bin), decode(await fs.openAsBlob(ecm))]);
  const ok = got.sha1 === want && got.size === fs.statSync(bin).size;
  if (!ok) bad++;
  console.log(`${ok ? 'ok  ' : 'FAIL'} ${ecm}: ${got.sha1} (${want} expected), ${got.size} bytes, ` +
              `${got.s.toFixed(2)} s, ${(got.size / 1048576 / got.s).toFixed(0)} MB/s`);
}

const blob = await fs.openAsBlob(args[0]);
const mid = Math.floor(blob.size / 2);
const flipped = new Uint8Array(await blob.slice(mid, mid + 1).arrayBuffer());
flipped[0] ^= 0x10;
for (const [name, damaged, want] of [
  ['bad magic', new Blob([new Uint8Array([0x45, 0x43, 0x58, 0]), blob.slice(4)]), 'not ECM'],
  ['cut in the middle', blob.slice(0, mid), 'ECM file cut short'],
  ['cut before the end', blob.slice(0, blob.size - 2), 'ECM file cut short'],
  ['a byte flipped', new Blob([blob.slice(0, mid), flipped, blob.slice(mid + 1)]), 'ECM checksum'],
]) {
  let got = 'no error';
  try { await decode(damaged); } catch (e) { got = e.message; }
  if (got !== want) bad++;
  console.log(`${got === want ? 'ok  ' : 'FAIL'} ${name}: ${JSON.stringify(got)}`);
}
process.exit(bad ? 1 : 0);
