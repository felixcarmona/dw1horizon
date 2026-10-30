// web/test (the engine's tests, not deployed); puppeteer-core from build/stage9/node/node_modules (npm i puppeteer-core there).
// node run.mjs URL DISC.bin PROFILE_DIR [timeout s]: the real page end to end in headless Chromium: the disc and the
// other three games given to the page's "Add discs" input, "Build my disc", wait for the end (?test=1 sets the title
// DONE), then the image in OPFS hashed again with the page's own hash worker. Prints the page's state (times, log, SHA-1) and the peak RSS of the
// browser's processes (sampled every 2 s).
import puppeteer from './browser.mjs';
import { execSync } from 'node:child_process';
import { loadavg } from 'node:os';
const [url, disc, profile, tmo = '3600'] = process.argv.slice(2);
const FF = process.env.FIREFOX;
const b = FF
  ? await puppeteer.launch({ browser: 'firefox', executablePath: FF, headless: true, userDataDir: profile, protocolTimeout: 0 })
  : await puppeteer.launch({ executablePath: process.env.CHROMIUM || '/snap/bin/chromium', headless: 'new', userDataDir: profile,
    args: ['--no-sandbox', '--disable-gpu'], protocolTimeout: 0 });
const p = await b.newPage();
if (!FF) await p.setCacheEnabled(false);
p.on('console', (m) => { const t = m.text(); if (!/^\s*$/.test(t)) console.log('[page]', t.slice(0, 400)); });
p.on('pageerror', (e) => console.log('[pageerror]', e.message));
const pid = b.process().pid;
let peak = 0;
const cpuByPid = new Map();
const startLoad = loadavg()[0];
let maxLoad = startLoad;
const sample = () => {
  try {
    const kb = execSync('ps -eo pid=,ppid=,rss=,cputimes=').toString().trim().split('\n').map((l) => l.trim().split(/\s+/).map(Number));
    const kids = new Map();
    for (const [q, pp] of kb) { if (!kids.has(pp)) kids.set(pp, []); kids.get(pp).push(q); }
    const rss = new Map(kb.map(([q, , r]) => [q, r]));
    const cpu = new Map(kb.map(([q, , , s]) => [q, s]));
    let sum = 0; const st = [pid];
    while (st.length) {
      const q = st.pop(); sum += rss.get(q) || 0;
      cpuByPid.set(q, Math.max(cpuByPid.get(q) || 0, cpu.get(q) || 0));
      st.push(...(kids.get(q) || []));
    }
    peak = Math.max(peak, sum);
    maxLoad = Math.max(maxLoad, loadavg()[0]);
  } catch {}
};
const iv = setInterval(sample, 2000);
const t0 = Date.now();
await p.goto(url, { waitUntil: 'networkidle0' });
// OTHERS="dcb=PATH;dw2=PATH;dw2003=PATH": the other three games (the release makes the imported species' models from
// them); default: the USA Card Battle and World 2 and the European World 2003 of SOURCE_ISOS. OTHERS=none: none
// (the page then refuses to build: the missing-discs state). All four go through the page's one "Add discs" input,
// together, as a player choosing them at once.
const ISOS = process.env.SOURCE_ISOS || 'build/isos';
const OTHERS = process.env.OTHERS ?? [`dcb=${ISOS}/digital-card-battle/Digimon Digital Card Battle (USA).bin`,
  `dw2=${ISOS}/digimon-world-2/Digimon World 2 (USA).bin`,
  `dw2003=${ISOS}/digimon-world-2003/Digimon World 2003 (E) [SLES-03936].bin`].join(';');
const others = (OTHERS === 'none' ? '' : OTHERS).split(';').filter(Boolean).map((kv) => kv.slice(kv.indexOf('=') + 1));
await (await p.waitForSelector('#add-input')).uploadFile(disc, ...others);
await p.waitForFunction(() => !document.querySelector('#patch-button').disabled, { timeout: 300000, polling: 500 }).catch(async (e) => { console.log(await p.evaluate(() => document.querySelector("#patch-status").textContent + " | " + [...document.querySelectorAll(".slot:not([data-state=\"empty\"]), #problems-list li")].map((s) => s.innerText.replace(/\s+/g, ' ')).join(" ; "))); throw e; });
const tb = Date.now();
console.log(`disc checked in ${((tb - t0) / 1000).toFixed(1)} s; building`);
await p.click('#patch-button');
let lastLine = '';
let lastF = 0;
const prog = setInterval(async () => {
  try {
    const s = await p.evaluate(() => `${document.querySelector('#build-phase')?.textContent} | ${document.querySelector('#build-time')?.textContent}`);
    // (the overall bar never goes back)
    const f = await p.evaluate(() => Number(getComputedStyle(document.querySelector('#build-progress')).getPropertyValue('--f')));
    if (f < lastF - 1e-9) console.log(`BAR WENT BACK ${lastF} -> ${f}`);
    lastF = f;
    if (s !== lastLine) { lastLine = s; console.log(`${((Date.now() - tb) / 1000).toFixed(0)} s  ${s}`); }
  } catch {}
}, 5000);
await p.waitForFunction(() => document.title === 'DONE', { timeout: Number(tmo) * 1000, polling: 1000 });
clearInterval(prog);
const wall = (Date.now() - tb) / 1000;
const r = await p.evaluate(async () => {
  const R = window.RESULTS;
  let file = null;
  if (R.phase === 'done') {
    const root = await navigator.storage.getDirectory();
    const f = await (await (await root.getDirectoryHandle('horizon-build')).getFileHandle('image.bin')).getFile();
    file = await new Promise((res) => {
      const w = new Worker('js/hash-worker.js');
      w.onmessage = ({ data }) => { if (data.progress == null) { w.terminate(); res({ ...data, size: f.size }); } };
      w.postMessage({ file: f });
    });
  }
  return { phase: R.phase, error: R.error, base: R.base, times: R.times, download: R.download, result: R.result,
           units: R.units, workers: R.workerCount, memoryRetries: R.memoryRetries, log: R.log, file };
});
clearInterval(iv); sample();
console.log(JSON.stringify({ ...r, log: undefined }, null, 1));
console.log(r.log.join('\n'));
console.log(`wall (build button to DONE) ${wall.toFixed(1)} s; peak RSS of the browser's processes ${(peak / 1024).toFixed(0)} MB`);
console.log(`browser CPU ${[...cpuByPid.values()].reduce((a, b) => a + b, 0)} s; load average start ${startLoad.toFixed(1)}, peak ${maxLoad.toFixed(1)}, end ${loadavg()[0].toFixed(1)}`);
await b.close();
process.exit(r.phase === 'done' ? 0 : 1);
