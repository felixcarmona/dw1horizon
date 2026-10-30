"""Asset-free tests of tools/motioncyclelayer.py (field action review, event layering, shared streams).

    python3 tools/test_motioncyclelayer.py
"""
import copy,unittest
from motioncyclelayer import layer,combine_events,repeat_native,share_identical_streams,normalize_field_world_support

class CycleLayerTest(unittest.TestCase):
    def test_condition_actions_need_explicit_review_and_cannot_replace_source(self):
        from motioncyclelayer import require_field_action
        for slot in [1,18]:
            for basis in [None,'', ' ', True]:
                with self.subTest(slot=slot,basis=basis),self.assertRaises(ValueError):
                    require_field_action(slot,33,basis)
            require_field_action(slot,33,'Reviewed tail branch only; preserve condition body and events')
            with self.assertRaises(ValueError):require_field_action(slot,slot,'reviewed')
        for slot in [0,5,33,True]:
            with self.assertRaises(ValueError):require_field_action(slot,33,'reviewed')

    def test_native_support_attachment_translation_keeps_field_orientation_and_travel(self):
        import retarget as R
        sk=[(-1,-1),(-1,0),(-1,1)]
        field=[self.frame() for _ in range(3)];native=[self.frame() for _ in range(5)]
        for t,p in enumerate(field):p[0][8]=-10*t;p[2][3:6]=[100,200,300];p[2][6:9]=[2,20,4]
        for t,p in enumerate(native):
            p[1][4]=[0,100,200,100,0][t];p[2][6:9]=[3,21,[0,4,8,4,0][t]]
        before=copy.deepcopy((field,native))
        out,proof=layer(field,native,[1],2,0,sk,field_world_roots=[2],native_translation_roots=[2])
        for t,p in enumerate(out):
            self.assertEqual(p[2][6:9],native[t][2][6:9])
            self.assertEqual(p[0][8],-10*t)
            a,b=R.world_rots(sk,p)[2],R.world_rots(sk,field[t%2])[2]
            self.assertLess(max(abs(a[i][j]-b[i][j]) for i in range(3) for j in range(3)),.005)
        self.assertEqual(proof['native_translation_roots'],[2]);self.assertEqual((field,native),before)
        default,_=layer(field,native,[1],2,0,sk,field_world_roots=[2])
        self.assertTrue(all(p[2][6:9]==[2,20,4] for p in default))
        for roots in [[0],[1],[2,2],[True]]:
            with self.assertRaises(ValueError):layer(field,native,[1],2,0,sk,field_world_roots=[2],native_translation_roots=roots)

    def test_static_uniform_body_retains_scale_and_world_limb_orientation(self):
        import retarget as R
        from motioncyclelayer import static_uniform_field_body
        sk=[(-1,-1),(-1,0),(-1,1)];field=[self.frame() for _ in range(3)];native=copy.deepcopy(field)
        policy=dict(bone=1,scale=5324,review_basis='fixed native1.3 scale')
        for p in field+native:p[1][:3]=[5324]*3
        native[1][1][3]=200;field[1][2][4]=300
        before=copy.deepcopy((field,native));out,_=layer(field,native,[1],1,0,sk,field_world_roots=[2],static_field_body=policy)
        for p,f in zip(out,field):
            self.assertEqual(p[1][:3],[5324]*3)
            a,b=R.world_rots(sk,p)[2],R.world_rots(sk,f)[2]
            self.assertLess(max(abs(a[i][j]-b[i][j]) for i in range(3) for j in range(3)),.005)
        self.assertEqual((field,native),before)
        native[1][1][0]+=1
        with self.assertRaisesRegex(ValueError,'scale changed'):layer(field,native,[1],1,0,sk,field_world_roots=[2],static_field_body=policy)
        for bad in [dict(policy,bone=2),dict(policy,scale=True),dict(policy,review_basis='')]:
            with self.assertRaises(ValueError):static_uniform_field_body(sk,field,bad)

    def test_equivalent_euler_endpoint_closes_without_hiding_pose_change(self):
        from motioncyclelayer import close_equivalent_field_rotations
        import motionlab as M,motionloops
        from types import SimpleNamespace
        poses=[self.frame() for _ in range(3)]
        poses[0][2][3:6]=[100,200,300]
        poses[1][2][3:6]=[300,400,500]
        poses[2][2][3:6]=[2148,1848,2348]
        middle=copy.deepcopy(poses[1]);proof=close_equivalent_field_rotations(poses,[2])
        self.assertEqual(poses[-1][2],poses[0][2]);self.assertEqual(poses[1],middle);self.assertEqual(len(proof),1)
        anim=M.mmd.encode_anim(poses,3,loop_sample=0,events=[],tol=0,repeats=False)
        mod=SimpleNamespace(anims=SimpleNamespace(anims=[anim],table=[0]))
        self.assertEqual(motionloops.audit_animation(mod,[(-1,-1),(-1,0),(-1,1)],0,cycles=8)['status'],'stable')
        poses[-1][2][4]+=100
        with self.assertRaisesRegex(ValueError,'not equivalent'):close_equivalent_field_rotations(poses,[2])

    def test_native_attachment_keeps_own_motion_relative_to_current_body(self):
        import retarget as R
        sk=[(-1,-1),(-1,0),(-1,1),(-1,2),(-1,3)]
        def pose():return [[4096]*3+[0]*6 for _ in sk]
        field=[pose() for _ in range(3)];native=[pose() for _ in range(3)]
        for t,(p,angle) in enumerate(zip(field,[200,-500,200])):
            p[0][8]=t*6;p[1][4]=100;p[1][7]=20;p[2][3]=angle;p[2][7]=10;p[3][6]=8;p[4][8]=5
        for p,angle in zip(native,[30,200,30]):
            p[1][4]=angle;p[1][7]=-30;p[2][3]=-300;p[2][7]=10;p[3][6]=8;p[3][7]=-20;p[3][5]=angle;p[4][8]=5
        before=copy.deepcopy((field,native));out,proof=layer(field,native,[3,4],1,0,sk,native_anchors={3:1})
        for actual,source,base in zip(out,native,field):
            ar=R.world_rots(sk,actual);nr=R.world_rots(sk,source);ap=R.world_pos(sk,actual);np=R.world_pos(sk,source)
            for bone in [3,4]:
                a=[sum(R.m3t(ar[1])[i][j]*(ap[bone][j]-ap[1][j]) for j in range(3)) for i in range(3)]
                b=[sum(R.m3t(nr[1])[i][j]*(np[bone][j]-np[1][j]) for j in range(3)) for i in range(3)]
                self.assertLess(sum((x-y)**2 for x,y in zip(a,b))**.5,1)
                a=R.m3mul(R.m3t(ar[1]),ar[bone]);b=R.m3mul(R.m3t(nr[1]),nr[bone])
                self.assertLess(max(abs(a[i][j]-b[i][j]) for i in range(3) for j in range(3)),.002)
            self.assertEqual(actual[:3],base[:3]);self.assertEqual(actual[4],source[4])
        self.assertEqual((field,native),before);self.assertLess(proof['maximum_anchor_position_error'],1)

    def test_native_attachment_rejects_invalid_boundary_anchor_and_scale(self):
        sk=[(-1,-1),(-1,0),(-1,1)];field=[self.frame() for _ in range(3)];native=copy.deepcopy(field)
        for anchors in [{2:2},{2:0},{2:9},{1:2},{2:True}]:
            with self.assertRaises(ValueError):layer(field,native,[2],1,0,sk,native_anchors=anchors)
        with self.assertRaises(ValueError):layer(field,native,[1,2],1,0,sk,native_anchors={2:1})
        with self.assertRaises(ValueError):layer(field,native,[2],1,0,sk,native_world_roots=[2],native_anchors={2:1})
        native[1][1][0]=4095
        with self.assertRaisesRegex(ValueError,'unit ancestor scales'):layer(field,native,[2],1,0,sk,native_anchors={2:1})

    def test_field_support_noise_normalization_checks_real_mesh_and_keeps_sources(self):
        from types import SimpleNamespace
        from unittest.mock import patch
        import motionlab as M
        sk=[(-1,-1),(-1,0),(0,1)]
        field=[self.frame() for _ in range(3)];native=copy.deepcopy(field)
        native[1][1][:3]=[4095]*3;before=copy.deepcopy((field,native))
        model=SimpleNamespace(type=999,tmd=SimpleNamespace(obj_verts=lambda _: [[0,0,500]]))
        with patch.object(M.mmd,'exe',return_value=SimpleNamespace(skeleton={999:sk})):
            a,b,proof=normalize_field_world_support(model,sk,field,native,[2],1,'measured one-unit import scale noise')
            self.assertEqual(b[1][1][:3],[4096]*3);self.assertEqual(a,field)
            self.assertGreater(proof['maximum_mesh_vertex_shift'],0);self.assertLess(proof['maximum_mesh_vertex_shift'],1)
            model.tmd.obj_verts=lambda _: [[0,0,10000]]
            with self.assertRaisesRegex(ValueError,'moves mesh'):normalize_field_world_support(model,sk,field,native,[2],1,'review')
        self.assertEqual((field,native),before)
        for tolerance,basis in [(0,'review'),(2,'review'),(True,'review'),(1,None)]:
            with self.assertRaises(ValueError):normalize_field_world_support(model,sk,field,native,[2],tolerance,basis)

    def test_field_limb_world_orientation_survives_native_body_restore(self):
        import retarget as R
        sk=[(-1,-1),(-1,0),(-1,1),(-1,2)]
        def pose():return [[4096]*3+[0]*6 for _ in sk]
        field=[pose() for _ in range(3)];native=[pose() for _ in range(5)]
        for i,(p,x) in enumerate(zip(field,[200,-100,200])):
            p[0][8]=i*6;p[1][3]=x;p[2][4]=[30,60,30][i];p[3][5]=[70,-90,70][i];p[3][7]=10
        for p,x in zip(native,[0,400,0,-400,0]):p[1][3]=x
        before=copy.deepcopy((field,native))
        out,proof=layer(field,native,[1],2,0,sk,field_world_roots=[2])
        for t,p in enumerate(out):
            source=field[t%2];a=R.world_rots(sk,p);b=R.world_rots(sk,source)
            for bone in [2,3]:self.assertLess(max(abs(a[bone][i][j]-b[bone][i][j]) for i in range(3) for j in range(3)),.002)
            self.assertEqual(p[1],native[t][1]);self.assertEqual(p[2][:3]+p[2][6:],source[2][:3]+source[2][6:]);self.assertEqual(p[3],source[3]);self.assertEqual(p[0][8],t*6)
            import math
            positions=R.world_pos(sk,p);self.assertAlmostEqual(math.dist(positions[2],positions[3]),10)
        self.assertEqual((field,native),before);self.assertLess(proof['maximum_field_world_rotation_matrix_error'],.002)

    def test_field_world_roots_reject_selected_unbounded_or_scaled_branches(self):
        sk=[(-1,-1),(-1,0),(-1,1)];field=[self.frame() for _ in range(3)];native=copy.deepcopy(field)
        for roots in [[1],[2,2],[0],[9]]:
            with self.assertRaises(ValueError):layer(field,native,[1],1,0,sk,field_world_roots=roots)
        native[1][1][0]=4095
        with self.assertRaisesRegex(ValueError,'unit ancestor scales'):layer(field,native,[1],1,0,sk,field_world_roots=[2])

    def test_stream_sharing_preserves_slots_and_omits_unused_programs(self):
        from types import SimpleNamespace
        programs=[SimpleNamespace(build=lambda v=v:v) for v in [b'pose+sound1',b'unused',b'pose+sound1',b'pose+sound2']]
        table=[2,None,0,3,2];before=list(table)
        animations,new_table=share_identical_streams(programs,table)
        self.assertEqual(len(animations),2);self.assertEqual(table,before)
        self.assertEqual(new_table,[0,None,0,1,0])
        for old,new in zip(table,new_table):
            if old is not None:self.assertEqual(programs[old].build(),animations[new].build())
    def test_identical_pose_with_different_event_bytes_is_not_shared(self):
        from types import SimpleNamespace
        programs=[SimpleNamespace(build=lambda v=v:v) for v in [b'pose+sound1',b'pose+sound2',b'pose+texture']]
        animations,table=share_identical_streams(programs,[0,1,2])
        self.assertEqual(len(animations),3);self.assertEqual(table,[0,1,2])

    def test_native_audio_ownership_preserves_native_and_field_payloads(self):
        field=[(0,'tex',{'frame':1,'src':(9,9)}),(1,'sound',{'frame':2,'bank':1,'note':3})]
        native=[(0,'tex',{'frame':1,'src':(2,4)}),(2,'sound',{'frame':3,'bank':1,'note':15})]
        events,proof=combine_events(field,native,2,4,2,'native_with_field_sounds')
        self.assertEqual([(t,k,p.get('note')) for t,k,p in events],[(0,'tex',None),(1,'sound',3),(2,'sound',15),(3,'sound',3)])
        self.assertEqual(events[0][2]['src'],(2,4));self.assertEqual(proof['native_sound_events_preserved'],1);self.assertEqual(proof['field_sound_events_preserved'],2)
        self.assertEqual(proof['native_texture_event_mapping'],[dict(source_tick=0,target_tick=0)])
        with self.assertRaises(ValueError):combine_events(field,native,2,4,2,'native_texture_with_field_sounds')
    def test_native_audio_policy_rejects_unowned_effect_commands(self):
        with self.assertRaises(ValueError):combine_events([],[(0,'tex_scroll',{})],2,2,1,'native_with_field_sounds')
    def test_world_branch_retains_native_parent_compensation(self):
        import retarget as R
        sk=[(-1,-1),(-1,0),(-1,1)]
        field=[self.frame() for _ in range(3)]
        native=[self.frame() for _ in range(3)]
        for p,x in zip(field,[200,-100,200]):p[1][3]=x
        for p,x in zip(native,[0,400,0]):p[1][3]=x;p[2][3]=-x
        before=copy.deepcopy((field,native))
        out,proof=layer(field,native,[2],1,0,sk,[2])
        for actual,source,base in zip(out,native,field):
            a=R.world_rots(sk,actual)[2];b=R.world_rots(sk,source)[2]
            self.assertLess(max(abs(a[i][j]-b[i][j]) for i in range(3) for j in range(3)),.002)
            self.assertEqual(actual[1],base[1]);self.assertEqual(actual[0],base[0])
        self.assertEqual((field,native),before)
        self.assertLess(proof['maximum_world_rotation_matrix_error'],.002)
    def test_world_branch_explicit_uniform_ancestors_keep_original_scales(self):
        import retarget as R
        sk=[(-1,-1),(-1,0),(-1,1)]
        field=[self.frame() for _ in range(3)];native=[self.frame() for _ in range(3)]
        for p,x in zip(field,[200,-100,200]):p[1][:3]=[6144]*3;p[1][3]=x
        for p,x in zip(native,[0,400,0]):p[1][:3]=[6144]*3;p[1][3]=x;p[2][3]=-x;p[2][:3]=[4095,4096,4097]
        out,proof=layer(field,native,[2],1,0,sk,[2],True)
        self.assertTrue(proof['positive_uniform_world_orientation_ancestors'])
        from types import SimpleNamespace
        from unittest.mock import patch
        import math,motionlab as M
        with patch.object(M.mmd,'exe',return_value=SimpleNamespace(skeleton={999:sk})):
            for actual,source in zip(out,native):
                a=M.mmd.bone_matrices(SimpleNamespace(type=999),actual)[2]
                b=M.mmd.bone_matrices(SimpleNamespace(type=999),source)[2]
                for j in range(3):
                    na=math.sqrt(sum(a[i][j]**2 for i in range(3)))
                    nb=math.sqrt(sum(b[i][j]**2 for i in range(3)))
                    self.assertLess(max(abs(a[i][j]/na-b[i][j]/nb) for i in range(3)),.002)
        for actual,source,base in zip(out,native,field):
            self.assertEqual(actual[1],base[1]);self.assertEqual(actual[2][:3],source[2][:3])
            a=R.world_rots(sk,actual)[2];b=R.world_rots(sk,source)[2]
            self.assertLess(max(abs(a[i][j]-b[i][j]) for i in range(3) for j in range(3)),.002)
        field[1][1][0]=6143
        with self.assertRaisesRegex(ValueError,'uniform ancestor'):layer(field,native,[2],1,0,sk,[2],True)
        field[1][1][:3]=[-6144]*3
        with self.assertRaisesRegex(ValueError,'uniform ancestor'):layer(field,native,[2],1,0,sk,[2],True)

    def test_world_branch_rejects_scaled_ancestors_and_nonboundary(self):
        sk=[(-1,-1),(-1,0),(-1,1)];f=[self.frame() for _ in range(3)]
        with self.assertRaises(ValueError):layer(f,f,[1,2],1,0,sk,[2])
        n=copy.deepcopy(f);n[1][1][0]=4000
        with self.assertRaises(ValueError):layer(f,n,[2],1,0,sk,[2])
    def frame(self,root=0,body=0,arm=0):
        p=[[4096]*3+[0]*6 for _ in range(3)];p[0][8]=root;p[1][7]=body;p[2][3]=arm;return p
    def test_repeats_hop_and_transport_without_speed_change(self):
        f=[self.frame(0,-1),self.frame(-4,-8),self.frame(-8,-1)]
        n=[self.frame(arm=x) for x in [0,100,200,100,0]]
        before=copy.deepcopy((f,n));out,proof=layer(f,n,[2],2,0)
        self.assertEqual([p[0][8] for p in out],[0,-4,-8,-12,-16]);self.assertEqual([p[1][7] for p in out],[-1,-8,-1,-8,-1]);self.assertEqual([p[2][3] for p in out],[0,100,200,100,0]);self.assertEqual((f,n),before)
    def test_preserves_two_full_native_turns(self):
        f=[self.frame() for _ in range(3)];n=[self.frame(arm=i*1024) for i in range(9)]
        out,_=layer(f,n,[2],4,0)
        self.assertEqual([p[2][3] for p in out],[i*1024 for i in range(9)])

    def test_repeats_native_turns_and_event_clock(self):
        native=[self.frame(arm=i*1024) for i in range(9)];before=copy.deepcopy(native)
        poses,events=repeat_native(native,[(1,'tex',{'frame':2,'src':(0,0)})],[2],2)
        self.assertEqual(poses[8][2][3],8192);self.assertEqual(poses[-1][2][3],16384)
        self.assertEqual([e[0] for e in events],[1,9]);self.assertEqual([e[2]['frame'] for e in events],[2,10]);self.assertEqual(native,before)
    def test_rejects_unclosed_native_or_rotation_overflow(self):
        with self.assertRaises(ValueError):repeat_native([self.frame(body=x) for x in [0,3,2]],[],[1],2)
        with self.assertRaises(ValueError):repeat_native([self.frame(arm=i*1024) for i in range(9)],[],[2],8)
    def test_multiple_clocks_preserve_field_velocity(self):
        field=[self.frame(root=-i,body=-i%2) for i in range(3)]
        native=[self.frame(arm=x) for x in [0,100,0]]
        poses,events=repeat_native(native,[],[2],3)
        combined,proof=layer(field,poses,[2],3,0)
        self.assertEqual([p[0][8] for p in combined],list(range(0,-7,-1)))
        self.assertEqual([p[2][3] for p in combined],[0,100,0,100,0,100,0])

    def test_reject_retime_and_root_ownership(self):
        f=[self.frame() for _ in range(3)];n=[self.frame() for _ in range(10)]
        with self.assertRaises(ValueError):layer(f,n,[2],1,.2)
        with self.assertRaises(ValueError):layer(f,n,[0],4,.2)
    def test_fractional_retime_crosses_angle_wrap_without_long_spin(self):
        f=[self.frame() for _ in range(7)];n=[self.frame(arm=x) for x in [2000,-2000,-1900,-2000,2000,2000]]
        out,_=layer(f,n,[2],1,.2)
        self.assertLess(abs(out[1][2][3]-2000),100)
        self.assertEqual(out[-1][2][3],2000)

    def test_native_angle_wrap_uses_short_path(self):
        f=[self.frame() for _ in range(3)];n=[self.frame(arm=x) for x in [2000,-2000,2000]]
        out,_=layer(f,n,[2],1,0)
        self.assertEqual([p[2][3] for p in out],[2000,-2000,2000])

