# capture_expanded_state.sh DISC ELF PORT CARD_IN OUT_DIR: expanded-story engine, the disc of tools/dws/examples/expanded-state.dws: Continue
# from CARD_IN, entering Jijimon's house sets the story flags and variables and opens the save machine; confirm the save, copy the
# card to OUT_DIR/out.mcd and print its records (memory_card.py save).
set -uo pipefail
T=$(cd "$(dirname "$0")" && pwd); cd "$T/../../.."
. $T/symbols.sh
DISC=$1; ELF=$2; export EMU_PORT=$3; IN=$4; E=$5
mkdir -p $E; H=${EMU_HOME:-$PWD/.tools/emu/home-$EMU_PORT}
emu() { tools/dev/emulator.py "$@" >/dev/null; }
menu() { tools/dev/emulator.py peek $(sym $ELF CURRENT_MENU) 4 | awk '{print $2 $3 $4 $5}'; }
cp $IN $E/in.mcd
emu start $DISC --card $E/in.mcd; emu seq tools/dev/sequences/continue.seq; emu wait 4
for i in 1 2 3 4 5 6 7 8; do m=$(menu); [ "$m" = 3e000000 -o "$m" = 45000000 ] && break; emu press CROSS 4; emu wait 2; done
echo "menu $(menu)"; emu shot $E/confirm.png
emu press CROSS 4
for i in $(seq 1 30); do emu wait 1; [ "$(menu)" = ffffffff ] && break; done
echo "menu after $(menu) (${i} s)"; emu wait 2; emu shot $E/saved.png
emu stop; cp $H/memcard1.mcd $E/out.mcd
python3 tools/dev/memory_card.py ls $E/out.mcd | head -1
python3 tools/dev/memory_card.py save $E/out.mcd | grep -E "ext0|copy0" | cut -c1-600
