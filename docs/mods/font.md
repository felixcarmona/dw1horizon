# Fonts, extended glyphs and text layout

The mod executables (`build/decomp-mods`, `build/decomp-int`: patch 0024, so every one of them) draw
**á é í ó ú Á É Í Ó Ú ñ Ñ ü Ü ¿ ¡ à è ò À È Ò ï Ï ç Ç · « »** and the punctuation the US font
lacks: **( ) & % / … [ ] # * ~ @ – — ♪** everywhere the game draws text: script dialogue and selection boxes, menus
(`drawString`), and names. The original executable has no glyphs for them: use a mod executable, or let the tools
draw them plain (accents stripped, `…` as `...`, `–` `—` as `-`, `♪` left out; the others are refused at their line).

**The characters a line may use**: letters, digits, space and `. , ? ! ' " : ; + - =` (the original's 79 glyphs, with
`○ □ △ ×`), and for `--exe mods`, `species`, `story-state` also the 44 above. An executable built before a glyph was
appended does not have it: the tools read how many extra glyphs the target executable has from its build
(`fontgen.py glyphs EXE_DIR`) and refuse the newer ones at the `.py`/text line ("Tools" below), so a stale executable
never draws one as another glyph.

**The buttons** are written as the button they show: `×` (code 81A2), `△` (817E), `○` (819B), `□` (81A0). The US font
redrew two of them, so the codes do not mean what Shift-JIS says (there 81A2 is △ and 817E is ×); every tool (bytecode,
the text banks, `extract-text`, `fontgen.py preview`) maps them as the font draws them, and the executable's strings,
whose `decomp/text/*.yaml` keep the Shift-JIS labels, are given to `gen_text` swapped (`tools/localize/executable/bank.py`). On the
US disc × confirms and talks, △ opens the menu and cancels, ○ is the "alternative" button (tens in a shop, the camera
while fishing) and □ takes all (`decomp/include/dw/input.h`); the US text colours them 6, 5, 10 and 4.

Checked in the emulator: a quest with every character in Jijimon's
dialogue and in a selection box, and the same
characters in the lab menu (`drawString` → `renderString`). Each glyph in VRAM
matches the offline preview of `tools/fontgen.py` pixel for pixel.

## How the game draws text (USA)

- The font is **in the executable**, not on the disc: `CHAR_TO_GLYPH_TABLE`
  (79 Shift-JIS codes) and `GLYPH_DATA` (79 × `{u16 rows[11], u16 width}`),
  `font.c`. Each row is 12 pixels, bit 15 = leftmost, **0 = ink**. The last
  entry of `CHAR_TO_GLYPH_TABLE` is overwritten with the code being looked up
  (a sentinel), so an unknown code draws the last glyph.
- `drawGlyph(code, x, y)` expands one glyph into a 4-bpp 12×11 cell and
  `LoadImage`s it into the text area of VRAM (x 704, y 256, 256×256 px). The
  x is divided by 4, so **glyphs land on a 4-pixel grid** and each one
  overwrites the whole 12-px cell (the next glyph erases what the previous
  left to its right). It returns the glyph width (the advance).
- `drawString` (C strings: menus, names, battle HUD): a byte without bit 7
  is ASCII (`convertAsciiToJis`), a byte with bit 7 starts a 2-byte Shift-JIS
  code. A space is the 4-px glyph `81 40`.
- Script text (`showTextbox` → `drawString2`): the script stores 2-byte units;
  `00`–`1C` are control codes (escapes, `docs/mods/scripts.md`), anything else is
  a Shift-JIS code. Names inserted with `{player}`, `{item N}`... are C strings
  and follow the `drawString` rule. **Spaces**: in the original a space
  (`81 40`) only clears 12 px and advances by the width of the glyph before
  it (the advance is never updated for it): 12 px after a capital, 5 px after
  `,` or `.`, so `, ` and `. ` looked glued ("yes,sir"). **The mod
  executable advances a space a fixed 8 px** (`DRAW_STRING2_SPACE_WIDTH`,
  `script_textbox.c`; 12 in fixed-width mode as before): what the original
  gave after most lowercase letters, and a whole cell of the 4-px grid, so
  every space looks the same (6 would alternate between 4 and 8). With 8 px no
  original line of `DG.SCN` or `MAPHEAD.SCN` starts a glyph past the draw
  limit (the longest reaches 240 < 244). One line in a sized box (script 9)
  ends 1 px further right than the box's inner edge (the assembler warns about
  it).
- `renderString` then copies rows of that VRAM area to the screen as sprites
  (252 px wide, 12 px per row). `drawGlyph` skips glyphs that start at
  x ≥ 244.

## Fonts (build flag FONT, patches 0097, 0099 and 0175)

