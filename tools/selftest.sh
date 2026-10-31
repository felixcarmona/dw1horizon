#!/usr/bin/env bash
# Offline self-test of the toolchain: no emulator, about a minute.
# Checks that every tool still reproduces the original files byte for byte
# and that every DWS example compiles. The checks that read your disc's files
# need extracted/ (tools/extract.sh) and are skipped without it; the checks
# that need the decompilation (decomp/, a prepared submodule) likewise.
#   tools/selftest.sh
set -u
cd "$(dirname "$0")/.."
PY=python3; [ -x .venv/bin/python ] && PY=.venv/bin/python
OUT=build/selftest; mkdir -p "$OUT"
pass=0; fail=0; skip=0
DISC=0; [ -f extracted/SLUS_010.32 ] && DISC=1
DECOMP=0; [ -f decomp/config/us/symbols.txt ] && DECOMP=1
skip() {  # skip NAME WHY
    printf '  skip  %s (%s)\n' "$1" "$2"; skip=$((skip + 1))
}
disc() {  # disc NAME CMD...: run only with extracted/
    if [ "$DISC" = 1 ]; then run "$@"; else skip "$1" "needs extracted/"; fi
}
both() {  # both NAME CMD...: run only with extracted/ and the decompilation's symbols (git submodule update --init)
    if [ "$DISC" = 1 ] && [ "$DECOMP" = 1 ]; then run "$@"; else skip "$1" "needs extracted/ and decomp/"; fi
}
run() {   # run NAME CMD...
    local name=$1; shift
    if "$@" >"$OUT/$name.log" 2>&1; then
        printf '  ok    %s\n' "$name"; pass=$((pass + 1))
    else
        printf '  FAIL  %s (see %s)\n' "$name" "$OUT/$name.log"; fail=$((fail + 1))
    fi
}
echo "toolchain self-test"
if [ "$DISC" = 1 ] && [ ! -f text/us/dialogue.json ]; then
    run original-text-bank "$PY" -c 'from pathlib import Path; from tools.dws import textx; Path("text/us").mkdir(parents=True, exist_ok=True); textx.write_bank(textx.extract(), "text/us/dialogue.json")'
fi
disc scnasm-roundtrip  $PY tools/dws/bytecode/__main__.py check extracted/SCN/DG.SCN extracted/SCN/MAPHEAD.SCN
disc dwmap-roundtrip   $PY tools/dwmap.py roundtrip
disc mmd-roundtrip     $PY tools/mmd.py roundtrip
disc mmd-anim-roundtrip $PY tools/mmd.py anim-roundtrip
disc sound-roundtrip   $PY tools/sound.py roundtrip
disc sound-spu-budget  $PY tools/sound.py spu-budget
DERIVED=${DW_SELFTEST_DERIVE:-build/wtif}
if [ -f "$DERIVED/DIGI.DAT" ] && [ -d "$DERIVED/species" ]; then
    run species-archive "$PY" tools/dev/check_species_archive.py "$DERIVED"
    disc record-original-deltas "$PY" tools/audit_recordoriginals.py --from "$DERIVED" --check --out "$OUT/record-original-deltas.json"
else
    skip species-archive "needs the everything build (DW_SELFTEST_DERIVE)"
fi
if [ -f "$DERIVED.bin" ] && [ -f "$DERIVED/exe/SLUS_010.32.elf.map" ] && [ "$DISC" = 1 ]; then
    run npc-originals "$PY" tools/npc_originals.py "$DERIVED"
else
    skip npc-originals "needs a built disc image and extracted/ (DW_SELFTEST_DERIVE)"
fi
run npc-originals-tests "$PY" -W ignore tools/test_npc_originals.py
run species-format    $PY tools/species.py fmt --check                      # content/species in the canonical layout (docs/mods/species.md)
run species-lint      $PY tools/species.py lint --quiet                     # what the game cannot handle (docs/mods/species.md)
if [ -d "$DERIVED/species" ]; then
    run species-lint-tests env SPECIES_TEST_CONTENT="$DERIVED/species" "$PY" tools/test_species.py
else
    skip species-lint-tests "needs generated species (DW_SELFTEST_DERIVE)"
fi
run fi-info-clock     $PY tools/test_fi_info.py
disc evolution-tree   $PY tools/test_evo_tree.py --practical
disc evolution-tree-guard $PY -W ignore::ResourceWarning tools/test_evo_tree_guard.py
run starter-quiz      $PY tools/starter_quiz.py
run starter-quiz-tests $PY tools/test_starter_quiz.py
run world-gates $PY tools/world_audit.py
run world-gates-tests $PY -W ignore tools/test_world_audit.py
run city-residents $PY -m unittest tools.test_city_residents
if [ -f "$DERIVED/DIGI.DAT" ]; then
    run city-compiled $PY -m tools.city_residents $(find "$DERIVED" -name DG.SCN -o -name MAPHEAD.SCN)
else
    skip city-compiled "needs compiled stories (DW_SELFTEST_DERIVE)"
fi
run heap-tables       $PY tools/test_heap_tables.py                      # compact sector/size records remain lossless
run npc-footprints   $PY tools/test_reach_policies.py
run npc-routes       $PY tools/check_npc_routes.py                     # every authored new-screen visibility state
run npc-route-mutations $PY tools/test_npc_routes.py
if [ -d "${DERIVED}-maps/screens" ]; then
    run npc-routes-built $PY tools/check_npc_routes.py --maps "${DERIVED}-maps/screens"
