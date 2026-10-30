#!/usr/bin/env python3
"""The Spanish fan translation's font: which glyphs it redrew, and what each one draws.

    python3 tools/dws/text/esglyphs.py check ES JP          every redrawn glyph has a row in the table (exit 1 if not)
    python3 tools/dws/text/esglyphs.py sheet ES JP OUTDIR   PNG sheets of the redrawn glyphs, JP beside ES (OpenCV draws review sheets)

ES and JP are a disc image (raw 2352 or 2048), an extracted disc directory, or the executable itself (SLPS_017.97).

The `es-fan` disc (docs/reference/text-sources.md, 1.3 and 1.5) keeps the Japanese engine and its 992-glyph
fixed-width font (12x11, CHAR_TO_GLYPH_TABLE and GLYPH_DATA in decomp/config/jp/symbols.txt), and redraws about 400 of
the glyph slots: the Latin letters and digits restyled, accented letters and punctuation on kana slots, and two- to
four-letter tiles ("ci", "ón", "Dis") on kanji slots. It also edits the code table: the lowercase letters move to the
last 26 slots (8281-829A in order; the Japanese font had the pad buttons on 8281-8284), their old slots are blanked
(FFFF), the pad buttons move to four kanji codes, and 20 kanji codes are dropped. Its text therefore cannot be decoded
with a code page.

docs/data/es-fan-glyphs.csv says what each redrawn or added glyph draws: code (4 hex digits), text, kind (letter: a
plain letter or digit restyled; accent; punct; tile; button, as the US font's ○ × □ △; symbol; blank)
and an optional note. A tile's text is the letters it draws; where a letter straddles two cells it is given to the cell
that holds most of it, so a run of tiles concatenates to the word. A text may keep a space a cell draws as a gap
(" a ", "e "). Two-row tiles (two lines of small capitals in one block of cells) put the block's reading, top row then
bottom row, on its first cell and leave the others empty.

`load()` gives the extractor {code: text}; `decode()` turns the bytes of a string into Unicode: a code with a row gives
its text, any other code is cp932 then NFKC (the space 8140, and the Japanese text the translation left untouched).
Control units (00-1C) are the caller's business.

The table describes a font, not the game's text; the glyph bitmaps themselves are read from the player's discs and are
never committed.
"""

# Allow both direct script execution and package imports.
import sys as _image_sys
from pathlib import Path as _ImagePath
_image_sys.path.insert(0, str(next(p for p in _ImagePath(__file__).resolve().parents if (p / 'tools').is_dir())))
import csv, os, struct, sys, unicodedata

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, os.path.join(ROOT, 'tools'))
CSV = os.path.join(ROOT, 'docs', 'data', 'es-fan-glyphs.csv')
EXE = 'SLPS_017.97'
CHAR_TO_GLYPH_TABLE = 0x80128578   # decomp/config/jp/symbols.txt
GLYPH_DATA = 0x80128D38
NUM_GLYPHS, GLYPH_W, GLYPH_H = 992, 12, 11
KINDS = ('letter', 'accent', 'punct', 'tile', 'button', 'symbol', 'blank')   # letter: a plain letter or digit redrawn


def read_exe(path):
    """The executable's bytes, from an image, an extracted directory or the file itself."""
    if os.path.isdir(path):
        path = os.path.join(path, EXE)
    with open(path, 'rb') as f:
        head = f.read(8)
    if head == b'PS-X EXE':
        return open(path, 'rb').read()
    import discs
    b = discs.Image(discs.image_of(path)).find(EXE)
    if b is None:
        raise SystemExit(f'{path}: no {EXE} in this image')
    return b


def _at(exe, addr):
    return addr - struct.unpack_from('<I', exe, 0x18)[0] + 0x800


def font(exe):
    """(codes, glyphs): the glyph index -> 2-byte code table (the last entry is the search sentinel) and the glyph
    bitmaps, 11 rows of u16 each, bit 15 the leftmost of the 12 pixels, a clear bit ink and a set bit background."""
    codes = list(struct.unpack_from(f'<{NUM_GLYPHS}H', exe, _at(exe, CHAR_TO_GLYPH_TABLE)))
    o = _at(exe, GLYPH_DATA)
    glyphs = [struct.unpack_from(f'<{GLYPH_H}H', exe, o + i * GLYPH_H * 2) for i in range(NUM_GLYPHS)]
    return codes, glyphs


def _first(codes, glyphs):
    """{code: (index, bitmap)} of what the engine draws for each code: its search is linear, the first entry wins."""
    m = {}
    for i, c in enumerate(codes[:-1]):
        if c != 0xFFFF:
            m.setdefault(c, (i, glyphs[i]))
    return m


def redrawn(es, jp):
    """Compare the fonts code by code. Returns (diff, gone): diff is [(code, es index, jp index or None)] of every
    code whose ES glyph differs from the JP glyph of the same code, or that the JP table does not have; gone is the
    JP codes the ES table dropped (they draw the sentinel glyph). The translation did edit the code table: it moved
    the lowercase letters into the last 26 kanji slots (8281-829A in order), blanked their old slots (FFFF) and
    dropped 20 kanji."""
    me, mj = _first(*font(es)), _first(*font(jp))
    diff = [(c, i, mj[c][0] if c in mj else None) for c, (i, g) in sorted(me.items(), key=lambda t: t[1][0])
            if c not in mj or mj[c][1] != g]
    return diff, sorted(c for c in mj if c not in me)