`FONT=original|b` (Makefile, **default `b`** since 0099; `tools/mods.sh build`, `tools/build-full.sh` pass it on).

| FONT | Glyphs | Placement |
|---|---|---|
| `b` (default) | ours, drawn in the game's style (`tools/font/b.txt` -> `src/main/font_b.h`), **and** the US font: OPTIONS' FONT chooses at run time, NEW / CLASSIC / ORIGINAL (patches 0175, 0177, `docs/mods/options.md` "FONT") | font b to the pixel; CLASSIC the US letters to the pixel; ORIGINAL as `original` |
| `original` | the US font only (`GLYPH_DATA`, `font_extra.h`) | the original code: 12-px cells on the 4-px grid. Up to 0174 the executable was byte for byte the one without patches 0097 and 0099-0105 (checked on the series up to 0106; 0107 and 0108 then change it on purpose: the gym's box, the calendar's spaces) |

`FONT=a` (the US letters placed to the pixel, a test font) was left out by 0175.

**Both fonts in one executable** (patch 0175, `FONT_SWITCH` in `dw/mod_font.h`): `FONT_PROPORTIONAL` is the run-time
`MOD_FONT != MOD_FONT_ORIGINAL` (NEW and CLASSIC; patch 0177 added CLASSIC), and every place that chose a font with `#if` asks it at run time: `drawGlyph` calls
`drawGlyphPixel` (font b) or `drawGlyphCells` (the original's code and glyphs, `ORIGINAL_GLYPH_DATA` and
`ORIGINAL_EXTRA_GLYPH_DATA` from `font_extra.h`); `measureStringMode`, `fitStringMode`, `drawStringMode` and
`textFitCode` the b versions or the original's with the long names' tight and condensed modes; `DRAW_STRING_PIECES`,
`DRAW_STRING_CELLS` and `TEXTBOX_ROW_PIECES` the pieces or the plain draw; `drawString2` its two loops; the map caption,
the calendar's first date, the figure space and the lab's roster caption likewise. The packed rows of box 0 (patch 0100)
stay with both fonts: they are an encoding of the row, and `drawString2` maps `'` and `"` to the codes both fonts draw
them at. The two rings of glyph slots share one buffer of 2 992 bytes: font b's 34 slots of 88 bytes, or the
original's 30 of 72 followed by `FIT_STRIP`; each ring waits for the GPU when it wraps (`DrawSync`). `modSetFont`
switches: it waits for the GPU, starts the ring and the kerning afresh and has the scripts read again from the files
paged for the new font (`modFontScriptsChanged`). Cost on 0174 (Makefile defaults): `main_BSS_END` 0x801D45A8, 8 168 bytes
more than font b alone (0x801D25C0: the original's glyph tables 2 952, the condensed table 624, the original's code
paths; the shared buffer gives back 528), which left the Makefile's old default `PARTNER_MMD_MAX` 0x20000 344 bytes
under the link's `MIN_HEAP` limit (0176 made the default 0x18800). CLASSIC (0177) adds 944 bytes: its glyphs are made at
the draw from the original's tables (`classicRows`: the ink moved to the first column, the advance the ink and one blank
column, the digits one advance of 7), and font b's kerning (`kernOf`) answers 0 for it; a name wider than its field takes
the original's tight line (`fitStringMode`), whose strip lies under CLASSIC's ring, so its upload is waited for.

**Font b** (`tools/font/b.txt`, format at its top): 11 rows, one baseline (row 8) for capitals and lowercase (the US font
has two: its capitals sit a row lower), capitals, digits and ascenders 9 rows, x-height 6, descenders rows 9-10, 1-pixel
stems, a 1-pixel gap after every glyph, a 4-pixel space. All 79 US codes, the 44 extra glyphs and the four buttons are
drawn (`×` at 81A2, `△` at 817E, as the US font draws them). The letters follow the design mockup, the squared capital A
included (patch 0101); the glyphs the mockup lacked are drawn in its style. Accented capitals have a 7-row body under a 2-row accent (row 0-1),
as `extra.txt` does for the original. The digits share one advance (6), the 1 centred. `fontgen.py font-sheet b
OUT.png` shows every glyph between neighbours with sample lines at 1x and 4x; `fontgen.py preview "TEXT" OUT.png
--font b` one text.

