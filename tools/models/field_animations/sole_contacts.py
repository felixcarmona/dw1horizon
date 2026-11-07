"""Bake mesh-calibrated heel, sole and toe contacts into native gait transfers.

Ground contacts live in world space. Two-bone IK follows those contacts using
scaled segment lengths; foot orientation uses the mesh's own sole coordinates.
Only the named legs and the carrier's vertical translation are adjusted.
"""
import copy
import math

import animsheet
import legik
import mmd
import motionsecondary
import retarget as rt


def smooth(t):
    return t*t*(3-2*t)


def bake(model, frames, skeleton, cfg, slot):
    plan = cfg['sole_contacts']
    period = len(frames)-1
    profile = plan['profiles'].get(str(slot))
    carrier = cfg['carrier']
    feet = cfg['feet']
    poses = copy.deepcopy(frames)
    # The imported rig has uniform carrier scale. Include it in IK lengths and
    # the mesh's heel/toe pivots, rather than treating scaled bones as unit size.
    scale = frames[0][carrier][0]/4096
    if max(abs(frames[0][carrier][i]/4096-scale) for i in range(3)) > .001:
        raise ValueError('Sole contacts require a uniformly scaled carrier')
    matrices = [mmd.bone_matrices(model, p) for p in frames]
    positions = [[[a[i][3] for i in range(3)] for a in mats] for mats in matrices]
    travel = [frames[-1][0][6+i]-frames[0][0][6+i] for i in range(3)]
    lanes = {b: sum(p[b][0]-f[0][6] for p,f in zip(positions[:-1], frames[:-1]))/period for b in feet}
    center = sum(p[h][2]-f[0][8] for p,f in zip(positions[:-1], frames[:-1]) for h,_,_,_,_,_ in cfg['legs'])/(period*len(feet))
    targets = []
    rotations = []
    for tick in range(period+1):
        goals, rots = {}, {}
        for index, foot in enumerate(feet):
            heel, toe, sole = plan['heel'], plan['toe'], plan['sole']
            def root(t, axis):
                return frames[0][0][6+axis]+travel[axis]*t/period
            if profile is None:
                goals[foot] = [lanes[foot]+frames[0][0][6], -sole*scale, center+frames[0][0][8]]
                rots[foot] = mmd.rot_matrix(0,0,0)
                continue
            start = period/2 if index == 0 else 0
            phase = (tick-start)%period
            cycle_start = tick-phase
            flat_start, flat_end, end = profile['flat_start'], profile['flat_end'], profile['end']
            mid = (flat_start+flat_end)/2
            anchor = [lanes[foot]+root(cycle_start+mid, 0), -sole*scale, center+root(cycle_start+mid, 2)]
            def contact(q, a):
                if q < flat_start:
                    pitch = profile['heel_pitch']*(1-smooth(q/flat_start))
                    pivot = heel
                elif q <= flat_end:
                    pitch, pivot = 0., 0.
                else:
                    pitch = profile['toe_pitch']*smooth((q-flat_end)/(end-flat_end))
                    pivot = toe
                R = mmd.rot_matrix(pitch*4096/360,0,0)
                v = [0, sole*scale, pivot*scale]
                g = [a[i]+v[i]-sum(R[i][j]*v[j] for j in range(3)) for i in range(3)]
                return g, R, pitch
            if phase <= end:
                goal, rotation, _ = contact(phase, anchor)
            else:
                first, _, p0 = contact(end, anchor)
                nxt = [anchor[i]+travel[i] for i in range(3)]
                last, _, p1 = contact(0, nxt)
                u = (phase-end)/(period-end)
                weight = smooth(u)
                goal = [a+(b-a)*weight for a,b in zip(first,last)]
                # Follow the native's toe-off, folded swing and heel-first
                # landing, with zero angular velocity into the flat hold.
                pitch = p0+(p1-p0)*weight+profile['swing_pitch']*math.sin(math.pi*u)**2
                rotation = mmd.rot_matrix(pitch*4096/360,0,0)
                vertices = model.tmd.obj_verts(skeleton[foot][0])
                bottom = max(sum(rotation[1][j]*v[j]*scale for j in range(3)) for v in vertices)
                goal[1] = -bottom-profile['lift']*math.sin(math.pi*u)**2
            goals[foot], rots[foot] = goal, rotation
        targets.append(goals);rotations.append(rots)
    for hip, _, _, foot, _, _ in cfg['legs']:
        offsets = [targets[t][foot][2]-positions[t][hip][2] for t in range(period)]
        bias = (min(offsets)+max(offsets))/2
        for goals in targets:
            goals[foot][2] -= bias
    # Grounded feet constrain pelvis height. Airborne feet follow the native
    # swing within the shorter imported legs' reach; they must not push the
    # pelvis below the planted ankle.
    reference = animsheet.slot_frames(model, len(skeleton), cfg.get('rest_slot', 2))[0][0]
    reference_matrices = mmd.bone_matrices(model, reference)
    reference_positions = [[a[i][3] for i in range(3)] for a in reference_matrices]
    reference_rotations = rt.world_rots(skeleton, reference)
    lengths = {foot: (legik.norm(legik.sub(positions[0][k],positions[0][h])),
                      legik.norm(legik.sub(positions[0][a],positions[0][k])))
               for h,k,a,foot,_,_ in cfg['legs']}
    def planted(t, foot):
        if profile is None:
            return True
        start = period/2 if feet.index(foot) == 0 else 0
        return (t-start)%period <= profile['end']
    bounds = []
    for tick in range(period):
        lower = -1e6
        for h,k,a,foot,_,_ in cfg['legs']:
            if not planted(tick, foot):
                continue
            goal, origin = targets[tick][foot], positions[tick][h]
            reach = sum(lengths[foot])*.97
            horizontal = math.hypot(goal[0]-origin[0],goal[2]-origin[2])
            if horizontal >= reach:
                raise ValueError(f'Contact exceeds leg reach: slot {slot}, tick {tick}, foot {foot}: {horizontal:.1f}/{reach:.1f}')
            lower = max(lower, goal[1]-math.sqrt(reach*reach-horizontal*horizontal)
                        -(origin[1]-frames[tick][carrier][7]))
        bounds.append(lower)
    heights = [max(bounds[j]-.5*min((i-j)%period,(j-i)%period)**2 for j in range(period))
               for i in range(period)]
    heights.append(heights[0])
    previous = {}
    for tick,p in enumerate(poses):
        p[carrier][7] = round(heights[tick])
        def set_rotation(b, desired):
            parent = rt.world_rots(skeleton,p)[skeleton[b][1]]
            angles = mmd.matrix_euler(rt.m3mul(rt.m3t(parent),desired), previous.get(b))
            p[b][3:6] = previous[b] = [round(v) for v in angles]
        for h,k,a,foot,_,_ in cfg['legs']:
            mats = mmd.bone_matrices(model,p)
            # Place each hip over its foot lane. A lateral reach would rotate
            # the knee plane and twist the sole between Euler keys.
            parent = mats[skeleton[h][1]]
            inv = inverse3([row[:3] for row in parent[:3]])
            lateral = targets[tick][foot][0]-mats[h][0][3]
            p[h][6:9] = [round(p[h][6+i]+inv[i][0]*lateral) for i in range(3)]
            mats = mmd.bone_matrices(model,p)
            origin = [mats[h][i][3] for i in range(3)]
            goal = targets[tick][foot][:]
            if not planted(tick, foot):
                # Keep the authored swing inside the anatomical reach sphere.
                reach = sum(lengths[foot])*.95
                dx, dz = goal[0]-origin[0], goal[2]-origin[2]
                horizontal = math.hypot(dx,dz)
                if horizontal > reach*.9:
                    factor = reach*.9/horizontal
                    goal[0], goal[2] = origin[0]+dx*factor, origin[2]+dz*factor
                    horizontal *= factor
                vertical = math.sqrt(reach*reach-horizontal*horizontal)
                goal[1] = max(origin[1]-vertical, min(origin[1]+vertical,goal[1]))
            sagittal = [origin[0], goal[1], goal[2]]
            axis = legik.sub(sagittal, origin)
            knee, ankle = legik.solve(origin,sagittal,*lengths[foot],[0,axis[2],-axis[1]])
            solved = motionsecondary.native_plane_rotations([reference_positions[b] for b in (h,k,a)],[origin,knee,ankle],[reference_rotations[b] for b in (h,k)])
            set_rotation(h,solved[0]);set_rotation(k,solved[1]);set_rotation(foot,rotations[tick][foot])
            # Integer Euler conversion and the carrier's one-unit scale
            # asymmetry leave sub-unit residuals. Bake only that small residual
            # in the terminal joint's local translation.
            mats = mmd.bone_matrices(model,p);parent = mats[skeleton[foot][1]]
            inv = inverse3([row[:3] for row in parent[:3]])
            delta = [goal[i]-mats[foot][i][3] for i in range(3)]
            p[foot][6:9] = [round(p[foot][6+i]+sum(inv[i][j]*delta[j] for j in range(3))) for i in range(3)]
    poses[-1][1:] = copy.deepcopy(poses[0][1:])
    return refine(model, poses, skeleton, cfg, slot)


