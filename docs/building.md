# Building Horizon from source

The everything disc includes all patches, the extended story, eight languages and
all imported species. A build from the same sources and settings as a release
must reproduce that release's image SHA-1.

## Which build

| You want to | Use |
|---|---|
| Play | No build: patch your disc, see the [players' guide](release/README-players.md) |
| Change something and test it | `python3 -m tools.dev build`, cached, see [incremental builds](developer-cache.md) |
| Reproduce or verify a release | The from-zero commands below |

Both builds need the requirements and the steps below up to
`tools/decomp-build.sh regenerate`; `tools.dev` does the rest itself. Release builds
through `tools/release.py` keep the from-zero path.

## Requirements

- Linux or WSL, git, Python 3.10 or newer with venv/pip, a C/C++ compiler,
  make, rsync, and Docker with a running daemon accessible to your user.
- Player replay uses the Python standard library; no NumPy or Pillow is required.
  CMake is needed only to configure mkpsxiso.
- The decompilation's Docker toolchain (`tools/decomp-build.sh image`).
- [mkpsxiso](https://github.com/Lameguy64/mkpsxiso), including `dumpsxiso`;
  build it inside the checkout as shown below.

- Your Digimon World USA disc, SLUS-01032, as a raw `.bin` and `.cue` image.
  Expected image SHA-1: `5611645da66183e30d11fb6c11a2784ff47e1fdb`.
- Your Digital Card Battle, Digimon World 2 and Digimon World 2003 discs for the
  imported species. `tools/discs.py` identifies supported releases. Source readers
  accept raw 2352-byte or cooked 2048-byte images and verify the files used.
  Use European World 2003 or Japanese World 3; USA World 3 is unsupported.
  See the [supported-release matrix](data/source-releases.md). The examples below
  use European World 2003.

## Steps

Replace `REPOSITORY_URL` with this repository's clone URL. Check out the release
tag you want to reproduce before installing the tools. For an ordinary development
build, keep the branch tip instead. All subsequent commands run in `horizon/`.

```sh
git clone --recursive REPOSITORY_URL horizon
cd horizon
# To reproduce a release: git checkout vMAJOR.MINOR.PATCH
git submodule update --init --recursive
python3 -m venv .venv
.venv/bin/pip install cmake
git clone --recursive https://github.com/Lameguy64/mkpsxiso .tools/mkpsxiso
git -C .tools/mkpsxiso checkout a6b11ea86e67c189137ac50a4066044b3fdb0525
git -C .tools/mkpsxiso submodule update --init --recursive
.venv/bin/cmake -S .tools/mkpsxiso -B .tools/mkpsxiso/build -DCMAKE_BUILD_TYPE=Release
make -C .tools/mkpsxiso/build -j2
```

On Debian/Ubuntu, the host packages include `build-essential`, `git`,
`python3-venv`, `python3-pip` and `rsync`; install Docker following its platform
instructions. Confirm `docker info` works before starting the build.

Use the same absolute USA image path for extraction and decompilation regeneration:

```sh
tools/extract.sh '/path/Digimon World (USA).bin'
tools/decomp-build.sh image
tools/decomp-build.sh regenerate '/path/Digimon World (USA).bin'
tools/mods.sh prepare int
python3 -m tools.derive sources --out build/everything/source-games \
  --source-disc 'dcb=/path/Card Battle.bin' \
  --source-disc 'dw2=/path/World 2.bin' \
  --source-disc 'dw2003=/path/World 2003.bin'
SPECIES=all SPECIES_PROVIDER=imports TEXT=ours LANGS=en,es,pt-br,fr,de,it,ja,ca \
  DERIVE_JOBS=1 W=$PWD/build/decomp-int NAME=everything DW_HEAP_MAP=/nonexistent \
  story/mods/what-the-island-forgot/build.sh
sha1sum build/everything.bin
```

The output is `build/everything.bin` and `build/everything.cue`. Use absolute paths for `W` and
output directories. `DERIVE_JOBS=1` is the reference setting; a higher value is faster and gives
the same bytes, because story passes that write shared maps preserve recorded order. See [derive.md](derive.md) for generated files and
[patcher.md](patcher.md) for making a release package. The patcher's repeated
`--source-disc GAME=IMAGE` arguments provide the same three source games.

## Executable and hardware

`decomp/` references [jype0/dw_decomp](https://github.com/jype0/dw_decomp), pinned
to commit 83f99c5. `tools/mods.sh prepare int` applies our patches in order with
`git am`; assembly and game files are regenerated from your disc. The standard
build targets the original PlayStation's 2 MB of RAM.

The executable is compiled for each language with a shared address layout.
Language patches switch strings and translated resources at runtime. The
Japanese bitmap subset has its own licence; see [THIRD-PARTY.md](../THIRD-PARTY.md).

## Imported species

The imports step rebuilds the 175 imported models from the player's source discs,
then applies our plain model deltas. No sibling research projects, emulator or
private converted models are needed on this path.

Recipes live in `content/imports/`, the provider in `content/models/imports/` and our
edits in `content/modeldelta/`. Source and result hashes are verified. See
[model editing](../tools/models/README.md) for `tools/models/edit.py`.

The standalone authoring converters also support `DCB_ROOT`, `DW2_ROOT` and
`DW3_ROOT`, defaulting to sibling extraction projects named `digimoncardbattle`,
`digimonworld2` and `digimonworld2003`. The everything build uses the bundled
readers and the source discs above instead.

## Disc-derived artwork and record originals

Localized signs and tournament banners are masked deltas against the player's own
images, storing only changed pixels. They are committed for all eight languages
under `content/localized/signs/delta/` and
`content/localized/tournament/delta/`; the build needs no private localized art.
Full artwork used to author them stays untracked in `build/localized-src/`.
Developers regenerate with `tools/localize/signs.py --make-deltas` and
`tools/localize/build.py --make-deltas`.

Record originals are also rebuilt from the four player discs. The 37 models and
four textures use plain deltas under `content/record-originals/`; native DW1
records copy their source model and animation donor, while four cross-game
records use the same Card Battle and World 2 importers. The provider verifies
source, delta and target hashes before writing DIGI.DAT. There are no private
model, texture or artwork prerequisites.

## Checks

```sh
PYTHONPATH=tools python3 -m unittest tools.test_languages tools.test_modeldelta tools.test_pysum tools.test_derive_units
python3 tools/dws.py types --check
python3 -m tools.derive verify --out build/everything
```

Compare both the image SHA-1 and every file's SHA-1 with the reference release
built from the same patch series. A release made with an older series is a
different reference even when its version label is unchanged.

The executable embeds a Git-derived version. Building a branch tip or a new
public-history root can therefore change its bytes even when the patches match.
For comparisons between checkouts, set the same explicit `MOD_VERSION` on both
build commands (for example `MOD_VERSION=v0.1.0`); this does not make different
source trees equivalent. Expected output image hashes are recorded in the
reference package's `manifest.json`, in each variant's `outputs` map.

See [the patcher guide](patcher.md) for release manifests and packages.

## Toolchain evidence

The checksum proof for this cleanup uses mkpsxiso commit
`a6b11ea86e67c189137ac50a4066044b3fdb0525`, Python 3.14.8 and CMake 4.4.4.
The local `dw-build` Docker image ID is
`sha256:7635f9553c5b3789c2a91f2abf031fa7ec62217728f9f0b95264ea388c605b2a`.
That local image ID is evidence, not a downloadable registry pin. A release must
retain its own tested tool commits, versions and container identity beside its
output checksums; different host-tool versions require another byte comparison.