With b, every species name (MetalGreymonVaccine 109 px, HerculesKabuterimon 106) and every item name (Omnipotent
Floppy 93 px) fits its field as the font draws it, so a b build draws every name with `drawString`: the long names'
tight and condensed modes are not needed while it draws (0095's codes 0x10/0x11 are then never written); since 0175 the
original font, chosen in OPTIONS, uses them again (0099-0174 left them out of a b build).

**Placement to the pixel** (`font.c drawGlyph`): the glyph is shifted right by `x & 3` inside a 16-px cell that starts
at `x & ~3`, and the halfwords this cell shares with the previous glyph's cell (same row) take that cell's pixels, so
the upload no longer erases the previous letter's last columns. `clearTextSubArea` forgets the previous cell. The ring
is 40 slots of 88 bytes (the original's 3 600 bytes) and waits for the GPU when it wraps. A space is the font's blank
glyph (advance 4); tabs and the position codes clear from the next grid cell (`clearFromPen`). A glyph's `width` holds
its advance in the low byte and the original glyph's width (its *cell*) in the high byte.

**Rows cut into pieces** (patches 0097, 0105): some screens copy a row of VRAM text in pieces at offsets made for the
original advances (`renderString(..., w, h, srcX, srcY)`: the tab titles "Status  Tech", "YearDay", "HPMPnight",
"TechsetFinal  Techs"...). Two ways keep every piece holding exactly its characters:

- **Pieces** (`DRAW_STRING_PIECES(str, x, y, CROPS...)`, `font.c drawStringPieces`, patch 0105): the crops' offsets of the
  row are given at the draw (read from the screen's `renderString` calls); a glyph belongs to the crop that
  holds its original cell (on the 4-pixel grid), and each piece is drawn with the font's own spacing and kerning from
  where its first glyph's original cell started, or centred in the span its original cells took (`PIECE_CENTRE`: the tab
  titles, the chart's level names, the centred titles "Medals Chart", "Card List", "Tree"). A piece's leading spaces only
  move its start. Used for the menus' packed labels (`STATUS_VIEW_LABELS`, `TECH_VIEW_LABELS`, `PLAYER_VIEW_LABELS`,
  `CARD_CHART_LABELS`, the stat labels Off/Def, `STR_YEAR_DAY` in `game_menu.c`), the save screens' Yes/No rows
  (`main_menu.c`; patch 0102 added the in-world save prompt's, whose "N" of No was drawn on the Yes row; patch 0109: No's
  piece is `PIECE_LEFT`, it starts as far into its crop as Yes, since the two crops are shown one under the other: the
  spaced "Yes No" had put it 4-5 pixels right), Mojyamon's header (`MAIN_D_801307CC`) and the curling options (`kar.c`). Two crops placed side by side on the screen as they lie in
  VRAM (the Tech help's "C" + "ancel - △...") are one piece. The original font draws them with `drawString`, as before.
- **A text box row in pieces** (`TEXTBOX_ROW_PIECES(id, row, CROPS...)` after `createTextbox`, patch 0109): one row of a
  script text box laid out as `drawStringPieces` lays out a C string (`script_textbox.c drawString2Pieces`, `font.c
  drawGlyphPieces`, which both share), each glyph's original cell what `drawString2` advanced in the original (a space: the
  glyph before it). The card shop's confirm box (`CONFIRM_BOX_LAYOUT`): "All right?" to the pixel, Yes and No each centred
  in its crop's original span. The original font keeps that box in its cells.
- **Cells** (`DRAW_STRING_CELLS`, `TEXTBOX_IN_CELLS(id)` after `createTextbox`): each glyph's ink centred in its original
  cell. Kept for the digits row `MAIN_D_80124C54` that `renderNumber` copies at 8-px steps (game menu, battle, STD, TRN,
  TRN2, VS) and the text boxes cut per cell: the tournament calendar (DGET boxes 1 and 2) and the shop's bits box. A space
  in these rows advances by the glyph before it, as the original did (a blank grade cell after a grade is 12 pixels, like
  the cell; 12 at a row's start); the calendar's first date under 10 adds no space after its figure-space padding. The name
  keyboard keeps its 12-px cells (`DRAW_STRING2_IS_FIXED_WIDTH`), each letter centred.
- **The original font** (patch 0108): the boxes of `TEXTBOX_IN_CELLS` keep the original's rule for a space there too (by
  the glyph before it, 12 at a row's start), not patch 0025's fixed 8, which had moved the calendar's dates a column ("9 1
  01 11 21"; bisected: the series up to 0024 draws it as the retail disc, 0025 breaks it, the GCC build alone
  does not); its first date under 10 is written without its padding space (the original's advance at a row's start was
  never set: 0 in the retail and GCC builds).

Found by a screen tour that shoots every text screen and its VRAM text area, and a survey of every `renderString` crop:
a split letter (the "Year[1 )ay" of the pause menu, the "Yes N" / "lo" of the save prompt) means a row that needs pieces.
The tour includes the screens that are hard to reach (calendar, card shop, title and memory card Yes/No, Tech status
labels, Mojyamon, curling, the gym's box).

**The gym's "learned" box** (patch 0107, every font): `TRN_renderMoveLearnedBox` copied the move name `(strlen / 2) * 12`
wide, then 12 pixels of "was mastered!" and 48 more on the next row (the Japanese layout: "を" after the name, "おぼえた"
below), which cut the line in every font and text source. The name and the text are now copied at their measured widths
(`measureStringMode`), on one row when they fit the box's 156 pixels ("Spit Fire was mastered!" with font b), else the
text on the next row ("Spit Fire" / "was mastered!" with the original font and the US text).

**Kerning** (font b, patch 0103): `tools/font/b.txt` `kern LEFTS RIGHTS DELTA` lines, the pairs of the design mockup: T F V Y P W before lowercase letters, the period and the comma, r f before those two, one pixel
closer; the accented lowercase as their letter. `fontgen.py` refuses a pair whose ink would touch (no blank column left on
some row), so the mockup's pairs that touched in b are left out (W before lowercase and the period, P before m n r u v w x
y z ú ü ñ, V Y before ñ, y before . and ,): 121 pairs. `fontgen.py font-header b` writes them as `KERN_RULES` in
`font_b.h`; `drawGlyph` kerns a glyph drawn where the previous glyph's advance ended on the same row (a space, a column
code, a clear or a new string elsewhere breaks the pair; never in the original's cells or the name keyboard's cells): it
is drawn `k` pixels further and its advance returned `k` longer, so every caller's pen follows. `measureStringMode` counts
the same pairs, and so do the tools (`fontgen.kern`, `text_width`, `render_font`; `backend.text_px`; `bytecode
line_metrics_pixel`). The mockup kerned across a space ("T a": its layout kept the letter before a space as the previous
one); the game does not.

**Map caption** (patch 0104): the US map names are centred with spaces made for the original's letters ("      Native
Forest     ") and the caption's rectangle came from `strlen`; with a font placed to the pixel the name is drawn without the
padding and its rectangle centred by its measured width (`map.c mapCaption`). `FONT=original` keeps the original code.

**Numbers**: `intToStringSJIS` pads with a figure space (code `824E`, `FONT_FIGURE_SPACE`, as wide as a digit) and the
digits of a and b share one advance, so prices and amounts stay right-aligned.

Cost (`main_BSS_END`, the Makefile's defaults): `original` 0; `b`
+48 bytes on integration (0x801C7770; 0097-0101 had saved 1 876, kerning, the caption and `drawStringPieces` with its
crop tables spend 1 924), +32 on tier 2 (0x801C920C: the 2 MB headroom 47 348 bytes over `MIN_HEAP`). On 0109: `b`
0x801C7AE0 on integration, 0x801C957C on tier 2 (46 468 bytes over `MIN_HEAP`; 0109's row pieces +744 on integration, +728 on tier 2),
`original` 0x801C785C (0108 +148); `a` +340 / +356
(measured on 0097).

### Packed rows (patch 0100) and the tools

A script row lives in a 64-byte slot of `TEXTBOX_LINES_BUFFER` (31 two-byte units and the `0D 00` end). With a font
placed to the pixel, 240 px hold 40-45 letters, so `showTextbox` writes a letter, digit, space or `. , : ; ? ! ' " + - =`
of box 0 (dialogue and selections) as its one-byte ASCII form, which `drawString2` draws as the same glyph: a row holds
**62 bytes**. Other boxes keep two bytes a unit: the shop, keeper, Mojyamon and calendar code cut their rows at fixed byte
offsets (`TEXTBOX_LINES_PTR[0x246] = 0xd`...). Scripts on the disc do not change.

**Script texts shown in boxes 1-3** keep 31 units a row with every font: the code shows them with
`showMapHeadTextbox(idx, owner, box, section)` (box 1-3) or in the tournament info box: the item keeper's titles (MAPHEAD
1237 entries 4 and 5, keys `m1237.u4` `.u5`), Mojyamon's header (`m1238.u15`), the calendar's title (`m1240.u1`), the card
shop's question and answers (`m1240.u0`) and the cup texts (section 10 of the arena scripts 102, 168, 209, 213, box 3:
`s213.sec10.u*`...). `tools/dws/backend.py` `UNPACKED_KEYS` / `packed_key(key)`: `fits(row, packed=False)` and
`wrap(..., packed=False)` keep them to 31 units and 240 px; a hand-paged row of such a key that is longer is an error at
its line (`show_textbox(text("m1240.u1"))`) or key (a text-bank value); `tools/dws/bytecode/__main__.py asm --font-name b` warns about such a
row by section and table entry (`unpacked_entry`); `tools/dws/text/repage.py` leaves them as they are.

The tools read the target executable's font like its glyph count (`fontgen.exe_font EXE_DIR`: the linked executable,
else the worktree's last `font_sel.h`, else its Makefile's default; `dws --exe-font NAME`; `tools/build-full.sh` passes
the `FONT` it builds with): `tools/dws/backend.py` (`text_px` with the font's advances, `text_bytes`, `fits`: 62 bytes
and 240 px, the last row of a page 228 px, clear of the "next" button), `tools/dws/bytecode/__main__.py asm --font-name` (the same check on
encoded rows, `line_metrics_pixel`), `tools/localize/executable/bank.py exe-bank --font` (item names within 96 px as font b draws
them). `TEXT=us` builds still compile the US text for the original executable, so their `DG.SCN` and `MAPHEAD.SCN` are
the same bytes as before.

