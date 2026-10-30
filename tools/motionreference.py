#!/usr/bin/env python3
"""Explicit native-rig reference-motion study; source tracks read locally at build time."""
import copy
import math
import motionlab as M
R=M.R

def swing_world_offset(phase,begin,end,period,travel):
    """Minimum-jerk placement between two world-space stance anchors.

    Phase wraps at the loop endpoint; forward root travel remains cumulative.
    The support window is inclusive and offsets are zero inside it.
    """
    phase%=period
    if begin<=phase<=end:return 0
    wrapped=phase<begin
    u=(phase+(period if wrapped else 0)-end)/(period+begin-end)
    return travel*(10*u**3-15*u**4+6*u**5-(1 if wrapped else 0))

def resample(frames, phase):
    x=phase*(len(frames)-1)
    i=min(int(x),len(frames)-2);w=x-i
    p=copy.deepcopy(frames[i])
    for b in range(len(p)):
        p[b][:3]=[round((1-w)*frames[i][b][j]+w*frames[i+1][b][j]) for j in range(3)]
        a,z=R.rot_of(frames[i][b]),R.rot_of(frames[i+1][b])
        rot=R.m3mul(R.scale_rot(R.m3mul(z,R.m3t(a)),w),a)
        p[b][3:6]=[round(v) for v in M.mmd.matrix_euler(rot,p[b][3:6])]
        p[b][6:9]=[(1-w)*frames[i][b][j]+w*frames[i+1][b][j] for j in range(6,9)]
    return p

