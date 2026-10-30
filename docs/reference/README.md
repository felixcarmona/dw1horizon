# Reference: how the game works inside

What is known about Digimon World (PS1, USA release `SLUS-01032`) from its decompilation
([jype0/dw_decomp](https://github.com/jype0/dw_decomp), the `decomp/` submodule) and from tests in the emulator, and
how this project's patches hook into it. Addresses are RAM addresses of the original USA executable unless a page
says otherwise; `decomp/src/...` paths and function names point into the decompilation at the pinned commit. Nothing
here replaces your own disc: the pages describe formats and behaviour, they do not contain game data.

The authoring guides (the story language, maps, models, sound, fonts, translating) are in [../mods/](../mods/);
[new screen authoring](../mods/new-maps.md) covers the complete map workflow; how to
build is in [../building.md](../building.md); how to test is in [../developing.md](../developing.md).

## The disc and the executable

| Page | What it covers |
|---|---|
| [disc.md](disc.md) | the disc's layout, every file and what it is for, the physical order and the executable's own file table ([data/disc-files.csv](data/disc-files.csv): every file's sector and size) |
| [executable.md](executable.md) | the main executable and its 16 overlays, the memory map they share, the data tables inside the executable, the decompilation and our GCC build, related public projects |
| [file-formats.md](file-formats.md) | every data format on the disc at field level: images, models, maps, scripts, sound, movies, effects |
| [compiler.md](compiler.md) | where the GCC build behaves differently from the original compiler's, and the original game's own bugs found the same way |

## The game, subsystem by subsystem

| Page | What it covers |
|---|---|
| [core.md](core.md) | boot, the main loop at 20 Hz, the main and game states, the clock, a new game, the title menu |
| [ram-map.md](ram-map.md) | the key addresses at a glance and the global state by subsystem; how to list every global |
| [partner.md](partner.md) | the partner's care values (hunger, sleep, poop, weight, happiness, discipline, sickness, lifetime), training, evolution and its scoring, death and rebirth, technique learning |
| [world.md](world.md) | the 239 screens with exits and placed Digimon, entering a screen, movement and collision, the camera, NPCs, File City, prosperity, recruitment, transport, chests |
| [scripts.md](scripts.md) | the script interpreter: triggers and pstats and their meanings, the opcodes, routines, the text box engine |
| [story-engine.md](story-engine.md) | how the story is put together: entry points, the scripts-to-C conventions, the original quest chain and zone gates, how `story/` becomes the disc's script files, EXTENDED STORY |
| [combat.md](combat.md) | wild and arena battles, the fighter state, techniques, AI choice, hit and damage formulas, statuses, finishers, rewards, tournaments |
| [items-and-menus.md](items-and-menus.md) | the inventory, the effect of every item, shops, cards, the merit shop, the item keeper, the menus |
| [minigames.md](minigames.md) | fishing, curling, training and its slot machine, the VS mode, the ending |
| [engine.md](engine.md) | file loading, framebuffers and VRAM, models and animation playback, battle effects, sound and music, movies, random numbers |

## The mod's engine work

| Page | What it covers |
|---|---|
| [engine-patches.md](engine-patches.md) | how the C patch series hooks into the engine, feature by feature: limits, waiting, status display, portraits, partners as NPCs, quick battles |
| [memory.md](memory.md) | main RAM, VRAM and SPU RAM: the layout, the fixed buffers, the heap and its budget, what each patch reclaims |
| [ids.md](ids.md) | the id spaces (species, screens, items, techniques, cards, files) and how the mod widens them |
| [save-format.md](save-format.md) | the memory card save: the original file and checksum, the tagged extension the patches add |
| [frame-rate.md](frame-rate.md) | the engine's timing and how drawing at 30 or 60 fps is separated from the 20 Hz game logic |
| [text-sources.md](text-sources.md) | how text is keyed, sourced by checksum from a disc, picked and fitted |
| [imported-species.md](imported-species.md) | Digimon converted from three other PS1 games: their formats, matching, identity rules, extra species |
| [motion.md](motion.md) | how the partner's animation slots are used and how imported species are animated and checked |
