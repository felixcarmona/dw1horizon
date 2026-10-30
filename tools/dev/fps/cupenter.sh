#!/bin/bash
# cupenter.sh: from in-game control (card start), go to the Arena Lobby,
# register for the Grade D cup and enter it at 10:00 (the steps of the ids
# play-test, docs/reference/ids.md). Needs the emulator on EMU_PORT.
cd "$(dirname "$0")/../../.." || exit 1
tools/dev/memory_inspector.py set TAMER_SUB_STATE=0 >/dev/null
tools/dev/game_state.py set hour=8 minute=0 >/dev/null
tools/dev/game_state.py warp 208 0; tools/dev/emulator.py wait 8
tools/dev/game_state.py move -400 800; tools/dev/emulator.py wait 1
tools/dev/emulator.py press CROSS 4; tools/dev/emulator.py wait 3
tools/dev/emulator.py seq "talk IS_SCRIPT_PAUSED 4 1 40" >/dev/null; tools/dev/emulator.py wait 1
tools/dev/emulator.py press CROSS 4; tools/dev/emulator.py wait 3
tools/dev/emulator.py press CROSS 4; tools/dev/emulator.py wait 2
tools/dev/emulator.py press CROSS 4; tools/dev/emulator.py wait 4
tools/dev/emulator.py press CROSS 4; tools/dev/emulator.py wait 2
tools/dev/emulator.py press CROSS 4; tools/dev/emulator.py wait 2
tools/dev/emulator.py press CROSS 4; tools/dev/emulator.py wait 3
for n in 2 3 4; do tools/dev/game_state.py pstat $n; done
tools/dev/game_state.py set hour=10 minute=0 >/dev/null; tools/dev/emulator.py wait 1
tools/dev/game_state.py move -900 1400; tools/dev/emulator.py wait 1
tools/dev/emulator.py press CROSS 4; tools/dev/emulator.py wait 1
