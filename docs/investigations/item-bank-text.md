# Item Bank missing inventory letters

Investigation date: 2026-11-05. The report concerns occasional missing letters
in the right-hand Item Bank list in game version 0.0.5 on Android DuckStation.

## Cause and fix

The stored-item list and inventory share a 256-pixel-wide text texture. Each
uses a 128-pixel half, with two pages of six rows starting at text row 9.
The count-column control byte `0x1c` in `drawString2` moved the pen to column
100, but first cleared **100 pixels starting at the current pen**. With a
name ending at pixel 80, that clears through pixel 179: 52 pixels of the
inventory's half disappear. The amount erased depends on the name and font.

The two lists update independently. Opening both can hide the problem because
the right list is drawn after the left. Later scrolling or moving an item can
redraw the left page after the right page already contains valid text. This
explains both the intermittent appearance and the affected side.

`Keep-item-bank-column-clears-within-their-text-slot.patch` clears only the
positive gap to column 100. It preserves the existing cell rounding, count
position, glyph renderer, texture-cache-compatible clear and page allocation.
It introduces no allocation or persistent state.

## Reproduction and regression

The supplied Android screenshot shows Spanish item names with their beginnings
missing in all five right-hand rows, while the endings, counts and headers
remain intact. That matches the cross-slot clear reproduced locally.

On PCSX-Redux with `8mb: false`, open screen 211's counter (script 171,
section 81), using a copied save and a long bank list. Scroll the left list
past its fifth visible row. The beginning of the right-hand first name can
disappear while its ending and count remain visible. Reopening or redrawing
the right list restores the letters.

An isolated check redraws the right selected row with `updateItemMenuLine`,
dumps VRAM, redraws only the left selected row, and dumps VRAM again. Compare
the inventory half, VRAM word columns 736 through 767, rows 364 through 507.
The earlier development-disc fixture changed 94 words in that neighboring
slot. This is direct texture damage, independent of an emulator's texture
cache and screen clipping. A per-frame text budget does not explain writes
into the other list's slot.

Run the host regression against a prepared patch tree:

```sh
python3 tools/test_item_bank_text.py build/decomp-dev
```

It compiles the actual `drawString2`, proportional clear rounding and clear
macro with guarded neighboring pixels and address/undefined sanitizers.
It tests every name pen from 0 through 104, both font modes, both halves and
the optional half-space before the count. The original code fails; the fix
preserves the neighboring half in every case. Glyph drawing is stubbed, so
this check complements emulator tests rather than proving glyph appearance.

The earlier Android stale-text report concerned an additional DuckStation
texture-cache invalidation problem. Its full-row fills and partial-row uploads
remain in use; fixing this out-of-slot clear does not establish the behavior
of every Android DuckStation version.

## Memory

Matched compiles with the full eight-language padding and identical make
arguments move `main_BSS_END` from `0x801ceb00` to `0x801ceb10`: 16 resident
bytes. Heap changes from 185,328 to 185,312 bytes. A separate private copy of
the native tree was used for the comparison; restoring the fixed source
reproduced the original fixed native executable byte-for-byte. The heap sweep
passes. All 320 story setups fit against actual archive bytes; the tightest
setup is screen 207 with 592 bytes remaining. No new allocation or persistent
state is introduced.

## Corrected-disc results

The full eight-language developer build completed successfully. PCSX-Redux
reported `8mb: false`, with the interpreter and debugger enabled; RAM reads
were exactly 2,097,152 bytes. The matrix used 128 bank entries and 30 distinct
inventory entries, scrolling both lists and checking actual quantity changes
after a withdrawal and deposit.

| Item-name language | NEW (B) | CLASSIC (A) | ORIGINAL (A) | Neighboring-slot changes |
|---|---|---|---|---|
| English | Pass | Pass | Pass | 0 bytes |
| Spanish | Pass | Pass | Pass | 0 bytes |
| French | Pass | Pass | Pass | 0 bytes |
| Japanese | Pass | Pass | Pass | 0 bytes |

Language runs were applied from the disc's `DWLP` files before opening the
bank, followed by the language and font selectors. This tests localized item
names; already loaded field dialogue resources retain the captured state's
language. Screenshots after scrolling and transfers were reviewed.

Desktop DuckStation with OpenGL, native resolution, 100% CPU and 2 MB RAM
also preserved the right names after scrolling and transfers, with Enable
Texture Cache both off and on. Both settings started from the same saved
bank state. The earlier old-disc boot attempt did not reach the bank; the
corrected-disc test used its matching symbols and the save's confirm mapping.
One PCSX matrix setup process was interrupted during initial loading; its
restart from a captured bank state completed the eight NEW/ORIGINAL cases.
A further four CLASSIC cases passed from the same state: twelve cases total.

No original console or Android device was tested. The specific Android
DuckStation build from the earlier stale-text report remains untested. The
player's screenshot was available, but no matching player save state was
used. These limits do not change the direct pre-fix VRAM overwrite or the
patched parser's neighboring-slot regression result.
