#!/bin/bash
# fullcup.sh MODE SHOT: card start, Grade D cup, every rival's HP set to 0 during
# its fight; prints the results. MODE is a label: the frame rate is the disc's
# (a build parameter, FPS=20|30|60, since patch 0080).
cd "$(dirname "$0")/../../.." || exit 1
export EMU_PORT=${EMU_PORT:-38099}
E=tools/dev/emulator.py
$E stop >/dev/null 2>&1
$E start build/fps60.cue --card build/states/file-city.mcd >/dev/null
$E seq tools/dev/sequences/continue.seq >/dev/null
tools/dev/fps/cupenter.sh >/dev/null
m=0; prev=x; poked=; alive=0; shot=
for i in $(seq 1 200); do
	sleep 2
	set -- $1 $(tools/dev/memory_inspector.py show GAME_STATE TOURNAMENT_WINS CURRENT_SCREEN STD_CAMERA_STATE | awk '{print $3}')
	g=$2; wins=$3; scr=$4; cam=$5
	[ "$g" = 4 ] && [ "$prev" = 5 ] && [ $poked ] && { m=$((m+1)); poked=; }
	off=$(printf '%X' $((0x4C + m*0x68)))
	hp=$($E peek NPC_ENTITIES+0x$off 2 | awk '{print $3$2}')
	if [ "$g" = 4 ] && [ "$hp" != 0000 ]; then alive=$((alive+1)); [ $alive -ge 2 ] && { $E poke NPC_ENTITIES+0x$off 0000 >/dev/null; poked=1; alive=0; }; else alive=0; fi
	[ "$wins" = 3 ] && [ -z "$shot" ] && [ -n "$2" ] && { sleep 3; $E shot ${SHOT:-/dev/null} >/dev/null; shot=1; }
	[ "$g" = 0 ] && { $E press CROSS 4 >/dev/null; [ "$scr" != 208 ] && [ "$wins" = 3 ] && break; }
	[ "$g" = 0 ] && [ "$wins" = 3 ] && [ $i -gt 5 ] && n0=$((n0+1))
	[ "${n0:-0}" -gt 6 ] && break
	prev=$g
done
tools/dev/memory_inspector.py show TOURNAMENT_WINS TOURNAMENTS_WON HOUR MINUTE CURRENT_SCREEN GAME_STATE MOD_FPS_TICKS | tr '\n' ' '; echo
tools/dev/game_state.py trigger 15; tools/dev/game_state.py pstat 255
