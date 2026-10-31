# Developing and testing

How to check a change: the offline test suites first, then the game itself in an emulator driven by scripts, then original-2-MB runtime checks. Building the disc is in [building.md](building.md); what the game does inside, with RAM addresses, is in
[reference/](reference/README.md).

| Layer | What it proves | Needs | Where |
|---|---|---|---|
| Self-test | every tool reproduces the original files byte for byte; the compiler and the data checks pass | `extracted/` for most checks | `tools/selftest.sh` |
| Unit tests | the compiler, the species lint, the motion maths, the save-state reader | Python; some need `extracted/` | `tools/test_*.py` |
| Emulator tests | the game behaves as intended: a patch's rule, a story section, a save, a frame rate | an emulator, a built disc | `tools/dev/emulator.py` and the scripts below |
| Optional handheld | device controls and performance | an Android handheld with DuckStation | `tools/dev/device.sh` |

Everything here runs from the repository root. Outputs go to `build/` (ignored by git).
Checks read your own disc's files from `extracted/` (`tools/extract.sh`) and the
builds made from them. See the [content policy](../content/README.md) for what is
committed.

## 1. Offline tests

```bash
tools/selftest.sh                         # about a minute; prints ok / FAIL / skip per check
python3 tools/test_dws.py                 # the story compiler (needs extracted/)
python3 tools/test_species.py             # species files that the game cannot handle are refused
python3 tools/test_motionlab.py           # one of the asset-free motion tests (test_motion*.py)
```

`selftest.sh` runs, in order: the round trips of the format tools (`scnasm`, `dwmap`, `mmd`, `sound`: decode and encode
every original file and compare bytes), the species archive and its lint, the balance tables against the executable's
own, the economy audit, every DWS example compiled, the formatter and `dws.py doctor`, the story language's type stubs,
`py_compile` of every tool, the committed `story/base` against what your disc decompiles to, the offline checks of the
story tests (`tools/dev/story_test_offline.py`) and `tools/checkrefs.py` (every file a doc or script names must exist). A check
that reads your disc's files is reported as `skip (needs extracted/)` when `extracted/` is absent; likewise the checks
that also need the decompilation's symbols (`git submodule update --init decomp`). Species archive/lint checks use
the generated everything build (`DW_SELFTEST_DERIVE`, default `build/wtif`); see [building.md](building.md). The drift check against a prepared decompilation (`build/decomp-int`)
runs only when that build exists.

The unit tests (`tools/test_*.py`) are plain `unittest` files; each runs alone (`python3 tools/test_species.py`) and
needs no emulator. The `test_motion*.py` files use synthetic skeletons and animations (no game assets).

The world-gate audit and its unsafe-edge regression tests also run without an
extraction. Run `python3 tools/world_audit.py --built-maps build/NAME-maps` after
changing connections to check the model against actual map outputs as well.
See [the world audit](mods/world-audit.md) for story frontiers, original baselines,
deliberate exceptions and old-save escape checks.

`npc-originals` reads the built image selected by `DW_SELFTEST_DERIVE`. For
all native species used by NPC maps/scripts it compares the effective NPC's
posed idle dimensions (within 1%), original animation slots, radius and height
against the unmodified extraction. Twin records are checked through DIGI.DAT;
other native rows use the built executable and its linker map. Reviewed
exceptions belong in the small, reasoned list in `tools/npc_originals.py` (currently
empty). Run it directly with `python3 tools/npc_originals.py build/NAME`.

Other checks worth running after a specific change:

| After changing | Run |
|---|---|
| species JSON | `tools/species.py lint`, `tools/dev/playtest/species_proof.py` (emulator), `tools/species_bytes.py` (only names changed?) |
| balance tables, items, shops | `tools/balance.py check`, `tools/economy_audit.py` (no repeatable conversion turns bits into more bits), `tools/balance-proof.sh` |
| evolution data | `tools/evo_check.py` (every target reachable), `tools/evo_graph.py` |
| story scripts | `tools/dws.py check FILE --build`, then the story tests of section 5 |
| a C patch's tables | the matching script in `tools/dev/playtest/` (section 6) |

