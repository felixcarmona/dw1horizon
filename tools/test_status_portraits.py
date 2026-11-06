"""Perspective and fitting invariants for Status portrait audits."""
import sys
from pathlib import Path
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import status_portraits as status


class StatusPortraits(unittest.TestCase):
    def test_camera_target_is_screen_origin(self):
        self.assertEqual(status.project([status.camera((0, 0, 0))], (0, 0, 0)), [(160, 120)])

    def test_wide_wings_and_tall_head_fit_together(self):
        # Both extremes must fit even when they belong to different ticks.
        points = [(-800, 0, -100), (800, 0, 100), (0, -1600, 0), (0, 100, 0)]
        original = [0, 0, 0]
        position = status.fit(points, original)
        box = status.envelope(points, position)
        self.assertTrue(status.inside(box))
        self.assertGreater(max(box[2] - box[0], box[3] - box[1]), 25)
        self.assertGreaterEqual(status.camera(position)[2], status.camera(original)[2])

    def test_panel_bounds_follow_menu_box_and_three_pixel_separator(self):
        self.assertEqual(status.BOUNDS, (14, 105, 158, 217))
        self.assertLess(status.TARGET[3], 218)  # bottom border starts at 218
        self.assertGreater(status.TARGET[1], 104)  # separator ends at 104

    def test_reported_portraits_cannot_sink_into_care_rows(self):
        for box in ([64, 148, 138, 199], [72, 157, 127, 207]):
            self.assertEqual(status.readability_problem(box), 'Life/care overlap')

    def test_readability_floor_and_actual_label_are_independent(self):
        self.assertIsNone(status.readability_problem([83, 106, 130, 151]))
        self.assertEqual(status.readability_problem([83, 106, 100, 124]), 'unreadable height')
        self.assertIsNone(status.readability_problem([83, 106, 100, 125]))
        self.assertEqual(status.readability_problem([20, 106, 80, 151], True), 'label overlap')

    def test_repair_never_crosses_the_life_boundary(self):
        points = [(-500, -1000, 0), (500, 500, 0)]
        fitted = status.fit(points, [0, 0, 0])
        self.assertLess(status.envelope(points, fitted)[3], status.LIFE_Y)

    def test_camera_anchor_translates_the_whole_pose_without_mutating_it(self):
        pose = [[4096, 4096, 4096, 0, 0, 0, 10, 20, 30],
                [4096, 4096, 4096, 0, 0, 0, 3, 4, 5]]
        matrix = [[1, 0, 0, 13], [0, 1, 0, 24], [0, 0, 1, 35], [0, 0, 0, 1]]
        with patch.object(status.mmd, 'bone_matrices', return_value=[matrix, matrix]):
            framed = status.anchor_frames([pose], 1, object())[0]
        self.assertEqual(framed[0][6:9], [-3, -4, -5])
        self.assertEqual(framed[1], pose[1])
        self.assertEqual(pose[0][6:9], [10, 20, 30])
        self.assertIs(status.anchor_frames([pose], 0, None)[0], pose)

    def test_anchor_uses_reserved_record_space_without_growing_the_cache(self):
        species = status.species
        record = dict(para=species.unpack(species.PARA_FIELDS, bytes(0x34), 0),
                      modelName='', texSector=0, texFile=0, texSectors=0,
                      originalType=0, vball=0, vlall=0, flags=0, bones=[])
        baseline = species.pack_record(record)
        anchored = species.pack_record(dict(record, statusAnchorBone=12))
        self.assertEqual(len(anchored), 512)
        self.assertEqual([i for i, (a, b) in enumerate(zip(baseline, anchored)) if a != b], [0x1CE])
        self.assertEqual(species.unpack_record(anchored, 188)['statusAnchorBone'], 12)
        self.assertNotIn('statusAnchorBone', species.unpack_record(baseline, 188))

    def test_depth_changes_perspective(self):
        near, far = status.project([(100, 0, -1000), (100, 0, 1000)], (0, 0, 0))
        self.assertGreater(near[0], far[0])

    def test_each_edge_is_checked(self):
        self.assertTrue(status.inside(status.BOUNDS))
        for index, delta in enumerate((-1, -1, 1, 1)):
            box = list(status.BOUNDS)
            box[index] += delta
            self.assertFalse(status.inside(box))

    def test_fitting_portrait_is_not_enlarged_or_recentered(self):
        points = [(-50, -300, 0), (50, -250, 0)]
        original = [200, 330, -1320]
        self.assertEqual(status.fit(points, original), original)

    def test_small_overflow_uses_only_the_needed_offset(self):
        points = [(-50, -400, 0), (50, -350, 0)]
        original = [200, 330, -1320]
        fitted = status.fit(points, original)
        self.assertEqual(fitted[::2], original[::2])
        self.assertGreater(fitted[1], original[1])
        self.assertLess(abs(status.envelope(points, fitted)[1] - status.TARGET[1]), 1)

    def test_touching_outer_edge_does_not_qualify_as_overflow(self):
        self.assertTrue(status.inside(status.BOX_EDGES, status.BOX_EDGES))
        self.assertTrue(status.inside([75, 102, 125, 183], status.BOX_EDGES))

    def test_tiny_offcenter_model_is_offset_without_zooming(self):
        original = [0, 0, 0]
        fitted = status.fit([(-10, -10, 0), (10, 10, 0)], original)
        depth_change = status.camera(fitted)[2] - status.camera(original)[2]
        self.assertGreaterEqual(depth_change, 0)
        self.assertLess(depth_change, 2)  # integer XYZ rounding only

    def test_entity_scale_preserves_idle_root_momentum(self):
        pose = [[4100, 4090, 4096, 0, 0, 0, 0, 0, 0]]
        adjusted = status.scaled_pose(pose, 1.5)
        self.assertEqual(adjusted[0][:3], [6148, 6138, 6144])
        self.assertEqual(pose[0][:3], [4100, 4090, 4096])

    def test_texture_copy_uses_vram_words_and_preserves_overlapping_source(self):
        class Texture:
            w, h = 16, 4
            idx = bytearray(range(64))
        texture = Texture()
        status.move_image(texture, (0, 0), (2, 2), (1, 1))
        self.assertEqual(texture.idx[20:28], bytearray(range(8)))
        self.assertEqual(texture.idx[36:44], bytearray(range(16, 24)))


if __name__ == '__main__':
    unittest.main()
