# Tools

Run commands from the repository root. Generated files stay under `build/`.
Player replay requires Python 3.10+ and its standard library, with no NumPy or
Pillow. Optional image review and emulator tools have separate dependencies;
see [THIRD-PARTY.md](../THIRD-PARTY.md).

| Area | Entry points |
|---|---|
| Source builds | `extract.sh`, `decomp-build.sh`, `mods.sh`, `build-full.sh`, `discs.py`; [building](../docs/building.md) |
| Recorded replay | `python3 -m tools.derive`, with steps, import readers and recipes under `derive/`; [derive](../docs/derive.md) |
| Player packages | `patcher/dwpatch.py`, `release.py`, `release_pages.py`; [patcher](../docs/patcher.md), [Pages releases](../docs/release/releasing.md) |
| Story language | `dws.py`, `dws/py/`, `dws/bytecode/`, `dws/text/`, `dws/checks/`, `dws/testing/`, `dws/variants.py`; [DWS](../docs/mods/dws.md) |
| Content and maps | `species.py`, `balance.py`, `dwmap.py`, `screens.py`, `sound.py`, `maps/`; [map tools](maps/README.md) |
| Models and animation | `models/` ([supported commands](models/README.md)), `mmd.py`, `import_batch.py`, `dcb2mmd.py`, `dw2mmd.py`, `dw3mmd.py`, `models/edit.py`, `recordoriginals.py` (disc replay), `recordimports.py`, `recordedit.py` |
| Fonts and localization | `fontgen.py`, `font/compact.py`, `localize/`, `localize/executable/`, `image.py`, `mediancut.py` |
| Developer tools | `dev/` contains emulator transport, symbols, game state, captures, playtests, saves, frame-rate and memory checks; [developer tools](dev/README.md) |
| Offline checks | `selftest.sh`, `test_*.py`, `checkrefs.py`; [developing](../docs/developing.md) |
| World gates | `world_audit.py`, `data/world-*.json`, `test_world_audit.py`; [conditional reachability](../docs/mods/world-audit.md) |

Imported species are rebuilt from the player's source discs by `derive/importers/`,
using frozen recipes under `content/imports/` and authored model deltas under
`content/modeldelta/`. Record originals use the same four source discs.

Original font bitmaps and unchanged localized-image pixels are read from the
player's disc. The committed sign and banner deltas contain changed pixels.
Map foregrounds come from the project's authored map art.
