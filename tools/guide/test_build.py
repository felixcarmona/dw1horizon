"""Data-coverage and rule regressions for the offline guide (stdlib only)."""
import importlib.util
from pathlib import Path
import tempfile
import unittest

SPEC = importlib.util.spec_from_file_location('guide_build', Path(__file__).with_name('build.py'))
guide = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(guide)


class GuideTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.commit, cls.moves, species, cls.tree, _ = guide.snapshot()
        cls.partners = {s['id']: s for s in species if 'partner' in s}
        cls.page = guide.render(cls.commit, cls.moves, species, cls.tree, 'next')

    def test_complete_partner_and_technique_coverage(self):
        for s in self.partners.values():
            self.assertEqual(self.page.count(f'id="species-{s["id"]}"'), 1)
            for name in s['techniques']:
                self.assertIn(guide.resolve_move(name, self.moves), self.moves)
        for t in self.moves:
            self.assertIn(f'#{t["id"]} · ', self.page)
        self.assertEqual(self.page.count('<tr>') + self.page.count('<tr id='),
                         len(self.moves) + 2 * len(self.partners) + 3)

    def test_specialty_gap_uses_third_column(self):
        s = self.partners[3]  # fire / empty / battle
        t = guide.resolve_move('Sonic Jab', self.moves)
        self.assertEqual(guide.chance(s, t), t['learnChances'][2])
        self.assertIsNone(guide.chance({'specialties': ['ice', None, None]}, t))

    def test_shared_names_resolve_by_explicit_id(self):
        self.assertEqual(guide.resolve_move('Dynamite Kick (48)', self.moves)['id'], 48)
        self.assertEqual(guide.resolve_move('Dynamite Kick (44)', self.moves)['id'], 44)
        self.assertEqual(guide.resolve_move('Bubble (119)', self.moves)['id'], 119)

    def test_player_units_and_route_override(self):
        row = guide.requirements(self.partners[248], self.partners, self.tree)
        self.assertIn('MP ≥ 5000', row)
        self.assertIn('Happiness ≥ 90', row)
        self.assertIn('Care mistakes ≤ 5', row)
        self.assertIn('weight 21–31', guide.requirements(self.partners[17], self.partners, self.tree))
        self.assertIn('Fixed growth', guide.requirements(self.partners[1], self.partners, self.tree))
        rounded = dict(self.partners[248], evolution={'requirements': dict(
            self.partners[248]['evolution']['requirements'], happiness=95)}, id=-1)
        self.assertIn('Happiness ≥ 97 (rounded boundary; 98 guarantees it)',
                      guide.requirements(rounded, self.partners, self.tree))

    def test_deterministic_offline_build(self):
        with tempfile.TemporaryDirectory() as tmp:
            a, b = Path(tmp) / 'a', Path(tmp) / 'b'
            guide.build(a, self.commit)
            guide.build(b, self.commit)
            self.assertEqual(sorted(p.relative_to(a) for p in a.rglob('*') if p.is_file()),
                             [Path('assets/guide.js'), Path('assets/style.css'), Path('index.html')])
            for p in a.rglob('*'):
                if p.is_file():
                    self.assertEqual(p.read_bytes(), (b / p.relative_to(a)).read_bytes())
                    self.assertNotIn(b'https://', p.read_bytes())
                    self.assertNotIn(b'http://', p.read_bytes())
            self.assertIn(self.commit[:12], (a / 'index.html').read_text())


if __name__ == '__main__':
    unittest.main()
