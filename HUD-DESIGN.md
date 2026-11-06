# Field care HUD: B5a implementation and design history

The project adopted **B5a** on 2026-11-06. It is implemented under the existing **NEW STATUS BARS** option; OFF retains the original field bars. The review material below is historical design evidence.

**Selected direction: B, the bare grid with native icons and outlined thin bars, including toilet.** The selected layout is **B5**: happiness and discipline in the left column; hunger, toilet and tiredness in the right column, all on matching grey icon blocks. **B5a** centres the left pair vertically; **B5b** top-aligns it. B5a is the approved implementation; B5b remains a design-review variant. Earlier B6/B4 follow-ups are retained below as history. The original A–E review below is retained as context; its initial recommendation was A.

## Implemented B5a

The implementation uses **toilet icon 4**, the game's native toilet-need/poop
condition graphic, selected on 2026-11-06. The atlas generator reads the complete 16×16
frame from ETCTIM entry 3 (texture page 63, UV 208,144; CLUT 272,483) and fits it
to the existing 11×11 glyph area with nearest sampling. It retains the common
13×13 grey housing and replaces the proposed drawn toilet. Only the existing
toilet tile and its CLUT row change: 126 bytes in the same 125,632-byte ETCTIM
file. No resident artwork, buffer, upload or allocation is added.

The icon-4 follow-up merges `origin/main` at **78dff7bc** first. The merged
renderer initially left screen 207 **16 bytes over budget**. Extending its
existing coordinate table with the row positions removes repeated coordinate
arithmetic and saves **32 resident bytes**, preserving every gauge calculation
and OFF GPU call. The final nine-language build has `main_BSS_END`
**0x801ced58**, heap **184,736 B**, and all **320 actual-archive setups pass**.
Screen 207 remains tightest: peak **184,712 B**, available **184,728 B** after
allocator overhead, margin **16 B**. MENU is **53,860 B**. Every language has
the same endpoint. The icon itself changes only the existing asset data.

Localization now produces the combined field HUD and quick-care artwork in
both translated and English-only builds; the title step no longer supplies a
competing ETCTIM file. The merge also required deduplicating three patch-series
entries and using the already-reviewed effect-context patch from 5287b830,
which reconciles the overlapping quick-battle guards. All 390 patches apply.

`Render-the-B5a-field-care-HUD-from-live-partner-data.patch` replaces the ON renderer with five live gauges. Happiness/discipline blocks start at (236,192)/(236,206); hunger/toilet/tiredness at (274,185)/(274,199)/(274,213). Each block is 13×13, every outlined track has 18 fill steps, and the existing tick-owned slide supplies the horizontal anchor. The native warning bubbles remain active. Both mood icons use their high/low variants. No input handling, save field or timer is added.

The exact gauge contract below is used before pixel rounding, including final-hour warnings, full active needs, POOPY override, empty invalid toilet baseline, fatigue direction, clamping, nearest-pixel fill and minimum one pixel for positive readings. The current engine's `RAISE_ROW(type)` accessor supplies the toilet baseline, including imported species' live DIGI.DAT rows. The historical mockup script used a different meat crop; runtime uses the documented native meat crop (72,140), CLUT (96,488).

`tools/field_hud_art.py` derives seven combined icon-block/empty-track tiles and the native green/red fill stripes into previously empty cells of **ETCTIM.BIN entry 1**, at VRAM (960,448), texture page 31. CLUT rows (272,500..510) were empty. The generator checks both source and destination allocations and refuses occupied cells. The original command-label crops end at u=61; the finisher frame uses u=88..133,v=224..235 and its fill u=136..139,v=224..229. The new atlas avoids these rectangles and the upper condition icons. All existing pixels and palettes outside the reserved cells remain intact. Every localized ETCTIM copy receives the same atlas; no new disc file, upload, RAM copy or VRAM allocation is introduced.

### Need warning and active states

