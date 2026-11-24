"""The effects of the Darkness, Light, Water, Weapon and Earth rows (tools/technique_effects): each one builds into a chunk of the
machine's size, keeps what it leaves in memory inside what the disc's own effects keep, plays in the simulator to
its end, sounds, and hits what its technique hits (one enemy, or all of them for the area ones). The ones that hit by
position miss a target that walks away. The finishers written the same way (finishers.py) pass the same checks,
against the range of their own design (content/finishers/imports.json)."""
import json
import os
import unittest

from tools import efecompose as E
from tools import efesim as S
from tools.technique_effects import dark, earth, finishers, light, water, weapon

ROWS = {'dark': dark, 'light': light, 'water': water, 'weapon': weapon, 'earth': earth}
KEPT_MAX = 14 * 1024            # the largest of the disc's own effects keeps about 14 KB
# the single-target techniques whose hit is where the target stood, not the target (a shot's flight, a strike's spot)
DODGED = (123, 128, 131, 135, 137, 138, 139, 142, 147, 154, 157)
# the finishers (by species) that fly to where the target stood
FINISHERS_DODGED = (433, 409, 403)


def play(chunk, walk=0):
    """The chunk cast by fighter 1 on fighter 2, two more enemies beside it, at the distance techniques are cast
    from; walk: what the target moves sideways every tick."""
    f = [None] * 10
    f[1] = S.Fighter(-2, (0, 0, 0), 0)
    for k, pos in enumerate(((0, 0, -700), (450, 0, -920), (-450, 0, -920))):
        f[2 + k] = S.Fighter(-2, pos, 0x800)
    sim = S.Sim(chunk, f, 1, 2, seed=1)
    for _ in range(240):
        f[2].pos[0] -= walk
        sim.step(reset_hits=False)
        if not sim.live():
            break
    return sim


def entries(finisher=False):
    with open(os.path.join('content', 'battle', 'own-effects.json')) as f:
        spec = json.load(f)
    return {int(k): e for k, e in spec.items() if k != 'note' and 'authored' in e
            and (e['authored'] == 'finishers') == finisher}


def finisher_moves():
    with open(os.path.join('content', 'finishers', 'imports.json')) as f:
        return {e['species']: e for e in json.load(f)['finishers']}


def own_effect(species):
    name = next(n for n in os.listdir(os.path.join('content', 'species')) if n.startswith(f'{species}-'))
    with open(os.path.join('content', 'species', name)) as f:
        return json.load(f).get('own_effect')


def technique(tid):
    name = next(n for n in os.listdir(os.path.join('content', 'techniques')) if n.startswith(f'{tid}-'))
    with open(os.path.join('content', 'techniques', name)) as f:
        return json.load(f)


class TechniqueEffects(unittest.TestCase):
    def test_every_new_technique_has_its_effect(self):
        e = entries()
        self.assertEqual(sorted(e), list(range(330, 370)))
        for key, entry in e.items():
            self.assertEqual(entry['technique'], key - 330 + 122)
            self.assertIn(entry['technique'], ROWS[entry['authored']].EFFECTS)

    def test_every_authored_finisher_is_its_species_own_effect(self):
        moves = finisher_moves()
        for key, entry in entries(finisher=True).items():
            species = entry['technique']
            with self.subTest(species=species, name=entry['name']):
                self.assertIn(species, finishers.EFFECTS)
                self.assertEqual(moves[species]['name'], entry['name'])
                self.assertEqual(moves[species]['effect']['status'], 'authored')
                own = own_effect(species)
                self.assertEqual(own['chunk'], key)
                self.assertEqual(own['technique'], moves[species]['replaces']['name'])
        self.assertEqual(sorted(e['technique'] for e in entries(finisher=True).values()), sorted(finishers.EFFECTS))

    def test_each_finisher_builds_plays_and_hits(self):
        moves = finisher_moves()
        for key, entry in sorted(entries(finisher=True).items()):
            species = entry['technique']
            with self.subTest(species=species, name=entry['name']):
                chunk, kept = finishers.EFFECTS[species]().build(0x100 + key)
                self.assertEqual(len(chunk), E.CHUNK)
                self.assertLessEqual(kept, KEPT_MAX)
                sim = play(bytes(chunk))
                self.assertFalse(sim.live(), 'still running after 240 ticks')
                self.assertGreaterEqual(sim.tick, 20)
                self.assertTrue(sim.sounds)
                self.assertTrue(sim.sprites or sim.quads)
                wants = [2, 3, 4] if moves[species]['move']['range'] == 3 else [2]
                self.assertEqual(sorted({h[1] for h in sim.hits}), wants)
                if species in FINISHERS_DODGED:
                    self.assertNotIn(2, {h[1] for h in play(bytes(chunk), walk=60).hits})

    def test_each_builds_plays_and_hits(self):
        for key, entry in sorted(entries().items()):
            tid = entry['technique']
            with self.subTest(technique=tid, name=entry['name']):
                chunk, kept = ROWS[entry['authored']].EFFECTS[tid]().build(0x100 + key)
                self.assertEqual(len(chunk), E.CHUNK)
                self.assertLessEqual(kept, KEPT_MAX)
                sim = play(bytes(chunk))
                self.assertFalse(sim.live(), 'still running after 240 ticks')
                self.assertGreaterEqual(sim.tick, 20)
                self.assertTrue(sim.sounds)
                self.assertTrue(sim.sprites or sim.quads)
                hit = sorted({h[1] for h in sim.hits})
                wants = {3: [2, 3, 4]}.get(technique(tid)['range'], [2])    # range 3: every enemy; 4: the caster,
                self.assertEqual(hit, wants)                                # which the game makes the target
                if tid in DODGED:
                    self.assertNotIn(2, {h[1] for h in play(bytes(chunk), walk=60).hits})

if __name__ == '__main__':
    unittest.main()
