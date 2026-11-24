"""The atlas may touch only verified empty texels and palettes of BTLCOMND."""
from pathlib import Path
import struct
import unittest

from tools.field_hud_art import (build, EMPTY_COLOURS, FILL, FILL_COLOURS, FRAME, FRAME_H, FRAME_W, ICON, ICONS,
                                 NATIVE_BAR, PATH, SLOT, rgb15)
from tools.localize.build import tim_entries


class FieldHUDArt(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path=Path(__file__).resolve().parents[1]/'extracted'/PATH
        if not path.exists():
            raise unittest.SkipTest('requires the player disc extraction')
        cls.base=path.read_bytes()
        cls.new=build(cls.base)
        cls.dst=tim_entries(cls.base)[1][0]
        cls.clut=cls.dst-12-512
        cls.native=tim_entries(cls.base)[8][0]

    def pixel(self,data,x,y,base=None):
        b=data[(self.dst if base is None else base)+y*128+x//2]
        return (b>>(4*(x&1)))&15

    def pal(self,row,data=None):
        return struct.unpack_from('<16H',self.new if data is None else data,self.clut+row*32)

    def test_only_allocated_cells_change(self):
        allowed=set(range(self.clut+4*32,self.clut+13*32))
        other=tim_entries(self.base)[4][0]-12-512+15*32
        allowed.update(range(other,other+32))
        allowed.update(range(self.clut+15*32,self.clut+16*32))
        cells=[(u,v,ICON,ICON) for u,v in ICONS]+[(*FRAME,FRAME_W,FRAME_H),(*FILL,SLOT,2)]
        for u,v,w,h in cells:
            allowed.update(self.dst+y*128+x//2 for y in range(v,v+h) for x in range(u,u+w))
        self.assertEqual(len(self.base),len(self.new))
        self.assertTrue({i for i,(a,b) in enumerate(zip(self.base,self.new)) if a!=b}<=allowed)
        # Native commands, bubbles, original HUD, clock and all other entries survive byte for byte.
        for i,(pos,_,w,h) in enumerate(tim_entries(self.base)):
            if i!=1:
                self.assertEqual(self.base[pos:pos+w*h//2],self.new[pos:pos+w*h//2])

    def test_occupied_texels_and_palettes_fail_closed(self):
        u,v=FRAME
        bad=bytearray(self.base);bad[self.dst+v*128+u//2]=0x11
        with self.assertRaisesRegex(ValueError,'occupied'):
            build(bad)
        for row in (4,11,12):
            bad=bytearray(self.base);bad[self.clut+row*32]=1
            with self.assertRaisesRegex(ValueError,'occupied'):
                build(bad)

    def test_frame_is_the_native_bar_with_a_short_empty_slot(self):
        bu,bv,bc=NATIVE_BAR
        native_pal=struct.unpack_from('<16H',self.base,self.native-12-512+(bc-488)*32)
        keep=list(range(0,18))+[18]*SLOT+list(range(68,76))
        pal=self.pal(12)
        for y in range(FRAME_H):
            for x,sx in enumerate(keep):
                actual=pal[self.pixel(self.new,FRAME[0]+x,FRAME[1]+y)]
                if y in (3,4) and 18<=x<18+SLOT:
                    self.assertEqual(actual,rgb15(EMPTY_COLOURS[y-3]))
                else:
                    self.assertEqual(actual,native_pal[self.pixel(self.base,bu+sx,bv-128+y,self.native)],(x,y))

    def test_fill_is_one_native_blue(self):
        pal=self.pal(11)
        for y,rgb in enumerate(FILL_COLOURS):
            for x in range(SLOT):
                self.assertEqual(pal[self.pixel(self.new,FILL[0]+x,FILL[1]+y)],rgb15(rgb))
        self.assertEqual(sum(1 for c in pal if c),2)

    def test_need_icons_have_no_grey_block(self):
        greys={rgb15(c) for c in ((144,144,144),(184,184,184))}
        for k in (4,6):
            u,v=ICONS[k]
            pal=self.pal(4+k)
            colours={pal[self.pixel(self.new,u+x,v+y)] for y in range(ICON) for x in range(ICON)}
            self.assertFalse(colours&greys)
            self.assertIn(0,colours)

    def test_habitat_faces_match_native_pixels_in_both_phases(self):
        native_pal=struct.unpack_from('<16H',self.base,self.native-12-512+15*32)
        for k in range(2):
            u,v=ICONS[k]
            alternate=self.clut+15*32 if k==0 else tim_entries(self.base)[4][0]-12-512+15*32
            for phase,clut in enumerate((self.clut+(4+k)*32,alternate)):
                pal=struct.unpack_from('<16H',self.new,clut)
                for y in range(ICON):
                    for x in range(ICON):
                        actual=pal[self.pixel(self.new,u+x,v+y)]
                        sx=(64 if k==0 else 97)+phase*11+x
                        colour=native_pal[self.pixel(self.base,sx,116+y,self.native)]
                        self.assertEqual(actual,colour)
            bad=bytearray(self.base);bad[alternate]=1
            with self.assertRaisesRegex(ValueError,'occupied'):
                build(bad)


if __name__=='__main__':unittest.main()
