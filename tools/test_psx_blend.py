"""PSX material rules, import blend state and native ABE review baseline."""
from pathlib import Path
import sys
import unittest
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'tools')]
from tools.models.psx_blend import composite
from tools.models import audit_textures as audit
from tools.test_audit_textures import face, model
import dw3mmd


class Blending(unittest.TestCase):
    def test_abe_and_stp_are_both_required(self):
        bg = np.array([[20, 16, 12]] * 4)
        words = np.array([0, 0x8000, 0x001f, 0x801f])
        self.assertEqual(composite(bg, words, True, 0).tolist(),
                         [[20, 16, 12], [10, 8, 6], [31, 0, 0], [25, 8, 6]])
        self.assertEqual(composite(bg, words, False, 0).tolist(),
                         [[20, 16, 12], [0, 0, 0], [31, 0, 0], [31, 0, 0]])

    def test_all_four_blend_modes_and_saturation(self):
        word = 0x8000 | 24 | (8 << 5) | (16 << 10)
        expected = [[22, 12, 14], [31, 24, 28], [0, 8, 0], [26, 18, 16]]
        for abr, rgb in enumerate(expected):
            self.assertEqual(composite([20, 16, 12], word, True, abr).tolist(), rgb)

    def test_additive_glow_does_not_darken_background(self):
        self.assertEqual(composite([20, 16, 12], 0x8000, True, 1).tolist(), [20, 16, 12])

    def test_state_zero_is_opaque_and_other_states_select_abr(self):
        for state, expected in enumerate([(False, 0), (True, 0), (True, 1), (True, 2), (True, 3)]):
            self.assertEqual(dw3mmd.blend_state(state), expected)

    def test_quad_pairing_preserves_blend_boundary(self):
        p = dict(verts=[0, 1, 2], norms=None, uvs=[(0, 0), (1, 0), (0, 1)], row=0, semi=True, abr=0)
        q = dict(verts=[1, 3, 2], norms=None, uvs=[(1, 0), (1, 1), (0, 1)], row=0, semi=True, abr=1)
        verts = [(0, 0, 0), (1, 0, 0), (0, 1, 0), (1, 1, 0)]
        bone = dict(prims=[p, q], verts=verts)
        self.assertEqual(dw3mmd.merge_quads(bone), 0)
        q['abr'] = 0
        self.assertEqual(dw3mmd.merge_quads(bone), 1)


class ReviewThreshold(unittest.TestCase):
    def test_share_counts_flags_independently_of_palette_stp(self):
        opaque = face([(0, 0), (10, 0), (0, 10)], 0)
        semi = face([(0, 0), (10, 0), (0, 10)], 0, mode=0x36)
        self.assertEqual(audit.transparency(model(opaque, semi)), dict(primitives=2, abe=1, share=.5))
        self.assertEqual(audit.transparency(model()), dict(primitives=0, abe=0, share=0))

    @unittest.skipUnless((ROOT / 'extracted/CHDAT/ALLTIM.TIM').exists(), 'needs extracted/')
    def test_all_originals_pass_abe_review_baseline(self):
        for sid, name, data, tex in audit.original_models():
            tmd, _ = audit.load_pair(data, tex)
            if sid not in audit.NATIVE_TRANSLUCENT:
                self.assertLessEqual(audit.transparency(tmd)['share'], audit.ABE_SHARE, (sid, name))


if __name__ == '__main__':
    unittest.main()
