#!/usr/bin/env python3
"""Browser jobs must work when assigned to separate, cold workers."""
import importlib.util
from pathlib import Path
import unittest
import os
import shutil
import subprocess
import sys
import tempfile

spec = importlib.util.spec_from_file_location(
    'build_engine', Path(__file__).resolve().parents[1] / 'web/enginebuild/build_engine.py')
engine = importlib.util.module_from_spec(spec)
spec.loader.exec_module(engine)


class PlanTests(unittest.TestCase):
    def test_cold_writer_can_regenerate_authored_executable_text(self):
        root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as work:
            tree = Path(work)
            shutil.copytree(root / 'tools', tree / 'tools', copy_function=os.link,
                            ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
            data = {p.relative_to(root).as_posix() for p in (root / 'text').glob('*/names.json')}
            data.add('docs/data/map_files.csv')
            data.add('text/ours/pages.json')
            for name in engine.writer_inputs(data, set()):
                target = tree / name
                target.parent.mkdir(parents=True, exist_ok=True)
                os.link(root / name, target)
            subprocess.run([sys.executable, '-I', '-B', '-c',
                "import sys; from pathlib import Path; root=Path(sys.argv[1]); "
                "sys.path[:0]=[str(root/'tools/patcher'),str(root/'tools'),str(root)]; "
                "import fontcopy; data=fontcopy.semantic_table('text', "
                "['en','btl.BTL_STR_SHOUT_DEFENSE',64],str(root)); "
                "assert len(data)==64 and data.strip(bytes(1))", str(tree)], check=True,
                cwd=tree)

    def test_recipe_folder_and_player_source_inputs_are_consistent(self):
        import json
        root = Path(__file__).resolve().parents[1]
        recipe = json.loads((root / 'tools/derive/recipes/everything.json').read_text())
        out = 'build/' + recipe['environment']['NAME']
        self.assertEqual(engine.MANIFEST, out + '/derived/manifest.json')
        source = out + '/source-games/dcb/disc/SYSTEM.CNF'
        records = [dict(tree='/record', jobs=[dict(name='imports first', step='imports', part='unit',
                   index=0, argv=[], seconds=1, existed=[source, engine.MANIFEST], lists={}, absent=[],
                   writes={}, removes=[])])]
        jobs, warnings = engine.plan_jobs(records, set())
        self.assertEqual(warnings, [])
        self.assertEqual(set(jobs[0]['tree']), {source, engine.MANIFEST})
        self.assertEqual(jobs[0]['bundle'], [])

    def test_siblings_receive_cached_static_inputs_but_keep_their_tree_inputs(self):
        index = 'content/localized/signs/delta/index.json'

        def job(name, step, inputs):
            return dict(name=name, step=step, part='unit', index=0, argv=[], seconds=1,
                        existed=inputs, lists={}, absent=[], writes={}, removes=[])

        records = [dict(tree='/record', jobs=[
            job('signs extended', 'signs', [index, 'extracted/extended.MAP']),
            # Native Python already cached index.json; a fresh worker has not.
            job('signs base', 'signs', ['extracted/base.MAP']),
            job('other unit', 'other', ['extracted/other.MAP']),
        ])]
        jobs, warnings = engine.plan_jobs(records, {index})
        self.assertEqual(warnings, [])
        self.assertEqual(jobs[0]['bundle'], [index])
        self.assertEqual(jobs[1]['bundle'], [index])
        self.assertEqual(jobs[1]['tree'], ['extracted/base.MAP'])
        self.assertEqual(jobs[1]['deps'], [])
        self.assertEqual(jobs[2]['bundle'], [])


if __name__ == '__main__':
    unittest.main()
