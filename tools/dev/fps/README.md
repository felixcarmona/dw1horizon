# Frame-rate measurement tools

Scripts to build and verify the 60 fps renderer
(`docs/reference/frame-rate.md`, `docs/reference/frame-rate.md`). They drive the emulator
through `tools/dev/emulator.py` and read RAM by symbol; all locate their own worktree. Generated Lua goes under `build/dev/fps/`, separated by emulator port.

Since series patch `0080` the frame rate is a build parameter (`FPS=20|30|60`,
`docs/reference/frame-rate.md` "Choosing the frame rate"), no longer `MOD_FPS_MODE` in
RAM: a mode argument means "the disc was built with that rate" (`frame_cost.py` and
`tools/dev/duckstation.py perf` check `MOD_FPS_BUILD`), and comparing rates needs one disc
per rate. Compare separate discs and save states for each frame rate. `MOD_FPS_INTERP` and `MOD_FPS_TEST_TICK` are still RAM switches.

| Script | What it measures |
|---|---|
| `clockrate.py` | game minutes per real minute |
| `random_call_rate.py` | `rand()` calls per tick |
| `frame_cost.py`, `interpolation_cost.py` | tick / render / extra-pass cost per scene (MOD_PERF counters) on a build of a given frame rate |
| `statecheck.py` | hash of every entity and the RNG at each tick, to prove that extra passes do not change game state |
| `battlecheck.py` | the same for any loop going through `modPresent` (battles included): loads a save state (of a disc built with the mode's frame rate) and replays pad input per tick in one Lua call, hashes the battle state (fighters, `COMBAT_DATA`, objects, HUD, rewards, EFE engine) every tick; `OVL=STD` adds the overlay's data, `POKE=` writes a value on a given tick; `diff` compares two runs and says which columns differ |
| `cupenter.sh` | from in-game control: Arena Lobby, Grade D registration, into the cup (for a save state at the bracket) |
| `cupcheck.sh` | the cup, a File City walk and a Native Forest battle hashed in every mode against 20 fps (`MOD_FPS_TEST_TICK=8`) |
| `perfbattle.sh` | battle cost per render pass (20 fps, 60 fps, 60 fps with every pass forced) from a save state next to a wild Digimon |
| `buildcheck.sh` | a disc built with `FPS=20/30/60`: boots it in DuckStation (300 % CPU), lab menu screenshot, presented fps and logic ticks/s in the house, a Native Forest walk and a battle |
| `ticks_input.py` | replays a fixed input per tick (same walk in every mode) |
| `framedump.py` | every presented frame (true 60 fps capture; needs the interpreter CPU mode); `FD_FROM=ADDR:VALUE` starts at a RAM condition, `mp4 RAW OUT K` holds each swap K refreshes (game time for forced passes) |
| `tracer.py` | per-stage timing traces |

`FPS_MAP` selects the executable linker map (default `build/full/exe/SLUS_010.32.elf.map`).
For overlay hashing, `FPS_DECOMP` selects its matching patched source worktree
(default `build/decomp-full`). Presented-frame capture uses `FD_MAP`.
