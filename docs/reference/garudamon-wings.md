# Garudamon: field wing clearance

Garudamon's broad wing feathers were fitted into Angemon's folded wing stance. The source's right wing bones 4/5
map to donor 10/11 and its left 6/7 to 12/13. The sides are mapped correctly; their outer meshes cross the middle
because that folded stance is too narrow. The imported base has 28 bones (27 mapped nonroot source bones), and the
native rig has 26, including the root. This is not a 25-bone source rig. There is no Garudamon chibi recipe, native-binding
`chibi` stage or `rig-fits.json` entry. Bone-size fitting is not responsible: the fault is already present before the
gait pass (maximum opposing-wing intersections per sample, slots 0–4: 57, 60, 50, 55, 55).
The source model's own wing meshes have zero opposing-wing intersections in these five slots.

The supplied `build/device/imported-models/460.MMD` is the importer input on the **source** rig. For final-model
measurements, follow `build/device/imported-species/460-garudamon.json` to its generated model and skeleton.
Main's final model and the independently rebuilt pre-change provider output are byte-identical:
`433012fa91092719880f796b9b4b3745e45a8c85e5ec10cd906cd1aeb61a4a5a` (SHA-256).

| Field slot | Clip provenance | Final loop ticks |
|---|---|---:|
| 0 | authored idle, starting from Angemon slot 0's pose | 76 |
| 1 | Angemon source slot 1, poor-condition idle | 16 |
| 2 | Angemon slot 2, paced to 22 ticks, then replaced by the planted-foot authored walk | 14 |
| 3 | Angemon slot 3, paced to 20 ticks, then replaced by the authored tired walk | 22 |
| 4 | Angemon slot 4, paced to 20 ticks, then replaced by the authored run | 11 |

`garudamon_donor_gait.py` opens roots 10/12 by mirrored 45-degree yaw and 45-degree outward roll in the rest body's
axes, after the spring composition. Constant rotation preserves the source swing and the independent outer-joint lag;
no wing track is flattened or frozen. The three rotational channels of those two roots are replaced with the existing
channel packer. Every other channel, all mesh bytes and battle clips decode exactly as before. Slots 14–18 and 23
share slot 1's donor stream and receive the same wing correction. The original aliases are retained.
The final model uses 90,754 resident bytes (before: 90,662; limit: 100,352).
The provider pin was refreshed through `edit.py repin` (input unchanged) and `edit.py put --force` (delta byte-identical).

## Measurements

World-space distances use the body's moving mid-plane through the wings' shared chest bone 2. Its normal is the
idle-world +x axis transported by that bone's current transform. This removes false crossings from chest sway or yaw.
All four opposing mesh combinations (10/12, 10/13, 11/12, 11/13) are tested at every integer tick and fixed-alpha
1365/2730 thirds, including the final closing pose. Triangle counts are surface intersections, not AABB overlap.
The quantized SRT interpolation is shared with `motiontailspace`; PS1 matrix rounding and continuous time are not modeled.

| Slot | Samples | Max wrong-side depth, before → after (model units) | Max wing triangle intersections, before → after | Intersecting samples, before → after |
|---|---:|---:|---:|---:|
| 0 | 229 | 136.89 → 0 | 44 → 0 | 229 → 0 |
| 1 | 49 | 99.02 → 0 | 60 → 0 | 49 → 0 |
| 2 | 43 | 132.45 → 0 | 48 → 0 | 43 → 0 |
| 3 | 67 | 139.18 → 0 | 44 → 0 | 67 → 0 |
| 4 | 34 | 144.20 → 0 | 44 → 0 | 34 → 0 |

[Every measured Garudamon sample](garudamon-wing-crossing.csv) records both stages, tick, third, depth, centroid
side-swap depth and summed triangle count. Both wing joints on both sides retain more than 3 degrees of motion in
every field slot. Whole-model nonadjacent-piece triangle intersections also fall: mean per sample in slots 0–4 goes from
91.0/171.0/93.3/95.0/123.9 to approximately 19.9/121.4/21.1/31.9/33.6; this does not claim the whole model is collision-free.

## Sweep of the other imported species

`field_sides_qa.py` examines the final provider records, using reflected idle joint anchors, compatible known bone
roles and paired ancestry to infer opposing chains. Meshless intermediary bones are skipped. It tests every opposing
segment combination within each chain, so a feather hitting the opposite root is included. `battle_qa.measure` and
care QA also expose cheap `side_depth` and `side_centroid` diagnostics (in idle heights); the existing battle/care
acceptance thresholds are unchanged. The standalone sweep adds triangle confirmation and interpolation samples.

Run against a completed build:

```sh
python3 tools/models/field_sides_qa.py BUILD/imported-species --json sweep.json
```

