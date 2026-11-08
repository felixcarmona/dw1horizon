# Options: the title menu's OPTIONS

Patches 0167, 0169, 0173-0175, 0177, 0180-0182, 0199, 0212, 0234, 0239, 0244 and 0276 (`mods/patches/`). The title menu has a fifth row, **OPTIONS**, under BATTLE MODE. It
opens a box of eleven switches (ten in a `FONT=original` build, which has no FONT):

| Row | Values | Default | Effect |
|---|---|---|---|
| JAPANESE CONTROLS | OFF / ON | OFF; ON on a Japanese base disc (patch 0241) | the Japanese disc's buttons (below) |
| EVOLUTION GUIDE | OFF / ON | ON | the evolution chart's green lines and Square requirements popup (patches 0176, 0299); OFF hides the prompt and popup and draws the original detail view |
| NEW DIGIMON | OFF / ON | ON | OFF: the partner evolves only into the species the original game raises (the species files' `"vanilla": true`, ids 1-65: the chart's 61 and WereGarurumon, IceLeomon, Gigadramon, MetalEtemon by items), so no Megas; the chart is the original sheet and its trees show the original rows (below); the death's egg box shows only the original four eggs (patch 0334; ON adds the hand-made babies' four) |
| EXTENDED STORY | OFF / ON | ON | patch 0199: the story with the story mods built onto the disc (What the Island Forgot: its new places, the city's new residents), or OFF the original story; changing it on a save moves the tamer to Jijimon's house (below) |
| DIFFICULTY | EASY / NORMAL / HARD | NORMAL | EASY doubles partner damage and halves damage taken; HARD scales enemies and adds a damage floor (below) |
| QUICK BATTLE START | OFF / ON | ON | patches 0234, 0239: a field battle starts the moment it is triggered, its BATTLE letters and bubbles over the running fight (patches 0233, 0236, 0238); OFF, the original start |
| FRAME RATE | AUTO / 60 / 20 | AUTO | AUTO uses the CPU probe; 60 requests three render passes per tick; 20 requests one. Logic stays 20 Hz. |
| FONT | NEW / CLASSIC / ORIGINAL | NEW | font b, ours; the original letters evenly spaced; the original font as the original draws it (below) |
| LANGUAGE | eight languages selected at build time | the build's (`LANG_BASE`) | the selected runtime languages ([languages](language.md)) |
| MAP SIGNS | ORIGINAL / TRANSLATED | TRANSLATED | patch 0183: the signs painted in the map backgrounds as the disc has them, or in the language |
| CHEATS | OFF / ON | OFF | the paused Cheats menu and its editing tools (below) |

The care HUD and status-screen care panels are always enabled. The field and gym
HUD shows happiness, discipline, hunger, toilet and tiredness; the status screen
shows care bars, numbers and care mistakes. See [gauge meanings](../../HUD-DESIGN.md#exact-gauge-contract).
The digital clock beneath the field dial and continuous enemy head bars are also
permanent. Saved-options bytes 1 and 3 are ignored on load and written as 1.
Byte 2 stores FRAME RATE as 0xA0 (AUTO), 0xA1 (60), or 0xA2 (20). All other values load as AUTO.
Byte 13 is reserved: both inverted enemy-bar bits are ignored and written as 0;
the old title-header bits 6 and 5 are ignored and cleared.
The other saved bytes retain their positions, including on older saves.

Each row shows its label and its values (two, three for FONT); the chosen value is yellow and the others grey. Left and
right step to the value before and after, confirm takes the next one (round); cancel goes back to the title menu with the cursor on OPTIONS. A new setting needs the current menu row, value/get/set handling and runtime effect,
plus a compatible saved-options representation. Read `main_menu.c`,
`mod_options.c` and the save tags in the prepared patch-series tree; do not infer
available bytes from an older options count. Labels and values are translation
keys, with entries for each supported language. Check title options, save/load,
older saved options and every selected language after adding a setting.

Since 0175 the box is laid out in the font that draws it (`drawOptionsText`): the labels' column as wide as the widest
label, the values' columns as wide as the widest value, 8 pixels between columns, centred on the screen. The labels are
drawn in the text area's first rows and the values in the rows under them: the original font's "JAPANESE CONTROLS"
takes 200 of the area's 256 pixels. With that font long labels and their values do not fit beside each other, so a row shows only its chosen value, as the original game's own settings do;
left, right and confirm work the same.

## DIFFICULTY

Patch 0212. It changes only the fight, the tournaments included. EASY (`MOD_OPT_DIFFICULTY`, `MOD_DIFF_EASY`):

- every hit, finisher and block chip the partner deals is doubled, and every one it takes is halved, rounded up;
  `MOD_DIFF_DAMAGE` (`dw/mod_options.h`) in `BTL_calculateDamage` (wild battles) and `STD_calculateDamage` (arena and
  tournaments), before their minimum and `DAMAGE_CAP`, so a hit still does at least the minimum and never passes the cap;
- the poison ticks on the partner are halved too (`BTL_tickStatusEffects`, its STD twin);
- the stats and the saved HP are not touched: halving what the partner takes is twice its HP without bigger numbers on
  its bar, and NORMAL is the original game again at once. The time-out judgement (whoever took less damage wins) reads
  the damage as dealt.

Not changed: the VS mode (two players), a script's damage (`69 DEAL_DAMAGE`, a % of the HP, never kills). Measured in a
wild battle (`addEntityText` logged): NORMAL dealt 72-84 a hit, EASY 156-192; taken 29-329 against 35-66.

### HARD

HARD is opt-in; permanent partner growth retains its existing
rules. Wild/scripted battles and tournaments scale enemy HP ×1.1, Offense ×1.5,
Defense ×1.05, Speed ×1.15, Brains ×1.5 and finisher power ×1.5. Partner damage
from direct techniques/finishers is ×0.95. Poison retains its percentage of
the target's maximum HP; scripted percentage damage is unchanged. Empty move-slot idle weights are ×0.25, with a minimum of one; stronger
Brains also activates the existing targeting and buff priorities. Factors live
in `content/tables/battle-formulas.json: battleFormulas.hard`.

Enemy HP caps at 30000 and other attributes at 9999. MP, rewards, drops and
partner stats are unchanged. Original field encounter stats are saved before
scaling, used for rewards, and restored at battle end/flee, so difficulty does
not increase permanent gains or compound across fights. Single-player difficulty does not apply to two-player VS; the shared
Defense continuation below still applies there. HP scaling occurs before the bars and fighter AI initialize.

Save byte 10 retains NORMAL=0 and EASY=1, adds HARD=2, and defaults to NORMAL
for an absent/invalid byte. Both title-header and tagged-save copies use it;
no save allocation changes. HARD is translated in all nine languages. Chinese
retains its existing 8 MB and dedicated-font requirements. The third difficulty
value uses spare language-row texture/width slots; menu arrays stay the same size.

All difficulties use the ordinary-technique Defense continuation above 999;
HARD additionally floors enemy damage to the partner at 15% of the same hit
against Defense zero. Finishers already ignore Defense, so the floor is
automatically satisfied. See [implementation and evidence](../../HARD-DIFFICULTY.md).

See [the difficulty and growth review](../../STAT-SOFTCAP.md) and
`python3 tools/hard_audit.py` for targets, first-life HP/MP analysis and budgets.

## FONT

Patches 0175 (NEW FONT OFF/ON) and 0177 (the three values). A `FONT=b` executable carries both fonts (`FONT_SWITCH`,
`dw/mod_font.h`) and `MOD_FONT` says how it draws (`docs/mods/font.md` "Fonts"):

- **NEW** (`MOD_FONT_NEW`): font b.
- **ORIGINAL** (`MOD_FONT_ORIGINAL`): the original code, its 12-pixel cells on the 4-pixel grid (the gaps between
  letters 0 to 6 pixels, "B A T T L E"), the original glyphs, the long names' tight and condensed modes.
- **CLASSIC** (`MOD_FONT_CLASSIC`): the original letters placed to the pixel as font b is: each glyph's ink moved to its
  first column, its advance the ink and one blank column, the digits one advance of 7 (`classicRows`, `font.c`, made at
  the draw from the original's tables: no table of its own). A name wider than its
  field takes the original's tight line, the same letters one column apart.

The switch takes effect at once: the box redraws itself in the new font.

The script text is paged for the font that draws it (a row of font b holds some 45 letters, of the original 27), so a
build with both fonts puts a second copy of it on the disc, compiled for the original font's widths: `DGORIG.SCN`,
`MHORIG.SCN` and `SCRNORIG.DAT` beside `DG.SCN`, `MAPHEAD.SCN` and `SCRN.DAT` (`tools/build-full.sh`, `$O/orig`). With
ORIGINAL or CLASSIC (CLASSIC's letters are narrower than the original's cells, so its pages fit) the game reads the
copies (`modFontFile`, `file.c`); a disc without them (a story for the original
executable, `TEXT=us` without new screens, whose paging fits both fonts) reads the usual files. Switching the font reads
`MAPHEAD.SCN` and `DG.SCN`'s offset table again from the new font's files (`modFontScriptsChanged`, `script_interp.c`),
so it happens only at the title: in OPTIONS, or when a Continue takes the save's options. The executable's own strings
(menus, names, item texts) are one set for both fonts.

## Automatic frame rate

FRAME RATE defaults to AUTO. Left/right and confirm cycle AUTO / 60 / 20.
AUTO keeps the existing 16-scanline CPU probe, two agreeing samples and
8500/7500 hysteresis. The probe still runs during spare waits in forced modes,
but cannot override an explicit choice. Returning to AUTO uses the latest probe.
60 requests three passes per ordinary tick; existing deadline checks may skip
passes that cannot fit. 20 requests one. Battle speed and 20 Hz logic are unchanged.
An `FPS=20` developer build still compiles out extra passes.

At Press Start, the detected-settings panel always shows RAM (`RAM 2 MB` or
`RAM 8 MB`), estimated CPU speed (`CPU ~100%`, for example), and the selected
renderer (`20 FPS` or `60 FPS`). Its short hints read “CPU 250%: 60 FPS” and
“8 MB: Chinese only”. The other eight languages still work with 2 MB.
RAM is green with 8 MB; CPU is green at the raw 8500-count enable threshold.
The FPS color follows the selected mode, including the selector's hysteresis.
These are detected settings, not a measurement of how many frames a busy scene
actually presents. Title and menu animations retain their existing timing.

The estimate interpolates the documented 100/200/250/300% calibration points,
rounds to 25% steps and clamps to 100–300%. It is approximate across emulators; readings outside the measured range use the
nearest endpoint.
The panel reads the latest sample on entry and redraws if that reading or the
selected mode changes while it is visible. Press Start does not run the idle-wait
sampler, so a fresh boot shows the boot CPU reading. RAM remains the boot reading.
The display code and scratch are in the title overlay, loaded after the intro
movie and before installing the Press Start callback.

The same 16-scanline probe runs during spare presentation waits about every two
seconds. Two agreeing samples and separate enable/disable thresholds prevent
oscillation. This adapts to runtime overclock changes and same-build save states;
see [the scheduler and thresholds](../reference/frame-rate.md#automatic-selection).

Saved-options byte 2 and its title-header copy use 0xA0 + the option index.
The record stays 14 bytes and every other byte retains its position. All legacy
values map to AUTO: v0.0.7 wrote 20 unconditionally, so it is indistinguishable
from an older explicitly selected 20. Resetting both old 60 and old 20 to AUTO
provides one consistent migration; new explicit choices persist on save/load.
Missing and invalid values also default to AUTO. Changes made at the title keep
the existing precedence over the options of a subsequently continued save.
`MOD_FPS_MODE_RUN` always reports the effective 0/2 mode, including forced choices,
so a title panel reading it reports the renderer actually requested.

The immutable four-column row-pointer table remains in MENU_REL. Its third
values are data entries, avoiding separate FONT/DIFFICULTY/FRAME RATE branches.
The small language-name resolver stays resident with the name array so the
MENU text lookup can use a tail call and retain the mandatory overlay reserve.
Full nine-language build: main_BSS_END 0x801ce6ac, heap 186448 B, MENU 55164 B
(27 sectors, 132 B spare). Both 2 MB heap checks pass; all 320 actual-archive
setups fit, with 1728 B on the tightest setup.

## JAPANESE CONTROLS

All the controls as in the Japanese version.

| | Confirm (`CONFIRM_BUTTON`) | Cancel (`CANCEL_BUTTON`) | Third button (`ALT_BUTTON`) | Field menu |
|---|---|---|---|---|
| OFF (the US disc) | × 0x40 | △ 0x10 | ○ 0x20 | △ |
| ON (the Japanese disc) | ○ 0x20 | × 0x40 | △ 0x10 | △ |

- **Input.** The Japanese disc's code differs from the US one in these three masks only. The decomp, which builds both
  discs, writes them as the macros of `include/dw/input.h`. With the mod, the US macros read `MOD_OPT_BUTTONS`, so with
  the option on every screen answers as on the Japanese disc. A button the code tests by its bit is the same on both
  discs and stays: △ opens the field menu (`tamer.c`, `isKeyDown(0x10)`), and the same holds for □ and the VS and
  battle checks.
- **Text.** The font draws each button glyph as the button that now does its job (`modButtonGlyph` at the three glyph
  lookups of `font.c`): × as ○, △ as ×, ○ as △. So "×Select △Cancel" reads "○Select ×Cancel" with no second text. A
  green △ (`{color 5}`) is the exception and stays △: in the texts it is the field menu's button (the fishing help). The text paints a button in its colour (`{color 6}×` cyan, `{color 5}△` green, `{color 10}○`
  orange, `{color 4}□` pink; the names come from the game's own colour test in File City). A swapped glyph painted in
  its own button's colour takes the colour of the button it now is (`modButtonColor`). A glyph in the text's ordinary
  colour keeps it. In the yaml and the text banks a glyph is the Shift-JIS character of its code. △ (81A2) is the one
  the font draws as ×, and × (817E) the one it draws as △.
- **The dialogue box's button.** The three 16x12 frames of the × button (UI page u 0x4C v 0xB7: `SYSTEM_W.TIM`, VRAM
  (339, 183), CLUT (96, 500)) are drawn by `renderUIBox`. The care badge now uses a separate pink Square cap. The US disc has no ○
  there. When `loadStackedTIMFile` uploads `ETCTIM.BIN`, `modButtonsTimLoaded` copies the frames from the file's own
  pixels and makes a ○ version: the cross (indices 0xC and 0xD, a 6x5 box in each frame) is painted over with the face
  (index 3), and a 6x5 ring is drawn where it was. The ring is red, (248, 96, 104) and (160, 48, 56), with a CLUT of its
  own: the frames' one with its two blues made red. That CLUT is kept in the page's filler (u 0x80..0xBF of v 0xE6, all
  index 15, which nothing draws), at VRAM (352, 230). The CLUT columns 288/304 of rows 480-511 were not used, because
  the tournament and VS portraits use them. With the option off, the × frames and the filler are uploaded back. A disc
  whose frames are not the expected 6x5 cross keeps the ×. The VS mode's own `SYSTEM_W.TIM` load (`vs_select.c`) is
  not hooked. The mod carries no pixels of the disc.
- **Quick care.** Physical Square opens care in the field in either layout, regardless of partner distance or
  facing. The care cap's three 16×12 source frames occupy SYSTEM_W atlas holes `(240,27)`, `(240,39)` and
  `(192,96)` (TIM-relative texels); its palette is VRAM `(352,252)`. These are separate from Confirm and the
  translated label cells. The build derives these copies from the native cap in `SYSTEM_W.TIM` and
  `ETCTIM.BIN`; the normal UI load installs them, with no resident painter or new file. The original badge
  anchor, projection and animation are unchanged. Field Confirm
  remains talking/interacting; Square inside menus and battle retains its existing context-specific actions.
- **A Japanese base disc (patch 0241).** The Japanese disc draws a ○ in the same three frames (a flat 8x5 ellipse in
  the palette's oranges 7, 0xE, 0xF; its CLUT's 0xC and 0xD are unused). The frames tell the base (`framesButton`,
  `mod_options.c`): a 6x5 box of 0xC/0xD in each frame is the US ×, an 8x5 box of 7/0xE/0xF the Japanese ○, anything
  else keeps the disc's frames for both layouts. With the Japanese ○, ON shows the disc's own ○ as it is and OFF
  shows ours: the ellipse painted over with the face (3) and a 6x5 × drawn in the middle of its 8 columns (where the
  US disc has its ×), blue (112, 176, 248) and (64, 96, 208) in 0xC/0xD of the same CLUT in the filler: × blue, as the
  PlayStation's. One executable for every base: at boot, before the saves'
  options (`modBootOptions` calls `modButtonsBoot`), `SYSTEM_W.TIM` (9 sectors) is read into `GENERAL_BUFFER` and a
  Japanese ○ there turns JAPANESE CONTROLS on; a save's options, read right after, still win (the title shows a
  card's newest save's choice, a Continue its own). The US disc is as before. 464 bytes of heap.
- **Saved.** The options are the record `SAVE_TAG_OPTIONS` 0x0009 (`u8[14]`: buttons, reserved clock byte (always 1), FRAME RATE (0xA0/0xA1/0xA2), reserved care byte (always 1), font, evolution guide, new digimon, language, map signs, story, difficulty, quick battle start, cheats flags, reserved enemy-bar byte (always 0)),
  written with every save. A Continue takes them, unless OPTIONS changed any since the
  console started; a shorter record (0167's 1 byte) leaves the rest at their defaults. So the title screen before a Continue
  has the US controls (on a Japanese base disc with no saves, the Japanese ones: ○ confirms there), and the test tools, which press × at the title, keep working.
- **Shown before a Continue (patch 0193).** Each save's memory card header keeps a copy of the record too (its PocketStation
  bytes), with a save number one past the highest seen. When
  OPTIONS opens at the title and nothing was changed there yet, it reads the headers of every save on the connected cards
  (`modCardOptions`) and takes the newest save's options, the ones a Continue of that save applies: saved with NEW DIGIMON
  OFF, OPTIONS shows OFF, and one change to ON is enough. A missing, unformatted or unreadable card is skipped without
  the card error screens; saves from before 0193 have no copy and leave the defaults. With two saves that differ, OPTIONS
  shows the newer one's and a Continue of the older one still applies its own, unless OPTIONS was changed. Once opened,
  the newest save's JAPANESE CONTROLS and LANGUAGE are in force at the title too, and a New Game starts with these options.
  Since patch 0205 they are read once at boot, before the title (`modBootOptions`, main.c): the title screen and its menu
  come up in the newest save's language and font (the menu was English until OPTIONS opened; read at the menu's first
  frame instead, the read froze it about 5 s in the emulator, so it is done before the intro, while the screen is black).
  A card saved in Spanish shows the Spanish title menu from its first frame; fresh cards boot in English. A save made
  with NEW DIGIMON OFF shows OFF after a restart; changed once to ON, the Continue loads with it on and the partner of a
  new species back; empty cards show the defaults.

The masks, not a swap of the buttons at `PadRead`: a swap for every check would move the field menu to ×, which the
Japanese disc does not do. The ○ is a red ring, as in the PlayStation's colours (× blue, ○ red, △ green, □ pink).

Expected behaviour with the option ON:
- The title menu shows five rows. OPTIONS opens, and the row switches OFF ↔ ON. With ON, × goes back.
- Continue goes through with ○.
- In the world, × does nothing in the field, △ opens the menu, ○ enters DIGIMON, and × goes back.
- The dialogue box's button is a red ○ in its three frames. In a line, a cyan × draws as an orange ○ and an orange ○
  as a green △; a green △ (the field menu's button) stays.
- Saving writes record 9 = 01 in both extensions. After a restart, Continue comes back with the option on.

## EXTENDED STORY

Patch 0199. A disc built with a story mod (`tools/build-full.sh` `EXTRA_STORY`, e.g. `story/mods/what-the-island-forgot/build.sh`)
carries both stories. The disc's own names hold the extended one, as before: DG.SCN, MAPHEAD.SCN and the maps the mods
retouched or the story compiler edited for them (new exits, placed Digimon). Beside them the build puts each file as the
story without the mods has it: the script text compiled again from `story/base` alone (`STORY_MODS=none`, no retouched
maps) and a copy of every map file that differs, each under the file's name with an underscore for its first letter:
`SCN/_G.SCN` and `SCN/_APHEAD.SCN` (`_GORIG.SCN`, `_HORIG.SCN` paged for the original font), `_AYO03.MAP` beside
`MAYO03.MAP` (`tools/dws/variants.py`; a name already on the disc stops the build). With the row OFF `modStoryFile`
(`mod_options.c`) reads the copy when the disc has it, in `lookupFileTable` after the language's copy is looked up
(`modLangFile`): the original story in Spanish, or with its signs translated, is the copy of the language's copy by the same
rule (DG.SCN's Spanish copy LE004.SCN, its original story's `_E004.SCN`; a sign map's LE066.MAP, `_E066.MAP`). A rule and
not a table: the What the Island Forgot disc has about 130 copies, and rows and names for them would not fit the
executable's heap (`MIN_HEAP`) beside the bilingual disc's 440 new names. The bilingual What the Island Forgot disc needed more room still: patches 0209 and 0210 (the file table and language rows) leave it 4 324 bytes over `MIN_HEAP`. The
new screens (255 and up, SCRN.DAT) stay on the disc, but nothing of the original story leads to them; the screen jump
(0165) does nothing with the row OFF. `STORY_ALT=0` builds the extended story alone; a disc without the copies shows the
row and ignores it (no choice), as LANGUAGE does on a disc in one language.

The row is saved with the options (`SAVE_TAG_OPTIONS` byte 9; a save without it was played with the extended story).
Switching takes effect at once at the title (the script text is read again, as for FONT and LANGUAGE; the maps when
entered). A Continue applies the save's value, unless OPTIONS was changed since the start; then, if the save was played
with the other story, the tamer and the partner start in Jijimon's house at its exit 0 (`modStoryRelocate`, `main_menu.c`;
`initializeLoadedMap` places them at the exit's arrival), the house the original's File City door picks: 205 once Angemon
or Monzaemon live in the city or prosperity is 50, else 218. The save may stand on a screen the other story does not
have, or behind a way out it does not have; Jijimon's house exists in both. Nothing else changes: flags, recruits,
items and the partner stay, and each story reads its own flags (the mod's are the engine's free 717-786).

The balance maps (`content/maps` Digimon lists, `tools/balance.py build`) are made for each story from its own story
compiler output. The map signs are pasted into the files each story puts on the disc (`tools/localize/signs.py --file`;
before 0199 they were pasted into the disc's own files, so a translated sign dropped a retouch on the same screen, MAYO10
and the TWNB city screens); the sign copies are made before the balance step, so a sign map's copy has the story's
Digimon but not a balance list of a map the story did not edit.

## NEW DIGIMON

Patch 0181. Each species file of a species the original game raises says `"vanilla": true` (`tools/species.py`, ids
1-65); `species.py build` writes them as a bitmap in DIGI.DAT's header sector (`SPECIES_HEADER_VANILLA` 0x780, a bit per
id; `isVanillaSpecies`, `mod_species.c`; a file without it counts every species as vanilla). With the row OFF,
`modSpeciesAllowed` (`mod_options.c`) keeps every way the partner changes species to them: the Baby I's fixed Baby II,
the In-Training, Rookie and Champion/Ultimate candidates (with the model-fit test, `evolution.c`), the Ultimate rules
(Machinedramon) and the evolution items past the original ones (`handleEvoItems`). The original's special rules and
items name only vanilla species. The chart shows the original overview (the code before patch 0170,
`renderEvoChartViewVanilla`, `chartVanillaInput`) and its trees leave the other species out (`chartEvolutionPath`: DIGI.DAT's
links fill the original rows' empty slots, so the rest is the original row). A partner that is already a new species
is turned, when a save is loaded with the row off (patch 0182, `modVanillaSwap`, `main_menu.c`), into its species file's
`vanilla_as` (a vanilla species of its level, an Ultimate for a Mega: chosen from the nearest
vanilla ancestor down the vanilla rows, a shared specialty first; reviewable and editable in the files). Stats, care and
age stay; the equipped techniques become the new species' slots of the same techniques (none: its first learned one, or
its first one, learned), the finisher its own. The save remembers the swap (`SAVE_TAG_VANILLA_SWAP` 0x000A: the species
and the vanilla one); loaded with the row on and the partner still that vanilla species, it is turned back. Raised and
recruited flags are never cleared: with the row off the chart only hides the new species. A New Game with the row off gets one of
the nine original rookies from Jijimon's quiz (`quiz.vanillaCells`, [balance.md](balance.md)), so no swap is needed.

Levels follow the row too (patch 0335): an original whose species file gives it another level than the disc (the canon Megas Phoenixmon, HerculesKabuterimon, MetalEtemon, Machinedramon, Analogman, Jijimon; the tier pass's IceLeomon, Yanmamon, Flarerizamon, Vermilimon, Icemon, BlueMeramon, Meteormon, KingSukamon) has its disc level with the row off, so the original game has no Mega; `vanilla_as` and the evolution guard count a vanilla species at that level.

After changing a species’ tier, clear its old `vanilla_as` and regenerate with `tools/vanilla_as.py --write`.
The evolution guard rejects a fallback of another level, except Mega → Ultimate because the original game has no Mega.
Saved partner ids remain valid; Continue reads the current mapping. Existing swap tags restore their recorded original
id when the option returns to ON, without depending on either species’ level.

## Cheats

CHEATS defaults to OFF. With it on, Select opens the Cheats menu from the field
pause only. Select does nothing when the menu cannot open; the hint is hidden
there too. The menu freezes world ticks while editing. It provides money, care
recovery, parameter editing, evolution, teleportation, healing, native save/load,
return to title and a confirmed old-age death.

The menu's SELECT SHORTCUTS row (`MOD_OPT_SHORTCUTS`) defaults to OFF. Turned on,
under CHEATS, it adds Select + L1/R1 for partner changes and Select + L2/R2 for
map jumps where the existing world-state guards allow them. Turned off, those
presses do nothing, not even the refusal sound.

While the game is paused and Select would open the menu, a box at the bottom of
the screen says so (`LAB_STR_PAUSE_HINT`, `utils2.c`). Keep each translation within
200 pixels so the box stays clear of the status bars. The hint borrows the text-area row at 0xE4 and
restores its pixels when the pause ends.

The parameter editor covers care, evolution timers, age and lifetime, current and
maximum HP/MP, and combat stats. Its lifetime stops at 1 hour: at 0 the partner dies on the
next tick, so that only happens through the home row *Die of old age*, which asks
first, uses the idle guards of the other confirmed actions and counts as a natural
death for the rebirth bonus (patch 0307). Left/right adjusts by the displayed amount;
up/down changes that amount. Confirm applies the value and Cancel discards it.
Stat and care limits are enforced, and lowering maximum HP/MP clamps the current
value. Evolution rows show species stages; map rows show internal map codes.
In lists, up/down moves one row; left/right or L1/R1 moves ten rows, clamped at
either end (patch 0287). This also applies to the parameter list. The numeric
editor keeps the adjustment controls described above.
Choosing a destination performs the action through the normal idle/model guards.

Save/load retains the native memory-card flow and its confirmations. The saved
CHEATS option occupies bit 0 of byte 12 of the options extension; its title-header
copy uses the high bit of the options count. SELECT SHORTCUTS is bit 1 of that byte
and has no header copy: it is not a row of OPTIONS, so the loaded save always decides
it. Older records default to OFF, and explicit OPTIONS edits retain priority over
Continue.

`tools/test_cheats.py`, `tools/test_lab.py` and `tools/test_lab_labels.py` compile
the actual patched helpers with address/undefined-behavior sanitizers to check
save compatibility, bounds, care actions and labels. Pass the patched decompilation
worktree as their first argument.

`python3 tools/dev/playtest/qol.py DISC --exe EXE --out build/qol-proof` checks list
navigation and the numeric editor in original 2 MB RAM. It also checks three
consecutive farm purchases, insufficient bits and a full inventory for Palmon's
Giant Meat and both Vegiemon vegetables. Set `EMU_PORT` for your own instance.
The harness uses a private English copy of the release save, original 2 MB RAM
and counted emulated refreshes for input. Farm sections start through the script
hook; purchases and leaving use pad input. A `--boot-state` checkpoint must come
from the exact same disc. `--case navigation` runs only the list checks.

## Enemy life bars

Enemy life bars are permanent. The 32×3 fill sits in a black frame above each
living, on-screen enemy's species height, with its current HP in outlined 3×5
clock digits immediately to the right. The fill keeps at least one pixel until
the enemy dies. The group moves inside the screen and below the top corner HUDs;
finishers, cutscenes and results suppress the new head bars. Arena and VS keep
their fixed HP/MP panels and add the same head bar for the opponent.

Select no longer hides life bars. Their display is continuous in wild, arena and
VS battles. The player panels and finisher meters retain their existing behavior.
Cheats still uses Select while paused and its optional field shortcuts.

Record 0x0009 retains 14 bytes. Byte 12 keeps CHEATS/SELECT SHORTCUTS; byte 13
is reserved and written as zero. Loading ignores both old inverted enemy-bar
bits. The title header retains the first 12 option bytes, its CHEATS bit 7 and
count bits 0–4; its former enemy-bar bits 6 and 5 are cleared on write and ignored
on load. Existing save layouts remain readable.
