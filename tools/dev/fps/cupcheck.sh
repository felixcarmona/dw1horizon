#!/bin/bash
# cupcheck.sh STATE TAG "MODES" [NTICKS] [POKETICK]: hash the cup per tick from STATE
# (battlecheck.py, STD overlay included) in each mode ("MODE INTERP name" words),
# MOD_FPS_TEST_TICK=8; the rival (NPC_ENTITIES[0]) gets 0 HP on tick POKETICK.
cd "$(dirname "$0")/../../.." || exit 1
export EMU_PORT=${EMU_PORT:-38099}
STATE=$1; TAG=$2; MODES=$3; N=${4:-1500}; PT=${5:-900}
L=build/dev/fps; mkdir -p "$L"
IN="NONE:1000"
for i in $(seq 1 30); do IN="$IN CROSS:1 NONE:29"; done
first=
for m in $MODES; do
	IFS=, read mode interp name <<< "$m"
	python3 tools/dev/fps/battlecheck.py run $STATE $mode $interp $N "$IN" $L/$TAG-$name.log MOD_FPS_TEST_TICK=8 OVL=STD POKE=$PT:NPC_ENTITIES+0x4c:0 >/dev/null
	echo "$name: $(tools/dev/memory_inspector.py show GAME_STATE TOURNAMENT_WINS MOD_FPS_EFE_NO_ROOM MOD_FPS_TICKS MOD_FPS_RENDERS | awk '{print $1"="$3}' | tr '\n' ' ')"
	[ -z "$first" ] && first=$name || python3 tools/dev/fps/battlecheck.py diff $L/$TAG-$first.log $L/$TAG-$name.log
done
