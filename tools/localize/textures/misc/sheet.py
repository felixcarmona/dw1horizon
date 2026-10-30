"""Side-by-side sheets (lado-a-lado-*.png) + banner pictures + rects.json. Runs build.py's steps first."""

# Allow both direct script execution and package imports.
import sys as _image_sys
from pathlib import Path as _ImagePath
_image_sys.path.insert(0, str(next(p for p in _ImagePath(__file__).resolve().parents if (p / 'tools').is_dir())))
import json, os, random, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build
from build import WORDS, RECTS, OUT
from tex import Tex
from tools.image import Image, ImageDraw, ImageFont, ImageChops

for f in ('push', 'life', 'title', 'timeup', 'vsmode', 'taisen_f', 'banner'):
    getattr(build, f)()
json.dump(RECTS, open(f'{OUT}/rects.json', 'w'), ensure_ascii=False, indent=1)
if os.path.exists(f'{OUT}/rects.part.json'):
    os.remove(f'{OUT}/rects.part.json')

FONT = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 22)
FONTB = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', 26)
S = 4


def crop(t, clut, r, bg, tint=None, add=False):
    u, v, w, h = r
    im = t.image(clut, (u, v, w, h))
    if tint:
        px = im.load()
        for y in range(im.height):
            for x in range(im.width):
                p = px[x, y]
                px[x, y] = (int(p[0] * tint[0]), int(p[1] * tint[1]), int(p[2] * tint[2]), p[3])
    base = Image.new('RGBA', im.size, bg + (255,))
    if add:
        rgb = Image.new('RGBA', im.size, (0, 0, 0, 255)); rgb.alpha_composite(im)
        out = ImageChops.add(base.convert('RGB'), rgb.convert('RGB'))
        return out.convert('RGBA')
    base.alpha_composite(im)
    return base


def big(im, s=S):
    return im.resize((im.width * s, im.height * s), Image.NEAREST)


def sheet(name, title, rows, extra=()):
    """rows: list of (caption, en_img, es_img). extra: list of (caption, img) full width."""
    pad = 16
    blocks = []
    for cap, a, b in rows:
        a, b = big(a), big(b)
        side = a.width + b.width + 3 * pad <= 1300
        blocks.append((cap, a, b, side))
    W = 2 * pad
    for cap, a, b, side in blocks:
        W = max(W, (a.width + b.width + 3 * pad) if side else max(a.width, b.width) + 2 * pad)
    for cap, im in extra:
        W = max(W, im.width + 2 * pad)
    W = max(W, 700)
    H = 60
    for cap, a, b, side in blocks:
        H += 34 + 26 + (max(a.height, b.height) if side else a.height + b.height + 30) + pad
    for cap, im in extra:
        H += 34 + im.height + pad
    out = Image.new('RGB', (W, H), (236, 236, 232)); d = ImageDraw.Draw(out)
    d.text((pad, 14), title, font=FONTB, fill=(20, 20, 20))
    y = 60
    for cap, a, b, side in blocks:
        d.text((pad, y), cap, font=FONT, fill=(30, 30, 30)); y += 34
        if side:
            d.text((pad, y), 'EN', font=FONT, fill=(110, 110, 110)); d.text((2 * pad + a.width, y), 'ES', font=FONT, fill=(110, 110, 110))
            y += 26; out.paste(a, (pad, y)); out.paste(b, (2 * pad + a.width, y)); y += max(a.height, b.height) + pad
        else:
            d.text((pad, y), 'EN', font=FONT, fill=(110, 110, 110)); y += 26
            out.paste(a, (pad, y)); y += a.height + 4
            d.text((pad, y), 'ES', font=FONT, fill=(110, 110, 110)); y += 26
            out.paste(b, (pad, y)); y += b.height + pad
    for cap, im in extra:
        d.text((pad, y), cap, font=FONT, fill=(30, 30, 30)); y += 34
        out.paste(im, (pad, y)); y += im.height + pad
    out.save(f'{OUT}/{name}')


def w(k, which):
    t, clut, r = WORDS[k][which]
    return t, clut, r


# ------------------------------------------------ banner pictures
tiles = Tex('ETCDAT/BI_IN.TIM')
def banner_img(pts, clut=8, seed=1):
    rnd = random.Random(seed)
    tl = [tiles.image(clut, (128 + k * 8, 0, 8, 8)).resize((8, 12), Image.NEAREST) for k in range(3)]
    im = Image.new('RGBA', (400, 130), (28, 30, 44, 255))
    for x, y in pts:
        im.alpha_composite(tl[rnd.randrange(3)], (x + 196, y + 60))
    return im
bw = WORDS['banner']
ben, bes = banner_img(bw['en']), banner_img(bw['main'])
big(ben, 3).save(f'{OUT}/battle-banner-en.png'); big(bes, 3).save(f'{OUT}/battle-banner-es.png')
balt1, balt2 = banner_img(bw['wide']), banner_img(bw['lucha'])

