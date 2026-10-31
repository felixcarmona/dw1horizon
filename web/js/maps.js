// The new maps: a carousel of thumbnails, and each map at full size in a viewer. content/maps.json holds each map's size,
// media/maps/map-NN.jpg and .png come from the release's horizon-maps.tar.gz. Only art made for Horizon goes here,
// no maps from the disc, no characters, no names and no count: one picture of a place, the best of its states.
import { i18n } from './i18n.js';

export async function setupMaps() {
  const sizes = await (await fetch('content/maps.json')).json();
  const grid = document.querySelector('#map-grid'), view = document.querySelector('#map-view');
  const full = view.querySelector('img');
  const file = (i, ext) => `media/maps/map-${String(i + 1).padStart(2, '0')}.${ext}`;
  let at = 0;

  function show(i) {
    at = (i + sizes.length) % sizes.length;
    full.width = sizes[at][0];
    full.height = sizes[at][1];
    full.src = file(at, 'jpg');          // the thumbnail stands in until the full picture has arrived
    const big = new Image();
    big.onload = () => { if (big.src.endsWith(file(at, 'png'))) full.src = big.src; };
    big.src = file(at, 'png');
    for (const near of [at - 1, at + 1]) new Image().src = file((near + sizes.length) % sizes.length, 'png');
  }

  grid.replaceChildren(...sizes.map((_, i) => {
    const b = document.createElement('button');
    b.type = 'button';
    b.className = 'map-tile';
    const img = Object.assign(new Image(), { loading: 'lazy', src: file(i, 'jpg'), width: 480, height: 400, alt: '' });
    b.append(img);
    b.addEventListener('click', () => { show(i); view.showModal(); });
    return b;
  }));
  const slide = (way) => grid.scrollBy({ left: way * grid.clientWidth * .85, behavior: 'smooth' });
  document.querySelector('.map-back').addEventListener('click', () => slide(-1));
  document.querySelector('.map-forward').addEventListener('click', () => slide(1));
  const more = document.createElement('p');
  more.className = 'map-more';
  more.dataset.i18n = 'maps.more';
  more.textContent = i18n.t('maps.more');
  grid.append(more);
  const back = document.querySelector('.map-back'), forward = document.querySelector('.map-forward');
  const arrows = () => {
    back.hidden = grid.scrollLeft < 8;
    forward.hidden = grid.scrollLeft + grid.clientWidth > grid.scrollWidth - 8;
  };
  grid.addEventListener('scroll', arrows, { passive: true });
  arrows();
  view.querySelector('.map-close').addEventListener('click', () => view.close());
  view.querySelector('.map-prev').addEventListener('click', () => show(at - 1));
  view.querySelector('.map-next').addEventListener('click', () => show(at + 1));
  view.addEventListener('click', (e) => { if (e.target === view) view.close(); });
  view.addEventListener('keydown', (e) => {
    if (e.key === 'ArrowLeft') show(at - 1);
    if (e.key === 'ArrowRight') show(at + 1);
  });
  let startX = null;
  view.addEventListener('touchstart', (e) => { startX = e.touches[0].clientX; }, { passive: true });
  view.addEventListener('touchend', (e) => {
    const moved = e.changedTouches[0].clientX - startX;
    if (Math.abs(moved) > 50) show(at + (moved < 0 ? 1 : -1));
  }, { passive: true });
  labels();
}

// The tiles' names follow the page's language.
export function labels() {
  document.querySelectorAll('.map-tile').forEach((b, i) => b.setAttribute('aria-label', i18n.t('maps.open', { n: i + 1 })));
}
