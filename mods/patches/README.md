# mods/patches: the C patch series

The single series of C changes on the decompilation (`decomp/`, at the commit the repository pins), applied with
`git am` in file order. The series is linear: a change to an earlier patch is a new patch on top.

```
tools/mods.sh prepare [mods|int]   # a working copy with the series applied: mods = the core (0001-0050), int = all
tools/mods.sh build [mods|int]     # build it with GCC (Docker); FPS=20|30|60, FONT=original|a|b override the defaults
tools/mods.sh save [mods|int]      # export the commits made in the working copy as new patches at the end
```

Flow: `prepare` -> edit in `build/decomp-int/src` -> `git commit` there -> `save` -> `build`. `tools/build-full.sh` makes
the full disc.

**Heap.** Every byte a patch adds to the main executable comes off the heap the screens load their models into; too
little and a screen never finishes loading. Measure `main_BSS_END` before and after a patch and keep data that is not
needed every frame out of the main executable; `tools/build-full.sh` stops when a screen would be short
(`tools/heapcheck.py`).

**The font patch (0024)** is the one exception to "a change is a new patch on top": it is regenerated in place when a
glyph is appended to `tools/font/extra.txt` (`font_extra.h` is its own file, which no later patch touches;
`docs/mods/font.md` "Adding a glyph").

## The series by feature

| patches | feature |
|---|---|
| 0001-0004, 0022, 0094 | GCC build fixes: buffers sized for the GCC link, null checks, array overruns the original's layout hid |
| 0005-0012, 0048, 0063, 0070, 0085 | the lab menu (a test menu in the pause screen) |
| 0013-0020, 0065, 0082, 0146-0147 | wider ids: 16-bit screens, species and items, wide script opcodes, species up to 1024, screens beyond 255 (`SCRN.DAT`, `tools/screens.py`), new disc file names (`tools/newfiles.py`) |
| 0021, 0023, 0050, 0124, 0220, 0231 | fixes of bugs of the original game |
| 0024-0025, 0086-0089, 0095, 0097, 0099-0105, 0108-0109, 0175, 0177-0178, 0215 | the font: extra glyphs, glyphs placed to the pixel, font b, kerning, long names, packed rows (`docs/mods/font.md`) |
| 0026-0049, 0080 | 60 fps: a fixed 20 Hz logic tick with interpolated rendering; the `FPS` build parameter |
| 0051-0062, 0064, 0079 | the merged features: imported species in `DIGI.DAT` and save v2, new partners, the Mega level, stat caps, memory reclaim (streamed backgrounds, trimmed NPC models), sound limits |
| 0066-0068, 0170, 0176, 0178-0180, 0213, 0219 | species portraits, cup lists and the evolution chart (detail view, requirements card, scrolling) |
| 0069-0077, 0155-0156 | status bubbles over the partner |
| 0078, 0083-0084, 0087, 0106, 0116 | camera for big partners, technique effect origins, record originals (`docs/mods/species.md`) |
| 0081, 0110-0111, 0117-0123, 0125-0128, 0130-0137, 0139-0143, 0229, 0235 | game rules as data: species tables, evolution, medals, tamer level, care, clock, new game, items, economy, training, battle, fishing and curling, written by `tools/balance.py` from `content/` (`docs/reference/balance.md`) |
| 0090, 0138, 0145 | text sources: the text bank by key (`tools/textsrc/`) and script text storage |
| 0091-0093, 0096, 0114-0115, 0129 | saves: extensions, robustness, tagged records (v4), content absent from the build dropped on load |
| 0098, 0113, 0208-0211, 0216 | memory: code moved into overlays, cold animations (`tools/coldsplit.py`), stack size, compact file tables, the menu overlay |
| 0107 | the gym's "learned" box measured in the font |
| 0112 | a story built from zero: a missing script section runs nothing (`docs/mods/data-sources.md`) |
| 0144 | comment fix |
| 0148-0149, 0157, 0165 | temporary test tools: roster switch and screen jump (they go with the lab menu) |
| 0150-0155, 0158 | the care menu in front of the partner (food, cures, sleep, scold) |
| 0159-0160, 0198, 0206 | streaming fixes: map palettes from a resident copy, the background stream in battles, background overlay loads |
| 0161 | prosperity counts every recruited species |
| 0162-0164, 0218, 0282, 0297 | new status bars, the status screen's care numbers and tiredness bar |
| 0166 | the digital clock |
| 0167, 0169, 0173-0174, 0193-0194, 0201, 0205, 0214, 0241 | the OPTIONS menu and its rows (`docs/mods/options.md`) |
| 0168 | the death scene's veil |
| 0171 | STR movie playback timing |
| 0172 | timed field battles |
| 0181-0182 | the NEW DIGIMON option and the vanilla swap of saves |
| 0183, 0190-0191, 0195, 0203 | language: English / Spanish, map signs, the name keyboard (`docs/mods/translating.md`) |
| 0184-0189, 0196-0197, 0200, 0204, 0299 | quality of life: battle x2, evolution skip, training block |
| 0199 | the EXTENDED STORY option |
| 0202, 0207 | optional partner name |
| 0212 | the DIFFICULTY option |
| 0217, 0232, 0240, 0291, 0298 | imported field animation transitions |
| 0221-0222 | the partner's HP and MP in the triangle menu |
| 0223-0228, 0237 | amount boxes for trades, card packs and the card machine |
| 0230 | ground items once a day |
| 0233-0234, 0236, 0238-0239 | quick battle start |
| 0242-0243 | additional translations and Japanese font |
| 0244 | optional cheats and save-compatible option storage |
| 0245 | first-boot language picker and Catalan |
| 0246 | compact hashed sector entries for the eight-language disc |
| 0247-0254 | care/stat editing, evolution, teleportation, native save/load and menu labels |
| 0255-0256 | Fit complete translated title labels within the existing menu and glyph buffer; no additional RAM. |

