# Square quick care

Status: icon 1 selected and implemented. Field quick care uses physical Square;
Confirm remains field interaction. Validation measurements are recorded below.

## Field behavior

Square opens quick care from anywhere on the current field map. The partner does
not have to be nearby or face the tamer. Opening the list never consumes an item;
the ordinary confirm button gives the selected item or executes the selected care
command. Circle with JAPANESE CONTROLS ON, or Cross with it OFF, remains the field
interaction button. This separates care from talking, training and using machines.

The artwork decision changes **only the icon**. The existing care badge keeps
its exact anchor, projected size, bob, fade, visual suppression and three-frame
press timing. Care availability gains distance/facing independence as described
above. There is no HUD badge, hint row, edge clamp,
offscreen fallback or extra prompt text. Earlier A/B/C placement alternatives are withdrawn.
The field input change above is implemented only in ordinary field walking control.

Selected **1, native round cap**: the familiar gray button with a pink Square.
Options 2–4 change only cap shape, outline or face shading within the same texture
box. No option adds prompt behavior or changes the care list.

## Existing prompt: asset and drawing path

The floating round cap in `report-circle-prompt.png` matches the **quick-care
badge**, not a general marker proving an NPC or doorway can be interacted with.
Its round outer silhouette is the physical button cap; the colored mark on its
face identifies the input. The variants below change its artwork to identify Square.

The authoritative sources are the patches in `mods/patches/series`:

- `Patch-0158-X-badge.-The-dialogue-box-s-X-button-rend.patch` adds
  `bubble.c:renderBadge`, called from `renderConditionRing`.
- `Patch-0167-OPTIONS-in-the-title-menu-JAPANESE-CONTRO.patch` routes its
  palette through `modButtonClut`.
- `Patch-0241-on-a-Japanese-base-disc-JAPANESE-CONTROLS.patch` detects native
  Circle/Cross artwork and provides the alternate layout's frames.
- `Let-the-care-menu-win-over-nearby-machines.patch` established the previous
  Confirm priority by moving `modFeedTick` ahead of `checkMapInteraction`.
- `Use-Square-for-field-quick-care-with-a-separate-pink-badge.patch` restores
  map-interaction priority and gives physical Square exclusive ownership of field
  quick care, with separate artwork. Menu and battle input handlers are unchanged.

Asset: disc-derived `ETCDAT/SYSTEM_W.TIM`, 4-bit indexed UI texture page based at
VRAM `(320,128)`. Three **16×12 texel** frames occupy texture UV
`(0x4c + 16*frame, 0xb7)`. Within that TIM they occupy rows 55–66 and
VRAM-word columns 19–30. The native CLUT is `(96,500)`. This is also the dialogue
box's animated confirm cap in `script_textbox.c:renderUIBox`.

The native USA palette has a gray face `(88,88,88)`, gray shading from
`(24,24,24)` through `(160,160,160)`, transparent index 8, and Cross ink
`(96,176,240)` / `(72,96,136)`. The layout adapter uses indices 12/13 and a
private CLUT at `(352,230)`: generated Circle `(248,96,104)` /
`(160,48,56)`, generated Cross `(112,176,248)` / `(64,96,208)`.
A Japanese base retains its native orange Circle when Japanese controls are ON;
changing layout generates blue Cross. Do not recolor the existing confirm cap
when adding Square.

`renderBadge` submits a `POLY_FT4`, neutral RGB modulation `(128,128,128)`,
semitransparency enabled, texture page `GetTPage(0,1,320,128)`, one ordering-table
slot in front of the condition ring. It cycles the three frames with
`(MOD_RING_CLOCK / 4) % 3`. Source size is 16×12; on-screen size is multiplied by
the ring's world projection and its entry/exit scale, so **16×12 is not a promise
that the existing world-space badge always occupies 16×12 screen pixels**.

The anchor follows the partner's root and model height, with the condition row's
bob, beside the bottom row's right edge. With no condition bubble it appears at
the ring anchor. `MOD_FEED_HINT` grows/shrinks it over four game ticks (0.2 s at
20 Hz). The condition-ring renderer also hides it in menus, outside field state,
with unsuitable partner states, and when the condition-ring option is disabled.

