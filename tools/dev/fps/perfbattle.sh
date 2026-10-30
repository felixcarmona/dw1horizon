#!/bin/bash
# perfbattle.sh STATE: battle cost per render pass (MOD_PERF counters, frame_cost.py)
# with the dynarec. From a save state next to a wild Digimon with its "ready to
# begin" text open: CROSS starts the battle; once the fight runs (GAME_STATE 1)
# each mode is measured for 6 s: 20 fps, 60 fps (interpolated), and 60 fps
# with MOD_FPS_TEST_TICK=8 (every extra pass, to get its cost even
# when it does not fit). Needs the emulator running on EMU_PORT.
cd "$(dirname "$0")/../../.." || exit 1
R=$PWD
STATE=$(realpath "$1")
tools/dev/emulator.py load "$STATE" >/dev/null
tools/dev/emulator.py press CROSS 3 >/dev/null
until [ "$(tools/dev/memory_inspector.py show GAME_STATE | awk '{print $3}')" = 1 ]; do sleep 1; done
sleep 4
for mode in "0 0" "2 0" "2 8"; do
	set -- $mode
	tools/dev/memory_inspector.py set MOD_FPS_TEST_TICK=$2 >/dev/null
	echo -n "test tick=$2 "
	python3 tools/dev/fps/interpolation_cost.py 2 6 $1
done
tools/dev/memory_inspector.py set MOD_FPS_TEST_TICK=0 >/dev/null
tools/dev/memory_inspector.py show GAME_STATE MOD_FPS_EFE_NO_ROOM
