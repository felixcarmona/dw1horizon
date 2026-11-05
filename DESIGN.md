# Square quick care: field prompt design

Status: design only. No input, C code, game asset or patch-series change is included.

## Proposed behavior

Square opens quick care from anywhere on the current field map. The partner does
not have to be nearby or face the tamer. Opening the list never consumes an item;
the ordinary confirm button gives the selected item or executes the selected care
command. Circle with JAPANESE CONTROLS ON, or Cross with it OFF, remains the field
interaction button. This separates care from talking, training and using machines.

Recommend **A, the partner badge**. It preserves the existing visual association
between a partner's needs and care, with no new words or permanent HUD element.
B offers a fixed HUD anchor; C explicitly teaches the shortcut but adds text.
These are alternatives: display only one of them.

## Existing prompt: asset and drawing path

The floating round cap in `report-circle-prompt.png` matches the **quick-care
badge**, not a general marker proving an NPC or doorway can be interacted with.
Its round outer silhouette is the physical button cap; the colored mark on its
face identifies the input. A Square prompt should retain that cap and change the
mark to a pink square.

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

## Artwork and three options

All options use the native 16×12 gray cap. Only the face mark changes: a
6×5 perspective square, bright pink **(248,128,192)** and dark pink
**(160,64,120)**, both representable in PS1 5-bit channels. The square's corners
are square, with continuous edges; the gray cap supplies the depth. Its face is
perspectively compressed like the existing Circle/Cross mark. No antialiasing,
vector smoothing, modern font or enlarged UI is proposed.

Square is the physical Square button under **both** layouts. It is never passed
through the Circle/Cross layout substitution. The new frames require their own
texture location and palette; replacing the existing confirm frames would also
replace dialogue confirmation and is incorrect. Generate the cap from the
player's base disc and erase that base's original symbol, as the existing adapter
does, then draw Square. Keep all three pressed-frame offsets if retaining the
native animation.

| Option | Placement and presentation | Availability | Tradeoff |
|---|---|---|---|
| **A — Partner badge (recommended)** | Existing condition-ring badge anchor; 16×12 source, existing projection, bob and four-tick appearance | Every field tick where quick care can open, regardless of partner distance or facing | Familiar, no text. A large partner or crowded bubbles needs collision checking. |
| **B — Vitals badge** | Fixed 16×12 screen-pixel cap immediately left of lower-right HP/MP bars; reference `(218,204)` on 320×240 | Same predicate as A, in either old/new status-bar mode | Stable and visible when partner is offscreen; adds persistent HUD weight. |
| **C — Care hint row** | Native dark blue small box in bottom-left safe area; cap plus localized `Care`, reference box `(12,207)`–`(90,225)` | Same predicate as A; hidden immediately when another UI opens | Clearest meaning, but needs localized width checks and a text-buffer allocation strategy. |

A's mockup uses a 16×12 cap at the reference camera's partner-side anchor. Actual
implementation should reuse world projection rather than force that screen size
at every depth. Clamp A inside a 12-pixel screen safe margin, clear the clock and
condition bubbles, and use B's fixed anchor as a fallback if the partner is behind
the camera or offscreen. This fallback is the same single prompt, not a second
copy. Keep the care badge visible when condition bubbles are disabled: care
availability must not depend on that cosmetic option. Do not suppress a hunger,
sickness, toilet or other condition bubble to make room.

Hide all three during dialogue, training, battle loading/combat/results, inventory,
triangle menus, shops, evolution, cutscenes, map transitions, fade protection,
feeding/refusal animations and sleep. With no usable item or care command, show
nothing and Square does nothing. A low MP partner with an MP Floppy qualifies
even if no condition bubble is active. Reuse the existing ranked care list and
refusal/scolding flow. No item is automatically selected and used by Square.

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

## Fonts and control-layout coverage

A and B contain no text: Square and cap pixels are identical with NEW, CLASSIC
and ORIGINAL, and with Japanese controls ON/OFF. Their mockup sheets deliberately
repeat the same field background to compare the **proposed prompt**, not to claim
six independent emulator runs. C uses the project's actual glyph renderers:
font B for NEW, original letters placed to the pixel for CLASSIC, and the original
4-pixel placement for ORIGINAL. The icon is independent of those renderers.

The English `Care` row is shown in all three settings. A production C row would
need a short localized label in every supported language, width measured with
the active font, a maximum box width of 112 pixels, and correct Japanese/Chinese
bitmap glyph support. These localized rows have not been authored or verified.
A avoids that new localization and font-fit burden entirely. Existing care-list
text keeps its current language/font behavior for every option.

## Heap, VRAM and MENU estimate

This design changes no executable: **main_BSS_END delta 0; heap delta 0;
MENU_REL delta 0; VRAM delta 0** for this commit. The following are design budgets,
not compiled measurements or a hardware-safety claim.

| Resource | A/B provisional implementation budget | C provisional implementation budget |
|---|---|---|
| Sprite pixels | Three 16×12 frames at 4 bpp = **288 bytes VRAM** | Same |
| Palette | One 16-color CLUT = **32 bytes VRAM** | Same |
| New persistent CPU buffers | Target 0; reuse existing load-time scratch and hint/animation state | Avoid resident label cache; render on availability/language/font changes |
| Resident executable / heap loss | Budget **at most 1,024 bytes**, including code and any retained 320-byte upload data; remove distance/facing-only code if otherwise unused | Budget **at most 2,048 bytes**, including code/text routing; needs actual localization sizing |
| Per-render packet | One POLY_FT4, **40 bytes** in the existing GPU packet arena | Cap plus existing box/text primitives; reserve **256 bytes** packet budget |
| MENU_REL growth | **0 bytes** intended | **0 bytes** intended; field hint cannot call an unloaded MENU overlay |
| New disc filenames / allocations | 0; generate into existing disc-derived UI asset | 0 intended; reuse language/text infrastructure |

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

Review artifacts remain local under `build/design/`: PCSX-Redux screenshots,
three A/B/C sheets with native 320×240 panels, separate native panels, and a
nearest-neighbor 4× icon zoom. These are **composites**, not implemented controls.
The supplied report image is the visual reference; reconstructed cap pixels come
from the disc-derived SYSTEM_W.TIM rather than its enlarged, filtered crop.

Before a later implementation can be accepted:

1. Record `main_BSS_END` before/after using the same full multilingual build;
   run heapcheck for native and extended-story maps on original 2 MB RAM, with
   no heap overrides. Run the full documented build with eight jobs.
2. Measure MENU file/sector bounds and GPU packet high water; verify the proposed
   sprite/CLUT space against every supported base and language. Measure actual
   memory instead of treating the budgets above as evidence.
3. Test both layouts and all three font settings; show care with no bubble,
   hunger, low MP, scolding, tall/small partners, camera edges and no eligible
   entries. Verify old/new bars and condition-bubble visibility options.
4. Press Confirm beside NPCs, training machines, doors, chests and trigger tiles
   while care is eligible: no care menu or unintended MP Floppy use. Press Square
   far from and facing away from the partner: list opens, no item consumed until
   Confirm. Complete one distant item handoff, including partner pathing/refusal.
5. Verify evolution requirements, bank `all`, technique information, naming,
   finisher-ready battle, tournament/VS, minigames and simultaneous/held buttons.
   Check map changes and cutscene ownership; stop every test process afterward.

Implementation remains a separate step after a design is selected.
