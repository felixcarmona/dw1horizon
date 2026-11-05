# Green egg freeze investigation

Investigation date: 2026-11-05. This follows the earlier egg-selection reports
and PR #162. A successful reproduction must distinguish a stopped emulator from
a running hatch, a CD read, an animation wait, and the naming dialogue.

Confirmed cause: rebirth calls a species-fallback helper linked into MENU_REL.
Battle or evolution can overwrite that code before an egg hatches. The fix
keeps the shared helper in resident main code. The green egg's model, texture,
name and memory budget are not the failing allocation.

## Which green egg

Slots are zero-based, left to right, then top to bottom.

| Appearance | Slot | NEW DIGIMON on | NEW DIGIMON off | Hatched species |
|---|---:|---|---|---|
| White with green spots, top left | 0 | Present | Present | Botamon, 1 |
| Plain green, bottom left | 4 | Present | Absent | Pabumon, 470 |

The other original eggs are blue-spotted (Punimon), orange-striped (Poyomon),
and pink-striped (Yuramon). The other added eggs are cyan (Pichimon), silver
with black zigzags (YukimiBotamon), and red with peach spots (Nyokimon).
These identities come from the actual TAMA.TIM palettes and `eggBabyType`,
not from the colour of the baby. With NEW DIGIMON off there are four eggs;
Pabumon is not substituted into an original slot.

The cached screenshot attached to the earlier DuckStation report shows a
cyan egg, matching Pichimon (slot 5), with cracks and a glow. Its overlay
shows 0 FPS and about 61 VPS. It is distinct from the later report describing
a green egg; the later report has no image or save in the local cache.
The captured cyan appearance matches a successful test at sequence frame 132,
phase 206. At that point the phase has already advanced but voice/texture
loads may still be executing, before the asynchronous model read is queued.
This is a visual lead, not a CPU diagnosis from the reporter's emulator.
Additional v0.0.5 tests chose cyan slot 5 from the saved egg box on both
2 MB and 8 MB: both hatched Pichimon (471) and returned control.

## Assets and buffers

Pabumon uses Punimon's three-bone skeleton and animations, with a hand-made
mesh and texture. Its complete source MMD is 27,108 bytes. In the v0.0.5
DIGI.DAT its resident model is 22,642 bytes (12 sectors when read), its cold
animation data spans 4,472 bytes, and its TIM is 18,432 bytes (9 sectors).
The TIM has the expected 4-bit header. Its texture SHA-256 is
`14e24a92db13771e718d7e119e8a1d8b800950f00b04c3c29821758cd4ccaf42`;
the resident model SHA-256 is
`7db006fde3e582ac1c859f2b7d37fc1b62711ee59b2b8432a50c413bf6764007`.

The main baseline has byte-identical resident and cold animation data. Its
same-size TIM has 502 changed bytes from the later flat-battle sprite work,
with SHA-256 `f21480442bc7ee1d0ce423a743011b4e46454d99ccac1d5e9b278ed0472dfee9`.
A per-face UV/CLUT comparison checked 18,530 texel samples and found no colour
differences on the 3D model. A comparison of whole TIM hashes alone would
incorrectly conflate the battle sprite changes with the hatch's model skin.

Pabumon's hatch slots 0 (21 frames), 28 (55 frames), and 11 (63 frames) are
all resident. Slot 11 also has a non-cold user, so the splitter keeps it
resident. Its cold slots are 5, 7, 8, 9, 10, 12 and 13. The known cold-clip
read stall is therefore not required by this hatch's animation sequence.
The native Botamon MMD is 22,092 bytes; its slots 0, 28 and 11 have 30, 60
and 55 frames. Native Botamon is not cold-split.

`loadMMDAsync` reads the TIM at `EVO_MMD_ADDR` (0x80020000) and the model
at that address plus 0x4800. The Pabumon model read ends at 0x8002a800,
below `DOOA_SHARD_ADDR` (0x80044800). `applyMMD` copies the resident
model into the fixed partner buffer. It does not allocate the baby model
from the house's NPC heap. The egg texture TAMA.TIM remains 10,784 bytes
(256 by 80, 4-bit, sixteen CLUT rows); adding the green icon changes pixels
and palette entries, not the file size. Slot 4 uses the existing six-object
3D group 2, and copies CLUT row 497 over row 490 before the hatch.

## Hatch and naming path

