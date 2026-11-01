#!/usr/bin/env bash
# The integrated disc build/full.cue: every merged feature in one playable image.
#
#   tools/build-full.sh            rebuild everything from scratch: partner models,
#                                  DIGI.DAT, sound files, dev-save script, executable, disc
#   REUSE_MODELS=1 tools/build-full.sh
#                                  keep models already in build/full/models (fast rebuilds)
#   tools/build-full.sh NAME       the same for another worktree/disc: executable from
#                                  build/decomp-NAME (override with W=path), everything
#                                  generated in build/NAME/, disc build/NAME.cue. With
#                                  NAME given and no models there yet, build/full/models
#                                  is copied (REUSE_MODELS is then on).
#   SEEK_ORDER=0                   the disc in the original file order (default: laid out for short seeks, build-disc.py
#                                  --seek-order: what a map change reads first, MAP after it, the movies last; a map load is
#                                  ~0.7 s shorter at real CD timing). A DuckStation state made on one order does not load on the other
#   NO_MOVIES=1                    the executable skips the STR movies (they hung under DuckStation until patch 0171,
#                                  docs/developing.md); for the disc of a device: NO_MOVIES=1 tools/build-full.sh device
#   SPECIES="..."                  which imported species (content/species, ids 180..) the disc carries: ids, "all",
#                                  or folders of species files, comma or space separated (default: 180 181 182 373 =
#                                  Veemon, Puppetmon, Kimeramon, WarGreymon). The 180 species of the disc are always
#                                  there (content/species/0..179).
#   IMPORTS=0                      the base disc of a release (tools/patcher, docs/patcher.md): no species
#                                  converted from other games, only data from the Digimon World disc itself
#                                  (SPECIES is then empty unless given)
#   EXTRA_SPECIES=DIR              the same as SPECIES="<default> DIR" (a folder of species files, e.g. an import batch;
#                                  its files win over content/species for the same ids)
#   SPECIES_PROVIDER=imports           the imports' species files from a provider (tools/derive/steps/species.py): imports, the
#                                  imported models of content/models/imports (its species.py, into $O/imported-species),
#                                  every file it hands over pinned by SHA-1; the four imports converted below are then not made
#   MAIN_STORY=FILE.dws            compiled in place of the dev-save script, this script's default and never a player's
#                                  disc (e.g. tools/dws/examples/font-proof.dws, which
#                                  also opens the save machine; docs/mods/font.md "Fonts")
#   EXTRA_STORY="a.dws b.dws"      more story sources compiled with the dev-save one (.dws, .py, a mod's folder; SPECIES_CONTENT names the
#                                  species folders they place)
#   PARTNER_MMD_MAX=0x20000        executable built with this partner model buffer (see
#                                  docs/reference/memory.md "Partner model buffer"); the model
#                                  size check below uses it (default: the executable's)
#   TEXT=us|ours|jp|jp-rev1|es-fan  whose text the game shows (docs/reference/text-sources.md): the dialogue (story-build
#                                  --text-source) and the executable's strings (text-bank.json for gen_text.py, patch
#                                  0090) from text/<TEXT>/, made from your own disc by `tools/dws.py extract-text DISC`
#                                  (text/ours/ is committed). Default us: the US disc's text, the build as before. A key
#                                  the source lacks stays our English (text/ours) and is listed in build/NAME/text-fallback.txt
#   STORY_LANG=es                  the language of the mods' new lines in EXTRA_STORY (each mod's text/<lang>.json, by the
#                                  keys of its text/en.json); with TEXT=ours: our game and the mod in Spanish
#                                  (docs/mods/translating.md, "A mod in your language")
#   FONT=original|b                the fonts the executable draws text with (docs/mods/font.md "Fonts"): b, ours, placed to
#                                  the pixel, and the original one, chosen in OPTIONS (NEW FONT; the script text is then
#                                  built twice, the second copy paged for the original font: DGORIG.SCN, MHORIG.SCN,
#                                  SCRNORIG.DAT); original, the US font on its 4-pixel grid only (the original code).
#                                  Default: the Makefile's
#   LANGS=en,es,pt-br,fr,de,it,ja         a disc in selected languages (docs/mods/translating.md): OPTIONS (LANGUAGE) switches between our
#                                  English (TEXT=ours, set it) and our Spanish (text/es/) at run time. The script text is
#                                  compiled in both (tools/derive's story step, the Spanish passes in build/NAME/es), the
#                                  executable twice (the strings padded to the
#                                  longer language: tools/langpatch.py writes LANGEN.BIN/LANGES.BIN), the overlays and the
#                                  translated textures get Spanish copies (LANG_FILES of the Makefile)
#   LANG_BASE=en|es|pt-br|fr|de|it|ja    the language the game starts in (default en)
#   STORY_ALT=0                    a disc with a story mod (EXTRA_STORY) and an executable with EXTENDED STORY (patch 0199,
#                                  docs/mods/options.md) carries the original story beside the extended one: the script text
#                                  compiled again without the mods (build/NAME/base: _G.SCN, _APHEAD.SCN...) and a copy of
#                                  every map file the mods change (MAYO03.MAP's is _AYO03.MAP: tools/dws/variants.py).
#                                  STORY_ALT=0: the extended story only, no choice in OPTIONS
#   MOD_VERSION=TEXT               the version the title screen and the title menu show in a corner (patch 0257); default
#                                  `tools/version.py game` (the release tag, "v0.1.0", or a development version, docs/
#                                  patcher.md "Making a release"); MOD_VERSION= draws nothing
#   FPS=20|30|60                   the frame rate the executable presents (docs/reference/frame-rate.md; the
#                                  logic stays at 20 Hz). A build parameter, not a game setting;
#                                  default: the Makefile's (FPS ?= 60, the pending decision of
#                                  docs/reference/frame-rate.md)
#   SCREEN_CONTENT=DIR[:DIR]       more screen files (DIR/<id>-<name>.json, ids 255 and up: tools/screens.py) beside
#                                  content/screens, e.g. a mod's or a test's own screens (tools/dev/playtest/screens.sh)
#   EXTRA_FILES="DEST=SRC ..."     more files for the disc: DEST on the disc replaces it (a map a test edits), a new DEST is a
#                                  new file (MAP/NEW/RIFT01.MAP=...: a new name, 8.3, unique on the disc; the executable gets
#                                  its FILE_OFFSET_TABLE entry, patch 0147, tools/newfiles.py). A screen file's .MAP/.TFS
#                                  beside it in a SCREEN_CONTENT folder are added the same way (in MAP/NEW)
#   DERIVE_JOBS=N                  tools/derive's units side by side in N processes (default: one per CPU; 1: the
#                                  reference, the same bytes). DERIVE_ARGS="--strict --record": more of derive build's
#                                  options (strict: no processes, as in the browser; record: what each step read, and a
#                                  read of a file only the USA disc has stops the build). The bash no longer makes any
#                                  derived file (DERIVE=0 is unsupported)
#   PACK_ASCII=1                   the story's texts store letters, digits, spaces and . , : ; ? ! ' " + - = as one byte
#                                  (tools/dws/bytecode/__main__.py asm --pack-ascii, patch 0145: the executable expands them as it reads; about 168 KB
#                                  less text in DG.SCN, a fifth of MAPHEAD's). Default: on for every TEXT but us (a translation needs the room), off for the
#                                  US text (the disc byte for byte as the original's)
#
# Executable: a private worktree of the pinned decomp with the ordered mods/patches series applied; set W=path.
# Generated files go to build/NAME, with NAME taken from the first argument.
#
# Needs: Docker image dw-build (tools/decomp-build.sh image), extracted/, the venv, and for
# the imported models the source projects ($DCB_ROOT and the DW2003
# extraction used by tools/dw3mmd.py; see docs/reference/imported-species.md and mega READMEs).
set -euo pipefail
cd "$(dirname "$0")/.."
ROOT=$PWD
NAME=${1:-full}
if [ "$NAME" != full ] && [ -d "$ROOT/build/decomp-$NAME" ]; then DEFAULT_W=$ROOT/build/decomp-$NAME
else DEFAULT_W=$ROOT/build/decomp-int; fi
W=${W:-$DEFAULT_W}
# A release pipeline can prepare its own tree without tools/mods.sh.
# Rebuild the original glyphs from the player's disc, never a committed header.
if grep -q '#include "font_compact.h"' "$W/src/main/font.c" 2>/dev/null; then
  python3 tools/font/compact.py "$W"
