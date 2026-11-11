"""VioletElecmon (256) moves exactly like native Elecmon: its rig and every field and care program are Elecmon's own."""
import copy
import json
import os
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import animsheet
import mmd
import motionstorage
from tools.models.field_animations import native_binding as binding

DONOR = 18


class VioletElecmonNative(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        source = Path(os.environ.get('BINDING_MODELS', 'build/imported-model-edit/edit'))
        files = list(source.glob('256-*.MMD'))
        native_path = Path(mmd.EXTRACTED) / 'CHDAT/MMD0/ELEC.MMD'
        if not files or not native_path.exists():
            raise unittest.SkipTest('needs the imported 256 model (edit.py get 256) and the player DW1 extraction')
        cls.recipe = json.loads(binding.MANIFEST.read_text())['256']
        cls.record = json.loads(next(Path('content/species').glob('256-*.json')).read_text())
        cls.data, cls.proof = binding.bind(files[0].read_bytes(), cls.record['model']['skeleton'], cls.recipe)
        cls.rig = cls.proof['generated_skeleton']
        cls.model = mmd.MMD.parse(cls.data, len(cls.rig))
        cls.model.type = DONOR
        cls.native = mmd.MMD.load(str(native_path), DONOR)

    @staticmethod
    def program(model, slot):
        clip = copy.deepcopy(model.anims.anims[model.anims.table[slot]])
        clip.instrs = [i for i in clip.instrs if i['op'] != 'tex']
        clip.tail = b''
        return clip.build()

    def test_rig_is_elecmons(self):
        self.assertEqual([p for _, p in self.rig], [p for _, p in mmd.exe().skeleton[DONOR]])
        self.assertEqual(len(self.rig), 25)
        self.assertEqual((self.recipe['donor'], self.recipe['scale'], self.recipe['mesh_scale']), (DONOR, 1.0, 1.0))
        self.assertEqual(self.recipe['model'], 'CHDAT/MMD0/ELEC.MMD')

    def test_every_program_below_the_techniques_is_elecmons_unchanged(self):
        for slot, index in enumerate(self.native.anims.table[:46]):
            if index is None:
                continue
            with self.subTest(slot=slot):
                self.assertEqual(self.program(self.model, slot), self.program(self.native, slot))

    def test_field_clips_play_elecmons_frames(self):
        for slot in (0, 1, 2, 3, 4):
            with self.subTest(slot=slot):
                before, loop, _ = animsheet.slot_frames(self.native, 25, slot)
                after, new_loop, _ = animsheet.slot_frames(self.model, 25, slot)
                self.assertEqual((len(after), new_loop), (len(before), loop))
                self.assertEqual(after, before)

    def test_techniques_play_elecmons_clips_of_their_kind(self):
        moves = self.record['techniques']
        slots = self.recipe['technique_slots']
        self.assertEqual(len(slots), len(moves))
        elecmon = json.loads(next(Path('content/species').glob('18-elecmon.json')).read_text())['techniques']
        for position, move in enumerate(moves):
            if move in elecmon:
                # a move Elecmon has plays Elecmon's own clip for it (its list position is its slot minus 46)
                self.assertEqual(slots[position], 46 + elecmon.index(move), move)
            with self.subTest(move=move):
                self.assertEqual(self.program(self.model, 46 + position), self.program(self.native, slots[position]))

    def test_training_clip_is_elecmons_training_clip(self):
        training = self.record['partner']['training']
        self.assertEqual(training, {'animation': 46 + len(self.record['techniques']), 'hit_tick': 10})
        self.assertEqual(self.program(self.model, training['animation']), self.program(self.native, 46))

    def test_condition_bubble_rides_the_head(self):
        bubble = self.recipe['species_patch']['condition_bubble']
        self.assertEqual(bubble[3], 3)
        self.assertLess(bubble[3], len(self.rig))

    def test_resident_animation_buffer(self):
        storage = motionstorage.require(self.data, len(self.rig))
        self.assertTrue(storage['fits'])
        self.assertLessEqual(storage['resident_bytes'], storage['resident_limit'])
        self.assertEqual(storage['resident_limit'], 100352)

    def test_every_piece_is_bound_once_and_sits_where_elecmons_does(self):
        objects = sorted(o for o, _ in self.rig if o >= 0)
        self.assertEqual(objects, list(range(len(self.model.tmd.objects))))
        self.assertEqual(set(map(int, self.recipe['map'])), set(range(1, 23)))
        self.assertEqual(sorted(self.recipe['map'].values()), [b for b, (o, _) in enumerate(mmd.exe().skeleton[DONOR])
                                                              if o >= 0])
        # each piece's rest-pose box lies where Elecmon's matching piece does (within 40 units; the ears are
        # 30 units shorter in this model's own mesh)
        pose = animsheet.slot_frames(self.model, 25, 0)[0][0]
        pose[0] = [4096]*3 + [0]*6
        world = mmd.bone_matrices(self.model, pose)
        npose = animsheet.slot_frames(self.native, 25, 0)[0][0]
        npose[0] = [4096]*3 + [0]*6
        nworld = mmd.bone_matrices(self.native, npose)
        for bone, (obj, _) in enumerate(mmd.exe().skeleton[DONOR]):
            if obj < 0:
                continue
            nobj = self.rig[bone][0]
            boxes = []
            for mod, w, o in ((self.model, world, nobj), (self.native, nworld, obj)):
                pts = [[sum(w[bone][r][c]*v[c] for c in range(3)) + w[bone][r][3] for r in range(3)]
                       for v in mod.tmd.obj_verts(o)]
                boxes.append([(min(p[a] for p in pts), max(p[a] for p in pts)) for a in range(3)])
            for axis in range(3):
                for end in (0, 1):
                    self.assertLess(abs(boxes[0][axis][end] - boxes[1][axis][end]), 40, (bone, axis, end))


if __name__ == '__main__':
    unittest.main()
