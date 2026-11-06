# Player model reports

## Gallantmon: helmet eyes

The full-resolution eye repair is already included in v0.0.6. The final provider
uses the repaired model and texture directly, without a field overlay. Its eight
helmet faces sample a dedicated 56 by 32 texture rectangle beginning at (125, 0).
The source palette, model size and animation programs are preserved by
`tools/models/repair_gallantmon.py`.

A culled front, three-quarter and side render of the current pinned model shows
both yellow eyes. The model and texture pins must be checked together:

```sh
python3 tools/models/edit.py --from build/model-fixes-wolf check 318 --species-pins
```

The repair was introduced by commit `2068525a`; this report does not require a
second texture alteration.

## Submarimon: water outlet and preferred terrain

Blasting Spout's Whamon origin `[2, -102, 0, 155]` maps to Submarimon's
front drill, bone 7, at local `[0, 0, -180]`. The outlet follows the drill
through the finisher, rather than following the middle of the hull.
Other technique origin mappings are unchanged.

Preferred terrain is region 8: Coela Point and both Dragon Eye Lake screens
carry it in their MAP headers. Region 4, used previously, belongs to Tropical
Jungle. These region classes are distinct from the map-name indices.

## Mega size comparison

Size adjustments are baked into vertices and all animation translations,
including root momentum; rotation and bone-scale channels are unchanged.
The comparison uses native Machinedramon at the same camera scale.

| Species | Uniform multiplier | Idle height before / after |
|---|---:|---:|
| MaloMyotismon | 1.37 | 475 / 650 |
| Imperialdramon | 0.85 | 600 / 510 |

Imperialdramon's wide wings and quadrupedal body retain their silhouette.
Its final celebration is baked before resizing, so field and battle slots use
the same proportions. Attached effect origins and condition bubbles follow the
same multiplier; radius, height and status framing are updated with the model.
`tools/models/resize.py` refuses storage overflow and checks all animation
controls and non-translation channels remain exact.

## MegaKabuterimon: size and evolution route

MegaKabuterimon uses a uniform 0.90 multiplier (idle height 558 → 502),
keeping this Ultimate below HerculesKabuterimon while retaining its broad shell.
The existing curated route is Kabuterimon (19) → MegaKabuterimon (205) →
HerculesKabuterimon (60). No level-skipping route is added. Source records and
`content/tables/evolution-tree.json` already agree on both edges; the built
chart audit must also show these links with NEW DIGIMON enabled.

## VenomMyotismon: loose long-arm run

The run's shoulders drive alternating arcs, followed by the elbows and then
the heavy gauntlets. Smooth periodic reversals avoid a rigid held-fist pose.
Devimon's native long-arm motion is the visual reference. The existing chest,
head, wing, tail and supported-leg performance remains unchanged, as do root
travel, scale channels, clip duration and sound/control events. The authoring
pass checks every unselected channel over four decoded cycles and changes only
run slot 4. Final provider output retains the animation storage gate.

## Beelzemon: Blast Mode silhouette and face