class EventOwnershipTest(unittest.TestCase):
    def test_preserves_blink_states_and_repeats_field_sounds(self):
        native=[(t,'tex',dict(frame=t+1,src=(i*6,72),size=(6,24),dst=(6,72))) for i,t in enumerate([0,19,20,22,23])]
        field=[(0,'tex',dict(frame=1,src=(0,0),size=(1,1),dst=(4,0))),(2,'sound',dict(frame=3,bank=1,note=16))]
        before=copy.deepcopy((field,native));out,proof=combine_events(field,native,17,39,2,'native_texture_with_field_sounds')
        textures=[e for e in out if e[1]=='tex'];sounds=[e for e in out if e[1]=='sound']
        self.assertEqual([e[0] for e in textures],[0,17,18,19,20]);self.assertEqual([e[0] for e in sounds],[2,19])
        self.assertEqual([e[2]['src'] for e in textures],[e[2]['src'] for e in native]);self.assertEqual(proof['original_field_texture_events_replaced'],2)
        self.assertEqual((field,native),before)
    def test_rejects_implicit_dropped_events_or_impossible_schedule(self):
        with self.assertRaises(ValueError):combine_events([],[(0,'sound',{})],2,4,2)
        with self.assertRaises(ValueError):combine_events([],[(0,'sound',{})],2,4,2,'native_texture_with_field_sounds')
        with self.assertRaises(ValueError):combine_events([],[(i,'tex',{}) for i in range(4)],2,4,1,'native_texture_with_field_sounds')

if __name__=='__main__':unittest.main()
