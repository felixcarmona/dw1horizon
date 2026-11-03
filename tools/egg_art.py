#!/usr/bin/env python3
"""The four new eggs of the rebirth scene, drawn into the player's own egg texture (ETCDAT/TAMA.TIM).

  egg_art.py OUTDIR [--extracted DIR]          OUTDIR/ETCDAT/TAMA.TIM

When the partner dies the player picks one of the eggs (doo2.c, dooa.c; patch 0334). The original four stay as they
are; the four new ones hatch the hand-made Fresh babies and wear their official Digi-Egg colours (wikimon's Digitama
artwork): Pabumon plain green, Pichimon plain cyan, YukimiBotamon silver with two black zigzags, Nyokimon red with
peach spots.

TAMA.TIM is a 4-bit 256x80 texture with 16 CLUT rows (VRAM 128,488): the 3D eggs' skin at u 0-95 (rows 488-491, the
4 groups of six objects of TAMA.TMD), the four 32x32 selection icons at u 96-223 (rows 492-495) and the cursor
(row 496). Rows 497-503 and the texels at u 136-255, v 32-79 are empty. Written here, from the disc's own pixels:

- the new icons, 28 texels wide (the original icons' columns 2-29, the others are empty) at u 136, 164, 192, 220,
  v 40: Pabumon's and Pichimon's are the spotted icon with its spots filled in from the shell's shading around them,
  Nyokimon's the spotted icon, YukimiBotamon's the plain one with two zigzags;
- one CLUT row per new egg, 497-500, read by its icon and by its 3D egg (the scene copies it over the row of the
  3D egg it borrows, 488 + group, at the hatch: patch 0334). Indices 1-5 are the 3D skin's colours as in the original
  rows (index 1 the shell, 2-5 the pattern), 6-13 the icon's shell shading, 14 and 15 the outline;
- YukimiBotamon's zigzags on the 3D egg: the egg borrows group 1 (the wave egg), whose skin maps v 0-47 twice down
  the egg and u 0-95 once round it, so one zigzag band at v 17-30 shows as two. Its texels take indices the original
  row 489 never read (15 over the shell, 7, 13, 8 and 9 over the wave's 2-5); row 489 gets those indices with the
  colours they cover, so the original egg looks as before, and the YukimiBotamon row shows them dark.

Only pixel indices of empty texels, empty CLUT rows and unused entries of row 489 change: the file keeps its header
and size. The European and Japanese discs carry the same file (mods/base-discs).
"""
import argparse, os, struct, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PATH = 'ETCDAT/TAMA.TIM'

CLUT_Y, IMG_W, IMG_H = 488, 256, 80
PIX = 8 + 524 + 12            # the pixel block: after the header, the CLUT block (12 + 512) and the image header
ICON_U, ICON_V, ICON_W = 136, 40, 28
NEW_ROW = 497                 # rows 497-500: slots 4-7
SHELL_ROW = 492               # the spotted icon's row: its 9 shell greys give the shading order

# slot 4-7: (name, shell rgb, pattern rgb or None for a plain egg, icon) from wikimon's Digitama artwork
EGGS = [
    ('Pabumon', (95, 223, 87), None, 'plain'),
    ('Pichimon', (93, 235, 255), None, 'plain'),
    ('YukimiBotamon', (184, 187, 202), None, 'zigzag'),
    ('Nyokimon', (255, 113, 112), (255, 194, 147), 'spots'),
]
ZIGZAG_GROUP_ROW = 489        # the wave egg's row (group 1), which YukimiBotamon borrows
# the YukimiBotamon zigzag over the shell (index 1) and over the wave's indices 2-5
# Never index 14 (0x8000, black with the semi-transparency bit): the egg box draws its sprites semi-transparent
# (additive), so an STP texel shows what is behind it; 15 (0x0421) and the dark greys are opaque.
ZIG_OVER = {1: 15, 2: 7, 3: 13, 4: 8, 5: 9}
ZIG_ICON = 15


