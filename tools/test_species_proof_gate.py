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
        stack.enter_context(patch.object(proof.species, 'read_index',
                                         return_value=([234], None, None)))
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

    def test_confirmed_species_reaches_battle_checks(self):
        with tempfile.TemporaryDirectory() as directory, contextlib.ExitStack() as stack:
            calls = self.fixture(stack, directory, 234)
            calls['battle'].side_effect = lambda _t, _m, _o, r: r.update(
                in_battle=True, frames_advance=True,
                techniques_played=['0x2e'], game_state_after=0)
            with self.assertRaises(SystemExit) as stopped:
                proof.main()
            self.assertEqual(stopped.exception.code, 0)
            calls['battle'].assert_called_once()
            calls['status'].assert_called_once()
            result = json.loads((Path(directory) / 'result.json').read_text())['234']
            self.assertTrue(result['ok'])


if __name__ == '__main__':
    unittest.main()
