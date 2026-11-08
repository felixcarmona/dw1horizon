# HP and MP care bubbles

HP and MP are care needs strictly below 30%: `current * 10 < maximum * 3`, with a positive maximum. At exactly 30%, no resource bubble or resource-only Square hint appears. The need is independent of inventory: low resources still show their bubbles with an empty bag. Square needs an available action, as it does for the other conditions.

Square can still open the care menu above the threshold when the bag has a field-usable recovery item for a resource that is not full. Those optional recovery entries sort after the actual needs. Critical recovery retains its existing place before sleep; other care actions keep their priorities. Opening or cancelling the list does not consume an item.

## Pixel art and native layout

For v0.0.8, HP and MP use the game’s native battle HUD heart and MP orb, with
only their bottom approximately 30% coloured. The upper coloured texels become
an empty graphite shade, RGB5 `(10,10,11)`, distinct from the black outline.
Transparency, native outlines and lower red/blue pixels are preserved. The
existing battle HUD itself is unchanged. These are static low-resource icons;
there is no extra percentage state, label band, recovery disk or text.

The 11×11 sources come from ETCTIM entry 0 at `(144,48)` and `(155,48)`, using
palette `(256,491)`. `tools/care_bubble_art.py` derives them into the existing
16×16 cells `(224,0)` and `(224,16)` of entry 1, uploaded at `(960,448)`.
FEEL_EF CLUT rows 13/14 hold their palettes; the standalone FEEL_EF repeats them
so its ordinary upload cannot erase the private colours. Occupancy is **320 B**,
replacing the prior disk/label version’s 448 B. Upload/file sizes stay fixed;
no new file, bitmap array, buffer or allocation is added.

The renderer uses an 11×11 descriptor and 7/4 scale, giving a 19.25-unit icon
inside the native 26-unit circle. The existing 205/256 bubble scale, anchor,
animation, row spacing, tail suppression and Square overlay are unchanged.
One condition has a tail; two share a row without tails; three or more use the
existing two-row layout. Two resources still add four ordinary textured quads,
up to 160 command bytes per frame in the existing packet buffers.

See [HPMP-REDESIGN.md](HPMP-REDESIGN.md) for the design history and current
implementation evidence. The resident-memory tables below describe the earlier
resource feature and disk/label iterations; the new icon patch’s measurements
are recorded separately with its patch index row.

## Maximum simultaneous conditions and screen edges

The maximum ring contains eight bubbles: hunger, toilet, sleep, tiredness, sickness, injury, HP and MP. The unhappiness effect is a separate butterfly, selected only when the condition word is exactly `0x10`; it does not add a ninth bubble to this combination. Horizon's simultaneous condition display keeps every active bubble in a fixed slot. It animates the icons and bobs the group; it does not cycle away active conditions.

The eight bubbles occupy two rows of four at the existing spacing and size. The existing top clamp covers both rows. At a side edge the complete group now moves inward, including room for Square, with a three-pixel screen inset. Near the upper-left corner it also clears the visible sliding clock and its digital plate. Clock clearance uses the fixed HUD origin at x = 160; world-camera panning changes the bubble drawing offset independently. Bubble-to-bubble and bubble-to-badge offsets remain unchanged. The badge calculation itself is the legacy v0.0.6 lower-right calculation; the source was rebased after its verification landed on main.

The before capture measured horizontal clipping at x = −27 on the left and x = 357 on the right. Centre and top fit; the top corners also clip horizontally, and the left-side cases overlap the visible clock. `tools/dev/playtest/hpmp_extremes.py` holds a partner-position fixture while ordinary condition and rendering code run, observes every emitted textured GPU packet, and records every presented native frame with its vblank timing. Its after run verifies all eight conditions and Square on every recorded frame, checks the complete GPU bounds inside 320×240 and checks clearance from the clock. The clock/status HUD remains visible; a RAM fixture freezes the clock rule to isolate the conditions without hiding the HUD.

On the final disc, six positions each passed 120 recorded frames: **720 frames on 2,097,152 bytes of RAM**. Every frame kept all eight conditions and Square. The measured GPU bounds, including animation and bob, are:

| Partner position | Before bounds (x/y) | Final bounds (x/y) |
|---|---|---|
| Centre | `(126,53)–(201,87)` | `(125,53)–(200,86)` |
| Left | `(−27,53)–(56,87)` | `(75,52)–(150,86)` |
| Right | `(274,52)–(357,86)` | `(241,52)–(317,86)` |
| Top | `(126,6)–(196,36)` | `(127,6)–(197,36)` |
| Top-left | `(−28,6)–(45,36)` | `(76,6)–(144,36)` |
| Top-right | `(276,6)–(349,36)` | `(247,6)–(317,36)` |

The left-side positions also clear the visible clock. The before/after video preserves captured presentation timing, with an integer 2× display enlargement; the stills retain native pixels and separate exact 4× crops.

The host comparison exercises **194,400 layouts**: zero through eight bubbles, left/centre/right origins, growing and moving slots, four projected scales, every badge phase, three vertical positions and the clock hidden/visible and five independent world-camera offsets. It checks all positions and badge sizes against the legacy calculation, with the same group clamp, and checks the screen bounds.

## Resident memory

The field collector and mutable care state remain resident. The care menu's existing note routine, note strings and command captions move to MENU_REL. `feedOpen` loads MENU before reading them. The resident closing/giving paths restore the curling overlay through `closeMenuOverlay` before resuming field activity. The asynchronous care callbacks stay in main, so returning from a menu cannot return into an overwritten overlay.

The feature-only comparison, before permanent HUD integration, uses identical flags, generated headers and all nine padded language banks:

| Stage | main_BSS_END | Heap | MENU_REL |
|---|---:|---:|---:|
| Before recovery bubbles | `0x801CE5E0` | 186,640 B | 53,860 B |
| Resource needs and disks | `0x801CE780` | 186,224 B | 53,860 B |
| Care notes/captions in MENU | `0x801CE52C` | 186,832 B | 54,484 B |
| Viewport and clock clearance | `0x801CE67C` | 186,496 B | 54,484 B |
| Wider MP label descriptor | `0x801CE69C` | 186,464 B | 54,484 B |

The resource patch costs 416 resident bytes; moving existing UI routine/data into MENU saves 596 B; viewport/clock protection costs 336 B; the wider MP descriptor costs 32 B. Combined resident growth is **188 B**, and aligned heap decreases **176 B**. No BSS is added: it remains **621,116 B**. Final main text/rodata/data are **510,016 / 29,656 / 134,264 B**. MENU grows 624 B overall, retains **27 sectors** and stays within its linker read bounds. Normal heapcheck passes without an override; all **320 actual-archive screen setups fit**, with a tightest margin of **1,744 B on screen 207**.

The generated care-art cells and palettes match byte-for-byte across all nine language atlases, for the shared resource icons. ETCTIM remains 125,632 B in every language. The eight generated common FEEL copies match the same private palettes, with no foreign FEEL duplicates.

## Permanent HUD integration

The full nine-language build with the permanent HUD, status portrait anchor and
bounded damage curve measures `main_BSS_END = 0x801CDF7C`, heap **188,288 B**
(**+1,824 B** against the feature-only build). MENU is **54,324 B / 27 sectors**;
main BSS is **621,096 B**. All **320 actual-archive setups** fit, with a tightest
margin of **3,568 B on screen 207**. Standard heapcheck passes without an override.

The retired status-bars, digital-clock and enemy-bars runtime options stay
removed. Their saved bytes retain the permanent-HUD compatibility handling.
HP/MP thresholds, optional recovery, item-independent bubbles and the legacy
lower-right Square offset are preserved. The hand-pixelled icons and private
palettes match across all nine atlases and the common condition uploads.
A fresh 2 MB boot also verifies HP and MP at 29% plus hunger and Square with
the permanent HUD and digital clock visible; the native frame and exact 4× crop
were inspected. The retired runtime option symbols are absent from that executable.
The integrated toolchain selftest passes **120 groups, zero failed and zero
skipped groups**.

## Native verification

The feature’s 2 MB PCSX-Redux proof covers: HP 29% and MP 29% each show their bubble and Square; 31% and exactly 30% show neither. HP + MP + hunger use the existing two-row layout. With an empty bag both resource bubbles remain and Square disappears. At 31% the care menu still offers recovery; critical MP sorts before optional HP. Using one sm.recovery raises HP from 29% to 79% and clears the HP bubble.

