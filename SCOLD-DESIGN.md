# Scold condition bubble — design review

Status: option 1 selected and implemented. The original four-option mockups remain
reproducible with `design/scold/render.py`; the live proof uses the built game.

A Square badge caused by Scold must have a condition bubble explaining it. This
bubble means a justified Scold action is available after misbehaviour, such as
refusing food. It does not mean hunger, low discipline, or general unhappiness.

## Four options

| Option | Pictogram | Rationale |
| --- | --- | --- |
| 1 | The game's own Scold menu icon | Preferred baseline; shares the field menu's visual vocabulary. |
| 2 | Scold icon with a small red warning dot | Preserves the silhouette with a stronger warning cue. |
| 3 | Scold icon with a small red anger accent | Preserves the silhouette with a sharper behaviour cue. |
| 4 | One bold red anger mark | The only alternative to the native Scold icon; no letters or text. |

The numbered review sheet is generated at `build/scold/SCOLD-options-1-4.png`.
Every row shows a complete 320×240 field composite for Scold alone with Square,
a second composite beside another condition, and exact nearest-neighbour 4×
crops of both. These are design composites over existing 2 MB captures, not
screenshots of a working Scold bubble. The neighbour is the existing HP need.

Option 1 derives the actual `MENU_OPTIONS[5]` artwork: ETCTIM entry 4, UV (0,40),
20×20 cell, palette 13, corresponding to CLUT (256,509). The occupied silhouette
is 18×18. It is fitted without filtering into an 11×11 screen-pixel footprint
inside the existing 17×14 captured field bubble. “Native size” on the sheet means
actual field display size; it does not mean pasting the larger menu cell at 1:1.
Options 2 and 3 add only small red accents. There is no enlarged bubble or text.

## Implemented visibility contract

The bubble uses the same current eligibility as the badge's Scold case: the care collector
adds `FEED_SCOLD` exactly when `ITEM_SCOLD_FLAG == SCOLD_PENDING` (1). Reuse that
eligibility rather than introducing a separate refusal timer or condition bit.
The existing field/HUD visibility gates and ordinary bubble transition apply.
`modScoldAvailable(flag)` is shared by the care collector and bubble activation.
A cleared window suppresses Scold drawing immediately, including a stale animated
slot. The badge is drawn only if at least one bubble is actually drawn, so its
faster growth cannot produce a lone Square during a new bubble's first frames.

- Scold alone: show this bubble with the Square care badge.
- Scold plus other needs: include it once in the existing fixed bubble layout.
- Inventory contents do not affect Scold eligibility.
- Clear it when Scold ceases to be available, including after Scold is used or
  the pending state is cleared by ordinary movement. No extra linger timer.
- Unjustified Scold being selectable through the general field menu does not
  qualify. The trigger is the justified care action represented by the badge.
- Other needs and their actionability keep their existing rules.

Use the existing shell, bob, fixed group spacing, single-bubble tail, multi-bubble
tail suppression, screen clamps, and Square placement. The ring has nine slots; the full combination uses five bubbles above four.
The native icon uses the existing menu texture directly: page `0x1e`, UV (0,232),
20×20, CLUT (256,509), pivot (10,28) in the ordinary condition-icon coordinate
system. It fits the existing 26-texel circle. No atlas modification, new bitmap,
file-table entry, texture upload, or resident sprite descriptor is needed. The
localized field stacks preserve the same menu cell and palette.

## Evidence and reproduction

`design/scold/render.py` derives the menu icon from local player-disc inputs and
uses `hp29.png` and `hp31.png` from the existing original 2 MB HP/MP proof. The
source proof records 2,097,152 bytes of RAM. The renderer records source SHA-256
hashes, sprite coordinates, footprint, and zoom in `build/scold/evidence.json`.
Disc artwork and full game captures remain untracked.

```sh
.venv/bin/python design/scold/render.py --captures PATH_TO_EXISTING_HPMP_PROOF
```

The complete sheet was visually inspected at native scale and 4× before review
upload: all four silhouettes fit the shell and remain distinct; the single tail,
condition neighbour, and Square are visible. Native Scold is the clearest match
to the existing menu and is the recommended starting point.

## Implementation validation

