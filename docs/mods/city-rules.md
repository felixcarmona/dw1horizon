# City rules and NPC presence

Use [Python story handlers](story-language.md) for new quests, NPCs and presence
conditions. This page describes the declarative city data read by the tier-2
engine and the tools that explain the base game's city rules.

## City data

`story/base/city/city.dws` expresses the original C rules for prosperity,
File City layout, revival screens, new-game state, and shop/arena overlay lists.
`tools/dws/city.py` extracts and compiles these declarations. A `city { }` block
is a DWS escape hatch for changing those rules; it requires a compatible tier-2
target. The original executable and `ENGINE_TIER=0` retain their C rules.

The compiled table uses little-endian u16 words, a `CY` header, a version and
six block offsets. Conditions are clauses of four-byte atoms. MAPHEAD section
1260 holds a mod's table; the engine uses its built-in default when no replacement
is present. The default header is generated from the base declaration.

This data shares the target's resident MAPHEAD buffer. Current mod targets allow
0x8000 bytes; the original executable allows 25,000. The compiler checks capacity.
Historical heap measurements from a different patch series do not establish that
a changed city fits; validate the actual final build at the original 2 MB.

## Presence

NPC presence comes from MAPHEAD setup, rather than the city C table.
`tools/dws/presence.py` follows setup branches and derives conditions for each
screen, slot, species and autotalk value. The key-only declarations live under
`story/base/city/presence/`.

For new NPCs, the Python compiler combines presence conditions with the slots it
places. Use `screen(...).npc(..., when=...)` and guarded handlers. A change to an
existing NPC should use the supported base imports and ownership operations;
do not copy and hand-edit MAPHEAD assembly.

## Inspect and verify

Run from the repository root with the decompilation and player's USA extraction
available:

```sh
python3 tools/dws.py city-verify
python3 tools/dws.py why Angemon --screen 205 --recruit Angemon
python3 tools/dws.py why top_map --recruit Angemon --recruit Monzaemon
```

`city-verify` compares declarations with the original rules and checks presence
conditions over its state grid. `city-extract` regenerates base declarations from
the unmodified C and scripts; review the diff before committing regenerated source.
`city-compile --help` describes standalone table/header outputs for compiler work.
The integrated builder generates the required executable inputs automatically.

After changing a city rule or NPC, run the compiler checks and the affected
runtime scenarios. Check map selection, prosperity, NPC slots, transitions,
new-game state and save/continue where applicable. See
[development checks](../developing.md) and [memory budgets](../reference/memory.md).
