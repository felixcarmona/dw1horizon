#!/usr/bin/env python3
"""frame_cost.py MODE SECONDS: on a build with that frame rate (MODE 0/1/2 = FPS 20/30/60; the frame rate is a
build parameter, MOD_FPS_BUILD says which one runs), reset counters, wait, print averages."""

from pathlib import Path as _DevPath
import sys as _dev_sys
_DEV_ROOT = str(next(p for p in _DevPath(__file__).resolve().parents if (p / "tools").is_dir()))
_dev_sys.path.insert(0, _DEV_ROOT)
_dev_sys.path.insert(0, str(_DevPath(_DEV_ROOT) / "tools"))
import subprocess, sys, time, re
R=_DEV_ROOT
def mem(*a): return subprocess.run([R+'/tools/dev/memory_inspector.py',*a],capture_output=True,text=True,cwd=R).stdout
n=sys.argv[1]; secs=float(sys.argv[2])
b=re.search(r'MOD_FPS_BUILD = (\d+)',mem('show','MOD_FPS_BUILD'))
if not b or int(b.group(1))!={'0':20,'1':30,'2':60}[n]: sys.exit(f"the running build is not mode {n} (MOD_FPS_BUILD {b.group(1) if b else '?'}): build it with FPS=")
mem('set','MOD_PERF_RESET=1'); time.sleep(secs)
names='FRAMES TICK_SUM TICK_MAX RENDER_SUM RENDER_MAX GPU_SUM GPU_MAX XRENDER_SUM XRENDER_MAX XGPU_SUM XGPU_MAX XPASSES SUM MAX PERIOD'.split()
out=mem('show',*['MOD_PERF_'+x for x in names])
v={m.group(1):int(m.group(2)) for m in re.finditer(r'MOD_PERF_(\w+) = (-?\d+)',out)}
f=max(v['FRAMES'],1); x=max(v['XPASSES'],1)
print(f"n={n} ticks={v['FRAMES']} tick avg {v['TICK_SUM']/f:.0f} max {v['TICK_MAX']} | render {v['RENDER_SUM']/f:.0f}/{v['RENDER_MAX']} | gpu {v['GPU_SUM']/f:.0f}/{v['GPU_MAX']} | extra passes {v['XPASSES']} render {v['XRENDER_SUM']/x:.0f}/{v['XRENDER_MAX']} gpu {v['XGPU_SUM']/x:.0f}/{v['XGPU_MAX']} | busy {v['SUM']/f:.0f}/{v['MAX']} period {v['PERIOD']}")