fi
# the story compiler's heap check measures this tree's heap (its last build's map: tools/membudget.py heap_total_now)
export DW_HEAP_MAP=${DW_HEAP_MAP:-$W/build/us/psx/gcc/SLUS_010.32.elf.map}
# Cold animations (patch 0113, docs/reference/memory.md): an executable that has them reads the partners' rare animations from the disc, so the
# partner species' models are cut in two (tools/coldsplit.py); COLD=0 turns it off, an older executable never gets it
if [ -z "${COLD:-}" ] && grep -q COLD_ANIM_FLAG "$W/include/dw/species.h" 2>/dev/null; then export COLD=1; fi
O=$ROOT/build/$NAME
M=$O/models
PY=python3
mkdir -p "$O"
LANGS=${LANGS:-}; LANG_BASE=${LANG_BASE:-en}
# Validate before doing any build work. Canonical order keeps copies reproducible.
LANG_LIST=$($PY - "$LANGS" "$LANG_BASE" <<'PYLANG'
import sys
from tools.languages import selected
try:
    print(' '.join(selected(dict(LANGS=sys.argv[1], LANG_BASE=sys.argv[2]))))
except ValueError as e:
    sys.exit(str(e))
PYLANG
)
LANG_ON=0; [ -n "$LANG_LIST" ] && LANG_ON=1
if [ "$LANG_ON" = 1 ] && [ "${TEXT:-us}" != ours ]; then echo "LANGS=$LANGS: the English of a two-language disc is ours (TEXT=ours)"; exit 1; fi
if [ "${REUSE_MODELS:-1}" = 1 ] && [ "$NAME" != full ] && [ ! -d "$M" ] && [ -d "$ROOT/build/full/models" ]; then
  cp -a "$ROOT/build/full/models" "$M"; REUSE_MODELS=1
