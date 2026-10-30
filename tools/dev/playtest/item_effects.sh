#!/usr/bin/env bash
# item_effects.sh record|compare [TAG]: patch 0132 in the emulator (disc build/full.cue). Every food, chip, restore and Double Floppy item is used on a
# hand-made partner (handleFood, handleChips, handleRestore, handleDoubleFloppy) and the partner's care values and base stats are read back. `record`
# writes them to build/savedrop/item-effects-TAG.json (run it on a build from before the change); `compare` reads that file and prints the items that
# differ. The sickness roll and the medicines are random and are not part of it. With the effect table wiped in RAM (what a build without the item
# files holds) no item changes anything.
set -u
cd "$(dirname "$0")/../../.."
MODE=${1:-compare}; TAG=${2:-before}
export EMU_PORT=38121 EMU_ARGS="-interpreter -debugger"
DISC=${DISC:-build/full.cue}
mkdir -p build/savedrop; cp build/ids-saved.mcd build/savedrop/x.mcd
tools/dev/emulator.py start $DISC --card build/savedrop/x.mcd >/dev/null
tools/dev/emulator.py seq tools/dev/sequences/continue.seq >/dev/null; tools/dev/emulator.py wait 30 >/dev/null
tools/dev/emulator.py save build/savedrop/x.state >/dev/null
MODE=$MODE TAG=$TAG python3 -u - <<'PY'
import json, os, subprocess, sys, time
sys.path.insert(0, 'tools'); from tools.dev import symbols as dwsyms
T = dwsyms.table(os.environ.get('DW_SYMS', 'disc-full'))
def emu(*a): return subprocess.run([sys.executable, 'tools/dev/emulator.py', *a], capture_output=True, text=True).stdout
def gs(**kw): subprocess.run([sys.executable, 'tools/dev/game_state.py', 'set', *[f'{k}={v}' for k, v in kw.items()]], capture_output=True)
def show(*f):
    out = subprocess.run([sys.executable, 'tools/dev/game_state.py', 'show', *f], capture_output=True, text=True).stdout.split('\n')
    return {l.split()[0]: int(l.split()[-1], 0) for l in out if l.startswith('partner.')}
FIELDS = ['partner.para.energyLevel', 'partner.para.happiness', 'partner.para.weight', 'partner.para.tiredness', 'partner.para.discipline',
          'partner.para.remainingLifetime', 'partner.para.poopLevel', 'partner.para.trainBoostFlag', 'partner.para.trainBoostValue', 'partner.stats.hp',
          'partner.stats.mp', 'partner.stats.off', 'partner.stats.def', 'partner.stats.speed', 'partner.stats.brain', 'partner.stats.currentHP', 'partner.stats.currentMP']
BASE = {'partner.para.energyLevel': 10, 'partner.para.happiness': 20, 'partner.para.weight': 30, 'partner.para.tiredness': 60, 'partner.para.discipline': 40,
        'partner.para.remainingLifetime': 500, 'partner.para.poopLevel': 50, 'partner.stats.hp': 1000, 'partner.stats.mp': 900, 'partner.stats.off': 100,
        'partner.stats.def': 110, 'partner.stats.speed': 120, 'partner.stats.brain': 130, 'partner.stats.currentHP': 400, 'partner.stats.currentMP': 300}
ITEMS = [('handleFood', i) for i in list(range(0x26, 0x47)) + [0x79, 0x7a]] + [('handleChips', i) for i in range(0x17, 0x20)] + \
        [('handleRestore', 0xb), ('handleRestore', 0xc), ('handleDoubleFloppy', 9)]
def run(fn, item, wiped):
    emu('load', 'build/savedrop/x.state'); emu('lua', 'PCSX.pauseEmulator() return 1')
    if wiped:
        a = T['MOD_ITEM_FX']
        for i in range(64 * 21): emu('poke', hex(a + 2 * i), 'ffff')
    gs(**BASE)
    p = subprocess.Popen([sys.executable, 'tools/dev/playtest/call_function.py', f'{fn}({item})'], env=dict(os.environ, CALLFN_PAUSE='1'), stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    time.sleep(1.5); emu('lua', 'PCSX.resumeEmulator() return 1'); p.communicate(timeout=120)
    r = show(*FIELDS)
    return {k.split('.', 2)[2]: r[k] for k in FIELDS if k in r}
mode, tag = os.environ['MODE'], os.environ['TAG']
path = f'build/savedrop/item-effects-{tag}.json'
res = {f'{fn}({item:#x})': run(fn, item, 0) for fn, item in ITEMS}
if mode == 'record':
    json.dump(res, open(path, 'w'), indent=1); print(f'recorded {len(res)} items in {path}')
else:
    old = json.load(open(path)); bad = [k for k in res if res[k] != old.get(k)]
    print(f'{"ok " if not bad else "BAD"} every item does what it did before the change: {len(res) - len(bad)} of {len(res)}')
    for k in bad[:6]: print('   ', k, {f: (old[k].get(f), v) for f, v in res[k].items() if old[k].get(f) != v})
    w = {f'{fn}({item:#x})': run(fn, item, 1) for fn, item in ITEMS[::4]}
    KEYS = ('energyLevel', 'happiness', 'weight', 'tiredness', 'discipline', 'remainingLifetime', 'hp', 'mp', 'off', 'def', 'speed', 'brain', 'currentHP', 'currentMP')
    base = {k.split('.', 2)[2]: v for k, v in BASE.items()}
    same = [k for k, v in w.items() if all(v[f] == base[f] for f in KEYS)]
    print(f'{"ok " if len(same) == len(w) else "BAD"} table wiped: one item in four changes nothing at all: {len(same)} of {len(w)}')
PY
tools/dev/emulator.py stop >/dev/null
