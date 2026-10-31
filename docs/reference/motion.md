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
  Patch 0290 applies the same principle to MetalGreymon Vaccine (224): its
  80-tick native acting span contains five 16-tick walks or four 20-tick
  condition walks. Pending navigation changes yield at completed strides;
  its idle can yield immediately. The complete upper-body performance remains
  on its original clock. Unhappy partners still walk instead of running.
  Patch 0287 bounds the wait for the other imported walks and condition walks (slots 2/3) of at least 40 ticks: a pending
  navigation or needs change may yield after 24 completed logic ticks, and a request arriving later yields at once. That
  is not a stride boundary: the existing four-tick field blend hides the cut. Ordinary following still plays the full loop,
  189, 201 and 224 keep their step-aligned rules, and no timer or allocation is added.
- **Condition idles depend on the idle's length.** Standing near the tamer, `STOP_DISTANCE_TIMER` counts up each tick
  and `updateConditionAnimation` runs when it is greater than `anim->frameCount × EMOTION_ANIM_TIMEOUT`, the timeout a
  random 1..5 drawn when the idle starts. The timer is a signed 8-bit value (it wraps after 127), so with an idle of
  127 frames or more the condition idles (hungry, tired, the gestures...) never start, and with an idle over 25 frames
  some draws can never be reached. A long native idle therefore hides the partner's needs; keep field idles short or
  expect fewer condition animations.
- A clip the partner needs to finish (eat, toilet, refuse, sleep, victory, faint, get up, techniques) must not be empty:
  `startAnimation` returns on an empty entry and the code waiting for `animFrame >= frameCount` waits on the previous
  clip.

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

MetalGreymon Vaccine uses 22 / 15 / 52 units per tick in slots 2 / 3 / 4,
matching WarGreymon 373. Its gait periods are 16 / 20 / 10 ticks, with
7 / 10 / 3 ticks of support per foot. Native MetalGreymon Virus (12) travels
25 / 20.833 / 50 units per tick. The former Vaccine speeds, 11 / 8 / 30,
could neither walk alongside the tamer nor catch a running one. Its technique
aliases only reference slots 46–61 and cannot redirect field slots.

Scaling a donor's root travel by the size ratio alone (a big import walking with a small donor's legs) leaves a
catch-up slower than the tamer (13.9 units per tick was measured once, so the partner never caught up); cadence and
travel are chosen together.

## Engine layers for animation

**Cold animations (patch 0113, `tools/coldsplit.py`).** A partner model in `DIGI.DAT` is cut in two: the resident part
(the MMD without its rarely played animations) must fit `PARTNER_MODEL_BUFFER` (0x18800 = 100 352 bytes on the console
layout); each cold slot's table entry is `0x80000000 | (length in words << 16) | offset in words` into the cold part,
which follows the resident part on disc. When such a slot starts, the engine reads whole sectors into
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

Species 224's frozen `RealMetalGreymon.json` import uses Etemon (42), not
MetalGreymon (12). The reviewed `metal_greymon.py` generator changes only 0-4.
Consequently, a corrected field walk does not establish correct care animations.
The following baseline audit describes the **post-delta, post-field-overlay** model before the care repair;
the import spec's `clips` dictionary alone does not describe its techniques.

| Final slots (hexadecimal) | Motion provenance |
|---|---|
| 00-04 | Reviewed field generator; preserve these programs |
| 05, 07-0D | Etemon, same-numbered imported programs |
| 0E-12, 22 | Shared Etemon poor-condition idle (source 01) |
| 13, 18 | Shared Etemon source 13/18 program |
| 15-17, 19 | Etemon, same-numbered imported programs |
| 1B | Delta-adjusted Etemon condition walk; rotations match source 03/1B |
| 21 | Delta-adjusted DCB native idle |
| 23 | Etemon walk (source 02/23) |
| 24 | Delta-adjusted Etemon run; rotations match source 04/24 |
| 25, 2C | Etemon block and get-up |
| 28, 29, 2A, 2B | DCB native hit, knockback, victory and faint |
| 2E, 2F, 32, 33, 35, 37, 3B, 3D | Shared Etemon source 33 technique |
| 30, 31, 34, 36, 38, 39, 3A, 3C | Shared DCB `anim_02` (imported source 34) |

