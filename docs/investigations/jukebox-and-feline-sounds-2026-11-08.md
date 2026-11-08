# Jukebox text and feline footsteps — 2026-11-08

## Player answers

**Urban:** confirmed. Scrolling the jukebox can leave the end of an older, longer
title beside a shorter one. Every recycled row now clears to its right edge,
and long titles fit inside the menu with the original font too.

Vanilla restores the restaurant's normal music when the jukebox closes, before
you leave the restaurant. Keeping a selection until its end is possible, but
needs a separate music feature: most tracks loop indefinitely. It would need a
one-cycle policy and a handoff to the current map's music, including battles and
scripted music changes. That is more than removing the existing reset. This fix
does not change music playback.

**Panon:** confirmed. SaberLeomon's hoof effects came from movement animation
instructions, independently of its Leomon voice. The feline audit now replaces
inappropriate steps in field movement, battle movement and landing cues in
other actions. Nefertimon keeps the Leomon voice already assigned by PR #336.

## Text diagnosis and fix

The v0.0.7 Spanish control in PCSX-Redux reproduces the reported fragments beside
tracks 58, 62 and 63. English reproduces stale suffixes too. Vanilla also relies
on padding rather than a full row erase; its original, abbreviated titles do
not exercise the same translated/proportional-font widths.

`calculateMusicMenuStrings` copied the title then called
`padWithSpaces(out, 12, strlen(title))`. That helper subtracts half the byte
length from a fixed character count. The compiled Western titles mix one-byte
ASCII with two-byte extended glyphs. Padding is therefore neither a character
count nor a pixel-width guarantee. NEW advances a blank only four pixels;
ORIGINAL's padding also cannot reliably cover a previous longer title. Some
titles get no padding at all. The row ring reuses that uncleared VRAM.

The new row ends with `TEXT_COLUMN, 252`, which clears from the next aligned
cell to the row end through the existing bounded clear. This covers both the
bulk writer and the single-row recycling path, in every language. It keeps
0284's texture-cache-compatible clear and PR #121's text-area bounds. No global
clear rectangle or texture-cache behavior changes.

The number and gap take at most 22 pixels. Titles use the existing `textFitCode`
with 176 pixels, keeping the combined row within the 198-pixel text span inside the selection.
NEW's widest translations already fit; ORIGINAL and CLASSIC use the existing
tighter glyph modes as needed. The fitted-run decoder's local buffer now holds
one complete 64-byte text row rather than the old 23-byte item-name limit.
No resident buffer is added.

`tools/dev/playtest/jukebox_host.py` compiles the actual row writer and fitted-run
decoder with built language headers. It checks row canaries, selected/unselected
colors, both row terminators, the explicit clear and complete fitted titles.
The old C fails this regression check. `tools/dev/playtest/jukebox.py` runs the
real restaurant routine, measures all 63 built titles and scrolls through the
real cursor functions in PCSX-Redux. Its setup writes unlock the menu and choose
a dialogue owner; it does not substitute text or drawing code.

## Feline audit

Sound numbers below are SL effects, bank 1, unless stated otherwise. Native
Garurumon uses 12; native Leomon and Panjyamon use 16; Unimon, Centarumon and
ShimaUnimon use hoof effect 20. Effect 13 is the shared heavy step used by Tyrannomon and Drimogemon, not a voice.
All six movement slots are checked: 2, 3, 4, 27, 35 and 36. The explicit donor
step substitutions also cover landings in care, training and attack clips;
voice-bank instructions and other impact effects keep their original events.

The before column is main after PR #336; release differences are noted below.
Voice pairs are VBALL / VLALL chunk ids, not effect ids.

| Species | Before steps | After steps | Voice before → after |
|---|---|---|---|
| Leomon 48 | 16 | 16 | 42/3 → same |
| Leomon NPC 166 | 16 | 16 | 42/no partner → same |
| IceLeomon 63 (native Panjyamon) | 16 | 16 | 42/3 → same |
| GrapLeomon 306 | 16 | 16 | 42/3 → same |
| Nefertimon 198 | 13 | 12 | 42/3 → same |
| SaberLeomon 258 | 20 in field, 13 in battle/landings | 12 | 42/3 → same |
| Gatomon 234 | 11 in field, 12 in battle/landings | 12 | 27/1 → same |
| BlackGatomon 222 | 11 in field, 12 in battle/landings | 12 | 27/1 → same |
| Lynxmon 323 | 12 in field, 13 in battle/landings | 12 | 34/7 (Drimogemon) → 42/3 (Leomon) |
| Baihumon 276 | 12 | 12 | 20/7 (Garurumon) → same |
| Bastemon 432 | 16 in field, 21 in battle/landings | 16 | 27/1 → same |
| Salamon 221 (canine in the cat family) | 12 in field, 20 in battle/landings | 12 | 27/1 → same |
| Gryphonmon 293 (lion-bodied hybrid) | 12 mixed with 20 | 12 | 29/9 (Unimon) → 42/3 |
| Nyaromon 476 | baby bounce 10; run uses bank 3, note 52 | unchanged | 2/0 → same |
| YukimiBotamon 472 | baby bounce 10/11 | unchanged | 1/0 → same |
| Magnadramon 215 | silent field glide, battle 17 | unchanged | 7/4 → same |
| Silphymon 226 | 16 | 16 | 19/4 → same |
| Marsmon 297 (feline headgear) | 16 | 16 | 42/3 → same |

