// Player-facing release history. Loading failures stay separate from the patcher.
import { i18n, tag } from './i18n.js';

export const versionParts = (version) => /^v?\d+\.\d+\.\d+$/.test(version || '')
  ? version.replace(/^v/, '').split('.').map(Number) : null;

export function compareVersions(a, b) {
  const x = versionParts(a), y = versionParts(b);
  for (let i = 0; i < 3; i++) if (x[i] !== y[i]) return x[i] > y[i] ? 1 : -1;
  return 0;
}

export function releasedVersions(versions, releaseTag) {
  return versionParts(releaseTag) ? versions.filter((v) => compareVersions(v.version, releaseTag) <= 0) : versions;
}

let entries = null;
export async function setupChangelog(currentRelease) {
  const [data, current] = await Promise.all([
    fetch('content/changelog.json').then((r) => { if (!r.ok) throw new Error('changelog unavailable'); return r.json(); }),
    currentRelease,
  ]);
  entries = releasedVersions(data.versions, current?.release_tag);
  renderChangelog();
}

export function renderChangelog() {
  if (!entries) return;
  const section = document.querySelector('#changelog'), list = document.querySelector('#changelog-list');
  const make = (name, text) => Object.assign(document.createElement(name), { textContent: text });
  list.replaceChildren();
  entries.forEach((entry, index) => {
    const own = entry[i18n.lang] || entry.en;
    const details = document.createElement('details');
    details.className = 'changelog-version';
    details.open = index === 0;
    const summary = make('summary', `v${entry.version}`);
    const date = make('time', new Intl.DateTimeFormat(tag(i18n.lang),
      { day: 'numeric', month: 'long', year: 'numeric', timeZone: 'UTC' }).format(new Date(`${entry.date}T00:00:00Z`)));
    date.dateTime = entry.date;
    summary.append(date);
    details.append(summary);
    for (const group of ['new', 'changed', 'fixed']) {
      if (!own[group]?.length) continue;
      const bullets = document.createElement('ul');
      for (const bullet of own[group]) bullets.append(make('li', bullet));
      details.append(make('h3', i18n.t(`changelog.${group}`)), bullets);
    }
    if (own.upgrade) {
      const upgrade = make('p', own.upgrade);
      upgrade.className = 'changelog-upgrade';
      details.append(upgrade);
    }
    list.append(details);
  });
  section.hidden = entries.length === 0;
}
