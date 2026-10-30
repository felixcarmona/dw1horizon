"""The executable's text bank for a build with TEXT=<source> (docs/reference/text-sources.md 2.5).

    python3 tools/localize/executable/bank.py exe-bank SOURCE -o WORKTREE/text-bank.json [--report FILE]
    python3 tools/localize/executable/bank.py us-codes          # tools/localize/executable/us-format-codes.json from text/us/names.json (your disc)

Writes what the mod build's decomp/tools/gen_text.py reads (patch 0090): {"font": {char: code}, "text": {key: text}}. The font
part maps the mod executable's extra glyphs (tools/font/extra.txt: á é ñ ¿ ¡ ... ( ) & % / …) to their codes, so a text with them
encodes: the first N (`--font-glyphs N`: what the worktree's executable has; build-full.sh passes its NUM_EXTRA_GLYPHS). The
ASCII ones (( ) & % / [ ] # * ~ @) are in it under their full-width forms and the text part writes them so outside the format
codes: gen_text encodes every string with the map, and the executable's own strings keep their ASCII (%d, #C1); the text part is text/<SOURCE>/names.json (made by `dws extract-text`; text/ours/names.json for ours), fitted
to the game's font. For TEXT=us the text part is empty: the headers, hence the executable, are the ones without a bank.

Not taken from a source (they stay the build's): the species names (main.DIGIMON_NAMES.*, from content/species: the
names policy), and a name that does not fit its record (ITEM_NAMES: 19 bytes) or, an item's, the lists (96 pixels even
condensed: docs/mods/font.md "Item names"); both are listed in the report."""
import json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
sys.path.insert(0, os.path.join(ROOT, 'tools'))
# record sizes of the embedded tables (tools/localize/executable/extract.py EMBEDDED): the text and its NUL must fit
SIZES = {'main.ITEM_NAMES.': 20, 'main.ITEM_MENU_LABELS.': 8, 'main.STAT_LABELS.': 12}
KEEP = ('main.DIGIMON_NAMES.',)
FORMAT = re.compile(r'#[A-Z]\d*|%[-0-9.]*[a-z]')       # the battle messages' #C1 #R #W and the printf codes
# Strings whose spaces are layout (the fitter collapses runs of spaces and strips the ends):
# - the map captions: renderMapName crops strlen*8+4 px centred on the screen, so the US pads every name to 24 characters
#   (the Birdra list prints the same padded string); a source writes the plain name and it is centred here the US's way;
# - packed rows drawn once and cut by crop rectangles at fixed pixels: the source writes the spaces, kept as written.
# gen_text encodes a character by its Shift-JIS code, and the US font draws 81A2 (Shift-JIS △) as × and 817E (Shift-JIS ×)
# as △ (tools/dws/bytecode/__main__.py, "Text"): a source writes the button it means and the bank gives gen_text the other label
SJIS_LABELS = str.maketrans('×△', '△×')
MAP_NAME, MAP_NAME_WIDTH = 'main.STR_MAP_NAME_', 24
VERBATIM = ('kar.KAR_D_8005ABB8',                          # curling: two options cropped at 0 and 0x53 px (kar.c)
            # the status, technique and player screens' rows, the Year/Day header and the Yes/No rows: each word starts at
            # its crop's offset in the original font's cells (game_menu.c, main_menu.c: the language's crops and pieces)
            *('main.MAIN_D_' + a for a in ('801238A0', '801238B0', '801238D8', '80123900', '80123914', '80123920',
                                           '80123938', '8012394C', '80123958', '80123970', '80123A18', '80123A60', '80123A7C',
                                           '80123A98', '80123A3C', '80123AB0', '80123AD0', '80123AE4', '80123B10')),
            'shop.MAIN_D_801307CC',                         # Mojyamon's trade header: two crops at 0 and 0x42 px (script_menu.c)
            'main.STR_YEAR_DAY', 'main.STR_YES_NO', 'main.STR_YES_NO_SPACED',
            'main.CHART_STR_READY')                         # the chart card's verdict: "N of 4" + two spaces + "ready"
ITEM_NAME, ITEM_LIST_W = 'main.ITEM_NAMES.', 96             # every item list draws a name within 96 px (ITEM_FIELD_W)
# the format codes of every string of the US executable, {key: [codes]} (no text: committed), so the check that a source keeps
# them needs no text/us/ (the base disc may be another release); `us-codes` makes it again from text/us/names.json
US_CODES = os.path.join(HERE, 'us-format-codes.json')


