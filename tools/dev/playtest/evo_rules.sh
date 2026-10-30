#!/usr/bin/env bash
# evo_rules.sh: patch 0118 in the emulator (disc build/full.cue with content/tables/evolution-rules.json). Calls handleSpecialEvolutions
# (wake = mode 2, praise = mode 3) with a hand-made entity and partner state, every rule's chance poked to 100 so the roll cannot
# fail, and prints got/expected for the rules of the file, the Fresh pairs and the evolution items. Then the same with the
# rules wiped in RAM (what a build without the file holds): everything must answer -1.
set -u
cd "$(dirname "$0")/../../.."
export EMU_PORT=38113 EMU_ARGS="-interpreter -debugger"
DISC=${DISC:-build/full.cue}
mkdir -p build/savedrop; cp build/ids-saved.mcd build/savedrop/r.mcd
tools/dev/emulator.py start $DISC --card build/savedrop/r.mcd >/dev/null
tools/dev/emulator.py seq tools/dev/sequences/continue.seq >/dev/null; tools/dev/emulator.py wait 30 >/dev/null
tools/dev/emulator.py save build/savedrop/r.state >/dev/null
python3 - <<'PY'
import os
import subprocess, struct, sys
sys.path.insert(0, 'tools'); from tools.dev import symbols as dwsyms
T = dwsyms.table(os.environ.get('DW_SYMS', 'disc-full'))
def emu(*a): return subprocess.run([sys.executable, 'tools/dev/emulator.py', *a], capture_output=True, text=True).stdout
def poke(addr, fmt, *v): emu('poke', hex(addr), struct.pack(fmt, *v).hex())
def gs(**kw): subprocess.run([sys.executable, 'tools/dev/game_state.py', 'set', *[f'{k}={v}' for k, v in kw.items()]], capture_output=True)
def call(expr):
    r = subprocess.run([sys.executable, 'tools/dev/playtest/call_function.py', expr], capture_output=True, text=True).stdout.strip()
    v = int(r.rsplit('=', 1)[1]) if '=' in r else None
    return v - 0x100000000 if v is not None and v > 0x7FFFFFFF else v
FAKE = 0x801E1000
R = T['MOD_EVO_RULES']
def fresh():
    emu('load', 'build/savedrop/r.state')
    for i in range(10): poke(R + 30 * i + 11, 'b', 100)                 # every rule's chance: the roll cannot fail
def special(mode, typ, scold=0, screen=0, **fields):
    fresh()
    base = dict(**{'partner.para.discipline': 0, 'partner.para.happiness': 0, 'partner.para.tiredness': 5, 'partner.para.battles': 0,
                   'partner.para.evoTimer': 0, 'partner.stats.def': 0}); base.update({f'partner.{k}': v for k, v in fields.items()})
    gs(**base); poke(T['NANIMON_TRIGGER'], '<i', scold); poke(T['CURRENT_SCREEN'], '<h', screen); poke(FAKE, '<i', typ)
    got = call(f'handleSpecialEvolutions({mode},{FAKE})')
    return got, int.from_bytes(bytes.fromhex(''.join(emu('peek', 'NANIMON_TRIGGER', '4').split('\n')[0].split()[1:5])), 'little')
cases = [
 ('Birdramon, all 100/100/0', 2, 21, dict(**{'para.discipline': 100, 'para.happiness': 100, 'para.tiredness': 0}), 0, 0, 7),
 ('Seadramon, all 100/100/0', 2, 10, {'para.discipline': 100, 'para.happiness': 100, 'para.tiredness': 0}, 0, 0, 7),
 ('Birdramon, happiness 99', 2, 21, {'para.discipline': 100, 'para.happiness': 99, 'para.tiredness': 0}, 0, 0, -1),
 ('Agumon, all 100/100/0', 2, 3, {'para.discipline': 100, 'para.happiness': 100, 'para.tiredness': 0}, 0, 0, -1),
 ('Vegiemon, 50 battles, discipline 100', 2, 25, {'para.battles': 50, 'para.discipline': 100}, 0, 0, 58),
 ('Vegiemon, 49 battles', 2, 25, {'para.battles': 49, 'para.discipline': 100}, 0, 0, -1),
 ('Bakemon, def 500, discipline 100', 2, 38, {'stats.def': 500, 'para.discipline': 100}, 0, 0, 47),
 ('Bakemon, def 499', 2, 38, {'stats.def': 499, 'para.discipline': 100}, 0, 0, -1),
 ('Koromon on screen 1', 2, 2, {}, 0, 1, 32), ('Tanemon on screen 1', 2, 44, {}, 0, 1, 32), ('Koromon on screen 2', 2, 2, {}, 0, 2, -1),
 ('Whamon, evoTimer 200', 3, 24, {'para.evoTimer': 200}, 0, 0, 49), ('Shellmon, evoTimer 200', 3, 35, {'para.evoTimer': 200}, 0, 0, 49),
 ('Whamon, evoTimer 201', 3, 24, {'para.evoTimer': 201}, 0, 0, -1),
 ('scold flag set', 3, 3, {}, 1, 0, 53), ('no scold flag', 3, 3, {}, 0, 0, -1),
 ('Whamon, evoTimer 240', 3, 24, {'para.evoTimer': 240}, 0, 0, 28), ('Rookie Agumon, evoTimer 240', 3, 3, {'para.evoTimer': 240}, 0, 0, -1),
]
for name, mode, typ, f, scold, screen, want in cases:
    got, flag = special(mode, typ, scold, screen, **f)
    print(f'{"ok " if got == want else "BAD"} {name:42s} got {got} expected {want}' + (f'  (scold flag now {flag})' if scold else ''))
fresh()
for f, want in ((1, 2), (15, 16), (29, 30), (43, 44), (3, -1)):
    got = call(f'getFreshEvolutionTarget({f})'); print(f'{"ok " if got == want else "BAD"} Fresh {f:2d} -> got {got} expected {want}')
def target(): return int.from_bytes(bytes.fromhex(emu('peek', 'EVOLUTION_TARGET', '2').split()[1] + emu('peek', 'EVOLUTION_TARGET', '2').split()[2]), 'little', signed=True)
for item, want in ((0x7D, 64), (0x7E, 63), (0x7F, 65)):
    fresh(); poke(T['EVOLUTION_TARGET'], '<h', -1); call(f'handleEvoItems({item})')
    print(f'{"ok " if target() == want else "BAD"} item {item:#x} (handleEvoItems) -> target {target()} expected {want}')
print('wiped rules (what a build without the file holds):')
fresh(); poke(T['MOD_EVO_RULES'], '<5h', *([-1] * 5))                       # no rule at all
for i in range(10): poke(R + 30 * i, '<h', -1)
for i in range(8): poke(T['MOD_EVO_FRESH'] + 4 * i, '<2h', -1, -1)
for i in range(4): poke(T['MOD_EVO_ITEMS'] + 6 * i, '<h', -1)
poke(T['EVOLUTION_TARGET'], '<h', -1); call('handleEvoItems(0x7e)'); print('  item 0x7e ->', target(), '(expected -1)')
poke(FAKE, '<i', 24); gs(**{'partner.para.evoTimer': 240})
print('  praise Whamon evoTimer 240 ->', call(f'handleSpecialEvolutions(3,{FAKE})'), '(expected -1)')
print('  Fresh 1 ->', call('getFreshEvolutionTarget(1)'), '(expected -1)')
PY
tools/dev/emulator.py stop >/dev/null
