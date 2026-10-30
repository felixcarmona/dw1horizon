#!/usr/bin/env bash
# screens.sh: patches 0146 (screens beyond 255) and 0147 (new file names) end to end in the emulator, on screens 300 and
# 301 (tools/dev/playtest/screens/: their screen files, their maps made from your disc with new names HOLW01 and HOLW02, their
# story). About 5 minutes.
#   1. builds build/scr300.cue (tools/build-full.sh scr300 with SCREEN_CONTENT = the maps' folder, where maps.py copies the
#      screen files beside HOLW01.MAP/.TFS and HOLW02.MAP/.TFS; EXTRA_STORY; EXTRA_FILES); NO_BUILD=1 skips it
#   2. card start (build/states/file-city.mcd) in Jijimon's house; talking to Tokomon warps to screen 300 (WARP_TO16)
#   3. walks out of 300 through its west exit (to screen 0) and back in (screen 0's west exit now leads to 300: the caption
#      "Test Hollow" is the record's own)
#   4. a wild battle on 300 (RedVegiemon, slot 2), won by setting its HP to 0; back on 300 after it
#   5. walks 300 -> 301 (300's east exit), 301 -> 300 (301's west exit) and 300 -> 301 again: two new screens, each with
#      its own new files, on one disc
#   6. saves on 301 (its RedVegiemon by day, Dokunemon by night, opens the save machine) and reloads the card in a fresh emulator: screen 301 again,
#      and the poop the partner left (WORLD_POOP, when it pooped) is still on its screen
#   tools/dev/playtest/screens.sh            VIDEO=1 records build/scr300/t/proof-*.mp4 for the media gateway (VIDEO=walk: only the
#                                        walk 300 -> 301 -> 300 -> 301)
set -u
cd "$(dirname "$0")/../../.."
export EMU_PORT=${EMU_PORT:-38311} DW_SYMS=${DW_SYMS:-disc-full}
O=build/scr300; T=$O/t; M=$O/maps; mkdir -p "$T"
if [ "${NO_BUILD:-0}" != 1 ]; then
  python3 tools/dev/playtest/screens/maps.py "$M" >/dev/null
  SCREEN_CONTENT=$M EXTRA_STORY=tools/dev/playtest/screens/screen-300.dws REUSE_MODELS=1 \
    EXTRA_FILES="MAP/MAP1/MAYO01.MAP=$M/MAYO01.MAP" \
    tools/build-full.sh scr300 > "$T/build.log" 2>&1 || { tail -20 "$T/build.log"; exit 1; }
  python3 tools/screens.py show $O/SCRN.DAT
fi
emu() { tools/dev/emulator.py "$@" >/dev/null; }
gs() { python3 tools/dev/game_state.py "$@" 2>/dev/null | tail -1; }
screen() { gs show current_screen | awk '{print $2}'; }
ok() { if [ "$2" = "$3" ]; then echo "ok  $1 ($2)"; else echo "BAD $1: got $2, expected $3"; FAIL=1; fi; }
rec() {   # VIDEO=1 records every segment, VIDEO="walk reload" those (recording slows the emulator: the battle's HP loop may miss)
  case " ${VIDEO:-0} " in *" 1 "*|*" $1 "*) tools/dev/emulator.py record "$T/proof-$1.mp4" "$2" >/dev/null & ;; esac
}
menu() { tools/dev/emulator.py peek CURRENT_MENU 4 | awk '{print $2 $3 $4 $5}'; }
FAIL=0
cp build/states/file-city.mcd "$T/a.mcd"
emu start $O.cue --card "$T/a.mcd"; emu seq tools/dev/sequences/continue.seq; emu seq 'until CURRENT_SCREEN 2 218 CROSS 40, wait 8'
ok "card start in Jijimon's house" "$(screen)" 218
rec warp 14
for i in 1 2 3; do gs approach 1 >/dev/null; emu press CROSS 6; emu wait 10; [ "$(screen)" = 300 ] && break; done; wait
ok "talk to Tokomon: WARP_TO16 300" "$(screen)" 300
rec exits 24; gs move -3600 557 >/dev/null; emu press LEFT 90; emu wait 8
ok "west exit of 300 -> screen 0" "$(screen)" 0
emu press LEFT 60; emu wait 8; wait
ok "west exit of screen 0 -> 300" "$(screen)" 300
rec battle 50; gs approach 2 >/dev/null; emu press CROSS 6
for i in $(seq 1 25); do                                     # its talk, the fight (its HP set to 0), the result boxes
  python3 tools/dev/memory_inspector.py set 'NPC_ENTITIES[2].digimonEntity.stats.current.currentHP=0' >/dev/null 2>&1
  [ "$(gs show money | awk '{print $2}')" = 500 ] && break; emu press CROSS 6; emu wait 2
