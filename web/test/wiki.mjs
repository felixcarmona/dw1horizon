// node web/test/wiki.mjs SITE [SHOTS]; static pages, every type/language/viewport.
import puppeteer from './browser.mjs';
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import path from 'node:path';
import {spawn} from 'node:child_process';
import {once} from 'node:events';
const [site,shots]=process.argv.slice(2);
const manifest=JSON.parse(await fs.readFile(path.join(site,'wiki/manifest.json'),'utf8'));
const languages=['en','es','pt-br','fr','de','it','ja','ca','zh-hans'];
let browser,server;
try{
  server=spawn('python3',['-u','-c','import http.server\ns=http.server.ThreadingHTTPServer(("127.0.0.1",0),http.server.SimpleHTTPRequestHandler)\nprint(s.server_port,flush=True)\ns.serve_forever()'],{cwd:path.resolve(site),stdio:['ignore','pipe','ignore']});
  const [port]=await once(server.stdout,'data');const root=`http://127.0.0.1:${String(port).trim()}`;
  browser=await puppeteer.launch({executablePath:process.env.CHROMIUM||'/snap/bin/chromium',headless:true,args:['--no-sandbox']});
  const page=await browser.newPage();const errors=[],external=[],missing=[];
  page.on('pageerror',e=>errors.push(e.message));
  page.on('response',r=>{if(r.status()>=400&&r.url().startsWith(root))missing.push(r.url());});
  await page.setRequestInterception(true);
  let offline=false;
  page.on('request',r=>{
    if(!r.url().startsWith(root)&&/^https?:/.test(r.url())){if(page.url().includes('/wiki/'))external.push(r.url());r.abort();}
    else if(offline)r.abort();else r.continue();
  });
  await page.goto(root+'/',{waitUntil:'networkidle0'});
  assert.match(await page.$eval('.data-link',e=>e.getAttribute('href')),/^wiki\//);
  await page.click('.data-link');await page.waitForSelector('.wiki-main');
  const results=[];
  for(const lang of languages){
    const strings=JSON.parse(await fs.readFile(path.join(site,`i18n/${lang}.json`),'utf8'));
    const base=`/wiki/${lang}/${manifest.tag}/`;
    const pages=[['home',''],['digimon-list','digimon/'],['agumon','digimon/3-agumon/'],['tree','evolutions/'],['article','guides/duckstation-android/'],['search','search/?q=Agumon'],['techniques','techniques/'],['technique','techniques/2-spit-fire/'],['recruits','recruits/'],['articles','guides/']];
    for(const [view,width,height] of [['desktop',1440,1000],['phone',390,844]]){
      await page.setViewport({width,height});
      for(const [kind,route] of pages){
        await page.goto(root+base+route,{waitUntil:'load'});await page.waitForSelector('.wiki-main');
        await page.evaluate(()=>document.fonts.ready);
        assert.equal(await page.$eval('html',e=>e.lang),lang);
        assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true,`${lang} ${view} ${kind} overflow`);
        assert.equal(await page.evaluate(()=>document.fonts.check('500 16px "Plus Jakarta Sans"')),true);
        assert.equal(await page.$eval('#lang',e=>e.value),lang);
        assert.ok((await page.$eval('.version',e=>e.textContent)).includes(manifest.tag.slice(1)));
        assert.equal(await page.$$eval('details[open]',es=>es.length),0,'spoilers folded');
        if(kind==='digimon-list'){
          assert.equal(await page.$$eval('.species-card',es=>es.length),manifest.counts.species);
          assert.equal(await page.$$eval('.species-card img',es=>es.every(e=>e.loading==='lazy'&&e.alt.length>0)),true);
          assert.ok(await page.$eval('.species-card img',e=>e.complete&&e.naturalWidth>0));
          await page.click('button[data-level="rookie"]');
          const shown=await page.$$eval('.species-card:not([hidden])',es=>es.map(e=>e.dataset.level));
          assert.ok(shown.length>0&&shown.length<manifest.counts.species);assert.ok(shown.every(l=>l==='rookie'));
          await page.click('button[data-level=""]');
        }
        if(kind==='agumon'||kind==='tree'){
          await page.waitForSelector('.tree-edges g path');
          assert.equal(await page.$$eval('.tree-targets .tree-node',es=>es.length),6);
          await page.$eval('.tree-targets .tree-node',e=>e.scrollIntoView({block:'nearest',inline:'nearest'}));
          await page.click('.tree-targets .tree-node');
          assert.equal(await page.$eval('#wiki-requirements',e=>e.open),true);
          assert.ok(await page.$('.requirement-body a[href$="/digimon/5-greymon/"]'));
          assert.match(await page.$eval('.requirement-body',e=>e.textContent),/100/);
          await page.click('.dialog-close');
          await page.$eval('.tree-viewport',e=>{e.scrollLeft=0;});
        }
        if(kind==='search'){
          await page.waitForSelector('.result');
          assert.ok(await page.$('a.result[href$="/digimon/3-agumon/"]'));
          await page.click('[data-filter="technique"]');
          assert.equal(await page.$$eval('.result',es=>es.every(e=>e.dataset.kind==='technique')),true);
          await page.click('[data-filter="all"]');
          // Once the static index is loaded, queries and filters need no network.
          offline=true;
          await page.$eval('#wiki-query',e=>{e.value='DuckStation';e.dispatchEvent(new Event('input'));});
          assert.equal(await page.$$eval('.result',es=>es.length),2);
          await page.$eval('#wiki-query',e=>{e.value='impossible-wiki-query-123';e.dispatchEvent(new Event('input'));});
          assert.equal(await page.$eval('#search-results',e=>e.textContent),strings['wiki.empty']);
          await page.$eval('#wiki-query',e=>{e.value='Horizon';e.dispatchEvent(new Event('input'));});
          offline=false;
        }
        await page.evaluate(()=>scrollTo({top:0,behavior:'instant'}));
        if(shots&&['en','es'].includes(lang)&&['home','digimon-list','agumon','tree','article','search'].includes(kind)){
          await fs.mkdir(shots,{recursive:true});
          const name=`wiki-${lang}-${kind}-${view}.png`;
          // The full list has hundreds of entries; capture the actual viewport for a phone-readable overview.
          await page.screenshot({path:path.join(shots,name),fullPage:!['digimon-list','search'].includes(kind)});
        }
        results.push({lang,view,kind});
      }
    }
    for(const anchor of ['species-3','techniques','evolutions','recruits','recruit-3']){
      const legacy=lang==='en'?'/data/':`/data/${lang}.html`;
      await page.goto(root+legacy+'#'+anchor,{waitUntil:'load'});await page.waitForSelector('.wiki-main');
      assert.ok(page.url().startsWith(root+base));
      if(anchor==='species-3')assert.equal(new URL(page.url()).pathname,base+'digimon/3-agumon/');
      if(anchor==='recruit-3')assert.equal(new URL(page.url()).hash,'#recruit-3');
      assert.equal(await page.$$eval('details[open]',es=>es.length),0);
    }
    await page.goto(root+base+'guides/memory-cards/',{waitUntil:'load'});
    const next=languages[(languages.indexOf(lang)+1)%languages.length];
    await page.select('#lang',next);await page.waitForFunction(next=>document.documentElement.lang===next,{},next);
    assert.ok(page.url().includes(`/wiki/${next}/${manifest.tag}/guides/memory-cards/`));
  }
  assert.deepEqual(errors,[]);assert.deepEqual(missing,[]);assert.deepEqual(external,[]);
  if(shots)await fs.writeFile(path.join(shots,'browser-validation.json'),JSON.stringify({manifest,results,errors,missing,external},null,2));
  console.log(`ok: ${results.length} page/type/locale/viewport checks; redirects, trees, offline search, local images, no errors or external wiki requests`);
}finally{
  if(browser)await browser.close();
  if(server){server.kill();await once(server,'exit');}
}
