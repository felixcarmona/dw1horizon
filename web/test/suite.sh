#!/bin/bash
# The engine's end-to-end tests: the real page in headless Chromium (web/test/run.mjs) on the seven bases (USA,
# Japanese Rev 1, Spanish, European, French, German, Italian), then a random job order (?shuffle=SEED); each image must
# be the release's (the page checks it) and the OPFS file is hashed again by the page's hash worker. Every run
# gives the other three games too (run.mjs: OTHERS, default the three source discs of SOURCE_ISOS).
#   BASES="us fr shuf"       only those (ui us jp1 es eu fr de it shuf shuf-es src1 src2 src3; ui: web/test/ui.mjs, adding discs:
#                            the replaced one, the dialog of files that cannot be used, ready, no build)
#   web/test/suite.sh TAG [URL]     URL default http://127.0.0.1:8799/ (python3 -m http.server -d SITE 8799, SITE = web/
#                                   with build/web-engine as engine/), or https://dw1horizon.com/
# Logs: build/webengine-test/TAG-*.log (state, times, SHA-1s, the engine's log, peak RSS of the browser's processes).
# Needs puppeteer-core (build/stage9/node/node_modules) and /snap/bin/chromium; FIREFOX=path runs run.mjs in Firefox.
set -u
here=$(cd "$(dirname "$0")" && pwd)
out=$here/../../build/webengine-test; mkdir -p "$out"
URL=${2:-http://127.0.0.1:8799/}
I=${ISOS:-$here/../build/isos/digimon-world}
run() {  # run NAME BIN QUERY
  timeout 3000 node "$here/run.mjs" "${URL}?test=1$3" "$2" "$out/profile" 2400 > "$out/$1.log" 2>&1
  if grep -q '"phase": "done"' "$out/$1.log"; then echo "$1 ok: $(grep -o 'wall.*' "$out/$1.log")"; else echo "$1 FAILED"; fi
}
BASES=${BASES:-ui us jp1 es eu fr de it shuf src1 src2 src3}
for b in $BASES; do
  case $b in
    us) run $1-us "$I/Digimon World (USA).bin" "" ;;
    jp1) run $1-jp1 "$I/DigimonWorld (Japan) (Rev 1).bin" "" ;;
    es) run $1-es "$I/Digimon World (Spain).bin" "" ;;
    eu) run $1-eu "$I/Digimon World (Europe).bin" "" ;;
    fr) run $1-fr "$I/Digimon World (France).bin" "" ;;
    de) run $1-de "$I/Digimon World (Germany).bin" "" ;;
    it) run $1-it "$I/Digimon World (Italy).bin" "" ;;
    shuf) run $1-us-shuf3 "$I/Digimon World (USA).bin" "&shuffle=3" ;;
    ui) timeout 1500 node "$here/ui.mjs" "$URL" > "$out/$1-ui.log" 2>&1 && echo "$1-ui ok" || echo "$1-ui FAILED" ;;
    shuf-es) run $1-es-shuf7 "$I/Digimon World (Spain).bin" "&shuffle=7" ;;
    # the other releases of the three source games (the engine is recorded with the first of each only)
    src1) OTHERS="dcb=${SOURCE_ISOS:-build/isos}/digital-card-battle/Digimon Digital Card Battle (Europe).bin;dw2=${SOURCE_ISOS:-build/isos}/digimon-world-2/DigimonWorld 2 (Japan).bin;dw2003=${SOURCE_ISOS:-build/isos}/digimon-world-2003/DigimonWorld 3 - Aratanaru Bouken no Tobira (Japan).bin" run $1-src1 "$I/Digimon World (USA).bin" "" ;;
    # World 3 (USA): its own imports, checked against the "<base>+dw3-us" checksums (a regional base: both at once)
    src3) OTHERS="dcb=${SOURCE_ISOS:-build/isos}/digital-card-battle/Digimon Digital Card Battle (USA).bin;dw2=${SOURCE_ISOS:-build/isos}/digimon-world-2/Digimon World 2 (USA).bin;dw2003=${SOURCE_ISOS:-build/isos}/digimon-world-2003/Digimon World 3 (USA).bin" run $1-src3 "$I/Digimon World (Europe).bin" "" ;;
    src2) OTHERS="dcb=${SOURCE_ISOS:-build/isos}/digital-card-battle/DigimonWorld - Digital Card Arena (Japan).bin;dw2=${SOURCE_ISOS:-build/isos}/digimon-world-2/Digimon World 2 (USA).bin;dw2003=${SOURCE_ISOS:-build/isos}/digimon-world-2003/Digimon World 2003 (E) [SLES-03936].bin" run $1-src2 "$I/Digimon World (USA).bin" "" ;;
  esac
done
