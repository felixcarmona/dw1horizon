# Game languages

The runtime language selector supports English, Spanish, Brazilian Portuguese,
French, German, Italian, Japanese and Catalan. Text, executable strings, signs and
other translated textures switch together. A first-boot picker shows native names
and procedural flags; saved options skip it. OPTIONS can change the language later.

Our English translation is in `text/ours`; the other translations are in
`text/{es,pt-br,fr,de,it,ja,ca}`. `text/<language>.json` supplies common mod text,
and each story mod can provide its own `text/<language>.json`. Text is keyed to
script locations rather than copied into the story's code. Review records and
translation process notes are excluded from the published tree.

## Building

```sh
SPECIES=all SPECIES_PROVIDER=imports TEXT=ours LANGS=en,es,pt-br,fr,de,it,ja,ca \
  LANG_BASE=en DERIVE_JOBS=1 W=$PWD/build/decomp-int NAME=everything \
  DW_HEAP_MAP=/nonexistent story/mods/what-the-island-forgot/build.sh
```

Prepare the four player discs first; see
[building](../building.md). `LANGS` must contain English and at least one other
language, with no duplicates. The builder uses a canonical order, independent of
the order supplied. `LANG_BASE` must be among the selected languages.

The builder compiles each language with a common address layout and makes
`LANGEN.BIN`, `LANGES.BIN`, `LANGPT.BIN`, `LANGFR.BIN`, `LANGDE.BIN`, `LANGIT.BIN`,
`LANGJA.BIN` and `LANGCA.BIN`. Only selected languages are included. The original
and extended stories each have font-specific text copies. Japanese wrapping
breaks between glyphs and preserves references without inserting word spaces.

The sector table uses hashed names with a version marker and collision checks,
keeping eight languages within the original 2 MB PlayStation memory budget.
The font's compressed storage preserves glyph pixels and widths.

## Fonts and checks

The Japanese subset is generated from Fusion Pixel, with upstream notices in
`tools/font/japanese-license`; see [third-party licences](../../THIRD-PARTY.md).
`tools/font/import_japanese.py` regenerates the subset from the pinned font.

`PYTHONPATH=tools python3 -m unittest tools.test_languages` checks selector inputs,
text coverage, references, Japanese layout and language-patch transitions.

Localized signs use RGBA cutouts of the changed pixels, and tournament banners
use RGB deltas against the player’s own banners. These products are committed
for all eight languages; private authoring images stay in `build/localized-src/`.