The adjacent fox and mammal forms were checked too; none has hoof effect 20 or
horse voice banks, and their built models stay byte-identical:

| Species | Before → after steps | Voice before → after |
|---|---|---|
| Renamon 354 | 16 → 16 | 42/3 → same |
| Kyubimon 409 | 12 → 12 | 20/7 → same |
| Taomon 315 | 16 → 16 | 42/3 → same |
| Sakuyamon 316 | 16 → 16 | 42/3 → same |
| Gazimon 285 | 12 → 12 | 16/1 → same |
| Elecmon 18 | 11 → 11 | 16/1 → same |
| Elecmon NPC 140 | 11 → 11 | 16/no partner → same |
| VioletElecmon 256 | 11 → 11 | 16/1 → same |

Liamon and Meowmon are absent from the species catalog. Panjyamon is represented
by species 63, named IceLeomon in current content. Nyaromon is an additional cat
baby, not a renamed Meowmon. The audit includes the cat family's baby and canine
forms, its winged hybrid, the lion-bodied gryphon and the white tiger.

In v0.0.7 Nefertimon still had 29/9 (Unimon); PR #336 already fixed that to
42/3. Its gait effects remained 13. Salamon's old field gait used 20; its native
canine locomotion fix changed field steps to 12 but left other hoof cues. Those
remaining cues are included here.

These changes are build recipes and species data only. `movement_sound` retains
its integer form for existing recipes. An optional object adds `note` plus
`replace_notes`, restricted to bank 1, so a donor step can be replaced in other
actions without changing voice instructions. Every event keeps its frame;
geometry, pose programs, control flow and texture events remain identical.
Seven changed model sizes are unchanged; Lynxmon saves 864 bytes by sharing
now-identical streams. Pins cover the generated outputs.

`tools/dev/playtest/feline_sounds.py` compares all animation slots of all 26
species in two actual builds. `tools.test_movement_sounds` also proves that the
optional donor-note replacement preserves cries in other banks and unrelated
impact effects. The final build retains the existing storage/heap gates.

## Vanilla music control

A 2 MB PCSX-Redux control on the USA disc opens the native restaurant routine.
Selecting font 1 / track 0 through the real playback function gives
`CURRENT_SEQ_FONT/TRACK = 1/0`; running the ordinary jukebox close state restores
`28/0` (File City daytime). This matches vanilla `openJukebox`, case 2:
`destroyItemMenuBox`, then `playBGM(ACTIVE_BGM_FONT)`. A restaurant exit also
runs the destination header's ordinary BGM request.

`seqPlay` loops most jukebox selections forever. A correct "until it ends"
feature must define a single cycle, track a pending map request and relinquish
the selection at the cycle boundary. Battle music and script resets use the
same sequencer/music bank and need explicit interruption policy. It is feasible
without carrying a second full music bank, but needs engine state and transition
checks; it is not a cheap data-only extension of this text fix.

## Budget

The full nine-language build uses `main_BSS_END = 0x801ce5bc`, versus
`0x801ce56c` before: 80 bytes more main executable, available heap
186,768 → 186,688 bytes. There is no new resident state. The fitted-run helper
uses 40 additional temporary stack bytes. The ordinary 2 MB heap gate passes;
the tightest memory sweep screen keeps 30,336 bytes. Feline changes add no
resident bytes and all edited models meet the existing resident/cold storage
limits.

All 10 exported executable layouts pass `tools/title_storage_check.py`: MENU is
55,172 bytes, leaving 124 bytes within its 27-sector limit and retaining the
required 100-byte reserve. The relocated title bytes agree across languages.
The final nine-language image SHA-1 is
`f38b35bd2067558ab9739def1125999e1778497b` (`MOD_VERSION=v0.0.7`).
