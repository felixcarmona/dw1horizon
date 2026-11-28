"""The title screen's translated Press Start line: the disc's own letters and hand-drawn ones at their native size."""
import contextlib
import io
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from tools.localize import title_letters as T   # noqa: E402

EXTRACTED = os.path.join(ROOT, 'extracted', '')


class _Disc:
    """a stand-in TITLE256: every pixel of the disc's line white"""
    def block(self, x, y, w, h):
        return [[T.TCH['V']] * w for _ in range(h)]


class _Record:
    def __init__(self):
        self.ink = {}

    def s(self, x, y, v):
        self.ink[x, y] = v


class TitleLetters(unittest.TestCase):
    def glyphs(self, letters=T.TITLE_LETTERS):
        return T.title_glyphs(_Disc(), letters, T.TCH)

    def test_every_language_has_every_letter_at_the_lines_height(self):
        for letters in (T.TITLE_LETTERS, *T.RELEASE_TITLE_LETTERS.values()):
            G = self.glyphs(letters)
            for language, text in T.TEXTS.items():
                for ch in text.replace(' ', ''):
                    self.assertIn(ch, G, (language, ch))
                    self.assertEqual(len(G[ch]), 11, (language, ch))       # rows 240-250, never scaled to fit
                    self.assertEqual({len(row) for row in G[ch]}, {len(G[ch][0])}, ch)

    def test_every_translation_has_a_line(self):
        from tools.languages import CODES
        self.assertEqual(set(T.TEXTS), set(CODES) - {'en'})

    def test_hand_drawn_letters_use_only_the_lines_colours(self):
        for ch, rows in T.HAND.items():
            self.assertLessEqual(len(rows), 11, ch)
            self.assertLessEqual(set(''.join(rows)), set(T.TCH) | set('#.'), ch)

    def test_every_line_fits_its_quad_in_the_usa_and_european_letters(self):
        for letters in (T.TITLE_LETTERS, *T.RELEASE_TITLE_LETTERS.values()):
            G = self.glyphs(letters)
            for language, text in T.TEXTS.items():
                t = _Record()
                width = None if language in ('es', 'pt-br') else T.QUAD
                W = T.title_line(G, text, t, T.TCH[' '], width)
                xs = [x for x, _ in t.ink]
                self.assertGreaterEqual(min(xs), 0, language)
                self.assertLess(max(xs), W, language)
                self.assertTrue(all(240 <= y <= 250 for _, y in t.ink), language)
                # centred in the quad (to a column)
                self.assertLessEqual(abs(min(xs) - (W - 1 - max(xs))), 1, (language, min(xs), max(xs), W))

    def test_quads_match_the_executable(self):
        """main.c PRESS_START_QUAD: Spanish and Brazilian Portuguese have the width of their own line, every other
        translation the shared quad"""
        patch = open(os.path.join(ROOT, 'mods/patches/Patch-0242-Brazilian-Portuguese-as-a-third-language.patch'),
                     encoding='utf-8').read()
        quad = re.search(r'int16_t PRESS_START_QUAD\[6\] = \{\n(.*?)\n \};', patch, re.S).group(1)
        pt = re.search(r'MOD_LANG_PT_BR\n\+\s*(-?\d+), (\d+), (\d+), (\d+), (\d+), (\d+),', quad).groups()
        other = re.search(r'MOD_LANG_EN\n\s*(-?\d+), (\d+), (\d+), (\d+), (\d+), (\d+),', quad).groups()
        self.assertEqual(int(other[2]), T.QUAD)
        self.assertEqual((int(other[3]), int(other[5])), (11, 240))
        G = self.glyphs()
        self.assertEqual(T.title_line(G, T.TEXTS['pt-br'], _Record(), T.TCH[' ']), int(pt[2]))
        self.assertEqual(T.title_line(G, T.TEXTS['es'], _Record(), T.TCH[' ']), T.QUAD)

    def test_the_labels_pass_leaves_the_title_line_to_the_disc_letters(self):
        """the line was once font B shrunk to 9 rows (letters lost their shapes): nothing draws over the recipe's"""
        source = open(os.path.join(ROOT, 'tools/localize/labels.py'), encoding='utf-8').read()
        self.assertNotIn("'ETCNA/TITLE256.TIM'", source)

    @unittest.skipUnless(os.path.exists(EXTRACTED + 'ETCNA/TITLE256.TIM'), 'needs the USA disc in extracted/')
    def test_recipe_draws_each_language_in_the_discs_letters(self):
        sys.path.insert(0, os.path.join(ROOT, 'tools/localize/textures/misc'))
        from idx import load
        w, h, px, _, _ = load(EXTRACTED + 'ETCNA/TITLE256.TIM')
        disc = open(EXTRACTED + 'ETCNA/TITLE256.TIM', 'rb').read()
        tch = T.disc_tch(disc)

        class Disc:
            def block(self, x0, y0, bw, bh):
                return [[px(x0 + i, y0 + j) for i in range(bw)] for j in range(bh)]
        G = T.title_glyphs(Disc(), T.TITLE_LETTERS, tch)
        os.makedirs(os.path.join(ROOT, 'build'), exist_ok=True)
        for language in ('fr', 'ja', 'zh-hans'):
            with tempfile.TemporaryDirectory(dir=os.path.join(ROOT, 'build')) as d:
                shutil.copytree(os.path.join(ROOT, 'tools/localize/textures/misc'), d + '/misc')
                env = dict(os.environ, LOCALIZE_EXTRACTED=EXTRACTED, LOCALIZE_PREVIEWS='0', LOCALIZE_LANGUAGE=language)
                subprocess.run([sys.executable, 'build.py', 'title'], cwd=d + '/misc', env=env, check=True,
                               stdout=subprocess.DEVNULL)
                out = open(d + '/misc/TITLE256.TIM.es.idx', 'rb').read()
            want = _Record()
            T.title_line(G, T.TEXTS[language], want, tch[' '], T.QUAD)
            got = {(x, y): out[y * w + x] for y in range(240, 251) for x in range(T.QUAD) if out[y * w + x] != tch[' ']}
            self.assertEqual(got, want.ink, language)

    @unittest.skipUnless(os.path.exists(EXTRACTED + 'ETCNA/TITLE256.TIM'), 'needs the USA disc in extracted/')
    def test_the_built_french_title_keeps_the_recipes_line(self):
        """the whole localize build: nothing after the recipe draws over the line"""
        from tools.localize import build as L
        from tools.localize.build import tim_entries
        sys.path.insert(0, os.path.join(ROOT, 'tools/localize/textures/misc'))
        from idx import load
        w, h, px, _, _ = load(EXTRACTED + 'ETCNA/TITLE256.TIM')
        tch = T.disc_tch(open(EXTRACTED + 'ETCNA/TITLE256.TIM', 'rb').read())

        class Disc:
            def block(self, x0, y0, bw, bh):
                return [[px(x0 + i, y0 + j) for i in range(bw)] for j in range(bh)]
        want = _Record()
        T.title_line(T.title_glyphs(Disc(), T.TITLE_LETTERS, tch), T.TEXTS['fr'], want, tch[' '], T.QUAD)
        os.makedirs(os.path.join(ROOT, 'build'), exist_ok=True)
        with tempfile.TemporaryDirectory(dir=os.path.join(ROOT, 'build')) as d:
            with contextlib.redirect_stdout(io.StringIO()):
                L.build(d + '/out', EXTRACTED, scratch=d + '/scratch', language='fr')
            data = open(d + '/out/fr/ETCNA/TITLE256.TIM', 'rb').read()
        start, _, tw, _ = tim_entries(data)[0]
        got = {(x, y): data[start + y * tw + x] for y in range(240, 251) for x in range(T.QUAD)
               if data[start + y * tw + x] != tch[' ']}
        self.assertEqual(got, want.ink)


if __name__ == '__main__':
    unittest.main()
