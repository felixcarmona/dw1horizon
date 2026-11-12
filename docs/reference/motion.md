# Motion: how imported species are animated

How the partner animation slots are used by the engine, what that asks of a clip, how the imported species get their
everyday and field animations (retargeting from a DW1 donor, foot-based leg solving, per-species field recipes), the
engine layers that play them (cold animations, field transitions), and the measurements and rules that decide whether a
motion is acceptable. Where the models come from is [imported-species.md](imported-species.md).

The MMD animation stream (keyframe momentum, loops, texture and sound instructions, root motion, the interpreter's
quirks) is documented in [../mods/models.md](../mods/models.md) § 2.2 and is not repeated here; this page adds what
matters when writing new clips for an existing rig.

## Playback facts that shape a clip

- **20 logic ticks per second.** Every pose is integer: rotations in 1/4096 turn (one unit = 0.088°), scale 4.12,
  translations in model units. A keyframe sets per-channel momentum `delta/divisor` with the remainder spread out; the
  engine accumulates integers, so a clip is only exact when it is re-played tick by tick (`mmd.AnimPlayer` does what
  `tickAnimation` does).
- **Between ticks** the game interpolates each bone's Euler angles linearly (shortest arc) and its translation and
  scale, not by quaternion slerp; at 60 fps the two intermediate samples are fixed-point blends at alpha 1365 and 2730
  of 4096. A pose that is clear at every logic tick can still cross the floor or another piece between ticks, so checks
  sample the thirds too (`tools/motiontailspace.py --subframes 3`). An exporter that keeps only keyframes and lets a
  viewer slerp loses the shape between them (more than 10° off on about a quarter of the original slots, a half-turn
  flipped where a bone turns past 180° between keys).
- **Finite loops.** The loop end decrements the count and jumps back only while it is not 0; at 0 it skips to the next
  instruction. One pass too many is a common reader bug.
- **Infinite loops repeat motion, not poses.** The pose is not reset at the jump, so a loop closes only if the pose at
  the loop end equals the pose at the jump frame and every speed is set again at the jump frame. Imported delta loops
  that miss this drift a little on every pass (a native battle idle can turn a joint by degrees after three passes):
  `tools/motionloopfix.py` closes them over the last 1-3 ticks.
- **Scale channels** of source models often hold 4095/4097 from quantization; a solver must keep them, not round them
  to 4096 or treat them as motion.
- **Root motion** (bone 0) is accumulated into the entity's position, never into the pose; in battle slots 0x23/0x24
  its X is cancelled. A field clip's forward travel per loop is what the follow logic sees as the partner's speed.
- **Key-frame headers** stay in place even when empty: the pre-check of a pending instruction's kind (`& 0x1000`) also
  matches texture instructions, so reordering instructions can change behaviour.
- **Sounds** (code 4) play only when the entity is on screen; bank 4 is the species' voice. **Texture moves** (code 3)
  copy rectangles inside the model's own VRAM slot, x and widths in 16-bit words (4 pixels); a rectangle past the
  slot's 64 words reads pixels that are not stored (an imported closed-eye frame can do that). The flat-sprite
  rectangle and palette row 15 are reserved.

## The partner's slots and who starts them

