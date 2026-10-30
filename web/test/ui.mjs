// web/test (not deployed): the four slots in headless Chromium, no build. puppeteer-core from
// build/stage9/node/node_modules. node web/test/ui.mjs URL [SHOTS_DIR]
//   1. empty: four passive slots in grey, "Build my disc" disabled; only the drop zone (click, Enter) opens the
//      file chooser; files can still be dropped on a slot or anywhere on the page
//   2. checking, replaced: Digimon World (USA) and Card Battle added, then World 2: its slot shows the check's
//      progress while the two are ready; then Digimon World (Spain): the slot holds the Spanish disc and says nothing
//      more (no release, no note: Details shows it); the status names the game still missing
//   3. incompatible: one drop of files that cannot be used -> one dialog listing each (the same disc twice: ignored)
//   4. ready: the four slots in colour -> "Build my disc" enabled; × (keyboard) empties a slot and the focus goes to
//      the drop zone; a disc given while another of its game is still being checked is refused in the dialog
// With SHOTS_DIR, screenshots in English and Spanish, desktop and phone width: empty, checking, replaced, the dialog
// over the slots, ready.
import puppeteer from './browser.mjs';
import fs from 'node:fs';
import path from 'node:path';
const [url, shots] = process.argv.slice(2);
const I = process.env.SOURCE_ISOS || 'build/isos';
const DW = `${I}/digimon-world`;
// (the fixtures in the checkout's build/: the snap Chromium cannot read /tmp)
const BUILD = path.join(path.dirname(new URL(import.meta.url).pathname), '../../build');
fs.mkdirSync(BUILD, { recursive: true });
const fx = fs.mkdtempSync(path.join(BUILD, 'ui-fixtures-'));
const fake = (name, data) => { const p = path.join(fx, name); fs.writeFileSync(p, data); return p; };
const BAD = [
  `${DW}/DigimonWorld (Japan).bin`,                                    // first pressing: unsupported
  `${DW}/fan-patches/Digimon World (France).bin`,                      // modified dump
  `${DW}/fan-translations/DigimonWorld (Spanish v1.21).bin`,           // fan translation
  fake('Lonely.cue', 'FILE "Lonely.bin" BINARY\r\n  TRACK 01 MODE2/2352\r\n    INDEX 01 00:00:00\r\n'),
  fake('notes.txt', 'not a disc\n'.repeat(4000)),
  fake('game.chd', Buffer.concat([Buffer.from('MComprHD'), Buffer.alloc(4096)])),
  `${DW}/Digimon World (Spain).bin`,                                   // already added: ignored
];
const OTHERS = [`${I}/digital-card-battle/Digimon Digital Card Battle (USA).bin`, `${I}/digimon-world-2/Digimon World 2 (USA).bin`,
  `${I}/digimon-world-2003/Digimon World 2003 (E) [SLES-03936].bin`];
const b = await puppeteer.launch({ executablePath: process.env.CHROMIUM || '/snap/bin/chromium', headless: 'new', args: ['--no-sandbox', '--disable-gpu'],
  userDataDir: path.join(fx, 'profile'), protocolTimeout: 0 });
const p = await b.newPage();
if (process.env.APP_SOURCE) {
  await p.setRequestInterception(true);
  p.on('request', (r) => r.url().includes('/js/app.js')
    ? r.respond({ contentType: 'text/javascript', body: fs.readFileSync(process.env.APP_SOURCE, 'utf8') }) : r.continue());
}
p.on('pageerror', (e) => console.log('[pageerror]', e.message));
let failed = 0;
const ok = (cond, what) => { console.log(`${cond ? 'ok  ' : 'FAIL'} ${what}`); if (!cond) failed++; };
const add = async (...files) => { await (await p.$('#add-input')).uploadFile(...files); await new Promise((r) => setTimeout(r, 300)); };
// every file given so far looked at and checked (#patch data-batches: the drops still open)
const idle = () => p.waitForFunction(() => document.querySelector('#patch').dataset.batches === '0', { timeout: 600000, polling: 300 });
const slots = () => p.$$eval('.slot', (els) => els.map((e) => ({ game: e.dataset.game, release: e.dataset.release, state: e.dataset.state,
  text: e.innerText.replace(/\s+/g, ' ').trim() })));
