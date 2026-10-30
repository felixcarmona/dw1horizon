# DWS: story compiler and checks

Run the author-facing commands through `python3 tools/dws.py`; see
[the language guide](../../docs/mods/dws.md) and
[Python story authoring](../../docs/mods/story-language.md).

| Area | Responsibility |
|---|---|
| `bytecode/` | One opcode table, assembler/disassembler and binary text codec |
| `text/` | Shared box profiles, explicit-font metrics/paging, dialogue extraction and review |
| `pickups.py` | Stable daily pickup identities and reachable-script rewriting |
| `variants.py` | Original/extended story map-copy policy and name collision checks |
| `audio.py` | Story music bindings and bank/program commands from `story/core/audio.json` |
| `checks/` | Arrival safety from lowered placements; actual-target heap checks |
| `testing/` | Story graph/trace/route semantics, behavioral corpus and independent C city oracle |
| `py/` | Python story frontend, lowering, text synchronization and editor stubs |

Executable string extraction, relocation and multilingual padding live in
`tools/localize/executable/`. They use the shared text codec while retaining their
own native-string schema. Compiler and binary row capacities remain distinct:
authored unpacked rows reserve one unit of the 32-unit engine buffer; packed
dialogue reserves its terminator bytes. Special native windows retain their
unpacked profile with either font.

```sh
python3 -m tools.dws.bytecode check extracted/SCN/DG.SCN extracted/SCN/MAPHEAD.SCN
python3 tools/dws.py check-spawns story/mods/what-the-island-forgot/early-game.py \
  --screen-content build/game-maps/screens --maps build/game-maps/retouch
python3 tools/dws.py check-heap build/game/with-new-screens/MAPHEAD.SCN \
  --map build/decomp-game/build/us/psx/gcc/SLUS_010.32.elf.map \
  --archive build/game/DIGI.DAT --facts build/game/derived/exe-facts.json
```

Spawn checks report unknown/skipped coverage. `--enforce-source` selects which
sources fail the check; extra sources remain advisory during migration. `--suggest`
prints AST-positioned diffs for review and never writes a story source. The derive
recipe runs the compiler check after map and retouch outputs exist.

The allocation profiles are `original` and `extended-save`; the latter needs the
`story-state` executable to compile its wider persistent/scene variables. Saved
lock profile IDs remain compatible through the allocator's persisted-format
boundary. Ordinary everything builds continue to use the existing mod executable
and original allocation pools. Allocation identities and game/disc formats are
not renumbered by these source moves.
