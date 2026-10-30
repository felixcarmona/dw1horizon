# sleepsave.sh DISC ELF PORT CARD OUTDIR SCREEN: continue, warp to SCREEN (6/8: the fishing overlay FISH is resident),
# start the partner's sleep (PARTNER_STATE 3, as the game menu's Sleep), answer the save prompt, check the card and the
# overlay bytes, then continue from the saved card.
set -uo pipefail
T=$(cd "$(dirname "$0")" && pwd); cd "$T/../../.."
. $T/symbols.sh
DISC=$1; ELF=$2; export EMU_PORT=$3; IN=$4; E=$5; SCR=$6; mkdir -p $E
H=${EMU_HOME:-$PWD/.tools/emu/home-$EMU_PORT}
emu() { tools/dev/emulator.py "$@" >/dev/null; }; gs() { python3 tools/dev/game_state.py "$@"; }
pk() { tools/dev/emulator.py peek $(sym $ELF $1) $2 | cut -d' ' -f2- | tr -d ' '; }
cp $IN $E/in.mcd
emu start $DISC --card $E/in.mcd; emu seq tools/dev/sequences/continue.seq; emu wait 8
echo "build $(python3 -c "import json;print(json.load(open('build/emu-$EMU_PORT.json')).get('build'))")"
for t in 1 2; do for i in 1 2 3; do emu press TRIANGLE 4; emu wait 1; done
  gs warp $SCR 0 | tail -n 1; emu wait 14; [ "$(pk CURRENT_SCREEN 2)" = "$(printf '%02x00' $SCR)" ] && break; done
echo "screen $(pk CURRENT_SCREEN 2) fish_ptr $(pk FISHING_DATA_PTR 4)"; emu shot $E/1-screen.png
tools/dev/emulator.py peek 0x80070000 4096 | md5sum | cut -c1-12 > $E/ovl-before
emu poke $(sym $ELF PARTNER_SUB_STATE) 00; emu poke $(sym $ELF PARTNER_STATE) 03
for i in $(seq 1 30); do emu wait 1; [ "$(pk CURRENT_MENU 4)" = 28000000 ] && break; [ $i = 15 ] && emu poke $(sym $ELF PARTNER_SUB_STATE) 00 && emu poke $(sym $ELF PARTNER_STATE) 03; done
echo "menu $(pk CURRENT_MENU 4) after ${i} s"; emu shot $E/2-prompt.png; emu press DOWN 4; emu wait 1; emu shot $E/2b-save-and-go.png
for i in $(seq 1 12); do m=$(pk CURRENT_MENU 4); [ "$m" = ffffffff ] && break; emu press CROSS 4; emu wait 2; done
emu shot $E/3-after.png; echo "menu $(pk CURRENT_MENU 4) err $(pk MEMORY_CARD_ERROR 4)"
echo "overlay bytes same: $( [ "$(tools/dev/emulator.py peek 0x80070000 4096 | md5sum | cut -c1-12)" = "$(cat $E/ovl-before)" ] && echo yes || echo NO) fish_ptr $(pk FISHING_DATA_PTR 4)"
emu wait 6; emu shot $E/4-woke.png; echo "screen $(pk CURRENT_SCREEN 2) state $(pk PARTNER_STATE 1)"
emu stop; cp $H/memcard1.mcd $E/out.mcd
python3 tools/dev/memory_card.py save $E/out.mcd | grep -oE "bytes: [0-9]+|'screen': [0-9]+|'checksum_ok': [A-Za-z]+, 'refuses_original': [A-Za-z]+|'version': [0-9], 'size': [0-9]+, 'checksum_ok': [A-Za-z]+, 'matches_v1': [A-Za-z]+" | tr '\n' ' '; echo
bash $T/check.sh $DISC $ELF $EMU_PORT $E/out.mcd $E/5-continued
