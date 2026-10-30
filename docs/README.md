# Documentation

## Players

- [release/README-players.md](release/README-players.md): how to patch your disc with the command-line patcher.
- The web page, [dw1horizon.com](https://dw1horizon.com), does the same in the browser.

## Developers

- [building.md](building.md): building the whole disc from source and the four player discs.
- [derive.md](derive.md): `tools/derive`, the builder of every file made from the game's data.
- [patcher.md](patcher.md): the release package, the patch format, base discs, what a patch may carry.
- [developing.md](developing.md): testing a build: the self-test and unit tests, the emulators and the scripts that
  drive them, story tests, play tests of the patches, trying it on a handheld.
- [reference/](reference/README.md): how the game works inside (formats, RAM, engine, scripts, combat, the world) and
  how the patches hook into it.
- [C patch series](../mods/patches/README.md): the patches on the decompilation.
- [Tools](../tools/README.md): the tools, by purpose.

## Making content

| | |
|---|---|
| [mods/story-language.md](mods/story-language.md) | the story language (Python): screens, characters, dialogue, battles, choices |
| [mods/dws.md](mods/dws.md) | DWS intermediate syntax, text keys and compiler integration |
| [mods/city-rules.md](mods/city-rules.md) | File City's rules: residents, prosperity, what recruits do |
| [mods/species.md](mods/species.md) | species as data (`content/species`, DIGI.DAT) |
| [mods/data-sources.md](mods/data-sources.md) | which JSON in `content/` is the source of which game table |
| [mods/balance.md](mods/balance.md) | the balance tables |
| [mods/options.md](mods/options.md) | the OPTIONS menu and how to add a setting |
| [mods/new-maps.md](mods/new-maps.md) | new screen authoring, foreground cut-outs, collision and 2 MB acceptance |
| [mods/maps.md](mods/maps.md) | low-level map formats and inspection (`tools/dwmap.py`) |
| [mods/models.md](mods/models.md) | Digimon models and textures (`tools/mmd.py`) |
| [mods/scripts.md](mods/scripts.md) | low-level compiler output, containers and `scnasm` checks |
| [mods/sound.md](mods/sound.md) | music, effects and voices (`tools/sound.py`) |
| [mods/font.md](mods/font.md) | the fonts and the extra glyphs |
| [mods/translating.md](mods/translating.md), [mods/language.md](mods/language.md) | translating the game; the eight-language disc |

`data/*.csv` are name tables the build reads (items, techniques, species, map files, memory budget per screen).
