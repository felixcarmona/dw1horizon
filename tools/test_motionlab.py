#!/usr/bin/env python3
"""Asset-free tests: contact gait, native topology and DW1 infinite-loop encoding."""
import copy
import math
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import motionlab as M


class MotionTests(unittest.TestCase):
    def setUp(self):
        self.skel = [(-1,-1),(1,0),(2,1),(3,2),(4,3),(5,1),(6,5),(7,6)]
        self.rest = [[4096,4096,4096,0,0,0,0,0,0] for _ in self.skel]
        for b,offset in {1:[0,-65,0],2:[10,0,0],3:[0,30,-10],4:[0,30,10],
                         5:[-10,0,0],6:[0,30,-10],7:[0,30,10]}.items():
            self.rest[b][6:9] = offset
        self.recipe = dict(schema=1,anatomy_status='reviewed',mode='biped',body=1,
                           legs=[dict(chain=[2,3,4],phase=0),dict(chain=[5,6,7],phase=.5)],arms=[],
                           slots={'0x02':dict(ticks=24,duty=.6,stride=28,step_height=8,crouch=6,bob=1)})
        self.spec = self.recipe['slots']['0x02']
        self.mod = SimpleNamespace(type=999,tmd=SimpleNamespace(obj_verts=lambda oi:[(-3,5,-5),(3,5,5)] if oi in (4,7) else [(0,0,0)]))
        self.exe = patch.object(M.mmd,'exe',return_value=SimpleNamespace(skeleton={999:self.skel}))
        self.exe.start()
        self.addCleanup(self.exe.stop)

    def test_rest_scale_guard_only_ignores_q12_unit_scale_rounding(self):
        self.assertFalse(M.has_scaled_rest_bones([[4095,4097,4096,0,0,0,0,0,0]]))
        self.assertTrue(M.has_scaled_rest_bones([[4093,4096,4096,0,0,0,0,0,0]]))

    def test_grounding_gate_is_absolute_unless_recipe_opts_into_input_baseline(self):
        self.assertEqual(M.mesh_ground_limit(),3.0)
        self.assertEqual(M.mesh_ground_limit(105.0,3.0),108.0)
        self.assertEqual(M.mesh_ground_limit(0.0,0.0),3.0)
        with self.assertRaises(ValueError):M.mesh_ground_limit(-1.0,3.0)

    def test_explicit_lateral_stance_keeps_native_lengths_and_ground_contacts(self):
        recipe=copy.deepcopy(self.recipe)
        recipe['legs'][0]['stance_x']=.12
        recipe['legs'][1]['stance_x']=-.12
        M.validate(recipe,self.skel)
        poses,contacts,clamp,floor=M.generate(self.mod,self.skel,self.rest,recipe,self.spec)
        self.assertEqual(clamp,0)
        rest=M.R.world_pos(self.skel,self.rest)
        for pose in poses:
            positions=M.R.world_pos(self.skel,pose)
            for leg in recipe['legs']:
                h,k,a=leg['chain']
                lengths=[math.dist(rest[h],rest[k]),math.dist(rest[k],rest[a])]
                self.assertAlmostEqual(math.dist(positions[h],positions[k]),lengths[0],places=6)
                self.assertAlmostEqual(math.dist(positions[k],positions[a]),lengths[1],places=6)
                self.assertAlmostEqual(positions[a][0],rest[h][0]+leg['stance_x']*sum(lengths),delta=.15)
        measured=M.measure(self.mod,self.skel,poses,contacts,recipe['legs'],floor)
        self.assertLess(measured['max_stance_height_error'],.2)
        self.assertLess(measured['stance_slip_percent_root_speed'],5)
        for invalid in [float('nan'),float('inf'),.751,-.751]:
            recipe['legs'][0]['stance_x']=invalid
            with self.subTest(stance_x=invalid),self.assertRaisesRegex(ValueError,'stance_x'):
                M.validate(recipe,self.skel)

    def test_contact_after_encoding_and_repeated_loops(self):
        samples,contacts,clamp,floor = M.generate(self.mod,self.skel,self.rest,self.recipe,self.spec)
        self.assertEqual(clamp,0)
        anim = M.mmd.encode_anim(samples,len(self.skel),0,tol=0,repeats=False)
        player = M.mmd.AnimPlayer(anim,len(self.skel),2)
        frames = []
        for _ in range(73):
            self.assertTrue(player.tick())
            pose = copy.deepcopy(player.pose)
            pose[0][6:9] = list(player.root)
            frames.append(pose)
        for t in range(49):
            self.assertEqual(frames[t][1:],frames[t+24][1:])
        measured = M.measure(self.mod,self.skel,frames,[contacts[t%24] for t in range(73)],self.recipe['legs'],floor)
        self.assertLess(measured['stance_slip_percent_root_speed'],5)
        self.assertLess(measured['max_stance_height_error'],.2)
        self.assertLess(measured['max_mesh_ground_penetration'],.2)

    def test_four_tick_fast_gait_survives_encoding_and_repeats_without_drift(self):
        recipe=copy.deepcopy(self.recipe)
        recipe['slots']['0x02'].update(ticks=4,gait_cycles=2)
        M.validate(recipe,self.skel)
        poses,contacts,clamp,floor=M.generate(self.mod,self.skel,self.rest,recipe,recipe['slots']['0x02'])
        self.assertEqual(len(poses),9)
        self.assertEqual(clamp,0)
        anim=M.mmd.encode_anim(poses,len(self.skel),0,tol=0,repeats=False)
        player=M.mmd.AnimPlayer(anim,len(self.skel),2)
        frames=[]
        for _ in range(25):
            self.assertTrue(player.tick())
            pose=copy.deepcopy(player.pose);pose[0][6:9]=list(player.root);frames.append(pose)
        self.assertEqual(frames[0][1:],frames[8][1:])
        self.assertEqual(frames[1][1:],frames[9][1:])
        measured=M.measure(self.mod,self.skel,frames,[contacts[t%8] for t in range(len(frames))],recipe['legs'],floor)
        self.assertLess(measured['stance_slip_percent_root_speed'],5)
        self.assertLess(measured['max_stance_height_error'],.2)
        self.assertLess(measured['max_mesh_ground_penetration'],.2)

    def test_generated_gait_retains_initial_material_reset_without_fast_repeated_blinks(self):
        poses=[copy.deepcopy(self.rest) for _ in range(8)]
        events=[(0,'tex',dict(src=(1,2),size=(2,3),dst=(4,5))),
                (3,'tex',dict(src=(6,7),size=(2,3),dst=(4,5))),
                (0,'sound',dict(bank=1,note=2))]
        anim=M.mmd.encode_anim(poses,len(self.skel),events=events,repeats=False)
        mod=SimpleNamespace(anims=SimpleNamespace(table=[None,None,0],anims=[anim]))
        actual=M.gesture_texture_events(mod,len(self.skel),{},12,2)
        self.assertEqual(len(actual),1)
        self.assertEqual(actual[0][:2],(0,'tex'))
        self.assertEqual({k:actual[0][2][k] for k in ('src','size','dst')},events[0][2])

    def test_battle_movement_requires_explicit_context_and_never_enables_training(self):
        recipe=copy.deepcopy(self.recipe);recipe['slots']={'0x23':self.spec}
        with self.assertRaisesRegex(ValueError,'explicitly'):M.validate(recipe,self.skel)
        recipe['include_battle_movement']=True;M.validate(recipe,self.skel)
        recipe['slots']={'0x1b':self.spec}
        with self.assertRaisesRegex(ValueError,'field locomotion'):M.validate(recipe,self.skel)

    def test_training_slot_cannot_be_replaced_by_a_field_gait(self):
        recipe=copy.deepcopy(self.recipe)
        recipe['slots']={'0x1b':self.spec}
        with self.assertRaisesRegex(ValueError,'field locomotion'):
            M.validate(recipe,self.skel)

    def test_stance_is_constant_world_contact(self):
        for duty in (.42,.62,.7):
            positions = []
            for i in range(20):
                phase = duty*i/20
                z,lift,contact = M.trajectory(phase,duty,40,12)
                self.assertTrue(contact)
                self.assertEqual(lift,0)
                positions.append(z-40/duty*phase)
            self.assertLess(max(positions)-min(positions),1e-10)

    def test_swing_meets_stance_with_matching_velocity(self):
        for boundary in (.62,1):
            eps = 1e-6
            def z(p):return M.trajectory(p%1,.62,40,12)[0]
            centre = z(boundary)
            before = (centre-z(boundary-eps))/eps
            after = (z(boundary+eps)-centre)/eps
            self.assertAlmostEqual(before,after,places=2)

    def test_topology_and_role_conflicts_are_rejected(self):
        changes = [lambda r:r['legs'][0].update(chain=[2,4,3]),
                   lambda r:r['legs'][1].update(chain=[2,3,4]),
                   lambda r:r.update(arms=[dict(root=3,phase=0)]),
                   lambda r:r.update(mode='quadruped'),
                   lambda r:r.update(anatomy_status='proposal'),
                   lambda r:r['slots']['0x02'].update(duty=0),
                   lambda r:r['slots']['0x02'].update(stride=math.nan)]
        for edit in changes:
            with self.subTest(edit=edit):
                recipe = copy.deepcopy(self.recipe)
                edit(recipe)
                with self.assertRaises(ValueError):M.validate(recipe,self.skel)

    def test_unreachable_targets_are_reported(self):
        spec = dict(self.spec,stride=500)
        _,_,clamp,_ = M.generate(self.mod,self.skel,self.rest,self.recipe,spec)
        self.assertGreater(clamp,100)

    def test_skeleton_fingerprint_catches_external_rig_changes(self):
        other = list(self.skel)
        other[4] = (4,2)
        self.assertNotEqual(M.skeleton_digest(self.skel),M.skeleton_digest(other))

    def test_whole_body_performance_keeps_contacts_over_two_strides(self):
        spec=copy.deepcopy(self.spec)
        spec['gait_cycles']=2
        spec['performance']=dict(tracks=[dict(bone=1,cycles=2,
            rotation=[[0,2,0,0],[.25,4,2,2],[.5,2,0,0],[.75,4,-2,-2]],
            translation=[[0,0,0,0],[.25,2,2,0],[.5,0,0,0],[.75,-2,2,0]])])
        frames,contacts,clamp,floor=M.generate(self.mod,self.skel,self.rest,self.recipe,spec)
        self.assertEqual(len(frames),49)
        self.assertEqual(clamp,0)
        self.assertGreater(len({tuple(p[1][3:9]) for p in frames}),12)
        result=M.measure(self.mod,self.skel,frames,contacts,self.recipe['legs'],floor)
        self.assertLess(result['stance_slip_percent_root_speed'],5)
        self.assertLess(result['max_stance_height_error'],.2)
        anim=M.mmd.encode_anim(frames,len(self.skel),0,tol=0,repeats=False)
        player=M.mmd.AnimPlayer(anim,len(self.skel),2)
        repeated=[]
        for _ in range(97):
            self.assertTrue(player.tick())
            repeated.append(copy.deepcopy(player.pose))
        for i in range(49):self.assertEqual(repeated[i][1:],repeated[i+48][1:])

    def test_authored_curve_closes_with_continuous_velocity(self):
        keys=[[0,0,1,2],[.2,3,4,5],[.5,-1,2,3],[.8,-2,0,1]]
        for phase,*value in keys:self.assertEqual(M.periodic_curve(keys,phase),value)
        eps=1e-6
        before=M.periodic_curve(keys,1-eps);centre=M.periodic_curve(keys,0);after=M.periodic_curve(keys,eps)
        for a,b,c in zip(before,centre,after):self.assertAlmostEqual((b-a)/eps,(c-b)/eps,places=3)

    def test_native_blink_keeps_its_duration_in_longer_gait(self):
        events=[(0,'tex',dict(src=(0,0),size=(1,1),dst=(0,0))),
                (10,'tex',dict(src=(1,0),size=(1,1),dst=(0,0))),
                (11,'tex',dict(src=(2,0),size=(1,1),dst=(0,0))),
                (13,'tex',dict(src=(1,0),size=(1,1),dst=(0,0))),
                (14,'tex',dict(src=(0,0),size=(1,1),dst=(0,0)))]
        anim=M.mmd.encode_anim([copy.deepcopy(self.rest) for _ in range(25)],len(self.skel),0,events,tol=0,repeats=False)
        mod=SimpleNamespace(anims=SimpleNamespace(table=[0],anims=[anim]))
        remapped=M.gesture_texture_events(mod,len(self.skel),dict(performance=dict(texture_slot='0x00')),49)
        self.assertEqual([t for t,_,_ in remapped],[0,30,31,33,34])

    def test_texture_copy_uses_vram_words_and_snapshot_for_overlap(self):
        pixels=list(range(64));original=list(pixels)
        M.texture_move(pixels,16,4,dict(src=(0,0),size=(2,2),dst=(1,1)))
        self.assertEqual(pixels[20:28],original[0:8])
        self.assertEqual(pixels[36:44],original[16:24])
        with self.assertRaises(ValueError):M.texture_move(pixels,16,4,dict(src=(3,0),size=(2,2),dst=(0,0)))

    def test_source_reference_pose_is_blended_on_selected_bones(self):
        reference=copy.deepcopy(self.rest);reference[1][3]=100
        anim=M.mmd.encode_anim([copy.deepcopy(reference) for _ in range(25)],len(self.skel),0,tol=0,repeats=False)
        mod=copy.copy(self.mod);mod.anims=SimpleNamespace(table=[0],anims=[anim])
        spec=copy.deepcopy(self.spec)
        spec['performance']=dict(reference_pose=dict(slot='0x00',bones=[1],weight=.5))
        frames,_,clamp,_=M.generate(mod,self.skel,self.rest,self.recipe,spec)
        self.assertEqual(frames[0][1][3],50)
        self.assertEqual(frames[0][1][6:9],self.rest[1][6:7]+[self.rest[1][7]+spec['crouch'],self.rest[1][8]])
        self.assertEqual(self.rest[1][3],0)
        self.assertEqual(clamp,0)

    def test_explicit_knee_direction_overrides_rest_pose_guess(self):
        recipe=copy.deepcopy(self.recipe)
        for leg in recipe['legs']:leg['knee_pole']=[0,0,-1]
        forward,_,_,_=M.generate(self.mod,self.skel,self.rest,recipe,self.spec)
        for leg in recipe['legs']:leg['knee_pole']=[0,0,1]
        backward,_,_,_=M.generate(self.mod,self.skel,self.rest,recipe,self.spec)
        front=M.R.world_pos(self.skel,forward[6])[3][2]
        back=M.R.world_pos(self.skel,backward[6])[3][2]
        self.assertLess(front,back-10)

    def test_slot_support_phases_can_change_between_walk_and_trot(self):
        spec=dict(self.spec,leg_phases=[0,0])
        M.validate(dict(self.recipe,slots={'0x02':spec}),self.skel)
        _,contacts,_,_=M.generate(self.mod,self.skel,self.rest,self.recipe,spec)
        self.assertTrue(all(a==b for a,b in contacts))
        _,original,_,_=M.generate(self.mod,self.skel,self.rest,self.recipe,self.spec)
        self.assertTrue(any(a!=b for a,b in original))
        with self.assertRaises(ValueError):M.validate(dict(self.recipe,slots={'0x02':dict(spec,leg_phases=[0])}),self.skel)

    def test_branch_partition_keeps_empty_joint_and_avoids_duplicate_limbs(self):
        shape = SimpleNamespace(parent=[-1,0,1,2,3,1,5,6],
                                joint=[[0,0,0],[0,-.8,0],[.1,-.6,0],[.2,-.3,0],[.2,-.1,0],
                                       [-.1,-.6,0],[-.2,-.3,0],[-.2,-.1,0]],
                                tip=[[0,0,0],[0,-.8,0],[.1,-.6,0],[.2,-.3,0],[.2,-.1,0],
                                     [-.1,-.6,0],[-.2,-.3,0],[-.2,-.1,0]],mass=[0,10,0,10,10,0,10,10])
        shape.ancestors = lambda b:list(M.ancestors([(0,p) for p in shape.parent],b))
        groups = M.branches(shape)
        self.assertEqual(len(groups),2)
        self.assertEqual(groups[0]['bones'],[2,3,4])
        self.assertEqual(groups[0]['paired_root'],5)
        self.assertEqual(groups[1]['paired_root'],2)


if __name__ == '__main__':
    unittest.main()
