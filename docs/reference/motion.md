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

**Battle slots stay the source game's own; field slots are ours.** For an imported species, slots 0x21-0x24 hold the clips
the source game made for the fight, and our field work (slots 0-4) never aliases them: a generator or delta that wants a
battle slot to equal a field clip is a defect, and `tools/models/battle_restore.py` takes the importer's clip back
(retimed to the length the slot has now: idles keep their speed and repeat whole cycles, movement keeps its root travel
and its no-lunge rule, a one-shot clip such as a victory or a technique stays one-shot and holds its last pose). Byte-identity of slots 0-4 and the mesh is proved per species before the delta is stored. An original that sits far off
the natural stance (torso tipped back, head looking up) is corrected with a constant pitch of its own bones (`pitch`), which
keeps its swing and timing; a species whose source had no clip of its own gets a field one, pitched (`copy`, then `pitch`).
Reference rows that need a rest pose read slot 0 (`rest_slot` in `celebrations.json`) rather than 0x21 (RedOtamamon's and MegaGargomon's victories do, so giving 0x21 back leaves them as they were).

Every restored slot must pass `tools/models/battle_qa.py` on the final model (the provider's output, not the `edit.py get`
intermediate), measured against the importer's clip and against main's final model: fidelity to the source, limb liveness
(a chain that moves in the source, or in the field walk while its siblings move, must move: a missing bone map), bone map
completeness, mesh integrity (scale, vertex step, loop seam on looping clips only, a piece leaving the body, triangle crossings), posture (body
bones tipped off the field idle, under the floor, floating) and motion (movement length equal to main's, root excursion,
frantic speed). The thresholds are the 99th percentile or the maximum of the 141 native DW1 models' own battle clips
(564 clips; rates in the tool's header) and catch the known bad cases: Infermon's foot off its leg (0.19 heights against
0.08), Suijinmon's still front legs, ShellNumemon's and Okuwamon's torsos tipped back 65 and 29 degrees. A flagged clip is
kept only when no flagged number is worse than main's same slot (the source's own defect, e.g. a battle idle as tipped as
main's); otherwise the slot goes back to main's clip. That rule put back the source clips that collide or tear on the
reshaped (chibi) rig (Kimeramon, Angewomon 0x21, Infermon 0x22, Sakuyamon, Musyamon), the movements a shorter technique
timing made too fast (Okuwamon, Nefertimon, Woodmon), the ones that sink, tip or collide more than main's (Imperialdramon,
Pegasusmon, Raidenmon and others), and Creepymon's 0x23/0x24, which stay the twins of their field
clips (Gazimon's 0x21, the SaberLeomon and WarGreymon 0x22 and Renamon's 0x21 were put back later, rebuilt from the
source's clip with repairs: see the rebuilt battle clips below). Tests: `tools/test_battle_qa.py`.

**Rebuilt battle clips of imported species (batch 48).** A row in `content/models/imports/battle-rebuilds.json` restores a
slot from the source game's own clip and repairs only what breaks (`clip_repair.py`: `turn`, `damp`, `lift`); a rebuilt
slot ships only when `battle_qa.py` passes it on the final output and the resident buffer fits. Fujinmon 0x24 (torso
turned back 12 degrees, body raised 75 units: tipped 14.6, crossings 91, no sinking), Knightmon 0x24 (hips, shoulders and
head turned back: tipped 10.8 degrees against 27), Gargoylemon 0x23/0x24 (forelegs turned out: crossings 11 and 8 a tick
against 60 and 53; the other clips are compacted exactly to fit), Raidenmon 0x23/0x24 (thigh turned out and body raised:
crossings 108 and 122), Beelzemon 0x22 (the source's own walk, unrepaired: 71 crossings, tipped 25.8) are the source's again. Kept as main's: Armadillomon 0x22-0x24 and 0x2C (main is the source plus the deliberate head lift of `armadillomon_head.py`; not a gap), Gallantmon 0x24 (the source run needs
the torso turned back 10 degrees and does not fit: 101076 B after exact compaction against 100352), Beelzemon 0x24 (a
limb is still while its siblings move, 0.000 against 0.279 heights, crossings 203 against 119), Suijinmon 0x23/0x24
(front legs still, the four-leg field clips are the better movement), Kurisarimon 0x23/0x24 (the source's chains are
still and the loop jumps 0.81 and 0.11 heights), Hawkmon 0x21 (the source's right foot is turned 58 degrees outward; the
corrected foot is deliberate, see `hawkmon.py`).

A field overlay writes slots 0-4 and leaves 0x21-0x24 alone, with these documented exceptions: slots whose source clip
measured worse than main's on the overlay's FINAL output and which therefore keep playing a field clip (main's). Nefertimon
0x23/0x24 (vertex step 0.45/0.59 heights a tick, under the floor), Knightmon 0x24 (torso tipped 27 degrees against main's 8), Creepymon 0x23/0x24 (crossings 237 against 191, root travel 0.16
heights off; torso 27 degrees against 14), Gargoylemon 0x23/0x24 (60 and 53
measured worse than main's on the overlay's FINAL output and which therefore keep playing a field clip (main's). SaberLeomon 0x22 (crossings 34 a tick against main's 24),
Knightmon 0x24 (torso tipped 27 degrees against main's 8), Creepymon 0x23/0x24 (crossings 237 against 191, root travel 0.16
heights off; torso 27 degrees against 14), Gazimon 0x21 (loop seam 0.063 heights), Gargoylemon 0x23/0x24 (60 and 53
crossings against 3 and 5; as own streams they overflow the resident buffer, 100602 B against 100352) and Suijinmon
0x23/0x24 (vertex step 0.45/0.59 heights a tick, under the floor), SaberLeomon 0x22 (crossings 34 a tick against main's 24),
Creepymon 0x23/0x24 (crossings 237 against 191, root travel 0.16
heights off; torso 27 degrees against 14), Gazimon 0x21 (loop seam 0.063 heights), and Suijinmon
0x23/0x24 (the importer's clip has no bone map for the front legs). Each is noted in its generator. The chibi pass scales the
root travel of every clip, battle ones included, so a restored movement on a reshaped species differs from the source's in
root travel only (rotations stay exact).

LadyDevimon (223) has her own tired battle idle (slot 0x22, 61 ticks) and get-up (0x2C, 23 ticks) back, rebuilt from the
source game's clips (`content/models/imports/battle-rebuilds.json`): the tired idle's torso leans back 38 degrees in the
original, so the pelvis is turned forward 28 degrees (the right thigh 8 degrees back to keep the leg under it) and the body
raised 40 units, which keeps the soles off the floor (tipped 22 degrees against main's 10, sink 0.17 heights against main's
0.10); the get-up, which ends in the battle idle's pose instead of a neutral one, is raised up to 70 units over its middle
ticks (sink 0.27 heights against main's 0.28). Candlemon's 0x2B (defeat) and ShellNumemon's 0x22 are not restored on
purpose: Candlemon topples over backwards and lies on the floor where the original only leans the pedestal back 54 degrees,
and ShellNumemon's tired idle is the torso-leaned one (`battle_qa.POLISHED`).
**Rebuilt from the original.** A restored clip that fails the checks on our rig is not dropped for a field twin when the original's
poses, timing and arc can be kept and only what breaks repaired: `content/models/imports/battle-rebuilds.json` lists, per species and
slot, the length and the repairs (`tools/models/clip_repair.py`: `turn` a bone about a model axis, `damp` its swing, `smooth` a snap
over the neighbouring ticks, `wave` a chain the source left stiff, `mirror` a leg the source never moved from its twin, `lift` the
body), and `battle_restore.py rebuild` applies them to the importer's clip. `battle_qa.py` skips only fidelity for these slots; every
other check applies and each ships only at `pass`. Okuwamon 0x23/0x24 (21 ticks played in 11 and 9: the legs and wing flutter that
would snap are damped and smoothed, vertex step 0.47/0.92 down to 0.33/0.62 heights a tick, speed 20 down to 15 degrees a tick),
Tortomon 0x23/0x24 (the front leg the source never moved takes its twin's swing, mirrored), Mammothmon 0x22-0x24 (the tipped
tired idle leaned back, 49 degrees down to 20; the stiff tail wags 6 degrees), SkullMammothmon 0x22 (the same lean; crossings
168 down to 20 with the thighs and head turned) and 0x24 (the thighs turned out 25-30 degrees and the tail up: crossings 170
down to 61 against main's 69), Woodmon 0x23 (the claw's one-tick snap smoothed, 0.38 down to 0.24)
play the source's own clips now. SkullMammothmon 0x23 stays main's: with all three rebuilt the species is 1382 B over the resident
buffer (101734 B against 100352 B, after exact compaction, which is the only room allowed), so the pair with the biggest gain
ships (99414 B). Floramon 0x24 stays main's: the source's run passes at the 61 ticks the slot has, but the field pace's pins
have no supported tool to move. Garbagemon's
0x22-0x24 are the source's clips with the can held at its attachment (`garbagemon.py`): only the can's bone differs, so there is
nothing to restore.
Rebuilt battle clips (the source's own movement, repaired with the operations in `tools/models/clip_repair.py`, rows in
`content/models/imports/battle-rebuilds.json`): the movement and run clips of Veemon (0x23/0x24), MetalGarurumon
(0x23/0x24), Nefertimon (0x23/0x24), Imperialdramon (0x24), Pegasusmon (0x23) and Lighdramon (0x24), and Halsemon's
movement (0x23). Each keeps the source's poses and timing and only turns back the bones that crossed the body or tipped
the torso, damps an over-swinging bone, or lifts the body where the soles sank; every one passes the battle QA on the
final model. Imperialdramon's 0x23 and Pegasusmon's 0x24 stay main's clips (the best repair of the source's gallop still crosses the body 89 times a tick against main's 65 and a limit of 83; the
other tips the torso 36 degrees against main's 3). Nefertimon's
0x28-0x2C already are a reviewed repair of the source (paws flat, left gauntlet fixed) and stay as they are.

**Natively bound species get their originals by retargeting.** A native binding (`native_binding.py`) deep-copies the
donor's skeleton and every clip, so the source game's battle clips are gone. A recipe's `"battle_originals": {"slots":
[...]}` puts them back for the slots listed (`field_animations/native_battle.py`, stdlib only): each donor bone is
turned so that its lead piece (a rider's pivot, else the pieces at the top of the group on that bone; siblings are
averaged by weight) has the world orientation the source bone has in the source clip, relative to the bind pose and the
fit's rotation (a mirrored piece's fit is its twin's reflected through both twins' bind poses, which a source may pose
unevenly; pieces set whole in a reviewed orientation, `aim` and their mirrors, and the pieces `battle_originals.ride` lists (a small piece that moves on its own inside a larger one on the same bone) ride their bone and never lead it; a
spinning drum leads its own bone, so it turns as the source's drum does); donor bones above the body that carry pieces
follow the body; the hips' height follows the source's, scaled by the two rigs' hip heights; the root keeps the source's
rotation and travel. Lengths follow `battle_restore.plan` (the donor slot's length, idles tile or keep their own speed),
so technique effects keep their timing. Slots 0-4 and the mesh stay byte for byte. The check is
`tools/models/battle_qa_native.py check ID FINAL B.MMD MAIN.MMD`: it recovers each source piece in the final mesh,
measures the orientation error of the lead pieces (mean 8 degrees, any piece of 2 % of the weight 25 degrees),
end-effector motion about the clip's mean (0.15 heights) and liveness against the source, a retime ratio within 1.6 for
non-idle slots, and `battle_qa`'s mesh, posture and motion numbers against main's same slot (posture only on bones that
show and hold the source's body, not a donor hand holding only a source limb; spinning drums' bones counted among the
bones with pieces; the loop seam and absolute jump only on the looping slots 0x21-0x24). The resident buffer decides the
rest: retargeted clips are dense (every bone keyed), about 1.5 to 3 times the donor's, so only the passing slots that fit,
chosen in the order 0x21-0x24, 0x28/0x29, 0x2A-0x2C, techniques, ship. MegaKabuterimon 205:
0x21, 0x23, 0x24 (99,204 B). Zanbamon 430: 0x21, 0x22, 0x2A, 0x32, 0x38, 0x3C (99,368 B, exact compaction; 0x38's torso bone 26 was tipped beyond main's, so bone 24 is turned back 15 degrees about the x axis: it passes with a tip of 26 degrees against main's 20. 0x39 passes with the same turn but with 0x38 does not fit (100,854 B), and 0x23 passes with it and fits instead of 0x38; 0x24, 0x2F, 0x36 and 0x3B keep the donor's clip: bone 26 stays tipped 26 to 61 degrees against main's 4 to 14 at turns of 15 degrees, and at 25 to 45 degrees pieces move 10 to 19 degrees off the source on average and a tip 0.21 to 0.41 heights). Garudamon 460: 0x21-0x23, 0x28-0x2B, 0x2F, 0x31, 0x32, 0x34, 0x36, 0x37, 0x3B (100,222 B with the donor's NPC clips dropped; technique slots keep the donor clip's sound events, other slots the source's banks 1 and 4 only). Wormmon 183: 0x21-0x23 (67,920 B; the other slots miss the tip-of-tail measure, 0x24 by 0.03 heights, and stay the donor's). BomberNanimon 232: 0x21-0x23, 0x28, 0x29, 0x2C, 0x30, 0x31, 0x34, 0x35, 0x37, 0x38 (75,080 B; 0x24, 0x2A, 0x2B, 0x2E, 0x2F, 0x32, 0x33, 0x36 and 0x39 fail: triangle crossings above main's or retimed more than 1.6). VioletElecmon 256: 0x21, 0x22, 0x24, 0x2A, 0x2E-0x31, 0x33, 0x34, 0x36 (79,740 B; 0x23, 0x28, 0x29, 0x2B, 0x2C, 0x32 and 0x35 failed the check and keep Elecmon's clip). MetalTyrannomon 260: 0x21 and 0x2A (81,616 B); every other slot failed the check (tips off the source, still chains, retimed, tipped bones) and stays the donor's. Minotarumon 330: 0x21, 0x22, 0x28, 0x29, 0x2A, 0x2C, 0x2E, 0x33, 0x34, 0x38, 0x39 (86,714 B; 0x23, 0x24, 0x2B, 0x2F and the other techniques stay the donor's: triangle crossings or a floor sink worse than main, or a retime beyond 1.6). Vilemon 295: 0x21, 0x23, 0x28, 0x29, 0x2E-0x31, 0x33, 0x36, 0x39 (74,586 B; 0x22, 0x24, 0x2A-0x2C and the other techniques stay the donor's: crossings, retiming or vertex step). The rest of the native bindings, with only the slots that pass and fit (the others fail the check, mostly tips off the source, tipped bones or retiming, or no longer fit the buffer): ChaosLord 289: 0x21, 0x23, 0x24, 0x2A (92,426 B; 0x23 and 0x24 sank under the floor, so the hips are lifted 308 and 350 units). HiAndromon 302: 0x21, 0x23, 0x24, 0x28-0x2A, 0x2C, 0x30, 0x31, 0x34-0x36, 0x38, 0x3C (100,306 B, exact compaction and the donor's NPC clips dropped; 0x37 passes but needs 354 B more at exact compaction: with tolerance 5 both 0x37 and 0x3C fit at 94,290 B). KingEtemon 303: 0x22, 0x33, 0x3D (92,184 B; 0x21 passes but puts a glove inside the body, so it stays the donor's). Magnamon 197: 0x21, 0x23, 0x24, 0x36-0x3A (96,850 B; 0x22 and the rest fail: a thigh shares its donor bone with another piece, tips, retiming). Deltamon 292: 0x21, 0x22, 0x23 (88,906 B; 0x23 sank under the floor and its hips are lifted 125 units; the others sink under the floor about twice as far as the source, or are retimed beyond 1.6). GrapLeomon 306: 0x21-0x24, 0x2E, 0x30, 0x33 (98,134 B, exact compaction; 0x32 and 0x3A pass but do not fit). SkullSatamon 314: 0x21-0x23 (87,648 B). Raijinmon 333: 0x21, 0x22, 0x24, 0x2F, 0x30 (93,624 B). DemiDevimon 236: 0x21, 0x22, 0x32-0x37 (72,092 B). NeoCrimson 402: 0x22 (91,212 B; elsewhere two source bones that move against each other lead one donor bone, and the battle stance stands 20-30 degrees more upright than the field idle). PrinceMamemon 270: 0x21 (76,032 B; rotation error 0.4 degrees against main's 40.4, tips 0.033 heights). Its sphere, crown, cape and a small spinning quad inside the sphere all ride Mamemon's body bone; the recipe's `battle_originals.ride` lists the quad (piece 23), which then rides that bone without pulling its turn. The quad's spin and the 5-tick twinkle where the source moves it out of the sphere need a bone of their own and are not played (main's idle lacks them too). The other slots stay Mamemon's: in 0x22-0x24, 0x2A and 0x2E the sphere turns 47 to 179 degrees against the crown and cape on the same donor bone (piece 2 27.5 to 113.8 degrees off); the techniques' legs hang from the body bone but swing with the source's arm bone (tip of a foot 0.23 heights off); 0x2C misses by 0.4 degrees (the cape 25.8 degrees off); 0x28, 0x29, 0x2B, 0x33, 0x39-0x3B and 0x3D would be retimed beyond 1.6. MagnaAngemon 206 (bound offline from a motionless mesh, `field_animations/bound_battle.py`: the imports step makes the same World 2003 mesh with its clips as `imported-models/206.battle.MMD`, content/models/imports/bound-battle.json plays them on Angemon's rig): 0x21, 0x28, 0x29, 0x2E-0x34 (97,408 B, exact compaction of the battle and technique slots only; the hits keep Angemon's impact sounds; 0x2B and 0x2C fail, under the floor 0.32 heights against main's 0.16 and the tip of a leg off the source, and with 0x22-0x24 and 0x2A, which the source has no clip for, stay Angemon's). Renamon 354 keeps its 0x21: it fails the check (26 triangle crossings a tick, main 1). Cannondramon 405: 0x21-0x24, 0x28, 0x29, 0x2F, 0x30, 0x35, 0x36, 0x38, 0x39, 0x3A (98,316 B, exact compaction and the donor's NPC clips dropped; 0x23, 0x24, 0x30, 0x35, 0x38 and 0x39 sank under the floor and have their hips lifted 146 to 187 units). Kyubimon 409: 0x21, 0x2E-0x31, 0x33, 0x38 (99,788 B, exact compaction; the USA release's model 99,836 B; 0x39 passes but does not fit).
Test: `tools/test_native_battle.py`
and the species' tests.

Memory: a restored clip is one more resident program, so a species near the resident limit (100352 B) could not take it as
it was. Idles are restored at their own length (the repeats of a short cycle cannot fold into the clip's loop, and cost
three to five times the bytes), and `battle_restore.compact` re-encodes the model's resident clips from their own decoded
ticks: exact (tolerance 0, same ticks in fewer bytes) wherever that is enough, and up to 5 units (0.45 degrees) on the clips
that are neither field slots (0-4) nor battle slots for Vikemon (4), Growlmon (5) and Veedramon (5, technique clips only);
field slots 0-4 and the battle slots are never loosened (Veedramon's gait now reads its native idle from slot 0, the
importer's field idle, so that slot 33 can be the source's battle idle: its field clips stay tick for tick). That brought
Veemon (0x21), MetalGarurumon (0x22), Halsemon (0x24), Veedramon (0x21), Vikemon (0x22), Dragomon (0x21, 0x22), Divermon
(0x21), Growlmon (0x21, 0x23, 0x24), Kyukimon (0x21) and Bastemon (0x21) the source's clips; the rest of their battle slots
and all of Cyclonemon's and Datamon's stay main's, because the source clip fails `battle_qa` (a loop seam and a tipped
torso, a frantic idle, collisions on the reshaped rig), not for memory. Measured on the final models against main's: the
loosened technique clips move by at most 1.1 degrees on any bone and 0.017 heights of root travel; `battle_qa` (slots
0x21-0x24) passes or keeps main's verdict on every slot of the ten species.

WarGrowlmon (326) wears Growlmon's rig and clips, so it would inherit the three restored battle clips and no longer fit the
resident buffer (104,746 of 100,352 bytes); its recipe (`native-bindings.json`) points the battle slots 33, 35 and 36 at its own
field clips (`extra_slots`) and drops the donor clips they leave unused (`prune_unused`), as before. Its resident size is 98,340
bytes. A side effect of re-encoding Growlmon's clips: WarGrowlmon's tired walk (slot 3) and two non-field clips (0x18,
0x1B) differ from main's by at most 4 units (0.35 degrees); its idle, walk and run are tick for tick. `native_binding`
also reads the reviewed source through `reviewed.py`, so a variant release's own import of a native-bound species
(Kyubimon on the USA World 3 disc) builds with the reviewed recipe.

Species with a Digimon World 3 (USA) variant (`content/modeldelta/variants/dw3-us.json`) are restored on the PAL
import and `tools/models/variants.py make` carries the delta: a restored slot is no edit of ours, so the USA model keeps
that release's own battle clip, and the QA is run on both releases' final models. Ebidramon 0x21 and 0x24, Antylamon 0x21,
MaloMyotismon 0x21-0x24 and Kurisarimon 0x21 are the source's again (the Ebidramon and Kurisarimon generators no
longer write the twins). Ebidramon's 0x24 is leaned (`battle_restore.py pitch`, bone 1 by 20 and bone 9 by -5 degrees):
unleaned its body is tipped 35 degrees off the field idle, main 18; leaned, 15.3. Rebuilt battle clips: where the source's own clip fails the QA on our rig, the clip is kept and only the bones that
break it are repaired (`tools/models/clip_repair.py`, rows in content/models/imports/battle-rebuilds.json, applied by
`battle_restore.py rebuild`; the slot counts as a documented polish and keeps every other check). Renamon 0x21 (26
triangle crossings a tick on the reshaped rig, main 1): the two thighs turned 4 degrees apart about their side axis, 1
crossing a tick. SaberLeomon 0x22 (crossings 34 a tick, main 24, field idle 6): chest turned back 10 and the mane's bone
6 degrees, 15 a tick. WarGreymon 0x22 (the source's pounce, claws crossed in front of the chest, 443 crossings a tick,
main 74, field idle 40): shoulders turned out 20 degrees and forearms 25, 50 a tick; the care generator no longer ties 0x22
to the tired idle. Gazimon 0x21 (loop seam 0.063 heights, limit 0.05): the tail's bone 15 eased back to its first pose over
the last 8 ticks, seam 0.035; its overlay no longer writes the battle slot, and the exact compaction of the other clips
(about 2,900 B) pays for the source's longer clip (98,990 B resident). `edit.py repin` moves the pins of these overlays
(profile modules, the pace rows, a generator's `SOURCE`, the donors' pins of native bindings: NeoCrimson, which takes
WarGreymon's model as donor, is byte-identical).

Batch 48 rebuilt more imported battle clips from the source's own (`battle-rebuilds.json`, ops in `clip_repair.py`: turn,
damp, lift, wave, and `rig` to fit the source clip to our rig's scale and offsets). Aquilamon 0x22 and 0x23 (torso
compensated, wings spread, soles lifted) and its get-up 0x2C (source clip, passes unrepaired and is better than main on
every number); Infermon 0x22-0x24 (offline-reshaped rig fitted, body lifted 62-100 units); MarineAngemon 0x22 (torso
compensated); Quetzalmon 0x23, 0x24 (body pitched back and lifted) and its get-up 0x2C (left arm turned, body tipped 48
degrees against main's 89); GranKuwagamon 0x23 (lifted) and 0x24 (the four wing and limb bones damped to half, lifted);
Lillymon 0x22-0x24 (0x22 torso compensated). Stay main's: Submarimon (its tail screw spin is deliberate), Lillymon 0x21
(shoulder opening, deliberate), MarineAngemon 0x21 (constant scale of bone 25) and 0x23, 0x24 (the source's legs and limbs
are still, the liveness check fails), Aquilamon 0x24 (best rebuild 112 crossings a tick against a limit of 73, main 30).

Seven imported species have their remaining battle clips rebuilt from the source's own clip (`content/models/imports/battle-rebuilds.json`,
`battle_restore.py rebuild`, repair operations in `clip_repair.py`: `turn`, `damp`, `lift`, `retime`, `seam`, `sway`); each was
kept as the older clip only because the source's clip failed the check or the memory budget, and each ships only where the
check passes on the final model and the resident memory stays under 100352 bytes. Octomon 0x21 (retimed to 32 ticks, loop
seam closed over 6; 99432 bytes), Cyclonemon 0x21 (bone 3 turned back 45 degrees, seam over 5; 85466), Dragomon 0x24 (21 ticks,
bone 3 tipped back 22 degrees; 97788), Divermon 0x24 (25 ticks, one tail-leg sway of 12 degrees; 99522; its 0x23 stays the
older clip, restoring it needs 1940 bytes more than the budget leaves), BlackKingNumemon 0x23, 0x24 and the victory 0x2A (33 and
25 ticks, arms and tail turned out of the body, victory damped and turned; the generator no longer writes them; 87318),
Arukenimon 0x21, 0x23 and 0x24 (legs swaying as delayed pendulums; its victory follows the new idle pose; the generator's
pins moved; 95166) and Creepymon 0x23 and 0x24 (21 and 15 ticks, thighs swung forward 20 degrees and out 8, run torso
turned back 8; the generator no longer writes the twins; 75858). Divermon's technique clip that aliases 0x24 follows it.

A recipe's `"drop_npc_slots": true` leaves out the donor's clips of the slots only the tamer, the NPCs and the kart race play (6, 0x14, 0x1A, 0x1C-0x20, 0x26, 0x27; the importer's own species ship without them too, and no partner starts them), which frees the room for the source's battle clips; `battle_originals.repairs` `{"<slot>": [ops]}` runs `clip_repair` operations on the retargeted ticks of a slot (`lift` raises a body bone so the soles stay on the floor, `turn` compensates a tipped torso).

Room is made by `"compact": {"tol": N}` in the same entry (`native_battle.compact`, after the retarget; Wizardmon's
and Sorcermon's builder runs it once, after its cape and hair followers, which skip the restored slots):
`battle_restore.compact` re-encodes every clip with repeats losslessly, then, at N units of 1/4096 turn (at most 5,
0.44 degrees), every clip that is neither a field slot 0-4 nor a battle slot 0x21-0x24; identical streams are shared
and dead tails dropped. Field and battle slots decode exactly as before. Wizardmon 241 (tol 5): 0x21-0x23,
0x28-0x2B, 0x34, 0x35, 0x37 (99,770 B; its training clip 0x39 stays Angemon's). Sorcermon 242 (tol 2): 0x21, 0x22,
0x2E, 0x30, 0x33, 0x38 (98,358 B). Assaultmon 310 (tol 5): 0x21, 0x22, 0x28, 0x29, 0x2B, 0x2C, 0x2E-0x35, 0x3B
(99,076 B). Maildramon 324 (tol 5): 0x21, 0x23, 0x24, 0x2B, 0x2C, 0x2F, 0x32 (99,862 B). WarGrowlmon 326 (tol 4):
0x22, 0x28-0x2C (100,108 B).

The care and condition slots (1 and 14-19 the condition idles; 5, 7-13, 0x16, 0x1B and 0x25 the care clips) are measured
by `tools/models/care_qa.py` on the final model the same way, against the field idle, the importer's clip and main's
final model: distinctness (a condition idle's mean body-frame vertex distance to the nearest field idle pose at least
0.035 heights, the 1st percentile of the 611 native condition clips, whose median is 0.12; two condition idles that are
different programs at least 0.026 apart; sharing one program is the natives' own habit), liveness, anatomy (a bone
turning 60 degrees beyond its field and importer range), torso pitch (not flagged when the importer's own clip tips
as far against its own idle: that is the source's posture), mesh integrity (crossings between pieces are not flagged
within 1.25 times the importer's same clip: a reworked field idle can cross far less than the source's poses), loop seam, length (condition idles
under 127 ticks, slot 1 no longer than main's), the floor (under the field idle's own lowest point: a hovering flyer's
idle dips under its mean floor) and the resident buffer. A flagged clip is kept only when no flagged number is worse
than main's same slot. Tests: `tools/test_care_qa.py` (`CARE_QA_MODELS` runs it on a folder of real models).

Datamon 294 0x21 stays main's: the source's own 27-tick marching idle is frantic on our rig (6.4 degrees a tick against the 5.4
limit and main's 0.4), and with every bone but the root and the body damped to 0.8 of its swing (`damp`) it passes `battle_qa`
(speed 5.2, vertex step 0.09 h, loop seam 0.03 h, crossings 3.3 a tick), but the extra 4.9 KB program brings the resident part to
102,242 B after exact compaction of every clip, 1,890 B over 100,352 (only a lossy 5-unit compaction of the care and technique clips fits).
Solarmon 251 0x21 is not a gap: main's clip is the source's 89-tick spinning-disc idle except the last three ticks, which close
the loop (the source's last pose is 24 degrees from its first: loop seam 0.206 h); `battle_qa` reports it as main's, with the
source's own vertex step (0.986 h, source 1.006: the disc's spin), so it stays.

Where a field rework made slot 1 or 18 a copy of the new field idle (24 species; Gazimon's sick idle too), the last provider stage
`tools/models/field_animations/care_idles.py` makes the condition idles again from the final field idle: only rotation
channels of the body, head and non-leg limbs change (legs, the bones they hang from, scale and translation channels
stay the idle's, so the feet and the chibi proportions are kept), the idle's own motion is damped and each condition
gets its posture and timing (tired: slump, hanging head, drooping arms or wings and a slow heavy breath; sick: a deeper
hunch, limbs drawn in, two short shudders a loop; hungry: head down to the belly, looking from side to side; toilet:
restless side to side; sleepy: two slow nods that catch themselves; unhappy: head down and a slow sway). A clip is the
idle's cycle repeated (slot 1 one cycle, so never longer than main's; an idle cycle over 120 ticks is resampled to 120).
The rows (`content/models/imports/care-idles.json`: body type, bone roles, slots, gains) are made by
`care_idles_plan.py`, which reads the roles from the model's geometry, raises a condition's gain until it is 0.05
heights off the idle with no flag, lets a condition too close to another share its program, and uses a coarser
encoding when the resident buffer would overflow. A retargeted care clip that turns a bone far beyond anything the
species does is tamed in the same stage (the row's `tame`: per slot, the fraction of the swing each such bone keeps
about the clip's own mean pose), with the smallest cut that passes the bone check (`care_qa`'s flag names the bone).
Three species near the resident limit (Snimon 328, Apocalymon 400, MegaGargomon 335) had no row, because a condition clip
of their own (1.3-3.2 KB at the coarsest encoding the planner tries, 16 units) overflows the buffer. Apocalymon's row sets
`compact`, which re-encodes its other resident clips exactly first (96,962 B), and keeps its own tired idle for slots 1 and 18
(tolerance 2; resident 100,198 B; care_qa pass, 0.06 heights off the idle). Snimon and MegaGargomon have no such room
(exact compaction frees 56 and 162 B; their own tired clip would need 222 and 202 B more even at tolerance 16), so a row's
`share` points slots 1 and 18 at the program slots 14-17 already play, the donor's own condition clip (0 extra bytes; care_qa
pass, 0.13 and 0.18 heights off the idle; resident 99,332 and 99,484 B). Their other condition slots stay as they were.
Their battle slots 0x24 (Snimon: the source clip passes `battle_qa`, but 101,884 B resident after exact compaction) and
0x21 (Apocalymon: crossings 577 a tick against main's 70 on the reshaped rig, and 103,320 B) stay main's.
Bodies whose limbs read as legs (a squid's eight arms, a sun's two hands: every bone is then a leg or hangs from one, so the
planner found no free bone) name them to the planner (`--limbs` the first bone of each such chain, `--head`, `--lean`): they droop
like any limb, the head nods, and a body with no leg at all (Solarmon) leans as a whole. A short idle whose slot 1 is one cycle
(Bulbmon's 24 ticks) plays one cycle in the slots that share its program (the row's `cycles`), because two lengths of one
motion are two programs 0.004 heights apart. Gesomon 240 (one tired program in 1 and 14-18: a second, sick, does not fit; the delta is first compacted exactly,
98,870 to 97,442 B, then the stage adds 2.8 KB with the new clip encoded at tolerance 2: 100,278 B; slot 19 stays main's), Solarmon 251 (all seven slots: tired, sick shares tired, hungry shares
unhappy; 35,542 B, the body leans 13-18 degrees forward in tired) and Bulbmon 313 (the head nods and the two vine arms
droop: tired in 1 and 15-19, sick in 14; the delta is first compacted exactly, 80,934 to 68,204 B) got condition idles: before, slots 1 and 18
of Gesomon and Solarmon were the field idle itself and Bulbmon's seven were 0.007 heights off it.

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
including Roachmon's native hand swap. Kotemon first receives its own
walk, tired walk and run (`kotemon_gait.py`); its two native hit clips then recoil within three ticks
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
| `puppetmon_field.py` | Puppetmon 181 | the original's pelvis lean and twist over planted-sole legs (`quadruped.py`), then chest, head, both arms and the hammer from damped springs; two-stride loops (the second differs), an idle that breathes and shifts weight; walk 14 ticks at 22, tired 18 at 12, run 10 at 42; stance slip at most 29 % (the original slid up to 90, 209 and 47 % in the walk, tired walk and run) |
| `fieldsecondary.py` | Stingmon 187, Angewomon 190, Paildramon 199 | small delayed secondary motion (arms, feathers, tail tips) with root and leg channels exact |
| `fieldweight.py` | Ankylomon 189, Lighdramon 201 | step-synchronized body roll, yaw and pitch around the existing paw paths |
| `fieldglide.py` | MetalSeadramon 211, Magnadramon 215, Gesomon 240, MarineAngemon 248, Solarmon 251 | replaces only the root's forward momentum with one steady key per loop (same net travel), removing forward bursts; every pose channel exact |
| `tortomon.py` | Tortomon 261 | walk, condition walk and trot authored with `quadruped.py` from the shell bone: a lateral-sequence walk (16 ticks, 12 units/tick), a lower slower condition walk (22 ticks, 9) with a hung head, a trot (10 ticks, 36); each foot is planted flat and still for about a quarter of the cycle (duty 0.28, 0.26, 0.17; sole slide 0-4 units) while the shin turns over the ankle, then peels off heel first and swings in an arc (`arc`, `fold_soft`, per-leg `leg_reach`); no tick reaches the IK's stretch or fold limit and no joint jumps between ticks; cuffs up to 30 units under the floor and slip up to 30 % are allowed (profile `floor`, `stance_slip`), because the legs reach only about 70 units of ankle travel; slot 36 shares the run |
| `extyrannomon_arms.py` | ExTyrannomon 266 | arms only (bones 7, 8) of the walk, condition walk and run: a spring on the opposite-phase pitch of the same-side leg (swing 21, 11 and 36 degrees, a tick or two late), footfall kicks, sway abduction, disc roll; body, legs, tail, events and idle untouched; arm-versus-body and arm-versus-leg vertex counts never above the original; slot 36 shares the run |
| `mammothmon_gait.py` | Mammothmon 267 | walk, condition walk and run re-authored with `quadruped.py` so the hind (and front) feet plant: walk 20 ticks at 15 units/tick, condition walk 24 at 11, trot 10 at 36, the hind reach (about 150 units planted) setting the short cycles; trunk, ears and jaw follow on lagged closed loops; the idle is kept. Test: `tools/test_mammothmon_gait.py` |
| `kiwimon_gait.py` | Kiwimon 282 | offline model delta: walk (14 ticks, 17 units/tick), tired walk (18, 12) and run (10, 38) rewritten with `quadruped.py` on its own two legs (thigh, shin, ankle pad as the planted paw, the toes riding on it): each foot stands flat and still for half the walk (duty 0.52, 0.62 tired, 0.34 run; sole slide under 1 % of the travel) and swings with 18-48 units of clearance, the knees pointing out and back so the thighs stay out of the rump; the body crouches a little, bobs twice a cycle, shifts, rolls and yaws over the loaded foot and leans into the run; the head holds still in the world and snaps forward every step (`saw`), pecks once a cycle in the walk, swings low in the tired walk with a panting jaw, thrusts in the run; the rump trails late and rocks with the breath; the toes lift in the swing. The idle (slots 0 and 33, 60 ticks) is rewritten too: both soles planted, slow breathing, a weight shift, the head looking about and one peck; slot 36 shares the run, every other slot is kept. Test: `tools/test_kiwimon_gait.py` |
| `pukumon_gait.py` | Pukumon 401 | offline model delta: the imported clips held the left arm up and shared one fin/tail/jaw cycle; idle (96 ticks), walk (16 ticks, 19 units/tick), tired walk (24, 12) and run (12, 38) rewritten on the two fists (`quadruped.Rig` two-bone solve, the left arm the right one mirrored): each fist stands flat and still in the world for its stance and swings with 11-50 units of lift (stance slip mean 6-10 %, worst 44 %), the body vaults over the fists (reach-limited height, landing dips, flight in the run, surge, sway, roll, yaw, lean 5/15/14 degrees), tail, fins and jaw each at their own rate per clip. Battle slots 33, 35, 36 keep their own copy of the old clips. Resident buffer 56510 -> 68572 B. Test: `tools/test_pukumon_gait.py` |
| `woodmon.py` | Woodmon 272 | walk (12 ticks, 15 units/tick), tired walk (16, 11) and trot (10, 38) from the imported rest pose: four root legs with `quadruped.py` (planted flat, slip under 1 %) and a trunk written by the profile's `body` hook: it bobs, rolls, shifts its weight sideways, yaws, leans into the run and slouches when tired, the log arms swing against the legs with the forearm late, the chest claws trail; the idle (slots 0 and 33) is a calm 40-tick loop: slow breathing, arms and claws swaying 11-20 degrees with lag, legs planted; slots 35 and 36 share the walk and run |
| `grizzlymon_gait.py` | Grizzlymon 296 | idle (96 ticks, slots 0, 1 and 18), walk (24 ticks, 15 units/tick), tired walk (28, 11) and run (15, 38) with `quadruped.py` (new `flat_shin` key for the hind shin plates, speed 0 for the idle): a menacing bear's plantigrade lateral-sequence walk (hind foot, then the same-side fore foot; paws planted flat, slip about 10 %), the body rolling and shifting its weight over the loaded paw with shoulders and hips turning against each other, a hump over the planted fore paw, a body drop on every fore landing and the head pushed out low ahead of the shoulders, lunging with each step and sweeping slowly from side to side with the jaw a little open; the tired walk is a heavy, dragging stalk with the same low head; the run is a low rotary charge with the head thrust forward; the idle breathes heavily with the shoulders rising, sweeps the head wide and slowly lowers it, growls (jaw pulses and chest swell) and lifts and sets down a fore paw. Test: `tools/test_grizzlymon_gait.py` |
| `tapirmon.py` | Tapirmon 287 | idle (64 ticks, slots 0 and 33), walk (27 ticks = 3 strides of 9, 16 units/tick), tired walk (39 = 3 x 13, 10) and a light gallop (one 14-tick cycle, 38; hind pair pushes together, a flight phase, front pair lands together, spine flexing), each with a layered breath written leg by leg because the rig has two-bone legs with a rear foot plate and no tail or paw bones (`quadruped.py` does not fit): planted flat soles, swing paths that match the stance speed, a per-tick body-height solver that keeps every leg within reach, hind plates counter-rotated flat; the body, rear block, head, snout and ears follow lagged closed loops; the tired walk keeps the head low and facing forward; the idle takes one slow breath, looks aside, sniffs, twitches an ear and flicks the tail; slots 1 and 34-36 are untouched |
| `gryphonmon_gait.py` | Gryphonmon 293 | idle (96 ticks), walk (22 ticks, 16 units/tick), tired walk (28, 11) and a gallop (16, 38) made with `quadruped.py` on the rig's four legs (hocks and elbows fold backwards, the long flat paws are planted by their sole point): walk and tired walk are four-beat, the run is a gallop with a flight; the neck is arched and the paws lift high in the walk, the wings beat once a stride (quick downstroke, slower upstroke, the fan trailing the arm), wider in the run and low and slow when tired; the idle breathes, stretches the wings, scans with the beak, settles, flicks the tail and blinks; the celebration (slot 42) overlay now starts from this model; slots 1, 33, 35 and 36 are untouched |
| `cyclonemon_gait.py` | Cyclonemon 281 | idle, walk, condition walk and run authored with `quadruped.py` (opt-in `scale`, `paw_rest`, `body` keys for the 1.3-scaled body): the left arm is a planted crutch and both hind feet plant; idle 48 ticks, walk 18 at 15 units/tick, condition walk 26 at 11 (lower), run 12 at 38 (forward lean); feet slip under 4 %; the shoulder pad keeps its place on the torso. Test: `tools/test_cyclonemon_gait.py` |
| `crabmon_scuttle.py` | Crabmon 284 | offline model delta: six legs solved with damped least squares so each tip stands still in its stance (soles on the floor), the shell rides above them; idle 84 ticks (shared with slots 1 and 18), walk 22 at 15 units/tick (tetrapod pairs), condition walk 28 at 10 (a wave, low shell, drooping claws), run 14 at 38 (tripods with a flight phase); feet slip about 1 %; claws swing, snap and pull in |
| `dokugumon_gait.py` | Dokugumon 298 | offline model delta: six three-bone legs solved with damped least squares so each tip stands still in its stance (soles on the floor), the body raised and the feet wide; two alternating groups of three; idle 72 ticks (shared with slot 33), walk 20 at 18 units/tick, condition walk 32 at 12 (stalking, low body), run 16 at 40 (flight phase); the abdomen swings against the body, fangs and palps move softly; stance slip under 2 % |
| `armageddemon_gait.py` | Armageddemon 407 | offline model delta (slots 0, 2, 3, 4): six three-bone legs solved from the sole so each stands still in its stance; two alternating groups of three with whole-tick swings (rise first, travel in the middle, land on the place); idle 72 ticks, walk 24 at 22 units/tick, condition walk 36 at 14 (body 40 lower, one leg at a time), run 16 at 42 (flight phase); neck and head lag the twist, jaw twitches, the tail follows with a travelling wave; stance slip under 8 % |
| `kurisarimon_gait.py` | Kurisarimon 431 | offline model delta (slots 0, 1, 2, 3, 4, 18, 33): the chrysalis hovers on six dangling blade-footed legs, no foot ever stepping; each leg bone is a sum of two sine harmonics a beat behind its parent and each leg out of step with the next; idle 72 ticks (shared with slots 1, 18 and 33; slow bob, glances, a blade flicks), walk 32 at 18 units/tick (a glide, leaning, two bobs, legs paddling loosely, abdomen wave), condition walk 48 at 12 (low sagging drift, legs drooping), run 20 at 38 (strong lean, legs and abdomen streaming back, quick bob); the body is lifted per clip so that no vertex of the model goes under the floor. Test: `tools/test_kurisarimon_gait.py` |
| `arukenimon_gait.py` | Arukenimon 311 | offline model delta: six two-bone legs solved with damped least squares so each tip stands still in its stance, the body raised and the feet wide; two alternating groups of three; idle 96 ticks (shared with slot 33, breathing, glances, a lifting arm and a paw), walk 24 at 24 units/tick, condition walk 36 at 13 (one leg at a time, low hunched body), run 16 at 44 (flight phase); the torso turns against the pelvis, the head stays level and lags, the sleeves are delayed pendulums; the torso turns 15-26 degrees, pitches 10-18 and rolls 11-17 over a loop; stance slip 1 % (walk), 2 % (condition walk), 0.4 % (run) |
| `fujinmon_gait.py` | Fujinmon 317 | offline model delta: two two-bone legs planted in stance, a hand-written body (pelvis and chest turn against each other, the body sinks on each landing, the cannon arms are delayed pendulums, the scarf trails, the pauldron rotors turn one whole turn a loop: 18, 13 and 26 degrees a tick); walk 20 ticks at 18 units/tick, condition walk 28 at 12, run 14 at 40 (flight phase, forward lean); the idle and slot 35 are untouched; stance slip 3 to 6 % on average |
| `raidenmon_gait.py` | Raidenmon 336 | offline model delta: two two-bone legs planted in stance (the imported clips turned the foot blocks about the floor, soles 88 / 81 / 183 units under it and sliding), the donor's trunk, head, tail, arms and claws kept as its first three harmonics with eased swing and arms lifted off the floor; walk 24 ticks at 17 units/tick, condition walk 30 at 11, run 14 at 40 (flight phase); the idle only has its pelvis raised on the ticks where the soles sank (5 units); stance slip under 3 % |
| `deramon_gait.py` | Deramon 286 | idle (120 ticks, shared by slot 33), walk (16 ticks, 16 units/tick), tired walk (20, 10) and run (10, 38) for an 8-bone rig whose shell (bone 1) parents every other bone: each pose is written in the world and turned into local values, so the feet are placed (flat and still in stance, slip under 10 %, lift 16-38 units, ankle height set by the lowest sole point), the body, head and wings move as one group about a floor point (roll over the loaded foot, yaw, lean, bob, sway), and the shell takes the same motion through a damped spring per harmonic: it lags, rocks and bounces, and is kept off the floor; the idle keeps the original blink; slots 35 and 36 play other programs and are untouched. Test: `tools/test_deramon_gait.py` |
| `ebidramon_swim.py` | Ebidramon 305 | offline model delta: the shrimp dragon has no limb that reaches the floor but its tail fan, so every clip is a hover (the fan skims the floor at its lowest, never through it): idle 96 ticks (breathing, claw and pincer gestures; slots 1 and 18 follow it), walk 48 at 22 units/tick, tired walk 64 at 14 (low, nose down), run 32 at 40 (pitched forward, big bounce; the battle run, slot 36, is the source game's own clip again); the abdomen flexes as a wave with the fan last, swimmerets row front to back, arms swing as delayed pendulums, antennae trail. Test: `tools/test_ebidramon_swim.py` |
| `shakkoumon.py` | Shakkoumon 214 | idle, walk, condition walk and run authored from the rest pose: breathing and weight shift; a waddle (14 ticks, 20 units/tick) rolling over the standing foot, pelvis against chest, arms and head late, soles carried back at the ground speed (slip 26 %); a slower drooping condition walk (20 ticks, 12); a leaning run (12 ticks, 42) with a short flight; pelvis height set per tick on the lowest sole |
| `fieldphantom.py`, `fielddolphin.py`, `fieldzudo.py` | Phantomon 229, Dolphmon 238, Zudomon 219 | restore the native performance clock that the retargeted field clips had squeezed |
| `fieldpiedmon.py`, `fieldfairy.py` | Piedmon 245, Lillymon 209 | keep the native float: Piedmon (since replaced by `piedmon_levitate.py`, four distinct levitating clips); Lillymon's shoulders opened in slot 0x21, the performance the experimental runtime layer (above) shows in the field |
| `fieldnative.py`, `fieldseraph.py`, `fieldangel.py`, `fieldvenom.py`, `fieldaero.py`, `fielddevi.py`, `fieldrose.py`, `fieldsylph.py`, `fieldvike.py`, `fieldtuskmon.py`, `fieldshadramon.py`, `fieldshuri.py` | MegaKabuterimon 205, Seraphimon 207, MagnaAngemon 206, VenomMyotismon 212, AeroVeedramon 213, Devidramon 216, Rosemon 230, Silphymon 226, Vikemon 220, Tuskmon 253, Shadramon 250, Shurimon 225 | planted strides solved on the native legs (exact link lengths, the whole boot or claw mesh as support) under the native upper-body performance; Silphymon's walks also carry the upper body (pelvis bob, lean, torso counter-turn, arms against the legs) with strides as long as its boots |
| `fieldboxer.py`, `fieldstar.py`, `fieldsuperstar.py`, `fieldroll.py`, `fieldkoku.py` | BomberNanimon 232, Starmon 243, SuperStarmon 244, Togemon 208, Kokuwamon 247 | short one-link legs with rigid oversized boots that roll over their support vertices; body height follows the planted boot |
| `star_gait_refine.py` | Starmon 243 (SuperStarmon 244 by a rig dict) | offline model delta over the walk/run: ankles pushed out sideways so the boots clear each other, run pelvis pitch cut from 71-79 to about 36 degrees, ribbons hung down and back with a damped periodic pendulum lag; speeds and planting kept |
| `valkyrimon_limbs.py` | Valkyrimon 255 | offline model delta over the Angemon-transfer clips: limbs cleared of the body (elbow and hips turned a few degrees where the point-inside-mesh test fails), a calmer carriage (less bob and knee lift, relaxed delayed arms), legs kept apart, the left thigh's cloth hung from the pelvis, a breathing idle; timing, root travel and sounds unchanged |

| `saberleomon_gait.py` | SaberLeomon 258 (after the field pace pass) | legs re-timed through IK (lateral-sequence walk, bounding gallop with a flight phase), spine flex and bounce from foot support, delayed head share and bob, closed-loop trailing tail carried up in the run, forelegs set back 25 units, head carried by a fitted per-tick lift/pitch table so no leg triangle crosses the mane or jaw; cycle lengths, root travel, mesh and other programs exact |

| `taomon_arms.py` | Taomon 315 (after the chibi overlay, its `post_generator` stage) | turns the two sleeves' first bones (rotation only) tick by tick in the idle, walk, tired walk and run so no sleeve piece crosses a leg, apron or the tail; the turns (outward about the world's fore-aft axis, a swing back about the side axis on the run's raised knee) are the smallest clear ones, smoothed and periodic, stored in `content/models/imports/taomon-arms.json`; nothing else changes (`tools.test_taomon_arms`) |
| `okuwamon_limbs.py` | Okuwamon 259 | offline model delta: the idle kept as it was (clean limbs, closed-loop wings), the tired rest/walk/tired walk/run written as a four-legged diagonal gait solved per leg (planted flat feet, short steps for the 250-unit feet), pincers carried forward, a side-to-side waddle of pelvis, chest and pincers; cycles 20/10/12/8, root speeds 15/10/36 |
| `raremon_drag.py` | Raremon 264 | offline model delta: walk, tired walk and run rewritten as a drag-crawl (the idle and its alias stay); each arm is solved by two-bone IK (shoulder and elbow, no clamping) to a flat hand planted in the world during the pull while the hump surges forward on a von Mises burst of speed and the other arm reaches; lower body and tail lie on the floor as lagging springs, head and jaw follow late; cycles 16/24/12 (walk/tired walk/run), root speeds 15/10/35 |
| `skullmammothmon_clash.py` | SkullMammothmon 268 | offline model delta: walk, tired walk and run (slots 2, 3, 4, 36; 35 shares slot 2) with a per-tick neck pitch/lift and small shoulder/knee/ankle turns of the front legs so no front-leg triangle crosses the head, trunk or tusks; every other bone, timing and program unchanged, idle untouched |
| `octomon_scuttle.py` | Octomon 278 | offline model delta: idle (64 ticks, shared with slots 1, 18, 33), walk (16 ticks, 15 u/tick), tired walk (20, 10) and run (10, 35) as a tripod crawl of the six tentacles with planted tips (IK), a bobbing and swaying body and delayed arms; checked by `tools.test_octomon_scuttle` |
| `syakomon_hop.py` | Syakomon 283 | offline model delta: idle (96 ticks, shared with slots 1, 18, 33; breathing, mouth, fin), walk (28 ticks, 16 u/tick, planted hops), tired walk (36, 11, low dragging hops) and run (27, 38, bounds) of a legless clam: shell lowest point solved onto the floor, mouth and fin driven by damped springs; checked by `tools.test_syakomon_hop` |
| `apocalymon_float.py` | Apocalymon 400 | offline model delta: idle (120 ticks, shared with slots 1, 18, 33; slow hover), walk (60, 21 u/tick, hovering glide), tired walk (84, 13, low and sagging) and run (40, 44, forward surge) of a legless floater: the body and torso drive, the tentacle chains, cape and arms follow through damped springs, the body is raised wherever a tentacle ball would touch the floor, limbs move in two Euler channels to fit the resident buffer; checked by `tools.test_apocalymon_float` |
| `superstar_gait.py` | SuperStarmon 244 | offline model delta: Starmon's refined walk, tired walk and run on the larger body (translations times 1.75, cycles 22, 28 and 25 ticks for 19.5, 13.5 and 37.9 units a tick), idle with the arms hanging |
| `bearmon_gait.py` | Bearmon 353 | offline model delta (idle of 96 ticks with its alias, walk (20 ticks, 16 units/tick), tired walk (28, 10) and run (16, 36), each two cycles of 10, 14 and 8 ticks that differ slightly (leg lift, touchdown time) and are eased into each other. One gait phase drives the whole body (`quadruped.py` legs plus a hand-written body hook): hips turn against the chest, the chest rolls and shifts over the stance side, each hand swings against the leg on its side with forearm and mitt lagging, and the head, jaw and tail follow through springs. Cub personality: an exaggerated waddle (sway, roll, bounce), arms that swing wide and flop, a head that nods and tilts, a tail wag, a happy hop in one cycle and a stumble-recovery wobble in the other, a sleepy yawn and drooped head in the tired walk, and an idle with breath, weight shifts, looking round, an ear-flick head tilt, a tail-wag burst and a paw wave. Tests: `tools.test_bearmon_gait` |
| `veemon_gait.py` | Veemon 180 | overlay generator (`veemon-field`): idle of 96 ticks and the walk (12 ticks, two cycles, 16 units/tick), tired walk (18, 11) and run (8, 38), the battle idle 33 keeps the source game's own clip and the battle walk and run (35, 36) share the field clips. `quadruped.py` legs (planted soles, stance slip under 2 %) plus a body hook driven by one phase: hips against chest, weight over the stance leg, head late and tilting, wide arm swings against the leg on their side with the forearm and fist lagging, a three-segment tail wave, and cycle B with a happy skip; a loose second-order spring on arms, head, jaw and tail. Idle: breath, weight shifts, looking round, tail bursts, a bounce and fist pump and a stretch. Tired walk droops, run leans with big arm pumps. Cycle B is blended through rotation matrices (Euler branches of the legs differ). The run's soles stand 3 units higher (`sink`) because the 60 fps interpolation of a fast leg would dip under the floor; buffer 93,982 of 100,352 bytes (`tol` 3). The feet roll (toe-up touchdown, heel lifted at the push-off with the toes planted, toes curled in the swing; the run's roll is the curl only, its toe-off would add interpenetration) and the eyes blink through texture moves (`veemon_face.py`: eye block x 20-47, y 0-39, frames in spare texels; irregular blinks, a double one in the idle, heavy lids in the tired walk). Test `tools.test_veemon_gait`. |
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
Apocalymon's four clips (the same 105-tick wave in all of them) were later replaced by the floating clips of `apocalymon_float.py`, written over this post-pass's output.

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

Kyubimon uses native Garurumon's skeleton (26 bones, `CHDAT/MMD0/GARU.MMD`) at scale 1.0, bound by `native_binding.py`: its 26 bones
map by body part (face and ears onto the head, the three tail pairs onto the last two tail bones) and the recipe's `spread` puts the donor's joints on the
source's. The donor's own clips carry the techniques (slots 46 to 56, slot 57 plays 57). `kyubimon_donor_gait.py` (the recipe's `gait`) then writes the
idle, walk, condition walk and run again: the trunk, neck, head and tail chain are the donor's own clip, resampled and softened, a tail wave runs down the chain
with a lag, and the four legs are planted-paw solves from `quadruped.py` (40, 16, 22 and 14 ticks; 17.0, 11.5 and 40.0 units per tick). Stance slip is 18 %, 17 %
and 19 % mean (worst 36, 37 and 42 %), the lowest sole 2 units under the idle's floor. The resident model uses 95,352 of 100,352 bytes.

Minotarumon uses native Ogremon's skeleton (18 bones, `CHDAT/MMD1/OGRE.MMD`) and field programs at scale 0.88, bound by
`native_binding.py`: its 20 bones map by body part onto Ogremon's 18 (pieces 17, 19 and 20 onto the head, 5 and 6 onto one foot, 9 and 10 onto the other),
and pieces 6, 10, 19 and 20 share a donor bone and are placed by `pieces` offsets. Idle is Ogremon's own
16-tick loop; walk, condition walk and run are Ogremon's clips retimed by the recipe's `pace` with `ground` (22 ticks at 18.0,
30 at 13.0 and 20 at 41.0 units per tick). Stance slip is 38 %, 37 % and 28 % mean in the walk, condition walk and run (worst 212,
274 and 41 %). The 11 techniques play Ogremon's clips 46 to 56; slots 57, 58 and 60 play Ogremon's
clips 51, 49 and 46, and slot 33 the idle. The resident model uses 76,934 of 100,352 bytes.

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

SkullSatamon uses native Ogremon's skeleton (18 bones, `CHDAT/MMD1/OGRE.MMD`) at scale 1, bound by `native_binding.py`, with the
chibi row as the last stage of the binding (`"chibi"` in the recipe) so its proportions stay the ones pinned in
`chibi-proportions.json`. Ogremon has no wings, so both wings ride the donor's mane bone (4, a child of the head that swings
behind it): they lag the head in every clip and, as a bone of their own, stay out of the back (about 1,900 penetration counts in
the walk against 18,000 with the wings rigid on the torso). The cape's three pieces ride the pelvis bone, and the hip piece
rides the root, so the pelvis bone belongs to the cloth group and the chibi stage's shorter legs no longer sink it. The recipe
gives the head factor 1.6 and the hand factor 1.35, and the row's `fit` shortens the head bone to 0.7 along its axis so the head
comes out wider than tall (the pinned 0.376 wide against 0.267 tall). Walk and run are the donor's, retimed by `pace` with `ground`
(22 ticks at 30 and 20 ticks at 50 before the chibi stage, 21.6 and 36.0 units a tick after it); the tired walk is the donor's
own (24 ticks, 16.2). Stance slip is 27 % mean and 36 % max in the walk, 10 % and 21 % in the run, and 42 % and 103 % in the
tired walk (the donor's own stoop), above the usual target there. The walk's step turns 2.7 times the median step (the bar is
2.5). The resident model uses 85,256 of 100,352 bytes.

WarGrowlmon wears Growlmon's skeleton (25 bones) and field programs, bound by `native_binding.py` at scale 1.4 (recipe `326`; the donor is
another imported species, so the recipe names it with `donor_species` and pins its model by SHA-256: the binding reads Growlmon's model
from the imported base models, and a change to Growlmon's delta stops the build until the pin is renewed and WarGrowlmon's provider pin
is made again). The 26 mesh pieces map onto Growlmon's bones (the four back-whip pieces ride the upper body with the pods), so the walk,
tired walk and run are Growlmon's planted-foot clips (32 ticks at 16, 44 at 11, 28 at 36) and the idle is its 96-tick one; the technique
slots (14 of them) alias Growlmon's 46, 47 and 48 in the donor's order. Growlmon's blink is not carried (the binding drops texture moves, and WarGrowlmon's eyes are in
another atlas). The recipe's piece rules were found against the pinned chibi proportions: the four back-whip pieces keep the place of their own
source joint, the shoulders are spread 24 units apart so the armour clears the head, the foot pieces are lowered onto the floor and stretched
wider and longer without growing taller (`stretch`, an uneven scale along the world axes), the shin and thigh pieces are slid up their own
segments (the offsets in the recipe are those slides, resolved) so the knee mesh sits above the foot mesh, and the hand pieces are scaled to 0.9.
Proportions: head 0.358, head width 0.403, foot 1.001, hand 0.226, legs 0.370 (pins 0.363, 0.408, 1.001, 0.249, 0.366, inside the guard's
tolerance). The resident model uses 99,574 of 100,352 bytes.

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
Monmon 352 (`tools/models/field_animations/monmon_gait.py`, test `tools.test_monmon_gait`) had a walk, tired walk and run of one
43 to 45 tick cycle whose feet slid on the floor (stance slip up to 244 % of the body's speed on the walk, 231 % on the tired walk, 147 % on the run), the
import's rest pose having the left leg and arm posed differently from the right. The generator mirrors the right side onto the left (`rest_fix`, an
opt-in key of `quadruped.py`), plants each foot with the two-bone IK of `quadruped.py` (the knee forward, the ankle centred under the hip: the leg reaches
only 74 units) and writes the body by hand. The character is a playful little skipper: the walk is a skip (the second foot lands at 0.42 of the cycle, not 0.5, a long step and a short one, and the body
springs on every step, higher on one foot than the other: bob 9 plus an alternating 4), the run a bigger bouncing lope with a flight phase, the tired walk a droopy shuffle; in every clip the head tilts from side to side
(about 8 degrees each way, a cycle a tilt), looks a little about and nods, the hips and chest turn against each other, the gloves swing against the feet with the elbow and the glove lagging, and the leaf crown, the club and
the tail trail as second-order springs. Each walking clip is two different ground cycles (the second with the body terms scaled). The walk, tired walk and run are 24, 28 and 20 ticks (cycles of 12, 14 and 10: short, quick steps because the leg is short) at 16, 11 and 36 units a tick, the stance slip 5 % or less on average and
16 % at worst, the run on the ground for only 6 of 21 ticks. The idle is redone: a 60-tick (3 s) loop on planted feet, the head tilting from side to side with a dip, the weight shifting, the arms loose and the leaf crown, the club and the tail swaying.
The eyes are one ring painted on the head's texture (no eyelid or eye bone, and no separate geometry), so Monmon blinks through texture moves (`monmon_face.py`, as Salamon and Divermon do): a half-shut and a shut frame of the 16x16 eye block sit in row 80 of the texture (the model's rows 0-63 are unchanged) and the clips copy them over the eye; the same quad is drawn on both eyes, so both blink together. Every clip starts and ends open-eyed: the idle blinks once a loop (every 3 s) and so does the walk (every 1.2 s: it is a 24-tick clip, more often than the idle; two more cycles of it would cost about 4.5 KB of the 4.8 KB the resident buffer has left, so the blink stays once a loop), the tired walk blinks slowly and then droops half-shut for 8 ticks (a tired Monmon blinks often), and the 1 s run keeps its eyes open. The clips on other slots carry no eye moves, so an eye caught half-shut by a cut clip stays so until the next clip starts (not tested in the game). Against the import the belly and the legs overlap more (the legs fold under a ball belly: up to 98 and 104
triangles against 70 and 69 before, as deep as before) and the tilted head touches the gloves a few triangles more (14 and 12 against 6); the sum over all pairs fell from 398 to 347. 95526 of 100352 B resident. The test reads the model made by `tools/models/edit.py get 352` (`MONMON_MODEL`).
Gallantmon 318 (`tools/models/field_animations/gallantmon_gait.py`, test `tools.test_gallantmon_gait`) had a walk and tired walk whose feet barely
stood (stance 9 / 3 of 21 ticks, the soles slipping 80 % of the body's speed on average and 260 % at worst; tired walk 104 % / 163 %), a run that
averaged 53 units a tick (over the native 52) and stepped between 35 and 67 (stance 4 and 1 ticks of 17, slip 62 % / 84 %), and a walk whose root moved in uneven steps
(6 to 30). The generator plants each sole with `quadruped.py` (two-bone IK, the pole of the knee set outward 0.58 of its forward, the sole pivoting on the toe point)
and writes the body by hand: the pelvis and upper body yaw and roll against each other, the lance arm swings against the shield arm (the shield arm holds the
shield up as the body sinks so it never reaches the floor, and in the run swings it out clear of the legs), the pauldrons counter-turn, the plume and the cape trail late. The idle
is a 120-tick loop with the left foot back like the original stance (the chibi foot proportion measures both feet in the first idle frame). The walk, tired walk
and run are 24, 30 and 18 ticks at 16, 11 and 38 units a tick (constant root step, stance slip 5 % or less on average and 25 % at worst, the run airborne for a short
part of the cycle). Slots 33, 35 and 36 alias the new idle, walk and run; the old battle-movement programs 35 and 36 are dropped (96500 of 100352 B resident, from 94102).
The test reads the model made by `tools/models/edit.py get 318` (`GALLANTMON_MODEL`).

Growlmon 320 (`tools/models/field_animations/growlmon_gait.py`, test `tools.test_growlmon_gait`) had a walk, tired
walk and run that slid on the floor (the soles moved 98 % and 119 % of the body's travel in the walk and tired walk, 340 % at
worst) and threw the swinging feet 80 to 130 units up. The generator plants each foot with `quadruped.py` on the model's
own big-creature proportions (no overlay, no chibi reshape): the walk is 32 ticks (two different cycles of 16) at 16 units a
tick, the tired walk 44 (2 x 22) at 11, the run 28 (2 x 14) at 36, and the 96-tick idle keeps both feet planted. The
studio measures a stance slip of 3 to 7 % on average and 29 % at worst in the walk and tired walk and 27 % in the run
(the imported clips: 98 to 340 %); the soles stay within 4 units of the floor (7 in the run, whose feet move fast between
60 fps thirds, hence the profile's `floor` 9). The body is written by hand: the hips turn against the shoulders, the upper
body rolls over the loaded foot, the arms hang bent and swing late, the neck, head and jaw follow by a spring each and
the three-link tail trails a few ticks behind link by link. The character is a heavy brute: a slow wide plod, a low tired
drag with the head hung, a committed run with the jaw open and the tail streaming. The hind legs stand 20 units wide
and the left foot lands a tenth of a cycle after its turn in the run, which keeps the legs out of the hips (the imported
clips: 646 penetrating vertices over all pairs of parts, the new ones about 498). Growlmon also blinks
(`growlmon_face.py`): its eyes are painted in the head texture (no eyelid bone or piece), so frames of the open, half-shut and shut eye
are stamped into spare texels (rows 96 and below, 28x24 each at x 0, 28 and 56) and the clips paste them over the painted eye
with texture-move events through the profile's `events` hook, as Divermon does: the texture only, no mesh or skeleton change. The
idle blinks four times at irregular intervals (one quick double blink), the walk twice, the run once and the tired walk twice with
a slower, heavier blink; each plan ends with the open eye so the loop closes cleanly. Slot 36, a separate 21-tick copy of
the old run, plays the new run too (and the copy goes). The test reads the model made by
`tools/models/edit.py get 320` (`GROWLMON_MODEL`).

Maildramon 324 wears the native rig and programs of Unimon (a native binding, donor 33) reshaped by the chibi stage. The bound
clips kept the donor's lively trunk, wings and tail, but its legs slid over the floor (mean 68 % of the body's travel in the walk,
47 % tired, 95 % in the run, up to 257 / 159 / 400 %), the tired walk was as fast as the walk, the head hung forward with the horn
pointing back, the run's tail stuck up and the run jumped 3.4 times the usual step between two ticks. `maildramon_gait.py` is a
post-chibi stage (the recipe key `gait` in `native-bindings.json`, run after `chibi` and before `spin`, off for every other species)
that writes slots 2, 3 and 4 again: the trunk, neck, wings and tail are the donor's own clip resampled to a new cycle (a four-beat walk of 16
ticks at 16 units per tick, tired 20 at 10.5, a rotary gallop of 12 at 37 with a flight phase), their bob, wing, neck and tail swing toned down (calm, weighted, not frantic), the head and tail
carriage corrected, a neck nod, spine flex and tail stream added that follow the stride; the legs come from `quadruped.py` (profile key `claws` folds each foot's claw bone into its foot piece so
the claws land flat). Measured on the sole of each foot (mean / worst % of the body's travel): walk 11 / 14, tired 13 / 27, run
10 / 13; the largest step between ticks 1.5 times the median (run 1.2); the footsteps stay on the new touchdowns; the resident buffer
is 98322 B of 100352. The idle (slot 0, so the chibi pins) and the technique slots are the donor's and unchanged. The test is
`tools.test_maildramon_gait` (`MAILDRAMON_MODELS`).
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
Snatchmon (331) keeps its chibi-reshaped idle byte for byte and gets a light touch-up of the walk, tired walk and run (same 16 ticks, root travel, rhythm and
silhouette; `field_animations/snatchmon_polish.py`). The import's upper arms were static and its stance feet hovered above the floor and crept over it; the
tired walk was a deep hunch and the run a long low stretch with the hind legs close together. Each stance is now planted (the ball of the foot stays over its touchdown
spot and a hovering sole is lowered to the floor, as for Hookmon) and the footstep sounds sit on the touchdowns. The upper arms swing against the hind leg
of their side (about 16, 8 and 24 degrees in the walk, tired walk and run), the head, arms and chain trail the trunk a tick late, the trunk lifts a little
(the run by 20 degrees) and the run pulls in the hind foot's long kick back. Pelvis, legs and tail do not move with the trunk edit (bones 1 and 2 turn about
one origin). Checked by `tools.test_snatchmon_polish`.
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

Sakuyamon (316) has its legs put back on two lanes in the walk, tired walk and run (`field_animations/sakuyamon_gait.py`, shipped as the model delta; every other program
and every non-leg, non-hair channel are the import's byte for byte, and the root motion, stride, lift and timing too). The import maps Angemon's gait, whose hips
and feet sit 130-160 units apart, onto hips 33 apart: the knees closed to 41 (52 at rest; 32 in the run), the ankles crossed the body's midline in their lane (the feet's
meshes overlapped sideways by up to 20 units and the toes by 33, against a clear 14 and 48 at rest), up to 48 vertices of one shin or foot were inside the other leg, and each foot turned in to
about -10 degrees from the idle's toe-out of 30, so it looked knock-kneed and pigeon-toed. Each tick now keeps the ankle's height and fore-aft position and takes its sideways place
on a fixed lane (42 units either side of the centre line, 44 in the run), solved by position with the knee pointing forward and a little outwards in the pelvis' frame and the idle's
bend plane as the twist; the body sinks where a planted leg would be over-straight (3.6 units at most, a tent of 1.5 units a tick) rather than the foot moving in; the foot is turned back to a
toe-out of 14-16 degrees plus a quarter of the import's own foot swing. Now the feet are 7-28 units clear sideways (4 for the toes in the run: -2) and the legs never touch (0 vertices inside), the knees are 59-82 apart, and the
thigh and shin turn at most 32 degrees a tick (41 in the import) with no 90 degree twist flips. The import's stance slip (28-79 % mean by the foot bones' paths) is not changed.

Its run stands up (`field_animations/sakuyamon_posture.py`, a step between the leg gait and the hair): the import leans the chest 39 degrees forward (bone 1) while the pelvis and the head turn back by almost as much, so the legs and the head keep straight and the shoulders ride up, a hump (the spine from the pelvis to the middle of the shoulders leans 14..27 degrees forward, the pelvis-to-head line 20..34). Each tick the chest's forward lean over the idle's is cut to 30 % of itself (about 12 degrees), a turn about the shared pivot that the pelvis and the head take back in front of their own rotation, so the pelvis, the legs, the feet and the head keep exactly their world orientation (the leg gait is byte for byte the same) and only the chest, shoulders, arms and staff stand up: the spine now leans -4..-2 and the head line 2..5, the walk's being -13..-9 and -7..-2. The chest's own sway and the timing are the import's.

Its hair (bones 15 the cap, 16 the mass down the back, 17 and 18 the two long locks; `field_animations/sakuyamon_hair.py`, the last step, on the posture step's output) swung in one spring-like sway on every clip written without a look at the body, with the mass rooted inside the chest's upper back (with the chest leaning 39 degrees in the run the back rises into the hair): the hair's vertices inside the body were up to 32 in the idle, 22 in the walk, 25 in the tired walk and 183 in the run (122 in the chest, 31 in the arms, 37 in the legs, 7 in the staff; 203 after the lane change, which put 59 in the legs). Per tick the root of the mass is now shifted back along the chest's back (20-28 units in the idle and walks, up to 52 in the run, in whole units of its own frame) and, where needed, the mass and each lock are turned back a few degrees, the least that clears the chest, pelvis, legs, arms and staff, with the requirement widened by two ticks and filtered over the loop (so the hair moves back smoothly and early) plus a margin. Left: the cap's corners on the shoulders (3 vertices each side in every tick, the import's too) and, in the run, an arm swung back into the hair (at most 5; 6 vertices in all). The leg gait, the root motion and the other programs are untouched (`tools.test_sakuyamon_gait` pins them and bounds the hair and the run's lean per tick).
Musyamon (325) has its walk, tired walk and run stood up and its mane kept off its cape (`field_animations/musyamon_posture.py`, then `field_animations/musyamon_hair.py` on its output; shipped as the model delta; the legs, arms, root motion, speeds and every other program are the import's, `tools.test_musyamon_gait` pins them). The import leans the chest 22-40 degrees forward (bone 1) with the head 14-37 degrees (bone 23) on top of it, so it walked hunched with the head down (the spine from the pelvis to the head 39-59 degrees forward). Each tick the chest's lean over the idle's is cut by about half and the head takes its own inverse turn so it looks ahead (chest 7-25, head 3-17, spine 24-43 degrees in the three clips; the run's head reaches -0.2); the pelvis and the cape bones (17, 25, 26, 27) keep their world orientation, so the legs, soles and slip are byte for byte the same. The mane (bone 24, rigid on the head in every clip) crossed the cape and the chest's back (66-152 triangle pairs with the cape and 42-134 with the back per tick; in the idle 94-118 and 62-84). Per tick bone 24 is moved the least that leaves the fewest crossings with the cape, back, shoulders and arms (up to 30 units up and a few degrees), filtered over the closed loop; the back and arms are now clear (0 pairs, 8 at most in one walk tick) and the cape crossings are 22-72 per tick, almost all the right spike beside the head (bone 27), which the mane rests against. Left: that spike, and the head-to-mane overlap grows (36-52 pairs against 20) because the mane sits higher and further back on the head. The tired walk's sword now touches the legs in some ticks (at most 21 pairs, 0 before) and the cape the legs about as before.

BlackWarGreymon 404 (`tools/models/field_animations/blackwargreymon_gait.py`, test `tools.test_blackwargreymon_gait`) walks on the same
skeleton idea as WarGreymon 373: two legs with planted soles from `quadruped.py`, the torso (bone 1) as the pelvis and the waist (bone 2) as the chest,
a chest that counter-turns against the hips, arms that swing against their own leg with the claws trailing, wings and thigh plates on springs.
Its foot has a claw fan about 100 units ahead of the ball, so the sole pivot is the claw tips (`claws` in the profile) and the stance
is shifted back (`reach`). It is a baked delta (no overlay): the generator reads the stored model (pinned by SHA-256). The four clips are
96 (idle), 44 (walk, two cycles of 22), 28 (tired) and 24 (run, two cycles of 12) ticks at 16, 10 and 40 units a tick (before: 17.8, 12.1 and
42.1 at 107, 21, 25 and 13 ticks); the planted claws slip 5 % at most in the three gaits (before 75 to 87 % as the studio reads the two
ground markers, bones 22 and 23, which now follow the claw fans instead of the torso) and the lowest sole is 0.2 to 1.6 units above the floor (before -1 to 0).
Parts touch a little more than before (the head and the right arm 24 triangles, the left arm in the head 48 against 32, a leg in the
torso 58 against 47 in the run). The resident model uses 81,664 of 100,352 bytes.

Omnimon 461 (`tools/models/field_animations/omnimon_gait.py`, test `tools.test_omnimon_gait`) kept its feet and loosened everything above the hips.
Its walk, tired walk and run were one short cycle of plain sines (a chest turning a clean 10 degrees, a head that hardly moved, two arms
swinging as mirror images, a cape moving 4 to 10 degrees, a run that leaned no more than the walk). The pelvis, both legs and the root
motion are byte for byte the stored ones (speeds 16.1, 11.0 and 38.1, slip and soles as before); the three gaits are now two cycles that
differ (40, 48 and 24 ticks): the chest sinks and nods after each landing (the first of the pair heavier) and trails the hips on a spring,
the head takes part of the chest's turn late and nods against the landings, the arms swing behind the legs with a lag and an overshoot,
the forearms later, with different gains per cycle and side, and the cape streams with the speed, swings against the chest and flutters on two
slow waves, its tail later than its base; the tired walk slumps (chest 6.5 and head 9 degrees forward) and the run leans 7.5 degrees.
Hands and arm plates are kept 3 units over the floor by turning the shoulder the least needed (the lean put the cannon hand under it).
The idle gets a slow breath and a cape drift. Baked delta (the generator reads the stored model, pinned by SHA-256); resident 90,074 of 100,352 bytes.

Dinohyumon 308 (`tools/models/field_animations/dinohyumon_gait.py`, test `tools.test_dinohyumon_gait`) had clips whose
feet flipped (toe yaw up to 167 degrees), a tired walk that slid its soles (172 % mean, 446 % worst), only one to four
ticks of stance in 17, uneven root steps and a run whose arms hardly moved. The overlay runs the chibi reshape and then
plants each foot with `quadruped.py`: walk, tired walk and run are 32, 60 and 28 ticks (two cycles, the second with other leg lifts, heel strikes, landing times and bob, eased into and out of the first so no step repeats; arms, head, feather and loincloth follow the body on loose springs) at 17, 11 and 38 units a tick
(slip under 4 % mean), the idle 96 ticks with breathing, weight shifts and a raised arm. The posture is a low, forward-leaning warrior's: short weighted steps, the chest turning hard against the hips, the arms bent and held out of lockstep with the legs, a hunched dragging tired walk with the head low, a committed forward-leaning run. The pelvis bobs twice a cycle
and the arms and feather follow with delay. The run's loincloth overlaps a leg slightly more than before (14 against 8).

Pichimon (471, a hand-made baby) no longer plays Koromon's lunge: a 40 % squash and a 59-unit leap every 18 ticks, the tired walk
as fast as the walk (20.5 against 20.9 units a tick) and a slip of 124 % mean, 225 % worst. `pichimon_hop.py` writes slots 0, 2, 3
and 4: a 96-tick idle (two breaths of about 8 % squash, slow looks to each side, three blinks about 32 ticks apart, the feelers trailing), a walk of two
22-tick hops at 16 units per tick (14 high), a tired walk of two 30-tick hops at 11 (5 high, leaning forward, drooping feelers
eyes) and a run of three 16-tick hops at 38 (24 high). The squash is 0.84 to 1.08, the feelers lag the body. The face blinks through texture moves (the closed-eye frame at (54, 0), a half-lid frame on each side of it, shut for 4 ticks, 6 with the lids): three times a loop in the idle, once in the walk, twice in the tired walk, never in the run; every clip starts and ends on its own base eye. The body stays where it lands
while it is down and its lowest point is solved every tick: slip 0 % mean and worst on the three gaits, the lowest sole 0. The little arms (the two pectoral fins) used to be part of the body object, so they could not move on their own. The twelve fin quads now sit in the two
objects that were empty (the feeler-tip bones, 4 and 6), their vertices and normals expressed in that bone's rest frame, so the rest pose is vertex for vertex
the old one (the six degenerate points of the empty objects are gone). Each tick the tip bone is solved as `inverse(feeler base) . fin motion . rest offset`, so the fin turns
about its shoulder whatever the feeler does: a damped spring follows the hop height and squash, so the arms lag the body and overshoot on a landing, rest
in a slow sway in the idle, hang low and nearly still in the tired walk and stream back in the run (the tip travels 20 units in the walk, 15 in the run, 12 in the
idle, 8 tired). The feelers keep their own motion on bones 3 and 5 (the tip bending was dropped). The stored
model grows from 43 to 56 KB (animation and the fin split; resident 50.6 KB of 100 KB). The test is `tools.test_pichimon_hop`.

Motimon (474, a hand-made baby) no longer plays Koromon's lunge: a 40 % squash and a 59-unit leap every 18 ticks (the body rose 80, 52 and 160 units in the
walk, tired walk and run), a tired walk as fast as the walk (20.5 against 20.9 units a tick), a slip of 124 % mean and 225 % worst, soles up to 15 units under the floor,
and arms and eyes that never moved. `baby_calm.py` writes slots 0, 2, 3 and 4: a 128-tick idle (two slow breaths, a slow look to each side, the arms drifting a little
behind the breath, four blinks at uneven intervals, one of them a double blink), a walk of two 22-tick hops at 16 units a tick (6 units of flight, a 4.5-degree waddle), a tired walk of two
30-tick hops at 11 (2.5 units, leaning forward, lids half down, one slow blink) and a run of three 15-tick hops at 37 (9 units). The body rises 17, 13 and 24 units (squash included) against 80, 52 and 160.
Slip is 0 % mean and worst in the walk, 9 % in the tired walk, 1 % mean and 3 % worst in the run; the lowest sole is 0 in every clip. The little arms were two 66-primitive cones inside the body object. They now sit
in the two empty objects of the bones 4 and 6 (vertices in the bone's rest frame, so the mesh is vertex for vertex the old one; the old rest pose had one arm stretched out and the other raised like an ear, so every clip first turns both to hang relaxed below their shoulders, about 40 degrees under the horizontal, and swings them about that), and every tick the bone is solved as
`inverse(ear base) . arm motion . rest offset`, so each arm turns about its own shoulder (the arm tip travels 16 units in the idle, 24 in the walk, 11 tired, 22 in the run) behind a damped spring that
lags the hop and overshoots a little on a landing, alternating from one hop to the next. The blink is a texture copy: the donor's closed-eye frame at (34, 0), with a half-closed lid frame either side that
the texture did not have: it is drawn into the unused block at (44, 32) (the open eye squashed to its lower half), copied in two rects because the last four rows of that block belong to the arm patch. The
stored model grows from 33.8 to 42.7 KB (resident 38.2 KB of 100 KB). The test is `tools.test_baby_calm`.

Bukamon (475) gets the same treatment from the same generator (its flippers already sat on the objects of bones 3 and 5, so those bones turn about the shoulder; the
flipper tip travels 16, 30, 10 and 24 units in the four clips): the old clips left the soles 7 to 11 units under the floor, and the lowest sole is now 0. Its blink uses the donor's half-lid frame at (24, 0)
and the closed-eye frame at (34, 0), and the tired walk keeps the half-lid frame as its base eye. The model grows from 31.6 to 38.7 KB (resident 34.4 KB). Both babies share the clips' structure and differ
in their numbers (`CONFIGS` in the module).

Kyukimon 322 (`tools/models/field_animations/kyukimon_gait.py`, test `tools.test_kyukimon_gait`): the walk (80 ticks), tired walk (72) and run (72)
only rewrote the legs; every bone above the hips (body, chest, shoulders, arms, the five tail segments) played the idle's 74-tick loop, copied
(equal rotation ranges to a tenth of a degree), and head, hands, strap and wing spikes never moved, so the upper body neither moved much nor
belonged to the stride. The legs slid their soles 28 / 20 / 49 % of the travel on average (136 / 72 / 180 % worst) with a lift of 13 units. Now
one gait phase writes everything: planted feet (slip under 3 % mean in the studio's measure), hips against body against chest, arms against legs,
head steadying and late, a wave down the tail, trailing strap and wing spikes; the clips are two cycles each (32, 44, 28 ticks, 18 / 13 / 36
units a tick), cycle B unlike A, with loose springs on the upper bones. The idle is unchanged.

Mummymon 334 (`tools/models/field_animations/mummymon_gait.py`, test `tools.test_mummymon_gait`): the chibi build's walk, tired walk and run
were 16-tick loops whose soles slid 65 %, 202 % and 95 % of the travel (458 % worst in the tired walk), at 16.6, 14.7 and 36.9 units a tick (the tired walk
nearly as fast as the walk), with the rifle arm swinging the gun under the floor. The overlay runs the chibi reshape and then plants each foot with
`quadruped.py` (sole pivot at the ball of the foot): walk, tired walk and run are 30, 40 and 28 ticks, two cycles each with other lifts, heel strikes and
bob eased into one another, at 16, 11 and 38 units a tick (slip 2 to 4 % mean, 17 % worst), the pelvis tilting against the stride, the chest turning
against the hips, and the arms, head, hat, strips and rifle following on loose springs. The tired walk is a low, dragging one with the head down; the run
leans forward with the hind feet lifting to different heights. The rifle arm is carried bent (16 to 32 degrees extra elbow) so the gun stays above the floor
instead of being slung. The idle was not changed. The resident buffer is about 98.3 KB of 100.35 KB, so the clips use a per-bone encoding tolerance
(`tol` in the profile) and there is little room left for more ticks.

MegaGargomon 335 (`tools/models/field_animations/megagargomon_gait.py`, test `tools.test_megagargomon_gait`, `MEGAGARGOMON_MODEL`) moved like a
machine: walk, tired walk and run were one clip at three lengths, only the legs (46 to 49 degrees) and the upper arms (32 degrees, both
alike) turned, while torso, hips, cannons, forearms, fists, head and fins stayed at 0 degrees, the body bobbed 3 units, the tired walk
ran below the native range (8.6 units a tick) and the feet slid 35 to 95 % of the travel. The celebrations' base generator is now this module:
it runs the chibi reshape and writes slots 0 (also 1, 18 and 33), 2, 3 and 4 with `quadruped.py` on the two legs (flat feet, the ankle
under the hip): an 80-tick idle (breathing, weight shift, a look, a raised hand) and walk, tired walk and run of two different cycles
(20, 24 and 20 ticks each) at 17, 11 and 36 units a tick. The hips turn and roll against a counter-turning torso, the body sinks into
each footfall and rises slower, and the cannons, arms (upper arm, forearm, fist, each later than the last), head, face plate, fins and
hip flaps follow on loose springs. Foot slip in the studio: 6 to 10 % mean, 41 % at worst (run). `quadruped.py` takes a per-gait `clear`
(the floor margin of the 60 fps check; the fast run needs 7) and the profile an optional `tol` (encoder tolerance, per bone) to fit the
resident buffer. The pairs of parts that cross by mesh clash are listed in the test; the legs against the hips and the hip flaps against the legs
cross a little more than before.

Kotemon 351 (`tools/models/field_animations/kotemon_gait.py`, test `tools.test_kotemon_gait`): the donor's walk, tired walk and
run slid the soles (46, 129 and 48-59 % mean, up to 278 %), turned the claw plate 285 degrees and the foot block 143 degrees in a
cycle, and the upper body hardly moved. The legs are very short (the hip is 51 above the floor, the thigh link 20, the foot long),
so a foot cannot stride far from the hip: the steps are short and quick (a step every 6.5, 7.5 and 5.5 ticks in the walk, tired walk
and run) and each foot is placed first (flat on the floor, a small heel strike and peel, then a swing eased in the world). The
thigh stub stays under the skirt: it slides 3, 4 and 10 units at most (x, y, z) and the leg turns (up to 40 degrees, 60 in the run)
to reach the foot, so the stub's mesh stays within 11 units of the skirt's footprint (an earlier version slid it 40 to 70 units and
up into the torso, and the legs came out of the body; `test_the_legs_stay_attached_under_the_skirt` guards it). Walk, tired walk
and run are 26, 30 and 22 ticks (two cycles, the second with other touchdown times, stance lengths and bob) at 16, 11 and 36 units a
tick; the skirt and torso turn against each other, the head and the two shoulder plates follow on springs, and the tail trails.
Both hands hold the shinai, so the shoulders move as one rigid unit about the grip. The upper body bounces on each beat: the skirt, torso, head and shinai ride a spring that is kicked by a rectified sine
(`hop`, 5-6 units in the walk, 2 in the tired walk, 8 in the run), so the body lands and rebounds on every step, while the
hips and legs keep their height; the skirt rises and falls 10 units in the walk, 6 in the tired walk and 13 in the run and the head 5 to 10. The test `test_the_walk_and_run_bounce_and_the_tired_walk_bounces_less` guards the amplitudes
and that the arc stays smooth. Slip: walk 6-13 % mean and 40 % worst, tired walk
2-7 % and 29 %, run 8-13 % and 20 % (studio metric). The feet lift 15 to 20 units (the donor's 31 to 54: short legs cannot kick higher). The feet carry weight: the outer edge lands first and settles, the toe pushes off and the foot flexes up to land heel first, the claw plate trails; the two feet and the two cycles lift and time a little differently; every touchdown presses the hips down and over the landing foot (`squash`, `sway`) and the skirt follows on its spring. The stances are shorter than before (duty 0.22, 0.24 and 0.08 of a step): the leg is only 20 long, so the ankle can stay under the hip for about three ticks, and a planted foot kept longer was dragged along at body speed. The idle is
unchanged. The recipe keeps the overlay's hit-clip and hidden-sword repairs.

WarGreymon 373 (`tools/models/field_animations/wargreymon_gait.py`, test `tools.test_wargreymon_gait`) walked like a
wind-up toy: `war_greymon.py` wrote one 22-tick cycle of plain sines of a single phase (the arms two mirrored 34 degree
pendulums locked to the legs, a bob with a fourth-harmonic spring, the chest and head only counter-pitching, the back plates
under a degree, an idle of 1 to 2 degrees) and every step repeated the last. The overlay runs the chibi reshape and then
`quadruped.py` on the two legs with a body hook driven by one shared gait phase: the pelvis drops onto the loaded foot and
shifts over it, the hips and chest counter-turn (yaw, roll, lean) with the chest lagging, the head holds its gaze and
follows late, each arm swings against its own leg from the shoulder with the claw trailing and bending at the elbow, the back
plates lift and settle after the chest, and the loincloth and thigh plates follow the thighs. Springs (`FOLLOW`) give the claws,
head, plates and cloth their follow-through. The walk and the run are two different cycles each (44 and 24 ticks: other
lifts, landings, settle and bob) that ease from one into the other; the tired walk is one slumped, heavy cycle of 28 ticks
(the right leg lands late and lifts less); the run leans into a flight phase; the idle (96 ticks) breathes,
shifts its weight, glances and raises a claw. Before / after: ticks idle, walk, tired walk, run 73, 23, 21, 13 / 96, 44, 28, 24;
root speeds 17.2, 13.6, 40.8 / 16, 10, 40 units a tick (a constant step); stance slip 9-72 % mean-worst on the walk, 13-109 % on
the tired walk, 5-6 % on the run / 5.7-14 %, 4.8-15 %, 4.9-15 %; resident buffer 98486 bytes. Mesh crossings stay within the
chibi clips' on arms against head, torso and legs (and drop a lot on the arms against the head); the head against the chest
(37 triangles before) rises to 40 to 49 and a thigh plate against its leg (22 before) to 48 on the tired walk, both shallow.
This is a hand-built overlay, not a native donor binding; the chibi row (`chibi.json` 373) is applied first and its
proportions are unchanged. The battle idle (slot 33) is the source game's own 73-tick clip again, not the field idle: its deep
crouch put the still hip plates through the raised thighs (156 crossings a tick against main's 40) and the chest 28 degrees
over the field idle's, so `battle_idle` lets the hip plates take their thigh's turn, gives the back plates the field idle's
and leans the chest back 5 degrees (`battle_qa.py` lists the slot as polished); it then passes. Slot 34 keeps main's clip:
the source's own crosses the claws through each other (362 a tick against main's 74). The extra program would leave no
room for Buster Dive's dash (slot 0x35, `buster_dive.py` keeps the plain clip when the resident buffer would overflow), so
the overlay encodes the care, condition and technique clips again exactly (`battle_restore.compact`, tolerance 0):
resident buffer 98138 bytes with the dash.

Taomon (315): the walk, tired walk and run held both arms in the idle's hanging pose while the torso leans 40 to 80 degrees and the legs swing, so
the wide sleeves hung at thigh height and each leg passed through its sleeve at every step (up to 30 units deep; the aprons and, in the tired walk, the
tail crossed them too, and the idle's right sleeve brushed the leg for a dozen ticks). `field_animations/taomon_arms.py` runs on the chibi overlay's output
(the manifest row's `post_generator`) and rewrites only the rotation of the two sleeves' first bones (20 and 25), per tick, in slots 0 (shared with 33),
2, 3 and 4: a turn outward (22 degrees at most, about 23 on the run) and, on the run's raised-knee ticks, a swing back (about 11 degrees at most). Every
tick is checked by mesh clash and by vertex votes. Left over on the run: where the leaning torso puts the shoulder inside the thigh's top (bone 3 or 11)
no sleeve turn can clear it, so there the sleeve only keeps out of the leg no deeper than before; the run's sleeve-leg pairs fell from 486 to 72 and the deepest
overlap from 30 to 16 units. `python3 -m tools.models.field_animations.taomon_arms --source CHIBI_OUTPUT.MMD --search TURNS.json` finds the turns
(about two minutes), `--out AFTER.MMD` applies them. Speeds, ticks, feet, root, proportions and the other programs are the overlay's, to the byte.

Pharaohmon 319 (`tools/models/field_animations/pharaohmon_gait.py`, test `tools.test_pharaohmon_gait`): the chibi build kept
the import's tired walk and run, retargeted. The tired walk slid its soles 138 % of the travel (466 % at worst), leaning
the head 16 to 37 degrees past the idle's stance; the run threw the torso up to 65 degrees forward with the feet folded
behind it and on the floor for one or two ticks of 24. The overlay runs the celebrations recipe (and so the chibi reshape)
and then writes only slots 3 and 4 with `quadruped.py` on the two legs: the idle and the walk (slot 2) stay byte for byte
(the test compares every other slot's program). Tired walk: 56 ticks (two different cycles of 28) at 11 units a tick,
run: 24 ticks (two of 12) at 36, both with planted soles (slip 2 to 5 % mean, 8 to 18 % worst in the studio's measure) and the cycle B
lifting, bobbing and swinging unlike cycle A. The legs are almost straight at rest (198 units long, the hip 192 above the
ankle), so a flat-footed stride must be bought with a crouch and the heel peel: the pelvis moves about 45 units peak to peak in the tired walk
(`peel` -8 degrees, a low rounded foot lift of 26 to 28 units over 8 ticks, no toe kick) and 23 in the run. A late `arc` of 1.2 keeps the landing foot's slowing out of the studio's lowest quarter of
its lift (it counted as sliding). The posture follows the walk: a modest lean (head over hips: tired 9 to 15 degrees,
run 17 to 22, the walk 0 to 17), the head hung when tired, the arms swung clear of the thighs (negative `arm_out`, the old ones lay inside them) as delayed pendulums
with the forearm and fist later each, the cape and the loincloth trailing, everything above the legs on loose springs.

Knightmon 321 (`tools/models/field_animations/knightmon_gait.py`, test `tools.test_knightmon_gait`) limped in the tired walk
and ran unevenly: the left foot stood 10 ticks of 23 sliding 79 % (worst 120 %) and lifted 74 units, the right one stood 5
and lifted 58; the run (17 ticks) slid its feet 61 and 26 % (worst 203 %), the root step went 26 to 50 units, and the
joint curves had spikes of 50 to 240 times their median second difference. The base generator of its celebration overlay
now runs the chibi reshape and plants each foot with `quadruped.py`: tired walk 22 ticks at 11.5 units (the two feet's
heights within 5 % half a cycle apart, stance 11 and 11 ticks, lift 26 units, slip 5 %), run 16 ticks at 38 (stance 6 and 6,
lift 55, slip under 1 %), constant root speed, the head hung in the tired walk, the sword arm swinging half as much as the
free arm so the giant sword moves through 13 degrees of pitch (tired walk) and 22 (run) instead of 17 and 75. Idle, walk and
the celebration slots are unchanged. Slightly worse than before: the thigh and hip plates overlap the torso a few vertices more
(19 against 6 in the tired walk).

Lynxmon 323 (`tools/models/field_animations/lynxmon_gait.py`, test `tools.test_lynxmon_gait`) had a walk, tired walk and run in which
the four legs could not be told apart from each other or from the body. The texture paints legs, body and tufts with the same flame
pattern, so only the silhouette and the open floor under the belly can separate the limbs, and the imported clips threw both away:
the paws swung 146 to 263 units up into a belly 165 units over the floor, the feet came in towards the midline (fore paws from x 209
at rest to 95-164, hind paws from 140 to 74-155) so near and far legs and fore and hind legs stood on the same ground, the cycles were
16, 16 and 14 ticks, the soles slid (46 % of the body's travel at worst, 115 % in the run) and the tired walk and the run were faster
than any native partner (23.6 and 69.4 units a tick). The generator plants each paw with `quadruped.py` (opt-in profile key
`mirror_paws`: the left paws take the mirror of the right ones' rest rotation, because this rig's idle frame is not symmetric) and
keeps the limbs apart in the picture: a lateral-sequence walk, a low swing that stays under the belly (paw heights 40 to 95 units over the floor, 125 in
the run), a stance that stays about as wide as the rest pose (the paws stand 184 to 197 units out for the fore pair and 129 to 143 for the hind pair, against 209 to 212 and 134 to 140 at rest; the fore paws stand 41 to 65 units outside the hind ones and clear of them mostly along the body, 99 to 184 units apart) and a rotary
lope for the run. The walk is 36 ticks (two different cycles of 18) at 26 units a tick, the tired walk 48 (2 x 24) at 15, the run 32
(2 x 16) at 46; the idle is untouched. The body is written by hand (chest roll and bob, hips against the shoulders, a neck, head,
jaw and two-link tail that follow by a spring each). The studio measures a stance slip of 11 % on average and 26 % at worst in the walks and 11 % on average and 35 % at worst in the run (the imported clips: up to 46 % and 115 %). Parts penetrate (vertices and triangle centres inside another part, worst tick of each pair) 736 times over all pairs in the imported clips and 387 in the new ones, less in every pair but three: the left foreleg against the left hind leg (3 to 12; the idle already has 12 there and the run 11, the walk 6), the left foreleg against the left hind leg the other way round (6 to 8) and the head against the left arm (5 to 7). In triangle crossings (`meshclash.py`) the walk goes from 1464 to 543, the tired walk from 935 to 411 and the run from 810 to 643, with a few pairs slightly higher (the right foreleg against the right hind leg in the run, 91 to 94).
Nothing but the clips changes: the mesh and texture are exact and the species has no chibi row. The test reads the model made by
`tools/models/edit.py get 323` (`LYNXMON_MODEL`).
Gargoylemon 327 (`tools/models/field_animations/gargoylemon_gait.py`, test `tools.test_gargoylemon_gait`) had clips whose soles
slid (64-94 % mean, 121-236 % worst), feet lifted about 100 units, a tired walk almost as fast as the walk (19 against 21 units
a tick) and a slot 33 that was a separate copy of the old idle. The overlay runs the chibi reshape and then plants each hind foot
with `quadruped.py`: walk, tired walk and run are 36, 52 and 24 ticks (two cycles each, the second with other lifts, heel strikes
and landing times) at 16, 10 and 36 units a tick (slip under 6 %), the idle 120 ticks. The hips must stay up: a crouch deeper than
about 12 units (walk and tired) or 14 (run) leaves no room to fold a leg under the hip and the soles sink below the floor.
The hind track is 72 units in the moving gaits (44 in the idle) so the swinging thigh clears the tail root. Penetration against
the chibi clips is not met everywhere: the walk's thigh still grazes the tail root for 1-3 ticks per step (4 crossings, depth
11-21; none before), the run's head touches the forearms (3 crossings, depth 3) and the torso overlaps the legs by 2 more
crossings than the chibi pose (18 against 15-16); the test's bounds record those numbers. Each wing is a single bone, so the beat
follows the body with a spring but its tip cannot lag.
Ghoulmon 329 (`tools/models/field_animations/ghoulmon_gait.py`, test `tools.test_ghoulmon_gait`) had a walk, tired walk and run of 71 ticks
like its idle, written from another Digimon's rig: the feet lifted 27 units, the soles slid 37-44 % of the travel (207 % at worst) and the
stills looked like the idle, with legs that read as mechanical and an upper body that did not move. `quadruped.py` now plants each foot
(two-bone IK, heel strike and toe-off, flat soles) and `body` writes the rest as one overlapped motion: the pelvis bobs twice a cycle and
sways over the loaded foot, the hips turn against the torso, which rolls and pitches a little later, each arm swings against the leg on its
side with forearm, hand and claws each later, the wing membranes flap at each push-off and fold at each landing, and the three tail links
whip behind. Walk 26 ticks at 17 units a tick, tired walk 34 at 11 (slumped, arms low, wings drooping, tail dragging, torso leaning 14
degrees), run 14 at 38 with a flight phase and the wings streaming; slip under 3 % mean. The arms roll inwards about 12 degrees (an
outward roll put them through the legs) and the wing roots stay put (turning them put the wings through the body): the clips cross no
more mesh than the rest pose does. The idle is kept. No footstep sounds (the imported clips had none).

Bearmon 353 (`tools/models/field_animations/bearmon_gait.py`, test `tools.test_bearmon_gait`) read as robotic with the upper body
detached from the legs: in the imported walk, tired walk and run both arms, the jaw and the tail did not move at all, the head
only copied the chest's pitch (and was dead in the run), the hips copied the chest's yaw and roll, and the legs were overdriven
(thighs swinging about 112 degrees, shins folding 120 to 150) so the feet slid (mean 47 / 111 / 59 percent of the root speed in
the walk / tired walk / run, worst 98 / 277 / 123). The module builds the three clips with `quadruped.py` on one gait phase:
legs planted (slip 1 to 2 percent mean, worst 18 percent), hips counter-rotating the chest, chest roll and sideways shift over
the stance foot, each hand swinging against the leg on its side, and head, jaw and tail on springs. The leg cannot reach past
about 45 degrees around the hip without its shin block going through the floor, so the cycles are short (10, 14 and 8 ticks, run
at duty 0.30) and a second cycle with other lifts and touchdown times is eased in to avoid a metronome. Interpenetration is lower in total than the
import's (343 / 485 / 565 / 481 triangle hits to 340 / 402 / 448 / 473 in the idle / walk / tired / run) but a few pairs are slightly higher
(arm_l against torso, hips against arm_l in the run, tail against leg_r in the run).
A second pass gave Bearmon the personality of a starter: see the table row above.

Species 432 (Bastemon): `field_animations/bastemon_gait.py` (test `tools.test_bastemon_gait`, `BASTEMON_MODEL` from `edit.py get 432`)
is the overlay generator of its import ('bastemon-field' in `content/models/imports/species.py`): it runs the celebrations' build
(chibi proportions and the salute) and then writes the idle, walk, tired walk and run again from one gait phase per clip. The
earlier clips were not planted (stance slip 39 % mean and 141 % worst in the walk, 27 and 184 % tired) and the run went at 38.5 units a tick.
Now `quadruped.py` plants each sole and the body sits lower on bent knees (the chibi legs are nearly straight at rest, so a planted stride
needs the bend); the hips and the body wind against each other, the upper arms swing against the legs on their sides with a late
forearm, the head follows late, the hair and the two hip ribbons carry a wave down each chain (they stream out in the run) and every
loose part passes through a spring; two eased cycles per clip. Walk 12 ticks a cycle at 15 units a tick (24 ticks), tired walk 14 at 10.5
(28), run 10 at 36 (20), idle 60. Studio stance slip (mean, worst; the studio counts the foot bone): walk 3 and 7 %, 5 and 43 % (two feet); tired 19 and 40 %, 14 and 33 %; run 12 and 36 %, 12 and 36 % (the
foot bone is still counted while the heel peels; the soles themselves are planted to under 1 %, as `quadruped.py` measures). Weaker: ten part pairs
brush a few vertices more than the chibi clips do (ribbon against arm and thigh, forearm and head against the torso, thighs against the hips in
the tired walk; 344 against 346 in the pair maxima summed, pinned in the test), and the swinging feet of the walk and the tired walk step
3.4 to 3.6 times their median tick (every other bone stays under 2.5).

Species 354 (Renamon): `field_animations/renamon_gait.py` (test `tools.test_renamon_gait`, `RENAMON_MODEL` from `edit.py get 354`)
is the overlay generator of its import ('renamon-field' in `content/models/imports/species.py`): it applies the chibi
proportions and then writes the idle, walk, tired walk and run again from one gait phase per clip. The chibi clips replayed the
idle's loop on the tail and hands (equal to the idle's ranges to a tenth of a degree), left head and body nearly still and
turned each shoulder in one channel, so only the legs followed the stride. Now the hips and body wind against each other, the
arms swing against the legs on their sides with a soft elbow and a late hand, the head follows late and the four tail segments
carry a wave, the torso undulates in an S, the hands flick a little paw every stride, with two eased cycles per clip and loose springs on arms, head and tail. Feet stay planted (`quadruped.py`); the step is a cat's line: a low smooth lift, a quiet heel-first landing, hind feet almost in front of each other (`step_style` in the generator: `lift`, `arc`, `heel`, `settle`, `track`).
Walk 28 ticks at 16 units a tick (stance slip 6 % mean, 37 % worst; before 48 ticks at 13, 3-4 and 8 %), tired walk 40 at 11
(4 and 34 %; before 48 ticks, 5 and 16 %), run 24 at 40 (7 and 27 %; before 56 ticks, 3 and 6 %), idle 60 ticks (before 53),
root speed constant. Slightly worse than before: the run's stance slip is higher (worst 27 against 6 % in the studio metric) and
its second difference peaks higher on the short cycle (59 against 69 degrees per tick squared on a leg bone).

Raijinmon 333 wears the native rig and programs of Ogremon (a native binding, donor 34). The bound clips kept the donor's heavy arm swing and
trunk roll, but its legs slid over the floor (mean 79 % of the body's travel in the walk, 115 % tired, 56 % in the run, 297 / 376 / 159 % at
worst), the walk was a 22-tick lunge at 28 units per tick, the idle a 16-tick loop and the run lifted the feet up to 116 units off the floor.
`raijinmon_gait.py` is a stage of the binding (the recipe key `gait` in `native-bindings.json`, run after the last reshaping and before
`spin`, off for every other species) that writes slots 0, 2, 3 and 4 again: the trunk, head and arms are the donor's own clip resampled to a
new cycle (an idle of 60 ticks, a walk of 30 at 18 units per tick, tired 36 at 12, a run of 20 at 40 with a flight phase), their swing kept
and eased; the legs come from `quadruped.py` (a biped: two planted soles on a narrow track, a low lift). Measured on the sole of each foot
(mean / worst % of the body's travel): walk 2.5 / 24, tired 2.3 / 9, run 5.6 / 43; the largest step between ticks 1.9 times the median (idle 2.4,
run 2.4); the resident buffer is 85.8 KB of 100352 B. The technique and care slots are the donor's; the old Megaton Punch timing pin on
the retired Power Crane clip is gone. The test is `tools.test_raijinmon_gait` (`RAIJINMON_MODELS`).

NeoCrimson 402 (`neocrimson_wg_gait.py`, test `tools.test_neocrimson_gait`) wore Tyrannomon's clips through a hand map: the soles slid 32 % mean (143 % at worst) in the walk and the toes hung 40 units above the floor. Its parts now sit on WarGreymon's rig (native binding, `donor_species` 373) and the clips are WarGreymon's gait with each foot planted (`quadruped.py`): walk 22 ticks two cycles at 16 units a tick, tired walk 28 at 10, run 12 two cycles at 40, idle 96 ticks with breathing and glances; stance slip 10 % mean (36 % at worst) in the walk. `quadruped.py` now also reads a gait's `plateau` and a profile's `tol`. The run's left claw dips up to about 18 units under the floor in the swing (the foot mesh's spikes reach past the sole), the walk up to 4.

Cannondramon uses native Monochromon's skeleton (24 bones, `CHDAT/MMD1/MONO.MMD`) and programs at scale 0.85, bound by
`native_binding.py` with `spread_fit`: the body, neck, head, tail and four three-piece legs map by part onto Monochromon's rig, and the five
cannon and weapon pieces ride its chest. Idle (47 ticks) and the techniques are Monochromon's own; the walk, condition walk and run are
rebuilt by `cannondramon_gait.py` on planted soles (14 ticks at 15 units per tick, 20 at 10.5, 12 at 36), so the run no longer sinks
under the floor or slides. Stance slip is 15, 17 and 24 % mean (worst 32, 42 and 50 %). The resident model uses 87,984 of 100,352 bytes.
The gait stage reads soles, reach and knee direction from the rest pose, so it also fits the Unimon (27-bone) and
Garurumon (26-bone) rigs, which were tried as the other donors.

### Suijinmon (408): legs through legs

The centaur's four legs are thick (about 80 units across) and hang from the body one behind the other, front hips 96 units ahead of the hind
ones. The first four-beat walk and gallop swung each side's front leg back while the hind leg swung forward, so the two thighs and the
lower legs crossed on nearly every tick: `meshclash.py` counted 2307 (walk), 3437 (tired walk) and 2014 (run) crossing triangle pairs between
the front and hind leg of the same side over the loops, 40 to 51 units deep. Fixes, all in `suijinmon.py` and the planted-sole IK's opt-in keys:

- the walk is a diagonal walk: each diagonal pair (left hind with right front, right hind with left front) lands 0.22 of a cycle apart, so the
  pairs overlap as in a horse's walk and one side's front and hind legs are rarely at opposite ends of their strides; 14-tick cycle, 60 % stance, 18 units
  a tick, body roll 2.4 degrees for the weight shift. (A first version used a pace, each side stepping together: 27 crossings, but the owner did not
  like the amble and its splayed 25-unit tracks.) The tired walk is the same stride played in 21 ticks at 12;
- the front tracks stand 12 units in and the hind 12 out (`track`), the centres 60 apart further (`reach` -30 / +30), and the swinging paw is carried
  25 units wide of its track and back (`wide`);
- the knees' bend poles turn to the side and a little back for the hind legs, so the knees do not meet between the legs (`pole`);
- `world_ease` 0.5 lets the swinging paw leave and land at rest over the floor, which also keeps the tired walk's lift-off under 33 % slip;
- the soles stood 5 to 21 units over the idle's floor (the rig's floor line is 3 to 5 units over where the source's idle rests): the new `sink` key of
  `quadruped.py` (profile or gait row, units) stands them lower; the walk's lowest sole now reads 1 (idle -1).

Leg-leg crossings now (all six leg pairs): walk 122, tired walk 155, run 98 (deepest 24 to 34 units); stance slip 6/10 % (walk), 9/35 % (tired),
17/37 % (run) mean/max. Legs against the body already crossed in the idle (the body is built from overlapping blocks); they are a little denser per
tick in the gaits now (102 against 72 triangle pairs a tick in the walk) because the hind legs stand wider. Test: `tools.test_suijinmon_gait`.

Zanbamon wears native Monochromon's skeleton (24 bones, `CHDAT/MMD1/MONO.MMD`) at scale 1.35, bound by `native_binding.py` with `spread_fit`, and
nine bones of its own for the rider (recipe key `riders`: torso on the hind hub, cape, head and two crests on the torso and head, two
arms of two bones; each pivots where its lead piece sits). `zanbamon_gait.py` plants the legs (idle 34 ticks, walk 14 at 19 units a tick, tired
walk 18 at 12.5, run 12 at 40; stance slip 7, 5 and 4 % mean, worst 31, 18 and 19 %; no sole below the floor) and moves the human on the
mount's beat: the torso bobs, sways against the hips and twists against them through damped springs, the head and arms follow later and
looser, the cloak and crests trail on their own springs, the rider leans into the run, slumps when tired and breathes and looks about in the
idle. The pivots never slide on the mount. The resident model uses 97,890 of 100,352 bytes.

Guilmon 433 (`tools/models/field_animations/guilmon_gait.py`, test `tools.test_guilmon_gait`) had a walk and tired walk that
slid (the soles moved 49 to 85 % of the body's travel on average and 417 % at worst), sank up to 25 units under the floor and
let the arms flail out wide. The generator plants each foot with `quadruped.py` on the model's own legs (no overlay; Guilmon has no
chibi row): the walk is 24 ticks (two different cycles of 12) at 15 units a tick, the tired walk 32 (2 x 16) at 10, the run 24 (2 x 12) at 36 and the
96-tick idle keeps both feet planted (slots 33, 35 and 36 play the new idle, walk and run). Guilmon's legs are short, so the cycles are
shorter than Growlmon's: a stance covers about 100 units, which the legs reach without sinking the body. The profile's `clear` is 13 because the claw
bone hangs under the ankle mesh the module measures, and the left foot lifts a little before its tick (duty 6.4 / 12 against 6.5 / 12, 10.5 / 16 in the tired walk) so the first
swing step is not sampled at full speed. The studio measures a stance slip of 1 to 3 % on average and 18 % at worst (the imported clips: 26 to 85 %, 418 % at worst), the soles never go
below the floor in the studio's measure (the walk and tired walk have their own `clear`, 17 and 21). The body: hips against shoulders, the upper body rolling over the loaded foot, the arms carried
tucked in and bent with a swing of 15 degrees in the walk (wider, or with the elbows pushed out, they cut into the thighs and the torso), the elbow and hand late and a gesture or two in the idle, neck, head, jaw, ears and the three-link tail following by a spring each; a low tired slump with the head hung and the
tail down, a hunched run with the jaw open, an idle that breathes, shifts its weight, looks about, swishes the tail, flexes the claws and opens the jaw for a snort. The walk stands higher than before (a little more spring in the step). Guilmon also blinks (`guilmon_face.py`, the way Growlmon does; idle 3 blinks, walk 2, tired 2 slow, run 1, each lid, 3-4 shut ticks, lid; the studio's own renderer ignores texture moves, so check it with a player that applies them): the eye is painted in the head texture, so three frames (open, half shut, shut) are stamped into spare texels of the texture (rows 96 and below) and the clips paste them with texture-move events; the texture delta changes too. Offline: `edit.py get 433`, the generator with `--tex`/`--out-tex`, `edit.py put 433 AFTER.MMD AFTER.TIM`.

Garudamon 460 wears the native rig and programs of Angemon (26 bones, `CHDAT/MMD0/ANGE.MMD`, a native binding at scale 1.24). The imported
mesh only ever stands in a fighting stance (hips turned, one leg forward, fists up), and the binding fits the pieces in the source pose, so
every clip inherited it. The recipe key `bind_pose` (per source bone a local rotation, or rotation and translation, in 4096ths) gives the
binding a pose of its own instead of a frame of the bind slot (`bind_slot`, `bind_frame`): Garudamon's is the pose its mesh is modelled in
(every rotation zero, upright, feet pointing forward) with the legs a little apart, knees and elbows eased, head level and wings folded back.
`garudamon_donor_gait.py` (the recipe key `gait`) writes slots 0, 2, 3 and 4 again on two planted soles from `quadruped.py` (idle 76 ticks,
walk 14 at 18 units per tick, tired walk 22 at 11, run 11 at 44). Angemon's left leg, arm and wing bones are not its right ones mirrored (their
axes are turned half a turn about the vertical), so the profile names a sole point per leg (`sole` keyed by leg name) and the arm swing and
wing breath are written as world rotations carried into each bone's space. Angemon's pelvis bone sits at the gimbal pole of its
Euler angles (a turn through it makes the angles jump between ticks, and its own axes are not the world's), so it never turns: it only
carries the body down and up twice a stride (2.5 units in the walk) and 3 units over each standing foot. The trunk is written as world
turns on the bones under it: the hips (the legs' and loin's parent) turn at most 3 degrees about the vertical with the stride (4 in the run)
and roll at most 1, the chest turns back against them a little later (at most 4) and leans (2 degrees in the walk, 9 tired, 11 in the run),
and the head is held steady in the world. Chest, hips and feet face the way it walks: the feet do not turn at all and travel straight.
The limbs stay loose rather than mirrored:
each arm swings with the opposite leg on an eased wave, the right arm later and further than the left;
the forearm trails, so the elbow bends most (30 to 56 degrees in the walk, about 80 to 100 pumping in the run) just after the arm
reaches its back, and the loose hand trails the forearm; the knees fold high on the swing and the soles roll heel to toe. The head
nods late, hangs in the tired walk (torso slumped, shoulders rolled forward, arms dragging) and looks about in the idle,
which also breathes, sways its arms and shifts its weight unevenly; the wings drift and flap behind on loose springs, unevenly in
the idle, and close back in the run. Stance slip is 10 / 9 / 11 % mean in the walk, tired walk and run (worst 26 / 27 / 25 %), the
lowest sole sits 3 to 6 units above the floor line, the largest step between ticks is at most 2.1 times the median, triangle
crossings are 84 / 85 / 109 / 100 (idle, walk, tired, run), and the resident buffer is 85,474 of 100,352 bytes. The test is
`tools.test_garudamon_native`.

Pabumon (470, a hand-made baby) no longer plays Punimon's frantic clips (a blob squashed to half and stretched to one and a half
times its height, spun and thrown about). `pabumon_calm.py` writes slots 0, 2, 3 and 4 into its model delta: a 96-tick idle (four breaths,
two curious look-arounds, a crouch and a small hop that lands with an overshoot, two blinks), a walk of two 20-tick hops at 16 units per
tick (22 units high), a tired walk of two 24-tick scoots at 12 (6 units high, a heavy droop, half-shut eyes) and a run of four 12-tick hops
at 38 (24 high). Squash runs 0.74 to 1.25 with an anticipation crouch before each take-off, and the body leans into the movement. A blink
moves the eye texture to half-lidded, then to the closed arc for three ticks (six when tired), then back; blinks are not tied to the hops.
The body stays where it lands while it is down (the root follows the foot 60 % and a steady line 40 %, the body bone takes up the
difference), and its lowest point is solved every tick so the mesh never goes under the floor. The test is `tools.test_pabumon_calm`.

Yukimibotamon 472 (a hand-made baby on Botamon's rig, donor 1) played Botamon's own clips, which lunge hard (squash 30 %, 60-unit jumps,
stance slip up to 360 % of the body's travel) and flatten the wide body like paper. `field_animations/yukimibotamon_calm.py` writes slots 0, 2,
3 and 4 again, like Nyokimon's: a 96-tick idle (two breaths, slow looks to each side, three blinks: the half-closed lid frame, four ticks of the closed-eye frame, the lid again; walk has one, tired two slow ones, run one), a walk of two 22-tick hops at 17 units per tick (11 high), a tired walk of two 30-tick hops at 11 (4 high, leaning forward, half-closed
eyes) and a run of three 16-tick hops at 38 (18 high). The squash stays within 0.84 to 1.08, the body stays where it lands while it is down and
its lowest point is solved to the floor every tick. The test is `tools.test_yukimibotamon_calm`.
The open mouth frames (small, mid, wide) are one rounded mouth with its cavity and tongue, no omega lobes, because the mouth window is copied whole over the closed omega mouth; a lobe left in an open frame read as two mouths (`test_an_open_mouth_replaces_the_closed_one`).

Nyokimon 473 (a hand-made baby, `tools/models/babies/authoring/nyokimon.py`) moved on Yuramon's rig (donor 43): the hop clips sank the soles
up to 37 units under the rest bottom and the walk, tired walk and run slid 107 to 142 % of the body's travel at worst. It now wears Botamon's
rig (donor 1, three bones, the body object alone; face windows painted over Botamon's texture animations), but Botamon's own clips lunged
too hard (squash 30 %, 60-unit jumps), so `field_animations/nyokimon_calm.py` writes slots 0, 2, 3 and 4 again, with some character:
a 120-tick idle (two slow breaths, curious looks with a head tilt each way, two blinks, a happy bounce-wiggle with smiling eyes at the
end), a walk of two 22-tick hops at 17 units per tick (11 high; a higher and a lower hop, a crouch and wiggle before take-off, a tilt in
the air, a damped wobble on landing, a lagging lean of the sprout end, one blink), a tired walk of two 34-tick hops at 11 (4 high, a sleepy
rocking waddle, half-shut lids, one slow blink) and a run of three 16-tick hops at 38 (18 high). An open, smiling or sad mouth replaces the grey lip line of the closed mouth in its whole 24 x 16 window (they used to show both, two mouths at once; `test_an_open_mouth_replaces_the_closed_one`). A blink is a half lid, two or three ticks of
the closed eye (texture window x 24 words, `tex` events the field-clip programs run), a half lid. The squash stays within 0.86 to 1.10, the
body stays where it lands while it is down and its lowest point is solved to the floor every tick. The studio's slip metric reads a fixed
bone on this rig and is meaningless here, so the test measures the lowest points of the mesh: mean slip 4 / 7 / 2 %, worst 9 / 19 / 5 % of
the root speed on walk, tired and run, lowest sole 0 on every clip (before -25 / -35 / -37 / -3), resident motion buffer about 28.8 KB of
100352 B (the stored model 34.1 KB, from 28.8 KB). Tsunomon (16) and Tokomon (30) were built as alternatives and fit the same face
windows, but their hops are taller than the body. The tests are `tools.test_nyokimon_calm` and `tools.test_native_babies`.

Nyaromon 476 (a hand-made baby on Tokomon's rig, donor 30) played Tokomon's own clips: hops 126-133 units high, the lowest point of the mesh
0 to 133 units above the floor, and the body sliding 91-93 % of the root's travel (worst 133 %). Its mesh was one rigid object (head, ears and
tail), so nothing could swing on its own; `field_animations/nyaromon_calm.py` first moves the tail into two objects on a bone chain (bones 3 and 4,
split at the top of the arch, the base taking one extra row of quads so a bent joint shows no gap) and each ear into an object of its own
(bones 7 and 8), the very same triangles, UVs and colours (the build asserts the rest look), then writes slots 0, 2, 3, 4 and the aliases 33, 35, 36
again. Tokomon's other slots swing those bones 50-127 degrees, so every other program holds them at rest (the tail is as stiff as before there).
The tail is a two-segment wave with the tip lagging: a slow sway and now and then a flick in the idle, a sway opposite to the waddle's roll and a pitch
that follows the hop with a delay in the walk, hanging low and slow when tired, streaming behind in the run; the ears twitch in the idle and splay a
little with each hop. The head still does most of the work: a 96-tick idle (two breaths, a look and a head tilt each way, a small mew, four blinks, one of
them a double), a walk of two 16-tick steps at 20 units per tick (5 high: a weight shift and soft squash before each step, a roll and a twist
that alternate, a landing wobble, the back of the head lagging the rise), a tired walk of two 24-tick steps at 12 (2.5 high, head low and
forward, heavy slanted lids, two slow blinks) and a run of three 14-tick steps at 37 (9 high, mouth open, one blink). The page gets three eye windows
(lid, heavy lid, closed arc: 40 x 28 texels, each overwriting the whole open eye) at x 184 and 216, y 48 and 76, and a blink is a lid, two or
three ticks of the closed eye, a lid, the open eye (`tex` events); the mouth changes with windows of its own (shut, half, wide) so it never
reopens a closed eye. The body stays where it lands while it is down: mean slip 7.5 / 1.6 / 3.4 % of the root speed on the planted ticks
(worst 30 / 10 / 6 %), lowest sole 0 on every clip (before -0.9), highest 5.1 / 3.2 / 9.5 units (the body only), resident buffer 34,996 of 100,352 bytes (from
31,432), the stored model 40.5 KB. The studio's slip metric reads a fixed bone on this rig and is meaningless here. The tests are
`tools.test_nyaromon_calm` and `tools.test_native_babies`.

Veedramon (203) jaw: the walk, tired walk and run take the jaw (bone 4) from `gaits.py`'s `jaw` profile key, a damped spring on the stride
that turns about the jaw's own X axis only (walk 5 to 8 degrees, tired walk 11 to 15, hanging a little open, run 7 to 11; yaw and roll
exactly 0). Before, the profile copied the jaw out of the source tired and run clips (`source_aux`), which carried yaw to 24 degrees, roll to 15
and a pitch of -22 (through the upper jaw) because the source head stood still while the jaw acted; under the authored head the jaw slid off
to one side. Jaw vertices inside the head in the run 11 -> 1. The battle slots 33, 35, 36 keep the source clips. Test: `tools/test_veedramon_jaw.py`.

Veedramon (203) liveliness: the walk, tired walk and run add lagging follow-through on top of the native tail, neck and arm acting (`waves` and `head_bob`
in the profile: tail yaw wave travelling to the tip with a small pitch flick, loose shoulders, elbows and neck on their own phase, a head bob, a slow
`vary` modulation over the macro cycle so no two strides match), wider and larger arm swings (34 / 10 / 56 degrees, elbows bent 38 / 12 / 72), a bouncier
body (11 / 3 / 12) and leans of 5 / 16 / 22 degrees. The non-leg bones are fitted with a looser keyframe tolerance (`loose`, 6) which pays for it:
resident buffer 98532 B (was 98826). Speeds, soles and the jaw's hinge unchanged; the idle stays the native one.

MegaKabuterimon 205 wears the native rig and programs of Kabuterimon (28 bones, `CHDAT/MMD0/KABU.MMD`, a native binding at scale 1.0).
The donors' own legs were made for shorter legs than the mesh has (159 units against about 123): their soles slid over the floor (mean slip above
100%) and sank under it. `kabuterimon_donor_gait.py` (the recipe key `gait`) writes slots 0, 2, 3 and 4 again: the donor's trunk, arms, head and wings
are kept (resampled to the new cycle, the lower arms' elbows folded a little more so the hands clear the legs), and each leg is solved by `quadruped.py`
on its own sole (idle 60 ticks, walk 20 at 16 units per tick, tired walk 22 at 11, run 14 at 38). The knees are asked to bend up and a little
forward: the first guess, the mesh's own rest bend, took one thigh through the Euler gimbal (a quarter turn about its middle axis), so the
two legs' angles were not mirror images and the loop could not close in Euler angles. Stance slip is 5 / 9 / 4 % mean in the walk, tired walk and run (worst 19 / 25 / 7 %),
the lowest point of the mesh is at most 8 units under the floor line (a toe), and the resident buffer is 90,718 of 100,352 bytes.
On top of the donor's clips the stage adds slow overlapped motion: the waist, chest and head (the horn rides it) pitch with the stride, each lagging the one before, the
low arms trail, the walk and run are slow and heavy (long cycles, small swings of the arms and trunk) and the body leans forward in the run and slumps in the tired walk, and the idle (60 ticks) breathes, shifts its weight from foot to foot and flicks the head. The shell is one rigid piece
with the chest (the wing bones carry no mesh), so there is no wing spring to add. The test is `tools.test_megakabuterimon_native`.

Yokomon 477 (a hand-made baby on Tanemon's rig, donor 44) plays Tanemon's clips. Its four petal blades sit on bones 4 and 5, which hinge about z: idle, walk and
run swing them below the rest angle (rz down to -364, -728 and -499), so the flower is open, but Tanemon's tired walk holds them at +340 to +400, standing against the
neck like a closed bud. `field_animations/yokomon_petals.py` rewrites only the rz of those two bones in slot 3 (the initial pose and the values of the keys; the key frames,
spans, every other channel, the eye and sound events and the other slots are the donor's, byte for byte): the petals hang at -230 and follow the head's nod (bone 3, rx) three
ticks late with a quarter of its swing, from -310 to -152, bone 5 the mirror. Triangle crossings between the petals, neck and bulb fall from 110 to 63 of the 21 tired ticks.
The test is `tools.test_yokomon_petals`.
Yokomon's neck came off the bulb in every moving clip: Tanemon's head bone (3) nods about a pivot 51 units above the base of the stem, so a 30-degree nod swings the base 20 to 30 units
forward or back of the bulb's top (15 in the idle, 29 in the walk and run, 27 in the tired walk). `field_animations/yokomon_neck.py` adds to bone 3 the translation (ty, tz: one extra key entry per rx span and the initial pose) that cancels
that swing, so the nod turns about the base of the stem; rx, every other bone, the root, the events and the mesh are untouched, and the idle, walk and run aliases (slots 27, 33, 35, 36) share the change.
The base of the stem stays within 5 units of its rest place in every tick of every clip (test: `tools.test_yokomon_petals`).
