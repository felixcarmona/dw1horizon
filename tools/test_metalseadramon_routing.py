"""Replay the native aquatic event routing with the local pre-edit import."""
import hashlib
import json
import os
from pathlib import Path
import unittest

import mmd
from tools.models.field_animations import sea_serpent_audio


class MetalSeadramonRouting(unittest.TestCase):
    def test_identity_and_effect_origins(self):
        own = json.loads(Path('content/species/211-metalseadramon.json').read_text())
        family = json.loads(Path('content/species/61-megaseadramon.json').read_text())
        self.assertEqual((own['level'],own['specialties']),('mega',['ice','mech',None]))
        self.assertEqual(own['effects_like'],61)
        self.assertEqual(own['techniques'][-1],family['techniques'][-1])
        self.assertEqual((own['voice'],own['partner']['voice']),(family['voice'],family['partner']['voice']))
        self.assertEqual({r[0] for r in own['effect_origins']},{1,3})
        self.assertEqual(own['effect_origin_fallback'][0],6)

    def test_replay_preserves_performance(self):
        folder = os.environ.get('DW_SPECIES_REPAIR_FIXTURES')
        if not folder:
            self.skipTest('set DW_SPECIES_REPAIR_FIXTURES to the pre-edit model directory')
        source = (Path(folder)/'211-MetalSeadramon.MMD').read_bytes()
        own = json.loads(Path('content/species/211-metalseadramon.json').read_text())
        family = json.loads(Path('content/species/61-megaseadramon.json').read_text())
        donor = mmd.MMD.load('extracted/CHDAT/MMD2/MGSD.MMD',61)
        result,_ = sea_serpent_audio.repair(source,own['model']['skeleton'],donor,own['techniques'],family['techniques'])
        manifest = json.loads(Path('content/modeldelta/models.json').read_text())
        expected = next(r for r in manifest['models'] if r['id']==211)['mmd']['sha256']
        self.assertEqual(hashlib.sha256(result).hexdigest(),expected)
