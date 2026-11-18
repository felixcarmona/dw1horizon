// CHD v5 CD reader. Format/codec rules mirror tools/patcher/discformats.py.
// CHD specification: https://github.com/mamedev/mame/blob/master/src/lib/util/chd.cpp
// Input is a Blob (only slices are read); emit may be async. Memory: map + a few hunks.
const fail = (key = 'why.chdInvalid') => { throw new Error(key); };
const check = (signal) => { if (signal?.aborted) throw new DOMException('Cancelled', 'AbortError'); };
const text = (b) => String.fromCharCode(...b);
function uint(b, at, n) {
  let v = 0;
  for (let i = 0; i < n; i++) v = v * 256 + b[at + i];
  if (!Number.isSafeInteger(v)) fail();
  return v;
}
const CRC = Uint16Array.from({length:256}, (_, i) => {
  let v = i << 8;
  for (let j=0;j<8;j++) v = (v << 1) ^ (v & 32768 ? 0x1021 : 0);
  return v & 65535;
});
function crc16(b) {
  let crc = 65535;
  for (let i=0;i<b.length;i++) crc = ((crc << 8) ^ CRC[(crc >>> 8) ^ b[i]]) & 65535;
  return crc;
}
class Bits {
  constructor(b) { this.b=b; this.p=0; }
  read(n) {
    if (this.p+n>this.b.length*8) fail();
    let v=0;
    while (n--) { v=v*2+((this.b[this.p>>3] >> (7-(this.p&7)))&1); this.p++; }
    return v;
  }
}
function tree(bits) {
  const lengths=[];
  while (lengths.length<16) {
    let n=bits.read(4), repeat=1;
    if (n===1) { n=bits.read(4); if (n!==1) repeat=bits.read(4)+3; }
    if (n>8 || lengths.length+repeat>16) fail();
    while (repeat--) lengths.push(n);
  }
  const starts=new Uint16Array(9), codes=Array.from({length:9},()=>new Map());
  let start=0;
  for (let n=8;n;n--) {
    starts[n]=start;
    const total=start+lengths.filter(x=>x===n).length;
    if (n!==1 && total&1) fail();
    start=total>>1;
  }
  lengths.forEach((n,s)=> { if(n) { if(starts[n]>=2**n) fail(); codes[n].set(starts[n]++,s); } });
  return () => {
    let v=0;
    for(let n=1;n<=8;n++) { v=v*2+bits.read(1); if(codes[n].has(v)) return codes[n].get(v); }
    fail();
  };
}

