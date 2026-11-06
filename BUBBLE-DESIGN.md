# HP and MP condition bubbles

Design review only. No game code, condition flags, thresholds or disc assets have changed.

HP and MP become care needs only when `current * 10 < maximum * 3`, with a positive maximum. Exactly 30% is not low. Each low resource gets its own condition bubble, whether or not the bag contains a suitable recovery item. The Square badge continues to indicate an available care action; HP/MP recovery entries and their contribution to that badge must use the same threshold. Other care reasons can still show Square independently.

## Five options

Every option spells out HP and MP. Colour reinforces the words: dark red for HP, dark blue for MP. The heart is never used alone.

| Option | Artwork | Reading and tradeoff | Proposed extra texture payload |
|---|---|---|---|
| **1 — Chips + labels** | Native HP Chip (item 27) and MP Chip (28), reduced to fit above tiny pixel labels | Familiar stat items, but may suggest increasing the maximum rather than replenishing it. MP Chip is natively grey; its label supplies the blue cue. | Two 24×24 4-bit tiles: 576 B, plus palettes |
| **2 — Recovery items + labels** | Native sm.recovery (item 0) and MP Floppy (4), with HP/MP underneath | Connects the need to the inventory remedy. The floppy silhouettes are similar, so the labels are essential. | Two 24×24 4-bit tiles: 576 B, plus palettes |
| **3 — Battle icons + labels** | Native battle HUD red heart and blue orb, with tiny HP/MP alongside | Connects field care to battle resources. More crowded at field scale than the plain labels. | Two 24×24 4-bit tiles: 576 B, plus palettes |
| **4 — Large pixel labels** | New pixel HP and MP lettering inside the native condition bubble | **Recommended:** the clearest resource names at native size, with no item or affection ambiguity. | Two 16×16 4-bit tiles: 256 B, plus one shared 32 B palette |
| **5 — Labels + down arrow** | Pixel HP/MP plus a small matching downward arrow | Explicitly suggests low resources, but the arrow adds visual weight and reduces free space. | Two 24×24 4-bit tiles: 576 B, plus one shared 32 B palette |

Payloads are design estimates for precomposed icon tiles, excluding TIM headers, alignment and executable code. Options 1–3 should budget up to two 32 B palettes (640 B total). The bubble background, hunger icon and Square badge already exist. Reusing item/HUD pixels at build time avoids retaining a new bitmap array in the main executable. An allocation and palette-space audit is still required; these figures are not measured heap deltas or proof that free texture slots exist.

## Asset provenance and layout

- Bubble: `ETCDAT/FEEL_EF.TIM`, native 32×32 cell at texture UV `(160,144)`, CLUT `(272,484)`. The renderer draws its 32×26 circular part and the remaining six rows as a separate tail. `RING_SIZE = 205` scales it to 205/256 of the original bubble.
- Hunger: the same texture, 16×16 meat cell at UV `(144,128)`, CLUT `(272,483)`.
- Items: `ETCDAT/ITEM.TIM`; cells follow `(id % 16 * 16, id / 16 * 16)`, using `ITEM_CLUT_DATA` rather than a generic palette. HP Chip uses palette 0; MP Chip uses 4; sm.recovery uses 0; MP Floppy uses 4.
- Battle: `ETCDAT/BI_IN.TIM`, 11×11 icons at texture UV `(144,176)` and `(155,176)`, CLUT `(256,491)`, as specified by `BTL_STATUS_BAR_SPRITES`. These are icon-only assets; their accompanying HP/MP lettering in the mockups is new pixel lettering.
- Square: the native UI cap derived by `tools/care_badge.py`, with the care-specific pink palette stored in the existing SYSTEM_W upload. The ordinary confirm cap is separate.

The review sheets reuse a real 320×240 field capture with Agumon from an emulator running with 2 MB RAM. HP and MP appear side by side in separate full-frame composites, followed by a combined hunger + HP + Square case. Each full frame is shown at 1×; the detail below is an exact 4× nearest-neighbour crop. Lettering is hinted to the displayed pixel grid so scaling does not erase the H crossbar or the P bowl.

The fixed mockup anchor is `(158,27)` in the captured frame, with `k = 1` screen pixel per texel before the 205/256 ring scaling (a 26×21 pixel circular sprite rectangle). The head anchor and projection are compositing estimates, not instrumented measurements from the saved executable; exact runtime size and anchoring remain to be checked against a live hunger bubble before implementation.

The combined case follows the existing two-condition layout: centres at `anchor.x ± 11*k`, where `k` is the projected texel scale. Neither bubble has a tail. Square is drawn in front near the lower-right edge, using the renderer's existing badge placement; it is not a third condition or a new bubble above the row. A single need retains the native tail. Adding HP/MP to the condition ordering and extending the three-or-more layout are implementation work, outside this review.

## Review artifacts

Local, uncommitted review sheets are in `build/bubble-design/`:

- `0-all-options.png`: comparison of all five pairs and combined cases.
- `1-bubble-design.png` through `5-bubble-design.png`: numbered full-frame 1× composites and 4× details.
- `option-<number>-<case>-1x.png`: standalone native-resolution composites.

Disc-derived artwork and captures remain local. No media-service identifiers are recorded in this document.

## Validation still required after selection

The sheets are static composites. Threshold transitions, recovery-item filtering, appearance/disappearance animation, camera depth changes, larger partners, three-or-more active needs, and all supported languages have not been exercised with an implementation. Small labels in options 1–3 are less legible than option 4 and need particular attention on a television.

Any subsequent C patch must measure `main_BSS_END` and run heapcheck on the original 2 MB budget. No C change or full build was needed for this design-only commit.
