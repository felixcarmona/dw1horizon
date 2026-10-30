#!/bin/bash
# battle.sh TAG: from in-game control on screen 0, fight wild slot 0 with X presses; shots every 10 s
cd "$(dirname "$0")/../../.." || exit 1
export EMU_PORT=38096
T=build/dev/memory; mkdir -p $T/shots
E=tools/dev/emulator.py
python3 tools/dev/game_state.py approach ${2:-0} 120 | tail -1
for i in $(seq 1 6); do sleep 1.5; [ "$(tools/dev/memory_inspector.py show TAMER_STATE | awk '{print $3}')" = 6 ] && break; done
$E press CROSS 5 >/dev/null; sleep 3
for i in $(seq 1 90); do $E press CROSS 3 >/dev/null; sleep 1; g=$(tools/dev/memory_inspector.py show GAME_STATE | awk '{print $3}'); [ $((i % 10)) = 5 ] && $E shot $T/shots/$1-b$i.png >/dev/null; [ $i -gt 5 ] && [ "$g" = 0 ] && break; done
sleep 4; echo "after battle ($i s): $(tools/dev/memory_inspector.py show GAME_STATE TAMER_STATE CURRENT_SCREEN | tr '\n' ' ')"
python3 tools/dev/game_state.py show partner.stats.hp partner.stats.mp 2>/dev/null | tr '\n' ' '; echo
