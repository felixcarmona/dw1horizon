#!/usr/bin/env python3
"""Real recorder subprocesses: isolation, graph bytes, artifacts and failure logs."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
RECORDER = ROOT / 'web/enginebuild/record.py'
sys.path.insert(0, str(RECORDER.parent))
spec = importlib.util.spec_from_file_location('record_parallel', RECORDER.with_name('record_parallel.py'))
parallel = importlib.util.module_from_spec(spec)
spec.loader.exec_module(parallel)

DERIVE = '''import json, os, sys, tempfile, time
from pathlib import Path
HELPER = Path('input-helper.txt').read_text()
def main():
 a=sys.argv[1:]; out=Path(a[a.index('--out')+1]); step=a[a.index('--step')+1] if '--step' in a else a[a.index('--steps')+1]
 if a[0]=='units':
  policy=dict(order_group='sequence') if Path('ordered').exists() else {}
  print(json.dumps([dict(index=i,name='unit-'+str(i),**policy) for i in range(3)])); return
 out.mkdir(parents=True,exist_ok=True)
 if '--prepare' in a:
  (out/step).mkdir(exist_ok=True); return
 if '--finish' in a:
  dest=out/'derived';dest.mkdir(exist_ok=True)
  files={str(p.relative_to(out)):dict(file=str(p.relative_to(out))) for p in sorted(out.glob('*/*.bin'))}
  (dest/'manifest.json').write_text(json.dumps(dict(files=files))); return
 i=int(a[a.index('--index')+1]); time.sleep((3-i)*0.02)
 if not Path('ordered').exists() and step!='story': assert Path('empty').is_dir(), 'worker baseline directory was not restored'
 if Path('fail').exists() and i==1: raise RuntimeError('intentional unit failure')
 source=Path('extracted')/('input-'+str(i)); value=source.read_bytes(); source.write_bytes(value+b'-edited')
 if not Path('ordered').exists() and step!='story': assert not (out/step/('unit-'+str((i+1)%3)+'.bin')).exists(), 'sibling output leaked'
 (out/step/('unit-'+str(i)+'.bin')).write_bytes(value+HELPER.encode())
 common=out/step/'shared.bin'
 if Path('ordered').exists(): common.write_bytes((common.read_bytes() if common.exists() else b'')+str(i).encode())
 else: common.write_bytes(b'common' if not Path('conflict').exists() else str(i).encode())
 folder=Path(tempfile.mkdtemp(prefix='run-',dir=out/step))
 (folder/'data.bin').write_bytes(value)
 if i==0 and step!='story' and Path('empty').exists(): Path('empty').rmdir()
 print('unit complete')
'''


def fixture(tree):
    for name, data in {
        str(Path('tools')/'__init__.py'): '', 'tools/derive/__init__.py': '', 'tools/derive/__main__.py': DERIVE,
        str(Path('tools/derive')/'steps.py'): 'from types import SimpleNamespace\nSTEPS=[SimpleNamespace(NAME=n,AFTER=(() if i==0 else ("maps",)),units=True) for i,n in enumerate(("maps","story","signs"))]\ndef owned():return STEPS\ndef load(n):return next(s for s in STEPS if s.NAME==n)\n',
        'tools/derive/graph.py': 'def order(steps):return steps\n',
        'input-helper.txt': 'authored helper',
        **{'extracted/input-'+str(i): 'source-'+str(i) for i in range(3)},
    }.items():
        p = tree / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(data)
    (tree / 'empty').mkdir()


class RecorderTests(unittest.TestCase):
    def run_record(self, tree, out, jobs):
        return subprocess.run([sys.executable, '-B', str(RECORDER), str(tree), str(out),
             '--jobs', str(jobs), '--worker-memory-mib', '64'],
             env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1'), capture_output=True, text=True, timeout=60)

    def test_parallel_and_sequential_graph_and_outputs_are_byte_identical(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            graphs, artifacts = [], []
            for jobs in (1, 3):
                tree = root / str(jobs)
                fixture(tree)
                out = root / (str(jobs)+'.json')
                result = self.run_record(tree, out, jobs)
                self.assertEqual(result.returncode, 0, result.stdout+result.stderr)
                graphs.append(out.read_bytes())
                artifacts.append({str(p.relative_to(tree)): p.read_bytes() for p in tree.rglob('*.bin')})
                self.assertTrue((tree/'empty').exists())
                graph = json.loads(graphs[-1])
                self.assertEqual(graph['tree'], '{ROOT}')
                self.assertIn('input-helper.txt', graph['jobs'][2]['existed'])
                self.assertTrue(list(Path(str(out)+'.logs').rglob('*.timing.json')))
            self.assertEqual(graphs[0], graphs[1])
            self.assertEqual(artifacts[0], artifacts[1])

    def test_story_recording_never_dispatches_parallel_batches(self):
        with tempfile.TemporaryDirectory() as td:
            tree=Path(td)/'tree';fixture(tree)
            result=self.run_record(tree,Path(td)/'graph.json',3)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            self.assertNotIn('record story:',result.stdout)
            self.assertIn('record maps:',result.stdout)

    def test_ordered_mutations_keep_predecessor_state_at_every_worker_count(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); graphs=[]
            for count in (1,3):
                tree=root/str(count);fixture(tree);(tree/'ordered').touch()
                out=root/(str(count)+'.json')
                result=self.run_record(tree,out,count)
                self.assertEqual(result.returncode,0,result.stdout+result.stderr)
                graphs.append(out.read_bytes())
                for step in ('maps','story','signs'):
                    self.assertEqual((tree/'build/everything'/step/'shared.bin').read_bytes(),b'012')
            self.assertEqual(*graphs)

    def test_worker_failure_has_specific_log_and_no_partial_merge(self):
        with tempfile.TemporaryDirectory() as td:
            tree, out = Path(td)/'tree', Path(td)/'record.json'
            fixture(tree)
            (tree/'fail').touch()
            result = self.run_record(tree, out, 3)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('worker', result.stderr)
            logs = list(Path(str(out)+'.logs').rglob('maps-unit-1.log'))
            self.assertEqual(len(logs), 1)
            self.assertIn('intentional unit failure', logs[0].read_text())
            self.assertEqual(list((tree/'build/everything/maps').glob('*.bin')), [])
            self.assertEqual((tree/'extracted/input-0').read_bytes(), b'source-0')

    def test_disagreeing_shared_writes_fail_before_merge(self):
        with tempfile.TemporaryDirectory() as td:
            tree, out = Path(td)/'tree', Path(td)/'record.json'
            fixture(tree)
            (tree/'conflict').touch()
            result = self.run_record(tree, out, 3)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('conflicting recorder writes', result.stderr)
            self.assertEqual(list((tree/'build/everything/maps').glob('*.bin')), [])

    def test_mirror_updates_bytes_mode_inventory_and_preserves_empty_directories(self):
        with tempfile.TemporaryDirectory() as td:
            master, tree = Path(td)/'master', Path(td)/'tree'
            master.mkdir(); (master/'data').write_bytes(b'one'); (master/'empty').mkdir(mode=0o700)
            state = Path(td)/'state.json'
            parallel.mirror(master, tree, state)
            self.assertEqual((tree/'empty').stat().st_mode & 0o777, 0o700)
            old = (master/'data').stat()
            (master/'data').write_bytes(b'two')
            os.utime(master/'data', ns=(old.st_atime_ns, old.st_mtime_ns))
            (master/'data').chmod(0o600)
            (master/'new').write_bytes(b'new'); (master/'empty').rmdir()
            parallel.mirror(master, tree, state)
            self.assertEqual((tree/'data').read_bytes(), b'two')
            self.assertEqual((tree/'data').stat().st_mode & 0o777, 0o600)
            self.assertTrue((tree/'new').exists())
            self.assertFalse((tree/'empty').exists())
            (tree/'data').write_bytes(b'private edit')
            self.assertEqual((master/'data').read_bytes(), b'two')


if __name__ == '__main__':
    unittest.main()
