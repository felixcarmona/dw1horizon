#!/usr/bin/env python3
"""Several wild battles in a row on one screen, with a tall partner and every enemy joining: the proof that the
background stream and the battle camera leave the fight's memory alone (patch 0160; before it the second fight of a
screen jumped through garbage when the camera's lift asked the stream for a tile: docs/reference/memory.md,
"The ring in a battle").
  EMU_PORT=38312 tools/dev/playtest/battle_stream.py DISC.cue [--card CARD.mcd] [--screen N --exit K] [--battles N]
                                                  [--syms NAME] [--out DIR] [--keep]
Defaults: build/states/cherrymon.mcd (Cherrymon: tall enough for the camera lift), screen 324 exit 0 (the story mod's
Seam 2: Psychemon and Shamamon by day, 1500 apart; on the base disc use --screen 0 --exit 0, Native Forest), 3
battles, --syms disc-<disc name>, 45 minutes at most. The emulator runs the interpreter with the debugger: a first-chance exception
pauses it. What is checked, in the emulator:
  - no pause (no exception, no jump into the kernel's memory 0..0x7F);
  - the stream is never reopened outside the world (a Lua breakpoint on tfsStreamOpen with GAME_STATE != 0 fails);
  - every battle ends with the world back (GAME_STATE 0, tamer.state 0) and N battles were fought;
  - MOD_TFS_STATS.refused stays 0: the battle camera asked for no tile;
  - the VRAM tile window (MAP_TILE_X/Y) never moves during a fight while the camera does (the lift, clamped to the window):
    before each fight the tamer is placed so that the map camera sits 6 px inside the band's top edge, where any lift
    used to shift the rows (the crash); band_edge_px and camera_lift per fight are in the result.
Trigger 1 (boss battle: everyone on screen joins) is set for the run; the partner's care state is reset so it never
begs. Prints one JSON line and exits 1 on a failed check. About 4 minutes per battle on the interpreter.
"""

from pathlib import Path as _DevPath
import sys as _dev_sys
_DEV_ROOT = str(next(p for p in _DevPath(__file__).resolve().parents if (p / "tools").is_dir()))
_dev_sys.path.insert(0, _DEV_ROOT)
_dev_sys.path.insert(0, str(_DevPath(_DEV_ROOT) / "tools"))
import argparse, json, math, os, struct, subprocess, sys, time, urllib.parse
ROOT = _DEV_ROOT
sys.path.insert(0, os.path.join(ROOT, 'tools'))

ap = argparse.ArgumentParser()
ap.add_argument('disc')
ap.add_argument('--card', default='build/states/cherrymon.mcd')
ap.add_argument('--screen', type=int, default=324)
ap.add_argument('--exit', type=int, default=0)
ap.add_argument('--battles', type=int, default=3)
ap.add_argument('--syms', default=None)
ap.add_argument('--out', default='build/playtest-battle-stream')
ap.add_argument('--max', type=float, default=2700, help='seconds for the whole run (a fight takes 3-5 minutes on the interpreter)')
ap.add_argument('--keep', action='store_true', help='leave the emulator running at the end')
a = ap.parse_args()
os.environ.setdefault('EMU_PORT', '38312')
os.environ['DW_SYMS'] = a.syms or ('disc-' + os.path.splitext(os.path.basename(a.disc))[0])
os.environ['EMU_ARGS'] = (os.environ.get('EMU_ARGS', '') + ' -interpreter -debugger').strip()
from tools.dev import emulator as emu; from tools.dev import game_state as gamestate
OUT = os.path.join(ROOT, a.out); os.makedirs(OUT, exist_ok=True)
LOG = os.path.join(OUT, 'trap.log')
result = dict(disc=a.disc, screen=a.screen, battles=0, enemies=[], refused=None, reopens=None, ok=False, why='')

def run(cmd, timeout=600):
    r = subprocess.run(cmd, capture_output=True, text=True, cwd=ROOT, timeout=timeout); return r.stdout + r.stderr
