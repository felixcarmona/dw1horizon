import { renderFeatureList } from './features.js';
import { inspect, checkFiles, partOf } from './disc.js';
import { i18n, LANGS, NAMES, tag } from './i18n.js';
import { FLAGS } from './flags.js';
import { Build, missingSupport, tidyStorage } from './engine/engine.js';

// The links (the hero's Discord and GitHub buttons, the privacy note's code link): change them here.
const LINKS = {
  discord: 'https://discord.gg/SkVDPjYwS',
  github: document.querySelector('meta[name="source-repository"]')?.content || '',
};

// The box art is not ours and is not in this repository: the visitor's browser asks libretro-thumbnails for it, and
// the plain disc stands in when that fails.
const COVERS = 'https://raw.githubusercontent.com/libretro-thumbnails/Sony_-_PlayStation/master/Named_Boxarts/';
// The disc shows until the box art is ready. Each cover is drawn here at the size it is shown, in colour and in grey:
// phones do not have to paint two large filtered pictures per card, and a failed download leaves the disc.
async function showBoxart(id, art) {
  const image = Object.assign(new Image(), { crossOrigin: 'anonymous', referrerPolicy: 'no-referrer',
                                             src: COVERS + encodeURIComponent(BOXART[id]) + '.png' });
  await image.decode();
  const canvas = Object.assign(document.createElement('canvas'), { width: 320, height: 320 });
  const ctx = canvas.getContext('2d');
  ctx.drawImage(image, 0, 0, 320, 320);
  const colour = canvas.toDataURL('image/jpeg', .85);
  const pixels = ctx.getImageData(0, 0, 320, 320);
  for (let i = 0; i < pixels.data.length; i += 4) {
    const [r, g, b] = pixels.data.subarray(i, i + 3);
    pixels.data.fill(((.3 * r + .59 * g + .11 * b - 128) * .78 + 128) * 1.14, i, i + 3);   // grey, low contrast, light
  }
  ctx.putImageData(pixels, 0, 0);
  const grey = art.querySelector('.cover-grey');
  grey.style.filter = 'none';
  grey.src = canvas.toDataURL('image/jpeg', .85);
  art.querySelector('.cover-colour').src = colour;
}
const BOXART = {
  us: 'Digimon World (USA)', dcb: 'Digimon - Digital Card Battle (USA)',
  dw2: 'Digimon World 2 (USA)', dw2003: 'Digimon World 2003 (Europe) (En,Fr,De,Es,It)',
};

const $ = (sel, root = document) => root.querySelector(sel);
const el = (tag, props = {}, ...kids) => { const e = Object.assign(document.createElement(tag), props); e.append(...kids); return e; };
// Capability names help diagnostics, but the player-facing message offers a way forward.
const SUPPORT_DETAILS = {
  'engine.noWasm': 'WebAssembly workers are unavailable.',
  'engine.noOpfs': 'OPFS / synchronous private file storage is unavailable.',
  'engine.noStreams': 'DecompressionStream (deflate-raw) is unavailable.',
};
function errorDetails(node, detail) {
  node.append(el('details', {}, el('summary', { textContent: i18n.t('slot.details') }),
                 el('pre', { textContent: detail })));
}
function supportHelp(node, key) {
  if (!SUPPORT_DETAILS[key]) return;
  node.append(' ', el('a', { href: `${LINKS.github}/blob/main/docs/release/README-players.md`,
                           textContent: i18n.t('engine.playerGuide') }));
  errorDetails(node, SUPPORT_DETAILS[key]);
}
let discs, features;   // features: content/features.json as it is (js/features.js renders it)

// ---------------------------------------------------------------- the four games
//
// Four slots, one per game, each with its cover in grey until its disc is added. The player adds discs with the
// drop-zone button or by dropping anywhere on the page; each file's game and release are found from its bytes (disc.js
// inspect: the boot file of SYSTEM.CNF), then checked: the whole image against the redump checksums of
// data/discs.json, or, for the three games the imported species come from, the files the import reads (a 2048-byte
// .iso, another rip). The last usable disc of a game wins. Files that cannot be used are listed in one dialog per drop.
//
// games: id -> {id, disc (data/discs.json discs[]: the game's main release; species: how many Digimon come from it),
//               el: its slot (<li>), cur: entry | null (the disc in use), pending: entry | null (being checked)}
// entry: {file, expect (the release it is checked against), via ('files' or null), got: {crc32, sha1, size}, pct,
//         worker, batch}
const games = new Map();
const GAME_NAMES = { us: 'Digimon World', dcb: 'Digimon Digital Card Battle', dw2: 'Digimon World 2',
                     dw2003: 'Digimon World 3 / 2003' };
