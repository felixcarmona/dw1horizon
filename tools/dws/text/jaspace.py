#!/usr/bin/env python3
"""Spaces in Japanese dialogue: the ones that break a word ("あ るよ") are errors; and rows that start with a mark.

  python3 tools/dws/text/jaspace.py [--write] [--show N]

Line breaking (kinsoku, layout.NO_ROW_START): no row starts with 、。，．！？」』）ー or a small kana. The compiler's wrap
keeps to it (layout.kinsoku); for the hand-paged rows of the banks this tool pulls the marks back onto the row above when
it still fits (the font b row, the last-row limit for every row: safe in any place of the box), else carries the row
above's last letter down. The text audit reports a row that still starts with one.

Japanese does not space its words, so a space between two of its letters shows as a gap in the middle of a word. They
came in with machine rewrites that joined the rows of a page with a space and wrapped the text again letter by letter
(textbank.fit did the same at build time until it learnt join_rows). The rule, for every row of text/ja/dialogue/*.json
and the other Japanese dialogue banks:

  stray (removed):
    - a space between two kana or kanji (ー included): "あ るよ", "青リン ゴ", "問題 ありません";
    - a space after a Latin letter or digit before a kana or kanji: "HPとMP が", "2 倍";
    - a space before 、。！？ and a space after 、;
  kept:
    - a space after 。！？ (the text's sentence spacing, as the original's full-width space after ！？) and around "...";
    - a space between Latin words, numbers and references ({partner}), before a Latin word or number ("グレード D",
      "トレーニング x5") and after a speaker's name row;
    - a space in front of a sign's direction (東: 西: 南: 北:), which separates the sign's destinations;
    - every space of a laid-out box, whose spaces separate fields: the boxes of MAPHEAD tables and the cup notices
      (profiles.UNPACKED_KEYS: "8名 参加自由", "はい いいえ") and the boxes the story sizes itself (set_textbox_size:
      the fishing and digging instructions, Shell News), and of a few names kept spaced on purpose (KEPT).
names.json (the executable's menus) is laid out with spaces and is not touched.
Without --write it prints how many rows change and --show N of them. The text audit (tools/localize/check.py) and the
text bank (textbank.load_source) report a stray space as an error."""
import argparse, functools, glob, json, os, re, sys
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, os.path.join(ROOT, 'tools'))
from dws.text.profiles import base_dws, header_row, packed_key      # noqa: E402
from dws.text.layout import kinsoku, starts_badly      # noqa: E402

J = '぀-ヿ㐀-鿿'                           # kana (ー and ・ included) and kanji
SP = '[ 　]+'
STRAY = re.compile(rf'(?<=[{J}]){SP}(?=[{J}])|(?<=[A-Za-z0-9]){SP}(?=[{J}])|{SP}(?=[、。！？])|(?<=、){SP}')
SIGN = re.compile('[東西南北]:')                             # a space before a sign's next direction
KEPT = ('かみなりと かぜカップ',)                             # the cup's name in kana, spaced as two words


@functools.lru_cache(None)
def sized_keys(root=ROOT):
    """The keys the story shows in a box it sizes itself (set_textbox_size, then show_textbox(text("key"))), with the
    box's width."""
    pattern = re.compile(r'set_textbox_size\([^,]+,\s*(\d+),\s*\d+\);\s*show_textbox\(text\("([^"]+)"\)\)')
    return {k: min(240, int(cols) * 12 + 8)                 # -> {key: the box's width in pixels}
            for text in base_dws(root).values() for cols, k in pattern.findall(text)}


def laid_out(key):
    """A key whose spaces separate fields: none of them is stray."""
    key = re.sub(r'^s000\.sec(\d+)\.', r'm\1.', key)          # s000.sec1238.u15: MAPHEAD's m1238.u15 in script 0
    return not packed_key(key) or key in sized_keys()