These rows cover every populated slot. Source-program comparisons exclude
unconsumed stream tails (`motiondiscidentity.program`). In particular, final
35 and 3B no longer contain their originally assigned DCB `anim_01` and
`anim_03`: aliases replace them with Etemon's source 33. The care repair replaces those effective Etemon programs as well. Conversely, replacing every technique outside the spec's
native slot numbers would overwrite several aliases of DCB `anim_02`.

`animstudio.py bones` identifies the corresponding mesh parts below. DW1's
seven additional mesh-free helper joints mean that bone numbers cannot simply
be copied. This is an anatomical correspondence, not approval of a retargeted
clip or its contact behavior.

| Part | Species 224 bones | DW1 MetalGreymon bones |
|---|---|---|
| Torso, neck, metal head, jaw | 1, 2, 3, 4 | 2, 3, 4, 5 |
| Metal arm, forearm, claw | 5, 6, 7 | 7, 8, 9 |
| Organic arm, forearm, hand | 8, 9, 10 | 11, 12, 13 |
| Right and left wings | 11, 12 | 15, 17 |
| Pelvis | 13 | 18 (translation carrier: 1) |
| Tail base, middle, tip | 14, 15, 16 | 19, 20, 21 |
| Right thigh, shin, foot | 17, 18, 19 | 23, 24, 25 |
| Left thigh, shin, foot | 20, 21, 22 | 27, 28, 29 |

A generated second pass can read the player's
`extracted/CHDAT/MMD0/MTGR.MMD`: extraction precedes imports and overlays, and
derive's recorded read roots include `extracted/`. The provider passes the
post-delta model into its generator. Neither a donor change in a frozen spec
nor committed disc animation bytes are necessary. Each new clip still needs
decoded subframe contact checks, loop replay, effect/training timing review and
the resident/cold storage gates; anatomical correspondence alone proves none
of these.

#### Generated MetalGreymon care repair

After `metal_greymon.py`, the imports provider runs
`tools/models/field_animations/metal_greymon_care.py` for species 224 only.
Its source hash pins the first pass; its donor hash pins the player's extracted
`CHDAT/MMD0/MTGR.MMD`. Neither frozen import specs nor model deltas change.
The final species pin includes both passes. The generated report nests the
unchanged field proof under `field` and records the care pass separately.

The second pass replaces 26 Etemon-derived slots: 05, 07, 08, 0B-13, 16-19,
22, 25, 2E, 2F, 32, 33, 35, 37, 3B, 3D. The mesh, texture, skeleton,
reviewed 00-04 and every effective DCB-native program remain exact.
**Seven Etemon actions remain:** 09 (sleep), 0A (toilet), 15 (fallen pose), 1B (external HP
training), 23/24 (battle movement), and 2C (get-up). Their candidates failed
floor/contact checks, so only those slots keep their old programs. In particular,
1B's root keys and external loop controls and 23/24's old per-loop travel remain
unchanged; this repair does not claim to fix their skating.

The anatomy map above selects corresponding parts. A rigid shape registration
then matches each mesh's baked axes and pivot against the native mesh, rather
than retaining the importer's neck/claw calibration. Registration reads the
player's vertices, handles their different order, and rejects RMS error over
1.5 units. Native helper joints are folded into the mapped world transforms;
the target's local translations carry those different pivots. The head/neck
follow the native orientation without an additional bow.

Native gestures drive a two-bone solve above fixed care/attack footprints,
with flat foot orientations and a carrier that can move into reach. Body height is projected from the lowest
transformed foot vertices after encoding. A bounded integer carrier solve then
checks every vertex at logic samples and Euler/SRT thirds simultaneously:
no vertex below the floor by more than 2 units, and the supporting foot no more
than 4 units above it. The native's long claws sometimes cross the floor too;
elbow/shoulder and tail clearance corrections bend those branches instead of
lifting the feet. The finisher needs extra elbow clearance during its wind-up.

