#!/usr/bin/env bash
# expanded_story_rules.sh: the expanded-story executable (mods/patches) in the emulator. The disc has to carry the data tables:
# build/expanded-story.cue from `tools/build-full.sh expanded-story`, or by hand (the balance step: python3 tools/balance.py build --exe-dir build/decomp-expanded-story/build/us/psx/gcc
# -o build/expanded-story/exe-X, then tools/build-disc.py as build-full's step 6 does, here build/expanded-story-tables.cue); a disc without those tables has no rules
# and every rule is absent (a new game cannot even start). A real new game from the title screen (tools/dev/sequences/new-game.seq, as new_game_start.sh) must end
# in File City (screen 204) with Agumon (MOD_NEWGAME starters), then care and clock rules run on the expanded-story build with the table and wiped. About 12 minutes.
#   DISC=build/expanded-story-tables.cue tools/dev/playtest/expanded_story_rules.sh
set -u
cd "$(dirname "$0")/../../.."
export EMU_PORT=${EMU_PORT:-38203} EMU_ARGS="-interpreter -debugger"
DISC=${DISC:-build/expanded-story.cue}
mkdir -p build/savedrop
grep -v '^#' tools/dev/sequences/new-game.seq | grep -v '^save ' > build/savedrop/expanded-story-ng.seq
tools/dev/emulator.py start $DISC >/dev/null
tools/dev/emulator.py seq build/savedrop/expanded-story-ng.seq >/dev/null
tools/dev/emulator.py wait 3 >/dev/null
tools/dev/emulator.py save build/savedrop/expanded-story.state >/dev/null
python3 -u - <<'PY'
import os, struct, subprocess, sys, time
sys.path.insert(0, 'tools'); from tools.dev import symbols as dwsyms
T = dwsyms.table('decomp-expanded-story')
def emu(*a): return subprocess.run([sys.executable, 'tools/dev/emulator.py', *a], capture_output=True, text=True).stdout
def poke(addr, fmt, *v): emu('poke', hex(addr), struct.pack(fmt, *v).hex())
def gs(**kw): subprocess.run([sys.executable, 'tools/dev/game_state.py', 'set', *[f'{k}={v}' for k, v in kw.items()]], capture_output=True)
def get(field):
    out = subprocess.run([sys.executable, 'tools/dev/game_state.py', 'show', field], capture_output=True, text=True).stdout.strip()
    return int(out.split()[-1], 0)
def call(expr):
    p = subprocess.Popen([sys.executable, 'tools/dev/playtest/call_function.py', expr], env=dict(os.environ, DW_BUILD='decomp-expanded-story', CALLFN_PAUSE='1'), stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    time.sleep(2.0); emu('lua', 'PCSX.resumeEmulator() return 1'); p.communicate()
def ok(name, got, want): print(f'{"ok " if got == want else "BAD"} {name:62s} got {got} expected {want}', flush=True)
ok('new game ends in File City (screen 204)', get('current_screen'), 204)
ok('the partner is the first starter, Agumon (3)', get('partner.type'), 3)
ok('the game clock runs (a new game starts at 8:00)', get('hour') >= 8, True)
CARE = T['MOD_CARE']; F = 3600
def fresh(wiped, **fields):
    emu('load', 'build/savedrop/expanded-story.state'); emu('lua', 'PCSX.pauseEmulator() return 1')
    if wiped:
        for i in range(150): poke(CARE + 2 * i, '<h', -1)
    poke(T['HAS_IMMORTAL_HOUR'], '<i', 0)
    poke(T['CURRENT_FRAME'], '<H', F); poke(T['LAST_HANDLED_FRAME'], '<H', F - 1)
    base = {'partner.para.condition': 0, 'partner.para.happiness': 50, 'partner.para.discipline': 50, 'partner.para.tiredness': 10}
    base.update({f'partner.para.{k}': v for k, v in fields.items()}); gs(**base)
def case(name, fn, fields, reads, want, wiped_want):
    for wiped, w in ((0, want), (1, wiped_want)):
        fresh(wiped, **fields); call(fn)
        ok(f'{name}{" (table wiped)" if wiped else ""}', tuple(get(f'partner.para.{r}') for r in reads), w)
case('food level drops, a tired partner hungrier', 'tickHungerMechanics()', dict(foodLevel=50, tirednessHungerTimer=50, energyLevel=900), ('foodLevel',), (46,), (50,))
case('poop level drops', 'tickPoopingMechanic()', dict(poopLevel=5), ('poopLevel',), (4,), (5,))
case('sickness starts', 'tickSicknessMechanics()', dict(sicknessCounter=10, sicknessTries=30, tiredness=100), ('condition', 'happiness', 'timesBeingSick'), (0x40, 20, 1), (0, 50, 0))
case('the clamps (too high)', 'tickConditionBoundaries()', dict(happiness=500, discipline=500, tiredness=500, weight=500), ('happiness', 'discipline', 'tiredness', 'weight'), (100, 100, 100, 99), (500, 500, 500, 500))
PY
tools/dev/emulator.py stop >/dev/null
