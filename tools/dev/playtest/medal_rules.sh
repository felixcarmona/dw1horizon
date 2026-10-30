#!/usr/bin/env bash
# medal_rules.sh: patch 0120 in the emulator (disc build/full.cue with content/tables/medals.json). Script routine (checkTournamentMedalConditions
# returns the row of MOD_MEDALS, -1 for none) and tick check (checkMedalConditions awards and sets MEDAL_AWARD_PENDING) with each condition
# true and false; then with the rows wiped in RAM (what a build without the file holds): nothing is awarded.
set -u
cd "$(dirname "$0")/../../.."
export EMU_PORT=38114 EMU_ARGS="-interpreter -debugger"
DISC=${DISC:-build/full.cue}
mkdir -p build/savedrop; cp build/ids-saved.mcd build/savedrop/m.mcd
tools/dev/emulator.py start $DISC --card build/savedrop/m.mcd >/dev/null
tools/dev/emulator.py seq tools/dev/sequences/continue.seq >/dev/null; tools/dev/emulator.py wait 30 >/dev/null
tools/dev/emulator.py save build/savedrop/m.state >/dev/null
python3 -u - <<'PY'
import os
import re, subprocess, struct, sys
sys.path.insert(0, 'tools'); from tools.dev import symbols as dwsyms
T = dwsyms.table(os.environ.get('DW_SYMS', 'disc-full'))
def emu(*a): return subprocess.run([sys.executable, 'tools/dev/emulator.py', *a], capture_output=True, text=True).stdout
def poke(addr, fmt, *v): emu('poke', hex(addr), struct.pack(fmt, *v).hex())
def gs(*a): subprocess.run([sys.executable, 'tools/dev/game_state.py', *a], capture_output=True)
def call(expr):
    r = subprocess.run([sys.executable, 'tools/dev/playtest/call_function.py', expr], capture_output=True, text=True).stdout.strip()
    v = int(r.rsplit('=', 1)[1]) if '=' in r else None
    return v - 0x100000000 if v is not None and v > 0x7FFFFFFF else v
def peek(sym, n=4): return bytes.fromhex(''.join(l.split(None, 1)[1].replace(' ', '') for l in emu('peek', sym, str(n)).strip().split('\n')))
TRIG = T['SCRIPT_STATE'] + 245                                          # 800 trigger bits, bit n % 8 of byte n / 8
def trig(n, v=None):
    b = bytearray(peek_raw(TRIG, 100))
    if v is None: return bool(b[n // 8] >> (n % 8) & 1)
    b[n // 8] = (b[n // 8] | 1 << (n % 8)) if v else (b[n // 8] & ~(1 << (n % 8)) & 0xFF)
    emu('poke', hex(TRIG), bytes(b).hex())
def peek_raw(addr, n): return bytes.fromhex(''.join(l.split(None, 1)[1].replace(' ', '') for l in emu('peek', hex(addr), str(n)).strip().split('\n')))
def fresh():
    emu('load', 'build/savedrop/m.state')
    b = bytearray(peek_raw(TRIG, 100))
    for n in list(range(15, 51)) + list(range(364, 383)): b[n // 8] &= ~(1 << (n % 8)) & 0xFF
    emu('poke', hex(TRIG), bytes(b).hex())
def ok(name, got, want): print(f'{"ok " if got == want else "BAD"} {name:50s} got {got} expected {want}')
# script routine: rows 0-4 are medals 0-4
fresh(); ok('nothing set', call('checkTournamentMedalConditions()'), -1)
for first, count, row, name in ((15, 6, 0, 'D..R cups'), (21, 5, 1, 'version cups'), (26, 7, 2, 'attribute cups'), (33, 4, 3, 'type cups')):
    fresh()
    for t in range(first, first + count - 1): trig(t, 1)
    ok(f'{name}: one missing', call('checkTournamentMedalConditions()'), -1)
    trig(first + count - 1, 1); ok(f'{name}: all set', call('checkTournamentMedalConditions()'), row)
    trig(364 + row, 1); ok(f'{name}: medal {row} owned already', call('checkTournamentMedalConditions()'), -1)
fresh(); poke(T['TOURNAMENT_WINS'], '<h', 99); ok('99 wins', call('checkTournamentMedalConditions()'), -1)
poke(T['TOURNAMENT_WINS'], '<h', 100); ok('100 wins', call('checkTournamentMedalConditions()'), 4)
# tick: awards and sets the pending flag
def tick(name, medal, setup, want=True):
    fresh(); poke(T['MEDAL_AWARD_PENDING'], '<i', 0); setup(); call('checkMedalConditions()')
    pend = struct.unpack('<i', peek('MEDAL_AWARD_PENDING'))[0]
    got = trig(364 + medal)
    ok(name, (pend, got), (1, True) if want else (0, False))
tick('year 10 -> medal 14', 14, lambda: poke(T['YEAR'], 'B', 10))
tick('year 9 -> nothing', 14, lambda: poke(T['YEAR'], 'B', 9), False)
tick('999999 bits -> medal 13', 13, lambda: poke(T['MONEY'], '<i', 999999))
tick('999998 bits -> nothing', 13, lambda: poke(T['MONEY'], '<i', 999998), False)
tick('100 fish -> medal 9', 9, lambda: gs('set', 'partner.para.fishCaught=100'))
tick('99 fish -> nothing', 9, lambda: gs('set', 'partner.para.fishCaught=99'), False)
print('wiped rows (what a build without the file holds):')
fresh()
for i in range(16): poke(T['MOD_MEDALS'] + 16 * i, '<h', -1)
poke(T['TOURNAMENT_WINS'], '<h', 100); poke(T['YEAR'], 'B', 10); poke(T['MEDAL_AWARD_PENDING'], '<i', 0)
print('  100 wins, script routine ->', call('checkTournamentMedalConditions()'), '(expected -1)')
call('checkMedalConditions()'); print('  year 10, tick -> pending', struct.unpack('<i', peek('MEDAL_AWARD_PENDING'))[0], '(expected 0)')
PY
tools/dev/emulator.py stop >/dev/null
