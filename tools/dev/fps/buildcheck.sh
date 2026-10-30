#!/bin/bash
# buildcheck.sh FPS [OUT]: proof that a disc built with FPS=20|30|60 presents that frame rate
# with the logic at 20 Hz (docs/developing.md).
# DuckStation (tools/dev/duckstation.py) at 300 % CPU, so every pass the build asks for fits; GDB stub on
# DS_GDB_PORT (default here 38201). Disc: DISC (default build/frame-rate-$FPS.cue) and its linker map
# (DS_MAP, default build/frame-rate-$FPS/exe/SLUS_010.32.elf.map, from tools/build-full.sh frame-rate-$FPS).
# Card: DuckStation's memcards/file-city.mcd (a copy of build/states/file-city.mcd).
# Steps: boot (intro movie skipped), title -> CONTINUE GAME -> Jijimon's house; lab menu screenshot;
# then 10 s measurements (duckstation.py measure: presented frames and logic ticks per 60 vblanks) in the
# house, walking in Native Forest (screen 0), and in a battle there. Screenshots go to OUT
# (default build/dev/fps/build-check): menu, lab, house, forest, battle, prefixed with ds$FPS-.
set -u
cd "$(dirname "$0")/../../.."
F=$1; O=${2:-build/dev/fps/build-check}; mkdir -p "$O"
export DS_GDB_PORT=${DS_GDB_PORT:-38201}
export DS_MAP=${DS_MAP:-$PWD/build/frame-rate-$F/exe/SLUS_010.32.elf.map}
DISC=${DISC:-build/frame-rate-$F.cue}
D=tools/dev/duckstation.py; T=$O/duckstation-$F
$D stop >/dev/null 2>&1
$D start "$DISC" --oc 300 >/dev/null
sleep 30; $D press START 20; sleep 5; $D shot $T-menu.png        # the title menu, cursor on NEW GAME
$D press DOWN 3; sleep 1.5                                         # CONTINUE GAME (a short press: no key repeat)
$D seq "CROSS 6, wait 5, CROSS 6, wait 5, CROSS 6, wait 4, CROSS 6, wait 14"
echo "screen $($D peek CURRENT_SCREEN 2) (da00 = 218, the house)  MOD_FPS_BUILD $($D peek MOD_FPS_BUILD 4) (14/1e/3c000000 = 20/30/60)"
# the lab menu: pause, SELECT, screenshot, close, unpause
# (20-frame presses: shorter ones are sometimes missed in the world)
for i in 1 2 3 4; do $D press START 20; sleep 2; [ "$($D peek PAUSE_STATE 1)" = 01 ] && break; done
$D press SELECT 20; sleep 2.5; $D shot $T-lab.png
$D press TRIANGLE 20; sleep 2
for i in 1 2 3 4; do [ "$($D peek PAUSE_STATE 1)" = 00 ] && break; $D press START 20; sleep 2; done
echo "pause $($D peek PAUSE_STATE 1) (00 = unpaused)"
sleep 4; echo "house:  $($D measure 10)"; $D shot $T-house.png
$D warp 0 0 >/dev/null; sleep 8; echo "screen $($D peek CURRENT_SCREEN 2) (0000 = Native Forest)"
($D press RIGHT 120; $D press LEFT 120; $D press RIGHT 120) &
echo "forest: $($D measure 10)"; wait; $D shot $T-forest.png
$D approach 0 150 >/dev/null; sleep 4
for i in 1 2 3 4 5 6 7 8; do [ "$($D peek GAME_STATE 1)" = 01 ] && break; $D press CROSS 6; sleep 2; done
sleep 6; echo "game_state $($D peek GAME_STATE 1) (01 = battle)"
echo "battle: $($D measure 10)"; $D shot $T-battle.png
$D stop >/dev/null
