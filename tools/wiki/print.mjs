// Print only local static resources; the server and browser always close.
import puppeteer from '../../web/test/browser.mjs';
import {spawn} from 'node:child_process';
import {once} from 'node:events';
import fs from 'node:fs/promises';
import path from 'node:path';
const site=path.resolve(process.argv[2]);
let browser,server;
try {
  server=spawn('python3',['-u','-c','import http.server\ns=http.server.ThreadingHTTPServer(("127.0.0.1",0),http.server.SimpleHTTPRequestHandler)\nprint(s.server_port,flush=True)\ns.serve_forever()'],{cwd:site,stdio:['ignore','pipe','ignore']});
  const [data]=await once(server.stdout,'data');
  const root=`http://127.0.0.1:${data.toString().trim()}`;
  browser=await puppeteer.launch({executablePath:process.env.CHROMIUM||'/snap/bin/chromium',headless:true,args:['--no-sandbox']});
  const manifest=JSON.parse(await fs.readFile(path.join(site,'wiki/manifest.json'),'utf8'));
  for(const lang of (await fs.readdir(path.join(site,'wiki'))).sort()) {
    if(!await fs.access(path.join(site,'wiki',lang,'print.html')).then(()=>true,()=>false))continue;
    const page=await browser.newPage();
    await page.setRequestInterception(true);
    page.on('request',r=>r.url().startsWith(root+'/')?r.continue():r.abort());
    await page.goto(`${root}/wiki/${lang}/print.html`,{waitUntil:'networkidle0'});
    await page.evaluate(()=>document.fonts.ready);
    const missing=await page.evaluate(()=>[...document.querySelectorAll('a[href^="#"]')].filter(a=>!document.getElementById(a.hash.slice(1))).map(a=>a.hash));
    if(missing.length)throw new Error(`Broken PDF links: ${missing}`);
    await page.pdf({path:path.join(site,`wiki/${lang}/Horizon-Guide-${manifest.tag}-${lang}.pdf`),preferCSSPageSize:true,printBackground:true,timeout:120000,tagged:false,outline:false,displayHeaderFooter:false});
    await page.close();
  }
} finally {
  if(browser)await browser.close();
  if(server){server.kill();await once(server,'exit');}
}
