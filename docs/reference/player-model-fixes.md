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

## Beelzemon: Blast Mode face

The winged M377BLZB source is Blast Mode. Its irises should be green, as shown
in the [official reference](https://digimon.net/reference/detail.php?directory_name=beelzebumonblastmode)
and described by [Wikimon](https://wikimon.net/Beelzebumon:_Blast_Mode).
The DW3 source and previous import have red irises. Only the two iris shades
swap red and green channels in an isolated palette; the blue channel, shade
steps, gold highlights, eyelids, helmet, clothing and other palettes remain exact.

A direct culled render of the untouched DW3 model confirms a visible mouth
and a third forehead eye. Simplification collapsed the lower face to three
surfaces and removed the forehead eye. The repair restores all eight source
jaw polygons, its full 30×24 texture patch and the forehead eye's two source
triangles as one quad. Six lateral eye surfaces use a full 48×24 patch; the
forehead eye uses its original 16×24 patch. Six existing triangle pairs become
quads with the same diagonal, retaining 713 primitives. Animation bytes are
unchanged. The mouth restoration is retained because the untouched source
visibly has the mouth; no mouth detail is invented.

`tools/models/repair_beelzemon.py` authors the repair from the source disc.
`tools/models/edit.py put 403` stores the plain deltas and final provider pins.
Run `tools/test_beelzemon_face.py` with `BEELZEMON_BEFORE` and
`BEELZEMON_AFTER` pointing at reconstructed MMDs to check geometry, acting,
texture isolation, green iris shades and the polygon budget. Verify the player
output with `tools/models/edit.py check 403 --species-pins`.