The death map is Jijimon's house 218 or its larger version 205. Both forward
the old-age event to script 212, section 71. That section waits for the death,
opens `egg_choice`, calls `dying_b`, waits for the hatch, then asks about the
name. Sections 72 and 73 handle lost-life recovery and death without lives.
The egg-specific work is in the DOO2 and DOOA overlays; there is no separate
green-egg story script.

`DOOA_tickRebirth` starts at phase 200. At phase 205/frame 132 it loads the
baby voice and texture and queues the model. At phase 206/frame 152 it drains
the model queue, reincarnates the partner, applies the inherited stats, and
waits for the sound bank. It plays slot 28 at frame 202, then slot 11 at
frame 262; phase 7 waits for that animation to end. These are useful places
to capture the CPU, loading flag and animation counters if a failure occurs.

Pabumon's record contains the seven-byte ASCII name `Pabumon` plus a
terminator. `modPartnerNameFollow` changes an automatically assigned species
name to the baby's species name; a player-entered name is kept. The name
buffer has 20 bytes. The script's naming choices can open the keyboard;
a proof that only reaches this choice has not yet proved control returned.
The test chooses the last naming option and verifies both the final species
and free tamer control.

PR #162 guards added homecoming handlers during death-map entry, using
`engine.death_map_entry`. That fix is present on the main baseline and absent
from v0.0.5. It addressed dialogue running over a death; it is not evidence
that every reported egg freeze has the same cause.

## Repeatable checks

`tools/dev/playtest/eggs.py` now accepts `--ram-mb 2|8`, `--language`,
`--angemon 0|1`, `--species-name`, `--battle-first`, and `--skip-walk`, alongside the existing
partner, prosperity, homecoming and egg selectors. It records heap blocks,
NPC model IDs, the CPU PC/RA, sequence phase/frame/loading flag, partner
animation counters, cold-read state, and name bytes at the box and hatch.
It saves the failure image and emulator state on an error. Cursor selection
has a bounded retry count, including a range check for unavailable eggs.
The box must be in house 218/205 with the death sequence finished in phase 4;
leftover evolution-overlay values cannot qualify. `--battle-first` enters
and completes a real wild encounter without reloading MENU before death.

For example, with private paths supplied locally:

```sh
xvfb-run -a python3 tools/dev/playtest/eggs.py DISC.cue \
  --exe EXE --out build/green-egg-check --cases 4,0 \
  --partner 224 --prosperity 60 --angemon 1 --language es \
  --species-name --skip-walk --ram-mb 2 --port 39749
```

The harness copies the release corpus card; it does not modify a player card.
Language is selected in the copied save's options so the normal loader applies
it. Prosperity selects the house; Angemon's recruitment is trigger 220, and
his house model is species 142. A resident test asserts that model was loaded,
rather than assuming a prosperity value proves the resident was present.
Run a 2 MB case before an 8 MB case. An 8 MB pass cannot establish console
compatibility. When comparing discs, keep each disc's own executable and ELF
map together; do not reuse a state between different builds or RAM modes.

## v0.0.5 results

The reference is the final fourth-cut USA disc (SHA-1
`0837751cf5b5d84e7cea0dd344aad4b3311a0119`), with its own executable and
symbols. `main_BSS_END` is 0x801cdf64; the measured 2 MB heap is 188,304 bytes.
`tools/heapcheck.py` passes (minimum projected free in its historical sweep:
31,952 bytes). Live death-map measurements below are separate from that sweep.

Every row below passed on PCSX-Redux with both **2 MB and 8 MB** RAM. A pass
means the hatch completed, the naming choices were answered, control returned,
and the partner ID matched the chosen egg. These are selected combinations,
not a Cartesian sweep of every language, partner and city flag.

| Language | Dying partner | House | Angemon | NEW DIGIMON | Eggs tested | Free heap at egg box |
|---|---|---:|---|---|---|---:|
| English | Omnimon (461), Mega | 218 | Absent | On | 4 and 0 | 109,448 B |
| Spanish | MetalGreymonVaccine (224), Ultimate | 205 | Absent | On | 4 and 0 | 124,336 B |
| Spanish | MetalGreymonVaccine (224), Ultimate | 205 | Present | On | 4 and 0 | 90,176 B |
| Japanese | MetalGreymonVirus (12), Ultimate | 205 | Absent | Off | 0 | 124,336 B |

