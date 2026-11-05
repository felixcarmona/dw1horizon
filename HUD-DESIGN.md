# Field care gauges: design review

Design only. No game code, patch, texture asset, option or save format changes.

**Owner direction: B, the bare grid with native icons and outlined thin bars, including toilet.** The current owner layout is **B5**: happiness and discipline in the left column; hunger, toilet and tiredness in the right column, all on matching grey icon blocks. **B5a** centres the left pair vertically; **B5b** top-aligns it. These are design-review variants, not approved implementations. Earlier B6/B4 follow-ups are retained below as history. The original A–E review below is retained as context; its initial recommendation was A.

## Owner layout B5: two mood rows beside three needs rows

`build/hud-design/HUD-B5-review.zip` contains `B5a-review.png`, `B5b-review.png`, eight individual native **320×240 frames**, their exact **3× nearest-neighbour HUD crops**, `B5-thresholds-3x.png`, icon blocks, a SHA-256 frame manifest and the reproduction script with its captured-floor dependencies. Each review sheet uses the established light/dark floor × NEW/CLASSIC format, with labels outside the game image. These reuse the original captured floors; the proposed HUD is an illustrative composite, not an implemented runtime capture. Ordinary readings remain happiness 76%, discipline 32%, hunger 44%, toilet 60%, tiredness 68%.

| Variant | Left column, top to bottom | Right column, top to bottom | Alignment |
| --- | --- | --- | --- |
| **B5a** | Happiness, discipline | Hunger, toilet, tiredness | Left blocks start at y=192 and 206; their 27-pixel span is vertically centred against the right column's 41-pixel span. |
| **B5b** | Happiness, discipline | Hunger, toilet, tiredness | Left blocks start at y=185 and 199, sharing the first two right-row baselines. |

Both use a **75×41 layout envelope, x=235..309, y=185..225**, preserving B's right/bottom anchors and width while extending 18 pixels upward. Right blocks start at y=185, 199 and 213. Column pitch is 38 pixels; row pitch is 14. Icon blocks start at x=236 and 274. Every icon has the same **13×13 grey block**: RGB(144,144,144) body, RGB(184,184,184) top/left bevel and RGB(64,64,64) bottom/right shadow. An unscaled 11×11 native glyph (or the previously proposed toilet glyph) sits one pixel inside it. The meat/tiredness sprites' baked grey backgrounds are removed in this offline composition before applying the common block; happiness, discipline and toilet receive the same treatment and housing. Both mood faces retain their high/low variants. This avoids shrinking the faces to make the grey border visible. A future renderer must reproduce the common housing without silently adding texture allocations; the existing baked icon backgrounds need an implementation audit.

Retain B's bare floor between gauges, **18×2 fill tracks** with a one-pixel dark outline, and 18 fill steps (about 5.6 percentage points per pixel). Tracks start 15 pixels right and 6 pixels down from their icon block. Fill is rounded to the nearest pixel, with a minimum of one pixel for any positive reading and a visible grey empty track at zero. No labels, numbers, font glyphs, sleep gauge or page switching are added. All five readings remain visible together; discipline also remains in the native menu.

B5 uses the exact live-data and colour contract below for hunger, toilet, tiredness, happiness and discipline, including the native hungry/POOPY flags and unchanged warning bubbles. Sleep is excluded. The threshold sheet covers empty, 49%, 50%, full and active needs for both alignments; colours use live thresholds before fill rounding. The centred and top-aligned variants differ only in the left column's vertical position.

**Delivery:** sent immediately through `mg-send` as session `2026-11-05-224210-upload-yJzVpd` (both review sheets, the threshold sheet and the ZIP). Reproduce from the repository root with a Pillow-enabled Python: `python build/hud-design/render-b5.py` after unpacking the ZIP there. Generated review material remains ignored; only this document is committed.

**Validation and cost:** eight frames checked at 320×240 with changes bounded by the 75×41 envelope; crop enlargement checked for exact 3× pixel replication. Both fonts and floors were visually reviewed, including the common blocks on the faces. This is design-only: actual executable/RAM/VRAM delta is **0 bytes**. The taller footprint needs runtime checks against other field overlays and existing slide/suppression paths. No build, CRT/motion test or heap measurement is claimed. For planning, five textured icons, five flat block backgrounds and five full outlined gauges would use approximately **920 B of GPU packets/frame** (568 B above the current two-gauge estimate), assuming one 24 B flat quad per background; bevel rendering may require more packets or a texture. The toilet alone retains the earlier 160 B padded-tile/CLUT allowance; common-block texture treatment and actual packet costs must be measured before implementation. Apply the full multilingual 2 MB build, heap, VRAM and care-state acceptance checks below to either B5 variant.

