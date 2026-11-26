#!/usr/bin/env python3
"""Field care HUD art in unused ETCTIM.BIN texels and CLUT rows.

Entry 1 (960,448; 256x64; CLUT 272,496) has no native sprite in these cells.
The HUD is five short copies of the native field status bar stacked in one
column: happiness, discipline, hunger, toilet, tiredness. Each row draws three
quads: the bar frame, its icon on the frame's left cap (as the original game
draws its two bars) and the native two-tone blue fill.

- FRAME (56x8): the native 76x8 bar from SYSTEM_W (entry 8, CLUT row 500),
  its 50-texel slot cut to 30 and the slot's interior (blue; near black on
  Japan Rev 1, which also outlines the bar near black) made the dark
  empty track. CLUT row 508.
- ICONS (7 x 11x11): happy, sad, disciplined, undisciplined, meat, toilet,
  tired; native pixels with no background, CLUT rows 500..506. The meat and
  tired sprites lose their baked grey block. The two mood icons encode
  (normal, disliked) colour pairs; spare CLUT rows (272,511) and (256,511)
  select the original worse expressions without adding a tile.
- FILL (30x2): the native MP bar's two blue rows, CLUT row 507.

No allocation is added. Native pixels come from SYSTEM_W (entry 8) and the
toilet-need condition frame (entry 3), fitted whole to 11x11.
"""
import argparse
from pathlib import Path
import struct
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools.localize.build import tim_entries

PATH = 'ETCDAT/ETCTIM.BIN'
ICON = 11
ICONS = tuple((144 + k * ICON, 32) for k in range(7))
# Happy, sad, disciplined, undisciplined, meat, toilet, tired.
SOURCES = ((64,244,503,11), (97,244,503,11), (22,244,498,11),
           (33,244,498,11), (72,140,488,12), (208,400,483,16), (108,140,489,12))
FRAME = (144, 44)
FRAME_W, FRAME_H = 56, 8
SLOT = 30                      # fill texels; the native slot is 50
NATIVE_BAR = (0, 236, 500)     # SYSTEM_W u, v, CLUT row: the original field bar
SLOT_INDEX = 12                # the bar slot interior's CLUT index
SLOT_COLOURS = (0x7acc, 0x0421)   # its colour: USA/Europe blue, Japan Rev 1 near black
FILL = (200, 44)
FILL_COLOURS = ((205,230,246), (0,106,189))   # the native MP bar's two rows
EMPTY_COLOURS = ((40,40,40), (24,24,24))
CLUT_ICON, CLUT_FILL, CLUT_FRAME = 4, 11, 12  # rows 500, 507, 508


def rgb15(rgb):
    r,g,b = (v >> 3 for v in rgb)
    return r | g << 5 | b << 10


