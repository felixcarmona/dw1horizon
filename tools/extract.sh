#!/usr/bin/env bash
# Dumps the disc to extracted/ and writes the mkpsxiso XML project to build/.
# Usage: tools/extract.sh ["Digimon World (USA).bin"]
set -euo pipefail
cd "$(dirname "$0")/.."
IMG=${1:-"Digimon World (USA).bin"}
DUMP=.tools/mkpsxiso/build/dumpsxiso
[ -x "$DUMP" ] || { echo "Missing $DUMP: build mkpsxiso" >&2; exit 1; }
mkdir -p build extracted
"$DUMP" -x extracted -s build/digimonworld.xml "$IMG"
echo "Dumped to extracted/ ($(find extracted -type f | wc -l) files); project in build/digimonworld.xml"
