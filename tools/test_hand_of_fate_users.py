"""Hand of Fate (technique 82) only deals damage for species whose effects type has a row in its EFE table (issue 419:
Gatomon had none, so the finisher played its clip and hit nothing)."""
import unittest
import species

HAND_OF_FATE = 82

class HandOfFateUsers(unittest.TestCase):
    def test_every_user_has_an_origin_row(self):
        if not species.efe_rows().get(HAND_OF_FATE):
            raise unittest.SkipTest('needs the extracted disc')
        bad = []
        for t, s in sorted(species.load_content().items()):
            ids = [species.id_of('techs', n, 'test') for n in (s.get('techniques') or []) if n is not None]
            if HAND_OF_FATE in ids and species.technique_origin(s, HAND_OF_FATE) != 'row':
                bad.append(f"{t} {s['name']}")
        self.assertEqual(bad, [])

if __name__ == '__main__':
    unittest.main()
