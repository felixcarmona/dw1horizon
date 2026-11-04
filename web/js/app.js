import { setupChangelog, renderChangelog } from './changelog.js';
import { renderFeatureList } from './features.js';
import { setupMaps, labels as mapLabels } from './maps.js';
import { setupDigimon, labels as digimonLabels } from './digimon.js';
import { setupDesktop, renderDesktop, hasDesktop, visitorOS } from './desktop.js';
import { inspect, checkFiles, partOf } from './disc.js';
import { i18n, LANGS, NAMES, tag } from './i18n.js';
import { FLAGS } from './flags.js';
import { Build, missingSupport, tidyStorage, buildRoom, checkRoom, isMobile } from './engine/engine.js';
import { store, revive } from './remember.js';

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
// Open by default: a screenshot of an error then shows what went wrong without a click.
function errorDetails(node, detail, open = true) {
  // (translate="no": the error text is what a report needs, as it was)
  node.append(el('details', { open }, el('summary', { textContent: i18n.t('slot.details') }),
                 el('pre', { textContent: detail, translate: false })));
}
// A build's error in the player's words ({gb}: the room the build needs, in this page's language).
const errorText = (error) => i18n.t(error.key, { ...error.vars, gb: gb(error.vars?.bytes || 0) });
// What a player pastes when a build fails: the message, what to do, the error's own text and the build's log.
function copyReport(st) {
  const button = el('button', { type: 'button', className: 'build-copy', textContent: i18n.t('build.copyReport') });
  button.addEventListener('click', async () => {
    const text = [errorText(st.error), fixes(st.error.kind, st.error.vars?.bytes).map((f) => `- ${f.text}`).join('\n'),
                  st.error.detail, st.log.join('\n')].filter(Boolean).join('\n\n');
    try { await navigator.clipboard.writeText(text); button.textContent = i18n.t('build.copied'); } catch { /* the log stays on the page */ }
  });
  return button;
}
function supportHelp(node, key) {
  if (!SUPPORT_DETAILS[key]) return;
  node.append(' ', el('a', { href: `${LINKS.github}/blob/main/docs/release/README-players.md`,
                           textContent: i18n.t('engine.playerGuide') }));
  errorDetails(node, SUPPORT_DETAILS[key]);
}

// What the player can do about a kind of failure (engine.js explain: 'storage', 'blocked', 'memory', 'network', or
// null for anything else), most likely first: [{text, href}] (href: the desktop apps, when this page offers them).
// bytes: the room the build needs.
function fixes(kind, bytes = 0) {
  const t = i18n.t;
  const out = [];
  const add = (key, vars) => out.push({ text: t(key, vars) });
  const elsewhere = () => {
    if (hasDesktop()) out.push({ text: t('fix.desktop'), href: '#desktop' });
    else add(isMobile() ? 'fix.computer' : 'fix.otherBrowser');
  };
  const room = { gb: gb(bytes || 2 * 2 ** 30) };
  if (kind === 'storage') {
    add('fix.private');
    add('fix.freeDisk', room);
    const kept = keptBytes();
    if (kept) add('remember.freeSpace', { gb: gb(kept) });
    elsewhere();
  } else if (kind === 'private') {
    elsewhere();                                     // (the warning itself says to open a normal window)
  } else if (kind === 'blocked') {
    add('fix.private');
    add('fix.siteData');
    elsewhere();
  } else if (kind === 'memory') {
    // (the message itself says to close other tabs and programs)
    if (/Firefox/.test(navigator.userAgent) && visitorOS() === 'windows') add('fix.firefox64');
    elsewhere();
  } else if (kind === 'network') {
    add('fix.connection');
  } else {
    add('fix.retry');
  }
  return out;
}
function fixList(kind, bytes) {
  return el('ul', { className: 'fixes' }, ...fixes(kind, bytes).map((f) => el('li', {},
    f.href ? el('a', { href: f.href, textContent: f.text }) : f.text)));
}
const currentRelease = fetch(new URL('../engine/current.json', import.meta.url))
  .then((r) => r.ok ? r.json() : null).catch(() => null);

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
//               el: its slot (<li>), cur: entry | null (the disc in use), pending: entry | null (being checked),
//               remembered: {rec, handle} | null (a disc from last time waiting for the browser's permission)}
// entry: {file, expect (the release it is checked against), via ('files' or null), got: {crc32, sha1, size}, pct,
//         worker, batch, from: {handle, converted} (where the file came from: remembered discs),
//         store: 'handle' | 'copy' | null (how it is remembered for next time)}
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