const gameName = (id) => GAME_NAMES[id] || id;
const listOf = (items) => new Intl.ListFormat(i18n.lang, { type: 'conjunction' }).format(items);
// A release in plain words ("Spanish", "USA"): i18n release.<id>; the main releases are named by their game's id
const releaseWords = (r) => i18n.t(`release.${r.id}`);
// a file name that says it is a fan translation or a fan patch
const FAN_NAME = /fan|transl|traduc|\btrad\b|spanish|espa[nñ]ol|espan|english|french|german|italian|portugu|undub|hack|patch(ed)?\b|\bv\d+(\.\d+)+/i;
const sameFile = (a, b) => a && b && a.name === b.name && a.size === b.size && a.lastModified === b.lastModified;

// Every release this page knows by its boot file: [{release, game, supported}]
let byBoot;
function indexReleases() {
  byBoot = new Map();
  const add = (r, game, supported) => {
    if (!byBoot.has(r.boot)) byBoot.set(r.boot, []);
    byBoot.get(r.boot).push({ release: r, game, supported });
  };
  for (const d of discs.discs) add(d, d.id, true);
  for (const v of discs.variants) add(v, v.game, v.supported !== false);
  // other pressings (the first Japanese one, PlayStation the Best, fan translations): Digimon World, not usable
  for (const o of discs.other) if (!discs.variants.some((v) => v.sha1 && v.sha1 === o.sha1)) add(o, 'us', false);
}

// ---------------------------------------------------------------- a drop of files (a batch)
//
// The files of one drop or one choice: their problems are shown together, once every check of the batch has ended.
// (#patch's data-batches: how many are still open, for the tests)
let openBatches = 0;
const countBatches = (d) => { openBatches += d; document.querySelector('#patch').dataset.batches = String(openBatches); };
function newBatch() { countBatches(1); return { open: 0, problems: [] }; }
function hold(batch) { batch.open++; }
function release(batch) {
  if (--batch.open) return;
  countBatches(-1);
  if (batch.problems.length) showProblems(batch.problems);
}
// problem: {name: the file, key, vars, game: the game it is (what works for it is said) or null}
function problem(batch, file, key, vars = {}, game = null) {
  batch.problems.push({ name: file.name, key, vars, game });
}

// ---------------------------------------------------------------- checks

// The release among `cands` whose checksums the hash worker's result matches, or null.
const matching = (cands, got) => cands.find((c) => c.release.sha1 === got.sha1 && (!c.release.crc32 || c.release.crc32 === got.crc32));

function hash(entry, onDone) {
  const w = new Worker(new URL('./hash-worker.js', import.meta.url));
  entry.worker = w;
  w.onmessage = ({ data }) => {
    if (data.progress != null) { entry.pct = Math.floor(data.progress * 100); renderSlots(); return; }
    w.terminate();
    entry.worker = null;
    onDone(data);
  };
  w.onerror = (e) => {
    e.preventDefault();
    w.terminate();
    entry.worker = null;
    onDone({ error: e.message || 'worker' });
  };
  w.postMessage({ file: entry.file });
}

