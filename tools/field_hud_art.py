#!/usr/bin/env python3
"""B5a field gauges in unused ETCTIM.BIN texels and CLUT rows.

Entry 1 (960,448; 256x64; CLUT 272,496) has no native sprite in
these cells. Seven 34x13 tiles contain a common grey icon block and empty
outlined track. Rows 500..506 preserve native icon colours; 507 holds the
status screen's green/red fills and the light-blue need fills. Rows 508..510
blend the whole need icon 55% towards luminance-scaled brick red. The track
uses separate palette indices so it cannot inherit an icon tint. No allocation
is added. Native pixels come from SYSTEM_W (entry 8) and the toilet-need
condition frame (entry 3), fitted whole to 11x11.
"""
import argparse
from pathlib import Path
import struct
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools.localize.build import tim_entries

PATH = 'ETCDAT/ETCTIM.BIN'
CELLS = ((144,32), (178,32), (212,32), (144,45), (178,45), (212,45), (110,50))
# Happy, sad, disciplined, undisciplined, meat, toilet, tired.
SOURCES = ((64,244,503,11), (97,244,503,11), (22,244,498,11),
           (33,244,498,11), (72,140,488,12), (208,400,483,16), (108,140,489,12))


def rgb15(rgb):
    r,g,b = (v >> 3 for v in rgb)
    return r | g << 5 | b << 10


def active_tint(colour):
    """Option B: blend 55% towards luminance * (235,90,80), then PSX RGB15."""
    if not colour:
        return 0
    rgb = [((colour >> shift) & 31) * 255 / 31 for shift in (0,5,10)]
    luminance = sum(c*w for c,w in zip(rgb,(.299,.587,.114))) / 255
    return rgb15([round(.45*c + .55*luminance*t) for c,t in zip(rgb,(235,90,80))]) or 0x8000


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
        struct.pack_into('<16H',d,p,*(colours+[0]*(16-len(colours))))

    grey, light, shadow = map(rgb15, ((144,144,144),(184,184,184),(64,64,64)))
    outline, top, bottom = map(rgb15, ((16,24,32),(112,112,112),(88,88,88)))
    for k, ((u,v), source) in enumerate(zip(CELLS,SOURCES)):
        tile = [[0]*34 for _ in range(13)]
        for y in range(13):
            for x in range(13):
                tile[y][x] = light if y==0 or x==0 else shadow if y==12 or x==12 else grey
        sx,sy,cy,size = source
        pixels,base_y,clut_y = (need,384,480) if k==5 else (src,128,488)
        native = struct.unpack_from('<16H',d,pixels-12-512+(cy-clut_y)*32)
        for y in range(11):
            for x in range(11):
                a,b = ((2*t+1)*size//22 for t in (x,y))
                colour = native[pixel(pixels,sx+a,sy-base_y+b)]
                if k in (4,6) and colour in (grey,light,shadow):
                    colour = 0
                if colour:
                    tile[y+1][x+1] = colour
        for y in range(5,9):
            for x in range(14,34):
                tile[y][x] = top if y==6 and 15<=x<33 else bottom if y==7 and 15<=x<33 else outline
        # Keep track indices distinct even if a glyph shares a track ink.
        colours = list(dict.fromkeys([0]+[tile[y][x] for y in range(13) for x in range(13)]))
        icon_colours = len(colours)
        colours += [outline,top,bottom]
        if len(colours)>16:
            raise ValueError(f'HUD tile {k} exceeds its native palette: {len(colours)}')
        palette(4+k,colours)
        if k >= 4:
            palette(8+k,[active_tint(c) for c in colours[:icon_colours]]+colours[icon_colours:])
        for y,row in enumerate(tile):
            for x,c in enumerate(row):
                index = icon_colours + [outline,top,bottom].index(c) if x>=14 and 5<=y<9 else colours.index(c)
                put(u+x,v+y,index)
    colours = [0] + list(map(rgb15, ((117,218,96),(48,200,40),(234,117,96),(224,48,40),
                                    (160,210,255),(120,190,255))))
    palette(11,colours)
    for y in range(4):
        for x in range(18):
            put(144+x,59+y,1+y)
    for y in range(2):
        for x in range(18):
            put(164+x,59+y,5+y)
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
