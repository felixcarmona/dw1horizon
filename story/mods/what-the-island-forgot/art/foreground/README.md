# Foreground cut-outs

RGBA pieces cut from this mod's own generated backgrounds, without repainting.
RGB comes from the corresponding finished art; alpha selects the silhouettes
that cover characters. No original-disc textures are stored here. The complete
backgrounds remain in the mod's art directories.

Six reviewed ranges use SAM ViT-H masks from full-resolution generated art:

| Screens | Pieces and placement records | Build helper | Authoring tool |
| --- | --- | --- | --- |
| 300–311 | 19 pieces in `art/foreground-depth-a/`; [manifests](../../maps/foreground-depth-a/README.md) | `maps/foreground_depth_a.py` | `maps/author/sam_foreground_depth_a.py` |
| 312–322 | 26 pieces here; [manifests](../../maps/foreground/README.md) | `maps/foreground_depth_a2.py` | `maps/author/segment-depth-a2.py` |
| 323–334 | 36 pieces here; [manifests](../../maps/foreground/README.md) | `maps/foreground_depth_b.py` | `maps/author/foreground-depth-b.py` |
| 335–345 | 33 pieces here; [manifests](../../maps/foreground/README.md) | `maps/foreground.py` | `maps/author/sam-foreground.py` |
| 346–357 | 51 pieces in `art/foreground-c/`; [manifests](../../maps/foreground-c/README.md) | `maps/foreground_c.py` | `maps/author/foreground-c.py` |
| 358–368 | 51 pieces here; [manifests](../../maps/district-foreground/README.md) | `maps/district_foreground.py` | `maps/author/district-sam.py` |

The manifests record source hashes or source/crop transforms, object boxes,
positive and negative points, selected scores and case-specific cleanup. Compound
objects can combine separately segmented parts. Real gaps between legs, bars,
branches and rails stay transparent. Each range's README describes its pieces,
collision review and reproduction/check commands.

The builders copy the already quantized background indices into sprite TIMs,
so foreground colours match the background through day, evening and night.
Index zero stays transparent. Opaque black uses an exact nonzero alias or, for
range 323–334 where needed, black-only fragments using a donor palette block.
Background colours and retained animations are preserved. Existing donor texture
pages are reused except for the declared allocations on screens 312/313
(77,824 image bytes per state) and 368 (one 80×64 8-bit TIM). All 216 pieces
fit the original 2 MB console budget.

Image placement is independent of depth: ground contacts, narrow strips and
surface-height bands sort each object at its visible surface. Packing respects
the engine's texture-page boundaries and fixed sprite/instance limits. Collision
changes are recorded with their reasons in the range's manifests or screen data.

Authoring needs the optional SAM dependencies and checkpoint described by each
tool. For example, from the mod directory:

```sh
python maps/author/foreground-depth-b.py --checkpoint /path/to/sam_vit_h_4b8939.pth
```

Normal game builds use the checked-in RGBA pieces and require no SAM installation
or checkpoint.
