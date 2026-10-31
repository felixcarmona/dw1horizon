#!/usr/bin/env python3
"""The English textures made from the Japanese disc (Digimon World: Horizon on a Japanese base).

  fromjp.py OUTDIR --extracted DUMP [--compare US_DUMP]
  fromjp.py --make-cutouts --extracted DUMP [--src DIR]     (the developer: the signposts' cut-outs)

DUMP is the Japanese disc's files (dumpsxiso). The Japanese disc has its words baked into some textures in Japanese;
each recipe here erases them into the texture's own background and draws our English letters (committed glyph tables:
textures/systemw/fonts.py, textures/fi-info/pixfont.py, fromjp_glyphs.py) in the original's style, at the places the
US disc has them (the executable is the US one, so its rects are the US ones). Writes

  OUTDIR/<disc path>      the whole file, only pixel indices changed (TIM headers, CLUTs, sizes kept; a .MAP keeps
                          everything but the pixels of its sign TIM)
  OUTDIR/files.txt        one disc path per line

Nothing is read from a US disc; --compare US_DUMP only prints, per texture, how many pixels differ from the US one
(where the US layout is the target: the words; the Japanese art around them stays).
"""
import argparse, importlib.util, os, struct, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
import fromjp_glyphs as G  # noqa: E402


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


sys.path.insert(0, os.path.join(HERE, 'textures', 'systemw'))
import fonts as SW  # noqa: E402  SYSTEM_W's label fonts
import words as SWW  # noqa: E402  their renderers (outline / shadow rules measured on the English words)
sys.path.pop(0)
PF = _load('fiinfo_pixfont', os.path.join(HERE, 'textures', 'fi-info', 'pixfont.py'))   # FI_INFO's 3x6 / 3x7 fonts


# ----------------------------------------------------------------------------------------------- TIM access

def tim_entries(data, base=0):
    """-> [dict(pix=offset of the pixel data, bpp=0/1, w=pixels, h, clut=(x, y, w, h, rows))] of a TIM or a TIM stack"""
    out, off = [], base
    while off + 8 <= len(data):
        magic, flag = struct.unpack_from('<II', data, off)
        if magic != 0x10:
            break
        p, clut = off + 8, None
        if flag & 8:
            ln, cx, cy, cw, ch = struct.unpack_from('<IHHHH', data, p)
            clut = (cx, cy, cw, ch, [list(struct.unpack_from('<%dH' % cw, data, p + 12 + 2 * cw * j)) for j in range(ch)])
            p += ln
        ln, _, _, w, h = struct.unpack_from('<IHHHH', data, p)
        bpp = flag & 3
        out.append(dict(pix=p + 12, bpp=bpp, w={0: w * 4, 1: w * 2, 2: w}[bpp], h=h, clut=clut))
        off = (p + ln + 3) & ~3
    return out


