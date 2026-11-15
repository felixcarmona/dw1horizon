"""Chibi proportions: the floor rule, the height keys, points carried by the bake, and the empty manifest."""
import json
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'tools')]
import mmd
from tools.models.field_animations import chibi


def looping_clip():
    """Two bones: a key at frame 1, then a loop over frames 2..10 with one key at each end."""
    a = mmd.Anim()
    a.frame_count, a.has_scale = 12, False
    a.pose = [[0, 0, 0, 0, -100, 0]]
    a.instrs = [dict(op='key', frame=1, bones=[dict(bone=1, div=1, vals={'ty': 0})]),
                dict(op='loop_start', count=0xFF, raw=0x10FF),
                dict(op='key', frame=2, bones=[dict(bone=1, div=4, vals={'ty': 8})]),
                dict(op='sound', frame=4, bank=1, note=2),
                dict(op='key', frame=6, bones=[dict(bone=1, div=4, vals={'ty': -8}), dict(bone=1, div=2, vals={'rx': 4})]),
                dict(op='loop_end', frame=10, jump=2),
                dict(op='end')]
    return a


def heights(animation, ticks):
    player = mmd.AnimPlayer(animation, 2)
    out = {}
    for _ in range(ticks):
        player.tick()
        out.setdefault(player.frames[-1], player.pose[1][7])
    return out, player


class Floor(unittest.TestCase):
    def test_target(self):
        self.assertEqual(chibi.target(20), 0)          # a source that sinks goes on the floor
        self.assertEqual(chibi.target(-5), 0)          # one that nearly stands too
        self.assertEqual(chibi.target(-100), -100)     # a jump or a hover keeps its clearance
        for low in range(-40, 1):
            self.assertLessEqual(abs(chibi.target(low) - chibi.target(low - 1)), 2)   # no step at the margin

    def test_feet_carry_the_body_unless_the_source_rests_on_something_else(self):
        standing = (0.0, 0.0, 5)
        lying = (-90.0, 0.0, 9)
        self.assertEqual(chibi.on_feet([standing] * 7), [1.0] * 7)
        self.assertEqual(chibi.on_feet([lying] * 7), [0.0] * 7)
        blend = chibi.on_feet([standing] * 6 + [lying] * 6)
        self.assertEqual(blend[:4], [1.0] * 4)
        self.assertEqual(blend[-4:], [0.0] * 4)
        self.assertTrue(all(a >= b for a, b in zip(blend, blend[1:])))
        self.assertEqual(chibi.on_feet([(-3.0, 0.0, 5)] * 3), [1.0] * 3)     # a foot just over the lowest part still counts

    def test_a_loop_does_not_blend_with_what_came_before_it(self):
        standing, lying = (0.0, 0.0, 5), (-90.0, 0.0, 9)
        self.assertEqual(chibi.on_feet([standing] * 2 + [lying] * 5, 2)[2:], [0.0] * 5)

    def test_simplify_keeps_the_corners_only(self):
        line = [(x, min(x, 10 - x)) for x in range(11)]
        self.assertEqual(chibi._simplify(line, 0.5), [0, 5, 10])

    def test_heights_are_rewritten_exactly_and_the_loop_stays_closed(self):
        a = looping_clip()
        wanted = {1: -80, 2: -80, 3: -70, 4: -60, 5: -60, 6: -60, 7: -75, 8: -90, 9: -85, 10: -80}
        chibi._rewrite_heights(a, 1, wanted, 0.5)
        seen, player = heights(a, 30)
        self.assertEqual(seen, wanted)
        self.assertEqual(a.pose[0][4], -80)
        self.assertTrue(any(i.get('added') for i in a.instrs))
        self.assertEqual([e[1] for e in player.events][:1], ['sound'])
        frames = [i['frame'] for i in a.instrs if i['op'] in ('key', 'sound')]
        self.assertEqual(frames, sorted(frames))
        rotated = [g for i in a.instrs if i['op'] == 'key' for g in i['bones'] if 'rx' in g['vals']]
        self.assertEqual([(g['div'], g['vals']['rx']) for g in rotated], [(2, 4)])

    def test_frames_a_clip_never_plays_take_the_last_height(self):
        a = looping_clip()
        a.frame_count = 14
        a.instrs.insert(-1, dict(op='key', frame=10, bones=[dict(bone=1, div=1, vals={'tx': 1})]))
        wanted = {1: -80, 2: -80, 3: -70, 4: -60, 5: -60, 6: -60, 7: -75, 8: -90, 9: -85, 10: -80}
        chibi._rewrite_heights(a, 1, wanted, 0.5)
        self.assertEqual(heights(a, 30)[0], wanted)

    def test_a_clip_with_a_loop_that_skips_its_first_frame_is_left_to_a_constant_lift(self):
        a = looping_clip()
        a.instrs[-2]['jump'] = 3
        self.assertIsNone(chibi._chains(a))


