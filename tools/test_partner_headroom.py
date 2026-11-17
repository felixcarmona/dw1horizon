"""Decoded-motion and fixed-allocation regression on private real model fixtures.

PARTNER_HEADROOM_FIXTURES=build/heap-proof python3 -m unittest tools.test_partner_headroom
The directory contains ID-before.MMD and ID-safe.MMD for each reviewed species.
"""
import os
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'tools')]
import mmd
import coldsplit
import animsheet
from tools.models import partner_headroom as H


class DiscPlanning(unittest.TestCase):
    def test_disc_paths_and_model_outputs_need_no_build_directory(self):
        import tempfile
        from unittest.mock import patch
        from tools import species
        from tools.derive.steps import models

        content = species.load_content(str(ROOT/'content/species'))
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            # Real content includes generated models of headroom species. Resolve
            # them against a root with no build/, rather than existing fixtures.
            with patch.object(species, 'ROOT', td), \
                 patch.object(species, 'load_content', return_value=content):
                files = species.disc_files(str(ROOT/'content/species'))
                self.assertIn(('--file', 'CHDAT/MMD3/INSE.MMD',
                               'build/models/INSE-partner.MMD'), files)
                self.assertEqual(models.outputs(None),
                                 [(f'models/{f}', None) for f, _ in models.MODELS])
                self.assertFalse((root/'build').exists())
                with self.assertRaises(FileNotFoundError):
                    species.disc_files(str(ROOT/'content/species'), replace_models=True)

    def test_disc_assembly_explicitly_uses_headroom_replacement(self):
        from unittest.mock import patch
        from tools import species

        content = {113: {'model': {'file': 'build/models/INSE-partner.MMD',
                                   'name': 'INSE', 'bones': 1}}}
        with patch.object(species, 'load_content', return_value=content), \
             patch.object(species, 'is_record_original', return_value=False), \
             patch.object(H, 'disc_file', return_value='safe.MMD') as replace:
            self.assertEqual(species.disc_files(replace_models=True),
                             [('--file', 'CHDAT/MMD3/INSE.MMD', 'safe.MMD')])
            replace.assert_called_once_with(species.resolve_path(content[113]['model']['file']), 1, 113)

    def test_manifest_pins_the_assembled_replacement_instead_of_the_authored_model(self):
        import tempfile
        from types import SimpleNamespace
        from unittest.mock import patch
        from tools.derive import manifest, steps
        from tools.derive.steps import models, plan

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            for folder in ('models', 'partner-headroom', 'derived'):
                (root/folder).mkdir()
            (root/'models/INSE-partner.MMD').write_bytes(b'authored')
            safe = root/'partner-headroom/safe.MMD'
            safe.write_bytes(b'recompressed')
            disc = 'CHDAT/MMD3/INSE.MMD'
            (root/'derived/disc.txt').write_text(f'--file\t{disc}={safe}\n')
            ctx = SimpleNamespace(out=td, path=lambda *p: str(root.joinpath(*p)))
            with patch.object(steps, 'OWNED', ['models', 'plan']):
                m = manifest.load(td)
                manifest.record(m, td, models, models.outputs(ctx), 0, None)
                manifest.record(m, td, plan, plan.outputs(ctx), 0, None)
            self.assertEqual(m['files'][disc]['sha1'], manifest.sha1(safe))
            self.assertEqual(m['files'][disc]['step'], 'plan')



@unittest.skipUnless(os.environ.get('PARTNER_HEADROOM_FIXTURES'), 'private model fixtures required')
class PartnerHeadroom(unittest.TestCase):
    def test_actual_models_preserve_mesh_events_timing_and_channel_bound(self):
        import json
        folder=Path(os.environ['PARTNER_HEADROOM_FIXTURES'])
        metadata=json.loads((folder/'fixture-bones.json').read_text())
        for sid in sorted(H.SPECIES):
            with self.subTest(species=sid):
                nb=metadata[str(sid)]
                before=(folder/f'{sid}-before.MMD').read_bytes()
                after,proof=H.apply(before,[None]*nb,sid,cold=sid>=180)
                self.assertEqual(after,(folder/f'{sid}-safe.MMD').read_bytes())
                a,b=mmd.MMD.parse(before,nb),mmd.MMD.parse(after,nb)
                self.assertEqual(a.tmd.build(),b.tmd.build())
                self.assertEqual(len(a.anims.table),len(b.anims.table))
                for slot,(ai,bi) in enumerate(zip(a.anims.table,b.anims.table)):
                    self.assertEqual(ai is None,bi is None)
                    if ai is None:continue
                    if a.anims.anims[ai].build()==b.anims.anims[bi].build():continue
                    if sid>=180:self.assertIn(slot,H.SLOTS)
                    frames,loop,events=animsheet.slot_frames(a,nb,slot)
                    again,loop2,events2=animsheet.slot_frames(b,nb,slot)
                    self.assertEqual((len(frames),loop,list(events)),(len(again),loop2,list(events2)))
                    error=max(abs(int(x)-int(y)) for pa,pb in zip(frames,again)
                              for ba,bb in zip(pa,pb) for x,y in zip(ba,bb))
                    self.assertLessEqual(error,proof['tolerance'])
                resident,cold=coldsplit.split(after,nb) if sid>=180 else (after,b'')
                self.assertLessEqual((len(resident)+2047)//2048*2048,0x18000)
                self.assertEqual(H.apply(after,[None]*nb,sid,cold=sid>=180)[0],after)


if __name__=='__main__':unittest.main()
