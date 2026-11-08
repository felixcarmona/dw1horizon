# Story integration regressions

These tests exercise the authored ferry calendar, clock-gated hunters and reciprocal
Infinity exits with small AST harnesses. They do not start an emulator.

```sh
python3 -m unittest discover -s story/mods/what-the-island-forgot/test
```

`test_mayo05_foreground.py` rebuilds the Coela Point stair recipe from the player's
extracted disc and checks that the foreground leaves the stairs visible in all
three palettes. It also checks unchanged cutout geometry, transparent donor
texels, unrelated TIMs and exit collision. This test skips without `extracted/`.

`test_hunters.py` also checks the shared first-sighting flag in both encounter
orders, every hour and both rumour states. `test_hunter_tiles.py` builds the
sighting retouch and checks that only ordinary floor changes, keeping the
existing southern connection, exits, hunter records and backgrounds.

`playtest_feeding.py` runs the real inventory handover on original 2 MB RAM,
records per-refresh scale, position, visibility flags and resident meshes, verifies item consumption and
checks the live heap. The executable must keep its matching `SCRN.DAT` beside
its `exe/` directory. Generated cards, traces, screenshots and videos stay in
the output directory.

```sh
xvfb-run -a python3 story/mods/what-the-island-forgot/test/playtest_feeding.py \
  build/bugs11.cue --exe build/bugs11/exe/SLUS_010.32 \
  --archive build/bugs11/DIGI.DAT --map build/bugs11-maps/screens/SHOR01.MAP \
  --ids 307 --record --out build/feeding-proof
```

Use `--all --handoff-fixture` to check every imported partner's eating clip.
The optional fixture skips approach walking only when it has not finished;
the handover, cold read, animation and food effect still run in the game.
The result records whether that fixture was used. `--item 5 --discipline 0`
exercises Medium MP refusal; `--require-clip 13` requires that random branch.
`--pixel U V` selects another safe setup point on the supplied shore map.

`--state FIXTURE.state` resumes a fixture captured with the same disc before
repositioning on the shore; this supports splitting long roster runs.

`playtest_toilet.py` exercises File City's real toilet tile (120), approach,
cold slot 10, care update, return script and subsequent pad movement on 2 MB.
It observes the native return-look call and requires the partner's position
pointer, plus resident geometry and an intact heap. It skips no approach phase.
The building can hide the partner during the toilet animation; successful exit
and movement are checked separately.

```sh
xvfb-run -a python3 story/mods/what-the-island-forgot/test/playtest_toilet.py \
  build/bugs11.cue --exe build/bugs11/exe/SLUS_010.32 \
  --archive build/bugs11/DIGI.DAT --ids 307 --record --out build/toilet-proof
```

Use `--all` for all 175 imported partners. `--sleep-due` adds the night-time
sleep need; `--max-ticks` defaults to 400 logic ticks for a complete visit.
Each successful case saves `resume.state`; `--state` resumes a fixture made
with the same disc for a split run. `--allow-wrong-target` records the known
pre-fix stack pointer instead of rejecting it, for baseline comparison only.
