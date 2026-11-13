"""The tool takes a native-bound species' bone count from its generated skeleton, as the game build does."""
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mmd

SPECIES = (270, 183, 205, 430, 460)
ROOT = Path(__file__).resolve().parents[1]
SOURCE = Path(os.environ.get('MODEL_EDIT_FROM', ROOT / 'build/everything'))


class NativeBoneCount(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not (SOURCE / 'source-games/dcb/disc/SYSTEM.CNF').is_file():
            raise unittest.SkipTest('needs a derive build with source-games (MODEL_EDIT_FROM)')
        import argparse
        from tools.models import edit
        cls.edit = edit
        cls.a = argparse.Namespace(games=None, from_dir=str(SOURCE), source_disc=None)
        cls.a.games_dir = edit.games_dir(cls.a)

    def final(self, t):
        edit = self.edit
        row, = edit.rows(edit.load(edit.MODELS), [str(t)])
        model, tim, _ = edit.build(self.a, row)
        return edit.provider_output(t, model, tim, edit.donor_models(self.a, t))

    def test_final_models_parse_and_rebuild_byte_identical(self):
        for t in SPECIES:
            with self.subTest(species=t):
                data, _, s = self.final(t)
                rig = s['model']['skeleton']
                if t == 270:    # 19 bones in the generated rig, 24 in the species file
                    import species
                    self.assertNotEqual(len(rig), len(species.imports()[t]['model']['skeleton']))
                with tempfile.TemporaryDirectory() as tmp:
                    path = Path(tmp) / f'{t}.MMD'
                    path.write_bytes(data)
                    (Path(tmp) / f'{t}-report.json').write_text(json.dumps({'generated_skeleton': rig}))
                    m = mmd.MMD.load(str(path), t)      # no "unknown animation opcode": the pose table is read aligned
                self.assertEqual(m.nbones, len(rig))
                self.assertEqual(mmd.exe().bone_count[t], len(rig))
                self.assertEqual(m.build(), data)


if __name__ == '__main__':
    unittest.main()
