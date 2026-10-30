#!/bin/bash
# regress.sh DISC: card start, warp chain (File City, Native Forest, fishing and curling screens),
# day/night, a wild battle; background checked against the TFS after each step
cd "$(dirname "$0")/../../.." || exit 1
export EMU_PORT=38096
T=build/dev/memory; mkdir -p $T/shots
E=tools/dev/emulator.py
chk() { python3 tools/dev/memory/palette_check.py | tr '\n' ' '; echo; }
$E stop >/dev/null 2>&1
$E start ${1:-build/what-the-island-forgot.cue} --card build/states/file-city.mcd >/dev/null
$E seq tools/dev/sequences/continue.seq >/dev/null; sleep 3
python3 tools/dev/game_state.py set hour=12 minute=0 >/dev/null
for w in 236 237 0 6 8 136 3 0; do python3 tools/dev/memory/transit.py $w | cut -c1-24; chk; done
python3 tools/dev/memory/walk.py RIGHT:60 DOWN:60 LEFT:30 UP:30 | cut -c1-60; chk
python3 tools/dev/game_state.py set hour=20 minute=0 >/dev/null; sleep 64; echo "night:"; chk
python3 tools/dev/game_state.py set hour=12 minute=0 >/dev/null; python3 tools/dev/memory/transit.py 0 | cut -c1-24
python3 tools/dev/game_state.py approach 0 120 | tail -1
for i in $(seq 1 6); do sleep 1.5; [ "$(tools/dev/memory_inspector.py show TAMER_STATE | awk '{print $3}')" = 6 ] && break; done
$E press CROSS 5 >/dev/null; sleep 3
for i in $(seq 1 90); do $E press CROSS 3 >/dev/null; sleep 1; g=$(tools/dev/memory_inspector.py show GAME_STATE | awk '{print $3}'); [ $i -gt 5 ] && [ "$g" = 0 ] && break; done
sleep 4; echo "after battle: $(tools/dev/memory_inspector.py show GAME_STATE TAMER_STATE | tr '\n' ' ')"; chk
python3 tools/dev/memory/walk.py RIGHT:90 DOWN:90 RIGHT:90 UP:60 | cut -c1-120; chk
$E shot $T/shots/regress-end.png >/dev/null
echo "retries $($E log | grep -c retry)"
