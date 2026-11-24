"""The banners of the eighteen cups after the original's (cups 23..40): STDDAT/GRADE/NEWCUPS.BIN.

    python3 -m tools.cup_banners build OUT.BIN      # the disc file

The original's banners are one TIM file per cup, with a copy per language. These are ours: the generator's art, made
in the style of the original's banners (content/localized/tournament/new-cups/prompts.py has the prompts) and kept as
256x128 PNGs of 256 colours, colour 0 the transparent background (content/localized/tournament/new-cups/<language>/).
One file holds them all, a banner per language and cup in the order of include/dw/lang.h and of CUPS, each SECTORS
long, so the arena reads the one it shows with a single file name (STD_initializeTournament).

No Pillow, no downloads: the player's build packs them too.
"""
import os
import struct
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for path in (ROOT, os.path.join(ROOT, 'tools')):
    if path not in sys.path:
        sys.path.insert(0, path)
ART = os.path.join(ROOT, 'content', 'localized', 'tournament', 'new-cups')
SECTOR = 2048
SECTORS = 17                    # STD_NEW_CUP_SECTORS
W, H = 256, 128                 # the original banners' size and place in video memory
IMAGE_XY, CLUT_XY = (384, 0), (0, 486)
LANGUAGES = ['en', 'es', 'pt-br', 'fr', 'de', 'it', 'ja', 'ca', 'zh-hans']      # include/dw/lang.h
CUPS = ['ROOKIE_CUP', 'CHAMPION_CUP', 'ULTIMATE_CUP', 'MEGA_CUP', 'VACCINE_CUP', 'DATA_CUP', 'VIRUS_CUP',
        'NATURE_SPIRITS_CUP', 'DEEP_SAVERS_CUP', 'NIGHTMARE_SOLDIERS_CUP', 'WIND_GUARDIANS_CUP', 'METAL_EMPIRE_CUP',
        'VIRUS_BUSTERS_CUP', 'DRAGONS_ROAR_CUP', 'JUNGLE_TROOPERS_CUP', 'DARK_CUP', 'HOLY_CUP', 'AQUA_CUP']


def tim(path):
    """The banner of a PNG as its 17 sectors: an 8-bit TIM whose colour 0 is the transparent 0x0000."""
    import dwmap
    w, h, mode, rows, colours = dwmap.png_read(path)
    if (w, h, mode) != (W, H, 'P'):
        raise ValueError(f'{path}: a {w}x{h} {mode} picture, a banner is {W}x{H} with a palette')
    colours = (list(colours) + [(0, 0, 0)] * 256)[:256]
    clut = [0] + [max(1, (r >> 3) | (g >> 3) << 5 | (b >> 3) << 10) for r, g, b in colours[1:]]
    data = struct.pack('<II', 0x10, 9)
    data += struct.pack('<IHHHH', 12 + 512, *CLUT_XY, 256, 1) + struct.pack('<256H', *clut)
    data += struct.pack('<IHHHH', 12 + W * H, *IMAGE_XY, W // 2, H) + b''.join(bytes(row) for row in rows)
    if len(data) > SECTORS * SECTOR:
        raise ValueError('a banner is larger than its room in the file')
    return data.ljust(SECTORS * SECTOR, b'\0')


def build(out):
    data = b''.join(tim(os.path.join(ART, language, cup + '.png')) for language in LANGUAGES for cup in CUPS)
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    with open(out, 'wb') as f:
        f.write(data)
    return len(data)


if __name__ == '__main__':
    if len(sys.argv) == 3 and sys.argv[1] == 'build':
        print(build(sys.argv[2]), 'bytes')
    else:
        sys.exit(__doc__)
