#!/usr/bin/env bash
# gym_session.sh: patch 0141 in the emulator (disc build/full.cue with content/tables/training-gains.json). The HP gym of both gym sets (TRN: screen 112,
# TRN2: screen 99) is started with its setup function and a vblank listener in the emulator watches the gym's own state machine: the last value of the
# session timer while the work goes on (state 2) is session ticks - 1. With the table as built: 1199 (60 s of 20 ticks a second, the original); with the
# session poked to 100 ticks: 99; with the table wiped (no session: it ends at the first tick): 0. About 6 minutes.
set -u
cd "$(dirname "$0")/../../.."
export EMU_PORT=${EMU_PORT:-38141} EMU_ARGS="-interpreter -debugger"
DISC=${DISC:-build/full.cue}
mkdir -p build/savedrop; cp build/ids-saved.mcd build/savedrop/gy.mcd
tools/dev/emulator.py start $DISC --card build/savedrop/gy.mcd >/dev/null
tools/dev/emulator.py seq tools/dev/sequences/continue.seq >/dev/null; tools/dev/emulator.py wait 30 >/dev/null
tools/dev/emulator.py save build/savedrop/gy.state >/dev/null
python3 -u - <<'PY'
import os, struct, subprocess, sys, time
sys.path.insert(0, 'tools'); from tools.dev import symbols as dwsyms
T = dwsyms.table(os.environ.get('DW_SYMS', 'disc-full'))
def emu(*a): return subprocess.run([sys.executable, 'tools/dev/emulator.py', *a], capture_output=True, text=True).stdout
def poke(addr, fmt, *v): emu('poke', hex(addr), struct.pack(fmt, *v).hex())
def callfn(*exprs):
    p = subprocess.Popen([sys.executable, 'tools/dev/playtest/call_function.py', *exprs], env=dict(os.environ), stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    return p.communicate(timeout=300)[0]
def ok(name, got, want): print(f'{"ok " if got == want else "BAD"} {name:70s} got {got} expected {want}', flush=True)
def last_timer(screen, setup, timer, state, rules, session, wiped):
    emu('load', 'build/savedrop/gy.state'); emu('lua', 'PCSX.pauseEmulator() return 1')
    subprocess.run([sys.executable, 'tools/dev/game_state.py', 'warp', str(screen), '0'], capture_output=True)
    emu('lua', 'PCSX.resumeEmulator() return 1'); time.sleep(8)
    callfn(f'loadTrainingLibrary({screen})'); emu('wait', '10')
    emu('lua', 'PCSX.pauseEmulator() return 1')
    if wiped: poke(T[rules], '<34h', *[-1] * 34)
    elif session: poke(T[rules] + 2 * 32, '<h', session)
    emu('lua', f"""GS = {{ last2 = -1, done = -1 }}
if GS_L then GS_L:remove() end
GS_L = PCSX.Events.createEventListener('GPU::Vsync', function()
  local m = PCSX.getMemPtr(); local st = m[{state & 0x1fffff}]; local t = m[{timer & 0x1fffff}] + 256 * m[{(timer & 0x1fffff) + 1}]
  if st == 2 then GS.last2 = t elseif st == 3 and GS.done < 0 then GS.done = GS.last2 end
end) return 1""")
    emu('lua', 'PCSX.resumeEmulator() return 1')
    callfn(f'{setup}({screen})')
    for _ in range(300):
        time.sleep(1)
        v = emu('lua', 'return GS.done').strip()
        if v.lstrip('-').isdigit() and int(v) >= 0: return int(v)
    return None
for name, args in (('TRN HP gym (screen 112)', (112, 'TRN_setupHpTraining', T['MAIN_D_8013537A'], T['TRAINING_STATE'], 'MOD_TRAIN_RULES')),
                   ('TRN2 HP gym (screen 99)', (99, 'TRN2_setupHpTraining', T['MAIN_D_801353C2'], T['MAIN_D_801353BD'], 'MOD_TRAIN2_RULES'))):
    ok(f'{name}: as built, 60 s = 1200 ticks', last_timer(*args, 0, False), 1199)
    ok(f'{name}: session poked to 100 ticks', last_timer(*args, 100, False), 99)
    ok(f'{name}: table wiped, the session ends at once', last_timer(*args, 0, True) in (0, 1), True)
PY
tools/dev/emulator.py stop >/dev/null
