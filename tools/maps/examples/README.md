# Worked cut-out examples

The specs are our prompts and metadata. They contain no disc data or raster masks.
Full-resolution source art is supplied locally and is not bundled with these specs.
Use your own matching source images at the example paths, or pass their local paths
with `--art`; the recorded comparison below requires the original source art.
Run commands from the repository root after extracting the player's disc and running
`tools/maps/setup-sam.sh`. Review outputs are local `build/` artifacts, never shipped.

## Engine Room (300)

`engine-room.json` regenerates the two currently visible static foreground pieces
from `art/full/engine-room-2304x1856.png`. It preserves the fire instance and its
TIM space. Crop `[0,6,2304,1849]` is the centred 5:4 crop used for the 640×512 art.
The original positive/negative prompts, floor exclusion and cleanup are recorded;
`depth_world` comes from the established pieces' ground contacts.

Use the commands in [the tool README](../README.md#engine-room-regression-example).
Then compare the candidate independently against the original sprite instances and
finished background, including every time-of-day palette:

```sh
build/sam-venv/bin/python tools/maps/examples/compare_engine_room.py \
  build/engine-original/ENGN01.MAP build/engine-original/ENGN01.TFS build/engine-review
```

Both raw object masks reproduce the original SAM masks **pixel for pixel**.
The new floor exclusion differs at 80 edge pixels: prompt Y coordinates use the
exact crop-height scale (1843/512), while the original script used width/640 for
both axes. This does not change either cleaned object silhouette.
After subtracting the floor, discarding components below 25% of the largest and
filling holes for these solid objects, the comparison with the committed TIM
silhouettes was:

| Object | Committed opaque pixels | Regenerated pixels | Intersection / union | Added / removed |
|---|---:|---:|---:|---:|
| `br-crates` | 8038 | 8038 | 1.0 | 0 / 0 |
| `wreck` | 3853 | 3853 | 1.0 | 0 / 0 |

The raw masks alone differed by 180 and 134 pixels respectively: floor, detached
components and holes require the explicit cleanup. This is why raw segmentation
confidence cannot replace review. Keep hole filling off for gates, lanterns and rails.

The new packer chunks each silhouette into guarded 64-pixel rectangles instead of
two large rectangles; it preserves the world depth anchors, final image positions,
all existing TIM dimensions/counts/upload addresses, and the fire. Texture placement
bytes differ, so candidate MAP bytes are not expected to equal the original MAP.
The old TIM colours differ from the current finished background at 2695 masked
pixels in `br-crates` and 1205 in `wreck`; the new pieces have **zero** colour
mismatches. The Engine Room has one interior palette; the regression tests also
exercise multiple day/night palettes and preserved animation colours.
Opaque pixels take the finished TFS's exact indices; index-zero art pixels use
palette alias 17 (`0x8000`, opaque black), leaving transparent zero outside the mask.
The aliases affect only unused background palette slots. Collision is unchanged.
Run `check` on the candidate; its palette, silhouette, footprint and arrival checks
must pass. This example does not modify the shipped Engine Room or claim a new
walking acceptance result.

## Retired New Street open gate

This example uses the retired New Street art, which is distinct from the live
Stone Yard screen. It produces a **review sheet only**, with no candidate MAP/TFS or map edits:

```sh
build/sam-venv/bin/python tools/maps/cutout.py generate \
  tools/maps/examples/retired-new-street.json \
  --art story/mods/what-the-island-forgot/art/full/the-new-street-2304x1856.jpg \
  --map build/engine-original/ENGN01.MAP \
  --out build/retired-street-review --review-only
```

The Engine Room MAP supplies only the required 640×512 geometry placeholder here;
its collision/depth suggestions **do not describe New Street** and must not be used
as that screen's layout. The retired art's old layout is not a live map contract.
This is an isolated silhouette example, not an endorsement of the retired district
concept or a replacement for an active screen.

The gate prompt selects 5300 pixels, SAM confidence 0.985. At 3x, review both open
leaves and the arch, keeping the opening transparent. This tests the opposite of the
Engine Room's solid-object cleanup: no hole filling. No new art generation is needed.
