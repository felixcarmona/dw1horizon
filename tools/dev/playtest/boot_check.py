#!/usr/bin/env python3
"""Boots a disc past the intro movie and the first-start language picker, the way every emulator test starts.

  EMU_PORT=38330 tools/dev/playtest/boot_check.py DISC.cue EXE [--card CARD.mcd]

EXE is the disc's executable with EXE.elf.map and EXE.elf beside it (build/NAME/exe/SLUS_010.32). Two boots:
  1. a blank memory card: the movie must be skipped (START), the language picker (MOD_BOOT_LANGUAGE, a `static` read from
     the ELF symbols) must be pending and answered (START), and the title menu must come;
  2. CARD (default: the newest card of tools/dev/saves/corpus), Continue: the Tamer must have control in the world.
Exit 0 when both pass, 1 otherwise. A harness that cannot do this stalls every species proof (docs/developing.md).
"""

from pathlib import Path as _DevPath
import sys as _dev_sys
_DEV_ROOT = str(next(p for p in _DevPath(__file__).resolve().parents if (p / "tools").is_dir()))
_dev_sys.path.insert(0, _DEV_ROOT)
_dev_sys.path.insert(0, str(_DevPath(_DEV_ROOT) / "tools"))
import argparse, glob, os, sys

from tools.dev.saves.releases import Emu, CORPUS, ROOT


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('cue'); ap.add_argument('exe')
    ap.add_argument('--card')
    a = ap.parse_args()
    port = int(os.environ.get('EMU_PORT') or sys.exit('set EMU_PORT (38330..38339)'))
    card = a.card or sorted(glob.glob(os.path.join(CORPUS, '*.mcd')))[-1]
    emu = Emu(a.cue, a.exe, port, os.path.join(ROOT, 'build/boot-check'))
    emu.home = os.environ.get('EMU_HOME') or os.path.join(ROOT, '.tools/emu/home-' + str(port))
    emu.env['EMU_HOME'] = emu.home
    ok = True
    try:
        for name in ('MOD_BOOT_LANGUAGE', 'MAIN_MENU_TICKS', 'CURRENT_MENU'):
            if not emu.has(name):
                print(f'FAIL the harness cannot see {name} in {emu.exe}.elf(.map)'); return 1
        emu.start(None)
        picker = emu.to_title()
        ram = emu.ram()
        print(f'{"ok  " if picker else "FAIL"} blank card: first-start language picker (pending under the movie) answered')
        still = emu.language_picker(ram)
        print(f'{"FAIL" if still else "ok  "} blank card: title menu reached, picker closed')
        ok = picker and not still
        emu.stop()
        emu.start(card)
        error = emu.continue_game()
        print(f'{"ok  " if error == 0 else "FAIL"} {os.path.basename(card)}: continue -> {"in the world, Tamer has control" if error == 0 else error}')
        ok = ok and error == 0
    finally:
        emu.stop()
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
