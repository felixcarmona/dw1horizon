# Developer tools

Run these tools from the repository root. They locate their own worktree; generated
captures, Lua and reports belong under `build/`. Emulator transport honors `EMU_PORT`.

| Area | Entry points |
|---|---|
| PCSX-Redux | `emulator.py`, `symbols.py`, `game_state.py`, `memory_inspector.py`, `snapshot.py` |
| DuckStation and device | `duckstation.py`, `device.sh`, `device-state.sh`, `continue.sh` |
| Video and inspection | `frame_capture.py`, `presented_frames.py`, `vram_image.py`, `dashboard.py`, `story_video.py` |
| Story emulator tests | `story_test.py`, `story_trace.lua`, `story_test_offline.py`; scenarios remain under `tools/dws/testing/scenarios/` |
| Measurements | `fps/` for frame-rate/tick checks; `memory/` for streaming, VRAM, NPC and stack checks |
| Integration tests | `playtest/` and its independent host-C oracles; `saves/` and the published save corpus |
| Map walking | `walk/`; collision/reachability comes from `tools/maps/reach.py` |
| Model review | `models/review/`; a compatibility import remains for saved review provenance |

```sh
python3 tools/dev/emulator.py start build/what-the-island-forgot.cue
python3 tools/dev/game_state.py show current_screen tamer.state
python3 tools/dev/emulator.py stop
python3 tools/dev/saves/releases.py check
python3 tools/dev/story_test.py offline
FD_MAP=build/what-the-island-forgot/exe/SLUS_010.32.elf.map \
  python3 tools/dev/presented_frames.py start build/capture.raw 600
```

`frame_capture.py` captures at explicit emulator refresh boundaries. The presented-frame
capture records actual GPU swaps and expands their refresh counts to 60 Hz for video;
`FD_MAP` selects the matching executable. Generated FPS Lua is separated by port under
`build/dev/fps/`.

The root emulator, symbol, memory and game-state entry points remain thin compatibility
adapters for protected motion recipes. `tools/device.sh` also forwards frozen device drivers. `tools/emu-handlers.lua` and
`tools/playtest/technique_proof.py` retain their exact bytes because frozen recipes pin
their hashes. The technique proof's sibling import uses a small compatibility adapter. The old review-library path also has an import adapter for saved motion provenance; that historical recipe's hash already predates the current library.

See [emulator setup](../../docs/developing.md), [story testing](../../docs/developing.md),
[save compatibility](../../docs/reference/save-format.md), [FPS checks](fps/README.md) and
[memory checks](memory/README.md). `tools/selftest.sh` covers offline contracts; emulator
integration suites require a matching disc, symbols and memory card.

`playtest/` symbol-driven shell checks accept `DW_SYMS` (default `disc-full`).
The historical `saves/tagged.sh` and `saves/robust.sh` compare old save formats;
supply their documented disc/executable fixtures explicitly. They do not build retired engine variants.

Build and optionally boot the everything disc with
`python3 -m tools.dev build [--lang en] [--run]`.
See [incremental builds](../../docs/developer-cache.md) for cache verification,
source-disc paths, test-language selection and `--no-cache`.

Device drivers require `DEVICE` (adb USB serial or wireless `HOST:PORT`). Transfers
use `/sdcard/Digimon/`; there is no output-directory override. State hotkeys require
`INPUT_DEV`, `KEY_SAVE` and `KEY_LOAD`; launches require `TAP="X Y"` for the game
row. Discover controller codes with `adb -s "$DEVICE" shell getevent -l` and bind
those buttons in DuckStation first. These settings depend on your device.
