"""Recovery bubble art preserves native uploads and uses explicit pixel labels."""
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

    def test_preserves_disk_pixels_outside_label_plate_and_own_palette(self):
        native=Path('extracted',art.PATH).read_bytes();result=art.build(native)
        entries=tim_entries(native);src=entries[6][0];dst=entries[1][0];feel=entries[3][0]
        for which,(item,plate,ink) in enumerate(((0,1,8),(4,3,7))):
            u,v,width=art.TILES[which]
            left=(width-len(art.LABELS[which][0]))//2
            top=7 if which==0 else 5
            border=1 if which==0 else 0
            for y in range(16):
                for x in range(width):
                    if not (top<=y<top+8 and left-border<=x<left+len(art.LABELS[which][0])+border):
                        expected=art._pixel(native,src,item*16+x-(width-16)//2,y) if (width-16)//2<=x<(width+16)//2 else 0
                        self.assertEqual(art._pixel(result,dst,u+x,v+y),expected)
            old=struct.unpack_from('<16H',native,art._clut(src,24)+item*32)
            new=struct.unpack_from('<16H',result,art._clut(feel,16)+(13+which)*32)
            for index in range(16):
                if index not in (plate,ink):self.assertEqual(new[index],old[index])
            self.assertEqual(new[plate],0x7fff)

    def test_occupied_allocation_fails_without_mutating_input(self):
        for row in (0,16):
            native=bytearray(Path('extracted',art.PATH).read_bytes());dst=tim_entries(native)[1][0]
            native[dst+row*128+112]=1;before=bytes(native)
            with self.assertRaisesRegex(ValueError,'occupied'):art.build(native)
            self.assertEqual(bytes(native),before)

    def test_m_stems_tip_and_valleys_survive_field_point_sampling(self):
        # A one-texel stem or valley can disappear at field depth. Test the
        # character's distinguishing structure across sampling phase, not a
        # single screenshot alignment: two upper strokes, three at its tip.
        m=[row[:10] for row in art.LABELS[1]]
        def runs(row):
            return sum(v and (i==0 or not row[i-1]) for i,v in enumerate(row))
        for step in (1,1.25,1.5,1.75,2):
            for phase in (0,.25,.5,.75):
                indices=[];x=phase*step
                while x<10:
                    indices.append(int(x));x+=step
                sampled=[[row[i]!='.' for i in indices] for row in m]
                self.assertTrue(sampled[0][0] and sampled[0][-1])
                self.assertEqual(runs(sampled[0]),2)
                self.assertEqual(runs(sampled[3]),3)
                self.assertEqual(runs(sampled[5]),2)
                half=len(indices)//2
                self.assertGreater(sum(sampled[1][:half]),sum(sampled[0][:half]))
                self.assertGreater(sum(sampled[1][half:]),sum(sampled[0][half:]))



if __name__=='__main__':unittest.main()
