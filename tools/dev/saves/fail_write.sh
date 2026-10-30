# fail_write.sh DISC ELF PORT CARD STATE OUTDIR NTH: from STATE (the save's last confirm) press CROSS with write part NTH
# failing to start; shows the error box, answers the retry, then continues from the card.
set -uo pipefail
T=$(cd "$(dirname "$0")" && pwd); cd "$T/../../.."
. $T/symbols.sh
DISC=$1; ELF=$2; export EMU_PORT=$3; CARD=$4; ST=$5; E=$6; NTH=$7; mkdir -p $E
H=${EMU_HOME:-$PWD/.tools/emu/home-$EMU_PORT}
emu() { tools/dev/emulator.py "$@" >/dev/null; }
pk() { tools/dev/emulator.py peek $(sym $ELF $1) $2 | cut -d' ' -f2- | tr -d ' '; }
cp $CARD $E/in.mcd
EMU_ARGS="-interpreter -debugger" tools/dev/emulator.py start $DISC --card $E/in.mcd >/dev/null
emu load $ST
tools/dev/emulator.py lua "dofile('$T/cut.lua'); return CUT.fail($(sym $ELF MemCardWriteFile), $NTH)" >/dev/null
emu press CROSS 4
for i in $(seq 1 30); do emu wait 1; [ "$(pk CURRENT_MENU 4)" = 03000000 ] && break; done
emu wait 1; emu shot $E/1-error.png; echo "menu $(pk CURRENT_MENU 4) error $(pk MEMORY_CARD_ERROR 4) after ${i} s"
cp $H/memcard1.mcd $E/failed.mcd
for i in $(seq 1 12); do m=$(pk CURRENT_MENU 4); [ "$m" = ffffffff ] && break; emu press CROSS 4; emu wait 3; emu shot $E/2-retry-$i.png; done
echo "menu $(pk CURRENT_MENU 4) after the retry"; tools/dev/emulator.py lua "return CUT.report()"
emu stop; cp $H/memcard1.mcd $E/retried.mcd