| Slot | Played | Started by |
|---|---|---|
| 0 | field idle | `setPartnerIdle` when no condition below |
| 1 | poor-condition idle | `setPartnerIdle` under condition sleepy, tired, injured or sick (bits 0x01, 0x02, 0x20, 0x40) |
| 2 | walk (following at middle distance) | `setPartnerSlowWalking`, and when far but unhappy |
| 3 | condition walk | `setPartnerSlowWalking` under the same four condition bits |
| 4 | catch-up run (far from the tamer) | `partnerTickWalking`, unless unhappy |
| 5 / 7 | happy / unhappy gesture (happiness ≥ 31 / < −30, no condition) | `updateConditionAnimation` |
| 8 | eat | feeding (waits for the end) |
| 9, 11 | asleep, going to sleep; 11 (0x0B) also praise, favourite-food joy, the end of an evolution | sleep, care, evolution |
| 10, 12 | toilet, after pooping; 12 (0x0C) also scold, the evolution flash, a new egg | care |
| 13 | refuse | feeding, items |
| 14 (0x0E) | sick or injured idle | `updateConditionAnimation` |
| 15, 16, 17, 18, 19 (0x0F-0x13) | hungry, needs the toilet, sleepy, tired, unhappy idles; 0x12 also after training, 0x13 also the battle "senile" status | `updateConditionAnimation`, gyms, battle |
| 0x16, 0x1B, 0x25 | brain and HP training (0x1B's pauses are driven from outside: it is not a field run), blocking | gyms |
| 0x21, 0x22 | battle idle, tired battle idle | battle |
| 0x23, 0x24 | battle movement: 0x23 when poisoned or at HP ≤ 20 %, 0x24 otherwise; 0x24 also fleeing | `BTL_startWalkingAnimation` |
| 0x28, 0x29 | hit (front, knocked back) | battle |
| 0x2A, 0x2B, 0x2C | victory, faint, get up (the fight's end waits for them) | battle |
| 0x2E + *i* | technique *i* of the species' list (the finisher is its own index) | battle |

Slots 6, 0x14, 0x1A, 0x1C-0x20, 0x26 and 0x27 are the tamer's, NPCs' and the kart race's. Which slots a partner must
have, and the lint rule for each: [imported-species.md](imported-species.md), "What the game asks of every partner".

### Field selection details

- `getPartnerTamerCloseness` gives far / middle / near. Far: slot 4 (2 if unhappy). Middle: slot 2 or 3. Near: idle 0
  or 1, and the gesture and condition idles above.
- **A walk finishes its pass before switching.** `partnerTickWalking` sets `loopCount = 1` on an infinite walk loop and
  switches when it reaches 0, so the partner changes state only at the end of a walk cycle. A long walk loop makes the
  partner slow to react. Patch 0232 lets the two reviewed 73-frame quadruped walks (Ankylomon 189, Lighdramon 201:
  three 24-tick steps inside one 72-tick acting span) switch at the end of each completed step, and their 73-frame idle
  yield to a walk request at any tick.
  Patch 0291 bounds the wait for the other imported walks and condition walks (slots 2/3) of at least 40 ticks: a pending
  navigation or needs change may yield after 24 completed logic ticks, and a request arriving later yields at once. That
  is not a stride boundary: the existing four-tick field blend hides the cut. Ordinary following still plays the full loop,
  189 and 201 keep their step-aligned rules, and no timer or allocation is added. (Lighdramon's walk is now a 15-frame loop, so only its 73-frame idle still uses patch 0232's yield.)
- **Condition idles depend on the idle's length.** Standing near the tamer, `STOP_DISTANCE_TIMER` counts up each tick
  and `updateConditionAnimation` runs when it is greater than `anim->frameCount × EMOTION_ANIM_TIMEOUT`, the timeout a
  random 1..5 drawn when the idle starts. The timer is a signed 8-bit value (it wraps after 127), so with an idle of
  127 frames or more the condition idles (hungry, tired, the gestures...) never start, and with an idle over 25 frames
  some draws can never be reached. A long native idle therefore hides the partner's needs; keep field idles short or
  expect fewer condition animations.
- A clip the partner needs to finish (eat, toilet, refuse, sleep, victory, faint, get up, techniques) must not be empty:
  `startAnimation` returns on an empty entry and the code waiting for `animFrame >= frameCount` waits on the previous
  clip.

### Scripted movement and turns

`walk` starts slot 2; `run` and `walk_away` start slot 4. Movement completion
starts idle slot 0. `face` and `turn` do not start a partner clip:
`tickScriptedMovement` calls `tickLookAtEntity` / `tickEntitySetRotation`, and
`WAIT_FOR_ENTITY` resumes only after the movement record becomes inactive
(type 255). A visible dialogue box can therefore remain while a turn is pending.

Patch 0301 lets `rotateEntity` choose counterclockwise when both directions are
exactly 2048 angle units. Previously both strict comparisons rejected that tie,
so an actor facing exactly away from its target stayed still forever. This
applies to tamers, partners and NPCs, independently of species or animation slot.
At Birdramon's nest (screen 129, script 124, section 51), starting on the
step-0 tile at `(-192, -350)` reproduces the report with Apemon 227. After
"Hmmm.", `tamer.face(partner)` leaves the tamer at `(607, -299)`, heading 2106,
with the partner at `(571, -698)`: the target heading is 58. Both turn distances
are 2048. The interpreter stays on `WAIT_FOR_ENTITY` (0x4A), actor index 0,
waiting for the tamer's movement type to become 255. The partner's turn has
already finished; the tamer's slot 16 is at frame 51 of 51. This is a rotation
tie, rather than the empty-slot-4 failure fixed for MasterTyrannomon.

The Apemon model pin is identical on v0.0.2 and the main baseline (model SHA-1
`93cc58ec7b03efbb75f9f1cbd53fa07e67bfafe3`); that comparison needs no second gait model.
The host regression exercises all 16,777,216 pairs of 12-bit headings with the
script turn speed of 512 units per tick:

```sh
python3 tools/dev/playtest/rotation_host.py
```

The emulator regression boots a private test card with Apemon initialized by
the game, then triggers the original scene from that tile. It requires the
battle, recruitment, all later partner turns and walking, field control and a
return visit to finish. The opponent's HP is set to zero after battle entry.
Use `--partner 3` for the native Agumon control; `--baseline` instead asserts
the pre-fix hang. Checkpoints are tied to disc and executable hashes.

```sh
python3 tools/dev/playtest/birdramon_nest.py build/dev-everything.cue \
  --exe build/dev-everything/exe/SLUS_010.32 --port 40129
```

Controlled English builds with the same `MOD_VERSION=v0.0.2` reduce
`rotateEntity` from 196 to 180 bytes and `main_BSS_END` from `0x801cb3cc` to
`0x801cb3bc`. The aligned heap grows from 199,472 to 199,488 bytes. No BSS or
allocation is added. All 320 story setups fit; the conservative story check
keeps a 15,488-byte minimum on screen 361 in both builds (it does not credit
heap growth above its reference).

The everything build also runs `tools/scriptclips.py` after assembling
`DIGI.DAT`. It checks all 35 partner script slots, resolves native partner-only
and replacement files from the generated species definitions, and follows cold
entries into their actual data. An empty, absent or zero-duration required clip
fails the build. `face` has no clip dependency; this gate addresses the separate
empty-animation failure class.

The [per-species audit](../data/partner-script-clips.csv) records all 283 partners
of the tested everything build, with hashes of their resident model bytes:
none has a missing script slot. Regenerate the full durations report and snapshot
from a built disc's inputs with:

```sh
python3 tools/scriptclips.py build/dev-everything/DIGI.DAT \
  --out build/script-clips.json --csv docs/data/partner-script-clips.csv
python3 -m unittest tools.test_scriptclips
```

### Speeds

The tamer walks at 20 units per tick and runs at 50. Measured native partners walk at
15–31 and run at 35–52 units per tick. Imports below 15 walking or 35 running need
review, but a run below 50 is also normal among natives. The partner follows a
trail and can teleport when both it and the next tile are off screen
([world.md](world.md)); matching the tamer's speed is not a native requirement.
Keep the condition walk slower than the ordinary walk. Cadence and travel must
change together on planted gaits: increasing root travel alone makes feet skate.
Typical authored values:

| Gait | Cycle (ticks) | Root units per tick |
|---|---|---|
| walk (2) | 14-20 | 20-22.5 |
| condition walk (3) | 16-24 | 14-15 |
| run (4) | 8-12 | 45-52 |

MetalGreymon Vaccine (224) uses native MetalGreymon (12) field programs:
25 / 20.833 / 50 units per tick in slots 2 / 3 / 4. Every decoded field frame,
root translation, sound and loop is identical. There is no species-specific
stride transition or generated field overlay for 224.

Scaling a donor's root travel by the size ratio alone (a big import walking with a small donor's legs) leaves a
catch-up slower than the tamer (13.9 units per tick was measured once, so the partner never caught up); cadence and
travel are chosen together.

## Engine layers for animation

**Cold animations (patch 0113, `tools/coldsplit.py`).** A partner model in `DIGI.DAT` is cut in two: the resident part
(the MMD without its rarely played animations) must fit `PARTNER_MODEL_BUFFER` (0x18800 = 100 352 bytes on the console
layout); each cold slot's table entry is `0x80000000 | (length in words << 16) | offset in words` into the cold part,
which follows the resident part on disc. When such a slot starts, the engine reads whole sectors (blocking outside the world, through the file queue inside it) into
`COLD_ANIM_BUFFER` (8192 bytes). The read covers `offset % 2048 + length` rounded up to sectors, so a 7880-byte clip that
starts 1376 bytes into a sector needs 10 240 bytes and does not load (`loadColdAnimation` returns NULL and the partner
stays in its previous clip). `coldsplit.split` refuses a stream larger than the buffer and starts a large stream on a
sector boundary when needed; an animation that a resident slot also uses stays resident. `tools/motionstorage.py`
checks both limits (`audit`, `require`; `audit_archive` for every partner record of a `DIGI.DAT`; `linker_limits`
reads the two capacities from a build's linker map).

**Field transitions (patches 0217, 0240).** Imported species (type ≥ 180), partners and NPCs, ease between ordinary
field poses over four logic ticks: slots 0, 1 (0240), 2, 3, 4, 5 and 18. Only the matrices used for drawing are
blended (quaternion, shortest path) inside `renderDigimon` and restored afterwards: the animation program, its events
and navigation are untouched. An interrupted transition starts from the last displayed pose; zero or collapsed scales
follow the destination; the support height is the blended mesh's lowest transformed vertex, so a blend does
not sink into the ground. Storage is allocated only while a transition runs (released on completion, map change and
entity removal, checked against the entity and model), and an allocation failure falls back to plain drawing. Original
Digimon and every other slot keep their timing. It is not a terrain contact solver.

**NPC models** keep only the slots NPCs can play (`tools/npcanims.py`: 0-4, 0x13, 0x1C-0x20 and 0x21 up for every type,
plus what each script plays); partner and tamer models are never trimmed.

**Not in the patch series.** Some field recipes below were reviewed together with an experimental runtime layer that
plays a species' native slot 0x21 performance, or an independently clocked tail or antenna, over its field slots. That
layer is not part of `mods/patches/`. The data the recipes write is complete without it, but on the published engine
those appendages play what the model's own field clips hold; the flyers whose stored field clips are root controllers
(Aquilamon 188, Lillymon 209, LadyDevimon 223, DemiDevimon 236, MarineAngemon 248, Quetzalmon 249, Tylomon 254) are the
species most affected. `fieldfairy.py` is the concrete case: it edits Lillymon's slot 0x21 because that layer draws
0x21 in the field; on the published engine the edit shows only in her battle idle.

## How an import gets its animations

### 1. The importer's baseline

`mmdport.build_partner` (driven by `import_batch.py` or a hand-written spec; [../mods/models.md](../mods/models.md)
§§ 10-12) builds every slot of a new partner in two layers:

- **Everyday slots retargeted from a DW1 donor** of similar build (`tools/retarget.py`; the donor chosen by skeleton
  similarity). For every tick each mapped source bone S gives its world-space delta from the source's reference pose
  (slot 0, first tick): `D(S, t) = Wsrc(S, t) · Wsrc_ref(S)^T`; the target bone T is posed so that its world rotation is
  `D · Wtgt_rest(T)`, with parents posed first. `T=S@w` scales the delta's angle (damping a whip-like source),
  `T=S1:S2` carries the chord from joint S1 to joint S2 (several vine pieces onto one arm, no twist about the chord),
  `--hips T=S*k` carries a translation (hops, squats), `--root-scale` scales root motion. Sounds come from the source
  clip (bank 4 becomes the new species' voice); texture moves do not. Unmapped bones keep their rest rotation, or get
  the source game's own idle motion layered over the looping everyday slots, retimed to a whole number of cycles per
  loop.
- **Battle slots from the source game's own animations**, cut to ranges, retimed to the donor slot's length
  (technique effects are timed to it), lunges removed, a few ticks of blend back to the first pose.

The baseline's limits: joint angles do not transfer between legs of different proportions (a knee bend that suits the
donor lifts a long rigid leg far off the ground and the foot skates); a donor without moving arms leaves the import's
arms still; bones the map leaves out (tails, extra wings) only play the source idle; and the donor's gait character
(a dinosaur's for a humanoid) stays.

### 2. Walk polish by feet

| Tool | Does |
|---|---|
| `tools/legik.py MODEL OUT TYPE DONOR DONORTYPE --legs HIP,KNEE,ANKLE:DHIP,DANKLE ...` | solves each two-bone leg so the ankle follows the donor's ankle: target = the model's rest ankle plus *k* times the donor ankle's displacement from rest relative to its hip; the hip is where the model's own animation put it; the knee stays on its rest side |
| `tools/footfix.py check / plant` | measures the largest angle between each foot's world orientation and the idle's (and a toe pointing backwards, > 90°); `plant` rewrites the foot keys so the foot's world orientation is the idle's, keeping the shin and body motion |
| `tools/walkpolish.py one ID / all / videos` | for every import: finds legs by geometry (the lowest mirrored bone pairs; hip, knee, ankle = the foot bone and its two ancestors), pairs them with the donor's, solves walk and run slots by the donor's ankle path at three stride scales, plants the feet, and keeps the result only if the stance slip falls by 15 % or more and the file still fits; writes to its own output folder, never to `content/` |
| `tools/armswing.py` | arms that swing with the opposite leg (amplitude × how far that foot is from its mean fore-aft position; the elbow flexes on the forward swing); run after `legik`/`footfix` |
| `tools/armmatch.py` | arm segments point where the donor's arm segments point (directions joint to joint, no twist), so a donor's raised arms stay raised on a different rest posture |
| `tools/armmirror.py` | an arm the donor cannot drive copies the other arm, mirrored in x |
| `tools/armgesture.py` | eating clip: the wrist goes to the mouth and back at each bite (the peaks of the head's pitch), by a two-bone shoulder/elbow solve |
| `tools/followthrough.py` | limbs and tails rigid with their parent trail behind it: `W(t) = slerp(W(t−1), rigid(t), α)` per bone, deeper bones trailing more, run twice over a looping clip so it closes |

Feet that do not pair (flying, swimming, many legs, hands counted as feet), legs of two pieces hanging from one bone and
models with no legs are left as imported.

### Imported equipment and hit reactions

`tools/models/field_animations/imported_equipment.py` is a post-delta recipe
selected by the imports provider. `content/models/imports/animation-repairs.json`
pins its effective source, skeleton size, hidden bones and changed slots. It
restores the native hidden-part scales in donor clips that have no scale header:
Kotemon's two spare swords, Taomon's brush, Roachmon's alternate hand and
MegaGargomon's missile panels. Explicit native scale tracks remain intact,
including Roachmon's native hand swap. Kotemon first receives its existing
walking articulation; its two native hit clips then recoil within three ticks
and recover, keeping their 20-tick duration and root programs.

These are generated overlays, so the frozen import specs and model deltas stay
unchanged. A clean build applies the existing delta, this pinned recipe, then
checks the final species pins. Changing this recipe requires updating those
pins; editing only an extracted model does not affect a clean build.

Audit all imports after rebuilding:

```sh
python3 tools/models/audit_animations.py --models build/dev-everything/imported-models \
  --overlays build/dev-everything/imported-species-models --out build/animation-audit.json
```

The audit reports missing, zero-duration and static hit reactions, plus every
bone that is hidden only in some slots. Visibility findings need visual review:
mesh-free helpers and native part swaps are legitimate. Hit recovery also needs
runtime evidence: the battle engine considers the animation's running flag and
the incoming technique's iframe timer (`BTL_tickHitState`,
`BTL_tickFighterAction`); duration alone does not prove shortened hit-stun.

### MetalGreymon Vaccine: donor provenance

The imports provider builds species 224 from the player's
`extracted/CHDAT/MMD0/MTGR.MMD` and `CHDAT/ALLTIM.TIM` entry 12, using
`tools/models/metalgreymon.py`. Extraction precedes imports; derive records
reads from `extracted/`. Both native inputs are SHA-256 checked. No disc
model, texture or animation bytes are committed. The registry's `builder`
selects this generator instead of replaying the DCB model delta.

The model has the native 30-bone skeleton, unscaled vertices, radius 280 and
height 430. Field slots 0–4 and all care, condition, training and battle movement
programs are native, with no pose edits, retiming or event changes. The
condition bubble, effect type 12, voices 12/10 and item distance match
species 12. Offense training selects 0x38 (the unchanged native Megaton Punch
program from 0x31), with native hit tick 10; this avoids 224's All Range Beam
assignment at 0x31. Etemon effect remaps and the generated field
and care passes are removed. Species 189 and 201 retain their stride rules.
Patch 0298 keeps the general condition-walk restart guard after removing 0290.

The gold palette is applied to rows 0, 1, 2 and 4; wings in row 3 stay native.
Rows 5, 6 and 7 hold cream claws, brown/gold horn and gold stripes with the
darkest purple retained. Polygon selections and colours match the approved
prototype exactly. The TIM retains all 16 CLUT rows and its original pixels.
The partner upload uses the TIM's CLUT height; verify these rows in live VRAM
as well as the displayed model.

224 keeps its 14 techniques in their existing order, so saves retain their
equipped animation-slot meanings and finisher at 0x3B. Matching techniques
select their own native clips. Four moves without distinct native clips use:

| 224 technique | Native clip |
|---|---|
| Prominence Beam | Heat Laser (0x2E) |
| Magma Bomb | Meltdown (0x30) |
| Counter | Megaton Punch (0x31) |
| Dynamite Kick (44) | Buster Dive (0x32) |

The slot table reads from a snapshot to avoid alias cycles. Each selected
program, including Giga Scissor Claw from native 0x3C, remains byte-identical
to its native source. Slots 0–4 are also compared frame by frame in
`tools/test_native_metalgreymon.py`. The recoloured model is 89,824 bytes,
with 78,480 resident bytes and 11,352 cold bytes. The largest aligned cold
read is 4,096 bytes; the fixed 100,352-byte partner buffer is unchanged.

### 3. The production models and their field recipes

The build's species provider `imports` (`content/models/imports/`: `models.json` and `species.py`) rebuilds the 175 imported
models from player discs and plain deltas ([../building.md](../building.md)), with their
reviewed animations. `models.json` maps each species id to its model, an optional texture, `aliases_applied` (the
species file's `slot_aliases` are already inside the model, so the build drops them) and an optional `field_overlay`. A native `builder` instead generates its model/texture pair during imports.

A **field overlay** is a reviewed recipe that rewrites the field slots of one species, run by derive's `overlays` step
(one unit per species, [../derive.md](../derive.md)). Its contract:

- the generator module (`tools/field*.py`, `tools/models/field_animations/war_greymon.py`, `tools/models/field_animations/monmon.py`) exposes
  `build(model bytes, skeleton) -> (bytes, report)`;
- it pins the SHA-256 of the exact source model it was reviewed on and refuses any other input, and pins its skeleton's
  bone count, so a recipe is never applied to an unreviewed or already modified model;
- it changes only the slots it names (normally 0-4; `fieldfairy.py` is the exception: it edits slot 0x21 only) and proves it: the mesh, the skeleton and every other animation
  program, including the native battle idle 0x21, care and battle clips, compare exact after a re-parse
  (`motiondiscidentity.changed_programs`);
- it re-plays its output with the engine's interpreter for several cycles and asserts its own invariants (root travel
  per loop, untouched channels, events, loop closure, foot error);
- it checks the storage budgets (`motionstorage.audit`), shares byte-identical streams (`share_identical_streams`) and
  drops unconsumed stream tails to fit;
- the report (`-report.json`) records source and output hashes, changed slots and channels and the checks; a
  generated skeleton, when the recipe adds helper bones, replaces the species file's.

| Generator | Species | What it does |
|---|---|---|
| `fieldacting.py` | Veemon 180, Magnamon 197, Veedramon 203, Renamon 354, Beelzemon 403, BlackWarGreymon 404, Bastemon 432, ExVeemon 194, Flamedramon 195, Omnimon 461 | per-species biped profiles (an explicit bone map: carrier, pelvis, chest, head, legs, arms, capes, wings): support-foot paths synchronized with root travel, weight shift towards the supporting leg, torso counter-rotation, delayed arms; native head, wing, tail and equipment acting kept; idle kept |
| `fieldarticulation.py` | Puppetmon 181, Kotemon 351 | upper-body acting over the original root and leg programs (wrists counter the swing so a weapon keeps its orientation) |
| `fieldsecondary.py` | Stingmon 187, Angewomon 190, Paildramon 199 | small delayed secondary motion (arms, feathers, tail tips) with root and leg channels exact |
| `fieldweight.py` | Ankylomon 189, Lighdramon 201 | step-synchronized body roll, yaw and pitch around the existing paw paths |
| `fieldglide.py` | MetalSeadramon 211, Magnadramon 215, Gesomon 240, MarineAngemon 248, Solarmon 251 | replaces only the root's forward momentum with one steady key per loop (same net travel), removing forward bursts; every pose channel exact |
| `tortomon.py` | Tortomon 261 | walk, condition walk and trot authored with `quadruped.py` from the shell bone: a lateral-sequence walk (16 ticks, 12 units/tick), a lower slower condition walk (22 ticks, 9) with a hung head, a trot (10 ticks, 36); each foot is planted flat and still for about a quarter of the cycle (duty 0.28, 0.26, 0.17; sole slide 0-4 units) while the shin turns over the ankle, then peels off heel first and swings in an arc (`arc`, `fold_soft`, per-leg `leg_reach`); no tick reaches the IK's stretch or fold limit and no joint jumps between ticks; cuffs up to 30 units under the floor and slip up to 30 % are allowed (profile `floor`, `stance_slip`), because the legs reach only about 70 units of ankle travel; slot 36 shares the run |
| `extyrannomon_arms.py` | ExTyrannomon 266 | arms only (bones 7, 8) of the walk, condition walk and run: a spring on the opposite-phase pitch of the same-side leg (swing 21, 11 and 36 degrees, a tick or two late), footfall kicks, sway abduction, disc roll; body, legs, tail, events and idle untouched; arm-versus-body and arm-versus-leg vertex counts never above the original; slot 36 shares the run |
| `mammothmon_gait.py` | Mammothmon 267 | walk, condition walk and run re-authored with `quadruped.py` so the hind (and front) feet plant: walk 20 ticks at 15 units/tick, condition walk 24 at 11, trot 10 at 36, the hind reach (about 150 units planted) setting the short cycles; trunk, ears and jaw follow on lagged closed loops; the idle is kept. Test: `tools/test_mammothmon_gait.py` |
| `kiwimon_gait.py` | Kiwimon 282 | offline model delta: walk (14 ticks, 17 units/tick), tired walk (18, 12) and run (10, 38) rewritten with `quadruped.py` on its own two legs (thigh, shin, ankle pad as the planted paw, the toes riding on it): each foot stands flat and still for half the walk (duty 0.52, 0.62 tired, 0.34 run; sole slide under 1 % of the travel) and swings with 18-48 units of clearance, the knees pointing out and back so the thighs stay out of the rump; the body crouches a little, bobs twice a cycle, shifts, rolls and yaws over the loaded foot and leans into the run; the head holds still in the world and snaps forward every step (`saw`), pecks once a cycle in the walk, swings low in the tired walk with a panting jaw, thrusts in the run; the rump trails late and rocks with the breath; the toes lift in the swing. The idle (slots 0 and 33, 60 ticks) is rewritten too: both soles planted, slow breathing, a weight shift, the head looking about and one peck; slot 36 shares the run, every other slot is kept. Test: `tools/test_kiwimon_gait.py` |
| `woodmon.py` | Woodmon 272 | walk (12 ticks, 15 units/tick), tired walk (16, 11) and trot (10, 38) from the imported rest pose: four root legs with `quadruped.py` (planted flat, slip under 1 %) and a trunk written by the profile's `body` hook: it bobs, rolls, shifts its weight sideways, yaws, leans into the run and slouches when tired, the log arms swing against the legs with the forearm late, the chest claws trail; the idle (slots 0 and 33) is a calm 40-tick loop: slow breathing, arms and claws swaying 11-20 degrees with lag, legs planted; slots 35 and 36 share the walk and run |
| `grizzlymon_gait.py` | Grizzlymon 296 | idle (96 ticks, slots 0, 1 and 18), walk (24 ticks, 15 units/tick), tired walk (28, 11) and run (15, 38) with `quadruped.py` (new `flat_shin` key for the hind shin plates, speed 0 for the idle): a menacing bear's plantigrade lateral-sequence walk (hind foot, then the same-side fore foot; paws planted flat, slip about 10 %), the body rolling and shifting its weight over the loaded paw with shoulders and hips turning against each other, a hump over the planted fore paw, a body drop on every fore landing and the head pushed out low ahead of the shoulders, lunging with each step and sweeping slowly from side to side with the jaw a little open; the tired walk is a heavy, dragging stalk with the same low head; the run is a low rotary charge with the head thrust forward; the idle breathes heavily with the shoulders rising, sweeps the head wide and slowly lowers it, growls (jaw pulses and chest swell) and lifts and sets down a fore paw. Test: `tools/test_grizzlymon_gait.py` |
| `tapirmon.py` | Tapirmon 287 | idle (64 ticks, slots 0 and 33), walk (27 ticks = 3 strides of 9, 16 units/tick), tired walk (39 = 3 x 13, 10) and a light gallop (one 14-tick cycle, 38; hind pair pushes together, a flight phase, front pair lands together, spine flexing), each with a layered breath written leg by leg because the rig has two-bone legs with a rear foot plate and no tail or paw bones (`quadruped.py` does not fit): planted flat soles, swing paths that match the stance speed, a per-tick body-height solver that keeps every leg within reach, hind plates counter-rotated flat; the body, rear block, head, snout and ears follow lagged closed loops; the tired walk keeps the head low and facing forward; the idle takes one slow breath, looks aside, sniffs, twitches an ear and flicks the tail; slots 1 and 34-36 are untouched |
| `gryphonmon_gait.py` | Gryphonmon 293 | idle (96 ticks), walk (22 ticks, 16 units/tick), tired walk (28, 11) and a gallop (16, 38) made with `quadruped.py` on the rig's four legs (hocks and elbows fold backwards, the long flat paws are planted by their sole point): walk and tired walk are four-beat, the run is a gallop with a flight; the neck is arched and the paws lift high in the walk, the wings beat once a stride (quick downstroke, slower upstroke, the fan trailing the arm), wider in the run and low and slow when tired; the idle breathes, stretches the wings, scans with the beak, settles, flicks the tail and blinks; the celebration (slot 42) overlay now starts from this model; slots 1, 33, 35 and 36 are untouched |
| `cyclonemon_gait.py` | Cyclonemon 281 | idle, walk, condition walk and run authored with `quadruped.py` (opt-in `scale`, `paw_rest`, `body` keys for the 1.3-scaled body): the left arm is a planted crutch and both hind feet plant; idle 48 ticks, walk 18 at 15 units/tick, condition walk 26 at 11 (lower), run 12 at 38 (forward lean); feet slip under 4 %; the shoulder pad keeps its place on the torso. Test: `tools/test_cyclonemon_gait.py` |
| `crabmon_scuttle.py` | Crabmon 284 | offline model delta: six legs solved with damped least squares so each tip stands still in its stance (soles on the floor), the shell rides above them; idle 84 ticks (shared with slots 1 and 18), walk 22 at 15 units/tick (tetrapod pairs), condition walk 28 at 10 (a wave, low shell, drooping claws), run 14 at 38 (tripods with a flight phase); feet slip about 1 %; claws swing, snap and pull in |
| `dokugumon_gait.py` | Dokugumon 298 | offline model delta: six three-bone legs solved with damped least squares so each tip stands still in its stance (soles on the floor), the body raised and the feet wide; two alternating groups of three; idle 72 ticks (shared with slot 33), walk 20 at 18 units/tick, condition walk 32 at 12 (stalking, low body), run 16 at 40 (flight phase); the abdomen swings against the body, fangs and palps move softly; stance slip under 2 % |
| `arukenimon_gait.py` | Arukenimon 311 | offline model delta: six two-bone legs solved with damped least squares so each tip stands still in its stance, the body raised and the feet wide; two alternating groups of three; idle 96 ticks (shared with slot 33, breathing, glances, a lifting arm and a paw), walk 24 at 24 units/tick, condition walk 36 at 13 (one leg at a time, low hunched body), run 16 at 44 (flight phase); the torso turns against the pelvis, the head stays level and lags, the sleeves are delayed pendulums; the torso turns 15-26 degrees, pitches 10-18 and rolls 11-17 over a loop; stance slip 1 % (walk), 2 % (condition walk), 0.4 % (run) |
| `deramon_gait.py` | Deramon 286 | idle (120 ticks, shared by slot 33), walk (16 ticks, 16 units/tick), tired walk (20, 10) and run (10, 38) for an 8-bone rig whose shell (bone 1) parents every other bone: each pose is written in the world and turned into local values, so the feet are placed (flat and still in stance, slip under 10 %, lift 16-38 units, ankle height set by the lowest sole point), the body, head and wings move as one group about a floor point (roll over the loaded foot, yaw, lean, bob, sway), and the shell takes the same motion through a damped spring per harmonic: it lags, rocks and bounces, and is kept off the floor; the idle keeps the original blink; slots 35 and 36 play other programs and are untouched. Test: `tools/test_deramon_gait.py` |
| `ebidramon_swim.py` | Ebidramon 305 | offline model delta: the shrimp dragon has no limb that reaches the floor but its tail fan, so every clip is a hover (the fan skims the floor at its lowest, never through it): idle 96 ticks (breathing, claw and pincer gestures; slots 1, 18 and 33 follow it), walk 48 at 22 units/tick, tired walk 64 at 14 (low, nose down), run 32 at 40 (pitched forward, big bounce; slot 36 follows it); the abdomen flexes as a wave with the fan last, swimmerets row front to back, arms swing as delayed pendulums, antennae trail. Test: `tools/test_ebidramon_swim.py` |
| `shakkoumon.py` | Shakkoumon 214 | idle, walk, condition walk and run authored from the rest pose: breathing and weight shift; a waddle (14 ticks, 20 units/tick) rolling over the standing foot, pelvis against chest, arms and head late, soles carried back at the ground speed (slip 26 %); a slower drooping condition walk (20 ticks, 12); a leaning run (12 ticks, 42) with a short flight; pelvis height set per tick on the lowest sole |
| `fieldphantom.py`, `fielddolphin.py`, `fieldzudo.py` | Phantomon 229, Dolphmon 238, Zudomon 219 | restore the native performance clock that the retargeted field clips had squeezed |
| `fieldpiedmon.py`, `fieldfairy.py` | Piedmon 245, Lillymon 209 | keep the native float: Piedmon (since replaced by `piedmon_levitate.py`, four distinct levitating clips); Lillymon's shoulders opened in slot 0x21, the performance the experimental runtime layer (above) shows in the field |
| `fieldnative.py`, `fieldseraph.py`, `fieldangel.py`, `fieldvenom.py`, `fieldaero.py`, `fielddevi.py`, `fieldrose.py`, `fieldsylph.py`, `fieldvike.py`, `fieldtuskmon.py`, `fieldshadramon.py`, `fieldshuri.py` | MegaKabuterimon 205, Seraphimon 207, MagnaAngemon 206, VenomMyotismon 212, AeroVeedramon 213, Devidramon 216, Rosemon 230, Silphymon 226, Vikemon 220, Tuskmon 253, Shadramon 250, Shurimon 225 | planted strides solved on the native legs (exact link lengths, the whole boot or claw mesh as support) under the native upper-body performance; Silphymon's walks also carry the upper body (pelvis bob, lean, torso counter-turn, arms against the legs) with strides as long as its boots |
| `fieldboxer.py`, `fieldstar.py`, `fieldsuperstar.py`, `fieldroll.py`, `fieldkoku.py` | BomberNanimon 232, Starmon 243, SuperStarmon 244, Togemon 208, Kokuwamon 247 | short one-link legs with rigid oversized boots that roll over their support vertices; body height follows the planted boot |
| `star_gait_refine.py` | Starmon 243 (SuperStarmon 244 by a rig dict) | offline model delta over the walk/run: ankles pushed out sideways so the boots clear each other, run pelvis pitch cut from 71-79 to about 36 degrees, ribbons hung down and back with a damped periodic pendulum lag; speeds and planting kept |
| `valkyrimon_limbs.py` | Valkyrimon 255 | offline model delta over the Angemon-transfer clips: limbs cleared of the body (elbow and hips turned a few degrees where the point-inside-mesh test fails), a calmer carriage (less bob and knee lift, relaxed delayed arms), legs kept apart, the left thigh's cloth hung from the pelvis, a breathing idle; timing, root travel and sounds unchanged |

| `saberleomon_gait.py` | SaberLeomon 258 (after the field pace pass) | legs re-timed through IK (lateral-sequence walk, bounding gallop with a flight phase), spine flex and bounce from foot support, delayed head share and bob, closed-loop trailing tail carried up in the run, forelegs set back 25 units, head carried by a fitted per-tick lift/pitch table so no leg triangle crosses the mane or jaw; cycle lengths, root travel, mesh and other programs exact |

| `okuwamon_limbs.py` | Okuwamon 259 | offline model delta: the idle kept as it was (clean limbs, closed-loop wings), the tired rest/walk/tired walk/run written as a four-legged diagonal gait solved per leg (planted flat feet, short steps for the 250-unit feet), pincers carried forward, a side-to-side waddle of pelvis, chest and pincers; cycles 20/10/12/8, root speeds 15/10/36 |
| `raremon_drag.py` | Raremon 264 | offline model delta: walk, tired walk and run rewritten as a drag-crawl (the idle and its alias stay); each arm is solved by two-bone IK (shoulder and elbow, no clamping) to a flat hand planted in the world during the pull while the hump surges forward on a von Mises burst of speed and the other arm reaches; lower body and tail lie on the floor as lagging springs, head and jaw follow late; cycles 16/24/12 (walk/tired walk/run), root speeds 15/10/35 |
| `skullmammothmon_clash.py` | SkullMammothmon 268 | offline model delta: walk, tired walk and run (slots 2, 3, 4, 36; 35 shares slot 2) with a per-tick neck pitch/lift and small shoulder/knee/ankle turns of the front legs so no front-leg triangle crosses the head, trunk or tusks; every other bone, timing and program unchanged, idle untouched |
| `octomon_scuttle.py` | Octomon 278 | offline model delta: idle (64 ticks, shared with slots 1, 18, 33), walk (16 ticks, 15 u/tick), tired walk (20, 10) and run (10, 35) as a tripod crawl of the six tentacles with planted tips (IK), a bobbing and swaying body and delayed arms; checked by `tools.test_octomon_scuttle` |
| `syakomon_hop.py` | Syakomon 283 | offline model delta: idle (96 ticks, shared with slots 1, 18, 33; breathing, mouth, fin), walk (28 ticks, 16 u/tick, planted hops), tired walk (36, 11, low dragging hops) and run (27, 38, bounds) of a legless clam: shell lowest point solved onto the floor, mouth and fin driven by damped springs; checked by `tools.test_syakomon_hop` |
| `superstar_gait.py` | SuperStarmon 244 | offline model delta: Starmon's refined walk, tired walk and run on the larger body (translations times 1.75, cycles 22, 28 and 25 ticks for 19.5, 13.5 and 37.9 units a tick), idle with the arms hanging |
| `fieldgatomon.py`, `fieldcat222.py`, `fieldpup.py`, `fieldgizmo.py`, `fieldape.py`, `fieldscarab.py`, `fieldpaddle.py`, `fieldwalrus.py`, `fielddiaboromon.py` | Gatomon 234, BlackGatomon 222, Gizamon 239, Apemon 227, GranKuwagamon 210, Gomamon 217, Ikkakumon 218, Diaboromon 237 | quadruped and crouched gaits: one-segment limbs pinned through the body carrier instead of stretched, paired bounds, knuckle walks, flipper strokes |
| `fieldinfermon.py`, `fieldslug.py`, `fieldcandle.py` | Infermon 246, ShellNumemon 231, Candlemon 235 | six legs in alternating tripods; a slug's propulsion clock separate from its face acting (the body slides); a pedestal that hovered on a steady line, bobbing and swaying (Candlemon's clips are now baked hops, see below) |
| `black_king_numemon.py` | BlackKingNumemon 307 | overlay generator: the walk, tired walk and run (slots 2, 3, 4) keep every bone of the body and give the two front pads (bones 2/3 left, 4/5 right) a rowing stroke: the sole reaches forward, stays planted (it runs back in the body's frame at the clip's root speed, under 40% slip), pushes off with a short recoil, lifts and eases forward in a small arc; the pad yaw is solved per tick so the sole lands where it is aimed, and the right pad lags the left. The eyes are rubbery: each stalk joint follows the body's bob and roll through a chain of three damped springs (the left and right eye with their own stiffness and delay, the roll opposite on each: a see-saw) and the stalk stretches and thins with the bob; the eyes never close or flatten. Idle sways gently at a different rate for each eye, run swings widest, tired is slow with sagging brows and a lowered head, run has set brows. No joint turns more than 130 units (11 degrees) or scales more than 300 (7 percent) in a tick. The other slots and bones are byte for byte as before (`build(..., paddle=False, face=False)` makes the earlier clips); `tools/test_black_king_numemon_paddle.py` |
| `wargreymonfield.py` | WarGreymon 373 | an anatomical gait replacing the inherited dinosaur one: walk 16 ticks at 22 units/tick (support 0.56 of the cycle), condition walk 20 at 15 (0.64), run 10 at 52 (0.42); pelvis loads onto the support foot, arms oppose their own leg, two-bone IK with feet forward and slight toe-out, back plates clear of the legs; footstep sounds retimed to the new contacts |
| `monmonupperbody.py` | Monmon 352 | torso and pelvis sway and opposite shoulder swings derived from the native leg cadence (elbows lag 0.65 rad, wrists 1.1 rad); hip roots compensate so the legs keep their world poses |

Helpers shared by the recipes: `fieldchannelcodec.py` (re-encode selected channels and pack same-frame key blocks
exactly; callers verify decoded poses over several loops), `motioncyclelayer.py` (layer native bones of a long
performance over repeated short field cycles: field cadence and root travel repeat exactly, the native part is
resampled over a nearby whole number of cycles; each event is assigned to one of the two clips), `motionidle.py` (reuse a native idle
with its support surfaces grounded), `motionsecondary.py` (rolling and compound feet, pelvis fitting to both legs'
reach, three-segment legs, a damped tail response to body rotation and acceleration), `motionreference.py`
(reference-motion generation on the native rig).

## Methods that work

- **Solve by positions, not angles.** Legs follow foot targets (ankle paths, footprints) with two- or three-segment IK on
  the model's own link lengths; never stretch a link or merge joints. A bent-limb plane is transported with the body so
  the knee does not flip between solution branches.
- **Ground the mesh, not the joint.** The floor height of a foot is its lowest rotated mesh vertex; a boot made of two
  pieces (heel in the shin mesh, toe in its own bone) is solved as one compound support. Feet roll heel to toe around a
  real support vertex while the ankle moves to keep that vertex on its footprint.
- **Fit the pelvis to the legs.** The body height is chosen inside the intersection of both legs' reach (hips above
  their ankles), which avoids straight-knee and folded-knee singularities and the permanent crouch of a fixed height.
- **Keep the native performance.** The import's own idle, head, tail, wing and equipment motion is kept and layered on
  its own clock where the field cycle is shorter; the field recipe owns only the channels it needs (often the root, the
  legs and a carried arm).
- **Cadence and travel together.** Retiming a donor cycle changes speed; a recipe sets cycle length and root travel as a
  pair (see Speeds) and places footstep sounds at the new contacts, keeping their bank and note. Texture events are
  never retimed silently; a clip keeps its initial eye state and does not replay a blink on every short stride.
- **Read the anatomy, do not guess it.** `tools/motionlab.py audit` (and `animstudio.py bones`) lists the hierarchy,
  world joint positions and per-piece extents; geometry alone cannot tell a cape, hair or wing from a tail, or whether
  a creature walks, hops, glides or swims. A tail is mapped by chain length; a fan of parallel pieces keeps its native
  leaf orientations; a four-joint hind leg is not three joints plus a helper.

## Checks and the rules a motion must pass

| Check | Rule | Tool |
|---|---|---|
| Stance slip | planted gaits use the lowest-quarter height classifier and must stay within native slip: walk mean ≤73%, worst ≤189%; run mean ≤125%, worst ≤330%. Native walks (mean/worst): Agumon 73/143%, Ogremon 50/169%, Leomon 34/189%, Greymon 36/174%, Mojyamon 30/98%; measured native runs span 8–125% mean, worst up to 330%. Require nonempty stance samples; stationary idle uses units per tick | `animstudio.py metrics`, `motionsecondary.support_transfer_displacement` |
| Ground | planted gait mesh floor bound ≤+1.5 units at logic ticks and at the 60 fps thirds (alpha 1365 and 2730 of 4096) | the recipes' own checks, `motiontailspace.py` |
| Reach | every foot target reachable with native link lengths; encoded foot error within a few units | recipes (`validate_ik`) |
| Loop closure | three (or eight) repetitions compared sample by sample: joint translation, scale and physical rotation must not drift; entity travel and whole turns are allowed; one-shot clips are not closed | `motionloops.py`, `motionloopfix.py` |
| Deliberate rotation | a part that really turns continuously (a clock's winding key, rotors) is declared, bound to the mesh and rig hashes, and excluded from the drift check | `motionloopcontracts.py` |
| Self-intersection | non-coplanar triangle crossings between chosen mesh parts (hands against body and feet, the two feet, tail against legs, weapons against head), optionally restricted to material regions (a rigid tusk, not soft fur); every combination of independently clocked parts | `motionquality.py`, `motiontailspace.py` |
| Untouched data | mesh, skeleton and every slot the recipe does not own byte-identical; events and loop structure exact | `motiondiscidentity.py` |
| Storage | resident ≤ the partner buffer, every cold read within 8192 bytes after sector alignment | `motionstorage.py` |
| Speed | planted gait walk 15–31 and run 35–52 units per tick (native ranges; `pace.py` applies the floors, the species already over a ceiling stay as they are); condition walk slower than walk. Tamer walk/run are 20/50; verify actual following in game | recipe asserts |
| Angular speed | report physical joint rotation rates before/after. An envelope derived from the slow clip being replaced is not a rejection gate; retain existing recipe assertions unweakened | recipe asserts |

All existing reach, closure, event and storage assertions remain mandatory and unweakened.

Apemon retains 43/20/20-tick walk/condition/run programs, with 3/1/2 gait cycles,
0.62/0.7/0.32 duty for the hands (0.57/0.6/0.32 for the hind feet) and 20/14/35 units per tick (diagonal-sequence walk, one-stride tired shamble,
gallop with a flight phase). The hind feet follow a heel-strike, flat, heel-lift, toe-push-off schedule, a swing that lifts
early and lands toe-up, a knee that trails the foot, and their own per-side and per-stride length, height and timing.
The idle is a grounded 93-tick loop with a 2-unit hip range.
Mesh floor maxima stay below the ground in every clip.

Gatomon uses 15/10/35 units per tick, 6/8/2-tick gait periods and
0.375/0.5/0.25 duty within its existing 48-tick programs. Tick/thirds floor
maxima are −1.314/−2.337/−4.165 units.

Salamon (221) no longer has a field overlay: `salamon.py` writes its gaits with `quadruped.py` and they are stored in its
model delta. The earlier retarget from a larger wolf pulled the front paws onto the midline (9-11 units apart, 54 at rest),
which crossed them and read as a cat. Now every paw stays within 3 units of its rest side (front 49-53 apart, hind 47-53),
swings straight forward and back, and does not slide while planted: a lateral-sequence walk (9 ticks, 10 units per
tick), a tired walk (9 ticks, 8 units) and a diagonal trot (8 ticks, 28 units, a flight phase of about 2 ticks). The legs
are short, so a stride is bounded (about 90 units for the walk, 224 for the trot): a longer cycle needs a lower speed,
not faster legs. The body bounds gently: the pelvis moves 7 / 4 / 12 units peak to peak (walk / tired / run, much of it
the dip the short legs force), the chest pitches 5 / 4 / 9 degrees, the head 5 / 5 / 9, at most 4 / 2 / 7 units and
3 / 2 / 6 degrees per tick; a larger bob at these 8-9 tick cycles read as hyperactive. Ears follow late. The walk, tired walk and run play 3, 3 and 4 cycles in one clip so the
blink is not repeated every few ticks. The face blinks through texture moves (`salamon_face.py`, as Gomamon's): open, half-shut and
shut frames in rows 80 down, every clip starting and ending open-eyed; the idle keeps its motion and gains three blinks.
Only the texture rows 80 down and slots 0, 2, 3 and 4 change; the other slots carry no eye moves, so an eye caught half-shut when a clip is cut would stay so until the next one starts (the clips are short, and this was not tested in the game).

Candlemon (235) no longer hovers: `candlemon_hop.py` writes four clips stored in its model delta (the overlay
`candlemon.py` stays as the provenance of the earlier delta). It hops on its foot, which stays still while down and
moves only in the air; the root moves all the time (half the foot's travel, half a steady line). Walk 4 hops of 14
ticks, 20 units per tick, 52 high; condition walk 3 of 18, 13 units, 20 high; run 5 of 10, 38 units, 34 high; a
96-tick idle. The face acts through texture moves (`candlemon_face.py`): eyes open, half shut, shut (the source game's
own frames) and a mouth at rest, half shut, shut or wide (slid from the painted mouth). Each of the four clips sets its
face at tick 0; the other slots carry no face moves, so a face cut mid-change (or the condition walk's half-shut eyes,
the run's wide mouth) stays until slots 0, 2, 3 or 4 play again. Not tested in the game.

Floramon (273) has its own calm idle (a 9 s loop, about 60 % less visible motion than the native one, kept alive by a slow
breath, a drifting head and lagging petals and tendrils) and a bouncy skipping walk (`field_animations/floramon_gait.py`): a 26-tick loop of two hops of 13 ticks (the run's hops
are 10) at 16 units per tick, the pelvis rising about 34 units in flight (the run's 61) and crouching on landing, each foot
planted by IK for 5 ticks (slip 73 % to 13 %); the torso pitches with the hops and twists and sways against the hips, and
the head rocks side to side (about 27 degrees peak to peak, one side per skip) behind the trunk, and arms, flower, tendrils and tail lag behind. The run keeps its poses and root, the condition walk keeps its legs, arms and root and hangs its head about 25 degrees lower;
every field clip blinks with the native half and shut eye frames, once per 2.5-3 s in the idle (plus a double blink per loop).

Thundermon (252) has its own idle, walk, condition walk and run (`field_animations/thundermon_gait.py`, written offline and
shipped as the model delta). They run at 16 / 10 / 36 units per tick in 24 / 40 / 20 tick loops of two gait cycles (12 / 20 /
10 ticks each; the idle keeps its 97 ticks), with boots 76 units apart that plant and swing high. The ball rocks 14 / 16 / 7
degrees side to side, twists against the stride, bounces 12 / 13 / 14 units with a hard landing and a settle (the native
Agumon turns 9 to 18 degrees and bounces 20 to 36), and the arms and the bolt follow it late on damped springs with a second
harmonic so they do not read as one sine. Boot slip while supporting is at most 6 / 5 / 4 % of the root speed (mean); neither
boots nor arm parts enter the ball or each other at any tick. The eyes blink by texture moves (`thundermon_face.py`, the
frames in texels no face samples): the idle blinks twice in a row once a loop (ticks 30 and 38), the walk once at tick 9, the
tired walk slowly at 22 and the run at 12; each clip starts and ends with open eyes. Not tested in the game.

Garbagemon's (269) eyes blink and its grin opens by texture moves (`garbagemon_face.py`; frames in texels no face samples,
eight moves per change, the poses of every clip unchanged). The idle, shared by slots 0, 1, 18 and 33, is the old 19-tick
loop repeated seven times (133 ticks): a blink at tick 30, a double blink at 98 and 105, a yawn of 22 ticks at 52 and a
small gulp at 118. The walk blinks at 11 and chews open on the rise, shutting on the footfall; the tired walk blinks slowly
(five ticks) and yawns for 10 ticks after the footfall; the run snaps its jaws twice with a blink between. Every clip starts
and ends with open eyes and a shut mouth. Not tested in the game.

None of these certifies the look of a motion: each recipe was accepted on side-by-side reviews (source against
candidate, three views) and a game run. Diagnostics that count crossings must be normalised by the number of sampled
frames before cycles of different lengths are compared, and covering armour against the part it covers is an expected
overlap.

## Looking at animations outside the game

**`tools/animstudio.py`** renders models side by side as a video or a sheet. A model is `FILE.MMD:TYPE[:TEXTURE[:SLOT[:LABEL]]]`
(an import's own `.TIM`, or the disc's `ALLTIM` entry for an original). Panels `kind:view`: `mesh`, `parts` (each bone
its colour), `skel` (bones numbered; right side orange, left cyan, centre white, bones under 100 units from the ground
red), `xray`, `gait` (height of the two lowest bones and their position along the walking direction in the world: a
planted foot is a flat line, a sliding one a slope); views front, side, back, three-quarter, top. The ground has marks
every 100 units that move with the root, and the camera follows the root.

```bash
python3 tools/animstudio.py video out.mp4 DONOR.MMD:8 NEW.MMD:402:NEW.TIM --slot 2 --panels mesh:side,skel:side,gait
python3 tools/animstudio.py sheet out.png NEW.MMD:402:NEW.TIM --slot 2 --ticks 0 3 6 9
python3 tools/animstudio.py metrics NEW.MMD:402 --slot 2      # root speed, stance ticks, slip, foot lift per foot
python3 tools/animstudio.py bones NEW.MMD:402                 # parent, rest position, side, mesh part
```

**`tools/animsheet.py`** draws contact sheets: one row per slot, every frame with the same camera (fitted once to the
rest pose), root motion and facing applied, so hops, lunges and walk cycles read as they move (`mmd.py preview` refits
each pose). `--slots`, `--frames`, `--every K`, `--ticks`; `--list` prints each row's slot, length, loop sample and
root motion. Standard library only.

**`tools/motionlab.py`** is the anatomy audit and the procedural-gait library the recipes build on: `audit ID ...`
records the native hierarchy, world joint positions, per-piece bounds and the articulation seen in identified source
clips, and proposes mirrored branch pairs without naming them; `build RECIPE` generates requested field slots from an
authored gait recipe (stance and swing phases per leg, stride, duty, lift, optional performance tracks) and enforces the
reach, ground, loop, slip and storage checks above. Its recipe folder is not part of this repository, so `build` is a
library entry point here rather than a workflow.

Testing a motion in the emulator, and capturing the partner's slot from RAM while it plays, is
[../developing.md](../developing.md).

## Reading the models with other tools

`tools/mmd.py gltf` writes a glTF that a viewer shows the right way up (a root node turns the model 180° about X: the
PS1 is Y-down), with node transforms set to the pose of slot 0, one sample per engine tick (integer-exact, so every
pose of the game is in the file), loop points, sounds and texture moves in the animations' `extras`, and UVs normalised
by the texture's real size. A keyframe-only exporter is smaller but loses the shape between keys (above), and must
apply the finite-loop rule and the out-of-range normals ([imported-species.md](imported-species.md)) to agree with the
game.

### Footless native-range post-pass

`tools/models/field_animations/locomotion.py` applies a pinned travel-only
post-pass to ShellNumemon (slug slide), Solarmon (hover), Tylomon (swim), Syakomon
(clam glide) and Apocalymon (floating base). Its manifest is
`content/models/imports/locomotion.json`. The manifest pins the source model,
skeleton and, when present, the preceding reviewed recipe's output. Only root TZ
changes in the named field slots. Nine-cycle comparisons keep all poses, events,
loop durations and lateral/vertical root movement exact, so tick and interpolated
mesh-floor positions are unchanged. The final resident and cold reads must fit.
Syakomon's four clips were later replaced by the hop of `syakomon_hop.py`, written over this post-pass's output.

This post-pass deliberately covers footless locomotion. A general planted-gait
retime needs separate contact and thirds checks: resampling can cut across the
floor even when all original tick poses were supported, and re-encoding may
exceed a model's storage budget. Source pins and speed thresholds alone do not
prove a successful gait repair.

### Chibi proportions

`tools/models/field_animations/chibi.py`, with the manifest
`content/models/imports/chibi.json`, reshapes a reviewed imported partner to the
game's anatomy over whatever recipe it already has. A row holds the pins, the group of
every bone (head, hand, foot, thigh, shin, arm, wing, ...), the factors and the height
of the species. The pass bakes each bone's scale into its vertices and into its
children's offsets in every animation, then rescales uniformly to that height.

Every clip is then replayed through the interpreter and the carrier's height is
rewritten tick by tick. On a tick where the source stands on its legs, the legs land:
on the floor, or at the source's clearance if it really hovers or jumps. The lowest
vertex of the mesh is not the measure there, because a grown sleeve, a gun or a crest
would hold the body up with the feet in the air. On a tick where the source rests on
something else, such as lying down, the lowest vertex lands instead, and the two blend
over a few ticks. A row's `fit` shortens the limbs that would otherwise cross the floor
with the feet down. Root travel shrinks with the legs on the walk, condition walk and
run, down to the speed floors of the pace pass. The bone-tied fields of the species
record (`effect_origins`, `effect_origin_fallback`, `condition_bubble`) go through the
same bake and reach the record through the proof's `species_patch`.

The proof's `floors` gives, per slot, the feet of the ticks on the feet (source and
result) and the worst miss each way. The build refuses a row whose legs or resting
clip stay more than 4 units off their floor, whose part goes 8 units further under the
floor than the source's own clip, that leaves a loop open, changes anything but the
carrier's height while grounding, falls under a speed floor, misses the height by 1 %
or leaves the storage budget. To enable a species: add its row, bind an overlay to
this module in `content/models/imports/species.py` and `models.json`, and repin it.

Two optional row fields cover what the bake cannot know. `trim` corrects the uniform
rescale for the lift grounding gives the idle, for a source whose idle stands under or
over the floor (Creepymon's sinks 48 units): the height of the record stays. `rest_slots`
names clips that land on the lowest vertex throughout, because the shorter legs bring a
kneeling body, or a staff held to the ground, to the floor with the feet still on it.

44 of the 175 imported partners carry a row, including authoring profiles for models
already baked into constant-scale deltas. Stingmon 187, Angewomon 190, Rosemon 230
and Piedmon 245 use their proportions before chibi reshaping. Seraphimon 207,
Taomon 315 and Renamon 354 retain 30 % of the reshape; WarGreymon 373 and
BlackWarGreymon 404 retain 50 %. Each multiplier, including limb fit and trim,
uses `1 + strength * (full - 1)`; target height interpolates from the preceding
recipe's idle height. Celebration overlays remain after the proportions pass.
Piedmon and BlackWarGreymon are rebaked with constant bone scales, carrying
attachment offsets through the same proportions exactly once.

The other imports stay as they were: quadrupeds, whose
heads are already large and whose four legs the single rule does not cover; forms with no
humanoid legs (fish, serpents, blobs, plants, machines, insects); and bipeds already at
the game's proportions, or that would gain too little to be worth a resident byte.

Every batch keeps the chibi proportions of the species that carry a row, whatever it rebuilds: the clips, the rig,
the gait recipe. `content/models/imports/chibi-proportions.json` holds the approved ratios of each (head, head width,
feet, hands and legs against the height) and `tools/models/chibi_proportions.py check [ID ...]` measures the final
model against them, as `tools/test_chibi_proportions.py` does for all rows; `edit.py put` reminds of it. The pins are the
reference ratios, the species as approved before the animation batches; a deliberate change (another strength, a new rig)
is recorded with `accept ID "why"`, which keeps the reference and lists the accepted keys and the reason, so a drift nobody
decided stays visible. A species bound to a
native donor's rig (`native-bindings.json`) keeps its row by one more recipe field, `"chibi": {"row": "<id>"}` (optional
`"factors"` overrides): after the binding, the pace retime and the jaws, `chibi.reshape_bound` carries the row's groups
onto the donor's bones through the recipe's `map`, bakes the factors and the limb `fit`, grounds every clip again and
checks the floor, the speed floors and the buffer as for any row. The row's factors apply as they are; `factors`
overrides some (the leg shortening of a donor whose legs are short already).

### Field pace pass

`tools/models/field_animations/pace.py`, with the manifest
`content/models/imports/pace.json`, is the gait retime that note asks for. It covers
the 38 imported partners that stayed under walk 15 or run 35, and MetalGarurumon, whose gait was rewritten. A row's `after_generator` runs after it: Snimon's `snimon.py` lowers the blades and ties torso, head, tail, wings and arms to the steps. Twenty-three wrap their
existing recipe through `base_generator`; sixteen had none and only have this pass. Nefertimon's
`nefertimon.py` is one of them: it writes the walk, run and standing idle from the paws up (stance and
swing per leg, a rotary gallop and a lateral-sequence walk, two-bone solves in the idle's bend planes, the gauntlet
kept seated) and rewrites each clip where it is stored, so the battle aliases (0x1B, 0x21, 0x23, 0x24) play it too;
this pass then only derives its condition walk from that walk.

`quadruped.py` is the same method as a library for other four-legged rigs, driven by a species profile (the three
bones of each leg, the soles, where the paws stand, one row per clip with cadence, speed, touchdown phases, duty, lift
and body motion). Every target is a world point; the left legs' bend planes are the right legs' standing pose
mirrored in the world, so an import whose idle stands with one leg back does not twist the other. Footsteps keep the
species' own sound and land on touchdowns. MetalGarurumon (`metal_garurumon.py`, 191) walks in a lateral sequence
(18 ticks at 22 units per tick) and gallops (14 at 50). Its idle plants mirrored paws in the same neutral stance,
with chest expansion and delayed neck and tail motion over the imported acting.
`metal_garurumon_stop.py` adds eight resident braking programs: four entry phases
each for walk (6, 0x14, 0x1A, 0x1C) and run (0x1D-0x20). The field idle selector
chooses the nearest quarter-cycle, then returns to idle when that program ends.
Each closes the paws in two overlapping beats, brakes root travel over eight
ticks and settles by tick 12. The 88-unit walk stop and 200-unit run stop use the
same travel curve for the root and world-space sole targets. Footstep sounds
land with the paws. Collision checks continue during braking; renewed following
can interrupt it. Poor-condition walk/idle selection and other species retain
their existing behavior. The decoded programs check floor clearance at 60 fps,
settled sole drift and resident/cold storage after the pace overlay. Armadillomon
(`armadillomon.py`, 185) has legs of about 80 units under a shell whose rim stands on the floor, so its body cannot
drop to lengthen a stride: it walks in a quick lateral sequence (9 ticks at 18) and runs in a trot with a short
flight (8 ticks at 35).

Gallantmon's faint (0x2B) and shared recovery (0x2C/0x15) are authored by
`tools/models/repair_gallantmon_fall.py` and stored as a plain model delta. The knees give way before a backward
fall onto the shield side. Both boot anchors stay planted during compression. Impact remains at tick
30, followed by a small rebound and settle through tick 36. Head and arms follow
one to three ticks late; the shield rolls flat, and the plume trails the impact.
The cape's three panels lag behind the shoulder and fan beside the body.
Shoulder armour supports the landed pose; the cape cannot become its support.
`tools/models/gallantmon_contacts.py MODEL.MMD REPORT.json` checks that contact,
boot anchors, and nonadjacent cape/body surface crossings at 60 fps. Recovery rolls toward the knees, loads the shield
arm, reaches a low crouch at tick 17, then extends through ticks 22 and 27 to a
balanced stand at tick 30. The lance stays clear of the supporting pose.
The joining poses match; durations, sound events and unrelated programs stay exact.

The timing study uses native Andromon (36-tick faint, impact at 30, 30-tick
recovery) and MetalGreymon (20-tick faint/recovery, impact at 15). The quadruped
study uses Garurumon (18-tick idle, 16-tick walk, 14-tick run) and Monochromon
(47-tick idle, 24-tick walk, 20-tick run). Native field stopping normally finishes
a locomotion loop before selecting idle; the braking programs add deceleration
and closing steps for this rig. Culled front, side and three-quarter comparisons
and decoded contact measurements are reviewed together: numbers alone do not
certify the acting.
Both clips are checked against the floor at ticks and 60 fps interpolation points, and against the resident and
cold-animation storage limits.

The game's own species set the rule: slot 3 is the walk played 1.5 times slower at
2/3 of the speed, with gait cycles of 14-24 ticks for a walk and 12-20 for a run.
Each manifest row names, per slot, a source clip, a loop length and a speed. Cycle
counts come from the feet's dominant height harmonic. With the same source and
length, the poses stay exact and only the root travel changes. Otherwise the clip is
resampled at the engine's fixed alpha, with even travel and events moved in
proportion.

Resampling a foot arc less often cuts the chord through the ground, so the pass
raises the root's children by a smooth cyclic bump. It cannot use the root: root
translation is relative, so a loop-wide offset of it is lost in the encoded clip.

The build refuses a row that leaves its speed floor, exceeds the row's slip limit,
sinks the mesh past the source at ticks or thirds, drifts over nine loops, changes
another program or leaves the storage budget. Slip limits for walks are 125 % mean
and 250 % worst, the upper range measured on the 34 native partners sampled
(walk mean 22-125 %; the five species in the table above are the low end); hovering
and hopping species read 100 % by construction.

Blossomon's roots are written as a planted low-duty bound by `blossomon_gait.py` (diagonal groups, flight phase in the run,
slip under 25 % mean in stance, steps of 16, 20 and 11 ticks) and its trunk pitches, twists and lags the pelvis while the
vines, leaves and head follow with lag at a slower rate than the steps; its idle shares program 19 with
slots 1, 18 and 33.

Metrics do not certify the look: check the front view, because a body that bows
hides the face. Slot 3 of an import is often a tired walk with the head down, so a
walk's source is the species' own slot 2 wherever it passes. Shurimon and
Gizamon use slot 3 (the same carriage). Gomamon's idle, walk, condition walk and run are written
from scratch by `gomamon_scoot.py` (planted flipper steps, body roll and pitch, head, ear, mane and tail
follow-through) and stored in its model delta. Its face blinks and opens its mouth through texture moves
(`gomamon_face.py`): the closed-eye, half-shut and open-mouth frames sit in the texture's free rows 80 down and each clip
copies them over the painted sprites, starting every clip open-eyed and closed-mouthed. Mushroomon's slot 2 has almost no stride, so
its row takes only the legs from slot 3: `posture` plays every bone above the legs
from slot 2 and solves each hip to keep its world rotation. Its `loose` block adds acting
over the stride: arms oppose their legs, elbows arrive late, the torso turns against
the hips and rolls over the supporting foot. Tapirmon's slot 2 is a
bound with a one-tick stance, which the slip classifier cannot read, so its row
keeps the poses exact and carries a wider limit.

## WereGarurumon field motion

WereGarurumon (record 62) uses native Leomon's idle, ready, walk,
condition walk and run in slots 0–4. The old Garurumon-derived field gait
carried a quadruped's crouch and bounding leg motion onto the biped rig.
The replacement keeps Leomon's chest, shoulder, head and tail acting,
calibrates the relaxed reference pose, and solves the legs to follow its
foot paths with WereGarurumon's own limb lengths. Heel and toe roll remain;
a small eased clearance correction also checks the interpolated thirds
between logical ticks.

`tools/models/field_animations/weregarurumon.py` is the offline authoring
recipe. It requires the pinned pre-edit record-original model and native
`LEOM.MMD`; the normal build replays the plain model delta. Author a candidate
with `--source BEFORE.MMD --out AFTER.MMD --report REPORT.json`, then store it
with `tools/models/edit.py put 62 AFTER.MMD` and verify with
`tools/models/edit.py check 62 --species-pins` (provide source discs or
`--from` as described in the model tools README).

The mesh, texture, rig and consumed programs outside slots 0–4 are unchanged.
The record height is 709 units to cover the upright idle for culling and bubbles.
The status view is pulled back along its original camera ray so the upright
head and feet fit below the profile panel.
Forward travel matches Leomon: walk 22.5 and run 50 units per tick. Studio
stance slip is approximately 29–34% in walk and 8% in run, comparable to
Leomon; the previous walk measured 146–197%. These figures supplement visual
comparison in culled front, three-quarter and side views. The encoded model
has 100,084 authored bytes and 100,100 resident bytes after slot aliases,
without cold splitting, below the original 2 MB partner buffer's 100,352-byte
capacity.

### Partner recovery, dinosaur locomotion and large-model scale

Arukenimon's Megaton Punch, Counter, Dynamite Kick and Tremar shared a 96-tick
imported clip, including a long turned-away hold. Their timing recipes now end
at tick 36, map the attack cue from tick 27 to 11 and preserve both endpoint
poses. Other techniques retain their programs. `technique_timing.py` accepts an
explicit tick count so shortening recovery does not leave an invisible tail.

MetalTyrannomon uses Tyrannomon's native idle, walk, condition walk, run and
battle locomotion (slots 0, 2–4 and 33–36), anatomically retargeted with foot
contact. The native stride timing, root travel and step sounds are retained;
its battle voice and partner voice use Tyrannomon's entries. The mesh and attack
programs remain unchanged. The replay recipe and preceding delta are under
`content/models/authoring/native-polish/260.json` and
`content/modeldelta/authoring/260-before-native-polish.MMD.mdelta`. The final
resident model uses 99,406 of 100,352 bytes; each cold read fits 8,192 bytes.

PrinceMamemon uses Mamemon's native skeleton and every program of it (slots 0-59, plus
copies in 61 and 62), scaled 2.2 and bound by `native_binding.py`: the idle, walk, condition
walk and run are 17, 15, 19 and 15 ticks, and Mamemon's stride, root travel and sounds are
kept. The replay recipe is in `content/models/imports/native-bindings.json`.

Vilemon uses native Ogremon's skeleton (18 bones) and field programs at scale 0.72, bound by `native_binding.py`:
idle, walk, condition walk and run are Ogremon's own clips (17, 23, 25 and 21 frames at 17.6, 16.2 and 36.1 units per tick
for the gaits); the wings have no donor bone and ride the chest. The resident model uses 68,322 of 100,352 bytes.

HiAndromon uses native Andromon's skeleton (21 bones) and field programs at scale 1.2, bound by `native_binding.py`: its
25 bones map by body part onto Andromon's torso, shoulder pivots, arms, one hand and one foot per limb, and the chibi
proportions (head, arms, torso) are re-applied as piece scales, so the figure is about 14% shorter than before (497
against 582). Idle and walk are Andromon's own clips (21 frames each at 25.2 units per tick); the condition walk is Andromon's too
(23 frames, 19.6 per tick) with `pace`'s `smooth` (3 passes of a cyclic [1, 2, 1] filter over every rotation and the
root's travel per tick, since the donor keys every second tick and its root speed jumps from 30 to 5 and back); the run is retimed by the recipe's `pace` to 18 ticks at 40 (`close` makes the last pose the first,
since Andromon's run closes only within a unit or two). The 15 techniques play Andromon's clips of the same name
(Dynamite Kick plays Tremar) and the training slot 61 plays Megaton Punch. Andromon's left foot slides on its own
stance (about 29% mean in the walk), and the retimed run stays near 29% mean and 77% max. The resident model uses
86,492 of 100,352 bytes.

GrapLeomon uses native Leomon's skeleton (23 bones) and field programs at scale 0.98, bound by `native_binding.py`: idle, walk,
condition walk and run are Leomon's own 16-tick loops (22.0, 19.8 and 48.9 units per tick for the gaits, Leomon's own foot slip).
Its four striped drums (forearms and shins) are four bones of their own after the donor's (`spin` in the recipe: each is a
child of the donor's forearm or shin, its z axis along the drum), so the bound model has 27 bones. Their rz turns a steady
1, 3, 2 and 4 quarter turns per loop in the idle, walk, condition walk and run (5.6, 16.9, 11.3 and 22.5 degrees a tick; the
facets repeat every quarter turn, so every loop closes), written last into the first key of each loop; the left drums turn
the other way. The resident model uses 88,130 of 100,352 bytes.

Assaultmon uses native Centarumon's skeleton (27 bones, `CHDAT/MMD1/CENT.MMD`) at scale 1.45, bound by `native_binding.py`
(an experiment: its chibi row is applied as the last stage of the binding, `"chibi"` in the recipe). Both are four-legged, so the legs map one
to one (Assaultmon's four-bone front legs on Centarumon's three, its three-bone hind legs on the four, the spare donor bone
carries no mesh); the gun arms ride the arm bones, the guns the forearms, the two shoulder cannons the torso, and the tail the
tail bones. The recipe's `spread_fit` fits the pieces on the spread-shifted donor joints. Walk, tired walk and run are the donor's
walk and run retimed by `pace.retime` with `ground` (the checked soles stay on the floor) and then given the chibi row (shorter legs, so a
shorter stride): 20 ticks at 19.3, 30 at 12.9 and 21 at 36.6 units per tick; the tired walk is cut from the walk because the donor's own is faster. Stance slip is about 35 to 75 % mean
(the donor's own heel-toe roll slips as much), above the usual target, and the run's closing tick turns the chest through a
gimbal pose, as the donor's file does. The resident model uses 96,118 of 100,352 bytes.

ChaosLord uses Machinedramon's native skeleton (32 bones) and field programs, bound by `native_binding.py`
at scale 1. Native Machinedramon has no care clips, so the recipe's `donor_builder` takes the partner model
`content/models/partners/machinedramon.py` makes (its own idle, walk and run plus care clips) as the donor. The
walk and run are 21 and 19 ticks at 25 and 47.5 units per tick; the idle (37 ticks, and slot 33) and the run (and slot 36) are the
species' own clips retargeted in world space (pace's `original_run`: each bone's world rotation, limbs reaching the original's end joints); the condition walk (slot 3) is the walk
retimed by `pace.retime` (the recipe's `pace`) to 31 ticks at 16.7, so it stays slower than the walk. The thrusters
share the chest bone; the claw hand, second neck bone and cannon tips carry no mesh. The resident model uses 84,932
of 100,352 bytes.

Deltamon uses Tyrannomon's native skeleton (27 bones) and field programs at scale 1.2, bound by `native_binding.py`
(Greymon's were tried and scored worse). The tails are rigid on the pelvis; the tired walk (30 ticks at 16) and the run
(24 ticks at 50) are retimed by the recipe's `pace`, `native_arms.py` re-poses the two heavy arms in them, and
`native_jaws.py` opens the head jaw on the donor's jaw bone with a slow eased curve (one opening per loop, two in the run,
a held mouth when tired) and replays the source's own skull and metal head jaw turns on the donor's finger bones. The
resident model uses about 85,400 of 100,352 bytes.

KingEtemon uses Etemon's native skeleton (27 bones) and field programs at scale 1.2, bound by `native_binding.py`. The
torso is stretched and leaned onto the donor's chest so the head stays on it, the cape's four pieces ride the pelvis and
chest (Etemon has no cape bones), the head is pitched 30 degrees forward so it looks ahead, `native_hands.py` keeps the arms near the body (the donor's
diagonal swing leaned them up to 59 degrees outward; now at most 21) and sets the gloves on the forearms, and the soles are lowered 5 units onto the floor. The walk (16 ticks at 26), the tired
walk (20 ticks at 19) and the run (14 ticks at 50) are retimed by the recipe's `pace`, whose `lift` key holds a whole
clip higher or lower so the donor's crouch stands on the floor. Known limits: the stance slip is 100 mean for the walk,
230 for the tired walk and 100 for the run (the donor's own boxer steps slide against this root speed), and the swinging
foot lifts up to 21 above the floor in the tired walk. Body-part penetration is about half the previous model's. The
resident model uses about 89,600 of 100,352 bytes.

KingEtemon's hands. The source's gloves are not twins (a closed fist posed across the belly, an open hand hanging with
the wrist bent about 50 degrees) and, with no rule of their own, kept that pose inside Etemon's idle hand frame, which
sits 81-97 degrees off the forearm: one hand read as turned sideways (palm rolled 82-127 degrees in the walk), the other
folded far in (83 degrees at rest). Etemon's own hand turns also change per clip (walk 40 degrees about the forearm on
one side and none on the other, run 41-80 and swings up to 112), invisible on its round fist but not on a glove, and a
follow-through that rolled the hand about the forearm (Etemon's hand x runs along the limb) twisted the glove instead
of bending the wrist. Now each glove has an `aim` rule that lays it along its hand bone (8 degrees of droop toward the
palm, palm on the `palm` axis); in the gaits `hands` drops the donor's hand turns, turns the palm to the thigh, bends
the wrist about the line of the shoulders by the forearm's swing two ticks late, and `clear` leans the whole arm out
from the shoulder (then the wrist, for what is left) on the ticks a forearm or glove would enter a leg, foot, the cape
or the body, eased over the neighbouring ticks. Per tick in walk, tired walk and run: bend 8-34 degrees, palm roll
within 17, at most 15 a tick (the test allows 18); in those and in both idles no glove vertex inside a leg, foot, the
cape or the body and no forearm more than 2 (`tools/test_kingetemon_native.py`). The idles are gestures and keep part
of the donor's own turn of the hand (`keep`: the fist at the chest half, 41 degrees instead of 83; the hanging hand a
fifth, palm still about 45 degrees off the thigh; idle 33's raised hands half). Techniques keep the donor's hand turns
(up to 85 degrees off the forearm).

The foot mesh's sole plane, heel and toe define explicit forward-facing ground
contacts. Each stride lands on its heel, holds the sole flat in world space,
and rolls off its toe. Scaled two-bone IK and a cyclic pelvis-height envelope
keep those contacts reachable; the swing fits the shorter imported legs.
`sole_contacts.py` also fits the knee plane and ankle attachment through render
subframes. Bounded forearm and tail corrections keep the larger appendages
clear after grounding the pose. The native cadence, root channels, sound events, mesh, texture and
attack programs remain identical to the preceding locomotion transfer. Review
uses side/front foot close-ups and the animation studio's world-space gait
curves alongside native Tyrannomon.

Kimeramon's mesh and every animation translation are uniformly enlarged by
1.5, including field, battle and menu clips. Its collision radius/height are
263/600. Authored effect and condition-bubble attachment offsets grow with
the mesh; native effect lookup keys retain their original values. The decoded idle height is approximately 604 units, compared with 505
for native HerculesKabuterimon, 657 for Machinedramon and 678 for VenomMyotismon.
The status camera moves 1.5 times as far from the eye, retaining the complete
model inside the Condition panel. The model's size in bytes is unchanged; its
resident portion uses 87,652 bytes.

Tropical Jungle screen 13 (`TROP02`) retains an original-disc collision defect
on its southwest approach to screen 12: the grass boundary steps inward at rows
79 and 83. `maps/trop02-exit.py` opens 24 grass cells and extends exit 1 across
eight more cells, preserving the stump, plants, warps and original exit cells.
`tools.test_trop02_exit` checks a route with the tamer's 100-unit body box that
catches on the original and reaches the exit after the repair.

## Gesomon terrestrial field gait

The `gesomon-terrestrial` overlay changes only walk (2) and run (4) on the
pinned 29-bone import. Eight small tentacles alternate support groups, with
rear pairs delayed behind the front. Recoveries ease forward and lift clear;
mantle bob, sway and delayed long-arm motion follow the supports. Mesh, rig,
condition, care and battle clips remain unchanged; the idle and the tired walk
are described below. Native Kunemon
supplies the 18-tick cycle and contact timing; walk/run travel is 18/35 units
per tick.

The reviewed motion is locked by its exact output hash. Reconstruct species
240 with `tools/models/edit.py get 240`, then run
`PYTHONPATH=tools python3 -W ignore -m unittest tools.test_gesomon_gaits`.
The checks cover the reviewed bytes, decoded support contact, nine repeating
cycles, unchanged programs and original-console resident/cold storage. Final
provider model and texture hashes remain covered by `species-pins.json`.

RedOtamamon 233 (`tools/models/field_animations/redotamamon.py`, test
`tools.test_redotamamon_gait`) had one shared loop in all four field slots. The
generator authors four different ones on its own rig, with no donor motion
stored: a 96-tick idle (breathing, tail and body sway, head looks, claw twitch)
and a walk, a heavier condition walk and a run at 20, 13 and 38 units a tick.
The claws are solved with two-bone IK onto planted targets, and a floor pass
keeps every vertex above the rest ground plane. The eyes blink through
texture moves (`redotamamon_face.py`): the painted eye plate is copied into
three frames (open, lid half down, shut) in the free right side of the texture,
and each clip sets its first face at tick 0 and ends in it, so a clip cut
mid-blink is repaired by the next clip. The test reads the model
made by `tools/models/edit.py get 233` at the commit before the clips
(`REDOTAMAMON_MODEL`); the reviewed-source pin in `celebrations.json` follows
the new model.
Clockmon 290 (`tools/models/field_animations/clockmon_gait.py`, test
`tools.test_clockmon_gait`) had field clips whose root speeds (tired 23, run 71
units a tick) lay outside the native ranges, feet that slid at 50-140 % of the
travel and arms that changed from one clip to the next. The generator rebuilds
slots 0, 2, 3 and 4 from the world down, with no donor motion stored: the
chassis (bone 2) is placed per tick (height, sway, lean, roll, yaw) and the
rider (bone 1, its head, key and hammer arms) swings on after it; each foot is
a toe point that stays put in the world while the body passes over it; the
foot block rolls heel to push on a schedule, the hip piece turns towards it, and
the block may telescope a few units (`EXT`) because the legs are short and
straight at rest. Chassis yaw carries the stance hip back, which is what lets
the short legs cover the stride. The clips are a 90-tick idle and a walk, a
tired walk and a run of 12, 14 and 8 ticks at 15, 10 and 38 units a tick. The
test reads the model made by `tools/models/edit.py get 290` (`CLOCKMON_MODEL`);
the reviewed-source pin in `celebrations.json` follows the new model and the
overlay's celebration slots (11, 42) stay byte-identical.
Marsmon 297 (`tools/models/field_animations/marsmon_gait.py`, test `tools.test_marsmon_gait`) had a walk, tired
walk and run whose leg rotations came from another rig: the right foot crossed to the left side of the body (the
feet only 2-39 units apart, the right one at x = -47 to -17), the soles slid and the legs hung together. The
generator plants each foot with `quadruped.py` (two-bone IK on hip and knee, the heel flat, the boot keeping its
30 degree outward splay, a track of 43 units a side; the new gait option `world_ease` eases a swinging paw in the world, so it leaves and lands at rest) and writes the body by hand: the hips yaw and roll against the
shoulders, the upper body shifts over the loaded foot, the fists swing against the legs and open at the end of the swing, and the cape trails late, a link behind the last.
The character is a proud, heavy warlord: the walk is a swagger (chest out, chin up, a wider hip sway), the tired walk a slouch with the head down and the cape hanging, the run a lean-in with the cape streaming. The idle is redone as a 150-tick (5 s) loop on planted boots: the weight rolls from one to the other, a breath, a look aside with a head tilt, one fist raised to the chest and a flick of the cape.
The body bobs hard with each step (the pelvis falls on every landing and rises over the planted foot: 16, 18 and 21 units peak to peak in the walk, tired walk and run, two bobs a cycle; the clips before had 10, 10 and 13), the boots stay flat through the stride (a toe-up peel at lift-off had turned the trailing run foot backwards) and the run's world ease is a share (`world_ease` 0.85) so the trailing foot does not hang so far behind.
The walk, tired walk and run are 22, 26 and 14 ticks at 16, 11 and 38 units a tick (a long unhurried step like the native biped's, with the heel peeling at toe-off, a high knee lift and a leaning run). The test
reads the model made by `tools/models/edit.py get 297` (`MARSMON_MODEL`).
`field_animations/gesomon_rest.py` is written over that model and baked, with
the walk and run, into the plain delta (the species has no field overlay). The
import's idle hung the squid 9 to 89 units above the floor (mean 50, a
79-unit bob) and played again as the tired walk. The idle (slots 0, 1, 18)
keeps the import's 83 ticks and is lowered per tick so the lowest point of the
mesh is 0 to 3 units above the floor (bob 4); the long arms are rewritten (a
shoulder and two hinges solved for the claw) to hang forward and out and sway
with the breathing, and the arms of the walk and run to a loose counter-swing in step with
the gait; the claws' palms face in and down (on the floor in the tired walk). The tired walk (slot 3) is a 30-tick loop: mantle
and head 22 to 25 degrees down, pelvis 107 to 116 (idle 124 to 152), root
11 units a tick, the eight tentacles planted for 45 % of the cycle and dragged just
above the floor in between, the long arms stretched out limp behind the body, forearm and claw within a few units of the floor, palm down, dragged along, two footfall sounds per cycle. The loop is one
cycle because two do not fit the resident animation buffer (98870 of 100352
bytes used). `tools.test_gesomon_rest` checks the exact bytes, floor contact,
loop seam, droop, storage and the distance between the four gaits.


Divermon 304 (`tools/models/field_animations/divermon_gait.py`, test `tools.test_divermon_gait`) had a rigid body,
boots turned sideways, ears that flapped and a run that clamped. The import's rest pose turns the left ankle 77 degrees
outward, and its clips asked 230-480 unit steps of 123 unit legs: the soles slid (110-160 %), the knees (bones 19 and 23),
ears and tail were one constant value over the whole run (the "clamp": the legs only swung from the hip and the soles hung at the
end of their reach) and the pelvis fell 100 units in it. The generator plants each foot with `quadruped.py` (two-bone IK,
the sole flat, a 7 degree outward splay, `world_ease` and `arc` so a swinging foot leaves and lands at rest over the floor) and
writes the body by hand: the pelvis falls on every landing (18-20 units peak to peak, two bobs a cycle, a small extra dip as each
foot lands, one step heavier than the other), yaws and rolls against a chest that lags it, and the harpoon arm is held
level while it swings. The walk, tired walk and run play two strides over (32, 36 and 24 ticks at 18, 12 and 36 units a
tick; `cycles` 2 and the profile's `vary` hook of `quadruped.py`): the legs, pelvis and chest are the same in both, so the
feet stay planted, and the head, arms, ears, tank and tail each have their own slow swell of amplitude and drift of timing
over the whole loop (a spring per part, run over the loop), so no two strides are alike. Ears, tank and tail are damped springs
fed by the body's own bob with a 1-3 tick lag, low damping (they overshoot and settle) and a period of their own; the right
ear is slower and later than the left and the free arm swings further than the one that holds the harpoon. The idle is a
240-tick (8 s) loop: breathing, four slow weight shifts, five looks and head tilts, ear flicks and a tail swish at uneven times;
the tired walk is lower and leaning. Fewer, longer swings (duty 0.46 / 0.58 / 0.30) keep a leg's lift-off to 30-55 degrees
a tick in the walks and 70-80 in the run (the first version had 75-90). Slots 33, 35 and 36 follow their clips. The studio's
slide measure is 3 % mean and 20 % worst in the walk, 1 and 3 % in the tired walk and 0 and 1 % in the run. The test
reads the model made by `tools/models/edit.py get 304` (`DIVERMON_MODEL`).
Second pass: the face and some charm. The face is texture-only (`divermon_face.py`): texture moves paste frames (open, half, shut eye;
rest, shut, ajar, open, wide mouth) kept in unsampled texels over the painted eye and teeth, on every clip and its alias. Blinks last 3-5
ticks (a slow one when tired), the idle has four, a stride one. The pelvis gets a small hop at each footfall and the body a wobble; peak to
peak, walk / tired / run: pelvis height 19 -> 22 / 18 -> 20 / 20 -> 23, side sway 16 -> 24 / 16 -> 20 / 8 -> 16, hip roll 15 -> 22 / 16 -> 20
/ 18 -> 23, head roll 3.4 -> 7 / 2.7 -> 6.3 / 4.3 -> 4.8 degrees. The knee turns up to 4 times its median per-tick step in the walk (3 before):
the hop's price within the narrow pelvis-height window the legs can reach.
MarineAngemon 248 (`tools/models/field_animations/marine_angemon.py`, test
`tools.test_marineangemon_gait`) held every bone still in all four field slots
and only the root travelled, so the fairy slid along. The generator authors
four different loops on its own rig, with no donor motion stored: a 48-tick
idle hover and a walk, a drooping condition walk and a run at 18, 13 and 38
units a tick. In every clip the wings beat (two to four beats a loop, with a
slow swell so no two are alike), the arms swing against each other with the
wrist lagging the shoulder, the ear ribbons sway and trail with overshoot, and
the tail and body answer the beat. A constant lift per clip keeps the lowest
point of the mesh at a hover height. The encoder uses a per-bone tolerance to
stay inside the resident buffer. The eyes blink through texture moves
(`marine_angemon_face.py`): the painted eye plate is copied into three frames
(open, lid half down, shut) in texels no face samples, and each clip sets its
first face at tick 0 and ends in it. The test reads the model made by
`tools/models/edit.py get 248` or the commit before the clips
(`MARINEANGEMON_MODEL`).

### Quetzalmon (249): four flights
The import's idle, walk, condition walk and run (slots 0 and 1, 2, 3, 4) held one frozen pose: every bone's angle and
offset was constant in all four clips and only the root's travel differed (15.9, 13.6 and 38.1 units a tick), so the
winged serpent slid like a statue. `field_animations/quetzalmon_flight.py` (overlay `quetzalmon-flight`) writes the five
slots again on the reviewed 16-bone import; every other slot, the mesh and the rig are unchanged, and slot 1 shares the
idle. The motion is modelled on how the native flyers (Birdramon, Airdramon) move, not on a repeated sine: each wing beat
is a held top, a quick power downstroke and a slower recovery, the beats of a loop differ a little in length and depth, and
the left wing trails the right. The wings drive everything else through damped springs: the body rises through the
downstroke and peaks as it ends (a soft spring on the stroke), the coil of the neck, the tail and the crest then follow that
heave link after link, each later and looser than the one before, the head turns back against the neck so it stays level,
the body pitches nose-up with the rise and rolls with the wings' unevenness, and the neck sways from side to side. Each
spring runs for several loops and one loop is kept, so every clip repeats its pose exactly. One constant lift per loop sets
the lowest point of the mesh above the floor (the rest sat 15 units up). The wings flap from just above the horizontal down
to well below it, spread, never swept back.

| clip | ticks | beats | wings (degrees from the folded rest) | forward lean | body rise | root per tick |
| --- | --- | --- | --- | --- | --- | --- |
| idle (0, 1) | 54 | 2 | 44 to 82 | upright | 26 | 0 |
| walk (2) | 48 (the earlier 24-tick walk twice over) | 3 (one per 16 ticks) | 42 to 84 | 30 degrees, neck 20 more | 28 | 15.9 |
| condition walk (3) | 28 | 1 | 52 to 88, slow lift | 20 degrees, head nodding 18 | 12 | 13.6 |
| run (4) | 20 | 2 (one per 10 ticks) | 48 to 84 | 15 degrees, neck 10 more | 30 | 38.1 |

The animation buffer holds 91992 of 100352 bytes. `tools.test_quetzalmon_flight` checks the pinned source, the
speeds, the seams, the beats, the floor clearance, the distance of the wings to the body and the storage.

### Flymon (262): four flights
The import's idle, walk, condition walk and run (slots 0 and 1, 2, 3, 4) played one 29-tick pose sequence, so the wasp
read as the same animation at three root speeds (17.9, 13.2 and 38.2 units a tick). `field_animations/flymon_flight.py`
writes the five slots again on the reviewed 29-bone import and the result is stored in the plain delta (no overlay: the
generator is run offline, `tools/models/edit.py put 262`); every other slot, the mesh and the rig are unchanged and slot 1
shares the idle. The wings beat about the front-to-back axis from their own hinge (the hinge offsets never change), a
quick downstroke and a slower recovery, the beats of a loop a little unequal, the left wing behind the right and the small
upper pair behind the large pair, chased by a soft spring. The body's rise, the abdomen, the legs, the four small arms and
the antennae are chains of springs on that stroke, each link later than the one before; the legs hang a few degrees behind
the rear arms so the two never meet. Every clip repeats its pose exactly and the root travels the same distance every tick.
The encoder tolerance is 7 units of 1/4096 turn (0.6 degrees) on every bone but the root and the body's offsets (1 unit):
exact tolerances overflow the resident buffer.

| clip | ticks | beats | wings (degrees down from the folded rest) | body pitch (forward) | body rise | root per tick |
| --- | --- | --- | --- | --- | --- | --- |
| idle (0, 1) | 30 | 2 | 6 +- 13 | 1 degree | 15 | 0 |
| walk (2) | 30 | 3 | 7 +- 17 | 11 degrees | 12 | 18 |
| condition walk (3) | 40 | 2 | 11 +- 21 (upper pair 5 higher) | 9 degrees, heaving 7, abdomen drooping | 9 | 13 |
| run (4) | 20 | 4 | 3 +- 9 | 30 degrees, legs and arms trailing | 7 | 38 |

Against the import: the loop lengths (29 ticks each: idle 30, walk 30, condition walk 40, run 20; the idle stays short because a long one hides the condition idles) and the root speeds rounded to
whole units (17.9, 13.2, 38.2 to 18, 13, 38); the footstep sound stays once per loop. The animation buffer holds 95788
of 100352 bytes (92076 before). The head is the body's root bone, so its turns are a slight yaw of the whole body.
`tools.test_flymon_flight` checks the pinned source, the speeds, the seams, the beats, the hinges, that no vertex of a limb
or wing enters the body or another limb and that the wings of a side never cut each other, the floor and the storage.

`field_animations/shadramon_loose.py` is written over Shadramon's model (the claw strides of `shadramon.py`, baked into
its plain delta) and baked into the delta in turn. The import's idle (slot 0; the battle idle, slot 33, shared that
clip and keeps it) hopped: the pelvis rose from 123 to 297 units and the mesh top from 429 to 576. The new idle has the
same 73 samples, both claws on the floor on every one (lowest vertex 0.3 to 2.6 units up, pelvis 148 to 152), the weight
shifting from foot to foot, the chest, head, arms and the four wing lobes moving at their own phases. The walk and run
keep every ankle position and foot orientation of the strides (largest difference 0.35 units), their speeds (16 and 38)
and their planting; the pelvis now sways over the stance foot, drops on the swinging side and turns against the
shoulders, the spine and head follow through a spring, the arms swing with a different amplitude each, and each wing lobe
has its own amplitude, phase and a second harmonic. The tired walk is unchanged. Resident animation buffer 96846 of
100352 bytes. `tools.test_shadramon_loose` checks the exact bytes, the floor, the seam, the planting and the old feet.

`field_animations/tuskmon_lift.py` is written over Tuskmon's model (the strides of `tuskmon.py`, baked into its plain
delta) and baked into the delta in turn. In the idle, walk, tired walk and run the pelvis stands 21, 14, 13 and 9 units
higher (the gaits' legs are nearly straight, which is the limit) and the chest tips up 3 to 4 degrees; every claw keeps
its world position and orientation, so the planting and foot slide are those of before and the cycle lengths and root
speeds do not change. The tired idle (slot 1, head on the floor) keeps its posture. The horns (bone 21) are rigid on
the chest: their rotation against it is constant (it swung up to 6 to 20 degrees away from its mean before). Resident animation
buffer 85344 of 100352 bytes. `tools.test_tuskmon_lift` checks the exact bytes, the height, the claws, the floor, the
horns and the seams.

`field_animations/tylomon_swim.py` is written over Tylomon's model and baked into the delta; the footless post-pass
(`locomotion.json`) and the celebration pass still run over it with the new pins. The import's four field clips (17, 27, 21
and 21 samples) held the whole body nearly still for a quarter of the loop (speed under a tenth of its peak), then snapped
through one yaw with every bone within three ticks of the others (the tail swung 409 units from side to side, the head 75),
and the condition walk and the run were the same poses. The new clips straighten the spine and run a travelling wave down it
(yaw per segment, the head leading, growing to the tail tip, a second harmonic of a seventh to a fifth of it, a vertical wave a
quarter behind, roll, sway, bob), with the fins on springs and the head turning back against the body. Idle 60 ticks; walk 36
ticks at 15 units; condition walk 48 ticks at 14 (head and tail sag, the body sinks lower, the fins hang); run 18 ticks at 35 (the
body stretched and tilted forward, the fins swept back). The tail swings 52, 140, 110 and 95 units, the phase falls steadily from
head to tail, the holds fall to 3 to 8 per cent of the loop and the fastest tick to under twice the mean speed. Resident
animation buffer 67090 of 100352 bytes. `tools.test_tylomon_swim` checks the bytes, the seams, the distance per tick, the wave,
the absence of holds and of a short beat, the floor and the storage.

`field_animations/plesiomon_swim.py` is written over Plesiomon's model (no overlay pass runs on it) and baked into the delta.
The import's four field clips (40 ticks each) were one pose cycle and differed only in the root's speed (0, 22, 15.5 and 39
units a tick). Bones: 1 body, 14 to 18 neck, 19 head, 20 jaw, 10 to 13 tail, 6 + 7 and 8 + 9 front flippers (right, left), 2 + 3
and 4 + 5 hind flippers. The new clips run a travelling wave up the neck (the base held, the yaw and a vertical wave a quarter
behind growing to the head, which trails on a spring and nods against the wave) and down the tail (the tip on a spring, so it
lashes), and row the flippers through springs, the outer joint trailing the inner and the hind pair a little behind the front
pair: a slow figure of eight in the idle (72 ticks), a rowing stroke with left and right half a stroke apart in the walk (40
ticks at 22 units) and the condition walk (60 ticks at 15, low, the neck and head sagging, the tail dragging, short strokes),
and a wide stroke of both sides together in the run (24 ticks at 39, the body pitched forward, the neck stretched out low, a
tail that whips). Speeds are the importer's, rounded to whole units. Slots 1 and 18 shared the idle and follow it. The head
sways 26, 50, 38 and 23 units sideways relative to the body, the tail tip 33, 79, 51 and 125, the front flipper tips 60, 105,
41 and 146 up and down; no vertex group goes through another more often than in the import's pose (counted in every pose) and
the joints stay as close together as they were. Resident animation buffer 83734 of 100352 bytes.
`tools.test_plesiomon_swim` checks the bytes, the aliases, the lengths and speeds, the seams, the waves, the strokes, the body,
the absence of jumps, the vertex counts and gaps, the blink and the storage.
`field_animations/scorpiomon_swim.py` is written over Scorpiomon's model (the Anomalocarimon import: a hovering arthropod with no
legs; its mesh stays 105 to 220 units above the floor) and baked into the delta. The import's idle, walk, tired walk and run
(30 samples each) were one and the same pose sequence, only the root faster (29.5, 28.8 and 57.5 units a tick, the last two outside
the native ranges). The foot slip of 93 to 130 per cent reported for them was measured on the two lowest bones, the mouth plates; there
is no foot to plant, so the checks are different ones. Rig: carapace (bone 1) carrying the face plate (2), mouth plates (3, 4), eyes
(5, 6), claws (7 to 9 right, 10 to 12 left), side blades (13, 14 right, 15, 16 left) and the tail chain (17 to 22, fan last).
Idle 64 ticks (slow breath bob, blades rippling out of step, claws curling and opening with a lag per segment, a small tail wave,
mouth plates working); walk 32 ticks at 26 units (blades rowing in turn, body roll 9 degrees and sway 16 units toward the stroking
side, claws carried forward, a tail wave of about 90 units vertical); tired walk 44 ticks at 14 (body 37 units lower, nose and head
down, claws drooping 60 units lower, blades hanging, tail trailing low, mouth open); run 20 ticks at 42 (nose down, blades fast,
claws tucked up under the face, tail raised and lashing). Every loop closes, the root step is constant, no joint turns past 2.8 times
its median in a tick, and the limbs cross no more than the import's rest pose does (its face plate and the claw and blade roots overlap
by design). The idle's stream is shared with slots 1 and 18, which follow it; no other slot shares the four. Resident animation
buffer 75194 of 100352 bytes (89648 before). `tools.test_scorpiomon_swim` checks the bytes, the seams, the distance per tick, the
speed order, the postures, the tail wave, the rowing in turn, the joint speeds, the clashes and the storage.

