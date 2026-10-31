# Incremental everything builds

After the prerequisites in [building.md](building.md), run from this checkout:

```sh
python3 -m tools.dev build --jobs 8
python3 -m tools.dev build --lang en
python3 -m tools.dev build --lang en --run
```

For quick English playtests on a 16-core host with spare CPU, use
`python3 -m tools.dev build --lang en --jobs 8 --run`. The default four derive
workers leave more CPU for other sessions; `--jobs 8` also works for the full disc.

The first command builds all eight languages. `--lang en` produces a **test build**
with English only: it changes the language picker, executable padding and disc
contents, so compare it with an English-only clean build, not an eight-language
release. Comma-separated subsets must include English, the base for the on-disc
overlays. `--run` boots PCSX-Redux with its original 2 MB RAM and stops it after
60 seconds (change with `--run-seconds`). It uses port 39129 unless `EMU_PORT` is
set; it needs the local emulator installation described in [08-emulator.md](developing.md).

`--dev-save` adds the development helper `tools/dws/examples/dev-save.dws`, where talking to Jijimon opens the save
machine; `tools/dev/saves/capture_save.sh` and `tools/dev/playtest/species_proof.py --save` need it. Players' discs never have it.

Outputs are `build/dev-everything.bin` and `.cue`. `--name NAME` selects another
output name. `build/NAME-timings.json` records stage seconds and the image SHA-1.
The command creates a private, detached, patched decomp worktree under
`build/decomp-dev`, using the checkout's gitlink and `mods/patches`. It copies
regenerated assembly, linker sources and SDK headers from the local decomp seed.
A changed patch series refreshes this private tree; local tracked C edits must be
committed/exported before a refresh, and untracked sources preserved. The old
detached commit stays reachable under `refs/dev-build/<commit>` in the decomp repository. `--w PATH` uses an already prepared private
patched tree and also keys local uncommitted C contents.

The four player-disc locations use the release driver's variables:
`DW1_US_IMAGE`, `DCB_IMAGE`, `DW2_IMAGE`, `DW3_IMAGE`; defaults are under
`build/isos`. `ISOS` overrides the DW1 directory and `SOURCE_ISOS` the source
games' parent directory, for example
`ISOS=/path/isos/digimon-world SOURCE_ISOS=/path/isos python3 -m tools.dev build --jobs 8`.
This command requires its own `extracted/` directory,
refuses a symlink there, and replaces the generated output folders each time.
One build may run in a checkout at a time. `--jobs N` defaults to four derive
workers; native compilation defaults to eight workers (`NATIVE_JOBS`).

## Cache correctness and storage

`DW_CACHE_DIR=/path/to/cache python3 -m tools.dev build` overrides the default
`build/cache/`. Entries and blobs are content-addressed with SHA-256. Indexes
only suggest entries: every input and cached output is hashed before reuse.
Corrupt, incomplete or missing entries are misses. Published files use atomic
renames and restored outputs are independent copies. Timestamps never select
cached results. Cache artifacts contain data from the player's discs: keep this
folder private and outside releases. It can be deleted at any time.

Extraction keys include the entire image's SHA-1, extractor code and binary.
Derived units record actual opens (including failed opens), file probes,
directory membership, preimages of in-place edits and all written artifacts.
Directory membership catches added/deleted glob matches. All build tool sources,
recipe settings, environment and interpreter identity are also keyed. Units that
write outside the generated build directory, or run unrecorded subprocesses,
fall back to ordinary execution. Preparation, finalization, checks, manifests,
file-layout planning and image assembly continue through the normal build path.
Map/cut-out rendering is cached per screen. Compiled `SCRN.DAT` records also have
individual entries keyed by parsed screen data, script text, assembler options and
the codec's source/data fingerprint. Their reads remain dependencies of the enclosing
archive even when a record hits the cache; unsafe record I/O disables archive reuse.
Cached story compilation uses private recipe-map copies. The first English pass
allocates any new saved names; subsequent passes read those locks and can overlap.
Only the files each pass actually writes are replayed into the shared map folders,
in the original recorded order. This also preserves the last writer when some
passes hit the cache and others rebuild. Uncached/reference scheduling is unchanged.

Native results are keyed per language by the pinned decomp, patch series, actual
compiler sources, bank/padding, make arguments and Docker image ID. A native miss
starts with clean objects and generated text headers unless it can verify a common
compile from the same build family. It checks every shared object, dependency file
and generated header against a checksummed manifest, and requires identical common
sources, settings and toolchain before changing the language bank/selector. This
preserves the original driver's English-to-other-language object sharing. Its optional C object
cache hashes preprocessed source and headers plus compiler options and image ID;
it restores both object and dependency file. A direct lookup rehashes the recorded
dependencies and also keys the include/source filename namespace, so an added
header cannot silently shadow a previously selected one. Code using assembler file inclusions
bypasses this object cache. The normal uncached compiler remains the fallback.

Absolute output paths are part of entry identity, because generated logs and
species records contain those paths. A shared cache directory does not imply
cross-checkout artifact reuse. Different output names retain independent entries.
The unchecked legacy model-copy shortcut is disabled. Portrait scratch data lives
inside the fresh output folder and is covered by the verified species entry.
No cache entry substitutes for the existing heap and derived-file gates.

## Clean verification and releases

```sh
python3 -m tools.dev build --no-cache
# For the same test subset:
python3 -m tools.dev build --lang en --no-cache
python3 -m unittest tools.test_build_cache tools.test_compiler_cache
```

`--no-cache` recreates derived/extracted data and starts with a clean English native
compile; other languages may share its verified common objects within that build.
It neither reads nor populates the developer caches. When comparing builds,
preserve the same source commit, disc releases, language selection and version
stamp; for controlled development comparisons, use the same explicit
`MOD_VERSION=v0.1.0` for both builds. Compare all extracted disc-file SHA-1s as
well as the image SHA-1. A matching image alone does not diagnose a difference.

`tools/release.py` stays on the **from-zero path**, with a new private compiler
and output tree. It removes developer cache flags from its environment, disables legacy model reuse
and uses a new output-local portrait directory; release
publication does not depend on accepting an incremental result. The developer
cache is deliberately opt-in and is not enabled for the browser/player replay.
