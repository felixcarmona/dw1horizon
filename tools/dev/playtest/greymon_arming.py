#!/usr/bin/env python3
"""Greymon's challenge is armed only by Jijimon's talk, and only for a Champion or above.

  python3 tools/dev/playtest/greymon_arming.py build/dev-everything.cue --exe EXE --card CARD

A city entry and the walk past the door arm nothing; babies and rookies, imported ones too, are turned away; with the
rumour spread a Champion arms it at prosperity 10 and the tiles by the door start the fight; a save from 0.0.2 that
holds the challenge armed on entry loses it.
"""
from pathlib import Path
import argparse
import struct
import sys

ROOT = next(p for p in Path(__file__).resolve().parents if (p / 'tools').is_dir())
sys.path[:0] = [str(ROOT), str(ROOT / 'tools')]
from tools.dev.saves.releases import Emu
from tools.langpatch import elf_symbols

ARMED, RUMOUR, OLD_DISC, AGUMON, GREYMON = 87, 755, 776, 203, 205      # Jijimon's news needs Agumon in the city
BOTAMON, VEEMON, AIRDRAMON = 1, 180, 7
RING = (50, -1450)      # a tile of step 6 under the door of Jijimon's house, screen 168
OFF_RING = (1500, -1450)


def bit(e, n):
    ram = e.ram()
    return bool(ram[e.A('SCRIPT_STATE+245') - 0x80000000 + n // 8] & (1 << (n % 8)))


def setup(e, partner, prosperity, rumour, armed=False, old=False):
    e.run('load', 'BOOT'); e.run('lua', 'PCSX.resumeEmulator()'); e.wait(1)
    for n, v in ((ARMED, armed), (RUMOUR, rumour), (OLD_DISC, old), (GREYMON, False), (AGUMON, True)): e.gs('trigger', str(n), str(int(v)))
    e.gs('pstat', '1', str(prosperity))
    e.gs('set', f'partner.type={partner}')


def warp(e, screen, exit_=0):
    assert e.warp(screen, exit_), f'screen {screen} did not load'
    e.wait(2)


def talk_to_jijimon(e):
    warp(e, 218)
    e.gs('approach', '0', '150')
    e.wait(1)
    for _ in range(12):
        e.press('CONFIRM', 6); e.wait(.5)
    assert e.in_control(60), 'the talk did not end'


def place(e, x, z):
    e.poke('TAMER_POSITION_DATA+0x78', struct.pack('<3i', x, 0, z))
    e.poke('TAMER_ENTITY+0x10', struct.pack('<3i', x << 15, 0, z << 15))


def walk_past(e):
    """Three seconds on the tile, then off it: a tile's section reruns while the tamer stands there, so he is free only off it."""
    place(e, *RING); e.wait(3); place(e, *OFF_RING); e.wait(1)
    return e.peek('GAME_STATE', 'H') == 0 and e.in_control(5)


def check(name, got, want):
    print(('ok  ' if got == want else 'BAD ') + name, 'got', got, flush=True)
    return got == want


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('disc'); ap.add_argument('--exe', required=True); ap.add_argument('--card', required=True)
    ap.add_argument('--out', default='build/greymon-arming'); ap.add_argument('--port', type=int, default=39053)
    a = ap.parse_args(); out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    e = Emu(a.disc, a.exe, a.port, str(out / 'emu'))
    for name, (address, _, _) in elf_symbols(a.exe + '.elf').items(): e.table.setdefault(name, address)
    good = True
    boot = str((out / 'boot.state').resolve())
    plain = e.run
    e.run = lambda *args, **kw: plain(*[boot if x == 'BOOT' else x for x in args], **kw)
    try:
        e.start(a.card); assert e.continue_game() == 0
        e.wait(10); assert e.in_control()
        e.poke('MOD_OPT_STORY', struct.pack('<i', 1))
        e.gs('set', 'hour=10', 'minute=0', 'gametime_running=0')
        e.run('save', boot)

        setup(e, AIRDRAMON, 16, True); warp(e, 168)
        good &= check('entering the city arms nothing', bit(e, ARMED), False)
        good &= check('the road by the door stays free', walk_past(e), True)

        for name, partner in (('baby', BOTAMON), ('imported rookie', VEEMON)):
            setup(e, partner, 16, True); talk_to_jijimon(e)
            good &= check(f'{name}: Jijimon arms nothing', bit(e, ARMED), False)

        setup(e, AIRDRAMON, 10, False); talk_to_jijimon(e)
        good &= check('rumour kept quiet, prosperity 10: not armed', bit(e, ARMED), False)
        setup(e, AIRDRAMON, 15, False); talk_to_jijimon(e)
        good &= check('rumour kept quiet, prosperity 15: armed', bit(e, ARMED), True)

        setup(e, AIRDRAMON, 10, True); talk_to_jijimon(e)
        good &= check('rumour spread, prosperity 10, Champion: armed', bit(e, ARMED), True)
        warp(e, 168); place(e, *RING); e.wait(3)
        good &= check('the tile starts his scene', bit(e, ARMED), False)
        e.run('shot', str(out / 'greymon-scene.png'))

        setup(e, BOTAMON, 16, True, armed=True, old=True); warp(e, 168)
        good &= check('old save: challenge forgotten', (bit(e, ARMED), bit(e, OLD_DISC)), (False, False))
        good &= check('old save: the road by the door stays free', walk_past(e), True)
    finally:
        e.run('shot', str(out / 'last.png'), check=False)
        e.stop()
    sys.exit(0 if good else 1)


if __name__ == '__main__': main()
