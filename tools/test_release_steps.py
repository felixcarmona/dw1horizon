"""Release keep-going and resume: failures, dependencies, corruption and verified reuse."""
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from tools.release_steps import Store,Step,run


class RecoveryTests(unittest.TestCase):
    def test_middle_failure_blocks_dependants_and_keeps_independent_work(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);calls=[]
            def action(name,fail=False):
                def invoke():
                    calls.append(name)
                    (root/name).write_text('partial' if fail else 'complete')
                    if fail:raise RuntimeError('middle failed')
                return invoke
            steps=[Step('first',action('first'),{},[root/'first']),
                   Step('middle',action('middle',True),{},[root/'middle'],('first',),('worker','middle')),
                   Step('dependent',action('dependent'),{},[root/'dependent'],('middle',)),
                   Step('independent',action('independent'),{},[root/'independent'],('first',))]
            store=Store(root/'state');result=run(steps,store,3)
            self.assertFalse(result['ok'])
            self.assertEqual(set(calls),{'first','middle','independent'})
            rows={row['name']:row for row in result['steps']}
            self.assertEqual(rows['dependent']['blocked_by'],['middle'])
            self.assertEqual(rows['middle']['command'],['worker','middle'])
            self.assertEqual(rows['middle']['exit'],1)
            self.assertTrue(Path(rows['middle']['log']).exists())
            self.assertEqual(len(json.loads((root/'state/failures.json').read_text())['failures']),2)
            self.assertIn('blocked by middle',(root/'state/failures.txt').read_text())
            calls.clear()
            steps[1].run=action('middle');steps[1].inputs={'fix':'applied'}
            result=run(steps,Store(root/'state'),3)
            self.assertTrue(result['ok'])
            self.assertEqual(set(calls),{'middle','dependent'})
            self.assertEqual({row['name'] for row in result['steps'] if row['status']=='reused'}, {'first','independent'})

    def test_corrupted_output_with_preserved_timestamp_is_rebuilt(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);output=root/'data';calls=[]
            def build():calls.append(1);output.write_bytes(b'right')
            def inputs():return {'source':'unchanged'}
            for attempt in range(3):
                result=run([Step('build',build,inputs,[output])],Store(root/'state'))
                self.assertTrue(result['ok'])
                if attempt==0:
                    before=output.stat();output.write_bytes(b'wrong')
                    __import__('os').utime(output,ns=(before.st_atime_ns,before.st_mtime_ns))
            self.assertEqual(len(calls),2)
            self.assertEqual(output.read_bytes(),b'right')

    def test_value_blob_corruption_and_missing_output_never_reuse(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);calls=[];output=root/'output'
            def build():calls.append(1);output.write_bytes(b'ok');return (3,{7:b'owned bytes'})
            first=Store(root/'state');expected=first.call('phase',build,{},[output])
            self.assertEqual(Store(root/'state').call('phase',build,{},[output]),expected)
            blob=next((root/'state/blobs').iterdir());blob.write_bytes(b'corrupt')
            self.assertEqual(Store(root/'state').call('phase',build,{},[output]),expected)
            output.unlink()
            self.assertEqual(Store(root/'state').call('phase',build,{},[output]),expected)
            self.assertEqual(len(calls),3)

    def test_changed_source_bytes_modes_and_directory_inventory_change_key(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);source=root/'source';source.mkdir();(source/'input').write_bytes(b'one')
            calls=[];output=root/'output'
            def build():calls.append(1);output.write_bytes(b'data')
            def round():
                store=Store(root/'state')
                return store.call('phase',build,lambda:store.hashes.tree([source]),[output])
            round();round();(source/'input').write_bytes(b'two');round()
            (source/'input').chmod(0o600);round();(source/'empty').mkdir();round()
            self.assertEqual(len(calls),4)

    def test_order_only_barrier_runs_after_failures_but_required_step_is_blocked(self):
        with tempfile.TemporaryDirectory() as td:
            seen=[]
            def fail():seen.append('failed');raise RuntimeError('expected')
            result=run([Step('bad',fail,{}),Step('inspect',lambda:seen.append('inspect'),{},after=('bad',)),
                        Step('complete',lambda:seen.append('complete'),{},deps=('bad','inspect'))],Store(td))
            self.assertEqual(seen,['failed','inspect'])
            self.assertFalse(result['ok'])

    def test_make_release_collects_all_independent_worker_results(self):
        from unittest.mock import patch
        sys.path.insert(0,str(Path(__file__).resolve().parent/'patcher'))
        import dwpatch
        with tempfile.TemporaryDirectory() as td:
            store=Store(td);seen=[]
            def bad():raise RuntimeError('base failed')
            tasks={'bad':lambda:dwpatch.recovery_step('base/bad',bad,{}),
                   'good':lambda:dwpatch.recovery_step('base/good',lambda:seen.append('good'),{})}
            with patch.object(dwpatch,'RELEASE_STATE',store),patch.object(dwpatch,'RELEASE_COMMON',{}):
                with self.assertRaisesRegex(dwpatch.PatchError,'base failed'):
                    dwpatch.run_release_tasks(tasks,2)
            self.assertEqual(seen,['good'])
            self.assertEqual(store.rows['base/good']['status'],'ok')
            self.assertEqual(store.rows['base/bad']['status'],'failed')

    def test_recovery_plan_has_explicit_gate_and_artifact_dependencies(self):
        from unittest.mock import patch
        import release
        from tools import release_recovery
        captured=[]
        def plan_only(plan,store,workers):captured.extend(plan);return store.report()
        with tempfile.TemporaryDirectory() as td:
            folder=Path(td);card=folder/'fixture.mcd';card.write_bytes(b'fixture')
            info=dict(version='0.0.0-dev.1+test',commit='a'*40,date='2026-11-06',tag=None)
            with patch.object(release,'identity',return_value=info),patch.object(release_recovery.steps,'run',side_effect=plan_only):
                self.assertEqual(release.main(['--keep-going','--save-check-emu','--ending-card',str(card),'--out',str(folder/'cut')]),0)
            by_name={step.name:step for step in captured}
            self.assertNotIn('selftest',by_name['package'].deps)
            self.assertIn('package',by_name['engine'].deps)
            self.assertIn('engine',by_name['browser'].deps)
            self.assertEqual(set(by_name['archive'].deps),{'package','engine'})
            self.assertIn('selftest',by_name['checkout'].after)
            self.assertIn('browser',by_name['complete'].deps)
            self.assertIn('ending',by_name['complete'].deps)
            captured.clear()
            with patch.object(release,'identity',return_value=info),patch.object(release_recovery.steps,'run',side_effect=plan_only):
                self.assertEqual(release.main(['--resume','--out',str(folder/'cut')]),0)
            self.assertIn('ending',{step.name for step in captured})
            self.assertIn('published-save',{step.name for step in captured})
            with patch.object(release,'identity',return_value=info):
                with self.assertRaisesRegex(ValueError,'required gate'):
                    release.main(['--resume','--skip-browser','--out',str(folder/'cut')])

    def test_blocked_attempt_preserves_an_earlier_successful_completion(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);calls=[]
            def parent():
                if (root/'fail').exists():raise RuntimeError('temporary prerequisite failure')
                (root/'parent').write_bytes(b'stable')
            def child():calls.append(1);(root/'child').write_bytes(b'stable')
            def plan(store):
                return [Step('parent',parent,lambda:{'fail':(root/'fail').exists()},[root/'parent']),
                        Step('child',child,lambda:store.hashes.tree([root/'parent']),[root/'child'],('parent',))]
            store=Store(root/'state');self.assertTrue(run(plan(store),store)['ok'])
            (root/'fail').touch();store=Store(root/'state');self.assertFalse(run(plan(store),store)['ok'])
            (root/'fail').unlink();store=Store(root/'state');self.assertTrue(run(plan(store),store)['ok'])
            self.assertEqual(len(calls),1)

    def test_cycles_and_unknown_dependencies_fail_before_work(self):
        with tempfile.TemporaryDirectory() as td:
            store=Store(td)
            with self.assertRaisesRegex(ValueError,'cycle'):
                run([Step('a',lambda:None,{},deps=('b',)),Step('b',lambda:None,{},deps=('a',))],store)
            with self.assertRaisesRegex(ValueError,'unknown'):
                run([Step('a',lambda:None,{},deps=('missing',))],store)


if __name__=='__main__':unittest.main()
