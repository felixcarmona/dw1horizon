# Triangle labels and the clock texture

FI_INFO.TIM is also ETCTIM.BIN entry 4. Its TIM origin is VRAM (896,448),
but GetTPage(896,448) selects a page rooted at (896,256): TIM row zero
is page V 192.
The sprite table stores V as TIM row + 1; renderGameMenu adds 0xbf.

The patched source through 0273 has these consumers of this page (including
literal tpage 0x1e, GetTPage/getTPage spellings and hexadecimal coordinates):

| Consumer | TIM pixels sampled |
|---|---|
| clock.c, CLOCK_TEXCOORD_U/V and renderGameClock | Five 32×16 frames at (128,0), (160,0), (128,16), (160,16), (128,32) |
| clock.c, other renderGameClock draws | Bells at (192,32), (192,48), both 16×16; face (208,23), 48×40; hour point (203,24), 6×6 |
| clock.c, CLOCK_SPRITE | Minute hand (120,0), 8×16 |
| game_menu.c, MENU_OPTIONS and renderGameMenu | Icons below u100, including highlighted copies; original English labels below u128 |
| game_menu.c, renderVitalsSprite | HP/MP sprites at V168..182, entirely above FI_INFO (V192..255), CLUT rows491/492 |
| game_menu.c, renderDateDigits | Date digits below u128 |
| game_menu.c, renderTriangleCursor | u0..12, rows59..63, CLUT (256,508) |
| fade.c, renderFade; std_main.c, STD_renderBracketIntro | u250..251, rows61..62 (V509 wraps to253), CLUT (256,502) |
| mod_feed.c, feedRenderList | MENU_OPTIONS command icons below u100, CLUT (256,509) |
| shop/script_menu.c, renderSelectionBox | Cursor art below u12, CLUT (256,508) |

GetTPage(896,448) and GetTPage(896,256) both encode page 0x1e;
all these call sites were checked. Other uses sample different V coordinates
or different resident textures (battle effects, fishing and arena HUD). The menu/feed icons also use
CLUT rows 508/509, outside the clock's 496..502; their U range stays below 128.
No draw samples the status-word interiors in the two remaining blocks:
u128..159 rows48..63 and u160..191 rows32..63. The former claim that the
*whole* u128..191 rows32..63 block was unused was wrong: its upper-left
32×16 cell is the sleeping creature's second animation frame.

Patch 0274 changes only sprite-table values, with no new runtime storage.
All translated languages use these cell origins (inclusive U and TIM row):

| Label key | U | Row | Height |
|---|---:|---:|---:|
| OBJETOS / ITENS | 128 | 48 | 7 |
| JUGADOR / JOGADOR | 160 | 32 | 7 |
| ALABAR / ELOGIAR | 128 | 55 | 7 |
| DORMIR | 160 | 39 | 7 |
| REÑIR / BRONCA | 160 | 46 | 9 / 7 |
| PESCAR | 160 | 55 | 7 |

Shared labels use the full 32-pixel width, centered under their icons, so longer
words such as GRONDER are not squeezed into the old 19-pixel REÑIR sprite.
Portuguese keeps widths 19, 28, 25, 23, 25 and 24 for entries 1, 3, 4, 6, 5 and 7.
DIGIMON and English keep the original disc cells. The recipe prints the C rows;
other translations use the shared non-English sprite dimensions. Their entire
catalog strings are resampled into those dimensions, including accents and
shadow, and both texture copies receive the same drawing.

European base manifests require FI_INFO to match the USA bytes and rename the
European ETCTIM_E.BIN. Japanese bases run fromjp.fi_info on both copies: it
reletters the original menu cells and the three bubble interiors (EVOLVE at
u165..188 rows36..43, POOP at u133..156 rows52..59, DEAD at u165..188
rows52..59). None overlaps a clock frame. Both Japanese pressings have the
same sleeping-creature cell as USA. Localization then replaces the free blocks,
including those bubble interiors, while preserving all five clock frames.

The build checks label/clock and label/label overlap and compares all five
clock frames with the input in both texture copies after the final label pass.
The selftest includes synthetic corruption of each frame and rejection of the
former (128,32) label cell.
