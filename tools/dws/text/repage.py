#!/usr/bin/env python3
"""Re-page the hand-paged dialogue of a text source for a font placed to the pixel (docs/mods/font.md "Fonts").

  python3 tools/dws/text/repage.py [ours] [--font b] [--write] [--show N]

A value given as pages of rows (text/<source>/dialogue/*.json) keeps its rows as written; they were broken for the
original font (31 units a row), so with font b (62 bytes and 240 px a row) most rows are short. An entry is re-paged
only when it is wrapped prose: every row break inside a page was forced (the next word would not have fitted the row in
the original font) and no row is a list item, a speaker line, a heading or empty. Then:
  - a page break is kept when the page ends a sentence (. ! ? … ~ or a closing quote) or was not full: a deliberate
    pause; a full page that stops mid-sentence is joined to the next (the break was forced);
  - each page's text is wrapped again with the font (the last row of a page 228 px, clear of the "next" button), as
    many rows a page as the entry had; a page that needs more becomes several.
Words and punctuation are never changed. Without --write it prints how many entries change and --show N examples.
"""
import argparse, glob, json, os, re, sys
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, os.path.join(ROOT, 'tools'))
from dws import backend as BE      # noqa: E402

END = re.compile(r'[.!?…~]["\'’”)]*$|[.!?…]+ *\)?$')


def set_font(name):
    BE.FONT.update({'extra': name != 'original', 'glyphs': len(BE.EXTRA_ORDER), 'chars': frozenset(BE.EXTRA_ORDER),
                    'of': f'font {name}', 'stripped': set(), 'name': name})


def fits_in(font, row):
    old = dict(BE.FONT); set_font(font)
    try: return BE.fits(row)
    finally: BE.FONT.clear(); BE.FONT.update(old)


def is_prose(pages):
    rows = [r for p in pages for r in p]
    if len(rows) < 2: return False
    for r in rows:
        s = r.strip()
        if not s or s.startswith(('-', '*', '•')) or s.endswith(':') or '{color 7}' in s or '{tab' in s or '{pos' in s \
                or '{raw' in s or r != r.strip():
            return False
    for p in pages:                      # every break inside a page was forced in the original font
        for a, b in zip(p, p[1:]):
            first = b.split(' ')[0]
            if fits_in('original', a + ' ' + first):
                return False
    return True


def repage(pages, font):
    per = max(len(p) for p in pages)
    groups, cur = [], []
    for i, p in enumerate(pages):
        cur += p
        last = i == len(pages) - 1
        if last or END.search(p[-1].rstrip()) or len(p) < per:
            groups.append(' '.join(cur)); cur = []
    set_font(font)
    out = []
    for text in groups:
        for page in BE.wrap(text, per):
            out.append(page)
    return out


def dump(d, style):
    """The file as the text tools write it: one entry a line (compact) or json.dumps(indent=1) (indent)."""
    if style == 'indent':
        return json.dumps(d, ensure_ascii=False, indent=1) + '\n'
    return '{\n' + ',\n'.join(' ' + json.dumps(k, ensure_ascii=False) + ': ' + json.dumps(v, ensure_ascii=False)
                              for k, v in d.items()) + '\n}\n'


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument('source', nargs='?', default='ours')
    ap.add_argument('--font', default='b', choices=('a', 'b'))
    ap.add_argument('--write', action='store_true')
    ap.add_argument('--show', type=int, default=0)
    a = ap.parse_args(argv)
    changed = shown = total = 0
    for f in sorted(glob.glob(os.path.join(ROOT, 'text', a.source, 'dialogue', '*.json'))):
        raw = open(f, encoding='utf-8').read()
        d = json.loads(raw)
        style = next((st for st in ('compact', 'indent') if dump(d, st).rstrip('\n') == raw.rstrip('\n')), None)
        ending = raw[len(raw.rstrip('\n')):]
        if style is None:
            print(f'{os.path.basename(f)}: an unknown layout, left as it is'); continue
        dirty = False
        for k, v in d.items():
            if k.startswith('_') or not isinstance(v, list) or not v: continue
            pages = [v] if all(isinstance(x, str) for x in v) else v
            if not all(isinstance(p, list) and p and all(isinstance(r, str) for r in p) for p in pages): continue
            total += 1
            if not is_prose(pages) or not BE.packed_key(k): continue    # boxes 1-3 keep 31 units a row
            new = repage(pages, a.font)
            if new == pages: continue
            changed += 1
            if shown < a.show:
                shown += 1
                print(f'{os.path.basename(f)} {k}:\n  was ' + json.dumps(pages, ensure_ascii=False) + '\n  now '
                      + json.dumps(new, ensure_ascii=False))
            d[k] = new[0] if (len(new) == 1 and all(isinstance(x, str) for x in v)) else new
            dirty = True
        if dirty and a.write:
            open(f, 'w', encoding='utf-8').write(dump(d, style).rstrip('\n') + ending)
    print(f'{changed} of {total} hand-paged entries re-paged for font {a.font}' + ('' if a.write else ' (dry run)'))


if __name__ == '__main__':
    main(sys.argv[1:])
