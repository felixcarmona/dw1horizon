#!/usr/bin/env python3
"""Extra font glyphs for the mod executable: one text file, three outputs.

Usage:
  fontgen.py header OUT.h            C table for the mods branch (src/main/font_extra.h)
  fontgen.py preview "TEXT" OUT.png  renders TEXT the way drawGlyph does (3x, nearest)
  fontgen.py sheet OUT.png           every extra glyph next to its base letter
  fontgen.py list                    code, character and width of each extra glyph
  fontgen.py condensed-header OUT.h  C table of the long names' condensed lowercase (src/main/font_condensed.h)
  fontgen.py fit "NAME" OUT.png      NAME drawn vanilla, tight and condensed (font.c drawStringMode), with widths
  fontgen.py glyphs EXE_DIR          how many extra glyphs a built executable has (its .elf, else its worktree's header)
  fontgen.py font-header a|b OUT.h   the glyph tables of a font placed to the pixel (src/main/font_a.h, font_b.h)
  fontgen.py font-sheet a|b OUT.png  every glyph of the font between neighbours, sample lines, at 1x and 4x
  fontgen.py preview "TEXT" OUT.png --font a|b   TEXT as that executable draws it (to the pixel, with the shadow)
  fontgen.py original-metrics [OUT.json]  the original font's numbers from the USA executable (extracted/SLUS_010.32),
                                     default tools/font/original-metrics.json (committed; regenerate it with this)

The glyphs are drawn in tools/font/extra.txt (format at the top of that file).
tools/dws/bytecode/__main__.py and dws (tools/dws/backend.py) read the same file for the character -> code mapping and
the widths, so adding a glyph is: draw it there, run `fontgen.py header`, rebuild
the mod executable. docs/mods/font.md has the details.

Two sources for the original font's 79 glyphs. Measuring text (metrics, text_width: what dws, bytecode and
tools/localize/executable/bank.py use while the mod is built) needs only numbers, committed in tools/font/original-metrics.json: the
CHAR_TO_GLYPH_TABLE codes, each glyph's cell width and the columns its ink spans. Drawing (font-header, font-sheet,
preview, fit, render_font) needs the bitmaps, which only the player's disc has: those read the USA executable
(extracted/SLUS_010.32) and are developer tasks. rule: the build measures from the committed numbers, never the disc.
"""

# Allow both direct script execution and package imports.
import sys as _image_sys
from pathlib import Path as _ImagePath
_image_sys.path.insert(0, str(next(p for p in _ImagePath(__file__).resolve().parents if (p / 'tools').is_dir())))
import json, os, re, struct, sys, unicodedata

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXTRA = os.environ.get('FONT_EXTRA') or os.path.join(ROOT, 'tools/font/extra.txt')
EXE = os.path.join(ROOT, 'extracted/SLUS_010.32')
ORIGINAL_METRICS = os.path.join(ROOT, 'tools/font/original-metrics.json')
EXE_BASE = 0x80090000                 # file offset = address - EXE_BASE (PS-X EXE header included)
CHAR_TO_GLYPH_TABLE, GLYPH_DATA, NUM_GLYPHS = 0x801307E0, 0x80130880, 79
W, H = 12, 11                         # GLYPH_WIDTH, GLYPH_HEIGHT (font.c)
FIRST_CODE = 0xF040                   # Shift-JIS user-defined area: F040-F07E, then F080-F0FC
GLYPHS_PER_LEAD = 0x7F - 0x40 + 0xFD - 0x80
MAX_GLYPHS = GLYPHS_PER_LEAD * 10       # Shift-JIS private-use leads F0..F9
SPACE_WIDTH = 8                       # advance of a dialogue space (DRAW_STRING2_SPACE_WIDTH, script_textbox.c)
_EXTRA_CACHE = {}


