# batch.sh JOBFILE NPORTS BASEPORT: runs the lines of JOBFILE (shell commands with the word PORT) on NPORTS emulator ports
J=$1; N=$2; B=$3
for k in $(seq 0 $((N - 1))); do
  ( awk -v n=$N -v k=$k 'NR % n == k' $J | while read -r line; do eval "${line//PORT/$((B + k))}"; done ) &
done; wait
