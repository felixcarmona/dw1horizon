#!/usr/bin/env python3
"""Inclusive CPU cycle profile in PCSX-Redux's interpreter/debugger.

Usage: FPS_MAP=... EMU_PORT=... curlingprofile.py OUT.json [TICKS]
Pause on an aiming/throw save state first, or start while that state is active.
Unlike wall time, emulated CPU cycles exclude debugger/HTTP overhead. Inclusive
costs overlap: callers contain callees. Use DuckStation perf for final timings.
"""
from pathlib import Path
import json
import os
import re
import sys
import time
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from tools.dev import emulator as emu
from tools.dev.lua import write_script


def lua(code):
    return emu.api('/api/v1/lua/eval?code='+quote(code)).decode()


def main():
    symbols = dict((name, int(addr, 16)) for addr, name in re.findall(
        r'^\s+(0x[0-9a-f]+)\s+(\w+)\s*$',
        Path(os.environ['FPS_MAP']).read_text(), re.M))
    names = ['KAR_tickStones', 'KAR_updateCollisions', 'KAR_renderScene',
             'KAR_tick', 'KAR_updateRingMarkers', 'KAR_bounceOffWall',
             'KAR_resolveStoneCollision', 'tickObjects', 'NPCEntityTick',
             'tickPartner', 'renderObjects', 'renderDigimon', 'renderMapObjects',
             'GsSetRefView2', 'GsSortObject4', 'SquareRoot0']
    entries = '{'+','.join('{%d,%s}' % (symbols[n], json.dumps(n))
                          for n in names if n in symbols)+'}'
    code = r'''
CP = {bp={}, ret={}, log={}, n=0, done=false}
local function cycles() return tonumber(PCSX.getCPUCycles()) end
local function add(a, name)
  CP.log[name] = {calls=0, cycles=0, max=0}
  CP.bp[#CP.bp+1] = PCSX.addBreakpoint(a, 'Exec', 4, name, function()
    local ra = tonumber(PCSX.getRegisters().GPR.n.ra)
    if CP.ret[ra] == nil then
      CP.ret[ra] = {}
      CP.bp[#CP.bp+1] = PCSX.addBreakpoint(ra, 'Exec', 4, 'profile-return', function()
        local stack = CP.ret[ra]
        local item = table.remove(stack)
        if item == nil then return end
        local dt = (cycles()-item[2]) % 4294967296
        local row = CP.log[item[1]]
        row.calls = row.calls+1; row.cycles = row.cycles+dt
        row.max = math.max(row.max, dt)
      end)
    end
    table.insert(CP.ret[ra], {name, cycles()})
  end)
end
for _, entry in ipairs(ENTRIES) do add(entry[1], entry[2]) end
CP.bp[#CP.bp+1] = PCSX.addBreakpoint(LOOP, 'Exec', 4, 'profile-tick', function()
  CP.n = CP.n+1
  if CP.n < COUNT then return end
  for _, bp in ipairs(CP.bp) do bp:remove() end
  CP.done = true
  PCSX.pauseEmulator()
end)
PCSX.resumeEmulator()
return 'profiling'
'''
    code = code.replace('ENTRIES', entries).replace('LOOP', str(symbols['gameLoop']))
    code = code.replace('COUNT', sys.argv[2] if len(sys.argv) > 2 else '40')
    print(lua('return dofile(%s)' % json.dumps(write_script('fps','curling-profile',code))))
    while lua('return tostring(CP.done)').strip() != 'true':
        time.sleep(2)
    result = lua("local out={} for n,r in pairs(CP.log) do out[#out+1]=string.format('%s %d %d %d',n,r.calls,r.cycles,r.max) end return table.concat(out,'\\n')")
    rows = {}
    for line in result.splitlines():
        name, calls, cycles, maximum = line.split()
        rows[name] = dict(calls=int(calls), cycles=int(cycles), max=int(maximum))
    Path(sys.argv[1]).write_text(json.dumps(rows, indent=2)+'\n')
    print(result)


if __name__ == '__main__':
    main()
