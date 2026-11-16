// Streaming Node proof/benchmark: no whole-input or whole-output buffers.
// node web/test/chd-bench.mjs INPUT.chd [OUTPUT.bin]
import { openAsBlob } from 'node:fs';
import { open } from 'node:fs/promises';
import { createHash } from 'node:crypto';
import { decodeChd } from '../js/chd.js';
const [src,dst]=process.argv.slice(2);
const file=await openAsBlob(src), out=dst?await open(dst,'w'):null, hash=createHash('sha1');
let bytes=0;
const start=performance.now();
try {
  await decodeChd(file,async b=>{ hash.update(b); bytes+=b.length; if(out) await out.write(b); });
  const seconds=(performance.now()-start)/1000;
  console.log(JSON.stringify({src,bytes,sha1:hash.digest('hex'),seconds,MiBs:bytes/1048576/seconds,peakRSSMiB:process.resourceUsage().maxRSS/1024}));
} finally { await out?.close(); }
