# Simplified Chinese

The translation follows the project's English text, checked against both original
Japanese versions and each scene's script context. The glossary records official
Simplified Chinese species names with individual Bandai references; authored and
provisional terms are separate. No fan-patch dialogue is used. Native-speaker
approval is still required; local review evidence and open questions stay outside
the published tree.

Chinese is language ID 8. It requires an 8 MB console; the normal language picker
shows a disabled entry with that requirement on a 2 MB console. Selection loads
the complete bitmap font and Chinese runtime into extra RAM. Glyph rendering
performs no CD reads. Player and partner naming retains the Latin keyboard;
custom names survive language changes.

The renamed Fusion Pixel subsets and their upstream notices are in
`tools/font/chinese*.json` and `tools/font/chinese-license/`; see
[third-party terms](../../THIRD-PARTY.md). Dialogue uses 12px glyphs, keeping all
twelve bitmap rows. Compact labels and battle-mode lists use the designed 8px glyphs; both fonts
load together when Chinese is chosen. The 12px
font's blank-space advance is four pixels to match the game's packed text and
original cell grid; glyph pixels are not cropped or resampled.

```sh
python3 -m tools.chinese audit --layout
python3 -m tools.chinese review build/chinese-review/index.html
python3 -m tools.chinese font build/chinese-review/FONTZH.BIN
python3 -m unittest tools.test_chinese
```

The player's builder generates the binary font offline from committed pixels,
using the standard library. No font download is needed. The authoring importer
accepts only the pinned upstream BDF checksums. Missing keys, glyphs, substitutions
or invalid Chinese row boundaries fail the build.

`tools/font/chinese-codes.json` is an append-only glyph order. Font imports append
new characters without changing existing two-byte codes, so saved names keep their
meaning across translation revisions. Do not remove or reorder entries.
