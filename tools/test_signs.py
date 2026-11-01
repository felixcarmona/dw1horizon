"""Sign foregrounds with an opaque palette zero and a transparent colour elsewhere."""
import struct
import unittest
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from tools.localize.signs import Pixels, sprite_paste
from tools.localize import signs, cutout


class SpriteTransparency(unittest.TestCase):
    def paste(self, palette_alpha):
        pixels = bytes((0, 1, 255, 2))
        palette = [0x0482, 0x7FFF, 0x001F] + [0x0482] * 252 + [0]
        tim = (struct.pack('<III4H', 0x10, 9, 524, 0, 480, 256, 1)
               + struct.pack('<256H', *palette)
               + struct.pack('<I4H', 12 + len(pixels), 384, 0, 2, 1) + pixels)
        m = SimpleNamespace(
            tims=[tim],
            sprites=[dict(clut=-1, texX=0, texY=0, width=4, height=1)],
            instances=[dict(frames=[0], x=0, y=0, flag=0)],
        )
        t = SimpleNamespace(cluts=[palette])
        sprite_paste(m, t, Pixels(4, 1, [(255, 255, 255)] * 4),
                     Pixels(4, 1, [255] * 4), 0, 0, palette_alpha=palette_alpha)
        return m.tims[0][-4:]

    def test_opaque_zero_is_repainted_and_transparent_255_stays_clear(self):
        self.assertEqual(self.paste(True), bytes((1, 1, 255, 1)))

    def test_other_signs_retain_the_historical_index_zero_rule(self):
        self.assertEqual(self.paste(False), bytes((0, 1, 1, 1)))


@unittest.skipUnless(Path('extracted/MAP/MAP1/MAYO11.MAP').exists(), 'needs extracted USA disc')
class OgreSign(unittest.TestCase):
    def setUp(self):
        self.mp = 'MAP/MAP1/MAYO11'
        self.m = signs.dwmap.MapFile(Path('extracted', self.mp + '.MAP').read_bytes())
        self.t = signs.dwmap.TfsFile(Path('extracted', self.mp + '.TFS').read_bytes())
        self.base = signs.disc_crop('extracted', self.mp, (27, 148, 223, 258), {})

    def test_takeover_covers_background_and_changes_only_its_frame(self):
        before = list(self.m.tims)
        for lang in ('en', 'es', 'fr', 'de', 'it', 'pt-br', 'ca'):
            with self.subTest(language=lang):
                m = signs.dwmap.MapFile(Path('extracted', self.mp + '.MAP').read_bytes())
                w, h, cut = cutout.load(lang + '/mayo11_ogre', self.base)
                new = [p[:3] if p[3] else self.base[i] for i, p in enumerate(cut)]
                n = signs.sprite_paste(m, self.t, signs.Pixels(w, h, new),
                                       signs.Pixels(w, h, [255] * (w*h)), 27, 148,
                                       frames=(6,), opaque=True)
                self.assertEqual(n, (184 - 27) * 96)
                self.assertEqual(m.tims[0], before[0])
                self.assertEqual(m.tims[2], before[2])
                original = signs.dwmap.TIM(before[1])
                changed = signs.dwmap.TIM(m.tims[1])
                self.assertEqual(original.clut, changed.clut)
                stride = original.w * 2
                self.assertEqual(original.pixels[:96*stride], changed.pixels[:96*stride])
                self.assertEqual(original.pixels[192*stride:], changed.pixels[192*stride:])
                # Every pixel under the localized sign is now opaque, including
                # the original transparent holes through which DRILL leaked.
                for y in range(96, 192):
                    for x in range(27, 184):
                        index = changed.pixels[y*stride+x]
                        self.assertNotEqual(self.t.cluts[0][index], 0)
                self.assertEqual(len(m.build()), len(Path('extracted', self.mp + '.MAP').read_bytes()))

    def test_japanese_delta_is_empty(self):
        _, _, cut = cutout.load('ja/mayo11_ogre', self.base)
        self.assertFalse(any(p[3] for p in cut))

    def test_normal_wording_does_not_get_painted_into_tree_or_lamp_glow(self):
        names = cutout.names
        with tempfile.TemporaryDirectory() as out, patch.object(
                cutout, 'names', side_effect=lambda lang: [n for n in names(lang)
                                                         if n in ('audit-13', 'mayo11_ogre')]):
            signs.signs(out, languages=('en',))
            result = signs.dwmap.MapFile(Path(out, 'en', self.mp + '.MAP').read_bytes())
        self.assertEqual(result.tims[0], self.m.tims[0])
        self.assertEqual(result.tims[2], self.m.tims[2])

    def test_japanese_job_emits_the_original_sprite_copy(self):
        names = cutout.names
        with tempfile.TemporaryDirectory() as out, patch.object(
                cutout, 'names', side_effect=lambda lang: [n for n in names(lang)
                                                         if n in ('audit-13', 'mayo11_ogre')]):
            signs.signs(out, languages=('ja',))
            result = signs.dwmap.MapFile(Path(out, 'ja', self.mp + '.MAP').read_bytes())
        self.assertEqual(result.tims, self.m.tims)

    def test_sprite_message_never_targets_the_background(self):
        self.assertEqual(signs.places('mayo11_ogre', 'extracted'),
                         [(self.mp, (27, 148, 223, 258))])
        self.assertEqual(signs.SPRITE_JOBS['mayo11_ogre']['frames'], (6,))


if __name__ == '__main__':
    unittest.main()
