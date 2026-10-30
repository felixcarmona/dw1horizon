#!/usr/bin/env python3
"""tools/dev/game_state.py with an explicit symbol map: GS_MAP=FILE (lines "    0xADDR    NAME", from `nm` of the disc's
ELF). Several worktrees share the code start, so game_state.py's automatic detection can pick the wrong one (then it
reads a screen of -135 and the like). The disc is taken as a 16-bit-ids build (the integration series, as every
recipe disc). Without GS_MAP it is game_state.py itself. Same arguments."""

from pathlib import Path as _DevPath
import sys as _dev_sys
_DEV_ROOT = str(next(p for p in _DevPath(__file__).resolve().parents if (p / "tools").is_dir()))
_dev_sys.path.insert(0, _DEV_ROOT)
_dev_sys.path.insert(0, str(_DevPath(_DEV_ROOT) / "tools"))
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tools.dev import symbols as dwsyms; from tools.dev import game_state as gamestate
if os.environ.get('GS_MAP'):
    dwsyms.CANDIDATES['explicit-map'] = (dwsyms.CANDIDATES['orig'][0], os.environ['GS_MAP'])
    gamestate.BUILD = 'explicit-map'
gamestate.main()