done
for i in 1 2 3; do emu press CROSS 6; emu wait 2; done; emu wait 4; wait
ok "after the battle, still on" "$(screen)" 300
ok "bits won" "$(gs show money | awk '{print $2}')" 500
gs warp 300 2 >/dev/null; emu wait 8                       # the Digimon that did not fight left the map: enter again
ok "game_state.py warp 300 2" "$(screen)" 300
gs trigger 232 1 >/dev/null     # 301's MAPHEAD section (Kunemon's Bed's) then places a Digimon that can be talked to
rec walk 40; gs move 2810 -2609 >/dev/null; emu press RIGHT 60; emu wait 8   # 300's exit 3 spawn, then east into its exit
ok "east exit of 300 -> screen 301 (HOLW02)" "$(screen)" 301
emu press LEFT 40; emu wait 8                               # 301's exit 0 spawn faces west, its exit is just behind
ok "west exit of 301 -> screen 300 (HOLW01)" "$(screen)" 300
emu press RIGHT 40; emu wait 8; wait
ok "east exit of 300 -> screen 301 again" "$(screen)" 301
SAVER=0; [ "$(python3 tools/dev/memory_inspector.py show 'ENTITY_TABLE[2]' 2>/dev/null | tail -1 | awk '{print $3}')" = 0x00000000 ] && SAVER=3
echo "    the saver on 301: slot $SAVER ($([ $SAVER = 0 ] && echo 'RedVegiemon, day' || echo 'Dokunemon, night'))"
emu press DOWN 4; emu wait 2
for i in 1 2 3 4 5; do       # just after the arrival the game still places the player itself: approach again until it holds
  gs approach $SAVER >/dev/null; emu wait 1; emu press CROSS 6; emu wait 4; [ "$(menu)" != ffffffff ] && break
done; emu shot "$T/talk301.png"
echo "    menu after the talk: $(menu)"
for i in $(seq 1 10); do [ "$(menu)" != ffffffff ] && break; emu wait 1; done          # the save machine opens (menu 0x3D)
for i in $(seq 1 12); do [ "$(menu)" = ffffffff ] && break; emu press CROSS 4; emu wait 3; done   # registration, Yes, the write
emu wait 3; emu stop; cp "${EMU_HOME:-$PWD/.tools/emu/home-$EMU_PORT}/memcard1.mcd" "$T/saved301.mcd"
python3 tools/dev/memory_card.py save "$T/saved301.mcd" | grep -oE "screens': \[[0-9, -]+\]" | head -1
cp "$T/saved301.mcd" "$T/b.mcd"
emu start $O.cue --card "$T/b.mcd"; rec reload 100; emu seq tools/dev/sequences/continue.seq; emu seq "until CURRENT_SCREEN 2 301 NONE 20"; emu wait 3; wait
ok "the card reloads on" "$(screen)" 301
echo "    WORLD_POOP[0].map = $(python3 tools/dev/memory_inspector.py show 'WORLD_POOP[0].map' 2>/dev/null | tail -1 | awk '{print $3}') (300 or 301 when the partner pooped there)"
emu shot "$T/reloaded.png"; emu stop
[ $FAIL = 0 ] && echo "screens.sh: all checks passed" || { echo "screens.sh: FAILED"; exit 1; }