def gs(*args): return run([sys.executable, 'tools/dev/game_state.py', *args])
def lua(code): return emu.api('/api/v1/lua/eval?code=' + urllib.parse.quote(code)).decode()
def lua_file(path): return emu.api('/api/v1/lua/eval?file=' + urllib.parse.quote(os.path.abspath(path))).decode()
def paused():
    try: return not json.loads(emu.api('/api/v1/execution-flow').decode()).get('running', True)
    except Exception: return False
def finish(ok, why=''):
    result['ok'] = ok; result['why'] = why
    try:
        if paused():
            result['registers'] = lua("return TRAP_SNAPSHOT and TRAP_SNAPSHOT('PAUSE') or ''")[:600]
        if os.path.exists(LOG): result['trap_log'] = open(LOG).read()[-1500:]
    except Exception: pass
    print(json.dumps(result), flush=True)
    json.dump(result, open(os.path.join(OUT, 'result.json'), 'w'), indent=1)
    if not a.keep:
        try: run([sys.executable, 'tools/dev/emulator.py', 'stop'])
        except Exception: pass
    sys.exit(0 if ok else 1)

# 1. the emulator, the saved game, the trap
if os.path.exists(LOG): os.remove(LOG)
run([sys.executable, 'tools/dev/emulator.py', 'stop'])
print(run([sys.executable, 'tools/dev/emulator.py', 'start', a.disc, '--card', a.card]).strip(), flush=True)
time.sleep(40)
gamestate.read_ram()
A = gamestate.A
ADDR = {k: A(k) for k in ('GAME_STATE', 'TAMER_STATE', 'IS_IN_MENU', 'NPC_ENTITIES', 'TAMER_POSITION_DATA', 'ENEMY_COUNT',
                          'MOD_TFS_STATS', 'tfsStreamOpen', 'handleBattleStart', 'CURRENT_SCREEN', 'IS_SCRIPT_PAUSED', 'MAP_TILE_X', 'MAP_TILE_Y', 'MAP_TILE_DATA')}
# the title and the card: the fixed sequence (tools/dev/sequences/continue.seq, START, CONTINUE, slot 1, "Continue adventure? Yes"),
# then CROSS every 3 s until the world runs with control (the interpreter boots slower than the sequence's waits)
def in_world(ram):
    scr = struct.unpack('<h', gamestate.ram_read(ram, ADDR['CURRENT_SCREEN'], 2))[0]
    return scr != 0 and gamestate.ram_read(ram, ADDR['TAMER_STATE'], 1)[0] == 0 and gamestate.ram_read(ram, ADDR['GAME_STATE'], 1)[0] == 0 \
        and struct.unpack('<i', gamestate.ram_read(ram, ADDR['IS_SCRIPT_PAUSED'], 4))[0] == 1
run([sys.executable, 'tools/dev/emulator.py', 'seq', 'tools/dev/sequences/continue.seq'])
for i in range(40):
    if in_world(gamestate.read_ram()):
        time.sleep(3); break
    emu.press('CROSS', 10); time.sleep(3.0)
else:
    print('the game did not reach the world from the card', flush=True); run([sys.executable, 'tools/dev/emulator.py', 'stop']); sys.exit(1)
