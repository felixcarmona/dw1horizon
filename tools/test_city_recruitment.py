"""Extended recruitment at the Python/compiler boundary; the original stays lossless."""
from pathlib import Path
import tempfile
import unittest

from tools.dws import recruitment
from tools.dws.py import lower
from tools.dws import build
from tools.city_residents import membership_bits, residents

ROOT = recruitment.ROOT


class Recruitment(unittest.TestCase):
    def lowered(self, zone, extended=True):
        path = next((ROOT / 'story/base/zones' / zone).glob('*/script.py'))
        with recruitment.story(extended):
            return lower.lower_file(str(path))[1]

    def test_wild_needs_first_win(self):
        source = self.lowered('back-dimension')
        self.assertIn('engine.result == 1 && !is_recruited(species(104))', source)
        self.assertIn('sound(8, 11);', source)
        self.assertIn(f'text("{recruitment.KEY}", species(104))', source)
        self.assertLess(source.index('battle();'), source.index('engine.result == 1'))
        self.assertNotIn('walk_away', source)

    def test_removed_wilds_only_fight(self):
        path = ROOT / 'story/base/zones/underground-lab/s065-68/script.py'
        with recruitment.story(True):
            source = lower.lower_file(str(path))[1]
        self.assertIn('battle();', source)
        self.assertNotIn('recruit(species(101))', source)
        self.assertIn('!is_recruited(species(90))', source)  # Tekkamon

    def test_original_helper_unchanged(self):
        source = self.lowered('back-dimension', False)
        self.assertNotIn(recruitment.KEY, source)
        self.assertIn('recruit(species(104));', source)

    def test_silent_conversation_has_no_stale_battle_guard(self):
        source = self.lowered('back-dimension')
        bare = source[source.index('on talk(bluemeramon3)'):]
        self.assertIn('if (!is_recruited(species(104)))', bare)
        self.assertNotIn('engine.result', bare)

    def test_existing_narrated_departure_keeps_its_scene(self):
        path = ROOT / 'story/base/zones/native-forest/s004-3/script.py'
        with recruitment.story(True):
            source = lower.lower_file(str(path))[1]
        # Etemon's authored departure is left alone; Aruraumon's silent shared code isn't.
        self.assertNotIn(f'text("{recruitment.KEY}", species(42))', source)
        self.assertIn(f'text("{recruitment.KEY}", species(86))', source)

    def test_mod_placed_helper_uses_the_same_policy(self):
        path = ROOT / 'story/mods/examples/src/forest_garurumon.py'
        with recruitment.story(True):
            source = lower.lower_file(str(path))[1]
        self.assertIn('engine.result == 1 && !is_recruited(species(77))', source)
        self.assertIn(f'text("{recruitment.KEY}", species(77))', source)

    def test_following_narration_keeps_its_scene(self):
        source = self.lowered('amida-forest')
        self.assertNotIn(recruitment.KEY, source)

    def test_reward_narration_does_not_hide_a_silent_recruit(self):
        path = ROOT / 'story/base/zones/toy-mansion/s145-151/script.py'
        with recruitment.story(True):
            source = lower.lower_file(str(path))[1]
        self.assertIn(f'text("{recruitment.KEY}", species(70))', source)

    def test_ending_narration_does_not_hide_three_recruits(self):
        path = ROOT / 'story/base/zones/mt-infinity/s184-225/script.py'
        with recruitment.story(True):
            source = lower.lower_file(str(path))[1]
        for species in (7, 12, 6):
            self.assertIn(f'text("{recruitment.KEY}", species({species}))', source)

    def test_templates_compile_in_every_language(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'join.dws'
            path.write_text('import "' + str(ROOT / 'story/core/recruit.dws') + '";\n'
                            'script 3 { on enter { say(narrator, text("' + recruitment.KEY + '", species(104))); } }\n')
            for lang in ('en', 'es', 'ca', 'de', 'fr', 'it', 'ja', 'pt-br'):
                with self.subTest(lang=lang), recruitment.story(True):
                    prog = build.compile_sources([str(path)], 'mods', lang=lang, text_source='ours')
                    self.assertIn(recruitment.KEY, prog.used_text)

    def test_otamamon_keeps_the_swamp_story_flag(self):
        source = self.lowered('geko-swamp')
        self.assertIn('recruit(species("Otamamon"));', source)
        self.assertNotIn(recruitment.KEY, source[source.index('on talk(otamamon)'):])

    def test_membership_is_the_roster(self):
        bits = membership_bits()
        self.assertEqual(len(bits), 14)
        self.assertEqual({i for i in range(112) if bits[i // 8] & (1 << (i % 8))},
                         {r['id'] for r in residents()})


if __name__ == '__main__':
    unittest.main()