def us_codes():
    """{key: [format codes]} of the US executable's strings (US_CODES); a missing file is an error, not a skipped check."""
    try: d = json.load(open(US_CODES, encoding='utf-8'))
    except (OSError, ValueError) as e:
        raise SystemExit(f'{os.path.relpath(US_CODES, ROOT)}: cannot read the US format codes ({e}); '
                         'python3 tools/localize/executable/bank.py us-codes writes it from text/us/names.json')
    return {k: v for k, v in d.items() if not k.startswith('_')}


def write_us_codes(path=US_CODES):
    up = os.path.join(ROOT, 'text', 'us', 'names.json')
    if not os.path.exists(up): raise SystemExit(f'{os.path.relpath(up, ROOT)} does not exist: python3 tools/dws.py extract-text YOUR-US-DISC')
    us = json.load(open(up, encoding='utf-8'))
    out = {'_comment': 'The format codes (#C1, %d) of each string of the US executable, by key of decomp/text/*.yaml: codes only, '
                       'no text (tools/localize/executable/bank.py us-codes makes it from text/us/names.json).'}
    out.update({k: FORMAT.findall(v) for k, v in sorted(us.items()) if not k.startswith('_') and isinstance(v, str)})
    with open(path, 'w', encoding='utf-8') as f:                  # one string a line
        f.write('{\n' + ',\n'.join(f'{json.dumps(k)}: {json.dumps(v)}' for k, v in out.items()) + '\n}\n')
    return len(out) - 1


def centre_map_name(t):
    t = t.strip()
    pad = max(0, MAP_NAME_WIDTH - len(t))
    left = (pad + 1) // 2                                  # the US's own padding: "      Native Forest     "
    return ' ' * left + t + ' ' * (pad - left)


def fit_verbatim(tb, k, v):
    """tb.fit word by word, the spaces between, before and after them kept as written."""
    return ''.join(p if not p.strip() else tb.fit(k, p) for p in re.split(r'( +)', v))


def full_width(c):
    return chr(ord(c) + 0xFEE0) if '!' <= c <= '~' else c


def font_map(n=None):
    """{char: code} of the first n extra glyphs (all of extra.txt by default); an ASCII one under its full-width form."""
    import fontgen
    return {full_width(ch): f'{code:04X}' for ch, (code, _w) in list(fontgen.extra_map().items())[:n]}


def ascii_glyphs(t, font):
    """A source's text with the ASCII characters of the font map (( ) & % / ...) in their full-width form, outside the
    format codes (#C1, %d): gen_text then encodes them as the extra glyphs."""
    parts, codes = FORMAT.split(t), FORMAT.findall(t)
    fix = lambda p: ''.join(full_width(c) if full_width(c) != c and full_width(c) in font else c for c in p)
    return fix(parts[0]) + ''.join(c + fix(p) for c, p in zip(codes, parts[1:]))


def encoded_len(text, font):
    from dws.text.layout import encoded_length
    return encoded_length(text, font)


def list_width(name, font='original'):
    """The narrowest of the ways the item lists draw a name (font.c drawStringMode: the font's own spacing, tight,
    condensed; tools/fontgen.py fit), in pixels. Font b draws every name in its own spacing (patch 0099)."""
    import fontgen
    if font in ('a', 'b'):
        own = fontgen.text_width(name, font) - fontgen.GAP
        if font == 'b': return own
        return min([own] + [fontgen.fit_layout(name, mode)[1] for mode in (1, 2)])
    return min(fontgen.fit_layout(name, mode)[1] for mode in range(3))


def fit_keeping_codes(tb, k, v):
    """tb.fit for one executable string, with its format codes (#C1, %d) kept: the fitter drops '#' and '%' (no glyph),
    which turned '#C7Go!#R' into 'C7Go!R'. The text between the codes is fitted; a space next to a code stays."""
    out = []
    for i, part in enumerate(FORMAT.split(v)):
        if i: out.append(FORMAT.findall(v)[i - 1])
        if not part.strip(): out.append(part); continue
        t = tb.fit(k, part)
        if not isinstance(t, str): t = ' '.join(r for p in t for r in p)
        out.append((' ' if part[0] == ' ' else '') + t + (' ' if part[-1] == ' ' else ''))
    return ''.join(out)


