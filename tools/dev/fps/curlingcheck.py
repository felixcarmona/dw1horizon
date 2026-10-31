#!/usr/bin/env python3
"""Replay curling input per logic tick and compare semantic stone state.

Usage: curlingcheck.py STATE MODE INTERP TICKS OUT
Requires PCSX-Redux's interpreter/debugger, EMU_PORT, DW_SYMS and FPS_MAP.
Start from an aiming save state of the SAME disc. MODE is the runtime option
(0/1/2). Every comparison uses twelve refreshes per tick, including mode 0.
The log excludes rendering matrices, ordering tables and interpolation caches.
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
    return emu.api('/api/v1/lua/eval?code=' + quote(code)).decode()


def main():
    state, mode, interp, count, output = sys.argv[1:]
    symbols = dict((name, int(addr, 16)) for addr, name in re.findall(
        r'^\s+(0x[0-9a-f]+)\s+(\w+)\s*$',
        Path(os.environ['FPS_MAP']).read_text(), re.M))
    def sym(name):
        return symbols[name] & 0x1fffff
    counters = ['MAIN_D_80135244', 'MAIN_D_8013523A', 'MAIN_D_8013523C',
                'MAIN_D_8013523E', 'MAIN_D_8013524C', 'MAIN_D_80135252',
                'MAIN_D_80135238', 'MAIN_D_80135220']
    sizes = [4, 2, 1, 2, 4, 2, 2, 1]
    code = r'''
PCSX.pauseEmulator()
if KC_BP then KC_BP:remove() end
if KC_L then KC_L:remove() end
local f = Support.File.open(STATE, 'READ')
PCSX.loadSaveState(f); f:close()
local m = PCSX.getMemPtr()
local function w(a, n)
  local v = 0
  for i = n-1, 0, -1 do v = v * 256 + m[a+i] end
  return v
end
local function put(a, v)
  for i = 0, 3 do m[a+i] = v % 256; v = math.floor(v / 256) end
end
local function bytes(a, n)
  local s = {}
  for i = 0, n-1 do s[#s+1] = string.format('%02x', m[a+i]) end
  return table.concat(s)
end
local function hash(h, a, n, bones)
  for i = 0, n-1 do
    if not bones or i % 136 < 16 or i % 136 >= 20 then
      h = (h * 33 + m[a+i]) % 2147483647
    end
  end
  return h
end
KC_LOG = {}; KC_N = 0; KC_DONE = false
local applied = false
local pad = PCSX.SIO0.slots[1].pads[1]
KC_L = PCSX.Events.createEventListener('GPU::Vsync', function()
  if not applied then
    m = PCSX.getMemPtr()
    put(MODE_ADDR, MODE); put(INTERP_ADDR, INTERP); put(TEST_ADDR, PERIOD)
    FIXTURE_SETUP
    applied = true
  end
end)
local last, age = -1, 0
KC_BP = PCSX.addBreakpoint(LOOP_ADDR, 'Exec', 4, 'curlingcheck', function()
  if not applied or KC_DONE then return end
  local state = w(STATE_ADDR, 4)
  if state == last then age = age + 1 else age = 0; last = state end
  local row = {tostring(state), string.format('%08x', w(0x8464, 4))}
  for _, r in ipairs(COUNTERS) do row[#row+1] = bytes(r[1], r[2]) end
  for p = 0, 2 do
    local base = STONES_ADDR + p * 868
    row[#row+1] = bytes(base, 8)
    for i = 0, 4 do
      local stone = base + 8 + i * 172
      row[#row+1] = bytes(stone, 36) .. bytes(stone+148, 24)
    end
  end
  for e = 0, 9 do
    local ptr = w(ENTITIES_ADDR+e*4, 4)
    if ptr >= 0x80000000 and ptr < 0x80200000 then
      local addr = ptr % 0x200000
      local typ = w(addr, 4)
      local bones = w(DIGIMON_ADDR+typ*52+20, 4)
      local pose = w(addr+4, 4) % 0x200000
      local momentum = w(addr+12, 4) % 0x200000
      local h = hash(7, addr, 88)
      if bones < 64 then
        h = hash(h, pose, bones*136, true)
        h = hash(h, momentum, bones*82)
      end
      row[#row+1] = string.format('%x', h)
    else row[#row+1] = '-' end
  end
  KC_N = KC_N + 1; KC_LOG[KC_N] = table.concat(row, ' ')
  pad.clearOverride(PCSX.CONSTS.PAD.BUTTON.CROSS); pad.clearOverride(PCSX.CONSTS.PAD.BUTTON.RIGHT)
  if KC_N >= COUNT then
    KC_DONE = true; KC_BP:remove(); KC_BP = nil
    KC_L:remove(); KC_L = nil
    PCSX.pauseEmulator()
    return
  end
  if state == 6 then
    if age < 10 then pad.setOverride(PCSX.CONSTS.PAD.BUTTON.RIGHT)
    elseif age == 30 then pad.setOverride(PCSX.CONSTS.PAD.BUTTON.CROSS) end
  elseif state == 8 then
    if w(POWER_ADDR, 2) >= 1500 then pad.setOverride(PCSX.CONSTS.PAD.BUTTON.CROSS) end
  elseif state ~= 11 and age % 12 == 0 then pad.setOverride(PCSX.CONSTS.PAD.BUTTON.CROSS) end
end)
PCSX.resumeEmulator()
return 'running'
'''
    fixture_setup = ''
    if os.environ.get('KC_FIXTURE'):
        fixture = json.loads(Path(os.environ['KC_FIXTURE']).read_text())
        writes = [(sym(n), bytes.fromhex(v)) for n,v in fixture['globals'].items()]
        writes.append((0x8464, bytes.fromhex(fixture['rng'])))
        for p,row in enumerate(fixture['rows']):
            base = sym('KAR_D_8005B5A0')+p*868
            writes.append((base, bytes.fromhex(row['header'])))
            for i,stone in enumerate(row['stones']):
                writes.append((base+8+i*172, bytes.fromhex(stone[0])))
                writes.append((base+8+i*172+148, bytes.fromhex(stone[1])))
        fixture_setup = '\n'.join('m[%d]=%d' % (a+i,b)
                                  for a,data in writes for i,b in enumerate(data))
    values = dict(STATE=json.dumps(str(Path(state).resolve())), MODE=int(mode),
                  INTERP=int(interp), COUNT=int(count),
                  PERIOD=int(os.environ.get('KC_PERIOD','12')),
                  FIXTURE_SETUP=fixture_setup,
                  LOOP_ADDR=symbols['gameLoop'],
                  MODE_ADDR=sym('MOD_FPS_MODE_RUN'),
                  INTERP_ADDR=sym('MOD_FPS_INTERP'),
                  TEST_ADDR=sym('MOD_FPS_TEST_TICK'),
                  STATE_ADDR=sym('MAIN_D_80135244'),
                  POWER_ADDR=sym('MAIN_D_8013523E'),
                  STONES_ADDR=sym('KAR_D_8005B5A0'),
                  ENTITIES_ADDR=sym('ENTITY_TABLE'),
                  DIGIMON_ADDR=sym('DIGIMON_DATA'),
                  COUNTERS='{' + ','.join('{%d,%d}' % (sym(n), s)
                      for n, s in zip(counters, sizes)) + '}')
    code = re.sub(r'\b(' + '|'.join(values) + r')\b',
                  lambda m: str(values[m[0]]), code)
    path = write_script('fps', 'curling-check', code)
    print(lua('return dofile(%s)' % json.dumps(path)), flush=True)
    while lua('return tostring(KC_DONE)').strip() != 'true':
        time.sleep(5)
        print(lua('return tostring(KC_N)'), flush=True)
    Path(output).write_text(lua('return table.concat(KC_LOG, "\\n")') + '\n')
    print(output)


if __name__ == '__main__':
    main()