fi
mkdir -p "$M"
step() { printf '\n== %s\n' "$*"; }
# the disc is always built with --relayout (step 6): DG.SCN may grow past the original size, whatever TEXT is
# (tools/dws passes bytecode --grow; docs/mods/scripts.md "If DG.SCN grows")
export DWS_RELAYOUT=1
[ "${PACK_ASCII:-$([ "${TEXT:-us}" = us ] && echo 0 || echo 1)}" = 1 ] && export SCNASM_PACK_ASCII=1   # tools/dws/bytecode/__main__.py asm packs the texts (patch 0145)

model() {   # model OUTFILE command...
  local out=$1; shift
  if [ "${REUSE_MODELS:-0}" = 1 ] && [ -s "$out" ]; then echo "reuse $(basename "$out")"; return; fi
  "$@"
}
X=content/models
# The default four imports are converted before derive because its species step reads them in $M.
# The imports provider already regenerates their models and textures, so this fallback is skipped for everything.
SP_LIST=${SPECIES_PROVIDER:-}; USES_IMPORTED_MODELS=0; case " ${SP_LIST//,/ } " in *" imports "*) USES_IMPORTED_MODELS=1 ;; esac
if [ "${IMPORTS:-1}" != 0 ] && [ "${USES_IMPORTED_MODELS}" = 0 ]; then
  step "imported models -> $M"
  model $M/Veemon.MMD    $PY tools/dcb2mmd.py partner $X/dcb-import/veemon.json $M        # 180
  model $M/Puppetmon.MMD $PY tools/dcb2mmd.py partner $X/dcb-import/puppetmon.json $M     # 181
  model $M/Kimeramon.MMD $PY tools/dw2mmd.py partner $X/dcb-import/kimeramon-dw2.json $M  # 182 (Digimon World 2)
  model $M/WarGreymon.MMD $PY $X/mega/make-model.py $M                                    # Mega 373
fi

# ---------------------------------------------------------------- 0. derived files (tools/derive)
# Every file made from the game's data (tools/derive/README.md): the partner models, DIGI.DAT, the sound
# banks, the script text in every copy, SCRN.DAT, the story's and the balance's maps, EXTENDED STORY's map copies, the
# translated textures and signs, the title images, and the plan of the disc (which files replace the disc's, which are
# new, the Spanish copies' names LEnnn, NEW_FILES, LANG_FILES, PARTNER_MMD_MAX): tools/derive, one Python process (the
# code the patcher runs too), into $O at the paths below. `python3 -m tools.derive steps` lists the steps.
# (its settings of the tree $W: $O/derived/exe-facts.json; what it made: $O/derived/manifest.json, logs in
# $O/derived/logs; the plan: $O/derived/disc.txt, plan.env, plan.json)
# (derive uses the developer venv when present; image operations use our raster module)
# (--write-locks: a developer build appends a story's new saved names to its mod's save.lock; the player's build only
# reads them. --jobs: the steps' units side by side, DERIVE_JOBS processes, default one per CPU; DERIVE_JOBS=1 is the
# reference, the same bytes. DERIVE_ARGS: more of derive build's options, e.g. "--strict --record")
LPY=$PY; [ -x "$ROOT/.venv/bin/python" ] && LPY=$ROOT/.venv/bin/python
step "derived files (tools/derive)"
$LPY -m tools.derive facts --w "$W" --out "$O"
$LPY -m tools.derive build --out "$O" --checks --write-locks --jobs "${DERIVE_JOBS:-$(nproc)}" ${DERIVE_ARGS:-}
PMM_GIVEN=${PARTNER_MMD_MAX:-}
. "$O/derived/plan.env"                  # PARTNER_MMD_MAX, NEW_FILES, LANG_FILES, LANG_OVL (steps/plan.py)
PARTNER_MMD_MAX=${PMM_GIVEN:-$PARTNER_MMD_MAX}