# ------------------------------------------------ battle screen mock (320x240): TIME UP centred, ○PUSH top right
def battle_mock(k_time, k_push):
    im = Image.new('RGBA', (320, 240), (52, 66, 52, 255)); d = ImageDraw.Draw(im)
    for yy in range(150, 240, 6):
        d.line((0, yy, 320, yy), fill=(60, 78, 58, 255))
    t, c, r = WORDS['push'][k_push]
    pw = r[2]
    dx = 0 if k_push == 'en' else -(pw - 37)
    box = Image.new('RGBA', (41 + pw - 37, 11), (128, 128, 128, 128)); im.alpha_composite(box, (160 + 108 + dx, 120 - 76))
    im.alpha_composite(t.image(c, r), (160 + 110 + dx, 120 - 75))
    t, c, r = WORDS['timeup'][k_time]
    im.alpha_composite(t.image(c, r), (160 - 72, 120 - 12))
    return im
mock_en, mock_es = battle_mock('en', 'en'), battle_mock('es', 'es')
m = Image.new('RGB', (320 * 2 * 2 + 16, 240 * 2), (236, 236, 232))
m.paste(big(mock_en, 2), (0, 0)); m.paste(big(mock_es, 2), (640 + 16, 0))

p = WORDS['push']; tu = WORDS['timeup']
cb = WORDS['banner']['counts']
sheet('lado-a-lado-combate.png', 'Combate: ○PUSH, TIME UP, cartel BATTLE', [
    ('○PUSH -> ○PULSA (especial listo; 37 -> %d px de ancho)' % p['es'][2][2], crop(*w('push', 'en'), (100, 100, 100)), crop(*w('push', 'es'), (100, 100, 100))),
    ('TIME UP -> ¡TIEMPO! (mismo rectángulo 144x24)', crop(*w('timeup', 'en'), (48, 56, 48)), crop(*w('timeup', 'es'), (48, 56, 48))),
], extra=[
    ('Pantalla (maqueta 320x240, x2): izquierda EN, derecha ES', m),
    ('Cartel BATTLE (155 bloques)', big(ben, 3)),
    ('¡LUCHA! — propuesta: %d bloques + 1 repetido = 155, sin cambiar el tamaño de la tabla' % cb['main'][0], big(bes, 3)),
    ('Alternativa: ¡ ! de 2 columnas = %d bloques (hay que ampliar las tablas a %d)' % (cb['wide'][0], cb['wide'][0]), big(balt1, 3)),
    ('Alternativa: LUCHA sin signos = %d bloques (+%d repetidos)' % (cb['lucha'][0], 155 - cb['lucha'][0]), big(balt2, 3)),
])

# ------------------------------------------------ VIDA
sheet('lado-a-lado-vida.png', 'Vidas (LIFE.TIM, mezcla aditiva)', [
    ('LIFE -> VIDA (mismo rectángulo 64x24)', crop(*w('life', 'en'), (24, 24, 32), add=True), crop(*w('life', 'es'), (24, 24, 32), add=True)),
    ('Textura completa (corazones incluidos)', crop(WORDS['life']['en'][0], 0, (0, 0, 112, 24), (24, 24, 32), add=True),
     crop(WORDS['life']['es'][0], 0, (0, 0, 112, 24), (24, 24, 32), add=True)),
])

# ------------------------------------------------ título
tw = WORDS['title']
shot = Image.open(f'{OUT}/../common/en_title.png').convert('RGBA')
bgtex = tw['en'][0].image(0)
def title_mock(t, r, x):
    im = shot.copy()
    im.paste(bgtex.crop((100, 168, 240, 182)), (100, 168))   # the background under the text (drawn 1:1)
    spr = t.image(0, r); px = spr.load()
    for yy in range(spr.height):
        for xx in range(spr.width):
            q = px[xx, yy]
            px[xx, yy] = (0, q[1], 0, 255 if q[1] > 8 else 0)
    im.alpha_composite(spr, (160 + x, 120 + 49))   # the Spanish quad starts one row higher (texture row 240)
    return im
en_m = shot
es_m = title_mock(tw['es'][0], tw['es'][2], round(tw['cx'] - tw['W'] / 2))
alt_m = title_mock(tw['alt'][0], tw['alt'][2], round(tw['cx'] - tw['Wa'] / 2))
tm = Image.new('RGB', (640 * 2 + 16, 480), (236, 236, 232))
tm.paste(big(en_m, 2), (0, 0)); tm.paste(big(es_m, 2), (656, 0))
tm2 = big(alt_m, 2)
en_t = tw['en']
sheet('lado-a-lado-titulo.png', 'Pantalla de título (TITLE256.TIM)', [
    ('Press Start Button -> Pulsa el botón START (%d px; parpadea en verde)' % tw['W'],
     crop(en_t[0], 0, (0, 240, 121, 11), (0, 0, 0), tint=(0, 1, 0)), crop(tw['es'][0], 0, tw['es'][2], (0, 0, 0), tint=(0, 1, 0))),
    ('Sin tinte (como está en la textura)', crop(en_t[0], 0, (0, 240, 121, 11), (0, 0, 0)), crop(tw['es'][0], 0, tw['es'][2], (0, 0, 0))),
    ('Alternativa corta: Pulsa START (%d px)' % tw['Wa'], crop(en_t[0], 0, (0, 240, 121, 11), (0, 0, 0), tint=(0, 1, 0)),
     crop(tw['alt'][0], 0, tw['alt'][2], (0, 0, 0), tint=(0, 1, 0))),
], extra=[('Maqueta sobre la captura (x2): izquierda EN, derecha ES', tm), ('Alternativa corta en pantalla', tm2)])

