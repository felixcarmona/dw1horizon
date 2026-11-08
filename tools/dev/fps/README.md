# Frame-rate measurement tools

Scripts to build and verify the 60 fps renderer
(`docs/reference/frame-rate.md`, `docs/reference/frame-rate.md`). They drive the emulator
through `tools/dev/emulator.py` and read RAM by symbol; all locate their own worktree. Generated Lua goes under `build/dev/fps/`, separated by emulator port.

The standard `FPS=60` build chooses 20 or 60 from a two-second title workload
trial. `MOD_FPS_AUTO_MODE` stores its decision; `MOD_FPS_MODE_RUN` is the active
mode. Logic stays at 20 Hz. `FPS=20` compiles out the trial and extra passes;
`FPS=30|60` includes them. Restart to retest a changed CPU setting.

`FPS_DIAGNOSTICS=1` exports the raw title swap/vblank counts, rate ×100,
old hblank probe count, and packet byte count. On PCSX-Redux, run:

```sh
python3 tools/dev/fps/workloadcheck.py --exe build/full/exe/SLUS_010.32 \
  --port 38090 --out build/dev/fps/workload-city.json
```

The executable must match the running disc and include diagnostics. The tool
samples GPU vblanks without breakpoints, rejects missed counter increments,
and reports guest FPS, 20 Hz logic, host time and swap spacing. Optional
`--mode 0|2` changes RAM for comparison; restore a matching scene checkpoint
between comparisons. Six refreshes settle an in-progress tick before sampling.
Historical DuckStation tools below test the preceding CPU-based selector and
must be adapted before use with this policy.

| Script | What it measures |
|---|---|
| `workloadcheck.py` | PCSX-Redux title trial raw values and free-running field swaps, vblank spacing, logic and host throughput |
| `autocheck.py` | full-disc automatic/manual comparison: boot selection, original 2 MB and expanded 8 MB, light/heavy/battle fps, guest swap intervals and runtime overclock toggles |
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
| `curlingprofile.py` | inclusive CPU-cycle profile of curling and its render/collision callees in the interpreter |
| `curlingcheck.py` | tick-scripted curling inputs; records stone physics, scores, RNG and entity/bone/momentum hashes; runtime modes 0/1/2 on the same FPS=60 disc |
| `curlingdscheck.py` | fixed-seed complete DuckStation match, pad input after polling per tick, semantic state trace and optional per-state checkpoints (`DS_CHECKPOINTS=1`) |
| `duckframes.py` | every DuckStation refresh with FrameStep/F12, PNGs and RAM samples; verifies exactly one Vcount step per picture |
| `curlingmatch.py` | DuckStation pad driver and state/outcome trace for a complete curling match, including original-disc overclock smoke tests |

For curling comparisons, start from an aiming save state of the same disc and
set `FPS_MAP` to its linker map. `curlingcheck.py STATE MODE INTERP TICKS OUT`
uses twelve refreshes per tick by default so every requested pass fits in every
run. `KC_PERIOD=0` tests actual scheduling, and `KC_FIXTURE=FILE.json` applies a
recorded semantic starting fixture across builds. Mode arguments in this tool
set the runtime option. `curlingmatch.py` uses wall-timed pad input and records
actual powers and outcomes; differing scores alone do not prove a physics
difference between overclock settings.

`FPS_MAP` selects the executable linker map (default `build/full/exe/SLUS_010.32.elf.map`).
For overlay hashing, `FPS_DECOMP` selects its matching patched source worktree
(default `build/decomp-full`). Presented-frame capture uses `FD_MAP`.

Use `DS_DISPLAY` and `DS_GDB_PORT` for a private DuckStation instance. The
complete replay starts from free control in File City. Debugger pauses are
excluded from wall-time performance claims; measure each saved state separately.

`curlingdscheck.py` lets the intro's cadence calibration run without debugger
stops, then records from its one-time assignment onward. `recording_first_tick`
and `recorded_ticks` identify the captured range; pad timing keeps the original
absolute tick phase. `DS_FREE_WARMUP=0` records the intro too, but those debugger
stops can bias the cadence selector and must not be used for cadence acceptance.
Use free-running perf and `duckframes.py` for presentation checks. Optional
`DS_CURLING_GEOMETRY=1` records stone history, matrices and the player's hand.

For clean DuckStation captures, shorten `Display/OSDErrorDuration`,
`OSDWarningDuration`, `OSDInfoDuration` and `OSDQuickDuration` to `0.1`, and turn
`AnimateOSDMessages` off. `ShowOSDMessages=false` alone leaves overclock/RAM
warnings over the HUD; their fading pixels are not PSX frame changes.
`python3 -m unittest tools.test_curling_collision tools.test_duckstation_protocol`
checks the scanner/SDK cutoff and RSP acknowledgement/stop handling.