def load(path=CSV):
    """{code: text} of every row of the table."""
    with open(path, newline='', encoding='utf-8') as f:
        return {int(r['code'], 16): r['text'] for r in csv.DictReader(f)}


def decode(data, table=None):
    """Bytes of the es-fan text (2-byte codes; ASCII and control bytes pass through) -> Unicode."""
    table = load() if table is None else table
    out = []; i = 0
    while i < len(data):
        b = data[i]
        if b >= 0x80 and i + 1 < len(data):
            c = b << 8 | data[i + 1]; i += 2
            if c in table:
                out.append(table[c])
            else:
                try:
                    out.append(unicodedata.normalize('NFKC', bytes((c >> 8, c & 0xFF)).decode('cp932')))
                except UnicodeDecodeError:
                    out.append(f'{{{c:04X}}}')
        else:
            out.append(chr(b)); i += 1
    return ''.join(out)


def rows(path=CSV):
    with open(path, newline='', encoding='utf-8') as f:
        return list(csv.DictReader(f))


def check(es_path, jp_path):
    es, jp = read_exe(es_path), read_exe(jp_path)
    diff, gone = redrawn(es, jp)
    table = rows(); have = {}
    bad = 0
    for r in table:
        if r['kind'] not in KINDS:
            print(f"{r['code']}: unknown kind {r['kind']!r}"); bad += 1
        if r['code'] != r['code'].upper() or len(r['code']) != 4:
            print(f"{r['code']}: code is not 4 upper-case hex digits"); bad += 1
        c = int(r['code'], 16)
        if c in have:
            print(f"{r['code']}: two rows"); bad += 1
        have[c] = r
    missing = [c for c, _, _ in diff if c not in have]
    for c in missing:
        print(f'{c:04X}: redrawn, no row')
    codes = set(font(es)[0])
    for c in have:
        if c not in codes:
            print(f'{c:04X}: row for a code the font has no glyph for'); bad += 1
    print(f'{len(diff)} codes redrawn or added ({sum(j is None for _, _, j in diff)} added), {len(gone)} JP codes '
          f'dropped, {len(table)} rows, {len(missing)} redrawn glyphs without a row, {bad} bad rows')
    return 1 if missing or bad else 0


def sheet(es_path, jp_path, out, per=48, scale=6):
    from tools.image import Image, ImageDraw, ImageFont
    es, jp = read_exe(es_path), read_exe(jp_path)
    diff, _ = redrawn(es, jp)
    ge, gj = font(es)[1], font(jp)[1]
    try:
        label = ImageFont.truetype('DejaVuSansMono.ttf', 18)
    except OSError:
        label = ImageFont.load_default()
    known = {}
    if os.path.exists(CSV):
        known = {int(r['code'], 16): r['text'] for r in rows()}
    os.makedirs(out, exist_ok=True)
    gw, gh = GLYPH_W * scale, GLYPH_H * scale
    cols = 6; cell_w, cell_h = 2 * gw + 150, gh + 16
    paths = []
    for s in range(0, len(diff), per):
        part = diff[s:s + per]; nrows = (len(part) + cols - 1) // cols
        img = Image.new('RGB', (cols * cell_w, nrows * cell_h), 'white'); d = ImageDraw.Draw(img)
        for k, (code, i, j) in enumerate(part):
            x0, y0 = (k % cols) * cell_w, (k // cols) * cell_h
            d.text((x0 + 4, y0 + 8), f'{code:04X}', fill='black', font=label)
            if code in known:
                d.text((x0 + 4, y0 + 34), known[code], fill='blue', font=label)
            for n, (g, ink, bg) in enumerate(((gj[j] if j is not None else (0xFFFF,) * GLYPH_H, (150, 150, 150), (245, 245, 245)),
                                              (ge[i], (0, 0, 0), (255, 255, 210)))):
                gx = x0 + 70 + n * (gw + 6)
                d.rectangle([gx, y0 + 4, gx + gw - 1, y0 + 4 + gh - 1], fill=bg)
                for y, row in enumerate(g):
                    for x in range(GLYPH_W):
                        if not row & (0x8000 >> x):   # a clear bit is ink
                            d.rectangle([gx + x * scale, y0 + 4 + y * scale, gx + (x + 1) * scale - 1,
                                         y0 + 4 + (y + 1) * scale - 1], fill=ink)
        p = os.path.join(out, f'es-glyphs-{s // per + 1:02d}.png'); img.save(p); paths.append(p)
        print(p)
    print(f'{len(diff)} glyphs on {len(paths)} sheets in {out}')


def main(argv):
    if len(argv) >= 3 and argv[0] == 'check':
        return check(argv[1], argv[2])
    if len(argv) >= 4 and argv[0] == 'sheet':
        return sheet(argv[1], argv[2], argv[3])
    print(__doc__.split('\n\n')[1]); return 2


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