# the techniques, items and small tables of content/ (the source of the executable's tables, docs/mods/data-sources.md)
$PY tools/content.py lint
# a species, item or technique without a file that a map or the compiled story still uses (docs/mods/data-sources.md)
$PY tools/missing_refs.py --mods "${STORY_MODS:-all}"
# The partner model buffer of the executable: the biggest partner model on the disc (derive's species step: the 15 files
# above and every partner species), at least the original's 0x18800, whole sectors. PARTNER_MMD_MAX=... overrides it.
# The link fails if it leaves less than MIN_HEAP of heap.
export PARTNER_MMD_MAX
echo "PARTNER_MMD_MAX=$PARTNER_MMD_MAX"
# Tier 2 (memory modes, docs/mods/story-state-engine.md): one executable for 2 MB and 8 MB of RAM. Its static buffer stays the
# 2 MB one (the Makefile default, 0x18800); the species tools above get the disc's biggest model, and the 8 MB buffer must
# hold it. A partner bigger than the 2 MB buffer is refused on a console and plays on an emulator with 8 MB.
MAKE_PMM="PARTNER_MMD_MAX=$PARTNER_MMD_MAX"
if grep -q PARTNER_MMD_MAX_8MB "$W/include/dw/memmap.h" 2>/dev/null; then MAKE_PMM=""; fi

# ---------------------------------------------------------------- 2b. scripts
# The story (docs/reference/story-engine.md 11, derive's story step): story/base with every enabled mod's overrides
# (STORY_MODS=none|a,b to choose), the dev-save script (MAIN_STORY) and EXTRA_STORY on top, in $O; paged for the original
# font in $O/orig (ORIG); EXTENDED STORY's original story in $O/base (ALT); the Spanish ones in $O/es.
# MAPHEAD.SCN stays resident in MAPHEAD_SCRIPT_BUFFER: MAPHEAD_SCRIPT_MAX of this executable (0x8000 since patch 0091 / tier-2
# 0008; an older tree holds 0x6800)
MH_MAX=$(sed -n 's/^#define[[:space:]]*MAPHEAD_SCRIPT_MAX[[:space:]]*\(0x[0-9A-Fa-f]*\).*/\1/p' "$W/include/dw/memmap.h" 2>/dev/null)
MH_MAX=$(( ${MH_MAX:-0x6800} ))
# The extra glyphs of the font (á é ñ ... ( ) & % / …, docs/mods/font.md) this executable will have: its worktree's
# NUM_EXTRA_GLYPHS (an older tree has fewer; the text keeps only those, the rest drawn plain or dropped and listed)
FONT_GLYPHS=$(sed -n 's/^#define NUM_EXTRA_GLYPHS \([0-9]*\)/\1/p' "$W/src/main/font_extra.h" 2>/dev/null); FONT_GLYPHS=${FONT_GLYPHS:-0}
# the font the executable will draw with (FONT, else the worktree Makefile's default; a tree without patch 0097: original)
EXE_FONT=${FONT:-$(sed -n 's/^FONT ?= \([a-z]*\)/\1/p' "$W/Makefile" 2>/dev/null)}; EXE_FONT=${EXE_FONT:-original}
# ORIG: an executable with both fonts (FONT=b, patch 0173) reads a copy paged for the original font (steps/story.py)
TEXT=${TEXT:-us}
ORIG=0; { [ "$TEXT" != us ] || [ -n "${SCREEN_CONTENT:-}" ]; } && [ "$EXE_FONT" = b ] && grep -q '"DGORIG.SCN"' "$W/src/main/file_table_us.c" 2>/dev/null && ORIG=1
# ALT: EXTENDED STORY (patch 0199), the original story beside the extended one
ALT=0; [ -n "${EXTRA_STORY:-}" ] && [ "${STORY_ALT:-1}" = 1 ] && grep -q 'modStoryFile' "$W/src/main/mod_options.c" 2>/dev/null && ALT=1
BASE_V=(); if [ "$ALT" = 1 ]; then BASE_V=(base); [ "$ORIG" = 1 ] && BASE_V+=(base/orig); fi

