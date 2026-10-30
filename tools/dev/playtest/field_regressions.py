#!/usr/bin/env python3
"""Original-2-MB regressions for transitions missed by loading each screen alone.

  DISPLAY=:129 python3 tools/dev/playtest/field_regressions.py DISC --exe EXE --card CARD

Always boots a memory card with the supplied executable; never imports code from an old save state.
Root Clearing keeps every native NPC/partner and physically crosses screen 2's south exit.
Canyon loads the night hunters and checks battle entry, victory and return to field control.
"""

from pathlib import Path as _DevPath
import sys as _dev_sys
_DEV_ROOT = str(next(p for p in _DevPath(__file__).resolve().parents if (p / "tools").is_dir()))
_dev_sys.path.insert(0, _DEV_ROOT)
_dev_sys.path.insert(0, str(_DevPath(_DEV_ROOT) / "tools"))
import argparse
import json
from pathlib import Path
import struct
import sys
import time

sys.path[:0] = [str(Path(__file__).resolve().parents[2]), str(_DevPath(_DEV_ROOT))]
from tools.dev.saves.releases import Emu
from tools.langpatch import elf_symbols


def healthy(e):
    flow = json.loads(e.api('/api/v1/execution-flow'))
    assert flow['running'], f'emulator stopped: {flow}'
    return flow


def place(e, x, z):
    e.poke('TAMER_POSITION_DATA+0x78', struct.pack('<3i', x, 0, z))
    e.poke('TAMER_ENTITY+0x10', struct.pack('<3i', x << 15, 0, z << 15))


def root(e, out):
    e.gs('trigger', '755', '0')  # The unspread rumour used to remove a hunter absent by day.
    e.gs('set', 'hour=10', 'minute=0', 'gametime_running=0')
    e.poke('CURRENT_FRAME', struct.pack('<H', 10*1200))
    e.poke('LAST_HANDLED_FRAME', struct.pack('<H', 10*1200))
    e.poke('MOD_CLOCK', struct.pack('<h', -1))
    assert e.warp(2, 4), 'screen 2 did not load'
    e.wait(1)
    place(e, -750, -1750)
    e.run('save', str(out/'root-before.state'))
    e.press('DOWN', 36)
    for _ in range(30):
        e.wait(.5); healthy(e)
        ram = e.ram()
        if e.peek('CURRENT_SCREEN', 'h', ram) == 314 and e.peek('TAMER_STATE', 'b', ram) == 0: break
    else: raise AssertionError('2 -> 314 did not return control')
    e.wait(2); healthy(e)
    assert e.peek('CURRENT_SCREEN', 'h') == 314
    pos = e.peek('TAMER_POSITION_DATA+0x78', '3i')
    assert pos[1] == 0 and max(abs(v) for v in pos) < 10000, pos
    e.run('shot', str(out/'bug-arreglado-root-clearing.png'))
    return dict(screen=314, position=pos, ram_bytes=len(e.ram()), running=True)


def night(e, out):
    e.gs('set', 'partner.para.age=1', 'partner.para.evoTimer=0', 'partner.para.condition=0',
         'partner.stats.off=900', 'partner.stats.def=900', 'partner.stats.speed=900',
         'partner.stats.brain=900', 'partner.stats.hp=9000', 'partner.stats.mp=9000',
         'partner.stats.currentHP=9000', 'partner.stats.currentMP=9000', 'hour=21', 'minute=1', 'gametime_running=1')
    for n, v in [(719, 1), (757, 0), (749, 0)]: e.gs('trigger', str(n), str(v))
    e.poke('CURRENT_FRAME', struct.pack('<H', 21*1200+20))
    e.poke('LAST_HANDLED_FRAME', struct.pack('<H', 21*1200+20))
    e.poke('MOD_CLOCK', struct.pack('<h', -1))
    assert e.warp(41), 'night hunters did not load'
    healthy(e)
    e.gs('approach', '6', '150')
    started = False
    for _ in range(600):
        healthy(e); ram = e.ram()
        if e.peek('GAME_STATE', 'H', ram) == 1: started = True
        fought = bool(ram[e.A('SCRIPT_STATE+245')-0x80000000+757//8] & (1 << (757 % 8)))
        if fought: break
        e.press('CONFIRM', 8); e.wait(.5)
    else: raise AssertionError('night hunter fight did not finish')
    assert started and e.in_control(), 'battle/control missing'
    healthy(e)
    e.run('shot', str(out/'bug-arreglado-canyon-night.png'))
    return dict(screen=e.peek('CURRENT_SCREEN', 'h'), battle_started=True, hunter_fought=True, ram_bytes=len(e.ram()))


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('disc'); ap.add_argument('--exe', required=True); ap.add_argument('--card', required=True)
    ap.add_argument('--out', default='build/field-regressions'); ap.add_argument('--port', type=int, default=39051)
    ap.add_argument('--case', choices=('root', 'night', 'all'), default='all')
    a = ap.parse_args(); out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    e = Emu(a.disc, a.exe, a.port, str(out/'emu'))
    for name, (address, _, _) in elf_symbols(a.exe + '.elf').items():
        e.table.setdefault(name, address)
    e.env['EMU_ARGS'] = '-interpreter -debugger'
    result = {}
    try:
        e.start(a.card); assert e.continue_game() == 0
        # Continue clears the menu before its initial map/fade has fully settled.
        e.wait(10); assert e.in_control()
        assert len(e.ram()) == 0x200000
        e.poke('MOD_OPT_STORY', struct.pack('<i', 1))
        e.run('save', str(out/'boot.state'))
        for name, fn in [('root', root), ('night', night)]:
            if a.case not in (name, 'all'): continue
            if result:
                e.run('load', str(out/'boot.state')); e.run('lua', 'PCSX.resumeEmulator()'); e.wait(1)
            result[name] = fn(e, out)
            (out/'result.json').write_text(json.dumps(result, indent=2)+'\n')
            print(name, result[name], flush=True)
    except BaseException as error:
        result['error'] = str(error)
        try:
            result['flow'] = json.loads(e.api('/api/v1/execution-flow'))
            result['registers'] = e.run('lua', "local r=PCSX.getRegisters();return string.format('pc=%08x ra=%08x',tonumber(r.pc),tonumber(r.GPR.n.ra))")
            e.run('shot', str(out/'failure.png'))
            e.run('save', str(out/'failure.state'))
        finally:
            (out/'result.json').write_text(json.dumps(result, indent=2)+'\n')
        raise
    finally: e.stop()


if __name__ == '__main__': main()