trap = f'''
local ffi = require('ffi')
local OUT = '{LOG}'
local NAMES = {{'r0','at','v0','v1','a0','a1','a2','a3','t0','t1','t2','t3','t4','t5','t6','t7',
               's0','s1','s2','s3','s4','s5','s6','s7','t8','t9','k0','k1','gp','sp','fp','ra'}}
local function hex(v) return string.format('%08x', tonumber(v)) end
local function word(a) return ffi.cast('uint32_t*', PCSX.getMemPtr() + bit.band(tonumber(a), 0x1fffff))[0] end
local function log(s) local f = io.open(OUT, 'a') if f then f:write(s .. '\\n') f:close() end end
function TRAP_SNAPSHOT(tag)
  local r = PCSX.getRegisters(); local regs = {{}}
  for i, n in ipairs(NAMES) do regs[#regs+1] = n .. '=' .. hex(r.GPR.r[i-1]) end
  local sp = tonumber(r.GPR.n.sp); local st = {{}}
  for i = 0, 63 do st[#st+1] = hex(word(sp + i*4)) end
  return tag .. ' pc=' .. hex(r.pc) .. ' ' .. table.concat(regs, ' ') .. ' stack@' .. hex(sp) .. ' ' .. table.concat(st, ' ')
end
_TRAP_FAIL = nil
_BATTLES = 0
_BP_LOW = PCSX.addBreakpoint(0x00000000, 'Exec', 0x80, 'lowmem', function(addr, w, c)
  _TRAP_FAIL = _TRAP_FAIL or ('jump into kernel memory ' .. hex(addr)); log(TRAP_SNAPSHOT('CRASH')); PCSX.pauseEmulator(); return true
end)
_BP_OPEN = PCSX.addBreakpoint({ADDR['tfsStreamOpen']:#x}, 'Exec', 4, 'tfsStreamOpen', function(addr, w, c)
  local gs = word({ADDR['GAME_STATE'] & ~3:#x})
  gs = bit.band(bit.rshift(gs, {8 * (ADDR['GAME_STATE'] & 3)}), 0xff)
  log('tfsStreamOpen gs=' .. gs)
  if gs ~= 0 then _TRAP_FAIL = 'tfsStreamOpen called with GAME_STATE ' .. gs; log(TRAP_SNAPSHOT('REOPEN')); PCSX.pauseEmulator() end
  return true   -- a breakpoint whose invoker returns false is removed after its first hit
end)
_BP_BTL = PCSX.addBreakpoint({ADDR['handleBattleStart']:#x}, 'Exec', 4, 'handleBattleStart', function(addr, w, c)
  _BATTLES = _BATTLES + 1; log('handleBattleStart ' .. _BATTLES); return true
end)
return 'trap installed'
'''
tf = os.path.join(OUT, 'trap.lua'); open(tf, 'w').write(trap)
print(lua_file(tf), flush=True)

# 2. the partner never begs, everyone joins, the screen
def rd(ram, ad, n): return gamestate.ram_read(ram, ad, n)
def u8(ram, ad): return rd(ram, ad, 1)[0]
def i16(ram, ad): return struct.unpack('<h', rd(ram, ad, 2))[0]
def i32(ram, ad): return struct.unpack('<i', rd(ram, ad, 4))[0]
def u32(ram, ad): return struct.unpack('<I', rd(ram, ad, 4))[0]
def entities(ram):
    out = []
    for i in range(8):
        e = ADDR['NPC_ENTITIES'] + i * 0x68
        typ = i32(ram, e); pd = u32(ram, e + 4)
        if typ <= 0 or not (0x80000000 < pd < 0x80800000): continue
        out.append(dict(slot=i, type=typ, onMap=u8(ram, e + 0x34), hp=i16(ram, e + 0x4C), at=(i32(ram, pd + 0x78), i32(ram, pd + 0x80))))
    return out
