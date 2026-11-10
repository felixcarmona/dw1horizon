"""animstudio loads a field overlay bound to another rig through its NAME-report.json generated skeleton."""
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import animstudio
import mmd
from tools.models.field_animations import native_binding as binding


class OverlayWithGeneratedSkeleton(unittest.TestCase):
    def test_model_uses_the_skeleton_of_the_report(self):
        source = Path(os.environ.get('BINDING_MODELS', 'build/imported-model-edit/edit'))
        sid, recipe = next(iter(json.loads(binding.MANIFEST.read_text()).items()))
        files = list(source.glob(f'{sid}-*.MMD')) or list(source.glob(f'{sid}.MMD'))
        tims = list(source.glob(f'{sid}-*.TIM')) or list(source.glob(f'{sid}.TIM'))
        if not files or not tims or not (Path(mmd.EXTRACTED) / recipe['model']).exists():
            raise unittest.SkipTest('needs the imported model (tools/models/edit.py get) and the DW1 extraction')
        record = json.loads(next(Path('content/species').glob(f'{sid}-*.json')).read_text())
        data, proof = binding.bind(files[0].read_bytes(), record['model']['skeleton'], recipe)
        e, t = mmd.exe(), int(sid)
        saved = (list(e.skeleton[t]), e.bone_count[t])
        try:
            with tempfile.TemporaryDirectory() as tmp:
                path = Path(tmp) / 'overlay.MMD'
                path.write_bytes(data)
                path.with_name('overlay-report.json').write_text(json.dumps(proof))
                e.skeleton[t], e.bone_count[t] = [(-1, -1)] * saved[1], saved[1]      # the executable's own rig
                model = animstudio.Model(f'{path}:{t}:{tims[0]}', 0)
            self.assertEqual(model.nb, len(proof['generated_skeleton']))
            self.assertEqual(model.skel, [tuple(b) for b in proof['generated_skeleton']])
            self.assertTrue(len(model.verts))
        finally:
            e.skeleton[t], e.bone_count[t] = saved


if __name__ == '__main__':
    unittest.main()
