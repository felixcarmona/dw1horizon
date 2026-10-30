// web/test (the engine's tests, not deployed); puppeteer-core from build/stage9/node/node_modules (npm i puppeteer-core there).
// node shots.mjs URL OUTDIR LANG [STOP_AFTER_S]: screenshots of the build: the four discs added (ready), then the build
// (desktop at ~30 s and ~90 s, phone width), then the end. The discs: DW1 (default the USA one) and OTHERS as in run.mjs
// (default the three source discs of SOURCE_ISOS). STOP_AFTER_S: stop the build after the building shots. The
// disc-adding states (replaced, the dialog): web/test/ui.mjs.
import puppeteer from './browser.mjs';
const [url, out, lang, stopAfter] = process.argv.slice(2);
const I = process.env.SOURCE_ISOS || 'build/isos';
const DW1 = process.env.DW1 || `${I}/digimon-world/Digimon World (USA).bin`;
const OTHERS = process.env.OTHERS || [`dcb=${I}/digital-card-battle/Digimon Digital Card Battle (USA).bin`,
  `dw2=${I}/digimon-world-2/Digimon World 2 (USA).bin`, `dw2003=${I}/digimon-world-2003/Digimon World 2003 (E) [SLES-03936].bin`].join(';');
const b = await puppeteer.launch({ executablePath: process.env.CHROMIUM || '/snap/bin/chromium', headless: 'new', userDataDir: out + '/prof',
  args: ['--no-sandbox', '--disable-gpu'], protocolTimeout: 0 });
const p = await b.newPage();
p.on('pageerror', (e) => console.log('[pageerror]', e.message));
await p.setViewport({ width: 1280, height: 900 });
await p.goto(url, { waitUntil: 'networkidle0' });
await p.click(`[data-lang="${lang}"]`);
const shot = async (name, sel = '#patch') => {
  await (await p.$(sel)).screenshot({ path: `${out}/${lang}-${name}.png` });
  console.log(`${out}/${lang}-${name}.png`);
};
await shot('empty');
await (await p.waitForSelector('#add-input')).uploadFile(DW1);
await p.waitForFunction(() => document.querySelector('#patch').dataset.batches === '0' && document.querySelector('.slot[data-state="ready"]'), { timeout: 300000, polling: 500 });
await shot('one-disc');
await (await p.$('#add-input')).uploadFile(...OTHERS.split(';').filter(Boolean).map((kv) => kv.slice(kv.indexOf('=') + 1)));
await p.waitForFunction(() => !document.querySelector('#patch-button').disabled, { timeout: 300000 });
await shot('ready');
await p.click('#patch-button');
await new Promise((r) => setTimeout(r, 30000));
await shot('building', '#build');
await new Promise((r) => setTimeout(r, 60000));
await shot('building-later', '#build');
await p.setViewport({ width: 390, height: 844 });   // (isMobile would reload the page)
await new Promise((r) => setTimeout(r, 1500));
await shot('building-phone', '#build');
await p.setViewport({ width: 1280, height: 900 });
if (stopAfter) {
  await p.click('#build-stop');
  await new Promise((r) => setTimeout(r, 2000));
  await shot('stopped', '#build');
} else {
  await p.waitForFunction(() => ['done', 'error'].includes(document.querySelector('#build').dataset.phase), { timeout: 1800000, polling: 2000 });
  await shot('done', '#build');
}
await b.close();
