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
            '183': ('183', 'tools.models.field_animations.native_binding', '183-wormmon-native-crawl'),
            '187': ('187', 'tools.models.field_animations.followthrough', '187-stingmon-wing-followthrough'),
            '239': ('239', 'tools.models.field_animations.followthrough', '239-gizamon-active-gait'),
        }
        for sid, expected in following.items():
            self.assertEqual(selected.pop(sid), expected)
        # Silphymon's repaired walk is baked into its plain delta. Keep the
        # preceding field recipe covered without applying it over that repair.
        self.assertEqual(records['226'], {'model': '226-Silphymon.MMD', 'aliases_applied': True})
        selected['226'] = model.OVERLAYS['silphymon-field']
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
        for path in [*Path('content/models/authoring/native-polish').glob('*.json'),
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
        # Magnamon's native binding supersedes its retained authoring recipe.
        active = dict(model.OVERLAYS)
        previous_magnamon = active.pop('magnamon-field')
        self.assertEqual(previous_magnamon,
                         ('197', 'tools.models.field_animations.gaits', '197-magnamon-field'))
        self.assertEqual(len(selected)+len(following), len(active))
        self.assertEqual(set(selected.values()) | set(following.values()), set(active.values()))
        for species, (bound_species, _, _) in selected.items():
            self.assertEqual(species, bound_species)
        assignments = {t: entry[1:] for t, entry in selected.items()}
        self.assertEqual(assignments.pop('236'),
                         ('tools.models.field_animations.native_binding', '236-demidevimon-native-flight'))
        self.assertEqual(assignments['197'],
                         ('tools.models.field_animations.native_binding', '197-magnamon-native'))
        assignments['197'] = previous_magnamon[1:]
        # Celebration curves run after the final proportions. Unwrap them to
        # keep guarding all the original field recipes and output names.
        for sid, row in celebrations.items():
            self.assertEqual(assignments[sid][0], 'tools.models.field_animations.celebrations')
            if row.get('base_generator'):
                assignments[sid] = (row['base_generator'], assignments[sid][1])
            else:
                del assignments[sid]
        # The chibi proportions wrap the recipe that came before them; species without one have no other generator.
        chibi = json.load(open('content/models/imports/chibi.json'))
        for sid, row in chibi.items():
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
        # All pre-existing bindings outside the repairs stay pinned.
        for sid in ('315', '332', '335'):
            del assignments[sid]
        assignments['351'] = ('tools.models.field_animations.articulation', '351-kotemon-field')
        self.assertEqual(hashlib.sha1(json.dumps(assignments, sort_keys=True).encode()).hexdigest(),
                         'fb34cbd7c510ff8ca340ab9754de89a4c12a43f8')


if __name__ == '__main__':
    unittest.main()
