# Making a new screen correctly

Before accepting a screen:

- [ ] Approve the area's concept, useful buildings and connected route first.
- [ ] Match an original camera and a 22–27 pixel tamer; leave generous floor.
- [ ] Generate one carefully specified image; keep its full-resolution original and exact crop.
- [ ] Trace the finished floor, review every tile and run the body-box reach check.
- [ ] Cut every required foreground silhouette with full-resolution SAM ViT-H.
- [ ] Review masks and palette-safe TIMs at 3x; block object bodies, allow correct hidden floor.
- [ ] Check every exit, arrival, target, ground height and wild encounter distance.
- [ ] Preserve donor TIM counts; choose a MAPHEAD section matching the entity slots.
- [ ] Pass heap/VRAM checks and walk every arrival and foreground object on a 2 MB PlayStation configuration.
- [ ] Review reachable zones immediately after collision edits; review walking clips afterwards.
- [ ] Commit only our art, prompts, data and recipes; retain build and checksum evidence.

This is the authoring recipe. [Maps](maps.md) documents the binary formats and
[tools/maps](../../tools/maps/README.md) defines the cut-out JSON and commands.
The field draws characters over a pre-rendered background. Foreground sprites,
with a depth anchor at an object's ground contact, make characters pass behind
objects correctly. A beautiful background with a character walking over a door,
bridge or canopy is an unfinished map.

## Concept and source data

Design the area as a connected place with a purpose, exits and story roles before
making its screens. For a new district, present two or three complete concept
views and choose a concept first, then derive screens from that view.
Generate those concepts individually, assessing each before the next request.
Use File City's visual language: useful or convincingly useful buildings, terrain
between them, at most one specific house; avoid a grid of interchangeable houses.
A whole district must have the scope of the original city, with its square, lower
town and roughly ten interiors. Every building shown as enterable needs an interior.
Use clean TWNA13 and TWNB24 references when designing a city extension.

Work in a separate branch and worktree, and use a private decomp worktree for
builds. Run only one heavy build at a time and stop every emulator you start.

A map recipe reads the donor from the player's extracted disc **at build time**.
Use `maps/mapbase.py`'s `base_map`: it clears sprite pixels, hides donor instances,
clears exits and Digimon, and resets warp heights. Do not distribute donor MAP,
TFS, background textures or full-background retouches. For an edit to an original,
commit only our new RGBA element and paste it into the player's TFS in the recipe.
For an entirely new screen, keep our generated background and authored geometry.
Foreground pieces must contain only that screen's own pixels.

## Choose camera and scale before requesting art

Choose a comparable original and read its camera and TIM allocation:

```sh
python3 tools/dwmap.py describe extracted/MAP/MAP4/OGRE03.MAP
python3 tools/dwmap.py export extracted/MAP/MAP4/OGRE03.MAP build/donor-review
```

Check `docs/data/map_files.csv` for the donor's `n8`/`n4`. Copy the values into the
screen declaration's `tims8`/`tims4`; never infer them from another map's describe
output. The engine reads those counts from MAP_ENTRIES, not from the MAP file.
A wrong count can produce an absent HUD, coordinates around −32640 and dead warps.

Match the tamer's apparent size to an original: normally 22–27 pixels at screen
centre, eye distance about 6000–8000 world units. Start near 6500, then compare;
4000 makes the character too large and the screen too quick to cross. Camera values
in MAP setup are half the eye/target world coordinates. Pitch and projection matter
too: use the complete camera, not just the downward angle.

Use the existing description-driven authoring system when it fits. Each screen has
one JSON under `story/mods/what-the-island-forgot/maps/author/galleries/` or
`district/`; `gallery.py` makes the guide, layout and screen declaration. For example:

```sh
MAPS=story/mods/what-the-island-forgot/maps
python3 "$MAPS/author/gallery.py" guide the-workshop build/workshop-guide.png
# After accepting art and tracing floor_px / blocked_px:
python3 "$MAPS/author/gallery.py" layout the-workshop build/workshop-layout
python3 "$MAPS/author/gallery.py" screen the-workshop
# For district descriptions, prefix these commands with GALLERY_SET=district.
```

These commands write the selected screen's authoring data; copy a description to a
new unique screen before adapting it. Use final-camera guide sticks of 200 world
units and specify prop sizes against those sticks. Compare usable floor area with
the original (roughly a thousand free tiles is a useful comparison, not a quota).
Use soft grey guide regions and black exits; sharp outlines, hatching and bright
coloured regions can leak into the generated art.

## Generate the art

