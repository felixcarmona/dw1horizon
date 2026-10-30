#!/usr/bin/env bash
# The web engine's files (web/README.md "The engine") from a make-release (format 3, the derive builder):
#   web/build-engine.sh [RELEASE_DIR [OUT]]
# Fixed places, in the main checkout (not in a worktree, so worktrees can come and go):
#   RELEASE_DIR default <main>/build/web-release (copy a make-release there), OUT default <main>/build/web-engine
#   (web/deploy.sh publishes it as engine/; older versions in OUT are removed).
# Fetches Pyodide 314.0.7 (npm) into <main>/build/pyodide-314.0.7 the first time. The jobs' inputs
# are recorded on the USA and the Japanese (Rev 1) discs of ISOS: two derive
# builds in one process each, ~8 min each. RECORDS=DIR keeps the records there and reuses them (developers; the
# records only change when the release's derive steps do).
set -euo pipefail
here=$(cd "$(dirname "$0")" && pwd)
main=$(dirname "$(git -C "$here" rev-parse --path-format=absolute --git-common-dir)")
REL=$(cd "${1:-$main/build/web-release}" && pwd)
OUT=${2:-$main/build/web-engine}
ISOS=${ISOS:-$here/../build/isos/digimon-world}
PYO=$main/build/pyodide-314.0.7
if [ ! -f "$PYO/pyodide.asm.wasm" ]; then
  mkdir -p "$PYO"
  (cd "$PYO" && npm pack pyodide@314.0.7 --silent >/dev/null && tar xzf pyodide-314.0.7.tgz --strip-components=1 && rm pyodide-314.0.7.tgz)
fi
work=${ENGINE_WORK:-$main/build}
mkdir -p "$work"
# the three source games (a release whose manifest lists source_discs: the imported species' models are made from
# them): recorded with them, never packaged. DCB_IMAGE, DW2_IMAGE, DW3_IMAGE (default: SOURCE_ISOS, SOURCE_ISOS)
SRC=${SOURCE_ISOS:-$here/../build/isos}
sources=()
if python3 -c 'import json,sys; sys.exit(not bool(json.load(open(sys.argv[1])).get("source_discs")))' "$REL/manifest.json"; then
  sources+=(--source-disc "dcb=${DCB_IMAGE:-$SRC/digital-card-battle/Digimon Digital Card Battle (USA).bin}")
  sources+=(--source-disc "dw2=${DW2_IMAGE:-$SRC/digimon-world-2/Digimon World 2 (USA).bin}")
  sources+=(--source-disc "dw2003=${DW3_IMAGE:-$SRC/digimon-world-2003/Digimon World 2003 (E) [SLES-03936].bin}")
fi
python3 "$here/enginebuild/build_engine.py" --release "$REL" --pyodide "$PYO" --out "$OUT" --work "$work" \
  --disc us="$ISOS/Digimon World (USA).bin" --disc jp1="$ISOS/DigimonWorld (Japan) (Rev 1).bin" \
  "${sources[@]}" \
  ${RECORDS:+--records "$RECORDS"}
