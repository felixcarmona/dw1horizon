// The page's languages: the same eight the game's language option offers (tools/languages.py CODES). Strings live in
// i18n/<lang>.json, every one with en.json's keys (web/test/i18n.mjs checks); a string missing from one falls back
// to English. Elements name theirs with data-i18n="key" (text) or data-i18n-attr="attr:key" (an attribute). The
// choice is remembered per browser; the first visit follows the browser's languages (the first one the page has,
// by full tag, then by its language alone: pt-PT -> pt-br), else English.

export const LANGS = ['en', 'es', 'pt-br', 'fr', 'de', 'it', 'ja', 'ca'];
// Each language by its own name (the menu, the languages line): fixed, as Intl.DisplayNames lowercases some.
export const NAMES = {
  en: 'English', es: 'Español', 'pt-br': 'Português (Brasil)', fr: 'Français', de: 'Deutsch', it: 'Italiano',
  ja: '日本語', ca: 'Català',
};
// The BCP 47 tag of each (the html lang, Intl's locales).
export const tag = (lang) => lang.replace(/-(\w+)$/, (m, r) => `-${r.toUpperCase()}`);
const KEY = 'horizon.lang';

function remembered() {
  try { return localStorage.getItem(KEY); } catch { return null; }
}

export function guess(saved = remembered(), wanted = navigator.languages || [navigator.language]) {
  if (LANGS.includes(saved)) return saved;
  const tags = wanted.filter(Boolean).map((l) => l.toLowerCase());
  for (const l of tags) {
    if (LANGS.includes(l)) return l;
    const base = LANGS.find((c) => c.split('-')[0] === l.split('-')[0]);
    if (base) return base;
  }
  return 'en';
}

const cache = {};
async function load(lang) {
  cache[lang] ||= fetch(`i18n/${lang}.json`).then((r) => (r.ok ? r.json() : {})).catch(() => ({}));
  return cache[lang];
}

export const i18n = {
  lang: 'en',
  strings: {},

  async init() {
    await this.set(guess(), false);
  },

  async set(lang, remember = true) {
    if (!LANGS.includes(lang)) lang = 'en';
    const [en, own] = await Promise.all([load('en'), load(lang)]);
    this.strings = { ...en, ...own };
    this.lang = lang;
    document.documentElement.lang = tag(lang);
    if (remember) try { localStorage.setItem(KEY, lang); } catch { /* private mode: not remembered */ }
  },

  t: (key, vars) => {
    const s = i18n.strings[key] ?? key;
    return vars ? s.replace(/\{(\w+)\}/g, (m, k) => (vars[k] ?? m)) : s;
  },

  apply(root) {
    for (const el of root.querySelectorAll('[data-i18n]')) el.textContent = this.t(el.dataset.i18n);
    for (const el of root.querySelectorAll('[data-i18n-attr]')) {
      const [attr, key] = el.dataset.i18nAttr.split(':');
      el.setAttribute(attr, this.t(key));
    }
  },
};
