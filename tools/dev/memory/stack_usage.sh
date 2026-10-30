#!/bin/bash
# stack_usage.sh DISC: fresh boot, heavy scenes, stack high-water after each
cd "$(dirname "$0")/../../.." || exit 1
export EMU_PORT=38096
T=build/dev/memory; mkdir -p $T/shots
E=tools/dev/emulator.py
sw() { echo "$1: $(python3 tools/membudget.py live --json | python3 -c 'import json,sys; s=json.load(sys.stdin)["stack"]; print(s["used"], hex(s["deepest"]))')"; }
$E stop >/dev/null 2>&1
$E start ${1:-build/what-the-island-forgot.cue} --card build/states/file-city.mcd >/dev/null
$E seq tools/dev/sequences/continue.seq >/dev/null; sleep 3; sw "card start"
for w in 236 0 143 48 167; do python3 tools/dev/memory/transit.py $w >/dev/null; done; sw "warps"
# menus: triangle menu, item list, back; pause + lab menu
$E press TRIANGLE 5 >/dev/null; sleep 1.5; $E press CROSS 5 >/dev/null; sleep 1.5; $E press DOWN 5 >/dev/null; sleep 1; $E press CROSS 5 >/dev/null; sleep 1.5
$E press TRIANGLE 5 >/dev/null; sleep 1; $E press TRIANGLE 5 >/dev/null; sleep 1; $E press TRIANGLE 5 >/dev/null; sleep 1
$E press START 5 >/dev/null; sleep 1; $E press SELECT 5 >/dev/null; sleep 1.5; $E press DOWN 5 >/dev/null; sleep 0.5; $E press TRIANGLE 5 >/dev/null; sleep 1; $E press START 5 >/dev/null; sleep 1
sw "menus"
python3 tools/dev/memory/transit.py 0 >/dev/null; tools/dev/memory/battle.sh st1 0 >/dev/null; sw "wild battle (Native Forest)"
python3 tools/dev/memory/transit.py 143 >/dev/null; python3 tools/dev/game_state.py approach 0 110 >/dev/null; sleep 1
for i in $(seq 1 100); do $E press CROSS 3 >/dev/null; sleep 1; [ $i -gt 40 ] && [ "$(tools/dev/memory_inspector.py show GAME_STATE | awk '{print $3}')" = 0 ] && [ "$(tools/dev/memory_inspector.py show TAMER_STATE | awk '{print $3}')" = 0 ] && break; done
sw "Ogremon + WaruSeadramon battle (143)"
tools/dev/fps/cupenter.sh >/dev/null 2>&1; sleep 5
for i in $(seq 1 150); do $E press CROSS 3 >/dev/null; sleep 1; done
$E shot $T/shots/stack-cup.png >/dev/null; sw "cup ($(tools/dev/memory_inspector.py show CURRENT_SCREEN GAME_STATE | tr '\n' ' '))"
echo "stub hits: $(tools/dev/memory_inspector.py show MOD_NPC_STUB_HITS MOD_NPC_STUB_LAST | tr '\n' ' ')"
