#!/usr/bin/env python3
"""Factorial Town with the factory kept shut, at 20:00: the story's on-enter `.leave()` hits NPCs the map's hour rule
never spawned (screen 155 always has three absent, 154 at night, 153 by day). The unpatched engine freed an undefined
entity (removeEntity with a null entity, free3(0)) and the load never finished, so no screen could be left; patch 0302
ignores the unload.

  xvfb-run -a python3 tools/dev/playtest/absent_leave.py DISC --exe EXE --card CARD --expect hang|pass

Original 2 MB RAM. Enters the town screens (flag 761 set, hour 20), then loads each outside screen and requires control
(--expect pass) or records that one never finishes (--expect hang, the baseline). Screenshots stay under --out.
"""
from pathlib import Path
import argparse
import json
import struct
import sys

ROOT = next(p for p in Path(__file__).resolve().parents if (p / 'tools').is_dir())
sys.path[:0] = [str(ROOT), str(ROOT / 'tools')]
from tools.dev.saves.releases import Emu
from tools.langpatch import elf_symbols


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('disc'); ap.add_argument('--exe', required=True); ap.add_argument('--card', required=True)
    ap.add_argument('--expect', choices=('hang', 'pass'), required=True)
    ap.add_argument('--screens', type=int, nargs='+', default=[168, 182], help='screens outside the town to load')
    ap.add_argument('--out', default='build/absent-leave'); ap.add_argument('--port', type=int, default=44201)
    a = ap.parse_args(); out = Path(a.out).resolve(); out.mkdir(parents=True, exist_ok=True)
    e = Emu(a.disc, a.exe, a.port, str(out / 'emu'))
    for name, (addr, _, _) in elf_symbols(a.exe + '.elf').items(): e.table.setdefault(name, addr)
    e.env['EMU_ARGS'] = '-interpreter -debugger'
    result = {'expect': a.expect, 'screens': {}}
    try:
        from tools.dev.playtest.birdramon_recruitment import field_card
        field_card(a.card, str(out / 'test.mcd'))
        e.start(str(out / 'test.mcd')); r = e.continue_game(); assert r == 0, f'Continue failed: {r}'
        e.wait(5); assert e.in_control()
        result['ram_bytes'] = len(e.ram())
        e.poke('MOD_OPT_STORY', struct.pack('<i', 1))
        e.gs('set', 'hour=20', 'minute=0', 'gametime_running=0')
        e.gs('trigger', '761', '1')
        checkpoint = out / 'boot.state'; e.run('save', str(checkpoint))
        for s in [153, 154, 155] + a.screens:
            ok = e.warp(s)
            if ok: e.wait(2); ok = e.in_control(10)
            e.run('shot', str(out / f'screen-{s}.png'), check=False)
            result['screens'][s] = 'control' if ok else 'no control'
            print(s, result['screens'][s], flush=True)
            if not ok: break
        stuck = 'no control' in result['screens'].values()
        if a.expect == 'pass':
            assert not stuck and len(result['screens']) == 3 + len(a.screens), result
        else:
            assert stuck, 'baseline did not hang: ' + str(result)
    except BaseException as error:
        result['error'] = str(error); e.run('shot', str(out / 'failure.png'), check=False); raise
    finally:
        (out / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
        e.stop()
    print(json.dumps(result))


if __name__ == '__main__':
    main()