Before this change, `mod_feed.c:modFeedTick` required normal tamer and partner states,
script idle (`IS_SCRIPT_PAUSED == 1`), no fade protection, both care boxes fully
closed, no held world item, a nonempty care list, and `feedPartnerAhead()`.
That last test requires ±45 degrees and the item-take distance plus 12, capped
at 127 before `checkEatDistance`. The Square shortcut removes this last test;
the other guards remain, with an explicit field/battle ownership check.

## Four icon variants, one unchanged prompt

Every variant occupies the existing **16×12 texel canvas**, with transparent
surrounding pixels. The game's existing projection determines its screen size;
none forces it to 16×12 screen pixels. Each supplies three pressed-state frames
for the existing `(MOD_RING_CLOCK / 4) % 3` cycle. The same ring anchor and draw
quad are used; neither the icon's center nor its world height is moved.

| Variant | Artwork | Readability and tradeoff |
|---|---|---|
| **1 — Native round cap (recommended)** | Original shaded round gray cap; its face mark becomes a 6×5 perspective pink square | Closest match to the report image and existing pixel art. Dark rim separates it from light floors; gray bevel separates it from dark floors. |
| **2 — Square cap** | Squared gray button with a beveled light top/left edge, dark base and pink Square | Strongest square silhouette. Uses the same 16×12 canvas and anchor; the cap's outline is intentionally squarer within that box. |
| **3 — Outlined Square** | Original round cap with a pale pink Square and a one-pixel dark separator around the mark | Most conspicuous symbol at small scale; a heavier face than variant 1. |
| **4 — Recessed face** | Original round outer silhouette with a darker inset face, pink Square and reversed light/dark inner edge | More subdued cap with a clear pink mark. The face appears recessed in every frame; this is artwork, not a disabled/unavailable state. |

All retain integer pixels and the native gray bevel palette. Symbol colors are
PS1-representable **(248,128,192)** pink and **(160,64,120)** dark pink; variant 3
also uses **(248,192,224)** pale pink. Gray/black values come from the native UI
palette, including `(24,24,24)`, `(48,48,48)`, `(64,64,64)`, `(88,88,88)`,
`(104,104,104)`, `(136,136,136)` and `(160,160,160)`. No smoothing or new font is
used. The 6×5 mark is perspective-compressed like the original Circle/Cross mark;
the cap remains 16×12 in all three frames.

**JAPANESE CONTROLS ON and OFF use identical Square artwork for all four variants.**
Square is a physical button in both layouts and must bypass Circle/Cross glyph
substitution. NEW, CLASSIC, ORIGINAL and all language fonts therefore also show
identical icon pixels. No duplicate layout/font mockups or translations are needed.
The existing confirm glyphs and their layouts remain separate.

The image files are numbered 1–4. Each review sheet contains the icon on a light
floor and a dark floor at the game's actual rendering scale, plus a 4× source
zoom of the three animation frames. The zoom is explicitly outside the game
screenshot. Native full-screen PNGs are also supplied for each floor. The source
canvas zoom is 64×48 pixels; it does not imply the projected badge always has that
size divided by four on screen.

## Position and behavior constraints

Use the existing `renderBadge` call, its root/condition-row anchor, scale, draw
order, semitransparency, bob, four-tick appearance/disappearance and visibility
guards exactly as they stand. Do not replace the anchor with fixed screen
coordinates. Do not move the icon to avoid floors, scenery, the partner or other
bubbles. Do not introduce a HUD fallback or hint label. Do not alter the condition
bubbles to make room. No icon variant changes when care becomes available.

The source trace and before/after control mapping below describe the implementation.

## Input ownership, before and after

`confirm` = Circle ON / Cross OFF. `cancel` = Cross ON / Triangle OFF.
`alternate` = Triangle ON / Circle OFF. Square remains bit `0x80` in both layouts;
this proposal does not change `CONFIRM_BUTTON`, `CANCEL_BUTTON` or `ALT_BUTTON`.

