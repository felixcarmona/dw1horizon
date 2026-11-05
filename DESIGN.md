# Square quick care: icon design

Status: design only. No input, C code, game asset or patch-series change is included.

## Proposed behavior

Square opens quick care from anywhere on the current field map. The partner does
not have to be nearby or face the tamer. Opening the list never consumes an item;
the ordinary confirm button gives the selected item or executes the selected care
command. Circle with JAPANESE CONTROLS ON, or Cross with it OFF, remains the field
interaction button. This separates care from talking, training and using machines.

This revision compares **only the icon artwork**. The existing care badge keeps
its exact anchor, projected size, bob, appearance/disappearance, visibility rules
and three-frame press timing. There is no HUD badge, hint row, edge clamp,
offscreen fallback or new text. Earlier A/B/C placement alternatives are withdrawn.
The field input change above remains a separate future implementation step.

Recommend **1, native round cap**: the familiar gray button with a pink Square.
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
- `Let-the-care-menu-win-over-nearby-machines.patch` moves `modFeedTick` ahead
  of `checkMapInteraction` in `tamerTickWalkingState`. Consequently, current
  care wins a confirm press even beside a machine when care is available.
  Older prepared build trees with the reverse order are not current behavior.

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

`mod_feed.c:modFeedTick` currently requires normal tamer and partner states,
script idle (`IS_SCRIPT_PAUSED == 1`), no fade protection, both care boxes fully
closed, no held world item, a nonempty care list, and `feedPartnerAhead()`.
That last test requires ±45 degrees and the item-take distance plus 12, capped
at 127 before `checkEatDistance`. The proposed shortcut removes this last test;
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

The source trace and future control mapping remain below for implementation
context; this artwork revision implements neither input nor care eligibility.

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
| Item Bank / shop quantity boxes | Square selects the maximum amount (`all`); Confirm accepts, Cancel backs out; alternate supports amount stepping | Unchanged; applies to deposit/withdraw and other quantity boxes |
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

## Heap, VRAM and MENU estimate

This design changes no executable: **main_BSS_END delta 0; heap delta 0;
MENU_REL delta 0; VRAM delta 0** for this commit. The following are design budgets,
not compiled measurements or a hardware-safety claim.

| Resource | Provisional budget, any one variant |
|---|---|
| Sprite pixels | Three 16×12 frames at 4 bpp = **288 bytes VRAM** |
| Palette | One 16-color CLUT = **32 bytes VRAM**; all variants fit within 16 colors |
| Persistent CPU buffers | Target 0; generate from disc-derived UI data during the build/load path |
| Resident executable / heap loss | Conservative **1,024-byte budget** for routing/load code and any retained 320-byte upload data; must be measured later |
| Per-render packet | The existing single POLY_FT4, **40 bytes**; no extra badge packet |
| MENU_REL growth | **0 bytes** intended; no text or menu change |
| New disc filenames / allocations | 0 intended; use existing disc-derived UI assets |

Only one variant would ship. These budgets are not multiplied by four, and no
extra animation state or font/text buffer is needed. Existing confirm artwork
must remain intact: the care badge needs separate texture/palette routing rather
than replacing the shared dialogue cap or recoloring a shared CLUT. The preview
uses an isolated palette specifically because the native palette is also used by
other UI elements, including the HP/MP HUD.

These VRAM bytes require a verified unused rectangle and palette slot in every
base-disc/localization UI page. `(352,230)` is already owned by the confirm adapter
and must not be reused. Prefer a build-time generated asset delta over a new
resident frame array. Do not assume UI filler is free without a texture-use audit.
Existing ring state already supplies fade/bob and phase; sharing helpers must not
accidentally prevent compiler inlining and increase main's size unexpectedly.

As a reference only, the reviewed v0.0.6 build records `main_BSS_END = 0x801ce65c`,
186,528 bytes heap, and MENU_REL 55,132 bytes (55,296 bytes after 2,048-byte sector
rounding). This is not a measurement of a future implementation or necessarily
of this branch's full build. MENU's sector-bound linker assertion and
`tools/title_storage_check.py` remain mandatory; spare file bytes do not authorize
another sector. No MENU growth is needed for the recommended option.

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
reference captures of the existing badge on each floor. Preview changes are
emulator-local and are discarded when it stops; no disc or C patch is produced.

Before a later implementation can be accepted:

1. Record `main_BSS_END` before/after using the same full multilingual build;
   run heapcheck for native and extended-story maps on original 2 MB RAM, with
   no heap overrides. Run the full documented build with eight jobs.
2. Measure MENU file/sector bounds and GPU packet high water; verify the proposed
   sprite/CLUT space against every supported base and language. Measure actual
   memory instead of treating the budgets above as evidence.
3. Test both layouts and all three font settings; show care with no bubble,
   hunger, low MP, scolding, tall/small partners, camera edges and no eligible
   entries. Verify that old/new bars, condition-bubble visibility and prompt
   behavior remain unchanged.
4. Press Confirm beside NPCs, training machines, doors, chests and trigger tiles
   while care is eligible: no care menu or unintended MP Floppy use. Press Square
   far from and facing away from the partner: list opens, no item consumed until
   Confirm. Complete one distant item handoff, including partner pathing/refusal.
5. Verify evolution requirements, bank `all`, technique information, naming,
   finisher-ready battle, tournament/VS, minigames and simultaneous/held buttons.
   Check map changes and cutscene ownership; stop every test process afterward.

No icon has been selected for implementation. Implementation remains a separate step.
