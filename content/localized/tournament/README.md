# Translated tournament banners

`delta/<language>/` contains our RGB edits for all eight languages. The localization
step adds each delta modulo 256 to the player's banner pixels before quantization.
No full player-disc banner is a committed input.

Full authoring images live locally under ignored `build/localized-src/tournament/`.
After changing them, regenerate the deltas with
`python3 tools/localize/build.py --make-deltas` and review the resulting textures.
See [localization tools](../../../tools/localize/README.md) for input overrides.
Historical prompt helpers are authoring aids, not release build steps.

## The eighteen new cups

`new-cups/<language>/<CUP>.png` are the banners of the cups after the original's (Rookie Cup to Aqua
Cup): whole pictures, ours, 256x128 with 256 colours, colour 0 the transparent background.
`tools/cup_banners.py` packs them into `STDDAT/GRADE/NEWCUPS.BIN`. `new-cups/prompts.py` keeps the prompts they
were generated from: the English one first, with three of the translated original banners as style references,
and each language from the English one. A name that reads like the English one (Data, Vaccine) came out right
only when drawn without the English picture as a reference.