| Context | Before | After |
|---|---|---|
| Field, quick care eligible | Confirm opens care when close and facing the partner, before nearby machine/talk handling; Square has no quick-care role | Square opens care anywhere on the same map; Confirm only follows normal NPC/tile/chest/machine interaction |
| Field, no care entry | Confirm interacts; care does nothing | Confirm interacts; Square does nothing |
| Walking/running | D-pad moves; existing run modifier applies | Unchanged; Square opens only if normal field control and the care predicate allow it |
| Field triangle menu | Triangle opens the existing menu | Unchanged; its inventory/status/care commands remain available |
| Quick-care list already open | D-pad navigates, Confirm gives item/command, Cancel closes | Unchanged; Square does not give the item, repeat-open or close the list |
| Item inventory and item-use flow | Existing Confirm/Cancel and inventory operations | Unchanged; field shortcut disabled for the entire flow |
| Evolution chart | Square opens requirements on an eligible target; Square or Cancel closes the requirements popup | Unchanged; no care input reaches this menu |
| Techniques menu | Square enters the existing move-information state (`game_menu.c`, MENU_STATE 6 → 7) | Unchanged |
| Item Bank | Square moves the selected stack (`all`); Confirm moves one and alternate moves ten | Unchanged; no field care dispatch |
| Shop quantity boxes | Square selects the maximum amount; Confirm accepts, Cancel backs out; alternate supports amount stepping | Unchanged |
| Naming UI | Square clears the entered name | Unchanged |
| Field battle | Confirm issues highlighted command; Square requests a finisher when the gauge is ready | Unchanged; no quick-care badge or shortcut, including loading and results |
| Tournament / VS battle and selection | Existing Square finisher, selection and other context-specific actions | Unchanged; only the field walking-state handler gains care |
| Dialogue, training, title/options, scripted movement, fishing and other minigames | Their existing input handlers | Unchanged; no global Square hook |

The implementation must dispatch within ordinary field walking control, not in
pad polling. Give map/autotalk/warp state changes priority over opening care.
When Confirm and Square rise together, dispatch Confirm's interaction for that
tick and suppress care; do not dispatch both. This avoids a simultaneous training
script and care box. Require a fresh Square edge after any menu/transition closes;
a held button must not reopen care or spend an item. The cap is a promise of
availability, so input and prompt must share the same predicate.

## Control explanations

All nine `jijimons-house.json` language files explain Square in Tokomon's item
tutorial (`s178.sec6.u2`), Botamon's care advice (`s178.sec7.u3`) and Jijimon's
early forest hint (`s178.sec5.u20`). The tutorial also says that Confirm talks or
interacts, Square only opens the list, and an item must be selected and confirmed.
The colored Cross token uses the existing layout adapter to become Circle when
JAPANESE CONTROLS is on; Square is never remapped. No new glyph codes are needed.
The nine-language web care description and the player guide's controls section
match this behavior. There was no separate care FAQ in the documentation.

## Heap, VRAM and MENU estimate

The matched full multilingual comparison measures **main_BSS_END +432 B**
(`0x801ceb70` → `0x801ced20`), hence 432 bytes less heap. Both builds use the same
nine-language text padding, file tables, compiler image and make arguments, with
only the five files in the C patch restored for the baseline. MENU remains
**53,796 B** in both builds (**55,296 B** after sector rounding).

| Resource | Implemented icon 1 |
|---|---|
| Sprite pixels | Three 16×12 frames at 4 bpp = **288 bytes VRAM** |
| Palette | One 16-color CLUT = **32 bytes VRAM**; all variants fit within 16 colors |
| Persistent CPU buffers | 0 additional resident buffers; reuse the existing alternate-confirm frame buffer while loading |
| Resident executable / heap loss | **432 bytes measured** in the full multilingual comparison; loading uses a 96-byte stack sprite buffer |
| Per-render packet | The existing single POLY_FT4, **40 bytes**; no extra badge packet |
| MENU_REL growth | **0 bytes measured**; no menu code change |
| New disc filenames / allocations | 0; use existing disc-derived UI assets |

Only icon 1 ships. These costs are not multiplied by four, and no
extra animation state or font/text buffer is needed. Existing confirm artwork
must remain intact: the care badge needs separate texture/palette routing rather
than replacing the shared dialogue cap or recoloring a shared CLUT. The preview
uses an isolated palette specifically because the native palette is also used by
other UI elements, including the HP/MP HUD.

The three care frames use TIM-relative rectangles `(240,27,16,12)`,
`(240,39,16,12)` and `(192,96,16,12)`; their palette occupies VRAM `(352,252)`.
All four rectangles contain only filler on all eight supported base discs and
avoid the native and translated label crops, including Chinese menu cells.
`tools/localize/systemw.py` reserves these holes against future Chinese label
changes. `(352,230)` remains owned by the confirm adapter and is not reused.
The two right-edge uploads omit their first transparent source column and add
transparent padding. Their UV origin is 239, with the untouched native border
mapped transparent in the private palette; the endpoint is 255, so the existing
16-texel span cannot wrap through U=256. All eight base discs' border pixels were
checked. The guard columns are reserved against localized label changes too.
`modButtonsTimLoaded` derives the Square from the disc's Cross/Circle cap,
uploads one stack-local frame at a time with DrawSync before reuse, then restores
the alternate-confirm buffer. Changing layout preserves the care frames/palette.