## Earlier B follow-up: B6 and B4

The separate `HUD-B6-B4-review.zip` package contains `B6-review.png` and `B4-review.png`, with the same review format as B: four native **320×240 frames at 1×**, light/dark floor with NEW/CLASSIC, and an exact **3× nearest-neighbour crop** under each frame. Individual frames/crops, `B-native-states.png`, `B-thresholds-3x.png`, the two new icon PNGs, a SHA-256 frame manifest, and the reproduction script are included. These reuse the original captured floors described below; the newly drawn gauges are illustrative composites, not runtime captures of implemented gauges. The ordinary values are hunger 44%, toilet 60%, tiredness 68%, happiness 76%, discipline 32%, sleep 35%, independent of the captured clock.

| Candidate | Row order, left to right | Footprint and precision |
| --- | --- | --- |
| **B6** | Top: hunger, toilet, tiredness. Bottom: happiness, discipline, sleep. | **81×23**, x=229..309, y=203..225: six pixels wider to the left, same right/bottom anchors as B. Column pitch 28, row pitch 12; full 11×11 icons, 10×2 fill tracks plus one-pixel dark outlines. Ten fill steps, about 10 percentage points per pixel. |
| **B4** | Top: hunger, toilet. Bottom: tiredness, happiness. | **75×23**, x=235..309, y=203..225, exactly B's footprint. Column pitch 38, row pitch 12; full 11×11 icons, 18×2 fill tracks plus one-pixel dark outlines. Eighteen steps, about 5.6 points per pixel. Discipline stays in the existing status menu only; no field sleep gauge. |

Both retain B's bare background and native colour treatment. Existing meat, tiredness, happiness and discipline sprites remain at 11×11; new toilet and staggered-Z sleep icons are hand-drawn 11×11 pixel art with dark contours, silver highlights and blue shadows. These are offline proposals, not new game texture uploads or a claim that a free VRAM slot exists. No image-generation or font rendering is needed for either icon. Keep native condition bubbles visible, including toilet and sleep warnings.

Every track has two grey interior rows even when empty and a dark one-pixel outline. Fill is left-to-right, rounded to the nearest pixel, with at least one pixel for any nonzero value; true zero is empty. At 1×, B6 sacrifices precision to retain recognisable full-size icons: it supports broad low/mid/high readings, not minute-level estimation. B4 gives each reading more resolution. The state material covers empty, 49%, 50%, full and active needs; thresholds use live values before pixel rounding, so 49% and 50% can share a fill length while changing colour. These remain subject to CRT/motion validation.

### Exact gauge contract

Here `clamp(v,a,b)` clamps a live value, and percentages below are conceptual; the renderer can calculate pixels directly. Recompute after meals, toilet use, rest, sleep, evolution, load and map changes. No interval start time, new timer or save field is required.

