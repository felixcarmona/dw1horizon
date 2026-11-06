# HP and MP care bubbles

HP and MP are care needs strictly below 30%: `current * 10 < maximum * 3`, with a positive maximum. At exactly 30%, no resource bubble or resource-only Square hint appears. The need is independent of inventory: low resources still show their bubbles with an empty bag. Square needs an available action, as it does for the other conditions.

Square can still open the care menu above the threshold when the bag has a field-usable recovery item for a resource that is not full. Those optional recovery entries sort after the actual needs. Critical recovery retains its existing place before sleep; other care actions keep their priorities. Opening or cancelling the list does not consume an item.

## Pixel art and native layout

The HP bubble uses the native sm.recovery disk (ITEM.TIM item 0, palette 0). The MP bubble uses the native MP Floppy (item 4, palette 4). Both preserve their native pixels outside a small white label plate. HP uses dark-red pixel letters; MP uses blue pixel letters. The letters use explicit seven-row pixel patterns, bold stems, doubled critical rows and a two-texel letter gap. M is inset to retain both diagonals at native field scale. No font rasterizer, text string, blur or filtered resampling is involved. All nine languages share these same pixels.

The two icons occupy previously empty 16×16 cells `(224,0)` and `(240,0)` of ETCTIM.BIN entry 1, uploaded at `(960,448)`. Their private palettes use the empty rows 13 and 14 of FEEL_EF's CLUT block at `(272,480)`, i.e. VRAM rows 493 and 494. Each copies its own item's palette and replaces only two inks unused by that disk. The standalone FEEL_EF file repeats those palette rows so its ordinary upload preserves them.

The art is derived from the player's existing texture stack by `tools/care_bubble_art.py`. The files retain their original sizes and upload rectangles; no disc file, file-table name, bitmap array, heap buffer or upload is added. FEEL_EF is one common replacement, not a per-language duplicate.

The existing condition ring now has eight slots: hunger, toilet, sleep, tiredness, sickness, injury, HP and MP. HP/MP use the same native bubble background, anchor, 205/256 bubble scale, animation, row spacing, tail suppression, and Square overlay as the existing conditions. The disk occupies 20 texels inside the native 26-texel circular height, using the game's ordinary nearest-neighbour sprite scaling. One condition has a tail; two share a row without tails; three or more use the existing two-row layout. No mocked screen-space coordinates are used by the implementation.

## Resident memory

The field collector and mutable care state remain resident. The care menu's existing note routine, note strings and command captions move to MENU_REL. `feedOpen` loads MENU before reading them. The resident closing/giving paths restore the curling overlay through `closeMenuOverlay` before resuming field activity. The asynchronous care callbacks stay in main, so returning from a menu cannot return into an overwritten overlay.

The full nine-language comparison uses identical final disc flags, generated headers, language banks and padding. Before the feature, `main_BSS_END` is `0x801CE5E0`; the resource patch alone raises it to `0x801CE780` (+416 B). Moving the existing care UI routine/data into MENU lowers it to **`0x801CE52C`** (−596 B), a net **180 fewer resident bytes**. Aligned heap increases from **186,640 to 186,832 B** (+192 B).

MENU_REL grows from **53,860 to 54,484 B** (+624 B), retaining **27 sectors** and the existing linker read bounds. No BSS is added: it remains 621,116 B. Final main text/rodata/data are 509,648 / 29,656 / 134,264 B. Normal heapcheck passes without an override; **all 320 actual-archive screen setups fit**, with the tightest margin **2,112 B on screen 207**.

The full build includes all nine padded language banks. Its image SHA-1 is `2a077d518d37a69edb85193eb4cf70ea162630f9`. The generated care-art cells and palettes were checked byte-for-byte across all nine language atlases; each matches the current hand-pixelled source and keeps the original file sizes.

## Native verification

The final disc passes the 2 MB PCSX-Redux proof: HP 29% and MP 29% each show their bubble and Square; 31% and exactly 30% show neither. HP + MP + hunger use the existing two-row layout. With an empty bag both resource bubbles remain and Square disappears. At 31% the care menu still offers recovery; critical MP sorts before optional HP. Using one sm.recovery raises HP from 29% to 79% and clears the HP bubble.

Field and menu captures pass in both fonts for English, Spanish, Brazilian Portuguese, French, German, Italian, Japanese and Catalan. The native PNGs and exact 4× crops were inspected. Full toolchain selftest passes **118 checks, zero failures and zero skips**. Physical console testing remains outstanding; Simplified Chinese retains its existing 8 MB requirement and was checked through the full build and shared-art comparison.

## Reproduction

- Full disc: `ISOS=/path/to/dw1 SOURCE_ISOS=/path/to/isos python3 -m tools.dev build --jobs 8 --name hpmp-bubble`.
- Source workflow: `tools/mods.sh prepare int`, commit changes in the private prepared tree, then `tools/mods.sh save int` and `python3 tools/patch_series.py check --apply`.
- Care logic: `python3 tools/dev/playtest/hpmp_care_host.py build/decomp-dev` and `python3 tools/dev/playtest/quick_care_host.py build/decomp-dev`.
- Art allocation/preservation: `python3 -m unittest tools.test_care_bubble_art tools.test_care_badge`.
- Native proof: `python3 tools/dev/playtest/hpmp_bubbles.py DISC.cue --exe EXE --card AGUMON.mcd --out build/hpmp-proof`. This boots the tested executable on 2 MB RAM, captures 29/30/31% cases, combined hunger/HP/MP, an empty bag, optional/critical care ordering, and menus in both fonts across the eight 2 MB languages. It records exact rendered bubble anchors for the 4× crops.
- Complete toolchain: `DW_SELFTEST_DERIVE=build/hpmp-bubble tools/selftest.sh`.

The native evidence, raw PNGs, 4× crops and machine-readable results stay local under `build/hpmp-proof/`. Disc-derived pixels are not committed.
