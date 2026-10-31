"""Final overlays must be parsed with their generated skeleton, never the source rig."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools.models import audit_field


class FinalSkeleton(unittest.TestCase):
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


if __name__ == '__main__':
    unittest.main()
