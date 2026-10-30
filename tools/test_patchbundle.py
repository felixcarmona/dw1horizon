#!/usr/bin/env python3
"""Check that a recorded release bundle can import its steps in a fresh Python."""
import os
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.patcher import dwpatch as D


class BundleStartup(unittest.TestCase):
    def test_player_replay_drops_inherited_developer_cache_flags(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            folder = root / 'tools/derive'
            (folder / 'recipes').mkdir(parents=True)
            (folder / 'recipes/everything.json').write_text(json.dumps({'environment': {'NAME': 'test'}}))
            (folder / '__main__.py').write_text(
                'import json,os,pathlib\n'
                'p=pathlib.Path("build/test/derived");p.mkdir(parents=True)\n'
                '(p/"manifest.json").write_text(json.dumps(dict(os.environ)))\n')
            flags = dict(DW_BUILD_CACHE='unchecked', DW_CACHE_DIR='unchecked', DW_CLEAN_NATIVE='1', PYTHONPATH='')
            with patch.dict(os.environ, flags), patch.object(D, 'say'):
                manifest, _ = D.derive_run(str(root), 'everything', 'unused', jobs=1)
            self.assertFalse(set(manifest) & (set(flags) - {'PYTHONPATH'}))

    def test_retired_untracked_inventory_cannot_supply_bundle_inputs(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            repo, work, out = (tmp / n for n in ('repo', 'work', 'out'))
            recipe = 'tools/derive/recipes/everything.json'
            (repo / recipe).parent.mkdir(parents=True)
            (repo / recipe).write_text('{"untracked_inputs":{"build_folders":["private-models"]}}')
            (repo / 'tools/languages.py').write_text('')
            private = repo / 'build/private-models/input'
            private.parent.mkdir(parents=True)
            private.write_bytes(b'not a published build input')
            facts = tmp / 'facts.json'
            facts.write_text('{}')

            def build(root, *args, **kwargs):
                self.assertFalse((Path(root) / 'build/private-models/input').exists())
                return {'steps': {}}, str(work)

            git = [SimpleNamespace(stdout=recipe + '\ntools/languages.py\n'), SimpleNamespace(stdout='')]
            with patch.object(D, 'REPO', str(repo)), \
                 patch.object(D.subprocess, 'run', side_effect=git), \
                 patch.object(D, 'needs_usa_paths', return_value=set()), \
                 patch.object(D, 'derive_run', side_effect=build), \
                 patch.object(D, 'derive_files', return_value={}), patch.object(D, 'say'):
                D.make_bundle_derive(SimpleNamespace(files={}, read=None), str(work),
                                     str(out), 'everything', str(facts))
            self.assertFalse((out / 'bundle/build/private-models/input').exists())

    def test_eager_dependencies_survive_an_empty_record(self):
        # Step modules are imported before recording begins. None of their eager
        # dependencies appear in the recorded opens, even though players need them.
        (ROOT / 'build').mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='patchbundle-', dir=ROOT / 'build') as tmp:
            tmp = Path(tmp)
            repo, work, out = (tmp / n for n in ('repo', 'work', 'out'))
            tracked = [p.relative_to(ROOT).as_posix()
                       for p in (ROOT / 'tools/derive').rglob('*.py')]
            tracked += ['tools/languages.py', 'tools/derive/recipes/everything.json']
            for name in tracked:
                target = repo / name
                target.parent.mkdir(parents=True, exist_ok=True)
                if name.endswith('everything.json'):
                    target.write_text('{}')
                else:
                    shutil.copyfile(ROOT / name, target)
            facts = tmp / 'facts.json'
            facts.write_text('{}')
            git = [SimpleNamespace(stdout='\n'.join(tracked)), SimpleNamespace(stdout='')]
            with patch.object(D, 'REPO', str(repo)), \
                 patch.object(D.subprocess, 'run', side_effect=git), \
                 patch.object(D, 'needs_usa_paths', return_value=set()), \
                 patch.object(D, 'derive_run', return_value=({'steps': {}}, str(work))), \
                 patch.object(D, 'derive_files', return_value={}), \
                 patch.object(D, 'say'):
                D.make_bundle_derive(SimpleNamespace(files={}, read=None), str(work),
                                     str(out), 'everything', str(facts))
            env = dict(os.environ)
            env.pop('PYTHONPATH', None)
            result = subprocess.run([sys.executable, '-S', '-c',
                                     'from tools.derive.steps import owned; owned()'],
                                    cwd=out / 'bundle', env=env, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == '__main__':
    unittest.main()
