#!/usr/bin/env python3
"""Talk to the NPC in front: hold a pad direction into it and tap X until a script runs (IS_SCRIPT_PAUSED 0), on the
running emulator (EMU_PORT, DW_SYMS). An NPC talks when the tamer walks into it with X pressed; standing next to it
and pressing X does nothing.

  talk.py DIRECTION [TRIES]     DIRECTION: UP, DOWN, LEFT or RIGHT (screen directions); TRIES taps (default 15)
Exit 0 when the talk started.
"""

from pathlib import Path as _DevPath
import sys as _dev_sys
_DEV_ROOT = str(next(p for p in _DevPath(__file__).resolve().parents if (p / "tools").is_dir()))
_dev_sys.path.insert(0, _DEV_ROOT)
_dev_sys.path.insert(0, str(_DevPath(_DEV_ROOT) / "tools"))
import os, sys, time, subprocess
ROOT = _DEV_ROOT
sys.path.insert(0, os.path.join(ROOT, 'tools'))
from tools.dev import emulator as emu


def script_running():
    out = subprocess.run([sys.executable, os.path.join(ROOT, 'tools/dev/game_state.py'), 'show', 'script_paused'],
                         capture_output=True, text=True).stdout.split()
    return bool(out) and out[-1] == '0'


def main():
    if len(sys.argv) < 2 or sys.argv[1] not in ('UP', 'DOWN', 'LEFT', 'RIGHT'): sys.exit(__doc__)
    direction, tries = sys.argv[1], int(sys.argv[2]) if len(sys.argv) > 2 else 15
    emu.api(f'/api/v1/lua/press?button={direction}')
    try:
        for _ in range(tries):
            emu.api('/api/v1/lua/press?button=CROSS'); time.sleep(0.1); emu.api('/api/v1/lua/release?button=CROSS')
            time.sleep(0.25)
            if script_running(): return 0
    finally:
        emu.api(f'/api/v1/lua/release?button={direction}'); emu.api('/api/v1/lua/release?button=CROSS')
    return 1


if __name__ == '__main__':
    sys.exit(main())
