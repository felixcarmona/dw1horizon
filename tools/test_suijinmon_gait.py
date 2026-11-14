"""Check Suijinmon's walk, tired walk and run (species 408): the four legs must not pass through each other.

The model is read from build/imported-model-edit/edit (`tools/models/edit.py get 408`; SUIJINMON_MODEL names another
path): the imported model, to which the overlay writes the clips. The test runs `suijinmon.build` on it (about 2 s).

Legs (a leg is its three bones): right front 11-13, left front 8-10, right hind 2-4, left hind 14-16. The earlier
four-beat walk and gallop put each side's front and hind legs through each other (2307, 3437 and 2014 crossing triangle
pairs in the walk, the tired walk and the run, summed over the loop); the walk is now a diagonal walk with the legs of each side kept apart (122, 155 and 98 now).
"""
import os
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import animsheet
import mmd
from tools.models.field_animations import suijinmon as gait

BONES = 32
LEGS = {'RF': (11, 12, 13), 'LF': (8, 9, 10), 'RH': (2, 3, 4), 'LH': (14, 15, 16)}
# crossing triangle pairs between two legs, summed over the clip's ticks (numpy mesh check, tools/models/field_animations/meshclash.py)
CROSSINGS = {2: 150, 3: 190, 4: 120}
TICKS = {2: 14, 3: 21, 4: 14}
SPEED = {2: 18, 3: 12, 4: 40}


class SuijinmonGait(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            import numpy
        except ImportError:
            raise unittest.SkipTest('needs numpy for the mesh checks')
        path = Path(os.environ.get('SUIJINMON_MODEL', 'build/imported-model-edit/edit/408-Suijinmon.MMD'))
        if not path.exists():
            raise unittest.SkipTest('reconstruct with tools/models/edit.py get 408')
        import json
        cls.rig = json.loads(Path('content/species/408-suijinmon.json').read_text())['model']['skeleton']
        mmd.exe().skeleton[408] = cls.rig
        mmd.exe().bone_count[408] = BONES
        cls.data, cls.report = gait.build(path.read_bytes(), cls.rig)
        cls.model = mmd.MMD.parse(cls.data, BONES)
        cls.model.type = 408

    def frames(self, slot):
        return animsheet.slot_frames(self.model, BONES, slot)[0]

    def test_cycles_and_speeds(self):
        checks = {c['slot']: c for c in self.report['checks']}
        for slot, ticks in TICKS.items():
            if slot == 3:
                continue
            self.assertEqual(checks[slot]['ticks'], ticks)
            self.assertAlmostEqual(checks[slot]['units_per_tick'], SPEED[slot], delta=.5)
        tired = self.frames(3)
        self.assertEqual(len(tired) - 1, TICKS[3])
        self.assertAlmostEqual(abs(tired[-1][0][8] - tired[0][0][8]) / TICKS[3], SPEED[3], delta=.5)
        self.assertLess(SPEED[3], SPEED[2])
        self.assertLess(SPEED[2], SPEED[4])

    def test_planted_soles(self):
        for check in self.report['checks']:
            self.assertLessEqual(max(check['stance_slip'].values()), .1, check['slot'])
            self.assertLessEqual(check['lowest_point'], 3, check['slot'])

    def test_legs_do_not_cross_each_other(self):
        import itertools
        from tools.models.field_animations import meshclash
        clash = meshclash.Clash(self.model, self.rig)
        for slot, limit in CROSSINGS.items():
            total = 0
            for pose in self.frames(slot)[:-1]:
                world = clash.world(pose)
                for a, b in itertools.combinations(LEGS, 2):
                    total += clash.clash(pose, list(LEGS[a]), list(LEGS[b]), world)[0]
            self.assertLessEqual(total, limit, (slot, total))

    def test_idle_and_feeding_unchanged_by_the_gait(self):
        self.assertEqual(self.report['changed_slots'], [2, 3, 4, 8])


if __name__ == '__main__':
    unittest.main()