The unnumbered C patch is
`Explain-pending-care-Scold-with-its-native-menu-icon-bubble.patch`, appended to
`mods/patches/series` and `index.md`. The series applies cleanly to the pinned
source. Host tests exercise 216,000 layouts with zero through nine bubbles,
four scales, camera offsets, screen edges, and every badge phase. They also
check immediate suppression of an expired Scold slot and its lone badge.
The compiled care collector is checked against Scold flag values 0, 1, 2 and 3,
with and without the needs-only filter and with an empty bag.

Matched full-disc native compiles (identical nine-language banks, file plan and
version) measure `main_BSS_END` from `0x801CE10C` to `0x801CE1F4`:
**232 resident bytes**, **240 bytes of aligned heap**. The final heap is
**187,648 bytes**. MENU_REL remains **54,248 bytes**, 27 sectors, with 1,048
bytes before another sector would be needed. All nine language links pass the
whole-sector MENU and title-overlay overlap assertions. The early minimal-file
compile measured 248 resident bytes; the complete disc measurement above is the
release-relevant comparison.

Live evidence is produced by `tools/dev/playtest/scold_bubble.py` on the full
nine-language disc in original 2 MB mode. It uses ordinary pad input to give an
item, observes the native refusal and justified Scold menu entry, cancels to
show Scold alone with Square, then uses Scold. It reloads that same naturally
produced pending state and walks to expire the existing window. There is no
new expiry timer. Combined and nine-condition edge cases use explicit stat and
position fixtures while normal layout, icon rendering and care eligibility run.
The nine localized atlas cells and palettes are compared with the source disc.

Full-build budgets and review artifacts are recorded below. Physical-console
testing remains outstanding. Simplified Chinese retains its existing 8 MB
requirement; its native sprite and palette are verified through the atlas audit.

The full nine-language build passes standard heapcheck and all **320 actual-archive
screen setups**, without a heap override. The tightest setup is screen **207**,
with **2,928 bytes** remaining. Every language has the same main end and MENU size.

The final 2 MB run passes a real item refusal with Scold alone + Square; Scold use
clears both (the native flag becomes 2); walking expires the window and clears
both (flag 0). Hunger + HP + MP + Scold, all nine conditions, and six centre/edge/
corner layouts pass. Multi-field condition setup is paused atomically; normal
condition updates, layout, rendering, and care logic then resume. The review run
uses open city-plaza ground so foreground buildings do not obscure the icons.

| Layout | Complete emitted GPU bounds (left, top, right, bottom) |
| --- | --- |
| Centre | 111, 50, 216, 89 |
| Left | 76, 47, 180, 87 |
| Right | 212, 47, 317, 86 |
| Top | 103, 8, 211, 42 |
| Top-left | 75, 8, 172, 42 |
| Top-right | 219, 8, 317, 42 |

Each recorded edge frame retains the nine bubbles and Square, stays inside
320×240, and clears the clock. The sheet includes native full frames and exact
4× crops. The 31-second video captures presented frames with their vblank timing;
its captions occupy a separate band outside the gameplay frame. Both were
visually inspected before review upload.

```sh
ISOS=/path/to/digimon-world SOURCE_ISOS=/path/to/isos \
  python3 -m tools.dev build --jobs 8 --name scold-bubble
.venv/bin/python tools/dev/playtest/scold_bubble.py build/scold-bubble.cue \
  --exe build/scold-bubble/exe/SLUS_010.32 --out build/scold-proof --clear-ground
.venv/bin/python tools/dev/playtest/scold_contact.py build/scold-proof
DW_SELFTEST_DERIVE=build/scold-bubble tools/selftest.sh
```

Local evidence: `build/scold-proof/result.json`, native PNGs and presented-frame
clips; `build/scold/full-native-delta.json`, `nine-language-budgets.json`, and
`nine-atlases.json`; the full build's `heap.txt` and `story-heap.json`. The built
image SHA-1 is `7cab8eb6c19f80e30f6644e37a0fcea966476bfd`.

All **133 selftest groups are verified**. Interrupted runs were resumed without
repeating completed groups; the DWS suite finished in four batches covering all
**196 unittest IDs exactly once**. Its two existing optional-fixture skips are
the separate C city-reader equivalence tree and the original/readable/reordered
sweep discs. All feature-specific 2 MB cases ran. The image-dependency audit
passes after changing the review helper to the project's image wrapper.
The consolidated check report is `build/scold/selftest-verified.jsonl`; the
individual DWS batch manifests and logs retain the coverage evidence.