`blink-and-highlight-active-care-needs.patch` adds a one-Hz warning: the bar
alternates visible/empty every ten native play ticks (0.5 seconds), leaving its
icon, housing and empty track visible. `PLAYTIME_FRAMES` supplies the existing
20-Hz clock, including while gym game time is paused; no timer or saved state is
added. Active needs override blinking and rounding: their housing turns red and
their bar stays full red until the live condition clears.

Hunger warns when positive `foodLevel * MOD_CARE_HUNGER_FOOD_PERIOD <= 1200`;
toilet warns when positive `poopLevel * MOD_CARE_POOP_PERIOD <= 1200`. These are
one game hour at the live care periods, normally 60 hunger units or six toilet
units. Enabled timers reaching zero count as active even before the native flag
updates during a paused gym. Disabled timers do not invent warnings or due
states; existing native condition flags still take precedence. Invalid toilet
baselines remain empty unless POOPY is active.

Fatigue has no countdown. Its warning starts within six raw points of
`MOD_CARE_TIRED_EXHAUSTED_AT`, the last 18-step display interval. The default
threshold is 80, so values 74–79 blink; 80+ or the native exhausted flag is active.
The separate gym stop threshold of 70 is unchanged. Normal fatigue below active
still uses its native green/red split at 50. All three gauges re-read live care
data every draw, so meals, toilet use, rest and other resets need no HUD state.

Three additional palettes at (272,508..510) recolour only the housing's three
greys into red. The glyph inks and track stay intact. Existing atlas texels,
125,632-byte asset size, upload, VRAM allocation and ten-FT4/400-byte maximum
packet budget stay unchanged. The original OFF renderer has identical GPU calls
across 609,030 happiness/discipline/area/blink combinations after loop compaction.

### Need-alert memory measurements

The full nine-language build confirms `main_BSS_END` **0x801CED48**, down
16 bytes from the training-HUD baseline 0x801CED58. Main text is **509,488 B**
(−16); rodata/data/BSS remain **29,672 / 134,436 / 623,164 B**. The aligned heap
is **184,752 B** (+16), MENU remains **53,860 B**, and TRN/TRN2 remain
**29,400 / 23,668 B**. No new state, allocation, texture upload or packet capacity
is needed. All nine language endpoints match. Normal heapcheck passes without
an override, and all **320 actual-archive setups fit**; screen 207 has a
**32 B** minimum margin (184,712 B peak, 184,744 B after allocator overhead).

The independent actual-C checks cover 589,828 live-value/flag/baseline cases in
both blink halves and the complete original OFF GPU-call domain. The asset tests
verify that only the three housing inks change and that occupied palette rows
are rejected. All nine localized atlases match the derived normal/active tiles;
the complete 392-patch series applies cleanly.

### Need-alert runtime confirmation

The fresh nine-language disc (`d4e9e7327068f42a8c8cf68ea39c62ad104c0437`)
passed PCSX-Redux interpreter checks with exactly **2,097,152 bytes of RAM**.
Thirty-nine native **320×240** frames cover each need's normal, warning-on,
warning-off, active in both halves, and reset states; fatigue 100; NEW/30 and
CLASSIC/60; both fonts on a dark floor; and all three warnings during paused gym
training. Active bars remain 18 red pixels in both phases. Six consecutive
warning captures advance native play ticks **5503/5513/5523/5533/5543/5553**,
with care time fixed, confirming ten-tick half cycles. The paused-gym pair keeps
`IS_GAMETIME_RUNNING=0` while the same blink clock advances.

Representative care values/flags and the existing day-length rule were written
in RAM to select states. The renderer, palette selection and blink clock are
native; no HUD is composited and no blink counter is written. Reset captures
replace live care data and clear conditions, testing immediate redraw without
cached HUD state. Native meals/rest/toilet actions and real hardware/CRT motion
were not repeated in this follow-up.

