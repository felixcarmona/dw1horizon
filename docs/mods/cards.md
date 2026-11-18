# Card data and build inputs

The engine reserves IDs 0–511. Keep original card numbers stable: 0 and 65 are
sentinels, and 1–64 come from `content/tables/cards.json`. Additional real cards
are the rows of `content/cards/new.json`. Duplicate species and multiple cards
for a species are supported;
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
64-byte real-card bitmap and the 128-byte replacement-art lookup from the same JSON.
The economy audit includes every authored new card.

The derive `cards` step and `plan` step add `CARDTAB.BIN` and `CARD2.ALL` through
`tools/newfiles.py`. This supplies both ISO directory entries and `NEW_FILES`
for the generated executable file table; the ordinary relayout writer assigns
sectors and sizes. The disc's `CARD.ALL` stays pristine and is never a plan
replacement, including when a stale generated `CARD.ALL` exists. No hand-coded
disc sector or original disc data is committed.

By default the cards step composes `CARD2.ALL` from the committed artwork.
To supply an already composed archive, set `CARD2_ALL`:

```sh
CARD2_ALL=build/card-art/CARD2.ALL python3 -m tools.dev build --jobs 8 --name cards-engine
```

Each entry is exactly `0x7000` bytes (14 sectors), with the same 150×180 8bpp TIM
layout as `CARD.ALL`, pixels at VRAM (576,256), palette at (448,511). Entry `i`
is card ID `66+i` for new cards. Sparse metadata retains those positions,
including holes. Rows with `replaces` append their art after the highest new ID,
in JSON order: the current 240 new slots plus 64 replacements use 304 of the
446 allowed entries. All original IDs 1–64 have replacement art; their entries
are 240–303 in JSON order. Replacement IDs must be unique originals 1–64. Both composed and supplied archives must fit
446 entries; supplied archives must reach and validate every new and replacement
TIM. Old supplied archives without the appended art fail the build. With an
empty list, the build writes an empty archive.

`balance.py` generates 64 u16 archive entries in `MOD_CARD_ART`, indexed by
original ID minus one; `0xffff` marks originals without replacement art.
The direct lookup preserves sparse and arbitrary JSON ordering. The shared viewer/shop/pack-result loader uses
this lookup only with NEW CARDS ON. OFF reads original art from `CARD.ALL`.
There is no additional image buffer or allocation. The card builder also removes
stale generated `CARD.ALL` outputs from the old composer.

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

