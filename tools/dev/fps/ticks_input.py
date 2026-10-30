#!/usr/bin/env python3
"""ticks_input.py "RIGHT:33 LEFT+R1:33 NONE:10 ..."  |  ticks_input.py wait
Plays pad input by logic tick (MOD_FPS_TICKS), not by wall clock, so two runs
get exactly the same input on the same ticks. A Lua GPU::Vsync listener sets the
pad overrides for the current tick; 'wait' blocks until the script ends."""

from pathlib import Path as _DevPath
import sys as _dev_sys
_DEV_ROOT = str(next(p for p in _DevPath(__file__).resolve().parents if (p / "tools").is_dir()))
_dev_sys.path.insert(0, _DEV_ROOT)
_dev_sys.path.insert(0, str(_DevPath(_DEV_ROOT) / "tools"))
from tools.dev.lua import write_script
import subprocess, sys, os, re, time
R=_DEV_ROOT
S=os.path.dirname(os.path.abspath(__file__))
MAP=os.environ.get('FPS_MAP', R+'/build/full/exe/SLUS_010.32.elf.map')
def lua(code):
    p = write_script('fps', 'tick-input', code)
    return subprocess.run([R+'/tools/dev/emulator.py','lua','return dofile("%s")'%p],capture_output=True,text=True,cwd=R).stdout.strip()
def sym(name):
    for line in open(MAP):
        m=re.match(r'\s+(0x[0-9a-f]+)\s+'+name+r'\s*$',line)
        if m: return int(m.group(1),16)&0x1fffff
if sys.argv[1]=='wait':
    while lua('return tostring(TI_DONE)')!='true': time.sleep(0.5)
    print('done'); sys.exit()
segs=[]
for tok in sys.argv[1].split():
    b,n=tok.split(':'); segs.append(([x for x in b.split('+') if x!='NONE'],int(n)))
tbl='{'+','.join('{%d,{%s}}'%(n,','.join('PCSX.CONSTS.PAD.BUTTON.'+x for x in bs)) for bs,n in segs)+'}'
a=sym('MOD_FPS_TICKS')
print(lua('''TI_SEGS = %s; TI_START = nil; TI_DONE = false; TI_HELD = {}
local pad = PCSX.SIO0.slots[1].pads[1]
TI_L = PCSX.Events.createEventListener('GPU::Vsync', function()
  local m = PCSX.getMemPtr()
  local t = m[%d] + m[%d] * 256 + m[%d] * 65536
  if TI_START == nil then TI_START = t end
  local k = t - TI_START; local want = nil
  for _, s in ipairs(TI_SEGS) do
    if k < s[1] then want = s[2]; break end
    k = k - s[1]
  end
  for b, _ in pairs(TI_HELD) do pad.clearOverride(b) end
  TI_HELD = {}
  if want == nil then TI_DONE = true; TI_L:remove(); TI_L = nil; return end
  for _, b in ipairs(want) do pad.setOverride(b); TI_HELD[b] = true end
end)
return 'playing'
'''%(tbl,a,a+1,a+2)))