All 183 imported records were inspected, with 3,540 opposing mesh pairs found in 177 species, field slots 0–4.
No separable mirrored pair was inferred for Quetzalmon 249, Tylomon 254, Syakomon 283, Pabumon 470,
YukimiBotamon 472 or Nyokimon 473; this is coverage information, not a clearance certificate for fused geometry.
A candidate needs wrong-side penetration over 2.5% of idle height and a surface intersection **at the same sample**,
or a centroid over 2.5% of idle height onto the opposite side. Pair inference can include other paired appendages
(e.g. petals), and deliberate crossed poses need visual review. Coplanar surfaces and full containment are not detected
by the surface-intersection test. The following are measured findings, not authorization to repair other species.

47 other species have confirmed opposing-piece intersections; 6 more have side-swap-only candidates. No other species was changed.

| Species | Flagged field slots | Max depth (units) | Max triangle count per pair/sample |
|---|---|---:|---:|
| 181-puppetmon | 0,2,3,4 | 164.93 | 26 |
| 182-kimeramon | 2,3,4 | 86.96 | 37 |
| 187-stingmon | 2,3,4 | 32.46 | 30 |
| 188-aquilamon | 1 | 117.19 | 16 |
| 190-angewomon | 0,1,2,3,4 | 113.35 | 51 |
| 194-exveemon | 2,3,4 | 16.41 | 10 |
| 196-halsemon | 2,3 | 14.40 | 10 |
| 198-nefertimon | 4 | 8.42 | 17 |
| 199-paildramon | 2,3 | 39.07 | 16 |
| 203-veedramon | 1,4 | 23.37 | 6 |
| 205-megakabuterimon | 1 | 77.97 | 69 |
| 206-magnaangemon | 2,4 | 72.66 | 29 |
| 207-seraphimon | 2,3,4 | 45.83 | 32 |
| 210-grankuwagamon | 1 | 18.36 | 18 |
| 220-vikemon | 0,2,3,4 | 68.00 | 6 |
| 225-shurimon | 1,3 | 35.71 | 20 |
| 226-silphymon | 0,2,3,4 | 54.42 | 34 |
| 228-baronmon | 0 | 12.19 | 18 |
| 234-gatomon | 2 | 15.58 | 8 |
| 243-starmon | 2,3 | 102.69 | 0 |
| 244-superstarmon | 1,2,3 | 177.11 | 0 |
| 247-kokuwamon | 2,3,4 | 7.90 | 18 |
| 255-valkyrimon | 1,2,3,4 | 71.69 | 12 |
| 257-triceramon | 0,1,2,3,4 | 115.91 | 0 |
| 258-saberleomon | 4 | 84.90 | 5 |
| 260-metaltyrannomon | 2,3,4 | 56.18 | 8 |
| 264-raremon | 1 | 150.64 | 0 |
| 276-baihumon | 4 | 29.33 | 6 |
| 277-skullmeramon | 1,4 | 72.65 | 46 |
| 279-marinedevimon | 0,1,2,3,4 | 104.01 | 0 |
| 281-cyclonemon | 0,1,2,3,4 | 81.91 | 20 |
| 290-clockmon | 0,1,2,3,4 | 207.49 | 42 |
| 293-gryphonmon | 2,4 | 52.76 | 20 |
| 295-vilemon | 2,3,4 | 33.24 | 22 |
| 297-marsmon | 2,3 | 30.74 | 16 |
| 299-hookmon | 2,3,4 | 32.76 | 35 |
| 306-grapleomon | 3,4 | 62.97 | 43 |
| 307-blackkingnumemon | 2,3,4 | 31.71 | 27 |
| 311-arukenimon | 0,1 | 64.10 | 16 |
| 314-skullsatamon | 3 | 16.84 | 10 |
| 315-taomon | 3 | 57.22 | 0 |
| 316-sakuyamon | 0,1,2,3,4 | 27.62 | 12 |
| 319-pharaohmon | 0,2,3,4 | 41.08 | 63 |
| 321-knightmon | 4 | 39.74 | 11 |
| 323-lynxmon | 4 | 40.14 | 13 |
| 326-wargrowlmon | 1 | 40.92 | 5 |
| 335-megagargomon | 0,2,3,4 | 61.08 | 25 |
| 352-monmon | 1 | 12.27 | 7 |
| 354-renamon | 2,3,4 | 28.51 | 19 |
| 402-neocrimson | 1,2,3,4 | 155.33 | 12 |
| 409-kyubimon | 2,3,4 | 25.09 | 40 |
| 432-bastemon | 0,1,2,3,4 | 28.70 | 31 |
| 477-yokomon | 1,2,4 | 20.55 | 84 |

[The sweep measurements](field-side-crossing-sweep.csv) list each candidate bone pair and slot, sample counts, depth and triangle counts.
The six side-swap-only species are 243-starmon, 244-superstarmon, 257-triceramon, 264-raremon, 279-marinedevimon, 315-taomon.

Validation: 73 related tests, 4 fixture-dependent skips; provider source/delta/final-pin check passes.
The pre-existing stale Garudamon SHA-256 and resident-byte snapshots were replaced with the actual provider pin check and the buffer bound.