# ---------------------------------------------------------------- 3. sound (soundlimits)
# Indexed VBALL/VLALL/ESALL and FAALL with the house theme and synthesized instruments:
# derive's sound step writes the banks in $S; its story step applies story/core/audio.json
# music bindings to every MAPHEAD variant.
step "sound files"
# a bank is staged at GENERAL_BUFFER in whole sectors and must end below the save extensions: SOUND_STAGING_MAX of this
# executable (patch 0096; an older tree: the original's largest, 124 sectors)
SOUND_STAGING_MAX=$(sed -n 's/^#define[[:space:]]*SOUND_STAGING_MAX[[:space:]]*\(0x[0-9A-Fa-f]*\).*/\1/p' "$W/include/dw/memmap.h" 2>/dev/null)
export SOUND_STAGING_MAX=${SOUND_STAGING_MAX:-0x3E000}
S=$O/sound
MH_ALL=$O/MAPHEAD.SCN; [ -f "$O/with-new-screens/MAPHEAD.SCN" ] && MH_ALL=$O/with-new-screens/MAPHEAD.SCN
$PY tools/sound.py spu-budget --vhb-dir "$S" --maphead "$MH_ALL" | tail -3   # the built MAPHEAD (the new screens' too): its screens' music
for f in "$S"/*.VHB; do   # the staged size of every chunk of the disc's banks (the others are the original's, within it)
  $PY tools/sound.py check "$f" | grep -q 'staging buffer' && { $PY tools/sound.py check "$f" | grep 'staging buffer'; exit 1; }
done; echo "sound staging: every chunk within SOUND_STAGING_MAX $SOUND_STAGING_MAX"
# The screens >= 255 (patch 0146, tools/screens.py; derive's screens step): every screen file with such an id in
# content/screens and the SCREEN_CONTENT folders (dir:dir) becomes a record of SCRN.DAT with its MAPHEAD section, which
# leaves MAPHEAD.SCN (the executable reads it from the disc when the screen is entered).
for mh in "$O/MAPHEAD.SCN" $([ "$ORIG" = 1 ] && echo "$O/orig/MAPHEAD.SCN") $(for v in "${BASE_V[@]}"; do echo "$O/$v/MAPHEAD.SCN"; done); do
  MH_SIZE=$(stat -c %s "$mh")
  [ "$MH_SIZE" -le "$MH_MAX" ] || { echo "$mh is $MH_SIZE bytes; the executable's MAPHEAD_SCRIPT_BUFFER holds $MH_MAX"; exit 1; }
  echo "${mh#$O/}: $MH_SIZE bytes of the executable's $MH_MAX ($((MH_MAX - MH_SIZE)) free)"
done

# ---------------------------------------------------------------- 4. scripts
# (DG.SCN and its MAPHEAD.SCN were compiled before the sound step, which edits the MAPHEAD)
# memreclaim: the NPC animation keep table must cover the scripts on the disc. The audit
# reads the story build's assembly of story/base ($O/story/dis: the original's instructions, `dws.py story-verify`;
# a section a mod overrides keeps its base code there) and its MAPHEAD ($O/story/maphead.scn.txt, with the mods'
# MAPHEAD overrides), nothing of the disc's DG.SCN: tools/dws/bytecode/__main__.py cannot disassemble a patched DG.SCN linearly, and the
# dev-save script only adds Jijimon's save-machine talk (no NPC animation). An override that plays new NPC animations
# needs its own audit. (It runs before step 4b, which empties $O/story for the extended story's map copies.)
$PY tools/npcanims.py gen "$O/npc_anim_keep.c" --dg "$O/story/dis" --maphead "$O/story/maphead.scn.txt"
# the committed table (src/main/npc_anim_keep.c) must keep at least every slot the audit asks for
$PY - "$O/npc_anim_keep.c" "$W/src/main/npc_anim_keep.c" <<'PYEOF'
import re, sys
def load(p):
    s = open(p).read()
    m = re.search(r'NPC_ANIM_KEEP_MASKS\[\d+\]\[2\] = \{(.*?)\};', s, re.S).group(1)
    masks = [tuple(int(x, 16) for x in r) for r in re.findall(r'\{ (0x[0-9A-Fa-f]+), (0x[0-9A-Fa-f]+) \}', m)]
    idx = re.search(r'NPC_ANIM_KEEP_INDEX\[\w+\] = \{(.*?)\};', s, re.S).group(1)
    return [masks[int(i)] for i in re.findall(r'\b(\d+),', re.sub(r'/\*.*?\*/', '', idx))]
need, have = load(sys.argv[1]), load(sys.argv[2])
bad = [t for t, (a, b) in enumerate(zip(need, have)) if (a[0] & ~b[0]) or (a[1] & ~b[1])]
if bad:
    sys.exit(f'npc_anim_keep.c drops slots the scripts play for types {bad}: '
             f'copy {sys.argv[1]} into the worktree and commit it')
print('npc_anim_keep.c covers the audit')
PYEOF