def build(data):
    d = bytearray(data)
    entries = tim_entries(d)
    dst, bpp, w, h = entries[1]
    src, _, _, _ = entries[8]
    clut = dst - 12 - 512
    if (bpp,w,h) != (0,256,64) or struct.unpack_from('<4H',d,dst-8) != (960,448,64,64) \
            or struct.unpack_from('<4H',d,clut-8) != (272,496,16,16):
        raise ValueError('unexpected field HUD texture allocation')
    if entries[8][1:] != (0,256,128) or struct.unpack_from('<4H',d,src-8) != (320,128,64,128) \
            or struct.unpack_from('<4H',d,src-12-512-8) != (96,488,16,16):
        raise ValueError('unexpected native care-icon texture allocation')
    need = entries[3][0]
    if entries[3][1:] != (0,256,64) or struct.unpack_from('<4H',d,need-8) != (960,384,64,64) \
            or struct.unpack_from('<4H',d,need-12-512-8) != (272,480,16,16):
        raise ValueError('unexpected native toilet-need texture allocation')

    def pixel(p,x,y):
        return (d[p+y*128+x//2] >> (4*(x&1))) & 15

    def put(x,y,index):
        p = dst+y*128+x//2
        shift = 4*(x&1)
        # Fail closed if an asset allocation ever starts using our cells.
        if pixel(dst,x,y):
            raise ValueError(f'field HUD atlas cell is occupied: {x},{y}')
        d[p] = (d[p] & ~(15<<shift)) | index<<shift

    def palette(row, colours):
        p = clut+row*32
        if any(d[p:p+32]):
            raise ValueError(f'field HUD CLUT row is occupied: {496+row}')
        if len(colours) > 16:
            raise ValueError(f'field HUD CLUT row {496+row} needs {len(colours)} colours')
        struct.pack_into('<16H',d,p,*(colours+[0]*(16-len(colours))))

    def native_palette(cy):
        return struct.unpack_from('<16H',d,src-12-512+(cy-488)*32)

    grey, light, shadow = map(rgb15, ((144,144,144),(184,184,184),(64,64,64)))

    # Icons: native glyphs on a transparent background.
    for k, ((u,v), source) in enumerate(zip(ICONS,SOURCES)):
        sx,sy,cy,size = source
        pixels,base_y,clut_y = (need,384,480) if k==5 else (src,128,488)
        native = struct.unpack_from('<16H',d,pixels-12-512+(cy-clut_y)*32)
        tile = [[0]*ICON for _ in range(ICON)]
        for y in range(ICON):
            for x in range(ICON):
                a,b = ((2*t+1)*size//22 for t in (x,y))
                colour = native[pixel(pixels,sx+a,sy-base_y+b)]
                # The meat and tired sprites carry the status page's grey block.
                if k in (4,6) and colour in (grey,light,shadow):
                    colour = 0
                if k < 2:
                    worse = native[pixel(src,sx+x+11,sy-128+y)]
                    colour = (colour, worse)
                tile[y][x] = colour
        if k < 2:
            colours = list(dict.fromkeys([(0,0)]+[c for row in tile for c in row]))
            palette(CLUT_ICON+k,[c[0] for c in colours])
            # Spare CLUT rows: BTLCOMND (272,511), FI_INFO (256,511).
            alt = clut+15*32 if k==0 else entries[4][0]-12-512+15*32
            if any(d[alt:alt+32]):
                raise ValueError('HUD mood CLUT row is occupied')
            struct.pack_into('<16H',d,alt,*([c[1] for c in colours]+[0]*(16-len(colours))))
        else:
            colours = list(dict.fromkeys([0]+[c for row in tile for c in row]))
            palette(CLUT_ICON+k,colours)
        for y,row in enumerate(tile):
            for x,c in enumerate(row):
                if colours.index(c):
                    put(u+x,v+y,colours.index(c))

    # Frame: the native bar, slot shortened, interior emptied.
    bu,bv,bc = NATIVE_BAR
    bar_palette = native_palette(bc)
    keep = list(range(0,18)) + [18]*SLOT + list(range(68,76))
    # The slot interior is CLUT index 12 on every disc. The USA and European
    # palettes give it the native blue; Japan Rev 1's row 500 gives it near
    # black (8,8,8). Either way it becomes the dark empty track below.
    if bar_palette[SLOT_INDEX] not in SLOT_COLOURS:
        raise ValueError('unexpected native bar slot colour')
    frame = [[bar_palette[pixel(src,bu+sx,bv-128+y)] for sx in keep] for y in range(FRAME_H)]
    for y in (3,4):
        for x in range(18,18+SLOT):
            if pixel(src,bu+keep[x],bv-128+y) != SLOT_INDEX:
                raise ValueError('unexpected native bar slot')
            frame[y][x] = rgb15(EMPTY_COLOURS[y-3])
    colours = list(dict.fromkeys([0]+[c for row in frame for c in row]))
    palette(CLUT_FRAME,colours)
    for y,row in enumerate(frame):
        for x,c in enumerate(row):
            if colours.index(c):
                put(FRAME[0]+x,FRAME[1]+y,colours.index(c))

    # Fill: two rows of the native MP blue.
    palette(CLUT_FILL,[0]+[rgb15(c) for c in FILL_COLOURS])
    for y in range(2):
        for x in range(SLOT):
            put(FILL[0]+x,FILL[1]+y,1+y)
    return bytes(d)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('out',type=Path)
    p.add_argument('--extracted',type=Path,default=Path(__file__).resolve().parents[1]/'extracted')
    a=p.parse_args()
    out=a.out/PATH
    out.parent.mkdir(parents=True,exist_ok=True)
    out.write_bytes(build((a.extracted/PATH).read_bytes()))
    print(out)


if __name__=='__main__':
    main()