The English box also passed right/left wraparound and up/down row navigation.
The Spanish and Japanese cases used automatic species naming; the English
cases retained the corpus card's existing player-entered name. Captured names
were `Pabumon` or `Botamon` as appropriate. The resident case verified model
IDs 30, 142 and 117 (Tokomon, Angemon and Jijimon). Heap walks found no corrupt
block. The baby model loaded, animation 28 played, animation 11 reached its
last frame, and the sequence frame became -1 as expected.

The 8 MB mode does not enlarge this executable's NPC heap: it still measures
188,304 bytes. It enables the cold-animation cache above 2 MB. This distinction
matters when interpreting an 8 MB pass as evidence about heap pressure.

The first resident fixture mistakenly set trigger 236 (Centarumon), so it
loaded house 205 without Angemon. Its successful hatches are retained as the
without-Angemon row, and both RAM modes were rerun with trigger 220 and an
explicit assertion of resident model 142. The corrected resident runs passed.

DuckStation 0.1-12074-g697599c47 also passed the plain-green slot 4 case
with both 2 MB and 8 MB, English, Omnimon and house 218. It used OpenBIOS, CPU 100%,
the software renderer, and no game patch other than the harness's intro-movie
skip. The final partner was Pabumon, control returned, and the box/field
heap both kept 109,448 bytes free. The captured selected egg and final
field were inspected. This is a second emulator result; it does not match
every setting or version used in the reports.

The plain-green case also completed with DuckStation's OpenGL renderer,
3x internal resolution, xBR texture filtering and PGXP, at 2 MB and CPU 100%.
The capture used the OpenGL renderer through a software host driver, not a
physical console GPU. The successful field image and partner ID were checked.
Cyan Pichimon also completed with that enhanced renderer when MENU's helper
had not been replaced by another overlay.

## Main build

