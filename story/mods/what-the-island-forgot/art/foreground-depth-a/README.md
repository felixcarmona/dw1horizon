# Foreground masks for screens 300–311

These RGBA crops contain only this mod's generated background art. Their RGB pixels are
unchanged; alpha selects the foreground silhouettes, with transparent gaps between bones
and fern fronds. No original-disc texture, full MAP/TFS file or repainted pixel is included.

Files are named `SCREEN-piece.png`. The matching manifests in
[`maps/foreground-depth-a`](../../maps/foreground-depth-a/README.md) specify their native
pixel positions and ground contacts. The build copies the corresponding background palette
indices into unused donor sprite texture space, preserving the existing palettes and VRAM
upload rectangles. Keep RGB identical to the named source art when refining a mask.
