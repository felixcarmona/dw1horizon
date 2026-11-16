"""Scoped provider repins regenerate selected imports and preserve unrelated pins."""
import contextlib
import hashlib
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


if __name__ == '__main__':
    unittest.main()
