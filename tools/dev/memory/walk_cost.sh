#!/bin/bash
# walk_cost.sh DISC: card start, warp chain timing, then MOD_PERF during a File City walk across window boundaries
cd "$(dirname "$0")/../../.." || exit 1
export EMU_PORT=38096
T=build/dev/memory; mkdir -p $T/shots
tools/dev/emulator.py stop >/dev/null 2>&1
tools/dev/emulator.py start $1 --card build/states/file-city.mcd >/dev/null
tools/dev/emulator.py seq tools/dev/sequences/continue.seq >/dev/null; sleep 3
python3 tools/dev/memory/transit.py 236 0 1 3 0 236 | cut -c1-200
python3 tools/dev/fps/frame_cost.py 2 14 &
sleep 1.5
python3 tools/dev/memory/walk.py LEFT:90 RIGHT:200 UP:90 DOWN:60 LEFT:60 RIGHT:60 >/dev/null
wait
echo "retries $(tools/dev/emulator.py log | grep -c retry)"
