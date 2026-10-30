#!/usr/bin/env python3
"""Starts a tournament in the running emulator (EMU_PORT) without going through the registration desk.

The emulator must be in the Arena Lobby (screen 208, `game_state.py warp 208 0`) with control. It sets
pstat 3 (the cup, default 0), then hooks gameLoop's entry: at the next frame startTournament is called
with the return address set back to gameLoop (the same hijack tools/dev/story_trace.lua uses for
callScriptSection), and the hook is removed when it returns.

  EMU_PORT=38060 tools/dev/playtest/call_tournament.py [CUP]
"""

from pathlib import Path as _DevPath
import sys as _dev_sys
_DEV_ROOT = str(next(p for p in _DevPath(__file__).resolve().parents if (p / "tools").is_dir()))
_dev_sys.path.insert(0, _DEV_ROOT)
_dev_sys.path.insert(0, str(_DevPath(_DEV_ROOT) / "tools"))
import os, subprocess, sys
ROOT = _DEV_ROOT
sys.path.insert(0, os.path.join(ROOT, 'tools'))
from tools.dev import symbols as dwsyms

cup = int(sys.argv[1]) if len(sys.argv) > 1 else 0
t = dwsyms.table(os.environ.get('DW_BUILD', 'disc-full'))
gl, st = t['gameLoop'], t['startTournament']
subprocess.run([sys.executable, os.path.join(ROOT, 'tools/dev/game_state.py'), 'pstat', '3', str(cup)], check=True)
lua = f"""
if CALLT and CALLT.bp then CALLT.bp:remove() end
CALLT = {{ phase = 0, saved = 0 }}
CALLT.bp = PCSX.addBreakpoint({gl}, 'Exec', 4, 'calltourn', function()
  local r = PCSX.getRegisters()
  if CALLT.phase == 1 then r.GPR.n.ra = CALLT.saved; CALLT.phase = 2; return end
  if CALLT.phase == 0 then
    CALLT.saved = r.GPR.n.ra; r.GPR.n.ra = {gl}; r.pc = {st}; CALLT.phase = 1
  end
end)
return 'armed'
"""
open(os.path.join(ROOT, 'build/calltourn.lua'), 'w').write(lua)
print(subprocess.run([sys.executable, os.path.join(ROOT, 'tools/dev/emulator.py'), 'lua', "dofile('" + os.path.join(ROOT, 'build/calltourn.lua') + "')"], capture_output=True, text=True).stdout)
