# Magnamon and MegaGargomon source review

Magnamon is the Digital Card Battle model 189. It is a distinct imported mesh,
not a Ninjamon twin. Its frozen import spec used Tyrannomon for everyday acting;
the field overlay subsequently replaced locomotion, while care and battle still
mixed that retargeting with Card Battle clips. Its provisional finisher was
Ninjamon's Iga School Knife Throw.

The [official profile](https://digimon.net/reference_en/detail.php?directory_name=magnamon)
describes plasma projectiles and an explosive golden beam. The existing game
technique Energy Bomb supplies the projectile/explosion approximation; its menu
name remains Energy Bomb. This replaces the knife technique without renaming a
shared native technique or claiming to implement a new canon attack. Ordinary
Battle/Mech techniques remain available.

The reviewed native binding uses Leomon's humanoid skeleton and animation
programs. Each imported mesh piece is assigned anatomically; the chest and limb
segments fit the native joints. Native timing, easing, weight transfer, head and
arm motion, care sequences and battle controls remain. Translation tracks scale
once. The native binding recipe pins both inputs and maps every piece. Technique
slots select the corresponding native punch, kick, dash, guard, buff and casting
programs. The condition bubble and effect origins follow the new skeleton.

MegaGargomon is World 2003 M372SGRG, matching the
[official machine form](https://digimon.net/reference_en/detail.php?directory_name=saintgalgomon).
Its frozen import allowed small-face deletion to meet the largest observed
native primitive count. This removed both blue eye quads, face plates and rear vent surfaces: the
converted head had 70 primitives and the torso/backpack 86. Restoring the complete
source surfaces with matching UVs, palette rows, winding and normals produces
103 and 118 respectively after compatible triangle pairing. All other mesh
pieces, vertex positions, animation programs and the texture bytes remain exact.
The source eye material starts at texel (64, 160), palette (32, 240).
No transparency flag is enabled; the source atlas already contains the art.

The repaired base has 778 primitives. The native maximum of 713 is an importer
target, rather than a model renderer array bound. Surface deletion is avoided;
resident storage, cold sector reads, render packets and screen heap remain the
hardware checks. The pinned equipment, pace, proportions and celebration passes
are replayed on the new base. The original vertex pools remain intact because
those passes also use unused vertices as grounding landmarks.

Replay the authoring operation with the original model and imported base:

```sh
python3 tools/models/repair_megagargomon.py SOURCE.BIN BEFORE.MMD BEFORE.TIM AFTER.MMD
python3 tools/models/edit.py put 335 AFTER.MMD
```

Authoring requires `networkx` for maximum triangle pairing; player builds replay
only the plain delta and have no additional dependency. `tools.test_megagargomon`
checks complete source surfaces, winding, unchanged limb meshes and programs,
and original resident/cold storage limits. `tools.test_native_bindings` checks
Magnamon's complete native animation set and binding provenance. Both require
the documented local source fixtures; missing fixtures are reported as skipped.

A report of complete disappearance is separate from the missing surfaces. The
baseline model fits its resident/cold buffers, and its decoded clips do not set
the body or head scale to zero. These observations alone do not reproduce or
explain a rare battle disappearance.
