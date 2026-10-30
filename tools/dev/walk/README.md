# tools/dev/walk: recorded walks of a disc's screens in the emulator

Checks a screen's walkable ground and exits by walking the tamer through a tour of screens on the running emulator
while the screen is recorded, then lays the video side by side with each screen's walkable-zones image and the tamer's
path. See `docs/developing.md` for the emulator setup.

- `tour.py TOUR.json`: the walker. A tour is `[[screen, MAP_FILE, [[[u, v], pause], ...]], ...]` (background pixels of
  each waypoint); it plans over the engine's reachable lattice (`tools/maps/reach.py`, the tamer's body box), steers with the pad
  in screen directions, clicks through dialogs and battles (CIRCLE/X alternated), freezes the clock and refills the
  partner's HP/MP after every event, moves the partner behind the tamer after five stuck steps (narrow strips), and
  walks past a segment's last waypoint when the screen did not change (the exit boxes sit at the edge). Logs
  `TOUR.json.poslog.json` for the overlay.
- `walk.sh NAME TOUR.json FIRST_SCREEN FIRST_EXIT SEC`: one recorded walk: frees the game, resets the partner's care
  state and stats, warps, records SEC seconds while `tour.py` walks, then `overlay_video.py` makes `build/new-maps/walks/NAME.mp4`.
- `walkall.sh`: several walks in a row on a fresh emulator (`WALKS="name:tour:screen:exit:sec ..."`), `DISC` and `CARD` select the inputs. Clips remain under `build/new-maps/walks/`. `EMU_PORT` picks the emulator: two
  chains on two ports run fine.
- `framesheet.py VIDEO OUT.png [N] [POSLOG]`: a contact sheet to judge a walk without watching it.
- `adjust_arrivals.py TOUR.json ...`: makes each segment's last waypoint the real exit to the next screen (the map's warp pushed
  300 units outward, projected to pixels); run it on every new tour, the hand-picked exit pixels missed on 330 and 334.

Needs: the emulator (`tools/dev/emulator.py`) with the disc's symbols (`DW_SYMS`), a venv with numpy and cv2
(`PY=`, default `python3`), the zones images (`ZONES=`, default `build/new-maps/<screen>/NAME-zones.png`)
and the tours (`TOURS=`, default `build/new-maps/tours/`). A killed walker can leave
a pad button held; release the pad before the next test (see
[emulator setup](../../../docs/developing.md#2-emulators)). Stop `walkall.sh`
before editing it.