// A disc of game `g` to check: it becomes the game's pending disc. Several of one game in the same drop are checked one
// after another (the last usable one wins); one given while another drop's disc of that game is being checked is
// refused (said in the dialog).
function startCheck(g, file, cands, info, batch) {
  const same = (f) => sameFile(g.cur?.file, f) || sameFile(g.pending?.file, f) || g.queue.some((q) => sameFile(q.file, f));
  if (same(file)) return;                                                               // the same disc again: nothing
  if (g.pending && g.pending.batch !== batch) {
    problem(batch, file, 'why.stillChecking', { other: g.pending.file.name, game: gameName(g.id) });
    return;
  }
  if (g.pending) { hold(batch); g.queue.push({ file, cands, info, batch }); return; }
  const sizeMatch = cands.filter((c) => c.release.size === file.size);
  const entry = { file, expect: (sizeMatch[0] || cands.find((c) => c.supported) || cands[0]).release, via: null,
                  got: { size: file.size }, pct: 0, worker: null, batch, ended: false };
  g.pending = entry;
  hold(batch);
  renderAll();
  const done = () => {
    if (g.pending === entry) g.pending = null;
    end(entry);
    const next = g.queue.shift();
    if (next) { startCheck(g, next.file, next.cands, next.info, next.batch); release(next.batch); }
    renderAll();
  };
  const accept = (via) => {
    if (g.pending !== entry) return;
    entry.via = via;
    g.cur = entry;
    if (g.id === 'us' && !building) { last = null; $('#build-done').dataset.ready = ''; }
    done();
  };
  const reject = (key, vars = {}) => {
    // a disc that matches no checksum but whose game has known fan translations (data/discs.json `other`, an id
    // ending in -fan) and whose name says it is one: a fan translation, not a damaged dump
    if (key === 'why.badDump' && cands.some((c) => /-fan$/.test(c.release.id)) && FAN_NAME.test(file.name)) key = 'why.fanTranslation';
    if (g.pending === entry) problem(batch, file, key, vars, g.id);
    done();
  };
  const lookalike = () => `${gameName(g.id)} (${releaseWords(entry.expect)})`;
  // by the files the import reads (not Digimon World: the patch rebuilds its every sector)
  const byFiles = async (key) => {
    const supported = cands.filter((c) => c.supported && discs.files[c.release.id]);
    const r = supported.find((c) => c.release.size === file.size) || supported[0];
    if (g.id === 'us' || !r) return reject(key, { game: lookalike() });
    entry.expect = r.release;
    entry.pct = 0;
    entry.byFiles = true;
    renderSlots();
    const list = discs.files[r.release.id];
    let res;
    try {
      res = await checkFiles(file, list, (p) => { entry.pct = Math.floor(p * 100); renderSlots(); });
    } catch (e) {
      return reject('why.unreadable', { error: e.message });
    }
    if (g.pending !== entry) return done();
    if (res.bad.length + res.missing.length) return reject('why.badDump', { game: lookalike() });
    accept('files');
  };
  if (!info.raw) {
    if (g.id === 'us') return reject('why.isoDw1');
    return byFiles('why.badDump');
  }
  if (!sizeMatch.length) return byFiles('why.badDump');
  hash(entry, (data) => {
    if (g.pending !== entry) return done();
    if (data.error) return reject('why.unreadable', { error: data.error });
    Object.assign(entry.got, data);
    const m = matching(cands, data);
    if (m && /-fan$/.test(m.release.id)) return reject('why.fanTranslation');
    if (m && !m.supported) return reject('why.unsupported', { release: `${gameName(g.id)} · ${releaseWords(m.release)}` });
    if (m) { entry.expect = m.release; return accept(null); }
    byFiles('why.badDump');
  });
}

// An entry's check is over (once): its batch may show its problems.
function end(entry) {
  if (entry.ended) return;
  entry.ended = true;
  release(entry.batch);
}

function cancel(entry) {
  if (entry.worker) entry.worker.terminate();
  entry.worker = null;
  end(entry);
}

// ---------------------------------------------------------------- archives, ECM, PBP: turned into images first

const JOB_ERROR = { encrypted: 'why.encrypted', parts: 'why.parts', open: 'why.archiveBroken',
                    'not PBP': 'why.notImage', 'PBP multi-disc': 'why.pbpMulti', 'PBP encrypted': 'why.pbpEncrypted',
                    'ECM checksum': 'why.ecmChecksum', 'not ECM': 'why.notImage', 'ECM file cut short': 'why.ecmChecksum' };

// One line per running job under the list: "file: what is happening, nn %"
function job(name) {
  const li = document.createElement('li');
  $('#jobs').append(li);
  return {
    set(key, vars) { li.textContent = `${name}: ${i18n.t(key, vars)}`; },
    end() { li.remove(); renderPatch(); },
  };
}

let jobsRunning = 0;
function runWorker(script, message, onProgress) {
  jobsRunning++;
  renderPatch();
  return new Promise((resolve) => {
    const w = new Worker(new URL(script, import.meta.url), { type: 'module' });
    const end = (data) => { w.terminate(); jobsRunning--; resolve(data); };
    w.onmessage = ({ data }) => {
      if (data.progress != null) return onProgress(data.progress, data);
      end(data);
    };
    w.onerror = (e) => end({ error: e.message || 'worker' });
    w.postMessage(message);
  });
}

