#!/usr/bin/env python3
"""Asset-free support-pivot and secondary-response checks."""
import copy,math,unittest
import motionlab as M
import motionsecondary as S

class GeometryContact(unittest.TestCase):
    def test_cyclic_euler_branches_preserve_pose_and_remove_alternate_seam(self):
        rotations=[[100,950,200],[110,1000,210],[120,1050,220],
                   [130,1000,230],[140,950,240]]
        frames=[[[4096]*3+[0]*6,[4096]*3+r+[7,8,9]] for r in rotations]
        frames.append(copy.deepcopy(frames[0]))
        # Same rotation, different Euler representation at the last live pose.
        x,y,z=frames[-2][1][3:6];frames[-2][1][3:6]=[x+2048,2048-y,z+2048]
        fixed=S.cyclic_euler_branches(frames,[1])
        for before,after in zip(frames,fixed):
            self.assertEqual(before[0],after[0])
            self.assertEqual(before[1][:3]+before[1][6:],after[1][:3]+after[1][6:])
            a=M.mmd.rot_matrix(*before[1][3:6]);b=M.mmd.rot_matrix(*after[1][3:6])
            self.assertLess(max(abs(x-y) for ra,rb in zip(a,b) for x,y in zip(ra,rb)),1e-12)
        delta=lambda a,b:sum(((y-x+2048)%4096-2048)**2 for x,y in zip(a,b))
        self.assertLess(delta(fixed[-2][1][3:6],fixed[-1][1][3:6]),10000)
        self.assertEqual(fixed[0][1],fixed[-1][1])

    def test_native_chain_bend_is_invariant_under_scene_translation(self):
        native=[[-10,-70,8],[-15,-30,-12],[-10,0,4]]
        root=[-8,-68,9];target=[5,-1,15];shift=[235,-875,3290]
        knee,end=S.solve_native_chain(*native,root,target)
        moved=lambda p:[a+b for a,b in zip(p,shift)]
        shifted_knee,shifted_end=S.solve_native_chain(
            *[moved(p) for p in native],moved(root),moved(target))
        for original,translated in [(knee,shifted_knee),(end,shifted_end)]:
            for a,b,delta in zip(original,translated,shift):
                self.assertAlmostEqual(a+delta,b)
        self.assertAlmostEqual(math.dist(root,knee),math.dist(native[0],native[1]))
        self.assertAlmostEqual(math.dist(knee,end),math.dist(native[1],native[2]))
        self.assertLess(math.dist(end,target),1e-6)

    def test_bounded_support_lift_clears_shin_heel_and_retains_toe_heading(self):
        hip=[0,-70,0];toe=[(0,0,-30),(0,0,5)];heel=[(0,44,5),(0,44,15),(5,30,0)]
        def surfaces(lift):
            ankle=[0,-lift,0];knee,actual=M.legik.solve(hip,ankle,40,40,[0,0,-1])
            shin=M.R.swing([0,40,0],M.legik.sub(actual,knee))
            ys=[ankle[1]+v[1] for v in toe]
            ys += [knee[1]+sum(shin[1][j]*v[j] for j in range(3)) for v in heel]
            return max(ys),knee,actual
        self.assertGreater(surfaces(0)[0],0)
        lift=S.bounded_support_lift(lambda x:surfaces(x)[0],20,tolerance=.0001)
        error,knee,ankle=surfaces(lift)
        self.assertGreater(lift,.1);self.assertLessEqual(error,.0001)
        self.assertAlmostEqual(math.dist(hip,knee),40);self.assertAlmostEqual(math.dist(knee,ankle),40)
        self.assertEqual(ankle[0],0);self.assertAlmostEqual(ankle[2],0)
        self.assertLess(ankle[1],-.1)  # heel may support while toe stays above ground
        with self.assertRaisesRegex(ValueError,'reviewed'):
            S.bounded_support_lift(lambda x:surfaces(x)[0],.01)
    def test_bounded_support_lift_leaves_clear_geometry_and_rejects_nonfinite(self):
        self.assertEqual(S.bounded_support_lift(lambda x:-1,20),0)
        with self.assertRaises(ValueError):S.bounded_support_lift(lambda x:float('nan'),20)
        with self.assertRaises(ValueError):S.bounded_support_lift(lambda x:1,float('inf'))
    def test_same_side_paws_need_longitudinal_clearance_only_when_overlapping(self):
        identity=M.mmd.rot_matrix(0,0,0)
        cube=[(x,y,z) for x in (-2,2) for y in (-2,2) for z in (-5,5)]
        vertices=[cube,cube];rotations=[identity,identity]
        self.assertEqual(S.foot_pair_clearance(vertices,rotations,[[0,0,-3],[0,0,3]],1,axis=2),5)
        self.assertEqual(S.foot_pair_clearance(vertices,rotations,[[0,0,-3],[0,-5,3]],1,axis=2),0)
        self.assertEqual(S.foot_pair_clearance(vertices,rotations,[[0,0,-3],[5,0,3]],1,axis=2),0)
        with self.assertRaisesRegex(ValueError,'horizontal'):
            S.foot_pair_clearance(vertices,rotations,[[0,0,0],[0,0,0]],1,axis=1)

    def test_rocking_contact_transfer_and_real_sliding_are_distinguished(self):
        vertices=[(x,y,z) for x in [-10,10] for y in [-5,12] for z in [-90,15]]
        surfaces=[]
        for angle in [-2,2]:
            rotation,dz,sole=S.rolling_foot(vertices,M.mmd.rot_matrix(0,0,0),angle)
            surfaces.append([[sum(rotation[i][j]*v[j] for j in range(3))+[0,-sole,dz][i]
                              for i in range(3)] for v in vertices])
        self.assertFalse(any(abs(a[1])<1 and abs(b[1])<1 for a,b in zip(*surfaces)))
        self.assertLess(S.support_transfer_displacement(*surfaces),.2)
        translated=[[x,y,z+20] for x,y,z in surfaces[1]]
        self.assertGreater(S.support_transfer_displacement(surfaces[0],translated),19)

    def test_appendage_clearance_uses_the_smallest_feasible_hinge(self):
        points=[[0,5,-30],[0,-10,-20]];origin=[0,-20,0]
        rotation=S.clearance_rotation(points,origin,[1,0,0],[-30,0],0)
        ys=[sum(rotation[1][j]*(p[j]-origin[j]) for j in range(3))+origin[1] for p in points]
        self.assertAlmostEqual(max(ys),0,places=3)
        self.assertLess(rotation[2][1],0)

    def test_appendage_clearance_leaves_a_clear_pose_unchanged(self):
        self.assertEqual(S.clearance_rotation([[0,-10,-30]],[0,-20,0],[1,0,0],[-30,0],0),
                         M.mmd.rot_matrix(0,0,0))

    def test_appendage_clearance_rejects_impossible_limits(self):
        with self.assertRaisesRegex(ValueError,'clear'):
            S.clearance_rotation([[0,20,0]],[0,0,0],[1,0,0],[-5,5],0)

    def test_compound_boot_grounds_shin_heel_without_forcing_toe_down(self):
        identity=M.mmd.rot_matrix(0,0,0)
        toe=[(0,0,-30),(0,0,5),(10,-5,0)]
        heel=[(0,44,5),(0,44,15),(5,30,0)]
        hip=[0,-70,0]
        for angle in [-10,0,10]:
            rotation,dz,sole=S.rolling_foot(toe,identity,angle)
            target=[0,-sole,dz]
            ankle,rotation,result_angle=S.compound_foot(toe,identity,angle,target,hip,
                [40,40],[0,0,-1],heel,[0,40,0],identity,0)
            knee,actual=M.legik.solve(hip,ankle,40,40,[0,0,-1])
            shin=M.R.swing([0,40,0],M.legik.sub(actual,knee))
            lows=[sum(rotation[1][j]*v[j] for j in range(3))+ankle[1] for v in toe]
            lows += [sum(shin[1][j]*v[j] for j in range(3))+knee[1] for v in heel]
            self.assertAlmostEqual(max(lows),0,places=3)
            self.assertEqual(result_angle,angle)
            self.assertAlmostEqual(math.dist(hip,knee),40)
            self.assertAlmostEqual(math.dist(knee,actual),40)

    def test_compound_support_rejects_unreachable_leg(self):
        identity=M.mmd.rot_matrix(0,0,0)
        with self.assertRaisesRegex(ValueError,'reach'):
            S.compound_foot([(0,0,0)],identity,0,[0,0,0],[0,-100,0],
                [10,10],[0,0,-1],[(0,0,0)],[0,10,0],identity,0)

    def test_heel_and_toe_roll_preserve_support_footprint(self):
        # A long rigid foot: keeping its ankle fixed would penetrate the floor.
        vertices=[(x,y,z) for x in [-10,10] for y in [-5,12] for z in [-90,15]]
        identity=M.mmd.rot_matrix(0,0,0)
        for angle in [-28,-12,0,12,28]:
            rotation,dz,sole=S.rolling_foot(vertices,identity,angle)
            points=[[sum(rotation[i][j]*v[j] for j in range(3)) for i in range(3)] for v in vertices]
            index=max(range(len(points)),key=lambda i:points[i][1])
            self.assertAlmostEqual(points[index][1]-sole,0)
            self.assertAlmostEqual(points[index][2]+dz,vertices[index][2])
            self.assertTrue(all(p[1]-sole<=1e-9 for p in points))

    def test_contact_metric_checks_foot_surface_instead_of_moving_ankle(self):
        # The same toe stays planted while the ankle moves through an arc.
        v=[(0,0,-90),(0,0,15),(10,-5,0)]
        first=S.rolling_foot(v,M.mmd.rot_matrix(0,0,0),10)
        second=S.rolling_foot(v,M.mmd.rot_matrix(0,0,0),18)
        toe=[];ankles=[]
        for rotation,dz,sole in [first,second]:
            ankles.append([0,-sole,dz])
            toe.append([sum(rotation[i][j]*v[0][j] for j in range(3))+[0,-sole,dz][i] for i in range(3)])
        self.assertGreater(math.dist(*ankles),1)
        self.assertLess(math.dist(*toe),1e-9)