def rgb15(rgb):
    r, g, b = (max(0, min(255, round(c))) >> 3 for c in rgb)
    return (r | g << 5 | b << 10) or 0x0421     # 0 would draw transparent


def lum(v):
    return 0.299 * (v & 31) + 0.587 * (v >> 5 & 31) + 0.114 * (v >> 10 & 31)


class Tim:
    def __init__(self, data):
        self.d = data
        magic, flag = struct.unpack_from('<II', data, 0)
        clut = struct.unpack_from('<IHHHH', data, 8)
        img = struct.unpack_from('<IHHHH', data, 8 + 524)
        if (magic, flag, clut, img) != (0x10, 8, (524, 128, 488, 16, 16), (10252, 576, 256, 64, 80)) \
                or len(data) != PIX + IMG_W * IMG_H // 2:
            sys.exit(f'{PATH}: not the egg texture this tool knows (4-bit 256x80 at 576,256, CLUT 16x16 at 128,488)')

    def px(self, x, y):
        b = self.d[PIX + y * 128 + x // 2]
        return b >> 4 if x & 1 else b & 15

    def set(self, x, y, i):
        o = PIX + y * 128 + x // 2
        self.d[o] = (self.d[o] & 0x0f) | i << 4 if x & 1 else (self.d[o] & 0xf0) | i

    def row(self, y):
        return list(struct.unpack_from('<16H', self.d, 20 + (y - CLUT_Y) * 32))

    def set_row(self, y, values):
        struct.pack_into('<16H', self.d, 20 + (y - CLUT_Y) * 32, *values)


def icon(tim, k):
    """the original icon k (0-3) as 32 rows of 32 indices"""
    return [[tim.px(96 + 32 * k + x, y) for x in range(32)] for y in range(32)]


def shell_order(tim):
    """the icon's shell indices from the lightest to the darkest"""
    row = tim.row(SHELL_ROW)
    shell = [1] + list(range(6, 14))
    return sorted(shell, key=lambda i: -lum(row[i]))


def fill_pattern(ic, order):
    """the spots (indices 2-5) replaced by the shell's shading under them: a quadratic surface fitted to the shading
    order of the rest of the shell (least squares), rounded to the nearest grey"""
    rank = {i: r for r, i in enumerate(order)}
    terms = lambda x, y: (1.0, x, y, x * x, y * y, x * y)
    n = 6
    ata = [[0.0] * n for _ in range(n)]
    atb = [0.0] * n
    for y in range(32):
        for x in range(32):
            r = rank.get(ic[y][x])
            if r is None:
                continue
            t = terms(x / 32, y / 32)
            for i in range(n):
                atb[i] += t[i] * r
                for j in range(n):
                    ata[i][j] += t[i] * t[j]
    for c in range(n):                       # Gauss-Jordan on the normal equations
        piv = max(range(c, n), key=lambda r: abs(ata[r][c]))
        ata[c], ata[piv] = ata[piv], ata[c]
        atb[c], atb[piv] = atb[piv], atb[c]
        for r in range(n):
            if r != c:
                f = ata[r][c] / ata[c][c]
                ata[r] = [a - f * b for a, b in zip(ata[r], ata[c])]
                atb[r] -= f * atb[c]
    coef = [atb[i] / ata[i][i] for i in range(n)]

    def shade(x, y):
        v = sum(c * t for c, t in zip(coef, terms(x / 32, y / 32)))
        return order[max(0, min(len(order) - 1, round(v)))]
    return [[shade(x, y) if 2 <= ic[y][x] <= 5 else ic[y][x] for x in range(32)] for y in range(32)]


def zigzag(ic, order, rows, amp, period, width):
    """near-black zigzags (ZIG_ICON, opaque) across the shell, centred on the given icon rows"""
    shell = set(order)
    out = [line[:] for line in ic]
    for cy in rows:
        for x in range(32):
            t = x % period
            c = cy + amp - (4 * amp * t) // period if t < period // 2 else cy - amp + (4 * amp * (t - period // 2)) // period
            for y in range(c, c + width):
                if 0 <= y < 32 and out[y][x] in shell:
                    out[y][x] = ZIG_ICON
    return out


def palette(tim, shell_rgb, pattern_rgb, order):
    """a new egg's row: 1 the shell, 2-5 the pattern (the shell on a plain egg), 6-13 the icon's shading of the shell
    (the original greys' brightness against index 1), 14-15 the outline"""
    grey = tim.row(SHELL_ROW)
    top = lum(grey[1])
    row = [0] * 16
    for i in order:
        row[i] = rgb15(tuple(c * lum(grey[i]) / top for c in shell_rgb))
    # the skin's spots are index 5 (2-4 only edge their outline); the icon shades its spots 2 (light) to 5
    for i, f in ((2, 0.6), (3, 0.4), (4, 0.2), (5, 0.0)):
        row[i] = rgb15(tuple(c + (255 - c) * f for c in pattern_rgb)) if pattern_rgb else row[1]
    row[14], row[15] = grey[14], grey[15]
    return row


def zigzag_skin(tim):
    """YukimiBotamon's band on the wave egg's skin: u 0-95, a zigzag of 6 teeth round the egg centred on v 24"""
    row = tim.row(ZIGZAG_GROUP_ROW)
    if any(row[i] for i in ZIG_OVER.values() if i != 15) or row[15] not in (0, 0x0421):   # (15: the outline grey)
        sys.exit(f'{PATH}: row {ZIGZAG_GROUP_ROW} already uses the indices the zigzag needs')
    for src, dst in ZIG_OVER.items():
        row[dst] = row[src]
    tim.set_row(ZIGZAG_GROUP_ROW, row)
    period, amp = 16, 5
    for u in range(96):
        t = u % period
        c = 24 + amp - (4 * amp * t) // period if t < period // 2 else 24 - amp + (4 * amp * (t - period // 2)) // period
        for v in range(c - 2, c + 2):
            i = tim.px(u, v)
            if i not in ZIG_OVER:
                sys.exit(f'{PATH}: the zigzag meets index {i} at {u},{v}')
            tim.set(u, v, ZIG_OVER[i])


def build(data):
    tim = Tim(bytearray(data))
    for y in range(NEW_ROW, NEW_ROW + len(EGGS)):
        if any(tim.row(y)):
            sys.exit(f'{PATH}: CLUT row {y} is not empty')
    for y in range(ICON_V, ICON_V + 32):
        for x in range(ICON_U, ICON_U + ICON_W * len(EGGS)):
            if tim.px(x, y):
                sys.exit(f'{PATH}: texel {x},{y} is not empty')
    for k in range(4):
        ic = icon(tim, k)
        if any(line[x] for line in ic for x in (0, 1, 30, 31)):
            sys.exit(f'{PATH}: icon {k} is wider than 28 texels')
    order = shell_order(tim)
    spots = icon(tim, 0)
    plain = fill_pattern(spots, order)
    for slot, (name, shell, pattern, kind) in enumerate(EGGS):
        ic = {'plain': plain, 'spots': spots,
              'zigzag': zigzag(plain, order, rows=(10, 19), amp=2, period=6, width=2)}[kind]
        u0 = ICON_U + ICON_W * slot
        for y in range(32):
            for x in range(ICON_W):
                tim.set(u0 + x, ICON_V + y, ic[y][x + 2])
        tim.set_row(NEW_ROW + slot, palette(tim, shell, pattern, order))
    zigzag_skin(tim)
    return bytes(tim.d)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('out')
    ap.add_argument('--extracted', default=os.path.join(ROOT, 'extracted'))
    a = ap.parse_args()
    data = build(open(os.path.join(a.extracted, PATH), 'rb').read())
    dst = os.path.join(a.out, PATH)
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    open(dst, 'wb').write(data)
    print(dst)


if __name__ == '__main__':
    main()
