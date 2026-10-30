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
| 0162-0164, 0218 | new status bars |
| 0166 | the digital clock |
| 0167, 0169, 0173-0174, 0193-0194, 0201, 0205, 0214, 0241 | the OPTIONS menu and its rows (`docs/mods/options.md`) |
| 0168 | the death scene's veil |
| 0171 | STR movie playback timing |
| 0172 | timed field battles |
| 0181-0182 | the NEW DIGIMON option and the vanilla swap of saves |
| 0183, 0190-0191, 0195, 0203 | language: English / Spanish, map signs, the name keyboard (`docs/mods/translating.md`) |
| 0184-0189, 0196-0197, 0200, 0204 | quality of life: battle x2, evolution skip, training block |
| 0199 | the EXTENDED STORY option |
| 0202, 0207 | optional partner name |
| 0212 | the DIFFICULTY option |
| 0217, 0232, 0240 | imported field animation transitions |
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