MENU's sector-bound linker assertion and `tools/title_storage_check.py` remain
mandatory; spare file bytes do not authorize another sector. The final heap is
**184,784 bytes**. Both the native sweep and all **320 archive-backed screen
setups** pass without a heap override. The tightest setup is screen 207, with
**64 bytes** of remaining margin; screen 41 retains 3,000 bytes. All nine language
builds have the same `main_BSS_END` and MENU size, identical title storage, and
valid sector bounds. The linked-reference title-storage check also passes.

## Evidence and implementation acceptance

Review artifacts remain local under `build/icon-review/`: four numbered sheets,
native 320×240 light/dark screenshots, 16×12 source frames and nearest-neighbor
4× zooms. These are **artwork previews**, not implemented Square controls.
The supplied report image identifies the badge being redesigned; its position is
established by the game's existing renderer rather than manually choosing a
nearby location.

For the screenshots, a restored PCSX-Redux visual fixture renders the existing
care badge. A temporary debug hint holds it visible for comparison; texture-only
uploads and a care-palette preview override replace its artwork. Its drawing
coordinates, projection and animation code are untouched. The comparison includes
reference captures of the existing badge on each floor. Those preview changes were
emulator-local and were discarded; no disc or C patch was produced for the previews.

The implementation evidence is separate from the artwork previews. The full
nine-language disc was freshly booted with Continue in PCSX-Redux, with 2 MB RAM
(the game's 8 MB probe returns false). Its own field state was reused only with
the same executable hash. No texture override or replacement input handler was
used for these captures. Fixtures set needs, inventory, positions and raised
flags; the battle fixture fills the actual finisher gauge. Actions use emulated
pad input, and menu/battle observations read the running game's state.

| Runtime check | JAPANESE CONTROLS OFF | JAPANESE CONTROLS ON |
|---|---|---|
| Square opens care near the partner | Passed, 141 world units | Passed, 141 world units |
| Square opens care far away, facing away | Passed, 5,141 world units | Passed, 5,076 world units |
| Opening care preserves all 10 MP Floppies | Passed near/far | Passed near/far |
| Confirm talks to an NPC beside the partner; no care or item use | Cross passed | Circle passed |
| Triangle menu blocks care; Square opens technique help | Passed | Passed |
| Item Bank Square transfers the full selected stack | Passed | Passed |
| Evolution chart Square opens/closes requirements | Passed | Passed |
| Battle Square reaches finisher command 11; no care | Passed, actual Square edge traced | Passed, actual Square edge traced |
| New, original and classic fonts open care with unchanged artwork | All three passed | All three passed |

The care atlas/palette hash is identical across layouts and all three fonts.
Native 320×240 screenshots are in `build/care-proof/`; tutorial captures are in
`build/care-hints-proof/`. The new tutorial pages were checked in-game: Square
stays pink, while the talk/interaction glyph changes from Cross to Circle.
Review sheets preserve screenshot pixels at native size, with captions outside
the game image. The light-floor hunger bubble and dark-floor standalone badge
both retain the existing renderer's anchor and projection.

The source-level guard/art regression passes, including simultaneous Confirm
priority and restoration of alternate Confirm frames. Native texture audits cover
all eight supported base discs and 24 cap frames. Atlas-reservation tests pass.
The Chinese audit reports 6,471/6,471 keys, 2,005 extended glyphs, no missing glyphs
and no errors; the new Japanese text uses existing glyphs. New Latin care pages
fit all three font metrics. Language/Chinese tests (40), atlas tests (6) and web
translation tests pass. All 1,713 derived files match the completed build manifest.

Physical hardware, a full boot matrix of other base discs, distant item handoff
completion/refusal, naming, tournament/VS and minigames were not exercised. GPU
packet high water was not profiled; source inspection confirms that the existing
single 40-byte badge packet is reused. The broader partner-size, camera-edge and
condition-option matrix remains untested. Icon variants 2–4 remain design
references only.