class Tex:
    """One TIM entry's pixel indices, editable, written back in place"""

    def __init__(self, data, entry=0, base=0):
        self.e = tim_entries(data, base)[entry]
        e = self.e
        self.w, self.h = e['w'], e['h']
        raw = data[e['pix']:e['pix'] + (self.w * self.h // 2 if e['bpp'] == 0 else self.w * self.h)]
        if e['bpp'] == 0:
            self.p = bytearray(v for b in raw for v in (b & 15, b >> 4))
        else:
            self.p = bytearray(raw)

    def g(self, x, y):
        return self.p[y * self.w + x] if 0 <= x < self.w and 0 <= y < self.h else -1

    def s(self, x, y, v):
        if not (0 <= x < self.w and 0 <= y < self.h):
            raise IndexError((x, y))
        self.p[y * self.w + x] = v

    def fill(self, x0, y0, x1, y1, v):
        """[x0, x1) x [y0, y1) to index v"""
        for y in range(y0, y1):
            for x in range(x0, x1):
                self.s(x, y, v)

    def put(self, rows, x0, y0, skip=None):
        """rows: list of lists of indices (None or skip = leave the pixel)"""
        for y, r in enumerate(rows):
            for x, v in enumerate(r):
                if v is not None and v != skip:
                    self.s(x0 + x, y0 + y, v)

    def write(self, data):
        e = self.e
        if e['bpp'] == 0:
            packed = bytes(self.p[i] & 15 | (self.p[i + 1] & 15) << 4 for i in range(0, len(self.p), 2))
        else:
            packed = bytes(self.p)
        data[e['pix']:e['pix'] + len(packed)] = packed


# ----------------------------------------------------------------------------------------------- word renderers

def compose(font, word, gap=1):
    """-> rows (str) of the word, glyphs bottom-aligned; '.' empty, any other char what the glyph has there"""
    gl = [font[c] for c in word]
    H = max(len(g) for g in gl)
    W = sum(len(g[-1]) for g in gl) + gap * (len(gl) - 1)
    out = [['.'] * W for _ in range(H)]
    x = 0
    for g in gl:
        off = H - len(g)
        for y, row in enumerate(g):
            for i, ch in enumerate(row):
                if ch != '.' and x + i < W:
                    out[y + off][x + i] = ch
        x += len(g[-1]) + gap
    return [''.join(r) for r in out]


def ink_set(rows, chars='#'):
    return {(x, y) for y, r in enumerate(rows) for x, c in enumerate(r) if c in chars}


def outline8(ink):
    return {(x + dx, y + dy) for (x, y) in ink for dx in (-1, 0, 1) for dy in (-1, 0, 1)} - ink


def draw_outlined(t, font, word, x0, y0, ink, line, gap=1):
    """the word's ink (index ink) with an 8-neighbour outline (index line); (x0, y0) the first ink pixel's top left"""
    pts = ink_set(compose(font, word, gap))
    for (x, y) in outline8(pts):
        t.s(x0 + x, y0 + y, line)
    for (x, y) in pts:
        t.s(x0 + x, y0 + y, ink)


def draw_shadowed(t, font, word, x0, y0, ink, shadow, gap=1, off=(1, 1), right=None):
    """ink with a drop shadow at off where the shadow pixel is not ink itself (none past column right)"""
    pts = ink_set(compose(font, word, gap))
    for (x, y) in pts:
        q = (x + off[0], y + off[1])
        if q not in pts and (right is None or x0 + q[0] <= right):
            t.s(x0 + q[0], y0 + q[1], shadow)
    for (x, y) in pts:
        t.s(x0 + x, y0 + y, ink)


def draw_plain(t, font, word, x0, y0, colours, gap=1):
    """colours: glyph char -> index"""
    for y, r in enumerate(compose(font, word, gap)):
        for x, c in enumerate(r):
            if c in colours:
                t.s(x0 + x, y0 + y, colours[c])


def draw_rows(t, font, word, x0, y0, row_ink, line, gap=1):
    """outlined like draw_outlined, the ink's index chosen by the glyph row (row_ink[y])"""
    pts = ink_set(compose(font, word, gap))
    for (x, y) in outline8(pts):
        t.s(x0 + x, y0 + y, line)
    for (x, y) in pts:
        t.s(x0 + x, y0 + y, row_ink[y])


def width(font, word, gap=1):
    return len(compose(font, word, gap)[0])


# ----------------------------------------------------------------------------------------------- the recipes

def bi_in(t):
    """BI_IN.TIM (= ETCTIM.BIN entry 0): the finisher's ○PUSH (the Japanese で必殺); the ○ (cols 128-137) stays"""
    t.fill(138, 8, 166, 17, 0)
    draw_outlined(t, G.PUSH, 'PUSH', 139, 9, 10, 1, gap=2)


def fi_info(t):
    """FI_INFO.TIM (= ETCTIM.BIN entry 4): the triangle menu's labels at GAME_MENU_TEXT_SPRITES' rects (texY - 1,
    7 rows: ink F, shadow 1 at +1,+1). Reletter only the three status-bubble
    interiors; u128..159, rows32..47 is a live night-clock frame and stays intact."""
    t.fill(80, 19, 128, 40, 0)
    t.fill(80, 40, 99, 47, 0)
    for word, x, y in (('ITEM', 81, 19), ('DIGIMON', 81, 26), ('PLAYER', 81, 33), ('FISH', 81, 40),
                       ('PRAISe', 108, 19), ('SCOLD', 108, 26), ('SLEEP', 108, 33)):
        draw_shadowed(t, G.MENU6, word, x, y, 15, 1, right=127)   # the sprite ends there; col 128 is other art
    for word, font, gap, x0, x1, y0, y1, fill, ink in G.BUBBLES:
        t.fill(x0, y0, x1, y1, fill)
        w = len(compose(font, word, gap)[0])
        draw_plain(t, font, word, (x0 + x1 - w) // 2, y0 + 1, {'#': ink}, gap)


def system_w(t):
    """SYSTEM_W.TIM (= ETCTIM.BIN entry 8): the English words where the US disc has them; the Japanese disc has most
    shop and tech headers in English already (MENU PRICE No. TITLE ... SPEC DATA PLACE POINT COUNT), not these"""
    # move-help element names (CLUT row 4: ink A, glyph-drawn shadow D, F transparent), one per 20-px cell
    t.fill(0, 24, 140, 34, 15)
    for word, x in (('FIRE', 3), ('AIR', 42), ('EARTH', 60), ('ICE', 85), ('MECH', 101), ('FILTH', 121)):
        t.put(SWW.r_elem(word), x, 24, skip=15)
    draw_shadowed(t, G.BATTLE7, 'BATLE', 20, 25, 10, 13, right=39)   # T = the joined TT
    # TECH. (the Japanese WAZA) between SPEC and DATA: small header font, outline D
    t.fill(17, 48, 36, 55, 13)
    t.put(SWW.r_small('TECH.'), 17, 48, skip=15)
    # NAME / DIGI / WEIGHT / AGE tags (CLUT row 9: ink 2, outline 1, 0 transparent)
    t.fill(128, 48, 208, 58, 0)
    t.fill(128, 58, 147, 68, 0)
    for word, x, y in (('NAME', 129, 48), ('DIGI', 155, 48), ('WEIGHT', 180, 48), ('AGE', 129, 58)):
        t.put(SWW.r_tag(word), x, y, skip=0)
    # TYPE / SPECIAL / ACTIVE (CLUT row 9, two tones, no outline)
    t.fill(0, 56, 76, 64, 0)
    for word, font, main, acc, x in (('TYPE', SW.TSA, 12, 13, 4), ('SPECIAL', SW.TSA_SPECIAL, 6, 7, 25),
                                     ('ACTIVE', SW.TSA_ACTIVE, 8, 9, 52)):
        draw_plain(t, font, word, x, 57, {'#': main, 'x': acc})
    # HAPPINESS / SPEED / BRAINS (CLUT row 4: ink E, shadow D at +1,+1)
    t.fill(212, 58, 256, 94, 15)
    for word, x, y in (('HAPPINESS', 214, 58), ('SPEED', 212, 70), ('BRAINS', 212, 82)):
        t.put(SWW.r_stat(word), x, y, skip=15)
    # PROFILE / CONDITION / PARAMETER on the gold bands (CLUT row 8: ink 1, shadow 8 at +1,+1)
    gold_bands(t, ((75, 'PROFILE', SW.GOLD5), (86, 'CONDITION', SW.GOLD5), (97, 'PARAMETER', SW.GOLD4)))


def gold_bands(t, bands):
    """the three striped bands rebuilt without their letters: inside, each row its majority index; the shaded ends
    (columns 0, 52, 53) the majority of the same pixel in the three bands (the letters sit at different columns);
    then the word centred, ink 1, shadow 8"""
    tops = [v for v, _, _ in bands]
    clean = {}
    for r in range(1, 10):
        row = [t.g(x, v + r) for v in tops for x in range(1, 53)]
        row = [c for c in row if c not in (1, 8)]
        common = max(sorted(set(row)), key=row.count)
        for x in range(0, 54):
            vals = [t.g(x, v + r) for v in tops]
            best = max(sorted(set(vals)), key=vals.count)
            edge = x in (0, 52, 53)                     # the band's shaded ends; inside, one index per row
            clean[(x, r)] = best if edge and vals.count(best) >= 2 and best not in (1, 8) else common
    for v0, word, font in bands:
        for (x, r), c in clean.items():
            t.s(x, v0 + r, c)
        rows = compose(font, word)
        W = len(rows[0])
        x0 = 1 + (52 - (W + 1)) // 2
        draw_shadowed(t, font, word, x0, v0 + 1, 1, 8)


def taisen_f(t):
    """STDDAT/TAISEN_F.TIM, the VS mode's menus (vs_select.c MODE_SELECT_SPRITES / MAP_SELECT_SPRITES: u, v, w, h).
    The 8x8 name font at its top left stays Japanese: the US executable never draws it (VS name chars: AddPrim only
    when !VERSION_IS(US))"""
    # headers: BATTLE MODE SELECT (120, 0, 124, 14), STAGE SELECT (120, 14, 124, 14); background F
    t.fill(120, 0, 248, 28, 15)
    for line, y, words in ((0, 1, ('BATTLE', 'MODE', 'SELECT')), (1, 15, ('STAGE', 'SELECT'))):
        ws = [width(G.HEAD, w) for w in words]
        space = 6
        x = 120 + (124 - (sum(ws) + space * (len(ws) - 1))) // 2
        for w, wd in zip(words, ws):
            draw_rows(t, G.HEAD, w, x, y, G.HEAD_ROWS, 1)
            x += wd + space
    # stage labels, two lines each: (120, 28, 52, 24) BEATWOOD / COLISEUM, (172, 28, 48, 24) EXTRA / COLISEUM,
    # (120, 52, 52, 24) DIGIMON / COLISEUM; each its own ink index
    t.fill(120, 28, 222, 52, 15)
    t.fill(120, 52, 177, 76, 15)
    for u, v, w, ink, top in ((120, 28, 52, 11, 'BEATWOOD'), (172, 28, 48, 8, 'EXTRA'), (120, 52, 52, 3, 'DIGIMON')):
        for word, y in ((top, v + 1), ('COLISEUM', v + 14)):
            draw_outlined(t, G.STAGE9, word, u + (w - width(G.STAGE9, word)) // 2, y, ink, 1)
    # mode labels: BATTLE under each "n vs n" (0 / 52 / 104, 232, 52, 23), ink 3
    t.fill(0, 246, 156, 256, 15)
    for u in (0, 52, 104):
        draw_outlined(t, G.MODE7, 'BATTLE', u + (52 - width(G.MODE7, 'BATTLE', 2)) // 2, 248, 3, 1, gap=2)


# ----------------------------------------------------------------------------------------------- map signposts

# The lit signposts are .MAP sprites (instances that blink over the background's sign board) cut from one 8-bit TIM.
# Per map: the TIM, the crop of the background the art covers, then the messages: the sprites that show one message
# together (their texture rects and their places on the background come from the .MAP), boxes on the background to
# leave alone (the arrows drawn in the same pieces) and the art: the image generator's English sign made from the
# Japanese one on its background (the developer’s full edit), brought back to the crop's size, of which the
# repository keeps only its lamps and their rims (the pixels it changed, CHANGED against the background of the map it
# was made from, that are warm, and the changed ones around them): the cut-out fromjp/<art> (tools/localize/cutout.py;
# --make-cutouts makes them from the developer's full art, build/localized-src/signs/fromjp/<art>.png). MAYO02_2 shows
# MAYO01_2's board and messages at the same place: it takes MAYO01_2's art.
# A lamp of the art is a pixel it changed (against the background of the map it was made from) that is a lamp (warm: red
# well above blue), with the changed pixels around it (its rim); lamps take the nearest colour of the sprite's CLUT,
# the rest of the message's pieces is erased: to the transparent index, or on a sign whose sprite carries its board
# (MAYO01_2, MAYO02_2 on the Japanese disc) to the map's own background pixel there.
# The guard's one exception: FRZL03's GREAT / CANYON. The generator's three tries (an image, a regeneration with the
# cross of its sprites described, an edit request) all left the tip of GREAT's T and the foot of CANYON's N a pixel
# or two outside the pieces: those 9 lamp pixels are cut (exactly 9; any other count stops the build as usual).
CUT = {'frzl03-1': 9}
import cutout  # noqa: E402  (tools/localize/cutout.py)
CHANGED = 60          # summed RGB difference from the background that counts as changed
WARM = {None: 64,     # red minus blue of a lamp; FRZL03's pale yellow lamps on light ice: less
        'MAP/MAP7/FRZL03.MAP': 32}
SIGNS = {
    'MAP/MAP8/MAYO00.MAP': (2, (232, 300, 400, 412), [
        ([18], [], 'mayo00-0'), ([19], [], 'mayo00-1'), ([20], [], 'mayo00-2'), ([21], [], 'mayo00-3')]),
    'MAP/MAP5/GIAS00.MAP': (1, (692, 160, 812, 240), [
        ([39], [], 'gias00-0'), ([40], [], 'gias00-1'), ([41], [], 'gias00-2')]),
    'MAP/MAP7/FRZL03.MAP': (1, (248, 212, 428, 332), [
        ([7, 8], [(366, 252, 400, 276)], 'frzl03-0'),
        ([9, 10, 11], [(310, 288, 340, 308)], 'frzl03-1'),
        ([12, 13, 14, 15], [(292, 243, 320, 262)], 'frzl03-2')]),
    'MAP/MAP8/MAYO01_2.MAP': (2, (228, 312, 396, 424), [([33 + n], [], f'mayo01_2-{n}') for n in range(5)]),
    'MAP/MAP8/MAYO02_2.MAP': (2, (228, 312, 396, 424), [([32 + n], [], f'mayo01_2-{n}') for n in range(5)]),
}


def background(ext, mp):
    """the day background of map mp (a key of SIGNS) inside its crop: (x, y) -> (r, g, b)"""
    sys.path.insert(0, os.path.dirname(HERE))
    import dwmap
    sys.path.pop(0)
    cx0, cy0, cx1, cy1 = SIGNS[mp][1]
    mm = dwmap.MapFile(open(os.path.join(ext, mp), 'rb').read())
    tf = dwmap.TfsFile(open(os.path.join(ext, mp[:-4] + '.TFS'), 'rb').read())
    _, _, img = tf.image_indices(mm)
    pal = tf.palette_rgb(0)
    return {(x, y): tuple(pal[img[y][x]][:3]) for y in range(cy0, cy1) for x in range(cx0, cx1)}


def art_map(art):
    """the map (a key of SIGNS) art was made on"""
    return next(p for p in SIGNS if os.path.basename(p)[:-4].lower() == art.rsplit('-', 1)[0])


def changed_pixels(new, base):
    """the pixels of new (x, y) -> (r, g, b) that differ from base's by more than CHANGED"""
    return {p for p, c in new.items() if sum(abs(a - b) for a, b in zip(c, base[p])) > CHANGED}


def map_signs(data, path, ext):
    """data: the whole .MAP (bytearray); only the sign TIM's pixels change"""
    sys.path.insert(0, os.path.dirname(HERE))
    import dwmap
    sys.path.pop(0)
    k, (cx0, cy0, cx1, cy1), messages = SIGNS[path]
    m = dwmap.MapFile(bytes(data))
    sec = struct.unpack_from('<I', data, 4 * (1 + k))[0]          # the offset table: setup, then the TIMs
    tim = dwmap.TIM(m.tims[k])
    t = Tex(data, 0, base=sec)
    clut = tim.clut[4][:tim.clut[2]]
    rgb = [((v & 31) << 3, (v >> 5 & 31) << 3, (v >> 10 & 31) << 3) for v in clut]
    opaque = [i for i, v in enumerate(clut) if v != 0]
    memo = {}

    def nearest(c):
        if c not in memo:
            memo[c] = min(opaque, key=lambda i: (sum((p - q) ** 2 for p, q in zip(rgb[i], c)), i))
        return memo[c]
    used = {}
    for v in t.p:
        used[v] = used.get(v, 0) + 1
    clear = max((i for i, v in enumerate(clut) if v == 0), key=lambda i: (used.get(i, 0), -i))

    own = background(ext, path)

    def art_lamps(art, kept):
        """the generator's sign: -> {background pixel: CLUT index} of its lamps and their rim, and the lamps"""
        src = art_map(art)
        base = own if src == path else background(ext, src)
        w, h, px = cutout.load(f'fromjp/{art}', list(base.values()))
        if (w, h) != (cx1 - cx0, cy1 - cy0):
            sys.exit(f'fromjp/{art}: a cut-out of a {w}x{h} crop, the crop is {cx1 - cx0}x{cy1 - cy0}')
        new = {(cx0 + i % w, cy0 + i // w): c[:3] for i, c in enumerate(px) if c[3]}   # (only the pixels it changed)
        changed = changed_pixels(new, base)
        warm = WARM.get(path, WARM[None])
        lamps = {p for p in changed if new[p][0] - new[p][2] > warm and not kept(*p)}
        rim = {(x + i, y + j) for x, y in lamps for i in (-1, 0, 1) for j in (-1, 0, 1)} & changed
        return {p: nearest(new[p]) for p in lamps | rim}, lamps
    for sids, keep, art in messages:
        pieces = []
        for sid in sids:
            sp = m.sprites[sid]
            page = 384 + (sp['texX'] // 256) * 128
            u0 = (page - tim.x) * 2 + sp['texX'] % 256
            inst = next(i for i in m.instances if sid in i['frames'])
            pieces.append((u0, sp['texY'] - tim.y, sp['width'], sp['height'], inst['x'], inst['y']))

        def kept(x, y):
            return any(kx0 <= x < kx1 and ky0 <= y < ky1 for kx0, ky0, kx1, ky1 in keep)
        px = [(u + i, v + j, x + i, y + j) for u, v, w, h, x, y in pieces for j in range(h) for i in range(w)
              if not kept(x + i, y + j)]
        board = sum(1 for u, v, _, _ in px if clut[t.g(u, v)] != 0) > len(px) // 2
        lit, lamps = art_lamps(art, kept)
        lost = sorted(lamps - {(x, y) for _, _, x, y in px})
        if lost and len(lost) == CUT.get(art):         # the one exception: these few are cut, known and counted
            lost = []
        if lost:                                        # a lamp outside the message's pieces would be cut
            sys.exit(f'{path}: {len(lost)} lamp pixels of {art} fall outside sprites {sids}: {lost}')
        for u, v, x, y in px:
            if (x, y) in lit:
                t.s(u, v, lit[(x, y)])
            elif board and clut[t.g(u, v)] != 0:
                t.s(u, v, nearest(own[(x, y)]))
            else:
                t.s(u, v, clear)
    t.write(data)


RECIPES = [
    ('ETCDAT/BI_IN.TIM', None, 0, bi_in),
    ('ETCDAT/ETCTIM.BIN', None, 0, bi_in),
    ('ETCDAT/FI_INFO.TIM', None, 0, fi_info),
    ('ETCDAT/ETCTIM.BIN', None, 4, fi_info),
    ('ETCDAT/SYSTEM_W.TIM', None, 0, system_w),
    ('ETCDAT/ETCTIM.BIN', None, 8, system_w),
    ('STDDAT/TAISEN_F.TIM', None, 0, taisen_f),
]


# written as the Japanese disc has them (listed in files.txt all the same, the base-disc tool expects every one):
# STDDAT/STDTIM.BIN's entries 3 and 4 are the katakana name fonts of the tournament and VS intros, which the US
# executable never draws (STD_renderIntroNameChar, STD_renderBracketGlyph: AddPrim only when !VERSION_IS(US)); the
# titles wait for the owner's choice (the Japanese logo is a different picture)
UNCHANGED = ['STDDAT/STDTIM.BIN', 'ETCNA/TITLE256.TIM', 'ETCNA/TITLE2.TIM']


def build(ext):
    """-> {disc path: bytearray}"""
    files = {p: bytearray(open(os.path.join(ext, p), 'rb').read()) for p in UNCHANGED}
    for path, _, entry, fn in RECIPES:
        if path not in files:
            files[path] = bytearray(open(os.path.join(ext, path), 'rb').read())
        t = Tex(files[path], entry)
        fn(t)
        t.write(files[path])
    for path in SIGNS:
        files[path] = bytearray(open(os.path.join(ext, path), 'rb').read())
        map_signs(files[path], path, ext)
    return files


def make_cutouts(ext, src=None):
    """The developer's: the signposts' cut-outs (tools/localize/cutout.py) from the full art in src (default
    build/localized-src/signs/fromjp: <art>.png, make.py reduce's), each the pixels it changed against the background
    of its map on the Japanese disc in ext. -> the names written"""
    sys.path.insert(0, os.path.dirname(HERE))
    import dwmap
    sys.path.pop(0)
    src = src or os.path.join(cutout.SRC, 'fromjp')
    done = []
    for art in sorted({a for _, _, ms in SIGNS.values() for _, _, a in ms}):
        mp = art_map(art)
        cx0, cy0, cx1, cy1 = SIGNS[mp][1]
        w, h, mode, rows, _ = dwmap.png_read(os.path.join(src, art + '.png'))
        if (w, h, mode) != (cx1 - cx0, cy1 - cy0, 'RGB'):
            sys.exit(f'{art}.png: {w}x{h} {mode}, the crop is {cx1 - cx0}x{cy1 - cy0} RGB')
        new = {(cx0 + x, cy0 + y): tuple(rows[y][3 * x:3 * x + 3]) for y in range(h) for x in range(w)}
        base = background(ext, mp)
        changed = changed_pixels(new, base)
        # only what map_signs takes of it: the lamps (warm changed pixels, by the lowest warmth of the maps that show
        # it, whatever their kept boxes) and their rim; map_signs finds the same lamps and rims in them
        warm = min(WARM.get(p, WARM[None]) for p, (_, _, ms) in SIGNS.items() if any(a == art for _, _, a in ms))
        lamps = {q for q in changed if new[q][0] - new[q][2] > warm}
        keep = lamps | ({(x + i, y + j) for x, y in lamps for i in (-1, 0, 1) for j in (-1, 0, 1)} & changed)
        cutout.save(f'fromjp/{art}', w, h, [(*new[(cx0 + i % w, cy0 + i // w)], 255)
                                            if (cx0 + i % w, cy0 + i // w) in keep else (0, 0, 0, 0)
                                            for i in range(w * h)], list(base.values()))
        done.append(art)
    print(f'{cutout.CUTOUTS}: {len(done)} signpost cut-outs from {src}')
    return done


def compare(files, us):
    for path, _, entry, _ in RECIPES:
        if path in SIGNS:
            continue
        a = Tex(files[path], entry)
        b = Tex(bytearray(open(os.path.join(us, path), 'rb').read()), entry)
        d = [i for i in range(len(a.p)) if a.p[i] != b.p[i]]
        box = (min(i % a.w for i in d), min(i // a.w for i in d), max(i % a.w for i in d), max(i // a.w for i in d)) if d else ''
        print(f'{path} entry {entry}: {len(d)} pixels differ from the US one {box}')


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('out', nargs='?')
    ap.add_argument('--extracted', required=True, help="the Japanese disc's files")
    ap.add_argument('--compare', help='a US dump: print how far each texture is from the US one')
    ap.add_argument('--make-cutouts', action='store_true', help='remake the signposts\' cut-outs from --src')
    ap.add_argument('--src', help='the full art (default build/localized-src/signs/fromjp)')
    a = ap.parse_args()
    if a.make_cutouts:
        make_cutouts(a.extracted, a.src)
        return
    if not a.out:
        ap.error('OUTDIR is needed')
    files = build(a.extracted)
    for path, data in sorted(files.items()):
        p = os.path.join(a.out, path)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        open(p, 'wb').write(data)
    open(os.path.join(a.out, 'files.txt'), 'w').write(''.join(p + '\n' for p in sorted(files)))
    print(f'{a.out}: {len(files)} files ({", ".join(sorted(files))})')
    if a.compare:
        compare(files, a.compare)


if __name__ == '__main__':
    main()
