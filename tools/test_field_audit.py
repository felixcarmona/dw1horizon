"""Final overlays must be parsed with their generated skeleton, never the source rig."""
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools.models import audit_field
from tools.models.battle_qa import Rig
import numeric as np


class FinalSkeleton(unittest.TestCase):
    def test_final_catalogue_selects_last_stage_among_multiple_overlays(self):
        with tempfile.TemporaryDirectory() as folder:
            out = Path(folder)
            (out / 'imported-species-models').mkdir()
            (out / 'species').mkdir()
            for name in ('206-first.MMD', '206-care.MMD'):
                (out / 'imported-species-models' / name).write_bytes(b'model')
            path = out / 'imported-species-models/206-care.MMD'
            sk = [[-1, -1]] + [[-1, 0]] * 27
            (out / 'species/206-final.json').write_text(json.dumps(dict(model=dict(skeleton=sk, file=str(path)))))
            with patch.object(audit_field.mmd.MMD, 'parse'), patch.object(audit_field.mmd, 'exe'):
                _, _, actual = audit_field.load(out, dict(id=206, model=dict(skeleton=sk[:26])))
                self.assertEqual(actual, path)

    def test_final_catalogue_carries_rig_through_a_later_care_overlay(self):
        with tempfile.TemporaryDirectory() as folder:
            out = Path(folder)
            (out / 'imported-species-models').mkdir()
            (out / 'imported-species-models/206-care.MMD').write_bytes(b'model')
            (out / 'species').mkdir()
            sk = [[-1, -1]] + [[-1, 0]] * 27
            (out / 'species/206-final.json').write_text(json.dumps(dict(model=dict(skeleton=sk))))
            with patch.object(audit_field.mmd.MMD, 'parse') as parse, patch.object(audit_field.mmd, 'exe'):
                _, actual, _ = audit_field.load(out, dict(id=206, model=dict(skeleton=sk[:26])))
                parse.assert_called_once_with(b'model', 28)
                self.assertEqual(actual, sk)

    def test_generated_overlay_skeleton_is_used_for_parsing_and_playback(self):
        with tempfile.TemporaryDirectory() as folder:
            out = Path(folder)
            overlays = out / 'imported-species-models'
            overlays.mkdir()
            (overlays / '206-reviewed.MMD').write_bytes(b'model')
            sk = [[-1, -1]] + [[-1, 0]] * 27
            (overlays / '206-reviewed-report.json').write_text(json.dumps({'generated_skeleton': sk}))
            record = dict(id=206, model=dict(skeleton=sk[:26]))
            with patch.object(audit_field.mmd.MMD, 'parse') as parse, \
                    patch.object(audit_field.mmd, 'exe') as exe:
                exe.return_value.bone_count = {}
                exe.return_value.skeleton = {}
                _, actual, _ = audit_field.load(out, record)
                parse.assert_called_once_with(b'model', 28)
                self.assertEqual(actual, sk)
                self.assertEqual(exe.return_value.bone_count[206], 28)
                self.assertEqual(exe.return_value.skeleton[206], sk)

    def test_stale_second_overlay_is_rejected_instead_of_arbitrarily_selected(self):
        with tempfile.TemporaryDirectory() as folder:
            out = Path(folder)
            overlays = out / 'imported-species-models'
            overlays.mkdir()
            for name in ('206-old.MMD', '206-new.MMD'):
                (overlays / name).touch()
            with self.assertRaisesRegex(ValueError, 'ambiguous final overlays'):
                audit_field.load(out, dict(id=206))


class HoverHeight(unittest.TestCase):
    def test_absolute_peak_catches_a_high_hover_despite_a_low_first_tick(self):
        frames = np.array([[[4096, 4096, 4096, 0, 0, 0, 1000, -10, -2000],
                            [4096, 4096, 4096, 0, 0, 0, 0, y, 0]] for y in (-20, -210)])
        rig = Rig([-1, 0], {1: [[0, 0, 0], [0, -100, 0]]}, [], {0: (frames, 0)})
        r = audit_field.hover_heights(rig, 0)
        self.assertEqual(r['frames'], [[30, 130], [220, 320]])
        self.assertTrue(r['high_hover'])

    @unittest.skipUnless(os.environ.get('NATIVE_MODELS_ROOT'), 'set NATIVE_MODELS_ROOT to extracted native disc')
    def test_native_flyers_and_hoverers_pass(self):
        for sid in (7, 21, 24, 25, 28, 29, 37):
            sk = audit_field.mmd.exe().skeleton[sid]
            path, = Path(os.environ['NATIVE_MODELS_ROOT']).glob(
                f'CHDAT/MMD*/{audit_field.mmd.exe().names[sid]}.MMD')
            rig = Rig.from_mmd(path.read_bytes(), sk, sid)
            for slot in audit_field.HOVER_LIMITS:
                with self.subTest(species=sid, slot=slot):
                    self.assertFalse(audit_field.hover_heights(rig, slot)['high_hover'])


if __name__ == '__main__':
    unittest.main()