Each patch's commit message describes its change in detail.

0257 shows the release version on the title screen and title menu (tools/version.py through MOD_VERSION).

Patches 0258–0263 recover heap space through compact file routes and tables, overlay helpers, and staged NPC models.
Patch 0264 fixes gym calendar rollover; 0265 tracks daily pickups by stable location IDs.
Patches 0266–0269 correct composed reward text, guide rows and localized raster labels.
Patch 0271 shows the Select hint for the Cheats menu while paused.
Patch 0272 puts the Select + L1/R1/L2/R2 shortcuts behind a row of the Cheats menu, off by default.

| patch | feature | main executable cost (`main_BSS_END`) |
|---|---|---|
| 0273 | Jijimon's seven-question, three-answer starter quiz; 35 partner rookies and opening techniques | +832 bytes: 0x801ca0b8 → 0x801ca3f8 (series through 0272 → 0273, same EN bank, original 2 MB target); heapcheck passes |
| 0274 | Keep translated triangle-menu labels clear of all five clock frames | +0 bytes: 0x801ce870 → 0x801ce870 (all eight padded language banks, original 2 MB target); eight-entry label table stays 64 bytes; heapcheck passes |
| 0275 | Ignore Cheats menu Select outside the field pause; match the hint/menu guard before replacing box 5 | +16 bytes: 0x801cb2b4 → 0x801cb2c4 (controlled build, same EN bank and padding); heapcheck passes |
| 0276 | Saved enemy-bar style and continuous/brief Select choice; head bars in wild, arena and VS fights; both defaults ON on old cards | +216 bytes: 0x801ce870 → 0x801ce948 (same eight-language EN bank); heap −208 after alignment; BTL +1792, STD +1760, VS +1860, MENU +108 bytes; overlay assertions and heapcheck pass |
| 0277 | City residents tab; separate prosperity refresh and original-story range | +1,892 bytes: 0x801ce958 → 0x801cf0bc (all eight padded banks, original 2 MB target); code +1,824 bytes; story heap minimum 1,840 bytes on screen 361; all 320 setups fit |
| 0278 | Continue looping music across screens with the same resolved BGM; retain explicit resets and one-shot replay | +352 bytes: measured on top of 0276 (measured against the series through 0275, same EN bank and build inputs, original 2 MB target); heapcheck passes |
| 0279 | Show Monochromon shift profit, customer count and blue target bar | +960 bytes, measured before the rebase over 0275-0276: 0x801cab40 → 0x801caf00 (same English test bank, original 2 MB target); 0x801ced18 with 0280 in the eight-language image; heapcheck passes |
| 0280 | Lower Monochromon recruitment from 3072 to 2560 bits and rescale the profit bar | +0 bytes: 0x801caf00 → 0x801caf00 (same English test bank, original 2 MB target); series ends at 0x801ced18 in the eight-language image; heapcheck passes |
| 0281 | Restore seven original field NPCs through disc-derived NPC records; preserve partner and tournament identities | +400 bytes before the rebase over 0277-0280 (0x801ce948 → 0x801cead8); series ends at 0x801cf74c in the eight-language image, original 2 MB target; heapcheck passes, story minimum 160 bytes on screen 361 |
| 0282 | Status screen: discipline and care mistakes as numbers beside the weight, a tiredness bar as the fourth row (red from 50); only with NEW STATUS BARS on; the original bars' four calls compacted | about +600 bytes: the function and data sizes of the ELF against the originals; 181,968 bytes of heap with 0282 still out |
| 0283 | The card menus' read-only messages, labels and save icon move from the executable into `MENU_REL` | about -2,400 bytes: series ends at 0x801cf040 in the eight-language image (0x801cf74c before 0282-0283, about -1,800 net); `heapcheck` and the 320 story setups pass, screen 361 keeps 1,952 bytes |
| 0284 | Clear text with VRAM fills and zeroes so DuckStation with Enable Texture Cache stops showing old text over new | +336 bytes: 208 of code and 128 of zeroes, from the symbol sizes of the English test build (original 2 MB target) |
| 0285 | Finish active techniques, hit reactions and buffered damage before a field-battle timeout; preserve natural outcomes | +0 resident bytes; BTL +120 bytes. Controlled eight-bank base padding: main_BSS_END stays 0x801cf190, heap 183,648 bytes. |
| 0286 | Bound large-partner world framing; converge while idle without replaying the tamer delta; retain small-partner and battle behavior | +112 resident bytes including linker alignment: 0x801cf190 → 0x801cf200, heap 183,648 → 183,536 bytes (controlled eight-bank base padding). |
| 0287 | Cheats lists: left/right moves ten rows, up/down one, clamped at the ends; shared by parameters, evolution and teleport | +0 resident bytes; MENU size unchanged at 47,128 bytes. Controlled eight-bank base padding: main_BSS_END stays 0x801cf200. |
| 0288 | Show the shared title version during field START pause, above the clock; preserve the borrowed text row | +144 resident bytes: 0x801cf200 → 0x801cf290 (controlled eight-bank base padding). Integrated Spanish padding adds another 48 bytes: final 0x801cf2c0, heap 183,344 bytes; all 320 setups fit in each language, screen 361 minimum 1,312 bytes. |
| 0289 | Clamp wild-battle target-score Defense to the old range, including external cheats; preserve old-range scores and target ties | +0 bytes: 0x801cb880 → 0x801cb880 (same English test bank, original 2 MB target); heap stays 198,256 bytes; BTL +36 bytes (151,240 → 151,276), overlay assertions and heapcheck pass |
| 0291 | Let pending navigation/needs changes leave imported field walks of at least 40 ticks after 24 completed ticks; preserve the step rules of 189 and 201 and avoid restarting an already active condition walk | +96 bytes: heap 183,504 → 183,408 and screen 361 margin 1,472 → 1,376 in the eight-language layout, BSS unchanged; `heapcheck` passes |
| 0292 | Draw curling HUD on every frame, interpolate stones and held stones, keep collision order and avoid redundant streamed background uploads; choose a steady cadence | +68 bytes: 0x801cb9fc → 0x801cba40 (same EN bank and version, original 2 MB target); aligned heap −80 bytes; draw history and tile helper stay in KAR; exposing the existing 12-byte VRAM identity table adds no RAM |
| 0293 | Move laboratory UI literals, field/home tables and redraw cache into MENU; keep field roster captions resident and clear scratch on entry | −2,472 resident bytes: 0x801cf2c0 → 0x801ce918; aligned heap +2,480 to 185,824 bytes in all eight languages. MENU grows 2,472 to 49,600 bytes, with 4,960 spare; all 320 setups fit in each language, screen 361 minimum 3,792 bytes. |
| 0294 | Replay curling's prompt text, selection cursor and confirm button on extra render passes |
| 0295 | Keep curling's aim camera off the CD: the forced whole-window upload is skipped there, the overlay keeps the window from the ring |
| 0296 | Count extended prosperity only for the owned City roster; a 14-byte bitset is generated by the balance build from `content/tables/city-residents.json`; original-story rules stay intact | +96 resident bytes, BSS unchanged: 0x801cbe08 → 0x801cbe68 in a controlled default-file-table build; final disc heap and screen 361 checked separately |
| 0297 | Status screen: the divider moves to the middle, each care row has its number in a box beside the bar, the repeated discipline field goes and the care mistakes take its place; happiness is shown as 0..100 here and on the evolution card (rules keep -100..100); only with NEW STATUS BARS on | +337 bytes of code in `game_menu`; 320 story setups pass, screen 361 keeps 3,216 B on the eight-language image |
| 0298 | Keep an active condition walk from restarting at pending transitions after removing 0290 | Resident and full-disc memory measurements are recorded in reference/memory.md |
| 0299 | Restore the chart detail layout; Square opens a modal requirements table with full translated labels, fixed 12-pixel rows, ten-row scrolling, dimmed background and active cancel prompt; borrow and release the existing text rows | −1,684 resident bytes from the pre-popup core: main_BSS_END 0x801cea6c → 0x801ce3d8. Round two adds 700 resident bytes over 0x801ce11c; aligned eight-language heap 187,872 → 187,168 bytes, screen 361 margin 5,840 → 5,136; all 320 setups fit. Four primitive/number helpers move 800 bytes out of MENU; chartAppend stays there for its readiness-string relocation. MENU 54,512 → 54,000 bytes, 560 spare below EVL. |
| 0300 | Stop training x5 for natural evolution only when the tick's shared target picker finds a target; leave Fresh timer resets in the tick | +336 resident bytes: 0x801ceb2c → 0x801cec7c, aligned heap 185,296 → 184,960 bytes (controlled eight-language text padding and full file table, original 2 MB target); shared ladder saves 80 bytes over duplication; all 320 actual-archive setups fit, screen 361 margin 2,928 bytes. |
| 0301 | Complete exact half-turns by choosing counterclockwise on equal rotation distances; applies to scripted tamer, partner and NPC turns | −16 resident bytes: 0x801cb3cc → 0x801cb3bc in controlled EN builds; heap +16 to 199,488 bytes; 320 story setups fit, screen 361 margin 15,488 bytes |
| 0302 | Finish partner walks within one root-travel step; bound blocked or stopped arrival waits to 600 logic ticks | +512 resident bytes including a 16-byte watchdog: 0x801cb3cc → 0x801cb5cc; English test-disc heap 199,472 → 198,960 bytes; screen 361 margin stays positive at 15,488 bytes (conservative cap) |
| 0303 | Ignore the script command that unloads a Digimon which is not placed (a `.leave()` on an NPC the map never spawned freed an undefined entity and hung later loads) | +96 resident bytes (`scriptUnloadEntity` 0x34 → 0x94 bytes); eight-language full build: heap 184,368 bytes, 320 story setups fit, screen 361 margin 2,336 bytes |
| 0306 | Keep the whole partner species past 255 in scripts: `STORE_DIGIMON_TYPE` stores 0xFF past 254, the attribute gates and `{digimon N}` read the partner back, the Sukamon backup keeps its species in saved register w15. Fixes VioletElecmon at the mansion gate and partners reverting to another species. |
| 0307 | Cheats: the lifetime editor stops at 1 hour, and a confirmed *Die of old age* row sets the lifetime to 0 so the natural death runs at once | Eight-language build: heap 186,992 bytes, screen 361 margin 4,960, heapcheck passes; MENU 54,164 bytes, 396 spare below EVL |
| 0308 | Read ENDI again in `start_ending`: the game-clear save's MENU_REL fills 27 sectors, 0x2E0 bytes into ENDI. Link asserts count whole sectors | 32 B of main; heap 185,968 B, screen 207 keeps 1,248 B |
| 0313 | With RAM above 2 MB the partner's cold animations stay at 0x80200000 and start without the disc; the title screen shows a panel when 8 MB RAM or a CPU overclock near 250% is missing, one row and one check each, and nothing when both are there | `tools/dev/playtest/cold_cache.py` |
| 0314 | Move 17 read-only tables and paths that only VS reaches into `VS_REL`, which pays for 0313 | Eight-language build: heap 185,264 B, screen 207 keeps 544 B |

