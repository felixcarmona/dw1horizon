// Local review helper: npm install --prefix build/wiki-browser puppeteer-core@25.16.0.
import {createRequire} from 'node:module';
const puppeteer = (await import(createRequire(import.meta.url).resolve('../../build/wiki-browser/node_modules/puppeteer-core'))).default;
import {spawn} from 'node:child_process';
import {mkdir, writeFile} from 'node:fs/promises';
import assert from 'node:assert/strict';
const port=Number(process.env.WIKI_PREVIEW_PORT || 18744);
const base=`http://127.0.0.1:${port}`;
const server=spawn('python3',['-m','http.server',String(port),'--bind','127.0.0.1','--directory','build/wiki-mockups'],{stdio:'ignore'});
let browser;
try{
  for(let n=0;n<100;n++){
    if(server.exitCode!==null)throw new Error('Preview server exited');
    try{if((await fetch(base+'/snapshot.json')).ok)break;}catch{}
    await new Promise(r=>setTimeout(r,100));
  }
  const snapshot=await fetch(base+'/snapshot.json').then(r=>r.json());
  assert.equal(snapshot.version,'v0.0.7');
  browser=await puppeteer.launch({executablePath:process.env.CHROMIUM || '/usr/bin/chromium-browser',headless:true,args:['--no-sandbox']});
  await mkdir('build/wiki-review',{recursive:true});
  const results=[];
  for(const [label,width,height] of [['phone',390,844],['desktop',1440,1000]]){
    for(const [num,route,name] of [['01','index.html','wiki-home'],['02','digimon.html','agumon'],['03','article.html','android-setup'],['04','search.html?q=Horizon','search']]){
      const page=await browser.newPage();
      await page.setCacheEnabled(false);
      const errors=[],external=[];
      page.on('pageerror',e=>errors.push(e.message));
      page.on('request',r=>{if(!r.url().startsWith(base)&&!r.url().startsWith('data:'))external.push(r.url());});
      await page.setViewport({width,height,deviceScaleFactor:1});
      const response=await page.goto(base+'/'+route,{waitUntil:'networkidle0'});
      assert.equal(response.status(),200);
      await page.evaluate(()=>document.fonts.ready);
      assert.equal(await page.$eval('.wiki-main',()=>document.documentElement.scrollWidth<=innerWidth),true,route+' overflow');
      assert.equal(await page.evaluate(()=>document.fonts.check('500 16px "Plus Jakarta Sans"')),true);
      assert.deepEqual(errors,[]);assert.deepEqual(external,[]);
      if(name==='agumon'){
        assert.equal(await page.$eval('#recruit details',e=>e.open),false);
        await page.click('.route summary');
        assert.match(await page.$eval('.route details p',e=>e.textContent),/Offense ≥ 100/);
        await page.click('.route summary');
      }
      if(name==='search'){
        await page.click('[data-filter="Technique"]');
        const visible=await page.$$eval('.result',es=>es.filter(e=>!e.hidden).length);
        assert.equal(visible,snapshot.digimon.moves.length);
        await page.click('[data-filter="All"]');
      }
      const file=`build/wiki-review/${num}-${name}-${label}.png`;
      await page.screenshot({path:file,fullPage:true});
      results.push({file,width,height:await page.$eval('body',e=>e.scrollHeight),errors,external});
      // Check all local preview links and fragment targets against the target document.
      const links=await page.$$eval('a[href]',es=>es.map(e=>e.href).filter(h=>h.startsWith(location.origin)));
      for(const link of new Set(links)){
        const url=new URL(link);
        const text=await fetch(url).then(r=>{assert.equal(r.status,200,link);return r.text();});
        if(url.hash){
          const target=await browser.newPage();
          try{await target.goto(url.href,{waitUntil:'domcontentloaded'});await target.waitForSelector(url.hash);assert.ok(await target.$(url.hash),link);}finally{await target.close();}
        }
        assert.ok(text.includes('<!doctype html>'));
      }
      if(name==='search'){
        await page.goto(base+'/search.html?q=zz-no-match',{waitUntil:'networkidle0'});
        assert.match(await page.$eval('#results',e=>e.textContent),/No matches/);
      }
      await page.close();
    }
  }
  await writeFile('build/wiki-review/validation.json',JSON.stringify({snapshot:snapshot.commit,results},null,2)+'\n');
  console.log(JSON.stringify(results,null,2));
}finally{
  if(browser)await browser.close();
  server.kill('SIGTERM');
}
