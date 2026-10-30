# District and canyon depth review

Screen 358–368 manifests for district_foreground.py. Each changed collision cell records
its old value, new value and reason. The floor and footprint polygons record the art
review; the explicit tile edits are applied to the original recipe data at build time.

Each piece names an RGBA cut-out under art/foreground/, its background-pixel placement,
and its ground-plane depth anchor. A null depth sorts each strip at its own near edge, for sloping furniture.
Strips default to 16 pixels; the nest rim and crack lip use 8 and 4 pixels. The original donor texture pages are reused. Only
screen 368 adds a small 80-by-64-pixel page; its screen entry declares that extra TIM.

The canyon retouches reserve transparency at build time. Screen 366 merges palette
entries identical in all three palettes; screen 368 uses an unused index. Background
pixels retain identical rendered colors in day, evening and night. The stone bridge retains its
original foreground and single deck, with additional cut-outs for its near parapet stones.

The masks for this range use SAM ViT-H on the full-resolution generated sources,
with a box and positive/negative points for each object. Compound props use the
union of separately prompted components, such as a table and its kettles. Each
piece's `segmentation` records the source SHA-1, coordinate transform, prompts,
selected score and cleanup. Closed-backed furniture has no artificial holes;
real gaps between stool legs and rails remain transparent. The nest rim and crack
lip follow the segmented boundary, with narrower strips for their sloping depth.
The earlier traced polygons remain only as collision-review records.

[The authoring script](../author/district-sam.py) reproduces the RGBA pieces. Run
it in an environment with torch, segment_anything, OpenCV and the project raster module, supplying
`--checkpoint`, `--sources` and `--out`. The sources argument is a JSON dictionary
mapping the recorded source basenames to local full-resolution files. The script
verifies their hashes, loads the model once, uses three CPU threads and reuses
image embeddings. SAM and its weights are not needed by the ordinary game build.

[The built-sprite checker](../author/check-district-foreground.py) takes a map
folder and `--reference` pointing to the untouched map/background files. It checks
every foreground pixel and padding pixel through every available time-of-day
palette, unchanged background colours, retained sprite definitions, animation
colours/transparency, 4-bit textures and the fixed map/instance limits. `--report`
writes the budgets as JSON.

The packer keeps the original palette's transparent words intact. Only masked
foreground pixels receive an opaque alias when their colour becomes zero in a
time-of-day palette. An unused entry, or an exact duplicate across all palettes,
provides the alias without changing background colours or original animations.

Packed strips leave a texel clear at texture-page boundaries. The engine shortens
both UV spans when either span touches that boundary; avoiding it preserves thin
rails, rims and lintels without changing the engine.

The scrap-office stove uses 8-pixel-high bands with `vertical_face` depth. Each
band sorts at its actual height above the reviewed floor base. A single floor
anchor let raised model limbs draw through the tall metal front. This changes
only sorting geometry; the SAM alpha and source RGB remain identical. The checker
projects these anchors independently to verify both band height and floor base.
