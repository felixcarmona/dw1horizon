"""Deterministic secondary response and mesh-derived rigid-foot support geometry."""
import copy,math
import motionlab as M
R=M.R

def foot_pair_clearance(vertices,rotations,origins,margin=1,axis=0):
    """Required gap along horizontal axis for a geometrically ordered foot pair.

    Conservative mesh bounds; vertically or longitudinally separated feet do
    not require a lateral correction. Callers can use a cycle-wide constant
    stance correction to preserve the donor trajectory's timing and shape.
    """
    if len(vertices)!=2 or len(rotations)!=2 or len(origins)!=2 or margin<0:
        raise ValueError('expected an ordered foot pair and nonnegative margin')
    if axis not in (0,2):raise ValueError('foot clearance axis must be horizontal')
    boxes=[]
    for vs,rotation,origin in zip(vertices,rotations,origins):
        points=[[sum(rotation[i][j]*v[j] for j in range(3))+origin[i] for i in range(3)] for v in vs]
        boxes.append([(min(v[i] for v in points),max(v[i] for v in points)) for i in range(3)])
    if any(min(boxes[0][i][1],boxes[1][i][1])<=max(boxes[0][i][0],boxes[1][i][0]) for i in range(3) if i!=axis):
        return 0.0
    return max(0.0,boxes[0][axis][1]+margin-boxes[1][axis][0])

def native_plane_rotations(reference, solved, rotations):
    """Carry each segment's native twist with the complete bent-limb plane."""
    def sub(a,b):return [x-y for x,y in zip(a,b)]
    def cross(a,b):return [a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0]]
    def unit(a):
        n=math.sqrt(sum(v*v for v in a))
        if n<1e-6:raise ValueError('native plane requires nondegenerate bent limbs')
        return [v/n for v in a]
    old=[sub(reference[i+1],reference[i]) for i in range(2)]
    new=[sub(solved[i+1],solved[i]) for i in range(2)]
    normals=[unit(cross(*old)),unit(cross(*new))]
    result=[]
    for i in range(2):
        bases=[]
        for axis,normal in [(unit(old[i]),normals[0]),(unit(new[i]),normals[1])]:
            columns=[axis,normal,cross(axis,normal)]
            bases.append([list(row) for row in zip(*columns)])
        result.append(R.m3mul(R.m3mul(bases[1],R.m3t(bases[0])),rotations[i]))
    return result

def rolling_foot(vertices,flat,angle):
    rotation=R.m3mul(R.from_axis_angle([1,0,0],math.radians(angle)),flat)
    def point(rot,v):return [sum(rot[i][j]*v[j] for j in range(3)) for i in range(3)]
    offsets=[point(rotation,v) for v in vertices]
    index=max(range(len(vertices)),key=lambda i:offsets[i][1])
    pivot=offsets[index];original=point(flat,vertices[index])
    # Rotating around the lowest support vertex keeps heel/toe in its flat footprint.
    return rotation,original[2]-pivot[2],pivot[1]

def clearance_rotation(points,origin,axis,limits,floor):
    """Smallest bounded hinge correction keeping an appendage above ground."""
    if (not points or len(axis)!=3 or len(limits)!=2 or
        not all(math.isfinite(v) for v in [*axis,*limits,floor]) or
        sum(v*v for v in axis)<1e-8 or not limits[0]<=0<=limits[1]):
        raise ValueError('invalid appendage clearance geometry or limits')
    norm=math.sqrt(sum(v*v for v in axis));axis=[v/norm for v in axis]
    relative=[M.legik.sub(p,origin) for p in points]
    def evaluate(angle):
        rotation=R.from_axis_angle(axis,math.radians(angle))
        return max(sum(rotation[1][j]*v[j] for j in range(3))+origin[1] for v in relative)-floor
    if evaluate(0)<=0:return R.from_axis_angle(axis,0)
    candidates=[]
    for direction,bound in [(-1,limits[0]),(1,limits[1])]:
        previous=0
        for step in range(1,math.ceil(abs(bound))+1):
            angle=direction*min(step,abs(bound))
            if evaluate(angle)<=0:
                bad,good=previous,angle
                for _ in range(16):
                    middle=(bad+good)/2
                    if evaluate(middle)<=0:good=middle
                    else:bad=middle
                candidates.append(good);break
            previous=angle
    if not candidates:raise ValueError('appendage cannot clear ground within reviewed angular limits')
    return R.from_axis_angle(axis,math.radians(min(candidates,key=abs)))