fi
run npc-staging       $PY tools/test_npc_staging.py                     # actual model routes and transient allocation peaks
run release-version   $PY tools/test_version.py
run derive-sum        $PY tools/test_pysum.py                             # tools/derive's sum() is CPython 3.12's, bit for bit
run derive-units      $PY tools/test_derive_units.py                      # a unit that fails stops the step at once, no worker left (fork, spawn)
run patcher-release $PY -m unittest tools.test_patcher_release_selection
run patcher-publication $PY -m unittest tools.test_patcher_codecopy tools.test_patcher_datacopy tools.test_patcher_buffers tools.test_patcher_headermeta tools.test_patcher_literals tools.test_literal_gate tools.test_delta_audit tools.test_changed_build_proof
run build-cache       $PY -m unittest tools.test_build_cache tools.test_compiler_cache tools.test_derive_cache tools.test_native_build
run patcher-bundle    $PY tools/test_patchbundle.py                       # eager imports survive the recorded release bundle
both balance-original  $PY tools/balance.py verify --exe-dir extracted        # species.py extract -> encode == the disc's tables (27)
both balance-check     $PY tools/balance.py check --exe-dir extracted
run balance-map-outputs $PY -m unittest tools.test_balance_maps
run ground-pickup-ids $PY tools/test_ground_items.py
run economy-audit     $PY tools/economy_audit.py                            # no repeatable conversion turns bits into more bits
if [ -f "$DERIVED/exe/SLUS_010.32.elf" ]; then
    run balance-int $PY tools/balance.py verify --exe-dir "$DERIVED/exe"
elif [ -f build/decomp-int/build/us/psx/gcc/SLUS_010.32.elf ]; then
    run balance-int $PY tools/balance.py verify
else
    skip balance-int "needs a balanced executable (DW_SELFTEST_DERIVE)"
fi
disc dwtables          sh -c 'rm -rf "$2/tables" && "$1" tools/dwtables.py extracted/SLUS_010.32 "$2/tables" >/dev/null && for f in "$2"/tables/*.csv; do [ -f "docs/data/$(basename "$f")" ] || continue; cmp -s "$f" "docs/data/$(basename "$f")" || { echo "differs: $f"; exit 1; }; done' sh "$PY" "$OUT"
disc dws-tests         $PY -W ignore tools/test_dws.py
disc dws-safety        $PY -W ignore tools/test_dws_safety.py
run dws-authored      $PY -W ignore tools/test_dws_authored.py
run island-story      $PY -W ignore -m unittest discover -s story/mods/what-the-island-forgot/test
for d in tools/dws/examples/*.dws; do
    n=$(basename "$d" .dws)
    exe=original; case $n in expanded-*) exe=story-state;; esac       # the engine tier 2 examples
    disc "dws-$n" $PY tools/dws.py check "$d" --build --exe $exe -o "$OUT/dws-$n.SCN"
done
run dws-fmt           $PY tools/dws.py fmt --check tools/dws/examples/*.dws tools/dws/examples/lib/*.dws
run dws-doctor        $PY tools/dws.py doctor
disc dws-types         $PY tools/dws.py types --check                     # typings/dw (the story language's stubs) is current
run python-compiles   sh -c "$PY -m py_compile tools/*.py tools/dws/*.py tools/dev/playtest/*.py content/models/*/*.py content/models/*/*/*.py"
disc dws-roundtrip     $PY tools/dws.py roundtrip
disc dws-readable      $PY tools/dws.py decompile-all --readable -o "$OUT/readable" --scripts 2,22,178,184
disc story-base-committed $PY tools/dws.py story-base --reproduce       # original generation + reviewed authored edits; both sides pinned
disc story-build       $PY tools/dws.py story-build tools/dws/examples/dev-save.dws --mods none -o "$OUT/story/DG.SCN"   # story/base -> DG.SCN, MAPHEAD.SCN
both dwstest-offline  $PY tools/dev/story_test.py offline
run dw3-names        $PY tools/dw3_names_check.py                      # DW2003 imports named as the game names them (skips without $DW3_ROOT)
run map-reach-policies $PY tools/test_reach_policies.py
run developer-contracts $PY tools/test_dev_contracts.py
run presented-frame-video $PY tools/test_presented_frames.py
run gallery-foregrounds $PY tools/test_gallery_foregrounds.py
run image-raster      $PY -m unittest tools.test_image
run sign-sprites      $PY -m unittest tools.test_signs
run image-dependencies $PY -m unittest tools.test_no_pillow
run numeric-replay    $PY -m unittest tools.test_arraymath tools.test_dcbplayer tools.test_texel
run patcher-python-only $PY -m unittest tools.test_no_numpy
run dws-resource-tests $PY -W ignore -m unittest tools.test_dws_variants tools.test_dws_resources tools.test_dws_text_profiles tools.test_dws_bytecode tools.test_dws_text_sources tools.test_dws_story_testing tools.test_dws_spawns
run partner-models $PY -W ignore -m unittest tools.test_partner_model_generators
run model-apis $PY -W ignore -m unittest tools.test_model_provider tools.test_modeldelta tools.test_imported_model_edit tools.test_recordoriginals
run model-tools-python $PY -m compileall -q tools/models
run allocation-pools $PY -m unittest tools.test_allocation_pools
run check-links       $PY tools/checkrefs.py
run check-links-tests $PY tools/test_checkrefs.py
echo "$pass passed, $fail failed, $skip skipped"
[ "$fail" -eq 0 ]