`field_animations/triceramon_gait.py` replaces the idle, walk, tired walk and run of Triceramon (257) with authored
clips. The import's clips had walk and tired walk the wrong way round (tired faster than the walk, 18.6 against 15.6 units
a tick), stance feet that slid (88 % of the root speed in the walk) and no breathing. The new speeds are 16 (20 ticks),
11 (23 ticks) and 38 (16 ticks) units a tick, so the tired walk is the slowest and the run the fastest with a shorter,
lower, more leaning stride; the idle is 64 ticks. Stance feet are solved onto points moving back with the root, so the
mean slip is 6 to 14 % of the root speed. The arms swing against the legs of the same side (the import pushed up to 106
points of the arm mesh through the leg), the head, neck and tail follow through springs and the loops close on their
first sample. The torso rides the steps instead of gliding: the pelvis rises and falls 17 units peak to peak in the walk, 11 in the
tired walk and 30 in the run (which dips on each landing and has a short flight), and head, neck and tail answer with
a lag. Resident animation buffer 99304 of 100352 bytes. `tools.test_triceramon_gait` checks the exact bytes, the
bob, the speed order, the seams, the planting, the floor, the limb overlaps and the storage.

`field_animations/darktyrannomon_idle.py` replaces the field idle (slot 0) of DarkTyrannomon (265) and nothing else. The
import's idle was a 21-tick fidget played as a loop: the torso yawed 30 degrees, the head swept 38, the jaw opened 41 and
the tail swung 42 degrees every 0.7 seconds, bones turned up to 8.3 degrees a tick (a step changed by up to 6.3 degrees),
and the feet lifted up to 35 units with a 30-unit pelvis bounce, so it read as convulsions. The new idle is 96 ticks: two breaths whose
depth swells and fades (chest 11 degrees), a tail (bones 3-5, base to tip 25, 28 and 34 degrees) that sways with the glances and
flicks with the yawns, a head (bone 20) nodding and glancing 17 degrees, a lower jaw (bone 21: only its pitch changes, the chin
goes straight down in the head's frame, never sideways) that opens twice a loop (a small and a wide yawn, 25 degrees at most, the
chin 33 and 55 units down) and shuts between them, and, above all, the arms: bones 12-15 and 16-19 (the big outer limbs with
the long claws) swing free, rotation only (shoulders 13-15 degrees forward/back and outward, elbows 15-17, hands and claws
17-21, a lag and a different phase per arm). The feet are bones 6-8 and 9-11 (the short limbs at the centre) with the pelvis (1): solved onto the floor
once and bit for bit the same in every tick. Every bone turns under 2.4
degrees a tick and its step changes by under 0.8. The battle idle
(slot 33) shared the old program and keeps it. Resident animation buffer 94786 of 100352 bytes.
`tools.test_darktyrannomon_idle` checks the exact bytes, the other slots, the seam, the step and frequency bounds, the
range of every bone, the still feet, the free arms, the overlaps and the storage.