The OPTIONS row **NEW CARDS** defaults to ON. OFF hides IDs 66–511 in every
collection and acquisition view, preserves their saved counts and existing stock,
and requires only originals for Card Complete. OFF also restores the original
full-size artwork for the 64 replaced cards; ON selects the authored
replacements. Their eligibility stays the same. See [options](options.md#new-cards).

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
offset, all 64 OFF/ON replacement/original selections, JSON-driven pack
eligibility, IDs 255/256/511, old/short record defaults,
and the real-card medal rule. It checks the loader's selected bytes, rather than
GPU presentation. Artwork review and emulator presentation remain separate
phase-B checks.

The artwork-option change was measured with matched executable-only links using
the complete cards-engine file plan (1,509 new files) and shared language padding:
`main_BSS_END` 0x801CE898 → 0x801CE908 (+112 bytes), aligned heap
185,952 → 185,840 bytes. This includes the 16-byte lookup and loader code.
MENU remains 55,296 bytes (27 sectors); heapcheck retains at least 29,488 bytes
against the original-screen sweep. These are host/link checks; no full disc build
or emulator test was run for this change.

## Album range and scrollbar

The 11-column, six-row album trims its numbered range to the highest real card
in the existing `MOD_CARD_REAL` bitmap. Current content ends at ID 305: 28 rows,
with top row 0–22. Unassigned trailing capacity through ID 511 is hidden;
sparse holes are blank and directional movement skips them within the same
column or horizontal row. The original selectable slots 0 and 65 remain for
compatibility. NEW CARDS OFF retains its original six rows and range 0–65.

The header retains the selected card ID on the left. Its denominator preserves
the original album's 65 numbering convention and adds only real new IDs from
the bitmap: **305 ON, 65 OFF**. There are 64 collectible original bitmap bits
and 240 new bits; sentinel 65 accounts for the legacy numbering difference.
The 64 replacement-art rows add no collection entries. No new array, cache,
allocation or resident state is needed.

When there are more than six rows, the right edge shows a cyan thumb over the
dark track used by the evolution requirements popup, drawn through the existing
`renderBox` helper (thumb before track). Its 138-pixel track spans the grid;
thumb height is `138 * 6 / totalRows`, and its position spans the remaining
track proportionally to `topRow / (totalRows - 6)`. It is hidden in OFF mode.

Matched English FONT=b, FPS=60 executable-only links, using the same complete
1,509-file cards-engine plan and shared language padding as the artwork-option
measurement above, give `main_BSS_END` **0x801CE908 → 0x801CEBD8 (+720 bytes)**.
This is resident code growth, including the navigation moved out of MENU;
the small top-row helper moves into MENU instead. Aligned heap is
185,840 → 185,120 bytes. MENU is **55,204 bytes, still 27 sectors (92 bytes
spare)**; all linker assertions pass. The original-screen heapcheck passes,
with 28,768 bytes remaining in its tightest projection.

`cards_host.py` checks shipped 305/65 totals, partial final rows, sparse
navigation, full capacity through ID 511, and scrollbar geometry at every
scroll position for 6–47 rows under address/undefined-behaviour sanitizers.
The 55 card/heap/economy/language unit tests, merit-card host check, save capacity
and inline checks, and economy audit pass. No full disc build, new archive heap
sweep, emulator/GPU presentation check, or other font/language executable link
was run for this change.

## Generating and keeping the artwork

Cards are built by `tools/cardmaker.py` from kept artwork plus our own frame and font, so changing
the frame or the font only needs a re-run. The artwork of each card is generated from a render of
the real 3D model (the model sheet is the reference image) placed in a low-poly PlayStation-style
scene. Everything that steers the image is a field of its row in `content/cards/new.json`: `scene`,
`pose`, `anatomy` (the limbs the model really has) and `frame` (colour override).

- `tools/generate_cards.sh KEY...` generates the missing originals (2K images, retrying on rate
  limits). Each original is written as `<key>.png` with a `<key>.json` that records the exact
  prompt and model; those records are committed in `content/cards/generation/`.
- The originals are kept in the repository as lossy WebP copies (quality 92, about 0.3 MB each) in
  `content/cards/originals/`: visually the same as the 2K PNGs the generator returned, and enough to
  re-reduce the art and re-run the card maker. The full-quality PNGs (about 1.8 MB each) are not committed;
  `content/cards/originals.sha256` lists their checksums, and `CARD_ORIGINALS` points the tool at them
  when they are at hand (the PNG wins over the WebP).
- `python3 tools/cardmaker.py reduce KEY...` writes the committed art, `content/cards/art/<key>.png`.
- `python3 tools/cardmaker.py render KEY` previews a finished card; `tools/cards.py` composes the
  card archives from the committed art at build time.
- Imported species need their model files: `CARD_MODEL_FOLDERS` lists the folders to search.
- Anatomy rules for new cards: draw exactly the limbs the model has, never invent legs or arms, and
  stand every creature on the ground unless it visibly flies.

## All-original artwork lookup (cards-opt4, Part A)

The lookup now supports every original, including sparse and unordered replacement
rows, without scanning packed entries. The archive contract stays at 446 entries;
240 new cards plus 64 replacements consume 304 entries (8,716,288 bytes).
Both supplied-archive validation and composition use the identical JSON mapping.
The derive cards step delegates this mapping to `tools/cards.py`; no separate
count or hand-maintained mapping lives in the derive pipeline.

Matched executable-only English FONT=b, FPS=60 links with the complete 1,509-file
plan and shared language padding measure `main_BSS_END` 0x801CEBB8 → 0x801CEC18
(+96 bytes). The lookup grows 16 → 128 bytes while loader code shrinks.
Aligned heap is 185,152 → 185,056 bytes; MENU remains 55,204 bytes (27 sectors).
The original-screen heapcheck passes, tightest projected free heap 28,704 bytes.
These measurements supersede the historical measurements above for this tree.
All 55 card/heap/economy/language unit tests, card and merit host checks,
save capacity/inline checks and economy audit pass. No full disc or emulator
check was performed.
