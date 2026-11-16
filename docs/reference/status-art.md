# Status profile labels and the virus icon

The triangle-menu labels live in `FI_INFO.TIM`, mirrored in `ETCTIM.BIN`
entry 4. The profile's NAME/DIGI/AGE/WEIGHT artwork instead lives in
`SYSTEM_W.TIM`, mirrored in entry 8, using CLUT 9 at VRAM (96,497).
`tools/localize/textures/systemw/` supplies the condensed bitmap alphabets;
`tools/localize/labels.py` supplies the other translated labels.

The care-numbers changes (PR #23, followed by the permanent-panel changes)
rendered `CHART_STR_MISTAKES` with `drawStringMode` into the dynamic text page,
then drew it using colour 17 over a cyan rectangle. That explains its different
case, letter height and outline. The chart still uses that runtime string.
`MAIN_D_801238B0` is a different packed text row: its Spanish spelling is
`Disc / Vida / Vir. / HP / MP / noche`. Its existing crops and wording stay
unchanged; neither string should be edited to repair a texture or sprite.

`tools/localize/status_art.py` now derives the mistakes tag from each language's
`text/*/names.json`, uppercases Latin wording, and draws the eight-row TAG
alphabet with its complete cyan outline. A four-pixel M keeps MISTAKES readable
without scaling its other letters. Japanese uses the authored/OFL Japanese
bitmap subset; Chinese uses the existing small UI glyph tooling. All nine
tags occupy **36×10** pixels, right-aligned within the crop, with three pixels
before the number inset. The atlas slot **(108,72)** is empty in the source
texture and supersedes only the unused RAPIDEZ alternative. It avoids the live
SPECIAL crop, relocated technique headers, Chinese menu labels and care caps.
Both single-language and multilingual derive paths stamp the loose and stacked
textures after the existing label passes. No palette or upload grows.

The garbled virus picture was two overlapping table entries. Element 10 sampled
the **9×11 gauge cap at (240,37)**; element 20 sampled the **9×11 care sprite
at (44,116)**. They were positioned at x=-137 and x=-138, and `statsCareLayout`
put both at y=84. Their CLUT 10 therefore displayed the brown cap and blue
details together. This was overlapping sprite/UV selection, not a corrupted
CLUT. Element 10 now draws the profile tag using CLUT 9. Element 20 alone draws
the clean **11×11** filth icon authored in
`content/localized/status/virus.txt`, with a dark outline and native ochre
shading. The virus gauge represents accumulated filth. This follows the
native-colour, whole-silhouette approach of `tools/field_hud_art.py` and the
outlined hand-drawn icon guidance in `engine-patches.md`.

The existing sprite and CLUT tables retain their sizes (168 and 21 bytes).
They are resident data restored by the language banks; **MENU_REL is unchanged**.
In matched focused English/Spanish builds with font B, the endpoint moves from
`0x801CAA74` to `0x801CA9C0`. Aligned allocator heap grows **201,856 → 202,032 B**
(+176 B). Both heap checks pass without an override. MENU_REL remains **53,124 B**.
These are focused build measurements, not absolute heap figures for an
everything-release build with all nine executable banks and added files.

Validation artifacts are under `build/status-proof/`, with native builds in
`build/status-{en,es}-exe/`. Both panels were captured through normal rendering
after loading a corpus card on original 2 MB PCSX-Redux. Every translated
texture recipe was also built; the tag and icon crops match between the loose
SYSTEM_W and stacked ETCTIM outputs for all eight translations. The supplied
Spanish before image, enlarged live after images and nine-language contact
sheet were sent with `mg-send` as session `2026-11-16-102237-upload-5X4xjd`.

Recheck the authored raster pins and crop tables with:

```sh
python3 -m tools.localize.status_art
python3 -m tools.localize.systemw build/status-decomp
python3 -m unittest tools.test_status_art tools.test_systemw tools.test_field_hud_art \
  tools.test_care_badge tools.test_care_bubble_art tools.test_localize_ui tools.test_patch_series
python3 tools/heapcheck.py build/status-en-exe/SLUS_010.32.elf.map
python3 tools/heapcheck.py build/status-es-exe/SLUS_010.32.elf.map
python3 tools/dev/playtest/status_art.py --disc build/status-es.cue \
  --exe build/status-es-exe/SLUS_010.32 --language es --out build/status-proof-replay
```

Use the corresponding English disc/executable and `--language en` to repeat
the other capture. After intentional visual changes, regenerate authored-only
hashes with `python3 -m tools.localize.status_art --write-pins` and C crops with
`python3 -m tools.localize.systemw ENGINE_TREE --write`. The committed pin file
contains only hashes of our index rasters; no player's texture, palette, disc
or screenshot is committed. All 465 engine patches were replayed in order
without commits and produced exactly the source used for the test builds.
