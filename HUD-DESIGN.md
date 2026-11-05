# Four field care gauges: design review

Design only. No game code, patch, texture asset, option or save format changes.

**Recommend A, the framed 2×2 grid.** It shows all four values continuously, keeps the existing face icons recognisable and occupies the current 75×23-pixel footprint. B is the lighter alternative if the long silver frames feel too busy. E preserves the best precision but hides half the information.

## Review material

The separate review package contains `A-review.png` through `D-review.png`, `E-review-mood.png` and `E-review-needs.png`. Each sheet contains four **320×240 frames at 1×**, with a **3× nearest-neighbour HUD crop** beneath each: light floor / NEW, dark floor / NEW, light floor / CLASSIC, dark floor / CLASSIC. Sheet labels sit outside the game image. Individual frames and crops are included, named by option, floor and font. `thresholds-index.png` compares empty, 49%, 50%, full and active hunger states; its crops are also 3×.

Screens are genuine PCSX-Redux field captures with only the proposed HUD composited. The emulator ran with original 2 MB RAM. Capture preparation used runtime data changes to select maps, time and representative care values, and `modSetFont(0/2)` for NEW/CLASSIC. A temporary emulator breakpoint moved the existing HUD's slide offset offscreen to capture the floor underneath; no background was painted over or reconstructed. The HUD was drawn in integer pixels at native resolution before making enlarged crops.

The capture disc is an existing full multilingual v0.0.1 build fixture, rather than a new build of this branch. Its field HUD textures and geometry are the basis of this comparison. These images establish layout and font independence, not the runtime behaviour of an implemented four-gauge HUD. Raw captures, VRAM dumps, the compositing script and a frame checksum manifest are retained in the untracked review directory `build/hud-design/`.

## Shared visual rules

The existing field HUD uses screen coordinates x=235..309, y=203..225. Its draw coordinates are centred: `STATUS_UI_OFFSET_X=75`, with the screen origin added at (160,120). Existing frames are 75×8, drawn at y=205 and 217; 11×11 face icons begin at y=203 and 215. All five proposals fit that same 75×23 bounding rectangle. Keep its slide-in/out and suppression during menus and battles.

No names, numbers or translated text appear inside the proposed HUD. Long partner names cannot affect its layout. NEW and CLASSIC therefore use the same glyph-free geometry and textures.

- Happiness: existing smiling/angry face; normalise internal −100..100 to 0..100. Red below 50%, green from 50%, matching the status screen and current field bars.
- Discipline: existing disciplined/undisciplined face; 0..100, red below 50%, green from 50%.
- Hunger: existing meat icon. Proposed **meal countdown**, not a fabricated percentage of stomach contents. A green bar drains towards the next hunger event; once hungry, a red bar drains through its grace period. The existing hunger bubble remains authoritative and visible.
- Tiredness: existing blue tired-condition icon from the status screen; direct 0..100, green below 50%, red from 50%. It grows with fatigue, exactly as the status screen does. It must not silently become a remaining-stamina gauge.

Colours follow `renderMenuStatusBar` and `renderStatusBarFill`: green base RGB(48,200,40), red RGB(224,48,40), lighter upper edge, grey RGB(112,112,112)/(88,88,88) track. A, D and E reuse the native silver/blue frame texture, with two flat dark rows masking its baked blue track before drawing the independent fills. B and C give the two-pixel tracks a one-pixel dark outline. Empty tracks remain visible.

Native texture sources, from texture page 5:

| Icon | UV and CLUT | Destination |
| --- | --- | --- |
| Happiness | (64,244), negative (97,244); CLUT (96,503) | 11×11 |
| Discipline | (22,244), low (33,244); CLUT (96,498) | 11×11 |
| Meat | (72,140), 12×12; CLUT (96,488) | 11×11 nearest sampling |
| Tiredness | (108,140), 12×12; CLUT (96,489) | 11×11 nearest sampling |

The meat and tiredness icons already exist in the field-resident texture page; no new pixel art, font glyph or texture upload is needed. C deliberately compresses all four source icons to 7×5 to demonstrate the readability cost of four rows.

### Hunger is a countdown, with two phases

For this design, green fill is `clamp(foodLevel, 0, 180) / 180`: a fixed three-game-hour lookahead, full for anything longer. This avoids storing a guessed meal-interval denominator and behaves sensibly when entering a map or loading a save halfway through an interval. Once `condition & 4` is active, red fill is `clamp(starvationTimer, 0, 180) / 180`. This refill at the phase change is deliberate: a new, red grace countdown begins. The green/red transition is based on the hungry flag, not the 50% colour rule used for happiness and discipline.

`tickHungerMechanics` supplies these timers and the hungry bit. Energy reserve is a separate input to the game's eventual care-mistake decision; the red timer does **not** promise that expiry always awards a care mistake. Feeding, sleep, evolution and loading must refresh from the game's live fields. No new timer or gameplay timing is proposed. This meaning needs playtesting before implementation is accepted.

The ordinary comparison uses happiness 76, discipline 32, meal countdown 44%, tiredness 68. State sheets additionally show 0/49/50/100 and a red hunger grace countdown at 30%. Colours convey condition, while icon shape and stable placement identify each gauge.

## Options

