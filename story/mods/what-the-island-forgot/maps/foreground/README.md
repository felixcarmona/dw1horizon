# Foreground placement: screens 312–345

These manifests cover 26 pieces on screens 312–322, 36 on 323–334, and 33 on
335–345. The [complete range index](../../art/foreground/README.md) also describes
300–311, 346–357 and 358–368. Empty piece lists record reviewed screens that
need no additional foreground upload.

## Screens 312–322

Each JSON file describes one new screen's foreground pieces: its own-art RGBA paths, native-pixel positions, sorting anchors, and explicit collision cell changes with before/after values and reasons. A null depth follows the near edge in narrow strips. Empty piece lists record reviewed screens that need no foreground upload.

Screens 312–322 use `../foreground_depth_a2.py`. Run `../author/check-depth-a2.py SCREENS_DIR [REFERENCE_SCREENS_DIR]` to check exact day/night colors, opaque black, sprite bounds and unchanged backgrounds.

## Screens 323–334

Each JSON describes foreground pieces cut from that screen's own generated art.
The PNGs under `art/foreground/` contain only those pixels and an alpha mask;
`at` restores the crop's original position. `depth` is the object's ground-plane
anchor in background pixels, independent of the crop bounds. A diagonal wall
uses `depth_line` and narrow `strip_width` fragments so its north end does not
incorrectly cover a character standing in front of it.

`foreground_depth_b.apply` copies the already quantized background indices into
the donor's cleared sprite TIMs. It allocates no new texture pages, uses the
background CLUT (including day/night changes), makes opaque sprites, and splits
at texture-page boundaries. All fragments of a normal object share its anchor.
For raised faces, `vertical_face` solves the camera projection for the height of
each texture band (`strip_height`). Its fragments sort at the corresponding
height above `depth` or `depth_line`, instead of sorting the entire face at its
feet or applying a constant offset that can hide front walkers. Colour and black
fragments from one band share the same sort plane. A reviewed `sort_y` can
conservatively offset a band; front-side poses are checked as well. Boundary
pieces with no reachable floor in front can use a standalone offset. Pixel placement and masks
are independent of all sorting anchors. The imported TFS is unchanged.

Black background pixels need special handling: index zero is transparent over
an actor. The builder substitutes an existing opaque black palette entry when
available. Otherwise it splits those pixels into black-only fragments and
reuses a donor TIM's palette block at reserved map-sprite CLUT row 484. Coloured
pixels keep the live background palette; no texture page or TIM is added.
Both engine limits are checked: 180 definitions and 188 instances.

The silhouettes and review notes record the art review. `blocked_tiles`, where
present, records each collision tile corrected during the review and its reason;
the playable collision remains in the screen's `*-data.json` file. Every active
PNG alpha in this range was regenerated with SAM ViT-H on the full-resolution
generated art, using object boxes and positive/negative points.
The manifests record prompts, source/crop transforms, scores and cleanup;
`maps/author/foreground-depth-b.py` reproduces them. No polygon clipping or
repainting defines the silhouettes.


## Screens 335–345

Each JSON records the depth review of one screen in 335–345. An empty `pieces` list means the inspected props do not overlap a reachable character; its `review` explains why. It does not make isolated upper walkways or blocked walls into floor.

- `pieces`: own-art RGBA filename, native pixel `at`, optional pixel `depth` anchor, and SAM box/positive/negative prompts retained in `segmentation`. With no fixed anchor, each narrow strip sorts at its own lower edge. `strip_width` can reduce the default 32-pixel strips: the steep brace on 344 uses four-pixel strips so a near edge cannot cover a character standing in front of it.
- `collision`: individual `[x, z]` cells, their expected `before`, their replacement `after`, and the physical reason. A stale expected value fails the build.
- `reviewed_body_box`: the tamer's visual footprint used during the review; reachability also uses the engine's 100-unit movement radius.
- `fill_background_tiles`: fill the donor's omitted corner tiles from this screen's own art. Existing tiles remain byte-identical, and new pixels use only already-used palette colours. The complete layout stays within the native 35-tile table and uses the same streamed VRAM window.

`maps/foreground.py` applies these after importing the background. It reuses hidden sprite slots and the donor TIM allocation, reserves active frames, and checks texture/table bounds and arrivals. Sprite UVs stay short of the page boundary, where the engine otherwise shortens them by one texel. Unused background palette entries hold opaque black (`0x8000`) while index zero remains transparent in every time-of-day CLUT; existing background pixels and their colours remain unchanged. [The cut-outs](../../art/foreground/README.md) are our pixels, never disc textures. Other screens have no manifest here and retain their original recipe output.

The `segmentation_source` records the SHA-1 and crop/scale of the full-resolution generated art, the SAM ViT-H model, and cleanup. [The authoring replay](../author/sam-foreground.py) loads the model once with three CPU threads, chooses the best-scoring prompted mask, removes components smaller than twelve native pixels (or a reviewed per-piece minimum for isolated noise), and downsamples to the screen's own dimensions. Inspect its RGBA output against a contrasting background before accepting it.

The two solid upper-rock pieces additionally set `max_hole_area` to twelve pixels: this fills enclosed segmentation specks in solid stone. Open frames, railings and other real holes retain their transparency. Review taller partners too; the rock above a lintel can need its own piece even when the tamer fits entirely beneath it.