class DigitigradeReach(unittest.TestCase):
    def test_third_segment_reaches_support_without_stretching_any_link(self):
        hip=[0,-100,0];paw=[0,0,0]
        knee,hock,actual=S.solve_three_segment(hip,paw,[45,45,40],[0,1,0],[0,0,-1])
        self.assertAlmostEqual(math.dist(hip,knee),45)
        self.assertAlmostEqual(math.dist(knee,hock),45)
        self.assertAlmostEqual(math.dist(hock,actual),40)
        self.assertLess(math.dist(actual,paw),1e-7)
        self.assertLess(knee[2],0)

    def test_lifted_hock_can_fold_above_hip_while_stance_paw_stays_below(self):
        hips=[[0,-50,0],[0,-50,0]];ends=[[0,0,0],[0,-75,0]];lengths=[[30,30],[30,30]]
        with self.assertRaises(ValueError):S.fit_pelvis(hips,ends,lengths,max_y=0,max_z=0)
        self.assertEqual(S.fit_pelvis(hips,ends,lengths,max_y=0,max_z=0,allow_end_above=[False,True]),(0,0))
        for hip,end,(a,b) in zip(hips,ends,lengths):self.assertLess(math.dist(hip,end),a+b)

    def test_native_bend_transport_crosses_hip_height_without_knee_flip(self):
        root=[0,0,0];rest_mid=[0,30,-10];rest_end=[0,40,40];knees=[]
        for y in range(-10,11):
            end=[0,y,50]
            pole=S.transported_native_pole(root,rest_mid,rest_end,root,end)
            knee,_=M.legik.solve(root,end,40,40,pole);knees.append(knee)
        self.assertLess(max(math.dist(a,b) for a,b in zip(knees,knees[1:])),2)
        with self.assertRaisesRegex(ValueError,'straight'):
            S.transported_native_pole(root,[0,20,20],rest_end,root,[0,0,50])

    def test_unreachable_distal_orientation_is_rejected(self):
        with self.assertRaisesRegex(ValueError,'unreachable'):
            S.solve_three_segment([0,-200,0],[0,0,0],[45,45,40],[0,1,0],[0,0,-1])

