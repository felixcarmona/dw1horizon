// The Digimon list and evolution guide: text only, no pictures. content/digimon.json comes from tools/site_digimon.py,
// which holds what each field means. One group per level. The rows are made once per language and kept.
import { i18n, tag } from './i18n.js';

const LEVELS = ['fresh', 'in-training', 'rookie', 'champion', 'ultimate', 'mega'];
const STATS = ['hp', 'mp', 'offense', 'defense', 'speed', 'brain'];
let guide, view, list, count, levels, search;
let byId = new Map(), rows = new Map(), level = '';

const el = (name, className, ...kids) => {
  const e = document.createElement(name);
  if (className) e.className = className;
  e.append(...kids);
  return e;
};
const t = i18n.t;
// Upper or lower case, spaces and hyphens do not matter: "were garu" finds WereGarurumon.
const fold = (s) => s.toLowerCase().replace(/[^\p{L}\p{N}]/gu, '');
const range = (v) => (v.length === 1 ? `${v[0]}+` : v[0] === v[1] ? `${v[0]}` : t('digimon.range', { lo: v[0], hi: v[1] }));
// the game keeps happiness as -100..100 and shows players 0..100
const happinessShown = (v) => Math.trunc((v + 100) / 2);
const links = (ids) => ids.flatMap((id, i) => {
  const a = el('button', 'digi-link', byId.get(id).name);
  a.type = 'button';
  a.dataset.id = id;
  return i ? [', ', a] : [a];
});

const newChip = (x) => (x.new ? [el('span', 'tag tag-new', t('digimon.new'))] : []);

function row(x) {
  if (rows.has(x.id)) return rows.get(x.id);
  const b = el('button', 'digi-card', el('span', 'digi-name', x.name), ...newChip(x));
  b.type = 'button';
  b.dataset.id = x.id;
  const li = el('li', '', b);
  rows.set(x.id, li);
  return li;
}

function group(l, xs) {
  return el('div', 'digi-group', el('h3', '', t(`digimon.level.${l}`), el('span', 'digi-group-count', `${xs.length}`)),
            el('ul', 'digi-cards', ...xs.map(row)));
}

function fill() {
  const q = fold(search.value);
  const found = guide.digimon.filter((x) => (!level || x.level === level) && fold(x.name).includes(q));
  list.replaceChildren(...LEVELS.flatMap((l) => {
    const xs = found.filter((x) => x.level === l);
    return xs.length ? [group(l, xs)] : [];
  }));
  count.textContent = found.length ? t('digimon.count', { n: found.length }) : t('digimon.none');
}

function chips() {
  levels.replaceChildren(...['', ...LEVELS].map((l) => {
    const b = el('button', 'digi-chip', t(l ? `digimon.level.${l}` : 'digimon.allLevels'));
    b.type = 'button';
    b.dataset.level = l;
    b.setAttribute('aria-pressed', l === level);
    return b;
  }));
}

function line(label, ...value) {
  return [el('dt', '', label), el('dd', '', ...value)];
}

// The rows of the in-game guide's card, in its order.
function requirements(x) {
  const q = x.req;
  const any = t('digimon.any');
  const box = el('div', 'digi-req', el('h4', '', t('digimon.need', { name: x.name, pass: guide.pass, of: 4 })));
  const stats = q.top
    ? line(t('digimon.stats'), t('digimon.top', {
      stats: new Intl.ListFormat(tag(i18n.lang), { type: 'disjunction' }).format(q.top.map((k) => t(`digimon.stat.${k}`))),
    }))
    : q.stats
      ? line(t('digimon.statsAll'), STATS.filter((k) => q.stats[k]).map((k) => `${t(`digimon.stat.${k}`)} ${range(q.stats[k])}`).join(', '))
      : line(t('digimon.stats'), any);
  const b = q.bonus;
  const bonus = !b ? line(t('digimon.bonus'), any) : line(t('digimon.bonusOne'), el('ul', '',
    ...(b.from ? [el('li', '', `${t('digimon.comingFrom')} `, ...links([b.from]))] : []),
    ...['discipline', 'happiness', 'battles', 'techs'].filter((k) => b[k]).map((k) => el('li', '', `${t(`digimon.${k}`)} ${range(k === 'happiness' ? b[k].map(happinessShown) : b[k])}`))));
  if (q.after) box.append(el('p', 'digi-after', t('digimon.after', { hours: q.after })));
  box.append(el('dl', '',
    ...line(t('digimon.mistakes'), q.mistakes ? range(q.mistakes) : any),
    ...line(t('digimon.weight'), range(q.weight)), ...stats, ...bonus));
  return box;
}

