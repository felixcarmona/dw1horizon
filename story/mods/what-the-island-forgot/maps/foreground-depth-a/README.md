# Foreground review: screens 300–311

These manifests record the depth and collision review of this range. The RGBA files in
`art/foreground-depth-a` are SAM ViT-H masks of this mod's own full-resolution generated art:
their RGB comes unchanged from the finished screen image. Each piece's `sam` record stores its
source/crop transform, object box, positive and negative points, and selected score. The
author tool `maps/author/sam_foreground_depth_a.py` reproduces review drafts with one model
load and three CPU threads. SAM cleanup is recorded per case: component filtering, solid-object pinhole filling. Inspect silhouettes at native size and 3x before installing them.

`foreground_depth_a.apply` copies the corresponding **already quantized background colours**
into unused donor sprite texture space. Transparent mask pixels remain index 0; true black
inside a mask uses a nonzero 0x8000 alias valid in every time-of-day CLUT. If none exists,
the helper reserves a background-unused palette entry, also unused by active background-CLUT
sprites. No displayed background pixel changes. It preserves donor sprite palettes,
active animations, TIM counts and upload rectangles. The cot and sign have different ground contacts and
therefore use separate pieces. `depth_planes` divides each mask into short surface bands.
For each column, `depth: null` uses its lowest opaque pixel as the ground contact; explicit
depths describe a prop's ground contact. Each band's screen ray intersects the vertical plane
through that contact, giving it a world-space sorting anchor at the visible surface.
This prevents a tall actor's head or torso piercing the upper half of a prop while allowing
the actor to walk visibly in front of it. The bands preserve the exact union of mask pixels. No engine patch,
new texture page or dynamically allocated object array is required.

| Screen | Review |
| --- | --- |
| 300 | Existing machinery, crates/barrels and fire layers already handle the reachable edges. Back-wall tent/gear have no rear floor. Preserve them. |
| 301 | Camp canvas, crates, cot and sign get separate depth masks; the sign stem is solid. Cave mouths and both exits remain open. |
| 302 | The player's MGEN17 background: a single connected elevated walkway, with void below and no lower route. Preserve the original art and collision; distribute no disc texture. |
| 303 | Three sandstone near faces follow reachable switchback approaches; the lowest shelf has no reachable rear overlap and remains background. Face cells are solid, and the turns remain the only connections between ledges. Preserve the existing entry-step piece. |
| 304 | Mask the memorial's body; its plinth remains solid. Visible floor behind the upper body is free, subject to the tamer's body width. |
| 305 | The protruding eastern fern fronds cover the trail edge. Gaps between fronds stay transparent. Other foliage backs onto blocked walls. |
| 306 | Segment individual bones with transparent floor between them, the raised flagpole and the grave's cairn/upright. Existing solid footprints and three travel directions remain. |
| 307 | No overhead arch crosses the corridor. Columns and wall faces are outside the floor; preserve its full width. |
| 308 | The book/lectern, near doorway jamb and two separately prompted book piles get masks. Free the floor behind the lectern shaft; retain its solid pedestal. The lintel is above the reachable actor envelope; the far stack and candles have no rear floor. |
| 309 | Ship hull, mast and thin bowsprit use the existing solid wreck footprint; the raised bowsprit has its own depth contact. The sloping hull sorts in narrow strips; the beach remains walkable around it. |
| 310 | Ice wall and side faces bound the floor; no path behind/under them. No added foreground. |
| 311 | Same floor as 310, bounded by the water curtain. No added foreground. |

Run `maps/author/check_foreground_depth_a.py REFERENCE_DIR REBUILT_DIR` from the mod root
(or use its repository-relative path from the repository root) to check source RGB, unchanged
background colours/warps/active frames, explicit collision edits, exact alpha coverage and
opaque colours in every time-of-day CLUT, round trips and the engine's fixed sprite/instance
limits. It rejects opaque pixels outside the mask and transparent pixels inside it.
Neither directory is shipped.
