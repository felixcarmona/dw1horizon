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
  const page=await browser.newPage();const errors=[],external=[],missing=[];let fromMainPage=false;
  page.on('pageerror',e=>errors.push(e.message));
  page.on('response',r=>{if(r.status()>=400&&r.url().startsWith(root))missing.push(r.url());});
  await page.setRequestInterception(true);
  let offline=false;
  page.on('request',r=>{
    if(!r.url().startsWith(root)&&/^https?:/.test(r.url())){if(page.url().includes('/wiki/')&&!fromMainPage)external.push(r.url());r.abort();}
    else if(offline)r.abort();else r.continue();
  });
  await page.goto(root+'/',{waitUntil:'networkidle0'});
  assert.equal(await page.$('#feature-digimon, #feature-guide, #open-guide'),null);
  assert.equal(await page.$eval('.hero-actions #wiki-entry',e=>e.textContent),'Wiki');
  assert.ok(await page.$('.hero-actions #wiki-entry.button.soft'));
  assert.equal(await page.$('.wiki-entry'),null);
  assert.match(await page.$eval('#wiki-entry',e=>e.getAttribute('href')),/^wiki\//);
  await page.click('#wiki-entry');await page.waitForSelector('.wiki-main');
  const results=[];const palette=new Map();
  for(const lang of languages){
    const strings=JSON.parse(await fs.readFile(path.join(site,`i18n/${lang}.json`),'utf8'));
    const base=`/wiki/${lang}/`;
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
        assert.equal(await page.$('.version'),null);
        assert.equal(await page.$('img,picture,video,canvas,object,embed,svg image'),null,'wiki ships without pictures');
        const badges=await page.$$eval('.badge',es=>es.map(e=>{
          const css=getComputedStyle(e);
          const rgb=value=>value.match(/[\d.]+/g).slice(0,3).map(Number).map(v=>{v/=255;return v<=.04045?v/12.92:((v+.055)/1.055)**2.4;});
          const luminance=value=>rgb(value).reduce((sum,v,i)=>sum+v*[.2126,.7152,.0722][i],0);
          const a=luminance(css.color),b=luminance(css.backgroundColor);
          return {key:e.dataset.level?'level:'+e.dataset.level:'attribute:'+e.dataset.attribute,text:e.textContent.trim(),colour:css.color+'/'+css.backgroundColor,contrast:(Math.max(a,b)+.05)/(Math.min(a,b)+.05)};
        }));
        for(const badge of badges){
          assert.ok(badge.text);assert.ok(badge.contrast>=4.5,`${badge.key} contrast ${badge.contrast}`);
          if(palette.has(badge.key))assert.equal(badge.colour,palette.get(badge.key),'consistent badge colours');else palette.set(badge.key,badge.colour);
        }
        assert.equal(await page.$$eval('details[open]',es=>es.length),0,'spoilers folded');
        if(kind==='home'){
          const guide=await page.$eval('a.pdf-guide',e=>({href:e.getAttribute('href'),text:e.textContent,download:e.hasAttribute('download')}));
          assert.equal(guide.href,manifest.pdfs[lang].file);
          assert.ok(guide.download);
          assert.ok(guide.text.includes(strings['wiki.pdfTitle'])&&guide.text.includes('MB'));
          const response=await fetch(root+guide.href);
          assert.equal(response.headers.get('content-type'),'application/pdf');
          assert.equal((await response.arrayBuffer()).byteLength,manifest.pdfs[lang].bytes);
        }
        if(kind==='digimon-list'){
          assert.equal(await page.$$eval('.species-card',es=>es.length),manifest.counts.species);
          assert.equal(await page.$$eval('.species-card',es=>es.every(e=>e.querySelectorAll('.badge').length===2&&e.querySelector('.specialties'))),true);
          await page.click('button[data-level="rookie"]');
          const shown=await page.$$eval('.species-card:not([hidden])',es=>es.map(e=>e.dataset.level));
          assert.ok(shown.length>0&&shown.length<manifest.counts.species);assert.ok(shown.every(l=>l==='rookie'));
          await page.click('button[data-level=""]');
        }
        if(kind==='agumon'){
          const heading=await page.$('.recruit-record h2');
          assert.equal(await heading.evaluate(e=>e.textContent),strings['wiki.whereToRecruit']);
          assert.equal(await heading.evaluate(e=>e.checkVisibility()),true);
          assert.ok(await page.$eval('.recruit-record .chips',e=>e.checkVisibility()));
          assert.equal(await page.$eval('.recruit-record .spoiler p',e=>e.checkVisibility()),false);
          const own=JSON.parse(await fs.readFile(path.join(site,`wiki/${lang}/search-index.json`),'utf8'));
          const move=own.find(e=>e.type==='technique'&&e.url.endsWith('/2-spit-fire/'));
          assert.equal(await page.$eval('#techniques a[href$="/2-spit-fire/"]',e=>e.textContent),move.title.replace(/ #2$/,''));
          if(lang==='es'){
            assert.equal(await page.$eval('#techniques a[href$="/2-spit-fire/"]',e=>e.textContent),'Escupefuego');
            assert.match(await page.$eval('.recruit-record',e=>e.textContent),/Bosque Indígena/);
          }
        }
        if(kind==='technique'){
          assert.equal(await page.$eval('#learn h2',e=>e.textContent),strings['wiki.whereLearn']);
          assert.ok(await page.$eval('#learn > .table-wrap',e=>e.checkVisibility()));
          assert.ok(await page.$('#learn a[href$="/digimon/69-flarerizamon/"]'));
          assert.ok(await page.$('#learn > .spoiler'));
          assert.equal(await page.$eval('#learn > .spoiler table',e=>e.checkVisibility()),false);
          assert.equal(await page.$$eval('#learn details[open]',es=>es.length),0);
          assert.ok(await page.$eval('#learn',e=>e.textContent.includes('07:00–19:00')));
          assert.ok((await page.$eval('.wiki-main',e=>e.textContent)).includes(strings['wiki.canLearn']));
          if(shots&&['en','es'].includes(lang)&&view==='phone'){
            await fs.mkdir(shots,{recursive:true});
            await page.$eval('#learn',e=>e.scrollIntoView({block:'start'}));
            await page.screenshot({path:path.join(shots,`${lang}-technique-phone.png`)});
          }
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
          assert.ok(await page.$('a.result[href$="/digimon/3-agumon/"] .badge[data-attribute="vaccine"]'));
          assert.equal(await page.$('#search-results img'),null);
          const recruit=await page.$('a.result[data-kind="recruit"]');
          assert.ok(recruit);assert.equal(await recruit.evaluate(e=>e.checkVisibility()),false);
          await page.click('#search-results > .spoiler > summary');
          assert.equal(await recruit.evaluate(e=>e.checkVisibility()),true);
          await page.click('[data-filter="technique"]');
          assert.equal(await page.$$eval('.result',es=>es.every(e=>e.dataset.kind==='technique')),true);
          await page.click('[data-filter="all"]');
          // Once the static index is loaded, queries and filters need no network.
          offline=true;
          await page.$eval('#wiki-query',e=>{e.value='DuckStation';e.dispatchEvent(new Event('input'));});
          assert.equal(await page.$$eval('.result',es=>es.length),2);
          await page.$eval('#wiki-query',e=>{e.value='impossible-wiki-query-123';e.dispatchEvent(new Event('input'));});
          assert.equal(await page.$eval('#search-results',e=>e.textContent),strings['wiki.empty']);
          await page.$eval('#wiki-query',e=>{e.value='Agumon';e.dispatchEvent(new Event('input'));});
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
      assert.ok(page.url().startsWith(root+base),`Expected ${base}; actual ${page.url()}`);
      if(anchor==='species-3')assert.equal(new URL(page.url()).pathname,base+'digimon/3-agumon/');
      if(anchor==='recruit-3')assert.equal(new URL(page.url()).hash,'#recruit-3');
      assert.equal(await page.$$eval('details[open]',es=>es.length),0);
    }
    // Real localized cemetery text is rendered, but only after a deliberate spoiler tap.
    await page.goto(root+base+'guides/hidden-mechanics/',{waitUntil:'load'});
    assert.equal(await page.$$eval('.spoiler[open]',es=>es.length),0);
    assert.equal(await page.$eval('.article-body table',e=>e.checkVisibility()),false);
    assert.ok(await page.$eval('#step-0',e=>e.checkVisibility()));
    await page.click('.article-body > .spoiler > summary');
    assert.equal(await page.$$eval('.article-body table tbody tr',es=>es.length),3);
    assert.ok(await page.$eval('.article-body table',e=>e.checkVisibility()));
    await page.goto(root+base+'guides/new-game-quiz/',{waitUntil:'load'});
    assert.equal(await page.$$eval('.article-body table',es=>es.every(e=>!e.checkVisibility())),true);
    await page.goto(root+base+'digimon/7-airdramon/',{waitUntil:'load'});
    assert.equal(await page.$eval('.recruit-record h2',e=>e.checkVisibility()),false);
    await page.goto(root+base+'digimon/116-analogman/#evolutions',{waitUntil:'load'});
    assert.equal(await page.$eval('h1',e=>e.checkVisibility()),false);
    await page.goto(root+base+'recruits/#recruit-37',{waitUntil:'load'});
    assert.equal(await page.$$eval('.spoiler[open]',es=>es.length),0);
    assert.equal(await page.$eval('[data-recruit="recruit-37"] h2',e=>e.checkVisibility()),false);
    await page.click('.wiki-main > .spoiler > summary');
    assert.ok(await page.$eval('[data-recruit="recruit-37"] h2',e=>e.checkVisibility()));
    assert.equal(await page.$eval('[data-recruit="recruit-37"] table',e=>e.checkVisibility()),false);
    for(const anchor of ['digimon','evolutions','feature-digimon','feature-guide']){
      // The main page's own requests may still be in flight after its redirect to the wiki.
      fromMainPage=true;await page.goto(root+'/#'+anchor,{waitUntil:'load'});await page.waitForSelector('.wiki-main');
      assert.ok(page.url().startsWith(root+base),`Expected ${base}; actual ${page.url()}`);
      assert.equal(await page.$$eval('details[open]',es=>es.length),0);
      await page.goto('about:blank');fromMainPage=false;
    }
    await page.goto(root+base+'guides/memory-cards/',{waitUntil:'load'});
    const next=languages[(languages.indexOf(lang)+1)%languages.length];
    await page.select('#lang',next);await page.waitForFunction(next=>document.documentElement.lang===next,{},next);
    assert.ok(page.url().includes(`/wiki/${next}/guides/memory-cards/`));
  }
  assert.deepEqual(errors,[]);assert.deepEqual(missing,[]);assert.deepEqual(external,[]);
  if(shots)await fs.writeFile(path.join(shots,'browser-validation.json'),JSON.stringify({manifest,results,errors,missing,external},null,2));
  console.log(`ok: ${results.length} page/type/locale/viewport checks; redirects, trees, offline search, text-only cards, badge contrast, no errors or external wiki requests`);
}finally{
  if(browser)await browser.close();
  if(server){server.kill();await once(server,'exit');}
}
