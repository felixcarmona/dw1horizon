"""Derive depleted native battle HUD icons into existing field uploads.

The 11x11 heart and MP orb retain their native silhouettes and pale shading.
A saturated lower third signals low resources. Two existing 16x16
cells and FEEL_EF palette rows 13/14 hold the art, without new uploads or RAM.
"""
import struct
from tools.localize.build import tim_entries

PATH = 'ETCDAT/ETCTIM.BIN'
FEEL = 'ETCDAT/FEEL_EF.TIM'
TILES = ((224,0,16),(224,16,16))
ICONS = ((144,48), (155,48))  # ETCTIM entry 0, battle HUD heart and MP orb
FILL_ROW = 6
OUTLINE = (6, 6, 7)
FILL = ((30, 8, 10), (3, 19, 30))
SURFACE = ((31, 16, 17), (14, 26, 31))


def faded(colour):
    """Quantize proposal 4: pale neutral base with subdued native shading."""
    rgb = tuple(((colour >> shift) & 31) * 255 // 31 for shift in (0, 5, 10))
    grey = sum(rgb) // 3
    return tuple(min(27, round((116 + grey * .30 + v * .16) * 31 / 255)) for v in rgb)


def _pixel(data, base, x, y):
    return (data[base + y * 128 + x // 2] >> (4 * (x & 1))) & 15


def _clut(base, rows):
    return base - 12 - rows * 32


def build(data):
    """Return an ETCTIM copy; reject occupied atlas cells/palette rows."""
    d = bytearray(data)
    entries = tim_entries(d)
    dst, bpp, w, h = entries[1]
    src, sbpp, sw, sh = entries[0]
    feel, fbpp, fw, fh = entries[3]
    if (bpp,w,h,sbpp,sw,sh,fbpp,fw,fh) != (0,256,64,0,256,64,0,256,64) or \
            struct.unpack_from('<4H',d,dst-8) != (960,448,64,64) or \
            struct.unpack_from('<4H',d,feel-8) != (960,384,64,64) or \
            struct.unpack_from('<4H',d,_clut(feel,16)-8) != (272,480,16,16) or \
            struct.unpack_from('<4H',d,src-8) != (896,384,64,64) or \
            struct.unpack_from('<4H',d,_clut(src,16)-8) != (256,480,16,16):
        raise ValueError('unexpected care-bubble texture allocation')
    # Validate every destination before changing the caller's copy.
    for y in range(32):
        if any(_pixel(d,dst,x,y) for x in range(224,256)):
            raise ValueError('care-bubble atlas cells are occupied')
    palette_base = _clut(feel,16)
    if any(d[palette_base+13*32:palette_base+15*32]):
        raise ValueError('care-bubble CLUT rows are occupied')
    native_palette = list(struct.unpack_from('<16H',d,_clut(src,16)+11*32))
    for which, (u_source, v_source) in enumerate(ICONS):
        u0,v0,width = TILES[which]
        native = [[_pixel(d,src,u_source+x,v_source+y) for x in range(11)] for y in range(11)]
        palette = [0]
        tile = [[0]*width for _ in range(16)]
        for y,row in enumerate(native):
            for x,index in enumerate(row):
                if not index:
                    continue
                boundary = any(not (0 <= x+dx < 11 and 0 <= y+dy < 11)
                               or not native[y+dy][x+dx]
                               for dx,dy in ((-1,0),(1,0),(0,-1),(0,1)))
                if boundary:
                    rgb = OUTLINE
                elif y >= FILL_ROW:
                    rgb = SURFACE[which] if y == FILL_ROW else FILL[which]
                else:
                    rgb = faded(native_palette[index])
                colour = sum(v << shift for v,shift in zip(rgb,(0,5,10)))
                if colour not in palette:
                    palette.append(colour)
                tile[y][x] = palette.index(colour)
        if len(palette) > 16:
            raise ValueError('care-bubble palette exceeds 4-bit allocation')
        palette += [0] * (16-len(palette))
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