// A release this page knows but cannot use: its message names the supported releases of its slot (data/discs.json
// `instead`, tools/discs.py unsupported()); `soon` says its support is planned. [key, vars] for problem()/reject().
const NAMES_INSTEAD = new Set(['why.notYet', 'why.useInstead']);
function notUsable(r, game) {
  if (!r.instead || !r.instead.length) return ['why.unsupported', { release: `${gameName(game)} · ${releaseWords(r)}` }];
  const instead = new Intl.ListFormat(i18n.lang, { type: 'disjunction' }).format(r.instead);
  return [r.soon ? 'why.notYet' : 'why.useInstead', { release: r.title, instead }];
}

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
function startCheck(g, file, cands, info, batch, from = {}) {
  const same = (f) => sameFile(g.cur?.file, f) || sameFile(g.pending?.file, f) || g.queue.some((q) => sameFile(q.file, f));
  if (same(file)) return;                                                               // the same disc again: nothing
  if (g.pending && g.pending.batch !== batch) {
    problem(batch, file, 'why.stillChecking', { other: g.pending.file.name, game: gameName(g.id) });
    return;
  }
  if (g.pending) { hold(batch); g.queue.push({ file, cands, info, batch, from }); return; }
  const sizeMatch = cands.filter((c) => c.release.size === file.size);
  const entry = { file, expect: (sizeMatch[0] || cands.find((c) => c.supported) || cands[0]).release, via: null,
                  got: { size: file.size }, pct: 0, worker: null, batch, ended: false, from, store: null };
  g.pending = entry;
  g.remembered = null;
  dropNote(g.id);
  hold(batch);
  renderAll();
  const done = () => {
    if (g.pending === entry) g.pending = null;
    end(entry);
    const next = g.queue.shift();
    if (next) { startCheck(g, next.file, next.cands, next.info, next.batch, next.from); release(next.batch); }
    renderAll();
  };
  const accept = (via) => {
    if (g.pending !== entry) return;
    entry.via = via;
    g.cur = entry;
    if (g.id === 'us' && !building) { last = null; $('#build-done').dataset.ready = ''; }
    remembered(g, entry);
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
    if (m && !m.supported) return reject(...notUsable(m.release, g.id));
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

// × on a slot: its disc out (a check stopped), forgotten for next time too.
function remove(id) {
  const g = games.get(id);
  for (const q of g.queue.splice(0)) release(q.batch);
  if (g.pending) { const p = g.pending; g.pending = null; cancel(p); }
  g.cur = null;
  g.remembered = null;
  notes.delete(id);
  forget([id]);
  if (id === 'us' && !building) last = null;
  renderAll();
  $('#add-button').focus();      // (the slot has nothing to focus now)
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

// [{file, info, from}] of the images and cue sheets in `files` (one archive's parts, or one file), unpacking as
// needed. from: {handle (the file's, when the browser gave one: one file, not a split archive), converted}
async function expand(files, batch, depth = 0, from = { handle: null, converted: false }) {
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
    for (const f of r.files) out.push(...await expand([f], batch, depth + 1, { ...from, converted: true }));
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
    return expand([r.file], batch, depth + 1, { ...from, converted: true });
  }
  if (info.kind === 'chd') { problem(batch, file, 'why.chd'); return []; }
  if (info.kind === 'unsupported') {
    // one track of a disc with several (the audio of "Game (Track 2).bin"): its data is in track 1, with the .cue
    problem(batch, file, /\(track\s*\d+\)/i.test(file.name) ? 'why.track' : 'why.notImage');
    return [];
  }
  return [{ file, info, from }];
}

// Files given to the page (chosen or dropped): each to the game it is. items: File, or {file, handle} when the
// browser gave a handle to it (remembered for next time without a copy).
async function handleFiles(items) {
  const batch = newBatch();
  hold(batch);
  try {
    const list = items.map((x) => (x instanceof Blob ? { file: x, handle: null } : x));
    const handleOf = new Map(list.map((x) => [x.file, x.handle]));
    const found = [];
    for (const grp of groups(list.map((x) => x.file))) {
      found.push(...await expand(grp, batch, 0, { handle: grp.length === 1 ? handleOf.get(grp[0]) || null : null, converted: false }));
    }
    const images = found.filter((x) => x.info.kind === 'image').map((x) => x.file.name.toLowerCase());
    for (const { file, info, from } of found) {
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
        problem(batch, file, ...notUsable(cands[0].release, g.id), g.id);
        continue;
      }
      startCheck(g, file, cands, info, batch, from);
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
    // (a known release's message already names what works instead)
    if (p.game && !NAMES_INSTEAD.has(p.key)) li.append(el('span', { className: 'problem-works', textContent: i18n.t(`works.${p.game}`) }));
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
    const x = el('button', { type: 'button', className: 'disc-remove', textContent: '×' });
    x.addEventListener('click', () => remove(g.id));
    li.append(art, el('div', { className: 'slot-text' }, el('b', { className: 'slot-name', textContent: gameName(g.id) }),
                      el('small', { className: 'slot-purpose' })), x);
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
    // remembered: a disc from last time the browser has to allow again ("Use my discs from last time")
    const state = !e ? (g.remembered ? 'remembered' : 'empty') : busy ? 'busy' : 'ready';
    li.dataset.state = state;
    li.dataset.release = e ? e.expect.id : g.remembered ? g.remembered.rec.release : '';
    li.dataset.store = (!busy && e?.store) || '';
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
    check.hidden = state !== 'ready' && state !== 'remembered';
    check.textContent = state === 'remembered' ? '↺' : '✓';
    check.setAttribute('aria-label', t(state === 'remembered' ? 'slot.remembered' : 'disc.ok'));
    $('.slot-purpose', li).textContent = g.id === 'us' ? t('slot.purpose.us') : t('slot.purpose.source', { n: g.disc.species });
    const x = $('.disc-remove', li);
    x.hidden = state === 'empty';
    x.setAttribute('aria-label', t('disc.remove', { title: gameName(g.id) }));
  }
  renderSums();
  renderRemember();
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

// The file chooser: the browser's own picker where it has one (Chromium on a computer), which gives handles: the
// discs are then remembered for next time without a copy. Elsewhere the <input>.
function setupAdd() {
  const input = $('#add-input');
  $('#add-button').addEventListener('click', async () => {
    if (typeof window.showOpenFilePicker !== 'function') { input.click(); return; }
    let handles;
    try {
      handles = await window.showOpenFilePicker({ multiple: true, id: 'horizon-discs' });
    } catch (e) {
      if (e?.name !== 'AbortError') input.click();      // (a picker this page may not use: the plain chooser)
      return;
    }
    const items = [];
    for (const handle of handles) { try { items.push({ file: await handle.getFile(), handle }); } catch { /* gone already */ } }
    if (items.length) handleFiles(items);
  });
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
    // handles where the browser gives them (Chromium): asked for every item now, before any await (the items are
    // only readable during the event)
    const items = [...e.dataTransfer.items].filter((i) => i.kind === 'file');
    const files = items.map((i) => i.getAsFile());
    if (!items.length || typeof items[0].getAsFileSystemHandle !== 'function' || files.some((f) => !f)) {
      handleFiles([...e.dataTransfer.files]);
      return;
    }
    const handles = items.map((i) => { try { return i.getAsFileSystemHandle().catch(() => null); } catch { return null; } });
    Promise.all(handles).then((hs) => handleFiles(files.map((file, i) => ({ file, handle: hs[i]?.kind === 'file' ? hs[i] : null }))));
  });
}

// ---------------------------------------------------------------- remembered discs
//
// A returning player builds the new release without giving the discs again (js/remember.js keeps the records and
// the copies; web/README.md "Remembered discs"). Two ways, per disc:
//  - a handle (Chromium on a computer: the picker or a drop gives one): kept as soon as the disc is accepted, no copy.
//    Next time it may need the browser's permission again: one click on "Use my discs from last time".
//  - a copy in this browser's storage, only if the player asks for it (the option under the drop zone, with its
//    size): any browser with OPFS, not on phones and tablets. Also for a disc that came out of an archive, ECM or PBP
//    (its image is kept: a handle to an archive means unpacking it again).
// What was remembered is trusted only while the file is the one checked (name, size, date: sameFile) and this
// release still accepts that release; then it is not hashed again (the build still checks its files and the disc
// it writes). Anything else: that slot is empty again with one line saying why, the others stay.

const saved = new Map();     // game -> its record (IndexedDB's, as this page last wrote or read it)
const notes = new Map();     // game -> [key, vars]: why its disc from last time is not here
const KEEP = 'horizon.keepDiscs';
// supported: this browser can keep copies; on: the player asked for them; job: the copy running (game, pct);
// waiting: another tab builds or copies; note: [key, vars] of the last failure
// paused: "Build my disc" was pressed (no copy may take the lock before the build does)
const keep = { supported: false, on: false, job: null, game: null, pct: 0, waiting: false, note: null, pumping: false,
               paused: false };
const gb = (n) => new Intl.NumberFormat(i18n.lang, { minimumFractionDigits: 1, maximumFractionDigits: 1 }).format(n / 2 ** 30);
const keptBytes = () => [...saved.values()].filter((r) => r.kind === 'copy').reduce((a, r) => a + r.size, 0);
function setKeep(on) {
  keep.on = on;
  try { if (on) localStorage.setItem(KEEP, '1'); else localStorage.removeItem(KEEP); } catch { /* not kept */ }
}
function dropNote(id) { notes.delete(id); }

// The release a record was accepted as, if this page still accepts it: {release, supported} or null
function releaseOf(rec) {
  const all = [...discs.discs.map((d) => ({ release: d, game: d.id, supported: true })),
               ...discs.variants.map((v) => ({ release: v, game: v.game, supported: v.supported !== false }))];
  const c = all.find((x) => x.release.id === rec.release && x.game === rec.game);
  if (!c || !c.supported) return null;
  if (rec.via === 'files') return discs.files[c.release.id] ? c : null;
  return c.release.sha1 && c.release.sha1 === rec.image?.sha1 && (!c.release.crc32 || c.release.crc32 === rec.image.crc32) ? c : null;
}

const recordOf = (g, entry, extra) => ({
  game: g.id, release: entry.expect.id, via: entry.via || null, converted: false,
  image: { crc32: entry.got.crc32 || null, sha1: entry.got.sha1 || null, size: entry.file.size }, ...extra,
});

// A disc was accepted: its handle is remembered (if the browser gave one); otherwise what was remembered for its game
// is forgotten (a new disc replaces it) and, with the option on, it is copied.
async function remembered(g, entry) {
  entry.storing = true;
  try {
    if (keep.game === g.id) await stopCopy();
    const h = entry.from?.handle;
    if (h) {
      let file = entry.file;
      if (entry.from.converted) { try { file = await h.getFile(); } catch { file = null; } }   // (the archive's own)
      const rec = file && recordOf(g, entry, { kind: 'handle', handle: h, converted: !!entry.from.converted,
                                               name: file.name, size: file.size, lastModified: file.lastModified });
      if (rec && g.cur === entry && await store.put(rec)) {
        saved.set(g.id, rec);
        entry.store = 'handle';
        await store.removeCopies([g.id]);
        return;
      }
    }
    if (g.cur !== entry) return;
    saved.delete(g.id);
    await store.del(g.id);
    await store.removeCopies([g.id]);
  } finally {
    entry.storing = false;
    renderSlots();
    pumpCopies();
  }
}

// Forget these games' discs (null: all): their records and copies.
async function forget(ids = null) {
  if (keep.job && (!ids || ids.includes(keep.game))) await stopCopy();
  for (const id of ids || [...saved.keys()]) { saved.delete(id); await store.del(id); }
  if (!ids) await store.clear();
  await store.removeCopies(ids);
  renderRemember();
}

// A disc from last time that cannot be used: its slot empty, one line why, forgotten.
async function drop(g, key) {
  g.remembered = null;
  notes.set(g.id, [key, { game: gameName(g.id) }]);
  await forget([g.id]);
  renderAll();
}

// The page loads: the discs from last time into their slots (copies and handles the browser still allows), the
// ones waiting for permission shown as such.
async function restore() {
  keep.supported = await store.canCopy();
  try { keep.on = keep.supported && localStorage.getItem(KEEP) === '1'; } catch { keep.on = false; }
  for (const rec of await store.all()) {
    const g = games.get(rec.game);
    if (!g) { await store.del(rec.game); continue; }
    if (g.cur || g.pending) continue;                // a disc given meanwhile: it replaced this one
    saved.set(g.id, rec);
    if (!releaseOf(rec)) { await drop(g, 'remember.retired'); continue; }
    if (rec.kind === 'copy') {
      const file = await store.copyOf(rec);
      if (file) adopt(g, rec, file, null); else await drop(g, 'remember.evicted');
      continue;
    }
    const h = revive(rec.handle);
    if (!h) { await drop(g, 'remember.unreadable'); continue; }
    let perm = 'prompt';
    try { perm = await h.queryPermission({ mode: 'read' }); } catch { /* asked on the click */ }
    if (perm === 'granted') await openHandle(g, rec, h);
    else if (perm === 'denied') await drop(g, 'remember.denied');
    else { g.remembered = { rec, handle: h }; renderAll(); }
  }
  renderAll();
  await store.tidy();
  pumpCopies();
}

// A remembered handle the browser allows: the same file as last time goes into its slot unhashed; a file that
// changed (or an archive, converted again) is checked as if just added, and remembered again once usable.
async function openHandle(g, rec, h) {
  g.remembered = null;
  let file;
  try {
    file = await h.getFile();
  } catch (e) {
    const key = e?.name === 'NotFoundError' ? 'remember.gone'
      : e?.name === 'NotAllowedError' || e?.name === 'SecurityError' ? 'remember.denied' : 'remember.unreadable';
    return drop(g, key);
  }
  if (g.cur || g.pending) return;
  if (rec.converted || !sameFile(rec, file)) {
    saved.delete(g.id);
    await store.del(g.id);
    handleFiles([{ file, handle: h }]);
    return;
  }
  adopt(g, rec, file, h);
}

// A disc from last time into its slot as checked (its checksums from the record). One checked by the files the
// import reads has them read again: a later release may check more files.
function adopt(g, rec, file, handle) {
  if (g.cur || g.pending) return;
  const { release: expect } = releaseOf(rec);
  const entry = { file, expect, via: rec.via, got: { ...rec.image }, pct: 100, worker: null, batch: null, ended: true,
                  from: { handle, converted: false }, store: rec.kind };
  g.remembered = null;
  if (rec.via !== 'files') { g.cur = entry; renderAll(); return; }
  Object.assign(entry, { pct: 0, byFiles: true });
  g.pending = entry;
  renderAll();
  checkFiles(file, discs.files[expect.id], (p) => { entry.pct = Math.floor(p * 100); renderSlots(); })
    .then((res) => (res.bad.length + res.missing.length ? 'remember.retired' : null), () => 'remember.unreadable')
    .then((why) => {
      if (g.pending !== entry) return;
      g.pending = null;
      if (why) drop(g, why); else { g.cur = entry; renderAll(); }
    });
}

// "Use my discs from last time": the browser's permission for each, one after another in this click. A browser
// that allows one prompt per click leaves the rest waiting, and the button stays for them.
async function useRemembered() {
  for (const g of games.values()) {
    const r = g.remembered;
    if (!r) continue;
    let perm;
    try { perm = await r.handle.requestPermission({ mode: 'read' }); } catch { break; }
    if (perm === 'granted') await openHandle(g, r.rec, r.handle);
    else if (perm === 'denied') await drop(g, 'remember.denied');
    else break;                                      // (the prompt closed: the rest wait)
  }
  renderAll();
}

// A disc to copy: accepted, not being checked or remembered, not a copy already, not a handle to the image itself.
const wanted = (g) => g.cur && !g.pending && !g.cur.storing && g.cur.store !== 'copy'
  && !(g.cur.store === 'handle' && !g.cur.from?.converted);

// The copies the player asked for, one after another, when no build runs (here or in another tab: the lock). Room is
// checked first: the copies and a build after them must fit, or nothing is copied.
async function pumpCopies() {
  if (!keep.on || keep.job || keep.pumping || building || keep.paused) return;
  keep.pumping = true;
  let again = false;
  try {
    const want = [...games.values()].filter(wanted);
    if (!want.length) { keep.waiting = false; return; }
    const need = want.reduce((a, g) => a + g.cur.file.size, 0);
    const free = await store.free();
    if (free != null && free < need + await buildRoom()) {
      keep.note = ['remember.noRoom', { gb: gb(need) }];
      setKeep(false);
      return;
    }
    if (!keep.on || building || keep.paused) return;
    const g = want[0], entry = g.cur;
    if (!wanted(g)) return;
    keep.game = g.id;
    keep.pct = 0;
    keep.job = store.copy(g.id, entry.file, (p) => { keep.pct = Math.floor(p * 100); renderRemember(); });
    renderRemember();
    const out = await keep.job.done;
    keep.job = null;
    keep.game = null;
    keep.waiting = !!out.busy;
    if (out.busy) { setTimeout(pumpCopies, 3000); return; }
    if (out.stopped) return;                         // (a build, a forget: copied later if still wanted)
    again = true;
    if (out.error) {
      console.warn('keeping', g.id, out.error);
      keep.note = out.quota ? ['remember.noRoom', { gb: gb(need) }] : ['remember.failed', {}];
      setKeep(false);
      return;
    }
    const rec = recordOf(g, entry, { kind: 'copy', name: entry.file.name, size: entry.file.size });
    const file = await store.copyOf(rec);
    if (!file || g.cur !== entry || !keep.on || !await store.put({ ...rec, lastModified: file.lastModified })) {
      await store.removeCopies([g.id]);              // (replaced, removed or turned off meanwhile)
    } else {
      saved.set(g.id, { ...rec, lastModified: file.lastModified });
      entry.store = 'copy';
      entry.file = file;                             // (an archive's image no longer held in memory)
    }
  } finally {
    keep.pumping = false;
    renderSlots();
  }
  if (again) pumpCopies();                          // the next disc
}

async function stopCopy() {
  const job = keep.job;
  if (!job) return;
  job.stop();
  await job.done.catch(() => {});
}

function setupRemember() {
  $('#remember-use').addEventListener('click', useRemembered);
  $('#remember-forget').addEventListener('click', async () => {
    await forget(null);
    setKeep(false);
    notes.clear();
    for (const g of games.values()) {
      g.remembered = null;
      if (g.cur?.store === 'copy') g.cur = null;     // (its file is gone)
      else if (g.cur) g.cur.store = null;
    }
    renderAll();
  });
  $('#remember-keep').addEventListener('change', async (e) => {
    if (e.target.checked) {
      store.persist();                               // (asked during the click: Firefox shows its prompt)
      keep.note = null;
      setKeep(true);
      pumpCopies();
    } else {
      setKeep(false);
      const ids = [...saved.values()].filter((r) => r.kind === 'copy').map((r) => r.game);
      await stopCopy();
      await forget(ids);
      for (const g of games.values()) if (g.cur?.store === 'copy') g.cur = null;
    }
    renderAll();
  });
}

function renderRemember() {
  const t = i18n.t;
  const waiting = [...games.values()].filter((g) => g.remembered && !g.cur && !g.pending);
  $('#remember-ask').hidden = !waiting.length;
  $('#remember-ask-text').textContent = t('remember.ask', { list: listOf(waiting.map((g) => gameName(g.id))) });
  const want = keep.supported ? [...games.values()].filter(wanted) : [];
  const kept = keptBytes();
  const row = $('#remember-keep-row');
  row.hidden = !keep.supported || !(keep.on ? kept || want.length || keep.job : want.length);
  $('#remember-keep').checked = keep.on;
  $('#remember-keep').disabled = !!building;
  $('#remember-keep-text').textContent = t('remember.keep', { gb: gb(kept + want.reduce((a, g) => a + g.cur.file.size, 0)) });
  const line = $('#remember-line');
  line.textContent = keep.job ? t('remember.copying', { game: gameName(keep.game), pct: keep.pct })
    : keep.waiting ? t('remember.otherTab') : keep.note ? t(keep.note[0], keep.note[1]) : '';
  line.hidden = !line.textContent;
  const status = $('#remember-status');
  status.hidden = !saved.size || !!keep.job;
  $('#remember-status-text').textContent = t(kept ? 'remember.keptCopies' : 'remember.kept', { gb: gb(kept) });
  $('#remember-forget').disabled = !!building;
  $('#remember-notes').replaceChildren(...[...notes.values()].map(([k, v]) => el('li', { textContent: t(k, v) })));
  $('#remember').hidden = $('#remember-ask').hidden && row.hidden && line.hidden && status.hidden && !notes.size;
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
  renderWarning(ready);
  renderBuild();
}

// Before a build: is there room for it in this browser? Asked once the four discs are ready (js/engine/engine.js
// checkRoom; it makes a file of the build's size for a moment, so not for every visitor), and said under the button
// with what to do. The button stays: the browser may be wrong, and the build asks again before it starts.
let room = null;          // {need, reason, free} of the last check
let roomAsked = false;
async function askRoom() {
  if (roomAsked) return;
  roomAsked = true;
  try {
    const need = await buildRoom();
    const q = new URLSearchParams(location.search);
    room = await checkRoom(need, TEST && Number(q.get('room')) || need);
  } catch { room = null; }
  renderPatch();
}
function renderWarning(ready) {
  const box = $('#patch-warning');
  const t = i18n.t;
  let line = null, kind = null;
  if (ready && !building) {
    if (!roomAsked) askRoom();
    const vars = { gb: gb(room?.need || 0) };
    if (room?.reason === 'quota') [line, kind] = [t('patch.lowSpace', vars), 'storage'];
    else if (room?.reason === 'unkept') [line, kind] = [t('patch.private', vars), 'private'];
    else if (room?.reason === 'blocked') [line, kind] = [t('engine.storageBlocked'), 'blocked'];
    else if (isMobile()) [line, kind] = [t('patch.phone'), 'phone'];
  }
  box.hidden = !line;
  if (!line) { box.replaceChildren(); return; }
  box.dataset.kind = kind;
  box.replaceChildren(el('p', { textContent: line }), ...(kind === 'phone' ? [] : [fixList(kind, room?.need)]));
}

async function patch() {
  if (building || !patchState()[1]) return;
  store.persist();                                   // (asked during the click: storage the browser should not evict)
  keep.paused = true;                                // (the build needs the lock a copy holds: copied again after)
  keep.waiting = false;
  await stopCopy();
  if (building || !patchState()[1]) { keep.paused = false; pumpCopies(); return; }
  $('#build-done').dataset.ready = '';
  const q = new URLSearchParams(location.search);
  const opts = { onState: (st) => { last = st; renderBuild(); } };
  if (TEST && q.get('workers')) opts.workers = Number(q.get('workers'));
  // the other three games (their files are read and checked by the engine's extractor)
  const others = [...games.values()].filter((g) => g.id !== 'us');
  building = new Build({ us: games.get('us').cur.file, sources: Object.fromEntries(others.map((g) => [g.id, g.cur.file])),
                         titles: Object.fromEntries(others.map((g) => [g.id, g.cur.expect.title])) }, opts);
  if (TEST && q.get('oom')) building.oomTest = q.get('oom');
  if (TEST && q.get('quota')) building.quotaTest = q.get('quota');
  if (TEST && q.get('room')) building.roomTest = Number(q.get('room'));
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
    keep.paused = false;
    renderAll();
    store.tidy().then(pumpCopies);
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
    err.textContent = errorText(st.error);
    supportHelp(err, st.error.key);
    const own = !['build.cancelled', 'engine.otherTab'].includes(st.error.key) && !SUPPORT_DETAILS[st.error.key];
    if (own) err.append(fixList(st.error.kind, st.error.vars?.bytes));
    // the error's own text and the browser line (the log's first: browser, cores, memory, workers), open
    if (st.error.detail) errorDetails(err, [st.error.detail, st.log[0]].filter(Boolean).join('\n\n'));
    if (st.error.key !== 'build.cancelled') err.append(copyReport(st));
  }
  $('#build-log').textContent = st.log.join('\n');
  // the build's log open once the build stops on an error, at its last lines (the player may close it again)
  if (st.phase === 'error' && !st.logShown) {
    st.logShown = true;
    $('.build-log').open = true;
    $('#build-log').scrollTop = $('#build-log').scrollHeight;
  }
  // a device this slow (a phone): a computer does it in minutes
  const slow = $('#build-slow');
  slow.hidden = !busy || !(st.eta > 3600 && st.elapsed > 60);
  if (!slow.hidden) slow.replaceChildren(t('build.slow'), ' ', ...(hasDesktop() ? [el('a', { href: '#desktop', textContent: t('fix.desktop') })] : []));
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
  renderChangelog();
  mapLabels();
  digimonLabels();
  renderDesktop();
}

async function start() {
  [discs, features] = await Promise.all([
    fetch('data/discs.json').then((r) => r.json()),
    fetch('content/features.json').then((r) => r.json()),
  ]);
  await i18n.init();
  indexReleases();
  for (const d of discs.discs) games.set(d.id, { id: d.id, disc: d, el: null, cur: null, pending: null, queue: [], remembered: null });
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
  setupRemember();
  renderAll();
  setupChangelog(currentRelease).catch(() => { $('#changelog').hidden = true; });
  setupDesktop(currentRelease, LINKS.github).catch((e) => console.warn('desktop apps:', e));
  setupMaps().catch(() => { $('#maps').hidden = true; });
  setupDigimon().catch(() => { $('#digimon').hidden = true; });
  tidyStorage().catch(() => {});   // what a stopped or crashed build left, the old engines
  restore().catch((e) => console.warn('remembered discs:', e));
}

start();

// ---------------------------------------------------------------- release version

// The line under "Create my disc", "v0.1.0 · 27 Oct 2026": the release the engine builds (engine/current.json, written by web/build-engine.sh
// from the release's manifest; tools/version.py), its date in the page's language. Nothing without an engine.
(async () => {
  const el = $('#release');
  let cur;
  try {
    cur = await currentRelease;
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
