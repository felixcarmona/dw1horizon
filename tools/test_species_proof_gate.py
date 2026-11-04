"""Never label another species' downstream checks as the requested species."""

from pathlib import Path as _DevPath
import sys as _dev_sys
_dev_sys.path.insert(0, str(next(p for p in _DevPath(__file__).resolve().parents if (p / "tools").is_dir())))
import contextlib
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from tools.dev.playtest import species_proof as proof


class EvolutionEvidenceGate(unittest.TestCase):
    def fixture(self, stack, directory, actual, extra=()):
        stack.enter_context(patch.dict(os.environ, EMU_PORT='38799'))
        stack.enter_context(patch.object(sys, 'argv', [
            'species_proof.py', 'unused.cue', 'unused.dat', directory,
            '234', *extra]))
        stack.enter_context(patch.object(proof.species, 'read_archive', return_value=(
            b'', None, {234: {'para': {'name': 'Gatomon', 'moves': []}}})))
        calls = {}
        for name in ['boot', 'lab_evolve', 'battle', 'feed', 'status',
                     'save_game', 'run', 'seq']:
            calls[name] = stack.enter_context(patch.object(proof, name))
        stack.enter_context(patch.object(proof, 'partner_type', return_value=actual))
        calls['boot'].return_value = True
        stack.enter_context(contextlib.redirect_stdout(io.StringIO()))
        return calls

    def test_failed_evolution_skips_battle_feed_status_and_save_reload(self):
        with tempfile.TemporaryDirectory() as directory, contextlib.ExitStack() as stack:
            calls = self.fixture(stack, directory, 3, ('--feed', '--save', '234'))
            with self.assertRaises(SystemExit) as stopped:
                proof.main()
            self.assertEqual(stopped.exception.code, 1)
            for name in ['battle', 'feed', 'status', 'save_game']:
                calls[name].assert_not_called()
            self.assertEqual(calls['boot'].call_count, 2)
            result = json.loads((Path(directory) / 'result.json').read_text())['234']
            self.assertFalse(result['evolved'])
            self.assertFalse(result['ok'])
            self.assertEqual(result['type_after_evolution'], 3)

    def test_a_boot_that_never_reached_the_world_fails_without_evolving(self):
        with tempfile.TemporaryDirectory() as directory, contextlib.ExitStack() as stack:
            calls = self.fixture(stack, directory, None)
            calls['boot'].return_value = False
            with self.assertRaises(SystemExit) as stopped:
                proof.main()
            self.assertEqual(stopped.exception.code, 1)
            calls['lab_evolve'].assert_not_called()
            result = json.loads((Path(directory) / 'result.json').read_text())['234']
            self.assertEqual(result['error'], 'never reached the world')

    def test_confirmed_species_reaches_battle_checks(self):
        with tempfile.TemporaryDirectory() as directory, contextlib.ExitStack() as stack:
            calls = self.fixture(stack, directory, 234)
            calls['status'].side_effect = lambda _t, _o, r: r.update(status_drawn=True)
            calls['battle'].side_effect = lambda _t, _m, _o, r: r.update(
                in_battle=True, frames_advance=True,
                techniques_played=['0x2e'], game_state_after=0, finisher_expected=False)
            with self.assertRaises(SystemExit) as stopped:
                proof.main()
            self.assertEqual(stopped.exception.code, 0)
            calls['battle'].assert_called_once()
            calls['status'].assert_called_once()
            result = json.loads((Path(directory) / 'result.json').read_text())['234']
            self.assertTrue(result['ok'])


class BattleEvidenceGate(unittest.TestCase):
    PLAYED = dict(evolved=True, in_battle=True, frames_advance=True, techniques_played=['0x2e'],
                  game_state_after=0, finisher_expected=True, finisher_played=True, finisher_damage=40)

    def test_a_played_finisher_that_hit_passes(self):
        self.assertEqual(proof.battle_failures(self.PLAYED), [])

    def test_an_unplayed_finisher_fails(self):
        self.assertIn('finisher_played', proof.battle_failures({**self.PLAYED, 'finisher_played': False}))

    def test_a_finisher_without_damage_fails(self):
        for damage in (0, None):
            self.assertIn('finisher_damage', proof.battle_failures({**self.PLAYED, 'finisher_damage': damage}))

    def test_a_species_with_no_finisher_is_not_asked_for_one(self):
        result = {**self.PLAYED, 'finisher_expected': False, 'finisher_played': False, 'finisher_damage': None}
        self.assertEqual(proof.battle_failures(result), [])

    def test_a_fight_that_never_returned_fails(self):
        self.assertIn('back_in_world', proof.battle_failures({**self.PLAYED, 'game_state_after': 1}))


class HarnessReads(unittest.TestCase):
    def test_an_empty_read_is_a_harness_error_not_a_failed_check(self):
        with patch.object(proof, 'run', return_value='dwsyms: build x (explicit)\n.digimonEntity: not a struct\n'):
            with self.assertRaises(RuntimeError) as raised:
                proof.mem(proof.ANIM, proof.FRAME)
        self.assertIn('not a struct', str(raised.exception))

    def test_values_are_read_by_name(self):
        with patch.object(proof, 'run', return_value='GAME_STATE = 1\nMONEY = 5 (0x5)\n'):
            self.assertEqual(proof.mem('GAME_STATE', 'MONEY'), {'GAME_STATE': 1, 'MONEY': 5})


if __name__ == '__main__':
    unittest.main()
