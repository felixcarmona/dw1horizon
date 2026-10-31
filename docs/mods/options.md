# Options: the title menu's OPTIONS

Patches 0167, 0169, 0173-0175, 0177, 0180-0182, 0199, 0212, 0234, 0239 and 0244 (`mods/patches/`). The title menu has a fifth row, **OPTIONS**, under BATTLE MODE. It
opens a box of thirteen switches (twelve in a `FONT=original` build, which has no FONT):

| Row | Values | Default | Effect |
|---|---|---|---|
| JAPANESE CONTROLS | OFF / ON | OFF; ON on a Japanese base disc (patch 0241) | the Japanese disc's buttons (below) |
| DIGITAL CLOCK | OFF / ON | ON | the HH:MM plate under the clock (patch 0166, `renderDigitalClock` in `clock.c`) |
| NEW STATUS BARS | OFF / ON | ON | the happiness and discipline bars as 0162-0164 draw them; OFF draws the original's: the field's (`renderStatusBars`, `partner_impl.c`) and the triangle menu's Status page (`renderMenuStatusBar`, `game_menu.c`, patch 0218) |
| EVOLUTION GUIDE | OFF / ON | ON | the evolution chart's requirement card and green lines (patch 0176); OFF draws the original detail view |
| NEW DIGIMON | OFF / ON | ON | OFF: the partner evolves only into the species the original game raises (the species files' `"vanilla": true`, ids 1-65: the chart's 61 and WereGarurumon, IceLeomon, Gigadramon, MetalEtemon by items), so no Megas; the chart is the original sheet and its trees show the original rows (below) |
| EXTENDED STORY | OFF / ON | ON | patch 0199: the story with the story mods built onto the disc (What the Island Forgot: its new places, the city's new residents), or OFF the original story; changing it on a save moves the tamer to Jijimon's house (below) |
| DIFFICULTY | EASY / NORMAL | NORMAL | patch 0212: EASY, the partner deals double damage and takes half in battles and tournaments (below) |
| QUICK BATTLE START | OFF / ON | ON | patches 0234, 0239: a field battle starts the moment it is triggered, its BATTLE letters and bubbles over the running fight (patches 0233, 0236, 0238); OFF, the original start |
| FRAME RATE | 20 FPS / 60 FPS | the build's (60) | `MOD_FPS_MODE` (below) |
| FONT | NEW / CLASSIC / ORIGINAL | NEW | font b, ours; the original letters evenly spaced; the original font as the original draws it (below) |
| LANGUAGE | eight languages selected at build time | the build's (`LANG_BASE`) | the selected runtime languages ([languages](language.md)) |
| MAP SIGNS | ORIGINAL / TRANSLATED | TRANSLATED | patch 0183: the signs painted in the map backgrounds as the disc has them, or in the language |

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
takes 200 of the area's 256 pixels. With that font the two values do not fit beside it (200 + 2 x 61 pixels for "20 FPS"
and "60 FPS", more than the screen), so a row shows only its chosen value, as the original game's own settings do;
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

## FRAME RATE

With a build made with `FPS=30` or `FPS=60` (`dw/mod_fps.h`), `MOD_FPS_MODE` is the variable `MOD_FPS_MODE_RUN`
(`main.c`, the build's rate at start) and the row switches it between 0 (20, the original: one render per tick) and 2 (60); the game logic stays at 20 Hz.
Mode 1 (30) remains for an `FPS=30` build, whose row then shows neither value chosen until one is picked.
With `FPS=20` it is still the compile-time 0 and the extra passes compile out; the row then shows neither value chosen
and does nothing. Measured in an emulator (Jijimon's house, 10 s): 30 FPS row 29.95 fps, 60 FPS row 60.0 fps,
20.0 ticks/s in both. An emulator too slow for the extra passes shows one frame per tick in either mode.

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
  (339, 183), CLUT (96, 500)) are drawn by `renderUIBox` and by the care menu's badge (patch 0158). The US disc has no ○
  there. When `loadStackedTIMFile` uploads `ETCTIM.BIN`, `modButtonsTimLoaded` copies the frames from the file's own
  pixels and makes a ○ version: the cross (indices 0xC and 0xD, a 6x5 box in each frame) is painted over with the face
  (index 3), and a 6x5 ring is drawn where it was. The ring is red, (248, 96, 104) and (160, 48, 56), with a CLUT of its
  own: the frames' one with its two blues made red. That CLUT is kept in the page's filler (u 0x80..0xBF of v 0xE6, all
  index 15, which nothing draws), at VRAM (352, 230). The CLUT columns 288/304 of rows 480-511 were not used, because
  the tournament and VS portraits use them. With the option off, the × frames and the filler are uploaded back. A disc
  whose frames are not the expected 6x5 cross keeps the ×. The VS mode's own `SYSTEM_W.TIM` load (`vs_select.c`) is
  not hooked. The mod carries no pixels of the disc.
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
- **Saved.** The options are the record `SAVE_TAG_OPTIONS` 0x0009 (`u8[9]`: buttons, clock, frame rate as 30/60, bars, font, evolution guide, new digimon, language, map signs),
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

## Cheats

CHEATS defaults to OFF. With it on, Select opens the Cheats menu from the field
pause only. Select does nothing when the menu cannot open; the hint is hidden
there too. The menu freezes world ticks while editing. It provides money, care
recovery, parameter editing, evolution, teleportation, healing, native save/load
and return to title.

The menu's SELECT SHORTCUTS row (`MOD_OPT_SHORTCUTS`) defaults to OFF. Turned on,
under CHEATS, it adds Select + L1/R1 for partner changes and Select + L2/R2 for
map jumps where the existing world-state guards allow them. Turned off, those
presses do nothing, not even the refusal sound.

While the game is paused and Select would open the menu, a box at the bottom of
the screen says so (`LAB_STR_PAUSE_HINT`, `utils2.c`). Keep each translation within
200 pixels so the box stays clear of the status bars. The hint borrows the text-area row at 0xE4 and
restores its pixels when the pause ends.

The parameter editor covers care, evolution timers, age and lifetime, current and
maximum HP/MP, and combat stats. Left/right adjusts by the displayed amount;
up/down changes that amount. Confirm applies the value and Cancel discards it.
Stat and care limits are enforced, and lowering maximum HP/MP clamps the current
value. Evolution rows show species stages; map rows show internal map codes.
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