**`FONT=original` with `TEXT=ours`**: `text/ours` is paged for font b (208 entries re-paged by `tools/dws/text/repage.py`
with 62-byte rows). Built for the original font, a hand-paged entry with a row that does not fit it is wrapped again for
that font (`textbank.fit`: its words, never cut), and the build says so: `story: note: text source ours: 208 hand-paged
keys have rows too wide for font original and are wrapped again for it (...)`. None of them is a single-box MAPHEAD line
that would need more pages than the game shows.

## The new glyphs

| Code | | Code | | Code | | Code | |
|---|---|---|---|---|---|---|---|
| F040 | á | F048 | ï | F050 | À | F058 | ¿ |
| F041 | é | F049 | ü | F051 | È | F059 | ¡ |
| F042 | ó | F04A | ñ | F052 | Ò | F05A | · |
| F043 | ú | F04B | ç | F053 | Í | F05B | « |
| F044 | à | F04C | Á | F054 | Ï | F05C | » |
| F045 | è | F04D | É | F055 | Ü | | |
| F046 | ò | F04E | Ó | F056 | Ñ | | |
| F047 | í | F04F | Ú | F057 | Ç | | |

Punctuation (appended):

| Code | | Width | Code | | Width | Code | | Width |
|---|---|---|---|---|---|---|---|---|
| F05D | ( | 4 | F062 | … | 12 | F067 | ~ | 8 |
| F05E | ) | 4 | F063 | [ | 4 | F068 | @ | 12 |
| F05F | & | 12 | F064 | ] | 4 | F069 | – (en dash) | 12 |
| F060 | % | 12 | F065 | # | 12 | F06A | — (em dash) | 16 |
| F061 | / | 8 | F066 | * | 8 | F06B | ♪ | 12 |

