"""Sighting tiles preserve walls, exits, other triggers and hunter placements."""
import importlib.util
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[4]
MAPS = ROOT / 'story/mods/what-the-island-forgot/maps'
sys.path[:0] = [str(ROOT / 'tools'), str(MAPS)]
import dwmap


def recipe(name):
    spec = importlib.util.spec_from_file_location(name, MAPS / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@unittest.skipUnless(list((ROOT / 'extracted/MAP').glob('*/GIAS01.MAP')), 'needs the player disc extraction')
class HunterTiles(unittest.TestCase):
    def test_only_ordinary_floor_changes(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            forest = recipe('mayo03-south')
            with patch.object(forest, 'mark_sighting'):
                forest.main(tmp)
            for name in ('GIAS01',):
                src = next((ROOT / 'extracted/MAP').glob('*/' + name + '.MAP'))
                shutil.copyfile(src, out / src.name)
                shutil.copyfile(src.with_suffix('.TFS'), out / (name + '.TFS'))
            before = {n: (out / (n + '.MAP')).read_bytes() for n in ('MAYO03', 'GIAS01')}
            backgrounds = {n: (out / (n + '.TFS')).read_bytes() for n in before}
            forest.main(tmp)
            recipe('hunter_sightings').main(tmp)
            for name, step in (('MAYO03', 0), ('GIAS01', 1)):
                old = dwmap.MapFile(before[name])
                new = dwmap.MapFile((out / (name + '.MAP')).read_bytes())
                changes = [(a, b) for a, b in zip(old.collision, new.collision) if a != b]
                with self.subTest(map=name):
                    self.assertGreater(len(changes), 0)
                    self.assertTrue(all(a == 0 and b == 51 + step for a, b in changes))
                    self.assertEqual(old.warps, new.warps)
                    self.assertEqual(old.digimon, new.digimon)
                    self.assertEqual(backgrounds[name], (out / (name + '.TFS')).read_bytes())
                    # Replacing only collision reproduces every byte of the output.
                    old.collision = new.collision
                    self.assertEqual(old.build(), new.build())
