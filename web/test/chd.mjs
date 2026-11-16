// Generated fixtures only; no disc data. Python writer supplies independent codecs/ECC.
import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import { mkdtempSync, readFileSync, rmSync, writeFileSync, existsSync } from 'node:fs';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { decodeChd } from '../js/chd.js';
import { decodePbp } from '../js/pbp.js';
import { decodeEcm } from '../js/ecm.js';
import { inspect } from '../js/disc.js';
const dir=mkdtempSync(path.join(tmpdir(),'web-chd-'));
try {
  execFileSync('python3',['-c',`
from tools.test_chd import *
p=Path(sys.argv[1])
tracks=[('MODE1_RAW',b''.join(sector(i) for i in range(9)),0),('MODE2_RAW',b''.join(sector(i,2) for i in range(7)),2),('AUDIO',bytes(range(256))*27+bytes(2352*3-256*27),1)]
(p/'expected.bin').write_bytes(b''.join(t[1] for t in tracks))
for codec in (b'cdzl',b'cdlz',b'zlib',b'lzma',b'none'):
 (p/(codec.decode()+'.chd')).write_bytes(chd(tracks,codec=codec))
for name,kw in [('uncompressed',dict(compressed=False)),('old',dict(metadata=b'CHCD')),('chtr',dict(metadata=b'CHTR')),('large',dict(hunk_frames=32))]:
 (p/(name+'.chd')).write_bytes(chd(tracks,**kw))
for n in (8,28):
 for refs in (True,False):
  raw=sector(0)*4*n
  name=f'rle-{n}-{refs}'
  (p/(name+'.bin')).write_bytes(raw)
  (p/(name+'.chd')).write_bytes(chd([('MODE1_RAW',raw,0)],references=refs,rle=True))
raw=sector(0)*4+sector(1)*4+sector(0)*8+sector(1)*4
for name,kw in [('self',dict(self_codes=True)),('cycle',dict(cycle=True))]:
 (p/(name+'.bin')).write_bytes(raw)
 (p/(name+'.chd')).write_bytes(chd([('MODE1_RAW',raw,0)],**kw))
raw=b''.join(sector(i) for i in range(128))
# Unflagged Form 2 bytes (including unconventional EDC) must survive unchanged.
form2=bytearray(iso.form2(12,b'\\x01\\0\\x28\\0'*2+bytes(2328)))
form2[-4:]=b'EDC!'
(p/'form2.bin').write_bytes(form2*5)
(p/'form2.chd').write_bytes(chd([('MODE2_RAW',bytes(form2)*5,0)]))
zero=chd([('MODE1_RAW',bytes(2352*4),0)],compressed=False)
map_at=int.from_bytes(zero[40:48],'big'); zero[map_at:map_at+4]=bytes(4)
(p/'sparse.chd').write_bytes(zero); (p/'sparse.bin').write_bytes(bytes(2352*4))

(p/'real.bin').write_bytes(raw)
from tools.test_desktop_patcher import pbp
(p/'real.pbp').write_bytes(pbp(raw))
n=len(raw)-1; record=bytearray([(n&31)<<2]); n >>= 5
while n:
 record[-1] |= 128; record.append(n&127); n >>= 7
(p/'real.ecm').write_bytes(b'ECM\\0'+record+raw+bytes.fromhex('fcffffff3f')+struct.pack('<I',iso.edc(raw)))
(p/'real.cue').write_text('FILE "real.bin" BINARY\\n TRACK 01 MODE1/2352\\n INDEX 01 00:00:00\\n')
`,dir],{cwd:path.resolve(import.meta.dirname,'../..')});
  async function decode(b,options) {
    const parts=[], progress=[];
    await decodeChd(new Blob([b]),x=>parts.push(Buffer.from(x)),x=>progress.push(x),options);
    assert.equal(progress.at(-1),1);
    return Buffer.concat(parts);
  }
  const expected=readFileSync(path.join(dir,'expected.bin'));
  for(const name of ['cdzl','cdlz','zlib','lzma','none','uncompressed','old','chtr','large','self','form2','sparse',... [8,28].flatMap(n=>['True','False'].map(x=>`rle-${n}-${x}`))]) {
    const want=existsSync(path.join(dir,name+'.bin'))?readFileSync(path.join(dir,name+'.bin')):expected;
    assert.deepEqual(await decode(readFileSync(path.join(dir,name+'.chd'))),want,name);
    console.log('ok',name);
  }
  assert.deepEqual(await inspect(new File([readFileSync(path.join(dir,'cdlz.chd'))],'renamed.bin')), {kind:'chd',format:'chd'});
  for (const [ext,decoder] of [['pbp',decodePbp],['ecm',decodeEcm]]) {
    const parts=[];
    await decoder(new Blob([readFileSync(path.join(dir,'real.'+ext))]),b=>parts.push(Buffer.from(b)));
    assert.deepEqual(Buffer.concat(parts),readFileSync(path.join(dir,'real.bin')));
    console.log('ok regression',ext);
  }
  const good=readFileSync(path.join(dir,'cdzl.chd'));
  for(const [at,value,key] of [[16,Buffer.from('cdfl'),'why.chdFlac'],[104,Buffer.from([1]),'why.chdParent'],[12,Buffer.from([0,0,0,4]),'why.chdVersion'],[60,Buffer.from([0,0,2,0]),'why.chd']]) {
    const b=Buffer.from(good); value.copy(b,at);
    await assert.rejects(decode(b),{message:key});
  }
  const corrupt=readFileSync(path.join(dir,'none.chd'));
  const mapAt=Number(corrupt.readBigUInt64BE(40));
  corrupt[corrupt.readUIntBE(mapAt+4,6)+100] ^= 1;
  await assert.rejects(decode(corrupt),{message:'why.chdInvalid'});
  assert.notDeepEqual(await decode(corrupt,{verifyCrc:false}),expected);
  await assert.rejects(decode(good.subarray(0,good.length-1)),{message:'why.chdInvalid'});
  await assert.rejects(decode(readFileSync(path.join(dir,'cycle.chd'))),{message:'why.chdInvalid'});
  const stop=new AbortController(); stop.abort();
  await assert.rejects(decode(good,{signal:stop.signal}),{name:'AbortError'});
  const mid=new AbortController(); let emitted=0;
  await assert.rejects(decodeChd(new Blob([good]),()=>{emitted++;mid.abort();},()=>{},{signal:mid.signal}),{name:'AbortError'});
  assert.equal(emitted,1);
  // An absent executable is the only reason to skip chdman integration.
  if(existsSync('/usr/bin/chdman')) for(const codec of ['cdzl','cdlz']) {
    const out=path.join(dir,'real-'+codec+'.chd');
    execFileSync('/usr/bin/chdman',['createcd','-i',path.join(dir,'real.cue'),'-o',out,'-c',codec],{stdio:'pipe'});
    assert.deepEqual(await decode(readFileSync(out)),readFileSync(path.join(dir,'real.bin')));
    console.log('ok chdman',codec);
  }
  console.log('CHD errors, cancellation and roundtrips passed');
  if(process.env.CHD_FIXTURE_DIR) {
    const dest=process.env.CHD_FIXTURE_DIR;
    for(const name of ['real-cdzl.chd','real-cdlz.chd','real.bin','real.pbp','real.ecm']) writeFileSync(path.join(dest,name),readFileSync(path.join(dir,name)));
  }
} finally { rmSync(dir,{recursive:true,force:true}); }
