"""The atlas may touch only verified empty texels and palettes of BTLCOMND."""
from pathlib import Path
import struct
import unittest

from tools.field_hud_art import build, CELLS, PATH, SOURCES, rgb15
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

    def pixel(self,data,x,y):
        b=data[self.dst+y*128+x//2]
        return (b>>(4*(x&1)))&15

    def test_only_allocated_cells_change(self):
        allowed=set(range(self.clut+4*32,self.clut+15*32))
        for u,v in CELLS:
            allowed.update(self.dst+y*128+x//2 for y in range(v,v+13) for x in range(u,u+34))
        allowed.update(self.dst+y*128+x//2 for y in range(59,63) for x in range(144,182))
        self.assertEqual(len(self.base),len(self.new))
        self.assertTrue({i for i,(a,b) in enumerate(zip(self.base,self.new)) if a!=b}<=allowed)
        # Native commands, bubbles, original HUD, clock and all other entries survive byte for byte.
        for i,(pos,_,w,h) in enumerate(tim_entries(self.base)):
            if i!=1:
                self.assertEqual(self.base[pos:pos+w*h//2],self.new[pos:pos+w*h//2])

    def test_occupied_texels_and_palettes_fail_closed(self):
        bad=bytearray(self.base);u,v=CELLS[0];bad[self.dst+v*128+u//2]=1
        with self.assertRaisesRegex(ValueError,'occupied'):
            build(bad)
        bad=bytearray(self.base);bad[self.clut+4*32]=1
        with self.assertRaisesRegex(ValueError,'occupied'):
            build(bad)

    def test_tiles_have_identical_housing_and_track(self):
        for k,(u,v) in enumerate(CELLS):
            pal=struct.unpack_from('<16H',self.new,self.clut+(4+k)*32)
            for y in range(13):
                for x in range(34):
                    if 1<=x<=11 and 1<=y<=11:continue
                    expected=(184,184,184) if x<13 and (x==0 or y==0) else \
                             (64,64,64) if x<13 and (x==12 or y==12) else \
                             (144,144,144) if x<13 else \
                             (112,112,112) if 15<=x<33 and y==6 else \
                             (88,88,88) if 15<=x<33 and y==7 else \
                             (16,24,32) if 14<=x<34 and 5<=y<9 else (0,0,0)
                    self.assertEqual(pal[self.pixel(self.new,u+x,v+y)],rgb15(expected),(k,x,y))

    def test_active_need_tints_whole_icon_preserves_track(self):
        for k in range(4,7):
            normal=struct.unpack_from('<16H',self.new,self.clut+(4+k)*32)
            active=struct.unpack_from('<16H',self.new,self.clut+(8+k)*32)
            u,v=CELLS[k]
            for y in range(13):
                for x in range(34):
                    index=self.pixel(self.new,u+x,v+y)
                    c=normal[index]
                    if x<13 and c:
                        rgb=[((c>>shift)&31)*255/31 for shift in (0,5,10)]
                        lum=(.299*rgb[0]+.587*rgb[1]+.114*rgb[2])/255
                        want=rgb15([round(.45*a+.55*lum*b) for a,b in zip(rgb,(235,90,80))]) or 0x8000
                    else:
                        want=c
                    self.assertEqual(active[index],want,(k,x,y))
            self.assertEqual(active[0],0)
        bad=bytearray(self.base);bad[self.clut+12*32]=1
        with self.assertRaisesRegex(ValueError,'occupied'):
            build(bad)

    def test_need_fills_are_light_blue(self):
        pal=struct.unpack_from('<16H',self.new,self.clut+11*32)
        for y,rgb in enumerate(((160,210,255),(120,190,255))):
            for x in range(18):
                self.assertEqual(pal[self.pixel(self.new,164+x,59+y)],rgb15(rgb))

    def test_status_screen_fill_colours(self):
        pal=struct.unpack_from('<16H',self.new,self.clut+11*32)
        colours=((117,218,96),(48,200,40),(234,117,96),(224,48,40))
        for y,rgb in enumerate(colours):
            for x in range(18):
                self.assertEqual(pal[self.pixel(self.new,144+x,59+y)],rgb15(rgb))


if __name__=='__main__':unittest.main()
