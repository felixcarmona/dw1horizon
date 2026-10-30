# Derived game files

Derive regenerates game-derived files from the player's four discs, committed
source and reviewed deltas. Native builds, standalone packages and browser
workers run the same step implementations. Use the normal everything build
from [the patcher guide](../../docs/patcher.md) to prepare the executable
facts and complete output tree.

```sh
python3 -m tools.derive steps
python3 -m tools.derive units --recipe everything --out build/everything \
    --facts build/everything/derived/exe-facts.json --json
python3 -m tools.derive verify --out build/everything
```

## Steps and units

Each module in `steps/` declares its name, description and dependencies. Its
build function or prepare/unit/finish API writes the declared outputs. Independent
units can run concurrently. Shared writes require explicit ordering; a finish
runs after its units and records the step result. The story passes preserve
their recorded order wherever they overwrite the same files.

`runner.py` runs tool code in the caller's process, restores its settings and
unloads repository modules before another step can inherit their state. A failed
worker stops the step and its remaining workers. Strict and recording modes run
serially; browser workers execute the same individual units.

## Facts, recipes and manifests

`facts.py` reads the private pinned decomp tree's actual buffer sizes, symbols
and file-table locations. Semantic defaults such as original-game allocation
pools remain separate from these measured target facts.

`recipe.py` supplies the everything settings, ordered story sources and map
writes. Player builds clear unrelated developer overrides before applying that
recipe. Imported models use the `imports` provider and committed species pins;
field overlays run after imports and before species/archive generation.

`manifest.py` replaces each completed step entry with its description, outputs,
sizes, hashes and recorded inputs. The final plan maps generated and authored
files onto disc paths. Source paths and job identifiers may change during a
layout cleanup; the resulting game files and raw disc bytes must remain equal.

## Recording and verification

The patcher starts from tracked source in a clean tree, records the files each
step reads, then rebuilds using only the bundle and declared disc inputs. The
browser recorder additionally captures each unit's reads, directory listings,
writes and removals to build the worker dependency plan. Test regional inputs
against their own reference outputs, including the Japanese localized assets.

The player path uses the Python standard library. The scalar numeric helpers
preserve the established import arithmetic across supported Python versions.
Importer source, delta and target checks remain mandatory. A cleanup must never
rebase a delta or change a pin to hide a differing output. Compare independently
extracted disc-file sums, the raw image and cue layout after each producer move.
