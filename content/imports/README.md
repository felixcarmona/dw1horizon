# Imported species

The imports step rebuilds 175 species from the player's Digital Card Battle,
Digimon World 2 and Digimon World 2003 discs. It uses the bundled Python readers,
then applies our model edits from [../modeldelta](../modeldelta/README.md).
No converted models or textures are stored here.

| Path | Purpose |
|---|---|
| `lists/` | Source models, donors, levels and conversion settings for each batch |
| `specs/` | Frozen bone maps, animation clips and geometry budgets, pinned by SHA-256 |
| `releases/` | Source file checksums and mappings for supported disc releases |
| `retired.json` | Species IDs superseded by another record |

`tools/import_batch.py` authors the import specs. The player build replays the
frozen specs through `tools/derive/importers`; it checks every source and output
before applying the model delta. See [building](../../docs/building.md) for discs
and commands, and [model deltas](../modeldelta/README.md) for animation editing.