The other Latin vowels and two symbols (appended for the name keyboard's pages, patch 0195):

| Code | | Code | | Code | | Code | |
|---|---|---|---|---|---|---|---|
| F06C | â | F073 | ö | F07A | Ê | F082 | Ã |
| F06D | ê | F074 | ã | F07B | Î | F083 | Õ |
| F06E | î | F075 | õ | F07C | Ô | F084 | Ì |
| F06F | ô | F076 | ì | F07D | Û | F085 | Ù |
| F070 | û | F077 | ù | F07E | Ä | F086 | ♥ |
| F071 | ä | F078 | ß | F080 | Ë | F087 | ★ |
| F072 | ë | F079 | Â | F081 | Ö | | |

They are drawn the way the first ones were (the same bodies under a circumflex, diaeresis, tilde or grave; widths 8,
4 for î ì, 12 for the capitals, ♥ ★); font b has its own letters (`b.txt`), its ♥ ★ are font a's. Patch 0195
regenerates `font_extra.h` and `font_b.h` instead of 0024: a later regeneration of 0024 has to take them out of 0195.
Each glyph is 48 bytes of the executable with FONT_SWITCH (font b's table and the original's): 1 296 bytes.

(`python3 tools/fontgen.py list` prints the current table.)

- **Code points**: the Shift-JIS user-defined area, `F040`–`F07E` and then
  `F080`–`F0FC` (188 slots). No original text uses them (checked on every
  script of `DG.SCN` and `MAPHEAD.SCN`), the lead byte has bit 7 set so both
  `drawString` and `drawString2` treat them as 2-byte codes, and neither byte
  is `00` or a control code.
- **Lookup**: `drawGlyph` checks for lead byte `F0` first and indexes
  `EXTRA_GLYPH_DATA` directly (`font.c`, generated `font_extra.h`); every
  other code goes through the original table unchanged, so the 79 original
  glyphs and the "unknown code → last glyph" fallback are as before.
- **Metrics** (copied from the original glyphs): lowercase x-height rows 3–8
  (baseline row 8), capitals and digits rows 0–9 (baseline row 9), descenders
  to row 10. Lowercase accents are 2-pixel strokes in rows 0–1 with row 2
  blank. Capitals have no room above them in the 11-row cell, so accented
  capitals use a 7-row body (rows 3–9, same baseline and width) under a
  2-row accent; drawing the accent touching a full-height letter was tried and
  read worse. ¿ ¡ are the ? ! turned over, hanging one row below the
  baseline. `·` is the 2×2 period raised to the middle of the x-height.
  Widths follow the 4-px grid: 8 lowercase, 12 capitals, 4 for í ï ·.
- **Punctuation**: `( ) [ ]` span the whole cell (rows 0-10), 3 columns, width 4
  (1 blank column to the letter inside, 2 to the one outside, as the letters
  leave). `&` `%` `#` `@` are capital-sized (rows 0-9, 8-9 columns, width 12).
  `/` is a 1-pixel diagonal over 5 columns (the original's `\` is 2 pixels
  thick and reads bold next to letters). `…` is three of the period's 2×2 dots
  2 columns apart: it looks like `...` but is one glyph and 12 px (`...` is 15,
  each period 5 wide). `–` is 9 px on row 5 (the original `-` is 7), `—` 12 px
  with a 16-px advance (the cell is 12 wide). `*` (5×5) sits at cap height,
  `~` on rows 4-5, `♪` is a filled head with a stem and a flag (rows 0-9).
  Checked at 1x and 7x next to the US letters (`fontgen.py preview`) and in
  the emulator.

## Adding a glyph

1. Append it to `tools/font/extra.txt`: a line `glyph CHAR WIDTH` and 11 rows
   of `#`/`.` (format and metrics at the top of the file). **Only append**: the
   position in the file is the code, so reordering changes assembled texts.
2. Preview it the way the game will draw it (4-px grid, space rule):
   `.venv/bin/python tools/fontgen.py preview "Text with it|second line" build/p.png`
   and `fontgen.py sheet build/sheet.png` (each glyph next to its base letter).
3. Extend the compact font generator and runtime tables together. The current
   `tools/font/compact.py` takes exactly 71 extra glyphs per Latin font, so
   appending to `extra.txt` alone does not extend a production executable.
   Keep the original glyphs disc-sourced and update both the original-style and
   new-font tables, their counts and the runtime lookup bounds. Export engine
   changes as a new patch at the end of the series using `tools/mods.sh save`.
4. Rebuild the affected executables and verify the new glyph in both fonts and
   in dialogue, names and menus. `scnasm.py` and the DWS back end read `extra.txt`
   for the character → code mapping and widths, and each target's build for its
   glyph count. Recheck the actual executable's memory budget on the original
   2 MB PlayStation; compact tables and caches determine the added cost.

`fontgen.py` refuses a glyph whose ink reaches the last column of its advance
(it would touch the next glyph).

## Tools

- `tools/dws/bytecode/__main__.py` encodes these characters (UTF-8 in `.scn.txt`, NFC-normalised)
  as `F0 xx` and decodes them back; `check` on the original files is still
  identical. `asm --font original` rejects them instead, for discs with the
  original executable; `--font-glyphs N` rejects the ones past the first N (an
  executable built before they were added); `--strip-accents` turns them into
  plain letters (`·`→`.`, `«»`→`"`, drops `¿¡`).
- **Which glyphs a target has** (`tools/dws/backend.py` `set_font`): none for
  the original executable; for `--exe mods`, `species`, `story-state` the first N of
  `extra.txt`, N read from the executable `disc` would ship (its
  `SLUS_010.32.elf`: `EXTRA_GLYPH_DATA` is 24 bytes a glyph; without a build,
  its worktree's `font_extra.h`). `--exe-dir DIR` points at another build of
  that executable, `--font-glyphs N` says N (`tools/build-full.sh` passes its
  worktree's `NUM_EXTRA_GLYPHS`: the executable it builds next).
  `python3 tools/fontgen.py glyphs build/decomp-int/build/us/psx/gcc` prints
  it: "29 of the 44 extra glyphs (...); lacks ( ) & % / …" means that build
  predates the punctuation glyphs.
- `dws.py ... --exe mods` keeps the glyphs the target has. A character it lacks
  is an error at its `.py` line (`( ) & % / [ ] # * ~ @`: no plain form) or a
  note there (an accent, `…`, `–`, `—`, `♪`: drawn plain), and `disc` refuses an
  executable with fewer glyphs than the text was compiled for. `disc --exe mods`
  builds the image with the mod executable (`--from build/decomp-mods/build/us/
  psx/gcc --relayout`). Without `--exe` (original executable, the default) the
  accents are stripped and the compiler prints which ones.
- Another text source (`TEXT=ours`, `es-fan`: `tools/dws/textbank.py` `fit`)
  keeps what the target has and replaces the rest (`…` → `...`, `〜` → `~` or
  `-`); the executable's strings (`tools/localize/executable/bank.py`) encode them too, the
  ASCII ones through their full-width forms so that the executable's own `%d`
  and `#C1` codes stay ASCII.
- Both measure lines with the real glyph widths and the space rule of the
  target (8 px for the mod executable; the previous glyph's width with
  `--font original` / the original executable), so automatic wrapping no
  longer lets a line run past the 244-px draw limit.

```bash
python3 tools/dws.py disc mod.dws --name font --exe mods      # keeps the accents
python3 tools/dws.py disc mod.py --name fontp --exe story-state      # a Python story, punctuation included
```

## Long names

Species names go up to 19 characters (HerculesKabuterimon, MetalGreymonVaccine: 150 and 154 pixels in the
font's own spacing); the C screens were made for some 14. `drawGlyph` cannot place a glyph closer than its
4-pixel grid, so a name too wide for its field is composed in software (`drawStringMode`, `font.c`, patch 0089):
each glyph's ink is placed at pixel precision into one strip (`FIT_STRIP`, 1408 bytes) that is uploaded at once.
No glyph loses a column (patches 0086/0088 scaled the textured quad instead, which turned the K of
HerculesKabuterimon into a "<"). Three ways, the first that fits is used (`fitStringMode`):

| Mode | How | HerculesKabuterimon | MetalGreymonVaccine |
|---|---|---|---|
| `FIT_VANILLA` | `drawString`: the original pixels | 150 | 154 |
| `FIT_TIGHT` | the same glyphs, 1 blank column between two letters (a space adds 3) | 128 | 131 |
| `FIT_CONDENSED` | the same, with a 5-column lowercase (`tools/font/condensed.txt`) | 110 | 115 |

Every name that fits a field is drawn by `drawString` and copied as the original copied it, so its pixels are
the original's (checked with Agumon on every screen below against a build without 0086/0088/0089: 0 differing
pixels). The condensed lowercase keeps the original rows
(x-height 3-8, ascenders, descenders); capitals, digits and f i j k l keep the original glyphs.
`fontgen.py fit "NAME" OUT.png` shows a name the three ways with its widths; `fontgen.py condensed-header
src/main/font_condensed.h` writes the table after editing `condensed.txt`.

| Screen | Field | A name that does not fit |
|---|---|---|
| Status screen | 120 px | tighter; HerculesKabuterimon and MetalGreymonVaccine condensed |
| Evolution chart, detail | 120 px, centred as the original | up to 136 px, centred in the level's panel, tighter if it must |
| Battle registration | to the box edge (0xD6) | the box as wide as the title box (0xF6); up to 124 px (12 px inside its edge), tighter if it must |
| Registered Digimon list | to the cursor's end (0xCC) | the list under the title box, as wide, cursor 0xE6; up to 116 px (MasterTyrannomon and longer condensed). Decided over all 40 slots |
| Save slots, slot confirmation | 96 px (the original cut MetalGreymon to "MetalGreymo") | every box 0x18 further left and 0x110 wide, cursors too; up to 136 px. Decided over the card's slots |
| Tournament "dealt damage" window (STD overlay) | 120 px, centred by `strlen * 6` | tighter, centred by its width |

The save title keeps 17 characters of the species name (`title + 0x1C`); the rest of a longer name is written
to the header's reserved bytes after `LN` (`modTitleNameTail`, `main_menu.c`) and the slot screens join it back.
A save made before this patch shows the 17 characters. The lab menu ("To " + 19 characters) and the dialogue
fit as they were; the battle results box puts the name alone on its row.

## Item names

An item's name is 19 bytes (`ITEM_PARA`), but the lists were made for some 12 letters: their columns cut a name at about
96 pixels ("Happymushr", "Deluxe Mushr"), which is why the US abbreviated (Happymushrm, Deluxmushrm, Leomonstone). With
the item names patch every list draws a name whole the way the long names do: a name that fits its column is
drawn as before (`drawString` / `drawString2`: the original pixels, checked against a build without the patch); a longer
one with `drawStringMode`, tight or condensed, the first that fits (`fitStringMode`). No column moved: the counts and prices
stay where they were.

| Screen | Field | How |
|---|---|---|
| Inventory (field menu, battle item command) | 96 px (`ITEM_FIELD_W`), the text area's column | `drawInventoryTextLine`: `drawStringMode` |
| Fishing bait list (FISH overlay) | 96 px | `FISH_drawBaitMenuRow`: `drawStringMode` |
| Shop buy, sell and merit lists | 93 px, a glyph cell (12) before the price (`0x16`: column 0x69; a price of 4 digits starts at its edge) | a script-text line: fit code |
| Item keeper (Keeping / In hand) | 96 px, 4 before the count (`0x1c`: 0x64) | fit code; a 19-byte name drops the 6-px `0x0f` gap (the keeper's rows are 32 bytes) |
| Shop amount box (buy how many) | 96 px (`AMOUNT_BOX_LAYOUT`: 8 x 12) | fit code |
| Mojyamon's trades | given: 96 px; got: 96 px from the header's second column (0x72) | a row that would end past 218 px (where the US rows end) moves the item got to that column; others as before |
| "Got X" box (chests, pick-ups) | the box is 262 wide | the name's row copied as wide as the name (was 96 px), font spacing |
| Battle results ("X dropped Y"), dialogue (`{item N}`), the bait's lines | prose | no column: as before |

**Fit codes.** The shop and keeper lists are script-text lines drawn by `drawString2` (colour codes, column codes `0x16`
`0x1c`...). Two codes of the mod, which `showTextbox` never passes on (it expands `0x10`-`0x15` into numbers), draw a name:
`TEXT_FIT_TIGHT` (0x10) / `TEXT_FIT_CONDENSED` (0x11), followed by a colour (0xFF keeps it) and the name up to the next
code. They replace the line's colour code `01 c`, so a line is no longer: `textFitCode(name, field)` returns 1 (the plain
colour code) for a name that fits as the font draws it. `TEXT_COLUMN` (0x12) x moves the pen to column x (Mojyamon's
trades). After a fitted name the pen moves to the next cell of the 4-pixel grid, because the clears of the codes that follow
work in whole cells.

**The limit for a name** is therefore 96 pixels in one of the three ways (in the shop's lists a name of 94-96 condensed
still leaves 8 pixels before the price) (`fontgen.py fit "Name" out.png` prints them) and
19 bytes; `tools/localize/executable/bank.py` keeps the build's name for a source's item name that is wider (listed in the report).
Examples: Happymushroom 106 / 93 / 80 (drawn tight), Deluxe Mushroom 118 / 101 / 89 (condensed), Omnipotent Floppy 130 /
110 / 96 (condensed, the limit); too wide: Medium MP Floppy (97), Monochrome Stone (98), Amazing Fishing Rod (107).

`FIT_STRIP`, the composition strip, covers 144 pixels instead of the text area's 256: the widest line it composes is a
name drawn tight in a field of at most 136 (MetalGreymonVaccine, 131). That gives back 616 bytes of bss, more than the
patch's code.

## Not covered

- The VS mode (two-player battle) has its own 8×8 texture font
  (`VS_FONT_CHARS`, `vs_scene.c`); it gets none of these glyphs.
- A few C screens center names with `strlen(name) * 6`: a 2-byte character
  counts as two there (`std_main.c`).

## Japanese glyphs

`tools/font/japanese.txt` holds the renamed Fusion Pixel bitmap subset used by
the Japanese translation. Its ○ □ × △ are never used for buttons: the executable's
text bank leaves those four to their button codes (`tools/localize/executable/bank.py`). Source pins and upstream licences are under
`tools/font/japanese-license/`; see [THIRD-PARTY.md](../../THIRD-PARTY.md).
`tools/font/import_japanese.py` imports the pinned BDF and `tools/font/compact.py`
encodes glyphs without changing their pixels or widths. Japanese text uses
multiple private-use lead-byte ranges and wraps between glyphs, keeping runtime
references intact.

## Player-side regional Latin tables

The package generates the five compact `LATIN_*` arrays from the selected
player's boot executable and the authored `b.txt`/`extra.txt` glyphs. USA uses
its 79 explicit-width records. The other bases use their 992-code table and
eleven-row glyphs; missing characters use the authored font, with a generated
blank space. Cross/triangle codes are swapped when reading the non-USA tables
to preserve the mod's input labels. CLASSIC and ORIGINAL therefore use the
player's regional lettering.

`tools/font/compact.py` and `tools/patcher/fontcopy.py` share fixed capacities
(4,048 bytes total) and a fifteen-bit maximum Huffman code. Overflow fails the
build. The current map binds every destination array. Generated bytes enter
only through zero-difference copies into that exact array; they cannot supply
arbitrary table payload. No original bitmap is stored in the recipe.

The common capacities add 1,024 bytes to main's allocation compared with the
previous USA-only encoding. This also moves its linked data/BSS references and
adds one executable disc sector. The checked native build retains 187,888 bytes
of heap; all 320 archive-based setups fit, with a minimum margin of 5,856 bytes.
[Combined reference pins](../reference/font-table-pins.json) record all
seven new image hashes, reasons and original-2-MB field/battle/OPTIONS/save checks.