// Split archives travel together: their parts are grouped by name (game.part1.rar, game.part2.rar...)
function groups(files) {
  const by = new Map(), out = [];
  for (const f of files) {
    const p = partOf(f.name);
    if (!p) { out.push([f]); continue; }
    const k = p.base.toLowerCase();
    if (!by.has(k)) { by.set(k, []); out.push(by.get(k)); }
    by.get(k).push(f);
  }
  return out;
}

// [{file, info}] of the images and cue sheets in `files` (one archive's parts, or one file), unpacking as needed
async function expand(files, batch, depth = 0) {
  const file = files[0];
  let info;
  try {
    info = await inspect(file);
  } catch (e) {
    problem(batch, file, 'why.unreadable', { error: e.message });
    return [];
  }
  if (files.length > 1 || info.kind === 'archive') {
    if (depth > 3) return [];
    const j = job(file.name);
    const format = info.format.toUpperCase();
    j.set('status.extracting', { format, pct: 0 });
    const r = await runWorker('./archive-worker.js', { files },
                              (p) => j.set('status.extracting', { format, pct: Math.floor(p * 100) }));
    j.end();
    if (r.error) { problem(batch, file, JOB_ERROR[r.error] || 'why.archiveError', { error: r.error }); return []; }
    const out = [];
    for (const f of r.files) out.push(...await expand([f], batch, depth + 1));
    // an archive with nothing this page can use: one line for it (not one per file inside)
    if (!out.length && !batch.problems.some((p) => r.files.some((f) => f.name === p.name))) problem(batch, file, 'why.emptyArchive');
    return out;
  }
  if (info.kind === 'ecm' || info.kind === 'pbp') {
    const j = job(file.name);
    const format = info.kind.toUpperCase();
    j.set('status.decoding', { format, pct: 0 });
    const r = await runWorker('./convert-worker.js', { kind: info.kind, file },
                              (p) => j.set('status.decoding', { format, pct: Math.floor(p * 100) }));
    j.end();
    if (r.error) { problem(batch, file, JOB_ERROR[r.error] || 'why.unreadable', { error: r.error }); return []; }
    return expand([r.file], batch, depth + 1);
  }
  if (info.kind === 'chd') { problem(batch, file, 'why.chd'); return []; }
  if (info.kind === 'unsupported') {
    // one track of a disc with several (the audio of "Game (Track 2).bin"): its data is in track 1, with the .cue
    problem(batch, file, /\(track\s*\d+\)/i.test(file.name) ? 'why.track' : 'why.notImage');
    return [];
  }
  return [{ file, info }];
}

// Files given to the page (chosen or dropped): each to the game it is.
async function handleFiles(files) {
  const batch = newBatch();
  hold(batch);
  try {
    const found = [];
    for (const grp of groups(files)) found.push(...await expand(grp, batch));
    const images = found.filter((x) => x.info.kind === 'image').map((x) => x.file.name.toLowerCase());
    for (const { file, info } of found) {
      if (info.kind === 'cue') {
        if (!info.files.some((name) => images.includes(name.toLowerCase()))) problem(batch, file, 'why.cueOnly', { file: info.files[0] || '.bin' });
        continue;
      }
      const cands = byBoot.get(info.boot) || [];
      if (!cands.length) {
        problem(batch, file, info.boot ? 'why.otherGame' : 'why.notImage', { serial: (info.boot || '').replace('_', '-').replace('.', '') });
        continue;
      }
      const g = games.get(cands[0].game);
      // a release with no checksum (PlayStation the Best): not usable whatever its bytes
      if (cands.every((c) => !c.supported && !c.release.sha1)) {
        problem(batch, file, 'why.unsupported', { release: `${gameName(g.id)} · ${releaseWords(cands[0].release)}` }, g.id);
        continue;
      }
      startCheck(g, file, cands, info, batch);
    }
  } finally {
    renderAll();
    release(batch);
  }
}

// ---------------------------------------------------------------- the problems dialog