function show(id) {
  const x = byId.get(id);
  const from = x.from.length ? links(x.from) : [t(x.level === 'fresh' ? 'digimon.hatches' : 'digimon.noRoute')];
  const to = x.to.length ? links(x.to) : [t('digimon.noNext')];
  const body = view.querySelector('.digi-body');
  body.replaceChildren(
    el('h3', '', x.name),
    el('p', 'digi-kind', `${t(`digimon.level.${x.level}`)} `, ...newChip(x), ' ', el('span', `tag tag-${x.attribute}`, t(`digimon.attr.${x.attribute}`))),
    el('div', 'digi-part', el('h4', '', t('digimon.from')), el('p', '', ...from)),
    el('div', 'digi-part', el('h4', '', t('digimon.to')), el('p', '', ...to)));
  if (x.req === 'automatic') body.append(el('p', 'digi-part', t('digimon.automatic')));
  else if (x.req) body.append(requirements(x));
  if (x.techniques.length) body.append(el('div', 'digi-part', el('h4', '', t('digimon.techniques')), el('p', '', x.techniques.join(', '))));
  view.scrollTop = 0;
  body.focus({ preventScroll: true });
}

export async function setupDigimon() {
  guide = await (await fetch('content/digimon.json')).json();
  byId = new Map(guide.digimon.map((x) => [x.id, x]));
  const section = document.querySelector('#digimon');
  view = section.querySelector('#digi-view');
  list = section.querySelector('#digi-list');
  count = section.querySelector('#digi-count');
  levels = section.querySelector('#digi-levels');
  search = section.querySelector('#digi-search');
  // the group headings stick under the tools, whatever height the tools take in this language
  const tools = section.querySelector('.digi-tools');
  new ResizeObserver(() => section.style.setProperty('--tools', `${tools.offsetHeight}px`)).observe(tools);
  search.addEventListener('input', fill);
  levels.addEventListener('click', (e) => {
    const b = e.target.closest('.digi-chip');
    if (!b) return;
    level = b.dataset.level;
    for (const c of levels.children) c.setAttribute('aria-pressed', c === b);
    fill();
  });
  const open = (e) => {
    const b = e.target.closest('[data-id]');
    if (!b) return;
    if (!view.open) view.showModal();
    show(Number(b.dataset.id));
  };
  list.addEventListener('click', open);
  view.addEventListener('click', (e) => { if (e.target === view) view.close(); else open(e); });
  view.querySelector('.digi-close').addEventListener('click', () => view.close());
  const openGuide = () => { if (!section.open) section.showModal(); };
  document.querySelector('#open-guide').addEventListener('click', openGuide);
  section.querySelector('.digi-guide-close').addEventListener('click', () => section.close());
  section.addEventListener('close', () => { if (location.hash === '#digimon') history.replaceState(null, '', location.pathname); });
  addEventListener('hashchange', () => { if (location.hash === '#digimon') openGuide(); });
  if (location.hash === '#digimon') openGuide();
  labels();
}

// What follows the page's language.
export function labels() {
  if (!guide) return;
  rows = new Map();
  document.querySelector('#digi-lead').textContent = t('digimon.lead', { n: guide.digimon.length });
  search.placeholder = t('digimon.search');
  search.setAttribute('aria-label', t('digimon.search'));
  chips();
  fill();
}
