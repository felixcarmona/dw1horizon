# The patcher and the release

A release reaches players as a patch against their own disc, applied by one Python script,
`tools/patcher/dwpatch.py` (Windows, macOS, Linux; Python 3.10+ standard library), or by the same code running in the
browser (`web/`). The players' guide is [release/README-players.md](release/README-players.md).

## What a release contains

```
release/
  dwpatch.py          the patcher
  isowriter.py        the disc writer (an ISO 9660 / CD-XA writer in Python)
  manifest.json       the accepted base discs (redump checksums), the files to read from them, every hole's SHA-1
                      (per base where it differs), the output's SHA-1 per base
  everything.dwp      the patch: how every file of the patched disc is assembled
  bases/              one mapping per supported release (mods/base-discs/dw1-*.json)
  bundle/             our tools and our data: what tools/derive reads to rebuild the derived files
  audit.txt           per file: where each byte comes from
  README.md           docs/release/README-players.md
```

One package serves every supported base disc: Digimon World (USA), the five European releases (Europe, France,
Germany, Spain, Italy) and Japan Rev 1.

## File reconstruction

Format 3 stores a file layout and operations that copy whole files or byte ranges
from the player's discs, reuse earlier output, apply binary differences, or fill a
hole with a locally rebuilt file. Derived models, DIGI.DAT, scripts, maps, sound
banks and translated textures are holes; every reconstructed file is hash-checked.

Compiled executables, overlays and language banks use per-file, per-base binary
differences against manifest-selected source files. The current packaging pass
eliminates their raw literal operations and delta extras. Such differences still
represent transformed input, so the publication gate checks reconstructed data and
source availability as well as raw literals. Remaining regional mapping data is
inventoried separately. See [the publication boundary](#what-the-release-still-carries-that-is-not-ours)
and the audit sections below.

## Base discs

Each supported release has a mapping (`mods/base-discs/dw1-<release>.json`, made by `tools/basedisc.py`) that says,
for every file of the USA disc, what that release gives: the same file, a renamed one, the release's own (the movies),
a small patch, or a file made by a localize tool (Japan: the images with Japanese text, redrawn in our words). Files
only the USA disc has (the executable, the overlays, the scripts) are never read: the build makes everything it needs
without them.

European bases keep their own TITLE256/TITLE2 artwork with the HORIZON stamp;
Japan Rev 1 uses its localized images and retains two hidden sprite sorting
coordinates. Enemy lists are regenerated from content data. The Japanese output
therefore intentionally differs by four MAYO00 data bytes from the older
normalized reference; see [the map normalization explanation](mods/japanese-map-remainder.md).
These regional inputs receive their own derived-file and complete-image hashes.
The USA output remains unchanged.

World 2003 Europe and World 3 Japan supply the same 57 recipe model files,
including meshes, animation tracks and textures. Japan needs checksum verification;
its verifier and inventory are bundled even when recording with Europe. USA World 3
remains identifiable but unsupported. Its historical normalization payload is
excluded from this public source tree and from player bundles.

## Checks

- Input: the image is identified by its SYSTEM.CNF and checked against its redump size and SHA-1; a missing file, a
  `.cue` naming the wrong file, a CHD/ECM/PBP or archive, a 2048-byte `.iso`, another game or region, a modified dump:
  each has its own message.
- The patch file's SHA-1 against the manifest; every rebuilt file against its SHA-1 for that base (a mismatch names
  the files and writes nothing); the output's SHA-1 against the release's (written as `.part`, renamed only when it
  matches), then a `.cue`.

## Commands

```
# Low-level packaging; tools/release.py supplies these inputs and runs the gates.
python3 tools/patcher/dwpatch.py make-release --original '/path/World (USA).bin' \
    --variant everything=build/everything.bin --base 'jp1=/path/World (Japan) (Rev 1).bin' \
    --source-disc 'dcb=/path/Card Battle.bin' --source-disc 'dw2=/path/World 2.bin' \
    --source-disc 'dw2003=/path/World 2003.bin' -o build/release
# In the unpacked release folder:
python3 dwpatch.py apply '/path/World (USA).cue' \
    --source-disc 'dcb=/path/Card Battle.bin' --source-disc 'dw2=/path/World 2.bin' \
    --source-disc 'dw2003=/path/World 2003.bin' [-o OUT]
python3 dwpatch.py check DISC.bin                                  # only the input check
python3 dwpatch.py info
```

