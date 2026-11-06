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