All changed slots keep their existing duration, decoded events and non-key
controls. Stationary native care actions also remove Etemon's entity-translation
keys: a native eating pose over an inherited shuffle would still skate.
The seven shared technique aliases use native Pulse Laser (36); slot 3D uses
native finisher action 3C. Both map native attack tick 26 to existing effect
sample 15, with separate interpolation before and after the anchor. Original
sound timestamps remain exact. The current species technique list selects 3B
as its gameplay finisher; 3D remains an additional model slot. Offense
training uses untouched DCB slot 3C,
with its existing `hit_tick` 15. Blocking/eating/refusal still terminate, and
looping replacements replay eight cycles without pose drift.

The round-2 resident model is 95,242 bytes (limit 100,352); cold data is 28,764 bytes,
and the largest sector-aligned cold read is 6,144 bytes (limit 8,192). The
partner buffer therefore stays at its original size. These storage checks and
the decoded contact/event/loop proofs run inside the generator, before its
output is accepted. They apply to the 26 replacements, not the seven retained
legacy clips. Visual and in-game review remain necessary.

The subsequent field-speed repair changes only slots 2–4 relative to that care
repair. Foot targets and entity travel use the same new speeds; increasing
root travel alone would skate. Shorter walk support phases keep the longer
strides inside the native leg reach. The run lowers the carrier by eight units
and reduces foot roll; an encoded carrier-height solve enforces the same
2-unit floor limit everywhere and 4-unit supporting-foot limit at ticks and
interpolation thirds. The run retains its airborne phase (maximum foot
clearance 15.46 units); flight has no supporting foot. Pulling those swinging
feet onto the floor would skate. Slip is selected from decoded supporting
surfaces, independently of the authored phase, so such a regression fails.
Mean supporting-foot centroid travel is 0.62 / 0.34 / 0.52 units per tick
(approximately 2.8 / 2.3 / 1.0 percent of root travel). Nine-cycle checks retain
loop closure, limb lengths, scales, native upper acting and footstep bank/note;
all other programs, the mesh and skeleton stay exact. The resulting resident
model is 95,820 bytes (578 more than round 2), still inside the original
100,352-byte buffer; cold storage and its read limits are unchanged.

The English 2 MB test confirms the engine uses these speeds: during steady
slot-4 following, partner/tamer displacement measures 52 versus 50 units per
logic tick (the old model measured approximately 30). On a straight MAYO01
walk starting 600 units behind, the gap after 2,900 units of tamer travel is
684 rather than 1,270; the revised walking trace never exceeds 690. Starting
1,400 units behind a walking tamer plays slot 4 and closes to 744, then walks.
Player control and the straight path remain uninterrupted in those traces.

### 3. The production models and their field recipes

