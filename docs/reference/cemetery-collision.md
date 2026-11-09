# Overdell Cemetery collision pockets

The Android battle recording in report 1569113319217045664 shows screen 35,
`DGHA02`, on the stone path below the fallen tree. Background matching places
the visible viewport near background pixel (166,363). The tamer at the lower
edge stands on connected floor. The partner is mostly obscured at the tree's
west side by the HUD; its species and exact foot position cannot be recovered
reliably from this clip alone.

The native collision contains two false holes in object bodies: tile (38,50)
inside the upright broken stone beside the stump, and (36,54) inside the broken
stone below it. A 100-unit tamer has dead positions in the former; a 190-unit
partner at world (-1350,-450) in the latter cannot take any of the 32 tested
50-unit steps. The nearby tiles (34,53) and (37,56) incorrectly block bare grass.
The entry script adds no impassable rectangles here. These are original asset
errors, not a recent release's collision change.

`content/maps/DGHA02.json` closes both object holes and opens the two grass
cells. Opening the grass matters: simply sealing the broken stone would leave
an actor already standing there wedged. Existing warps, triggers, camera,
foreground and actor placement bytes are unchanged.

A PCSX-Redux check with original 2 MB RAM and the original collision routines
uses the controllable tamer model with its radius temporarily set to 190.
From (-1350,-450), all eight directional inputs remain at that position before
the change. With the corrected grid, twelve input frames move south to
(-1350,-550) or west to (-1450,-450). This isolates the map geometry; it does not
replay the reporter's save or identify the obscured partner.

## Whole-map static audit

The same isolated-tile check runs over all 242 native map assets and 69 generated
maps, with retouches preferred over original geometry and committed native
collision edits applied last:

```sh
python3 tools/maps/check_traps.py --maps build/NAME-maps --jobs 2 --json build/traps.json
python3 tools/test_collision_pockets.py
python3 -m unittest tools.test_reach_policies tools.test_map_collision_edits
```

The checker uses `reach.py`'s 10-unit arrival flood and its 32-direction,
50-unit dead-position test. It checks every used arrival together and uses
script-only arrival coordinates when a map has no ordinary warp. It rejects
plain free cells that contain a dead position and receive no walking positions.
It excludes exit and script triggers: their effects require the script model.

The review closes 114 such cells across 55 native assets, including the cemetery
shard; the cemetery also gets the broken-stone closure and two grass openings.
Other corrections are on prop bodies, wall faces, cliff lips and outside the
rendered routes. Each committed cell records its previous value and reason.
Most preserve the exact walking set; some remove small standing margins beside
the newly solid scenery. They do not change connections or script triggers.

These are fixed-size MAP collision-byte changes. They add no main executable,
heap, model, sprite or archive allocation. C changes still belong in the patch
series; these asset changes use the existing native collision data pipeline.

The static check does not certify every partner radius, forced battle movement,
combat-camera boundary, live actor or scripted obstacle. Larger-body movement
candidates must be checked with actual movement strides and live state before
changing clear floor, props or exits on their account.
