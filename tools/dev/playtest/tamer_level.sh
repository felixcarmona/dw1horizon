#!/usr/bin/env bash
# tamer_level.sh: patch 0121 in the emulator (disc build/full.cue with content/tables/tamer-level.json). Every event's chance poked to 100:
# modTamerLevelEvent changes the tamer level by the event's sign; then the rebirth inheritance (setReincarnateStats, first four stats:
# 5 % per level of 1000 old HP and 400 old Offense on top of 100); then the table wiped in RAM (a build without the file): nothing
# changes and nothing is inherited.
set -u
cd "$(dirname "$0")/../../.."
export EMU_PORT=38115 EMU_ARGS="-interpreter -debugger"
DISC=${DISC:-build/full.cue}
mkdir -p build/savedrop; cp build/ids-saved.mcd build/savedrop/t.mcd
tools/dev/emulator.py start $DISC --card build/savedrop/t.mcd >/dev/null
tools/dev/emulator.py seq tools/dev/sequences/continue.seq >/dev/null; tools/dev/emulator.py wait 30 >/dev/null
tools/dev/emulator.py save build/savedrop/t.state >/dev/null
python3 -u - <<'PY'
import os
import subprocess, struct, sys
sys.path.insert(0, 'tools'); from tools.dev import symbols as dwsyms
T = dwsyms.table(os.environ.get('DW_SYMS', 'disc-full'))
def emu(*a): return subprocess.run([sys.executable, 'tools/dev/emulator.py', *a], capture_output=True, text=True).stdout
def poke(addr, fmt, *v): emu('poke', hex(addr), struct.pack(fmt, *v).hex())
def peek(addr, n): return bytes.fromhex(''.join(l.split(None, 1)[1].replace(' ', '') for l in emu('peek', hex(addr), str(n)).strip().split('\n')))
def call(expr): subprocess.run([sys.executable, 'tools/dev/playtest/call_function.py', expr], capture_output=True, text=True)
def ok(name, got, want): print(f'{"ok " if got == want else "BAD"} {name:46s} got {got} expected {want}')
TL, LEVEL = T['MOD_TAMER_LEVEL'], T['TAMER_ENTITY'] + 0x38                   # TamerEntity.tamerLevel follows the 0x38-byte Entity
def fresh(chance=100):
    emu('load', 'build/savedrop/t.state')
    for i in range(10): poke(TL + 2 * i, '<h', chance)
    poke(LEVEL, 'b', 5)
def level(): return struct.unpack('b', peek(LEVEL, 1))[0]
events = ((0, 1, 'a happy year'), (2, -1, 'a bad year'), (4, -1, 'eating poop'), (5, -1, 'sleeping late'), (6, -1, 'a chip item'),
          (7, 1, 'evolving to a Champion'), (8, 1, 'evolving to an Ultimate'), (9, 1, 'evolving to a Mega'))
for slot, sign, name in events:
    fresh(); call(f'modTamerLevelEvent({slot},{sign})'); ok(f'{name} (chance 100)', level(), 5 + sign)
    fresh(0); call(f'modTamerLevelEvent({slot},{sign})'); ok(f'{name} (chance 0)', level(), 5)
    fresh(-1); call(f'modTamerLevelEvent({slot},{sign})'); ok(f'{name} (slot -1: does not exist)', level(), 5)
# rebirth: 5 % per level of the old stats
for natural, want_hp, want_off in ((1, 150, 120), (0, 100, 100)):
    emu('load', 'build/savedrop/t.state'); poke(LEVEL, 'b', 5)
    ds = T['DEATH_STATS']                                                      # Stats: off def speed brain (2 bytes each), prios, moves, hp, mp
    poke(ds, '<4h', 400, 0, 0, 0); poke(ds + 16, '<2h', 1000, 0); poke(T['IS_NATURAL_DEATH'], '<i', natural)
    call('setReincarnateStats(100,100,100,100)')
    b = T['PARTNER_ENTITY'] + 0x38
    off, = struct.unpack('<h', peek(b, 2)); hp, = struct.unpack('<h', peek(b + 16, 2))
    ok(f'rebirth, natural death = {natural}: hp / offense', (hp, off), (want_hp, want_off))
emu('load', 'build/savedrop/t.state'); poke(LEVEL, 'b', 5)
for i in range(13): poke(TL + 2 * i, '<h', -1)
poke(T['DEATH_STATS'], '<4h', 400, 0, 0, 0); poke(T['DEATH_STATS'] + 16, '<2h', 1000, 0); poke(T['IS_NATURAL_DEATH'], '<i', 1)
call('setReincarnateStats(100,100,100,100)'); b = T['PARTNER_ENTITY'] + 0x38
ok('wiped table: natural death inherits nothing', struct.unpack('<h', peek(b + 16, 2))[0], 100)
PY
tools/dev/emulator.py stop >/dev/null