| Gauge | Live data source and displayed fill | Direction and colour |
| --- | --- | --- |
| Hunger | `PARTNER_PARA.foodLevel` from `tickHungerMechanics`: `clamp(foodLevel,0,180)/180`. While `condition & 4`, use `clamp(starvationTimer,0,180)/180` instead. | Green meal countdown **drains** towards hunger; full for 180+ game minutes remaining. When hungry, a new red grace countdown drains. Its phase reset is deliberate; it is not stomach fullness or a guaranteed time to a care mistake. |
| Toilet | `PARTNER_PARA.poopLevel` from `tickPoopingMechanic`, with species baseline `T = RAISE_DATA[PARTNER_ENTITY.digimonEntity.entity.type].poopTimer`. For `T>0`, fill is `1-clamp(poopLevel,0,2*T)/(2*T)`. If `condition & 8`, force full. Guard invalid `T<=0` with empty unless POOPY is active. | **Fills towards needs-to-go**, green before POOPY and full red while POOPY. `poopLevel` counts remaining ten-game-minute units; this is not the virus bar. A fixed `2*T` denominator handles native toilet/wild-poop reset to `2*T`; birth/evolution/portable potty resetting to `T` deliberately starts half full. Feeding, battles and time skips can advance it. No second phase or invented holding-time percentage: while POOPY, `poopingTimer` is a separate frame countdown and the native bubble remains authoritative. |
| Tiredness | `clamp(PARTNER_PARA.tiredness,0,100)/100`, as in the status screen. | **Fills with fatigue**; green below 50%, red at 50% and above. Rest/sleep reduces it. This is distinct from bedtime. |
| Happiness | `(clamp(PARTNER_PARA.happiness,-100,100)+100)/200`, matching the status screen. | **Fills with happiness**; red below 50% (raw value below 0), green from 50%. Use the native positive/negative face. |
| Discipline | `clamp(PARTNER_PARA.discipline,0,100)/100`. B5 and B6; still present in the menu in B4. | **Fills with discipline**; red below 50%, green from 50%. Use the native high/low discipline face. |
| Sleep | B6 only. If `condition & 1`, force empty red. Otherwise let `now=60*HOUR+MINUTE`, `bed=60*PARTNER_PARA.sleepyHour`, and `remaining=(bed-now+1440)%1440`; fill is `clamp(remaining,0,180)/180`. | Green **time-until-sleepy countdown drains** over the last three game hours; full earlier, empty red while SLEEPY. It does not show fatigue, sleep duration or a sleep-deprivation grace period. |

Sleep follows the effective hour boundary used by `tickSleepMechanics`: the current condition transition compares `HOUR`, not `sleepyMinute`, even though the schedule stores both and fatigue can update them. Thus the proposed countdown deliberately uses `sleepyHour:00`; using the stored minute would disagree with the actual bubble. A zero countdown remains zero at the boundary while waiting for the condition tick; the active flag takes precedence thereafter. Re-read the live schedule, including midnight wrapping and fatigue adjustments; do not predict tomorrow's schedule from a cached interval. If the game's sleep transition is later changed to honour minutes, update this contract and its boundary checks together. Sources: `decomp/src/main/partner_impl.c` (`tickHungerMechanics`, `tickPoopingMechanic`, `tickSleepMechanics`, `handleToilet`, `handleWildPoop`, `setSleepTimes`), native reset in `decomp/src/main/item.c`, and `docs/reference/partner.md`. Modded builds must use their live timers and species rows.

### B follow-up cost

**Actual executable/RAM/VRAM cost of this review: 0 bytes.** Only this document is committed. Images and scripts remain under ignored `build/hud-design/`; no game build, texture import, heapcheck or measured linker delta is claimed.

Planning allowances relative to the current two-gauge game HUD, not relative to B and not additive to the A–E estimates:

| Candidate | Extra resident main code allowance | Extra BSS | MENU_REL delta | Heap loss allowance including alignment | New icon VRAM allowance | Approximate full-fill GPU packets/frame |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| B6 | 2,048 B | 0 B | 0 B | 2,064 B | 320 B | 960 B (608 B above current) |
| B4 | 1,280 B | 0 B | 0 B | 1,296 B | 160 B | 640 B (288 B above current) |

The icon allowance assumes each new 11×11 icon reserves a padded 16×16 4-bpp tile (128 B) and one 16-colour CLUT (32 B): toilet for B4, toilet plus sleep for B6. Existing icons need no extra VRAM. Raw new image+palette payloads are correspondingly 160/320 B, before TIM/container and sector overhead; packaging and startup upload code need measurement. A resident RAM copy of either texture is **not** included or proposed: upload using existing startup scratch, then release it. If the chosen loader retains a copy, count that against heap too. VRAM placement and CLUT space must be audited before accepting the implementation.

Each bare gauge assumes one 40 B textured icon quad and five 24 B flat quads (outline, two track rows, two fill rows), giving 160 B at full fill. Actual empty rows may emit fewer packets. These packets consume the existing frame work buffer; any required capacity increase adds resident cost beyond the table. No persistent page state, input routing or new menu option is assumed. Reuse existing menu discipline rendering in B4.

Before implementation acceptance, apply the original 2 MB full multilingual build/linker/heapcheck requirements below, audit packet and texture capacity, and validate toilet resets (including portable potty), POOPY holding/expiry, meals, hungry grace, rest, sleep across midnight, fatigue-adjusted bedtime, evolution and save/load. Confirm the six-pixel leftward extension clears other field overlays and the slide/suppression paths. These are design allowances, not measured free space.

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
