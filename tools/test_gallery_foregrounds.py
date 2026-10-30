"""Gallery ranges must modify one imported background, once, before serializing the map."""
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if not (ROOT / 'story').exists():
    ROOT = Path.cwd()
MAPS = ROOT / 'story/mods/what-the-island-forgot/maps'
sys.path.insert(0, str(MAPS))
spec = importlib.util.spec_from_file_location('gallery_recipe_under_test', MAPS / 'galleries.py')
galleries = importlib.util.module_from_spec(spec)
spec.loader.exec_module(galleries)


class GalleryForegrounds(unittest.TestCase):
    def test_each_range_keeps_its_palette_until_the_map_is_written(self):
        for screen, owner, folder in [(338, 'generic', 'galleries'),
                                      (346, 'mine', 'galleries'),
                                      (357, 'mine', 'galleries'),
                                      (358, 'district', 'district'),
                                      (365, 'district', 'district')]:
            with self.subTest(screen=screen), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                author = root / 'maps/author' / folder
                author.mkdir(parents=True)
                (root / 'art').mkdir()
                (author / 'room.json').write_text(json.dumps(
                    dict(id=screen, file='ROOM', name='room', donor='DONOR')))
                (root / 'maps/room-data.json').write_text(json.dumps(
                    dict(camera=[0, 0, 0, 0, 0, 0], projection=320,
                         collision=[], warps=[])))
                (root / 'art/room.png').touch()
                out = root / 'output'
                calls = []
                class Map:
                    def build(self):
                        self.assert_palette()
                        calls.append('build')
                        return b'map with ' + owner.encode()
                    def assert_palette(self):
                        self_palette = (out / 'ROOM.TFS').read_bytes()
                        if self_palette != b'imported/' + owner.encode():
                            raise AssertionError(self_palette)
                m = Map()
                def import_png(donor, art, target):
                    calls.append('import')
                    Path(target).write_bytes(b'imported')
                def apply_range(label):
                    def apply(m, name_or_id, target):
                        calls.append(label)
                        path = Path(target)
                        path.write_bytes(path.read_bytes() + b'/' + label.encode())
                    return apply
                modules = {'foreground_c': types.SimpleNamespace(apply=apply_range('mine')),
                           'district_foreground': types.SimpleNamespace(apply=apply_range('district'))}
                with patch.object(galleries, 'MOD', str(root)), \
                     patch.object(galleries, 'base_map', return_value=m), \
                     patch.object(galleries, 'import_png', side_effect=import_png), \
                     patch.object(galleries, 'apply_foreground', side_effect=apply_range('generic')), \
                     patch.object(galleries, 'check_arrivals'), patch.dict(sys.modules, modules):
                    galleries.main(str(out), folder)
                self.assertEqual(calls, ['import', owner, 'build'])
                self.assertEqual((out / 'ROOM.MAP').read_bytes(), b'map with ' + owner.encode())


if __name__ == '__main__':
    unittest.main()
