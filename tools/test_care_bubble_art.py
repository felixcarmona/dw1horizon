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
        allowed={dst+y*128+x for y in range(16) for x in range(112,128)}
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
            left=(16-len(art.LABELS[which][0]))//2
            for y in range(16):
                for x in range(16):
                    if not (7<=y<15 and left-1<=x<left+len(art.LABELS[which][0])+1):
                        self.assertEqual(art._pixel(result,dst,224+16*which+x,y),art._pixel(native,src,item*16+x,y))
            old=struct.unpack_from('<16H',native,art._clut(src,24)+item*32)
            new=struct.unpack_from('<16H',result,art._clut(feel,16)+(13+which)*32)
            for index in range(16):
                if index not in (plate,ink):self.assertEqual(new[index],old[index])
            self.assertEqual(new[plate],0x7fff)

    def test_occupied_allocation_fails_without_mutating_input(self):
        native=bytearray(Path('extracted',art.PATH).read_bytes());dst=tim_entries(native)[1][0]
        native[dst+112]=1;before=bytes(native)
        with self.assertRaisesRegex(ValueError,'occupied'):art.build(native)
        self.assertEqual(bytes(native),before)


if __name__=='__main__':unittest.main()