def stray_spaces(key, row):
    """The stray spaces of a Japanese row -> [match]: none for a row without Japanese or a laid-out key."""
    if laid_out(key) or not re.search(f'[{J}]', row):
        return []
    kept = [(m.start(), m.end()) for k in KEPT for m in re.finditer(re.escape(k), row)]
    return [m for m in STRAY.finditer(re.sub(r'\{[^}]*\}', lambda e: '\x00' * len(e.group()), row))
            if not SIGN.match(row, m.end()) and not any(a <= m.start() < b for a, b in kept)]


def clean(key, row):
    for m in reversed(stray_spaces(key, row)):
        row = row[:m.start()] + row[m.end():]
    return row


def rewrap(rows, ok):
    """Rows broken again letter by letter (escapes and Latin words whole) where they fit, with kinsoku."""
    from dws.text.layout import break_rows
    from dws.textbank import join_rows
    return break_rows(join_rows(rows), ok)


def mend_rows(key, value):
    """A value's hand-paged rows with kinsoku: within each page and across pages (a page's first row of text that starts
    with a mark). Laid-out keys and strings (the compiler wraps them) stay. Needs BE.FONT set (font b)."""
    from dws import backend as BE
    if isinstance(value, str):
        return value
    fields = laid_out(key)                                  # a laid-out box: marks moved, its rows never broken again
    flat = all(isinstance(x, str) for x in value)
    pages = [list(value)] if flat else [list(p) for p in value]
    from dws.textbank import _named
    above = 1 if key in _named() else 0                     # a named speaker's box: its name takes the first row
    heads = [1 if not above and p and header_row(p[0]) else 0 for p in pages]   # (under a name a coloured row is text)
    width = sized_keys().get(re.sub(r'^s000\.sec(\d+)\.', r'm\1.', key))
    def both(r):                                            # a laid-out box: its rows are kept for the original font too
        from dws.text.repage import set_font
        saved = dict(BE.FONT); set_font('original')
        try: return BE.fits(r, False, packed_key(key)) and (width is None or BE.text_px(r) <= width)
        finally: BE.FONT.clear(); BE.FONT.update(saved)
    def fit_at(first):                                      # rows from box row `first`: the box's 4th row is the last
        if fields:
            return lambda r, i: BE.fits(r, False, packed_key(key)) and (width is None or BE.text_px(r) <= width) and both(r)
        return lambda r, i: BE.fits(r, first + i >= 3, packed_key(key))
    for j, p in enumerate(pages):
        h = heads[j]
        ok = fit_at(above + h)
        p[h:] = kinsoku(p[h:], ok)
        if not fields and any(starts_badly(r) for r in p[h + 1:]):
            again = rewrap(p[h:], ok)            # no mark fits back, no letter fits down: the page's rows broken again
            if len(again) <= len(p) - h and not any(starts_badly(r) for r in again[1:]):
                p[h:] = again
        if j and len(p) > h and starts_badly(p[h]) and len(pages[j - 1]) > heads[j - 1]:
            prev = pages[j - 1]
            two = kinsoku([prev[-1], p[h]], lambda r, i: fit_at(above + len(prev) - 1)(r, 0) if i == 0 else ok(r, 0))
            prev[-1] = two[0]
            if len(two) == 1: del p[h]
            else: p[h] = two[1]
    pages = [p for p in pages if p]
    if not fields and any(starts_badly(r) for p, h in zip(pages, heads) for r in p[h:][1 if p is pages[0] else 0:]) and \
            len({p[0] if h else None for p, h in zip(pages, heads)}) == 1:
        # full rows on both sides of the mark: the entry (one speaker) is broken again into pages of the rows its box has
        h = heads[0]
        rows = rewrap([r for p in pages for r in p[h:]], fit_at(above + h))
        per = 4 - above - h
        new = [pages[0][:h] + rows[i:i + per] for i in range(0, len(rows), per)]
        single = re.match(r'^(m\d+|s000\.sec\d+)\.', key) is not None       # a MAPHEAD table's line: its pages are counted
        if len(new) <= len(pages) + (0 if single else 1) and not any(starts_badly(r) for p in new for r in p[h + 1:]) \
                and all(fit_at(above + h)(r, i) for p in new for i, r in enumerate(p[h:])):
            pages = new
    return pages[0] if flat and len(pages) == 1 else pages