def index_to_code(i):
    if not 0 <= i < MAX_GLYPHS:
        raise ValueError(f'extra glyph index out of range: {i}')
    t = 0x40 + i % GLYPHS_PER_LEAD
    if t >= 0x7F:
        t += 1                        # Shift-JIS trail bytes skip 0x7F
    return ((0xF0 + i // GLYPHS_PER_LEAD) << 8) | t


def code_to_index(code):
    t = code & 0xFF
    return ((code >> 8) - 0xF0) * GLYPHS_PER_LEAD + t - 0x40 - (t > 0x7F)


def load_extra(path=EXTRA, include_japanese=True):
    """[(char, width, rows)] in code order. rows: 11 strings of 12 '#'/'.'."""
    out, cur = [], None
    paths = [path]
    japanese = os.path.join(ROOT, 'tools/font/japanese.txt')
    if include_japanese and os.path.abspath(path) == os.path.join(ROOT, 'tools/font/extra.txt') and os.path.isfile(japanese):
        paths.append(japanese)
    stamp = tuple((os.path.abspath(p), os.stat(p).st_mtime_ns, os.stat(p).st_size) for p in paths)
    if stamp in _EXTRA_CACHE:
        return [(ch, width, list(rows)) for ch, width, rows in _EXTRA_CACHE[stamp]]
    raw_lines = []
    for p in paths:
        with open(p, encoding='utf-8') as source:
            raw_lines.extend(source)
    for n, raw in enumerate(raw_lines, 1):
        line = raw.rstrip('\n')
        if not line.strip() or line.startswith(';'):
            continue
        m = re.match(r'^glyph\s+(\S)\s+(\d+)\s*$', line)
        if m:
            cur = (unicodedata.normalize('NFC', m.group(1)), int(m.group(2)), [])
            out.append(cur); continue
        if cur is None or not re.fullmatch(r'[.#]{1,12}', line.strip()):
            sys.exit(f'{path}:{n}: expected "glyph CHAR WIDTH" or a row of . and #')
        cur[2].append(line.strip().ljust(W, '.'))
    for ch, w, rows in out:
        if len(rows) != H:
            sys.exit(f'{path}: glyph {ch!r} has {len(rows)} rows (needs {H})')
        ink = max((r.rfind('#') for r in rows), default=-1)
        if ink > w - 2 and w < W:
            sys.exit(f'{path}: glyph {ch!r}: ink in column {ink} touches the next glyph (width {w})')
    if len(out) > MAX_GLYPHS:
        sys.exit(f'{path}: more than {MAX_GLYPHS} glyphs')
    if len({c for c, _, _ in out}) != len(out):
        sys.exit(f'{path}: a character is defined twice')
    if len(_EXTRA_CACHE) >= 8:
        _EXTRA_CACHE.pop(next(iter(_EXTRA_CACHE)))
    _EXTRA_CACHE[stamp] = tuple((ch, width, tuple(rows)) for ch, width, rows in out)
    return out


def extra_map(path=EXTRA):
    """{char: (code, width)} for the tools."""
    return {ch: (index_to_code(i), w) for i, (ch, w, _) in enumerate(load_extra(path))}


def exe_glyphs(exe_dir):
    """How many extra glyphs a built mod executable has: (count, where it was read), or (None, None) when exe_dir holds no
    build. The linked .elf decides (EXTRA_GLYPH_DATA is 24 bytes a glyph; an executable built before a glyph was appended
    lacks it, and would draw its code as some other glyph); without one, the worktree's src/main/font_extra.h (what the
    next build of it will have). The glyphs are the first `count` of extra.txt: the file is only ever appended to."""
    import subprocess
    elf = os.path.join(exe_dir, 'SLUS_010.32.elf')
    if os.path.exists(elf):
        try:
            out = subprocess.run(['nm', '-S', elf], capture_output=True, text=True, check=True).stdout
        except (OSError, subprocess.CalledProcessError):
            out = None
        if out is not None:
            m = re.search(r'^[0-9a-f]+ ([0-9a-f]+) \w EXTRA_GLYPH_DATA$', out, re.M)
            jp = re.search(r'^[0-9a-f]+ ([0-9a-f]+) \w JAPANESE_GLYPH_DATA$', out, re.M)
            packed = re.search(r'^[0-9a-f]+ ([0-9a-f]+) \w JAPANESE_GLYPH_BITMAPS$', out, re.M)
            latin = re.search(r'^([0-9a-f]+) A LATIN_GLYPH_COUNT$', out, re.M)
            huffman = re.search(r'^([0-9a-f]+) A JAPANESE_GLYPH_COUNT$', out, re.M)
            indexed = re.search(r'^[0-9a-f]+ ([0-9a-f]+) \w JAPANESE_GLYPH_INDICES$', out, re.M)
            return (((int(m.group(1), 16) if m else 0) + (int(jp.group(1), 16) if jp else 0)) // 24 +
                    (int(packed.group(1), 16) // 13 if packed else 0) +
                    ((int(indexed.group(1), 16) - 1) * 8 // 90 if indexed else 0) +
                    (int(huffman.group(1), 16) if huffman else 0) +
                    (int(latin.group(1), 16) if latin and not m else 0)), elf
    h = os.path.normpath(os.path.join(exe_dir, '..', '..', '..', '..', 'src', 'main', 'font_extra.h'))
    if os.path.exists(h):
        m = re.search(r'^#define NUM_EXTRA_GLYPHS (\d+)', open(h, encoding='utf-8').read(), re.M)
        return (int(m.group(1)) if m else 0), h
    return None, None


def row_word(r):
    v = 0xFFFF
    for b, c in enumerate(r):
        if c == '#':
            v &= ~(0x8000 >> b)
    return v


def japanese_bitmap(rows):
    """The 10x10 bitmap in 13 bytes (MSB first); the 11th row and right padding are blank."""
    if any('#' in row[10:] for row in rows) or any('#' in row for row in rows[10:]):
        raise ValueError('Japanese bitmap must fit its 10x10 source cell')
    bits = [int(rows[y][x] == '#') for y in range(10) for x in range(10)] + [0] * 4
    return bytes(sum(bits[i + b] << (7 - b) for b in range(8)) for i in range(0, 104, 8))


def japanese_dictionary(glyphs):
    """Nine-bit row indices, shared row words, and one trailing byte for safe C reads."""
    words = sorted({row_word(row) for _, _, rows in glyphs for row in rows[:10]})
    if len(words) > 512:
        raise ValueError('Japanese row dictionary exceeds nine bits')
    lookup = {word: i for i, word in enumerate(words)}
    bits = []
    for _, _, rows in glyphs:
        japanese_bitmap(rows)  # Validate the source cell dimensions.
        for row in rows[:10]:
            index = lookup[row_word(row)]
            bits.extend((index >> shift) & 1 for shift in range(8, -1, -1))
    bits.extend([0] * (-len(bits) % 8))
    packed = bytes(sum(bits[i + b] << (7 - b) for b in range(8)) for i in range(0, len(bits), 8))
    return words, packed + b'\0'


def japanese_huffman(glyphs, block=8, height=10):
    """Canonical Huffman row words, with a random-access checkpoint each eight glyphs."""
    import collections
    import heapq
    frequencies = collections.Counter(row_word(row) for _, _, rows in glyphs for row in rows[:height])
    heap = [(count, word, word) for word, count in frequencies.items()]
    heapq.heapify(heap)
    serial = 65536
    while len(heap) > 1:
        ac, _, a = heapq.heappop(heap)
        bc, _, b = heapq.heappop(heap)
        heapq.heappush(heap, (ac + bc, serial, (a, b)))
        serial += 1
    lengths = {}
    def visit(node, depth):
        if isinstance(node, int):
            lengths[node] = max(1, depth)
        else:
            visit(node[0], depth + 1)
            visit(node[1], depth + 1)
    visit(heap[0][2], 0)
    words = sorted(lengths, key=lambda word: (lengths[word], word))
    counts = [0] * (max(lengths.values()) + 1)
    codes, code, previous = {}, 0, 0
    for word in words:
        length = lengths[word]
        code <<= length - previous
        codes[word] = (code, length)
        counts[length] += 1
        code += 1
        previous = length
    bits, offsets = [], []
    for index, (_, _, rows) in enumerate(glyphs):
        if height == 10:
            japanese_bitmap(rows)
        if index % block == 0:
            offsets.append(len(bits))
        for row in rows[:height]:
            code, length = codes[row_word(row)]
            bits.extend((code >> shift) & 1 for shift in range(length - 1, -1, -1))
    bits.extend([0] * (-len(bits) % 8))
    data = bytes(sum(bits[i+b] << (7-b) for b in range(8)) for i in range(0, len(bits), 8))
    return words, counts, offsets, data


def header(out):
    g = load_extra()
    latin = len(load_extra(include_japanese=False))
    lines = ['/* Generated by tools/fontgen.py from tools/font/extra.txt: do not edit. */',
             '/* Glyph i is Shift-JIS code 0xF040 + i (trail byte 0x7F skipped). */', '',
             f'#define NUM_EXTRA_GLYPHS {len(g)}', f'#define NUM_LATIN_GLYPHS {latin}', '',
             'static const GlyphData EXTRA_GLYPH_DATA[NUM_LATIN_GLYPHS] = {']
    for i, (ch, w, rows) in enumerate(g[:latin]):
        name = unicodedata.name(ch, '?')
        lines.append(f'\t/* {index_to_code(i):04X} {ch} {name.lower()} */')
        words = ', '.join('0x%04x' % row_word(r) for r in rows)
        lines.append(f'\t{{ {{ {words}, }}, {w} }},')
    lines.append('};')
    words, counts, offsets, data = japanese_huffman(g[latin:])
    lines += ['', f'#define NUM_JAPANESE_GLYPHS {len(g) - latin}',
              f'#define JAPANESE_HUFFMAN_MAX_BITS {len(counts)-1}',
              f'__asm__(".globl LATIN_GLYPH_COUNT\\n.set LATIN_GLYPH_COUNT, {latin}\\n.globl JAPANESE_GLYPH_COUNT\\n.set JAPANESE_GLYPH_COUNT, {len(g)-latin}");']
    for name, ctype, values, fmt in [('JAPANESE_GLYPH_ROWS','uint16_t',words,'04x'),
                                    ('JAPANESE_HUFFMAN_COUNTS','uint16_t',counts,'04x'),
                                    ('JAPANESE_GLYPH_OFFSETS','uint32_t',offsets,'08x'),
                                    ('JAPANESE_GLYPH_BITS','uint8_t',data,'02x')]:
        lines.append(f'static const {ctype} {name}[{len(values)}] = {{')
        lines += ['\t' + ', '.join('0x' + format(v,fmt) for v in values[i:i+12]) + ',' for i in range(0,len(values),12)]
        lines.append('};')
    open(out, 'w', encoding='utf-8').write('\n'.join(lines) + '\n')
    print(f'{out}: {len(g)} glyphs')


# ---------------------------------------------------------------- preview
def base_font():
    exe = open(EXE, 'rb').read()
    o = CHAR_TO_GLYPH_TABLE - EXE_BASE
    codes = struct.unpack_from('<%dH' % NUM_GLYPHS, exe, o)
    o = GLYPH_DATA - EXE_BASE
    glyphs = {}
    for i, code in enumerate(codes):
        d = struct.unpack_from('<12H', exe, o + i * 24)
        rows = [''.join('.' if (v >> (15 - b)) & 1 else '#' for b in range(W)) for v in d[:H]]
        glyphs.setdefault(code, (d[11], rows))
    return codes, glyphs


ASCII = {' ': 0x8140, '.': 0x8142, '?': 0x8148, '!': 0x8149, '"': 0x8176, "'": 0x8175, ',': 0x8143,
         '\\': 0x815F, ':': 0x8146, ';': 0x8147, '+': 0x817B, '-': 0x817C, '=': 0x8181,
         '○': 0x819B, '□': 0x81A0, '×': 0x81A2, '△': 0x817E}     # the buttons as GLYPH_DATA draws them (tools/dws/bytecode/__main__.py, "Text")


def glyph_for(ch, codes, glyphs, extra):
    if ch in extra:
        return extra[ch]
    if 'A' <= ch <= 'Z': code = 0x8260 + ord(ch) - 65
    elif 'a' <= ch <= 'z': code = 0x8281 + ord(ch) - 97
    elif '0' <= ch <= '9': code = 0x824F + ord(ch) - 48
    else: code = ASCII.get(ch, codes[-1])
    return glyphs.get(code, glyphs[codes[-1]])


def render(lines, scale=3, space=None):
    """Simulates drawString2: x advances by the glyph width, LoadImage lands on x & ~3 and
    writes the whole 12-px cell (the next glyph erases what the previous one left there).
    A space (81 40) only clears 12 px and advances SPACE_WIDTH px (mod executable);
    space=0 simulates the original, where it advances by the previous glyph's width."""
    space = SPACE_WIDTH if space is None else space
    from tools.image import Image
    codes, glyphs = base_font()
    extra = {ch: (w, rows) for ch, w, rows in load_extra()}
    bg, fg = (24, 32, 72), (230, 230, 230)
    width = 256; img = Image.new('RGB', (width + 4, 12 * len(lines) + 4), bg)
    px = img.load()
    for ln, text in enumerate(lines):
        x = 0; y = 2 + ln * 12; adv = 12      # text rows start at x 0 of the VRAM text area
        for ch in unicodedata.normalize('NFC', text):
            x0 = (x & ~3) + 2
            if x0 - 2 + W > width:
                break
            if ch == ' ':
                rows = ['.' * W] * H
                adv = space or adv
            else:
                adv, rows = glyph_for(ch, codes, glyphs, extra)
            for r in range(H):
                for c in range(W):
                    px[x0 + c, y + r] = fg if rows[r][c] == '#' else bg
            x += adv
    return img.resize((img.width * scale, img.height * scale), Image.NEAREST)


# ---------------------------------------------------------------- long names (font.c drawStringMode)
CONDENSED = os.path.join(ROOT, 'tools/font/condensed.txt')
FIT_GAP = 1                           # blank columns between two letters' ink (FIT_GAP in font.c)
FIT_SPACE = 3                         # what a glyph without ink (a space) adds (FIT_SPACE in font.c)


def load_condensed(path=CONDENSED):
    """{char: rows} of the condensed lowercase (11 rows of 12 '#'/'.')."""
    out, cur = {}, None
    for n, raw in enumerate(open(path, encoding='utf-8'), 1):
        line = raw.strip()
        if not line or line.startswith(';'):
            continue
        m = re.match(r'^glyph\s+([a-z])$', line)
        if m:
            cur = out.setdefault(m.group(1), []); continue
        if cur is None or not re.fullmatch(r'[.#]{1,12}', line):
            sys.exit(f'{path}:{n}: expected "glyph LETTER" or a row of . and #')
        cur.append(line.ljust(W, '.'))
    for ch, rows in out.items():
        if len(rows) != H:
            sys.exit(f'{path}: glyph {ch!r} has {len(rows)} rows (needs {H})')
    return out


def condensed_header(out):
    g = load_condensed()
    lines = ['/* Generated by tools/fontgen.py from tools/font/condensed.txt: do not edit. */',
             '/* The condensed lowercase of long names, a..z (font.c drawStringMode); width 0: the original glyph. */', '',
             'static const GlyphData CONDENSED_GLYPH_DATA[26] = {']
    for c in 'abcdefghijklmnopqrstuvwxyz':
        if c in g:
            words = ', '.join('0x%04x' % row_word(r) for r in g[c])
            ink = max(r.rfind('#') for r in g[c]) + 1
            lines.append(f'\t{{ {{ {words}, }}, {ink} }}, /* {c} */')
        else:
            lines.append(f'\t{{ {{ 0 }}, 0 }}, /* {c}: original */')
    lines.append('};')
    open(out, 'w', encoding='utf-8').write('\n'.join(lines) + '\n')
    print(f'{out}: {len(g)} condensed glyphs')


def fit_glyphs(text, mode):
    """[(advance, rows)] the way drawStringMode picks them: mode 0 vanilla, 1 tight, 2 condensed."""
    codes, glyphs = base_font()
    extra = {ch: (w, rows) for ch, w, rows in load_extra()}
    cond = load_condensed() if mode == 2 else {}
    out = []
    for ch in unicodedata.normalize('NFC', text):
        w, rows = glyph_for(ch, codes, glyphs, extra)
        out.append((w, cond.get(ch, rows)))
    return out


def fit_layout(text, mode):
    """[(x, rows)] and the ink width: vanilla advances on the 4-px grid, or ink + FIT_GAP (font.c drawStringMode)."""
    pen, placed, width = 0, [], 0
    for w, rows in fit_glyphs(text, mode):
        cols = [c for c in range(W) if any(r[c] == '#' for r in rows)]
        if mode == 0:
            placed.append((pen & ~3, rows)); width = (pen & ~3) + (max(cols) + 1 if cols else 0); pen += w
        elif not cols:
            pen += FIT_SPACE
        else:
            x = pen - cols[0]
            placed.append((x, rows)); width = x + cols[-1] + 1; pen = width + FIT_GAP
    return placed, width


def fit_preview(text, out, scale=4):
    """The name drawn the three ways, each with its ink width: what the long-name screens choose from."""
    from tools.image import Image, ImageDraw
    bg, fg = (24, 32, 72), (230, 230, 230)
    rows3 = [fit_layout(text, m) for m in (0, 1, 2)]
    width_px = 240
    img = Image.new('RGB', (width_px, 16 * 3), bg); px = img.load()
    for i, (placed, width) in enumerate(rows3):
        y = 2 + i * 16
        for x0, rows in placed:
            for r in range(H):
                for c in range(W):
                    if rows[r][c] == '#' and 0 <= x0 + 2 + c < width_px:
                        px[x0 + 2 + c, y + r] = fg
    img = img.resize((img.width * scale, img.height * scale), Image.NEAREST)
    d = ImageDraw.Draw(img)
    for i, (_, width) in enumerate(rows3):
        d.text(((width_px - 50) * scale, i * 16 * scale + 16), f"{['vanilla', 'tight', 'condensed'][i]} {width}",
               fill=(255, 220, 120))
    img.save(out); print(out, [w for _, w in rows3])


# ---------------------------------------------------------------- fonts placed to the pixel (FONT=a|b, docs/mods/font.md "Fonts")
# The executable's font is a build parameter (Makefile FONT=original|a|b). original: the glyphs above on the 4-pixel grid.
# a and b: drawGlyph places each glyph to the pixel and its width is its advance: the ink and GAP blank columns.
FONTS = ('original', 'a', 'b')
GAP = 1                               # blank columns after a glyph's ink (its advance includes them)
PROP_SPACE = 4                        # advance of the space glyph (81 40) of fonts a and b
FONT_B = os.path.join(ROOT, 'tools/font/b.txt')
BUTTONS_DRAWN = {0x819B: '○', 0x81A0: '□', 0x81A2: '×', 0x817E: '△'}   # what the US font draws at these codes


def code_char(code):
    """The character the US font draws at one of its 79 codes (None: none of ours)."""
    if 0x8260 <= code <= 0x8279: return chr(65 + code - 0x8260)
    if 0x8281 <= code <= 0x829A: return chr(97 + code - 0x8281)
    if 0x824F <= code <= 0x8258: return chr(48 + code - 0x824F)
    if code in BUTTONS_DRAWN: return BUTTONS_DRAWN[code]
    return {v: k for k, v in ASCII.items() if k not in '○□×△'}.get(code)


def load_font_txt(path):
    """{char: (advance or None, rows)} of a font file (tools/font/b.txt): `glyph CHAR [ADVANCE]` and 11 rows of '#'/'.'
    (row 0 first; up to 12 columns). Without ADVANCE it is the ink's width + GAP."""
    out, cur = {}, None
    for n, raw in enumerate(open(path, encoding='utf-8'), 1):
        line = raw.rstrip('\n')
        if not line.strip() or line.startswith(';') or line.startswith('kern '):
            continue
        m = re.match(r'^glyph\s+(\S)(?:\s+(\d+))?\s*$', line)
        if m:
            ch = unicodedata.normalize('NFC', m.group(1))
            if ch in out:
                sys.exit(f'{path}:{n}: {ch!r} is drawn twice')
            cur = out[ch] = (int(m.group(2)) if m.group(2) else None, [])
            continue
        if cur is None or not re.fullmatch(r'[.#]{1,12}', line.strip()):
            sys.exit(f'{path}:{n}: expected "glyph CHAR [ADVANCE]" or a row of . and #')
        cur[1].append(line.strip().ljust(W, '.'))
    for ch, (_, rows) in out.items():
        if len(rows) != H:
            sys.exit(f'{path}: glyph {ch!r} has {len(rows)} rows (needs {H})')
    return out


_KERN = {}


def kern_rules(font):
    """[(lefts, rights, delta)] of a font's kerning: `kern LEFTS RIGHTS DELTA` lines of tools/font/b.txt (a glyph of
    RIGHTS right after one of LEFTS moves DELTA pixels; the first rule that names a pair decides). Fonts original and a
    have none."""
    if font != 'b':
        return []
    out = []
    for n, raw in enumerate(open(FONT_B, encoding='utf-8'), 1):
        if raw.startswith('kern '):
            m = re.fullmatch(r'kern\s+(\S+)\s+(\S+)\s+(-?\d+)\s*', raw.rstrip('\n'))
            if not m: sys.exit(f'{FONT_B}:{n}: expected "kern LEFTS RIGHTS DELTA"')
            out.append((unicodedata.normalize('NFC', m.group(1)), unicodedata.normalize('NFC', m.group(2)), int(m.group(3))))
    return out


def kern(font):
    """{(left, right): delta} of a font (kern_rules): what drawGlyph adds to the pen between two glyphs drawn one right
    after the other (font.c kernOf). A space breaks a pair."""
    if font not in _KERN:
        k = {}
        for lefts, rights, d in kern_rules(font):
            for a in lefts:
                for b in rights:
                    k.setdefault((a, b), d)
        _KERN[font] = k
    return _KERN[font]


def check_kern(font):
    """Every kerned pair keeps a blank column between the two glyphs' ink on every row (fontgen refuses the font)."""
    g = font_glyph_map(font)
    for (a, b), d in kern(font).items():
        if a not in g or b not in g:
            sys.exit(f'font {font}: kern pair {a}{b}: {a if a not in g else b!r} has no glyph')
        adv, ra = g[a]; _, rb = g[b]
        for r in range(H):
            la = [c for c in range(W) if ra[r][c] == '#']; lb = [c for c in range(W) if rb[r][c] == '#']
            if la and lb and adv + d + lb[0] - la[-1] < 2:
                sys.exit(f'font {font}: kern {a}{b} {d} makes their ink touch on row {r}')


def to_pixel(rows, adv=None, blank_adv=PROP_SPACE):
    """(advance, rows) of a glyph placed to the pixel: its ink moved to column 0 and advance ink + GAP; with an explicit
    `adv` the columns stay as drawn (a left bearing kept, as in a tabular digit 1)."""
    cols = [c for c in range(W) if any(r[c] == '#' for r in rows)]
    if not cols:
        return (adv if adv is not None else blank_adv), ['.' * W] * H
    left, right = cols[0], cols[-1]
    if adv is None:
        rows = [(r[left:] + '.' * left) for r in rows]
        right -= left; left = 0
    adv = right + 1 + GAP if adv is None else adv
    if adv < right + 1 + GAP or adv < 2:
        sys.exit(f'a glyph whose ink ends in column {right} needs an advance of at least {right + 1 + GAP} (has {adv})')
    return adv, rows


def tabular(glyphs):
    """{digit: (advance, rows)} with one advance for every digit (the widest), each digit's ink centred in it, so numbers
    padded with the figure space stay right-aligned."""
    adv = max(a for a, _ in glyphs.values())
    out = {}
    for d, (a, rows) in glyphs.items():
        cols = [c for c in range(W) if any(r[c] == '#' for r in rows)]
        ink = cols[-1] - cols[0] + 1
        pad = (adv - GAP - ink) // 2
        out[d] = (adv, ['.' * pad + r[cols[0]:][:W - pad] for r in rows])
    return out


def disc_glyphs():
    """(codes, [(cell, rows)]) of the original font's 79 glyphs in CHAR_TO_GLYPH_TABLE order, read from the USA
    executable (extracted/SLUS_010.32): the bitmaps, for drawing (a developer's task: font headers, sheets, previews)."""
    exe = open(EXE, 'rb').read()
    codes = struct.unpack_from('<%dH' % NUM_GLYPHS, exe, CHAR_TO_GLYPH_TABLE - EXE_BASE)
    base = []
    for i in range(NUM_GLYPHS):
        d = struct.unpack_from('<12H', exe, GLYPH_DATA - EXE_BASE + i * 24)
        base.append((d[11], [''.join('.' if (v >> (15 - b)) & 1 else '#' for b in range(W)) for v in d[:H]]))
    return list(codes), base


def write_original_metrics(out=ORIGINAL_METRICS):
    """tools/font/original-metrics.json from the USA executable: the numbers measuring needs (codes, cells, ink
    columns), no bitmap."""
    codes, base = disc_glyphs()
    ink = []
    for _, rows in base:
        cols = [c for c in range(W) if any(r[c] == '#' for r in rows)]
        ink.append([cols[0], cols[-1]] if cols else None)
    lines = ['{', ' "_about": "GENERATED by tools/fontgen.py original-metrics from the USA executable (CHAR_TO_GLYPH_TABLE, '
             'GLYPH_DATA): the original font\'s 79 glyphs as numbers, what measuring text needs (no bitmap). codes: the '
             'Shift-JIS code of each glyph; cells: its width (GLYPH_DATA advance); ink: the first and last column of its '
             'ink (null: blank). Do not edit.",',
             ' "codes": ' + json.dumps(codes) + ',', ' "cells": ' + json.dumps([c for c, _ in base]) + ',',
             ' "ink": ' + json.dumps(ink), '}']
    open(out, 'w').write('\n'.join(lines) + '\n')
    print(f'{out}: {len(codes)} glyphs')


def committed_glyphs():
    """(codes, [(cell, rows)]) like disc_glyphs, from the committed numbers (tools/font/original-metrics.json). The rows
    are not the drawing: each holds only its ink's first and last column (in row 0), which is all to_pixel, tabular and
    the cell check read. For measuring only (metrics); never drawn or written to a header."""
    m = json.load(open(ORIGINAL_METRICS))
    base = []
    for cell, ink in zip(m['cells'], m['ink']):
        rows = ['.' * W] * H
        if ink:
            r0 = ['.'] * W; r0[ink[0]] = r0[ink[1]] = '#'; rows = [''.join(r0)] + rows[1:]
        base.append((cell, rows))
    return list(m['codes']), base


def font_tables(font, original=None):
    """The executable's tables for a font: ([(advance, rows)] of GLYPH_DATA in CHAR_TO_GLYPH_TABLE order,
    [(char, advance, rows)] of EXTRA_GLYPH_DATA in code order). original: (codes, glyphs) of the original font
    (committed_glyphs for measuring), default the disc's (disc_glyphs)."""
    codes, base = original or disc_glyphs()
    extra = load_extra()
    if font == 'original':
        return base, extra
    if font not in FONTS:
        sys.exit(f'unknown font {font!r} (one of {", ".join(FONTS)})')
    a_base = [to_pixel(rows) for _, rows in base]
    a_extra = [(ch, *to_pixel(rows)) for ch, _, rows in extra]
    if font == 'a':
        out_base, out_extra = a_base, a_extra
    else:
        b = load_font_txt(FONT_B)
        def pick(ch, fallback):
            if ch in b:
                adv, rows = b[ch]
                return to_pixel(rows, adv)
            return fallback
        out_base = [pick(code_char(code), a_base[i]) if code_char(code) else a_base[i] for i, code in enumerate(codes)]
        out_extra = [(ch, *pick(ch, (adv, rows))) for ch, adv, rows in a_extra]
    digits = {i: out_base[i] for i, code in enumerate(codes) if 0x824F <= code <= 0x8258}
    for i, g in tabular(digits).items():
        out_base[i] = g
    latin = len(load_extra(include_japanese=False))
    out_extra[latin:] = [(ch, 11, rows) for ch, _, rows in extra[latin:]]
    for i, (adv, rows) in enumerate(out_base):          # FONT_CELLS centres the ink in the original's cell
        if adv - GAP > base[i][0] and any('#' in r for r in rows):
            sys.exit(f'font {font}: the glyph of {codes[i]:04X} is wider ({adv - GAP}) than its original cell ({base[i][0]})')
    for (ch, adv, rows), (_, w, _) in zip(out_extra, extra):
        if adv - GAP > w and any('#' in r for r in rows):
            sys.exit(f'font {font}: {ch!r} is wider ({adv - GAP}) than its original cell ({w})')
    return out_base, out_extra


def figure_space(font):
    """The advance of the blank that pads numbers (FONT_FIGURE_SPACE): a digit's."""
    exe = open(EXE, 'rb').read()
    codes = struct.unpack_from('<%dH' % NUM_GLYPHS, exe, CHAR_TO_GLYPH_TABLE - EXE_BASE)
    return font_tables(font)[0][codes.index(0x824F)][0]


def font_advances(font):
    """{char: advance} of a font (the space included), for measuring text the way the executable draws it."""
    exe = open(EXE, 'rb').read()
    codes = struct.unpack_from('<%dH' % NUM_GLYPHS, exe, CHAR_TO_GLYPH_TABLE - EXE_BASE)
    base, extra = font_tables(font)
    out = {}
    for code, (adv, _) in zip(codes[:-1], base[:-1]):
        ch = code_char(code)
        if ch is not None: out.setdefault(ch, adv)
    out.setdefault(BUTTONS_DRAWN[codes[-1]] if codes[-1] in BUTTONS_DRAWN else '\0', base[-1][0])
    for ch, adv, _ in extra:
        out[ch] = adv
    return out


def font_header(font, out):
    """src/main/font_<font>.h: GLYPH_DATA (the 79 codes of CHAR_TO_GLYPH_TABLE), EXTRA_GLYPH_DATA and the figure space
    for font.c. A glyph's width is its advance, with the original glyph's width (its cell, FONT_CELLS) in the high byte."""
    base, extra = font_tables(font)
    obase, oextra = font_tables('original')
    exe = open(EXE, 'rb').read()
    codes = struct.unpack_from('<%dH' % NUM_GLYPHS, exe, CHAR_TO_GLYPH_TABLE - EXE_BASE)
    src = {'a': 'the US glyphs (the executable) and tools/font/extra.txt',
           'b': 'tools/font/b.txt (what it lacks: as in a)'}[font]
    words = lambda rows: ", ".join("0x%04x" % row_word(r) for r in rows)
    lines = [f'/* Generated by tools/fontgen.py font-header {font} from {src}: do not edit. */',
             '/* A glyph is placed to the pixel (font.c drawGlyph): width = advance | original width << 8. */',
             '', '// clang-format off', 'GlyphData GLYPH_DATA[NUM_GLYPHS] = {']
    for i, (adv, rows) in enumerate(base):
        ch = code_char(codes[i])
        lines.append(f'\t{{ {{ {words(rows)}, }}, {adv} | {obase[i][0]} << 8 }}, /* {codes[i]:04X} {ch or "?"} */')
    latin = len(load_extra(include_japanese=False))
    lines += ['};', '// clang-format on', '', f'#define NUM_EXTRA_GLYPHS {len(extra)}', f'#define NUM_LATIN_GLYPHS {latin}', '',
              'static const GlyphData EXTRA_GLYPH_DATA[NUM_LATIN_GLYPHS] = {']
    for i, (ch, adv, rows) in enumerate(extra[:latin]):
        lines.append(f'\t{{ {{ {words(rows)}, }}, {adv} | {oextra[i][1]} << 8 }}, /* {index_to_code(i):04X} {ch} */')
    rules = kern_rules(font)
    if rules:
        check_kern(font)
        code_of = {code_char(c): c for c in reversed(codes[:-1]) if code_char(c)}
        code_of.update({ch: index_to_code(i) for i, (ch, _, _) in enumerate(extra)})
        lines += ['};', '', '/* kerning (tools/font/b.txt `kern`, font.c kernOf): DELTA, the number of LEFT codes, of RIGHT',
                  ' * codes, then the codes (Shift-JIS); 0 ends the table */', '#define FONT_KERN 1',
                  'static const uint16_t KERN_RULES[] = {']
        for lefts, rights, d in rules:
            lines.append(f'\t(uint16_t){d}, {len(lefts)}, {len(rights)}, /* {lefts} | {rights} */')
            cs = ['0x%04x' % code_of[c] for c in lefts + rights]
            lines += ['\t' + ', '.join(cs[i:i + 12]) + ',' for i in range(0, len(cs), 12)]
        lines += ['\t0,']
    lines += ['};', '',
              '/* FONT_FIGURE_SPACE (dw/mod_font.h): a blank as wide as a digit, in the cell of a dialogue space */',
              f'static const GlyphData FIGURE_SPACE_GLYPH = {{ {{ {words(["." * W] * H)}, }}, {figure_space(font)} | 8 << 8 }};']
    open(out, 'w', encoding='utf-8').write('\n'.join(lines) + '\n')
    print(f'{out}: font {font}, {len(base)} + {len(extra)} glyphs')


FONT_DEFAULT = 'b'                    # the Makefile's FONT ?= since patch 0099
from tools.dws.text.profiles import PACKED_ROW_BYTES as ROW_BYTES
PACKED = set('ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789 .,:;?!\'"+-=')   # one byte in a packed row


def exe_font(exe_dir):
    """The font of a built executable: ('original'|'a'|'b', where it was read), or (None, None) when exe_dir holds no
    build and no worktree. The linked executable decides (a build placed to the pixel has drawStringCells; its first
    GLYPH_DATA entry tells a from b); without one, the worktree's last generated font_sel.h, else its Makefile's default
    (a worktree without patch 0097 has the original font)."""
    import subprocess
    elf = os.path.join(exe_dir, 'SLUS_010.32.elf')
    exe = os.path.join(exe_dir, 'SLUS_010.32')
    if os.path.exists(elf) and os.path.exists(exe):
        try:
            out = subprocess.run(['nm', elf], capture_output=True, text=True, check=True).stdout
        except (OSError, subprocess.CalledProcessError):
            out = None
        if out is not None:
            if not re.search(r' T drawStringCells$', out, re.M):
                return 'original', elf
            # Packed font b replaces the old GlyphData table with Latin bitmaps.
            if re.search(r'^([0-9a-f]+) \w LATIN_GLYPH_BITS$', out, re.M):
                return 'b', elf
            addr = int(re.search(r'^([0-9a-f]+) \w GLYPH_DATA$', out, re.M).group(1), 16)
            data = open(exe, 'rb').read()
            t_addr = struct.unpack_from('<I', data, 0x18)[0]
            got = struct.unpack_from('<12H', data, addr - t_addr + 0x800)
            for f in ('a', 'b'):
                adv, rows = font_tables(f)[0][0]
                if [row_word(r) for r in rows] == list(got[:H]):
                    return f, elf
            return 'b', elf
    wt = os.path.normpath(os.path.join(exe_dir, '..', '..', '..', '..'))
    sel = os.path.join(wt, 'build', 'us', 'psx', 'generated', 'font_sel.h')
    if os.path.exists(sel):
        m = re.search(r'#define FONT_(\w+) 1', open(sel).read())
        if m: return m.group(1).lower(), sel
    mk = os.path.join(wt, 'Makefile')
    if os.path.exists(mk):
        m = re.search(r'^FONT \?= (\w+)', open(mk).read(), re.M)
        return (m.group(1) if m else 'original'), mk
    return None, None


_METRICS = {}


def metrics(font):
    """{char: advance} of a font placed to the pixel (a, b): what the executable's pen moves by for each character.
    From the committed numbers (committed_glyphs), not the disc: the build measures with it."""
    if font not in _METRICS:
        codes, glyphs = committed_glyphs()
        _METRICS[font] = {ch: adv for ch, (adv, _) in by_char(codes, *font_tables(font, (codes, glyphs))).items()}
    return _METRICS[font]


def row_bytes(chars):
    """Bytes of a packed row (FONT a/b, box 0: showTextbox): a character of PACKED one, any other glyph two."""
    return sum(1 if c in PACKED else 2 for c in chars)


def font_glyph_map(font):
    """{char: (advance, rows)} of a font, the space and the buttons included (the drawing: reads the disc; measuring
    uses metrics)."""
    codes, glyphs = disc_glyphs()
    return by_char(codes, *font_tables(font, (codes, glyphs)))


def by_char(codes, base, extra):
    """{char: (advance, rows)} of font_tables' two tables: the first glyph of a character wins, an extra glyph replaces it."""
    out = {}
    for code, g in zip(codes, base):
        ch = code_char(code)
        if ch is not None: out.setdefault(ch, g)
    for ch, adv, rows in extra:
        out[ch] = (adv, rows)
    return out


def render_font(lines, font, scale=3, shadow=True, width=256):
    """Lines drawn the way the executable of `font` draws them: to the pixel for a and b (each glyph at the pen, the pen
    moves by its advance), the 4-pixel grid for original (render). White text with the game's black shadow (+1,+1)."""
    from tools.image import Image
    if font == 'original':
        return render(lines, scale)
    g = font_glyph_map(font)
    bg, fg = (24, 32, 72), (213, 213, 213)
    img = Image.new('RGB', (width + 4, 13 * len(lines) + 4), bg); px = img.load()
    for ln, text in enumerate(lines):
        x, y = 0, 2 + ln * 13
        ink = []
        k, prev = kern(font), None
        for ch in unicodedata.normalize('NFC', text):
            adv, rows = g.get(ch, g['?'])
            x += k.get((prev, ch), 0); prev = ch
            ink += [(x + c, y + r) for r in range(H) for c in range(W) if rows[r][c] == '#']
            x += adv
        for (a, b) in ink:
            if shadow and a + 3 < img.width: px[a + 3, b + 1] = (0, 0, 0)
        for (a, b) in ink:
            if a + 2 < img.width: px[a + 2, b] = fg
    return img.resize((img.width * scale, img.height * scale), Image.NEAREST)


def text_width(text, font):
    """Pixels from the pen to the end of the last glyph's advance (what the next glyph would start at)."""
    if font == 'original':
        codes, base = committed_glyphs()
        glyphs = {}
        for code, glyph in zip(codes, base):
            glyphs.setdefault(code, glyph)
        extra = {ch: (w, rows) for ch, w, rows in load_extra()}
        return sum(SPACE_WIDTH if c == ' ' else glyph_for(c, codes, glyphs, extra)[0] for c in text)
    adv = metrics(font)
    return sum(adv.get(c, adv['?']) for c in unicodedata.normalize('NFC', text)) + kerning(text, font)


def kerning(text, font):
    """What the font's kerning adds to a text's width (negative: pairs drawn closer); a space breaks a pair."""
    k = kern(font)
    t = unicodedata.normalize('NFC', text)
    return sum(k.get(p, 0) for p in zip(t, t[1:])) if k else 0


def font_sheet(font, out, scale=4):
    """Every glyph of a font between two neighbours (H.H, n.n, o.o), at 1x and `scale`x: for checking the drawing."""
    from tools.image import Image
    g = font_glyph_map(font)
    chars = [c for c in g if c != ' ']
    lines = []
    for i in range(0, len(chars), 10):
        lines.append(' '.join(f'H{c}n' for c in chars[i:i + 10]))
    lines += ['', 'Jijimon: I\'ll find a different way.', 'Tamer Level, Digivolve! Happymushroom,',
              'Native Forest, Analogman, Agumon.', 'HerculesKabuterimon MetalGreymonVaccine',
              'The quick brown fox jumps over', 'the lazy dog. 0123456789 Sp.Recovery',
              'Offense Infinity can\'t left "ok"', '(1/2) 50% #3 ¿Qué tal, señor? ¡Vámonos!',
              'Àvia, col·lecció «hola» ÁÉÍÓÚ Ñ Ü Ç']
    big = render_font(lines, font, scale, width=200)
    one = render_font(lines, font, 1, width=200)
    img = Image.new('RGB', (big.width, big.height + one.height + 8), (10, 10, 10))
    img.paste(one, (0, 0)); img.paste(big, (0, one.height + 8))
    img.save(out); print(out)


def sheet(out):
    codes, glyphs = base_font()
    g = load_extra()
    pairs = []
    for ch, w, rows in g:
        base = unicodedata.normalize('NFD', ch)[0]
        pairs.append(base + ch if base != ch else ch)
    lines = [' '.join(pairs[i:i + 6]) for i in range(0, len(pairs), 6)]
    render(lines, 4).save(out); print(out)


def main():
    a = sys.argv[1:]
    if a[:1] == ['header'] and len(a) == 2: header(a[1])
    elif a[:1] == ['preview'] and len(a) == 3: render(a[1].split('|'), 3).save(a[2]); print(a[2])
    elif a[:1] == ['sheet'] and len(a) == 2: sheet(a[1])
    elif a[:1] == ['condensed-header'] and len(a) == 2: condensed_header(a[1])
    elif a[:1] == ['font-header'] and len(a) == 3: font_header(a[1], a[2])
    elif a[:1] == ['font-sheet'] and len(a) == 3: font_sheet(a[1], a[2])
    elif a[:1] == ['preview'] and len(a) == 5 and a[3] == '--font':
        render_font(a[1].split('|'), a[4]).save(a[2]); print(a[2])
    elif a[:1] == ['fit'] and len(a) == 3: fit_preview(a[1], a[2])
    elif a[:1] == ['original-metrics'] and len(a) <= 2: write_original_metrics(*a[1:])
    elif a[:1] == ['glyphs'] and len(a) == 2:
        n, src = exe_glyphs(a[1])
        if n is None: sys.exit(f'{a[1]}: no build (SLUS_010.32.elf) and no worktree header')
        g = load_extra()
        print(f'{n} of the {len(g)} extra glyphs ({src})' + (f'; lacks {" ".join(c for c, _, _ in g[n:])}' if n < len(g) else ''))
    elif a[:1] == ['list']:
        for i, (ch, w, _) in enumerate(load_extra()):
            print('%04X %s %2d  %s' % (index_to_code(i), ch, w, unicodedata.name(ch, '?').lower()))
    else:
        sys.exit(__doc__)


if __name__ == '__main__':
    main()