Both real x5 HP training runs also pass on this disc (TRN NEW/30, TRN2
CLASSIC/60), with no care writes between awards. Tiredness rises
14/22/30/38/46/54; toilet fill grows 2/5/7/9/11/14 pixels. Final food values 10/5
lie inside the warning window and were captured in its empty half. Cancellation,
native hunger stop, learned-order/tally clearance, OFF and callback cleanup pass.
At the native hunger stop, food −10 and condition 0 already render a full red
hunger bar and red housing during paused training.

The reviewed sheets are `need-gauges-normal-blinking-active.png`,
`need-gauges-font-gym-reset.png`, `need-gauges-dark-floor.png`,
`TRN-five-session-sheet.png`, `TRN2-five-session-sheet.png` and
`training-ui-checks-sheet.png`. Each pairs native frames with exact 3× HUD crops.
They and the native-frame/evidence ZIP were sent with `mg-send`; generated
artifacts remain ignored under `build/need-alerts/`.

Reproduce with a Pillow-enabled Python:
`tools/dev/playtest/need_gauge_states.py DISC.cue --exe EXE --card AGUMON.mcd`.
Only reuse `--boot-state` with this exact disc. The existing
`tools/dev/playtest/training_care_hud.py` reproduces the x5 checks;
`field_hud_host.py TREE` checks the exhaustive live-value domain, and
`need_gauge_states_host.py TREE --before PREVIOUS.c` checks warning boundaries,
care-rule overrides, read-only state and the original OFF call sequence.

### Icon-4 runtime confirmation

`build/hud-icon4.cue` completed the full nine-language build without `HEAP_OK`
or a language subset; image SHA-1 is
`168ea26c8a35eaf0641372ba8e5c8ac032f1e196`. The final field asset comes from the
localized-assets manifest, with one producer for the shared ETCTIM upload.

PCSX-Redux's interpreter ran the fresh disc with exactly **2,097,152 bytes of
RAM**. All eight light/dark × NEW/CLASSIC × 30/60 FPS-mode combinations passed.
All sixteen ordinary/needs screenshots were visually reviewed at native
320×240 and with exact 3× HUD crops. Every screenshot's toilet block matches
the selected icon's native pixels after the emulator's 5-bit colour expansion.
The OFF, suppression and battle frames were also checked; battle ON/OFF frames
remain pixel-identical. Native toilet/portable-potty resets are 48/24 and rest
changes tiredness 70→40. No new motion clip was needed for this icon follow-up.

Validation also passed 589,828 actual-C gauge cases, 609,030 original OFF GPU-call
comparisons, 14 asset/UI tests, all nine localized atlas comparisons, full
390-patch application and `git diff --check`. Artifacts are under
`build/hud-icon4-runtime/`; build and heap logs are `build/hud-icon4-final.log`
and `build/hud-icon4/story-heap.txt`. The task emulator and Xvfb were stopped.

### Initial B5a measurements before the icon-4 integration merge

The initial full default multilingual build passed on 2026-11-06. A controlled relink swaps only the field renderer while retaining the final text banks, padding, species data, tables and file routes:

| Measurement | Original two-gauge ON renderer | B5a | Delta |
| --- | ---: | ---: | ---: |
| `main_BSS_END` | `0x801ced5c` | `0x801cecdc` | **−128 B** |
| Main text | 509,568 B | 509,424 B | −144 B |
| Main rodata, including alignment | 29,640 B | 29,656 B | +16 B |
| Main data/BSS sizes | 134,428 / 623,152 B | 134,428 / 623,152 B | 0 B |
| `malloc3` heap | 184,736 B | **184,864 B** | **+128 B** |
| MENU file size | 53,812 B | **53,812 B** | 0 B |
| Screen 207 margin | 16 B | **144 B** | +128 B |

