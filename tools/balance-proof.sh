#!/usr/bin/env bash
# tools/balance-proof.sh: byte-identity proof of tools/balance.py and tools/species.py (docs/mods/balance.md section 6,
# docs/mods/species.md) and the example disc. Needs build/full (models, sound, DG.SCN: tools/build-full.sh once).
# A: the integrated disc with the executable as linked (every table as the C initializes it)
# B: the same with every table written from JSON (content/balance, content/species 0..179)
# C: the examples: content/balance/examples (Tremar's MP cost) and content/balance/examples/species (Veemon without
#    Sonic Jab, so on evolving it learns Tremar)
# Discs: build/balproof-{a,b,c}.bin. BASE=dir: another linked build (default build/decomp-int).
set -euo pipefail
cd "$(dirname "$0")/.."
P=build/balance/proof; mkdir -p $P; rm -f $P/DIGI-*.DAT; M=build/full/models; F=build/full; BASE=${BASE:-build/decomp-int/build/us/psx/gcc}
PY=.venv/bin/python
SPECIES=${SPECIES:-180 181 182 373}
$PY tools/species.py select "$SPECIES" -o $P/species --models $M
rm -rf $P/species-c && cp -a $P/species $P/species-c
for f in content/balance/examples/species/*.json; do        # the example's species replace theirs
  id=$(basename "$f" | cut -d- -f1); rm -f $P/species-c/$id-*.json; cp "$f" $P/species-c/
done
$PY tools/species.py --content $P/species-c select "$SPECIES" -o $P/species-c --models $M >/dev/null
$PY tools/species.py --content $P/species build -o $P/DIGI-AB.DAT | tail -1
$PY tools/species.py --content $P/species-c build -o $P/DIGI-C.DAT | tail -1
rm -rf $P/exe-B $P/exe-C
$PY tools/balance.py build --exe-dir $BASE -o $P/exe-B
SPECIES_CONTENT=$P/species-c $PY tools/balance.py --content content/balance/examples build --exe-dir $BASE -o $P/exe-C
disc() {  # NAME EXEDIR DIGI SPECIESDIR
  local files=(); while IFS=$'\t' read -r opt spec; do files+=("$opt" "$spec"); done \
    < <($PY tools/species.py --content "$4" disc-files)
  $PY tools/build-disc.py "$1" --from "$2" --relayout --add DIGI.DAT="$3" "${files[@]}" \
  --file SOUND/VHB/FAALL.VHB="$F/sound/FAALL.VHB" --file SOUND/VHB/VBALL.VHB="$F/sound/VBALL.VHB" \
  --file SOUND/VHB/VLALL.VHB="$F/sound/VLALL.VHB" --file SOUND/VHB/ESALL.VHB="$F/sound/ESALL.VHB" \
  --file SCN/MAPHEAD.SCN="$F/MAPHEAD.SCN" --file SCN/DG.SCN="$F/DG.SCN" | tail -1
}
disc balproof-a $BASE $P/DIGI-AB.DAT $P/species
disc balproof-b $P/exe-B $P/DIGI-AB.DAT $P/species
disc balproof-c $P/exe-C $P/DIGI-C.DAT $P/species-c
sha256sum build/balproof-a.bin build/balproof-b.bin build/balproof-c.bin $P/DIGI-*.DAT $BASE/SLUS_010.32 $P/exe-?/SLUS_010.32 $BASE/TRN_REL.BIN $P/exe-?/TRN_REL.BIN | tee $P/sha256.txt
if cmp -s build/balproof-a.bin build/balproof-b.bin; then echo "A == B: byte-identical disc"
else   # the species files were edited since the C (species.py verify lists them): B carries the edits
  echo "A != B: the executables differ in $(cmp -l $BASE/SLUS_010.32 $P/exe-B/SLUS_010.32 | wc -l) bytes; species.py verify:"
  $PY tools/species.py verify --exe-dir $BASE | sed 's/^/  /'
fi
cmp -l build/balproof-a.bin build/balproof-c.bin | wc -l | sed 's/$/ bytes differ between A and C/'
rm -rf build/disc-balproof-a build/disc-balproof-b build/disc-balproof-c
