# check.sh DISC ELF PORT CARD OUTPREFIX [card2]: Continue from CARD (slot 1); prints screen, money, partner type, story var 0
# and flag 0 (expanded story), the error index and the menu. Addresses from ELF.
set -uo pipefail
T=$(cd "$(dirname "$0")" && pwd); cd "$T/../../.."
. "$T/symbols.sh"
DISC=$1; ELF=$2; export EMU_PORT=$3; CARD=$4; O=$5
pk() { tools/dev/emulator.py peek "$(sym "$ELF" "$1")" "$2" | cut -d' ' -f2- | tr -d ' '; }
cp "$CARD" "$O.run.mcd"
tools/dev/emulator.py start "$DISC" --card "$O.run.mcd" >/dev/null
tools/dev/emulator.py seq tools/dev/sequences/continue.seq >/dev/null; tools/dev/emulator.py wait 8
tools/dev/emulator.py shot "$O.png" >/dev/null
x="screen=$(pk CURRENT_SCREEN 2) money=$(pk MONEY 4) type=$(pk PARTNER_ENTITY 4) err=$(pk MEMORY_CARD_ERROR 4) menu=$(pk CURRENT_MENU 4)"
[ "$(nm "$ELF" | grep -c STORY_VAR_VALUES)" != 0 ] && x="$x var0=$(pk STORY_VAR_VALUES 4) flag0=$(pk STORY_FLAG_BITS 1)"
echo "$(basename "$O"): $x"
tools/dev/emulator.py stop >/dev/null