const passiveSlots = async () => p.$$eval('.slot', (els) => els.every((e) => {
  const css = getComputedStyle(e);
  return e.tabIndex === -1 && !e.hasAttribute('role') && css.cursor !== 'pointer'
    && ['Top', 'Right', 'Bottom', 'Left'].every((side) => !['dashed', 'dotted'].includes(css[`border${side}Style`]));
}));
const drop = async (target, ...files) => {
  await p.evaluate(() => {
    const input = document.createElement('input');
    input.type = 'file'; input.multiple = true; input.id = 'drop-fixture'; input.hidden = true;
    document.body.append(input);
  });
  await (await p.$('#drop-fixture')).uploadFile(...files);
  await p.$eval('#drop-fixture', (input, selector) => {
    const data = new DataTransfer();
    for (const file of input.files) data.items.add(file);
    document.querySelector(selector).dispatchEvent(new DragEvent('drop', { bubbles: true, cancelable: true, dataTransfer: data }));
    input.remove();
  }, target);
};
const slot = async (game) => (await slots()).find((s) => s.game === game);
const states = async () => (await slots()).map((s) => s.state).join(' ');
const shot = async (lang, name, phone = false) => {
  if (!shots) return;
  await p.setViewport(phone ? { width: 390, height: 844 } : { width: 1280, height: 900 });
  const target = (await p.$('#problems[open]')) ? null : await p.$('#patch');
  if (target) await p.evaluate(() => document.activeElement?.blur());      // the resting state, no focus ring
  await new Promise((r) => setTimeout(r, 400));
  const file = `${shots}/${lang}-${name}${phone ? '-phone' : ''}.png`;
  if (target) await target.screenshot({ path: file }); else await p.screenshot({ path: file });
  console.log(file);
  await p.setViewport({ width: 1280, height: 900 });
};
// the file chooser an action opens (cancelled), or null
const chooser = async (act) => {
  const [c] = await Promise.all([p.waitForFileChooser({ timeout: 3000 }).catch(() => null), act()]);
  if (c) await c.cancel();
  return c;
};

