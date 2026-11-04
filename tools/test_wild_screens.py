"""Placement-only screens inherit pickups without borrowing NPC dialogue."""
import json
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
MOD = ROOT / 'story/mods/what-the-island-forgot'
SOURCE = 'arcs/works/wild-screens.dws'


class WildScreens(unittest.TestCase):
    def test_every_placement_only_screen_has_plain_encounters(self):
        early = (MOD / 'early-game.py').read_text()
        screens = set(map(int, re.findall(r'new_screen\((\d+)', early)))
        text = (MOD / SOURCE).read_text()
        blocks = re.split(r'script new for screen (\d+) \{', text)
        actual = {int(blocks[i]): blocks[i + 1] for i in range(1, len(blocks), 2)}
        self.assertEqual(set(actual), screens)
        for screen, body in actual.items():
            self.assertEqual(re.findall(r'section\((\d+)\) replace \{ battle\(\); \}', body),
                             list(map(str, range(5, 13))), screen)
            self.assertIn('section(51) replace {}', body)
            # Copy the donor enter event: preserve spawn odds and stable pickup IDs.
            self.assertNotIn('empty', body)
            self.assertNotIn('section(254)', body)

    def test_build_paths_include_the_encounter_scripts(self):
        import tomllib
        mod = tomllib.loads((MOD / 'mod.toml').read_text())
        self.assertIn(SOURCE, mod['sources'])
        recipe = json.loads((ROOT / 'tools/derive/recipes/everything.json').read_text())
        self.assertIn(str((MOD / SOURCE).relative_to(ROOT)), recipe['story']['sources'])


if __name__ == '__main__':
    unittest.main()
