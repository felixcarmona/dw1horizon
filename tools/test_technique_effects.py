"""The effects of the Darkness, Light and Water rows (tools/technique_effects): each one builds into a chunk of the
machine's size, keeps what it leaves in memory inside what the disc's own effects keep, plays in the simulator to
its end, sounds, and hits what its technique hits (one enemy, or all of them for the area ones)."""
import json
import os
import struct
import unittest

from tools import efecompose as E
from tools.technique_effects import dark, light, water

ROWS = {'dark': dark, 'light': light, 'water': water}
KEPT_MAX = 14 * 1024            # the largest of the disc's own effects keeps about 14 KB
LAUNCH = struct.pack('<6h', -2, 0, 0, 0, 0, -1)


def entries():
    with open(os.path.join('content', 'battle', 'own-effects.json')) as f:
        spec = json.load(f)
    return {int(k): e for k, e in spec.items() if k != 'note' and 'authored' in e}


def technique(tid):
    name = next(n for n in os.listdir(os.path.join('content', 'techniques')) if n.startswith(f'{tid}-'))
    with open(os.path.join('content', 'techniques', name)) as f:
        return json.load(f)


class TechniqueEffects(unittest.TestCase):
    def test_every_new_technique_has_its_effect(self):
        e = entries()
        self.assertEqual(sorted(e), list(range(330, 354)))
        for key, entry in e.items():
            self.assertEqual(entry['technique'], key - 330 + 122)
            self.assertIn(entry['technique'], ROWS[entry['authored']].EFFECTS)

    def test_each_builds_plays_and_hits(self):
        for key, entry in sorted(entries().items()):
            tid = entry['technique']
            with self.subTest(technique=tid, name=entry['name']):
                chunk, kept = ROWS[entry['authored']].EFFECTS[tid]().build(0x100 + key)
                self.assertEqual(len(chunk), E.CHUNK)
                self.assertLessEqual(kept, KEPT_MAX)
                sim = E.run(bytes(chunk), LAUNCH)
                self.assertFalse(sim.live(), 'still running after 240 ticks')
                self.assertGreaterEqual(sim.tick, 20)
                self.assertTrue(sim.sounds)
                self.assertTrue(sim.sprites or sim.quads)
                hit = sorted({h[1] for h in sim.hits})
                wants = {3: [2, 3, 4]}.get(technique(tid)['range'], [2])    # range 3: every enemy; 4: the caster,
                self.assertEqual(hit, wants)                                # which the game makes the target

if __name__ == '__main__':
    unittest.main()