Write the complete prompt first. Specify camera, scale, floor, exits, intended
foreground elements, lighting, references and crop. Each generation costs money:
generate one image, assess it, then decide on a precise edit or another generation.
Use the configured art-generation service and its documented credentials; never
copy API keys into scripts, prompts or reports.

Every prompt must require:

- Even, soft light from above. No light beams, god rays, floor haze, fog, bloom or
  bright floor glare: characters cannot be shaded into these effects.
- A static scene: no smoke, steam, pouring/falling water, jets, sparks or leaping
  flames baked into the background. Still water is fine; animation needs sprites.
- No text, letters, numbers, signs or logos. Generated lettering is unreliable.
- Enterable buildings at least as substantial as TWNA13's ITEM BANK, with a large,
  wide-open dark doorway. Closed doors and tiny kiosk-like interiors are rejected.
- Clear, generous ground between objects and walls, including earth, gravel and
  grass. One traversable level; connect any levels only through visible ramps or stairs.
- No overhead wires or cables, cranes, awnings, roofs or branches over walkable
  ground in the initial design. Put buildings against blocked back edges. Ground
  cables are acceptable. Where the design truly needs an overlap, budget and make
  its foreground pieces before accepting the screen.

The guide is not a diagram: the whole output must be the rendered scene. Explicitly
request a high camera looking down for a horizontal gallery. Require rock or scenery
to every image edge, without black diorama corners or blank grey floor. For a wide
concept spanning two screens, request one continuous scene without a seam.

Fix art defects by asking the generator to edit **that image alone**, with a precise
instruction, or regenerate. Do not clone floor, paste props, paint shadows or repair
the scene with homemade composites. Do not attach older attempts or marked-up
copies: their defects and marks can return. A targeted edit may use an enlarged crop
centred on the defect, describing its size relative to that crop. Palette conversion,
downscaling and silhouette extraction are pipeline operations, not scene repainting.

Keep the full-resolution image, exact `[left,top,right,bottom]` crop, final size and
prompt together. An overlay placed on existing walkable floor must match the drawn
strip exactly; compare its outline to the walkable projection before accepting it.
Do not rely on percentage coordinates in a prompt to place a narrow bridge.

## Trace generous floor and inspect every tile

Trace `floor_px` on the **finished art**. The generator may shift or widen the guide's
paths. Include all visible traversable ground between walls; do not equate a grass
mask with floor. SAM floor masks can help, but union them with a generous traced
floor and subtract actual walls and object bodies. Do not type a band from a guide's
centreline across rock lips or between switchbacks.

Project the raw grid over the art and inspect the entire screen, tile by tile:

```sh
PY=build/sam-venv/bin/python
$PY tools/maps/tilegrid.py build/new/SCREEN.MAP path/to/our-art.png build/grid.png
# Optional crop in final-art pixels, still rendered at 4x:
$PY tools/maps/tilegrid.py build/new/SCREEN.MAP path/to/our-art.png build/grid-detail.png 400 240 640 512
$PY tools/maps/reach.py build/new/SCREEN.MAP --check
$PY tools/maps/zonesimg.py build/new/SCREEN.MAP path/to/our-art.png build/zones.png
```

Record a reason for every blocked tile. Never block a whole rectangle of empty floor
or block a polygon whenever any corner touches it. Small bottles, bags and cans have
bodies, not just base points: block those bodies. A tall object left in the background
cannot have walkable ground behind it, because the character would draw over it.
Prefer a correct foreground cut-out so the useful floor can stay open.

The tamer radius is 100 world units. Movement checks 100 ahead and 50 either side;
a one-tile-wide corridor that looks green can be impassable. `reach.py` simulates
these directional checks on a 10-unit lattice. Its checker floods from one arrival
and requires the others to be connected; seeding every arrival would conceal islands.
Dynamic actors and scripted transitions still need emulator testing. If separate
levels intentionally have independent entrances, review their connectivity separately
in the recipe; do not claim the generic single-component check passed.

After **every** collision change, generate and review the zones image before
building or recording.
Green must mean reachable floor, blue exits and white arrivals. Review unexplained
grey ground yourself. Walking videos come afterwards.

## Make foreground cut-outs with full-resolution SAM

Inventory every object that should cover a character: bridge underside, arch,
door frame and open leaf, canopy, pillar, machinery, tall rock, fence, railing,
tree trunk, roof edge and cave-mouth upper rim. Decide which floor lies behind it,
which tiles its physical body occupies, and where its depth anchor touches ground.
A single depth point cannot describe several independent levels: split the object
into pieces with appropriate anchors where needed.

Install the tool once (no Pillow or torchvision; see [developer image tools](../developing.md)):

```sh
tools/maps/setup-sam.sh
```

