#!/usr/bin/env bash
# "What the island forgot": builds build/what-the-island-forgot.cue from the player's own extracted disc.
#
#   story/mods/what-the-island-forgot/build.sh          the disc
#   DEV=1 story/mods/what-the-island-forgot/build.sh    the same plus the playtest hook (Tokomon warps to the Engine Room)
#   NAME=x ...                                          another disc name (build/x.cue)
#
# Nothing of the game is in this folder: the maps are made from extracted/ (maps/*.py), with our art (art/) laid over or
# in place of the game's. What is built, in which order, is the recipe tools/derive/recipes/everything.json (the single
# source: its "story" sources, the mod's story files in the order they are compiled, and its "maps", the map recipes;
# a new story file or map recipe goes there). Steps:
#   1. the maps (tools/derive's maps and retouch steps, into build/NAME-maps): the new screens (300 and up) and the
#      retouched originals (Great Canyon Bottom Area, Leomon Ancestor's Cave, ...), the spawn audit among them
#   2. the disc: tools/build-full.sh with the screen files, the generated map files and the story (EXTRA_STORY,
#      SCREEN_CONTENT, DWS_MAPS, EXTRA_FILES: `python3 -m tools.derive recipe-env everything`)
set -euo pipefail
cd "$(dirname "$0")/../../.."
NAME=${NAME:-what-the-island-forgot}

echo "== 1. maps"
# (the recipes side by side in DERIVE_JOBS processes, default one per CPU: the same bytes as DERIVE_JOBS=1, the reference)
python3 -m tools.derive build --recipe everything --out "build/$NAME" --steps maps,retouch --jobs "${DERIVE_JOBS:-$(nproc)}" ${DERIVE_ARGS:-}

echo "== 2. disc build/$NAME.cue"
eval "$(python3 -m tools.derive recipe-env everything --out "build/$NAME" $([ "${DEV:-0}" = 1 ] && echo --dev))"
REUSE_MODELS=${REUSE_MODELS:-1} tools/build-full.sh "$NAME"