def bounded_support_lift(height_error, maximum, tolerance=.01):
    """Find a bounded upward ankle shift using actual support-surface geometry.

    Scan one-unit brackets, then bisect the first clear bracket. The evaluator
    must reject unreachable poses; this does not change any bone length.
    """
    if (isinstance(maximum,bool) or not math.isfinite(maximum) or maximum<=0
        or not math.isfinite(tolerance) or tolerance<0):
        raise ValueError('invalid compound support lift bound')
    initial=height_error(0)
    if not math.isfinite(initial):raise ValueError('nonfinite support residual')
    if initial<=tolerance:return 0.
    bad=0.
    for step in range(1,math.ceil(maximum)+1):
        good=min(step,maximum);residual=height_error(good)
        if not math.isfinite(residual):raise ValueError('nonfinite support residual')
        if residual<=tolerance:
            for _ in range(16):
                middle=(bad+good)/2;residual=height_error(middle)
                if not math.isfinite(residual):raise ValueError('nonfinite support residual')
                if residual<=tolerance:good=middle
                else:bad=middle
            if height_error(good)>tolerance:raise ValueError('compound support verification failed')
            return good
        bad=good
    raise ValueError('compound support cannot clear ground within reviewed ankle lift')


def compound_foot(vertices,flat,angle,target,hip,lengths,pole,shin_vertices,
                  rest_shin_direction,rest_shin_rotation,floor):
    """Ground a compound boot, allowing heel strike with the toe in the air.

    The heel is rigid with the shin and the toe has its own hinge. Preserve the
    requested hinge orientation; solve ankle height and forward position so the
    actual supporting vertex stays on its rest footprint. Both pieces contribute
    to the unilateral ground constraint.
    """
    rotation,old_z,old_sole=rolling_foot(vertices,flat,angle)
    base=[target[0],target[1]+old_sole,target[2]-old_z]
    # Preserve swing clearance already present in the toe target.
    support_floor=base[1]
    def rotate(rot,v):return [sum(rot[i][j]*v[j] for j in range(3)) for i in range(3)]
    flat_toe=[rotate(flat,v) for v in vertices]
    flat_heel=[M.legik.sub(rotate(rest_shin_rotation,v),rest_shin_direction) for v in shin_vertices]
    footprint=flat_toe+flat_heel
    ankle=list(target)
    for _ in range(400):
        distance=math.dist(hip,ankle)
        if not abs(lengths[0]-lengths[1])+.001<=distance<=sum(lengths)-.001:
            raise ValueError('compound boot support exceeds native leg reach')
        knee,actual=M.legik.solve(hip,ankle,*lengths,pole)
        shin=R.m3mul(R.swing(rest_shin_direction,M.legik.sub(actual,knee)),rest_shin_rotation)
        offsets=[rotate(rotation,v) for v in vertices]
        offsets += [M.legik.sub([rotate(shin,v)[i]+knee[i] for i in range(3)],ankle) for v in shin_vertices]
        index=max(range(len(offsets)),key=lambda i:offsets[i][1])
        desired_y=support_floor-offsets[index][1]
        desired_z=base[2]+footprint[index][2]-offsets[index][2]
        error=max(abs(desired_y-ankle[1]),abs(desired_z-ankle[2]))
        if error<.0001:return ankle,rotation,angle
        ankle[1]+=.2*(desired_y-ankle[1]);ankle[2]+=.2*(desired_z-ankle[2])
    raise ValueError(f'compound heel/toe contact did not converge: residual {error:.4f}, pivot {index}, angle {angle:.2f}')