def inverse3(a):
    x,y,z = a
    rows = [[y[1]*z[2]-y[2]*z[1],x[2]*z[1]-x[1]*z[2],x[1]*y[2]-x[2]*y[1]],
            [y[2]*z[0]-y[0]*z[2],x[0]*z[2]-x[2]*z[0],x[2]*y[0]-x[0]*y[2]],
            [y[0]*z[1]-y[1]*z[0],x[1]*z[0]-x[0]*z[1],x[0]*y[1]-x[1]*y[0]]]
    det = sum(a[0][i]*rows[i][0] for i in range(3))
    return [[v/det for v in row] for row in rows]


def refine(model, poses, skeleton, cfg, slot):
    """Fit contacts through rendered subframes while keeping keyed feet fixed.

    Local Euler interpolation of a bent knee follows an arc. Small, bounded
    changes of the knee plane and terminal attachment cancel that arc instead
    of lifting the whole character away from the ground.
    """
    def matrix(p, bone):
        chain=[]
        while bone >= 0:
            chain.append(bone);bone=skeleton[bone][1]
        result=[[1,0,0,0],[0,1,0,0],[0,0,1,0],[0,0,0,1]]
        for b in reversed(chain):
            v=p[b];R=mmd.rot_matrix(*v[3:6])
            local=[[R[i][j]*v[j]/4096 for j in range(3)]+[v[6+i]] for i in range(3)]+[[0,0,0,1]]
            result=mmd.mat_mul(result,local)
        return result
    def rotation(p, bone):
        if bone < 0:return [[1,0,0],[0,1,0],[0,0,1]]
        return rt.m3mul(rotation(p,skeleton[bone][1]),mmd.rot_matrix(*p[bone][3:6]))
    period = len(poses)-1
    for hip,knee,_,foot,_,_ in cfg['legs']:
        base = copy.deepcopy(poses[:-1])
        desired = []
        vertices = model.tmd.obj_verts(skeleton[foot][0])
        target_matrices = [matrix(p,foot) for p in base]
        target_rotations = [rotation(p,foot) for p in base]
        profile=cfg['sole_contacts']['profiles'].get(str(slot))
        start=period/2 if cfg['feet'].index(foot)==0 else 0
        for t,M in enumerate(target_matrices):
            if profile is None or (t-start)%period <= profile['end']:
                bottom=max(sum(M[1][j]*v[j] for j in range(3))+M[1][3] for v in vertices)
                M[1][3]-=bottom+.75+cfg['sole_contacts'].get('clearance',0)
        vertices = model.tmd.obj_verts(skeleton[foot][0])
        sole = [v for v in vertices if v[1] == cfg['sole_contacts']['sole']]
        # Corners spanning the sole constrain pitch, roll, height and slip.
        probes = [min(sole,key=lambda v:v[0]),max(sole,key=lambda v:v[0]),
                  min(sole,key=lambda v:v[2]),max(sole,key=lambda v:v[2])]
        for M in target_matrices:
            desired.append([[sum(M[i][j]*v[j] for j in range(3))+M[i][3] for i in range(3)] for v in probes])
        variables = [[0.]*6 for _ in base]
        working = copy.deepcopy(base)
        def fit(t, values):
            p = copy.deepcopy(base[t])
            for (b,j),v in zip([(hip,3),(hip,4),(hip,5),(knee,3),(knee,4),(knee,5)],values):
                p[b][j] += v
            before = target_matrices[t]
            rotations = target_rotations[t]
            parent = rotation(p,skeleton[foot][1])
            p[foot][3:6] = mmd.matrix_euler(rt.m3mul(rt.m3t(parent),rotations),base[t][foot][3:6])
            M=matrix(p,foot)
            inv=inverse3([row[:3] for row in matrix(p,skeleton[foot][1])[:3]])
            delta=[before[i][3]-M[i][3] for i in range(3)]
            p[foot][6:9]=[p[foot][6+i]+sum(inv[i][j]*delta[j] for j in range(3)) for i in range(3)]
            return p
        def segment(t):
            nxt=(t+1)%period
            a,b=working[t],copy.deepcopy(working[nxt])
            delta=[poses[-1][0][6+i]-poses[0][0][6+i] for i in range(3)] if nxt==0 else [0]*3
            for i in range(3):b[0][6+i]+=delta[i]
            residual=[]
            for u in (1/3, .5, 2/3):
                p=[]
                for x,y in zip(a,b):
                    p.append([v+(((w-v+2048)%4096-2048) if 3<=j<6 else w-v)*u for j,(v,w) in enumerate(zip(x,y))])
                M=matrix(p,foot)
                target=[[x+(y+delta[i]-x)*u for i,(x,y) in enumerate(zip(v,w))] for v,w in zip(desired[t],desired[nxt])]
                penetration=max(v[1] for v in target)
                if penetration>-.5:
                    for v in target:v[1]-=penetration+.5
                for v,goal in zip(probes,target):
                    actual=[sum(M[i][j]*v[j] for j in range(3))+M[i][3] for i in range(3)]
                    residual.extend((2 if i==1 else 1)*(actual[i]-goal[i])/2 for i in range(3))
                    residual.append(8*max(0,actual[1]-.25))
            return residual
        working=[fit(t,variables[t]) for t in range(period)]
        def residual(t):
            return (segment((t-1)%period)+segment(t)
                    +[math.sqrt(.1)*(working[t][foot][6+i]-base[t][foot][6+i]) for i in range(3)]
                    +[math.sqrt(.0005)*v for v in variables[t]])
        for sweep in range(8):
            improved=False
            order=range(period) if sweep%2==0 else reversed(range(period))
            for t in order:
                old=variables[t][:];saved=working[t];r0=residual(t)
                score=sum(v*v for v in r0);columns=[]
                for axis in range(6):
                    variables[t][axis]=old[axis]+2
                    working[t]=fit(t,variables[t]);rr=residual(t)
                    columns.append([(b-a)/2 for a,b in zip(r0,rr)])
                    variables[t][axis]=old[axis]
                working[t]=saved
                normal=[[sum(x*y for x,y in zip(a,b))+(.002 if i==j else 0)
                         for j,b in enumerate(columns)] for i,a in enumerate(columns)]
                rhs=[-sum(x*y for x,y in zip(column,r0)) for column in columns]
                delta=linear_solve(normal,rhs)
                maximum=max(abs(v) for v in delta)
                if maximum>64:delta=[v*64/maximum for v in delta]
                for factor in (1.,.5,.25):
                    candidate=[max(-256,min(256,v+factor*d)) for v,d in zip(old,delta)]
                    variables[t]=candidate;working[t]=fit(t,candidate)
                    cost=sum(v*v for v in residual(t))
                    if cost<score-.001:
                        improved=True;break
                else:
                    variables[t]=old;working[t]=saved
            if not improved:break
        for t in range(period):
            for bone in (hip,knee,foot):poses[t][bone]=[round(v) for v in working[t][bone]]
    poses[-1][1:]=copy.deepcopy(poses[0][1:])
    return poses