make-release records which of our files the derive build opens (that becomes `bundle/`), verifies the bundle alone
rebuilds every hole byte for byte, writes the patch and the audit, and applies the package to each `--base` disc
(their output SHA-1s go in the manifest). `apply` copies `bundle/` to a temporary folder, writes the base disc's files
the build reads into it, runs `python3 -m tools.derive build --recipe everything`, checks every hole and streams the
patched disc. The browser runs the same jobs in Pyodide workers (`web/README.md`).

## What the release still carries that is not ours

Models, textures, localized signs and tournament banners are rebuilt from the
player's discs. Program files use per-base binary differences; raw program
literals and delta extras are eliminated by the current packaging path. Differences
are transformed data, so that observation alone does not establish authorship.

The mandatory gate inventories payload literals, mapping bytes, delta extras and
out-of-source differences, and independently audits reconstructed data. Retained
regional mappings and unavailable source tables can still block publication. Read
the exact package's `literal-gate.json` and reconstructed-data report; a diagnostic
build that exits with a refusal is not publishable. The later audit sections
explain the evidence and limits. Clean omits the unsupported historical USA World 3
normalization payload; inventories from private snapshots cannot substitute for an
audit of this tree's actual package.

## Release save compatibility

`make-release` runs `tools/dev/saves/releases.py check` before packaging. The stripped
save corpus in `tools/dev/saves/corpus/` preserves published saves without the game's
header artwork. `--save-check-emu` also loads each save in the target disc using the
2 MB emulator checker. See [save format](reference/save-format.md#every-releases-save).

## Relocated code copies

Format 3 packages copy moved code from each player's base disc and apply address
fixups recorded by `tools/patcher/reloc.py`. The `fix` table XORs only changed
address fields after a code copy. An `o` operation reuses a range of an earlier
output file, including identical overlay runs. These operations reduce literal
bytes in the package while preserving the output disc.

## Release versions

A release is an **annotated git tag `vMAJOR.MINOR.PATCH`** on the commit it is built from; the owner sets it when he
wants a release. One rule gives every build its version and date, `tools/version.py` (`python3 tools/version.py`
prints both):

| HEAD | version | date (UTC, YYYY-MM-DD) |
|---|---|---|
| the commit of the latest tag `vX.Y.Z` reachable from it | `X.Y.Z` | the tag's |
| N commits after that tag | `X.Y.Z-dev.N+HHHHHHHH` (the first 8 hex digits of HEAD) | HEAD's commit date |
| no Git executable or checkout metadata | `0.0.0-dev+unknown` | unknown |
| no tag yet | `0.0.0-dev.N+HHHHHHHH` (N = the commits of HEAD) | HEAD's commit date |

Only HEAD and the tags count, not uncommitted changes: one commit builds one disc. Lightweight tags and other names
(`v1.0.0-rc`) are ignored. Where the version shows:

- **the game**: "v0.1.0" in the bottom left corner of the title screen (Press Start) and of the title menu, small and
  grey (patch 0257; `tools/build-full.sh` gives `tools/version.py game` to the executable's make as `MOD_VERSION`, a
  fixed 32-byte array, so a new version changes those bytes of `SLUS_010.32` only). Field START pause also shows the
  same string at (16, 8), above the clock, with the same grey and shadow (patch 0288). Empty `MOD_VERSION` draws
  nothing in either place; all eight languages share the string. The executable is authored: the
  package carries it and apply checks its SHA-1 like every other file, on every base;
- **the package**: make-release writes `version` and `date` into `manifest.json` (`--version` still overrides the
  version, never the date); apply's first line and `info` print `TITLE VERSION (DATE)`;
- **the web page**: `web/build-engine.sh` copies them into `engine/current.json` (`release_version`, `release_date`;
  `version` stays the engine's own hash, the page's cache key), and the page's footer shows "v0.1.0 · 27 Oct 2026",
  the date in the page's language (`Intl.DateTimeFormat`).

Use the [release pipeline](#release-pipeline) to build, verify and package. Public deployment follows [Pages releases](release/releasing.md).
Tag creation remains explicit; the pipeline accepts an existing annotated tag.
The low-level `make-release` and engine commands above describe individual stages,
not an alternative to the pipeline's checks.

## Release pipeline

From a clean developer checkout, use `python3 tools/release.py v0.1.0`. The owner must already have created the
annotated tag on HEAD. The command never creates or moves tags. Omit the tag for a development commit; if HEAD
is exactly a release, supply its tag explicitly. Run this from the checkout that should supply the deployed page.

```sh
python3 tools/release.py --dry-run                     # print the whole job, no writes/builds/deploy
python3 tools/release.py --preflight-only              # real clean/version, save-file and fast unit checks only
python3 tools/release.py v0.1.0 --save-check-emu        # full release and USA browser check; no deployment
# Optional deployment to your own server (separate from GitHub Pages):
python3 tools/release.py v0.1.0 --deploy
# Explicit GitHub publication opt-in, after all checks succeed:
python3 tools/release.py v0.1.0 --publish --notes-file /absolute/path/release-notes.txt
```

For a cut from an already verified final proof, `--prepare-reuse` seals the exact git tree,
package, seven retained output images, audit metadata and engine. After tagging the same
tree, `--reuse-from HANDOFF` restamps the fixed title buffer, recomputes all executable
deltas and output pins, and reruns publication, seven streamed writer comparisons, an
isolated Python 3.10 USA writer and the independent browser checksum. It performs no
native build or graph recording. All mismatches fail closed. See the commands and
retention requirements in the [v0.0.1 owner checklist](release/v0.0.1-owner-checklist.md#fast-cut-from-a-verified-final-proof).

Prerequisites are the normal native developer setup ([building.md](building.md)): this checkout's USA `extracted/`, built
`.tools/mkpsxiso`, the Python dependencies listed in the build guide, the `dw-build` Docker image, and a decomp repository with
generated `asm/`, `build/us/psx/generated/` and `external/psyq_headers/`. `DECOMP_REPO` defaults to this checkout's
`decomp/`; it is read as a seed. The command creates its **own detached decomp worktree**, at the parent repo's pinned
gitlink commit, applies every `mods/patches/*.patch` in order, and copies the generated inputs. It never prepares,
resets or builds the shared decomp checkout. Browser prerequisites are those of `web/test/suite.sh` (Chromium and
puppeteer-core); deployment needs the existing nginx destination permissions. `web/build-engine.sh` continues to
use its shared Pyodide download cache; the pipeline sets `ENGINE_WORK` to `OUT/engine-work` for private scratch
trees. Use a deployment destination you control.

Input paths come from environment variables (all accept absolute paths or `~`):

| Variable | Default |
|---|---|
| `ISOS` | `build/isos/digimon-world` |
| `DW1_US_IMAGE`, `DW1_EU_IMAGE`, `DW1_FR_IMAGE`, `DW1_DE_IMAGE`, `DW1_ES_IMAGE`, `DW1_IT_IMAGE`, `DW1_JP1_IMAGE` | the corresponding standard `.bin` filename under `ISOS` (see `web/test/suite.sh`) |
| `SOURCE_ISOS` | `build/isos` |
| `DCB_IMAGE` | `$SOURCE_ISOS/digital-card-battle/Digimon Digital Card Battle (USA).bin` |
| `DW2_IMAGE` | `$SOURCE_ISOS/digimon-world-2/Digimon World 2 (USA).bin` |
| `DW3_IMAGE` | `$SOURCE_ISOS/digimon-world-2003/Digimon World 2003 (E) [SLES-03936].bin` |

The sequence is: clean tree/tag and file save gate; fast unit regressions; input SHA-1 inventory; private C patch
replay; source-disc extraction; the recipe's everything build with original **2 MB** settings; `heapcheck.py` and
the story compiler's heap check using the final executable map; offline `tools/selftest.sh`; `make-release` with
all seven bases and three source discs (its file save gate always runs); standalone shipped-patcher applies for USA and Japan Rev 1, checked against the manifest; engine build into a new candidate folder;
the browser suite's USA runner served locally with that candidate, requiring both success and an independent OPFS
SHA-1 matching the package manifest; package-only tarball; unchanged checkout/version check. `--deploy` additionally runs `web/deploy.sh`; it is off by default.
Offline selftests run with the original tool defaults, with disc recipe settings cleared from their environment.
Every command must succeed before the next step starts. Existing selftest or heap failures block deployment;
the command does not waive them. No emulator is launched unless an emulator option is given.

`--save-check-emu` also Continues/resaves every published save through make-release's emulator gate.
`--record-save /absolute/path/seed.mcd` additionally runs `tools/dev/saves/releases.py add`, including its emulator
checks, into a private copy at `OUT/save-corpus/`. Review and commit only the new `.json`/`.mcd` pair afterwards,
as described above; this preserves the tagged checkout during the build. `--skip-browser` explicitly skips the
USA browser gate. `--jobs N` sets derive concurrency (default 4); the native executable builder keeps its existing
make limit. The sequence runs only one heavy stage at a time.

`--out DIR` must name a new folder (default `build/releases/<UTC timestamp>/`). It retains the package, candidate
engine, tarball, optional save corpus, browser log and `summary.json`. The summary prints every step's elapsed
seconds, total time, input and output SHA-1s, and a SHA-1 for every packaged/engine file, including on a late
failure. Native outputs are under `build/release-<folder-name>*`; decomp and per-language trees remain available
for inspection. Delete those explicitly when no longer needed, unregistering the private decomp worktree with
`git -C "$DECOMP_REPO" worktree remove <OUT>/decomp` first. A failed run is never resumed in place: use a new output
folder after fixing the cause.

Engine records are cached locally at `build/release-records/<SHA256>/`. The fingerprint covers every bundled
derive input, base/source IDs and engine recorder/scheduler source. Identical graph inputs reuse USA/JP1 records;
any potentially graph-changing input gets a fresh folder. This is deliberately conservative: dynamic file reads
can change without changing job names. Literal patch/executable or release metadata changes alone do not invalidate
the records. No unvalidated older `RECORDS` directory is accepted from the environment.

Deployment and publication are off by default. Preparation alone writes only local artifacts. `--publish` requires an owner tag and an existing notes file, pushes only that tag
to `origin` (`--remote` can select another configured Git remote), then calls `gh release create --verify-tag` with
the packed **package**, never a source or output image. GitHub CLI must target the same repository as that remote.
It never changes repository visibility or site access policy. Deployment leaves the site's hosting
configuration unchanged.

## 13. Literal provenance and a final copy pass

`audit.txt`'s historical word **authored** is an encoder eligibility flag. It includes the rebuilt original program;
it is **not** evidence that every byte is our own work. `lit_usa` is only the subset of literals previously found in
USA code files but unavailable through the regional relocation maps. Audit the **entire literal blob**, including
translated overlays, buffers and language banks.

The developer tools below inventory every literal operation by destination file, byte offset, length, operation
index, blob offset and SHA-1. Their evidence files contain offsets/hashes rather than game bytes:

```sh
python3 tools/patcher/literal_audit.py scan --release build/release-pkg \
  --isos /path/to/player-discs --output build/literal-evidence
python3 tools/patcher/literal_provenance.py --release build/release-pkg \
  --evidence build/literal-evidence --build build/everything \
  --image build/everything.bin --decomp decomp
python3 tools/patcher/literal_audit.py refine --release build/release-pkg \
  --evidence build/literal-evidence --output build/release-refined
```

`scan` needs a C++17 compiler on a POSIX developer host. It indexes every 16-byte window of every literal, scans every
byte alignment in the official `.bin`/raw `.iso` files under `--isos`, and verifies exact matches before extending
them within file/literal boundaries. It searches logical files across sector boundaries, license data, and complete
raw images (including directories, headers and unallocated areas), and a complete sector user-data view
for archives omitted from the ISO directory tree (notably DW3). Fan patch/translation folders are excluded;
unreadable image candidates are listed in `scan-errors.json`. Every supported DW1 base must match its manifest
SHA-1. Uniform windows use the longest source run, avoiding thousands of tiny zero-copy records. Both overlapping
seeds and final fragments shorter than 16 bytes are retained when a verified 16-byte seed proves them.

`literal_provenance.py` splits the original literal operations further at match and linker input-section boundaries:

- **a:** new patch symbols absent from the pinned decomp source, authored replacement text, and generated layout,
  version, startup and padding records;
- **b:** original-derived functions and C program tables, plus reconstructed PsyQ library code/data. This is a
  conservative provenance category: an original function that our patches modify stays here. Its measured byte
  count is the complete literal extent mapped to that original-derived symbol, **not** a measurement of unchanged
  original instructions or an assertion of exclusive authorship;
- **c:** exact bytes found on a searched disc. Equality proves availability, not historical authorship or copyright;
- **d:** unresolved/mixed provenance, including short inherited buffer fragments and the Latin font
  compression tables (patch 0245 combines original game glyphs and authored glyphs);
- **e:** known third-party Japanese font material and generated encoding tables, from Fusion Pixel under the
  source-declared SIL OFL 1.1. This extra class avoids calling a licensed third-party font our own or unknown.

Matches take priority over the other categories. Section attribution is checked against the retained build's actual
binary bytes; differing post-link data stays unresolved except for the explicit generated layout/version fields.
`scan` also writes `mapping-literals.json` / `mapping-literal-totals.json` for hex data and fills in the regional
DW1 mappings and the DW3 USA normalization mapping. Those bytes are outside the DWP blob and must not be missed.
The refinement pass inventories them; it does not rewrite frozen import recipes.

Retain the build's language executables, linker maps, `derived/plan.json`, text banks and `lang/` outputs. Review
`provenance.json` and its input hashes (add `--refined-release build/release-refined` after refining for before/after totals); these source/symbol rules are evidence aids, not publication clearance.

`refine` rechecks the source hashes and every proposed range. It replaces only the intersection available on **every**
supported base, using the existing `r` operation with each base's own file/offset. The reserved source name `@raw`
addresses byte ranges in the input image, so license/directory/sector bytes can also supply copies; the shipped
reader seeks and reads just those ranges. `@userdata` similarly addresses the 2048-byte data portions of
sectors, crossing their raw headers when necessary. It compacts the remaining literals
and updates the patch checksum/size. The tool ships its current standalone reader, which the browser engine also uses. Neither needs a new opcode,
external package or native library. The compressed patch may grow because copy metadata replaces compressible literal bytes.
The original audit is explicitly retained as `audit-before-refinement.txt`; `runs.csv` and
`literal-refinement.json` describe the refined payload.

For an older release with an obsolete dependency bundle, `refine --bundle-from PACKAGE` can adopt a verified
standard-library-only bundle and its writer/players guide (the refinement tool supplies the current reader). It requires identical extraction lists, builder options, source-disc requirements and
all derived-file sizes/SHA-1s, including base-specific hashes. An old donor may still contain newer Python syntax;
compile its `bundle/tools` with Python 3.10 and apply the syntax-only DW2 diagnostic fix from `tools/dw2mmd.py`
when needed, recording the override hash separately. The donor manifest hash is recorded. Independently
apply and verify the resulting package; identical manifest claims alone do not validate a new bundle.

An exact match confined to another regional disc cannot become a copy from a disc the player does not own. Such
ranges remain class c and must be reported explicitly. Do not disguise their contents as XOR fix-ups. Before
publication, compare every assembled file (including the rewritten executable table and license) against the
unrefined package on every supported base, check disc hashes with the actual writer, and exercise standalone
Python 3.10 without NumPy/Pillow and the browser writer. Remaining b/c/d ranges and the separate mapping-data inventory require the owner's decision or
further work. This pass does not change any game bytes.

## 14. Mandatory literal gate and changed-build proof

Format-3 `make-release` runs `tools/patcher/literal_gate.py` after every variant,
bundle and standalone runtime file is complete. It includes the existing Japanese
font source/OFL notices. The everything frontend accepts only format 3 and its
derive recipe. An incomplete/audit-only manifest cannot receive a pass.

The gate freshly searches DWP literals, every base's binary-delta extras, and
inline mapping data throughout `bases/` and `bundle/`. Diff bytes addressing no
source are literals too (bspatch adds them to zero). Adjacent literal operations
are joined. Sources include logical ISO files, license data, raw sectors and the
complete sector-data plane. Known canonical regional/import mapping fragments
are also checked below the scanner's **16-byte seed** size. Source coordinates,
lengths and hashes go into `literal-gate.json`, never game-byte dumps. That report
binds the current manifest, patches, JSON, runtime and selected derive-plan hashes.

`delta_audit.py` also reconstructs program data and discovers its objects from
the current linker maps. It measures equal/different bytes for every base's
actual delta controls. Inherited data with fewer than 25% equal bytes over at
least 16 diff bytes requires exact witnesses on that player's four inputs;
mixed Latin font tables and inherited buffer objects always require verified sources. Missing witnesses
block publication and are listed by file, symbol, base, size and hash in
`delta_audits`. Licensed Japanese font data remains class e. These conservative
checks do not establish the provenance of every transformed byte; in particular,
passing a similarity threshold is not evidence of authorship.

The encoder searches complete pointer-bearing data records for exact copies of
their non-pointer fields. When a coarse assembly object differs, it also tries
the sized records retained in the current ELF. All non-pointer fields must
match together in one source layout, with at least 16 matching bytes in total;
individual fields may be shorter than the scanner seed. Copies use the pinned
corresponding file on each player's disc. Pointer fields still require current
ELF relocation evidence, and the gate still audits the complete coarse object
and its gaps. No release-specific refinement is needed for these short fields.

`codecopy.audit_literals(payload, build_dir, base_paths, plan=selected_plan)` must
freshly return any remaining literal ranges eligible for a per-file delta as
`{file, offset, length}` dictionaries. The builder passes its actual selected
variant manifest/plan. A three-argument query is accepted only when its freshly
read recorded plan exactly equals that selected plan; overrides require explicit
plan support. Any match or eligible range blocks publication. Missing
audit support, dead blob bytes, invalid controls, unknown operation/mapping
schemas and stale evidence cannot pass. Inline mapping data outside a source-aware
audit backend is unresolved class d and blocks publication, including short runs. New mods and imports use their current
build outputs, with no frozen function/range lists or exemptions. The native
scan needs C++17 when searchable literals remain; applying stays plain Python
3.10/Pyodide without NumPy or Pillow.

On failure, inspect the report, replace disc literals with source copies or
player-side derivation, and regenerate missing delta coverage from the current
manifest. Extend the inventory before adding an operation schema. Do not waive a
failure, reuse another release's pass, hide assets in address fixups or alter the
target merely to pass. Report exact unavailable-source sizes. The report counts
`short_literal_bytes`: arbitrary sub-seed runs and transformed provenance are
not cleared by byte matching. Conventional difference blocks are not raw
literals; a passing scan is not proof of exclusive authorship of their source.

Run the regressions with:

```sh
PYTHONPATH=tools python3 -m unittest test_literal_gate test_changed_build_proof -v
```

The changed-build harness selects an original function from the current map and
pinned C source, inserts a 16-NOP block, and changes an authored `say` string.
Use private disposable source trees under this worktree's `build/`, not shared
references; do not add the test edit to the shipping patch series.

```sh
python3 tools/patcher/changed_build_proof.py prepare \
  --build ../literal-2/build/reference --decomp build/changed-decomp \
  --story build/changed-source/story/mods/what-the-island-forgot \
  --output build/changed-edits.json
# Build these edited sources normally; retain independent images for every base.
python3 tools/patcher/changed_build_proof.py prove \
  --release build/changed-package --build build/changed \
  --baseline-build ../literal-2/build/reference \
  --baseline-image ../literal-2/build/reference.bin \
  --bases build/base-inputs.json --references build/changed-reference-images.json \
  --edits build/changed-edits.json --output build/changed-proof \
  --source-disc dcb=/path/to/dcb.bin --source-disc dw2=/path/to/dw2.bin \
  --source-disc dw2003=/path/to/dw2003.bin
```

Both input JSON files map every advertised base key to an absolute image path.
`prove` requires changed/moved functions and story containers, reruns the gate,
loads the shipped reader, compares every emitted file/license SHA-1 against the
independent images, then checks every streamed whole-disc SHA-1/size. XA and
license checks use the actual sector encoder, including EDC/ECC normalization.
Derived holes are independently hash-checked cached inputs; this is reconstruction,
not a fresh derive. Run under real Python 3.10 for that compatibility proof.

For real WebAssembly, run
`node tools/patcher/changed_build_wasm.mjs /absolute/pyodide-runtime /absolute/config.json`.
The JSON gives absolute `release`, `bases`, `references`, `glue` (`web/enginebuild`),
and new `output` paths, plus `source_discs` as `game=/absolute/image` strings.
It runs the shipped reader on all bases in Pyodide, forbids NumPy/PIL imports,
verifies gate input binding/cached holes, and records disc hashes/sizes. This uses
NodeFS and the browser's in-process tool adapter; it is not a browser-page/OPFS or
full-derive test. A prepared harness or synthetic pass is not a completed changed
full-build proof.

For a negative publication regression, `prove --expect-blocked` requires a fresh
gate refusal and then runs identity checks while retaining that refusal. The
WASM config uses `expect_blocked: true` for the same diagnostic. Neither option
changes the package gate or makes a blocked package publishable.

## Regional data provenance

The package reconstructs inherited buffers, fonts, UI records and item parameters
from the selected player's regional disc. Linker addresses are generated from
current relocation evidence; authored text and semantic fields are regenerated
from their source recipes. The mandatory publication gate independently checks
source pins, destination bounds, generated fields and all seven regional outputs.
Unknown data remains a release blocker. No original buffer subtraction payload
is bundled.

The [regional reference pins](reference/font-table-pins.json) retain the reviewed
output hashes and original 2 MB gameplay results. These reference images use the
previous version stamp; a new release generates and verifies its own manifest.
The fixed font capacities retain 187,888 bytes of heap, with all 320 checked
archive setups fitting and a minimum margin of 5,856 bytes.