function showProblems(list) {
  const dlg = $('#problems');
  const ul = $('#problems-list');
  const seen = new Set([...ul.children].map((li) => li.dataset.key));
  for (const p of list) {
    const key = `${p.name}\n${p.key}`;
    if (seen.has(key)) continue;
    seen.add(key);
    const li = el('li', {}, el('b', { className: 'problem-file', textContent: p.name }),
                  el('span', { className: 'problem-why', textContent: i18n.t(p.key, p.vars) }));
    li.dataset.key = key;
    if (p.game) li.append(el('span', { className: 'problem-works', textContent: i18n.t(`works.${p.game}`) }));
    ul.append(li);
  }
  if (!ul.children.length) return;
  $('#problems-title').textContent = i18n.t('problems.title', { n: ul.children.length });
  if (!dlg.open) dlg.showModal();
}

function setupDialog() {
  const dlg = $('#problems');
  $('#problems-close').addEventListener('click', () => dlg.close());
  dlg.addEventListener('close', () => {
    $('#problems-list').replaceChildren();
    ($('#add-button').hidden ? $('#patch-button') : $('#add-button')).focus();
  });
  dlg.addEventListener('click', (e) => { if (e.target === dlg) dlg.close(); });     // (outside the box)
}

// ---------------------------------------------------------------- the four slots

// One slot per game, made once (start) and updated in place (renderSlots: a rebuild at each progress tick would
// restart the cover's transition and lose the focus of a button inside). Its parts: the cover twice (grey, and the
// colour revealed from the left to --p) with the check's percentage or the check mark on its corner, the game's name,
// what it is for. The same height in every state; the release and checksums are under Details.
function buildSlots() {
  const items = [];
  for (const g of games.values()) {
    const li = el('li', { className: 'slot' });
    li.dataset.game = g.id;
    const cover = (cls) => el('img', { className: `cover ${cls}`, src: 'media/disc.svg', alt: '', width: 320, height: 320 });
    const pct = el('span', { className: 'slot-pct' });                        // (the cover is the progress bar)
    pct.setAttribute('aria-hidden', 'true');
    const check = el('span', { className: 'slot-check', textContent: '✓' });   // labelled "checked" (renderSlots)
    check.setAttribute('role', 'img');
    const art = el('div', { className: 'slot-art' }, cover('cover-grey'), cover('cover-colour'), pct, check);
    showBoxart(g.id, art).catch(() => {});
    li.append(art, el('div', { className: 'slot-text' }, el('b', { className: 'slot-name', textContent: gameName(g.id) }),
                      el('small', { className: 'slot-purpose' })));
    g.el = li;
    items.push(li);
  }
  $('#slots').replaceChildren(...items);
}

const PROGRESS_ATTRS = ['role', 'aria-valuemin', 'aria-valuemax', 'aria-valuenow', 'aria-label'];
function renderSlots() {
  const t = i18n.t;
  for (const g of games.values()) {
    const li = g.el;
    const busy = !!g.pending;
    const e = g.pending || g.cur;
    const state = !e ? 'empty' : busy ? 'busy' : 'ready';
    li.dataset.state = state;
    li.dataset.release = e ? e.expect.id : '';
    const pct = state === 'ready' ? 100 : busy ? e.pct : 0;
    const art = $('.slot-art', li);
    art.style.setProperty('--p', `${pct}%`);
    if (busy) {
      for (const [a, v] of [['role', 'progressbar'], ['aria-valuemin', '0'], ['aria-valuemax', '100'], ['aria-valuenow', String(pct)],
                            ['aria-label', t('disc.checking', { pct })]]) art.setAttribute(a, v);
    } else for (const a of PROGRESS_ATTRS) art.removeAttribute(a);
    const pctEl = $('.slot-pct', li);
    pctEl.hidden = !busy;
    if (busy) pctEl.textContent = `${pct} %`;
    const check = $('.slot-check', li);
    check.hidden = state !== 'ready';
    check.setAttribute('aria-label', t('disc.ok'));
    $('.slot-purpose', li).textContent = g.id === 'us' ? t('slot.purpose.us') : t('slot.purpose.source', { n: g.disc.species });
  }
  renderSums();
}

