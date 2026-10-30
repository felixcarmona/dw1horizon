#!/usr/bin/env bash
# world_rules.sh: patch 0122 in the emulator (disc build/full.cue with content/tables/{tournament-rules,daily-rules,daytime}.json).
# (STD_REMAP lives in the STD overlay, loaded only during a tournament: checked in the build output of balance.py, not here.)
# Prints the tables the game holds; calls dailyPStatTrigger (6 different cards 1..64 except 4, the counters up, the registration's tomorrow bit
# cleared) and modTimeOfDay for every hour (0 dusk, 1 night, 2 day); then the tables wiped in RAM: no cards, no counters, always day.
set -u
cd "$(dirname "$0")/../../.."
export EMU_PORT=38117 EMU_ARGS="-interpreter -debugger"
DISC=${DISC:-build/full.cue}
mkdir -p build/savedrop; cp build/ids-saved.mcd build/savedrop/w.mcd
tools/dev/emulator.py start $DISC --card build/savedrop/w.mcd >/dev/null
tools/dev/emulator.py seq tools/dev/sequences/continue.seq >/dev/null; tools/dev/emulator.py wait 30 >/dev/null
tools/dev/emulator.py save build/savedrop/w.state >/dev/null
python3 -u - <<'PY'
import os
import subprocess, struct, sys
sys.path.insert(0, 'tools'); from tools.dev import symbols as dwsyms
T = dwsyms.table(os.environ.get('DW_SYMS', 'disc-full'))
def emu(*a): return subprocess.run([sys.executable, 'tools/dev/emulator.py', *a], capture_output=True, text=True).stdout
def peek(addr, n): return bytes.fromhex(''.join(l.split(None, 1)[1].replace(' ', '') for l in emu('peek', hex(addr), str(n)).strip().split('\n')))
def poke(addr, fmt, *v): emu('poke', hex(addr), struct.pack(fmt, *v).hex())
def call(expr):
    r = subprocess.run([sys.executable, 'tools/dev/playtest/call_function.py', expr], capture_output=True, text=True).stdout.strip()
    return int(r.rsplit('=', 1)[1]) if '=' in r else None
def ok(name, got, want): print(f'{"ok " if got == want else "BAD"} {name:44s} got {got} expected {want}')
def tab(sym, n): return struct.unpack(f'<{n}h', peek(T[sym], 2 * n))
ok('MOD_TOURNAMENT', tab('MOD_TOURNAMENT', 8), (720, 1200, 1381, 1241, 1242, 22, 22, 149))
ok('MOD_DAILY', tab('MOD_DAILY', 7), (6, 64, 4, 28, 4, 2, 127))
ok('MOD_DAYTIME', tab('MOD_DAYTIME', 9), (16, 20, 6, 7, 5, 6, 21, 6, 17))
ok('STD_ARENA_SCREEN', tab('STD_ARENA_SCREEN', 1), (106,))
ok('time of day, hours 0..23', tuple(call(f'modTimeOfDay({h})') for h in range(24)), tuple(1 if h < 6 or h >= 20 else 0 if h >= 16 else 2 for h in range(24)))
SS = T['SCRIPT_STATE']; PS = SS + 345
bad = 0
for n in range(20):
    poke(PS + 28, '4B', 3, 255, 0, 9); poke(PS + 2, 'B', 0x95)
    call('dailyPStatTrigger()')
    stock = list(peek(SS, 6)); p = list(peek(PS + 28, 4)); p2 = peek(PS + 2, 1)[0]
    if sorted(set(stock)) != sorted(stock) or any(not 1 <= c <= 64 or c == 4 for c in stock) or p != [4, 255, 1, 10] or p2 != 0x15: bad += 1
ok('20 rerolls: 6 different cards in 1..64 but 4, counters 3,255,0,9 -> 4,255,1,10, p2 0x95 -> 0x15', bad, 0)
print('wiped tables (what a build without the files holds):')
emu('load', 'build/savedrop/w.state')
for sym, n in (('MOD_DAILY', 7), ('MOD_DAYTIME', 9), ('MOD_TOURNAMENT', 8)): poke(T[sym], f'<{n}h', *([-1] * n))
poke(PS + 28, '4B', 3, 255, 0, 9); poke(PS + 2, 'B', 0x95); call('dailyPStatTrigger()')
ok('  no stock, no counters, p2 untouched', (tuple(peek(SS, 6)), tuple(peek(PS + 28, 4)), peek(PS + 2, 1)[0]), ((255,) * 6, (3, 255, 0, 9), 0x95))
ok('  always day', tuple(call(f'modTimeOfDay({h})') for h in range(24)), (2,) * 24)
PY
tools/dev/emulator.py stop >/dev/null
