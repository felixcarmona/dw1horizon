"""Every species with a chibi row keeps its chibi proportions, whatever a later batch does to its clips or rig.

The measured proportions of each final model (head, feet, hands, legs against its height) must stay at the approved values
of content/models/imports/chibi-proportions.json. The models come from `tools/models/edit.py get` (CHIBI_MODELS names
the folder; default build/imported-model-edit/edit) and the player DW1 extraction; without them the model tests skip.
CHIBI_IDS limits them to some species (a space separated list)."""
import copy
import json
import os
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'tools')]
import mmd
import motionstorage
from tools.models import chibi_proportions as pins
from tools.models.field_animations import chibi, native_binding

MODELS = Path(os.environ.get('CHIBI_MODELS', ROOT / 'build/imported-model-edit/edit'))


class Pins(unittest.TestCase):
    def test_every_row_has_approved_proportions(self):
        rows = json.loads(chibi.MANIFEST.read_text())
        approved = json.loads(pins.PINS.read_text())
        self.assertEqual(sorted(approved, key=int), sorted(rows, key=int))
        for sid, values in approved.items():
            self.assertTrue(set(pins.KEYS) <= set(values) <= set(pins.KEYS) | {'accepted'}, sid)
            if 'accepted' in values:               # a key may be accepted only with its reason
                self.assertTrue(set(values['accepted']) - {'why'} <= set(pins.KEYS) and values['accepted'].get('why'), sid)
            self.assertGreater(values['head'], 0.05, sid)        # a species at its source proportions has no row to keep

    def test_a_stray_is_told(self):
        pinned = dict(head=0.30, head_width=0.25, foot=0.60, hand=0.20, legs=0.40)
        self.assertEqual(pins.strays('1', dict(pinned), pinned), {})
        self.assertEqual(sorted(pins.strays('1', dict(pinned, head=0.18, legs=0.55), pinned)), ['head', 'legs'])

    def test_a_bound_rig_takes_the_groups_of_its_source_pieces(self):
        groups = {1: 'chest', 2: 'head', 3: 'headpart', 4: 'foot', 5: 'shin'}
        self.assertEqual(chibi.donor_groups({'1': 10, '2': 11, '3': 11, '4': 12, '5': 12}, groups),
                         {10: 'chest', 11: 'head', 12: 'foot'})


@unittest.skipUnless(list(MODELS.glob('199-*.MMD')) and (Path(mmd.EXTRACTED) / 'CHDAT/MMD0/TYRA.MMD').exists(),
                     'needs the imported models (tools/models/edit.py get) and the player DW1 extraction')
class FinalModels(unittest.TestCase):
    def test_every_chibi_species_keeps_its_proportions(self):
        approved = json.loads(pins.PINS.read_text())
        wanted = os.environ.get('CHIBI_IDS', '').split() or sorted(approved, key=int)
        lost = {}
        for sid in wanted:
            off = pins.strays(sid, pins.measure(sid, MODELS), approved[sid])
            if off:
                lost[sid] = off
        self.assertEqual(lost, {}, 'these species lost their chibi proportions (a deliberate change rewrites its pins: '
                                   'tools/models/chibi_proportions.py write ID)')


@unittest.skipUnless(list(MODELS.glob('260-*.MMD')) and (Path(mmd.EXTRACTED) / 'CHDAT/MMD0/TYRA.MMD').exists(),
                     'needs the imported 260 model (edit.py get 260) and the player DW1 extraction')
class BoundRig(unittest.TestCase):
    """The chibi stage of a native binding, shown on MetalTyrannomon's recipe with the stage switched on."""

    @classmethod
    def setUpClass(cls):
        cls.recipe = json.loads(native_binding.MANIFEST.read_text())['260']
        cls.record = json.loads(next((ROOT / 'content/species').glob('260-*.json')).read_text())
        cls.source = next(MODELS.glob('260-*.MMD')).read_bytes()
        cls.plain = native_binding.bind(cls.source, cls.record['model']['skeleton'], cls.recipe)
        staged = dict(copy.deepcopy(cls.recipe), chibi=dict(row='260', factors=dict(leg_axial=1.0)))
        cls.staged = native_binding.bind(cls.source, cls.record['model']['skeleton'], staged)
        row = json.loads(chibi.MANIFEST.read_text())['260']
        cls.groups = chibi.donor_groups(cls.recipe['map'], {int(b): g for b, g in row['groups'].items()})

    def measured(self, built):
        return chibi.proportions(built[0], built[1]['generated_skeleton'], self.groups, 9260)

    def test_the_stage_is_off_unless_the_recipe_asks(self):
        self.assertNotIn('chibi', self.plain[1])
        self.assertIn('chibi', self.staged[1])

    def test_the_head_grows_and_the_height_holds(self):
        before, after = self.measured(self.plain), self.measured(self.staged)
        self.assertGreater(after['head'], before['head'] * 1.1)
        self.assertLess(abs(after['height'] - before['height']), 0.01 * before['height'])

    def test_speeds_floor_and_budget(self):
        report = self.staged[1]['chibi']
        for slot, (low, high) in {'2': (15, 31), '3': (10, 20), '4': (35, 52)}.items():
            self.assertTrue(low <= report['speeds'][slot][1] <= high, (slot, report['speeds'][slot]))
        self.assertLess(report['speeds']['3'][1], report['speeds']['2'][1])
        self.assertLess(report['speeds']['2'][1], report['speeds']['4'][1])
        for slot, floor in report['floors'].items():
            self.assertLessEqual(max(floor['feet_under'], floor['resting_under']), chibi.MAX_SINK, slot)
            self.assertLessEqual(max(floor['feet_over'], floor['resting_over']), chibi.MAX_FLOAT, slot)
        storage = motionstorage.require(self.staged[0], len(self.staged[1]['generated_skeleton']))
        self.assertLess(storage['resident_bytes'], 100352)


if __name__ == '__main__':
    unittest.main()