# ---------------------------------------------------------------- 4b. new files
# Every file this build adds to the disc or replaces on it, and the names the executable is built with: derive's plan
# step (steps/plan.py; tools/newfiles.py plan): $O/derived/disc.txt lists build-disc.py's --file/--add in order (the
# new files' order is the disc's layout), NEW_FILES the new names the executable's FILE_OFFSET_TABLE lacks (patch 0147),
# LANG_FILES the Spanish copies (LEnnn.EXT, a name each: the executable's table of which file each copies),
# LANG_OVL the overlays' Spanish copies (placeholders until step 5b). A screen >= 255 whose "file" has no .MAP/.TFS
# stopped the build there.
step "new files"
DISC_FILES=(); while IFS=$'\t' read -r opt spec; do DISC_FILES+=("$opt" "$spec"); done < "$O/derived/disc.txt"
grep -c '^--add' "$O/newfiles.txt" | sed 's/$/ new files on the disc/'
MAKE_NEW=()
if [ "$LANG_ON" = 1 ]; then
  echo "LANG_FILES=$LANG_FILES"
  MAKE_NEW=("LANG_FILES=$LANG_FILES" "LANG_BASE=$LANG_BASE")
fi
if grep -q '^NEW_FILES ?=' "$W/Makefile" 2>/dev/null; then MAKE_NEW+=("NEW_FILES=$NEW_FILES"); echo "NEW_FILES=$NEW_FILES"; fi

# ---------------------------------------------------------------- 5. executable
step "executable ($W)"
# the executable's strings of the text source (keys of decomp/text/*.yaml; TEXT=us: none, the yaml's own text) and the
# codes of the mod font's extra glyphs, for decomp/tools/gen_text.py (patch 0090); the headers are made again when it changes
$PY tools/localize/executable/bank.py exe-bank "${TEXT:-us}" --font-glyphs "$FONT_GLYPHS" --font "$EXE_FONT" -o "$O/text-bank.json" --report "$O/text-exe-kept.txt"
MOD_VERSION=${MOD_VERSION-$($PY tools/version.py game)}
echo "version: ${MOD_VERSION:-(none)}"
make_exe() {   # make_exe TREE BANK PAD LOG [LANG]: the executable of TREE with the strings of BANK (padded to PAD's), LANG's tables
  $PY -m tools.city_residents --c-extra-header "$1"
  $PY tools/sdk_messages.py "$1"
  if [ -n "${DW_BUILD_CACHE:-}" ] || [ "${DW_CLEAN_NATIVE:-0}" = 1 ]; then
    $PY tools/native_build.py "$1" "$2" "$3" "$4" $MAKE_PMM ${FPS:+FPS=$FPS} ${FONT:+FONT=$FONT} \
      "${MAKE_NEW[@]}" ${5:+LANG_BUILD=$5} "MOD_VERSION=$MOD_VERSION"
    return
  fi
  cmp -s "$2" "$1/text-bank.json" 2>/dev/null || cp "$2" "$1/text-bank.json"
  if [ -n "$3" ]; then cmp -s "$3" "$1/text-bank-pad.json" 2>/dev/null || cp "$3" "$1/text-bank-pad.json"; else rm -f "$1/text-bank-pad.json"; fi
  docker run --rm --user "$(id -u):$(id -g)" -e HOME=/tmp -v "$1:/work" -w /work dw-build \
    make -j8 TOOLCHAIN=gcc $MAKE_PMM ${FPS:+FPS=$FPS} ${FONT:+FONT=$FONT} "${MAKE_NEW[@]}" ${5:+LANG_BUILD=$5} "MOD_VERSION=$MOD_VERSION" > "$4" 2>&1 || { tail -30 "$4"; exit 1; }
}
if [ "$LANG_ON" = 1 ]; then
  for lang in $LANG_LIST; do
    source=$lang; [ "$lang" = en ] && source=ours
    $PY tools/localize/executable/bank.py exe-bank "$source" --font-glyphs "$FONT_GLYPHS" --font "$EXE_FONT" \
      -o "$O/text-bank-$lang.json" --report "$O/text-exe-kept-$lang.txt"
  done
  $PY tools/localize/executable/padding.py "$O/text-bank-pad.json" $(for lang in $LANG_LIST; do echo "$O/text-bank-$lang.json"; done)
  for lang in $LANG_LIST; do
    tree=$W
    if [ "$lang" != "$LANG_BASE" ]; then
      tree=$W-lang-$lang
      rsync -a --checksum --delete --exclude .git "$W/" "$tree/"
    fi
    make_exe "$tree" "$O/text-bank-$lang.json" "$O/text-bank-pad.json" "$O/make-$lang.log" "$lang"
  done
else
  make_exe "$W" "$O/text-bank.json" "" "$O/make.log"