| Option | Geometry within 75×23 | Precision at native scale | Readability and tradeoff |
| --- | --- | --- | --- |
| **A — framed 2×2** | Happiness above discipline on the left; meat above tiredness on the right. Column pitch 38; row pitch 12. Four 11×11 icons and 18×2 tracks over the current two 75×8 frames. | 18 fill steps, about 5.6 percentage points per pixel. | Best balance. Full-size icons survive, and the frame anchors all four readings on patterned floors. Low values still have only a few fill pixels. |
| **B — bare 2×2** | Same icon and bar positions as A; remove both long frames and outline each short track. | Same 18 steps. | Less silver UI, but each track looks detached. Dark outlines help on pale floors; the common housing in A groups the values more clearly. |
| **C — four thin rows** | Four rows at y offsets 0,6,12,18. Icons compressed to 7×5; tracks 59×2 with dark outline, beginning at x offset 14. | 59 steps, about 1.7 points per pixel. | Long bars read well, but the tiny faces, meat and tired symbol lose their identities. The 3× crop cannot repair native-size ambiguity. Reject for normal play. |
| **D — two rows + vertical needs** | Left pair retains 11×11 faces but shortens mood tracks to 28×2. Meat/tiredness icons sit above two 3×9 vertical fills on the right. Need columns 12 pixels apart. | Mood 28 steps (3.6 points); vertical needs only 9 steps (11.1 points). | Familiar left pair. The need gauges are coarse, visually unequal and require switching between horizontal and vertical reading. Shortening the existing mood bars is necessary to stay within the footprint. |
| **E — L1/R1 pages** | Keep two 50×2 tracks and full-size icons. Mood page: happiness/discipline. Needs page: meat/tiredness. Two tiny page lamps fit the trailing cap. | 50 steps, 2 points per pixel. | Clearest individual bars. Hunger/tiredness are hidden on the mood page, so it does not meet the strongest interpretation of “all four in real time”. Lamps are subtle; discovering the controls is a separate usability problem. |

For E, either L1 or R1 changes the pair once per button press, only during free field control; never steal those inputs from a menu, dialogue, battle or a held-Select shortcut. The default is mood, and page selection lasts for the session without a save-format change. Keep active condition bubbles on both pages. Do not add automatic page switching: it would move information while the player reads it. Input conflicts and discoverability are unresolved until implementation/playtesting.

## Cost estimates for an original 2 MB PlayStation

**Actual cost of this work: main 0 bytes, MENU 0 bytes, heap 0 bytes.** Only this document is committed. There is no new executable to measure, so no new `main_BSS_END` measurement or heapcheck result is claimed.

The following are conservative **planning allowances for a future implementation**, not compiler measurements. They assume sharing the existing bar helpers, reusing resident textures, calculating the countdown directly from existing fields, and adding no language strings, disc files, tables, persistent state or new options row. Main code is resident and consumes heap byte-for-byte after linker alignment. Field drawing code cannot simply live in MENU_REL: that overlay is not kept loaded in the field.

| Option | Extra resident main code allowance | Extra BSS allowance | MENU_REL delta | Estimated heap loss allowance, including alignment | New VRAM |
| --- | ---: | ---: | ---: | ---: | ---: |
| A | 1,024 B | 0 B | 0 B | 1,040 B | 0 B |
| B | 1,024 B | 0 B | 0 B | 1,040 B | 0 B |
| C | 1,024 B | 0 B | 0 B | 1,040 B | 0 B |
| D | 1,536 B | 0 B | 0 B | 1,552 B | 0 B |
| E | 1,792 B | 4 B for page state | 0 B | 1,808 B | 0 B |

These allowances are intentionally larger than the expected extra draw-call glue and include common countdown/clamping logic. They are neither measured predictions nor safe budgets to spend on tight maps. E also needs input routing and page-state lifetime management; D needs a separate vertical fill path. A new selectable layout setting or tutorial would add costs outside these assumptions.

GPU packet use is a separate consideration. With POLY_FT4 at 40 B and POLY_F4 at 24 B, the current two full bars use approximately 352 B per frame: two frame quads, two icon quads and eight flat bar rows. At full fill, A uses about 720 B including four dark masking rows; B/C about 640 B including four outline quads; D about 720 B including masking rows and four quads per vertical gauge; E about 496 B including masking rows and two page-lamp quads. These use the existing work buffer, rather than allocating a new heap block. Check the existing packet capacity and actual emitted packets; expanding that buffer would be another resident memory cost.

Before any C version is accepted: compare `main_BSS_END` before/after on the full multilingual build, record actual main/MENU sizes, run the normal full-build heapcheck without an override, and inspect the tightest map margins. Validate on original 2 MB settings with meals, hungry-grace expiry, feeding, sleeping, evolution, save/load and map changes. Check field/menu/battle suppression and packet capacity. For E, also verify shoulder-button conflicts. If the measured heap cannot afford it, stop and reduce or relocate an existing resident cost first.

## Visual review and limits

The supplied sheets were inspected at 1× and 3× on Freezeland snow (screen 92 at midday) and a dark Native Forest scene (screen 0 at night), with NEW and CLASSIC selected independently. A and B retain identifiable icons and visible empty tracks. C's icon compression is its limiting factor, especially the tired symbol. D's nine-pixel needs have too little resolution for small changes. E reads most like the existing HUD but requires an intentional page change. No layout touches the clock, wraps text or increases the HUD footprint.

The review includes both E pages and threshold samples. The crops magnify exact native pixels; they do not imply CRT readability. No console, CRT/composite-video, colour-vision accessibility, motion/flicker or implemented-input tests were performed. No C patch, full build or runtime heap validation was needed or performed for this design-only change. Choosing a design does not implement it.
