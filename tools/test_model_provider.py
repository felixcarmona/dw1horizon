"""Characterize the dynamic overlay registry before changing provider paths and labels."""
import hashlib
import json
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from tools.derive.steps import species

from tools.derive.steps.overlays import imported_models as provider


class ModelProvider(unittest.TestCase):
    def test_editor_pins_final_provider_output_without_a_field_overlay(self):
        from tools.models import edit

        self.assertNotIn('field_overlay', edit.import_records()['182'])

        def generate(out, sid, generate):
            base = Path(module.BASE_MODELS)
            model = Path(out).with_suffix('.MMD')
            texture = base / f'{sid}.TIM'
            model.write_bytes((base / f'{sid}.MMD').read_bytes() + b'dash repair')
            return 'model.json', {'model': {'file': str(model)}, 'texture': {'file': str(texture)}}

        module = SimpleNamespace(species_file=generate)
        spec = SimpleNamespace(loader=SimpleNamespace(exec_module=Mock()))
        with patch.object(edit.importlib.util, 'spec_from_file_location', return_value=spec), \
                patch.object(edit.importlib.util, 'module_from_spec', return_value=module):
            actual = edit.provider_pin(182, b'base model', b'texture')
        self.assertEqual(actual, [hashlib.sha1(b'base modeldash repair').hexdigest(),
                                  hashlib.sha1(b'texture').hexdigest()])

    def test_generated_base_folder_is_forwarded_to_the_imported_provider(self):
        make = Mock(return_value={'183': ('/model.MMD', '/model.TIM')})
        module = SimpleNamespace(make=make)
        spec = SimpleNamespace(loader=SimpleNamespace(exec_module=Mock()))
        context = SimpleNamespace(path=lambda name: '/build/' + name)
        with patch.object(species.importlib.util, 'spec_from_file_location', return_value=spec), \
                patch.object(species.importlib.util, 'module_from_spec', return_value=module):
            actual = species.ImportedModels(None).provide_models(context, generate=False)
        self.assertEqual(module.BASE_MODELS, '/build/imported-models')
        make.assert_called_once_with('/build/imported-species', generate=False)
        self.assertEqual(actual, {'183': ('/model.MMD', '/model.TIM')})

    def test_every_reviewed_overlay_keeps_its_species_generator_and_output(self):
        model = provider()
        records = model.records()
        self.assertEqual(len(records), 183)  # the 175 source-game imports and the eight hand-made babies
        selected = {t: model.OVERLAYS[e['field_overlay']]
                    for t, e in records.items() if e.get('field_overlay')}
        # These overlays follow already baked field work; cover the live
        # generators separately while retaining the earlier authoring history.
        following = {
            '307': ('307', 'tools.models.field_animations.black_king_numemon', '307-blackkingnumemon-slug'),
            '183': ('183', 'tools.models.field_animations.native_binding', '183-wormmon-native-crawl'),
            # BomberNanimon wears Nanimon's rig and programs; its boxer clips stay as the scale lock's provenance.
            '232': ('232', 'tools.models.field_animations.native_binding', '232-bombernanimon-native'),
            # Wizardmon wears Angemon's rig and programs (its cape and hair follow); its paced gait was retired with it.
            '241': ('241', 'tools.models.field_animations.wizardmon_native', '241-wizardmon-native'),
            # Sorcermon is Wizardmon's body: the same rig, programs and followers.
            '242': ('242', 'tools.models.field_animations.sorcermon_native', '242-sorcermon-native'),
            # VioletElecmon wears native Elecmon's rig and programs.
            '256': ('256', 'tools.models.field_animations.native_binding', '256-violetelecmon-native'),
            # Deltamon wears native Tyrannomon's rig and programs.
            '292': ('292', 'tools.models.field_animations.native_binding', '292-deltamon-native'),
            # ChaosLord wears native Machinedramon's rig and programs.
            '289': ('289', 'tools.models.field_animations.native_binding', '289-chaoslord-native'),
            # GrapLeomon wears native Leomon's rig and programs, with four turning drums.
            '306': ('306', 'tools.models.field_animations.native_binding', '306-grapleomon-native'),
            # Minotarumon wears native Ogremon's rig and programs.
            '330': ('330', 'tools.models.field_animations.native_binding', '330-minotarumon-native'),
            # NeoCrimson wears WarGreymon's rig, its parts bound by the recipe, and WarGreymon's gait (neocrimson_wg_gait.py).
            '402': ('402', 'tools.models.field_animations.native_binding', '402-neocrimson-native'),
            # Vilemon wears native Ogremon's rig and programs.
            '295': ('295', 'tools.models.field_animations.native_binding', '295-vilemon-native'),
            # HiAndromon wears native Andromon's rig and programs.
            '302': ('302', 'tools.models.field_animations.native_binding', '302-hiandromon-native'),
            # KingEtemon wears native Etemon's rig and programs.
            '303': ('303', 'tools.models.field_animations.native_binding', '303-kingetemon-native'),
            # SkullSatamon wears a native donor's rig and programs.
            '314': ('314', 'tools.models.field_animations.native_binding', '314-skullsatamon-native'),
            # WarGrowlmon wears Growlmon's rig and programs (the donor is an imported species: `donor_species`).
            '326': ('326', 'tools.models.field_animations.native_binding', '326-wargrowlmon-native'),
            # Maildramon wears native Unimon's rig and programs, its legs planted by a gait stage (maildramon_gait.py).
            '324': ('324', 'tools.models.field_animations.native_binding', '324-maildramon-native'),
            # Assaultmon wears native Centarumon's rig and programs.
            '310': ('310', 'tools.models.field_animations.native_binding', '310-assaultmon-native'),
            # PrinceMamemon wears native Mamemon's rig and programs.
            '270': ('270', 'tools.models.field_animations.native_binding', '270-princemamemon-native'),

            # MetalTyrannomon wears native Tyrannomon's rig and programs.
            '260': ('260', 'tools.models.field_animations.native_binding', '260-metaltyrannomon-native'),
            '187': ('187', 'tools.models.field_animations.followthrough', '187-stingmon-wing-followthrough'),
            '239': ('239', 'tools.models.field_animations.followthrough', '239-gizamon-active-gait'),
            # LadyDevimon's flight (ladydevimon_flight.py) is written over her baked chibi delta.
            '223': ('223', 'tools.models.field_animations.ladydevimon_flight', '223-ladydevimon-flight'),
            # Quetzalmon's flight (quetzalmon_flight.py) is written over its reviewed import delta.
            '249': ('249', 'tools.models.field_animations.quetzalmon_flight', '249-quetzalmon-flight'),
        }
        for sid, expected in following.items():
            self.assertEqual(selected.pop(sid), expected)
        # Silphymon's repaired walk is baked into its plain delta. Keep the
        # preceding field recipe covered without applying it over that repair.
        self.assertEqual(records['226'], {'model': '226-Silphymon.MMD', 'aliases_applied': True})
        selected['226'] = model.OVERLAYS['silphymon-field']
        # Gesomon's walk, run, idle and tired walk are baked into its plain delta (gesomon.py, gesomon_rest.py).
        self.assertEqual(records['240'], {'model': '240-Gesomon.MMD', 'aliases_applied': True, 'movement_sound': 17})
        selected['240'] = model.OVERLAYS['gesomon-terrestrial']
        # Solarmon's whole gears and its four distinct gaits are baked into its plain delta (solarmon_gaits.py); the
        # recipe chain stays registered as the source they were authored over.
        self.assertEqual(records['251'], {'model': '251-Solarmon.MMD', 'aliases_applied': True})
        selected['251'] = model.OVERLAYS['solarmon-steady-hover']
        # Baked deltas retain their effective field generator as authoring provenance.
        for path in [*Path('content/modeldelta/scale-locks').glob('*.json'),
                     *Path('content/modeldelta/resizes').glob('*.json')]:
            proof = json.loads(path.read_text())
            sid = str(proof['species'])
            self.assertTrue(records[sid]['aliases_applied'])
            if sid not in following:
                self.assertNotIn('field_overlay', records[sid])
            preceding = proof['preceding_provider'].get('field_overlay')
            if preceding:
                self.assertNotIn(sid, selected)
                selected[sid] = model.OVERLAYS[preceding]
        # Native locomotion is authored after the effective field proportions.
        # Keep those baked generators covered without running them a second time.
        for path in [*Path('content/models/authoring').glob('*.json'),
                     *Path('content/models/authoring/native-polish').glob('*.json'),
                     *Path('content/models/authoring/gait-refinement').glob('*.json'),
                     *Path('content/models/authoring/animal-refinement').glob('*.json')]:
            proof = json.loads(path.read_text())
            preceding = proof.get('preceding_provider', {}).get('field_overlay')
            if preceding:
                sid = str(proof['species'])
                self.assertTrue(records[sid]['aliases_applied'])
                if sid not in following:
                    self.assertNotIn('field_overlay', records[sid])
                self.assertNotIn(sid, selected)
                selected[sid] = model.OVERLAYS[preceding]
        # Reviewed native-donor deltas retain their old overlay as provenance.
        reviewed = json.loads(Path('content/modeldelta/reviewed-motion.json').read_text())
        for sid, proof in reviewed['models'].items():
            preceding = proof.get('preceding_provider', {}).get('field_overlay')
            if preceding:
                self.assertTrue(records[sid]['aliases_applied'])
                self.assertNotIn('field_overlay', records[sid])
                self.assertNotIn(sid, selected)
                selected[sid] = model.OVERLAYS[preceding]
        celebrations = json.load(open('content/models/imports/celebrations.json'))
        # Magnamon's native binding (with its own field walk and run) supersedes its retained authoring recipe.
        active = dict(model.OVERLAYS)
        previous_magnamon = active.pop('magnamon-field')
        self.assertEqual(previous_magnamon,
                         ('197', 'tools.models.field_animations.gaits', '197-magnamon-field'))
        # Flamedramon's walk and run authored on its own skeleton (flamedramon.py, baked into its delta) replace the
        # procedural stride; the profile stays registered as the source that clip was authored from.
        previous_flamedramon = active.pop('flamedramon-field')
        self.assertEqual(previous_flamedramon,
                         ('195', 'tools.models.field_animations.gaits', '195-flamedramon-field'))
        self.assertNotIn('field_overlay', records['195'])
        self.assertEqual(len(selected)+len(following), len(active))
        self.assertEqual(set(selected.values()) | set(following.values()), set(active.values()))
        for species, (bound_species, _, _) in selected.items():
            self.assertEqual(species, bound_species)
        assignments = {t: entry[1:] for t, entry in selected.items()}
        self.assertEqual(assignments.pop('236'),
                         ('tools.models.field_animations.native_binding', '236-demidevimon-native-flight'))
        # Lillymon's field flight (lillymon_flight.py) runs after its celebration overlay and replays it first.
        self.assertEqual(assignments['209'],
                         ('tools.models.field_animations.lillymon_flight', '209-lillymon-native-flight'))
        assignments['209'] = ('tools.models.field_animations.celebrations', '209-lillymon-native-flight')

        # Magnadramon's field flight (magnadramon_flight.py) runs after its steady glide and replays it first.
        self.assertEqual(assignments['215'],
                         ('tools.models.field_animations.magnadramon_flight', '215-magnadramon-glide'))
        assignments['215'] = ('tools.models.field_animations.gliding', '215-magnadramon-glide')
        # Dolphmon's gaits (dolphmon_gaits.py) run after its native swim (dolphmon.py) and replay it first.
        self.assertEqual(assignments['238'], ('tools.models.field_animations.dolphmon_gaits', '238-dolphmon-gaits'))
        assignments['238'] = ('tools.models.field_animations.dolphmon', '238-dolphmon-native-swim')
        self.assertEqual(assignments['197'],
                         ('tools.models.field_animations.magnamon', '197-magnamon-native'))
        assignments['197'] = previous_magnamon[1:]
        assignments['195'] = previous_flamedramon[1:]
        # Creepymon's clips (creepymon_gait.py) run on the celebration build and replace its field slots.
        self.assertEqual(assignments['312'], ('tools.models.field_animations.creepymon_gait', '312-creepymon-chibi'))
        assignments['312'] = ('tools.models.field_animations.celebrations', '312-creepymon-chibi')

        # Pharaohmon's tired walk and run (pharaohmon_gait.py) run on top of the celebrations recipe.
        self.assertEqual(assignments['319'], ('tools.models.field_animations.pharaohmon_gait', '319-pharaohmon-chibi'))
        assignments['319'] = ('tools.models.field_animations.celebrations', '319-pharaohmon-chibi')
        # Celebration curves run after the final proportions. Unwrap them to
        # keep guarding all the original field recipes and output names.
        for sid, row in celebrations.items():
            self.assertEqual(assignments[sid][0], 'tools.models.field_animations.celebrations')
            if row.get('base_generator'):
                assignments[sid] = (row['base_generator'], assignments[sid][1])
            else:
                del assignments[sid]
        # Snatchmon's touched-up walk, tired walk and run (snatchmon_polish.py) run on top of its chibi proportions.
        self.assertEqual(assignments['331'], ('tools.models.field_animations.snatchmon_polish', '331-snatchmon-chibi'))
        assignments['331'] = ('tools.models.field_animations.chibi', '331-snatchmon-chibi')
        # Hookmon's corrected clips (hookmon_polish.py) run on top of its chibi proportions and rebuild them first.
        self.assertEqual(assignments['299'], ('tools.models.field_animations.hookmon_polish', '299-hookmon-chibi'))
        assignments['299'] = ('tools.models.field_animations.chibi', '299-hookmon-chibi')
        # So are Kyukimon's walk, tired walk and run (kyukimon_gait.py).
        self.assertEqual(assignments['322'], ('tools.models.field_animations.kyukimon_gait', '322-kyukimon-chibi'))
        assignments['322'] = ('tools.models.field_animations.chibi', '322-kyukimon-chibi')
        # So are Dinohyumon's (dinohyumon_gait.py).
        self.assertEqual(assignments['308'], ('tools.models.field_animations.dinohyumon_gait', '308-dinohyumon-chibi'))
        assignments['308'] = ('tools.models.field_animations.chibi', '308-dinohyumon-chibi')
        # Knightmon's tired walk and run (knightmon_gait.py) are the celebration's base generator and rebuild its chibi proportions first.
        self.assertEqual(assignments['321'], ('tools.models.field_animations.knightmon_gait', '321-knightmon-chibi'))
        assignments['321'] = ('tools.models.field_animations.chibi', '321-knightmon-chibi')
        # And Gargoylemon's (gargoylemon_gait.py).
        self.assertEqual(assignments['327'], ('tools.models.field_animations.gargoylemon_gait', '327-gargoylemon-chibi'))
        assignments['327'] = ('tools.models.field_animations.chibi', '327-gargoylemon-chibi')
        # Antylamon's smoothed walk (antylamon_polish.py) runs on top of its chibi proportions the same way.
        self.assertEqual(assignments['309'], ('tools.models.field_animations.antylamon_polish', '309-antylamon-chibi'))
        assignments['309'] = ('tools.models.field_animations.chibi', '309-antylamon-chibi')
        # The chibi proportions wrap the recipe that came before them; species without one have no other generator.
        chibi = json.load(open('content/models/imports/chibi.json'))
        for sid, row in chibi.items():
            if row.get('applied_by') == 'native_binding':        # the row is the last stage of the species' native binding
                continue
            self.assertEqual(assignments[sid][0], 'tools.models.field_animations.chibi')
            if row['base_generator']:
                assignments[sid] = (row['base_generator'], assignments[sid][1])
            else:
                del assignments[sid]
        # The field pace pass wraps the recipe that came before it; species without one have no other generator.
        paced = json.load(open('content/models/imports/pace.json'))
        for sid, row in paced.items():
            self.assertEqual(assignments[sid][0], 'tools.models.field_animations.pace')
            if row['base_generator']:
                assignments[sid] = (row['base_generator'], assignments[sid][1])
            else:
                del assignments[sid]
        for sid, name in (('315', '315-taomon-equipment'), ('332', '332-roachmon-equipment'),
                          ('335', '335-megagargomon-equipment'), ('351', '351-kotemon-field')):
            self.assertEqual(assignments[sid], ('tools.models.field_animations.imported_equipment', name))
        # Beelzemon's own gait module replaces its earlier gaits profile under the same overlay.
        self.assertEqual(assignments['403'][0], 'tools.models.field_animations.beelzemon')
        assignments['403'] = ('tools.models.field_animations.gaits', assignments['403'][1])
        # Reviewed footless post-passes wrap these original generators.
        for sid, module in (('231', 'shell_numemon'), ('251', 'gliding')):
            self.assertEqual(assignments[sid][0], 'tools.models.field_animations.locomotion')
            assignments[sid] = ('tools.models.field_animations.' + module, assignments[sid][1])
        for sid in ('254', '283', '400'):
            self.assertEqual(assignments[sid][0], 'tools.models.field_animations.locomotion')
            del assignments[sid]
        # Species-specific supported clips replace donor motion and the two pace-only passes.
        for sid, module, name in (('294', 'datamon', 'datamon'), ('313', 'bulbmon', 'bulbmon'),
                                  ('285', 'gazimon', 'gazimon'), ('279', 'marine_devimon', 'marinedevimon')):
            self.assertEqual(assignments.pop(sid),
                             ('tools.models.field_animations.' + module, sid + '-' + name + '-field'))
        self.assertEqual(assignments.pop('408'),
                         ('tools.models.field_animations.suijinmon', '408-suijinmon-centaur-field'))
        # The reviewed terrestrial gait replaces Gesomon's previous glide.
        self.assertEqual(assignments['240'],
                         ('tools.models.field_animations.gesomon', '240-gesomon-terrestrial'))
        self.assertNotIn('gesomon-hops', model.OVERLAYS)
        assignments['240'] = ('tools.models.field_animations.gliding', '240-gesomon-steady-run')
        # Shakkoumon's own gaits (shakkoumon.py) replace the steady glide it was pinned with.
        self.assertEqual(assignments['214'],
                         ('tools.models.field_animations.shakkoumon', '214-shakkoumon-glide'))
        assignments['214'] = ('tools.models.field_animations.gliding', '214-shakkoumon-glide')

        # MetalSeadramon swims with Seadramon's clips instead of the steady glide.
        self.assertEqual(assignments['211'],
                         ('tools.models.field_animations.metal_seadramon', '211-metalseadramon-swim'))
        assignments['211'] = ('tools.models.field_animations.gliding', '211-metalseadramon-glide')
        # All pre-existing bindings outside the repairs stay pinned.
        for sid in ('315', '332', '335'):
            del assignments[sid]
        assignments['351'] = ('tools.models.field_animations.articulation', '351-kotemon-field')
        # Raidramon (201) no longer has a field overlay: its gait is in its model delta (raidramon.py).
        self.assertNotIn('201', assignments)
        # Salamon (221) neither: its gait and blinking face are in its model delta (salamon.py, salamon_face.py).
        self.assertNotIn('221', assignments)
        # Woodmon (272) neither: its walk, tired walk and run are in its model delta (woodmon.py).
        self.assertNotIn('field_overlay', records['272'])
        # Gryphonmon (293) keeps only its celebration overlay: the gaits are in its model delta (gryphonmon_gait.py).
        self.assertEqual(records['293']['field_overlay'], 'gryphonmon-celebration')
        # Grizzlymon (296) neither: its idle, walk, tired walk and run are in its model delta (grizzlymon_gait.py).
        self.assertNotIn('field_overlay', records['296'])
        # KingEtemon (303) and GrapLeomon (306) wear native rigs and have no chibi row any more: their two entries left the pin.
        # WarGrowlmon (326) wears Growlmon's rig; its row stays for the proportions guard and its baked chibi recipe stays as provenance.
        self.assertEqual(hashlib.sha1(json.dumps(assignments, sort_keys=True).encode()).hexdigest(),
                         'ada12a6db27f1f55c83b6e27f247df97a0e3dd2c')


if __name__ == '__main__':
    unittest.main()
