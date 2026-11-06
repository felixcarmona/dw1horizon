# starter

The smallest whole mod, to read in ten minutes and copy: one retouched map, one recruit, one quest in stages. It stands
alone: nothing here imports from `what-the-island-forgot`, and it builds on the original executable.

In the game: IceLeomon stands in Kunemon's Bed (screen 1) and has lost its medal. Say yes, step on the round stone at the
west of the clearing, go back to it: it pays 500 bits and leaves for File City.

| file | shows |
|---|---|
| `mod.toml` | the mod's name and its reserved save numbers |
| `save.lock` | which number each flag got; append-only, committed, written by the compiler |
| `maps/mayo02-stone.py` | a map recipe: reads the player's own map at build time, turns six tiles into step trigger 1, checks the arrivals and that the tiles can be reached |
| `src/kunemons_bed.py` | one screen's story: the quest (`class LostMedal(Quest)`), the new NPC with its presence rule (`when=`), `on_talk` per stage, `on_step(1)` on the recipe's trigger, the recruit (`send_to_city`) |
| `text/en.json` | the mod's lines, keyed by the hash of the words; written by `text sync` |

## Check and build

From the repository root, with `extracted/` and `text/us` in place (`docs/building.md`). The trigger exists only in the
recipe's map, so the recipe runs first and `DWS_MAPS` points the compiler at its output:

```sh
python3 story/mods/starter/maps/mayo02-stone.py build/starter-maps          # the map
mkdir -p build/dws                                                          # the compiler's scratch folder
export DWS_MAPS=build/starter-maps
python3 tools/dws.py check story/mods/starter                               # errors at the .py lines, the screen's heap
python3 tools/dws.py check story/mods/starter/src/kunemons_bed.py --build   # also assembles
python3 tools/dws.py text sync starter                                      # after changing a line
python3 tools/dws.py disc story/mods/starter -o build/starter.SCN --name starter    # build/starter.cue, in seconds
```

The disc is the original game plus this mod. It carries the recipe's map because the mod places an NPC on that screen;
a recipe for a screen with no NPC of the mod needs its file passed to `tools/build-disc.py`. `tools/test_dws.py` runs the
recipe and compiles the mod, so it cannot rot.

## To copy it

1. `python3 tools/dws.py slots SCREEN` shows the free NPC slot, the heap left, the arrivals and the triggers.
   `python3 tools/dwmap.py overlay extracted/MAP/MAPn/NAME.MAP x.png` draws the walkable tiles with their coordinates.
2. Pick a screen no other mod retouches: a map file has one recipe. `everything.json` lists those of the shipped story.
3. Change `name`, `namespace` and the range in `mod.toml`, and delete `save.lock` while nothing has been released.
4. Run the commands above. `check` refuses a wall tile, a missing trigger, or a species the heap of the screen cannot hold.

## Things that cost a day

- Only plain floor becomes a trigger, with a number the map does not use yet. Trigger tiles stay walkable.
- An NPC with no run clip hangs a scene on `run()` or `walk_away()`: `walk()` is always safe. `send_to_city` walks nowhere.
- A wild Digimon stands further than its range + 300 from every arrival. This one has `range=0` and stands over 1100 away.
- The game must fit an original 2 MB PlayStation. `check` prints the heap; do not ship a screen it refuses.
- A new screen (not this edit) needs more: `docs/mods/new-maps.md` on `"like": 240`, warps at y 0, and TIM counts.

## Save numbers

`mod.toml` reserves flags 787-788 for the example quest. The original-engine profile offers flags 717-788;
789-797 are engine-owned daily Mojyamon state and 798-799 are daily vending state. The shipped story reserves
717-786 and the other examples reserve 780-786, so the starter's two flags fit beside both. Older starter-only
test saves using 790-791 must be recreated; shipped story save identities are unchanged.

## On the Horizon disc

This mod is not in `tools/derive/recipes/everything.json`, so it changes no shipped disc. Adding it means listing the
recipe and the source there, and giving IceLeomon a row in `content/tables/city-residents.json` and a home
(`docs/mods/city-rules.md`): on that disc only roster species count as residents.