The normal heapcheck passed without `HEAP_OK`: its tightest historical sweep projection is OGRE03 at 28,512 B. The actual-archive check passed **all 320 setups**, with zero negative margins. Screen 207 is tightest: Birdramon, Leomon and Hawkmon peak at 184,712 B against 184,856 B available after allocator overhead. This 144 B margin is small; keep checking the actual archive when code or models change.

The new renderer emits at most ten FT4 packets, **400 B/frame**, from the existing work buffer. This replaces the old flat-row helpers rather than retaining both ON renderers. No new persistent memory is allocated. The OFF renderer was compared against its original GPU-call sequence in 609,030 happiness/discipline/area-response/blink combinations. The actual ON C renderer passed 589,828 live-value/flag/baseline cases, including imported-species baseline changes. Asset allocation, common housing, fill colours and eight translated atlases were checked separately.

### Runtime verification and delivery

PCSX-Redux ran this full disc with original **2 MB RAM**. All eight NEW/CLASSIC × light/dark floor × 30/60 FPS runtime-mode combinations passed, with ordinary and active-needs native 320×240 screenshots for each. The log independently records `MOD_FONT` 0/2 and `MOD_FPS_MODE_RUN` 1/2. Both original OFF frames were inspected. The existing slide still reaches x-offset 240 when hidden and 75 when shown. JAPANESE CONTROLS has no role in the glyph-free HUD and no input routing was added.

Two 25-second motion clips use the NEW/light/30 and CLASSIC/dark/60 combinations. Care fixtures are written atomically, then native ticks consume the food and toilet timers. The native `handlePostBattleTiredness` event supplies +5 fatigue and its food cost. An awake-schedule fixture isolates this from bedtime. Native reset checks passed: toilet gives `2*T = 48`, portable potty gives `T = 24`, and `reduceTiredness(30)` changes 70 to 40. The clips' final hungry grace timers are 152/156, POOPY is active, and tiredness is 51 from 46.

All sixteen ordinary/warning frames, both OFF frames, suppression and battle frames were visually reviewed. Both videos decoded cleanly; their per-second HUD contact sheets were inspected, and all **1,194 decoded frames** were checked for gauge states: hunger green 1–2 pixels then red 18→16, toilet green 17→18 pixels then full red, tiredness green 8 pixels then red 9. The HTTP screen recorder samples up to 30 frames/s while the game uses the selected 30/60 FPS runtime modes. A real wild-battle checkpoint produced **pixel-identical ON/OFF frames** six GPU swaps after restore; the native battle command/HP/MP/enemy bars remain intact.

The two runtime review sheets, both motion clips, a battle capture and the native-frame/reproduction ZIP were sent with `mg-send` (six files). Local evidence is under ignored `build/hud-runtime/`, with the full build at `build/hud-baseline.cue` (image SHA-1 `4cab78257afbf857638322c21fd79fc0c8384bf9`) and controlled memory evidence under `build/hud-budget/`. The task's emulator and Xvfb were stopped after verification.

## Selected layout B5: two mood rows beside three needs rows

`build/hud-design/HUD-B5-review.zip` contains `B5a-review.png`, `B5b-review.png`, eight individual native **320×240 frames**, their exact **3× nearest-neighbour HUD crops**, `B5-thresholds-3x.png`, icon blocks, a SHA-256 frame manifest and the reproduction script with its captured-floor dependencies. Each review sheet uses the established light/dark floor × NEW/CLASSIC format, with labels outside the game image. These reuse the original captured floors; the proposed HUD is an illustrative composite, not an implemented runtime capture. Ordinary readings remain happiness 76%, discipline 32%, hunger 44%, toilet 60%, tiredness 68%.

| Variant | Left column, top to bottom | Right column, top to bottom | Alignment |
| --- | --- | --- | --- |
| **B5a** | Happiness, discipline | Hunger, toilet, tiredness | Left blocks start at y=192 and 206; their 27-pixel span is vertically centred against the right column's 41-pixel span. |
| **B5b** | Happiness, discipline | Hunger, toilet, tiredness | Left blocks start at y=185 and 199, sharing the first two right-row baselines. |