Patch 0304 lets scripts set, clear and test recruited bits for species 112..1023
through reserved operands of the existing trigger instructions. Prosperity keeps
the 14-byte low-ID membership table and an exact-sized generated u16 high-ID list;
the current roster has 20 entries, 40 bytes of list data. `tools.city_residents
--c-extra-header TREE` must run before a native build (the integrated drivers do
this automatically). The City tab and save format already support these IDs.
Measured on the eight-language build: `main_BSS_END` 0x801ce860, heap 186,000 B.
The tightest setups are screen 207 with 1,280 B of margin and screen 41 with
4,216 B. The 20-entry list and roster cost 24 B of main against the same patch
with an empty list.

Patch 0290 is removed: species 224 now uses the native MetalGreymon field programs.
Patch 0298 retains its general condition-walk restart guard, without 224 stride rules.

The localized Ogre Tunnel takeover sign is a map-art change in
`tools/localize/signs.py` and `content/localized/signs/delta`, with no engine
patch or resident executable growth. See [game languages](../../docs/mods/language.md).
Whamon's timed return at the city dock is a story-only fix, using the existing
spawn instruction; it adds no engine patch or resident executable bytes. See the
[shore story notes](../../story/mods/what-the-island-forgot/arcs/shore/README.md).

Patches 0309-0312 answer a tester's v0.0.3 report: the City tab reads each cell's level from its packed roster id instead of a species record (0309), the version stamps stay inside the visible rows (0310), play time shows two-digit minutes (0311) and the care menu runs before map interaction (0312). Together they lower `main_BSS_END` by 16 bytes.

Patch 0315 draws a still meat bubble over the meat farmer (NPC slot 6 of screens 168-179) while a harvest waits: p31 >= 1, or the first visit to Tanemon. It reuses the status bubble's sprites, so it needs no new art, and it hides while a script runs. Proof: real talk with Palmon on an original-2-MB boot.

Patch 0316 slims patch 0315 from 704 B to 496 B of heap: two sprite calls with the whole bubble sprite, no second caller of the row's drawing code, whose inlining that caller would stop. Eight-language build: heap 184,768 B, screen 207 keeps 48 B.

Patch 0317 keeps both idle frames of every icon in the chart block and alternates them in the chart and City grids.
