// Release-tag player data, shared website layout and every page language.
// node web/test/data.mjs SITE [SHOTS]; uses the same driver as the Pages checks.
import puppeteer from './browser.mjs';
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import path from 'node:path';
import { spawn } from 'node:child_process';
import { once } from 'node:events';
const [site, shots] = process.argv.slice(2);
let browser, server;
try {
  server = spawn('python3', ['-u', '-c', 'import http.server\ns=http.server.ThreadingHTTPServer(("127.0.0.1",0),http.server.SimpleHTTPRequestHandler)\nprint(s.server_port,flush=True)\ns.serve_forever()'],
    {cwd: path.resolve(site), stdio: ['ignore', 'pipe', 'ignore']});
  const [port] = await once(server.stdout, 'data');
  const root = `http://127.0.0.1:${String(port).trim()}/`;
  browser = await puppeteer.launch({executablePath: process.env.CHROMIUM || '/snap/bin/chromium', headless: true,
    args: ['--no-sandbox', '--disable-gpu']});
  const page = await browser.newPage();
  const errors = [], external = [];
  page.on('pageerror', e => { if (page.url().includes('/data/')) errors.push(e.message); });
  await page.setRequestInterception(true);
  page.on('request', r => {
    if (r.url().startsWith('http') && !r.url().startsWith(root)) {
      if (page.url().includes('/data/')) external.push(r.url());
      r.abort();
    } else r.continue();
  });
  await page.setViewport({width:1440,height:1000});
  await page.goto(root);
  await page.waitForSelector('.data-link');
  const style = await page.evaluate(() => {
    const body = getComputedStyle(document.body);
    return [body.color, body.fontFamily, body.backgroundImage];
  });
  await page.click('.data-link');
  await page.waitForSelector('#lang option');
  await page.waitForFunction(() => document.fonts.check('16px "Plus Jakarta Sans"'));
  assert.match(page.url(), /\/data\/$/);
  assert.deepEqual(await page.evaluate(() => {
    const body = getComputedStyle(document.body);
    return [body.color, body.fontFamily, body.backgroundImage];
  }), style, 'shared website theme and font');
  const counts = await page.$eval('.data-overview', el => el.textContent.match(/(\d+) techniques · (\d+) partner forms/).slice(1).map(Number));
  assert.equal(await page.$$eval('#species-table tbody tr', rows => rows.length), counts[1]);
  assert.equal(await page.$$eval('#techniques-table tbody tr', rows => rows.length), counts[0]);
  const english = await fs.readFile(path.join(site,'data/index.html'),'utf8');
  assert.match(english,/Data for Horizon [0-9]+\.[0-9]+\.[0-9]+\./);
  try {
    const release = JSON.parse(await fs.readFile(path.join(site,'engine/current.json'),'utf8'));
    assert.ok(english.includes(release.commit.slice(0,12)), 'guide snapshot matches served release');
    assert.ok(english.includes('Data for Horizon ' + release.release_version + '.'), 'guide version matches served release');
  } catch(e) { if(e.code !== 'ENOENT') throw e; }
  await page.type('#techniques-search','fire tower');
  assert.equal(await page.$$eval('#techniques-table tbody tr:not([hidden])',rows=>rows.length),1);
  await page.$eval('#techniques-search',el=>{el.value='';el.dispatchEvent(new Event('input'));});
  await page.click('#techniques-table th:nth-child(3) button');
  const power = await page.$$eval('#techniques-table tbody td:nth-child(3)',cells=>cells.map(cell=>Number(cell.textContent)));
  assert.deepEqual(power,power.slice().sort((a,b)=>a-b));
  const languages = (await fs.readdir(path.join(site,'i18n'))).filter(name=>name.endsWith('.json')).map(name=>name.slice(0,-5)).sort();
  for(const lang of languages) {
    const strings = JSON.parse(await fs.readFile(path.join(site,'i18n',lang+'.json'),'utf8'));
    await Promise.all([page.waitForNavigation({waitUntil:'networkidle0'}),page.select('#lang',lang)]);
    await page.waitForFunction(lang=>document.querySelector('#lang').value===lang,{},lang);
    await page.waitForFunction(title=>document.querySelector('#techniques h2').textContent===title,{},strings['data.techniques']);
    const title = await page.$eval('h1',el=>el.textContent);
    assert.equal(title,strings['data.nav']);
    assert.equal(await page.$eval('html',el=>el.lang.toLowerCase()),lang);
    const expected = new URL(lang==='en'?'data/':`data/${lang}.html`,root);
    assert.equal(new URL(page.url()).pathname,expected.pathname);
    assert.ok(await page.$eval('#techniques',(el,text)=>el.textContent.includes(text),strings['data.learningRule']));
    assert.ok(await page.$eval('#techniques-table',el=>el.textContent.includes('Fire Tower')));
    for(const [size,width,height] of [['desktop',1440,1000],['mobile',390,844]]) {
      await page.setViewport({width,height});
      await page.evaluate(()=>scrollTo({top:0,behavior:'instant'}));
      assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
      assert.equal(await page.$$eval('a[href^="#"]',links=>links.filter(a=>!document.getElementById(a.hash.slice(1))).length),0);
      if(shots) {
        await fs.mkdir(shots,{recursive:true});
        await page.screenshot({path:path.join(shots,`data-${size}-${lang}.png`)});
      }
    }
  }
  assert.deepEqual(errors,[]);
  assert.deepEqual(external,[],'no guide CDNs, trackers or external fonts');
  console.log('ok: release snapshot, shared theme, search/sort, all nine languages, desktop/mobile, zero guide external requests');
} finally {
  if(browser) await browser.close();
  if(server) {server.kill(); await once(server,'exit');}
}