class SecondaryResponse(unittest.TestCase):
    def test_rest_has_no_invented_tail_oscillation(self):
        sk=[(-1,-1),(-1,0),(-1,1),(-1,2)]
        rest=[[4096,4096,4096,0,0,0,0,0,0] for _ in sk]
        samples=[copy.deepcopy(rest) for _ in range(25)]
        S.tail_response(samples,sk,rest,dict(body=1,bones=[2,3]))
        self.assertTrue(all(p==rest for p in samples))

    def test_tail_follows_body_input_and_repeats_without_reset(self):
        sk=[(-1,-1),(-1,0),(-1,1),(-1,2)]
        rest=[[4096,4096,4096,0,0,0,0,0,0] for _ in sk]
        samples=[copy.deepcopy(rest) for _ in range(25)]
        for t,p in enumerate(samples):p[1][4]=round(70*math.sin(t*2*math.pi/24))
        a=copy.deepcopy(samples);b=copy.deepcopy(samples)
        cfg=dict(body=1,bones=[2,3],frequency=3,damping=.9,lag_ticks=1)
        S.tail_response(a,sk,rest,cfg);S.tail_response(b,sk,rest,cfg)
        self.assertEqual(a,b)
        self.assertEqual(a[0][1:],a[-1][1:])
        self.assertGreater(max(abs(p[2][4]) for p in a),5)
        self.assertNotEqual([p[2][4] for p in a],[p[3][4] for p in a])

