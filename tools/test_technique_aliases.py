"""Additional techniques retain the imported model's acting and existing slots."""
import copy
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mmd
_module = importlib.util.spec_from_file_location('imported_species',
    Path(__file__).resolve().parents[1] / 'content/models/imports/species.py')
provider = importlib.util.module_from_spec(_module)
_module.loader.exec_module(provider)


class TechniqueAliases(unittest.TestCase):
    def model(self, angle):
        model = mmd.MMD()
        model.nbones = 1
        model.tmd = mmd.TMD()
        model.anims = mmd.AnimSection()
        poses = [[[4096, 4096, 4096, i * angle, 0, 0, 0, -10, 0]] for i in range(8)]
        model.anims.anims = [mmd.encode_anim(poses, 1, events=[
            (3, 'sound', dict(bank=4, note=17))], tol=0)]
        model.anims.table = [0] * 49
        return model.build()

    def spec(self, path):
        return dict(id=999, techniques=['Sonic Jab', 'Wind Cutter', 'Ice Needle', 'Ice Statue'],
                    _path='fixture', model=dict(file=str(path), skeleton=[[-1, -1]],
                                               slot_aliases=[[48, 47]]))

    def assert_shared(self, original, result):
        before = mmd.MMD.parse(original, 1)
        after = mmd.MMD.parse(result, 1)
        for slot in range(49):
            a = before.anims.anims[before.anims.table[slot]]
            b = after.anims.anims[after.anims.table[slot]]
            self.assertEqual(mmd.simulate(a, 1), mmd.simulate(b, 1))
        self.assertEqual(after.anims.table[49], after.anims.table[48])
        self.assertEqual(len(after.anims.anims), len(before.anims.anims))

    def test_existing_aliases_and_attack_events_survive_table_extension(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'base.MMD'
            data = self.model(31)
            model = mmd.MMD.parse(data, 1)
            model.anims.anims.append(mmd.encode_anim(
                [[[4096, 4096, 4096, 400, 0, 0, 0, -10, 0]]], 1, tol=0))
            model.anims.table[48] = 1
            path.write_bytes(model.build())
            spec = self.spec(path)
            untouched = copy.deepcopy(spec)
            result = provider.technique_aliases(spec, {'Ice Statue': 'Ice Needle'})
            self.assertEqual(spec, untouched)
            after = mmd.MMD.parse(result, 1)
            self.assertEqual(after.anims.table[49], after.anims.table[47])
            self.assertEqual(after.anims.table[48], after.anims.table[47])
            for slot in range(48):
                self.assertEqual(after.anims.table[slot], model.anims.table[slot])
            source = model.anims.anims[model.anims.table[47]]
            target = after.anims.anims[after.anims.table[49]]
            self.assertEqual(mmd.simulate(source, 1), mmd.simulate(target, 1))

    def test_additions_use_final_overlay_and_repeated_builds_match(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            base, overlay = folder / 'base.MMD', folder / 'overlay.MMD'
            base.write_bytes(self.model(10))
            overlay.write_bytes(self.model(97))
            report = folder / 'overlay.json'
            report.write_text(json.dumps({}))
            recs = {'999': {'field_overlay': 'fixture',
                            'technique_aliases': {'Ice Statue': 'Ice Needle'}}}
            own = self.spec(base)
            with patch.object(provider, '_species', side_effect=lambda *args: ('999-fixture.json', copy.deepcopy(own))), \
                 patch.object(provider, 'overlay_paths', return_value=(str(overlay), str(report))):
                _, spec = provider.species_file(str(folder / 'species'), '999', recs, ['fixture'])
                first = Path(spec['model']['file']).read_bytes()
                self.assert_shared(overlay.read_bytes(), first)
                _, again = provider.species_file(str(folder / 'species'), '999', recs, ['fixture'])
                self.assertEqual(first, Path(again['model']['file']).read_bytes())


if __name__ == '__main__':
    unittest.main()
