#!/usr/bin/env python3
"""Play a fresh/restarted New Game and inspect its actual partner care.

The restart fixture seeds the PREVIOUS partner's age, then requests the same
native cleanup/title transition as Cheats > Main menu. No care writes occur
between the new title selection and acceptance. --from-state must belong to
the supplied executable and be a field state with free control (no UI open).
FMVs can be skipped; quiz, naming and all introduction scripts still execute.
"""
import argparse
import json
from pathlib import Path
import struct
import sys
import time

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT), str(ROOT / 'tools')]
from tools.dev.saves.releases import Emu
from tools.dev.game_state import PARTNER_PARA_FIELDS
from tools.langpatch import elf_symbols


def care(emu):
    ram = emu.ram()
    at = emu.A('PARTNER_PARA') - 0x80000000
    result = {}
    for name, fmt in PARTNER_PARA_FIELDS:
        result[name] = struct.unpack_from('<' + fmt, ram, at)[0]
        at += struct.calcsize('<' + fmt)
    result.update(species=emu.peek('PARTNER_ENTITY', 'i', ram),
                  screen=emu.peek('CURRENT_SCREEN', 'h', ram),
                  language=emu.peek('MOD_LANG', 'i', ram),
                  money=emu.peek('MONEY', 'i', ram),
                  day=emu.peek('DAY', 'h', ram),
                  stats=emu.peek('PARTNER_ENTITY+0x38', '4h8x4h', ram))
    return result


def until(emu, predicate, seconds=180):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(.25)
    raise RuntimeError('native state transition timed out')


def title(emu, language):
    deadline = time.monotonic() + 240
    while time.monotonic() < deadline:
        ram = emu.ram()
        if emu.peek('CURRENT_MENU', 'i', ram) == 0 and emu.peek('MAIN_MENU_TICKS', 'i', ram) > 3:
            if not emu.language_picker(ram):
                assert emu.peek('MOD_LANG', 'i', ram) == language
                return
            cursor = emu.peek('MOD_BOOT_LANGUAGE_CURSOR', 'i', ram)
            if cursor != language:
                emu.press('DOWN' if language == 2 else 'UP', 4)
            else:
                emu.press('START', 8)
        else:
            emu.press('START', 8)
        time.sleep(.5)
    raise RuntimeError('title/language selection timed out')


def new_game(emu, out, media):
    # NEW GAME -> no memory card -> yes, with each cursor read from the real UI.
    until(emu, lambda: emu.peek('CURRENT_MENU', 'i') == 0 and
          emu.peek('MAIN_MENU_TICKS', 'i') > 3)
    while emu.peek('MENU_HIGHLIGHTS', 'b') != 0:
        emu.press('UP', 4)
        time.sleep(.3)
    emu.press('CONFIRM', 16)
    until(emu, lambda: emu.peek('CURRENT_MENU', 'i') == 10)
    while emu.peek('MENU_HIGHLIGHTS+0x10', 'b') != 2:
        emu.press('DOWN', 4)
        time.sleep(.3)
    emu.press('CONFIRM', 16)
    until(emu, lambda: emu.peek('CURRENT_MENU', 'i') == 19)
    emu.press('CONFIRM', 16)
    until(emu, lambda: emu.peek('CURRENT_MENU', 'i') == -1)
    # CURRENT_SCREEN/free-control can still hold the previous game's values
    # throughout the quiz. Require the new introduction to visit the house.
    house = False
    deadline = time.monotonic() + 1200
    last = None
    while time.monotonic() < deadline:
        ram = emu.ram()
        screen = emu.peek('CURRENT_SCREEN', 'h', ram)
        paused = emu.peek('IS_SCRIPT_PAUSED', 'i', ram)
        now = (screen, paused)
        if now != last:
            print('opening', now, flush=True)
            last = now
        house |= screen == 218
        if house and screen == 204 and paused == 1 and emu.peek('TAMER_STATE', 'b', ram) == 0:
            emu.run('pause')
            result = care(emu)
            (out / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
            emu.run('save', str(out / 'field.state'))
            emu.run('shot', str(media / (out.name + '-field.png')))
            return result
        emu.press('CONFIRM', 8)
        time.sleep(.4)
    raise RuntimeError('new-game introduction timed out')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('disc')
    p.add_argument('--exe', required=True)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--media', type=Path, required=True)
    p.add_argument('--port', type=int, default=42519)
    p.add_argument('--expect-age', type=int, required=True)
    p.add_argument('--language', type=int, choices=(0, 2), default=2,
                   help='fresh-card language picker: 0 English, 2 Portuguese')
    p.add_argument('--from-state', type=Path)
    p.add_argument('--restart-age', type=int)
    p.add_argument('--skip-movies', action='store_true')
    args = p.parse_args()
    if (args.from_state is None) != (args.restart_age is None):
        p.error('--from-state and --restart-age must be used together')
    out, media = args.out.resolve(), args.media.resolve()
    out.mkdir(parents=True, exist_ok=True)
    media.mkdir(parents=True, exist_ok=True)
    emu = Emu(str(Path(args.disc).resolve()), args.exe, args.port, str(out / 'emu'))
    emu.table.update({n: v[0] for n, v in elf_symbols(emu.exe + '.elf').items()})
    emu.env['EMU_ARGS'] = '-interpreter -debugger'
    try:
        emu.start(None)
        if args.from_state:
            emu.run('load', str(args.from_state.resolve()))
            emu.run('pause')
            at = 0
            for name, fmt in PARTNER_PARA_FIELDS:
                if name == 'age':
                    break
                at += struct.calcsize('<' + fmt)
            emu.poke(f'PARTNER_PARA+{at}', struct.pack('<h', args.restart_age))
            before = care(emu)
            (out / 'prior-fixture.json').write_text(json.dumps(before, indent=2) + '\n')
            emu.poke('MOD_CHEATS_TRANSITION', struct.pack('<i', 2))
            emu.run('resume')
        else:
            title(emu, args.language)
        if args.skip_movies:
            emu.run('lua', f'''NG_MOVIE=PCSX.addBreakpoint({emu.A('playMovie')},'Exec',4,'new-game-fmv',function()
 local r=PCSX.getRegisters();r.GPR.n.v0=0;r.pc=r.GPR.n.ra
end);return true''')
        result = new_game(emu, out, media)
        print(json.dumps(result), flush=True)
        assert result['age'] == args.expect_age, result
        assert result['species'] == 3, 'first quiz answers must select Agumon'
        assert result['money'] == 1000, 'the actual start kit must have executed'
        assert result['stats'] == [80, 60, 70, 70, 800, 600, 800, 600], result
        assert result['careMistakes'] == 0 and result['evoTimer'] == 0, result
    finally:
        emu.stop()


if __name__ == '__main__':
    main()