// LZMA1 raw range decoder: fixed lc=3, lp=0, pb=2, fresh state per hunk.
// Output doubles as the dictionary; CHD resets it at every hunk.
// SDK level 6 reduceSize, rounded to the next encodable 2*2^n or 3*2^n dictionary.
function dictionary(size) {
  size=Math.max(4096,Math.min(size,1<<26));
  for(let n=11;n<26;n++) for(const v of [2*2**n,3*2**n]) if(v>=size) return v;
}
function lzma(input, size) {
  let at=0, range=0xffffffff, code=0;
  const byte=()=> { if(at>=input.length) fail(); return input[at++]; };
  if(byte()!==0) fail();
  for(let i=0;i<4;i++) code=(code*256+byte())>>>0;
  const probs=n=>new Uint16Array(n).fill(1024);
  const match=probs(12*16), rep=probs(12), g0=probs(12), g1=probs(12), g2=probs(12), short=probs(12*16);
  const literal=probs(8*0x300), slots=probs(4*64), special=probs(114), align=probs(16);
  const lengths=()=>({choice:probs(2),low:probs(16*8),mid:probs(16*8),high:probs(256)});
  const len=lengths(), rlen=lengths();
  function norm() { if(range<0x1000000) { range=(range*256)>>>0; code=(code*256+byte())>>>0; } }
  function bit(p,i) {
    const bound=(range>>>11)*p[i];
    let v;
    if(code<bound) { range=bound; p[i]+=(2048-p[i])>>>5; v=0; }
    else { range=(range-bound)>>>0; code=(code-bound)>>>0; p[i]-=p[i]>>>5; v=1; }
    norm(); return v;
  }
  function tree(p,base,n) { let v=1; for(let i=0;i<n;i++) v=v*2+bit(p,base+v); return v-2**n; }
  function reverse(p,base,n) { let v=1,out=0; for(let i=0;i<n;i++) { const b=bit(p,base+v); v=v*2+b; out+=b*2**i; } return out; }
  function length(p,pos) {
    if(!bit(p.choice,0)) return tree(p.low,pos*8,3)+2;
    if(!bit(p.choice,1)) return tree(p.mid,pos*8,3)+10;
    return tree(p.high,0,8)+18;
  }
  const out=new Uint8Array(size), dict=dictionary(size);
  let pos=0,state=0,r0=0,r1=0,r2=0,r3=0;
  while(pos<size) {
    const ps=pos&3;
    if(!bit(match,state*16+ps)) {
      const base=(pos ? out[pos-1]>>5 : 0)*0x300;
      let sym=1;
      if(state>=7) {
        if(r0>=pos) fail();
        let m=out[pos-r0-1];
        do { const mb=(m>>7)&1; m=(m<<1)&255; const b=bit(literal,base+((1+mb)<<8)+sym); sym=sym*2+b; if(mb!==b) break; } while(sym<256);
      }
      while(sym<256) sym=sym*2+bit(literal,base+sym);
      out[pos++]=sym-256;
      state=state<4?0:state<10?state-3:state-6;
      continue;
    }
    let n;
    if(bit(rep,state)) {
      if(!bit(g0,state)) {
        if(!bit(short,state*16+ps)) {
          if(r0>=pos || r0>=dict) fail();
          state=state<7?9:11; out[pos]=out[pos-r0-1]; pos++; continue;
        }
      } else {
        let distance;
        if(!bit(g1,state)) distance=r1;
        else { if(!bit(g2,state)) distance=r2; else { distance=r3; r3=r2; } r2=r1; }
        r1=r0; r0=distance;
      }
      n=length(rlen,ps); state=state<7?8:11;
    } else {
      r3=r2; r2=r1; r1=r0;
      n=length(len,ps); state=state<7?7:10;
      const slot=tree(slots,Math.min(n-2,3)*64,6);
      if(slot<4) r0=slot;
      else {
        const nb=(slot>>1)-1;
        r0=(2+(slot&1))*2**nb;
        if(slot<14) r0+=reverse(special,r0-slot-1,nb);
        else {
          let v=0;
          for(let i=0;i<nb-4;i++) {
            range>>>=1;
            let b=0;
            if(code>=range) { code=(code-range)>>>0; b=1; }
            v=v*2+b; norm();
          }
          r0+=v*16+reverse(align,0,4);
        }
      }
    }
    if(r0>=pos || r0>=dict || n>size-pos) fail();
    for(let end=pos+n;pos<end;pos++) out[pos]=out[pos-r0-1];
  }
  return out;
}
async function inflate(data,size,codec) {
  if(codec==='lzma') return lzma(data,size);
  if(codec==='cdfl' || codec==='flac') fail('why.chdFlac');
  if(codec!=='zlib') fail('why.chd');
  const ds=new DecompressionStream('deflate-raw');
  const writer=ds.writable.getWriter();
  writer.write(data).catch(()=>{}); writer.close().catch(()=>{});
  const reader=ds.readable.getReader(), out=new Uint8Array(size);
  let pos=0;
  try {
    for(;;) { const {value,done}=await reader.read(); if(done) break; if(pos+value.length>size) { await reader.cancel(); fail(); } out.set(value,pos); pos+=value.length; }
  } catch { fail(); }
  if(pos!==size) fail();
  return out;
}
const F=new Uint8Array(256), B=new Uint8Array(256);
for(let i=0;i<256;i++) { F[i]=(i<<1)^(i&128?0x11d:0); B[i^F[i]]=i; }
function ecc(s) {
  const saved=s.slice(12,16);
  if(s[15]===2) s.fill(0,12,16);
  for(const [majors,minors,mult,inc,dest] of [[86,24,2,86,2076],[52,43,86,88,2248]]) {
    const size=majors*minors;
    for(let major=0;major<majors;major++) {
      let index=(major>>1)*mult+(major&1), a=0,b=0;
      for(let minor=0;minor<minors;minor++) { const v=s[12+index]; index+=inc; if(index>=size) index-=size; a=F[a^v]; b^=v; }
      a=B[F[a]^b]; s[dest+major]=a; s[dest+major+majors]=a^b;
    }
  }
  s.set(saved,12);
}
async function decompress(data,size,codec) {
  if(codec!=='cdzl' && codec!=='cdlz') return inflate(data,size,codec);
  const frames=size/2448, bitmap=Math.ceil(frames/8), header=bitmap+(size<65536?2:3);
  const length=uint(data,bitmap,header-bitmap);
  if(!length || header+length>=data.length) fail();
  const sectors=await inflate(data.subarray(header,header+length),frames*2352,codec==='cdzl'?'zlib':'lzma');
  const sub=await inflate(data.subarray(header+length),frames*96,'zlib'), out=new Uint8Array(size);
  for(let i=0;i<frames;i++) {
    const s=sectors.subarray(i*2352,(i+1)*2352);
    if(data[i>>3]&(1<<(i&7))) { s.fill(255,1,11); s[0]=s[11]=0; ecc(s); }
    out.set(s,i*2448); out.set(sub.subarray(i*96,(i+1)*96),i*2448+2352);
  }
  return out;
}

