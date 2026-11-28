"""Every element has a battle command icon: the five new rows' tiles keep to empty BTLCOMND texels and the C side
(include/dw/tech_row_icons.h, from its patch) reads the same cells and palettes."""
import re
import struct
import unittest
from pathlib import Path

from tools import battle_icon_art as art
from tools import care_bubble_art
from tools.field_hud_art import build as field_hud_art
from tools.localize import tech_rows_art
from tools.localize.build import tim_entries

ROOT = Path(__file__).resolve().parents[1]
HEADER = 'include/dw/tech_row_icons.h'
ORIGINAL_UVS = tuple((k * 0x20, 0xd0) for k in range(7))


def header_text():
    """The header as its patch creates it."""
    for name in (ROOT / 'mods/patches/series').read_text().split():
        text = (ROOT / 'mods/patches' / name).read_text(errors='replace')
        m = re.search(r'^diff --git a/%s b/%s\nnew file mode.*?\n@@[^\n]*\n(.*?)(?=^diff --git |\Z)' % (HEADER, HEADER),
                      text, re.S | re.M)
        if m:
            return '\n'.join(line[1:] for line in m.group(1).splitlines() if line.startswith('+')) + '\n'
    raise AssertionError('no patch in the series creates ' + HEADER)


def define(text, name):
    m = re.search(r'^#define %s\s+(.*)$' % name, text, re.M)
    if not m:
        raise AssertionError(name + ' is not in ' + HEADER)
    return m.group(1).split('/*')[0].strip()


class Header(unittest.TestCase):
    def test_c_reads_the_cells_and_palettes_drawn(self):
        text = header_text()
        uvs = tuple((int(u, 0), int(v, 0)) for u, v in
                    re.findall(r'\{\s*(\w+),\s*(\w+)\s*\}', define(text, 'TECH_ROW_BATTLE_ICON_UVS')))
        self.assertEqual(uvs, art.uvs())
        self.assertEqual(int(define(text, 'TECH_ROW_BATTLE_CLUT'), 0), tech_rows_art.CLUT_ID)
        self.assertEqual(int(define(text, 'TECH_ROW_BATTLE_CLUT_ONE'), 0), tech_rows_art.NEW_CLUT_IDS[0])
        self.assertEqual(int(define(text, 'TECH_ROW_BATTLE_CLUT_BLINK'), 0), tech_rows_art.NEW_CLUT_IDS[1])
        self.assertEqual(art.CLUTS, (tech_rows_art.CLUT_ID,) * 3 + (tech_rows_art.NEW_CLUT_IDS[0],) * 2)

    def test_tables_cover_every_element(self):
        # the three fights' tables are twelve rows long (NUM_ELEMENTS): the original eight-row table drew Darkness
        # from { 0, 0 }, outside BTLCOMND, and read Light..Earth past its end
        patch = (ROOT / 'mods/patches/Battle-command-icons-for-the-new-technique-rows.patch').read_text()
        for prefix in ('BTL', 'STD', 'VS'):
            self.assertIn(f'+uint8_t {prefix}_SPECIAL_ICON_UVS[NUM_ELEMENTS][2] = {{', patch)
            self.assertIn(f'+\t\tTECH_ROW_SET_ICON(prim, {prefix}_SPECIAL_ICON_UVS, eff);', patch)
        self.assertEqual(patch.count('+\t\t\tTECH_ROW_BLINK_ICON(prim);'), 3)

    def test_patcher_rebuilds_the_tables_from_the_same_cells(self):
        # the three twelve-row tables travel as a player-side recipe (tools/patcher/tabledata.py), not as delta
        # data: with eight rows of the original and the rest rewritten, no disc witnesses them
        import sys
        sys.path.insert(0, str(ROOT / 'tools/patcher'))
        import fontcopy
        import tabledata
        data = bytes(v for cell in ORIGINAL_UVS + art.uvs() for v in cell)
        self.assertEqual(fontcopy.semantic_table('battle_element_icons', []), data)
        for name, source in (('BTL', 'src/btl/battle_hud.c'), ('VS', 'src/vs/vs_main.c'), ('STD', 'src/std/std_main.c')):
            obj = dict(offset=0, length=24, section=f'.data.{name}_SPECIAL_ICON_UVS', source=source)
            self.assertEqual(tabledata.authored_recipe(obj, data)['generator'], 'battle_element_icons')
            self.assertIsNone(tabledata.authored_recipe(obj, bytes(24)))
            self.assertIsNone(tabledata.authored_recipe(dict(obj, source='src/btl/other.c'), data))