def tail_response(samples,skel,rest,cfg):
    bones=cfg['bones'];n=len(samples)-1;body=cfg['body'];dt=.025
    reference=R.world_rots(skel,rest)[body]
    input_values=[]
    for p in samples[:-1]:
        delta=R.m3mul(R.world_rots(skel,p)[body],R.m3t(reference))
        axis,angle=R.axis_angle(delta)
        input_values.append([v*math.degrees(angle) for v in axis])
    offsets=[]
    for index,b in enumerate(bones):
        state=[0.,0.,0.];velocity=[0.,0.,0.];record=[]
        omega=2*math.pi*cfg.get('frequency',3.0)/(1+index*.12)
        damping=cfg.get('damping',.9)
        for step in range(n*24):
            t=step%n;lag=cfg.get('lag_ticks',1)*(index+1)
            signal=input_values[(t-lag)%n]
            before=samples[(t-1)%n][body][6:9];now=samples[t][body][6:9];after=samples[(t+1)%n][body][6:9]
            acceleration=[after[j]-2*now[j]+before[j] for j in range(3)]
            target=[-signal[0]*.3-acceleration[1]*.12,
                    -signal[1]*.55+acceleration[0]*.2,-signal[2]*.2]
            # Smaller distributed rotations avoid adding the full lag at every joint.
            target=[max(-cfg.get('limit_degrees',9),min(cfg.get('limit_degrees',9),v/(1+index*.6))) for v in target]
            for _ in range(2):
                for j in range(3):
                    velocity[j]+=(omega*omega*(target[j]-state[j])-2*damping*omega*velocity[j])*dt
                    state[j]+=velocity[j]*dt
            if step>=n*23:record.append(list(state))
        offsets.append(record)
    for t,p in enumerate(samples[:-1]):
        for i,b in enumerate(bones):
            rot=M.mmd.rot_matrix(*(v*4096/360 for v in offsets[i][t]))
            value=R.m3mul(rot,R.rot_of(p[b]))
            p[b][3:6]=[round(v) for v in M.mmd.matrix_euler(value,p[b][3:6])]
    samples[-1][1:]=copy.deepcopy(samples[0][1:])

def support_transfer_displacement(before,after,band=1):
    """Sample horizontal contact velocity at the lowest midpoint surface.

    A heel-to-toe transfer can have no vertex touching at both endpoint ticks.
    Midpoint support estimates the contacting material instead of mistaking
    that transfer for a lost foot. This is a sampled estimate, not a continuous
    friction certificate.
    """
    if not before or len(before)!=len(after):raise ValueError('support correspondence changed')
    heights=[(a[1]+b[1])/2 for a,b in zip(before,after)]
    low=max(heights)
    return min(math.hypot(b[0]-a[0],b[2]-a[2]) for a,b,y in zip(before,after,heights) if y>=low-band)


def fit_pelvis(hips,targets,lengths,max_y=32,max_z=40,max_down=None,allow_end_above=None,preferred=None):
    """Smallest weighted pelvis shift with both hips above their reachable ankles.

    Search fore/aft offset and intersect analytic vertical reach intervals. The
    shorter segment's inner limit prevents folded-knee singularities.
    """
    if allow_end_above is not None:
        return fit_folded_pelvis(hips,targets,lengths,max_y,max_z,max_down,allow_end_above,preferred)
    py,pz=preferred or (0,0)
    choices=[]
    for dz in range(-max_z,max_z+1):
        low,high=-float(max_y),min(float(max_y),max_down if max_down is not None else float(max_y))
        valid=True
        for hip,target,(l1,l2) in zip(hips,targets,lengths):
            horizontal=(hip[0]-target[0])**2+(hip[2]+dz-target[2])**2
            outer=(l1+l2-1)**2-horizontal
            if outer<0:valid=False;break
            inner=max(0,(abs(l1-l2)+1)**2-horizontal)
            low=max(low,target[1]-hip[1]-math.sqrt(outer))
            high=min(high,target[1]-hip[1]-math.sqrt(inner))
        if max_down is not None:low,high=math.ceil(low),math.floor(high)
        if valid and low<=high:
            dy=max(low,min(high,py))
            choices.append(((dy-py)**2+2*(dz-pz)**2,dy,dz))
    if not choices:raise ValueError('no reachable pelvis position within authored bounds')
    _,dy,dz=min(choices)
    return round(dy),dz


