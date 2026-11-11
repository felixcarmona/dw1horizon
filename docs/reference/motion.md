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
| `shakkoumon.py` | Shakkoumon 214 | idle, walk, condition walk and run authored from the rest pose: breathing and weight shift; a waddle (14 ticks, 20 units/tick) rolling over the standing foot, pelvis against chest, arms and head late, soles carried back at the ground speed (slip 26 %); a slower drooping condition walk (20 ticks, 12); a leaning run (12 ticks, 42) with a short flight; pelvis height set per tick on the lowest sole |
| `fieldphantom.py`, `fielddolphin.py`, `fieldzudo.py` | Phantomon 229, Dolphmon 238, Zudomon 219 | restore the native performance clock that the retargeted field clips had squeezed |
| `fieldpiedmon.py`, `fieldfairy.py` | Piedmon 245, Lillymon 209 | keep the native float: Piedmon (since replaced by `piedmon_levitate.py`, four distinct levitating clips); Lillymon's shoulders opened in slot 0x21, the performance the experimental runtime layer (above) shows in the field |
| `fieldnative.py`, `fieldseraph.py`, `fieldangel.py`, `fieldvenom.py`, `fieldaero.py`, `fielddevi.py`, `fieldrose.py`, `fieldsylph.py`, `fieldvike.py`, `fieldtuskmon.py`, `fieldshadramon.py`, `fieldshuri.py` | MegaKabuterimon 205, Seraphimon 207, MagnaAngemon 206, VenomMyotismon 212, AeroVeedramon 213, Devidramon 216, Rosemon 230, Silphymon 226, Vikemon 220, Tuskmon 253, Shadramon 250, Shurimon 225 | planted strides solved on the native legs (exact link lengths, the whole boot or claw mesh as support) under the native upper-body performance; Silphymon's walks also carry the upper body (pelvis bob, lean, torso counter-turn, arms against the legs) with strides as long as its boots |
| `fieldboxer.py`, `fieldstar.py`, `fieldsuperstar.py`, `fieldthundermon.py`, `fieldroll.py`, `fieldkoku.py` | BomberNanimon 232, Starmon 243, SuperStarmon 244, Thundermon 252, Togemon 208, Kokuwamon 247 | short one-link legs with rigid oversized boots that roll over their support vertices; body height follows the planted boot |
| `star_gait_refine.py` | Starmon 243 (SuperStarmon 244 by a rig dict) | offline model delta over the walk/run: ankles pushed out sideways so the boots clear each other, run pelvis pitch cut from 71-79 to about 36 degrees, ribbons hung down and back with a damped periodic pendulum lag; speeds and planting kept |
| `superstar_gait.py` | SuperStarmon 244 | offline model delta: Starmon's refined walk, tired walk and run on the larger body (translations times 1.75, cycles 22, 28 and 25 ticks for 19.5, 13.5 and 37.9 units a tick), idle with the arms hanging |
| `fieldgatomon.py`, `fieldcat222.py`, `fieldpup.py`, `fieldgizmo.py`, `fieldape.py`, `fieldscarab.py`, `fieldpaddle.py`, `fieldwalrus.py`, `fielddiaboromon.py` | Gatomon 234, BlackGatomon 222, Gizamon 239, Apemon 227, GranKuwagamon 210, Gomamon 217, Ikkakumon 218, Diaboromon 237 | quadruped and crouched gaits: one-segment limbs pinned through the body carrier instead of stretched, paired bounds, knuckle walks, flipper strokes |
| `fieldinfermon.py`, `fieldslug.py`, `fieldcandle.py` | Infermon 246, ShellNumemon 231, Candlemon 235 | six legs in alternating tripods; a slug's propulsion clock separate from its face acting (the body slides); a pedestal that hovered on a steady line, bobbing and swaying (Candlemon's clips are now baked hops, see below) |
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

Thundermon uses 20/10/35 units per tick, 4/4/5 gait cycles and
0.5/0.4/0.25 duty within 16/20/20-tick programs. Tick/thirds floor
maxima are −4.587/−5.849/−3.654 units; run slip reaches 123.75% mean.

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
