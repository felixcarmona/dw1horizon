"""Data-coverage and rule regressions for the offline guide (stdlib only)."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

SPEC = importlib.util.spec_from_file_location('guide_build', Path(__file__).with_name('build.py'))
guide = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(guide)


class GuideTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.commit, cls.moves, species, cls.tree, _ = guide.snapshot('origin/main')
        cls.partners = {s['id']: s for s in species if 'partner' in s}
        cls.page = guide.render(cls.commit, cls.moves, species, cls.tree, 'next')

    def test_complete_partner_and_technique_coverage(self):
        for s in self.partners.values():
            self.assertEqual(self.page.count(f'id="species-{s["id"]}"'), 1)
            for name in s['techniques']:
                if name is None:
                    continue
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
            guide.build(a, self.commit, 'next')
            guide.build(b, self.commit, 'next')
            self.assertTrue((a / 'index.html').is_file())
            self.assertTrue((a / 'es.html').is_file())
            self.assertEqual((a / 'assets/site.css').read_bytes(), (guide.ROOT / 'web/style.css').read_bytes())
            for p in a.rglob('*'):
                if p.is_file():
                    self.assertEqual(p.read_bytes(), (b / p.relative_to(a)).read_bytes())
                    if p.suffix == '.html':
                        self.assertNotRegex(p.read_text(), r'(?:href|src)="https?://')
            self.assertIn(self.commit[:12], (a / 'index.html').read_text())


    def test_release_tag_and_spanish_names(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            commit = guide.build(out, 'v0.0.6')
            self.assertIn('Data for Horizon 0.0.6.', (out / 'index.html').read_text())
            es = (out / 'es.html').read_text()
            self.assertIn('Datos de Horizon 0.0.6.', es)
            self.assertIn('Buscar técnicas', es)
            self.assertIn('Fire Tower', es)
            self.assertNotIn('Fuego Tower', es)
            self.assertIn(commit[:12], es)
            self.assertNotIn('Tsunomon route: weight 21', es)

    def test_all_page_languages_use_their_catalogs(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            guide.build(out, self.commit, 'next')
            for catalog in (guide.ROOT / 'web/i18n').glob('*.json'):
                lang = catalog.stem
                strings = json.loads(catalog.read_text())
                page = (out / ('index.html' if lang == 'en' else lang + '.html')).read_text()
                self.assertIn(f'<html lang="{lang}">', page)
                self.assertIn(strings['data.nav'], page)
                self.assertIn(strings['data.learningRule'], page)
                self.assertIn('Fire Tower', page)

    def test_spanish_compound_requirements(self):
        english = json.loads((guide.ROOT / 'web/i18n/en.json').read_text())
        spanish = json.loads((guide.ROOT / 'web/i18n/es.json').read_text())
        source = '<p>Bonus (any one): from IceDevimon; Happiness ≥ 97 (rounded boundary; 98 guarantees it)</p>'
        result = guide.translate(source, english, spanish)
        self.assertIn('IceDevimon', result)
        self.assertIn('98 lo garantiza', result)
        self.assertNotIn('rounded boundary', result)
        self.assertNotIn('HieloDevimon', result)

    def test_site_overlay_preserves_release_engine_and_disc_metadata(self):
        spec = importlib.util.spec_from_file_location('web_build', guide.ROOT / 'web/build.py')
        site = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(site)
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            for name in ('data/discs.json', 'engine/current.json'):
                path = out / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text('release sentinel')
            site.build(out, 'v0.0.7')
            for name in ('data/discs.json', 'engine/current.json'):
                self.assertEqual((out / name).read_text(), 'release sentinel')
            self.assertTrue((out / 'data/index.html').is_file())
            self.assertTrue((out / 'data/es.html').is_file())
            self.assertIn('href="wiki/"', (out / 'index.html').read_text())

    def test_displayed_mp_exempts_finishers(self):
        self.assertEqual(guide.base_mp(guide.resolve_move('Fire Tower', self.moves)), 81)
        self.assertEqual(guide.base_mp(guide.resolve_move('Pepper Breath', self.moves)), 0)


if __name__ == '__main__':
    unittest.main()
