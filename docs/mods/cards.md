# Card data and build inputs

The engine reserves IDs 0–511. Keep original card numbers stable: 0 and 65 are
sentinels, and 1–64 come from `content/tables/cards.json`. Additional real cards
are the rows of `content/cards/new.json`. The phase-A list is empty until artwork
is supplied. Duplicate species and multiple cards for a species are supported;
card number, rather than species, identifies a collectible and its saved count.

Each new row has these fields:

```json
{"key": "example-card", "number": 66, "species": 300, "with": [301], "rarity": 2, "merit": 10}
```

The document wraps these rows in a `cards` array, matching the card maker.
`key` and `number` must each be unique. `number` is 66–511, `species` is an engine
species ID (0–1023) or owned species name, and optional `with` lists companion species for artwork only. The
engine displays the primary species name. Rarity 0 is rarest: rarities 0–4 require
merit 100/30/10/5/1, respectively. The native price table remains
5000/1500/500/100/50. Unassigned IDs have rarity 5 and enter neither packs, daily
stock, nor the Card Complete medal requirement. Other artwork metadata, such as
`scene`, `pose`, `frame` and `style`, is ignored by the engine builder.

`tools/cards.py` validates these rows and generates `CARD/CARDTAB.BIN`: exactly
512 little-endian `<HBB` rows, one sector. Its four-byte row keeps the species
aligned and stores merit in a byte. `tools/balance.py` derives the resident
64-byte real-card bitmap from the same JSON; no extra metadata table is resident.
The economy audit includes every authored new card.

The derive `cards` step and `plan` step add `CARDTAB.BIN` and `CARD2.ALL` through
`tools/newfiles.py`. This supplies both ISO directory entries and `NEW_FILES`
for the generated executable file table; the ordinary relayout writer assigns
sectors and sizes. No hand-coded disc sector or original disc data is committed.

Set `CARD2_ALL` to the phase-B archive path when building with new cards:

```sh
CARD2_ALL=build/card-art/CARD2.ALL python3 -m tools.dev build --jobs 8 --name cards-engine
```

Each entry is exactly `0x7000` bytes (14 sectors), with the same 150×180 8bpp TIM
layout as `CARD.ALL`, pixels at VRAM (576,256), palette at (448,511). Entry `i`
is card ID `66+i`. Sparse metadata retains those positions: the archive must
reach the highest assigned ID, including holes, and may contain up to 446
entries. A missing archive or an incorrectly sized archive fails the build when
new cards are listed. With an empty list, the build writes an empty archive.
No new card is obtainable in that configuration.

The original thumbnail sheet is part of the stacked `ETCTIM.BIN` upload loaded
by `main.c`. Its album UVs are `(id%8)*32, (id/8)*16`, on a 256-pixel texture
page. A 512-card sheet would require 64 rows and exceed that page. Original
portraits retain their sheet and CLUTs; new cards use the existing generic
rarity-coloured card sprite, avoiding additional image data, VRAM allocation,
runtime resampling or disc reads while scrolling. The full viewer reads art
only when a card is opened or the results selection changes.

The metadata sector uses `OVL_BTL_BASE` during card interactions. Native shop-file reads use a different
overlay slot, and battles are inactive during the album and shops.
Entering a card shop or the album loads the table once. Leaving the album for
another Player tab reloads MENU before any chart callback can run. The existing
card image buffer and stack allocator hold viewer art and shop lists. Card rows
use a u16 ID plus a byte count/flags; list counts and scroll offsets are u16.
Menu boxes allocate their actual struct size. Pack results reserve at most 297
rows (99 three-card packs), keeping their live list below the image staging area.
This supports all 510 possible real cards on an original 2 MB PlayStation.

With the complete multilingual file plan, `main_BSS_END` moves from
`0x801CE958` to `0x801CE94C` (−12 bytes, including both new file entries).
The aligned heap is 185,760 → 185,776 bytes (+16). The album renderer and its
original portrait CLUT map move into MENU's tail, after the metadata sector;
linker assertions prevent overlap. MENU grows from 53,788 to 55,240 bytes and
retains its 27-sector allocation (56 bytes spare). The original-screen heap
sweep passes, with its tightest projection retaining 29,424 bytes. This measures
the complete file directory and shared language padding, rather than an
English-only executable. The archive-backed sweep also passes all 320 screen
setups; the tightest retains 776 bytes (16 more than the matched baseline).

The v1 script-state bytes never grow. The additional 223 count bytes and six
u16 daily stock IDs use optional save tags `0x000D` and `0x000E`; the inline bound
is 1,093/1,120 bytes (27 spare). See [save format](../reference/save-format.md).

Validation without an emulator:

```sh
python3 -m unittest tools.test_cards tools.test_heap_tables
python3 tools/dev/playtest/cards_host.py build/decomp-int
python3 tools/dev/playtest/merit_cards_host.py build/decomp-int
python3 tools/dev/saves/capacity.py build/decomp-int
python3 tools/dev/saves/inline.py build/decomp-int
python3 tools/economy_audit.py
```

The card host check compiles the production collection functions, navigation,
pack roll, shop builder/trade, daily stock, record writer/reader and inline
scatter helper with address/undefined-behaviour sanitizers. It generates a
temporary archive of 446 distinct flat-colour TIMs and verifies every new image
offset, JSON-driven pack eligibility, IDs 255/256/511, old/short record defaults,
and the real-card medal rule. It checks the loader's selected bytes, rather than
GPU presentation. Artwork review and emulator presentation remain separate
phase-B checks.
