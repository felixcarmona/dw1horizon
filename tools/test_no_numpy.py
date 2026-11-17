"""Player-module imports and browser vendoring with no third-party packages."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class PythonOnly(unittest.TestCase):
    def test_player_modules_import_without_site_packages(self):
        # -I -S also hides NumPy installed in the developer's system Python.
        script = '''
import importlib, importlib.util, json, sys
from pathlib import Path
root = Path(sys.argv[1])
sys.path[:0] = [str(root)]
assert importlib.util.find_spec('numpy') is None
assert importlib.util.find_spec('PIL') is None
from tools.derive.steps.overlays import imported_models
from tools.derive.importers import source_context
for name in sorted({r[1] for r in imported_models().OVERLAYS.values()}):
    importlib.import_module(name)
sys.path.insert(0, str(root / 'tools'))
with source_context(root / 'unused-test-sources'):
    for name in ('dcb.model', 'dcb.anim', 'dcb.pose', 'dcb.tim', 'dcb.vram',
                 'dw2.model', 'dw2.gltf', 'dw2.texture', 'dw3.model',
                 'dw3.pose', 'dw3.tim', 'dw3.texture', 'dcb2mmd',
                 'dw2mmd', 'dw3mmd', 'import_batch', 'rigfix', 'tools.models.delta', 'mmd', 'motionstorage'):
        importlib.import_module(name)
# The hand-made babies' builders (their authoring/ scripts are developer-only and never imported by the build).
for name, entry in json.load(open(root / 'content/models/imports/models.json')).items():
    if entry.get('builder'):
        importlib.import_module(entry['builder'])
# Exercise the repaired numeric paths too: an import-only check misses viewer
# imports inside builders and unsupported operations in the local backend.
from tools.derive import arraymath as np
from tools.models.field_animations import antylamon_polish, black_king_numemon, native_hands
for matrix, rhs, want in (([[2., 1.], [1., 3.]], [5., 10.], [1., 3.]),
                          ([[1., 3.], [2., 1.]], [10., 5.], [1., 3.])):
    result = black_king_numemon.solve2(np.array(matrix), np.array(rhs))
    assert max(abs(a - b) for a, b in zip(result, want)) < 1e-12
rotation = antylamon_polish.exp_so3(np.array([0., 0., .5]))
assert abs(antylamon_polish.log_so3(rotation)[2] - .5) < 1e-12
from types import SimpleNamespace
points = np.array([[.1, .1, .1], [2., 2., 2.]])
hand = np.array([[[.1, .1, .1]] * 3])
tetra = np.array([[[0., 0., 0.], [0., 1., 0.], [1., 0., 0.]],
                  [[0., 0., 0.], [1., 0., 0.], [0., 0., 1.]],
                  [[0., 0., 0.], [0., 0., 1.], [0., 1., 0.]],
                  [[1., 0., 0.], [0., 1., 0.], [0., 0., 1.]]])
mesh = SimpleNamespace(world=lambda pose, bones: {1: (points, hand), 2: (None, tetra)},
                       parts={2: [np.arange(4)]})
assert native_hands._Mesh.inside_count(mesh, None, 1, [2]) == 2
assert 'numpy' not in sys.modules
assert not any(n == 'PIL' or n.startswith('PIL.') for n in sys.modules)
'''
        result = subprocess.run([sys.executable, '-I', '-S', '-c', script, os.environ.get("DW_PLAYER_BUNDLE", str(ROOT))],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_direct_field_cli_imports_without_site_packages(self):
        env = dict(os.environ)
        env.pop('PYTHONPATH', None)
        for name in ('gaits.py', 'articulation.py', 'secondary_motion.py', 'weight_shift.py', 'monmon.py', 'war_greymon.py'):
            result = subprocess.run([sys.executable, '-S', str(ROOT / 'tools/models/field_animations' / name), '--help'],
                                    capture_output=True, text=True, env=env)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_vendor_runtime_does_not_need_or_copy_a_wheel(self):
        spec = importlib.util.spec_from_file_location('build_engine_test', ROOT / 'web/enginebuild/build_engine.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as tmp:
            src, dst = Path(tmp) / 'src', Path(tmp) / 'dst'
            src.mkdir()
            (src / 'pyodide-lock.json').write_text(json.dumps(dict(info={'python': '3.14.2'},
                packages={'numpy': {'file_name': 'numpy-not-installed.whl', 'sha256': 'unused'}})))
            for name in ('pyodide.asm.wasm', 'python_stdlib.zip', 'pyodide.asm.mjs'):
                (src / name).write_bytes(b'test runtime fixture')
            (src / 'pyodide.mjs').write_text('import "pyodide.asm.mjs";')
            self.assertEqual(module.vendor_pyodide(str(src), str(dst)), {'python': '3.14.2'})
            self.assertFalse(list(dst.glob('*.whl')))
            self.assertTrue((dst / 'pyodide.esm.js').is_file())


if __name__ == '__main__': unittest.main()
