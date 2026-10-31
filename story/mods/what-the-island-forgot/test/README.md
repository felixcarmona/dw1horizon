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
