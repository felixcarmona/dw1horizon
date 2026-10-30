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
import importlib, importlib.util, sys
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
                 'dw2mmd', 'dw3mmd', 'import_batch', 'rigfix', 'tools.models.delta'):
        importlib.import_module(name)
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