# ------------------------------------------------ modo VS
en_f, es_f = WORDS['taisen']['t']
BOXBG = (28, 36, 70)
def lab(t, clut, r): return crop(t, clut, r, BOXBG)
rows = [
    ('BATTLE MODE SELECT -> MODO DE COMBATE', lab(en_f, 1, (120, 0, 124, 14)), lab(es_f, 1, (120, 0, 124, 14))),
    ('STAGE SELECT -> ELIGE ESCENARIO', lab(en_f, 2, (120, 14, 124, 14)), lab(es_f, 2, (120, 14, 124, 14))),
]
def pair(t, r, c1, c2):
    a = lab(t, c1, r); b = lab(t, c2, r)
    im = Image.new('RGBA', (a.width * 2 + 4, a.height), BOXBG + (255,)); im.paste(a, (0, 0)); im.paste(b, (a.width + 4, 0)); return im
for n, num in enumerate(['7 vs 7', '3 vs 3', '5 vs 5']):
    r = (n * 52, 232, 52, 23)
    rows.append((f'{num} / BATTLE -> COMBATE / {num} (elegido | sin elegir)', pair(en_f, r, 12, 13), pair(es_f, r, 12, 13)))
for name_en, name_es, r in (('BEATWOOD / COLISEUM', 'COLISEO / BEATWOOD', (120, 28, 52, 24)),
                            ('DIGIMON / COLISEUM', 'COLISEO / DIGIMON', (120, 52, 52, 24)),
                            ('EXTRA / COLISEUM', 'COLISEO / EXTRA', (172, 28, 48, 24))):
    rows.append((f'{name_en} -> {name_es} (elegido | sin elegir)', pair(en_f, r, 3, 4), pair(es_f, r, 3, 4)))
vw = WORDS['vsmode']
rows.append(('VS MODE -> MODO VS (TAISEN2.TIM, 77 -> 79 px)', crop(*vw['en'], (40, 40, 56)), crop(*vw['es'], (40, 40, 56))))

# screen mock of the two select boxes (positions from MODE_SELECT_SPRITES / MAP_SELECT_SPRITES, box at -90,-70 180x128)
MODE = [(1, 120, 0, 124, 14, 28, 7), (12, 0, 232, 52, 23, 10, 96), (13, 52, 232, 52, 23, 65, 96), (13, 104, 232, 52, 23, 122, 96)]
MAP = [(2, 120, 14, 124, 14, 28, 7), (3, 120, 52, 52, 24, 8, 96), (4, 120, 28, 52, 24, 64, 96), (4, 172, 28, 48, 24, 122, 96)]
def box_mock(t, spr):
    im = Image.new('RGBA', (320, 240), (10, 10, 16, 255)); d = ImageDraw.Draw(im)
    d.rectangle((70, 50, 70 + 179, 50 + 127), fill=BOXBG + (255,), outline=(200, 200, 220, 255))
    for i in range(3):
        d.rectangle((70 + [14, 70, 126][i], 50 + 37, 70 + [14, 70, 126][i] + 39, 50 + 37 + 47), fill=(60, 70, 110, 255))
    for c, u, v, ww, hh, x, y in spr:
        im.alpha_composite(t.image(c, (u, v, ww, hh)), (70 + x, 50 + y))
    d.rectangle((70 + 8, 50 + 31 + 60, 70 + 8 + 51, 50 + 31 + 60 + 1), fill=(255, 230, 0, 255))
    return im
bm = Image.new('RGB', (640 * 2 + 16, 480 * 2 + 16), (236, 236, 232))
bm.paste(big(box_mock(en_f, MODE), 2), (0, 0)); bm.paste(big(box_mock(es_f, MODE), 2), (656, 0))
bm.paste(big(box_mock(en_f, MAP), 2), (0, 496)); bm.paste(big(box_mock(es_f, MAP), 2), (656, 496))
sheet('lado-a-lado-modo-vs.png', 'Modo VS (TAISEN_F.TIM, TAISEN2.TIM)', rows,
      extra=[('Maqueta de las cajas (x2; retratos como rectángulos): izquierda EN, derecha ES', bm)])
print('ok')