class Atlas(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = ROOT / 'extracted' / art.PATH
        if not path.exists():
            raise unittest.SkipTest('requires the player disc extraction')
        cls.base = care_bubble_art.build(field_hud_art(path.read_bytes()))
        cls.new = art.build(cls.base)
        cls.dst = tim_entries(cls.base)[art.ENTRY][0]

    def pixel(self, data, x, y):
        return (data[self.dst + y * 128 + x // 2] >> (4 * (x & 1))) & 15

    def test_only_the_windows_change(self):
        allowed = set()
        for u, v, w, h in art.windows():
            allowed |= {self.dst + y * 128 + x // 2 for y in range(v, v + h) for x in range(u, u + w)}
        self.assertEqual(len(self.base), len(self.new))
        self.assertTrue({i for i, (a, b) in enumerate(zip(self.base, self.new)) if a != b} <= allowed)

    def test_windows_stay_in_the_page_and_apart(self):
        taken = set()
        for u, v, w, h in art.windows():
            # the engine's quad edges are u + 16 and v + 15 as bytes: they must not wrap
            self.assertLessEqual(u + w, 255)
            self.assertLessEqual(v + art.ATLAS_V + h, 255)
            cells = {(x, y) for y in range(v, v + h) for x in range(u, u + w)}
            self.assertFalse(cells & taken)
            taken |= cells

    def test_every_element_draws_its_techset_tile(self):
        dlw, pairs = tech_rows_art.art()
        we, singles = tech_rows_art.new_art()
        # the original seven still sit where the original table points
        for u, v in ORIGINAL_UVS:
            for frame in (0, 16):
                self.assertTrue(any(self.pixel(self.new, u + frame + x, v - art.ATLAS_V + y)
                                    for y in range(15) for x in range(16)))
        tiles = [(dlw, pair) for pair in pairs] + [(we[0], [tile]) for tile in singles]
        for (u, v), (palette, frames) in zip(art.CELLS, tiles):
            for k, tile in enumerate(frames):
                seen = set()
                for y in range(15):
                    for x in range(16):
                        n = self.pixel(self.new, u + 16 * k + x, v + y)
                        colour = palette[n]
                        dy, dx = y - art.OFFSET[1], x - art.OFFSET[0]
                        if 0 <= dx < 13 and 0 <= dy < 13:
                            sx, sy = (1 + [i for i in range(10) for _ in range(2 if i in art.DOUBLED else 1)][t]
                                      for t in (dx, dy))
                            want = tile[sy][sx]
                            self.assertEqual(colour, 0 if want == 12 else palette[want], (u, v, k, x, y))
                        else:
                            self.assertEqual(colour, 0, (u, v, k, x, y))
                        if colour:
                            seen.add(colour)
                self.assertGreaterEqual(len(seen), 3)
        # both palettes draw the empty texels clear
        self.assertEqual(dlw[art.CLEAR], 0)
        self.assertEqual((we[0][art.CLEAR], we[1][art.CLEAR]), (0, 0))

    def test_occupied_texels_fail_closed(self):
        for u, v in art.CELLS:
            bad = bytearray(self.base)
            bad[self.dst + (v + 7) * 128 + (u + 8) // 2] = 0x11
            with self.assertRaisesRegex(ValueError, 'occupied'):
                art.build(bytes(bad))

    def test_palette_rows_untouched(self):
        clut = self.dst - 12 - 512
        self.assertEqual(self.base[clut:clut + 512], self.new[clut:clut + 512])
        self.assertEqual(struct.unpack_from('<4H', self.new, self.dst - 8), (960, 448, 64, 64))


if __name__ == '__main__':
    unittest.main()