class Record(unittest.TestCase):
    def test_points_ride_the_bake(self):
        scales = {7: (chibi._diagonal(2.0), [0.0, 10.0, 0.0])}
        self.assertEqual(chibi.carried_point(scales, 0.5, 7, [4, 20, 0]), [4, 15, 0])
        self.assertEqual(chibi.carried_point(scales, 0.5, 3, [4, 20, 0]), [2, 10, 0])

    def test_species_patch(self):
        scales = {7: (chibi._diagonal(2.0), [0.0, 0.0, 0.0])}
        record = dict(effect_origins=[[7, 'any', 10, 0, 3, 8, 8, 8]], condition_bubble=[0, -50, 0, 7],
                      effect_origin_fallback=[7, 1, 2, 3])
        self.assertEqual(chibi.species_patch(record, scales, 1.0),
                         dict(effect_origins=[[7, 'any', 20, 0, 3, 8, 8, 8]], condition_bubble=[0, -100, 0, 7],
                              effect_origin_fallback=[7, 2, 4, 6]))


class Manifest(unittest.TestCase):
    def test_no_species_is_enabled_without_its_pins(self):
        rows = json.loads(chibi.MANIFEST.read_text())
        for row in rows.values():
            self.assertTrue({'source_sha256', 'post_source_sha256', 'skeleton_sha256', 'groups', 'factors', 'height'} <= set(row))
        with self.assertRaisesRegex(ValueError, 'pinned'):
            chibi.build(b'not a reviewed model', [])

    def test_rows_stay_within_the_reviewed_limits(self):
        for sid, row in json.loads(chibi.MANIFEST.read_text()).items():
            self.assertLessEqual(row['factors']['head'], 1.9, sid)
            self.assertLess(abs(row.get('trim', 1.0) - 1.0), 0.08, sid)       # Creepymon's sunken idle is the widest
            self.assertTrue(all(isinstance(slot, int) for slot in row.get('rest_slots', ())), sid)

    def test_imports_without_site_packages(self):
        script = 'import sys; sys.path[:0] = [sys.argv[1], sys.argv[1] + "/tools"]\n' \
                 'import tools.models.field_animations.chibi\n' \
                 'assert "numpy" not in sys.modules and "PIL" not in sys.modules'
        result = subprocess.run([sys.executable, '-I', '-S', '-c', script, str(ROOT)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)




class ClipProportions(unittest.TestCase):
    def poses(self):
        import copy
        idle = [[4096, 4096, 4096, 0, 0, 0, 0, 0, 0],
                [4096, 4096, 4096, 0, 0, 0, 0, -200, 0],
                [4096, 4096, 4096, 0, 0, 0, 0, -100, 0],
                [4096, 4096, 4096, 0, 0, 0, 50, 100, 0]]
        return idle, [copy.deepcopy(idle), copy.deepcopy(idle)]

    def test_unreshaped_head_fails_even_when_median_size_passes(self):
        from tools.models import clip_rig
        idle, frames = self.poses()
        for p in frames:
            p[2][7] = -140
        result = clip_rig.proportions(frames, idle, [-1, 0, 1, 1], {2: 'head', 3: 'shin'})
        self.assertTrue(clip_rig.failure(result))
        self.assertAlmostEqual(result['parts']['head'], 0.4)

    def test_reshaped_idle_and_crouch_pass(self):
        from tools.models import clip_rig
        idle, frames = self.poses()
        frames[1][1][7] += 60
        frames[1][3][3] += 600
        self.assertFalse(clip_rig.failure(clip_rig.proportions(frames, idle, [-1, 0, 1, 1],
                                                            {2: 'head', 3: 'shin'})))

    def test_all_ticks_are_checked_and_hidden_parts_are_visibility(self):
        from tools.models import clip_rig
        idle, frames = self.poses()
        frames[1][2][7] *= 1.3
        self.assertTrue(clip_rig.failure(clip_rig.proportions(frames, idle, [-1, 0, 1, 1], {2: 'head'})))
        frames[1][2][:3] = [0, 0, 0]
        self.assertFalse(clip_rig.failure(clip_rig.proportions(frames, idle, [-1, 0, 1, 1], {2: 'head'})))

    def test_proportion_bounds_are_inclusive_without_rounding(self):
        import math
        from tools.models import clip_rig
        row = dict(first=1.08, min=0.88, max=1.12, deviation=0.12)
        self.assertFalse(clip_rig.bone_failure(row))
        self.assertTrue(clip_rig.bone_failure(dict(row, first=math.nextafter(1.08, math.inf))))
        self.assertTrue(clip_rig.bone_failure(dict(row, min=math.nextafter(0.88, -math.inf))))
        self.assertTrue(clip_rig.bone_failure(dict(row, max=math.nextafter(1.12, math.inf))))

    def test_carrier_is_identified_by_parent_not_bone_number(self):
        from tools.models import clip_rig
        idle, frames = self.poses()
        frames[1][3][7] *= 5
        result = clip_rig.proportions(frames, idle, [-1, 2, 0, 0], {1: 'head', 3: 'chest'})
        self.assertNotIn('3', result['bones'])
        self.assertFalse(clip_rig.failure(result))


class RigChannels(unittest.TestCase):
    def test_reviewed_clearance_is_encoded_when_dimensions_already_pass(self):
        import copy
        from types import SimpleNamespace
        from unittest.mock import patch
        import animsheet
        from tools.models import clip_rig
        skeleton = [(-1, -1), (-1, 0), (0, 1)]
        pose = [[4096, 4096, 4096, 0, 0, 0, 0, 0, 0],
                [4096, 4096, 4096, 0, 0, 0, 0, -200, 0],
                [4096, 4096, 4096, 0, 0, 0, 0, -100, 0]]
        frames = [copy.deepcopy(pose), copy.deepcopy(pose)]
        frames[1][0][6] = 5
        animation = mmd.encode_anim(frames, 3, None, tol=0)
        model = mmd.MMD()
        model.tmd = mmd.TMD()
        model.anims = mmd.AnimSection()
        model.anims.anims = [animation, copy.deepcopy(animation)]
        model.anims.table = [0] + [None] * 33 + [1]
        data = model.build()
        operations = [dict(op='turn', bone=2, axis='z', deg=8),
                      dict(op='offset', bone=2, delta=[5, 0, 0])]
        with patch.object(clip_rig, 'groups_for', return_value={2: 'head'}), \
                patch.object(clip_rig, 'post_fits', return_value={'9897': {'34': operations}}), \
                patch.object(chibi, 'Rig', return_value=SimpleNamespace(verts={2: [(0, 0, 0)]})), \
                patch.object(chibi, 'bone_lows', return_value={2: 0}):
            result, _ = clip_rig.conform(data, skeleton, '9897')
        before, after = mmd.MMD.parse(data, 3), mmd.MMD.parse(result, 3)
        self.assertEqual(before.anims.anims[before.anims.table[0]].build(),
                         after.anims.anims[after.anims.table[0]].build())
        old_frames = animsheet.slot_frames(before, 3, 34)[0]
        new_frames = animsheet.slot_frames(after, 3, 34)[0]
        self.assertEqual(new_frames[0][2][6], 5)
        self.assertNotEqual(new_frames[0][2][5], old_frames[0][2][5])
        self.assertEqual([p[0] for p in new_frames], [p[0] for p in old_frames])

    def test_unit_scale_is_not_read_from_translation_when_encoding_omits_it(self):
        from tools.models.field_animations.articulation import replace_channels
        original = mmd.Anim()
        original.has_scale = True
        original.frame_count = 2
        original.pose = [[4096, 4096, 4096, 0, 0, 0, 30, 80, 0]]
        original.instrs = [dict(op='end')]
        frames = [[[4096, 4096, 4096, 0, 0, 0, 0, 0, 0],
                   [4096, 4096, 4096, 0, 0, 0, 30, 80, 0]]] * 2
        fitted = replace_channels(original, frames, None, 2, {(1, c) for c in (0, 1, 2, 6, 7, 8)})
        self.assertEqual(fitted.pose[0][:3], [4096, 4096, 4096])


class FittedJointMotion(unittest.TestCase):
    def test_tail_keeps_motion_on_a_constant_radius(self):
        import copy
        import math
        from tools.models import clip_rig
        idle = [[4096, 4096, 4096, 0, 0, 0, 0, 0, 0],
                [4096, 4096, 4096, 0, 0, 0, 0, -200, 0],
                [4096, 4096, 4096, 0, 0, 0, 0, -50, 80]]
        frames = [copy.deepcopy(idle) for _ in range(5)]
        for pose, y, z in zip(frames, [-50, -54, -60, -54, -50], [80, 95, 110, 95, 80]):
            pose[2][7:9] = [y, z]
        fitted = clip_rig.fit(frames, idle, idle, dimensions=[2])
        def motion(poses):
            points = [p[2][6:9] for p in poses]
            mean = [sum(p[i] for p in points) / len(points) for i in range(3)]
            return math.sqrt(sum(math.dist(p, mean) ** 2 for p in points) / len(points))
        self.assertGreater(motion(fitted), 0.5 * motion(frames))
        for before, after in zip(frames, fitted):
            self.assertEqual(before[0], after[0])
            self.assertEqual(before[2][3:6], after[2][3:6])
            self.assertAlmostEqual(math.dist(after[2][6:9], [0, 0, 0]), math.dist(idle[2][6:9], [0, 0, 0]))


class FittedFeet(unittest.TestCase):
    def test_shorter_rig_keeps_planted_world_paths_and_rejects_unreachable_steps(self):
        import copy
        import math
        from types import SimpleNamespace
        from tools.models import clip_rig
        skeleton = [(-1,-1),(-1,0),(-1,1),(-1,2),(0,3)]
        mmd.exe().add_type(9898, skeleton)
        model = SimpleNamespace(type=9898, tmd=SimpleNamespace(obj_verts=lambda o: [(-5,0,-5,0),(5,0,5,0)]))
        pose = [[4096,4096,4096,0,0,0,0,0,0] for _ in skeleton]
        pose[3][7]=90;pose[4][7]=90
        frames=[]
        for tick, angle in enumerate([-64,0,64]):
            p=copy.deepcopy(pose);p[0][8]=-10*tick
            p[1][7]=-180*math.cos(angle*2*math.pi/4096)
            p[2][3]=angle;p[4][3]=-angle;frames.append(p)
        fitted=copy.deepcopy(frames)
        for p in fitted:p[3][7]=70
        result,joints=clip_rig._plant_feet(frames,fitted,model,skeleton,
                                         {1:'carrier',2:'thigh',3:'shin',4:'foot'},{3},1)
        self.assertEqual(joints,{2,3,4})
        for old,new in zip(frames,result):
            self.assertEqual(old[0],new[0])
            self.assertEqual(new[3][6:9],[0,70,0])
            a=mmd.bone_matrices(model,old)[4];b=mmd.bone_matrices(model,new)[4]
            for axis in range(3):self.assertAlmostEqual(a[axis][3],b[axis][3],places=6)
        impossible=copy.deepcopy(frames)
        for p in impossible:p[4][6]=300
        with self.assertRaisesRegex(ValueError,'planted sole'):
            clip_rig._plant_feet(impossible,fitted,model,skeleton,
                                {1:'carrier',2:'thigh',3:'shin',4:'foot'},{3},1)


if __name__ == '__main__':
    unittest.main()
