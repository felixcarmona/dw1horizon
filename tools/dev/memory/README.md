# Memory and streaming checks

Checks for reclaimed memory and map streaming (`docs/reference/memory.md` "Reclaimed memory").
They drive `tools/dev/emulator.py` on `EMU_PORT` (default 38096) and read symbols of the running
build; run them from the repository root. Outputs go to `build/dev/memory/`.

| Script | What |
|---|---|
| `transit.py SCREEN[:EXIT] ...` | warp chain; vsyncs from the warp to control, `MOD_TFS_STATS` |
| `walk.py BUTTON:FRAMES ...` | presses (`A+B` together), camera/window and streaming stats after each |
| `palette_check.py` | which TFS palette is active and whether every VRAM window tile equals the `.TFS` |
| `streaming_ring.py` | every ready ring slot compared with the `.TFS` |
| `npc_models.py` | NPC models in RAM: kept slots identical to the file, dropped ones on the stub |
| `background_check.py RAW TFS W H` | per captured frame (`tools/dev/presented_frames.py`), background match per 64×64 cell (`BG_REF=frame` for the offset) |
| `city_walk.sh` | card start + File City walk with reversals, `streaming_ring.py`/`palette_check.py` after every step |
| `regress.sh [DISC]` | warp chain incl. fishing/curling screens, day/night, a wild battle |
| `battle.sh TAG [SLOT]` | fight the wild Digimon in NPC slot SLOT with X presses |
| `stack_usage.sh [DISC]` | stack high-water after menus, battles and the cup (`tools/dev/fps/cupenter.sh`) |
| `walk_cost.sh DISC` | warp timings and `MOD_PERF` during a walk (`tools/dev/fps/frame_cost.py`) |
| `tools/dev/presented_frames.py` | presented-frame capture with `FD_MAP` (default: `build/full/exe/SLUS_010.32.elf.map`) |