class PelvisConstraints(unittest.TestCase):
    def test_body_clearance_can_require_raising_an_otherwise_reachable_pelvis(self):
        dy,dz=S.fit_pelvis([[0,-60,0]],[[0,-10,0]],[[40,30]],max_down=-8.2)
        self.assertLessEqual(dy,-8.2)
        self.assertLessEqual(math.dist([0,-60+dy,dz],[0,-10,0]),70)

    def test_body_clearance_does_not_sacrifice_leg_reach(self):
        with self.assertRaises(ValueError):
            S.fit_pelvis([[0,-75,0]],[[0,-10,0]],[[40,30]],max_down=-10)

    def test_temporal_fit_anticipates_clearance_without_breaking_reach(self):
        parameters=[dict(hips=[[0,-50,0]],targets=[[0,0,0]],lengths=[[40,40]],max_y=25,max_z=0,max_down=(-15 if t==2 else 25)) for t in range(8)]
        seed=[S.fit_pelvis(**p) for p in parameters]
        fitted=S.smooth_pelvis_cycle(parameters,dict(iterations=80))
        jerk=lambda path:max(abs(path[(t+1)%8][0]-2*path[t][0]+path[(t-1)%8][0]) for t in range(8))
        self.assertLess(jerk(fitted),jerk(seed))
        self.assertLessEqual(fitted[2][0],-15)
        for p,(dy,dz) in zip(parameters,fitted):
            self.assertLess(math.dist([0,-50+dy,dz],[0,0,0]),80)
            self.assertLessEqual(dy,p['max_down'])

    def test_rest_is_unchanged_when_both_legs_reach(self):
        self.assertEqual(S.fit_pelvis([[20,-70,0],[-20,-70,0]],[[20,-20,0],[-20,-20,0]],[[40,30],[40,30]]),(0,0))

    def test_pelvis_moves_without_changing_segment_lengths(self):
        hips=[[20,-95,0],[-20,-95,0]];targets=[[20,-10,0],[-20,-10,0]]
        dy,dz=S.fit_pelvis(hips,targets,[[40,30],[40,30]])
        self.assertGreater(dy,0)
        for hip,target in zip(hips,targets):
            distance=math.dist([hip[0],hip[1]+dy,hip[2]+dz],target)
            self.assertLessEqual(distance,70)
            self.assertGreaterEqual(distance,10)

    def test_impossible_lateral_targets_are_rejected(self):
        with self.assertRaises(ValueError):S.fit_pelvis([[0,-70,0]],[[100,-20,0]],[[40,30]])

if __name__=='__main__':unittest.main()
