#!/usr/bin/env python3
"""Final battle, clear save and five minutes of credits on original 2 MB hardware.

EMU_PORT and DW_SYMS select a private emulator and this disc's symbols. Supply a
private memory card saved before the final fight on screen 225. Only battle HP
is assisted; the game's battle, save and ending code execute normally.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import time

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT), str(ROOT / 'tools')]
from tools.dev.playtest import species_proof as P
import dwmap


def ending_ranges(maptext):
    section = maptext.split('\n.ENDI ', 1)[1].split('\n.EVL ', 1)[0]
    ranges = [(int(a, 16) - 0x80060000, int(n, 16)) for a, n in re.findall(
        r'^ \.text\.[^\n]+\n\s+(0x[0-9a-f]+)\s+(0x[0-9a-f]+)', section, re.M)]
    if not ranges:
        raise RuntimeError('no ENDI executable ranges found in the current map')
    return ranges


def play(cue, card, out, result):
    def sample():
        ram = P.EMU.ram()
        names = [('CURRENT_SCREEN', 'h'), ('GAME_STATE', 'B'), ('TAMER_STATE', 'b'),
                 ('CURRENT_MENU', 'i'), ('MAIN_STATE', 'i'), ('PAUSE_STATE', 'i')]
        return ram, [P.EMU.peek(name, fmt, ram) for name, fmt in names]

    def shot(name):
        P.EMU.run('shot', str(out / (name + '.png')))

    P.EMU = P.emulator(str(cue))
    P.EMU.start(str(card))
    result['ram_bytes'] = len(P.EMU.ram())
    P.EMU.to_title()
    selected = False
    for _ in range(120):
        ram, now = sample()
        if selected and now[3] == -1 and now[0] == 225:
            break
        if now[3] == 0 and P.EMU.peek('MAIN_MENU_TICKS', 'i', ram) > 3:
            if P.EMU.peek('MENU_HIGHLIGHTS', 'b', ram) != 1:
                P.EMU.press('DOWN', 6)
            else:
                P.EMU.press('CONFIRM', 6)
                selected = True
        else:
            P.EMU.press('CONFIRM', 6)
        P.EMU.wait(2)
    else:
        raise RuntimeError('pre-fight card did not load into screen 225')
    shot('loaded-before-final')
    screen = dwmap.MapFile((ROOT / 'extracted/MAP/MAP16/MGEN99.MAP').read_bytes())
    tiles = [i for i, value in enumerate(screen.collision) if value == 51]
    i = tiles[len(tiles) // 2]
    tile = ((i % 100 - 50) * 100 + 50, (50 - i // 100) * 100 - 50)
    result['samples'] = []
    last, ending_at = None, None
    fought = saved = triggered = assisted = False
    start = time.monotonic()
    screenshots = set()
    while time.monotonic() - start < 1200:
        ram, now = sample()
        elapsed = round(time.monotonic() - start)
        if now != last:
            print('ending', elapsed, now, flush=True)
            last = now
            result['samples'].append([elapsed, *now])
        paused = P.EMU.peek('IS_SCRIPT_PAUSED', 'i', ram)
        if now[0] == 225 and now[2] == 0 and paused == 1 and not triggered:
            if now[5]:
                P.EMU.press('START', 6)
            else:
                P.EMU.gs('move', str(tile[0]), str(tile[1]))
                triggered = True
        if now[1] == 1:
            fought = True
            if not assisted:
                P.mset('NPC_ENTITIES[0].digimonEntity.stats.current.currentHP=1',
                       'PARTNER_ENTITY.digimonEntity.stats.base.hp=30000',
                       'PARTNER_ENTITY.digimonEntity.stats.current.currentHP=30000')
                assisted = True
                result['battle_assistance'] = 'Foe HP set to 1; partner HP to 30000 after the actual battle starts.'
        if now[3] in (0x45, 0x3e):
            saved = True
        if now[2] == 16 and ending_at is None:
            ending_at = time.monotonic()
            exe = Path(os.environ['DW_SYMS'])
            overlay = (exe.parent / 'ENDI_REL.BIN').read_bytes()
            ranges = ending_ranges(Path(str(exe) + '.elf.map').read_text())
            expected = b''.join(overlay[a:a+n] for a, n in ranges)
            live = b''.join(ram[0x60000+a:0x60000+a+n] for a, n in ranges)
            result.update(endi_text_bytes=len(expected), endi_code_matches_disc=live == expected,
                          endi_disc_code_sha256=hashlib.sha256(expected).hexdigest(),
                          endi_live_code_sha256=hashlib.sha256(live).hexdigest())
            shot('ending-code-restored')
            if live != expected:
                raise RuntimeError('ENDI executable code differs after clear save')
        if ending_at is not None:
            age = int(time.monotonic() - ending_at)
            for threshold in (30, 150, 300):
                if age >= threshold and threshold not in screenshots:
                    shot(f'credits-{threshold}')
                    screenshots.add(threshold)
            if age >= 300:
                break
        else:
            P.EMU.press('CONFIRM', 6)
        P.EMU.wait(2)
    result.update(fought=fought, clear_save_seen=saved, credits_completed=300 in screenshots)
    result['ok'] = all(result.get(k) for k in ('fought', 'clear_save_seen', 'endi_code_matches_disc', 'credits_completed'))
    if not result['ok']:
        raise RuntimeError('final battle, clear save or credits gate failed')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('cue', type=Path)
    parser.add_argument('out', type=Path)
    parser.add_argument('--card', required=True, type=Path)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    result = {'ok': False}
    start = time.monotonic()
    try:
        play(args.cue.resolve(), args.card.resolve(), args.out.resolve(), result)
    finally:
        if P.EMU:
            P.EMU.stop()
        result['seconds'] = round(time.monotonic() - start, 2)
        (args.out / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
        print(json.dumps(result), flush=True)
    return 0 if result['ok'] else 1


if __name__ == '__main__':
    sys.exit(main())