## 2. Emulators

Two emulators run headless on Linux, both from portable folders under `.tools/` (ignored by git), both with OpenBIOS
(the free BIOS that ships with PCSX-Redux; a console BIOS is not needed). Install
`Xvfb`, `xdotool` and `ffmpeg` for headless displays, scripted input and video capture.

- **PCSX-Redux** is the test harness: it has a web server to read and write RAM, take screenshots and run Lua inside
  the emulator, and Lua breakpoints. Install a Linux x64 build (an AppImage, from the project's release channel) and
  extract it without FUSE into `.tools/emu/pcsx-redux-zip/` so that `.tools/emu/pcsx-redux-zip/squashfs-root/AppRun`
  exists (`appimage --appimage-extract`). `tools/dev/emulator.py` starts it in portable mode (`-no-ui`, settings and memory
  cards in `.tools/emu/home*/`) with `SDL_AUDIODRIVER=dummy`. About half a core; the game runs at real speed.
- **DuckStation** is the second opinion: it emulates GPU drawing time, CD seek and read timing and optionally the
  instruction cache, so it is closer to a console for frame-rate and loading measurements. Extract its AppImage into
  `.tools/duckstation/squashfs-root/`, put an empty `portable.txt` next to its binary and OpenBIOS in its `bios/`.
  `tools/dev/duckstation.py start` writes the settings it needs (no setup wizard, OpenBIOS, null audio, the GDB stub, a shared
  memory card) and runs it on a private Xvfb display.

### The harness: `tools/dev/emulator.py`

```bash
tools/dev/emulator.py start build/wtif.cue --card build/states/file-city.mcd   # boot a disc with a memory card
tools/dev/emulator.py seq tools/dev/sequences/continue.seq    # ~90 s: CONTINUE the card's save, control in Jijimon's house
tools/dev/emulator.py press CROSS 8                 # hold a button for 8 frames
tools/dev/emulator.py shot build/x.png              # what the GPU shows
tools/dev/emulator.py peek MONEY 4                  # read RAM: an address or a symbol of the running executable
tools/dev/emulator.py poke MONEY e8030000           # write RAM (1000 bits)
tools/dev/emulator.py seq "until IS_SCRIPT_PAUSED 4 1 CROSS 60"   # press X until a RAM condition holds
tools/dev/emulator.py save build/x.state ; tools/dev/emulator.py load build/x.state   # full save states
tools/dev/emulator.py record build/v.mp4 20         # 20 s of video, in parallel with other commands
tools/dev/frame_capture.py build/frames 10          # every displayed frame, paused at each vertical refresh
tools/dev/emulator.py lua 'return PCSX.getMemPtr()[0x134eb4]'
tools/dev/emulator.py stop
```

- `EMU_PORT` picks the instance (default 38090): every port has its own state file (`build/emu-PORT.json`) and
  portable folder, so several emulators run side by side. Most test scripts default to a port of their own and honour
  `EMU_PORT`. `emulator.py start` refuses a port already in use.
- `EMU_ARGS` passes options to PCSX-Redux: `-interpreter -debugger` is required for Lua breakpoints (they do not fire
  under the dynarec), at about half speed. Keep the original 2 MB RAM for
  compatibility tests; `-8mb` is for development diagnostics only. `EMU_AUDIO=FILE.raw` records
  what the SPU plays, and `record` muxes it into the video.
- Symbols: `emulator.py`, `game_state.py` and `memory_inspector.py` resolve names for the executable that is running, the original or any
  GCC build (`tools/dev/symbols.py` compares the code in RAM with each known build). `DW_SYMS=NAME` names the build
  explicitly (`decomp-int`, `disc-wtif`, ...); use it when several builds share the code start.
- Memory cards are fresh on every `start` unless `--keep-cards` or `--card FILE` is given.

Underneath, `emulator.py` talks to the emulator's web server: `GET /api/v1/screen/still` (PNG), `GET /api/v1/gpu/vram/raw`,
`GET|POST /api/v1/cpu/ram/raw`, `/api/v1/execution-flow`, and `/api/v1/lua/<handler>` for the handlers defined in
`tools/emu-handlers.lua` (`eval`, `press`, `release`, `frames`). The web server accepts RAM writes without
authentication on every interface: do not expose its port, and stop the emulator after a test.

Things to know:
- Save states hold the executable and the disc's file offset table: they only fit the disc they were made with. A
  memory card save holds only game data and works with any build, so tests start from a card and `continue.seq`.
- A Lua event listener must be kept in a live variable, or the garbage collector removes it (a pad override then stays
  held). A script killed between a press and its release leaves the button held: release the 16 buttons of
  `emu.BUTTONS` before the next test.
- A breakpoint that pauses the emulator is resumed with `tools/dev/emulator.py lua 'PCSX.resumeEmulator()'`.
- "DMA bus error" in the log means the game built a looping GPU ordering table. PCSX-Redux then leaves an interrupt bit
  set and the next DMA wait hangs; on a console the GPU would time out instead. Find who linked the primitive twice
  (an exec breakpoint on `AddPrim`).
- The web server rejects very long URLs; `emu.py lua` passes long code through a file.
- The second pad is disconnected by default; a two-player test connects it from Lua and presses through
  `PCSX.SIO0.slots[2]`. `tools/dev/playtest/versus_mode.py` opens the VS mode on fake registered Digimon without cards.

### A memory card to start from

Most scripts expect `build/states/file-city.mcd`: a card whose save puts the player in File City with control. Make it
once: start a new game on your built disc choosing the memory card instead of "no memory card"
(`tools/dev/sequences/new-game.seq` plays the opening up to control in about ten minutes), build a disc with
`tools/dws/examples/dev-save.dws` (talking to Jijimon opens the save machine), save, and copy the emulator's
`.tools/emu/home*/memcard1.mcd` a few seconds after the save ends. `tools/dev/memory_card.py` reads and edits card images without
the emulator (`ls`, `save` shows both copies of a save with checksum and contents, `patch`, `fill`).

### Game state by name

```bash
tools/dev/game_state.py show money hour partner.stats tamer.state current_screen
tools/dev/game_state.py set money=5000 hour=12 partner.para.foodLevel=100
tools/dev/game_state.py warp 236 0            # change screen like a door (screen ids: reference/world.md)
tools/dev/game_state.py approach 0            # stand in front of NPC slot 0, facing it; then press CROSS to talk
tools/dev/game_state.py dump build/s.json ; tools/dev/game_state.py apply build/s.json
tools/dev/memory_inspector.py show PARTNER_ENTITY.digimonEntity.stats   # any global with its C type (DWARF of the GCC build)
tools/dev/memory_inspector.py watch HOUR MINUTE GAME_STATE -i 1
tools/dev/memory_inspector.py where 0x801557E0            # which variable and field is at an address
tools/dev/dashboard.py -w                         # a live dashboard of the state
```

Recipes need the player in control: `GAME_STATE` 0, `TAMER_STATE` 0, `IS_SCRIPT_PAUSED` 1, `IS_IN_MENU` 0. A warp
writes `TARGET_MAP` and `CURRENT_EXIT` and sets the tamer state to 5; moving the player writes the location, the
entity's animation location and `STORED_TAMER_POS`; a forced evolution writes `EVOLUTION_TARGET` and the partner and
tamer states. The clock (`HOUR`, `MINUTE`) must agree with `CURRENT_FRAME` (20 frames a game minute); to cross midnight
set 23:59 and wait. The addresses are in [reference/ram-map.md](reference/ram-map.md).

### DuckStation: `tools/dev/duckstation.py`

```bash
tools/dev/duckstation.py start build/wtif.cue [--oc 300] [--icache] [--state FILE] [--hq]
tools/dev/duckstation.py seq tools/dev/sequences/continue.seq
tools/dev/duckstation.py peek MOD_FPS_BUILD 4         # symbols from DS_MAP (the build's linker map)
tools/dev/duckstation.py measure 10                   # vblanks, logic ticks and presented frames over 10 s
tools/dev/duckstation.py shot build/ds.png ; tools/dev/duckstation.py stop
```

Memory goes through DuckStation's GDB stub (127.0.0.1, `DS_GDB_PORT`, default 2345): connecting halts the emulator, the
request runs and the stub resumes it. Input is the keyboard through `xdotool` on the private display. `--hq` draws with
OpenGL at 3x with a texture filter and PGXP on a real X server (needs a GPU), the way a handheld would.

## 3. Recorded walks (`tools/dev/walk/`)

The walkable ground and the exits of a screen are checked by walking the tamer through a tour of screens while the
screen is recorded, then laying the video beside the screen's walkable-zones image with the tamer's path. `tour.py`
plans over the engine's own reachable lattice (`reach.py`) and steers with the pad, clicking through dialogs and
battles; `walk.sh` and `walkall.sh` record one or several walks. Details and pitfalls: `tools/dev/walk/README.md`.

## 4. Play tests of the patches (`tools/dev/playtest/`)

One script per rule that a C patch moved into data or changed: each boots `build/int.cue` (or `DISC=`), puts the game in
a known state by RAM writes, calls or triggers the code and compares what it did with the table in `content/tables/`,
often also with the table poked to other values (proof that the code reads it) and wiped (proof of the fallback).
Examples: `care_rules.sh`, `evo_rules.sh`, `evo_formula.sh`, `gym_session.sh`, `item_effects.sh`, `economy.sh`,
`world_rules.sh`, `new_game.sh`. `battle_host.c` and `train_mult_host.c` compile the original and the table-driven
function on the host and compare them over every input.

Helpers: `callfn.py` calls any game function at a frame boundary and prints its return value; `talk.py` walks into the
NPC in front and taps X until its script runs; `shopnav.py` drives a shop by the game's own RAM state;
`labevolve.py` evolves the partner through the development menu; `raise.py` marks types as raised; `calltourn.py`
starts a tournament from the lobby; `technique_proof.py` and `species_proof.py` play every technique and species of a
disc unattended; `fonttour.py` screenshots every screen that draws text; `battle_stream.py` runs battles in a row on
one screen (the background stream and the battle camera).

`python3 tools/dev/playtest/timed_battle_host.py build/decomp-int` runs the actual field battle loop with deterministic events: expiry during
finishers, attacks, hit/block reactions and pending damage; victory or defeat at the deadline; and an unlimited fight.
For the Airdramon ambush, use the real script and original 2 MB RAM:

```bash
python3 tools/dev/playtest/airdramon_timeout.py build/air-fixed.cue \
  --exe build/air-fixed/exe/SLUS_010.32 --port 39141 --case hold --release-tick 90 \
  --out build/air-held --field-state build/air-field.state
python3 tools/dev/playtest/airdramon_timeout.py build/air-fixed.cue \
  --exe build/air-fixed/exe/SLUS_010.32 --port 39141 --case fight --release-tick 100 \
  --out build/air-fought --field-state build/air-field.state
```

The harness copies the save corpus to a private native-Agumon test card, shortens only the test's “Hold back” limit
to ten seconds, keeps Airdramon at quarter HP and starts his finisher at the selected tick. Tick 90 places expiry
during impact; `--release-tick 140 --allow-charge` tests the aura hold. The unlimited path wins by a real partner
attack after the finisher. JSON, screenshots and states record the deadline and completed story outcome, including
HUD objects, finisher globals and the partner's hit state. Field checkpoints require the same disc and test-card
hashes. `--expect-unsafe` diagnoses the old premature teardown; it does not assert that every timing visibly freezes.

Other suites:

| Folder | What |
|---|---|
| `tools/dev/saves/` | memory card saves: make a save, continue from it, cut a write at every point (a power cut must leave the old or the new save), failing reads and writes, absent content dropped on load; `tearmodel.py` predicts every torn card offline |
| `tools/dev/fps/` | the frame rate: logic ticks and game minutes per real minute, per-tick state hashes at 20/30/60 fps, cost per render pass; its README |
| `tools/dev/memory/` | the reclaimed memory: the background stream ring, VRAM window, NPC model slots, stack high water; its README |
| `tools/citytest/`, `tools/dws/testing/city_equivalence.py` | the table-driven city rules against the original C, compiled on the host and in the emulator ([mods/city-rules.md](mods/city-rules.md)) |
| `tools/dev/models/review/`, `tools/animstudio.py` | the imported species' animations: an offline studio (mesh, bones, foot gait, the donor beside it) and a web review page ([reference/motion.md](reference/motion.md)) |

## 5. Story tests

How a build of the story scripts (`DG.SCN`, `MAPHEAD.SCN`) is shown to behave like the original disc: run the same
thing on both in PCSX-Redux and compare what the script engine did. The static half (same bytes, control-flow
equivalence per section) is `dws.py roundtrip`, `dws.py story-verify` and `tools/dws/flowcmp.py`; this is the dynamic
half. Engine background: [reference/story-engine.md](reference/story-engine.md), [reference/scripts.md](reference/scripts.md).

| Tool | What |
|---|---|
| `tools/dev/story_test.py` | `disc`, `boot`, `run`, `check`, `diff`, `list`, `record`, `offline` |
| `tools/dev/story_trace.lua` | runs inside the emulator: frame-exact scenario player and tracer |
| `tools/dws/testing/scenarios/` | the scenario corpus, one JSON file each, with its expected digest |
| `tools/dev/story_test_offline.py` | the checks that need no emulator (run by the self-test) |
| `tools/dws/testing/sweep.py`, `tools/dws/testing/trace_audit.py` | every section of the story called once, original against rebuilt discs; the audit of normalized verdicts |
| `tools/dws/testing/checkpoints.py`, `tools/dws/testing/route.py`, `tools/dws/testing/branches.py` | the new-game route between saved checkpoints; the main story to the ending; loss branches and area tours |
| `tools/dws/testing/random_audit.py`, `tools/dws/randflow.py` | random draws at run time; the static proof that every path draws in the same order |
| `tools/story_analysis.py` | measures the story layer from a disassembly (CSV tables in `build/story-analysis/` that `tools/dws/testing/branches.py` reads) |
| `tools/dev/story_video.py` | a split-screen video: the game beside the story source with the running line highlighted |

### How a run works

1. The emulator starts on the disc under test with `-interpreter -debugger` and a memory card.
2. One saved state is loaded (`build/dwstest/boot.state`: the game in Jijimon's house with control; `tools/dev/story_test.py boot`
   makes it once). Every run, on every disc, starts from that state.
3. While paused, the harness writes into RAM what the state holds from the disc it was made on: the disc under test's
   MAPHEAD and `DG.SCN` offset table, `ACTIVE_MAP_SCRIPT = 0xFFFF` (so the screen script is read again) and the
   scenario's `setup` (money, items, triggers, pstats, clock).
4. `tools/dev/story_trace.lua` is installed and the emulator resumes. A breakpoint on `gameLoop` gives one hit per frame: presses,
   waits and conditions are counted in frames, never in host time.
5. When the steps end (or a battle starts, or a limit is hit) the trace is written and the emulator paused.

Steps (all counts are frames; `parse_step` in `tools/dev/story_test.py` is the reference):

| Step | Meaning |
|---|---|
| `wait N`, `press BTN [N]` | wait; hold a button N frames |
| `until COND [press BTN [N] [every G]] [max M]` | wait until the condition holds, pressing BTN every G frames |
| `talk until COND [max M]` | press CROSS whenever a text box or a menu waits |
| `talk after battle N [max M]` | press CROSS until the N-th battle of the run has started and ended |
| `warp SCREEN [EXIT]`, `approach SLOT [DIST]`, `move X Z` | change screen; stand in front of an NPC; stand on a spot |
| `call SCRIPT SECTION [EVENT]` | run any section without walking to it (the Lua hook enters `callScriptSection` at a frame boundary) |
| `trigger N 0\|1`, `pstat N V`, `poke SYMBOL HEX`, `clock H M` | state changes in the middle of a scenario |
| `trace on\|off`, `mark NAME`, `end` | the tracer is off during `pre` and on during `run`; `mark` takes a checkpoint |
| `npc? SID skip K`, `tile? V skip K`, `approach? SLOT skip K`, `warpif SCREEN [EXIT] skip K` | optional steps |

Conditions are joined with `and`: `free` (no script running and the tamer idle), `idle`, `running`, `screen==N`,
`trigger N` / `!trigger N`, `pstat N>=V`, or `SYMBOL[:size] OP value` (`MONEY>=500`).

A scenario is `tools/dws/testing/scenarios/NAME.json` with `setup`, `pre` (untraced: getting to the place), `run` (traced),
`end_on_battle`, `max_frames` and `expect` (`digest`, `instructions`).

```bash
export EMU_PORT=38020
tools/dev/story_test.py boot                       # once
tools/dev/story_test.py disc dws --dws             # a disc whose DG.SCN and MAPHEAD are decompiled and recompiled
tools/dev/story_test.py disc mut1 --mutate 178:5:1318=d8    # a negative control: a byte changed
tools/dev/story_test.py run kunemon-decline --show # one run, the executed instructions listed
tools/dev/story_test.py check --discs orig,dws,mut1 --mutants mut1   # the corpus on every disc; a mutant must differ
tools/dev/story_test.py check kunemon-decline --discs orig --reps 3   # determinism of one scenario
```

### What is traced

One line per event in `build/dwstest/NAME.DISC.N.trace`: instructions dispatched (with the count of random draws so
far), watched bytes that changed (triggers, cards, pstats, money, merit, screen, inventory, partner stats), sounds and
music, battle starts and checkpoints. Raw traces contain the bytes of the game's text, so they stay in `build/`; only
digests are committed. The canonical form drops file layout (an instruction is `script:section+offset MNEMONIC #hash`
with branch targets as `section+offset`), so moved code compares equal when it does the same thing; the digest is the
SHA-1 of the canonical lines, without frame numbers (frames are compared separately as drift).

Determinism comes from loading one state per run (booting from a card is not reproducible), running presses inside the
emulator by frame, pinning the clock when tracing starts, and replacing the cached scripts from the disc under test.
`rand()` and the game's own generator are deterministic from the state; only the number of draws before a point
changes values. A battle frozen mid-load leaves the CD busy, so a run that ends in a battle stops the emulator.

### The section sweep and the routes

`tools/dws/testing/sweep.py` runs every section of the scripts once (each in the screen that loads its script, in a state that places
the NPCs it names) on the original disc and on rebuilt discs (`reorder`: every script's code chunks shuffled;
`readable`: the decompiler's readable output recompiled), as a background service with a ledger in `build/sweep/`. Its
normalized comparison drops only what moving code changes without changing behaviour: instruction positions and
branch targets, `JUMP_TO`, `IF` (its outcome shows in what runs next) and a `SET_DIALOG_OWNER` to the speaker already
set; ambient sounds and the count of random draws are not compared because the original differs from itself in them.
`SWEEP_PIN_RANDOM=1` sets the generators before each `STORE_RANDOM`, so a roll's value depends on the instruction. End
rules (in game frames): the section returned, a battle reached, 240 idle frames, 4 000 instructions, or a host-time
watchdog. Verdicts: PASS, FAIL (re-run at once to separate flakes), NOT-RUNNABLE, HANG.

```bash
tools/dws/testing/sweep.py start [--disc all|orig|reorder|readable] [--pin-random]
tools/dws/testing/sweep.py status --short ; tools/dws/testing/sweep.py report ; tools/dws/testing/sweep.py stop
```

`tools/dws/testing/checkpoints.py` plays from a real new game and compares the discs between saved checkpoints; `tools/dws/testing/route.py` walks the
main story to the ending (forced battles ended by setting the foes' HP to 0, unplayed state written by pokes);
`tools/dws/testing/branches.py` runs the loss branch of each forced battle and area tours chosen by the sections they add.

Gotchas found by these tests: the tile lookup has no bounds check (an NPC parked off the map puts the tamer outside the
grid and the read lands in the MAPHEAD buffer); a tile section that does not change the screen reruns every frame while
the tamer stands on it; a lost forced battle abandons the section in C and wakes the tamer in Jijimon's house; Jijimon's
talk branches on the partner's species; opening the Item Shop menu without its shopkeeper loops forever; a CROSS in the
first ~60 frames after a teleport can be ignored.

### Writing a scenario

1. Find the entry: screen, script and section (`dws.py decompile ID`, `scnasm.py dis`) and where the NPC or tile is
   (`tools/dwmap.py`; tile `(tx, tz)` is at `x = (tx-50)*100+50`, `z = (50-tz)*100-50`).
2. Put the state it needs in `setup` and get there in `pre`.
3. `tools/dev/story_test.py run NAME --show --keep --shot build/x.png` lists what ran and leaves the emulator paused.
4. `check NAME --discs orig --reps 3`, and once stable `check NAME --record`.

## 6. Optional handheld testing

An Android handheld running DuckStation can be reached over adb (USB, or wireless adb on the local
network: enable USB debugging, then `adb tcpip 5555` once over USB, or the device's wireless debugging).

```bash
export DEVICE=HOST:5555                 # or the USB serial from `adb devices`
tools/dev/device.sh                         # build build/device.cue (python3 -m tools.dev build), copy it to the device, start DuckStation
tools/dev/device.sh push                    # copy the existing build and start
tools/dev/device-state.sh save NAME         # DuckStation quick save, kept on the device as NAME
tools/dev/device-state.sh load NAME         # restart the game and load it
tools/dev/device-state.sh shot build/d.png  # screenshot over adb
```

The device driver copies the image to `/sdcard/Digimon/`; add that folder to
DuckStation's game list. The current driver does not expose a directory override.
`device-state.sh` presses
DuckStation's Quick Save and Quick Load hotkeys on the device's own controller with `sendevent`: bind them once in
DuckStation (Controller Settings > Hotkeys) to two buttons nothing else uses and give their key codes and the input
device (`KEY_SAVE`, `KEY_LOAD`, `INPUT_DEV`; find them with `adb shell getevent -l`). A press injected with
`adb shell input` registers as a virtual device and does not reach the bindings. A save state belongs to the disc it
was made with.

Keep original 2 MB RAM and stock CPU/CD timing for compatibility checks. Handheld
speedups and rendering preferences are optional performance settings and do not
prove original-console behaviour.

DuckStation settings, in its per-game settings file for the disc's serial (`gamesettings/SLUS-01032.ini`
in its data folder), applied on a clean boot:
- `[CDROM] ReadSpeedup = 0, SeekSpeedup = 0, LoadImageToRAM = true`: a screen change is mostly CD seeks; loading the
  image to RAM cuts it from about 7 s to 2 s.
- CPU overclock (set in the app): the 60 fps build draws more frames than the original console's CPU allows; with the
  emulated CPU at 1x it presents fewer frames than it could.
- Resolution scale 2x or 3x with a bilinear texture filter; heavier filters cost GPU time with the largest imported
  models on screen.
- Analog-only triggers (L2/R2 reported as axes) must be bound as positive axes, or button combinations with them do
  nothing.
