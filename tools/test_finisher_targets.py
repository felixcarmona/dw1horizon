"""The damage recorder must retain charge control and observe the settled HP drain."""
import contextlib
import io
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock

from tools.dev.playtest import finisher_targets as F


class Recorder(unittest.TestCase):
    def run_trial(self, lost_charge=False, self_hit=False):
        enemy = F.P.ENEMY_HP
        anim, frame = F.P.ANIM, F.P.FRAME

        def sample(charge=80, remaining=-1, hp=2500):
            return {F.PARTNER_HP: hp + 1500 if self_hit else 4000,
                    **dict.fromkeys(enemy, 2500), enemy[0]: 2500 if self_hit else hp,
                    F.CHARGE: charge, F.CHARGE_TIME: remaining,
                    anim: 0x38, frame: 1, 'GAME_STATE': 1, 'NO_AI_FLAG': 0,
                    'EFE_TARGET_ENTITY_INDEX': 2}

        # A presentation pass can discard a successful RAM write. The second
        # active-window sample still has zero charge and needs another write.
        charge = 0 if lost_charge else 80
        reads = [sample(), sample(), sample(0, 79), sample(0, 78),
                 sample(charge, 0, 2000), sample(charge, -1, 1000)]
        writes = mock.Mock()
        emu = SimpleNamespace(has=lambda name: True, ram=lambda: bytes(0x200000),
                              run=lambda *args: '0')
        recorder = mock.Mock(returncode=0)
        recorder.poll.side_effect = [None, None, None, 0]

        def battle(species, moves, out, result, **kwargs):
            self.assertIsNone(kwargs['chargeup'], 'the watcher owns the charge window')
            kwargs['launch_and_watch'](0x38, 30, lambda: None)
            result.update(in_battle=True, frames_advance=True, finisher_played=True,
                          game_state_after=0)

        fake = SimpleNamespace(
            ENEMY_HP=enemy, ANIM=anim, FRAME=frame, NPC_SLOTS=8, E=['emulator'],
            emulator=lambda cue: emu, EMU=emu, mem=lambda *names: reads.pop(0),
            mset=writes, seq=lambda text: None, game_state=lambda values: values['GAME_STATE'],
            lab_evolve=lambda *args: None, partner_type=lambda: 324, battle=battle,
            species=SimpleNamespace(read_archive=lambda path: (None, None, {
                324: {'para': {'moves': [62]}}})), run=lambda *args: None)
        with tempfile.TemporaryDirectory() as tmp:
            argv = ['finisher_targets', 'disc.cue', 'DIGI.DAT', tmp, '324',
                    '--trials', '1', '--attach', '--chargeup', '80']
            if self_hit:
                argv.append('--baseline')
            with (mock.patch.object(F, 'P', fake), mock.patch.object(F, 'bind_memory'),
                  mock.patch.object(F.subprocess, 'Popen', return_value=recorder),
                  mock.patch.object(F.time, 'sleep'), mock.patch('sys.argv', argv),
                  contextlib.redirect_stdout(io.StringIO())):
                status = F.main()
            result = json.loads((Path(tmp) / 'result.json').read_text())[0]
        return status, result, writes

    def test_reapplies_charge_and_records_the_whole_hp_drain(self):
        status, result, writes = self.run_trial()
        self.assertEqual(status, 0)
        self.assertTrue(result['ok'])
        self.assertEqual(result['enemy_damage'], 1500)
        self.assertEqual([u['damage'] for u in result['hp_updates']], [500, 1000])
        charge_writes = [call for call in writes.call_args_list
                         if call == mock.call(f'{F.CHARGE}=80')]
        self.assertEqual(len(charge_writes), 2)
        self.assertEqual(len(result['samples']), 5)

    def test_rejects_a_hit_that_lost_its_requested_charge(self):
        status, result, _ = self.run_trial(lost_charge=True)
        self.assertEqual(status, 1)
        self.assertFalse(result['ok'])
        self.assertTrue(result['chargeup_set'])
        self.assertEqual(result['enemy_damage'], 1500)

    def test_baseline_records_caster_hp_loss_at_the_requested_charge(self):
        status, result, _ = self.run_trial(self_hit=True)
        self.assertEqual(status, 0)
        self.assertTrue(result['ok'])
        self.assertEqual(result['self_damage'], 1500)
        self.assertEqual(result['enemy_damage'], 0)
        self.assertTrue(all(u['entity'] == F.PARTNER_HP for u in result['hp_updates']))


if __name__ == '__main__':
    unittest.main()
