"""Every raisable species' finisher has been seen damaging an enemy in the emulator (issue 419: Gatomon's Hand of Fate
played its clip and hit nothing). docs/data/finisher-proof.json comes from tools/dev/playtest/finisher_targets.py runs
merged by finisher_proof_merge.py. "proven" means every trial hit; a finisher that hits only sometimes is listed under
"conditional" and one that never hit under "unproven", each with its reason. Changing a species' finisher means
proving the new one and recording it."""
import json
import os
import unittest
import species

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FINISHERS = range(58, 113)


def load():
    return json.load(open(os.path.join(ROOT, 'docs', 'data', 'finisher-proof.json')))


class FinisherProof(unittest.TestCase):
    def test_every_raisable_species_finisher_is_recorded(self):
        data = load()
        missing = []
        for t, s in sorted(species.load_content().items()):
            if 'partner' not in s: continue
            ids = [species.id_of('techs', n, 'test') for n in (s.get('techniques') or []) if n is not None]
            fin = [m for m in ids if m in FINISHERS]
            if not fin: continue
            k = str(t)
            if k in data['conditional'] or k in data['unproven']: continue
            p = data['proven'].get(k)
            if not p or p['finisher'] != fin[0] or p['enemy_damage'] <= 0 or p['trials'] < 1:
                missing.append(f"{t} {s['name']} finisher {fin[0]}: " + (str(p) if p else 'not proven'))
        self.assertEqual(missing, [], 'prove with finisher_targets, then finisher_proof_merge.py')

    def test_lists_do_not_overlap_and_give_reasons(self):
        data = load()
        lists = [set(data['proven']), set(data['conditional']), set(data['unproven'])]
        for i in range(3):
            for j in range(i + 1, 3):
                self.assertEqual(sorted(lists[i] & lists[j]), [], 'a species is in two lists')
        for name in ('conditional', 'unproven'):
            for k, why in data[name].items():
                self.assertGreater(len(why), 40, f'{name} {k} needs a reason with numbers')


if __name__ == '__main__':
    unittest.main()