The winged M377BLZB source is Blast Mode. Its irises should be green, as shown
in the [official reference](https://digimon.net/reference/detail.php?directory_name=beelzebumonblastmode).
Only the two iris shades swap red and green channels in an isolated palette;
blue, shade steps, gold highlights and all other palettes remain exact.

The source reader must honor empty section-table slots: otherwise the free hand
is truncated. The complete untouched model has 905 primitives, including a
hidden effect mesh. Culled front, three-quarter, side and back comparisons show
that the import lost helmet spikes, wing-tip surfaces and belt detail. The
repair rebuilds the whole head (130 source triangles), all six wing sections
and all four belt sections, using the existing DW1 proportion bake. The source
jaw and all three green eyes retain their full-resolution texture patches.
The current cannon, five claws and boot spikes are present and retained.

Exact triangle pairing and unused-pool cleanup recover space. New pairs keep
the same diagonal, shared UVs and normals, winding and material; they must form
convex quads. A small fit of the existing broad body/leg panels supplies the
remaining slots. Their six extent landmarks are pinned, preserving width,
height and depth. Head, wing tips, belts, arms, cannon, hands and boots are protected
from this fit. Animation bytes stay exact. The result keeps the 713-primitive,
172-vertices-per-object and original resident/cold-buffer limits.

`tools/models/repair_beelzemon.py` is an authoring tool; it needs NetworkX and
takes the untouched source, DW1-proportioned MMD/TIM, pinned raw importer MMD,
and output stem. The player build needs no authoring dependency: plain deltas
and final provider pins carry the result. Store with `tools/models/edit.py put
403`, then run `check 403 --species-pins`.

`tools/test_beelzemon_face.py` takes `BEELZEMON_BEFORE`, `BEELZEMON_AFTER`,
`BEELZEMON_SOURCE` and `BEELZEMON_IMPORT`. It checks every restored source
triangle with its winding, UVs and normals; retained protected geometry;
body-panel extents; unchanged acting; texture isolation and storage budgets.

## Silphymon and Starmon: field strides

Silphymon's Card Battle rig carries the head on bone 3 and its ears on bones 4
and 5. The proportion recipe previously treated only bone 5 as the head,
enlarging that ear alone. Both ears now retain the source head proportions.
The corrected proportion bake is stored before the final walk delta; the
provider uses the resulting model directly.

The field walk, condition walk and run use native Kokatorimon motion for
Silphymon and native Leomon motion for Starmon. Anatomical chain calibration
and inverse kinematics fit the native foot paths to the imported leg lengths.
The feet keep their own orientation with native heel and toe roll. Clearance
is checked at logical ticks and intermediate blend samples. Silphymon's stride
uses longer timing for its larger body; Starmon's retains the native timing.
Upper-body acting and secondary motion keep the gait loose. Meshes, rigs,
care clips and attack programs are preserved after the proportion correction.
Starmon shares the repaired walk and run with battle slots 35 and 36, matching
the native donor and replacing its separate imported battle shuffle.

The authoring tools are `tools/models/field_animations/silphymon_walk.py` and
`starmon_walk.py`. Silphymon's `--prepare` option reconstructs the corrected
proportion bake from its pinned pre-edit import. Store final results with
`tools/models/edit.py put`, then check the provider pins. The replay tests use
`MODEL_REPORT_DIR` for the pre-edit and reviewed files:

```sh
MODEL_REPORT_DIR=build/reports PYTHONPATH=tools python3 -m unittest \
  tools.test_player_model_reports tools.test_dws_battle_moves
```

Saberdramon uses the native DW1 model. The reviewed provider and integrated
record preserve its source primitives, UVs and texture pages, with identical
palette rows and sampled texels. A reported tan wing-root surface does not
justify altering those assets without a demonstrated import regression.

The story compiler already gives Starmon's replacement of the noncombat
Unimon placement usable attack priorities. This behavior is present in
v0.0.6; its regression tests cover the actual placement and moves. It does
not establish that a later report of inactivity is resolved: verify the live
wild encounter and its technique execution before changing battle behavior.

## Beelzemon: ordinary cannon strike

The World 2003 source `M377BLZB` is Blast Mode. Its Blaster is the
[right-arm weapon](https://wikimon.net/Beelzebumon%3A_Blast_Mode); the imported
mesh keeps it on bones 20–23, opposite the bare-hand chain 16–19. The native
Leomon hand strike previously drove the bare fist while the projectile origin
already followed cannon bone 22.

`tools/models/repair_beelzemon_attack.py` authors the complete firing action.
The free arm rises to brace below the cannon. The torso loads, turns into the
shot and takes the recoil; knee flexion and a small pelvis shift carry its
weight while both feet remain planted. The head counters the turn, and the
wings and tail follow with delayed motion. Small translation channels use a
stricter encoding tolerance so compression retains the weight shift.

The four short strikes share one 15-tick program. The nine casting aliases,
including Tremor, share a 44-tick program. Their existing events, durations and
technique rules remain exact. Field/care animations, Buster Dive, War Cry and
the finisher remain unchanged, as do the mesh, rig and texture.

The consumed resident model uses 99,480 bytes within the 100,352-byte partner
buffer. Every sector-aligned cold read fits 8,192 bytes. The intermediate delta
retains the old Buster Dive alias until the provider replays its reviewed dash;
storage is checked on that consumed result.

Native Andromon Pulse Laser and MetalGreymon Heat Laser provide the visual
reference. The side-by-side videos remain a separate review requirement;
physical regression checks cannot establish animation quality by themselves.
Reproduce event, weapon, bracing, foot placement and storage checks with the
pre-edit provider output at `MODEL_REPORT_DIR/before/403.MMD`:

```sh
MODEL_REPORT_DIR=build/reports PYTHONPATH=tools \
  python3 -W ignore -m unittest tools.test_beelzemon_attack
```

## Apocalymon: voice and Power Crane

The imported card-game model retains a humanoid torso, floating core and metal
claws. Its old voice pair, VBALL 48 / VLALL 2, belonged to Megadramon and
Gigadramon. It now borrows Myotismon's pair, 56 / 3, following the humanoid dark
character rather than the everyday animation donor. This is a native DW1 voice
substitution, not a newly imported canonical voice recording. Notes 53–55 are
present in the selected VBALL bank.

Power Crane, slot 51, previously aliased the general 61-tick cast, whose core
pitch ranged from −648 to 164 angular units. Its dedicated crane gesture reaches
with the forward claw while the torso, free claws and heavy core counter the
motion. The core stays within a small tilt instead of pitching through that
full range. Other casting aliases and the Status portrait remain unchanged.
The dedicated clip retains its original duration and sound event. Its resident
model fits the 100,352-byte buffer at 100,330 bytes; cold reads still fit 8,192.

## Omnimon: Grey melee and Garuru ranged techniques

The [official profile](https://digimon.net/reference_en/detail.php?directory_name=omegamon)
identifies the Grey sword in the left arm and the Garuru cannon in the right.
The imported mesh agrees: bones 3–7 carry Grey and 9–13 carry Garuru. The source
physical clip moved Garuru while Grey's shoulder and elbow remained fixed.
The physical action is now reflected onto the Grey chain, with the body's weight
shift and cloak response carried through and eased transitions to the ready pose.
The mesh is preserved.

| Ordinary technique | Action |
| --- | --- |
| Megaton Punch, Counter, Sonic Jab | Grey sword |
| Tremor | Grey sword ground strike |
| Buster Dive | Existing whole-body dash |
| Dynamite Kick | Existing kick |
| Ice Statue, Aurora Freeze, Giga Freeze, Water Blit | Existing Garuru cannon cast |
| Prominence Beam, Magma Bomb, Red Inferno, Fire Tower | Existing Garuru cannon cast |

Only slots 46, 48, 50 and 51 change. Ranged programs, the dash, kick, finisher and
all field animations retain their exact decoded motion. Duration and events of
the physical group remain exact. The resident model uses 83,376 bytes. Reproduce
both imported-model regressions with the pre-edit files in
`FOLLOWUP_REPORT_DIR/before/{400,461}.MMD`:

```sh
PYTHONPATH=tools python3 -W ignore -m unittest tools.test_reported_attacks
```

## Tyrannomon scene: uninterrupted native strides

The black actor in the Ancient Glacial Region recruitment scene is native
MasterTyrannomon (`TIRS`, NPC twin 467); the red actor uses native Tyrannomon
(`ETYR`, 132). Both source walks use both feet. In the animation studio, TIRS
lifts its feet by 67/60 units and ETYR by 112/112; the partner MasterTyrannomon
walk retains Tyrannomon's full motion at its larger size, lifting both feet by
167 units. Native Greymon provides the biped reference. These clips retain
their original body, arm and tail motion.

Script 79 restarted the black actor's 31-tick walk every 15 ticks and restarted
the red actor's departure run every 10 ticks. `scriptSetEntityWalking` starts
the animation unconditionally, so those commands repeatedly replayed the
beginning of a stride. The scene now starts each movement once. Its existing
waits, sounds, facing changes, arrival checks and recruitment remain in place.
No model, texture, rig or animation program changes for either actor.

## SkullSatamon: posture after flatten recovery

The imported `M244SKST` keeps its source healthy battle idle in slot `0x21`.
The flatten transition starts `0x22`, the tired idle. Previously, recovery
restored the model scale and cleared the flatten flags while retaining that
stance; a healthy fighter could keep it until another action started.

`Restore-battle-idle-after-flatten-recovery.patch` selects the existing
healthy/tired idle when recovery ends. Low HP and poison still select the tired
stance. Active attacks, knockback, stun and confusion are preserved. SkullSatamon's
mesh, rig, textures, animation programs and provider pins remain unchanged.
The full nine-language build adds 52 bytes to BTL (151,248 bytes, still 74
sectors). Main BSS end stays at `0x801cdf84`, leaving 188,272 bytes of heap.
All 320 archive-backed screen setups fit; minimum margin is 3,552 bytes.

The host regression compiles the actual status-transition and idle-selection
functions with address/undefined-behavior sanitizers, covering health, poison,
the scaled native model and active reactions:

```sh
python3 tools/dev/playtest/flat_recovery_host.py build/decomp-dev build/flat-host
```

Use `--baseline` against the previous engine to reproduce the stale tired idle.