def generate(mod,skel,rest,recipe,spec):
    import species
    cfg=spec['reference_motion'];sid=cfg['species']
    if cfg.get('swing_path') not in (None,'minimum_jerk'):raise ValueError('unknown swing trajectory')
    if not math.isfinite(cfg.get('swing_height',18)) or cfg.get('swing_height',18)<0:
        raise ValueError('swing height must be finite and nonnegative')
    source=M.Path(species.originals().model_path(sid))
    if M.digest(source.read_bytes())!=cfg['input_sha256']:
        raise ValueError('reference source hash mismatch')
    donor=M.mmd.MMD.load(str(source),sid);ds=M.mmd.exe().skeleton[sid]
    if M.skeleton_digest(ds)!=cfg['skeleton_sha256']:
        raise ValueError('reference skeleton mismatch')
    frames,loop,_=M.animsheet.slot_frames(donor,len(ds),int(cfg['slot'],0))
    if loop!=0:raise ValueError('reference must loop from its first frame')
    n=spec['ticks'];k=cfg['scale'];body=recipe['body'];dh=cfg['pelvis']
    if len(cfg['legs']) != len(recipe['legs']):raise ValueError('reference leg count mismatch')
    if any(not math.isfinite(cfg[key]) or cfg[key]<=0 for key in ('scale','body_scale','lift_scale')):
        raise ValueError('reference scales must be finite and positive')
    for arm in cfg['arms']:
        for tb,sb,se,te in arm['segments']:
            if skel[te][1]!=tb or ds[se][1]!=sb:
                raise ValueError('reference arm segment must join adjacent native bones')
            if any(tb in leg['chain'] for leg in recipe['legs']):
                raise ValueError('reference arm overlaps target leg')
    src=[resample(frames,t/n) for t in range(n+1)]
    positions=[R.world_pos(ds,p) for p in src]
    rotations=[R.world_rots(ds,p) for p in src]
    dr=R.rest_pose(donor,len(ds),0);drw=R.world_rots(ds,dr);drp=R.world_pos(ds,dr)
    # Native rest has no authored comic guard or added idle gestures.
    tp=R.world_pos(skel,rest);tw=R.world_rots(skel,rest)
    W=M.mmd.bone_matrices(mod,rest)
    floor=max(sum(W[leg['chain'][-1]][1][j]*v[j] for j in range(3))+W[leg['chain'][-1]][1][3]
              for leg in recipe['legs'] for v in mod.tmd.obj_verts(skel[leg['chain'][-1]][0]))
    source_period=len(frames)-1
    hips_mean=[sum(P[dh][j]-p[0][6+j] for P,p in zip(positions[:-1],src[:-1]))/n for j in range(3)]
    legs=[]
    for leg,ref in zip(recipe['legs'],cfg['legs']):
        chain=leg['chain'];h,knee,a=chain[0],chain[1],chain[-1];hock=chain[2] if len(chain)==4 else None
        da=ref['ankle']
        if ref.get('chain') and (len(ref['chain'])!=len(chain) or ref['chain'][-1]!=da or
            any(type(b) is not int or not 0<b<len(ds) for b in ref['chain']) or
            any(ds[c][1]!=p for p,c in zip(ref['chain'],ref['chain'][1:]))):
            raise ValueError('explicit reference chain must match the native chain arity and hierarchy')
        begin,end=ref['support']
        if not 0 <= begin < end < source_period:
            raise ValueError('support interval outside reference cycle')
        begin/=source_period;end/=source_period
        # Corrections are authored from explicit source support intervals, never guessed roles.
        support=[t for t in range(n) if begin<=t/n<=end]
        if len(support)<3:raise ValueError('support interval requires at least three resampled ticks')
        anchor=sum(positions[t][da][2]*k for t in support)/len(support)
        foot_ref=rotations[(support[0]+support[-1])//2][da]
        source_vertices=donor.tmd.obj_verts(ds[da][0])
        def forward_span(vertices,rotation):
            values=[sum(rotation[2][j]*v[j] for j in range(3)) for v in vertices]
            return max(values)-min(values)
        if cfg.get('center_support'):
            mean_local=sum(positions[i][da][2]-src[i][0][8] for i in range(n))/n
            anchor=k*(sum(src[i][0][8] for i in support)/len(support)+mean_local)
        pitch_ratio=cfg.get('foot_roll',{}).get('geometry_scale',cfg['scale'])*forward_span(source_vertices,foot_ref)/max(1,forward_span(mod.tmd.obj_verts(skel[a][0]),tw[a]))
        legs.append(dict(h=h,k=knee,a=a,da=da,begin=begin,end=end,support=support,
            anchor=anchor,correction={t:anchor-positions[t][da][2]*k for t in support},
            lengths=[math.dist(tp[h],tp[knee]),math.dist(tp[knee],tp[hock if hock is not None else a])],
            hock=hock,pole_mode=leg.get('pole_mode','world'),native_leg_plane=leg.get('native_leg_plane',False),native_last=M.legik.sub(tp[a],tp[hock]) if hock is not None else None,
            reference_last=M.legik.sub(drp[da],drp[ds[da][1]]) if hock is not None else None,
            centre_z=sum(positions[t][da][2]-src[t][0][8] for t in range(n))/n,
            base_x=ref.get('target_ankle_x',leg.get('ankle_x',tp[a][0]*cfg.get('stance_width_scale',1))),
            base_z=ref.get('target_ankle_z',leg.get('ankle_z',tp[a][2])),sole=floor-tp[a][1],pole=leg.get('knee_pole',leg.get('pole',[0,0,-1])),
            vertices=mod.tmd.obj_verts(skel[a][0]),foot_reference=foot_ref,pitch_ratio=pitch_ratio))
        if leg.get('heel_on_shin'):
            legs[-1]['heel_vertices']=mod.tmd.obj_verts(skel[knee][0])
    arm_fit=cfg.get('arm_fit')
    native_pose=None
    if cfg.get('native_pose'):
        native=cfg['native_pose']
        native_frames,_,_=M.animsheet.slot_frames(mod,len(skel),int(native['slot'],0))
        native_pose=native_frames[native.get('tick',0)]
        if any(type(b) is not int or not 0<b<len(skel) or
               any(b in leg['chain'] for leg in recipe['legs']) for b in native['bones']):
            raise ValueError('native upper-body reference overlaps a leg or invalid bone')
    if arm_fit:
        wrist_means={arm['segments'][-1][2]:[sum(P[arm['segments'][-1][2]][j]-P[dh][j] for P in positions[:-1])/n for j in range(3)] for arm in cfg['arms']}
    output=[];contacts=[];clamps=[];previous={};history=[]
    if cfg.get('temporal_pelvis') and (not cfg.get('pelvis_fit') or arm_fit):
        raise ValueError('temporal pelvis requires leg-only fitting')
    for t in range(n+1):
        p=copy.deepcopy(rest);P=positions[t];sw=rotations[t]
        p[0][8]=round((src[t][0][8]-src[0][0][8])*k)
        # Pelvis and chest retain the reference's coordination, with model-space deltas.
        for mapping in cfg['body_map']:
            tb,sb=mapping[:2];weight=mapping[2] if len(mapping)>2 else 1
            if not math.isfinite(weight) or not 0<=weight<=1:raise ValueError('body reference weight outside 0..1')
            desired=R.m3mul(R.scale_rot(R.m3mul(sw[sb],R.m3t(drw[sb])),weight),tw[tb])
            M.rotate_local(p,skel,tb,desired,previous)
        for j in range(3):
            delta=P[dh][j]-src[t][0][6+j]-hips_mean[j]
            p[body][6+j]+=round(delta*cfg['body_scale'])
        # Source sideways entity sway becomes pelvis sway, not sideways world travel.
        p[body][6]+=round(src[t][0][6]*cfg['body_scale'])
        bias=cfg.get('body_height_bias',0)
        if not math.isfinite(bias) or abs(bias)>100:raise ValueError('body height bias outside reviewed model-space bounds')
        p[body][7]+=spec['crouch']+bias
        # Preserve reference segment DIRECTIONS, not donor local Euler angles.
        for arm in cfg['arms']:
            for tb,sb,se,te in arm['segments']:
                desired=R.m3mul(R.swing(M.legik.sub(tp[te],tp[tb]),M.legik.sub(P[se],P[sb])),tw[tb])
                M.rotate_local(p,skel,tb,desired,previous)
        if native_pose is not None:
            for bone in cfg['native_pose']['bones']:
                p[bone]=copy.deepcopy(native_pose[bone])
        row=[];goals=[]
        for lg in legs:
            h,kn,a,da=lg['h'],lg['k'],lg['a'],lg['da']
            phase=t%n;support=lg['support'];b,e=support[0],support[-1]
            contact=b<=phase<=e
            if contact:correction=lg['correction'][phase]
            else:
                # Bridge the support correction through swing and across the clip seam.
                x=phase if phase>e else phase+n
                span=n+b-e;u=(x-e)/span
                c0=lg['correction'][e];c1=lg['correction'][b]
                v0=c0-lg['correction'][e-1];v1=lg['correction'][b+1]-c1
                correction=(2*u**3-3*u*u+1)*c0+(-2*u**3+3*u*u)*c1
                correction+=(u**3-2*u*u+u)*span*v0+(u**3-u*u)*span*v1
            # Source ankle height drives swing clearance; planted feet remain level.
            source_ground=max(positions[i][da][1] for i in support)
            lift=max(0,(source_ground-P[da][1])*cfg['lift_scale'])
            smooth_swing=cfg.get('swing_path')=='minimum_jerk'
            if smooth_swing and not contact:
                lift=cfg.get('swing_height',18)*64*u**3*(1-u)**3
            if contact:lift=0
            elif cfg.get('foot_roll') and not smooth_swing:
                distance=min((phase-e)%n,(b-phase)%n)
                blend=min(1,distance/3);lift*=blend*blend*(3-2*blend)
            foot_rotation=tw[a];roll_z=0;sole=lg['sole']
            if cfg.get('foot_roll'):
                import motionsecondary
                delta=R.m3mul(sw[da],R.m3t(lg['foot_reference']))
                forward=[-delta[i][2] for i in range(3)]
                pitch=math.degrees(math.atan2(forward[1],-forward[2]))
                if cfg['foot_roll'].get('geometry_transfer'):
                    pitch=math.degrees(math.asin(max(-.95,min(.95,math.sin(math.radians(pitch))*lg['pitch_ratio']))))
                distance=0 if contact else min((phase-e)%n,(b-phase)%n)
                blend=min(1,distance/3);blend=blend*blend*(3-2*blend)
                low=cfg['foot_roll'].get('support_limit',14)
                high=cfg['foot_roll'].get('swing_down_limit',cfg['foot_roll'].get('swing_limit',32)) if pitch>0 else cfg['foot_roll'].get('swing_limit',32)
                limit=low+(high-low)*blend
                pitch=limit*math.tanh(pitch*cfg['foot_roll'].get('weight',.5)/limit)
                foot_rotation,roll_z,sole=motionsecondary.rolling_foot(lg['vertices'],tw[a],pitch)
                lg['pitch']=pitch
            target=[lg['base_x'],floor-sole-lift,
                (P[da][2]-src[t][0][8]-lg['centre_z'])*k+lg['base_z']+correction+roll_z]
            if smooth_swing and not contact:
                travel=(src[-1][0][8]-src[0][0][8])*k
                target[2]=lg['base_z']+lg['anchor']-lg['centre_z']*k-src[phase][0][8]*k
                target[2]+=swing_world_offset(phase,b,e,n,travel)+roll_z
            # Compensate integer root rounding just as in the procedural solver.
            target[2]+=(src[t][0][8]-src[0][0][8])*k-p[0][8]
            if lg['hock'] is not None:
                weight=cfg.get('hock_reference_weight',1)
                if not math.isfinite(weight) or not 0<=weight<=1:raise ValueError('hock reference weight outside0..1')
                delta=R.scale_rot(R.swing(lg['reference_last'],M.legik.sub(P[da],P[ds[da][1]])),weight)
                lg['end_offset']=[sum(delta[i][j]*lg['native_last'][j] for j in range(3)) for i in range(3)]
            else:lg['end_offset']=[0,0,0]
            goals.append((lg,target,foot_rotation,contact))
        if cfg.get('temporal_pelvis'):history.append((copy.deepcopy(p),copy.deepcopy(goals)))
        if cfg.get('pelvis_fit'):
            import motionsecondary
            params=pelvis_parameters(p,goals,mod,skel,body,cfg,floor,recipe['legs'])
            dy,dz=motionsecondary.fit_pelvis(**params)
            p[body][7]+=dy;p[body][8]+=dz
        row=apply_leg_goals(p,goals,skel,tp,tw,previous,floor,clamps)
        if arm_fit:
            current_pos=R.world_pos(skel,p);current_rot=R.world_rots(skel,p)
            body_delta=R.m3mul(current_rot[body],R.m3t(tw[body]))
            for arm in cfg['arms']:
                h,kn=arm['segments'][0][0],arm['segments'][1][0]
                a=arm['segments'][1][3];da=arm['segments'][1][2]
                side=1 if tp[h][0]>0 else -1
                anchor=[side*arm_fit['width'],arm_fit['height'],arm_fit['forward']]
                relative=M.legik.sub(anchor,tp[body])
                target=[current_pos[body][i]+sum(body_delta[i][j]*relative[j] for j in range(3)) for i in range(3)]
                for i in range(3):target[i]+=(P[da][i]-P[dh][i]-wrist_means[da][i])*arm_fit['motion_scale'][i]
                L1,L2=math.dist(tp[h],tp[kn]),math.dist(tp[kn],tp[a])
                hip=current_pos[h]
                elbow,wrist=M.legik.solve(hip,target,L1,L2,[side,arm_fit.get('elbow_down',.3),arm_fit.get('elbow_back',.3)])
                clamps.append(max(0,math.dist(hip,target)-L1-L2+.001,abs(L1-L2)+.001-math.dist(hip,target)))
                M.rotate_local(p,skel,h,R.m3mul(R.swing(M.legik.sub(tp[kn],tp[h]),M.legik.sub(elbow,hip)),tw[h]),previous)
                forearm_delta=R.swing(M.legik.sub(tp[a],tp[kn]),M.legik.sub(wrist,elbow))
                M.rotate_local(p,skel,kn,R.m3mul(forearm_delta,tw[kn]),previous)
                M.rotate_local(p,skel,a,R.m3mul(forearm_delta,tw[a]),previous)
        apply_clearances(p,mod,skel,cfg,floor,previous)
        output.append(p);contacts.append(row)
    if cfg.get('temporal_pelvis'):
        import motionsecondary
        params=[pelvis_parameters(p,g,mod,skel,body,cfg,floor,recipe['legs']) for p,g in history[:-1]]
        shifts=motionsecondary.smooth_pelvis_cycle(params,cfg['temporal_pelvis']);output=[];contacts=[];previous={}
        for t,(p,goals) in enumerate(history):
            dy,dz=shifts[t%len(shifts)];p[body][7]+=dy;p[body][8]+=dz
            row=apply_leg_goals(p,goals,skel,tp,tw,previous,floor,clamps)
            apply_clearances(p,mod,skel,cfg,floor,previous);output.append(p);contacts.append(row)
    if cfg.get('tail'):
        import motionsecondary
        motionsecondary.tail_response(output,skel,rest,cfg['tail'])
    output[-1][1:]=copy.deepcopy(output[0][1:])
    return output,contacts,max(clamps),floor


def sound_events(spec,length):
    """Extract only explicitly selected generic sound banks from the local reference."""
    import species
    cfg=spec['reference_motion'];banks=cfg.get('sound_banks',[])
    if not banks:return []
    mod=M.mmd.MMD.load(species.originals().model_path(cfg['species']),cfg['species'])
    frames,_,events=M.animsheet.slot_frames(mod,M.mmd.exe().bone_count[cfg['species']],int(cfg['slot'],0))
    period=len(frames)-1
    return [(round(t*(length-1)/period),kind,dict(event)) for t,kind,event in events
            if kind=='sound' and event['bank'] in banks]


def angular_envelope(skel,frames,bones):
    """Physical angular speed and velocity change across a closed gait cycle."""
    maximum=acceleration=0.
    for bone in bones:
        rotations=[R.world_rots(skel,p)[bone] for p in frames];velocities=[]
        for a,z in zip(rotations,rotations[1:]):
            axis,angle=R.axis_angle(R.m3mul(z,R.m3t(a)));velocities.append([math.degrees(angle)*v for v in axis])
        maximum=max(maximum,max((math.sqrt(sum(v*v for v in value)) for value in velocities),default=0))
        if velocities:
            acceleration=max(acceleration,max(math.dist(a,z) for a,z in zip(velocities,velocities[1:]+velocities[:1])))
    return dict(max_step_degrees=maximum,max_velocity_change_degrees=acceleration)


def apply_leg_goals(p,goals,skel,tp,tw,previous,floor,clamps,full_fk_model=None):
    row=[]
    for lg,target,foot_rotation,contact in goals:
        h,kn,a=lg['h'],lg['k'],lg['a']
        local=copy.deepcopy(p);local[0][6:9]=[0,0,0]
        if full_fk_model is None:hip=R.world_pos(skel,local)[h]
        else:
            world=M.mmd.bone_matrices(full_fk_model,local)
            hip=[world[h][i][3] for i in range(3)]
        L1,L2=lg['lengths']
        end=[target[i]-lg['end_offset'][i] for i in range(3)];d=math.dist(hip,end)
        if 'heel_vertices' in lg:
            import motionsecondary
            target,foot_rotation,_=motionsecondary.compound_foot(lg['vertices'],tw[a],lg['pitch'],target,
                hip,[L1,L2],lg['pole'],lg['heel_vertices'],M.legik.sub(tp[a],tp[kn]),tw[kn],floor)
            d=math.dist(hip,target)
        clamps.append(max(0,d-(L1+L2-.001),abs(L1-L2)+.001-d))
        if lg['hock'] is None:end=target
        pole=lg['pole']
        if lg['pole_mode']=='native_transport':
            import motionsecondary
            pole=motionsecondary.transported_native_pole(tp[h],tp[kn],tp[lg['hock'] if lg['hock'] is not None else a],hip,end)
            if lg.get('native_swivel_degrees',0):
                pole=motionsecondary.swivel_native_pole(pole,hip,end,lg['native_swivel_degrees'])
        elif lg['pole_mode']!='world':raise ValueError('unknown knee pole mode')
        if lg['hock'] is not None:
            import motionsecondary
            knee,ankle,_=motionsecondary.solve_three_segment(hip,target,[L1,L2,math.dist(tp[a],tp[lg['hock']])],lg['end_offset'],pole)
        else:knee,ankle=M.legik.solve(hip,target,L1,L2,pole)
        inner=lg['hock'] if lg['hock'] is not None else a
        if lg.get('native_leg_plane',False):
            import motionsecondary
            desired=motionsecondary.native_plane_rotations(
                [tp[h],tp[kn],tp[inner]],[hip,knee,ankle],[tw[h],tw[kn]])
        else:
            desired=[R.m3mul(R.swing(M.legik.sub(tp[kn],tp[h]),M.legik.sub(knee,hip)),tw[h]),
                     R.m3mul(R.swing(M.legik.sub(tp[inner],tp[kn]),M.legik.sub(ankle,knee)),tw[kn])]
        M.rotate_local(p,skel,h,desired[0],previous)
        M.rotate_local(p,skel,kn,desired[1],previous)
        if lg['hock'] is not None:
            M.rotate_local(p,skel,inner,R.m3mul(R.swing(lg['native_last'],M.legik.sub(target,ankle)),tw[inner]),previous)
        M.rotate_local(p,skel,a,foot_rotation,previous)
        row.append(contact)
    return row


def apply_clearances(p,mod,skel,cfg,floor,previous):
    for clearance in cfg.get('ground_clearance',[]):
        import motionsecondary
        root=clearance['root'];W=M.mmd.bone_matrices(mod,p)
        if any(root!=b and root not in M.ancestors(skel,b) for b in clearance['bones']):
            raise ValueError('clearance bones must belong to the selected appendage')
        points=[[sum(W[b][i][j]*v[j] for j in range(3))+W[b][i][3] for i in range(3)]
                for b in clearance['bones'] for v in mod.tmd.obj_verts(skel[b][0])]
        correction=motionsecondary.clearance_rotation(points,[W[root][i][3] for i in range(3)],
            clearance['axis'],clearance['limits'],floor-clearance.get('margin',1))
        M.rotate_local(p,skel,root,R.m3mul(correction,R.world_rots(skel,p)[root]),previous)


def pelvis_parameters(p,goals,mod,skel,body,cfg,floor,legs):
    if skel[body][1]!=0:raise ValueError('pelvis fit currently requires a root-child pelvis')
    local=copy.deepcopy(p);local[0][6:9]=[0,0,0];hips=R.world_pos(skel,local);fit=dict(cfg['pelvis_fit'])
    if any(lg['hock'] is not None for lg,_,_,_ in goals):fit['allow_end_above']=[lg['hock'] is not None and not contact for lg,_,_,contact in goals]
    if cfg.get('body_clearance'):
        clearance=cfg['body_clearance'];bones=clearance['bones']
        if not bones or any(b in leg['chain'] for b in bones for leg in legs):raise ValueError('body clearance must exclude support limbs')
        if any(b!=body and body not in M.ancestors(skel,b) for b in bones):raise ValueError('body clearance parts must descend from the pelvis')
        matrices=M.mmd.bone_matrices(mod,local)
        low=max(sum(matrices[b][1][j]*v[j] for j in range(3))+matrices[b][1][3] for b in bones for v in mod.tmd.obj_verts(skel[b][0]))
        fit['max_down']=min(fit.get('max_down',float('inf')),floor-clearance.get('margin',1)-low)
    return dict(hips=[hips[lg['h']] for lg,_,_,_ in goals],targets=[[target[i]-lg['end_offset'][i] for i in range(3)] for lg,target,_,_ in goals],lengths=[lg['lengths'] for lg,_,_,_ in goals],**fit)
