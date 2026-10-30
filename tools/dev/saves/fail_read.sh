# fail_read.sh DISC ELF PORT CARD OUTDIR NTH...: Continue from CARD with MemCardReadFile call NTH failing to start
# (one run per NTH; 99 = none, logs the calls). The title is driven to "Continue adventure?" without the debugger,
# saved as a state, then reloaded with it.
set -uo pipefail
T=$(cd "$(dirname "$0")" && pwd); cd "$T/../../.."
. $T/symbols.sh
DISC=$1; ELF=$2; export EMU_PORT=$3; CARD=$4; E=$5; shift 5; mkdir -p $E
emu() { tools/dev/emulator.py "$@" >/dev/null; }
pk() { tools/dev/emulator.py peek $(sym $ELF $1) $2 | cut -d' ' -f2- | tr -d ' '; }
cp $CARD $E/in.mcd
emu start $DISC --card $E/in.mcd
emu seq "wait 45, START 20, wait 6, START 20, wait 6, DOWN 8, wait 1, CROSS 10, wait 5, CROSS 10, wait 5, CROSS 10, wait 4"
emu shot $E/0-prompt.png; tools/dev/emulator.py save $E/prompt.state >/dev/null; emu stop
for N in "$@"; do
  cp $CARD $E/in.mcd
  EMU_ARGS="-interpreter -debugger" tools/dev/emulator.py start $DISC --card $E/in.mcd >/dev/null; emu load $E/prompt.state
  tools/dev/emulator.py lua "dofile('$T/cut.lua'); return CUT.fail($(sym $ELF MemCardReadFile), $N)" >/dev/null
  emu press CROSS 10; for k in 1 2 3 4; do emu wait 0.7; emu shot $E/fail-$N-$k.png; done; emu wait 7
  echo "fail $N: menu $(pk CURRENT_MENU 4) error $(pk MEMORY_CARD_ERROR 4) screen $(pk CURRENT_SCREEN 2) money $(pk MONEY 4) | $(tools/dev/emulator.py lua 'return CUT.report()' | tr '\n' ' ')"
  emu stop
done
