#!/usr/bin/env python3
"""Prove the earned life-loss evolutions (script 212, DIGIMON routine 12 `earned_evolution`).

Per case: the partner becomes the starting species, gets the stats of the case, and loses a life to a long sickness
(the game's own path: a sick partner whose sickness timer is past its limit calls Jijimon's house). The scene is confirmed to the end
and the partner's species and pstat 254 are read back. 254 is set to a marker first, so a lost 30% roll (254 keeps
the marker), a refusal (0) and a started evolution (1) can be told apart; told apart. The emulator's random numbers repeat
after a state load, so the roll is forced: `rand` is replaced in RAM by a stub that returns 0 (the roll comes up 0, a
win); --natural leaves it alone to see a lost roll. A case fails unless it ends as expected:

  met      stats at 999: the partner must become the target
  unmet    stats at 100: routine 12 must refuse and the species must stay
  vanilla  NEW DIGIMON off, stats at 999: an imported target must be refused

  life_loss_evolution.py DISC.cue --exe EXE --out DIR [--cases 5:26:met,5:26:unmet,...]
"""
import argparse
import json
import os
from pathlib import Path
import struct
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT), str(ROOT / 'tools')]
from tools.dev.playtest.eggs import EggEmu, evolve, to_control
from tools.dev.playtest.qol import test_card
from tools.langpatch import elf_symbols

DEFAULT = '5:26:met,5:26:unmet,9:277:met,9:277:vanilla,267:268:met,460:59:met,460:59:unmet'
MARKER = 77
RAND_ZERO = bytes.fromhex('0800e00300000224')      # jr ra; li v0, 0
P254 = 'SCRIPT_STATE+%d' % (345 + 254)


def set_stats(e, value):
    e.gs('set', *(f'partner.stats.{name}={value}' for name in ('off', 'def', 'speed', 'brain')),
         f'partner.stats.hp={min(value * 10, 9999)}', f'partner.stats.mp={min(value * 10, 9999)}')


def lose_life(e, forced):
    """a life lost to sickness; returns pstat 254 after the scene"""
    if forced:
        e.poke('rand', RAND_ZERO)
    e.poke('HAS_IMMORTAL_HOUR', b'\0')
    e.gs('set', 'partner.lives=3', 'partner.para.condition=64', 'partner.para.sicknessTimer=30000')
    e.poke(P254, bytes([MARKER]))
    for _ in range(60):
        if e.peek('PARTNER_ENTITY+0x7C', 'b') == 2:
            break
        e.wait(.5)
    else:
        raise AssertionError('the sickness did not take a life')
    e.wait(3)
    assert to_control(e, 90), 'the scene did not hand control back'
    return e.peek(P254, 'B')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('disc'); p.add_argument('--exe', required=True); p.add_argument('--out', required=True)
    p.add_argument('--cases', default=DEFAULT)
    p.add_argument('--natural', action='store_true', help='do not force the roll')
    p.add_argument('--port', type=int, default=int(os.environ.get('EMU_PORT', 39251)))
    a = p.parse_args(); out = Path(a.out).resolve(); out.mkdir(parents=True, exist_ok=True)
    e = EggEmu(a.disc, a.exe, a.port, str(out / 'emu'))
    e.ram_mb = 2
    e.env['EMU_ARGS'] = ''
    e.out = out
    for name, (address, _, _) in elf_symbols(a.exe + '.elf').items():
        e.table.setdefault(name, address)
    results = []
    ok = True
    try:
        e.start(test_card(out))
        error = e.continue_game()
        assert error == 0, f'Continue failed: {error}'
        e.wait(5); assert e.in_control()
        e.run('save', str(out / 'start.state'))
        for case in a.cases.split(','):
            start, target, kind = case.split(':'); start = int(start); target = int(target)
            e.run('load', str(out / 'start.state')); e.run('lua', 'PCSX.resumeEmulator()'); e.wait(1)
            e.poke('MOD_OPT_NEW_DIGIMON', struct.pack('<i', 1))
            evolve(e, start)
            e.poke('MOD_OPT_NEW_DIGIMON', struct.pack('<i', 0 if kind == 'vanilla' else 1))
            set_stats(e, 100 if kind == 'unmet' else 999)
            e.wait(1)
            e.run('save', str(out / 'case.state'))
            flag = lose_life(e, not a.natural)
            e.wait(40 if flag == 1 else 2)       # the evolution plays out
            to_control(e, 90)
            row = dict(start=start, target=target, kind=kind, p254=flag, species_after=e.peek('PARTNER_ENTITY', 'i'),
                       lives_after=e.peek('PARTNER_ENTITY+0x7C', 'b'))
            if a.natural:
                want = (MARKER, start)
            else:
                want = (1, target) if kind == 'met' else (0, start)
            row['ok'] = (flag, row['species_after']) == want
            e.run('shot', str(out / f'{start}-{target}-{kind}.png'))
            ok &= row['ok']
            results.append(row)
            print(json.dumps(row), flush=True)
    finally:
        (out / 'results.json').write_text(json.dumps(results, indent=1) + '\n')
        e.stop()
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
