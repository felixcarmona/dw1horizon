"""Derive labelled recovery disks into existing field texture uploads.

No new disc file, texture upload, or resident bitmap is required. An unused 16x16 cell at ETCTIM entry 1 (224,0) holds item 0; a
32x16 cell at (224,16) holds item 4 with a wider pixel label. FEEL_EF CLUT rows 13/14 hold their own palettes with two unused inks
replaced for a hand-pixelled label plate. The standalone FEEL_EF repeats those
palettes so its ordinary upload cannot erase them. Labels never use a font.
"""
import struct
from tools.localize.build import tim_entries

PATH = 'ETCDAT/ETCTIM.BIN'
FEEL = 'ETCDAT/FEEL_EF.TIM'
# Two-texel strokes and gaps keep every part of M visible through native
# point sampling. A wider tile holds the label without changing bubble size.
TILES = ((224,0,16),(224,16,32))
LABELS = (('HH.HH..PPPPP.', 'HH.HH..PP..PP', 'HHHHH..PP..PP', 'HHHHH..PPPPP.',
           'HH.HH..PPPPP.', 'HH.HH..PP....', 'HH.HH..PP....'),
          ('MM......MM..PPPPP.', 'MMMM..MMMM..PP..PP', 'MMMM..MMMM..PP..PP', 'MM..MM..MM..PPPPP.',
           'MM..MM..MM..PPPPP.', 'MM......MM..PP....', 'MM......MM..PP....', 'MM......MM..PP....'))


def _pixel(data, base, x, y):
    return (data[base + y * 128 + x // 2] >> (4 * (x & 1))) & 15


def _clut(base, rows):
    return base - 12 - rows * 32


def build(data):
    """Return an ETCTIM copy; reject occupied atlas cells/palette rows."""
    d = bytearray(data)
    entries = tim_entries(d)
    dst, bpp, w, h = entries[1]
    src, sbpp, sw, sh = entries[6]
    feel, fbpp, fw, fh = entries[3]
    if (bpp,w,h,sbpp,sw,sh,fbpp,fw,fh) != (0,256,64,0,256,128,0,256,64) or \
            struct.unpack_from('<4H',d,dst-8) != (960,448,64,64) or \
            struct.unpack_from('<4H',d,feel-8) != (960,384,64,64) or \
            struct.unpack_from('<4H',d,_clut(feel,16)-8) != (272,480,16,16) or \
            struct.unpack_from('<4H',d,_clut(src,24)-8) != (224,488,16,24):
        raise ValueError('unexpected care-bubble texture allocation')
    # Validate every destination before changing the caller's copy.
    for y in range(32):
        if any(_pixel(d,dst,x,y) for x in range(224,256)):
            raise ValueError('care-bubble atlas cells are occupied')
    palette_base = _clut(feel,16)
    if any(d[palette_base+13*32:palette_base+15*32]):
        raise ValueError('care-bubble CLUT rows are occupied')
    for which, (item, plate, ink, colour) in enumerate(((0,1,8,0x0852),(4,3,7,0x7c82))):
        u0,v0,width = TILES[which]
        native = [[_pixel(d,src,item*16+x,y) for x in range(16)] for y in range(16)]
        used = {v for row in native for v in row}
        tile = [[0]*width for _ in range(16)]
        for y,row in enumerate(native):
            tile[y][(width-16)//2:(width+16)//2] = row
        if plate in used or ink in used:
            raise ValueError('native recovery disk uses reserved label inks')
        palette = list(struct.unpack_from('<16H',d,_clut(src,24)+item*32))
        palette[plate], palette[ink] = 0x7fff, colour
        label = LABELS[which]
        left = (width-len(label[0]))//2
        top = 7 if which == 0 else 5
        border = 1 if which == 0 else 0
        for y in range(top,top+8):
            for x in range(max(0,left-border),min(width,left+len(label[0])+border)):
                tile[y][x] = plate
        for y,row in enumerate(label):
            for x,v in enumerate(row):
                if v != '.':
                    tile[y+top+8-len(label)][x+left] = ink
        struct.pack_into('<16H',d,palette_base+(13+which)*32,*palette)
        for y,row in enumerate(tile):
            for x,v in enumerate(row):
                u=u0+x
                offset=dst+(v0+y)*128+u//2
                shift=4*(u&1)
                d[offset]=(d[offset]&~(15<<shift)) | v<<shift
    return bytes(d)


def feel(data, stack):
    """Preserve the native standalone file except the two new palette rows."""
    d=bytearray(data)
    dst,bpp,w,h=tim_entries(d)[0]
    src=tim_entries(stack)[3][0]
    if (bpp,w,h)!=(0,256,64) or struct.unpack_from('<4H',d,dst-8)!=(960,384,64,64) or \
            struct.unpack_from('<4H',d,_clut(dst,16)-8)!=(272,480,16,16):
        raise ValueError('unexpected standalone condition texture allocation')
    a=_clut(dst,16)+13*32
    if any(d[a:a+64]):
        raise ValueError('standalone care-bubble CLUT rows are occupied')
    b=_clut(src,16)+13*32
    d[a:a+64]=stack[b:b+64]
    return bytes(d)