Field and menu captures pass in both fonts for English, Spanish, Brazilian Portuguese, French, German, Italian, Japanese and Catalan. The native PNGs and exact 4× crops were inspected. All **119 selftest groups** are verified: 118 passed in the full run; the story reproduction group passed on rerun after correcting stale authored-story pins. Its four authored-story regression tests also pass. Physical console testing remains outstanding; Simplified Chinese retains its existing 8 MB requirement and was checked through the full build and shared-art comparison.

## Reproduction

- Full disc: `ISOS=/path/to/dw1 SOURCE_ISOS=/path/to/isos python3 -m tools.dev build --jobs 8 --name hpmp-bubble`.
- Source workflow: `tools/mods.sh prepare int`, commit changes in the private prepared tree, then `tools/mods.sh save int` and `python3 tools/patch_series.py check --apply`.
- Care logic: `python3 tools/dev/playtest/hpmp_care_host.py build/decomp-dev` and `python3 tools/dev/playtest/quick_care_host.py build/decomp-dev`.
- Art allocation/preservation: `python3 -m unittest tools.test_care_bubble_art tools.test_care_badge`.
- Native proof: `python3 tools/dev/playtest/hpmp_bubbles.py DISC.cue --exe EXE --card AGUMON.mcd --out build/hpmp-proof`. This boots the tested executable on 2 MB RAM, captures 29/30/31% cases, combined hunger/HP/MP, an empty bag, optional/critical care ordering, and menus in both fonts across the eight 2 MB languages. It records exact rendered bubble anchors for the 4× crops.
- Maximum conditions: `python3 tools/dev/playtest/hpmp_extremes.py DISC.cue --exe EXE --card AGUMON.mcd --fixture build/hpmp-proof --out build/hpmp-extremes-after --port 38865`. The fixture hash must match the tested executable; an old executable’s state is refused.
- Complete toolchain: `DW_SELFTEST_DERIVE=build/hpmp-bubble tools/selftest.sh`.

The native evidence, raw PNGs, 4× crops and machine-readable results stay local under `build/hpmp-proof-wide/` and `build/hpmp-extremes-wide/`. Disc-derived pixels are not committed.


## Earlier v0.0.8 dark-icon verification

The selected 4a heart/orb replacement builds in all nine language atlases, with
identical resource pixels and palettes and unchanged upload sizes. Compared with
the immediately preceding disk/label renderer under identical language padding,
`main_BSS_END` falls from **0x801CE104 to 0x801CE0F4**, saving **16 resident bytes**.
Aligned heap grows from **187,888 to 187,904 B**. Normal heapcheck passes and all
**320 actual-archive screen setups fit**, minimum **3,184 B on screen 207**.
Art occupancy falls from **448 to 320 B** inside existing uploads; there is no
new allocation, persistent state, file, or GPU quad.

A fresh native 2 MB proof passes 29/30/31% resource boundaries, combined needs,
empty inventory, recovery sorting and recovery use. Six maximum-group positions
pass **720 presented frames** with all eight conditions and Square inside the
viewport and clear of the clock. Every recorded frame retains at least **9 red
HP pixels and 14 blue MP pixels**, with a distinct empty grey region. The
inspected native/4× sheet is `build/hpmp-4a-proof/HPMP-4a-2MB-sheet.png`.
See [HPMP-REDESIGN.md](HPMP-REDESIGN.md) for commands and complete evidence.
Physical hardware remains untested.

The complete standard selftest passes **128 groups, 0 failed, 0 skipped**,
including applying the entire unnumbered patch series to the pinned decomp.

## Faded native resource icons

Proposal 4 supersedes the dark 4a art. The upper heart/orb region now has pale
native shading with a dark outer contour; a bright saturated lower third makes
the low state visible. The fixed 320-byte atlas/palette allocation, native
silhouettes, resource thresholds, bubble layout and Square badge are preserved.
See [HPMP-REDESIGN.md](HPMP-REDESIGN.md#current-implementation-proposal-4-faded-native-colour)
for the current implementation and its verification.

The faded revision passes the full nine-language build, unchanged 187,904 B
heap, all 320 actual-archive setups, fresh 2 MB proof including 720 edge frames,
and the complete 128-group selftest. Its inspected native/4× sheet is
`build/hpmp-faded-proof/HPMP-FADED-2MB-sheet.png`.