// Under "Details": the expected and computed checksums of every disc added.
function renderSums() {
  const num = (n) => (n == null ? '' : new Intl.NumberFormat(i18n.lang).format(n));
  const rows = [];
  for (const g of games.values()) {
    const e = g.pending || g.cur;
    if (!e) continue;
    const ex = e.expect;
    const tr = el('tr');
    const name = el('th', {}, el('a', { href: ex.redump || '#', target: '_blank', rel: 'noopener', textContent: ex.title }),
                    el('div', { className: 'serial', textContent: ex.serial || '' }));
    tr.append(name);
    for (const [exp, got] of [[ex.crc32, e.got.crc32], [ex.sha1, e.got.sha1], [num(ex.size), num(e.got.size)]]) {
      // one line, in green, when what the disc gave is what was expected; both lines only when they differ
      const td = el('td');
      if (got && got === exp) td.append(el('div', { className: 'got', textContent: got }));
      else td.append(el('div', { textContent: exp || '' }), ...(got ? [el('div', { className: 'got', textContent: got })] : []));
      if (got) td.lastChild.dataset.match = String(got === exp);
      tr.append(td);
    }
    if (e.via === 'files') tr.append(el('td', { className: 'files', textContent: i18n.t('disc.byFiles') }));
    rows.push(tr);
  }
  $('#sums-body').replaceChildren(...rows);
  $('.sums').hidden = !rows.length;
}

function setupAdd() {
  const input = $('#add-input');
  $('#add-button').addEventListener('click', () => input.click());
  input.addEventListener('change', () => { const f = [...input.files]; input.value = ''; if (f.length) handleFiles(f); });
  const veil = $('#drop-veil');
  const zone = $('#add-button');
  let depth = 0;
  const hasFiles = (e) => [...(e.dataTransfer?.types || [])].includes('Files');
  const lit = (on) => { for (const x of [veil, zone, $('#slots')]) x.classList.toggle('on', on); };
  addEventListener('dragenter', (e) => { if (hasFiles(e)) { depth++; lit(true); } });
  addEventListener('dragleave', (e) => { if (hasFiles(e) && --depth <= 0) { depth = 0; lit(false); } });
  addEventListener('dragover', (e) => { if (hasFiles(e)) e.preventDefault(); });
  addEventListener('drop', (e) => {
    if (!hasFiles(e)) return;
    e.preventDefault();
    depth = 0;
    lit(false);
    handleFiles([...e.dataTransfer.files]);
  });
}

// ---------------------------------------------------------------- the patch button

// The everything disc needs all four games: Digimon World (any of its seven supported releases, the redump dump) and
// the three the imported species come from (any release data/discs.json lists, checked whole or by the files the
// import recipes read): the engine's extractor reads those files from them (tools/derive/importers/discs.py) and the
// release's deltas make the imported models.
function patchState() {
  if (building) return ['patch.building', false];
  const all = [...games.values()];
  if (jobsRunning || all.some((g) => g.pending)) return ['patch.waiting', false];
  const missing = all.filter((g) => !g.cur);
  if (missing.length === all.length) return ['patch.needDiscs', false];
  if (missing.length) return ['patch.missing', false, { list: listOf(missing.map((g) => gameName(g.id))) }];
  const why = missingSupport();
  if (why) return [why, false];
  return ['patch.ready', true];
}

let patching = null;   // a message key while the button has been pressed
let building = null;   // the running Build
let last = null;       // its last state
function renderPatch() {
  const [key, ready, vars] = patchState();
  const btn = $('#patch-button');
  btn.disabled = !ready;
  $('#patch-status').textContent = i18n.t(patching && ready ? patching : key, vars);
  supportHelp($('#patch-status'), key);
  renderBuild();
}

async function patch() {
  if (building || !patchState()[1]) return;
  $('#build-done').dataset.ready = '';
  const q = new URLSearchParams(location.search);
  const opts = { onState: (st) => { last = st; renderBuild(); } };
  if (TEST && q.get('workers')) opts.workers = Number(q.get('workers'));
  // the other three games (their files are read and checked by the engine's extractor)
  const others = [...games.values()].filter((g) => g.id !== 'us');
  building = new Build({ us: games.get('us').cur.file, sources: Object.fromEntries(others.map((g) => [g.id, g.cur.file])),
                         titles: Object.fromEntries(others.map((g) => [g.id, g.cur.expect.title])) }, opts);
  if (TEST && q.get('oom')) building.oomTest = q.get('oom');
  if (TEST && q.get('recycle')) building.recycleMB = Number(q.get('recycle'));
  building.keepTree = TEST && q.has('keep');
  building.shuffle = TEST ? Number(q.get('shuffle')) || 0 : 0;
  last = building.state;
  renderAll();
  const tick = setInterval(() => {      // the clock between the engine's own news
    if (!building) { clearInterval(tick); return; }
    last.elapsed = (performance.now() - last.t0) / 1000;
    if (last.eta != null && last.phase !== 'done') last.eta = Math.max(0, last.eta - 1);
    renderBuild();
  }, 1000);
  try {
    await building.run();
  } catch (e) {
    console.error(e);
  } finally {
    clearInterval(tick);
    building = null;
    renderAll();
    if (TEST) { window.RESULTS = { ...last, result: last.result && { ...last.result, bin: undefined, cue: undefined } }; document.title = 'DONE'; }
  }
}

