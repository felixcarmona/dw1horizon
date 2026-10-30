# mods/

One folder per mod or DLC: `python3 tools/dws.py new mod NAME`. Each has a `mod.toml` (name, version, requires, load_after,
conflicts, save namespace and flag range), a `README.md`, `src/` (its story in Python: `docs/mods/story-language.md`;
`examples/` has small ones) and `text/` (its own text, committed; `dws text sync`).
The build merges mods in dependency order and refuses two mods that replace the same hook or write the same flag.

`overrides/` (deprecated: a Python mod writes its own NPC or a guarded handler instead; still applied, with a warning): sections of the original story (`story/base`, made from your disc) this mod replaces,
`script_NNN/secN.dws` (its own DWS for that section) or `script_NNN/secN.patch` (a `diff -U1` of `dws story-section NNN N`),
`maphead/secN.dws` for MAPHEAD. `tools/dws.py story-build` (and so `tools/build-full.sh`) applies the overrides of every mod
unless `mod.toml` says `enabled = false`; `STORY_MODS=a,b` / `--mods` choose.
