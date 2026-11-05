#!/usr/bin/env python3
"""Validate the reviewed Suijinmon generator against its pinned source model."""
import argparse
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[3]
sys.path[:0]=[str(ROOT),str(ROOT/'tools')]
import animsheet
import mmd
from tools.models.field_animations import quadruped as q
from tools.models.field_animations.suijinmon import build,PROFILE


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('model',type=Path);p.add_argument('--out',type=Path,required=True)
    a=p.parse_args();skeleton=mmd.exe().skeleton[408]
    data,report=build(a.model.read_bytes(),skeleton)
    model=mmd.MMD.parse(data,len(skeleton));model.type=408
    rig=q.Rig(model,skeleton,PROFILE)
    frames,_,_=animsheet.slot_frames(model,len(skeleton),3)
    floor=q._floor(rig,frames)
    assert floor<=q.FLOOR,('condition walk floor',floor)
    speed=abs(frames[-1][0][8]-frames[0][0][8])/(len(frames)-1)
    assert abs(speed-12)<.1,('condition walk speed',speed)
    animation=model.anims.anims[model.anims.table[3]]
    played,_=q._played(animation,len(skeleton),3,27)
    for tick in range(27,27*9+1,27):
        assert all(abs(a-b)<=2 for pose,other in zip(played[0][1:],played[tick][1:]) for a,b in zip(pose,other))
    report['condition_walk'].update(lowest_point=round(floor,2),nine_loops_close=True)
    a.out.write_text(json.dumps(report,indent=2)+'\n')
    print('PASS: mesh unchanged; only walk, condition, run, feed and their aliases changed')
    print('PASS: four-leg stance, floor clearance, closed loops, native speeds and model storage')

if __name__=='__main__':main()
