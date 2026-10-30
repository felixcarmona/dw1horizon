#!/usr/bin/env python3
"""tracer.py start VAR[:size[s]] ...  |  tracer.py dump [stop]
Records the given variables once per logic tick (when MOD_FPS_TICKS changes),
sampled at the emulator's vblank, via a temporary Lua GPU::Vsync listener."""

from pathlib import Path as _DevPath
import sys as _dev_sys
_DEV_ROOT = str(next(p for p in _DevPath(__file__).resolve().parents if (p / "tools").is_dir()))
_dev_sys.path.insert(0, _DEV_ROOT)
_dev_sys.path.insert(0, str(_DevPath(_DEV_ROOT) / "tools"))
from tools.dev.lua import write_script
import subprocess, sys, re, os
R=_DEV_ROOT
S=os.path.dirname(os.path.abspath(__file__))
def emu_lua_file(code):
    p = write_script('fps', 'timing-trace', code)
    return subprocess.run([R+'/tools/dev/emulator.py','lua','return dofile("%s")'%p],capture_output=True,text=True,cwd=R).stdout
MAP=os.environ.get('FPS_MAP', R+'/build/full/exe/SLUS_010.32.elf.map')
_t=None
def addr(name):
    global _t
    if _t is None:
        _t={}
        for line in open(MAP):
            m=re.match(r'\s+(0x[0-9a-f]+)\s+([A-Za-z_][A-Za-z0-9_]*)\s*$',line)
            if m: _t[m.group(2)]=int(m.group(1),16)
    if name not in _t: sys.exit('no var '+name)
    return _t[name]&0x1fffff
if sys.argv[1]=='start':
    specs=[]
    for v in ['MOD_FPS_TICKS:4']+sys.argv[2:]:
        name,_,sz=v.partition(':'); sz=sz or '4'
        signed=sz.endswith('s'); sz=int(sz.rstrip('s'))
        if name.startswith('0x'): a=int(name,16)&0x1fffff
        elif '+' in name: b,o=name.split('+'); a=addr(b)+int(o,0)
        else: a=addr(name)
        specs.append((a,sz,signed))
    rd=[]
    for a,sz,sg in specs:
        e='(m[%d]+m[%d]*256+m[%d]*65536+m[%d]*16777216)'%(a,a+1,a+2,a+3) if sz==4 else ('(m[%d]+m[%d]*256)'%(a,a+1) if sz==2 else 'm[%d]'%a)
        if sg: lim=2**(8*sz); e='(function(x) if x>=%d then return x-%d end return x end)(%s)'%(lim//2,lim,e)
        rd.append(e)
    code='''TR_LOG = {}; TR_LAST = -1; TR_N = 0
TR_L = PCSX.Events.createEventListener('GPU::Vsync', function()
  local m = PCSX.getMemPtr()
  local t = %s
  if t ~= TR_LAST and TR_N < 3000 then
    TR_LAST = t; TR_N = TR_N + 1
    TR_LOG[TR_N] = table.concat({%s}, ' ')
  end
end)
return 'tracing'
'''%(rd[0],', '.join('tostring(%s)'%e for e in rd))
    print(emu_lua_file(code))
else:
    code='local s = table.concat(TR_LOG, "\\n")\n'
    if len(sys.argv)>2: code+='TR_L:remove(); TR_L = nil\n'
    code+='return s\n'
    print(emu_lua_file(code))
