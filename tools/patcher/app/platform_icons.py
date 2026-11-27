"""The pictures on the patcher's Make buttons (gui.py): a disc, an Android robot, an apple, a window and a penguin,
drawn here in simple shapes of our own (no one's logo), without libraries, as PNG data for Tk.

    python3 tools/patcher/app/platform_icons.py OUT_FOLDER     # disc.png, apk.png, setup.png, mac.png, linux.png

Standard library only.
"""
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import make_icons  # noqa: E402

DARK = (0x1b, 0x1a, 0x24)
WHITE = (0xff, 0xff, 0xff)


def _circle(x, y, cx, cy, r):
    return (x - cx) ** 2 + (y - cy) ** 2 <= r * r


def _ellipse(x, y, cx, cy, rx, ry):
    return ((x - cx) / rx) ** 2 + ((y - cy) / ry) ** 2 <= 1


def _disc(x, y):
    """A compact disc: silver, a rainbow sheen, the hole."""
    if not _circle(x, y, 16, 16, 14.5) or _circle(x, y, 16, 16, 2.6):
        return None
    if _circle(x, y, 16, 16, 5.2):
        return (0xd6, 0xd8, 0xe0) if not _circle(x, y, 16, 16, 4.2) else (0xee, 0xef, 0xf3)
    a = math.atan2(y - 16, x - 16)
    sheen = max(0.0, math.cos(2 * (a + 0.6))) ** 3          # two light bands across the face
    hue = (a / math.pi + 1) * 0.5
    tint = tuple(0.5 + 0.5 * math.cos(2 * math.pi * (hue + k / 3)) for k in range(3))
    base = (0xb8, 0xbc, 0xc8)
    return tuple(min(255, base[i] * (1 - 0.45 * sheen) + (180 + 75 * tint[i]) * 0.45 * sheen) for i in range(3))


def _android(x, y):
    """A robot: a half-dome head with antennae and eyes, a body, arms and legs."""
    green = (0x3d, 0xb8, 0x6b)
    if y <= 12.5 and _ellipse(x, y, 16, 12.5, 8.5, 7.5):
        if _circle(x, y, 13, 9.5, 1.1) or _circle(x, y, 19, 9.5, 1.1):
            return WHITE
        return green
    for ax, sign in ((11.5, -1), (20.5, 1)):                 # the antennae, leaning out
        t = (6 - y) / 3.0
        if 0 <= t <= 1 and abs(x - (ax + sign * 2 * t)) < 0.7:
            return green
    if make_icons._rounded(x, y, 7.5, 13.5, 24.5, 25, 2):
        return green
    if make_icons._rounded(x, y, 3.5, 13.5, 6.5, 22, 1.5) or make_icons._rounded(x, y, 25.5, 13.5, 28.5, 22, 1.5):
        return green
    if make_icons._rounded(x, y, 10.5, 24, 13.5, 30, 1.5) or make_icons._rounded(x, y, 18.5, 24, 21.5, 30, 1.5):
        return green
    return None


def _apple(x, y):
    """An apple: two lobes, a bite on the right, a leaf."""
    grey = (0x55, 0x57, 0x63)
    u, v = (x - 18.2) * 0.7 + (y - 6.2) * 0.7, -(x - 18.2) * 0.7 + (y - 6.2) * 0.7   # the leaf, tilted
    if _ellipse(u, v, 0, 0, 1.6, 3.4):
        return grey
    lobes = _circle(x, y, 12.2, 16.5, 7.6) or _circle(x, y, 19.8, 16.5, 7.6) or _ellipse(x, y, 16, 22, 9.5, 7.5)
    notch = _circle(x, y, 16, 7.4, 3.2) or (y > 26 and _circle(x, y, 16, 31.2, 3.0))
    bite = _circle(x, y, 28.6, 17, 4.2)
    if lobes and not notch and not bite and y >= 9:
        return grey
    return None


def _windows(x, y):
    """A window of four panes."""
    blue = (0x1f, 0x7a, 0xd6)
    for x0, x1 in ((4, 15), (17, 28)):
        for y0, y1 in ((4, 15), (17, 28)):
            if x0 <= x <= x1 and y0 <= y <= y1:
                return blue
    return None


def _penguin(x, y):
    """A penguin: black body, white face and belly, eyes, an orange beak and feet."""
    orange = (0xf2, 0xa9, 0x1c)
    if (_ellipse(x, y, 11.5, 28.5, 4.2, 1.9) or _ellipse(x, y, 20.5, 28.5, 4.2, 1.9)):
        return orange
    if _ellipse(x, y, 16, 12.2, 2.6, 1.5) and y >= 11.2:
        return orange
    if _ellipse(x, y, 16, 18, 9, 11) or _circle(x, y, 16, 8.5, 6.2):
        if _circle(x, y, 13.6, 8.6, 1.0) or _circle(x, y, 18.4, 8.6, 1.0):
            return DARK
        if _circle(x, y, 13.6, 8.6, 2.0) or _circle(x, y, 18.4, 8.6, 2.0):
            return WHITE
        if _ellipse(x, y, 16, 20, 6.2, 8.2):
            return (0xf4, 0xf2, 0xea)
        return DARK
    return None


DRAWINGS = {'disc': _disc, 'apk': _android, 'setup': _windows, 'mac': _apple, 'linux': _penguin}


def png(kind, size=40):
    sample = DRAWINGS[kind]
    ss = 4
    step = 32 / (size * ss)
    out = bytearray()
    for py in range(size):
        for px in range(size):
            acc, n = [0.0, 0.0, 0.0], 0
            for sy in range(ss):
                for sx in range(ss):
                    c = sample((px * ss + sx + 0.5) * step, (py * ss + sy + 0.5) * step)
                    if c is not None:
                        n += 1
                        for i in range(3):
                            acc[i] += c[i]
            out += (bytes(int(acc[i] / n + 0.5) for i in range(3)) + bytes([int(255 * n / (ss * ss) + 0.5)])
                    if n else b'\0\0\0\0')
    return make_icons.encode_png(bytes(out), size)


if __name__ == '__main__':
    os.makedirs(sys.argv[1], exist_ok=True)
    for k in DRAWINGS:
        with open(os.path.join(sys.argv[1], k + '.png'), 'wb') as f:
            f.write(png(k, 96))
