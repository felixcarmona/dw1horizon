"""Offline pixel edits of the native 11x11 battle HUD silhouettes."""
from PIL import ImageColor

# '.' keeps the native texel. Every other symbol places one authored pixel.
CROSS = ['...........', '...........', '...........', '.....w.....',
         '....www....', '.....w.....', '...........', '...........',
         '...........', '...........', '...........']
LOW = ['...........', '...........', '...........', '...........',
       '........kkk', '........krk', '........krk', '........krk',
       '........kkk', '........krk', '........kkk']
CRACK = ['...........', '...........', '.....k.....', '....kk.....',
         '....k......', '....kk.....', '.....k.....', '....kk.....',
         '....k......', '...........', '...........']
MEDICAL = ['...........', '...........', '...........', '....RwR....',
           '....www....', '....RwR....', '...........', '...........',
           '...........', '...........', '...........']
INK = {'w': '#fff8e8', 'k': '#101010', 'r': '#ff4030', 'R': '#782020'}


def overlay(base, rows):
    assert len(rows) == 11 and all(len(row) == 11 for row in rows)
    im = base.copy()
    for y, row in enumerate(rows):
        for x, value in enumerate(row):
            if value != '.':
                im.putpixel((x, y), ImageColor.getrgb(INK[value]) + (255,))
    return im


def depleted(base):
    """Keep the original silhouette; colour only its bottom ~30% by height."""
    im = base.copy()
    for y in range(7):
        for x in range(11):
            r, g, b, alpha = base.getpixel((x, y))
            if alpha and max(r, g, b) > 20:
                im.putpixel((x, y), (58, 58, 66, 255))
    return im


def dimmed(base):
    im = base.copy()
    for y in range(11):
        for x in range(11):
            r, g, b, alpha = base.getpixel((x, y))
            if alpha and max(r, g, b) > 20:
                im.putpixel((x, y), (r // 3, g // 3, b // 3, alpha))
    return im


def make(heart, orb):
    return {
        '4a-hp': depleted(heart), '4a-mp': depleted(orb),
        '4b-hp': overlay(heart, MEDICAL), '4b-mp': depleted(orb),
        '4c-hp': overlay(heart, LOW), '4c-mp': overlay(orb, LOW),
        '4d-hp': overlay(heart, CRACK), '4d-mp': dimmed(orb),
        '4e-hp': overlay(depleted(heart), CROSS), '4e-mp': depleted(orb),
    }
