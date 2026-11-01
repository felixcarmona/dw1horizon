# Localized textures and signs

The derive builder uses these tools to translate text baked into the player's
textures. All eight languages share the same build path.

- `build.py` builds menu textures and tournament banners from the player's disc.
  Banner art is reconstructed by adding the committed RGB delta modulo 256 before
  quantization. Deltas live in `content/localized/tournament/delta/<language>/`.
- `signs.py` pastes RGBA sign cutouts over the player's map backgrounds. Only the
  changed pixels are committed in `content/localized/signs/delta/`; its index
  records each crop's size and placement.
  Alternate sprite messages in `SPRITE_JOBS` use the same crop and delta format,
  but target only their specified frames, including initially hidden instances.
  The Ogre Tunnel edit fills transparent holes to cover the normal name beneath
  it; Japanese keeps the original sprite. Full edits use the job name
  (`mayo11_ogre.png`) under `build/localized-src/signs/<language>/`.
- `fromjp.py` rebuilds the English menu labels and sign sprites from a Japanese
  base disc. Japanese sign cutouts are in the `fromjp` cutout family.
- `cutout.py` loads and saves sign cutouts. `sized.py` supports authoring images.
- `textures/` holds authored pixel fonts and layout recipes. `mediancut.py` in
  the parent tools directory provides deterministic quantization.

The player build requires neither Pillow nor private localized artwork. Full
sign and banner authoring images remain untracked in `build/localized-src/`.
After editing them, regenerate the published products with
`python3 tools/localize/signs.py --make-cutouts` and
`python3 tools/localize/build.py --make-deltas`. These authoring commands need
the image tooling used by the checked-out scripts and an extraction of the relevant player disc. Use `--src` and
`--extracted` to select alternate input directories.

See [building from source](../../docs/building.md) for source discs and the
model replay setup.

`check.py` audits composed rows and localized layout; `systemw.py` packs raster labels using source-specific crop metadata.
