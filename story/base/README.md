# Base story sources

`story/base` is committed, key-only source derived from the USA story: Python
views beside their DWS form, MAPHEAD hooks and shared blocks, and names. It
contains no original dialogue; text keys are resolved from the player's disc
or the selected translation. `city/` contains our declarative city rules.

`tools/dws.py story-build` compiles these sources with the selected mods, using
Python by default (`--from-dws` selects DWS). Existing source is preserved.

```sh
python3 tools/dws.py story-base --reproduce
```

This generates a comparison in scratch storage and checks the committed sources.
Reviewed Horizon changes are pinned by original and authored SHA-256 and a reason
in `authored.json`; all other files must reproduce exactly. An explicit
`story-base --refresh` replaces generated sources, so review the resulting diff
and preserve reviewed edits before committing. The local `.stamp.json` is ignored.

For new quests and NPC changes, write a Python mod; see
[the story language](../../docs/mods/story-language.md). Never copy the game's
dialogue into sources or commit generated SCN containers.
