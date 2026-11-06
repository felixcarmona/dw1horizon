"""Ordered writes remain ordered; only declared snapshots may be split apart."""
import hashlib
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

source = Path(__file__).resolve().parents[1]/'web/enginebuild/record_groups.py'
spec = importlib.util.spec_from_file_location('record_groups', source)
groups = importlib.util.module_from_spec(spec)
spec.loader.exec_module(groups)


def job(index, group=None, snapshot=False):
    return dict(step='story', name=str(index), index=index, order_group=group,
                record_snapshot=snapshot, existed=[], writes={}, removes=[])


class Groups(unittest.TestCase):
    def test_stateful_groups_are_single_ordered_tasks(self):
        units = [job(0,'shared'), job(1), job(2,'shared'), job(3)]
        self.assertEqual([[j['index'] for j in task] for task in groups.groups(units)], [[0,2],[1],[3]])

    def test_snapshot_groups_split_without_losing_identity(self):
        units = [job(0,'shared',True), job(1,'shared',True)]
        self.assertEqual(len(groups.groups(units)), 2)
        self.assertTrue(groups.same_group(*units))
        self.assertFalse(groups.stateful_peers(*units))
        with self.assertRaisesRegex(RuntimeError, 'inconsistent'):
            groups.groups([units[0], job(1,'shared',False)])

    def test_group_read_dependencies_require_stateful_execution(self):
        a,b=job(0,'shared'),job(1,'shared')
        a['writes']={'output':None};b['existed']=['output']
        groups.validate_reads([a,b])
        a['record_snapshot']=b['record_snapshot']=True
        groups.validate_reads([a,b])  # both explicitly read their prepared snapshots
        b['record_snapshot']=False
        with self.assertRaisesRegex(RuntimeError, 'dependent sibling'):
            groups.validate_reads([a,b])

    def test_only_declared_ordering_allows_different_write_bytes_or_modes(self):
        with tempfile.TemporaryDirectory() as td:
            results=[]
            for i in range(3):
                folder=Path(td)/str(i);folder.mkdir();(folder/'shared').write_bytes(str(i).encode())
                j=job(i,'shared');j['writes']={'shared':None}
                results.append(dict(graph=j,artifact=folder))
            digest=lambda p:hashlib.sha256(p.read_bytes()).digest()
            operations=groups.merge_operations(results,digest)
            self.assertEqual(operations['shared'].read_bytes(), b'2')
            results[1]['graph']['order_group']=None
            with self.assertRaisesRegex(RuntimeError,'conflicting'):
                groups.merge_operations(results,digest)

    def test_story_snapshot_recording_is_disabled(self):
        from tools.derive.steps import story
        with tempfile.TemporaryDirectory() as td:
            for readonly, main, expected in ((True, '', False), (False, '', False), (True, 'custom.dws', False)):
                ctx=SimpleNamespace(root=td, out=td, env={}, facts=None, locks_read_only=readonly,
                                    path=lambda *parts:str(Path(td).joinpath(*parts)))
                settings=SimpleNamespace(main=main, screens=[], maps='', extra=[], scrn=False,
                    langs=lambda ctx:[('en',td,'us','en','',False)], variants=lambda text,facts:[''])
                with patch.object(story, 'Settings', return_value=settings), patch.object(story,'pass_argv',return_value=[]):
                    unit=story.units(ctx)[0]
                self.assertEqual(unit.record_snapshot, expected)
                self.assertIsNotNone(unit.order_group)

    def test_ordered_removal_then_write_uses_canonical_final_operation(self):
        with tempfile.TemporaryDirectory() as td:
            folder=Path(td);(folder/'shared').write_bytes(b'last')
            a,b=job(0,'shared'),job(1,'shared')
            a['removes']=['shared'];b['writes']={'shared':None}
            operations=groups.merge_operations([dict(graph=a,artifact=folder),dict(graph=b,artifact=folder)],
                                               lambda p:p.read_bytes())
            self.assertEqual(operations['shared'].read_bytes(), b'last')


if __name__=='__main__':
    unittest.main()
