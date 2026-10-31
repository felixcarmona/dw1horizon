// The flag drawn in the language menu for each page language (js/i18n.js LANGS). A flag stands for the language, not
// for one country: Spanish gets Spain's, Portuguese Brazil's, English the Union Jack. Inline SVG, so it looks the same
// everywhere (flag emoji draw as two letters on Windows).
const svg = (box, body, fit = 'none') => `<svg viewBox="${box}" preserveAspectRatio="${fit}" width="100%" height="100%">${body}</svg>`;
const bars = (n, colours, vertical = true) => colours.map((c, i) => vertical
  ? `<rect x="${i}" width="1" height="${n}" fill="${c}"/>` : `<rect y="${i}" width="${n}" height="1" fill="${c}"/>`).join('');

export const FLAGS = {
  en: svg('0 0 60 30', '<clipPath id="fl-s"><path d="M0,0v30h60v-30z"/></clipPath><clipPath id="fl-t"><path d="M30,15h30v15zv15h-30zh-30v-15zv-15h30z"/></clipPath>'
    + '<g clip-path="url(#fl-s)"><path d="M0,0v30h60v-30z" fill="#012169"/><path d="M0,0L60,30M60,0L0,30" stroke="#fff" stroke-width="6"/>'
    + '<path d="M0,0L60,30M60,0L0,30" clip-path="url(#fl-t)" stroke="#C8102E" stroke-width="4"/><path d="M30,0v30M0,15h60" stroke="#fff" stroke-width="10"/>'
    + '<path d="M30,0v30M0,15h60" stroke="#C8102E" stroke-width="6"/></g>', 'xMidYMid slice'),
  es: svg('0 0 3 4', '<rect width="3" height="4" fill="#AA151B"/><rect y="1" width="3" height="2" fill="#F1BF00"/>'),
  'pt-br': svg('0 0 20 14', '<rect width="20" height="14" fill="#009B3A"/><path d="M10 1.2L18.2 7 10 12.8 1.8 7z" fill="#FEDF00"/><circle cx="10" cy="7" r="3.4" fill="#002776"/>'),
  fr: svg('0 0 3 2', bars(2, ['#002395', '#fff', '#ED2939'])),
  de: svg('0 0 3 3', bars(3, ['#000', '#DD0000', '#FFCE00'], false)),
  it: svg('0 0 3 2', bars(2, ['#009246', '#fff', '#CE2B37'])),
  ja: svg('0 0 3 2', '<rect width="3" height="2" fill="#fff"/><circle cx="1.5" cy="1" r=".6" fill="#BC002D"/>'),
  ca: svg('0 0 9 9', '<rect width="9" height="9" fill="#FCDD09"/>' + [1, 3, 5, 7].map((y) => `<rect y="${y}" width="9" height="1" fill="#DA121A"/>`).join('')),
};
