# power_cut.sh DISC ELF PORT CARD STATE OUT NTH VS: from STATE (the save's last confirm, CARD inserted) press CROSS; the
# write is cut on MemCardWriteFile call NTH after VS vsyncs (NTH 99: never); the emulator is then killed (power cut)
# and its card copied to OUT.mcd; the part log goes to OUT.log.
set -uo pipefail
T=$(cd "$(dirname "$0")" && pwd); cd "$T/../../.."
DISC=$1; ELF=$2; export EMU_PORT=$3; CARD=$4; STATE=$5; OUT=$6; NTH=$7; VS=$8
H=${EMU_HOME:-$PWD/.tools/emu/home-$EMU_PORT}; A=0x$(nm $ELF | awk '$3=="MemCardWriteFile"{print $1}')
cp $CARD $OUT.in.mcd
tools/dev/emulator.py start $DISC --card $OUT.in.mcd >/dev/null
tools/dev/emulator.py load $STATE >/dev/null
tools/dev/emulator.py lua "dofile('$T/cut.lua'); return CUT.arm($A, $NTH, $VS)" >/dev/null
tools/dev/emulator.py press CROSS 4 >/dev/null
for i in $(seq 1 40); do sleep 0.5; p=$(tools/dev/emulator.py lua "return tostring(CUT.paused)"); [ "$p" = true ] && break; done
tools/dev/emulator.py lua "return CUT.report()" > $OUT.log
cp $H/memcard1.mcd $OUT.paused.mcd
st=$(python3 -c "import json;print(json.load(open('build/emu-$EMU_PORT.json'))['pid'])"); kill -9 $st; sleep 1; tools/dev/emulator.py stop >/dev/null 2>&1
cp $H/memcard1.mcd $OUT.mcd
cmp -s $OUT.paused.mcd $OUT.mcd && echo "same on disk at the pause and after the kill" >> $OUT.log || echo "disk changed after the pause" >> $OUT.log
