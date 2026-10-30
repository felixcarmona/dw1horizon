#!/usr/bin/env bash
# robust.sh: the power-cut test of docs/developing.md (section 6) on the tagged extension (save v4; expanded story: v5),
# a short version: a tagged-save build (an inverted v4 save: partner species 181) and the expanded-story engine (
# made by `MAIN_STORY=tools/dws/examples/dev-save.dws tools/build-full.sh`; a story variable makes its save inverted), the write cut after
# each part, then Continue from every card the cut left: it must load the old or the new save, never "Data Error".
#   tools/dev/saves/robust.sh [tagged|story|grow]    (default: all three)
set -uo pipefail
T=$(cd "$(dirname "$0")" && pwd); cd "$T/../../.."
export MKWAIT=${MKWAIT:-30}
S=tools/dev/saves; D=${D:-build/dev/saves/robust}; mkdir -p $D
: "${TAGGED_DISC:?Set TAGGED_DISC to the v4 test disc}"
: "${TAGGED_ELF:?Set TAGGED_ELF to its executable}"
: "${STORY_DISC:?Set STORY_DISC to the expanded-story test disc}"
: "${STORY_ELF:?Set STORY_ELF to its executable}"
IE=$TAGGED_ELF; TE=$STORY_ELF
FC=$D/fc.mcd; cp build/states/file-city.mcd $FC
which=${1:-all}
. $S/symbols.sh
check() {   # DIR DISC ELF: Continue from every cut card, in turn (polling until the game is loaded or refused: the machine may be busy)
  local pk
  for f in $1/p*v*.log; do n=$(basename $f .log); export EMU_PORT=38270
    local elf=$3; pk() { tools/dev/emulator.py peek $(sym $elf $1) $2 | cut -d' ' -f2- | tr -d ' ' | head -1; }
    cp $1/$n.mcd $1/c-$n.run.mcd; tools/dev/emulator.py start $2 --card $1/c-$n.run.mcd >/dev/null; tools/dev/emulator.py seq tools/dev/sequences/continue.seq >/dev/null
    for i in $(seq 1 90); do e=$(pk MEMORY_CARD_ERROR 4); [ "$(pk CURRENT_MENU 4)" = ffffffff -o "$e" != 00000000 ] && break; tools/dev/emulator.py wait 2 >/dev/null; done
    x="screen=$(pk CURRENT_SCREEN 2) money=$(pk MONEY 4) type=$(pk PARTNER_ENTITY 4) err=$e menu=$(pk CURRENT_MENU 4)"
    [ "$(nm $3 | grep -c STORY_VAR_VALUES)" != 0 ] && x="$x var0=$(pk STORY_VAR_VALUES 4) flag0=$(pk STORY_FLAG_BITS 1)"
    tools/dev/emulator.py stop >/dev/null
    echo "$n: $(grep -c '^part' $f) parts $(grep pause $f) | $x"; done
}
if [ $which = all -o $which = tagged ]; then
  echo "== tagged save: an inverted v4 save (species 181), 1111 now, 2222 being saved"
  bash $S/capture_save.sh "$TAGGED_DISC" $IE 38260 $FC $D/tagged-old 00000000 | tail -n 1
  bash $S/capture_save.sh "$TAGGED_DISC" $IE 38260 $D/tagged-old/out.mcd $D/tagged-new 57040000 "PARTNER_ENTITY b5000000" | tail -n 1
  bash $S/capture_save.sh "$TAGGED_DISC" $IE 38260 $D/tagged-new/out.mcd $D/tagged-confirm ae080000 "" state | tail -n 1
  bash $S/power_cuts.sh "$TAGGED_DISC" $IE $D/tagged-new/out.mcd $D/tagged-confirm/confirm.state $D/tagged-cuts 1 38262 "99 0" "1 30" "2 30" "3 0" "3 60" "4 30"
  grep -h '^part' $D/tagged-cuts/p99v0.log; check $D/tagged-cuts "$TAGGED_DISC" $IE
fi
if [ $which = all -o $which = story ]; then
  echo "== expanded story: a v5 save with story state, 1111 now, 2222 being saved"
  bash $S/capture_save.sh "$STORY_DISC" $TE 38261 $FC $D/story-new 57040000 "STORY_VAR_VALUES 7b930400;STORY_FLAG_BITS 01" | tail -n 2
  bash $S/capture_save.sh "$STORY_DISC" $TE 38261 $D/story-new/out.mcd $D/story-confirm ae080000 "STORY_VAR_VALUES 02000000" state | tail -n 1
  bash $S/power_cuts.sh "$STORY_DISC" $TE $D/story-new/out.mcd $D/story-confirm/confirm.state $D/story-cuts 1 38263 "99 0" "1 30" "2 100" "3 0" "3 40" "4 100"
  grep -h '^part' $D/story-cuts/p99v0.log; check $D/story-cuts "$STORY_DISC" $TE
fi
if [ $which = all -o $which = grow ]; then
  echo "== expanded story: a one-block original save growing to three blocks, and the tagged inverted v4 save growing to three"
  bash $S/capture_save.sh "$STORY_DISC" $TE 38261 $FC $D/original-confirm ae080000 "STORY_VAR_VALUES 02000000" state | tail -n 1
  bash $S/power_cuts.sh "$STORY_DISC" $TE $FC $D/original-confirm/confirm.state $D/original-cuts 1 38264 "99 0" "1 0" "2 100" "3 40"
  check $D/original-cuts "$STORY_DISC" $TE
  [ -f $D/tagged-new/out.mcd ] && { bash $S/capture_save.sh "$STORY_DISC" $TE 38261 $D/tagged-new/out.mcd $D/migration-confirm ae080000 "STORY_VAR_VALUES 02000000" state | tail -n 1
    bash $S/power_cuts.sh "$STORY_DISC" $TE $D/tagged-new/out.mcd $D/migration-confirm/confirm.state $D/migration-cuts 1 38265 "99 0" "1 0" "2 100" "3 40"; check $D/migration-cuts "$STORY_DISC" $TE; }
fi
