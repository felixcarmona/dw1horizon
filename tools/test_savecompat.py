"""Release fixtures must fail on semantic slot/tag changes and malformed records."""

from pathlib import Path as _DevPath
import sys as _dev_sys
_dev_sys.path.insert(0, str(next(p for p in _DevPath(__file__).resolve().parents if (p / "tools").is_dir())))
import copy
import struct
import sys
import unittest
from unittest import mock
from types import SimpleNamespace
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from tools.dev.saves import releases
from tools.dev import memory_card as mcd


class SaveCompatibility(unittest.TestCase):
    def test_locks_compare_slots_even_when_values_equal(self):
        recorded = {'wtif': {'flags': {}, 'vars': {'memories': [9, 1]}}}
        locks = {'mods': {'wtif': {'flags': {}, 'vars': {'memories': 10}}}}
        rows = []
        releases.story_rows(rows, recorded, locks, lambda kind, slot: 1)
        self.assertTrue(any(not ok and 'was var 9' in why for ok, _, why in rows))

    def test_valid_end_required_and_records_must_fit(self):
        head = b'DW4E' + struct.pack('<HHI', 4, 64, 0)
        valid = mcd.build_extension(head, [(3, struct.pack('<i', 181))], 64)
        self.assertEqual(mcd.parse_records(valid), [(3, struct.pack('<i', 181))])
        for body in (struct.pack('<HH', 3, 100), struct.pack('<HH', 0, 1),
                     struct.pack('<HHiHHi', 3, 4, 181, 3, 4, 182)):
            with self.subTest(body=body):
                broken = head + body + bytes(64 - len(head) - len(body))
                self.assertIsNone(mcd.parse_records(broken))

    def test_button_layout_follows_loaded_options(self):
        emu = object.__new__(releases.Emu)
        emu.has = lambda symbol: True
        calls = []
        emu.run = lambda *args: calls.append(args)
        for japanese, expected in ((0, ['CROSS', 'TRIANGLE']), (1, ['CIRCLE', 'CROSS'])):
            emu.peek = lambda *args: japanese
            calls.clear()
            emu.press('CONFIRM', 4)
            emu.press('CANCEL', 4)
            self.assertEqual([call[1] for call in calls], expected)

    def test_retired_frame_rate_checks_the_automatic_selector(self):
        for mode in (0, 2, 1):
            emu=SimpleNamespace(has=lambda name:name=='modCpuProbe',peek=lambda *args:mode)
            rows=[];releases.compare_option(rows,emu,'frameRate',30,{})
            self.assertEqual(rows[0][0],mode in (0,2))
        legacy=SimpleNamespace(has=lambda name:False)
        rows=[];releases.compare_option(rows,legacy,'frameRate',30,{'frameRate':20})
        self.assertFalse(rows[0][0])
        rows=[];releases.compare_option(rows,legacy,'unrecognized',7,{})
        self.assertFalse(rows[0][0])

    def test_resave_normalizes_only_retired_presentation_bytes(self):
        original=bytes([1,0,30,0,2,0,1,1,1,1,1,1,0,3,71,82])
        automatic=SimpleNamespace(has=lambda name:name=='modCpuProbe')
        current=releases.resaved_option_prefix(automatic,original)
        expected=bytearray(original);expected[1]=1;expected[2]=20;expected[3]=1;expected[13]=0
        self.assertEqual(current,bytes(expected));self.assertEqual(current[14:],original[14:])
        self.assertEqual(original[2],30)
        legacy=SimpleNamespace(has=lambda name:name not in ('modCpuProbe','MOD_OPT_FPS'))
        self.assertEqual(releases.resaved_option_prefix(legacy,original),original)
        for length in range(4):self.assertEqual(len(releases.resaved_option_prefix(automatic,original[:length])),length)

    def test_frame_rate_override_migration_and_resave(self):
        emu=SimpleNamespace(has=lambda name:name in ('modCpuProbe','MOD_OPT_FPS'))
        for saved in range(256):
            expected=saved if 0xA0 <= saved <= 0xA2 else 0xA0
            rows=[];releases.compare_option(rows,emu,'frameRate',saved,{'frameRate':expected})
            self.assertTrue(rows[0][0])
            raw=bytes([0,1,saved,1])
            self.assertEqual(releases.resaved_option_prefix(emu,raw)[2],expected)
            rows=[];releases.compare_option(rows,emu,'frameRate',saved,{'frameRate':0xA3})
            self.assertFalse(rows[0][0])

    def test_warp_answers_arrival_dialogue_and_requires_the_target_screen(self):
        for final_screen in (218,204):
            emu=object.__new__(releases.Emu);writes=[];controls=[]
            emu.api=lambda *args,**kwargs:None;emu.wait=lambda seconds:None
            emu.poke=lambda name,data:writes.append(name)
            def control():controls.append(True);return True
            emu.in_control=control
            def peek(name,fmt,ram=None):
                if name=='CURRENT_SCREEN':return 218 if ram is not None else final_screen
                if name=='TAMER_STATE':return 6
                return 0
            emu.peek=peek;emu.ram=lambda:b'RAM'
            self.assertEqual(emu.warp(218),final_screen==218)
            self.assertEqual(controls,[True]);self.assertEqual(writes[-1],'TAMER_STATE')

    def test_release_hook_always_checks_files_and_optional_emulator(self):
        from patcher import dwpatch
        args = SimpleNamespace(save_check_emu=False, variant=['everything=build/everything.bin'])
        with mock.patch.object(dwpatch.subprocess, 'run', return_value=SimpleNamespace(returncode=0)) as run:
            dwpatch.save_check(args)
            self.assertEqual([call.args[0][2] for call in run.call_args_list], ['check'])
            run.reset_mock()
            args.save_check_emu = True
            dwpatch.save_check(args)
            self.assertEqual([call.args[0][2] for call in run.call_args_list], ['check', 'emu'])
        with mock.patch.object(dwpatch.subprocess, 'run', return_value=SimpleNamespace(returncode=1)):
            with self.assertRaises(SystemExit): dwpatch.save_check(args)

    def test_published_cards_and_registry_sabotage(self):
        fixtures = sorted(Path(releases.CORPUS).glob('*.json'))
        self.assertTrue(fixtures, 'release corpus is required')
        locks = releases.load_locks()
        for js in fixtures:
            rows = []
            releases.check_card(str(js), str(js.with_suffix('.mcd')), locks, rows)
            self.assertTrue(all(ok for ok, _, _ in rows), rows)
        saved = mcd.TAGS
        try:
            mcd.TAGS = copy.copy(saved)
            mcd.TAGS[3] = 'changedMeaning'
            rows = []
            releases.check_card(str(fixtures[0]), str(fixtures[0].with_suffix('.mcd')), locks, rows)
            self.assertTrue(any(not ok and 'tag registry' in name for ok, name, _ in rows))
        finally:
            mcd.TAGS = saved


if __name__ == '__main__':
    unittest.main()
