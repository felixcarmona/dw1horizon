#!/usr/bin/env bash
# new_game_start.sh: patch 0143 in the emulator (disc build/full.cue). A real new game from the title screen (tools/dev/sequences/new-game.seq: the Jijimon scene,
# names, the movie, the house) must end in File City (screen 204, the MAPHEAD section of MOD_NEWGAME[startScript]) with the partner of
# MOD_NEWGAME[starters[0]] (Agumon, 3). Second run, at the same time on its own port: the first starter poked to 17 before the scene must give that
# partner. About 10 minutes.
#   tools/dev/playtest/new_game_start.sh
set -u
cd "$(dirname "$0")/../../.."
DISC=${DISC:-build/full.cue}
mkdir -p build/savedrop
# the sequence in two parts: boot to the menu, (poke), then the new game; the final "save" line is left out (both runs would write the same file)
grep -v '^#' tools/dev/sequences/new-game.seq | grep -v '^save ' > build/savedrop/ng-all.seq
head -1 build/savedrop/ng-all.seq > build/savedrop/ng-head.seq; tail -n +2 build/savedrop/ng-all.seq > build/savedrop/ng-tail.seq
run() {   # port, starter0 to poke ("-" = none), result file
  export EMU_PORT=$1 EMU_ARGS="-interpreter -debugger"
  tools/dev/emulator.py start $DISC >/dev/null
  tools/dev/emulator.py seq build/savedrop/ng-head.seq >/dev/null
  if [ "$2" != "-" ]; then
    python3 - "$2" <<'PY'
import os
import struct, subprocess, sys
sys.path.insert(0, 'tools'); from tools.dev import symbols as dwsyms
T = dwsyms.table(os.environ.get('DW_SYMS', 'disc-full'))
subprocess.run([sys.executable, 'tools/dev/emulator.py', 'poke', hex(T['MOD_NEWGAME'] + 4 * 9), struct.pack('<i', int(sys.argv[1])).hex()])
PY
  fi
  tools/dev/emulator.py seq build/savedrop/ng-tail.seq >/dev/null
  for f in current_screen partner.type; do
    python3 tools/dev/game_state.py show $f 2>&1 | tail -1 | awk '{print $NF}'
  done | tr '\n' ' ' > $3
  tools/dev/emulator.py stop >/dev/null
}
run 38131 - build/savedrop/ngs-default.txt &
run 38132 17 build/savedrop/ngs-gabumon.txt &
wait
python3 - <<'PY'
import os
def ok(name, got, want): print(f'{"ok " if got == want else "BAD"} {name:60s} got {got} expected {want}')
for f, want, what in (('build/savedrop/ngs-default.txt', ('204', '3'), 'default table: File City, Agumon'), ('build/savedrop/ngs-gabumon.txt', ('204', '17'), 'first starter poked to 17: File City, partner 17')):
    ok(what, tuple(open(f).read().split()), want)
PY
