# Digimon World: Horizon

Horizon is a fan mod of *Digimon World* (PlayStation, 1999). It is built on the community decompilation of the game,
and it is delivered as a patch that you apply to your own disc. Original disc images are not included.

> Digimon is a trademark of Bandai (Bandai Namco). Horizon is an unofficial fan project, not affiliated with or
> endorsed by Bandai, Bandai Namco or Sony. To play it you need your own discs of the four games listed below.

## What it changes

- **What the Island Forgot**: a new story woven into the original one, with new places beyond the familiar screens.
  The Digimon you recruit move into File City. EXTENDED STORY in OPTIONS switches back to the 1999 story.
- **Less waiting**: double-speed battles on R2, START skips an evolution's animation, five training sessions in one
  go at the gym, field battles that start the moment they are triggered. None of it changes what your partner gains.
- **60 frames per second**: the world, battles and tournaments are drawn at up to 60 fps; the game keeps its original
  timing underneath (your partner ages, trains and gets hungry exactly as before).
- **Eight languages, switchable in game**: English, Spanish, Brazilian Portuguese, French, German, Italian,
  Japanese and Catalan, with a first-boot language picker and Japanese bitmap font.
- **Optional cheats**: care and stat editing, evolution, teleportation, save/load and return to title.
- **An evolution guide**: the evolution chart shows what each evolution asks for.
- **Digimon from three more games**: Digimon from Digital Card Battle, Digimon World 2 and Digimon World 2003 join
  the evolution chart, Megas included, each with its own animations.
- Many fixes and comforts: original bugs fixed, larger limits (screens, items, species), a reworked OPTIONS menu,
  a Japanese base disc with its own controls.

## Play it

You need your own Digimon World raw `.bin` + `.cue` image and source discs for
Digital Card Battle, Digimon World 2 and Digimon World 2003. The patch accepts the USA base disc
(SLUS-01032), the five European releases and the Japanese Rev 1 disc, each checked against its redump checksum.

- **In the browser**: [dw1horizon.com](https://dw1horizon.com) builds the patched disc on your computer from your
  own disc. Nothing is uploaded.
- **On the command line**: download a release and run its `dwpatch.py` with Python 3.10 or newer,
  supplying all four disc images. Commands and release dependencies:
  [the player guide](docs/release/README-players.md).

Load the patched `.cue` in an emulator such as DuckStation or PCSX-Redux, or burn it.

## Build it from source

Follow [the source-build guide](docs/building.md) for checkout, host tools,
extraction of your four discs, decompilation preparation and the complete build
command. It also explains how the version stamp affects checksum comparisons.

## What is in this repository

| Path | What |
|---|---|
| `mods/patches/` | our changes to the game's code: one series of patches on the decompilation (`decomp/`, a submodule pinned to an upstream commit) |
| `content/` | numeric gameplay configuration, authored changes, model generators and disc replay recipes; see its [data policy](content/README.md) |
| `story/` | the story as source: the language's core library, the base story (keys only, no dialogue), the story mods (`what-the-island-forgot`) |
| `text/` | our translations in eight languages, by key |
| `tools/` | the builders: `tools/derive` (every file made from the player's game data), the disc and executable builds, the patcher (`tools/patcher/dwpatch.py`), and the authoring tools (maps, models, scripts, sound, font) |
| `docs/` | for players and developers ([docs/README.md](docs/README.md)) |

## How disc files are reconstructed

Models, scripts, maps, sound banks and textures are rebuilt locally from the
player's discs by our tools, each checked against the SHA-1 the release expects.
The executable is compiled from the patched decompilation when building from
source. Player packages reconstruct it using a patch against the player's disc.
The [patcher guide](docs/patcher.md#what-the-release-still-carries-that-is-not-ours)
describes the current package's remaining literal-data publication issues;
local reconstruction alone does not establish the provenance of every patch byte.

## Licence

MIT ([LICENSE](LICENSE)) for our code and our content (story, text, art). The decompilation and the other third-party
pieces keep their own licences. Digimon and the original game belong to their owners.
