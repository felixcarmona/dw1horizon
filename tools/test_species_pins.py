"""Scoped provider repins regenerate selected imports and preserve unrelated pins."""
import contextlib
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools.derive.steps import species


class ScopedPins(unittest.TestCase):
    def test_selected_import_is_regenerated_without_other_providers_or_pin_changes(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            path = root / species.PINS
            path.parent.mkdir(parents=True)
            before = {'imports': {'470': ['old', 'texture'], '471': ['keep', None]},
                      'record_originals': {'62': ['original', None]}, 'imports@dw3-us': {'183': ['variant', None]}}
            path.write_text(json.dumps(before))
            model, texture = root / '470.MMD', root / '470.TIM'
            model.write_bytes(b'new model')
            texture.write_bytes(b'texture')
            with patch.object(species.runner, 'ROOT', td), \
                 patch.object(species, 'species_tools', lambda: contextlib.nullcontext(None)), \
                 patch.object(species.ImportedModels, 'provide_models', return_value={470: (str(model), str(texture))}) as generate, \
                 patch.object(species.RecordOriginals, 'provide_models') as originals:
                result = species.pin(td, [470])
            generate.assert_called_once()
            self.assertEqual(generate.call_args.kwargs, {'generate': True, 'ids': {470}})
            originals.assert_not_called()
            expected = json.loads(json.dumps(before))
            expected['imports']['470'] = [hashlib.sha1(p.read_bytes()).hexdigest() for p in (model, texture)]
            self.assertEqual(result, expected)
            self.assertEqual(json.loads(path.read_text()), expected)

    def test_prepared_scoped_pin_reuses_inputs_and_preserves_other_pins(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            path = root / species.PINS
            path.parent.mkdir(parents=True)
            before = {'imports': {'470': ['old', None], '471': ['keep', None]},
                      'record_originals': {'62': ['original', None]}}
            path.write_text(json.dumps(before))
            model = root / '470.MMD'
            model.write_bytes(b'final pass')
            with patch.object(species.runner, 'ROOT', td), \
                 patch.object(species, 'species_tools', lambda: contextlib.nullcontext(None)), \
                 patch.object(species.ImportedModels, 'provide_models', return_value={470: (str(model), None)}) as provider, \
                 patch.object(species.RecordOriginals, 'provide_models') as originals:
                result = species.pin(td, [470], generate=False)
            self.assertEqual(provider.call_args.kwargs, {'generate': False, 'ids': {470}})
            originals.assert_not_called()
            before['imports']['470'] = [hashlib.sha1(model.read_bytes()).hexdigest(), None]
            self.assertEqual(result, before)

    def test_cli_accepts_ids_and_prepared_in_either_order(self):
        for tail in ([], ['470', '471'], ['--prepared'],
                     ['--prepared', '470', '471'], ['470', '--prepared', '471']):
            with self.subTest(tail=tail), patch.object(species, 'pin', return_value={}) as pin, \
                 contextlib.redirect_stdout(io.StringIO()):
                species.main(['pin', '/build', *tail])
            ids = [int(x) for x in tail if x != '--prepared'] or None
            pin.assert_called_once_with('/build', ids, generate='--prepared' not in tail)

    def test_prepared_full_pin_reuses_both_providers(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / species.PINS
            path.parent.mkdir(parents=True)
            path.write_text('{"imports": {}, "record_originals": {}}')
            with patch.object(species.runner, 'ROOT', td), \
                 patch.object(species, 'species_tools', lambda: contextlib.nullcontext(None)), \
                 patch.object(species.ImportedModels, 'provide_models', return_value={}) as imports, \
                 patch.object(species.RecordOriginals, 'provide_models', return_value={}) as originals:
                species.pin(td, generate=False)
            self.assertEqual(imports.call_args.kwargs, {'generate': False, 'ids': None})
            self.assertEqual(originals.call_args.kwargs, {'generate': False})


if __name__ == '__main__':
    unittest.main()
