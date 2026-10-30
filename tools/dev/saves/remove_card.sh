#!/usr/bin/env bash
# remove_card.sh DISC ELF PORT CARD OUT [POKES]: Continue from CARD after poking the tables that a deleted species, item or
# technique leaves empty (POKES: "SYMBOL[+OFF] HEX;..."), and prints the partner's type, equipped moves, learned bits and
# the first inventory types as the game loaded them (patch 0113, dropAbsentSaveContent).
set -uo pipefail
T=$(cd "$(dirname "$0")" && pwd); cd "$T/../../.."
. $T/symbols.sh
DISC=$1; ELF=$2; export EMU_PORT=$3; CARD=$4; O=$5; POKES=${6:-}
pk() { tools/dev/emulator.py peek $(sym $ELF $1) $2 | cut -d' ' -f2- | tr -d ' '; }
cp $CARD $O.run.mcd
tools/dev/emulator.py start $DISC --card $O.run.mcd >/dev/null; for i in $(seq 1 60); do tools/dev/emulator.py wait 2 >/dev/null; [ "$(pk DIGIMON_DATA 4)" != 00000000 ] && break; done   # the executable is loaded
IFS=';' read -ra PK <<< "$POKES"; for p in "${PK[@]}"; do [ -n "$p" ] && tools/dev/emulator.py poke $(sym $ELF ${p% *}) ${p#* } >/dev/null; done
tools/dev/emulator.py seq tools/dev/sequences/continue.seq >/dev/null; tools/dev/emulator.py wait 8 >/dev/null
tools/dev/emulator.py shot $O.png >/dev/null
echo "$(basename $O): screen=$(pk CURRENT_SCREEN 2) type=$(pk PARTNER_ENTITY 4) stats=$(pk PARTNER_ENTITY+0x38 32) learned=$(pk PARTNER_ENTITY+0x58 16) inv=$(pk INVENTORY 12) amt=$(pk INVENTORY+0x78 4) row2=$(pk MOVE_DATA+32 16) reg0=$(pk SAVE_FILE+0x51C 4) reg1=$(pk SAVE_FILE+0x55C 4) reg0b=$(pk SAVE_FILE+0x71C 4) reg1b=$(pk SAVE_FILE+0x75C 4) menu=$(pk CURRENT_MENU 4)"
tools/dev/emulator.py stop >/dev/null
