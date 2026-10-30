# power_cuts.sh DISC ELF OLDCARD STATE OUTDIR NPORTS BASEPORT "nth vs" ...: cut the save at each point, in parallel
T=$(cd "$(dirname "$0")" && pwd)
DISC=$1; ELF=$2; OLD=$3; ST=$4; D=$5; N=$6; B=$7; shift 7
mkdir -p $D; : > $D/jobs
for c in "$@"; do set -- $c; echo "EMU_ARGS=\"-interpreter -debugger\" bash $T/power_cut.sh $DISC $ELF PORT $OLD $ST $D/p$1v$2 $1 $2" >> $D/jobs; done
unset EMU_ARGS; bash $T/batch.sh $D/jobs $N $B >/dev/null 2>&1