def solve_three_segment(hip,paw,lengths,last_direction,pole):
    """Preferred hock orientation plus an analytic upper two-link solution.

    A digitigrade thigh, shin and metatarsal stay separate native links. The
    preferred distal direction is constrained by the chosen source performance;
    unreachable targets are rejected rather than stretching any link.
    """
    if len(lengths)!=3 or min(lengths)<=0 or not all(math.isfinite(v) for v in [*hip,*paw,*lengths,*last_direction,*pole]):
        raise ValueError('invalid digitigrade geometry')
    norm=math.sqrt(sum(v*v for v in last_direction))
    if norm<1e-8:raise ValueError('distal direction is zero')
    offset=[v/norm*lengths[2] for v in last_direction];hock=[paw[i]-offset[i] for i in range(3)]
    reach=math.dist(hip,hock)
    if not abs(lengths[0]-lengths[1])+.001<=reach<=lengths[0]+lengths[1]-.001:
        raise ValueError('digitigrade hock is unreachable with the preferred distal direction')
    knee,actual=M.legik.solve(hip,hock,*lengths[:2],pole)
    return knee,actual,[actual[i]+offset[i] for i in range(3)]


def fit_folded_pelvis(hips,targets,lengths,max_y,max_z,max_down,allow_end_above,preferred=None):
    """Intersect complete vertical reach regions for selected lifted hocks.

    A lifted digitigrade hock may be above its hip; a supporting paw still uses
    the ordinary hip-above-foot region. Preserve inner and outer reach limits.
    """
    if len(allow_end_above)!=len(hips) or any(type(v) is not bool for v in allow_end_above):
        raise ValueError('one explicit folded-end flag per leg is required')
    py,pz=preferred or (0,0)
    choices=[]
    for dz in range(-max_z,max_z+1):
        regions=[(-float(max_y),min(float(max_y),max_down if max_down is not None else float(max_y)))]
        for hip,target,(a,b),folded in zip(hips,targets,lengths,allow_end_above):
            horizontal=(hip[0]-target[0])**2+(hip[2]+dz-target[2])**2
            outer=(a+b-1)**2-horizontal
            if outer<0:regions=[];break
            inner=max(0,(abs(a-b)+1)**2-horizontal);centre=target[1]-hip[1]
            allowed=[(centre-math.sqrt(outer),centre-math.sqrt(inner))]
            if folded:allowed.append((centre+math.sqrt(inner),centre+math.sqrt(outer)))
            regions=[(max(lo,x),min(hi,y)) for lo,hi in regions for x,y in allowed if max(lo,x)<=min(hi,y)]
            if not regions:break
        for lo,hi in regions:
            lo,hi=math.ceil(lo),math.floor(hi)
            if lo<=hi:
                dy=max(lo,min(hi,round(py)));choices.append(((dy-py)**2+2*(dz-pz)**2,dy,dz))
    if not choices:raise ValueError('no reachable folded pelvis position within authored bounds')
    _,dy,dz=min(choices);return dy,dz


def swivel_native_pole(pole,root,end,degrees):
    """Bounded rotation about the support axis, preserving the foot goal."""
    if isinstance(degrees,bool) or not isinstance(degrees,(int,float)) or not math.isfinite(degrees) or abs(degrees)>15:
        raise ValueError('native knee swivel must be within15degrees')
    if degrees==0:return pole
    axis=M.legik.sub(end,root)
    if sum(v*v for v in axis)<1e-8:raise ValueError('knee swivel requires a support axis')
    rotation=M.R.from_axis_angle(M.legik.unit(axis),math.radians(degrees))
    return [sum(rotation[i][j]*pole[j] for j in range(3)) for i in range(3)]


def transported_native_pole(rest_root,rest_mid,rest_end,root,end):
    """Transport the native bend plane without a world-axis pole flip."""
    base=M.legik.sub(rest_end,rest_root);length2=sum(v*v for v in base)
    if length2<1e-8:raise ValueError('native bend chain has no extent')
    mid=M.legik.sub(rest_mid,rest_root);projection=sum(a*b for a,b in zip(mid,base))/length2
    bend=[mid[i]-projection*base[i] for i in range(3)]
    if sum(v*v for v in bend)<1e-8:raise ValueError('straight native chain needs an explicit bend plane')
    rotation=M.R.swing(base,M.legik.sub(end,root))
    return [sum(rotation[i][j]*bend[j] for j in range(3)) for i in range(3)]