fi
# the tree's facts again, now with this executable's linker map (FILE_OFFSET_TABLE's offset: the patcher's; no derived
# byte reads it)
$LPY -m tools.derive facts --w "$W" --out "$O"

# ---------------------------------------------------------------- 5b. balance tables
# content/balance/*.json (docs/reference/combat.md) written into copies of the executable and overlays ($O/exe), and the
# wild Digimon overrides into patched .MAP files. With no override the copies are byte-identical; the engine layer
# (content/balance/engine/tables.json) must match the C tables (else: tools/balance.py sync).
# the heap the executable leaves against what the screens were measured needing (tools/heapcheck.py, docs/reference/memory.md
# "Heap"): stops the build when a screen would be short of heap (its loading would never end); HEAP_OK=1 lets it through
step "heap"
$PY tools/heapcheck.py "$W/build/us/psx/gcc/SLUS_010.32.elf.map" | tee "$O/heap.txt"
# The sweep predates replacement models. Check the full setup script (including
# paged added screens) against the archive and this target's compaction masks.
if [ -f "$O/DIGI.DAT" ] && [ -f "$O/with-new-screens/MAPHEAD.SCN" ]; then
  $PY tools/dws.py check-heap "$O/with-new-screens/MAPHEAD.SCN" \
    --map "$W/build/us/psx/gcc/SLUS_010.32.elf.map" --archive "$O/DIGI.DAT" \
    --facts "$O/derived/exe-facts.json" --json "$O/story-heap.json" | tee "$O/story-heap.txt"
fi
# SHOP_REL.BIN: the original's shop overlay, whose code the executable has (mk/version/us.mk: src/shop linked into main).
# checkShopMap and loadShopLibrary still read the file to OVL_SHOP_BASE (0x80080800) on the shop screens, and nothing
# runs or reads those bytes: the executable reaches that window only through DOOA's and DGET's symbols, after loading
# those overlays (tools/xref.py check). rule: the disc carries zeros of the size FILE_OFFSET_TABLE gives it (0x7E10:
# the same sectors), not the base disc's overlay
SHOP_SIZE=$(( $(sed -n 's/.*{ 0x[0-9a-fA-F]*, \(0x[0-9a-fA-F]*\), "SHOP_REL.BIN" }.*/\1/p' "$W/src/main/file_table_us.c") ))
shop_placeholder() { [ -f "$1/SHOP_REL.BIN" ] || head -c "$SHOP_SIZE" /dev/zero > "$1/SHOP_REL.BIN"; }
# MOV_REL.BIN: the STR player is ~2 KB of code; the rest of its image is the player's buffers, which the original link
# stored in the file with whatever the build machine's memory held (decomp src/mov/mov_bss_us.c: 253 KB of non-zero
# residue on the USA disc, a different one on every release). Each is written before it is read: MOV_ENV by
# MOV_initEnvironment and MOV_readFrame, MOV_VLC_TABLE by DecDCTvlcBuild (its first 0x11000 bytes, all DecDCTvlc2
# reads), the run-level buffers by DecDCTvlc2, the slice buffers by the MDEC's DMA, MOV_RING_BUFFER's slots by the CD
# stream (StGetNext reads a slot once its status, cleared by StSetRing, says filled). Validated in PCSX-Redux:
# the four movies played from this file with the buffers as built, zeroed, 0xAA and random ran cycle for cycle the same
# (CPU cycles at every 100th frame and at the end, VRAM at those frames, RAM after the movie but the buffers' own
# leftovers; with OP1, also through the landing screen to the next OP1). rule: the disc's MOV_REL.BIN carries these buffers as zeros (found by name in the linker map), so the
# package for other base discs need not carry the USA residue
mov_zero_buffers() {
  $PY - "$1/MOV_REL.BIN" "$1/SLUS_010.32.elf.map" <<'PY'
import re, sys
mov, mapf = sys.argv[1:3]
m = open(mapf).read()
base = int(re.search(r'^\.MOV\s+0x([0-9a-f]+)', m, re.M).group(1), 16)
names = ('MOV_ENV', 'MOV_VLC_TABLE', 'MOV_RING_BUFFER', 'MOV_SLICE_BUFFER_0', 'MOV_SLICE_BUFFER_1',
         'MOV_RUN_LEVEL_BUFFER_0', 'MOV_RUN_LEVEL_BUFFER_1')
found = {s: (int(a, 16), int(n, 16)) for s, a, n in
         re.findall(r'\.data\.(\w+)\s+0x([0-9a-f]+)\s+0x([0-9a-f]+)\s+\S*src/mov/mov_bss_us\.c\.o', m)}
if set(found) != set(names):
    sys.exit(f'MOV_REL.BIN: mov_bss_us.c gives {sorted(found)}, the build zeros {sorted(names)}: check the rule first')
data = bytearray(open(mov, 'rb').read())
for s, (a, n) in found.items():
    o = a - base
    if o < 0x40 or o + n > len(data): sys.exit(f'MOV_REL.BIN: {s} at {a:#x} is outside the file')
    data[o:o + n] = bytes(n)
open(mov, 'wb').write(data)
print(f'MOV_REL.BIN: {sum(n for _, n in found.values())} bytes of buffers zeroed ({len(data)} bytes)')
PY
}
step "balance tables -> $O/exe"
# (the balance maps, the wild Digimon of content/maps, are derive's balance step: they need no executable)
rm -rf "$O/exe"
$PY tools/balance.py build --exe-dir "$W/build/us/psx/gcc" -o "$O/exe" --no-maps | tee "$O/balance.log"
shop_placeholder "$O/exe"; mov_zero_buffers "$O/exe"
if [ "$LANG_ON" = 1 ]; then
  step "language patches and overlays"
  for lang in $LANG_LIST; do
    tree=$W; [ "$lang" != "$LANG_BASE" ] && tree=$W-lang-$lang
    dst=$O/exe-$lang
    rm -rf "$dst"
    $PY tools/balance.py build --exe-dir "$tree/build/us/psx/gcc" -o "$dst" --no-maps > "$O/balance-$lang.log"
    shop_placeholder "$dst"; mov_zero_buffers "$dst"
  done
  # Every target patch contains all bytes that ANY language changes. A pairwise diff from
  # English alone cannot restore a byte that Spanish and English share after Portuguese.
  $PY tools/langpatch.py multi --out "$O/lang" $(for lang in $LANG_LIST; do
    tree=$W; [ "$lang" != "$LANG_BASE" ] && tree=$W-lang-$lang
    echo "$lang:$tree/build/us/psx/gcc/SLUS_010.32.elf:$O/exe-$lang/SLUS_010.32"
  done)
  for p in $LANG_OVL; do
    IFS=: read -r lang b c <<< "$p"
    $PY tools/langpatch.py overlay "$O/exe-en/$b" "$O/exe-$lang/$b" | grep -v ' 0 bytes differ' || true
    cp "$O/exe-$lang/$b" "$O/lang/$c"
  done
  # The original filenames always contain English, regardless of boot language.
  cp "$O/exe-en/"* "$O/exe/"
  cp "$O/exe-$LANG_BASE/SLUS_010.32" "$O/exe/SLUS_010.32"
  cp "$O/exe-$LANG_BASE/SLUS_010.32.elf.map" "$O/exe/SLUS_010.32.elf.map"
