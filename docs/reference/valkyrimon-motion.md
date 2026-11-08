# Valkyrimon: size and field stride

The player report described the added winged humanoid as oversized, with an
awkward walk. The model's internal species name is `Valkyrimon` (255).

The original recipe in `content/imports/specs/Valkyrimon.json` maps its field
performance from HerculesKabuterimon (60). There was no subsequent humanoid
field recipe. The imported idle's carrier is pitched, yawed and rolled; its
leg references are asymmetric. Transferring the insect's motion through those
references produces a crouched, uneven stride. The decoded original walk has
54/92 units of foot-joint lift and mean stance slip of 79%/56% of root speed.
Native Angemon's walk has 57/58 lift and 22%/23% slip by the same studio metric.
These measurements describe joint motion, not a full sole-contact solver.

The original idle mesh measures 551.6 units high and 629.4 wide, including the
crest, shield and wings. Native Angemon measures 402.9 high; the reviewed
Angewomon mesh measures 418.5 high and 407.9 wide (record height 418). MagnaAngemon, Seraphimon and
SlashAngemon have larger silhouettes (records 608, 655 and 553; the
SlashAngemon mesh measures 553.0 high and 479.3 wide). Valkyrimon's
large crest and wings make the old 551-unit setting particularly prominent.
A uniform 0.8 resize brings its measured idle to 439.7 high and 504.3 wide:
still a broad Mega, near the smaller humanoid angels in body height. Its
existing large head and compact legs already have chibi proportions; no
additional head or limb distortion is applied.

`tools/models/field_animations/valkyrimon.py` is an offline authoring recipe.
It resizes mesh vertices and every animation translation once, then fits
native Angemon's walk, condition walk and wing-assisted run to the existing
30-bone rig. The calibrated reference carrier is upright, with its complete boots on the
floor. Each pose lowers that carrier only as far as both real leg lengths
require; this avoids preserving the insect reference's deep knee bend. Mean
near-support knee flexion is 52.8 degrees, compared with native Angemon's 44.4. Native torso counter-motion,
shoulders, elbows and wings follow their original curves. Two-link solves
retain the actual leg lengths, with twist carried by the bent-leg plane;
this avoids knee Euler winding during the airborne run. Foot orientation and
clearance follow the native donor. A small, spread carrier correction clears
both complete boots at keys and renderer thirds.

The walk plays over 24 ticks, the condition walk over 28 and run over 16.
Root travel and sound times follow the same retime. Follow speeds are 15.58,
10.21 and 41.25 units/tick, above the existing pace floors. Repeated cycles
must close without accumulating pose drift. All other programs, including
idle, care, techniques and finisher, retain the original acting after the
uniform resize. Texture, rig, aliases and technique assignments stay intact.
Bone-local effect origins and condition offsets follow the same size factor.
The Status camera scales with the model to retain portrait readability. The
existing provider still applies its Buster Dive reach repair after resizing.

The player build uses the plain delta and provider pins, with no runtime
recipe, executable patch, buffer growth or heap cost. `mods/patches/series`
is unchanged because this repair changes model data only. After the existing
Buster Dive pass, the effective provider uses 82,368 of 100,352 resident bytes;
the largest sector-aligned cold read is 6,144 of 8,192 bytes. The fixed partner
slot has 17,984 bytes left. No map or story spawn names species 255.

English before/after disc builds keep `main_BSS_END` at `0x801cb740` and
198,576 bytes of heap. All 320 archive-backed screen setups fit with the same
minimum margin, 12,800 bytes on screen 207. PCSX-Redux with original 2 MB RAM
plays idle, walk and run on both discs. The full multilingual release and
physical hardware were not tested.

Replay with a source-disc extraction available:

```sh
mkdir -p build/review/before build/review/after
# BASELINE is a clean origin/main build before the repair.
cp build/BASELINE/imported-models/255.MMD build/review/before/255-Valkyrimon.MMD
python3 tools/models/field_animations/valkyrimon.py \
  --source build/review/before/255-Valkyrimon.MMD \
  --out build/review/after/255-Valkyrimon.MMD --report build/review/authoring.json
PYTHONPATH=tools python3 -W ignore -m unittest tools.test_valkyrimon
python3 tools/models/edit.py --from build/NAME check 255 --species-pins
```

The tests compare all unaffected programs against a uniform resize, check
both boots at keys and thirds, alternating foot lift, pace, repeated loops,
source/donor pins and original-console resident/cold-animation limits.
Videos should use models from the clean baseline and repaired disc builds,
a shared camera scale and explicit walk/idle/run captions. Studio footage
shows the decoded animation; emulator footage separately checks the game.