Create a per-screen JSON using the [input contract](../../tools/maps/README.md).
Prompt each object with a bounding box, positive points on its material and negative
points on the surrounding floor/openings. SAM ViT-H must see the **full-resolution**
art; transform prompts through the exact background crop. Do not feed SAM the final
small texture or substitute polygons, boxes or approximate geometric masks.

Build the screen MAP and finished TFS with its normal recipe, then run:

```sh
PY=build/sam-venv/bin/python
$PY tools/maps/cutout.py generate path/to/screen-cutouts.json \
  --art path/to/full-resolution.png --map build/new/SCREEN.MAP \
  --tfs build/new/SCREEN.TFS --out build/screen-cutout-review
$PY tools/maps/cutout.py check path/to/screen-cutouts.json \
  --map build/new/SCREEN.MAP --out build/screen-cutout-review
```

The output contains per-object RGBA, binary masks, TIM files, candidate MAP/TFS,
placement metadata, tile suggestions and a 3x outline/contact sheet. Nothing is
installed automatically. Review the sheet at its actual 3x scale, looking for thin
posts, ropes, rail and lantern frames, holes, floor, shadows, halos, detached specks
and frame-edge rectangles. Fix bad objects individually with tighter boxes, extra
positive/negative points, exclusions or separate prompts; inspect again. A high SAM
confidence is not acceptance. Cleanup thresholds must preserve real thin parts and
openings. Floor subtraction, relative component removal and hole filling are
optional per-object settings; hole filling is appropriate only for genuinely solid
objects. The Engine Room example records its original cleanup explicitly.

TIM packing reuses declared sprite space and preserves the donor's TIM counts,
addresses and sizes. Keep animations outside reclaimed space. Pieces are split into
small rectangles with transparent guards and share an object's depth anchor.
The engine uses that 3D anchor for ordering, not object list order. Do not assign
background depth (`y=10000`) to an object that should hide the tamer.

Quantize against the finished background palette: use its exact indices for masked
pixels. Background index 0 can be black; GPU colour word 0 is transparent in sprites.
The tool preserves opaque black with a nonzero alias across every time-of-day
palette and leaves zero outside the mask. Never change alpha into opaque black
rectangles or turn dark object pixels into holes. An exhausted palette, absent donor
tile or full sprite page must fail, then be resolved deliberately in the recipe.

Review `tiles.json` and record `tiles.behind` and `tiles.blocked` in the spec. Behind
means allowed floor with correct occlusion. On/inside an object's body means blocked.
Feet under a foreground silhouette require explicit review; a `behind` declaration
must correspond to the actual depth anchor. Foreground sprites should not hide the
character's feet when he stands in front. A bridge's upper and lower surfaces must
not connect except at real ramps. Apply approved collision decisions in the screen's
recipe/data, rebuild and rerun checks. Do not rubber-stamp every diagnostic as behind.

Commit only our masks/RGBA/spec and reproducible recipe changes. Run packing against
the player's MAP/TFS at build; generated candidates contain donor data and belong
only under `build/`. See the Engine Room example in `tools/maps/examples/` for a
measured comparison with the established pieces, and the retired New Street example
for an independent open-gate review without changing an active map.

## Exits, arrivals and encounters

A warp entry contains the spawn **when arriving** through that exit, plus the target
map/exit for departure. Set every target before the final layout run: target −1 is
unused and skipped by arrival checks; leaving a live doorway at −1 can fade to black.
Check reciprocal links and arrivals in both directions, including dynamic story exits.

Place edge exits by world/tile rows at the actual visible edge. Perspective can put
five rows in a small pixel box; avoid broad pixel bands at foreshortened far ends.
The gallery author starts with the last 400 world units for an edge exit, then
`mapbase.trim_exit` removes the inner 200 units (two tiles). Pixel mouths use the
same trim on the bounding edge facing the arrival; a diagonal facing point must
not leave the closest trigger unchanged. Already shallow mouths retain a
100-unit span between tile centers, so an exit still has a usable strip. Arrivals
stay 700 units inward. `Cam.arrival_rotation` uses the engine's heading convention
(0 = −Z, 1024 = −X); use it for warp arrivals facing into the map. The older
`Cam.rotation` describes the opposite vector and is retained for existing recipes.
For a trigger-only correction, trim the committed map data rather than rebuilding
its floor from an older authoring description; verify that every blocked bit is
unchanged. Keep arrivals at least two tiles clear of their own exit tiles and avoid a
one-step re-trigger. An interior mouth uses `box_px`, `spawn_px` and `face_px` traced
on the actual mouth. Rerun layout after changing targets.

Every new ground-level warp must have **y=0**. Donors can retain y=2600: walking may
look normal but battles then place the partner above the enemy and never finish.
For a hanging battle, inspect the fighters' positions and heights first.

