"""Text metrics and paging with an explicit font; no compiler configuration state."""
import re
import fontgen
from .. import bytecode
from .profiles import COMPILER_ROW_UNITS, ROW_PIXELS, LAST_ROW_PIXELS, PACKED_DIALOGUE, UNPACKED_WINDOW

MAX_PX = ROW_PIXELS

NAME_PX = 80        # a name ({player}, {item N}...) in a font placed to the pixel: most are shorter (Agumon 35 px in b)


def text_px(s, font):
    """Width in the text box (bytecode.line_metrics): each glyph's width from the font; a space
    is fontgen.SPACE_WIDTH px on the mod executable and as wide as the glyph before it on
    the original (that is how its drawString2 advances). Fonts a and b: their own advances (a space 4) and font b's
    kerning (fontgen.kern)."""
    if font.get('chinese'):
        from tools.chinese import row_metrics, font_glyphs
        return row_metrics(s, font_glyphs())[0]
    s = re.sub(r'\{color \d+\}', '', s)               # a colour change draws nothing (bytecode.line_metrics)
    if (font['name'] in ('a', 'b')):
        adv = fontgen.metrics(font['name']); names = len(re.findall(r'\{[^}]*\}', s))
        runs = re.split(r'\{[^}]*\}', s)                # a name breaks a kerned pair, like a space
        return names * NAME_PX + sum(adv.get(c, 12) for c in ''.join(runs)) + sum(fontgen.kerning(r, font['name']) for r in runs)
    s = re.sub(r'\{[^}]*\}', 'XXXXXXXX', s)          # variable names: approximate width
    px = 0; prev = 12
    for c in s:
        if c == ' ':
            px += fontgen.SPACE_WIDTH if font['extra'] else prev
        else:
            prev = bytecode.CHARWIDTH.get(c, 12); px += prev
    return px


MAX_UNITS = COMPILER_ROW_UNITS
# Escapes that showTextbox copies into the row as they are (script_textbox.c: cases 1, 2, 12, 14, 15): one 2-byte unit
# each, drawn as nothing. A colour change is no wider on screen but takes a unit of the row: "go at {color 6}×{color 1}
# to throw at full power!" is 31 letters and 33 units, and ran on into the next row in the game ("full powerB").
CODE_UNIT = re.compile(r'\{(?:color|tab|tab11|half|pos[0-9a-f]{2}) [^}]*\}')


def text_units(s):
    """2-byte units of a row in the row buffer: a glyph (the buttons ○ □ △ × too) or a colour change one each, a name
    ({player}...) about eight, a {raw 03 ...} two."""
    n = len(CODE_UNIT.findall(s)); s = CODE_UNIT.sub('', s)
    n += 2 * len(re.findall(r'\{raw 03[^}]*\}', s)); s = re.sub(r'\{raw 03[^}]*\}', '', s)
    return n + len(re.sub(r'\{[^}]*\}', 'XXXXXXXX', s))


def text_bytes(s):
    """Bytes of a row in a packed row buffer (fonts a and b): a letter, digit, space or . , : ; ? ! ' " + - = one
    (showTextbox writes its ASCII form), any other glyph and a colour change two, a name about sixteen."""
    n = 2 * len(CODE_UNIT.findall(s)); s = CODE_UNIT.sub('', s)
    n += 4 * len(re.findall(r'\{raw 03[^}]*\}', s)); s = re.sub(r'\{raw 03[^}]*\}', '', s)
    n += 16 * len(re.findall(r'\{[^}]*\}', s))
    return n + fontgen.row_bytes(re.sub(r'\{[^}]*\}', '', s))


LAST_ROW_PX = LAST_ROW_PIXELS

def fits(s, font, last_row=False, packed=True):
    """Apply the named box profile with the compiler's intentional safety headroom."""
    profile = PACKED_DIALOGUE if font['name'] in ('a', 'b') and packed else UNPACKED_WINDOW
    pixels = profile.last_row_pixels if last_row else profile.row_pixels
    if profile.packed:
        return text_px(s, font) <= pixels and text_bytes(s) <= profile.row_bytes
    return text_px(s, font) <= pixels and text_units(s) <= profile.author_units


def row_limit(font, packed=True):
    """The row buffer's limit as a phrase, for messages."""
    return f'{fontgen.ROW_BYTES} bytes' if (font['name'] in ('a', 'b')) and packed else f'{MAX_UNITS} units'


def row_size(s, font, packed=True):
    """A row's size in its buffer, as a phrase (bytes of a packed row, else units) with its width."""
    return (f'{text_bytes(s)} bytes' if (font['name'] in ('a', 'b')) and packed else f'{text_units(s)} units') + f', {text_px(s, font)} px'