const TEST = new URLSearchParams(location.search).has('test');
const mb = (n) => new Intl.NumberFormat(i18n.lang, { maximumFractionDigits: 0 }).format(n / 2 ** 20);
function clock(secs) {
  if (secs == null || !isFinite(secs)) return '';
  secs = Math.max(0, Math.round(secs));
  const m = Math.floor(secs / 60), s = secs % 60;
  return m ? `${m} min ${String(s).padStart(2, '0')} s` : `${s} s`;
}

let urls = [];
const STEP_NOW = (name) => `now.${name}`;
const capital = (x) => x.charAt(0).toLocaleUpperCase(i18n.lang) + x.slice(1);
// What is being done right now, in the player's words.
function nowLine(st) {
  const t = i18n.t;
  switch (st.phase) {
    case 'start': return t('now.start');
    case 'download':
      return st.download.fresh > 0 ? t('now.download', { done: mb(st.download.done), total: mb(st.download.total) }) : t('now.start');
    case 'extract': return t('now.extract');
    case 'build': {
      const what = (st.now || []).slice(0, 2).map((x) => t(STEP_NOW(x)));
      return what.length ? capital(new Intl.ListFormat(i18n.lang, { type: 'conjunction' }).format(what)) : t('now.build');
    }
    case 'check': return t('now.check');
    case 'write': return t('now.write');
    case 'done': return t('build.done');
    default: return t('build.stopped');
  }
}

function renderBuild() {
  const box = $('#build');
  const st = last;
  box.hidden = !st;
  if (!st) return;
  const t = i18n.t;
  box.dataset.phase = st.phase;
  $('#build-phase').textContent = nowLine(st);
  const busy = !['done', 'error'].includes(st.phase);
  const p = Math.floor(100 * (st.progress || 0));
  $('#build-time').textContent = busy
    ? (st.eta != null ? t('build.left', { pct: p, eta: clock(st.eta) }) : `${p} %`)
    : st.phase === 'done' ? t('build.took', { time: clock(st.elapsed) }) : '';
  $('#build-progress').style.setProperty('--f', String(st.phase === 'done' ? 1 : st.progress || 0));
  $('#build-progress').setAttribute('aria-valuenow', String(st.phase === 'done' ? 100 : p));
  $('#build-steps').replaceChildren(...st.steps.map((x) => {
    const li = document.createElement('li');
    li.dataset.state = x.done === x.total ? 'done' : x.done ? 'busy' : 'wait';
    li.textContent = `${t(`step.${x.name}`)} ${x.done}/${x.total}`;
    return li;
  }));
  $('#build-detail').hidden = !busy || !['build', 'check', 'write'].includes(st.phase);
  $('#build-workers').replaceChildren(...(busy ? st.workers : []).map((w) => {
    const li = document.createElement('li');
    li.textContent = `${w.id + 1}: ${w.job || t(w.state === 'loading' ? 'build.loading' : 'build.idle')}`;
    li.dataset.state = w.job ? 'busy' : 'idle';
    return li;
  }));
  const err = $('#build-error');
  err.hidden = st.phase !== 'error';
  if (st.error) {
    err.textContent = t(st.error.key, st.error.vars);
    supportHelp(err, st.error.key);
    if (st.error.detail) errorDetails(err, st.error.detail);
  }
  $('#build-log').textContent = st.log.join('\n');
  const done = $('#build-done');
  done.hidden = st.phase !== 'done';
  if (st.phase === 'done' && st.result && !done.dataset.ready) {
    for (const u of urls) URL.revokeObjectURL(u);
    const r = st.result;
    urls = [URL.createObjectURL(r.bin), URL.createObjectURL(r.cue)];
    Object.assign($('#dl-bin'), { href: urls[0], download: `${r.name}.bin` });
    Object.assign($('#dl-cue'), { href: urls[1], download: `${r.name}.cue` });
    done.dataset.ready = '1';
  }
  if (st.result) {
    $('#dl-all').textContent = t('build.downloadBin', { mb: mb(st.result.size) });
    $('#build-sha').textContent = t(st.result.want ? 'build.checked' : 'build.checkedFiles',
                                    { sha1: st.result.sha1, n: st.result.holes, base: st.base ? st.base.title : '' });
  }
  $('#build-stop').hidden = !busy;
}