Choose `maphead: {"like": 240}` for an empty Digimon table, or a section whose
`load_digimon`/`set_digimon` calls exactly match the slots you provide. Section 0 loads
Native Forest slots and can spawn garbage entities, with moving black shadow bars,
when used on an empty map. Set appropriate music explicitly if the copied section's
BGM is wrong. Set the sound bank and screen flags to match actual placed entities.

Place every wild Digimon farther from **every** used arrival than its tracking range
plus 300 world units. Default tracking range 1000 means strictly more than 1300;
1350 provides a margin. A fade-in encounter can start with no enemy and trap the
player in an uncloseable FINISH screen. Rerun the existing spawn audit after every
exit/target/encounter change:

```sh
python3 tools/dws.py check-spawns story/mods/what-the-island-forgot/early-game.py \
  --screen-content build/map-work-maps/screens --margin 300
```

The audit is also part of the normal map build. Inspect its diagnostics; move the
spawn onto reachable floor or deliberately lower the chase range. Test an actual
battle to completion, then another one on the same visit.

## Integrate, build, measure and walk

Register unique file/screen ids, the recipe and story sources in
`tools/derive/recipes/everything.json`, using the existing authoring conventions.
The recipe must reproduce the new screen from our inputs and the player's donor.
Read the actual build options in `tools/build-full.sh`. Keep the decomp tree private;
start from the repository's pinned submodule commit and apply this branch's patch
series. Do not prepare or reset a shared decomp tree.

Before changing shipped content, build untouched main in an isolated worktree and
save per-file SHA-1s plus the image SHA-1. Use the same language set, version stamp,
recipe and private toolchain for the changed build. A documentation/tool-only change
must preserve every disc byte. A map-content change must explain every changed file;
keep unrelated disc files identical.

A typical everything build, after preparing the private tree:

```sh
SPECIES=all SPECIES_PROVIDER=imports TEXT=ours LANGS=en,es,pt-br,fr,de,it,ja,ca \
  DERIVE_JOBS=2 W="$PWD/build/decomp-map-work" NAME=map-work \
  MOD_VERSION=map-review story/mods/what-the-island-forgot/build.sh
python3 tools/heapcheck.py build/decomp-map-work/build/us/psx/gcc/SLUS_010.32.elf.map
python3 tools/dws.py check-heap build/map-work/with-new-screens/MAPHEAD.SCN \
  --map build/decomp-map-work/build/us/psx/gcc/SLUS_010.32.elf.map \
  --archive build/map-work/DIGI.DAT --facts build/map-work/derived/exe-facts.json
# Static allocation for donor OGRE03 (48); substitute your donor's screen id.
python3 tools/membudget.py vram-map 48
tools/selftest.sh
```

The build's story heap check must pass against the actual archive/model sizes for
all affected setups, including large partners and battle transients. Read its output;
a positive generic estimate alone does not prove a new setup fits. The static VRAM command reads extracted original maps; it cannot resolve a new
screen id directly. Compare the candidate TIM dimensions, upload addresses and
CLUTs with the donor and inspect the actual new screen live. Check foreground
TIM upload rectangles, background windows, character textures and CLUTs in VRAM.
The cut-out tool does not allocate more TIM space, but extra definitions/instances
still cost RAM. Never solve a budget problem by requiring more than the original
**2 MB PlayStation RAM**. Run live memory/VRAM inspection as needed with
`python3 tools/membudget.py live --vram` against your private emulator.

Use a private emulator, display, ports, memory card and matching-disc state; stop
all of them afterwards. See [the emulator and testing documentation](../developing.md). Review at 3x, with original 2 MB RAM.
Walk through **every** used arrival in both directions, all floor corridors, behind
and in front of each piece, through open doors and around small objects. Record
short walking clips that show those crossings; static zones and screenshots cannot
prove ordering or walkability. Review day, evening and night palettes, check partner
occlusion too, and test encounter start/finish and repeat visits.

Examine every recorded clip. Reject masks with black boxes, halos,
missing thin parts or floor included; characters drawn through an object; a tamer
walking over a bridge underside/open door; blocked empty floor; isolated green
islands; wrong camera scale; immediate return warps; floating battles; or memory
that only works in an expanded emulator. Fix every observed problem on the screen. Keep the zones images from each layout
change alongside the reviewed walking clips and 3x comparisons.

Keep a review record of prompts/crops, reasons for tile decisions, arrival checks,
map/TIM counts, heap/VRAM results, emulator configuration, clips and SHA-1 differences.
Commit small, with a plain English subject explaining the change and its reason.
