"""Extended recruitment at the Python/compiler boundary; the original stays lossless."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import json

from tools.dws import recruitment
from tools.dws.py import lower
from tools.dws import build, bytecode, backend
from tools import city_residents as city
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

    def test_high_species_through_python_and_roster_gate(self):
        source = """from dw import *
area = screen(3)
resident = area.npc(Species.Wizardmon, slot=5, at=(0, 0), when=recruited(Species.Wizardmon))
@resident.on_talk
def talk():
    recruit(Species.Wizardmon)
    if recruited(Species.Wizardmon):
        unrecruit(Species.Wizardmon)
"""
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            path = root / 'story/mods/fixture/src/resident.py'
            path.parent.mkdir(parents=True)
            path.write_text(source)
            roster = root / 'roster.json'
            roster.write_text('[{"id":241,"hidden":false}]')
            with patch.object(city, 'ROSTER', roster), patch.object(recruitment, 'roster', return_value={241}), recruitment.story(True):
                prog = build.compile_sources([str(path)], 'species', text_source='ours')
                code = '\n'.join(prog.b.scripts[4]['events'][0][2])
                self.assertIn('SET_TRIGGER 33009', code)
                self.assertIn('UNSET_TRIGGER 33009', code)
                self.assertIn('IF not trigger 33009', code)  # announcement's first-recruit guard
                self.assertIn(recruitment.KEY, prog.used_text)
                rule = prog.b.city['presence'][3]['npcs'][0][3]
                self.assertEqual(backend.presence_if(rule, 3, 5), 'trigger 33009')
                script = ('.section 0 setup\n.section 10 start\nsetup:\nIF ' +
                          backend.presence_if(rule, 3, 5) + ', else hidden\nhidden:\nEND_SCRIPT\nstart:\n' +
                          code + '\nEND_SCRIPT\n')
                compiled = root / 'DG.SCN'
                compiled.write_bytes(bytecode.assemble_script(script, 'high resident')[0])
                self.assertEqual(city.compiled_recruits(compiled), {241})
                self.assertEqual(city.verify([compiled]), 1)
                self.assertEqual(city.membership_bits(), bytes(14))
                self.assertIn('= {241};', city.extra_header())
                # An additional imported recruit is still refused by the exact gate.
                extra = bytecode.assemble_script('.section 0 s\ns:\nSET_TRIGGER 33041\nEND_SCRIPT', 'unlisted')[0]
                unlisted = root / 'MAPHEAD.SCN'
                unlisted.write_bytes(extra)
                with self.assertRaisesRegex(ValueError, r'unlisted \[273\]'):
                    city.verify([compiled, unlisted])

    def test_high_send_to_city_and_recruit_tests(self):
        source = """from dw import *
area = screen(3)
resident = area.npc(Species.Datamon, slot=5, at=(0, 0), when=not recruited(Species.Datamon))
@resident.on_talk
def talk():
    send_to_city(species=Species.Datamon, line="Going.")
"""
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'story/mods/fixture/src/resident.py'
            path.parent.mkdir(parents=True)
            path.write_text(source)
            prog = build.compile_sources([str(path)], 'species', text_source='ours')
            code = '\n'.join(prog.b.scripts[4]['events'][0][2])
            self.assertIn('SET_TRIGGER 33062', code)
            rule = prog.b.city['presence'][3]['npcs'][0][3]
            self.assertEqual(backend.presence_if(rule, 3, 5), 'not trigger 33062')
            with self.assertRaises(build.DwsErrors):
                build.compile_sources([str(path)], 'original', text_source='ours')

    def test_recruit_operand_boundaries_and_original_bytes(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'recruits.dws'
            for species in (0, 111, 112, 124, 179, 241, 273, 290, 294, 1023):
                with self.subTest(species=species):
                    path.write_text(f'script 1 {{ on enter {{ recruit(species({species})); '
                                    f'if (is_recruited(species({species}))) {{ unrecruit(species({species})); }} }} }}')
                    prog = build.compile_sources([str(path)], 'species', text_source='ours')
                    code = '\n'.join(prog.b.scripts[1]['events'][0][2])
                    operand = 200 + species if species < 112 else 0x8000 + species
                    self.assertIn(f'SET_TRIGGER {operand}', code)
                    self.assertIn(f'UNSET_TRIGGER {operand}', code)
                    if species < 112:
                        old = build.compile_sources([str(path)], 'original', text_source='ours')
                        self.assertEqual(prog.b.scripts[1]['events'][0][2], old.b.scripts[1]['events'][0][2])
                    else:
                        with self.assertRaises(build.DwsErrors):
                            build.compile_sources([str(path)], 'original', text_source='ours')
            for species in (-1, 1024, 65535):
                for action in ('recruit', 'unrecruit', 'is_recruited'):
                    with self.subTest(species=species, action=action):
                        body = f'{action}(species({species}));' if action != 'is_recruited' else f'if (is_recruited(species({species}))) {{ return; }}'
                        path.write_text('script 1 { on enter { ' + body + ' } }')
                        with self.assertRaises(build.DwsErrors):
                            build.compile_sources([str(path)], 'species', text_source='ours')

    def test_membership_is_the_roster(self):
        bits = membership_bits()
        self.assertEqual(len(bits), 14)
        self.assertEqual({i for i in range(112) if bits[i // 8] & (1 << (i % 8))},
                         {r['id'] for r in residents()})


if __name__ == '__main__':
    unittest.main()
