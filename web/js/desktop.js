// "Prefer an app?": the desktop patcher, Horizon Patcher, for Windows and macOS, at the end of the patcher section.
// Shown only when engine/current.json has `desktop` (tools/release_pages.py writes it at deployment from the release's
// horizon-desktop.json, after checking both zips are there: the links never point at a missing file) and the page
// knows its repository. The visitor's system first and highlighted; Linux gets the browser builder and dwpatch.py;
// phones only a line saying the apps are for computers.
import { i18n, tag } from './i18n.js';
import { isMobile } from './engine/engine.js';

const OS = { windows: 'Windows', macos: 'macOS' };
let data = null;   // {cur, repo}

// The visitor's system from the user agent ("Windows NT", "Macintosh"; an iPad that says Macintosh has touch).
export function visitorOS(ua = navigator.userAgent, touch = navigator.maxTouchPoints || 0) {
  if (isMobile() || /Android|iPhone|iPad/i.test(ua) || (/Macintosh/.test(ua) && touch > 1)) return 'phone';
  if (/Windows/.test(ua)) return 'windows';
  if (/Macintosh|Mac OS X/.test(ua)) return 'macos';
  if (/Linux|X11|CrOS/.test(ua)) return 'linux';
  return 'other';
}

export async function setupDesktop(currentRelease, repo) {
  const cur = await currentRelease;
  if (!repo || !cur?.release_tag || !cur.desktop?.windows || !cur.desktop?.macos) return;
  data = { cur, repo };
  renderDesktop();
}

const el = (name, props = {}, ...kids) => { const e = Object.assign(document.createElement(name), props); e.append(...kids); return e; };
const link = (href, text) => el('a', { href, textContent: text, target: '_blank', rel: 'noopener' });
// A translated string with one {link} in it, made into text and the link.
const withLink = (key, a) => {
  const [before, after = ''] = i18n.t(key).split('{link}');
  return [before, a, after];
};

// Made again only when the language changes (renderAll runs on every disc change; open details stay open).
export function renderDesktop() {
  if (!data || data.lang === i18n.lang) return;
  data.lang = i18n.lang;
  const { cur, repo } = data, { desktop } = cur;
  const box = document.querySelector('#desktop');
  const os = visitorOS();
  box.dataset.os = os;
  const order = os === 'macos' ? ['macos', 'windows'] : ['windows', 'macos'];
  const guide = `${repo}/blob/main/docs/release/README-players.md`;
  const mb = (bytes) => new Intl.NumberFormat(tag(i18n.lang), { maximumFractionDigits: 0 }).format(bytes / 1048576);

  const buttons = document.querySelector('#desktop-buttons');
  buttons.replaceChildren(...order.map((id) => el('a', {
    className: `button has-version ${id === os ? 'primary' : 'outline'}`,
    href: `${repo}/releases/download/${cur.release_tag}/${desktop[id].name}`,
  }, el('span', { textContent: i18n.t('desktop.download', { os: OS[id] }) }),
     el('small', { className: 'release', textContent: `${cur.release_tag} · ${mb(desktop[id].size)} MB` }))));
  buttons.querySelectorAll('a').forEach((a, i) => { a.dataset.os = order[i]; });

  document.querySelector('#desktop-linux').replaceChildren(...withLink('desktop.linux', link(`${guide}#bring-your-own-disc`, 'dwpatch.py')));
  document.querySelector('#desktop-linux').hidden = os !== 'linux';
  document.querySelector('#desktop-phone').hidden = os !== 'phone';

  // The first start, per system: the visitor's first.
  const steps = {
    windows: ['desktop.win1', 'desktop.win2', 'desktop.win3'],
    macos: desktop.macos.notarized ? ['desktop.mac1', 'desktop.macNotarized'] : ['desktop.mac1', 'desktop.mac2', 'desktop.mac3'],
  };
  const help = document.querySelector('#desktop-help');
  const open = new Set([...help.querySelectorAll('details[open]')].map((d) => d.dataset.os));
  help.replaceChildren(...order.map((id) => {
    const list = el('ol', {}, ...steps[id].map((key) => el('li', { innerHTML: strong(i18n.t(key)) })));
    const body = [list];
    if (id === 'macos' && !desktop.macos.notarized) body.push(el('p', {}, ...withLink('desktop.macMore', link(`${guide}#the-desktop-app`, i18n.t('desktop.guide')))));
    const details = el('details', { className: 'desktop-os', open: open.has(id) },
      el('summary', { textContent: i18n.t(id === 'windows' ? 'desktop.firstWindows' : 'desktop.firstMac') }), ...body);
    details.dataset.os = id;
    return details;
  }));

  // Why it is safe: where it is built, the policy, the checksums.
  const built = desktop.run || `${repo}/blob/${cur.release_tag}/.github/workflows/desktop.yml`;
  const unsigned = !desktop.windows.signed || !desktop.macos.notarized;
  const why = document.querySelector('#desktop-why-body');
  why.replaceChildren(
    el('p', {}, i18n.t('desktop.safe', { tag: cur.release_tag }), ' ',
       link(built, i18n.t('desktop.buildLog')), ' · ', link(`${repo}/blob/main/docs/code-signing-policy.md`, i18n.t('desktop.policy'))),
    ...(unsigned ? [el('p', { textContent: i18n.t('desktop.unsigned') })] : []),
    el('p', { textContent: i18n.t('desktop.check') }),
    el('ul', { className: 'desktop-sums' }, ...order.map((id) => el('li', {}, el('b', { textContent: desktop[id].name }),
      el('code', { textContent: desktop[id].sha256, translate: false })))),
    el('p', {}, link(`${repo}/releases/tag/${cur.release_tag}`, i18n.t('desktop.allFiles'))),
  );
  box.hidden = false;
}

// **text** in a string: the button or menu names the player looks for. Everything else stays text.
function strong(s) {
  const esc = s.replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
  return esc.replace(/\*\*(.+?)\*\*/g, '<b>$1</b>');
}
