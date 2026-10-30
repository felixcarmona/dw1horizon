"""Characterize the dynamic overlay registry before changing provider paths and labels."""
import hashlib
import json
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from tools.derive.steps import species

from tools.derive.steps.overlays import imported_models as provider


class ModelProvider(unittest.TestCase):
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
        self.assertEqual(len(records), 175)
        selected = {t: model.OVERLAYS[e['field_overlay']]
                    for t, e in records.items() if e.get('field_overlay')}
        self.assertEqual(len(selected), 65)
        self.assertEqual({e['field_overlay'] for e in records.values() if e.get('field_overlay')},
                         set(model.OVERLAYS))
        for species, (bound_species, _, _) in selected.items():
            self.assertEqual(species, bound_species)
        assignments = {t: entry[1:] for t, entry in selected.items()}
        self.assertEqual(hashlib.sha1(json.dumps(assignments, sort_keys=True).encode()).hexdigest(),
                         '520fa1214ae8f4a7a0d706407dc3b507f50be270')


if __name__ == '__main__':
    unittest.main()
