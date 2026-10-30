#!/usr/bin/env python3
"""statecheck.py start N  |  statecheck.py dump OUT
At the entry of gameLoop (a Lua exec breakpoint: every render pass of the
previous tick is over and everything interpolated has been put back) records
for N ticks: MOD_FPS_TICKS, the rand() seed word, the tamer's anim position
and frame, and a hash of every ENTITY_TABLE entity (struct, all bones'
PositionData except posMatrix.flg, momentum data). Needs the interpreter
(EMU_ARGS="-interpreter -debugger", PCSX.settings.emulator.Debug.Debug = true)."""

from pathlib import Path as _DevPath
import sys as _dev_sys
_DEV_ROOT = str(next(p for p in _DevPath(__file__).resolve().parents if (p / "tools").is_dir()))
_dev_sys.path.insert(0, _DEV_ROOT)
_dev_sys.path.insert(0, str(_DevPath(_DEV_ROOT) / "tools"))
from tools.dev.lua import write_script
import subprocess, sys, os, re
R=_DEV_ROOT; S=os.path.dirname(os.path.abspath(__file__))
MAP=os.environ.get('FPS_MAP', R+'/build/full/exe/SLUS_010.32.elf.map')
def sym(n):
    for l in open(MAP):
        m=re.match(r'\s+(0x[0-9a-f]+)\s+'+n+r'\s*$',l)
        if m: return int(m.group(1),16)
    sys.exit('no '+n)
def lua(code):
    p = write_script('fps', 'state-check', code)
    return subprocess.run([R+'/tools/dev/emulator.py','lua','return dofile("%s")'%p],capture_output=True,text=True,cwd=R).stdout.strip()
if sys.argv[1]=='start':
    n=int(sys.argv[2])
    print(lua('''SC_LOG = {}; SC_N = 0; SC_MAX = %d
local function w32(m, a) return m[a] + m[a+1]*256 + m[a+2]*65536 + m[a+3]*16777216 end
local function hash(m, h, a, len, skip)
  for i = 0, len - 1 do
    if skip == nil or (i %% 0x88) < 0x10 or (i %% 0x88) >= 0x14 then h = (h * 33 + m[a + i]) %% 2147483647 end
  end
  return h
end
SC_BP = PCSX.addBreakpoint(0x%x, 'Exec', 4, 'statecheck', function()
  if SC_N >= SC_MAX then return end
  local m = PCSX.getMemPtr()
  local parts = {}
  for e = 0, 9 do
    local p = w32(m, 0x%x + e * 4)
    if p == 0 then parts[#parts + 1] = '-' else
      p = p %% 0x200000
      local typ = w32(m, p)
      local bones = w32(m, 0x%x + typ * 52 + 20)
      local pd = w32(m, p + 4) %% 0x200000
      local mo = w32(m, p + 12) %% 0x200000
      local h = hash(m, 7, p, 0x58)
      h = hash(m, h, pd, bones * 0x88, true)
      h = hash(m, h, mo, bones * 82)
      parts[#parts + 1] = string.format('%%x', h)
    end
  end
  local t = %s
  SC_N = SC_N + 1
  SC_LOG[SC_N] = table.concat({w32(m, 0x%x), w32(m, 0x8464), t, table.concat(parts, ',')}, ' ')
  if SC_N >= SC_MAX then SC_BP:remove() end
end)
return 'statecheck on'
'''%(n,sym('gameLoop'),sym('ENTITY_TABLE')&0x1fffff,sym('DIGIMON_DATA')&0x1fffff,
     '(function() local p = w32(m, %d) %% 0x200000; return w32(m, p+16) .. "," .. w32(m, p+24) .. "," .. (m[p+28] + m[p+29]*256) .. "," .. m[p+46] end)()'%(sym('ENTITY_TABLE')&0x1fffff),
     sym('MOD_FPS_TICKS')&0x1fffff)))
elif sys.argv[1]=='n':
    print(lua('return tostring(SC_N)'))
else:
    open(sys.argv[2],'w').write(lua('return table.concat(SC_LOG, "\\n")')+'\n')
