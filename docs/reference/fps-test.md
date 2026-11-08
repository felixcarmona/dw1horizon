# Private v0.0.7 frame-rate diagnostic build

This branch starts at v0.0.7 and backports FRAME RATE plus diagnostics only.
It is not a release. MOD_FPS_DIAG in dw/mod_fps.h compiles the overlay in;
its version is fixed to v0.0.7-fpstest1 whenever diagnostics are enabled.
Normal main builds contain none of this instrumentation.

The field, battle and title show a small plate: `P02180 R>60 F41 D21`.
P is the raw 16-scanline CPU polling-loop count used by AUTO. A means AUTO;
R means an explicit request. The number after > is the effective 20/60 mode.
F counts actual buffer swaps per 60 guest refreshes over the previous window,
including variable-length windows after loads. D counts skipped extra passes
and extra passes that finished late in that window. These are guest-clock
numbers; a game cannot measure iOS wall time if its emulator slows down.
Logic remains 20 Hz. The plate draws on every render pass without changing
logic, rollback state or random numbers.

Save byte 2 uses 0xA0/0xA1/0xA2. Every older value defaults to AUTO because
v0.0.7 wrote 20 unconditionally. Both record and title-header copies persist
new explicit choices. All other byte positions remain unchanged.

The code build retains 186816 B of heap (main_BSS_END 0x801ce538).
MENU is 54000 B, 27 sectors; all 320 archive-based screen setups fit.
The diagnostic image builder retains the published disc allocations, updates
language-patch lengths within their existing sectors, preserves regional
program data by ELF symbol, and preserves Chinese fonts/name/resource data.
Only program bytes and necessary ISO directory length/EDC/ECC bytes change.
The BPS encoder copies inherited glyph objects from the player's source;
the independent audit rejects glyph literals or changed asset sectors.

Developer checks:

```
python3 tools/test_fps_auto.py build/decomp-int
python3 tools/test_fps_diag.py build/decomp-int
python3 tools/test_cheats.py build/decomp-int
python3 tools/test_savecompat.py
python3 tools/dev/fps/optioncheck.py build/test.cue --exe build/code/exe-en/SLUS_010.32 --out build/fps-proof
```

Delivery consists of per-pin BPS patches to the published v0.0.7 outputs,
a checksum manifest, and a player README. No images or extracted assets belong
in that delivery. Rom Patcher JS has applied the full 910400400-byte USA image
in both Node and its official browser interface under WebKit, producing the
same test SHA-1. A physical iPhone was unavailable for testing.