def exe_bank(source, glyphs=None, exe_font='original'):
    """-> (bank dict, [(key, why it stays the build's)]). glyphs: how many extra glyphs the executable has (None: all);
    exe_font: its font (original, a, b: docs/mods/font.md "Fonts"), which measures the item names."""
    font = font_map(glyphs)
    if source == 'us': return {'font': font, 'text': {}}, []
    p = os.path.join(ROOT, 'text', source, 'names.json')
    if not os.path.exists(p):
        if source not in ('us', 'jp', 'jp-rev1', 'es-fan'):           # ours, or a new language: the executable keeps its own strings
            return {'font': font, 'text': {}}, [('(all)', f'text/{source}/names.json does not exist: the executable\'s strings stay English')]
        raise SystemExit(f'TEXT={source}: {os.path.relpath(p, ROOT)} does not exist: python3 tools/dws.py extract-text YOUR-DISC')
    from dws import backend as BE
    from dws.textbank import TextBank, CJK
    n = len(BE.EXTRA_ORDER) if glyphs is None else min(glyphs, len(BE.EXTRA_ORDER))
    BE.FONT.update({'extra': True, 'glyphs': n, 'chars': frozenset(BE.EXTRA_ORDER[:n]), 'of': f'--font-glyphs {n}',
                    'name': exe_font})
    tb = TextBank('en', 'us')
    src = json.load(open(p, encoding='utf-8'))
    if source not in ('us', 'ours', 'jp', 'jp-rev1', 'es-fan'):      # a language of ours (text/es/): what it lacks stays our English
        po = os.path.join(ROOT, 'text', 'ours', 'names.json')
        src = {**json.load(open(po, encoding='utf-8')), **src}
    codes = us_codes()                                          # the US executable's own strings: their format codes
    out, kept = {}, []
    for k, v in src.items():
        if k.startswith('_') or not isinstance(v, str): continue
        if k.startswith(KEEP): kept.append((k, 'species names come from content/species')); continue
        if CJK.search(v) and set(CJK.findall(v)) - BE.FONT['chars']:
            kept.append((k, 'Japanese characters missing from the target font')); continue
        if k in codes and codes[k] != FORMAT.findall(v):
            kept.append((k, 'its format codes differ from the US executable\'s (' + ' '.join(codes[k]) + ')')); continue
        if k.startswith(MAP_NAME): t = centre_map_name(tb.fit(k, v))
        elif k in VERBATIM: t = fit_verbatim(tb, k, v)
        else: t = fit_keeping_codes(tb, k, v)
        t = ascii_glyphs(t, font).translate(SJIS_LABELS)
        size = next((n for pre, n in SIZES.items() if k.startswith(pre)), None)
        if size is not None and encoded_len(t, font) > size - 1:
            kept.append((k, f'{encoded_len(t, font)} bytes; the record holds {size - 1}')); continue
        if k.startswith(ITEM_NAME) and list_width(v, exe_font) > ITEM_LIST_W:
            kept.append((k, f'{list_width(v, exe_font)} px even condensed; the item lists draw {ITEM_LIST_W}')); continue
        out[k] = t
    if tb.unfit: kept.append(('(characters)', 'dropped, no glyph: ' + ' '.join(sorted(tb.unfit))))
    return {'font': font, 'text': out}, kept


def main(argv):
    import argparse
    ap = argparse.ArgumentParser(prog='bank.py')
    if argv[:1] == ['us-codes']:
        print(f'{write_us_codes()} strings\' format codes -> {os.path.relpath(US_CODES, ROOT)}'); return 0
    ap.add_argument('cmd', choices=('exe-bank',)); ap.add_argument('source'); ap.add_argument('-o', required=True)
    ap.add_argument('--report')
    ap.add_argument('--font-glyphs', type=int, default=None, metavar='N',
                    help='the executable has the first N extra glyphs of tools/font/extra.txt (default: all)')
    ap.add_argument('--font', choices=('original', 'a', 'b'), default='original',
                    help='the executable\'s font (docs/mods/font.md "Fonts"): how wide an item name is')
    a = ap.parse_args(argv)
    bank, kept = exe_bank(a.source, a.font_glyphs, a.font)
    with open(a.o, 'w', encoding='utf-8') as f: json.dump(bank, f, ensure_ascii=False, indent=0, sort_keys=True)
    if a.report:
        with open(a.report, 'w', encoding='utf-8') as f: f.write(''.join(f'{k}\t{w}\n' for k, w in kept))
    print(f'text bank for the executable: TEXT={a.source}, {len(bank["text"])} texts, {len(kept)} kept as built'
          + (f' ({a.report})' if a.report else ''))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
