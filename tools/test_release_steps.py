"""Release keep-going and resume: failures, dependencies, corruption and verified reuse."""
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
sys.path.insert(0,str(Path(__file__).resolve().parent/'patcher'))
from tools.release_steps import Store,Step,run


class RecoveryTests(unittest.TestCase):
    def test_native_runtime_keys_the_immutable_compiler_image(self):
        from unittest.mock import patch
        from tools import release_recovery as recovery
        values=['["python",{}]','sha256:first','["python",{}]','sha256:changed']
        with patch.object(recovery.subprocess,'check_output',side_effect=values) as command:
            first=recovery.native_runtime();second=recovery.native_runtime()
        self.assertEqual(first['python'],second['python'])
        self.assertNotEqual(first['toolchain'],second['toolchain'])
        self.assertEqual(command.call_args_list[1].args[0],
                         ['docker','image','inspect','--format','{{.Id}}','dw-build'])
        with patch.object(recovery.subprocess,'check_output',side_effect=['["python",{}]','']):
            with self.assertRaisesRegex(RuntimeError,'toolchain image'):
                recovery.native_runtime()

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

    def test_native_generation_does_not_invalidate_prepared_sources(self):
        import subprocess
        from unittest.mock import patch
        from tools import release_recovery as recovery
        class Commands:
            def cmd(self,argv):
                subprocess.run(list(map(str,argv)),check=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);seed=root/'seed';seed.mkdir();runner=Commands()
            runner.cmd(['git','init',seed])
            for relative,data in {'src/main/main.c':'int fixture;\n','Makefile':'all:\n\ttrue\n',
                                  '.gitignore':'/asm/\n/build/\n/external/\n/src/main/generated.h\n'}.items():
                path=seed/relative;path.parent.mkdir(parents=True,exist_ok=True);path.write_text(data)
            runner.cmd(['git','-C',seed,'add','src/main/main.c','Makefile','.gitignore'])
            author=recovery.release.git('log','-1','--format=%an%n%ae').splitlines()
            runner.cmd(['git','-C',seed,'-c','user.name='+author[0],'-c','user.email='+author[1],
                        'commit','-m','Seed recovery fixture'])
            pin=recovery.release.git('rev-parse','HEAD',cwd=seed)
            for relative in ('asm','build/us/psx/generated','external/psyq_headers'):
                folder=seed/relative;folder.mkdir(parents=True);(folder/'fixture').write_text('source\n')
            context={'seed':str(seed),'pin':pin};prepared=root/'prepared';native=root/'native';calls=[]
            def prepare():
                calls.append('prepare')
                with patch('tools.patch_series.paths',return_value=[]):recovery.prepare_decomp(context,runner,prepared)
                return recovery.release.git('rev-parse','HEAD',cwd=prepared)
            def build():
                calls.append('native');revision=recovery.release.git('rev-parse','HEAD',cwd=prepared)
                recovery.prepare_decomp(context,runner,native,revision=revision,source=prepared)
                (native/'src/main/generated.h').write_text('generated\n');(native/'asm/fixture').write_text('regenerated\n')
            for attempt in range(3):
                store=Store(root/'state');store.call('prepare',prepare,{'pin':pin},[prepared])
                store.call('native',build,lambda:store.hashes.tree([prepared]),[native])
                self.assertEqual((prepared/'asm/fixture').read_text(),'source\n')
                if attempt==1:(native/'asm/fixture').write_text('corrupt\n')
            self.assertEqual(calls,['prepare','native','native'])

    def test_selftest_uses_the_cut_c_tree(self):
        from unittest.mock import patch
        from tools import release_recovery as recovery
        calls=[]
        class Commands:
            def __init__(self,*args):pass
            def cmd(self,argv,env=None):calls.append((argv,env))
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);context=dict(out=str(root/'cut'),build=str(root/'native'),w=str(root/'decomp'),
                                      name='fixture',bases={},sources={},options={'jobs':1},frozen_identity={'version':'0.0.0'})
            with patch.object(recovery,'Commands',Commands):recovery.run_step('selftest',context)
            self.assertEqual(calls[0][1]['DW_SELFTEST_DECOMP'],context['w'])

    def test_package_keys_cover_discs_native_auxiliaries_and_runtime(self):
        from types import SimpleNamespace
        from unittest.mock import patch
        sys.path.insert(0,str(Path(__file__).resolve().parent/'patcher'))
        import dwpatch
        from tools.release_steps import encoded
        import hashlib
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);native=root/'native';runtime=root/'tools';runtime.mkdir();(runtime/'producer.py').write_text('producer')
            for folder in ('derived','exe','exe-zh-hans'):(native/folder).mkdir(parents=True)
            files={str(Path('tools')/'producer.py'):b'producer','original.bin':b'original','eu.bin':b'europe','source.bin':b'source','native.bin':b'target',
                   'docs/proposals/technique-coherence.csv':b'reviewed slot records',
                   'native/derived/exe-facts.json':b'{}','native/exe/SLUS.elf.map':b'map',
                   'native/exe/MAIN.BIN':b'program','native/exe-zh-hans/MENU.BIN':b'overlay',
                   'native/chinese-font':b'font','override.map':b'override'}
            for relative,data in files.items():
                path=root/relative;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(data)
            manifest=native/'derived/manifest.json';manifest.write_text(json.dumps({'plan':{'CHINESE_RESOURCES':[{'source':'chinese-font'}]}}))
            a=SimpleNamespace(variant=['everything='+str(root/'native.bin')+',map='+str(root/'override.map')],
                              recipe='everything',original=str(root/'original.bin'),base=['eu='+str(root/'eu.bin')],
                              source_disc=['dcb='+str(root/'source.bin')])
            store=Store(root/'state')
            with patch.object(dwpatch,'RELEASE_STATE',store),patch.object(dwpatch,'REPO',str(root)), \
                 patch.object(dwpatch,'DERIVE_TREES',('tools',)),patch('tools.derive.cache.runtime_sources',return_value='runtime-a') as libraries:
                def fingerprint():return hashlib.sha256(encoded(dwpatch.recovery_inputs(a,str(root/'native.bin')))).hexdigest()
                original=fingerprint()
                for relative in files:
                    path=root/relative;data=path.read_bytes();path.write_bytes(data+b'changed')
                    self.assertNotEqual(original,fingerprint(),relative);path.write_bytes(data)
                data=manifest.read_text();manifest.write_text(json.dumps({'plan':{'CHINESE_RESOURCES':[{'source':'chinese-font'}]},'files':{'NEW':{}}}))
                self.assertNotEqual(original,fingerprint(),'manifest');manifest.write_text(data)
                timed=json.loads(data);timed['steps']={'story':{'seconds':999}};manifest.write_text(json.dumps(timed))
                self.assertEqual(original,fingerprint(),'observed timings are not encoder inputs');manifest.write_text(data)
                extra=native/'exe/extra';extra.write_text('new file');self.assertNotEqual(original,fingerprint(),'inventory');extra.unlink()
                libraries.return_value='runtime-b';self.assertNotEqual(original,fingerprint(),'runtime libraries')

    def test_selftest_reports_each_failure_and_continues(self):
        import shutil
        import subprocess
        from tools import release_recovery as recovery
        if not shutil.which('bash'):self.skipTest('requires bash')
        text=(recovery.ROOT/'tools/selftest.sh').read_text()
        def function(name):
            start=text.index(name+'() {');return text[start:text.index('\n}',start)+2]
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);out=root/'logs';out.mkdir();report=root/'steps.jsonl'
            script='set -u\nPY=$1; OUT=$2; REPORT=$3; pass=0; fail=0; skip=0; report_errors=0\n'
            script+='\n'.join(function(name) for name in ('report_step','skip','run'))
            script+='\nrun first "$PY" -c \'print("first")\'\nrun middle "$PY" -c \'import sys;print("middle failed");sys.exit(7)\'\nskip missing "missing fixture"\nrun last "$PY" -c \'print("last")\'\n'
            result=subprocess.run(['bash','-c',script,'selftest',sys.executable,str(out),str(report)],capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)
            rows=[json.loads(line) for line in report.read_text().splitlines()]
            self.assertEqual([row['name'] for row in rows],['first','middle','missing','last'])
            self.assertEqual([row['status'] for row in rows],['ok','failed','blocked','ok'])
            self.assertEqual(rows[1]['exit'],7)
            self.assertEqual(rows[1]['command'][:2],[sys.executable,'-c'])
            self.assertIn('middle failed',Path(rows[1]['log']).read_text())
            self.assertEqual(rows[2]['blocked_by'],['missing fixture'])

    def test_driver_consolidates_package_and_selftest_failure_lists(self):
        from unittest.mock import patch
        import release
        from tools import release_recovery as recovery
        info=dict(version='0.0.0-dev.1+test',commit='a'*40,date='2026-11-06',tag=None)
        def failed_plan(plan,store,workers):
            out=store.root.parents[1];(out/'logs').mkdir();(out/'package-state').mkdir()
            def row(name,code=1):
                log=out/'logs'/(name.replace('/','-')+'.log');log.write_text(name+' failed')
                return dict(name=name,status='failed',exit=code,command=['worker',name],log=str(log),seconds=0.1)
            package=row('package');selftest=row('selftest');base=row('base/everything/eu',9);check=row('case-one',7)
            (out/'package-state/failures.json').write_text(json.dumps({'failures':[base]}))
            (out/'selftest-steps.jsonl').write_text(json.dumps(check)+'\n'+json.dumps(dict(name='case-good',status='ok'))+'\n')
            return dict(ok=False,steps=[package,selftest],failures=[package,selftest])
        with tempfile.TemporaryDirectory() as td:
            out=Path(td)/'cut'
            with patch.object(release,'identity',return_value=info),patch.object(recovery.steps,'run',side_effect=failed_plan):
                self.assertEqual(release.main(['--keep-going','--out',str(out)]),1)
            report=json.loads((out/'failures.json').read_text())
            rows={row['name']:row for row in report['failures']}
            self.assertEqual(set(rows),{'package','selftest','package/base/everything/eu','selftest/case-one'})
            self.assertEqual(rows['selftest/case-one']['exit'],7)
            self.assertIn('package/base/everything/eu',(out/'failures.txt').read_text())
            self.assertTrue((out/'rounds/round-001-logs/selftest-case-one.log').exists())

    def test_damaged_child_report_retains_other_failures(self):
        from tools import release_recovery as recovery
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/'steps.jsonl'
            path.write_text(json.dumps({'name':'first','status':'failed','exit':7})+'\npartial json\n'+
                            json.dumps({'name':'last','status':'failed','exit':9})+'\n')
            result={'ok':True,'failures':[]}
            rows=recovery.child_failure_rows(path,'selftest',result,lines=True)
            self.assertEqual([row['name'] for row in rows],['first','last'])
            self.assertFalse(result['ok'])
            self.assertEqual(result['failures'][0]['name'],'selftest/report-line-2')

    def test_source_checkpoint_ignores_program_and_timing_but_keys_asset_inputs(self):
        from unittest.mock import patch
        import dwpatch
        common=dict(recipe='everything',runtime={'producer':'code'},python='runtime',environment={},sources=[['dcb','disc']],
                    bases=[['us','usa'],['eu','europe']],target='program-a',native={'program':'side-file'},manifest={'plan':{}})
        with patch.object(dwpatch,'RELEASE_COMMON',common):
            initial=dwpatch.recovery_common('source-bundle')
            common['target']='program-b';common['native']={'program':'changed-side-file'}
            common['manifest']={'plan':{},'timings':99}
            self.assertEqual(initial,dwpatch.recovery_common('source-bundle'))
            common['sources']=[['dcb','changed']]
            self.assertNotEqual(initial,dwpatch.recovery_common('source-bundle'))
            self.assertEqual(dwpatch.recovery_common('encode/everything')['target'],'program-b')

    def test_native_version_override_is_absent_from_asset_environment(self):
        from tools import release_recovery as recovery
        context=dict(w='private-c-tree',name='fixture',build='private-native',options={'jobs':1},frozen_identity={'version':'0.0.0'})
        self.assertNotIn('MOD_VERSION',recovery.environment(context))

    def test_failed_regional_source_keeps_other_source_outputs_running(self):
        from types import SimpleNamespace
        from unittest.mock import patch
        import dwpatch
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);work=root/'work';work.mkdir();store=Store(root/'state')
            image=root/'variant.bin';image.write_bytes(b'variant');spec='dw2003='+str(image)
            a=SimpleNamespace(source_variant=[spec],source_disc=['dw2003=reference'],variant_jobs=2,base_jobs=2,
                              worker_memory_mib=6144,keep_outputs=str(root/'outputs'))
            base_paths={key:str(root/(key+'.bin')) for key in ('us','eu','jp1')}
            holes=[{'id':0,'file':'model'}];baseline={key:{0:b'base'} for key in base_paths};made=[]
            def checkpoint(name,function,values,outputs=()):return store.call(name,function,{})
            def derive(*args):
                key=args[-2]
                def build():
                    if key=='eu':raise RuntimeError('regional source failed')
                    return key,{0:b'variant'}
                return store.call('source-derive/dw3-us/'+key,build,{})
            def write(payload,disc,data,path,pin):
                Path(path).write_bytes(b'image');made.append(disc.key);return 'pin-'+disc.key,5
            with patch.object(dwpatch,'RELEASE_STATE',store),patch.object(dwpatch,'RELEASE_COMMON',{}), \
                 patch.object(dwpatch,'recovery_step',side_effect=checkpoint),patch.object(dwpatch,'source_variant_derive',side_effect=derive), \
                 patch.object(dwpatch,'variant_of_image',return_value=('dw3-us','boot')),patch.object(dwpatch,'regional_derive',return_value=True), \
                 patch.object(dwpatch,'BaseDisc',side_effect=lambda key,*args,**kwargs:SimpleNamespace(key=key)), \
                 patch.object(dwpatch,'build_disc3',side_effect=write):
                with self.assertRaisesRegex(dwpatch.PatchError,'source variant derivations failed'):
                    dwpatch.record_source_variants(a,{'extract':[]},str(root/'package'),str(work),'everything',
                        {'recipe':'everything'},holes,baseline,base_paths,{}, {},{},prepared={spec:('us',{0:b'variant'})})
            self.assertEqual(set(made),{'us','jp1'})
            self.assertEqual(store.rows['source-derive/dw3-us/eu']['status'],'failed')
            self.assertEqual(store.rows['source-output/dw3-us/eu']['blocked_by'],['source-derive/dw3-us/eu'])
            self.assertEqual(store.rows['source-output/dw3-us/us']['status'],'ok')
            self.assertEqual(store.rows['source-output/dw3-us/jp1']['status'],'ok')

    def test_worker_failure_keeps_fresh_log_and_exact_child_command(self):
        from unittest.mock import patch
        import dwpatch
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);worker=root/'derive.log';worker.write_text('stale previous attempt')
            store=Store(root/'state')
            def fail():
                worker.write_text('fresh compiler failure')
                error=RuntimeError('child failed');error.code=7;error.command=['derive','--base','eu'];raise error
            with patch.object(dwpatch,'RELEASE_STATE',store),patch.object(dwpatch,'RELEASE_COMMON',{}):
                with self.assertRaises(Exception):dwpatch.recovery_step('base/eu',fail,{},worker_log=worker)
            row=store.rows['base/eu'];text=Path(row['log']).read_text()
            self.assertEqual(row['exit'],7);self.assertEqual(row['command'],['derive','--base','eu'])
            self.assertEqual(row['worker_log'],str(worker))
            self.assertIn('fresh compiler failure',text);self.assertNotIn('stale previous attempt',text)

    def test_cycles_and_unknown_dependencies_fail_before_work(self):
        with tempfile.TemporaryDirectory() as td:
            store=Store(td)
            with self.assertRaisesRegex(ValueError,'cycle'):
                run([Step('a',lambda:None,{},deps=('b',)),Step('b',lambda:None,{},deps=('a',))],store)
            with self.assertRaisesRegex(ValueError,'unknown'):
                run([Step('a',lambda:None,{},deps=('missing',))],store)


if __name__=='__main__':unittest.main()
