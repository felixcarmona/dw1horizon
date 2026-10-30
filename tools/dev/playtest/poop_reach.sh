#!/usr/bin/env bash
# poop_reach.sh: patch 0140 in the emulator (disc build/full.cue, care-rules.json poop.eat: species [11, 39], reachNear 200, reachFar 300, farFrom 11).
# tickPoopDetection is called with a poop pile on the current screen, the partner's species poked and the tamer placed at a distance from the pile:
# an eating species goes to eat it (PARTNER_STATE 9, POOP_TO_EAT = the pile) inside the reach and not outside (the reach is the open interval, a
# small pile uses reachNear, a pile of farFrom or more reachFar), another species never does. Then the same with parts of MOD_CARE wiped in RAM:
# no species slots (nothing eats), one species slot (only the other eats), no reach slots (radius 0: nothing is ever inside). About 2 minutes.
#   tools/dev/playtest/poop_reach.sh
set -u
cd "$(dirname "$0")/../../.."
export EMU_PORT=${EMU_PORT:-38201} EMU_ARGS="-interpreter -debugger"
DISC=${DISC:-build/full.cue}
mkdir -p build/savedrop; cp build/ids-saved.mcd build/savedrop/pr.mcd
tools/dev/emulator.py start $DISC --card build/savedrop/pr.mcd >/dev/null
tools/dev/emulator.py seq tools/dev/sequences/continue.seq >/dev/null; tools/dev/emulator.py seq 'until CURRENT_SCREEN 1 218 CROSS 40, wait 5' >/dev/null
tools/dev/emulator.py save build/savedrop/pr.state >/dev/null
python3 -u - <<'PY'
import os, struct, subprocess, sys, time
sys.path.insert(0, 'tools'); from tools.dev import symbols as dwsyms
T = dwsyms.table(os.environ.get('DW_SYMS', 'disc-full'))
def emu(*a): return subprocess.run([sys.executable, 'tools/dev/emulator.py', *a], capture_output=True, text=True).stdout
def poke(addr, fmt, *v): emu('poke', hex(addr), struct.pack(fmt, *v).hex())
def peek(addr, n): return bytes.fromhex(''.join(l.split(None, 1)[1].replace(' ', '') for l in emu('peek', hex(addr), str(n)).strip().split('\n')))
def gs(*a): subprocess.run([sys.executable, 'tools/dev/game_state.py', *a], capture_output=True)
def ok(name, got, want): print(f'{"ok " if got == want else "BAD"} {name:78s} got {got} expected {want}', flush=True)
CARE = T['MOD_CARE']; SLOTS = dict(near=145, far=146, farFrom=147, sp0=148, sp1=149)
TX, TZ = (60 - 50) * 100 + 50, (50 - 40) * 100 - 50        # the tile of the pile at x=60, y=40 in world units
def run(species, size, dx, wipe=()):
    emu('load', 'build/savedrop/pr.state'); emu('lua', 'PCSX.pauseEmulator() return 1')
    for s in wipe:
        if s == 'all':
            for i in range(150): poke(CARE + 2 * i, '<h', -1)
        else: poke(CARE + 2 * SLOTS[s], '<h', -1)
    screen = peek(T['CURRENT_SCREEN'], 1)[0]
    poke(T['WORLD_POOP'], '400B', *([255] * 400)); poke(T['WORLD_POOP'], '4B', screen, 60, 40, size)
    poke(T['PARTNER_ENTITY'], '<I', species); poke(T['PARTNER_STATE'], '2B', 0, 0); poke(T['POOP_TO_EAT'], 'B', 99)
    gs('move', str(TX + dx), str(TZ))
    p = subprocess.Popen([sys.executable, 'tools/dev/playtest/call_function.py', 'tickPoopDetection()'], env=dict(os.environ, CALLFN_PAUSE='1'), stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    time.sleep(2.0); emu('lua', 'PCSX.resumeEmulator() return 1'); p.communicate()
    return peek(T['PARTNER_STATE'], 1)[0] == 9 and peek(T['POOP_TO_EAT'], 1)[0] == 0
def check(name, species, size, dx, want, wipe=()):
    ok(name + (f' (wiped: {",".join(wipe)})' if wipe else ''), run(species, size, dx, wipe), want)
# 11 and 39 as built; small pile (size 5 < farFrom 11): reachNear 200; big pile (12 >= 11): reachFar 300
for sp in (11, 39):
    check(f'species {sp}, small pile, 199 away: eats', sp, 5, 199, True)
    check(f'species {sp}, small pile, 200 away: does not (open interval)', sp, 5, 200, False)
    check(f'species {sp}, small pile, 250 away: does not', sp, 5, 250, False)
    check(f'species {sp}, big pile, 299 away: eats', sp, 12, 299, True)
    check(f'species {sp}, big pile, 300 away: does not', sp, 12, 300, False)
    check(f'species {sp}, pile of exactly farFrom (11), 250 away: far reach, eats', sp, 11, 250, True)
check('species 11, small pile on the spot (0 away): eats', 11, 5, 0, True)
check('species 11, small pile 150 away on the other side: eats', 11, 5, -150, True)
check('species 3 (Agumon), on the spot: never', 3, 5, 0, False)
check('species 12, big pile on the spot: never', 12, 12, 0, False)
check('species 114 (Jijimon), on the spot: never', 114, 12, 0, False)
# wiped
check('whole table wiped, species 11 on the spot: nothing', 11, 5, 0, False, ('all',))
check('whole table wiped, species 39 on the spot: nothing', 39, 12, 0, False, ('all',))
check('both species slots wiped, species 11 on the spot: nothing', 11, 5, 0, False, ('sp0', 'sp1'))
check('both species slots wiped, species 39 on the spot: nothing', 39, 5, 0, False, ('sp0', 'sp1'))
check('species 0 slot wiped: species 11 does not eat', 11, 5, 0, False, ('sp0',))
check('species 0 slot wiped: species 39 still eats', 39, 5, 0, True, ('sp0',))
check('species 1 slot wiped: species 39 does not eat', 39, 5, 0, False, ('sp1',))
check('species 1 slot wiped: species 11 still eats', 11, 5, 0, True, ('sp1',))
check('reachNear wiped (radius 0): small pile on the spot is never inside', 11, 5, 0, False, ('near',))
check('reachFar wiped (radius 0): big pile on the spot is never inside', 11, 12, 0, False, ('far',))
check('reachFar wiped: a small pile still uses reachNear', 11, 5, 150, True, ('far',))
check('farFrom wiped (0): every pile is "far" = reachFar 300, 250 away eats', 11, 5, 250, True, ('farFrom',))
PY
tools/dev/emulator.py stop >/dev/null
