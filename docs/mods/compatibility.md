# What works with what

Horizon has three layers. Each is pinned to the one below it, so a checkout of this repository is always consistent:
take the tools, the patches and the story from the same commit. Mixing commits is not supported.

| Layer | Where | Pinned by |
|---|---|---|
| Decompilation | `decomp/` | the submodule's commit |
| Engine | `mods/patches/` | the order of the series: it is linear, and a change to an old patch is a new patch on top |
| Tools and content | `tools/`, `story/`, `content/` | the same commit as the engine |

## Releases

| Release | Decompilation | Patches | Save extension | Compiler target |
|---|---|---|---|---|
| v0.0.1 | `83f99c5` | 0001-0270 | version 4, tagged | `original` |
| v0.0.2 | `83f99c5` | 0001-0291 | version 4, tagged | `original` |
| v0.0.3 | `83f99c5` | 0001-0308 | version 4, tagged | `original` |
| v0.0.4 | `83f99c5` | 0001-0325 | version 4, tagged | `original` |
| v0.0.5 | `83f99c5` | 0001-0336 | version 4, tagged | `original` |

Add a row for each release. A save from an earlier release loads in a later one; the
release packaging checks this against a corpus of cards ([save-format.md](../reference/save-format.md)).

## Compiler targets

| Target | Allocation | Executable | State |
|---|---|---|---|
| `original` | the original engine's free flags and saved counters | the production series | what every release uses |
| `extended-save` | 16,384 flags, 1,024 saved and 256 scene variables | `story-state`, a separate C extension | compiles; **not** a runtime target |

The second row checks and generates code only. Its C extension is parked because its first patch does not apply to the
current series; rebase and measure it before running it ([story-state-engine.md](story-state-engine.md)).

`tools/dws/gen.py` refuses an operation that the selected executable does not implement, so a script written for the
wrong target fails at compile time, not in the game.

## What a mod can rely on

- Flag and counter numbers in a mod's `save.lock` are append-only: an existing save keeps its meaning.
- `mod.toml` names a mod's `requires`, `load_after`, `conflicts` and save ranges; `python3 tools/dws.py check` reports a
  clash between mods.
- Two mods can take the same patch or flag number on separate branches with no merge conflict. Run the whole build
  after combining them.
- Engine symbols, RAM addresses and overlay layouts are **not** a stable interface. They belong to one series.

## Reading the final engine

`tools/engine_tree.sh build` writes the decompilation with every patch applied, one commit each, to
`build/engine-tree`. Use `git log` and `git blame` there to see which patch made a line. That tree is generated: send
changes to `mods/patches/`. It holds no disc data. `tools/mods.sh prepare int` is the tree to build from, because it
also adds what is generated from your own disc.