The build's species provider `imports` (`content/models/imports/`: `models.json` and `species.py`) rebuilds the 175 imported
models from player discs and plain deltas ([../building.md](../building.md)), with their
reviewed animations. `models.json` maps each species id to its model, an optional texture, `aliases_applied` (the
species file's `slot_aliases` are already inside the model, so the build drops them) and an optional `field_overlay`.

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
| `fieldsecondary.py` | Stingmon 187, Angewomon 190, MetalGarurumon 191, Paildramon 199 | small delayed secondary motion (arms, feathers, tail tips) with root and leg channels exact |
| `fieldweight.py` | Ankylomon 189, Lighdramon 201 | step-synchronized body roll, yaw and pitch around the existing paw paths |
| `fieldglide.py` | MetalSeadramon 211, Shakkoumon 214, Magnadramon 215, Gesomon 240, MarineAngemon 248, Quetzalmon 249, Solarmon 251 | replaces only the root's forward momentum with one steady key per loop (same net travel), removing forward bursts; every pose channel exact |
| `fieldphantom.py`, `fielddolphin.py`, `fieldzudo.py` | Phantomon 229, Dolphmon 238, Zudomon 219 | restore the native performance clock that the retargeted field clips had squeezed |
| `fieldpiedmon.py`, `fieldfairy.py` | Piedmon 245, Lillymon 209 | keep the native float: Piedmon's leg rotations restored from its native floating cycle; Lillymon's shoulders opened in slot 0x21, the performance the experimental runtime layer (above) shows in the field |
| `fieldnative.py`, `fieldseraph.py`, `fieldangel.py`, `fieldvenom.py`, `fieldmetalgreymon.py`, `fieldaero.py`, `fielddevi.py`, `fieldrose.py`, `fieldsylph.py`, `fieldsorcer.py`, `fieldwizard.py`, `fieldvike.py`, `fieldtuskmon.py`, `fieldshadramon.py`, `fieldshuri.py` | MegaKabuterimon 205, Seraphimon 207, MagnaAngemon 206, VenomMyotismon 212, MetalGreymon (Vaccine) 224, AeroVeedramon 213, Devidramon 216, Rosemon 230, Silphymon 226, Sorcermon 242, Wizardmon 241, Vikemon 220, Tuskmon 253, Shadramon 250, Shurimon 225 | planted strides solved on the native legs (exact link lengths, the whole boot or claw mesh as support) under the native upper-body performance |
| `fieldboxer.py`, `fieldstar.py`, `fieldsuperstar.py`, `fieldthundermon.py`, `fieldroll.py`, `fieldkoku.py` | BomberNanimon 232, Starmon 243, SuperStarmon 244, Thundermon 252, Togemon 208, Kokuwamon 247 | short one-link legs with rigid oversized boots that roll over their support vertices; body height follows the planted boot |
| `fieldgatomon.py`, `fieldcat222.py`, `fieldpup.py`, `fieldgizmo.py`, `fieldape.py`, `fieldscarab.py`, `fieldpaddle.py`, `fieldwalrus.py`, `fielddiaboromon.py` | Gatomon 234, BlackGatomon 222, Salamon 221, Gizamon 239, Apemon 227, GranKuwagamon 210, Gomamon 217, Ikkakumon 218, Diaboromon 237 | quadruped and crouched gaits: one-segment limbs pinned through the body carrier instead of stretched, paired bounds, knuckle walks, flipper strokes |
| `fieldinfermon.py`, `fieldslug.py`, `fieldcandle.py` | Infermon 246, ShellNumemon 231, Candlemon 235 | six legs in alternating tripods; a slug's propulsion clock separate from its face acting (the body slides); a pedestal that holds its footprint at each landing |
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
| Stance slip | during stance (foot within the lowest quarter of its height range), the foot's speed over the ground as a share of the root's: a few percent for the recipes (an original Tyrannomon walk measures about 8 %); the polish pass accepts a change only if it falls by 15 % or more; for a stationary idle use the absolute slip in units per tick | `animstudio.py metrics`, `motionsecondary.support_transfer_displacement` |
| Ground | no mesh vertex below the floor beyond a small band (1 unit for rigid feet, 3 units during heel-to-toe transfer), at logic ticks and at the 60 fps thirds | the recipes' own checks, `motiontailspace.py` |
| Reach | every foot target reachable with native link lengths; encoded foot error within a few units | recipes (`validate_ik`) |
| Loop closure | three (or eight) repetitions compared sample by sample: joint translation, scale and physical rotation must not drift; entity travel and whole turns are allowed; one-shot clips are not closed | `motionloops.py`, `motionloopfix.py` |
| Deliberate rotation | a part that really turns continuously (a clock's winding key, rotors) is declared, bound to the mesh and rig hashes, and excluded from the drift check | `motionloopcontracts.py` |
| Self-intersection | non-coplanar triangle crossings between chosen mesh parts (hands against body and feet, the two feet, tail against legs, weapons against head), optionally restricted to material regions (a rigid tusk, not soft fur); every combination of independently clocked parts | `motionquality.py`, `motiontailspace.py` |
| Untouched data | mesh, skeleton and every slot the recipe does not own byte-identical; events and loop structure exact | `motiondiscidentity.py` |
| Storage | resident ≤ the partner buffer, every cold read within 8192 bytes after sector alignment | `motionstorage.py` |
| Speed | walk keeps up with a walking tamer, run with a running one (Speeds) | recipe asserts |
| Angular speed | knee changes stay inside the reference's envelope (125 % plus 5° per tick); for a four-joint leg driven by a three-joint donor, the whole leg's envelope | recipe asserts |

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

This post-pass deliberately covers footless locomotion. A general planted-gait
retime needs separate contact and thirds checks: resampling can cut across the
floor even when all original tick poses were supported, and re-encoding may
exceed a model's storage budget. Source pins and speed thresholds alone do not
prove a successful gait repair.
