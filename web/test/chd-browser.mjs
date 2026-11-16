// Tiny generated CHDs through the production worker, in Chromium. No engine build/disc required.
import assert from 'node:assert/strict';
import { spawn, execFileSync } from 'node:child_process';
import { mkdtempSync, rmSync, readFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { createHash } from 'node:crypto';
import puppeteer from './browser.mjs';
const dir=mkdtempSync(path.join(tmpdir(),'chd-browser-'));
const port=process.env.PORT || '8821';
let browser, server;
try {
  execFileSync(process.execPath,['web/test/chd.mjs'],{env:{...process.env,CHD_FIXTURE_DIR:dir},stdio:'pipe'});
  const expected=createHash('sha1').update(readFileSync(path.join(dir,'real.bin'))).digest('hex');
  server=spawn('python3',['-m','http.server','-b','127.0.0.1','-d','web',port],{stdio:'ignore'});
  await new Promise(r=>setTimeout(r,700));
  browser=await puppeteer.launch({executablePath:process.env.CHROMIUM || '/snap/bin/chromium',headless:true,args:['--no-sandbox','--disable-gpu']});
  const page=await browser.newPage();
  await page.goto(`http://127.0.0.1:${port}/test/`);
  await page.evaluate(async()=> {
    const input=document.createElement('input'); input.type='file'; input.id='chd'; document.body.append(input);
    const {conversionSession}=await import('/js/convert-storage.js');
    window.outputDir=await conversionSession();
    window.convert=(file,outputDir,cancel=false,kind='chd')=>new Promise((resolve,reject)=> {
      const worker=new Worker('/js/convert-worker.js',{type:'module'});
      worker.onerror=e=>{worker.terminate();reject(new Error(e.message));};
      worker.onmessage=({data})=> {
        if(data.progress!=null) { if(cancel) worker.postMessage({cancel:true}); return; }
        worker.terminate(); resolve(data);
      };
      worker.postMessage({kind,file,outputDir});
    });
  });
  const input=await page.$('#chd');
  for(const codec of ['cdzl','cdlz']) {
    await input.uploadFile(path.join(dir,`real-${codec}.chd`));
    for(const opfs of [false,true]) {
      const result=await page.evaluate(async(opfs)=> {
        const file=document.querySelector('#chd').files[0];
        const r=await window.convert(file,opfs?window.outputDir:null);
        if(r.error) return r;
        const bytes=await r.file.arrayBuffer();
        const hash=Array.from(new Uint8Array(await crypto.subtle.digest('SHA-1',bytes)),b=>b.toString(16).padStart(2,'0')).join('');
        return {hash,name:r.file.name};
      },opfs);
      assert.equal(result.hash,expected,JSON.stringify(result));
      assert.equal(result.name,`real-${codec}.bin`);
      console.log('ok browser',codec,opfs?'OPFS':'Blob');
    }
  }
  for (const ext of ['ecm','pbp']) {
    await input.uploadFile(path.join(dir,'real.'+ext));
    const result=await page.evaluate(async ext=> {
      const file=document.querySelector('#chd').files[0];
      const r=await window.convert(file,null,false,ext);
      if(r.error) return r.error;
      return Array.from(new Uint8Array(await crypto.subtle.digest('SHA-1',await r.file.arrayBuffer())),b=>b.toString(16).padStart(2,'0')).join('');
    },ext);
    assert.equal(result,expected); console.log('ok browser regression',ext);
  }
  await input.uploadFile(path.join(dir,'real-cdlz.chd'));
  const errors=await page.evaluate(async()=> {
    const file=document.querySelector('#chd').files[0];
    const bad=new Uint8Array(await file.arrayBuffer()); bad.set(new TextEncoder().encode('cdfl'),16);
    const before=await Array.fromAsync(window.outputDir.keys());
    const flac=await window.convert(new File([bad],'flac.chd'),window.outputDir);
    const truncated=await window.convert(file.slice(0,file.size-1),window.outputDir);
    const cancelled=await window.convert(file,window.outputDir,true);
    const after=await Array.fromAsync(window.outputDir.keys());
    return {flac:flac.error,truncated:truncated.error,cancelled:cancelled.error,before:before.length,after:after.length};
  });
  assert.equal(errors.flac,'why.chdFlac');
  assert.equal(errors.truncated,'why.chdInvalid');
  assert.equal(errors.cancelled,'Cancelled');
  assert.equal(errors.after,errors.before);
  console.log('ok browser errors, cancel and partial-output cleanup');
  // Stale-session cleanup must leave the current page's locked output alone.
  const cleanup=await page.evaluate(async()=> {
    const root=await (await navigator.storage.getDirectory()).getDirectoryHandle('horizon-conversions');
    await root.getDirectoryHandle('stale',{create:true});
    return (await Array.fromAsync(root.keys())).length;
  });
  const other=await browser.newPage(); await other.goto(`http://127.0.0.1:${port}/test/`);
  const kept=await other.evaluate(async()=> {
    const {conversionSession}=await import('/js/convert-storage.js'); await conversionSession();
    const root=await (await navigator.storage.getDirectory()).getDirectoryHandle('horizon-conversions');
    return Array.fromAsync(root.keys());
  });
  assert(!kept.includes('stale')); assert.equal(kept.length,cleanup);
  console.log('ok browser session cleanup and active-tab protection');
  if (process.env.CHD_REAL) {
    const app=await browser.newPage();
    app.on('pageerror',e=>console.error('page error:',e.message));
    await app.goto(`http://127.0.0.1:${port}/`,{waitUntil:'networkidle0'});
    await app.waitForSelector('.slot');
    const start=performance.now();
    await (await app.$('#add-input')).uploadFile(path.resolve(process.env.CHD_REAL));
    await app.waitForFunction(()=>document.querySelector('.slot[data-game="us"]')?.dataset.state==='ready', {timeout:180000});
    assert(await app.$$eval('#sums-body .got[data-match="true"]',els=>els.some(e=>e.textContent==='5611645da66183e30d11fb6c11a2784ff47e1fdb')));
    console.log('ok real USA CHD accepted by page with expected SHA-1:',((performance.now()-start)/1000).toFixed(2),'s (decode + validation)');
  }
} finally { await browser?.close(); server?.kill(); rmSync(dir,{recursive:true,force:true}); }
