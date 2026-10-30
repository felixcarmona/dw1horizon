# Map authoring tools

Our code in this directory is MIT licensed (see `LICENSE`). SAM and its checkpoint
are external Meta dependencies under Apache-2.0; they are downloaded, never vendored.
The complete authoring and acceptance recipe is [new-maps.md](../../docs/mods/new-maps.md).
Run commands from the repository root. Outputs belong under ignored `build/`.

```sh
tools/maps/setup-sam.sh
build/sam-venv/bin/python tools/maps/cutout.py --help
```

The setup uses the official [SAM repository](https://github.com/facebookresearch/segment-anything)
and its ViT-H download. The checkpoint is 2.4 GB. Its full SHA-256 is pinned in
both setup and inference. CPU inference defaults to three Torch threads. The setup installs neither Pillow
nor torchvision: `tools/maps/sam.py` loads the prompted predictor with our exact
bilinear image adapter. PNGs use `tools/image.py`; bundled bitmap glyphs draw developer captions. Run one
process for all objects on a screen: it encodes the full-resolution image once.

## Input contract

`cutout.py generate SPEC --art FULL.png --map SCREEN.MAP --tfs SCREEN.TFS --out DIR`
reads a version 1 JSON. All input paths are command arguments, relative to the
current working directory; JSON contains no machine paths.

```json
{
  "version": 1,
  "size": [640, 512],
  "crop": [0, 6, 2304, 1849],
  "chunk_size": 64,
  "hide_instances": [1, 2],
  "packing": [{"tim": 0, "x": 0, "y": 0, "width": 256, "height": 256}],
  "objects": [{
    "name": "gate-post",
    "box": [500, 170, 610, 360],
    "positive": [[560, 260]],
    "negative": [[510, 300], [600, 180]],
    "depth_world": [1400, 0, -1800],
    "tiles": {"behind": [[65, 61]], "blocked": [[65, 62]]},
    "min_component": 3
  }]
}
```

- `size`: final background dimensions, equal to the MAP tile layout. `crop`:
  **exclusive** full-resolution pixel bounds of the exact crop used for that
  background. Record the crop when making the art; do not guess it afterwards.
- `box`, `positive`, `negative`: final background pixel coordinates, transformed
  back into full-resolution coordinates before SAM runs. The box is a prompt,
  never a mask or a clipping rectangle. Tighten boxes and add floor negatives if
  SAM selects too much. `multimask` defaults to true (highest-confidence result).
- Masks are area-downscaled at a 0.5 threshold; components below `min_component`
  final pixels are removed. Real holes and disconnected thin parts remain. Never
  fill all holes or discard all but the largest component by default.
- Optional `exclusions` contain named SAM prompts (box optional) that objects may
  `subtract` before cleanup; use them for floor. `min_fraction` removes components
  below a fraction of the largest **after subtraction**. `fill_holes` defaults to
  false; enable only for solid objects. `sam-masks.npz` retains pre-cleanup results.
- `depth_world`: field sprite depth anchor `[x,y,z]`, usually the object's ground
  contact. The engine sorts this 3D point; JSON array order does **not** set draw
  order. Use the same anchor for all chunks of one object. A bridge or roof may
  need several objects with separate anchors. `y=10000` is background depth and
  is inappropriate for a foreground occluder.
- `tiles`: reviewed collision tile coordinates `[tx,tz]`, never image pixels.
  `blocked` is the object's body/footprint. `behind` is floor where hiding the
  character is correct. These are decisions for a human after viewing the grid.
  Undeclared overlaps become `behind` suggestions when the body overlaps and the
  tile is beyond the depth anchor, conservative `blocked` suggestions when feet
  touch the mask, or `review` when the depth is ambiguous. Suggestions record
  whether they were explicitly reviewed; none is automatically applied.
  The tool never changes collision automatically.
- `packing`: explicitly reclaimed rectangles in existing **8 bpp** TIMs, measured
  in TIM pixel coordinates. Areas cannot overlap or cross texture pages. The tool
  adds one transparent pixel around every chunk. `hide_instances` identifies the
  old instances whose space is being reclaimed; a preserved sprite overlapping an
  area is an error. Keep fire/other animations and their CLUTs outside these areas.
  TIM number, dimensions and upload addresses are retained. No new VRAM is allocated.

## Outputs and palette handling

`NAME.png` is full-screen RGBA for each object; `masks.npz` records its binary alpha.
The contact sheet `review-3x.png` shows the complete art with cyan contours and each
quantized cut on a checkerboard (raw art in review-only mode), at exactly 3x nearest-neighbour scale. `tiles.json` records
per-object tile suggestions and current collision values. `provenance.json` pins
art, prompts and source MAP and records SAM scores and palette aliases.

Packing uses the **finished TFS's indices**, which are already quantized to the
screen palette. It avoids a second, drifting quantization. An opaque masked pixel
whose palette colour would be transparent is remapped to an identical nonzero
alias, or a palette slot unused by both the background and preserved animations holding
`0x8000` for black. Aliases are matched
across **all** time-of-day palettes. Index 0 remains transparent outside the mask.
Legitimate black inside an object is retained. Exhausting unused colours fails;
reserve a private CLUT in the map recipe rather than silently choosing a near-black.
Masks on absent donor background tiles also fail instead of producing black squares.

`candidate.MAP`, `candidate.TFS`, `sprite-N.tim` and `placements.json` are review
outputs. MAP/TFS include the player's data; never commit or distribute them. The
candidate MAP retains collision and adds sprite definitions/instances, respecting
180 definitions / 188 instances. After review, adapt the screen recipe to consume
our RGBA/masks/spec and pack against the player's files at build time. Preserve
TIM counts and run the checks again on the actual recipe output. Do not paste an
opaque rectangle of background around a cut.

```sh
build/sam-venv/bin/python tools/maps/cutout.py check SPEC --map SCREEN.MAP --out DIR
build/sam-venv/bin/python tools/maps/tilegrid.py SCREEN.MAP ART.png build/grid.png
build/sam-venv/bin/python tools/maps/zonesimg.py SCREEN.MAP ART.png build/zones.png
build/sam-venv/bin/python tools/maps/reach.py SCREEN.MAP --check
```

`check` uses `DIR/candidate.MAP` when present, otherwise `--map`. It fails on empty
or rectangular silhouettes, masks filling a frame edge, alpha disagreement,
nontransparent pixels outside a packed mask, transparent palette colours inside
one, undeclared walkable feet under a silhouette, behind declarations in front of the
depth anchor, declared blocked tiles still
walkable, blocked/floating/bouncing arrivals and disconnected arrivals. Rectangular
legitimate props can require splitting prompts; no automatic check establishes
that an outline follows the correct object. Inspect the sheet and walking clips.
`behind` is a reviewed exception, not permission to leave an object's base walkable.

`reach.py` ports the engine's directional radius checks on a 10-unit lattice
(radius 100, ahead 100, sideways 50). It is an approximation, without dynamic
entities or step scripts; one-tile corridors and mutually disconnected arrivals
are caught. Its arrival check keeps **one** reference component. A wall-adjacent
spawn may walk out even when body clearance prevents walking back to its exact
center; its own flood must join that component. Disconnected rooms still fail.
`zonesimg.py`
shows the union of actual arrival floods, exits blue and arrivals white at 2x;
run the arrival check too so unioning does not conceal separate islands.

Use `--review-only` to emit masks, RGBA and review sheets without packing or writing
MAP/TFS. It still needs `--map` for geometry and tile suggestions. `--masks NPZ`
reuses previously generated, reviewed masks without Torch; provenance labels this
as cached. Generate into a new or empty output directory to prevent stale files.

## Engine Room regression example

The full-resolution example art must be supplied locally; it is not bundled with
these tools. See [the example requirements](examples/README.md).
Build the current map recipe first (from an extracted player disc):

```sh
python3 story/mods/what-the-island-forgot/maps/engine-room.py build/engine-original
build/sam-venv/bin/python tools/maps/cutout.py generate tools/maps/examples/engine-room.json \
  --art story/mods/what-the-island-forgot/art/full/engine-room-2304x1856.png \
  --map build/engine-original/ENGN01.MAP --tfs build/engine-original/ENGN01.TFS \
  --out build/engine-review
build/sam-venv/bin/python tools/maps/cutout.py check tools/maps/examples/engine-room.json \
  --map build/engine-original/ENGN01.MAP --out build/engine-review
```

This spec preserves the fire and regenerates the two currently visible static
foreground objects. Its tile lists are empty because these two established silhouettes need no
collision exceptions on the current Engine Room. The floor exclusion and cleanup
reproduce the committed silhouettes. Run the checker after any prompt or layout
change. See `examples/README.md` for the measured comparison.

## Shared geometry API

`tools/maps/reach.py` is the collision and reachability authority for map recipes
and developer walking tools. `reach(map)` seeds only used, free arrivals;
`from_spawn_coordinates(map)` also retains nonzero unused warp coordinates and
blocked starts, preserving the walking and recipe behavior. Both use the same
directional checks and C division at negative tile boundaries.

`check_arrivals(map)` returns diagnostics for bounds, height, bouncing and
connectivity. `check_recipe_arrivals(map, name)` preserves the map recipes'
existing blocked/bouncing checks and command failure messages. Changing a
recipe to the stronger check is a separate content-validation decision.