The source baseline is `5a838ffb` (the worktree's starting `origin/main`).
The full eight-language image has SHA-1
`4a042c017b5e09de22dd119d153c8cf4a56493a5` and size 902,502,384 bytes.
`main_BSS_END` is 0x801ce61c and the heap is 186,592 bytes, 1,712 fewer than
v0.0.5. The historical heap sweep passes with 30,240 bytes at its tightest
screen. The separate archive-based gate checked 320 setups with zero over
budget; its smallest margin is 1,872 bytes on screen 207 (screen 332 keeps
6,400 bytes).

The outer `tools.dev build` launcher exited with SIGTERM (143), leaving no
timing summary. Its inner build continued through all eight native compiles,
heap gates and disc creation, ending with `green-egg-freeze.cue ready`.
The finished ISO volume/root and PS-X EXE header were checked directly, and
the disc's executable matched the final staged executable byte for byte.
The staged copy includes the relayout's rewritten file-sector table; the
pre-relayout executable is expected to differ there. Runtime comparisons
use a copy of that staged executable with the matching ELF/map. The launcher
exit is retained as an infrastructure limitation, not labelled a clean
full-command exit.

## Reproduced cause and fix

On the main baseline, WarGreymon (373) evolved through the game's evolution
path and then died of old age. Selecting plain-green Pabumon stopped the
hatch in phase 206: the baby ID was already 470, its model had loaded, but
the sequence did not advance and control did not return. The saved failure
replays. Botamon with NEW DIGIMON off also failed after evolving the dying
partner; an Omnimon loaded directly from the card passed all three tested
eggs (0, 4 and 5). An initial Spanish setup stopped too early because the
test mistook leftover evolution-overlay state for an open egg box; the
harness now requires an actual death-room map before accepting that state.

`eggHatchStats` calls `getSpeciesVanillaAs` before checking the four native
stat rows, so every egg can reach this helper. The linker placed the helper
in MENU_REL even though rebirth in DOOA also calls it. Main's MENU helper
is at 0x800601ac, inside the range overwritten by EVL_REL (0x80060000 up).
The failure RAM's 68 helper bytes match the evolution overlay exactly and
do not match MENU_REL. Restoring only those 68 bytes in the saved failed
state lets the hatch finish and returns control with Pabumon. Heap remained
107,736 bytes free in house 218 throughout this recovery.

On v0.0.5 the same helper is at 0x8005fd9c, just below EVL_REL. That explains
why the earlier evolve-then-die cases passed there. Battle overlays start
at 0x80052ae0 and cover that address. Opening OPTIONS or Cheats reloads
MENU_REL, masking the lifetime error before the next death. A regression
test must leave MENU closed between the preceding overlay and the death.

A real wild encounter reproduced this on the shipped v0.0.5 disc: the
Omnimon from the card fought, the normal victory/unload path ran, and lifetime
was then set to zero without opening MENU. Plain-green Pabumon stalled at
frame 152/phase 206. Its helper bytes matched BTL_REL exactly rather than
MENU_REL. From that same battle-preceded egg-box state, restoring only the
68 helper bytes made Pabumon, Pichimon and Botamon all hatch and return
control. The enemy HP was zeroed to finish the encounter promptly; battle
entry, victory, field return, death and hatch all ran through the engine.
The same battle-then-death sequence also froze cyan Pichimon with 8 MB.
The eight-egg patch added this DOOA call before the native-stat-row check,
which is why the original eggs and NEW DIGIMON off are affected too.

`Keep-rebirth-species-fallback-resident.patch` removes the helper from MENU's
linker input so the ordinary main text selection keeps it resident. A source
comment records the shared MENU/DOOA lifetime requirement. The change does
not alter the eggs, models, textures, names, scripts or hatch statistics.
The patch series applies to the pinned decompilation. Its final heap cost
and fixed-build runtime results are measured separately below.

The fixed full eight-language build completed with exit 0. The helper now
resides at 0x800e44a0. Matched `main_BSS_END` measurements are
0x801ce61c → 0x801ce65c (+64 bytes); heap is 186,592 → 186,528 bytes
(64 bytes less, including alignment). The historical sweep's minimum is
30,176 bytes. The actual-archive gate again checked all 320 setups with zero
over budget; its minimum is 1,808 bytes on screen 207. The fixed disc SHA-1
is `9045ae006cb899d8e0bdba77dbcda689619b0bf7`.

DuckStation reproduced the main baseline after evolving Omnimon into the
Ultimate MetalGreymonVaccine (224), then dying and choosing plain green:
species 470 loaded, phase stayed 206, and control never returned. The fixed
disc completed the same sequence in OpenGL/3x/PGXP/xBR at 2 MB and CPU 100%:
Pabumon hatched, phase reached 7, and control returned. Live house-218 heap
changed only by the measured 64 bytes, 107,736 → 107,672 free. Both the
frozen and successful field captures were visually inspected.

All **18 fresh fixed-disc hatches** passed across eight configurations:

| RAM | Language | Dying partner / preceding event | House | NEW DIGIMON | Eggs | Free heap at box |
|---|---|---|---:|---|---|---:|
| 2 MB | English | WarGreymon 373, evolution | 218 | On | 4, 5, 0 | 107,672 B |
| 8 MB | English | Omnimon 461, directly from save | 218 | On | 4, 5, 0 | 107,672 B |
| 2 and 8 MB | Spanish | MetalGreymonVaccine 224, evolution | 205, Angemon present | On | 4, 0 | 88,400 B |
| 2 and 8 MB | Japanese | MetalGreymonVirus 12, evolution | 205, Angemon absent | Off | 0 | 122,560 B |
| 2 MB | English | Omnimon 461, wild battle | 218 | On | 4, 5, 0 | 107,672 B |
| 8 MB | English | Omnimon 461, wild battle | 205, Angemon present | On | 4, 5, 0 | 88,400 B |

Every case checked the actual baby ID and return of player control. The
Spanish/Japanese cases also asserted automatic species names, and resident
cases asserted model 142 was present. The 2 MB WarGreymon case verified the
pending SkullGreymon homecoming stayed out of death and ran at the next real
house entry. Ten focused egg-art/save-compatibility tests pass. The 352-patch
series check, including application to the pinned decompilation, passes.

## Limits

No reporter's failing memory card or state was available. The test card predates
these reports; it is not the reported old v0.0.4 save. Tests force lifetime to
zero and clear the immortal-hour flag, using the same natural-death path as
the Cheats action; they do not play through a complete lifetime. Changing
prosperity to 0/60 selects the two house layouts but does not simulate every
possible city/story flag combination. The live heap dump proves which models
actually remained loaded in each room; outdoor city residents were absent.
Runtime tests used the USA-source images and English, Spanish and Japanese;
the remaining languages were built but not individually played. Random
no-lives hatches were not rerun in this pass. No physical PlayStation was used.
Emulator tests with 2 MB establish the tested
memory configuration, not a hardware certification.

The exact reporters' cards remain unverified. Useful follow-up evidence is the exact
egg position, disc hash/base, language and settings, the failing card or a state
before choosing, and whether frames stop before the shell breaks, during the
hatch, or at naming. A failure capture should include repeated phase/frame/PC
samples, the loading flag, partner animation counters and the heap walk.
