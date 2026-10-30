#!/usr/bin/env bash
# clock_rules.sh: patch 0127 in the emulator (disc build/full.cue with content/tables/clock.json). The game clock runs from MOD_CLOCK (real
# seconds a game day lasts). For several day lengths the emulator runs ten seconds and the frames the clock advanced are compared with the
# logic ticks that passed (PLAYTIME_FRAMES counts one per tick): frames = ticks x 1440 / day seconds. The care periods are game time, so the
# food level, which drops once every 20 frames (a game minute), must drop by frames / 20 whatever the day length. Table wiped: time stands still.
set -u
cd "$(dirname "$0")/../../.."
export EMU_PORT=38117 EMU_ARGS="-interpreter -debugger"
DISC=${DISC:-build/full.cue}
mkdir -p build/savedrop; cp build/ids-saved.mcd build/savedrop/k.mcd
tools/dev/emulator.py start $DISC --card build/savedrop/k.mcd >/dev/null
tools/dev/emulator.py seq tools/dev/sequences/continue.seq >/dev/null; tools/dev/emulator.py wait 30 >/dev/null
tools/dev/emulator.py save build/savedrop/k.state >/dev/null
python3 - <<'PY'
import os
import subprocess, struct, sys, time
sys.path.insert(0, 'tools'); from tools.dev import symbols as dwsyms
T = dwsyms.table(os.environ.get('DW_SYMS', 'disc-full'))
def emu(*a): return subprocess.run([sys.executable, 'tools/dev/emulator.py', *a], capture_output=True, text=True).stdout
def poke(addr, fmt, *v): emu('poke', hex(addr), struct.pack(fmt, *v).hex())
def peek(addr, n): return bytes.fromhex(''.join(l.split(None, 1)[1].replace(' ', '') for l in emu('peek', hex(addr), str(n)).strip().split('\n')))
def gs(**kw): subprocess.run([sys.executable, 'tools/dev/game_state.py', 'set', *[f'{k}={v}' for k, v in kw.items()]], capture_output=True)
def get(field): return int(subprocess.run([sys.executable, 'tools/dev/game_state.py', 'show', field], capture_output=True, text=True).stdout.split()[-1], 0)
def ok(name, got, want, tol=0): print(f'{"ok " if abs(got - want) <= tol else "BAD"} {name:62s} got {got} expected {want}' + (f' (+-{tol})' if tol else ''))
def u16(sym): return struct.unpack('<H', peek(T[sym], 2))[0]
def run(day, seconds=10):
    emu('load', 'build/savedrop/k.state'); emu('lua', 'PCSX.pauseEmulator() return 1')
    poke(T['MOD_CLOCK'], '<h', day); poke(T['HAS_IMMORTAL_HOUR'], '<i', 0)
    gs(**{'partner.para.foodLevel': 5000, 'partner.para.condition': 0, 'partner.para.happiness': 80, 'partner.para.tiredness': 0})
    poke(T['CURRENT_FRAME'], '<H', 9600); poke(T['PLAYTIME_FRAMES'], '<H', 0)
    food0 = get('partner.para.foodLevel')
    emu('lua', 'PCSX.resumeEmulator() return 1'); time.sleep(seconds); emu('lua', 'PCSX.pauseEmulator() return 1')
    ticks, frames = u16('PLAYTIME_FRAMES'), (u16('CURRENT_FRAME') - 9600)
    return ticks, frames, food0 - get('partner.para.foodLevel'), get('partner.para.energyLevel')
for day in (1440, 2880, 720, 360, 144):
    ticks, frames, food, _ = run(day)
    want = ticks * 1440 / day
    ok(f'day {day} s: frames the clock advanced ({ticks} ticks)', frames, round(want), max(2, round(want * 0.03)))
    ok(f'day {day} s: food level drops once per game minute', food, frames // 20, 1)
ticks, frames, food, _ = run(-1, 4)
ok('MOD_CLOCK wiped: game time stands still', frames, 0)
ok('MOD_CLOCK wiped: nothing hungers', food, 0)
PY
tools/dev/emulator.py stop >/dev/null
