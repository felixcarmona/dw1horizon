# Translated tournament banners

`delta/<language>/` contains our RGB edits for all eight languages. The localization
step adds each delta modulo 256 to the player's banner pixels before quantization.
No full player-disc banner is a committed input.

Full authoring images live locally under ignored `build/localized-src/tournament/`.
After changing them, regenerate the deltas with
`python3 tools/localize/build.py --make-deltas` and review the resulting textures.
See [localization tools](../../../tools/localize/README.md) for input overrides.
Historical prompt helpers are authoring aids, not release build steps.
