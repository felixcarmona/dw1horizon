#!/usr/bin/env python3
"""random_call_rate.py MODE SECONDS: rand() calls per tick (seed at 0x80008464); MODE is a label (the frame rate is the
build's, MOD_FPS_BUILD)."""

from pathlib import Path as _DevPath
import sys as _dev_sys
_DEV_ROOT = str(next(p for p in _DevPath(__file__).resolve().parents if (p / "tools").is_dir()))
_dev_sys.path.insert(0, _DEV_ROOT)
_dev_sys.path.insert(0, str(_DevPath(_DEV_ROOT) / "tools"))
import subprocess, sys, time, re
R=_DEV_ROOT
def mem(*a): return subprocess.run([R+'/tools/dev/memory_inspector.py',*a],capture_output=True,text=True,cwd=R).stdout
def read():
    o=mem('show','0x80008464','MOD_FPS_TICKS')
    v=re.findall(r'= (\d+)',o); return int(v[0]),int(v[1])
s0,t0=read(); time.sleep(float(sys.argv[2])); s1,t1=read()
x=s0;k=0
while x!=s1 and k<2000000:
    x=(x*1103515245+12345)&0xffffffff; k+=1
print(f"n={sys.argv[1]} ticks={t1-t0} rand calls={k} per tick={k/max(t1-t0,1):.2f}" if x==s1 else "not found")
