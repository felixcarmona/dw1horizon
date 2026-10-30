"""Pin repository paths, scenario frame counts and video source-map boundaries."""

from pathlib import Path as _DevPath
import sys as _dev_sys
_dev_sys.path.insert(0, str(next(p for p in _DevPath(__file__).resolve().parents if (p / "tools").is_dir())))
import json
import os
import subprocess
import sys
from pathlib import Path
import tempfile
import unittest

from tools.dev import symbols as dwsyms
from tools.dev import emulator as emu
from tools.dev import story_test as dwstest
from tools.dev import story_video as dwsvideo
from tools.dev.playtest import batch_import, batch_import_video, shopnav
from tools.dev.playtest.screens import maps as screen_maps

ROOT = Path(__file__).resolve().parents[1]


class DeveloperContracts(unittest.TestCase):
    def test_paths_remain_relative_to_the_worktree(self):
        for module in (dwsyms, emu, dwstest, dwsvideo):
            self.assertEqual(Path(module.ROOT).resolve(), ROOT)
        self.assertTrue(Path(emu.HANDLERS).is_file())
        self.assertTrue(Path(dwstest.LUA).is_file())
        self.assertEqual(len(dwstest.scenarios()), 11)
        self.assertEqual(Path(dwstest.SCEN_DIR), ROOT / 'tools/dws/testing/scenarios')
        self.assertEqual(Path(dwsyms.ORIG_EXE), ROOT / 'extracted/SLUS_010.32')

    def test_story_semantics_cli_finds_developer_transport_without_pythonpath(self):
        env = dict(os.environ)
        env.pop('PYTHONPATH', None)
        for name in ('checkpoints', 'route', 'branches', 'sweep', 'trace_audit', 'random_audit'):
            with self.subTest(name=name):
                result = subprocess.run(
                    [sys.executable, str(ROOT / f'tools/dws/testing/{name}.py'), '--help'],
                    cwd=ROOT, env=env, capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stderr)

    def test_scenario_counts_are_game_frames(self):
        self.assertEqual(dwstest.parse_step('wait 17'), {'t': 'wait', 'n': 17})
        self.assertEqual(dwstest.parse_step('press cross 8'), {'t': 'press', 'b': 'CROSS', 'n': 8})
        self.assertEqual(dwstest.parse_step('press start'), {'t': 'press', 'b': 'START', 'n': 3})
        self.assertEqual(dwstest.lua_value({'trace': True, 'steps': [1, 'a']}),
                         '{["trace"]=true,["steps"]={1,"a"}}')

    def test_nested_helpers_find_inputs_and_commands_in_this_worktree(self):
        for module in (batch_import, batch_import_video, screen_maps):
            self.assertEqual(Path(module.ROOT), ROOT)
        for command in (batch_import.E[1], batch_import.M[1], batch_import.G[1],
                        batch_import_video.MONTAGE, shopnav.EMU):
            self.assertTrue(Path(command).is_file(), command)
            self.assertTrue(Path(command).is_relative_to(ROOT / 'tools/dev'))
        self.assertEqual(Path(screen_maps.MAP1), ROOT / 'extracted/MAP/MAP1')

    def test_frozen_recipe_imports_share_the_live_module_state(self):
        import importlib
        for old, new in (('emu', 'emulator'), ('dwsyms', 'symbols'),
                         ('mem', 'memory_inspector'), ('gamestate', 'game_state')):
            self.assertIs(importlib.import_module('tools.' + old),
                          importlib.import_module('tools.dev.' + new))

    def test_video_offsets_keep_last_same_offset_and_end_markers(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / 'source.json'
            path.write_text(json.dumps({'18': [[4, 'scene.py:2'], [4, 'scene.py:3'], [8, '-'], [10, 'scene.py:7']]}))
            src = dwsvideo.SrcMap(path)
            self.assertIsNone(src.at(18, 3))
            self.assertEqual(src.at(18, 4), ('scene.py', 3))
            self.assertIsNone(src.at(18, 8))
            self.assertEqual(src.between(18, 4, 10), [('scene.py', '7')])
            self.assertEqual(src.between(18, 10, 4), [])

    def test_symbol_arithmetic_keeps_target_addresses(self):
        self.assertEqual(dwsyms.resolve('0x80123456'), 0x80123456)
        money = dwsyms.resolve('MONEY')
        self.assertEqual(dwsyms.resolve('MONEY+0x10'), money + 16)
        self.assertEqual(dwsyms.resolve('MONEY-4'), money - 4)


if __name__ == '__main__':
    unittest.main()
