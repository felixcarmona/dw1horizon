#!/usr/bin/env python3
"""interpolation_cost.py BONES SECONDS [MODE]: MOD_FPS_INTERP_BONES=BONES, then frame_cost.py (MODE: the build's, 0/1/2 = FPS 20/30/60, default 2) plus
the interpolation cost (lines per pass in modInterpApply / modInterpRestore, per tick
in the snapshot) and what was interpolated (MOD_INTERP_STATS deltas per pass)."""

from pathlib import Path as _DevPath
import sys as _dev_sys
_DEV_ROOT = str(next(p for p in _DevPath(__file__).resolve().parents if (p / "tools").is_dir()))
_dev_sys.path.insert(0, _DEV_ROOT)
_dev_sys.path.insert(0, str(_DevPath(_DEV_ROOT) / "tools"))
import subprocess, sys, time, re, struct
R=_DEV_ROOT
def run(*a): return subprocess.run(list(a),capture_output=True,text=True,cwd=R).stdout
def words(name,n):
    out=run(R+'/tools/dev/memory_inspector.py','dump',name,str(4*n))
    b=bytes(int(x,16) for l in out.splitlines() for x in l.split()[1:])
    return struct.unpack('<%di'%n,b[:4*n])
b=sys.argv[1]; secs=sys.argv[2]; n=sys.argv[3] if len(sys.argv)>3 else '2'
run(R+'/tools/dev/memory_inspector.py','set',f'MOD_FPS_INTERP_BONES={b}')
s0=words('MOD_INTERP_STATS',6)
out=run('python3',R+'/tools/dev/fps/frame_cost.py',n,secs)
s1=words('MOD_INTERP_STATS',6); pi=words('MOD_PERF_INTERP',4)
d=[y-x for x,y in zip(s0,s1)]; p=max(pi[2],1); t=max(int(re.search(r'ticks=(\d+)',out).group(1)),1)
print(f'bones={b}', out.strip())
print(f'   apply {pi[0]/p:.1f} restore {pi[1]/p:.1f} lines/pass, snapshot {pi[3]/t:.1f} lines/tick | per lerped pass: roots {d[1]/max(d[0],1):.2f} skeletons {d[4]/max(d[0],1):.2f} bones {d[5]/max(d[0],1):.1f}')
