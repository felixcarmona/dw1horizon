#!/usr/bin/env python3
"""clockrate.py MINUTES: emulated vblanks, logic ticks and presented frames per game
minute, measured over MINUTES minute changes by a Lua GPU::Vsync listener
(emulated time, so it does not depend on how fast the emulator runs)."""

from pathlib import Path as _DevPath
import sys as _dev_sys
_DEV_ROOT = str(next(p for p in _DevPath(__file__).resolve().parents if (p / "tools").is_dir()))
_dev_sys.path.insert(0, _DEV_ROOT)
_dev_sys.path.insert(0, str(_DevPath(_DEV_ROOT) / "tools"))
from tools.dev.lua import write_script
import subprocess, sys, os, re, time
R=_DEV_ROOT; S=os.path.dirname(os.path.abspath(__file__))
MAP=os.environ.get('FPS_MAP', R+'/build/full/exe/SLUS_010.32.elf.map')
def sym(n):
    for l in open(MAP):
        m=re.match(r'\s+(0x[0-9a-f]+)\s+'+n+r'\s*$',l)
        if m: return int(m.group(1),16)&0x1fffff
def lua(code):
    p = write_script('fps', 'clock-rate', code)
    return subprocess.run([R+'/tools/dev/emulator.py','lua','return dofile("%s")'%p],capture_output=True,text=True,cwd=R).stdout.strip()
n=int(sys.argv[1]); mi=sym('MINUTE'); tk=sym('MOD_FPS_TICKS'); rn=sym('MOD_FPS_RENDERS')
w=lambda a:'(m[%d]+m[%d]*256+m[%d]*65536)'%(a,a+1,a+2)
lua('''CR_V = 0; CR_LAST = nil; CR_LOG = {}; CR_N = %d
CR_L = PCSX.Events.createEventListener('GPU::Vsync', function()
  local m = PCSX.getMemPtr(); CR_V = CR_V + 1
  local mn = m[%d]
  if CR_LAST ~= nil and mn ~= CR_LAST and #CR_LOG <= CR_N then CR_LOG[#CR_LOG + 1] = CR_V .. ' ' .. %s .. ' ' .. %s end
  CR_LAST = mn
  if #CR_LOG > CR_N then CR_L:remove(); CR_L = nil end
end)
return 'ok'
'''%(n,mi,w(tk),w(rn)))
while lua('return tostring(#CR_LOG > CR_N)')!='true': time.sleep(1)
rows=[list(map(int,l.split())) for l in lua('return table.concat(CR_LOG, "\\n")').split('\n')]
v=rows[-1][0]-rows[0][0]; t=rows[-1][1]-rows[0][1]; r=rows[-1][2]-rows[0][2]
print('per game minute over %d minutes: %.2f vblanks (%.3f s at 60 Hz), %.2f ticks, %.2f frames'%(n,v/n,v/n/60,t/n,r/n))