def camera(ram): return i16(ram, ADDR['MAP_TILE_DATA'] + 0x1bb4), i16(ram, ADDR['MAP_TILE_DATA'] + 0x1bb6)
def tile_window(ram): return struct.unpack('<b', rd(ram, ADDR['MAP_TILE_X'], 1))[0], struct.unpack('<b', rd(ram, ADDR['MAP_TILE_Y'], 1))[0]
def place_at_band_edge(x, z):
    """Moves the tamer to (x, z), then along z until the map camera's Y sits EDGE px below a multiple of 128 (the tile
    bands: handleTileUpdate shifts the rows up when cameraY drops below 128*k + 1): any upward lift of the battle camera
    then meets a band. Before patch 0160 this was the crash; now the window must hold. Best effort: a teleported tamer
    leaves the camera and the window to catch up, so the figure returned (cameraY mod 128) is what the fight starts with."""
    EDGE = 6
    gs('move', str(int(x)), str(int(z))); time.sleep(3.0); c0 = camera(gamestate.read_ram())[1]
    gs('move', str(int(x)), str(int(z + 600))); time.sleep(3.0); c1 = camera(gamestate.read_ram())[1]
    if c1 != c0:
        r = 600.0 / (c1 - c0)                               # world z per camera px (the sign too)
        z = z + 600 + (EDGE - (c1 % 128)) * r               # from where the camera is now to EDGE px below the next band
        gs('move', str(int(x)), str(int(z))); time.sleep(3.0)
    return camera(gamestate.read_ram())[1] % 128
def tamer_pos(ram):
    p = ADDR['TAMER_POSITION_DATA']; return i32(ram, p + 0x78), i32(ram, p + 0x80)
def stats(ram):
    s = ADDR['MOD_TFS_STATS']; names = ['opens', 'prefetches', 'hits', 'waits', 'misses', 'syncVsyncs', 'syncVsyncsMax', 'prefetchVsyncsMax',
                                        'invalidations', 'reopens', 'readErrors', 'rowReads', 'rowVsyncs', 'captures', 'captureWaitMax',
                                        'captureLinesMax', 'startLinesMax', 'refused']
    return {n: i32(ram, s + 4 * i) for i, n in enumerate(names)}

gs('set', 'hour=10', 'partner.stats.currentHP=5100', 'partner.stats.currentMP=3000', 'partner.stats.off=999', 'partner.stats.def=999',
   'partner.stats.speed=999', 'partner.para.foodLevel=30000', 'partner.para.energyLevel=100', 'partner.para.poopLevel=2000',
   'partner.para.tiredness=0', 'partner.para.discipline=100', 'partner.para.happiness=100', 'partner.para.sleepyHour=9',
   'partner.para.wakeupHour=10', 'partner.para.hoursAsleepDefault=1', 'partner.para.nextHungerHour=23',
   'partner.para.tirednessSleepTimer=0', 'gametime_running=0')
time.sleep(0.5)
gs('set', 'partner.para.condition=0', 'partner.para.poopingTimer=-1', 'partner.para.poopLevel=2000')
gs('trigger', '1', '1')
gs('warp', str(a.screen), str(a.exit)); time.sleep(7)
gs('set', 'gametime_running=0', 'hour=10')

