#!/bin/bash
# One recorded walk on the running emulator (EMU_PORT, default 38331; DW_SYMS=${DW_SYMS:-disc-what-the-island-forgot}): heals and boosts the partner, warps to the tour's
# first screen, records SEC seconds while tour2.py walks the tour, then makes the side-by-side video with the zones.
#   walk.sh NAME TOUR.json FIRST_SCREEN FIRST_EXIT SEC      -> build/new-maps/walks/NAME.mp4 (+ NAME-raw.mp4, logs, poslog)
cd "$(dirname "$0")/../../.." || exit 1
PY=${PY:-python3}   # a venv with numpy, cv2 (the new-maps one)
ZONES=${ZONES:-build/new-maps}             # where NAME-zones.png images live, one folder per screen
NAME=$1; TOUR=$2; SCR=$3; EX=$4; SEC=$5; W=build/new-maps/walks; mkdir -p "$W"
export EMU_PORT=${EMU_PORT:-38331} DW_SYMS=${DW_SYMS:-disc-what-the-island-forgot}
# a previous walk may have left a battle result or a dialog open: close it before warping (CIRCLE, X, START in turn), or give up
for i in $(seq 1 150); do                                 # up to three minutes: a battle left running must end first
  ST=$(tools/dev/game_state.py show tamer.state game_state 2>/dev/null | grep -v dwsyms | awk '{print $2}' | tr '\n' ' ')
  [ "$ST" = "0 0 " ] && break
  B=$(echo CIRCLE CROSS | cut -d' ' -f$((i % 2 + 1))); tools/dev/emulator.py press $B 10 >/dev/null 2>&1; sleep 1.2
done
[ "$ST" = "0 0 " ] || { echo "game not free before $NAME: state $ST"; exit 1; }
# the partner must not beg (hungry, poopy, sleepy: after two fights the tamer stood still for four minutes): fed, rested, awake till 23
tools/dev/game_state.py set hour=10 partner.stats.currentHP=5100 partner.stats.currentMP=3000 partner.stats.off=999 partner.stats.def=999 partner.stats.speed=999 \
  partner.para.foodLevel=30000 partner.para.energyLevel=100 partner.para.poopLevel=2000 partner.para.tiredness=0 partner.para.discipline=100 partner.para.happiness=100 \
  partner.para.sleepyHour=9 partner.para.wakeupHour=10 partner.para.hoursAsleepDefault=1 partner.para.nextHungerHour=23 partner.para.tirednessSleepTimer=0 gametime_running=0 >/dev/null 2>&1
# the game recomputes bedtime as wakeupHour - hoursAsleepDefault (wakeupHour 1 gave 16:00): wake at 10, sleep 1 h, bedtime 9:00, a day away
# foodLevel is game minutes until hungry, one less every 20 frames (100 = 33 s); the clock is frozen at 10:00 so bedtime never comes
sleep 0.5; tools/dev/game_state.py set partner.para.condition=0 partner.para.poopingTimer=-1 partner.para.poopLevel=2000 >/dev/null 2>&1   # poopLevel 0 means 'needs to go NOW' (POOPY again next tick); 2000 steps of 10 game minutes
tools/dev/game_state.py warp "$SCR" "$EX" >/dev/null 2>&1; tools/dev/emulator.py wait 6
# the screen load starts the clock again: freeze it after the warp (tour2 freezes it again on every screen change), or at
# 20 s per game hour bedtime (23:00) comes 4 minutes into the walk and the partner sleeps on the path
tools/dev/game_state.py set gametime_running=0 hour=10 >/dev/null 2>&1
tools/dev/emulator.py record "$PWD/$W/$NAME-raw.mp4" "$SEC" > "$W/$NAME-record.log" 2>&1 &
REC=$!
sleep 2
timeout $((SEC - 15)) $PY tools/dev/walk/tour.py "$TOUR" > "$W/$NAME-tour.log" 2>&1
TOUR_STATUS=$?
echo "tour exit $TOUR_STATUS" >> "$W/$NAME-tour.log"
python3 -c "
import sys; sys.path.insert(0, 'tools'); from tools.dev import emulator as emu
for b in emu.BUTTONS: emu.api(f'/api/v1/lua/release?button={b}')"
wait $REC
cp "$TOUR.poslog.json" "$W/$NAME-poslog.json"
ARGS=""
for f in $(python3 -c "import json; t=json.load(open('$TOUR')); print(' '.join(f'{s}={m}' for s, m, _ in t))"); do
  S=${f%%=*}; M=${f#*=}; B=$(basename "$M" .MAP); Z=$(ls "$ZONES"/*/"$B"-zones.png 2>/dev/null | head -1)
  [ -n "$Z" ] && ARGS="$ARGS $S=$M,$Z"
done
$PY tools/dev/walk/overlay_video.py "$W/$NAME-raw.mp4" "$W/$NAME-poslog.json" 1.0:2.0 "$W/$NAME.mp4" $ARGS --step 3 > "$W/$NAME-overlay.log" 2>&1
grep -E '^==|left|False|tour exit' "$W/$NAME-tour.log"
ls -la "$W/$NAME.mp4" | awk '{print $5, $9}'
tools/dev/game_state.py show tamer.state game_state current_screen tamer.location 2>/dev/null | grep -v dwsyms | tr '\n' ' '; echo

exit "$TOUR_STATUS"