fi

# ---------------------------------------------------------------- 6. disc
if [ "${NO_MOVIES:-0}" = 1 ]; then   # no movies (tools/skip-intro-movie.py); not needed for DuckStation since patch 0171
  python3 tools/skip-intro-movie.py "$O/exe/SLUS_010.32" "$O/exe/SLUS_010.32.elf.map"
fi
step "disc build/$NAME.cue"
# the executable and the overlays from $O/exe, every other file of the plan of step 4b (derive's: the gate --derived
# stops the disc when a file is neither in its manifest with the same bytes nor authored)
SEEK=(); [ "${SEEK_ORDER:-1}" = 1 ] && SEEK=(--seek-order)
$PY tools/build-disc.py "$NAME" --from "$O/exe" --relayout "${SEEK[@]}" --derived "$O/derived/manifest.json" "${DISC_FILES[@]}" \
  | awk '/^SCN\/.*sectors more than the original/ { print } { last[NR % 3] = $0 } END { for (i = NR - 2; i <= NR; i++) if (i > 0) print last[i % 3] }'
# (a file that outgrows its sectors, DG.SCN with a long translation: the files after it move and FILE_OFFSET_TABLE is
# rewritten; docs/mods/dws.md "If DG.SCN grows")
# the BIOS reads only the root directory's first sector: SYSTEM.CNF must be in it, or the disc does not boot
$PY - "$ROOT/build/$NAME.bin" <<'PYEOF'
import struct, sys
f = open(sys.argv[1], 'rb')
def sec(n): f.seek(n * 2352 + 24); return f.read(2048)
lba = struct.unpack_from('<I', sec(16), 158)[0]
d, o, names = sec(lba), 0, []
while o < 2048 and d[o]:
    names.append(d[o + 33:o + 33 + d[o + 32]]); o += d[o]
if b'SYSTEM.CNF;1' not in names:
    sys.exit(f'{sys.argv[1]}: SYSTEM.CNF is not in the root directory\'s first sector ({len(names)} entries fit): the disc would not '
             'boot; put new files in a folder')
PYEOF
echo "build/$NAME.cue ready"

