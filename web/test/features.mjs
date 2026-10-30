// Long showcases stay manual and lazy, including under reduced motion. Run with the media clips available.
// node web/test/features.mjs http://127.0.0.1:8284 [screenshots-dir]
import puppeteer from './browser.mjs';
import fs from 'node:fs';
const [url,shots]=process.argv.slice(2);
const profile=fs.mkdtempSync(new URL('../../build/features-test-',import.meta.url).pathname);
const browser=await puppeteer.launch({userDataDir:profile,executablePath:process.env.CHROMIUM||'/snap/bin/chromium',headless:'new',args:['--no-sandbox','--disable-gpu']});
try {
 for(const reduced of [false,true]) {
  const page=await browser.newPage();await page.setViewport({width:1280,height:400});
  if(reduced) await page.emulateMediaFeatures([{name:'prefers-reduced-motion',value:'reduce'}]);
  const requests=[];page.on('request',r=>{if(/(?:maps|digimon)-tour\.mp4/.test(r.url())) requests.push(r.url());});
  await page.goto(url,{waitUntil:'networkidle0'});await page.waitForSelector('#feature-maps-tour video');
  if(requests.length) throw Error('A long clip was fetched before its card was near the viewport');
  await page.setViewport({width:1280,height:900});
  for(const id of ['maps-tour','digimon']) {
   const video=await page.$(`#feature-${id} video`);
   const initial=await video.evaluate(v=>({controls:v.controls,loop:v.loop,paused:v.paused,autoplay:v.autoplay,muted:v.muted}));
   if(!initial.controls||initial.loop||!initial.paused||initial.autoplay||!initial.muted) throw Error(JSON.stringify(initial));
   await video.evaluate(v=>v.scrollIntoView({block:'center'}));
   await page.waitForFunction(id=>document.querySelector(`#feature-${id} video`).readyState>=1,{},id);
   if(!(await video.evaluate(v=>v.paused))) throw Error('Long video autoplayed');
   await video.evaluate(v=>v.play());await page.waitForFunction(id=>document.querySelector(`#feature-${id} video`).currentTime>.25,{},id);
   await video.evaluate(v=>{v.currentTime=v.duration-.25;});
   await page.waitForFunction(id=>document.querySelector(`#feature-${id} video`).ended,{},id);
   await video.evaluate(v=>{v.currentTime=.5;});
   await page.waitForFunction(id=>document.querySelector(`#feature-${id} video`).readyState>=2,{},id);
   if(!reduced&&shots){await video.hover();fs.mkdirSync(shots,{recursive:true});await (await page.$(`#feature-${id}`)).screenshot({path:`${shots}/video-${id==='digimon'?'digimon':'mapas'}-card.png`});}
   await page.evaluate(()=>scrollTo(0,0));await new Promise(r=>setTimeout(r,100));
  }
  if(reduced&&!(await page.$('#feature-story img'))) throw Error('Short loops should use their poster under reduced motion');
  console.log(`ok: long videos, ${reduced?'reduced':'normal'} motion`);await page.close();
 }
}finally{await browser.close();fs.rmSync(profile,{recursive:true,force:true});}
