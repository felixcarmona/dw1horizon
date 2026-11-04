# Game languages

The runtime language selector supports English, Spanish, Brazilian Portuguese,
French, German, Italian, Japanese, Catalan and Simplified Chinese. Chinese requires 8 MB RAM;
the other eight languages support an original 2 MB console. The picker shows
Chinese disabled with an 8 MB note when the extra RAM is absent. Text, executable strings, signs and
other translated textures switch together. A first-boot picker shows native names
and procedural flags; saved options skip it. OPTIONS can change the language later.

Our English translation is in `text/ours`; the other translations are in
`text/{es,pt-br,fr,de,it,ja,ca,zh-hans}`. `text/<language>.json` supplies common mod text,
and each story mod can provide its own `text/<language>.json`. Text is keyed to
script locations rather than copied into the story's code. Review records and
translation process notes are excluded from the published tree.

## Building

```sh
SPECIES=all SPECIES_PROVIDER=imports TEXT=ours LANGS=en,es,pt-br,fr,de,it,ja,ca,zh-hans \
  LANG_BASE=en DERIVE_JOBS=1 W=$PWD/build/decomp-int NAME=everything \
  DW_HEAP_MAP=/nonexistent story/mods/what-the-island-forgot/build.sh
```

Prepare the four player discs first; see
[building](../building.md). `LANGS` must contain English and at least one other
language, with no duplicates. The builder uses a canonical order, independent of
the order supplied. `LANG_BASE` must be among the selected languages.

The overlays have a copy per language. A language chosen at the title (the first-boot
picker, OPTIONS or a card's options) also reads the menu overlay again in that language,
over its own running code (patch 0329), so `tools/langpatch.py overlay --elf` stops the
build if two languages' copies of an overlay differ in code rather than only in strings.

The builder compiles each language with a common address layout and makes
`LANGEN.BIN`, `LANGES.BIN`, `LANGPT.BIN`, `LANGFR.BIN`, `LANGDE.BIN`, `LANGIT.BIN`,
`LANGJA.BIN`, `LANGCA.BIN` and `LANGZH.BIN`. Only selected languages are included. The original
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
for the first eight languages; private authoring images stay in `build/localized-src/`.

Drill Tunnel Entrance also has an alternate sign after the Ogre takeover.
Its normal sign is `audit-13`; `mayo11_ogre` supplies the takeover wording in
the same masked-delta pipeline, with the ogre word painted in dull olive green
and the tunnel word kept bright. Japanese retains the original sprite art.
The alternate edit targets only MAYO11 sprite frame 6 (TIM 1, rows 96–191),
including transparent holes that would otherwise expose the background's
localized Drill lettering. Frame 5 (rows 0–95) keeps the normal sign.
Both frames use the instance position (0, 152); the background keeps its normal
name. The normal edit targets only frame 5: the overlapping tree and additive
lamp glow must retain their original pixels, or they redraw Drill lettering
over the takeover. Authoring placements and English, Spanish and Portuguese wording live in
`content/localized/signs/jobs.py`; the other wording is in
`tools/localize/catalog.py`. `tools/localize/signs.py --make-cutouts` accepts
the alternate edit at the same 196 × 110 canonical crop as the normal sign.

Run `python3 -m unittest tools.test_signs` with an extracted USA disc to check
that the takeover covers the old lettering, preserves the other frame and TIM
palette, and leaves each MAP's byte size unchanged.

Green Gym's foreground sprites use an opaque palette entry 0 and a transparent
entry 255. All localized copies use the palette's transparency when repainting
those sprites, as the Spanish copy already did, so the background translation
and its foreground agree.

## Chinese extra RAM

`LANGZH.BIN` is a container with one resident sector-table entry. Its runtime,
font, route directory and species-name work buffers load above 2 MB only when
Chinese is selected on an 8 MB console. Script and texture resources remain in
the container, read through the normal file paths. The complete font stays in
RAM throughout play. Normal language switches restore the resident language data.

`tools/chinese_resources.py` validates the prefix checksum, font, write bounds and
resource routes before packaging. The Chinese compiler keeps references atomic,
uses Chinese punctuation rules, and checks explicit custom windows against their
script dimensions. Packed UI rows are aligned to the existing crop boundaries by
`tools/localize/executable/chinese_layout.py`. Naming uses the Latin keyboard.
Chinese selection preserves player names and custom partner nicknames.

The standard nine-language build must retain every 2 MB heap gate. Font and
container generation uses committed licensed pixels and authored translations;
see [Chinese sources](../../text/zh-hans/README.md).

Chinese battle registrations keep a Latin species-name fallback in the fixed save
record. The 8 MB runtime displays the official Chinese name from its extra-RAM
name pool, while custom Latin nicknames remain unchanged. Battle-mode lists use
a compact font atlas in text rows 128–215, separate from command text and digits.
