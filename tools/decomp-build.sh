#!/usr/bin/env bash
# Builds the decompilation (decomp/) with GCC inside the Docker image
# built from decomp/Dockerfile (Ubuntu noble + gcc-mipsel-linux-gnu).
#
# Usage: tools/decomp-build.sh [image|regenerate [DISC.bin]|build|shell]   (default: build)
#   image       builds the "dw-build" Docker image (once)
#   regenerate  dumps the disc to decomp/disks/us and runs `make regenerate` (splat)
#   build       `make TOOLCHAIN=gcc` → "$W"/build/us/psx/gcc/{SLUS_010.32,*_REL.BIN}
#   shell       opens a shell in the container
set -euo pipefail
cd "$(dirname "$0")/.."
ROOT=$PWD
W=${W:-$ROOT/decomp}
W=$(realpath "$W")
JOBS=${JOBS:-2}
[ -t 0 ] && TTY="-it" || TTY=""     # without a terminal (scripts, Claude) docker run -it fails
run() { docker run --rm $TTY --user "$(id -u):$(id -g)" -e HOME=/tmp -v "$W:/work" -w /work dw-build "$@"; }
case "${1:-build}" in
  image)      docker build -t dw-build "$W" ;;
  regenerate) mkdir -p "$W/disks/us"
              IMG=${2:-"Digimon World (USA).bin"}
              [ -f "$IMG" ] || { echo "missing disc: $IMG (pass its path after regenerate)" >&2; exit 1; }
              .tools/mkpsxiso/build/dumpsxiso -x "$W/disks/us" -s "$W/disks/us/us.xml" "$IMG"
              run make -j"$JOBS" regenerate ;;
  build)      run make -j"$JOBS" TOOLCHAIN=gcc
              ls -l "$W"/build/us/psx/gcc/SLUS_010.32 "$W"/build/us/psx/gcc/*_REL.BIN | awk '{print $5, $9}' ;;
  shell)      run bash ;;
  *) echo "usage: $0 [image|regenerate [DISC.bin]|build|shell]" >&2; exit 1 ;;
esac