def linear_solve(matrix, rhs):
    """Solve the small damped contact-fit normal equations with pivoting."""
    rows=[list(a)+[b] for a,b in zip(matrix,rhs)]
    n=len(rows)
    for col in range(n):
        pivot=max(range(col,n),key=lambda i:abs(rows[i][col]))
        rows[col],rows[pivot]=rows[pivot],rows[col]
        divisor=rows[col][col]
        if abs(divisor)<1e-12:raise ValueError('singular contact fit')
        rows[col]=[v/divisor for v in rows[col]]
        for i in range(n):
            if i==col:continue
            factor=rows[i][col]
            rows[i]=[a-factor*b for a,b in zip(rows[i],rows[col])]
    return [row[-1] for row in rows]


def clear_appendages(data, sid, skeleton, cfg):
    """Keep long imported claws and tail tips clear after planting the feet."""
    import footfix
    import motioncyclelayer
    model=mmd.MMD.parse(data,len(skeleton));model.type=sid
    footfix.unshare(model,cfg['slots'])
    reports=[];seen=set()
    for slot in cfg['slots']:
        index=model.anims.table[slot]
        if index in seen:continue
        seen.add(index)
        for spec in cfg['appendage_clearance']:
            bone=spec['bone'];children=spec['children'];axis=spec['axis']
            frames=animsheet.slot_frames(model,len(skeleton),slot)[0][:-1]
            period=len(frames);points=[];origins=[]
            for pose in frames:
                mats=mmd.bone_matrices(model,pose)
                origins.append([mats[bone][i][3] for i in range(3)])
                points.append([[sum(mats[b][i][j]*v[j] for j in range(3))+mats[b][i][3] for i in range(3)]
                               for b in children for v in model.tmd.obj_verts(skeleton[b][0])])
            if max(v[1] for pp in points for v in pp)<=-spec['floor_margin']:
                continue
            choices=[]
            for sign in (-1,1):
                curve=[]
                try:
                    for pp,origin in zip(points,origins):
                        limits=[-spec['limit'],0] if sign<0 else [0,spec['limit']]
                        rotation=motionsecondary.clearance_rotation(pp,origin,axis,limits,-spec['floor_margin'])
                        cosine=max(-1,min(1,(sum(rotation[i][i] for i in range(3))-1)/2))
                        curve.append(math.degrees(math.acos(cosine)))
                except ValueError:
                    continue
                envelope=[max(0,max(curve[j]-spec['easing']*min((i-j)%period,(j-i)%period)**2 for j in range(period))) for i in range(period)]
                choices.append((sum(v*v for v in envelope),sign,envelope))
            if not choices:
                raise ValueError(f'Appendage cannot clear floor: slot {slot}, bone {bone}')
            _,sign,envelope=min(choices)
            def target(t, pose, rotations):
                correction=rt.from_axis_angle(axis,math.radians(sign*envelope[t%period]))
                return rt.m3mul(correction,rotations[bone])
            footfix.rewrite_bone(model.anims.anims[index],len(skeleton),skeleton,slot,bone,target,step=spec['step'])
            reports.append(dict(slot=slot,bone=bone,maximum_degrees=max(envelope),direction=sign))
    model.anims.anims,model.anims.table=motioncyclelayer.share_identical_streams(model.anims.anims,model.anims.table)
    return model.build(),reports
