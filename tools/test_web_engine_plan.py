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
    def test_declared_order_groups_remain_edges_in_the_browser_graph(self):
        def row(name, part, group=None):
            return dict(name=name, step='story', part=part, index=0, argv=[], seconds=1,
                        existed=[], lists={}, absent=[], writes={}, removes=[], order_group=group,
                        record_snapshot=bool(group))
        rows=[row('prepare','prepare'),row('list','units'),row('first','unit','maps'),
              row('independent','unit'),row('last','unit','maps'),row('finish','finish')]
        record=dict(tree='{ROOT}',jobs=rows)
        jobs,warnings=engine.plan_jobs([record],set())
        self.assertEqual(warnings,[])
        scheduled=engine.schedule_deps(jobs,['story'],{'story':[]})
        by_name={job['name']:job for job in scheduled}
        self.assertIn(by_name['first']['id'],by_name['last']['deps'])
        self.assertNotIn(by_name['first']['id'],by_name['independent']['deps'])
        other=dict(record,jobs=[dict(j) for j in rows])
        other['jobs'][2]['order_group']=None
        with self.assertRaisesRegex(SystemExit,'ordering policies'):
            engine.plan_jobs([record,other],set())

    def test_independent_start_units_need_no_sequence_but_keep_the_recorded_order(self):
        def row(name, part, group=None, independent=False):
            return dict(name=name, step='story', part=part, index=0, argv=[], seconds=1,
                        existed=[], lists={}, absent=[], writes={}, removes=[], order_group=group,
                        record_snapshot=False, independent_start=independent)
        rows = [row('prepare', 'prepare'), row('list', 'units')]
        rows += [row(f'pass {i}', 'unit', 'maps', True) for i in range(3)]
        rows += [row('stateful', 'unit', 'locks'), row('stateful 2', 'unit', 'locks'), row('finish', 'finish')]
        jobs, warnings = engine.plan_jobs([dict(tree='{ROOT}', jobs=rows)], set())
        self.assertEqual(warnings, [])
        by_name = {j['name']: j for j in engine.schedule_deps(jobs, ['story'], {'story': []})}
        prep = by_name['prepare']['id']
        for i in range(3):
            self.assertEqual(by_name[f'pass {i}']['deps'], [prep])
            self.assertIn(by_name[f'pass {i}']['id'], by_name['finish']['deps'])
        # a group that is not independent keeps its sequence
        self.assertIn(by_name['stateful']['id'], by_name['stateful 2']['deps'])
        # the policy is part of what two records must agree on
        other = dict(tree='{ROOT}', jobs=[dict(j) for j in rows])
        other['jobs'][2]['independent_start'] = False
        with self.assertRaisesRegex(SystemExit, 'ordering policies'):
            engine.plan_jobs([dict(tree='{ROOT}', jobs=rows), other], set())

    def test_cold_writer_can_regenerate_authored_executable_text(self):
        root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as work:
            tree = Path(work)
            shutil.copytree(root / 'tools', tree / 'tools', copy_function=os.link,
                            ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
            data = {p.relative_to(root).as_posix() for p in (root / 'text').glob('*/names.json')}
            data.add('docs/data/map_files.csv')
            data.update(p.relative_to(root).as_posix() for p in (root / 'docs/data').glob('*.csv'))
            data.add('text/ours/pages.json')
            data.add('content/tables/story-screens.json')
            data.update(p.relative_to(root).as_posix() for p in (root / 'content/screens').glob('*.json'))
            # Cold text generation imports the backend's owned encounter defaults.
            for folder in ('content/battle', 'content/species', 'content/techniques', 'content/tables', 'content/items'):
                data.update(p.relative_to(root).as_posix() for p in (root / folder).glob('*.json'))
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

    def test_record_cache_is_verified_in_separate_processes(self):
        import hashlib
        import json
        with tempfile.TemporaryDirectory() as td:
            for key in ('us', 'jp1'):
                raw = json.dumps({'tree': key, 'jobs': []}).encode()
                record = Path(td) / ('record-' + key + '.json')
                record.write_bytes(raw)
                Path(str(record) + '.sha256').write_text(hashlib.sha256(raw).hexdigest())
            code = (
                "from concurrent.futures import ProcessPoolExecutor; import sys; "
                "sys.path.insert(0,sys.argv[1]); import build_engine as e; "
                "args=[('unused',k+'=unused','unused',[],sys.argv[2]) for k in ('us','jp1')]; "
                "pool=ProcessPoolExecutor(2); results=list(pool.map(e.record_base,args)); pool.shutdown(); "
                "assert [r['tree'] for r in results]==['us','jp1']")
            subprocess.run([sys.executable, '-c', code, str(Path(engine.__file__).parent), td], check=True)

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