def solve_native_chain(rest_root,rest_mid,rest_end,root,end):
    """Solve a rigid two-link chain from native joint positions.

    The low-level solver takes a pole direction, never an absolute knee
    position. Keep that conversion here so moving the scene origin cannot
    change the bend plane.
    """
    first=M.legik.norm(M.legik.sub(rest_mid,rest_root))
    second=M.legik.norm(M.legik.sub(rest_end,rest_mid))
    pole=transported_native_pole(rest_root,rest_mid,rest_end,root,end)
    return M.legik.solve(root,end,first,second,pole)


def cyclic_euler_branches(frames,bones):
    """Choose equivalent Euler poses over a closed cycle, including its seam.

    Greedily following the nearest representation can return on the other
    Euler branch at the end of a loop. A cyclic two-state path avoids placing
    that half-turn change blindly at the closing frame. Logical rotations,
    translations and scales stay unchanged; subframe geometry still needs
    its own review.
    """
    if len(frames)<3:raise ValueError('expected a closed animation cycle')
    result=copy.deepcopy(frames);count=len(frames)-1
    wrap=lambda x:(x+2048)%4096-2048
    cost=lambda a,b:sum(wrap(y-x)**2 for x,y in zip(a,b))
    for bone in bones:
        if not 0<bone<len(frames[0]):raise ValueError('invalid nonroot bone')
        first=M.mmd.rot_matrix(*frames[0][bone][3:6])
        last=M.mmd.rot_matrix(*frames[-1][bone][3:6])
        if max(abs(a-b) for x,y in zip(first,last) for a,b in zip(x,y))>1e-8:
            raise ValueError('logical rotations do not close')
        choices=[]
        for pose in frames[:-1]:
            x,y,z=pose[bone][3:6]
            choices.append([[wrap(x),wrap(y),wrap(z)],
                            [wrap(x+2048),wrap(2048-y),wrap(z+2048)]])
        best=None
        for seed in [0,1]:
            paths={seed:(0,[seed])}
            for tick in range(1,count):
                paths={state:min((value+cost(choices[tick-1][old],choices[tick][state]),path+[state])
                                 for old,(value,path) in paths.items()) for state in [0,1]}
            candidate=min((value+cost(choices[-1][state],choices[0][seed]),path)
                          for state,(value,path) in paths.items())
            if best is None or candidate<best:best=candidate
        for tick,state in enumerate(best[1]):result[tick][bone][3:6]=choices[tick][state]
        result[-1][bone][3:6]=result[0][bone][3:6]
    return result


def smooth_pelvis_cycle(parameters,cfg):
    """Cyclic projected fitting, anticipating contact constraints in time.

    Each projection retains all per-frame reach and body-clearance constraints.
    Keep the best position/velocity/acceleration objective among integer fits.
    """
    n=len(parameters);position=cfg.get('position_weight',.1);velocity=cfg.get('velocity_weight',1);accel=cfg.get('acceleration_weight',4);iterations=cfg.get('iterations',80)
    if n<4 or not 0<position or min(velocity,accel)<0 or velocity+accel<=0 or not 1<=iterations<=500:
        raise ValueError('invalid temporal pelvis objective')
    values=[list(fit_pelvis(**p)) for p in parameters]
    def energy(path):
        return sum((position*path[t][j]**2+velocity*(path[t][j]-path[(t-1)%n][j])**2+
            accel*(path[(t+1)%n][j]-2*path[t][j]+path[(t-1)%n][j])**2)*(1 if j==0 else 2)
            for t in range(n) for j in range(2))
    best=[v[:] for v in values];score=energy(best)
    for _ in range(iterations):
        old=[v[:] for v in values]
        for t in range(n):
            desired=[((velocity+4*accel)*(values[(t-1)%n][j]+values[(t+1)%n][j])-
                accel*(values[(t-2)%n][j]+values[(t+2)%n][j]))/(position+2*velocity+6*accel) for j in range(2)]
            values[t]=list(fit_pelvis(**parameters[t],preferred=desired))
        cost=energy(values)
        if cost<score:best=[v[:] for v in values];score=cost
        if old==values:break
    return best