// Emits fresh raw BIN chunks in track order. Awaiting emit provides output backpressure.
// AbortSignal is checked between reads/hunks; CRC16 verification is on by default.
// CHD omits the LZMA end marker: each hunk supplies its exact decoded length.
export async function decodeChd(file, emit, progress=()=>{}, {signal, verifyCrc=true}={}) {
  check(signal);
  async function read(at,n) {
    check(signal);
    if(!Number.isSafeInteger(at) || !Number.isSafeInteger(n) || at<0 || n<0 || at+n>file.size) fail();
    const b=new Uint8Array(await file.slice(at,at+n).arrayBuffer());
    if(b.length!==n) fail();
    return b;
  }
  let head=await read(0,16);
  if(text(head.subarray(0,8))!=='MComprHD') fail();
  if(uint(head,12,4)!==5) fail('why.chdVersion');
  if(uint(head,8,4)!==124) fail();
  head=await read(0,124);
  const codecs=Array.from({length:4},(_,i)=>text(head.subarray(16+i*4,20+i*4)));
  const compressed=codecs.some(x=>x!=='\0\0\0\0');
  if(compressed && codecs[0]==='\0\0\0\0') fail();
  const logical=uint(head,32,8), mapAt=uint(head,40,8), hunk=uint(head,56,4);
  let meta=uint(head,48,8);
  if(head.subarray(104).some(x=>x)) fail('why.chdParent');
  if(uint(head,60,4)!==2448 || !hunk || hunk%2448 || hunk>16*1024**2) fail('why.chd');
  if(!logical || logical%2448 || logical>1024**3 || !mapAt) fail();
  const tracks=[], visited=new Set(); let old;
  while(meta) {
    if(visited.has(meta) || visited.size>=1024) fail(); visited.add(meta);
    const mh=await read(meta,16), tag=text(mh.subarray(0,4)), length=uint(mh,5,3);
    if(length>65536) fail();
    const data=await read(meta+16,length); meta=uint(mh,8,8);
    if(tag==='CHSE') { if(text(data).replace(/\0+$/,'')!=='SESSION:1') fail('why.chd'); continue; }
    if(tag==='CHGT' || tag==='CHGD') fail('why.chd');
    if(tag==='CHCD') { old=data; continue; }
    if(tag!=='CHTR' && tag!=='CHT2') continue;
    const f=Object.fromEntries(text(data).replace(/\0+$/,'').trim().split(/\s+/).map(x=>x.split(':')));
    const frames=Number(f.FRAMES), kind=f.TYPE, validSub=x=>['NONE','RW','RW_RAW'].includes(x);
    if(Number(f.TRACK)!==tracks.length+1 || !Number.isInteger(frames) || frames<=0 || !['MODE1_RAW','MODE2_RAW','AUDIO'].includes(kind) || !validSub(f.SUBTYPE) || Number(f.PAD||0)!==0) fail('why.chd');
    if(tag==='CHT2') {
      const pg=Number(f.PREGAP), post=Number(f.POSTGAP);
      if(!Number.isInteger(pg) || pg<0 || !Number.isInteger(post) || post<0 || !f.PGTYPE || (f.PGTYPE.startsWith('V') && (f.PGTYPE.slice(1)!==kind || pg>frames)) || !validSub(f.PGSUB)) fail('why.chd');
    }
    tracks.push([kind,frames,(4-frames%4)%4]);
  }
  if(!tracks.length && old) {
    if(old.length!==2380) fail();
    const dv=new DataView(old.buffer,old.byteOffset,old.byteLength), little=dv.getUint32(0,true)<=99;
    const word=i=>dv.getUint32(i*4,little), count=word(0);
    if(count<1 || count>99) fail();
    for(let i=0;i<count;i++) {
      const at=1+i*6, kind={1:'MODE1_RAW',6:'MODE2_RAW',7:'AUDIO'}[word(at)], frames=word(at+4), pad=word(at+5);
      if(!kind || word(at+2)!==2352 || !frames || pad!==(4-frames%4)%4) fail('why.chd');
      tracks.push([kind,frames,pad]);
    }
  }
  if(!tracks.length || tracks.length>99 || tracks.reduce((n,t)=>n+t[1]+t[2],0)*2448!==logical) fail('why.chd');
  const count=Math.ceil(logical/hunk), entries=[];
  if(!compressed) {
    const raw=await read(mapAt,count*4);
    for(let i=0;i<count;i++) entries.push([4,hunk,uint(raw,i*4,4)*hunk,null]);
  } else {
    const mh=await read(mapAt,16), size=uint(mh,0,4);
    if(size>count*16+256 || mh[12]>24 || mh[13]>32 || mh[14]>48) fail();
    const bits=new Bits(await read(mapAt+16,size)), decode=tree(bits), types=[];
    let last=0;
    while(types.length<count) {
      check(signal);
      let kind=decode(), repeat=1;
      if(kind===7) { kind=last; repeat=3+decode(); }
      else if(kind===8) { kind=last; repeat=19+decode()*16+decode(); }
      else last=kind;
      if(types.length+repeat>count) fail();
      while(repeat--) types.push(kind);
    }
    let offset=uint(mh,4,6), lastSelf=0;
    const raw=new Uint8Array(count*12);
    for(let i=0;i<count;i++) {
      let kind=types[i], length=0, crc=0, where=offset;
      if(kind<4) { length=bits.read(mh[12]); crc=bits.read(16); if(!length || length>hunk) fail(); offset+=length; }
      else if(kind===4) { length=hunk; crc=bits.read(16); offset+=length; }
      else if(kind===5) lastSelf=where=bits.read(mh[13]);
      else if(kind===9 || kind===10) { if(kind===10) lastSelf++; kind=5; where=lastSelf; }
      else if([6,11,12,13].includes(kind)) fail('why.chdParent');
      else fail();
      if(where>=2**48 || (kind===5 && where>=count)) fail();
      entries.push([kind,length,where,crc]);
      let p=i*12; raw[p++]=kind;
      for(const [v,n] of [[length,3],[where,6],[crc,2]]) for(let j=n-1;j>=0;j--) raw[p++]=Math.floor(v/2**(j*8))&255;
    }
    if(crc16(raw)!==uint(mh,10,2)) fail();
  }
  let cached=-1, data;
  async function readHunk(index) {
    const seen=new Set();
    while(entries[index][0]===5) { check(signal); if(seen.has(index)) fail(); seen.add(index); index=entries[index][2]; }
    if(index===cached) return data;
    const [kind,length,where,crc]=entries[index];
    data=crc===null && where===0 ? new Uint8Array(hunk) : await read(where,length);
    if(kind<4) data=await decompress(data,hunk,codecs[kind]);
    if(verifyCrc && crc!==null && crc16(data)!==crc) fail();
    cached=index; return data;
  }
  let frame=0,done=0;
  const total=tracks.reduce((n,t)=>n+t[1],0);
  for(const [kind,frames,pad] of tracks) {
    let remaining=frames;
    while(remaining) {
      check(signal);
      const index=Math.floor(frame*2448/hunk), offset=frame*2448%hunk, data=await readHunk(index);
      const take=Math.min(remaining,(hunk-offset)/2448), raw=new Uint8Array(take*2352);
      for(let i=0;i<take;i++) raw.set(data.subarray(offset+i*2448,offset+i*2448+2352),i*2352);
      if(kind==='AUDIO') for(let i=0;i<raw.length;i+=2) { const b=raw[i]; raw[i]=raw[i+1]; raw[i+1]=b; }
      await emit(raw); remaining-=take; frame+=take; done+=take;
      if(index%64===0 || done===total) progress(done/total);
    }
    frame+=pad;
  }
  check(signal);
}