def problems(key, value):
    """['stray space in "...": ...'] for a value (a string, rows or pages)."""
    rows = [value] if isinstance(value, str) else [r for x in value for r in ([x] if isinstance(x, str) else x)]
    return [f'stray space in the middle of Japanese text: "{r[max(0, m.start() - 6):m.end() + 6]}"'
            for r in rows for m in stray_spaces(key, r)]


def kinsoku_problems(key, value):
    """['row starts with a mark: ...'] for the hand-paged rows of a value: every row of text but
    the entry's first (an utterance may open with "！！"); a speaker's name row is not text."""
    from dws.textbank import _named
    if isinstance(value, str):
        return []
    pages = [value] if all(isinstance(x, str) for x in value) else value
    named = key in _named()
    rows = [r for p in pages for r in (p[1:] if not named and p and header_row(p[0]) else p)]
    if not any(re.search(f'[{J}]', r) for r in rows):
        return []
    return [f'a Japanese row starts with a mark it may not start with (kinsoku): "{r[:12]}"' for r in rows[1:]
            if starts_badly(r)]


def banks(root=ROOT):
    """The Japanese dialogue banks: text/ja/dialogue/*.json, text/ja.json and the mods' text/ja.json."""
    return sorted(glob.glob(os.path.join(root, 'text', 'ja', 'dialogue', '*.json'))) + \
        [p for p in [os.path.join(root, 'text', 'ja.json')] if os.path.exists(p)] + \
        sorted(glob.glob(os.path.join(root, 'story', 'mods', '*', 'text', 'ja.json')))


def main(argv):
    from dws.text.repage import dump
    ap = argparse.ArgumentParser()
    ap.add_argument('--write', action='store_true')
    ap.add_argument('--show', type=int, default=0)
    a = ap.parse_args(argv)
    from dws.text.repage import set_font
    set_font('b')
    rows = keys = shown = 0
    for f in banks():
        raw = open(f, encoding='utf-8').read()
        d = json.loads(raw)
        style = next((st for st in ('compact', 'indent') if dump(d, st).rstrip('\n') == raw.rstrip('\n')), None)
        dirty = False
        for k, v in d.items():
            if k.startswith('_') or not isinstance(v, (str, list)): continue
            fix = (lambda r: clean(k, r))
            new = fix(v) if isinstance(v, str) else [fix(x) if isinstance(x, str) else [fix(r) for r in x] for x in v]
            while True:                                     # (a letter carried down can leave another mark to move)
                again = mend_rows(k, new)
                if again == new: break
                new = again
            if new == v: continue
            keys += 1
            flat = lambda x: [x] if isinstance(x, str) else [r for y in x for r in flat(y)]
            for x, y in zip(flat(v), flat(new)):
                if x != y:
                    rows += 1
                    if shown < a.show:
                        shown += 1; print(f'{os.path.relpath(f, ROOT)} {k}:\n  was {x}\n  now {y}')
            d[k] = new; dirty = True
        if dirty and a.write:
            if style is None:
                print(f'{os.path.relpath(f, ROOT)}: an unknown layout, left as it is'); continue
            open(f, 'w', encoding='utf-8').write(dump(d, style).rstrip('\n') + raw[len(raw.rstrip('\n')):])
    print(f'{rows} rows of {keys} entries have stray spaces or start with a mark' + (', mended' if a.write else ' (dry run)'))


if __name__ == '__main__':
    main(sys.argv[1:])
