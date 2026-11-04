# Simplified Chinese authoring

This is an incomplete translation draft, not a selectable game language yet.
The current draft covers the expanded starter quiz, Native Forest and Jijimon's
house. It follows `text/ours`, cross-checked against both original Japanese
extractions and the scripts in `story/base`. An independent second pass corrected
meaning, character voice and explicit row fit. Native-speaker approval and in-game
review are still required.

`glossary.json` records official Simplified Chinese species spellings and their
individual Bandai reference URLs. Project terms are separate; provisional terms
need review. No fan-patch dialogue is used. The naming keyboard will retain Latin
letters, digits and punctuation for player and partner names.

## Authoring checks

```sh
python3 -m tools.chinese audit --draft --layout --report build/chinese-review/audit.json
python3 -m tools.chinese review build/chinese-review/index.html
python3 -m unittest tools.test_chinese
```

The review page includes the English, original Japanese, Japanese Rev 1 and other
translations. It is a local artifact: extracted disc text must never be committed.
The audit records every missing key. Without `--draft`, any missing key fails the
check; the current bank deliberately fails that completeness gate. Authoring
layout checks use the exact bitmap advances, atomic substitutions, Chinese
punctuation rules and the existing 240/228 px, 62-byte dialogue bounds. They do
not validate the console's encoding walkers, scripts or overlay crops.

## Offline font prototype

`tools/font/chinese.json` is a licensed, renamed subset of Fusion Pixel 12px
monospaced Simplified Chinese. Source checksums and all upstream notices are in
`tools/font/chinese-license/`; see [third-party terms](../../THIRD-PARTY.md).
It contains every draft glyph plus ASCII and Chinese punctuation. Pixels retain
the upstream Simplified Chinese forms without cropping or resampling.

```sh
python3 -m tools.chinese font build/chinese-review/FONTZH.BIN
```

This generates a proposed `DWZH` font container using the standard library, with
no downloads, original game assets or runtime glyph streaming. The header is
32 bytes: magic and seven little-endian words (version 1, width 12, height 12,
record size 26, ASCII count 95, extended glyph count, payload CRC32). Each record
is a 16-bit advance and twelve inverted, MSB-first 16-bit row words. ASCII 32–126
comes first. Extended records follow the accompanying build-time code map.

The proposed Chinese-only two-byte range uses leads A0–DF and trails 40–FC,
skipping 7F, for 12,032 dense codes. These are not CP932 codes and must not enter
the existing runtime until every text walker handles them. The Unicode map is
for the builder; the console can index the dense records without that map.
`tools/chinese.py import-font` is a developer operation accepting only the pinned
licensed BDF; a player's patcher needs only the committed subset.

## Remaining runtime gates

Chinese must be language ID 8, with IDs 0–7 preserved. The normal selector must
show a disabled Chinese entry and an 8 MB requirement on a 2 MB console. Selection
on an 8 MB console must load the complete font above 2 MB using the existing RAM
probe. Chinese-specific code and data must stay outside the resident 2 MB budget.

The runtime loader, 12-row renderer, all text walkers, selected-language resource
directory, executable/species names, overlay crop tables, artwork, LANGZH
resources, desktop/browser replay and save-option gates are not implemented by
this authoring prototype. They need measured nonpositive `main_BSS_END`/heap
changes, full nine-language builds and both 2 MB and 8 MB gameplay tests before
Chinese is added to the public language registry.
