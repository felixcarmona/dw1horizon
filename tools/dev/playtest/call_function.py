#!/usr/bin/env python3
"""Calls game functions in the running emulator (EMU_PORT) and prints what they return (v0), one call per frame.

The calls are made from the entry of gameLoop (the hijack of tools/dev/playtest/call_tournament.py): the function returns to
gameLoop's entry, where the hook restores the real return address. The game must be running in the world.

  EMU_PORT=38068 tools/dev/playtest/call_function.py 'loadDynamicLibrary(12,0,0,0,0)' 'tournamentCheckEligible(3)' ...
Arguments are integers (0x.. allowed) or symbol names (their address). Up to four.
"""

from pathlib import Path as _DevPath
import sys as _dev_sys
_DEV_ROOT = str(next(p for p in _DevPath(__file__).resolve().parents if (p / "tools").is_dir()))
_dev_sys.path.insert(0, _DEV_ROOT)
_dev_sys.path.insert(0, str(_DevPath(_DEV_ROOT) / "tools"))
import os, re, subprocess, sys, time
ROOT = _DEV_ROOT
sys.path.insert(0, os.path.join(ROOT, 'tools'))
from tools.dev import symbols as dwsyms
t = dwsyms.table(os.environ.get('DW_BUILD', 'disc-full'))
calls = []
for c in sys.argv[1:]:
    m = re.fullmatch(r'(\w+)\((.*)\)', c.strip())
    name, args = m.group(1), [a.strip() for a in m.group(2).split(',') if a.strip()]
    vals = [(t[a] if a in t else int(a, 0)) & 0xFFFFFFFF for a in args] + [0] * (4 - len(args))
    calls.append((name, t[name], vals))
gl = t['gameLoop']
pause = "PCSX.pauseEmulator()" if os.environ.get('CALLFN_PAUSE') else ''     # CALLFN_PAUSE=1: freeze the emulator when the last call returns, so the state can be read as the call left it
lua = f"""
if CF and CF.bp then CF.bp:remove() end
CF = {{ q = {{}}, out = {{}}, phase = 0, saved = 0 }}
"""
for name, addr, v in calls:
    lua += f"CF.q[#CF.q+1] = {{{addr}, {v[0]}, {v[1]}, {v[2]}, {v[3]}}}\n"
lua += f"""
CF.bp = PCSX.addBreakpoint({gl}, 'Exec', 4, 'callfn', function()
  local r = PCSX.getRegisters()
  if CF.phase == 1 then
    CF.out[#CF.out + 1] = r.GPR.n.v0
    r.GPR.n.ra = CF.saved; CF.phase = 0
    if #CF.q == 0 then {pause} end
    return
  end
  if CF.phase == 0 and #CF.q > 0 then
    local c = table.remove(CF.q, 1)
    CF.saved = r.GPR.n.ra
    r.GPR.n.a0 = c[2]; r.GPR.n.a1 = c[3]; r.GPR.n.a2 = c[4]; r.GPR.n.a3 = c[5]
    r.GPR.n.ra = {gl}; r.pc = c[1]; CF.phase = 1
  end
end)
return 'armed'
"""
p = os.path.join(ROOT, f'build/callfn-{os.environ.get("EMU_PORT", "default")}.lua')     # one file per emulator: several playtests run at the same time
open(p, 'w').write(lua)
emu = lambda *a: subprocess.run([sys.executable, os.path.join(ROOT, 'tools/dev/emulator.py'), *a], capture_output=True, text=True).stdout
emu('lua', f"dofile('{p}')")
for _ in range(200):
    time.sleep(0.5)
    n = emu('lua', 'return #CF.out').strip()
    if n.isdigit() and int(n) >= len(calls):
        break
res = emu('lua', "local s = {} for i, v in ipairs(CF.out) do s[#s + 1] = tostring(v) end return table.concat(s, ' ')").split()
for (name, _, v), r in zip(calls, res):
    print(f'{name}({", ".join(str(x) for x in v if x or True)[:60]}) = {int(r) & 0xFFFFFFFF}')
