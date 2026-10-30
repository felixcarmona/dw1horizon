#!/usr/bin/env bash
# continue.sh DISC.cue CARD.mcd: starts the emulator on DISC with CARD and loads the save (tools/dev/sequences/continue.seq),
# then checks the game really is in the world in Jijimon's house (screen 218, tamer free). The menu presses
# can be missed (a slow disc, a busy machine): the run then stays on the title or the memory card slot screen,
# so the whole start is repeated, up to 4 times. Exit 0 = in the world. EMU_PORT as for emulator.py. GS_MAP=FILE names the
# disc's symbol map explicitly (tools/dev/playtest/game_state_with_map.py): needed when several builds share the code start.
cd "$(dirname "$0")/../.." || exit 2
[ $# -eq 2 ] || { echo "usage: tools/dev/continue.sh DISC.cue CARD.mcd" >&2; exit 2; }
GS=tools/dev/game_state.py; [ -n "${GS_MAP:-}" ] && GS=tools/dev/playtest/game_state_with_map.py
for try in 1 2 3 4; do
  python3 tools/dev/emulator.py stop >/dev/null 2>&1
  python3 tools/dev/emulator.py start "$1" --card "$2" >/dev/null || exit 2
  python3 tools/dev/emulator.py seq tools/dev/sequences/continue.seq >/dev/null
  for w in 1 2 3 4 5 6; do   # the last "Yes" may still be loading
    s=$(python3 $GS show current_screen tamer.state 2>/dev/null | awk '{printf "%s ", $2}')
    [ "$s" = "218 0 " ] && exit 0
    python3 tools/dev/emulator.py wait 5 >/dev/null
  done
  echo "continue.sh: try $try ended at screen/tamer.state '$s', starting again" >&2
done
exit 1
