"""Regional title inputs must reach derive and receive their own release hashes."""
import json
from pathlib import Path
import unittest

from tools.patcher.dwpatch import regional_derive


class RegionalTitles(unittest.TestCase):
    def test_only_consumed_regional_inputs_require_replay(self):
        files = {'MOVIE/OP1.STR': {'how': 'own'}, 'ETCNA/TITLE256.TIM': {'how': 'own'}}
        mapping = {'files': files}
        self.assertFalse(regional_derive(None, files))
        self.assertFalse(regional_derive(mapping, ['MAP/MAP0/GCITY00.MAP']))
        self.assertTrue(regional_derive(mapping, ['ETCNA/TITLE256.TIM']))
        self.assertTrue(regional_derive(dict(files={}, localize_tool='fromjp.py'), []))

    def test_all_european_mappings_keep_title_without_canonical_pixel_ops(self):
        root = Path(__file__).resolve().parents[1]
        for region in ('eu', 'fr', 'de', 'es', 'it'):
            with self.subTest(region=region):
                mapping = json.loads((root / f'mods/base-discs/dw1-{region}.json').read_text())
                title = mapping['files']['ETCNA/TITLE256.TIM']
                self.assertEqual(title['how'], 'own')
                self.assertEqual(title['source'], 'ETCNA/TITLE256.TIM')
                self.assertNotIn('ops', title)
                self.assertTrue(regional_derive(mapping, ['ETCNA/TITLE256.TIM']))
                self.assertEqual(mapping['files']['ETCNA/TITLE2.TIM']['how'], 'same')


if __name__ == '__main__':
    unittest.main()
