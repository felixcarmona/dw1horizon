#!/usr/bin/env python3
"""Live game dashboard: the state of Digimon World at a glance, read from RAM.

Usage:
  dashboard.py            print one snapshot
  dashboard.py -w [-i 1]  refresh every second (Ctrl-C to stop)

Works with the original executable and any GCC build (addresses via
tools/dev/symbols.py, types via tools/dev/memory_inspector.py). Names come from docs/data/*.csv.
"""

from pathlib import Path as _DevPath
import sys as _dev_sys
_DEV_ROOT = str(next(p for p in _DevPath(__file__).resolve().parents if (p / "tools").is_dir()))
_dev_sys.path.insert(0, _DEV_ROOT)
_dev_sys.path.insert(0, str(_DevPath(_DEV_ROOT) / "tools"))
import argparse, csv, os, struct, sys, time

ROOT = _DEV_ROOT
sys.path.insert(0, os.path.join(ROOT, 'tools'))
from tools.dev import memory_inspector as mem  # noqa: E402  (re-execs in the venv if needed)

CONDITIONS = ['sleepy', 'tired', 'hungry', 'poopy', 'unhappy', 'injured', 'sick']
OPCODES = {0x00: '-', 0x10: 'selection', 0x1A: 'textbox', 0x4A: 'wait entity', 0x64: 'routine',
           0x67: 'delay', 0xFF: 'closing boxes'}


def names(fname):
    return {int(r['id']): r['name'] for r in csv.DictReader(open(os.path.join(ROOT, 'docs/data', fname)))}


DIGIMON = {t: r['name'] for t, r in __import__('species').all_rows().items()}   # content/species
ITEMS = names('items.csv')
SCREENS = {int(r['id']): f"{r['file']} {r['map_name']}" for r in csv.DictReader(open(os.path.join(ROOT, 'docs/data/map_files.csv')))}


def val(expr):
    vars_, types = mem.build_index()
    addr, t = mem.resolve_expr(expr, vars_, types)
    return mem.scalar(t, addr)


def snapshot():
    mem.ram(True)
    v = val
    out = []
    screen = v('CURRENT_SCREEN')
    out.append(f"screen {screen} ({SCREENS.get(screen, '?')})   day {v('DAY')} year {v('YEAR')}  "
               f"{v('HOUR'):02}:{v('MINUTE'):02}   bits {v('MONEY')}   build {mem.build()}")
    ai = v('ACTIVE_INSTRUCTION')
    out.append(f"game_state {v('GAME_STATE')}  tamer_state {v('TAMER_STATE')}  script "
               f"{'idle' if v('IS_SCRIPT_PAUSED') == 1 else 'running'}  waiting on {OPCODES.get(ai, hex(ai))}")
    p = 'PARTNER_ENTITY.digimonEntity'
    typ = v(f'{p}.entity.type')
    out.append(f"partner {DIGIMON.get(typ, typ)}  HP {v(f'{p}.stats.current.currentHP')}/{v(f'{p}.stats.base.hp')}  "
               f"MP {v(f'{p}.stats.current.currentMP')}/{v(f'{p}.stats.base.mp')}  OFF {v(f'{p}.stats.base.off')} "
               f"DEF {v(f'{p}.stats.base.def')} SPD {v(f'{p}.stats.base.speed')} BRN {v(f'{p}.stats.base.brain')}  "
               f"lives {v('PARTNER_ENTITY.lives')}")
    c = 'PARTNER_PARA'
    cond = v(f'{c}.condition')
    flags = [n for i, n in enumerate(CONDITIONS) if cond & (1 << i)]
    out.append(f"care  food {v(f'{c}.foodLevel')}  energy {v(f'{c}.energyLevel')}  tired {v(f'{c}.tiredness')}  "
               f"happy {v(f'{c}.happiness')}  disc {v(f'{c}.discipline')}  weight {v(f'{c}.weight')}  "
               f"life {v(f'{c}.remainingLifetime')}  age {v(f'{c}.age')}  mistakes {v(f'{c}.careMistakes')}  "
               f"poop {v(f'{c}.poopLevel')}  [{', '.join(flags) or 'ok'}]")
    r = mem.ram()
    loc = lambda name: struct.unpack_from('<3i', r, mem.addr_of(name) + 0x78 - mem.RAM_BASE) if mem.addr_of(name) else None
    tpos = loc('TAMER_POSITION_DATA')
    out.append(f"tamer at x={tpos[0]} z={tpos[2]}" if tpos else 'tamer: ?')
    base = mem.addr_of('NPC_ENTITIES')
    if base and tpos:
        npcs = []
        for i in range(8):
            e = base + i * 0x68 - mem.RAM_BASE
            t, pd = struct.unpack_from('<iI', r, e)
            if not (0x80000000 < pd < 0x80200000) or t <= 0: continue
            x, y, z = struct.unpack_from('<3i', r, pd + 0x78 - mem.RAM_BASE)
            if abs(x) > 100000 or abs(z) > 100000: continue
            d = int(((x - tpos[0]) ** 2 + (z - tpos[2]) ** 2) ** 0.5)
            npcs.append((d, f'{5 + i}:{DIGIMON.get(t, t)}@{d}'))
        out.append('npcs  ' + ('  '.join(s for _, s in sorted(npcs)) or 'none'))
    inv = [(v(f'INVENTORY.types.array[{k}]'), v(f'INVENTORY.amounts.array[{k}]')) for k in range(v('INVENTORY.size'))]
    out.append('items ' + (', '.join(f'{ITEMS.get(t, t)} x{n}' for t, n in inv if t != 255) or 'none'))
    return '\n'.join(out)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('-w', action='store_true'); ap.add_argument('-i', type=float, default=1.0)
    a = ap.parse_args()
    if not a.w:
        print(snapshot()); return
    try:
        while True:
            s = snapshot()
            print('\033[2J\033[H' + time.strftime('%H:%M:%S') + '\n' + s, flush=True)
            time.sleep(a.i)
    except KeyboardInterrupt:
        pass


if __name__ == '__main__':
    main()
