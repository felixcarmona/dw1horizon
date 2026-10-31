// The "What's new" section: one card per entry of content/features.json (its `_doc` says the fields), rendered in
// the page's language. Media: a still (`image`), a short silent loop (`video`: MP4 + optional WebM, a poster; it
// plays muted, looped, inline, only while on screen, and never when the visitor prefers reduced motion, where the
// poster stands in) or a side by side (`compare`: one clip or image with the two halves labelled, twice as wide).
// Long videos (`controls: true`) use native controls and manual playback, including under reduced motion.
// Their metadata is fetched only near the viewport; playback fetches the rest.

const reducedMotion = matchMedia('(prefers-reduced-motion: reduce)');

let observer = null;
function watch(video) {
  observer ||= new IntersectionObserver((entries) => {
    for (const e of entries) {
      const v = e.target;
      if (e.isIntersecting) {
        if (!v.dataset.loaded) { v.dataset.loaded = '1'; if (v.controls && !v.dataset.autoplay) v.preload = 'metadata'; v.load(); }
        if (!v.controls || v.dataset.autoplay) v.play().catch(() => {});
      } else if (!v.paused) v.pause();
    }
  }, { rootMargin: '160px 0px' });
  observer.observe(video);
}

// A field of a media entry may differ per language ({en, es, ...}: the same line in Spanish on the Spanish page); a
// language it does not have gets the English one.
const pick = (v, lang) => (v && typeof v === 'object' ? (v[lang] || v.en) : v);

function mediaElement(m, lang) {
  const alt = pick(m.alt, lang) || '';
  const src = pick(m.src, lang), poster = pick(m.poster, lang), webm = pick(m.webm, lang);
  const aspect = m.type === 'compare' ? '8 / 3' : (m.aspect || '4 / 3');
  let el;
  if (src.endsWith('.mp4') && (m.controls || !reducedMotion.matches)) {
    el = document.createElement('video');
    Object.assign(el, { muted: true, loop: !m.controls || Boolean(m.autoplay), controls: Boolean(m.controls), playsInline: true, preload: 'none', autoplay: false, disablePictureInPicture: true });
    el.setAttribute('muted', '');          // the attribute is what lets autoplay through on iOS
    el.setAttribute('playsinline', '');
    if (poster) el.poster = poster;
    el.setAttribute('aria-label', alt);
    if (webm) {
      const s = document.createElement('source'); s.src = webm; s.type = 'video/webm'; el.append(s);
    }
    const s = document.createElement('source'); s.src = src; s.type = 'video/mp4'; el.append(s);
    if (!m.controls) el.addEventListener('click', () => { if (el.paused) el.play().catch(() => {}); else el.pause(); });
    if (m.autoplay && !reducedMotion.matches) el.dataset.autoplay = '1';   // starts by itself while on screen
    watch(el);
  } else {
    el = document.createElement('img');
    el.src = src.endsWith('.mp4') ? poster : src;
    el.alt = alt;
    el.loading = 'lazy';
    el.decoding = 'async';
    if (m.width && m.height) { el.width = m.width; el.height = m.height; }
  }
  el.style.aspectRatio = aspect;
  if (m.pixelated) el.classList.add('pixelated');
  const fig = document.createElement('figure');
  fig.className = 'feature-media' + (m.type === 'compare' ? ' compare' : '');
  fig.append(el);
  return fig;
}

// A run of ordinary cards between two wide ones (or the list's ends) fills its rows: six grid columns, a wide card
// spans them all, a run of two cards gets two halves, a run of three (or more) thirds, so the order stays as
// written and no row is left with a hole.
function spans(features) {
  const wide = (f) => f.wide || f.media.some((m) => m.type === 'compare');
  const out = [];
  let run = [];
  const flush = () => {
    const n = run.length;
    run.forEach((i, k) => { out[i] = n === 1 ? 'wide' : n === 2 ? 'half' : (n % 3 === 2 && k >= n - 2) ? 'half' : 'third'; });
    run = [];
  };
  features.forEach((f, i) => { if (wide(f)) { flush(); out[i] = 'wide'; } else run.push(i); });
  flush();
  return out;
}

// {n} and {languages} in a card's text: how many languages the released disc plays in, and their names in the
// page's language ("English and Spanish", "inglés y español").
function filler(lang, languages) {
  const loc = lang.replace(/-(\w+)$/, (m, r) => `-${r.toUpperCase()}`);
  let named;
  try { named = new Intl.DisplayNames([loc], { type: 'language' }); } catch { named = null; }
  const names = languages.map((l) => named?.of(l.replace(/-(\w+)$/, (m, r) => `-${r.toUpperCase()}`)) || l);
  const vars = { n: languages.length, languages: new Intl.ListFormat(loc, { type: 'conjunction' }).format(names) };
  return (s) => s.replace(/\{(\w+)\}/g, (m, k) => (vars[k] ?? m));
}

export function renderFeatureList(list, data, lang, languages = ['en']) {
  list.replaceChildren();
  const features = data.features.filter((f) => !f.hidden);
  const span = spans(features);
  const fill = filler(lang, languages);
  features.forEach((f, i) => {
    const own = f[lang] || f.en;
    const text = { title: fill(own.title), body: fill(own.body) };
    const art = document.createElement('article');
    art.className = 'feature ' + span[i] + (f.media.length ? ' has-media' : '');
    art.id = `feature-${f.id}`;
    for (const m of f.media) art.append(mediaElement(m, lang));
    const body = document.createElement('div');
    body.className = 'feature-text';
    const h = document.createElement('h3');
    h.textContent = text.title;
    const p = document.createElement('p');
    p.textContent = text.body;
    body.append(h, p);
    art.append(body);
    list.append(art);
  });
  if (data.more?.items?.length) {
    const more = document.createElement('section');
    more.className = 'feature-more';
    const h = document.createElement('h3');
    h.textContent = pick(data.more.title, lang);
    const ul = document.createElement('ul');
    for (const item of data.more.items) ul.append(Object.assign(document.createElement('li'), { textContent: fill(pick(item, lang)) }));
    more.append(h, ul);
    list.append(more);
  }
  if (data.note) {
    const note = document.createElement('p');
    note.className = 'feature-note';
    note.textContent = data.note[lang] || data.note.en;
    list.append(note);
  }
}
