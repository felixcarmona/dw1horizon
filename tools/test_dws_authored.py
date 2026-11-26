#!/usr/bin/env python3
"""Authored edits of the base story keep the behaviour they were made for."""
import sys as _sys, pathlib as _pl; _sys.path.insert(0, str(_pl.Path(__file__).resolve().parent))  # tools/ modules resolve under `python -m unittest tools.<name>`
import ast
import json
from pathlib import Path
import unittest
from types import SimpleNamespace
from unittest.mock import Mock

from dws import build as B
from dws.py import naming as N


@unittest.skipUnless(Path(B.ROOT, 'extracted/SCN/DG.SCN').exists(), 'needs extracted/ (your own disc)')
class UsText(unittest.TestCase):
    def test_us_text_keeps_disc_values_and_loads_new_vending_keys(self):
        from dws.textbank import TextBank
        from dws.textx import BANK
        bank = TextBank(source='us')
        bank.load_defaults()
        with open(BANK) as f:
            for key, value in json.load(f).items():
                if not key.startswith('_'):
                    self.assertEqual(value, bank.data[key], key)
        self.assertEqual('Choose an item.', bank.data['s009.sec81.vend_prompt'])


class PondPile(unittest.TestCase):
    """Run the actual entry handler with engine calls recorded; no disc needed."""

    def enter(self, work, stage=1, days=0):
        source = Path(N.script_file(29))
        tree = ast.parse(source.read_text())
        enter = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'enter')
        enter.decorator_list = []
        routine = SimpleNamespace(**{name: name for name in (
            'load_dirt_cart', 'load_dirt_pile', 'dirt_pile_shrink', 'dirt_cart_model')})

        class SavedWork(int):
            set = Mock()

        env = dict(Routine=routine, call=Mock(), underground_pond_dig_work=SavedWork(work),
                   drill_tunnel_progress=stage, drimogemon_job_days=days,
                   drimogemon=Mock(), objects={18: Mock(), 19: Mock()},
                   pstat=Mock(), raw=Mock())
        exec(compile(ast.Module(body=[enter], type_ignores=[]), str(source), 'exec'), env)
        env['enter']()
        return env

    def test_unfinished_work_keeps_the_pile_model_on_entry(self):
        # Include odd counters from saves made before hauling became two units a trip,
        # and both the accepted job and a box already in transit.
        for work in range(10):
            for stage in (1, 2, 3, 4):
                with self.subTest(work=work, stage=stage):
                    env = self.enter(work, stage)
                    env['call'].assert_any_call('load_dirt_pile')

    def test_completed_work_does_not_restore_the_rubble(self):
        for work in (10, 11, 255):
            env = self.enter(work)
            self.assertNotIn(('load_dirt_pile',), [c.args for c in env['call'].call_args_list])

    def test_last_trip_does_not_reblock_the_open_tunnel(self):
        env = self.enter(8, stage=2)
        env['call'].assert_any_call('load_dirt_pile')
        env['raw'].set_rect_impassable.assert_not_called()

    def test_five_day_wait_still_finishes_excavation(self):
        for work in (0, 8, 9):
            env = self.enter(work, days=5)
            calls = [c.args for c in env['call'].call_args_list]
            self.assertIn(('load_dirt_pile',), calls)
            self.assertEqual(calls.count(('dirt_pile_shrink',)), 10)
            env['underground_pond_dig_work'].set.assert_called_once_with(10)
            env['raw'].set_rect_impassable.assert_not_called()

    @unittest.skipUnless(Path(B.ROOT, 'extracted/MAP/MAP2/TUNN05.MAP').exists(), 'needs extracted/')
    def test_pickup_is_reachable_from_the_entrance_before_and_after_tunnel_opens(self):
        from dwmap import MapFile
        from maps.reach import model_tile, reach
        for work in (0, 8):
            with self.subTest(work=work):
                env = self.enter(work, stage=2)
                m = MapFile(Path(B.ROOT, 'extracted/MAP/MAP2/TUNN05.MAP').read_bytes())
                for c in env['raw'].set_rect_impassable.call_args_list:
                    _, x, z, w, h = c.args
                    for tz in range(z, z + h):
                        for tx in range(x, x + w):
                            m.collision[tz * 100 + tx] = 128
                entrance = m.warps[0]
                reached = reach(m, starts=[(entrance['x'], entrance['z'])])
                pickup = {(x, z) for x, z in reached
                          if m.collision[model_tile(x, z)[1] * 100 + model_tile(x, z)[0]] == 81}
                # At least a full tile of positions can interact, away from the pile centre.
                self.assertGreaterEqual(len(pickup), 100)
                self.assertTrue(any(x < 1900 for x, z in pickup))


if __name__ == '__main__':
    unittest.main()
