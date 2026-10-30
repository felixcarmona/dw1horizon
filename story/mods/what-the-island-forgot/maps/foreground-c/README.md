# Foreground depth: screens 346–357

The PNG alpha masks come from SAM ViT-H on each screen's full-resolution generated
art, using the Engine Room workflow: object boxes, positive points on the material,
negative points on surrounding floor, best-score masks, area downsampling, and
speck removal. Narrow grille parts additionally use the full-resolution colors
and recorded foreground strokes to clean their edges with GrabCut; fixed RNG
seeds make that refinement reproducible. The JSON stores each prompt, source crop and source SHA-1. Cut-out
RGB is copied unchanged from the finished art; no original disc pixels are stored.

The saved alpha is authoritative. Check its digest, binary coverage and source RGB:

    .venv/bin/python story/mods/what-the-island-forgot/maps/author/foreground-c.py --check

Regeneration requires the authoring environment, the ViT-H checkpoint and locally
supplied full-resolution source art. These are not player-build inputs. Follow
[the map authoring guide](../../../../../docs/mods/new-maps.md) for setup and review:

    python story/mods/what-the-island-forgot/maps/author/foreground-c.py --segment \
      --checkpoint PATH/sam_vit_h_4b8939.pth --source-root PATH/new-maps

The model loads once for the entire range, with three CPU threads. The Stone Yard's
source is the generated authoring reference already stored in this repository.
Use `--screen ID` to regenerate one screen. Review the resulting silhouettes and
walking footage; a high model score alone is not evidence that a mask is correct.

`maps/foreground_c.py` packs the masks into scrubbed donor TIMs at build time,
using exact finished background indices. Index zero remains transparent; opaque
black uses an unused palette entry. Palette changes affect no used background
color and preserve all times of day. Texture and sprite-table overflow fail the build.

The seven-by-five mine donors have five missing background tiles. Their own art is
quantized to the same palette and placed in existing sprite texture space at the
engine's farthest background draw order. This fills the inherited black rectangles
without growing the TFS beyond the original PlayStation's load buffer. Foreground
pixels in those corners use the same restored indices. No extra TIM allocation,
VRAM region, or palette row is introduced.

Disconnected High Gallery (350) stones retain their SAM components but use their
own ground positions, so a stone farther back cannot cover a character in front
of it. Its four leaning and fallen timber braces have their own SAM silhouettes
and ground positions, separate from the stone piles.

Collision changes retain an explicit previous value and per-tile reason. The
SAM review also opens floor behind the Workshop (346) stack, the Great Chamber (348) timber post
and the Rubbish Gallery (352) pile; their occupied ground bases stay solid. Object
bases stay solid; floor behind raised silhouettes is accessible. The Bridge has one
playable deck and a blocked lower railway. The Stair's solid rock separates its
switchbacks. The Stone Yard door leaf has its own occupied footprint.

Decode the packed atlas and compare every foreground and restored background pixel,
including transparent texels, across all time-of-day palettes:

    .venv/bin/python story/mods/what-the-island-forgot/maps/author/foreground-c.py \
      --check --built build/everything-maps/screens
