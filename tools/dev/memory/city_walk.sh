#!/bin/bash
# city_walk.sh: fresh boot, card start, File City walk with reversals; ring + VRAM checked after each step
cd "$(dirname "$0")/../../.." || exit 1
export EMU_PORT=38096
T=build/dev/memory; mkdir -p $T/shots
tools/dev/emulator.py stop >/dev/null 2>&1
tools/dev/emulator.py start ${1:-build/what-the-island-forgot.cue} --card build/states/file-city.mcd >/dev/null
tools/dev/emulator.py seq tools/dev/sequences/continue.seq >/dev/null; sleep 3
echo "retries after boot: $(tools/dev/emulator.py log | grep -c retry)"
python3 tools/dev/memory/transit.py 236 | cut -c1-30
for mv in DOWN:10 LEFT:90 RIGHT:20 LEFT:20 RIGHT:200 UP:60 UP:30 DOWN:10 UP:10 DOWN:30 UP:40 DOWN:60 LEFT:60 RIGHT:60 LEFT:60 UP:90 UP:60 DOWN:20 UP:20 RIGHT:60 LEFT:30 DOWN:100; do
  python3 tools/dev/memory/walk.py $mv | cut -c1-100
  python3 tools/dev/memory/streaming_ring.py | grep -v OK
  python3 tools/dev/memory/palette_check.py | tail -1 | grep -v ": none"
done
echo "retries at end: $(tools/dev/emulator.py log | grep -c retry)"
