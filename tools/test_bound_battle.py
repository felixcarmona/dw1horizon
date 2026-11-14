"""The source game's battle clips on a model bound offline (tools/models/field_animations/bound_battle.py).

The recipe and the arithmetic are checked here with no game data. Set DW_BOUND_BATTLE_MODELS to an imported-models
folder (a derive build's, or edit.py's base folder) holding 206.MMD and 206.battle.MMD to check the overlay itself:
field and care slots byte for byte, the compacted clips the same ticks, the buffer within its budget.
"""
import hashlib
import json
import math
import os
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'tools'), str(ROOT / 'tools/models')]

from tools.models.field_animations import bound_battle, native_battle  # noqa: E402


def _rz(a):
    return [[math.cos(a), -math.sin(a), 0], [math.sin(a), math.cos(a), 0], [0, 0, 1]]


def _rx(a):
    return [[1, 0, 0], [0, math.cos(a), -math.sin(a)], [0, math.sin(a), math.cos(a)]]


class Arithmetic(unittest.TestCase):
    def close(self, a, b, eps=1e-9):
        for ra, rb in zip(a, b):
            for x, y in zip(ra, rb):
                self.assertAlmostEqual(x, y, delta=eps)

    def test_affine_recovers_a_map(self):
        m = native_battle._mul(_rz(0.4), [[1.2, 0, 0], [0, 0.7, 0], [0, 0, 1.1]])
        x = [[1, 2, 3], [-4, 0, 2], [5, -1, 0], [0, 3, -2], [2, 2, 2]]
        y = [[sum(m[i][j] * p[j] for j in range(3)) + t for i, t in zip(range(3), (5, -7, 9))] for p in x]
        self.close(bound_battle.affine(x, y), m, 1e-9)

    def test_rotation_of_a_rotation_a_stretch_and_a_flat_piece(self):
        r = native_battle._mul(_rz(0.3), _rx(-1.1))
        self.close(bound_battle.rotation(r), r)
        self.close(bound_battle.rotation(native_battle._mul(r, [[2, 0, 0], [0, 0.5, 0], [0, 0, 1.5]])), r)
        flat = native_battle._mul(r, [[1.5, 0, 0], [0, 0.8, 0], [0, 0, 0]])      # a planar piece: rank 2
        self.close(bound_battle.rotation(flat), r)

    def test_rotation_of_a_reflection_turns(self):
        out = bound_battle.rotation(native_battle._mul(_rz(0.5), [[1, 0, 0], [0, 1, 0], [0, 0, -0.2]]))
        a, b, c = out
        det = a[0]*(b[1]*c[2]-b[2]*c[1]) - a[1]*(b[0]*c[2]-b[2]*c[0]) + a[2]*(b[0]*c[1]-b[1]*c[0])
        self.assertAlmostEqual(det, 1.0, delta=1e-9)
        self.close(native_battle._mul(out, native_battle._tr(out)), [[1, 0, 0], [0, 1, 0], [0, 0, 1]])


class Recipe(unittest.TestCase):
    def test_every_row_is_wired_and_pinned(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location('imported_species_test', ROOT / 'content/models/imports/species.py')
        species = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(species)
        registry = json.loads((ROOT / 'content/models/imports/models.json').read_text())
        batches = json.loads((ROOT / 'content/modeldelta/import-batches.json').read_text())['recipes']
        made = {f'{r["out"]}/{r["entry"]["name"]}.MMD': r for r in batches}
        from tools.derive.steps import imports
        for sid, row in bound_battle.rows().items():
            with self.subTest(species=sid):
                overlay = species.OVERLAYS[registry[sid]['field_overlay']]
                self.assertEqual(overlay[:2], (sid, 'tools.models.field_animations.bound_battle'))
                recipe = made[row['battle_source']['path']]
                self.assertTrue(recipe['entry']['battle_source'])
                source = (ROOT / recipe['spec']).read_bytes()
                self.assertEqual(hashlib.sha256(source).hexdigest(), recipe['spec_sha256'])
                self.assertEqual(json.loads(source)['format'], 'native-battle-source-v1')
                bound_battle.binding_spec(row)                       # its pin holds
                self.assertIn(f'imported-models/{sid}.battle.MMD', imports.files(sid))
                # battle and technique slots only; compaction never reaches a field or care slot
                self.assertTrue(all(s >= native_battle.IDLES[0] for s in row['slots']))
                self.assertTrue(set(row.get('keep_events', ())) <= set(row['slots']))
                self.assertGreaterEqual(row.get('compact_from', native_battle.IDLES[0]), native_battle.IDLES[0])
                with self.assertRaises(ValueError):
                    bound_battle.compact(b'', 26, native_battle.IDLES[0] - 1)

    def test_drop_npc_slots_leaves_only_their_clips_out(self):
        # the NPC slots' clips go, a clip an NPC slot shares with a kept slot stays, the order of the rest is kept
        from tools.models.field_animations import native_binding
        table = [None] * 0x2D
        table[0], table[0x14], table[0x1C], table[0x21], table[0x1D], table[0x22] = 0, 1, 2, 3, 3, 4
        out_table, out_anims = bound_battle.without_npc_slots(table, ['idle', 'npc', 'kart', 'battle', 'battle2'])
        self.assertTrue(all(out_table[s] is None for s in native_binding.NPC_SLOTS))
        self.assertEqual(out_anims, ['idle', 'battle', 'battle2'])
        self.assertEqual([out_anims[out_table[s]] for s in (0, 0x21, 0x22)], ['idle', 'battle', 'battle2'])


class Model(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        folder = os.environ.get('DW_BOUND_BATTLE_MODELS')
        if not folder:
            raise unittest.SkipTest('set DW_BOUND_BATTLE_MODELS to an imported-models folder')
        cls.folder = Path(folder)

    def test_magnaangemon(self):
        import animsheet
        import mmd
        import motionstorage
        row = bound_battle.rows()['206']
        data = (self.folder / '206.MMD').read_bytes()
        skeleton = json.loads((ROOT / 'content/species/206-magnaangemon.json').read_text())['model']['skeleton']
        bound_battle.BASE_MODELS = str(self.folder)
        try:
            out, proof = bound_battle.build(data, skeleton)
        finally:
            bound_battle.BASE_MODELS = None
        self.assertEqual(sorted(int(s) for s in proof['battle_originals']), row['slots'])
        self.assertTrue(motionstorage.audit(out, 26)['fits'])
        before, after = mmd.MMD.parse(data, 26), mmd.MMD.parse(out, 26)
        stream = lambda m, s: None if m.anims.table[s] is None else m.anims.anims[m.anims.table[s]].build()  # noqa: E731
        from tools.models.field_animations import native_binding
        dropped = set(native_binding.NPC_SLOTS) if row.get('drop_npc_slots') else set()
        for slot in range(len(before.anims.table)):
            if slot in dropped:
                self.assertIsNone(after.anims.table[slot], f'NPC slot {slot}')
            elif slot < native_battle.IDLES[0]:
                self.assertEqual(stream(after, slot), stream(before, slot), f'field/care slot {slot}')
            elif slot not in row['slots'] and before.anims.table[slot] is not None:
                self.assertEqual(animsheet.slot_frames(after, 26, slot), animsheet.slot_frames(before, 26, slot), slot)
        for slot in row.get('keep_events', ()):
            self.assertEqual(animsheet.slot_frames(after, 26, slot)[2], animsheet.slot_frames(before, 26, slot)[2])
        self.assertEqual(after.tmd.build(), before.tmd.build())


if __name__ == '__main__':
    unittest.main()
