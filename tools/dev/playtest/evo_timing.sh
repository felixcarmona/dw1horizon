#!/usr/bin/env bash
# evo_timing.sh: patch 0117 in the emulator (disc build/full.cue: REUSE_MODELS=1 tools/build-full.sh int). The disc must carry
# content/tables/evolution-rules.json. Prints MOD_EVO_TIMING, then Agumon (a Rookie, no candidate) at several evoTimers: the
# game clock is set to minute 59, so one hour ticks in the 8 s waited, so 95 -> 96 evolves into the fallback (state 0d, target 0b = 11),
# 71, 90, 94 do not. Then the rules wiped in RAM (what a file without the key builds): no fallback target, no Rookie hours -> it never evolves.
set -u
cd "$(dirname "$0")/../../.."
export EMU_PORT=38112 EMU_ARGS="-interpreter -debugger"
DISC=${DISC:-build/full.cue}
mkdir -p build/savedrop; cp build/ids-saved.mcd build/savedrop/e.mcd
tools/dev/emulator.py start $DISC --card build/savedrop/e.mcd >/dev/null
tools/dev/emulator.py seq tools/dev/sequences/continue.seq >/dev/null; tools/dev/emulator.py wait 30 >/dev/null   # the map fade-in must be over (DAYTIME_TRANSITION_FRAME >= 25)
echo "MOD_EVO_TIMING (-1 = does not exist): $(tools/dev/emulator.py peek MOD_EVO_TIMING 22 | cut -c11- | tr -d '\n')"
tools/dev/emulator.py save build/savedrop/e.state >/dev/null
run() {   # evoTimer [poke-address]
  tools/dev/emulator.py load build/savedrop/e.state >/dev/null
  [ -n "${2:-}" ] && tools/dev/emulator.py poke $2 ffff >/dev/null
  python3 tools/dev/game_state.py set partner.para.evoTimer=$1 minute=59 >/dev/null 2>&1   # the hour ticks (evoTimer + 1) and the check runs
  tools/dev/emulator.py wait 8 >/dev/null
  echo "evoTimer $1 ${3:-}-> partner state $(tools/dev/emulator.py peek PARTNER_STATE 1 | awk '{print $2}') (0d = evolving), target $(tools/dev/emulator.py peek EVOLUTION_TARGET 2 | awk '{print $2 $3}')"
}
for t in 71 90 94 95 200; do run $t; done
A=$(python3 -c "import sys; sys.path.insert(0,'tools'); from tools.dev import symbols as dwsyms; print(hex(dwsyms.table(os.environ.get('DW_SYMS', 'disc-full'))['MOD_EVO_TIMING']))")
run 200 $((A + 20)) "(no fallback target) "
run 200 $((A + 6)) "(no Rookie hours) "
tools/dev/emulator.py stop >/dev/null
