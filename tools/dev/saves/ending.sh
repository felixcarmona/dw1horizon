# ending.sh DISC ELF PORT CARD OUTDIR: continue, warp to File City (236), run script 192 section 51 (the game clear:
# load_ending, the talk, game_clear_save, start_ending), answer the save prompt, log the sound bank, check the card.
set -uo pipefail
T=$(cd "$(dirname "$0")" && pwd); cd "$T/../../.."
. $T/symbols.sh
DISC=$1; ELF=$2; export EMU_PORT=$3; IN=$4; E=$5; mkdir -p $E
H=${EMU_HOME:-$PWD/.tools/emu/home-$EMU_PORT}
emu() { tools/dev/emulator.py "$@" >/dev/null; }; gs() { python3 tools/dev/game_state.py "$@"; }
pk() { tools/dev/emulator.py peek $(sym $ELF $1) $2 | cut -d' ' -f2- | tr -d ' '; }
cp $IN $E/in.mcd
emu start $DISC --card $E/in.mcd; emu seq tools/dev/sequences/continue.seq; emu wait 8
for t in 1 2; do for i in 1 2 3; do emu press TRIANGLE 4; emu wait 1; done
  gs warp 236 0 | tail -n 1; emu wait 14; [ "$(pk CURRENT_SCREEN 2)" = ec00 ] && break; done
echo "screen $(pk CURRENT_SCREEN 2)"; emu shot $E/1-filecity.png; tools/dev/emulator.py save $E/filecity.state >/dev/null; emu stop
EMU_ARGS="-interpreter -debugger" tools/dev/emulator.py start $DISC --card $E/in.mcd >/dev/null; emu load $E/filecity.state
tools/dev/emulator.py lua "dofile('$T/ending.lua'); return EN.arm({gameLoop=$(sym $ELF gameLoop), css=$(sym $ELF callScriptSection), lms2=$(sym $ELF loadMapSounds2), gcs=$(sym $ELF gameClearSave), sfs=$(sym $ELF saveFileStart), sb=$(sym $ELF SOUND_BUFFERS)}, 192, 51, 1)"
for i in $(seq 1 90); do m=$(pk CURRENT_MENU 4); [ "$m" = 45000000 ] && break; emu press CROSS 4; emu wait 2; done
echo "menu $m after $i presses"; emu shot $E/2-prompt.png
emu press CROSS 4; for i in $(seq 1 40); do emu wait 1; [ "$(pk CURRENT_MENU 4)" = ffffffff ] && break; done
echo "menu $(pk CURRENT_MENU 4) err $(pk MEMORY_CARD_ERROR 4)"; emu shot $E/3-saved.png
for i in 1 2 3 4 5 6; do emu press CROSS 4; emu wait 2; done; emu wait 10; emu shot $E/4-ending.png
tools/dev/emulator.py lua "return EN.report()"
emu stop; cp $H/memcard1.mcd $E/out.mcd
python3 tools/dev/memory_card.py save $E/out.mcd | grep -oE "bytes: [0-9]+|'screen': [0-9]+|'checksum_ok': [A-Za-z]+, 'refuses_original': [A-Za-z]+|'version': [0-9], 'size': [0-9]+, 'checksum_ok': [A-Za-z]+, 'matches_v1': [A-Za-z]+" | tr '\n' ' '; echo
bash $T/check.sh $DISC $ELF $EMU_PORT $E/out.mcd $E/5-continued
