# Source game readers

These are our Python readers from the sibling game research projects, copied as
source so the player needs none of those projects. `sources.json` records each
original file's project, commit and SHA-256. No disc data, decoded models, emulator
or executable is included.

The readers use standard-library numerical helpers under `tools/derive/`;
player replay needs no third-party Python packages. Image-export helpers are
separate from disc replay. `dcb/pose.py` uses derive's correctly
rounded functions and explicit products to preserve native/Wasm rounding;
its immutable rotation cache preserves signed zero.

`source_context` makes these readers available only while importing, with explicit
player data directories, then restores the environment, path and package modules.