Both use a **75×41 layout envelope, x=235..309, y=185..225**, preserving B's right/bottom anchors and width while extending 18 pixels upward. Right blocks start at y=185, 199 and 213. Column pitch is 38 pixels; row pitch is 14. Icon blocks start at x=236 and 274. Every icon has the same **13×13 grey block**: RGB(144,144,144) body, RGB(184,184,184) top/left bevel and RGB(64,64,64) bottom/right shadow. An unscaled 11×11 native glyph (or the previously proposed toilet glyph) sits one pixel inside it. The meat/tiredness sprites' baked grey backgrounds are removed in this offline composition before applying the common block; happiness, discipline and toilet receive the same treatment and housing. Both mood faces retain their high/low variants. This avoids shrinking the faces to make the grey border visible. A future renderer must reproduce the common housing without silently adding texture allocations; the existing baked icon backgrounds need an implementation audit.

Retain B's bare floor between gauges, **18×2 fill tracks** with a one-pixel dark outline, and 18 fill steps (about 5.6 percentage points per pixel). Tracks start 15 pixels right and 6 pixels down from their icon block. Fill is rounded to the nearest pixel, with a minimum of one pixel for any positive reading and a visible grey empty track at zero. No labels, numbers, font glyphs, sleep gauge or page switching are added. All five readings remain visible together; discipline also remains in the native menu.

B5 uses the exact live-data and colour contract below for hunger, toilet, tiredness, happiness and discipline, including the native hungry/POOPY flags and unchanged warning bubbles. Sleep is excluded. The threshold sheet covers empty, 49%, 50%, full and active needs for both alignments; colours use live thresholds before fill rounding. The centred and top-aligned variants differ only in the left column's vertical position.

**Delivery:** sent immediately through `mg-send` (both review sheets, the threshold sheet and the ZIP). Reproduce from the repository root with a Pillow-enabled Python: `python build/hud-design/render-b5.py` after unpacking the ZIP there. Generated review material remains ignored; only this document is committed.

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
| Hunger | `PARTNER_PARA.foodLevel` from `tickHungerMechanics`: `clamp(foodLevel,0,180)/180`. While HUNGRY, force full. | Green meal countdown **drains** towards hunger; full for 180+ game minutes remaining. Blink during the final game hour. While hungry, hold full red with a red icon housing until satisfied; this is not stomach fullness or a care-mistake countdown. |
| Toilet | `PARTNER_PARA.poopLevel` from `tickPoopingMechanic`, with species baseline `T = RAISE_ROW(PARTNER_ENTITY.digimonEntity.entity.type).poopTimer` (native `RAISE_DATA`, imported species through the live record accessor). For `T>0`, fill is `1-clamp(poopLevel,0,2*T)/(2*T)`. If `condition & 8`, force full. Guard invalid `T<=0` with empty unless POOPY is active. | **Fills towards needs-to-go**, green before POOPY; blink during the final game hour, then hold full red with a red icon housing while POOPY. `poopLevel` counts remaining ten-game-minute units; this is not the virus bar. A fixed `2*T` denominator handles native toilet/wild-poop reset to `2*T`; birth/evolution/portable potty resetting to `T` deliberately starts half full. Feeding, battles and time skips can advance it. No second phase or invented holding-time percentage: while POOPY, `poopingTimer` is a separate frame countdown and the native bubble remains authoritative. |
| Tiredness | `clamp(PARTNER_PARA.tiredness,0,100)/100`, as in the status screen. | **Fills with fatigue**; green below 50%, red at 50% and above. Blink within the last six raw points before the live exhausted threshold (normally 74–79 before 80). While exhausted, hold full red with a red icon housing. Rest/sleep reduces it. This is distinct from bedtime. |
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