for (const lang of shots ? ['en', 'es'] : ['en']) {
  await p.setViewport({ width: 1280, height: 900 });
  await p.goto(url, { waitUntil: 'networkidle0' });
  await p.select('#lang', lang);
  // 1. empty
  ok(await p.$eval('#patch-button', (x) => x.disabled), `${lang}: empty: the button is disabled`);
  ok((await states()) === 'empty empty empty empty', `${lang}: four empty slots: ${await states()}`);
  const n = (await slots()).map((s) => (s.text.match(/(\d+) Digimon/) || [])[1]);
  ok(n.join() === ',78,41,56', `${lang}: the source slots say how many Digimon come from each: ${n.slice(1)}`);
  await shot(lang, 'empty'); await shot(lang, 'empty', true);
  ok(await passiveSlots(), `${lang}: empty slots have solid borders, default cursors and no keyboard activation`);
  for (const game of ['us', 'dcb', 'dw2', 'dw2003']) {
    ok(!(await chooser(() => p.click(`.slot[data-game="${game}"] .slot-name`))), `${lang}: clicking ${game} does not open the file chooser`);
  }
  ok(!(await chooser(() => p.evaluate(() => {
    for (const slot of document.querySelectorAll('.slot')) {
      slot.focus();
      for (const key of ['Enter', ' ']) slot.dispatchEvent(new KeyboardEvent('keydown', { key, bubbles: true }));
    }
  }))), `${lang}: slots do not open the chooser by keyboard`);
  const border = () => p.$eval('.drop-border rect', (e) => {
    const css = getComputedStyle(e), box = e.closest('button').getBoundingClientRect();
    return { stroke: css.stroke, width: css.strokeWidth, dash: css.strokeDasharray,
      fits: Math.abs(e.getBoundingClientRect().width - (box.width - 3)) < 1 };
  });
  const normal = await border();
  ok(normal.width === '3px' && normal.dash === '14px, 10px' && normal.fits, `${lang}: drop zone has 3px strokes, 14px dashes and 10px gaps fitting the box`);
  await p.hover('#add-button');
  await new Promise((r) => setTimeout(r, 200));
  ok((await border()).stroke !== normal.stroke, `${lang}: hover changes the dashed border colour`);
  await p.mouse.move(0, 0);
  await p.evaluate(() => document.querySelector('#add-button').dispatchEvent(new DragEvent('dragenter', {
    bubbles: true, dataTransfer: (() => { const d = new DataTransfer(); d.items.add(new File(['x'], 'test.bin')); return d; })()
  })));
  await new Promise((r) => setTimeout(r, 200));
  ok((await border()).stroke !== normal.stroke && await passiveSlots(), `${lang}: drag-over colours the drop zone and keeps slots passive`);
  await p.evaluate(() => window.dispatchEvent(new DragEvent('dragend')));
  await p.setViewport({ width: 390, height: 844 });
  ok((await border()).fits, `${lang}: dashed border fits the phone width`);
  await p.setViewport({ width: 1280, height: 900 });
  ok(await chooser(() => p.click('#add-button')), `${lang}: so does the drop zone`);
  await p.focus('#add-button');
  ok(await chooser(() => p.keyboard.press('Enter')), `${lang}: and Enter on it`);

  // 2. checking, replaced
  await drop('body', `${DW}/Digimon World (USA).bin`);
  await idle();
  await drop('.slot[data-game="dcb"]', OTHERS[0]);
  await idle();
  ok((await slot('us')).release === 'us' && (await slot('dcb')).state === 'ready', `${lang}: Digimon World (USA) and Card Battle added: ${await states()}`);
  await add(OTHERS[1]);
  // the World 2 disc is being checked (460 MB: a few seconds): its slot shows the progress over the cover
  await p.waitForFunction(() => { const s = document.querySelector('.slot[data-game="dw2"]'); return s.dataset.state === 'busy' && parseInt(s.querySelector('.slot-art').style.getPropertyValue('--p')) >= 30; }, { timeout: 60000, polling: 50 }).catch(() => {});
  const mid = await slot('dw2');
  ok(mid.state === 'busy' && /\d+ %/.test(mid.text), `${lang}: World 2 checking in its slot: ${mid.text}`);
  ok(await passiveSlots(), `${lang}: checking slots keep quiet borders and passive semantics`);
  await shot(lang, 'checking'); await shot(lang, 'checking', true);
  await idle();
  await add(`${DW}/Digimon World (Spain).bin`);
  await idle();
  const us = await slot('us');
  const details = await p.$eval('#sums-body', (x) => x.textContent.replace(/\s+/g, ' '));   // (Details is collapsed: no innerText)
  ok(us.release === 'dw1-es' && !/(English|Inglés|USA|EE\. UU\.|Spanish|Español|Replaced|sustituido)/.test(us.text) && /Digimon World \(Spain\)/.test(details),
     `${lang}: Spain replaced USA: the slot says nothing more (${us.text}), Details shows the Spanish disc`);
  const status = await p.$eval('#patch-status', (x) => x.textContent);
  ok(/2003/.test(status) && !/Digimon World 2[^0]/.test(status), `${lang}: the status names the missing game: ${status}`);
  await shot(lang, 'replaced'); await shot(lang, 'replaced', true);

  // 3. incompatible: one drop, one dialog (over the slots)
  await p.$eval('#slots', (x) => x.scrollIntoView({ block: 'center' }));
  await add(...BAD);
  await p.waitForSelector('#problems[open]', { timeout: 600000 });
  await idle();
  await new Promise((r) => setTimeout(r, 500));
  const items = await p.$$eval('#problems-list li', (els) => els.map((e) => e.innerText.replace(/\s+/g, ' ').trim()));
  console.log(items.map((x) => `    ${x}`).join('\n'));
  ok(items.length === BAD.length - 1, `${lang}: one dialog, ${items.length} files listed (${BAD.length - 1} expected; the disc added twice ignored)`);
  ok((await slot('us')).release === 'dw1-es', `${lang}: the Spanish disc stayed`);
  ok(await p.evaluate(() => document.activeElement?.id === 'problems-close'), `${lang}: the dialog's button has the focus`);
  await shot(lang, 'incompatible'); await shot(lang, 'incompatible', true);
  await p.keyboard.press('Escape');
  ok(!(await p.$('#problems[open]')), `${lang}: Escape closes the dialog`);

  // 4. ready
  await add(OTHERS[2]);
  await idle();
  ok(!(await p.$eval('#patch-button', (x) => x.disabled)), `${lang}: four games: the button is enabled`);
  ok((await states()) === 'ready ready ready ready', `${lang}: four slots ready: ${await states()}`);
  ok(await passiveSlots(), `${lang}: ready slots keep quiet borders and passive semantics`);
  await shot(lang, 'ready'); await shot(lang, 'ready', true);
  // Two discs of one game in one drop are queued; the last usable one wins.
  await add(`${DW}/Digimon World (USA).bin`, `${DW}/Digimon World (Europe).bin`);
  await idle();
  ok((await slot('us')).release === 'dw1-eu', `${lang}: two discs in one drop: the last usable one wins`);

  // Script only the expensive Build.run boundary; exercise the real page's progress and download rendering.
  await p.evaluate(async () => {
    const { Build } = await import('./js/engine/engine.js');
    window.originalRun = Build.prototype.run;
    window.fakeBuildNumber = 0;
    Build.prototype.run = async function () {
      const n = ++window.fakeBuildNumber;
      this.state.phase = 'build';
      this.onState(this.state);
      await new Promise((r) => { window.finishFakeBuild = r; });
      Object.assign(this.state, { phase: 'done', result: { bin: new Blob([`disc ${n}`]), cue: new Blob(['cue']),
        name: 'fixture', size: 6, holes: 0, sha1: `fixture-${n}` } });
      this.onState(this.state);
      return this.state.result;
    };
  });
  const links = [];
  for (let n = 1; n <= 2; n++) {
    await p.click('#patch-button');
    await p.waitForFunction(() => document.querySelector('#build').dataset.phase === 'build');
    await p.select('#lang', n === 1 ? 'es' : lang);
    ok(await p.$eval('#build', (x) => x.dataset.phase === 'build'), `${lang}: language switch keeps build ${n} running`);
    await p.evaluate(() => window.finishFakeBuild());
    await p.waitForFunction(() => document.querySelector('#build').dataset.phase === 'done' && !document.querySelector('#patch-button').disabled);
    links.push(await p.$eval('#dl-bin', async (x) => ({ href: x.href, text: await (await fetch(x.href)).text() })));
  }
  ok(links[0].text === 'disc 1' && links[1].text === 'disc 2' && links[0].href !== links[1].href,
    `${lang}: a second build replaces the first download`);
  await p.evaluate(async () => { const { Build } = await import('./js/engine/engine.js'); Build.prototype.run = window.originalRun; });
  // × empties a slot (keyboard: the × is a button) and leaves the focus in it
  await p.focus('.slot[data-game="dw2"] .disc-remove');
  await p.keyboard.press('Enter');
  ok((await slot('dw2')).state === 'empty' && (await p.$eval('#patch-button', (x) => x.disabled)), `${lang}: × empties the slot, the button is disabled again`);
  ok(await p.evaluate(() => document.activeElement?.id === 'add-button'), `${lang}: the focus goes to the drop zone`);
  // a disc given while another drop's disc of the same game is still being checked: said in the dialog
  await p.click('.slot[data-game="us"] .disc-remove');
  await add(`${DW}/Digimon World (USA).bin`);
  await add(`${DW}/Digimon World (Italy).bin`);
  await p.waitForSelector('#problems[open]', { timeout: 600000 });
  await idle();
  const still = await p.$$eval('#problems-list li', (els) => els.map((e) => e.innerText.replace(/\s+/g, ' ').trim()));
  ok(still.length === 1 && /Italy/.test(still[0]) && (await slot('us')).release === 'us', `${lang}: still being checked: ${still}`);
  await p.click('#problems-close');
}
await b.close();
fs.rmSync(fx, { recursive: true, force: true });
console.log(failed ? `${failed} FAILED` : 'all ok');
process.exit(failed ? 1 : 0);
