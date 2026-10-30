# tools/derive: the derived-files builder

Every file of the patched disc that is made from the game's data is made by one builder, `tools/derive`, in one
Python process: the same code runs in the developer's build (`tools/build-full.sh`), in the patcher on the player's
machine (`dwpatch.py apply`) and in the browser (Pyodide workers, `web/`). It reads only our sources (`tools/`,
`content/`, `story/`, `text/`, `mods/`, `docs/data/`) and the player's extracted files, and it gives the same bytes
on every machine.

```
python3 -m tools.derive steps                                    the steps
python3 -m tools.derive facts --w DECOMP_TREE --out build/NAME   the executable's settings the build depends on
python3 -m tools.derive build --recipe everything --out build/NAME [--jobs N] [--strict] [--record] [--checks]
python3 -m tools.derive units --out DIR --recipe everything --json   what a worker runs
python3 -m tools.derive unit  --out DIR --recipe everything --step S (--index N | --prepare | --finish | --build)
```

## The recipe

`tools/derive/recipes/everything.json` pins the build: its environment (text source, languages, story mods, species
provider), the story sources in the order they are compiled (the order changes bytes), and the map recipes of the
story mod. A new story file or map recipe is added there. `species-pins.json` holds the SHA-1 of every model and
texture a species provider hands over. The four player discs supply the game inputs.

## The steps

| Step | Makes |
|---|---|
| models | the partner and NPC models made from the disc's own models (`content/models/*`) |
| imports, record_originals | source-disc model replay and our deltas, before species assembly |
| overlays | the imported species' field animations, one unit per species |
| species | DIGI.DAT: every species of `content/species`, with the imported provider's models and the record originals |
| sound | the sound banks with our music and instruments (`content/sound`) |
| story | DG.SCN, MAPHEAD.SCN and their copies: per language, per font, and the original story beside the extended one |
| screens | SCRN.DAT: the screens 255 and up |
| maps, retouch | the story mod's new screens and the retouched originals (`story/mods/*/maps`) |
| balance | the maps' wild Digimon from `content/maps` |
| storycopies | the copies of the map files the extended story changes (the original story keeps its own) |
| signs, localize, title | the translated map signs, the translated textures, the title screen's HORIZON |
| plan | which files the disc replaces or adds, their names and the executable's file tables |

A step is a module of `tools/derive/steps/` with its outputs, its build and its checks. Steps made of units (the
model scripts, the overlays, the story passes, the map recipes, the sign passes) run them side by side (`--jobs`);
one process is the reference and gives the same bytes.

Its outputs go to `build/NAME/` at the paths the disc build reads, and `build/NAME/derived/manifest.json` lists every
derived file by disc path with its SHA-1: `tools/build-disc.py --derived` refuses any file that is neither in it nor
authored, and the patcher turns each into a hole.

## Rules that keep it reproducible

- **Strict mode** (`--strict`): no subprocesses or threads, as in the browser.
- **Recorder** (`--record`): every file a step opens is recorded; a read of a file only the USA disc has (the
  executable, the overlays, the scripts) stops the build, so every supported base disc builds the same files.
- Math: `tools/derive/crmath.py` gives correctly rounded sin, cos, atan2 and friends, so native Python and Pyodide
  (different libm) give the same doubles.
- Player builds use our committed artwork products: sign cutouts, banner deltas
  and map art at the required sizes. `tools/mediancut.py` provides deterministic
  quantization. Full localized authoring images are not build prerequisites.
- The player's build only reads `save.lock` files; a developer build (`--write-locks`) may append a story's new
  saved names.

Units sharing mutable map files use the same `order_group`. They run in recorded
pass order under fork and spawn; independent groups can run beside them.
`derive units --json` reports these groups. `DERIVE_UNIT_ORDER=reverse` tests
scheduling priority without changing writer order.
