# Imported footstep audit

Starmon 243 inherits native Leomon's SL effect 16, with two events per
16-tick cycle. Its sound is a short, strong clack, not a misrouted voice.
SuperStarmon 244 inherits SL effect 17, the native Seadramon movement cue,
six times per cycle. That sample lasts 2.282 seconds at its playback key;
retriggering it every 0.15–0.25 seconds layers long tails. Both selections
already exist in the pinned base imports, before the field overlays.
Animation repair preserved the sound identity along with the contact events.

The repair selects bank 1, effect 12 for Starmon, SuperStarmon, WarGreymon
373 and BlackWarGreymon 404 through the existing `movement_sound` recipe.
Field slots 2/3/4 and battle movement slots 27/35/36 change sound selection
only. Event counts, contact ticks and animation programs stay intact.
WarGreymon's run previously switched to effect 13; BlackWarGreymon's
condition walk and run switched to 21. The common short cue avoids that
change of sound character with speed.

This is an aesthetic choice supported by the duration measurements, not a
claim that native effect 16 is universally defective. Leomon and several
insects deliberately use it. The six-event SuperStarmon gait is retained;
reducing it to two events without checking foot contacts would change a
separate animation decision. Broader cadence and species choices below
remain review candidates.

## Routing and measurements

`anim.c` passes the animation bank and effect ID to `playSound`. Bank 4
is substituted with the entity's own voice bank. Banks 0/1/8 route effect
`n` to program `n // 16`, key `60 + n % 16`; bank 3 uses the literal key.
`startSound` selects tones by `max == key`, keys them at velocity 127,
and has no per-animation volume, decay or key-off argument. The tone's
ADSR and the sample waveform provide the envelope. Voices 10–23 are
allocated from a pool of fourteen; if all are active the next voice is
reused. See [sound routing](../mods/sound.md#3-sound-effects).

The audit uses actual simulated events from each final model, after all
field overlays and aliases, rather than interpreting instruction frame
numbers as runtime ticks. Times below assume stock 20 Hz game logic.
All listed SL cues are non-looping. Large negative pitch offsets are
native VAB tuning; they are not evidence of a pitch corruption.

| SL effect | Program/key | Sample | ADPCM bytes | Root / offset in semitones | Tone volume | ADSR | Played duration |
|---|---|---|---|---|---|---|---|
| 12 | 0/72 | 5 | 1360 | 90 / −18 | 100 | a8ff/5fde | 0.151 s |
| 13 | 0/73 | 12 | 2176 | 109 / −36 | 127 | 80ff/5fde | 0.686 s |
| 16 | 1/60 | 15 | 704 | 100 / −40 | 127 | 80ff/5fde | 0.275 s |
| 17 | 1/61 | 16 | 3408 | 110 / −49 | 70 | 80ff/5fde | 2.282 s |
| 18 | 1/62 | 17 | 1792 | 98 / −36 | 80 | 80ff/5fde | 0.564 s |
| 19 | 1/63 | 18 | 944 | 97 / −34 | 127 | 80ff/5fde | 0.262 s |
| 21 | 1/65 | 20 | 2688 | 92 / −27 | 127 | 80ff/5fde | 0.504 s |
| 24 | 1/68 | 7 | 1712 | 120 / −52 | 60 | a8ff/5fde | 1.357 s |

Program volume is 127 in both SL programs. In `80ff/5fde`, the attack is
fast, the sustain target is at the top of the envelope, and sustain decay
is very slow. It does not turn the long sample into a short step. Effect
12 additionally uses a softer exponential attack and a lower tone volume.

Offline single-event WAVs put 95% of the energy before 0.193 s for
Starmon, 1.720 s for SuperStarmon, 0.122 s for Agumon and 0.526 s for
Vademon. Their last samples above −40 dB relative to their own peak occur
at 0.268, 2.272, 0.150 and 0.555 s respectively. Thus SuperStarmon's long
tail is audible energy, not just silence at the end of a large file.
Starmon's single-event rendered peak is about 7.7 dB above Agumon's in
this common-gain offline approximation. No amplitude normalization was
applied to those single-event files.

SuperStarmon can have about twelve sample tails simultaneously in its
walk and fourteen in its run, before other effects use the same voice
pool. Its wave is pitched down 49 semitones from the stored root, versus
18 for effect 12. The replacement eliminates this long-tail accumulation
without changing cadence. The closest replacement retriggers are 0.15 s
apart, approximately the replacement sample's own length.

Vademon is different: native effect 18, two events per 22/20/18 ticks.
Its 0.564 s sample slightly overlaps at the native 0.55/0.50/0.45 s gaps.
This is original data, not an import regression or the same sample as
SuperStarmon. Leave it unchanged pending an explicit native sound review;
effect 12 is a possible shorter alternative to audition.

Agumon is the verified native effect-12 comparison. The older
[MetalGreymon recipe note](../reference/imported-species.md) named effect
12, but the current built MetalGreymon Vaccine and native Virus clips
actually use 13. This repair does not change either MetalGreymon.

## Event dump: reported species, ten other imports and native controls

Each entry gives cycle ticks, then every sound tick and its bank:effect ID.
The number of listed ticks is the event count; repeated ticks mean separate
retriggers. W/C/R mean slots 2/3/4. These are pre-fix values.

| Species | Walk: cycle / event ticks / bank:ID | Condition walk | Run |
|---|---|---|---|
| 243 Starmon | 16 / 2,10 / 1:16 | 16 / 0,8 / 1:16 | 16 / 2,10 / 1:16 |
| 244 SuperStarmon | 24 / 0,4,8,12,16,20 / 1:17 | 28 / 0,5,9,14,19,23 / 1:17 | 20 / 0,3,7,10,13,17 / 1:17 |
| 373 WarGreymon | 22 / 0,11 / 1:16 | 20 / 0,10 / 1:16 | 12 / 0,6 / 1:13 |
| 404 BlackWarGreymon | 20 / 0,10 / 1:16 | 24 / 0,12 / 1:21 | 12 / 0,6 / 1:21 |
| 180 Veemon | 10 / 0,5 / 1:12 | 14 / 0,7 / 1:12 | 6 / 0,3 / 1:12 |
| 181 Puppetmon | 16 / 2,10 / 1:12 | 20 / 1,11 / 1:12 | 12 / 3,9 / 1:12 |
| 183 Wormmon | 18 / 4,13 / 1:19 | 18 / 9 / 1:19 | 18 / 0,9 / 1:19 |
| 187 Stingmon | 16 / 2,10 / 1:16 | 16 / 0,8 / 1:16 | 16 / 2,10 / 1:16 |
| 197 Magnamon | 16 / 2,10 / 1:16 | 16 / 0,8 / 1:16 | 16 / 2,10 / 1:16 |
| 258 SaberLeomon | 32 / 5,14,21,30 / 1:12 | 32 / 0,8,16,24 / 1:12 | 42 / 5,12,19,26,33,40 / 1:12 |
| 293 Gryphonmon | 26 / 2,4,5,8,11,15,17,21,24 / 1:12 | 32 / 2,7,7,10,14,18,23,26,30 / 1:12 | 20 / 3,4,4,7,8,13,14,17,18 / 1:12 |
| 432 Bastemon | 32 / 0,8,16,24 / 1:16 | 40 / 0,10,20,30 / 1:16 | 40 / 0,5,10,15,20,25,30,35 / 1:16 |
| 3 Agumon | 16 / 2,10 / 1:12 | 20 / 1,11 / 1:12 | 12 / 3,9 / 1:12 |
| 5 Greymon | 20 / 1,11 / 1:13 | 24 / 3,15 / 1:13 | 18 / 2,11 / 1:13 |
| 10 Seadramon | 20 / 10 / 1:17 | 20 / 10 / 1:17 | 20 / 7 / 1:17 |
| 12 MetalGreymonVirus | 20 / 2,12 / 1:13 | 24 / 3,15 / 1:13 | 20 / 3,13 / 1:13 |
| 28 Vademon | 22 / 5,16 / 1:18 | 20 / 5,15 / 1:18 | 18 / 4,13 / 1:18 |
| 48 Leomon | 16 / 2,10 / 1:16 | 16 / 0,8 / 1:16 | 16 / 2,10 / 1:16 |
| 11 Numemon | 20 / 6 / 1:24 | 20 / 12 / 1:24 | 20 / 4 / 1:24 |

## Reproduction and validation

Generate imported models and provider species records through derive, then:

```sh
python3 tools/sound.py info SL 0
python3 tools/sound.py export SL 0 -o build/steps-originals
python3 tools/models/audit_steps.py --species build/NAME/imported-species \
  --out build/steps --render 243 244
python3 -m unittest tools.test_step_audit tools.test_movement_sounds
python3 tools/models/edit.py --from build/NAME check 243 244 373 404 --species-pins
```

`audit_steps.py` writes every field sound event to CSV and JSON, including
tone/sample identity, playback key, pitch, envelope, duration and loop flags.
It can also consume a folder containing native species JSON records for
comparison. Its WAVs wrap the unchanged source VAB and an event sequence
for the existing `sound.py` renderer. This is approximate SPU playback:
pitch, envelope and relative tone gain are included; reverb, the fourteen
voice limit and live footsteps alongside other game sounds are omitted.
Multi-event renders may be attenuated by the renderer to avoid clipping;
do not use them as calibrated absolute game loudness measurements.
Original samples and generated audio remain private under ignored `build/`.

The complete sweep covers 183 provider records (including eight hand-made babies
and the native-based MetalGreymon recipe) plus seven native controls. Source/delta replay
and final provider pins pass for the four repaired species. Every slot was
compared before/after: geometry, poses, control and texture programs,
nonmovement sounds, event frames and event counts are identical. Changed
slots are exactly 2, 3, 4, 27, 35 and 36 in all four models.

| Species | Model bytes before / after |
|---|---|
| Starmon | 87084 / 87084 |
| SuperStarmon | 87644 / 87644 |
| WarGreymon | 114414 / 114414 |
| BlackWarGreymon | 105344 / 105344 |

Resident and cold model sizes are also identical after splitting, and each
cold read fits its existing buffer. No C, executable, sample bank, resident
table or heap allocation changes; no engine patch is needed for this
existing offline data recipe. In particular, the screen-207 margin is not
reduced. This is a byte/size proof, not a new full-disc heap measurement.

A private emulator fixture replaced only these equal-size model streams
in an existing disc's DIGI.DAT, preserving its file layout and executable.
PCSX-Redux with original 2 MB RAM reached the title and continued the test
card into field control. The boot harness did not observe its expected
first-start language-picker condition, so the overall boot check reports
failure despite the successful Continue. These checks do not prove live
footstep playback; no listening judgement or original-console hardware
test is claimed.

The complete offline self-test reports 115 passed, 3 failed and 22 skipped.
The cache last-writer test passed when rerun after editing stopped. The two
remaining failures require unavailable local prerequisites: the original
decompilation symbol file for developer-contract tests, and OpenCV for two
portrait tests. Sound round trips, sound SPU budgets, species lint, compiler
checks and documentation references passed. The four targeted routing and
movement-preservation tests also passed. Full build-dependent checks were
skipped because this worktree has no freshly assembled everything disc.

## Ranked follow-up list

This is an exhaustive review order, not 183 confirmed defects. P0 is the
four-species repair. P1 finds duplicate same-tick events. P2 finds very
close events (at most two ticks); that needs a contact review. P3–P6 rank
long cues or similar sound choices for audition. Overlap alone is not a
bug: native heavy and aquatic cues intentionally overlap. P7 flags care
voices in condition walk; native tired behavior can intentionally cry.
Bank 3 belongs to the current partner, including when an NPC triggers it,
so those rows need contextual playback before any edit. P8 retains the
native slug recipe. P9 has no selection finding from this audit.

No automatic replacement is proposed for every insect, aquatic species or
heavy body. Auditioning a species means checking its foot/body contact and
sound together; the table gives a concrete next action without treating
all long or native-derived cues as wrong. Counts above two in a long clip
can represent several strides and are not by themselves excessive.

| Review rank | Species | Bank:effect IDs | W/C/R cycle ticks / count | Proposed action |
|---|---|---|---|---|
| 1 (P0) | 244 SuperStarmon | 1:17 | 24t/6, 28t/6, 20t/6 | Use SL 12; implemented, cadence retained |
| 2 (P0) | 243 Starmon | 1:16 | 16t/2, 16t/2, 16t/2 | Use SL 12; implemented, cadence retained |
| 3 (P0) | 373 WarGreymon | 1:13, 1:16 | 22t/2, 20t/2, 12t/2 | Use SL 12; implemented, cadence retained |
| 4 (P0) | 404 BlackWarGreymon | 1:16, 1:21 | 20t/2, 24t/2, 12t/2 | Use SL 12; implemented, cadence retained |
| 5 (P1) | 293 Gryphonmon | 1:12 | 26t/9, 32t/9, 20t/9 | Review duplicate contacts; SL 12 already selected |
| 6 (P2) | 192 Imperialdramon | 1:12 | 16t/4, 16t/4, 14t/4 | Review contact cadence; preserve poses; short cue alone may not suffice |
| 7 (P2) | 196 Halsemon | 1:12 | 16t/4, 16t/4, 14t/4 | Review contact cadence; preserve poses; short cue alone may not suffice |
| 8 (P2) | 201 Lighdramon | 1:12, 1:13 | 48t/6, 16t/4, 14t/4 | Review contact cadence; preserve poses; short cue alone may not suffice |
| 9 (P2) | 221 Salamon | 1:12 | 6t/4, 10t/4, 6t/3 | Review contact cadence; preserve poses; short cue alone may not suffice |
| 10 (P2) | 234 Gatomon | 1:12 | 48t/16, 48t/12, 48t/48 | Review contact cadence; preserve poses; short cue alone may not suffice |
| 11 (P2) | 252 Thundermon | 1:11, 1:16 | 16t/8, 20t/8, 20t/10 | Review contact cadence; preserve poses; short cue alone may not suffice |
| 12 (P2) | 264 Raremon | 1:12 | 16t/2, 16t/2, 12t/2 | Review contact cadence; preserve poses; short cue alone may not suffice |
| 13 (P2) | 276 Baihumon | 1:12 | 16t/4, 16t/4, 14t/4 | Review contact cadence; preserve poses; short cue alone may not suffice |
| 14 (P2) | 284 Crabmon | 1:12 | 24t/12, 24t/8, 24t/16 | Review contact cadence; preserve poses; short cue alone may not suffice |
| 15 (P2) | 287 Tapirmon | 1:12 | 16t/4, 16t/4, 14t/4 | Review contact cadence; preserve poses; short cue alone may not suffice |
| 16 (P2) | 296 Grizzlymon | 1:12 | 30t/12, 48t/12, 64t/16 | Review contact cadence; preserve poses; short cue alone may not suffice |
| 17 (P2) | 313 Bulbmon | 1:21 | 12t/4, 18t/4, 10t/4 | Review contact cadence; preserve poses; short cue alone may not suffice |
| 18 (P2) | 317 Fujinmon | 1:16, 1:21 | 26t/2, 29t/3, 16t/2 | Review contact cadence; preserve poses; short cue alone may not suffice |
| 19 (P2) | 323 Lynxmon | 1:12 | 16t/4, 16t/4, 14t/4 | Review contact cadence; preserve poses; short cue alone may not suffice |
| 20 (P2) | 405 Cannondramon | 1:12 | 10t/4, 10t/4, 14t/4 | Review contact cadence; preserve poses; short cue alone may not suffice |
| 21 (P2) | 409 Kyubimon | 1:12 | 12t/4, 17t/4, 6t/4 | Review contact cadence; preserve poses; short cue alone may not suffice |
| 22 (P3) | 202 Submarimon | 1:17 | 26t/2, 20t/1, 20t/2 | Audition SL 12/16 for land movement; keep 17 if aquatic/hover effect is intentional |
| 23 (P3) | 211 MetalSeadramon | 1:17 | 88t/1, 88t/1, 88t/1 | Audition SL 12/16 for land movement; keep 17 if aquatic/hover effect is intentional |
| 24 (P3) | 229 Phantomon | 1:17 | 104t/1, 104t/1, 104t/1 | Audition SL 12/16 for land movement; keep 17 if aquatic/hover effect is intentional |
| 25 (P3) | 238 Dolphmon | 1:17 | 72t/1, 72t/1, 72t/1 | Audition SL 12/16 for land movement; keep 17 if aquatic/hover effect is intentional |
| 26 (P3) | 240 Gesomon | 1:17 | 18t/2, 83t/4, 18t/2 | Audition SL 12/16 for land movement; keep 17 if aquatic/hover effect is intentional |
| 27 (P3) | 249 Quetzalmon | 1:17 | 24t/1, 28t/1, 20t/1 | Audition SL 12/16 for land movement; keep 17 if aquatic/hover effect is intentional |
| 28 (P3) | 254 Tylomon | 1:17 | 26t/2, 20t/1, 20t/2 | Audition SL 12/16 for land movement; keep 17 if aquatic/hover effect is intentional |
| 29 (P3) | 278 Octomon | 1:17 | 21t/1, 21t/1, 21t/1 | Audition SL 12/16 for land movement; keep 17 if aquatic/hover effect is intentional |
| 30 (P4) | 209 Lillymon | 1:18 | 22t/2, 20t/2, 18t/2 | Audition SL 12; same cue family as native Vademon |
| 31 (P4) | 223 LadyDevimon | 1:18 | 22t/2, 20t/2, 18t/2 | Audition SL 12; same cue family as native Vademon |
| 32 (P4) | 248 MarineAngemon | 1:18 | 22t/2, 20t/2, 18t/2 | Audition SL 12; same cue family as native Vademon |
| 33 (P4) | 311 Arukenimon | 1:18 | 22t/2, 20t/2, 18t/2 | Audition SL 12; same cue family as native Vademon |
| 34 (P5) | 182 Kimeramon | 1:13 | 20t/2, 24t/2, 20t/2 | Audition SL 12 for lighter bodies; retain deliberate heavy/hoof cues |
| 35 (P5) | 185 Armadillomon | 1:13 | 12t/2, 18t/2, 10t/2 | Audition SL 12 for lighter bodies; retain deliberate heavy/hoof cues |
| 36 (P5) | 189 Ankylomon | 1:13 | 48t/6, 28t/2, 20t/2 | Audition SL 12 for lighter bodies; retain deliberate heavy/hoof cues |
| 37 (P5) | 190 Angewomon | 1:16, 1:20 | 20t/2, 96t/12, 14t/2 | Audition SL 12 for lighter bodies; retain deliberate heavy/hoof cues |
| 38 (P5) | 193 Digmon | 1:13 | 20t/2, 24t/2, 20t/2 | Audition SL 12 for lighter bodies; retain deliberate heavy/hoof cues |
| 39 (P5) | 200 Pegasusmon | 1:20 | 18t/2, 20t/2, 16t/2 | Audition SL 12 for lighter bodies; retain deliberate heavy/hoof cues |
| 40 (P5) | 203 Veedramon | 1:13, 1:16 | 56t/8, 54t/6, 56t/14 | Audition SL 12 for lighter bodies; retain deliberate heavy/hoof cues |
| 41 (P5) | 210 GranKuwagamon | 1:13 | 24t/2, 24t/2, 20t/2 | Audition SL 12 for lighter bodies; retain deliberate heavy/hoof cues |
| 42 (P5) | 212 VenomMyotismon | 1:13 | 22t/2, 26t/2, 20t/2 | Audition SL 12 for lighter bodies; retain deliberate heavy/hoof cues |
| 43 (P5) | 213 AeroVeedramon | 1:13, 1:16 | 60t/10, 24t/2, 20t/4 | Audition SL 12 for lighter bodies; retain deliberate heavy/hoof cues |
| 44 (P5) | 216 Devidramon | 1:13 | 36t/6, 54t/6, 20t/4 | Audition SL 12 for lighter bodies; retain deliberate heavy/hoof cues |
| 45 (P5) | 218 Ikkakumon | 1:13 | 22t/2, 33t/2, 20t/4 | Audition SL 12 for lighter bodies; retain deliberate heavy/hoof cues |
| 46 (P5) | 219 Zudomon | 1:13 | 60t/8, 90t/8, 96t/16 | Audition SL 12 for lighter bodies; retain deliberate heavy/hoof cues |
| 47 (P5) | 224 MetalGreymonVaccine | 1:13 | 20t/2, 24t/2, 20t/2 | Audition SL 12 for lighter bodies; retain deliberate heavy/hoof cues |
| 48 (P5) | 237 Diaboromon | 1:13 | 24t/2, 28t/2, 22t/2 | Audition SL 12 for lighter bodies; retain deliberate heavy/hoof cues |
| 49 (P5) | 257 Triceramon | 1:13, 1:16 | 32t/4, 24t/2, 20t/2 | Audition SL 12 for lighter bodies; retain deliberate heavy/hoof cues |
| 50 (P5) | 260 MetalTyrannomon | 1:13 | 22t/2, 26t/2, 20t/2 | Audition SL 12 for lighter bodies; retain deliberate heavy/hoof cues |
| 51 (P5) | 262 Flymon | 1:20 | 29t/1, 29t/1, 29t/1 | Audition SL 12 for lighter bodies; retain deliberate heavy/hoof cues |
| 52 (P5) | 265 DarkTyrannomon | 1:13, 1:16 | 26t/2, 26t/2, 20t/2 | Audition SL 12 for lighter bodies; retain deliberate heavy/hoof cues |
| 53 (P5) | 266 ExTyrannomon | 1:11, 1:13 | 60t/6, 24t/2, 18t/2 | Audition SL 12 for lighter bodies; retain deliberate heavy/hoof cues |
| 54 (P5) | 267 Mammothmon | 1:13 | 24t/2, 24t/2, 20t/2 | Audition SL 12 for lighter bodies; retain deliberate heavy/hoof cues |
| 55 (P5) | 268 SkullMammothmon | 1:13 | 24t/2, 24t/2, 20t/2 | Audition SL 12 for lighter bodies; retain deliberate heavy/hoof cues |
| 56 (P5) | 272 Woodmon | 1:13 | 13t/2, 28t/2, 20t/2 | Audition SL 12 for lighter bodies; retain deliberate heavy/hoof cues |
| 57 (P5) | 280 Pumpkinmon | 1:13 | 20t/2, 22t/2, 20t/2 | Audition SL 12 for lighter bodies; retain deliberate heavy/hoof cues |
| 58 (P5) | 281 Cyclonemon | 1:13 | 20t/2, 20t/0, 18t/2 | Audition SL 12 for lighter bodies; retain deliberate heavy/hoof cues |
| 59 (P5) | 286 Deramon | 1:13, 3:52 | 22t/2, 21t/1, 20t/2 | Audition SL 12 for lighter bodies; retain deliberate heavy/hoof cues |
| 60 (P5) | 289 ChaosLord | 1:13, 1:14 | 20t/2, 48t/8, 18t/2 | Audition SL 12 for lighter bodies; retain deliberate heavy/hoof cues |
| 61 (P5) | 290 Clockmon | 1:11, 1:21 | 20t/2, 22t/2, 16t/2 | Audition SL 12 for lighter bodies; retain deliberate heavy/hoof cues |
| 62 (P5) | 291 Dragomon | 1:11, 1:13 | 16t/2, 28t/2, 22t/2 | Audition SL 12 for lighter bodies; retain deliberate heavy/hoof cues |
| 63 (P5) | 292 Deltamon | 1:13 | 28t/2, 28t/2, 20t/2 | Audition SL 12 for lighter bodies; retain deliberate heavy/hoof cues |
| 64 (P5) | 294 Datamon | 1:21 | 10t/2, 15t/2, 8t/2 | Audition SL 12 for lighter bodies; retain deliberate heavy/hoof cues |
| 65 (P5) | 295 Vilemon | 1:13, 1:16 | 60t/8, 24t/2, 20t/2 | Audition SL 12 for lighter bodies; retain deliberate heavy/hoof cues |
| 66 (P5) | 298 Dokugumon | 1:13 | 24t/2, 28t/2, 20t/2 | Audition SL 12 for lighter bodies; retain deliberate heavy/hoof cues |
| 67 (P5) | 310 Assaultmon | 1:20 | 20t/2, 16t/2, 14t/2 | Audition SL 12 for lighter bodies; retain deliberate heavy/hoof cues |
| 68 (P5) | 312 Creepymon | 1:21 | 20t/2, 22t/2, 16t/2 | Audition SL 12 for lighter bodies; retain deliberate heavy/hoof cues |
| 69 (P5) | 318 Gallantmon | 1:21 | 20t/2, 22t/2, 16t/2 | Audition SL 12 for lighter bodies; retain deliberate heavy/hoof cues |
| 70 (P5) | 320 Growlmon | 1:13 | 22t/2, 26t/2, 18t/2 | Audition SL 12 for lighter bodies; retain deliberate heavy/hoof cues |
| 71 (P5) | 321 Knightmon | 1:16, 1:21 | 27t/2, 22t/2, 16t/2 | Audition SL 12 for lighter bodies; retain deliberate heavy/hoof cues |
| 72 (P5) | 322 Kyukimon | 1:13 | 80t/10, 72t/8, 72t/18 | Audition SL 12 for lighter bodies; retain deliberate heavy/hoof cues |
| 73 (P5) | 324 Maildramon | 1:20 | 20t/2, 16t/2, 14t/2 | Audition SL 12 for lighter bodies; retain deliberate heavy/hoof cues |
| 74 (P5) | 326 WarGrowlmon | 1:13 | 22t/2, 26t/2, 12t/2 | Audition SL 12 for lighter bodies; retain deliberate heavy/hoof cues |
| 75 (P5) | 328 Snimon | 1:12, 1:13 | 64t/16, 28t/2, 22t/2 | Audition SL 12 for lighter bodies; retain deliberate heavy/hoof cues |
| 76 (P5) | 332 Roachmon | 1:13, 1:16 | 17t/2, 24t/2, 18t/2 | Audition SL 12 for lighter bodies; retain deliberate heavy/hoof cues |
| 77 (P5) | 333 Raijinmon | 1:16, 1:21 | 24t/2, 22t/2, 16t/2 | Audition SL 12 for lighter bodies; retain deliberate heavy/hoof cues |
| 78 (P5) | 335 MegaGargomon | 1:21 | 18t/2, 32t/2, 10t/2 | Audition SL 12 for lighter bodies; retain deliberate heavy/hoof cues |
| 79 (P5) | 402 NeoCrimson | 1:13 | 22t/2, 26t/2, 20t/2 | Audition SL 12 for lighter bodies; retain deliberate heavy/hoof cues |
| 80 (P5) | 407 Armageddemon | 1:13 | 24t/2, 24t/2, 20t/2 | Audition SL 12 for lighter bodies; retain deliberate heavy/hoof cues |
| 81 (P5) | 408 Suijinmon | 1:13 | 18t/4, 27t/4, 14t/2 | Audition SL 12 for lighter bodies; retain deliberate heavy/hoof cues |
| 82 (P5) | 430 Zanbamon | 1:20 | 18t/2, 20t/2, 16t/2 | Audition SL 12 for lighter bodies; retain deliberate heavy/hoof cues |
| 83 (P5) | 433 Guilmon | 1:13 | 22t/2, 26t/2, 18t/2 | Audition SL 12 for lighter bodies; retain deliberate heavy/hoof cues |
| 84 (P5) | 461 Omnimon | 1:13, 1:16 | 20t/2, 24t/2, 12t/2 | Audition SL 12 for lighter bodies; retain deliberate heavy/hoof cues |
| 85 (P6) | 187 Stingmon | 1:16 | 16t/2, 16t/2, 16t/2 | Audition SL 12 if the Leomon/insect clack does not fit; keep 16 when intentional |
| 86 (P6) | 194 ExVeemon | 1:16 | 16t/2, 16t/2, 16t/2 | Audition SL 12 if the Leomon/insect clack does not fit; keep 16 when intentional |
| 87 (P6) | 195 Flamedramon | 1:16 | 14t/2, 18t/2, 8t/2 | Audition SL 12 if the Leomon/insect clack does not fit; keep 16 when intentional |
| 88 (P6) | 197 Magnamon | 1:16 | 16t/2, 16t/2, 16t/2 | Audition SL 12 if the Leomon/insect clack does not fit; keep 16 when intentional |
| 89 (P6) | 199 Paildramon | 1:16 | 20t/2, 20t/2, 20t/2 | Audition SL 12 if the Leomon/insect clack does not fit; keep 16 when intentional |
| 90 (P6) | 205 MegaKabuterimon | 1:16 | 20t/2, 20t/2, 20t/4 | Audition SL 12 if the Leomon/insect clack does not fit; keep 16 when intentional |
| 91 (P6) | 206 MagnaAngemon | 1:16 | 16t/2, 16t/2, 16t/2 | Audition SL 12 if the Leomon/insect clack does not fit; keep 16 when intentional |
| 92 (P6) | 207 Seraphimon | 1:16 | 21t/2, 24t/2, 20t/2 | Audition SL 12 if the Leomon/insect clack does not fit; keep 16 when intentional |
| 93 (P6) | 220 Vikemon | 1:16 | 64t/8, 104t/8, 104t/16 | Audition SL 12 if the Leomon/insect clack does not fit; keep 16 when intentional |
| 94 (P6) | 225 Shurimon | 1:16 | 40t/8, 60t/8, 80t/16 | Audition SL 12 if the Leomon/insect clack does not fit; keep 16 when intentional |
| 95 (P6) | 226 Silphymon | 1:16 | 16t/2, 16t/2, 16t/2 | Audition SL 12 if the Leomon/insect clack does not fit; keep 16 when intentional |
| 96 (P6) | 227 Apemon | 1:16 | 43t/8, 20t/4, 20t/6 | Audition SL 12 if the Leomon/insect clack does not fit; keep 16 when intentional |
| 97 (P6) | 230 Rosemon | 1:11, 1:16 | 55t/10, 82t/10, 80t/16 | Audition SL 12 if the Leomon/insect clack does not fit; keep 16 when intentional |
| 98 (P6) | 232 BomberNanimon | 1:16 | 104t/20, 104t/16, 104t/26 | Audition SL 12 if the Leomon/insect clack does not fit; keep 16 when intentional |
| 99 (P6) | 246 Infermon | 1:16 | 19t/2, 28t/2, 17t/2 | Audition SL 12 if the Leomon/insect clack does not fit; keep 16 when intentional |
| 100 (P6) | 247 Kokuwamon | 1:16 | 20t/4, 30t/4, 30t/6 | Audition SL 12 if the Leomon/insect clack does not fit; keep 16 when intentional |
| 101 (P6) | 250 Shadramon | 1:16 | 15t/2, 18t/2, 14t/2 | Audition SL 12 if the Leomon/insect clack does not fit; keep 16 when intentional |
| 102 (P6) | 253 Tuskmon | 1:16 | 20t/2, 20t/2, 20t/2 | Audition SL 12 if the Leomon/insect clack does not fit; keep 16 when intentional |
| 103 (P6) | 255 Valkyrimon | 1:16 | 24t/2, 28t/2, 16t/2 | Audition SL 12 if the Leomon/insect clack does not fit; keep 16 when intentional |
| 104 (P6) | 259 Okuwamon | 1:16 | 20t/2, 20t/2, 20t/2 | Audition SL 12 if the Leomon/insect clack does not fit; keep 16 when intentional |
| 105 (P6) | 270 PrinceMamemon | 1:16 | 16t/2, 16t/2, 16t/2 | Audition SL 12 if the Leomon/insect clack does not fit; keep 16 when intentional |
| 106 (P6) | 277 SkullMeramon | 1:16 | 13t/2, 16t/2, 16t/2 | Audition SL 12 if the Leomon/insect clack does not fit; keep 16 when intentional |
| 107 (P6) | 279 MarineDevimon | 1:16 | 16t/2, 24t/2, 12t/2 | Audition SL 12 if the Leomon/insect clack does not fit; keep 16 when intentional |
| 108 (P6) | 282 Kiwimon | 1:11, 1:16 | 20t/2, 16t/2, 16t/2 | Audition SL 12 if the Leomon/insect clack does not fit; keep 16 when intentional |
| 109 (P6) | 288 Boltmon | 1:16 | 15t/2, 15t/2, 15t/2 | Audition SL 12 if the Leomon/insect clack does not fit; keep 16 when intentional |
| 110 (P6) | 297 Marsmon | 1:16 | 16t/2, 16t/2, 16t/2 | Audition SL 12 if the Leomon/insect clack does not fit; keep 16 when intentional |
| 111 (P6) | 299 Hookmon | 1:16 | 16t/2, 16t/2, 16t/2 | Audition SL 12 if the Leomon/insect clack does not fit; keep 16 when intentional |
| 112 (P6) | 300 SlashAngemon | 1:16 | 16t/2, 16t/2, 16t/2 | Audition SL 12 if the Leomon/insect clack does not fit; keep 16 when intentional |
| 113 (P6) | 302 HiAndromon | 1:16 | 16t/2, 16t/2, 16t/2 | Audition SL 12 if the Leomon/insect clack does not fit; keep 16 when intentional |
| 114 (P6) | 303 KingEtemon | 1:16 | 16t/2, 16t/2, 16t/2 | Audition SL 12 if the Leomon/insect clack does not fit; keep 16 when intentional |
| 115 (P6) | 304 Divermon | 1:16 | 16t/2, 18t/2, 14t/2 | Audition SL 12 if the Leomon/insect clack does not fit; keep 16 when intentional |
| 116 (P6) | 306 GrapLeomon | 1:16 | 16t/2, 16t/2, 16t/2 | Audition SL 12 if the Leomon/insect clack does not fit; keep 16 when intentional |
| 117 (P6) | 308 Dinohyumon | 1:16 | 16t/2, 16t/2, 16t/2 | Audition SL 12 if the Leomon/insect clack does not fit; keep 16 when intentional |
| 118 (P6) | 309 Antylamon | 1:16 | 16t/2, 16t/2, 16t/2 | Audition SL 12 if the Leomon/insect clack does not fit; keep 16 when intentional |
| 119 (P6) | 314 SkullSatamon | 1:16 | 16t/2, 16t/2, 16t/2 | Audition SL 12 if the Leomon/insect clack does not fit; keep 16 when intentional |
| 120 (P6) | 315 Taomon | 1:16 | 16t/2, 16t/2, 16t/2 | Audition SL 12 if the Leomon/insect clack does not fit; keep 16 when intentional |
| 121 (P6) | 316 Sakuyamon | 1:16 | 16t/2, 16t/2, 16t/2 | Audition SL 12 if the Leomon/insect clack does not fit; keep 16 when intentional |
| 122 (P6) | 319 Pharaohmon | 1:16 | 25t/2, 28t/2, 23t/2 | Audition SL 12 if the Leomon/insect clack does not fit; keep 16 when intentional |
| 123 (P6) | 325 Musyamon | 1:16 | 18t/2, 24t/2, 20t/2 | Audition SL 12 if the Leomon/insect clack does not fit; keep 16 when intentional |
| 124 (P6) | 327 Gargoylemon | 1:16 | 22t/2, 24t/2, 20t/2 | Audition SL 12 if the Leomon/insect clack does not fit; keep 16 when intentional |
| 125 (P6) | 330 Minotarumon | 1:16 | 64t/8, 24t/2, 20t/2 | Audition SL 12 if the Leomon/insect clack does not fit; keep 16 when intentional |
| 126 (P6) | 331 Vemmon | 1:16 | 16t/2, 16t/2, 16t/2 | Audition SL 12 if the Leomon/insect clack does not fit; keep 16 when intentional |
| 127 (P6) | 334 Mummymon | 1:16 | 16t/2, 16t/2, 16t/2 | Audition SL 12 if the Leomon/insect clack does not fit; keep 16 when intentional |
| 128 (P6) | 336 Raidenmon | 1:16 | 20t/2, 20t/2, 20t/2 | Audition SL 12 if the Leomon/insect clack does not fit; keep 16 when intentional |
| 129 (P6) | 354 Renamon | 1:16 | 48t/8, 48t/6, 56t/14 | Audition SL 12 if the Leomon/insect clack does not fit; keep 16 when intentional |
| 130 (P6) | 403 Beelzemon | 1:16 | 24t/2, 48t/4, 72t/12 | Audition SL 12 if the Leomon/insect clack does not fit; keep 16 when intentional |
| 131 (P6) | 406 MaloMyotismon | 1:16 | 22t/2, 24t/2, 20t/2 | Audition SL 12 if the Leomon/insect clack does not fit; keep 16 when intentional |
| 132 (P6) | 432 Bastemon | 1:16 | 32t/4, 40t/4, 40t/8 | Audition SL 12 if the Leomon/insect clack does not fit; keep 16 when intentional |
| 133 (P6) | 460 Garudamon | 1:16 | 16t/2, 16t/2, 16t/2 | Audition SL 12 if the Leomon/insect clack does not fit; keep 16 when intentional |
| 134 (P7) | 235 Candlemon | 1:10, 3:52 | 102t/6, 105t/5, 102t/6 | Review condition cry in context; bank 3 is shared partner care audio, not an SL step |
| 135 (P7) | 269 Garbagemon | 1:10, 3:52 | 19t/1, 21t/1, 19t/1 | Review condition cry in context; bank 3 is shared partner care audio, not an SL step |
| 136 (P7) | 274 Blossomon | 1:10, 3:52 | 34t/2, 42t/2, 34t/2 | Review condition cry in context; bank 3 is shared partner care audio, not an SL step |
| 137 (P7) | 476 Nyaromon | 1:10, 3:52 | 19t/2, 21t/1, 19t/2 | Review condition cry in context; bank 3 is shared partner care audio, not an SL step |
| 138 (P7) | 477 Yokomon | 1:10, 3:52 | 17t/1, 21t/1, 17t/1 | Review condition cry in context; bank 3 is shared partner care audio, not an SL step |
| 139 (P8) | 231 ShellNumemon | 1:24 | 104t/10, 104t/8, 104t/12 | Keep slug cue unless audible overlap is objectionable |
| 140 (P8) | 307 BlackKingNumemon | 1:24 | 32t/2, 40t/2, 24t/2 | Keep slug cue unless audible overlap is objectionable |
| 141 (P9) | 180 Veemon | 1:12 | 10t/2, 14t/2, 6t/2 | No bank-selection finding; check contact fit by eye/ear |
| 142 (P9) | 181 Puppetmon | 1:12 | 16t/2, 20t/2, 12t/2 | No bank-selection finding; check contact fit by eye/ear |
| 143 (P9) | 183 Wormmon | 1:19 | 18t/2, 18t/1, 18t/2 | No bank-selection finding; check contact fit by eye/ear |
| 144 (P9) | 184 Hawkmon | 1:11 | 12t/2, 14t/2, 12t/2 | No bank-selection finding; check contact fit by eye/ear |
| 145 (P9) | 188 Aquilamon | silent | 88t/0, 88t/0, 88t/0 | No bank-selection finding; check contact fit by eye/ear |
| 146 (P9) | 191 MetalGarurumon | 1:12 | 18t/4, 27t/4, 14t/2 | No bank-selection finding; check contact fit by eye/ear |
| 147 (P9) | 198 Nefertimon | 1:12 | 16t/2, 24t/2, 15t/2 | No bank-selection finding; check contact fit by eye/ear |
| 148 (P9) | 208 Togemon | 1:11 | 16t/2, 12t/2, 16t/4 | No bank-selection finding; check contact fit by eye/ear |
| 149 (P9) | 214 Shakkoumon | silent | 72t/0, 72t/0, 72t/0 | No bank-selection finding; check contact fit by eye/ear |
| 150 (P9) | 215 Magnadramon | silent | 88t/0, 88t/0, 88t/0 | No bank-selection finding; check contact fit by eye/ear |
| 151 (P9) | 217 Gomamon | silent | 72t/0, 108t/0, 72t/0 | No bank-selection finding; check contact fit by eye/ear |
| 152 (P9) | 222 BlackGatomon | 1:12 | 16t/2, 24t/2, 10t/2 | No bank-selection finding; check contact fit by eye/ear |
| 153 (P9) | 228 Baronmon | silent | 93t/0, 93t/0, 93t/0 | No bank-selection finding; check contact fit by eye/ear |
| 154 (P9) | 233 RedOtamamon | silent | 91t/0, 91t/0, 91t/0 | No bank-selection finding; check contact fit by eye/ear |
| 155 (P9) | 236 DemiDevimon | silent | 20t/0, 30t/0, 28t/0 | No bank-selection finding; check contact fit by eye/ear |
| 156 (P9) | 239 Gizamon | 1:11 | 12t/2, 18t/2, 8t/2 | No bank-selection finding; check contact fit by eye/ear |
| 157 (P9) | 241 Wizardmon | 1:12 | 104t/16, 104t/12, 104t/26 | No bank-selection finding; check contact fit by eye/ear |
| 158 (P9) | 242 Sorcermon | 1:12 | 70t/14, 105t/14, 110t/22 | No bank-selection finding; check contact fit by eye/ear |
| 159 (P9) | 245 Piedmon | silent | 104t/0, 104t/0, 104t/0 | No bank-selection finding; check contact fit by eye/ear |
| 160 (P9) | 251 Solarmon | silent | 88t/0, 88t/0, 88t/0 | No bank-selection finding; check contact fit by eye/ear |
| 161 (P9) | 256 VioletElecmon | 1:11 | 20t/4, 20t/2, 20t/4 | No bank-selection finding; check contact fit by eye/ear |
| 162 (P9) | 258 SaberLeomon | 1:12 | 32t/4, 32t/4, 42t/6 | No bank-selection finding; check contact fit by eye/ear |
| 163 (P9) | 261 Tortomon | 1:11, 1:12 | 32t/8, 10t/2, 10t/2 | No bank-selection finding; check contact fit by eye/ear |
| 164 (P9) | 263 Mushroomon | 1:12 | 16t/2, 20t/2, 12t/2 | No bank-selection finding; check contact fit by eye/ear |
| 165 (P9) | 271 Plesiomon | silent | 39t/0, 39t/0, 39t/0 | No bank-selection finding; check contact fit by eye/ear |
| 166 (P9) | 273 Floramon | 1:11 | 28t/0, 42t/0, 20t/2 | No bank-selection finding; check contact fit by eye/ear |
| 167 (P9) | 275 Scorpiomon | silent | 29t/0, 29t/0, 29t/0 | No bank-selection finding; check contact fit by eye/ear |
| 168 (P9) | 283 Syakomon | silent | 42t/0, 42t/0, 42t/0 | No bank-selection finding; check contact fit by eye/ear |
| 169 (P9) | 285 Gazimon | 1:12 | 12t/4, 18t/4, 10t/2 | No bank-selection finding; check contact fit by eye/ear |
| 170 (P9) | 305 Ebidramon | silent | 59t/0, 59t/0, 59t/0 | No bank-selection finding; check contact fit by eye/ear |
| 171 (P9) | 329 Ghoulmon | silent | 70t/0, 70t/0, 70t/0 | No bank-selection finding; check contact fit by eye/ear |
| 172 (P9) | 351 Kotemon | 1:12 | 16t/2, 20t/2, 12t/2 | No bank-selection finding; check contact fit by eye/ear |
| 173 (P9) | 352 Monmon | 1:12 | 44t/11, 42t/7, 44t/11 | No bank-selection finding; check contact fit by eye/ear |
| 174 (P9) | 353 Bearmon | 1:12 | 16t/2, 20t/2, 12t/2 | No bank-selection finding; check contact fit by eye/ear |
| 175 (P9) | 400 Apocalymon | silent | 104t/0, 104t/0, 104t/0 | No bank-selection finding; check contact fit by eye/ear |
| 176 (P9) | 401 Pukumon | silent | 16t/0, 20t/0, 16t/0 | No bank-selection finding; check contact fit by eye/ear |
| 177 (P9) | 431 Kurisarimon | silent | 59t/0, 59t/0, 59t/0 | No bank-selection finding; check contact fit by eye/ear |
| 178 (P9) | 470 Pabumon | 1:10 | 23t/3, 22t/0, 23t/3 | No bank-selection finding; check contact fit by eye/ear |
| 179 (P9) | 471 Pichimon | 1:10 | 18t/2, 18t/2, 18t/2 | No bank-selection finding; check contact fit by eye/ear |
| 180 (P9) | 472 YukimiBotamon | 1:10, 1:11 | 18t/1, 18t/2, 18t/1 | No bank-selection finding; check contact fit by eye/ear |
| 181 (P9) | 473 Nyokimon | silent | 26t/0, 26t/0, 26t/0 | No bank-selection finding; check contact fit by eye/ear |
| 182 (P9) | 474 Motimon | 1:10 | 18t/2, 18t/2, 18t/2 | No bank-selection finding; check contact fit by eye/ear |
| 183 (P9) | 475 Bukamon | 1:10 | 18t/2, 18t/2, 18t/2 | No bank-selection finding; check contact fit by eye/ear |