# 3. the battles
t0 = time.time(); last_gs = 0; toggle = False; dialogs = 0; idle_since = time.time(); fights = 0
window = None; cam0 = None; cam_range = [0, 0]; result['window_moves'] = 0; result['camera_lift'] = []; result['band_edge_px'] = []
while time.time() - t0 < a.max:
    if paused():
        finish(False, lua('return tostring(_TRAP_FAIL)') if lua('return tostring(_TRAP_FAIL)') != 'nil' else 'first-chance exception (the emulator paused)')
    ram = gamestate.read_ram()
    g = u8(ram, ADDR['GAME_STATE']); st = u8(ram, ADDR['TAMER_STATE']); menu = u8(ram, ADDR['IS_IN_MENU'])
    ents = entities(ram); tp = tamer_pos(ram)
    if g != 0 and last_gs == 0:
        fights += 1; print(f'battle {fights} starts', flush=True); window = None; cam0 = None; cam_range = [0, 0]
    if g != 0:                                      # the tile window must not move in a fight; the camera may (the lift)
        tx, ty = struct.unpack('<b', rd(ram, ADDR['MAP_TILE_X'], 1))[0], struct.unpack('<b', rd(ram, ADDR['MAP_TILE_Y'], 1))[0]
        cx, cy = i16(ram, ADDR['MAP_TILE_DATA'] + 0x1bb4), i16(ram, ADDR['MAP_TILE_DATA'] + 0x1bb6)
        if window is None: window = (tx, ty); cam0 = (cx, cy)
        elif (tx, ty) != window: result['window_moves'] += 1; print(f'  tile window moved {window} -> {(tx, ty)} in battle {fights}', flush=True); window = (tx, ty)
        cam_range = [max(cam_range[0], abs(cx - cam0[0])), max(cam_range[1], abs(cy - cam0[1]))]
    if g == 2 and last_gs == 3:
        n = i32(ram, ADDR['ENEMY_COUNT']); result['enemies'].append(n); print(f'  {n} enemies', flush=True)
    if g == 0 and last_gs != 0:
        result['battles'] = fights; result['camera_lift'].append(cam_range)
        print(f'battle {fights} over, world back; camera moved up to {cam_range} px, window {window}; stream {stats(ram)}', flush=True)
        gs('set', 'gametime_running=0', 'hour=10', 'partner.para.condition=0', 'partner.para.poopingTimer=-1', 'partner.para.poopLevel=2000', 'partner.para.tiredness=0',
           'partner.stats.currentMP=3000', 'partner.stats.currentHP=5100')   # two fights drain the MP and the third never ends (FINISH!! PUSH with MP 24)
        idle_since = time.time()
        if fights >= a.battles: break
    last_gs = g
    if menu and g == 0: emu.press('CIRCLE', 8); time.sleep(0.8); continue
    if g != 0: toggle = not toggle; emu.press('CIRCLE' if toggle else 'CROSS', 6); time.sleep(1.0); continue
    if st in (6, 7, 20): dialogs += 1; emu.press('CIRCLE' if dialogs % 4 == 0 else 'CROSS', 12); time.sleep(0.6); continue
    dialogs = 0
    if st == 0 and time.time() - idle_since > 6:       # idle: next to the nearest wild Digimon that is still up
        live = [e for e in ents if e['onMap'] and e['hp'] > 0]
        if not live: finish(False, f'no wild Digimon left on screen {a.screen} after {fights} battles')
        live.sort(key=lambda e: math.hypot(e['at'][0] - tp[0], e['at'][1] - tp[1]))
        e = live[0]; d = math.hypot(e['at'][0] - tp[0], e['at'][1] - tp[1])
        if d > 400:
            if len(live) > 1 and math.hypot(live[1]['at'][0] - e['at'][0], live[1]['at'][1] - e['at'][1]) < 2200:
                # two of them close enough: stand between them, nearer the first (both on screen when it touches: the join)
                mx, mz = (e['at'][0] * 2 + live[1]['at'][0]) / 3, (e['at'][1] * 2 + live[1]['at'][1]) / 3
            else:
                k = 260 / d; mx, mz = e['at'][0] + (tp[0] - e['at'][0]) * k, e['at'][1] + (tp[1] - e['at'][1]) * k
            edge = place_at_band_edge(mx, mz); result['band_edge_px'].append(edge)
            print(f'  tamer placed, camera {edge} px below a tile band edge', flush=True)
        else: emu.press('UP', 6)
        idle_since = time.time() - 3
    time.sleep(1.0)
else:
    s = stats(gamestate.read_ram()); result['refused'] = s['refused']; result['reopens'] = s['reopens']; result['stream'] = s
    finish(False, f'timeout after {fights} battles')

ram = gamestate.read_ram(); s = stats(ram)
result['refused'] = s['refused']; result['reopens'] = s['reopens']; result['stream'] = s
if paused(): finish(False, 'the emulator paused at the end')
if u8(ram, ADDR['GAME_STATE']) != 0: finish(False, 'GAME_STATE not 0 at the end')
if s['refused'] != 0: finish(False, f'the battle camera asked the stream for {s["refused"]} tiles')
if result['window_moves']: finish(False, f'the tile window moved {result["window_moves"]} times during the fights')
finish(True)
