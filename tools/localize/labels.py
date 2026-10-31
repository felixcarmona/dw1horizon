"""Small localized UI labels, rendered from the committed bitmap fonts.

Uses the established Spanish texture cells so runtime sprite geometry stays
identical across translations. No Pillow, downloads or subprocesses.
"""
from collections import Counter
from functools import lru_cache
import json
import os

from tools.localize.catalog import LANGUAGES, UI, word

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BATTLE = dict(fr='COMBAT!', de='KAMPF!', it='LOTTA!', ja='バトル!', ca='COMBAT!')


@lru_cache(None)
def glyphs():
    import sys
    sys.path.insert(0, os.path.join(ROOT, 'tools'))
    import fontgen
    table = {ch: rows for ch, _, rows in fontgen.load_extra()}
    table.update({ch: rows for ch, (_, rows) in fontgen.load_font_txt(os.path.join(ROOT, 'tools/font/b.txt')).items()})
    return table


def mask(text, maxw, maxh, preserve=False):
    table = glyphs()
    rows = [[] for _ in range(11)]
    for char in text:
        if char == ' ':
            cell = ['....'] * 11
        else:
            cell = table[char]
            width = max((row.rfind('#') + 1 for row in cell), default=1)
            cell = [row[:max(1, width)] + '.' for row in cell]
        for out, row in zip(rows, cell):
            out.extend(c == '#' for c in row)
    if not rows[0]:
        return [[False]]
    occupied = [y for y, row in enumerate(rows) if any(row)]
    if occupied:
        rows = rows[occupied[0]:occupied[-1] + 1]
    h, w = len(rows), len(rows[0])
    height = min(h, maxh)
    width = min(maxw, max(1, round(w * height / h)))
    if preserve:
        return [[any(rows[sy][sx]
                     for sy in range(y*h//height, max(y*h//height+1, (y+1)*h//height))
                     for sx in range(x*w//width, max(x*w//width+1, (x+1)*w//width)))
                 for x in range(width)] for y in range(height)]
    return [[rows[min(h - 1, y * h // height)][min(w - 1, x * w // width)] for x in range(width)] for y in range(height)]


def battle_banner(language):
    rows = mask(BATTLE[language], 36, 7)
    width = len(rows[0])
    points = [[-(width * 8) // 2 + x * 8, -48 + y * 12] for y, row in enumerate(rows) for x, ink in enumerate(row) if ink]
    if not points or len(points) > 155:
        raise ValueError(f'{language}: battle banner has {len(points)} blocks')
    return dict(text=BATTLE[language], blocks_drawn=len(points), entries=155,
                positions=points + [points[-1]] * (155 - len(points)))


def apply(files, language, work):
    if language not in LANGUAGES:
        return
    from tools.localize.build import tim_entries, put_indices
    col = LANGUAGES.index(language)
    grids = {}

    def grid(path, entry=0):
        key = path, entry
        if key not in grids:
            data = files[language, path]
            start, bpp, w, h = tim_entries(data)[entry]
            if bpp == 0:
                raw = data[start:start + w * h // 2]
                px = [v for b in raw for v in (b & 15, b >> 4)]
            elif bpp == 1:
                px = list(data[start:start + w * h])
            else:
                raise ValueError('indexed texture expected')
            grids[key] = w, h, px
        return grids[key]

    def draw(path, rect, text, ink, background, shadow=None, entry=0, gradient=None, preserve=False, padding=2):
        w, h, px = grid(path, entry)
        u, v, rw, rh = rect
        if not (0 <= u < u + rw <= w and 0 <= v < v + rh <= h):
            raise ValueError((path, rect, w, h))
        bands = [Counter(px[(v+y)*w+u:(v+y)*w+u+rw]).most_common(1)[0][0] for y in range(rh)] if background is None else [background] * rh
        for y in range(rh):
            px[(v+y)*w+u:(v+y)*w+u+rw] = [bands[y]] * rw
        bitmap = mask(text, rw - padding, rh - padding, preserve=preserve)
        bh, bw = len(bitmap), len(bitmap[0])
        x0, y0 = u + (rw-bw)//2, v + (rh-bh)//2
        points = {(x0+x, y0+y) for y, row in enumerate(bitmap) for x, on in enumerate(row) if on}
        if shadow is not None:
            for x, y in points:
                if x+1 < u+rw and y+1 < v+rh and (x+1,y+1) not in points:
                    px[(y+1)*w+x+1] = shadow
        for x, y in points:
            px[y*w+x] = gradient(y-v) if gradient else ink

    # Gold, tag, stat, element and header labels: retain each existing palette.
    from tools.localize.systemw import relocated_rect

    items = json.load(open(os.path.join(work, 'systemw', 'rects.json')))
    elements = {'FIRE', 'BATTLE', 'AIR', 'EARTH', 'ICE', 'MECH', 'FILTH'}
    for item in items:
        if item['es'] not in UI:
            continue
        text = word(item['es'], language)
        clut = item['clut_row']
        ink, bg, sh = (1, None, 8) if clut == 8 else (2, 0, 1) if clut == 9 else (14, 15, 13) if item['en'] in ('HAPPINESS', 'SPEED', 'BRAINS', 'SPEED (alternative)') else (10, 15, 13) if item['en'] in elements else (1, 15, 13)
        rect = relocated_rect(item) or [item[k] for k in ('u','v','w','h')]
        for path, entry in [('ETCDAT/SYSTEM_W.TIM',0), ('ETCDAT/ETCTIM.BIN',8)]:
            draw(path, rect, text, ink, bg, sh, entry, preserve=True)

    # Triangle-menu cells; the unchanged DIGIMON label uses the disc's lettering.
    from tools.localize.fi_info import CELLS, SHARED_SIZES, check_cells
    # These dimensions are the shared non-English GameMenuLabel rows printed by
    # fi-info/build.py. Include the shadow and the nine-row REÑIR sprite.
    sizes = SHARED_SIZES
    check_cells([(u, v, *sizes[e]) for e, (_, u, v) in CELLS.items()])
    for e, (text, u, v) in CELLS.items():
        width, height = sizes[e]
        for path, entry in [('ETCDAT/FI_INFO.TIM', 0), ('ETCDAT/ETCTIM.BIN', 4)]:
            draw(path, (u, v, width, height), word(text, language), 15, 0, 1,
                 entry, preserve=True, padding=1)

    # The four open-tournament captions sit below the AI-generated logo band.
    from tools.localize.build import tim_rgb
    for letter in 'ABCD':
        path = 'STDDAT/GRADE/GRADE' + letter + '.TIM'
        _, _, _, _, palette = tim_rgb(bytes(files[language,path]))
        def nearest(value):
            return min(range(1,len(palette)),key=lambda i: sum((a-b)**2 for a,b in zip(((palette[i]&31)*8,((palette[i]>>5)&31)*8,((palette[i]>>10)&31)*8),value)))
        white,grey = nearest((248,248,248)),nearest((64,64,64))
        captions = [('COLISÉE DIGITALMONSTER','TOURNOI OUVERT','CATÉGORIE '),
                    ('DIGITALMONSTER-KOLOSSEUM','OFFENES TURNIER','KLASSE '),
                    ('COLOSSEO DIGITALMONSTER','TORNEO APERTO','CATEGORIA '),
                    ('デジタルモンスター コロシアム','オープンたいかい','ランク '),
                    ('COLISEU DIGITALMONSTER','TORNEIG OBERT','CATEGORIA ')][col]
        draw(path,(0,64,256,14),captions[0],white,0,grey)
        draw(path,(0,78,256,15),captions[1],white,0,grey)
        draw(path,(0,93,256,27),captions[2]+letter,white,0,grey)

    push = ('APPUYEZ','DRÜCKEN','PREMI','おす','PREM')[col]
    finish = ('FINI!','FINALE!','FINALE!','ひっさつ!','FINAL!')[col]
    for path, entry in [('ETCDAT/BI_IN.TIM',0), ('ETCDAT/ETCTIM.BIN',0)]:
        draw(path,(139,8,31,9),push,10,0,1,entry)
        draw(path,(0,29,46,15),finish,12,0,10,entry,lambda y: 11 if y >= 12 else 14 if y >= 10 else 12)
    draw('ETCHI/LIFE.TIM',(48,0,64,24),('VIE','LEBEN','VITA','のこり','VIDA')[col],7,0,8)
    draw('ETCNA/TITLE256.TIM',(0,240,129,11),('Appuyez sur START','START drücken','Premi START','START をおして','Prem START')[col],0,255,91)
    draw('STDDAT/STDTIM.BIN',(0,8,144,24),('TEMPS ÉCOULÉ!','ZEIT UM!','TEMPO!','じかんぎれ!','TEMPS!')[col],1,0,15,2)
    draw('STDDAT/TAISEN2.TIM',(48,0,79,14),('MODE VS','VS-MODUS','MODO VS','VS モード','MODE VS')[col],1,15,14)
    draw('STDDAT/TAISEN_F.TIM',(120,0,124,13),('MODE COMBAT','KAMPFMODUS','MODO LOTTA','バトルモード','MODE COMBAT')[col],5,15,1)
    draw('STDDAT/TAISEN_F.TIM',(120,14,124,13),('CHOISIR UNE ARÈNE','ARENA WÄHLEN','SCEGLI ARENA','ステージせんたく','TRIA ESCENARI')[col],5,15,1)
    draw('STDDAT/TAISEN_F.TIM',(0,248,51,8),('COMBAT','KAMPF','LOTTA','バトル','COMBAT')[col],3,0,1)
    for (path, entry), (w,h,px) in grids.items():
        put_indices(files[language,path],entry,px)
    json.dump(battle_banner(language),open(os.path.join(work,'battle-banner-es.json'),'w'),ensure_ascii=False)
