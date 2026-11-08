#!/usr/bin/env python3
"""Exercise the renderer's actual Euler interpolation against native run poses."""
import argparse
import json
import math
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT / 'tools'), str(ROOT)]
import animsheet
import mmd
import retarget as rt


def function(source, name):
    match = re.search(r'^static [^\n]+\b' + name + r'\([^;{}]*\)\n\{', source, re.M)
    return source[match.start():source.index('\n}\n', match.end()) + 3]


def error(a, b):
    rotation = rt.m3mul(rt.m3t(a), b)
    return math.degrees(math.acos(max(-1, min(1, (sum(rotation[i][i] for i in range(3))-1)/2))))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('tree', type=Path)
    parser.add_argument('out', type=Path)
    parser.add_argument('--baseline', action='store_true')
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    source = (args.tree / 'src/main/main.c').read_text()
    helpers = '\n'.join(function(source, n) for n in ('modLerpAngle', 'modAbs', 'modAngleDiff'))
    if args.baseline:
        helpers += '''\nstatic void modLerpBoneRotation(SVECTOR *o,const int16_t *p,const SVECTOR *c,int32_t a) {
 o->vx=modLerpAngle(p[0],c->vx,a);o->vy=modLerpAngle(p[1],c->vy,a);o->vz=modLerpAngle(p[2],c->vz,a);
}\n'''
    else:
        helpers += function(source, 'modLerpBoneRotation')
        assert 'modLerpBoneRotation(&rot, pb->rot, &pd->rotation, alpha);' in source
    harness = '#include <stdint.h>\n#include <stdio.h>\ntypedef struct { int16_t vx,vy,vz,pad; } SVECTOR;\n'
    harness += helpers + '''\nint main(void) {
 int x,y,z,u,v,w,a;while(scanf("%d%d%d%d%d%d%d",&x,&y,&z,&u,&v,&w,&a)==7) {
 int16_t p[3]={x,y,z};SVECTOR c={u,v,w,0},o={0};modLerpBoneRotation(&o,p,&c,a);
 printf("%d %d %d\\n",o.vx,o.vy,o.vz);
 }return 0;
}\n'''
    c = args.out/'interpolation.c'; exe = args.out/'interpolation'
    c.write_text(harness)
    # The existing shortest-arc helpers deliberately sign-extend 12 bits by
    # shifting. Keep that target idiom while sanitizing the remaining math.
    subprocess.run(['cc','-O1','-g','-fsanitize=undefined','-fno-sanitize=shift','-fno-sanitize-recover=all',str(c),'-o',str(exe)],check=True)
    model = mmd.MMD.load(str(ROOT/'extracted/CHDAT/MMD0/GREY.MMD'),5)
    frames,_,_ = animsheet.slot_frames(model,26,4)
    cases = [(a[bone][3:6], b[bone][3:6], alpha, tick, bone)
             for tick,(a,b) in enumerate(zip(frames,frames[1:]))
             for bone in range(1,26) for alpha in (0,1365,2730,4096)]
    data = ''.join(' '.join(map(str,(*a,*b,alpha)))+'\n' for a,b,alpha,_,_ in cases)
    run = subprocess.run([str(exe)],input=data,text=True,capture_output=True,check=True)
    assert not run.stderr, run.stderr
    rows = []
    for case, line in zip(cases,run.stdout.splitlines(),strict=True):
        a,b,alpha,tick,bone = case
        actual = mmd.rot_matrix(*map(int,line.split()))
        expected = mmd.quat_matrix(mmd._slerp(mmd.quat(*a),mmd.quat(*b),alpha/4096))
        degrees = error(actual,expected)
        if alpha in (0,4096):
            assert degrees < .00001,(case,degrees)
        if tick == 17 and bone in (19,23) and alpha in (1365,2730):
            rows.append(dict(tick=tick,bone=bone,alpha=alpha,error_degrees=degrees))
            assert degrees > 9 if args.baseline else degrees < .2,(case,degrees)
    report = dict(cases=len(cases),baseline=args.baseline,seam=rows)
    (args.out/'result.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))


if __name__ == '__main__':
    main()
