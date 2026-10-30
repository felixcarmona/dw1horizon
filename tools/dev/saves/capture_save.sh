# capture_save.sh DISC ELF PORT CARD_IN OUT_DIR MONEY_HEX8 [POKES] [state]: continue, poke, save at Jijimon (dev-save script:
# the battle registration, menu 0x3E, or the save prompt 0x45 -> 0x3F-0x41 the write). Addresses from ELF (nm).
# POKES: "SYMBOL[+OFF] HEX;..." extra pokes. With "state": stop at the last confirm and write OUT_DIR/confirm.state.
set -uo pipefail
T=$(cd "$(dirname "$0")" && pwd); cd "$T/../../.."
. $T/symbols.sh
DISC=$1; ELF=$2; export EMU_PORT=$3; IN=$4; E=$5; MONEY=$6; POKES=${7:-}; MODE=${8:-}
mkdir -p $E; H=${EMU_HOME:-$PWD/.tools/emu/home-$EMU_PORT}
emu() { tools/dev/emulator.py "$@" >/dev/null; }
menu() { tools/dev/emulator.py peek $(sym $ELF CURRENT_MENU) 4 | awk '{print $2 $3 $4 $5}'; }
cp $IN $E/in.mcd
emu start $DISC --card $E/in.mcd; emu seq tools/dev/sequences/continue.seq; emu wait ${MKWAIT:-8}
echo "screen $(tools/dev/emulator.py peek $(sym $ELF CURRENT_SCREEN) 2 | cut -d' ' -f2-)"
emu poke $(sym $ELF MONEY) $MONEY
IFS=';' read -ra PK <<< "$POKES"; for p in "${PK[@]}"; do [ -n "$p" ] && emu poke $(sym $ELF ${p% *}) ${p#* }; done
python3 tools/dev/game_state.py approach 0 | tail -n 1; emu wait 1; emu press CROSS 4; emu wait 3
for i in 1 2 3 4 5 6; do m=$(menu); [ "$m" = 3e000000 -o "$m" = 45000000 ] && break; emu press CROSS 4; emu wait 2; done
echo "menu $(menu)"; emu shot $E/confirm.png
if [ "$MODE" = state ]; then tools/dev/emulator.py save $E/confirm.state >/dev/null; emu stop; exit 0; fi
emu press CROSS 4
for i in $(seq 1 30); do emu wait 1; [ "$(menu)" = ffffffff ] && break; done
echo "menu after $(menu) (${i} s)"; emu wait 2; emu shot $E/saved.png
emu stop; cp $H/memcard1.mcd $E/out.mcd
python3 tools/dev/memory_card.py ls $E/out.mcd | head -1
python3 tools/dev/memory_card.py save $E/out.mcd | grep -oE "bytes: [0-9]+|'checksum_ok': [A-Za-z]+, 'refuses_original': [A-Za-z]+|'version': [0-9], 'size': [0-9]+, 'checksum_ok': [A-Za-z]+, 'matches_v1': [A-Za-z]+|'money': [0-9]+|'partnerType': [0-9]+" | tr '\n' ' '; echo
