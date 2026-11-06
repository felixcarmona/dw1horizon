"""Language sign units preserve the serial builder's pixels and file-list order."""
from concurrent.futures import ProcessPoolExecutor
import multiprocessing
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch

from tools.derive.steps import signs as step
from tools.localize import signs, cutout

ROOT = Path(__file__).resolve().parents[1]


def small_sign(args):
    language, out = args
    return step.run_pass(str(ROOT), out, [], (language,), f'files.{language}.txt')


class SignUnits(unittest.TestCase):
    def test_units_have_independent_language_listings(self):
        ctx = SimpleNamespace(root='/fixture', env={}, path=lambda *p: '/'.join(p))
        with patch.object(step, 'passes', return_value=[('lang-signs', []), ('lang-signs-base', [])]), \
             patch.object(step.localize, 'lang_on', return_value=True), \
             patch.object(step.localize, 'translations', return_value=('es', 'ja')):
            units = step.units(ctx)
        self.assertEqual(len(units), 6)
        self.assertEqual(len({p for unit in units for p in unit.outputs}), 6)
        self.assertTrue(all(len(unit.args[3]) == 1 for unit in units))

    def test_merge_preserves_tfs_then_map_order_and_rejects_conflicts(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td); folder=root/'lang-signs'; folder.mkdir()
            ctx = SimpleNamespace(env={}, path=lambda *p: str(root.joinpath(*p)))
            (folder/'files.en.txt').write_text('en Z.TFS\nen A.MAP\n')
            (folder/'files.es.txt').write_text('es A.TFS\nes A.MAP\n')
            with patch.object(step, 'passes', return_value=[('lang-signs', [])]), \
                 patch.object(step.localize, 'lang_on', return_value=True), \
                 patch.object(step.localize, 'translations', return_value=('es',)):
                step.finish(ctx)
                self.assertEqual((folder/'files.txt').read_text(), 'en Z.TFS\nes A.TFS\nen A.MAP\nes A.MAP\n')
                (folder/'files.es.txt').write_text('en Z.TFS\n')
                with self.assertRaisesRegex(step.runner.StepError, 'conflicting'):
                    step.finish(ctx)

    @unittest.skipUnless((ROOT/'extracted/MAP/MAP1/MAYO11.MAP').exists(), 'requires USA sign fixtures')
    def test_parallel_language_pixels_match_serial_multi_language_builder(self):
        languages = ('en', 'es', 'ja')
        original_names = cutout.names
        with tempfile.TemporaryDirectory() as td, patch.object(cutout, 'names',
                side_effect=lambda language: [n for n in original_names(language) if n in ('audit-13', 'mayo11_ogre')]):
            root = Path(td); reference = root/'reference'; out=root/'units'/'lang-signs'
            signs.signs(str(reference), languages=languages)
            with ProcessPoolExecutor(3, mp_context=multiprocessing.get_context('fork')) as pool:
                list(pool.map(small_sign, [(language, str(out)) for language in languages]))
            ctx = SimpleNamespace(env={}, path=lambda *p: str((root/'units').joinpath(*p)))
            with patch.object(step, 'passes', return_value=[('lang-signs', [])]), \
                 patch.object(step.localize, 'lang_on', return_value=True), \
                 patch.object(step.localize, 'translations', return_value=languages[1:]):
                step.finish(ctx)
            def artifacts(folder):
                return {str(p.relative_to(folder)):p.read_bytes() for p in folder.rglob('*')
                        if p.is_file() and (p.suffix in ('.TFS', '.MAP') or p.name=='files.txt')}
            self.assertEqual(artifacts(reference), artifacts(out))


if __name__ == '__main__':
    unittest.main()
