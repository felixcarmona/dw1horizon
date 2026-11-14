"""Every raisable species' finisher has been seen damaging an enemy in the emulator (issue 419: Gatomon's Hand of Fate
played its clip and hit nothing). docs/data/finisher-proof.json comes from tools/dev/playtest/finisher_targets.py runs
merged by finisher_proof_merge.py. Changing a species' finisher means proving the new one and recording it."""
import json
import os
import unittest
import species

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FINISHERS = range(58, 113)


class FinisherProof(unittest.TestCase):
    def test_every_raisable_species_finisher_is_proven(self):
        data = json.load(open(os.path.join(ROOT, 'docs', 'data', 'finisher-proof.json')))
        proof, unproven = data['proven'], data['unproven']
        missing = []
        for t, s in sorted(species.load_content().items()):
            if 'partner' not in s: continue
            ids = [species.id_of('techs', n, 'test') for n in (s.get('techniques') or []) if n is not None]
            fin = [m for m in ids if m in FINISHERS]
            if not fin: continue
            if str(t) in unproven: continue
            p = proof.get(str(t))
            if not p or p['finisher'] != fin[0] or p['enemy_damage'] <= 0:
                missing.append(f"{t} {s['name']} finisher {fin[0]}: " + (str(p) if p else 'not proven'))
        self.assertEqual(missing, [], 'prove with finisher_targets, then finisher_proof_merge.py')

    def test_unproven_species_are_not_also_proven(self):
        data = json.load(open(os.path.join(ROOT, 'docs', 'data', 'finisher-proof.json')))
        self.assertEqual(sorted(set(data['unproven']) & set(data['proven'])), [], 'proven now: drop it from unproven')


if __name__ == '__main__':
    unittest.main()
