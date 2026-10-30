#!/usr/bin/env bash
# C mods on top of the decompilation: ONE patch series, mods/patches/NNNN-*.patch (see its README.md).
#
#   tools/mods.sh prepare [mods|int|tier2]  creates/updates a working copy of the decompilation with the series applied
#                                      mods (default): build/decomp-mods, branch "mods" = the pinned decomp + the core
#                                                       patches (everything before the first merge patch)
#                                      int:             build/decomp-int, branch "integration" = the whole series
#   tools/mods.sh build [mods|int|tier2]  builds that working copy with GCC (Docker) and assembles build/<name>.bin
#                                      with the Makefile's defaults (PARTNER_MMD_MAX 0x18800, mods 0x20000; FPS 60; the US text);
#                                      FPS=20|30|60 / FONT=original|a|b / PARTNER_MMD_MAX=0x19000 tools/mods.sh build int
#                                      override them. The disc has the original's data files; tools/build-full.sh
#                                      makes the full disc
#   tools/mods.sh save [mods|int]  exports the commits made in the working copy after `prepare` as new
#                                      patches at the end of the series
#
# Flow: prepare -> edit in build/decomp-int/src -> git commit there -> save -> build.
# The series is linear: a change to an old patch is a new patch on top (history stays readable).
set -euo pipefail
cd "$(dirname "$0")/.."
ROOT=$PWD
case "${2:-mods}" in
  mods) BR=mods;        W=$ROOT/build/decomp-mods; NAME=mods ;;
  int)  BR=integration; W=$ROOT/build/decomp-int;  NAME=integration ;;
  *) echo "usage: $0 [prepare|build|save] [mods|int]" >&2; exit 1 ;;
esac
SAVE_DIR=mods/patches
series() {   # the patches of the working copy: the core ones (up to the first merge) or all
  case "$BR" in
    mods) ls mods/patches/*.patch | sed '/Merge-branch/,$d' ;;
    *) ls mods/patches/*.patch ;;
  esac
}
case "${1:-build}" in
  prepare)
    # Branch tips can move after cloning; reproduce the gitlink pinned by this checkout.
    BASE=$(git -C "$ROOT" rev-parse HEAD:decomp)
    if [ ! -d "$W" ]; then
      git -C decomp worktree add "$W" -B "$BR" "$BASE"
    fi
    git -C "$W" checkout -q -B "$BR" "$BASE"
    git -C "$W" -c user.name="Horizon authors" -c user.email= am -q $(series | sed "s#^#$ROOT/#")
    git -C "$W" tag -f "series-$BR" >/dev/null
    [ -d decomp/asm ] || { echo "missing decomp/asm: tools/decomp-build.sh regenerate" >&2; exit 1; }
    rm -rf "$W/asm" && cp -a decomp/asm "$W/"
    mkdir -p "$W/build/us/psx" && rm -rf "$W/build/us/psx/generated" && cp -a decomp/build/us/psx/generated "$W/build/us/psx/"
    rm -rf "$W/external/psyq_headers" && cp -a decomp/external/psyq_headers "$W/external/" && rm -f "$W/external/psyq_headers/.git"
    python3 tools/sdk_messages.py "$W"
    # Original bitmap glyphs are generated locally from the player's extracted disc.
    if grep -q '#include "font_compact.h"' "$W/src/main/font.c"; then
      python3 tools/font/compact.py "$W"
    fi
    echo "working copy ready in $W (branch $BR, $(git -C "$W" log --oneline "$BASE".."$BR" | wc -l) patches)" ;;
  build)
    [ -t 0 ] && TTY="-it" || TTY=""
    docker run --rm $TTY --user "$(id -u):$(id -g)" -e HOME=/tmp -v "$W:/work" -w /work dw-build make -j"$(nproc)" TOOLCHAIN=gcc ${FPS:+FPS=$FPS} ${FONT:+FONT=$FONT} ${PARTNER_MMD_MAX:+PARTNER_MMD_MAX=$PARTNER_MMD_MAX}
    # --relayout: the overlays of the series outgrow the original's sectors (EVL_REL, patch 0079), so the files after
    # them move and FILE_OFFSET_TABLE is rewritten from the linker map (docs/mods/scripts.md "If DG.SCN grows")
    python3 tools/build-disc.py "$NAME" --from "$W/build/us/psx/gcc" --relayout | tail -1 ;;
  save)
    N=$(ls $SAVE_DIR/*.patch | wc -l)
    git -C "$W" format-patch -q -o "$ROOT/$SAVE_DIR" --start-number $((N + 1)) "series-$BR".."$BR"
    git -C "$W" tag -f "series-$BR" >/dev/null
    ls $SAVE_DIR | tail -3 ;;
  *) echo "usage: $0 [prepare|build|save] [mods|int]" >&2; exit 1 ;;
esac
