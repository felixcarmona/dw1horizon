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