# Japanese line breaking (kinsoku): a row never starts with closing punctuation, the long-vowel mark or a small kana;
# nor with a period (an ellipsis written "..." is never split: "きせつ." / "..？").
NO_ROW_START = frozenset('、。，．！？」』）ーぁぃぅぇぉっゃゅょゎァィゥェォッャュョヮヵヶ.')
TOKENS = re.compile(r'\{[^}]*\}|[A-Za-z0-9]+|.')


def starts_badly(row):
    """Whether a row's first letter (after its colour escapes: {color 6}; a name such as {partner} is a start) is one a
    Japanese row may not start with."""
    t = re.sub(r'^(\{color [^}]*\})+', '', row.lstrip())
    return bool(t) and t[0] in NO_ROW_START


def kinsoku(rows, fits):
    """Rows of Japanese text with no row starting with a NO_ROW_START mark: the marks go back onto the row above when
    it still fits (`fits(row, i)`), else the row above gives its last letter to the row below (when that one fits).
    A row emptied by it is dropped. Rows that cannot be mended stay as they are (the audit reports them)."""
    rows = list(rows)
    i = 1
    while i < len(rows):
        if not starts_badly(rows[i]):
            i += 1; continue
        toks = TOKENS.findall(rows[i].lstrip())
        n = 0
        while n < len(toks) and (toks[n].startswith('{color') or toks[n] in NO_ROW_START):
            n += 1                                          # the run of marks (and escapes among them): "？」"
        while n and toks[n - 1].startswith('{color'):
            n -= 1                                          # an escape after the run starts the row: it stays
        run, rest = ''.join(toks[:n]), ''.join(toks[n:]).lstrip()
        if fits(rows[i - 1] + run, i - 1):
            rows[i - 1] += run; rows[i] = rest
            if not rest: del rows[i]
            continue
        above = TOKENS.findall(rows[i - 1])
        k = len(above) - 1
        while k > 0 and (above[k] in NO_ROW_START or above[k].startswith('{color')):
            k -= 1                                          # carry a letter that may start a row, with what follows it
        carried = ''.join(above[k:])
        if k > 0 and fits(carried + rows[i].lstrip(), i):
            rows[i - 1] = ''.join(above[:k]); rows[i] = carried + rows[i].lstrip()
        i += 1
    return rows


def break_rows(text, ok):
    """Japanese text broken into rows letter by letter (escapes and Latin words whole) where they fit (`ok(row, i)`),
    with kinsoku: a mark that would start a row takes the row's last letter down with it."""
    toks = TOKENS.findall(text)
    lines, cur = [], []
    for t in toks:
        if cur and not ok(''.join(cur + [t]).rstrip(), len(lines)):
            take = 0
            if t in NO_ROW_START:                   # carry letters (and the marks or colours stuck to them) down
                take = 1
                while take < len(cur) and (cur[-take] in NO_ROW_START or cur[-take].startswith('{color')):
                    take += 1
                if take >= len(cur) or not ok(''.join(cur[-take:] + [t]).strip(), len(lines) + 1):
                    take = 0
            if take:
                lines.append(''.join(cur[:-take]).rstrip()); cur = cur[-take:] + [t]
            else:
                lines.append(''.join(cur).rstrip()); cur = [t] if t.strip() else []
        else:
            cur.append(t)
    if cur: lines.append(''.join(cur).rstrip())
    return [l.lstrip() for l in lines]


def wrap(text, lines_per_page, font, packed=True):
    """Split a text into pages of lines that fit in the text box (`packed`: box 0; False for UNPACKED_KEYS)."""
    if font.get('chinese'):
        from tools.chinese import wrap as chinese_wrap, font_glyphs
        return chinese_wrap(text, font_glyphs(), lines_per_page, packed)
    if re.search('[\u3040-\u30ff\u3400-\u9fff]', text):
        # Japanese has no word spaces. Keep references atomic and break between
        # glyphs; do not insert spaces into the translated prose.
        lines = break_rows(text, lambda r, i: fits(r, font, i % lines_per_page == lines_per_page - 1, packed))
        return [lines[i:i + lines_per_page] for i in range(0, len(lines), lines_per_page)] or [['']]
    words = re.findall(r'(?:\{[^}]*\}|\S)+', text); lines = []; cur = ''      # an escape ({color 6}) is never split
    for w in words:
        cand = (cur + ' ' + w).strip()
        if fits(cand, font, len(lines) % lines_per_page == lines_per_page - 1, packed): cur = cand
        else:
            if cur: lines.append(cur)
            cur = w
    if cur: lines.append(cur)
    return [lines[i:i + lines_per_page] for i in range(0, len(lines), lines_per_page)] or [['']]


def encoded_length(text, extra_codes):
    """Encoded bytes in a native text string; unknown glyphs retain the legacy two-byte bound."""
    total = 0
    for char in text:
        if char in extra_codes:
            total += 2
        else:
            try:
                total += len(char.encode('cp932'))
            except UnicodeEncodeError:
                total += 2
    return total
