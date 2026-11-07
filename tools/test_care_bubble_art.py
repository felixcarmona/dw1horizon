"""Depleted native resource icons preserve uploads, silhouettes and visible fill."""
from pathlib import Path
import struct
import unittest

from tools import care_bubble_art as art
from tools.localize.build import tim_entries


@unittest.skipUnless(Path('extracted',art.PATH).exists(),'needs source UI textures')
class CareBubbleArt(unittest.TestCase):
    def test_only_reserved_pixels_and_palettes_change(self):
        native=Path('extracted',art.PATH).read_bytes()
        result=art.build(native)
        entries=tim_entries(native); dst=entries[1][0]; feel=entries[3][0]
        allowed={dst+(v+y)*128+x for u,v,w in art.TILES for y in range(16) for x in range(u//2,(u+w)//2)}
        palette=art._clut(feel,16)+13*32
        allowed.update(range(palette,palette+64))
        changed={i for i,(a,b) in enumerate(zip(native,result)) if a!=b}
        self.assertTrue(changed);self.assertLessEqual(changed,allowed)
        self.assertEqual(len(native),len(result))
        standalone=Path('extracted',art.FEEL).read_bytes()
        patched=art.feel(standalone,result);p=art._clut(tim_entries(standalone)[0][0],16)+13*32
        self.assertEqual(patched[p:p+64],result[palette:palette+64])
        self.assertEqual(patched[:p],standalone[:p]);self.assertEqual(patched[p+64:],standalone[p+64:])

    def test_native_silhouettes_empty_tops_and_coloured_bottoms(self):
        native=Path('extracted',art.PATH).read_bytes();result=art.build(native)
        entries=tim_entries(native);src=entries[0][0];dst=entries[1][0];feel=entries[3][0]
        source_palette=struct.unpack_from('<16H',native,art._clut(src,16)+11*32)
        for shift in (0,5,10):
            # Empty graphite must remain visibly lighter than the native outline.
            self.assertGreaterEqual(((art.EMPTY >> shift) & 31)-2,6)
        for which,(sx,sy) in enumerate(art.ICONS):
            u,v,_=art.TILES[which]
            palette=struct.unpack_from('<16H',result,art._clut(feel,16)+(13+which)*32)
            fill=0;empty=0
            for y in range(16):
                for x in range(16):
                    got=palette[art._pixel(result,dst,u+x,v+y)]
                    if x>=11 or y>=11:
                        self.assertEqual(got,0);continue
                    old=source_palette[art._pixel(native,src,sx+x,sy+y)]
                    self.assertEqual(got==0,old==0,'silhouette changed')
                    if old in (0,0x0842) or y>=7:
                        self.assertEqual(got,old,'native outline or bottom colour changed')
                        fill+=int(y>=7 and old not in (0,0x0842))
                    else:
                        self.assertEqual(got,art.EMPTY);empty+=1
            self.assertGreaterEqual(fill,8)
            self.assertGreater(empty,fill)
            # The vacant right half of the former wide MP cell is reclaimed.
            for y in range(16):
                for x in range(240,256):self.assertEqual(art._pixel(result,dst,x,v+y),0)

    def test_occupied_allocation_fails_without_mutating_input(self):
        for row in (0,16):
            native=bytearray(Path('extracted',art.PATH).read_bytes());dst=tim_entries(native)[1][0]
            native[dst+row*128+112]=1;before=bytes(native)
            with self.assertRaisesRegex(ValueError,'occupied'):art.build(native)
            self.assertEqual(bytes(native),before)

    def test_fill_survives_native_field_point_sampling(self):
        result=art.build(Path('extracted',art.PATH).read_bytes())
        entries=tim_entries(result);dst=entries[1][0];feel=entries[3][0]
        for which,(u,v,_) in enumerate(art.TILES):
            palette=struct.unpack_from('<16H',result,art._clut(feel,16)+(13+which)*32)
            for pixels in (8,9,10,11,12,14):
                step=11/pixels
                for px in (0,.25,.5,.75):
                    for py in (0,.25,.5,.75):
                        coloured=empty=0
                        for y in range(pixels):
                            sy=min(10,int((y+py)*step))
                            for x in range(pixels):
                                sx=min(10,int((x+px)*step))
                                c=palette[art._pixel(result,dst,u+sx,v+sy)]
                                r,g,b=c&31,(c>>5)&31,(c>>10)&31
                                coloured+=int(r>g+3 and r>b+3 if which==0 else b>r+3 and b>g)
                                empty+=int(c==art.EMPTY)
                        self.assertGreaterEqual(coloured,2,(which,pixels,px,py))
                        self.assertGreater(empty,coloured,(which,pixels,px,py))



if __name__=='__main__':unittest.main()