`field_animations/pumpkinmon_idle.py` changes the field idle (slot 0) of Pumpkinmon (280) and nothing else. The import's idle is a
27-tick hop in a loop: the pelvis rises 19 units, and both legs fold up and swing, leaving the floor by 33 units (legs turning up to
45 degrees). The new program is the same idle tick for tick, with only the legs (bones 11-14) attenuated: every channel at a third of
its distance from the standing pose, the hips lowered in the pelvis' frame so the lowest point of the legs rises a third as much
(about 14 units), and the leg turns at most about 15 degrees. The other bones, the timing, the loop and the blink events are the
import's. Slot 33 (the battle idle) shared the old program and keeps it. `tools.test_pumpkinmon_idle` checks the exact bytes, that
only slot 0 changes, that every other bone is identical, the leg and sole ranges, the closed loop and the storage.

Dragomon (291) has its own idle, walk, condition walk and run (`field_animations/dragomon_gait.py`, shipped as the model delta): 96 / 26 / 30 / 20
ticks at 0 / 15 / 11 / 36 units per tick, a calm breathing and look-around idle, an easy upright walk, a slow heavy tired drag and an eager loose
lope. A rigid shin with a flat foot caps the stride (a foot's travel per cycle stays under about 200 units), so the cycles cannot be longer at the
native speeds; each loop holds two cycles plus a slow whole-loop drift (head wander, shoulder roll). The soles are the IK targets and slip at most
6 % (mean) while supporting (measure on the soles of bones 5 and 7: the studio's `metrics` reads the two lowest rest-pose bones, which here are the
left blade and one foot; the last step of each contact, the sole rolling off, is left out). The character is large, slow and overlapping: the pelvis
sinks onto each landing foot and recovers over the step (eased, no pop: a foot taking over from the other does not jolt the pelvis height), hips
drop and sway over the loaded leg, the chest counter-turns, the head and crest follow a few ticks later on lag springs (zeta .7: one slow settle, no
ringing), the arms are heavy pendulums with the blade arm slower, the wings rise and fall like breathing. Nothing but the feet moves faster than
twice the step rate (`tools.test_dragomon_gait`). The idle's 96 ticks follow Thundermon's precedent for the condition-idle draw (idles over 25
ticks make some draws unreachable); slots 33 and 36 share the idle and run programs.

Datamon 294 (`tools/models/field_animations/datamon_gait.py`, test `tools.test_datamon_gait`) read as robotic: its field
clips were 8-25 tick loops that repeated every third of a second, the four boots slid at 63-73 % of the travel, and the
arms and torso moved in lockstep. The generator rebuilds slots 0, 2, 3 and 4 with no donor motion stored (no native
model has four boot legs and two big arms on a capsule). The boots keep a pace gait (same-side boots step together, the
rear pair a little later, because a diagonal trot would drive the 57-long boots into each other): each sole is a point
that stays put in the world in stance and a Hermite arc through the air that leaves and lands at the ground's own speed,
with a short push-off backwards, and an inverse-kinematic step places the hip piece, the two small joint pieces and the
boot block on it, the chain telescoping a few units (`EXT`) because the legs are short. The torso leans onto the side
it stands on, nods and yaws with the stride and drops a little at each landing; the two big arms are lagged pendulums,
one joint behind the other and one arm behind the other. A boot's mean speed in the air is the root speed over its swing share (v / (1 - duty)), so the
step is slowed by a short stance share and a long stride cadence (12, 14 and 7 ticks a stride), not by sliding: peak boot
speeds are 36, 30 and 71 units a tick at root speeds of 15, 11 and 36. The loops are a 72-tick idle, a 36-tick walk, a
28-tick tired walk and a 21-tick run (15, 11 and 36 units a tick). The big arms hang with the hands level with the torso
(the model's rest pose holds them 35-42 units in front of it) and swing gently around that. The test reads the model made by `tools/models/edit.py get 294`
(`DATAMON_MODEL`).
Hookmon (299) keeps its chibi-reshaped idle, walk, tired walk and run (same ticks, root travel, rhythm and silhouette) and gets small
corrections on top (`field_animations/hookmon_polish.py`). The imported arms were static in the walk, tired walk and run, and the feet crept
over the floor in each stance, hovered a little above it and skidded in at each landing. Each stance (the ball of the foot staying over one
spot of the ground) is now planted: the foot lands there, is lowered onto the floor where the clip left it hovering, stays put (the heel
rises about the ball, the original toe-off) and leaves with the swing eased in and out of the spot. The leg is solved with two bones towards
the corrected ankle, keeping the clip's own knee direction and the foot's world rotation; a sole that skids low over the floor is lifted.
The footstep sounds play on the touchdown ticks (they were two to four ticks off). The shoulders, hook, gun arm and head carry on a share
(30 to 40 %) of the trunk's turn a few ticks late, so they trail it; the idle breathes (trunk and shoulders, about 1 degree) and the tired
walk hangs the head 7 degrees lower and leans the trunk 3 further. Slip of the toes during stance, mean / worst as a percentage of the
body's speed: walk 47 / 182 before and 10 / 23 now, tired walk 141 mean / 460 worst before and 8 / 30 now (`tools.test_hookmon_polish`).
Antylamon (309) keeps its chibi-reshaped idle, tired walk and run byte for byte and gets a smoother walk (slot 2: same 16 ticks, root travel, sounds
and silhouette; `field_animations/antylamon_polish.py`). Each shoulder had one stray key in the import (the left one at tick 14, the right one at tick 6, half a
loop apart): all three angles about 24 degrees off the middle of its neighbours, so the arm snapped out and back in two ticks (the hand moved 130 to 145 units a
tick against a median of 12; arm vertices 6.4 times the median). Those keys, and the neighbours pulled off with them (three ticks), are now a cubic curve through
the keys around them (arm 1.7 times the median, shoulder turn-rate change 48 down to 9 degrees per tick per tick). The legs lifted off with a kink (shin 70, foot
52 and thigh 38 degrees per tick per tick, median 12) and the foot hopped 38 units for one tick in a swing that otherwise skims 10 to 15 above the floor. The thighs,
shins and ankles are now eased towards the middle of their neighbours' turns (half way) by a weight that is zero while the foot is on the floor and one away from
it, so the stance ticks are the clip's own, to the byte, and the toes slip as much as before (mean / worst 29.6 / 55.5 % of the body's speed over the same steps); shin
28 and 33, thigh 21, foot hop 21 units, leg vertices 1.5 times the median (1.75 before). The root still moves 18 to 42 units a tick (it surges where a foot lands):
that is the import's and was left as it is. `tools.test_antylamon_polish` (`ANTYLAMON_MODEL`, from `tools/models/edit.py get 309`).
SlashAngemon (300) has its own walk (`field_animations/slashangemon_gait.py`, shipped as the model delta; the idle, tired walk and run are the import's). The old
walk planted each foot for about 11 ticks of 16, but the planted knee folded to 93 degrees every time the other foot lifted (thigh -69 to -104 degrees and back
in two ticks), the swinging foot flew at up to four times the ground speed and stopped dead on landing, and the chest yawed a held +-20 degrees that flipped
in three ticks (the tired walk and the run turn +-10 on smooth curves), so the wings swivelled in a snap. The new one is 16 ticks at 20 units a tick: each foot is
planted at the ground's speed, swings on an arc that leaves and meets the floor at the ground's speed, lands heel first and peels off the toe with the toe bone
flat; the legs are two-bone solves, the body sinks where the legs reach furthest and rises over the planted foot (bob 12 units against 21), the pelvis turns 6 and
rolls 3 degrees, the chest turns against the hips on a slow S-curve (about 12 degrees peak to peak) and rolls the other way, rising a little with each push-off; the head stays level and follows the chest's turn about three ticks late with a soft tilt and nod; each arm is a delayed pendulum (the blade arm lags a tick more, its hand opening outwards at the end of the swing) with a small shoulder roll; the wings lift softly at each push-off and fold at each landing, each feather section a little later; the skirt trails the hips. The arms ignore the chest's turn (turning with it pushed them into the torso). The upper body is held to the import's penetration per part, and `tools.test_slashangemon_gait` checks the amplitudes and that no part flutters. A short leg
(the chibi reshape) needs a crouch of about 6 units plus the heel peel to reach the stride (solver reach at most 0.985 of the leg). The stance slip is measured on the
vertex that is each part's sole at rest: at most 6 % (mean 1-2 %), against 33-56 % in the old walk. The tired walk still folds its planted knee like the old walk did.

Creepymon 312 (`tools/models/field_animations/creepymon_gait.py`, test `tools.test_creepymon_gait`) slid its feet in every gait (stance slip 96-104 % mean, 100-170 % worst) and ran at 56 u/tick, above the native range. The overlay builds the celebration model and replaces the idle, walk, tired walk and run: flat soles planted by leg IK at a constant ground speed (walk 20 ticks at 16 u/tick, tired 24 at 12, run 14 at 38 with a short hop, idle 72), the body sinking where the legs reach furthest, the pelvis and robe lagging behind the stride, the chest turning against the hips, and the arms and wings swinging with delay. Stance slip is 4-6 % mean and at most 28 %; the mesh and the chibi proportions are untouched.

Dinohyumon 308 (`tools/models/field_animations/dinohyumon_gait.py`, test `tools.test_dinohyumon_gait`) had clips whose
feet flipped (toe yaw up to 167 degrees), a tired walk that slid its soles (172 % mean, 446 % worst), only one to four
ticks of stance in 17, uneven root steps and a run whose arms hardly moved. The overlay runs the chibi reshape and then
plants each foot with `quadruped.py`: walk, tired walk and run are 32, 60 and 28 ticks (two cycles, the second with other leg lifts, heel strikes, landing times and bob, eased into and out of the first so no step repeats; arms, head, feather and loincloth follow the body on loose springs) at 17, 11 and 38 units a tick
(slip under 4 % mean), the idle 96 ticks with breathing, weight shifts and a raised arm. The posture is a low, forward-leaning warrior's: short weighted steps, the chest turning hard against the hips, the arms bent and held out of lockstep with the legs, a hunched dragging tired walk with the head low, a committed forward-leaning run. The pelvis bobs twice a cycle
and the arms and feather follow with delay. The run's loincloth overlaps a leg slightly more than before (14 against 8).
