"""Package outputs must not depend on which region supplied the input maps."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace

from tools import balance
import content


class RegionalMapOutputs(unittest.TestCase):
    def test_unchanged_and_changed_inputs_emit_the_same_generated_map(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / 'extracted/MAP/FOREST.MAP'
            source.parent.mkdir(parents=True)
            inventories = []
            for region, data in [('us', b'authored enemies'), ('jp', b'original enemies')]:
                source.write_bytes(data)
                with patch.object(balance, 'EXTRACTED', str(root / 'extracted')), \
                     patch.object(content, 'map_files', return_value={'FOREST': 'MAP/FOREST.MAP'}), \
                     patch.object(content, 'build_map', return_value=b'authored enemies'):
                    made = balance.build_maps(str(root / region))
                inventories.append([name for name, path in made])
                self.assertEqual(len(made), 1)
                self.assertEqual(Path(made[0][1]).read_bytes(), b'authored enemies')
            self.assertEqual(inventories[0], inventories[1])

    def test_story_maps_keep_the_story_producer(self):
        with patch.object(content, 'map_files', return_value={'FOREST': 'MAP/FOREST.MAP'}), \
             patch.object(content, 'build_map') as generate:
            self.assertEqual(balance.build_maps('/unused', {'MAP/FOREST.MAP': 'story-output'}), [])
            generate.assert_not_called()

    def test_replacement_geometry_is_the_input_to_gameplay_generation(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / 'retouched.MAP'
            source.write_bytes(b'edited geometry; original enemies')
            def generate(name, data):
                self.assertEqual(data, b'edited geometry; original enemies')
                return data.replace(b'original enemies', b'authored enemies')
            with patch.object(content, 'map_files', return_value={'FOREST': 'MAP/FOREST.MAP'}), \
                 patch.object(content, 'build_map', side_effect=generate):
                made = balance.build_maps(str(root / 'out'), overrides={'MAP/FOREST.MAP': str(source)})
            self.assertEqual(Path(made[0][1]).read_bytes(), b'edited geometry; authored enemies')

    def test_original_story_uses_its_own_geometry(self):
        from tools.derive.steps.balance import map_overrides
        ctx = SimpleNamespace(root='/repo', env={'EXTRA_FILES': 'MAP/FOREST.MAP=build/retouched.MAP'})
        self.assertEqual(map_overrides(ctx), {'MAP/FOREST.MAP': '/repo/build/retouched.MAP'})
        self.assertEqual(map_overrides(ctx, 'base'), {})


if __name__ == '__main__':
    unittest.main()
