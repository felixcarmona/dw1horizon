#!/bin/bash
# Record the supplied screen tours, one after another, on a fresh emulator.
#   tools/dev/walk/walkall.sh [WALKS="name:tour.json:first_screen:first_exit:seconds ..."] [EMU_PORT=...]   -> build/new-maps/walks/NAME.mp4
set -o pipefail
: "${WALKS:?Set WALKS=name:tour.json:screen:exit:seconds ...}"
DISC=${DISC:-build/what-the-island-forgot.cue}
CARD=${CARD:-build/states/file-city.mcd}
cd "$(dirname "$0")/../../.." || exit 1
export EMU_PORT=${EMU_PORT:-38331} DW_SYMS=${DW_SYMS:-disc-what-the-island-forgot}
T=tools/dev/walk; W=build/new-maps/walks; R=${TOURS:-build/new-maps/tours}
tools/dev/emulator.py stop >/dev/null 2>&1; sleep 2
tools/dev/emulator.py start "$DISC" --card "$CARD" || exit 1
tools/dev/emulator.py wait 45; tools/dev/emulator.py seq tools/dev/sequences/continue.seq >/dev/null; tools/dev/emulator.py wait 20
for i in $(seq 1 20); do   # CROSS until the world runs with control
  ST=$(tools/dev/game_state.py show tamer.state game_state script_paused current_screen 2>/dev/null | grep -v dwsyms | awk '{print $2}' | tr '\n' ' ')
  case "$ST" in "0 0 1 "*) [ "${ST##* }" != "0" ] && break ;; esac
  tools/dev/emulator.py press CROSS 10 >/dev/null; sleep 3
done
echo "world: $ST"
run() {  # NAME TOUR FIRST_SCREEN FIRST_EXIT SEC
  echo "== walk $1 ($(date +%H:%M))"; $T/walk.sh "$1" "$R/$2" "$3" "$4" "$5" 2>&1 | tail -4
  local status=${PIPESTATUS[0]}
  [ "$status" = 0 ] || return "$status"
  f=$W/$1.mp4; [ -f "$f" ] || { echo "no video for $1"; return; }

}

OUT=""
STATUS=0
for w in $WALKS; do
  IFS=: read -r n t s e sec <<< "$w"
  if run "$n" "$t" "$s" "$e" "$sec"; then
    [ -f "$W/$n.mp4" ] && OUT="$OUT $W/$n.mp4"
  else
    STATUS=$?
  fi
done
tools/dev/emulator.py stop
ls -la $OUT 2>/dev/null | awk '{print $5, $9}'

exit "$STATUS"