// ---------------------------------------------------------------- features

function renderFeatures() {
  renderFeatureList($('#feature-list'), features, i18n.lang, discLanguages());   // js/features.js
}

// ---------------------------------------------------------------- start

// The languages the released disc plays in (data/discs.json languages, from the everything recipe), each by its own
// name: the hero's line and the "language" card's {n} and {languages}.
const discLanguages = () => discs.languages || ['en'];

function renderLanguages() {
  const langs = discLanguages();
  $('#lang').value = i18n.lang;
  $('#lang-flag').innerHTML = FLAGS[i18n.lang] || '';
}

function renderAll() {
  i18n.apply(document);
  renderLanguages();
  renderSlots();
  renderPatch();
  renderFeatures();
}

async function start() {
  [discs, features] = await Promise.all([
    fetch('data/discs.json').then((r) => r.json()),
    fetch('content/features.json').then((r) => r.json()),
  ]);
  await i18n.init();
  indexReleases();
  for (const d of discs.discs) games.set(d.id, { id: d.id, disc: d, el: null, cur: null, pending: null, queue: [] });
  buildSlots();
  $('#link-discord').href = LINKS.discord;
  $('#link-github').href = LINKS.github;
  $('#link-github').hidden = !LINKS.github;
  $('#audit-link').href = `${LINKS.github}/tree/main/web/js/engine`;   // the code that builds the disc in the browser
  $('#audit-link').closest('p').hidden = !LINKS.github;
  $('#patch-button').addEventListener('click', patch);
  $('#build-stop').addEventListener('click', () => { if (building) building.cancel(); });
  // one button, both files: the .bin now, the .cue just after (the browser may ask once to allow several downloads)
  $('#dl-all').addEventListener('click', (e) => {
    e.preventDefault();
    $('#dl-bin').click();
    setTimeout(() => $('#dl-cue').click(), 400);
  });
  if ('serviceWorker' in navigator) navigator.serviceWorker.register('engine-sw.js').catch(() => {});
  const menu = $('#lang');
  menu.replaceChildren(...LANGS.map((l) => el('option', { value: l, lang: tag(l), textContent: NAMES[l] })));
  menu.addEventListener('change', async () => { await i18n.set(menu.value); patching = null; renderAll(); });
  setupAdd();
  setupDialog();
  renderAll();
  tidyStorage().catch(() => {});   // what a stopped or crashed build left, the old engines
}

start();

// ---------------------------------------------------------------- release version

// The line under "Create my disc", "v0.1.0 · 27 Oct 2026": the release the engine builds (engine/current.json, written by web/build-engine.sh
// from the release's manifest; tools/version.py), its date in the page's language. Nothing without an engine.
(async () => {
  const el = $('#release');
  let cur;
  try {
    cur = await fetch(new URL('../engine/current.json', import.meta.url)).then((r) => (r.ok ? r.json() : null));
  } catch { return; }
  if (!cur || !cur.release_version) return;
  const show = () => {
    let date = '';
    try {
      date = new Intl.DateTimeFormat(document.documentElement.lang || 'en',
        { day: 'numeric', month: 'short', year: 'numeric', timeZone: 'UTC' }).format(new Date(`${cur.release_date}T00:00:00Z`));
    } catch { /* no date */ }
    el.textContent = `v${cur.release_version}${date ? ` · ${date}` : ''}`;
    el.hidden = false;
  };
  show();
  new MutationObserver(show).observe(document.documentElement, { attributes: true, attributeFilter: ['lang'] });
})();
