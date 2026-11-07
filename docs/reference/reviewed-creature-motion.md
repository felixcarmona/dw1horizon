# Creature motion and size review

The six models use plain, pinned deltas. `tools/models/reviewed_motion.py` is an
offline authoring recipe; it is not a runtime overlay. Input/output SHA-256,
native donor checksums, uniform size factors and original-console storage
measurements are in `content/modeldelta/reviewed-motion.json`.

| Species | Source evidence and change |
|---|---|
| Kurisarimon (431) | World 2003 M175KRSR has a suspended segmented shell and six trailing tendril chains. Its native battle-idle acting remains intact. The old sleep/scold clips drove the chains through the shell. Those two clips now retain native breathing, an eased withdrawal, staggered tendril motion and settling. Their original durations, termination and sound events remain. |
| Infermon (246) | Card Battle 165 has six rigid leg chains and broad two-part paws. The old sleep clip folds those paws above the shell; scolding loses ground contact. Native breathing now supplies the care acting while each foot keeps a fixed support position. The whole model and all clip translations are resized to 72%; bone-attached bubbles/effects and dimensions follow. Battle voice 54 and care voice 8 select HerculesKabuterimon's native insect banks. |
| WereGarurumon (62) | The existing reviewed walk already comes from native Leomon. All its rotations, timing and events remain. A uniform 74% resize of every mesh and translation track brings the 709-unit record height to 525, within the native Ultimate range. Bone-attached bubbles/effects and dimensions follow. The record remains below the unsplit 100,352-byte partner buffer. |
| Diaboromon (237) | Card Battle 179 supplies the mesh and reverse-folded legs. Field slots 0–4 now follow native SkullGreymon's clocks, weight shifts and alternating arm/leg acting, with an explicit anatomy map, proximal reach correction and a fixed reverse-hock bend branch. Its long hands receive an eased ground-clearance envelope. The previous live overlay is retired; battle/care programs stay intact. |
| Mammothmon (267) | World 2 M212MANM originally borrowed Garurumon's everyday animation programs. Native Monochromon now supplies field, care, condition and battle movement, with anatomy-specific four-leg contact paths. Head/neck rotation transfer is reduced for the much longer trunk; the original elephant mesh, trunk segments and ears remain. Voice 41, effects donor 47 and behavior template 47 match Monochromon. |
| SkullMammothmon (268) | World 2 M215SMAN has the same heavy-quadruped donor change, with its own front-leg indices and an independently mapped trunk. Native World 2 battle, hit, faint, get-up and technique performances remain. |

Infermon's across-clip scale pumping was already corrected before this review.
That correction is retained: every occupied clip uses the same per-bone scale,
including battle and weak-condition clips. The earlier Bakemon voice selection
was a deliberate donor choice, rather than a species-level classification; this
review replaces both voice settings with the native insect donor.

The official [Infermon card](https://en.digimoncard.com/cardlist/?card_no=BT22-059&search=true)
confirms its Ultimate level. The official
[Mammothmon](https://digimon.net/reference_en/detail.php?directory_name=mammon)
and [SkullMammothmon](https://digimon.net/reference_en/detail.php?directory_name=skullmammon)
entries identify the elephant and skeletal elephant forms. No texture, color,
form, evolution level or technique list changes are part of this review. Native
donors supply suitable game acting and sounds; they do not claim canonical voices.

## Replay and checks

Reconstruct the pre-edit final provider models at the checksums in the manifest,
then run, for each listed species:

```sh
python3 tools/models/reviewed_motion.py ID before/ID.MMD after/ID.MMD
python3 tools/models/edit.py --from DERIVE_OUT put ID after/ID.MMD
python3 tools/models/edit.py --from DERIVE_OUT check ID --species-pins
```

The recipe rejects different input/donor checksums and a different output. It
keeps textures intact. `edit.py put` records the plain delta, source/target pins
and final provider pins, including technique repairs.

Kurisarimon also has a distinct USA World 3 source model. Carry its edits with
`tools/models/variants.py make dw3-us --games USA_GAMES --reference-games PAL_GAMES`,
then run `variants.py check dw3-us --games USA_GAMES`. The variant retains its
own source mesh and unaffected programs, with separate delta and provider pins.

With the before/after files under `build/motion-review-models4/`:

```sh
PYTHONPATH=tools python3 -W ignore -m unittest tools.test_reviewed_motion
```

`MODEL_REVIEW` selects another folder containing `before/ID.MMD` and
`after/ID.MMD`. The checks decode all occupied clips, check stable Infermon
scales and care support contacts, preserve unaffected programs and mesh,
compare native donor clocks/sounds, retain every WereGarurumon rotation, and
verify resident/cold-animation budgets. Ground contact is also checked at nominal
60 Hz blend samples, including the repeating seam; the carrier-height envelope
clears those intermediate poses without changing the donor clocks or root travel. The support correction after Infermon's
integer resize changes ankle translations by a few model units to compensate
rounding amplified by its 2.5-scale paw pieces.

Visual review uses `tools/animstudio.py`'s Model/Panel renderer at 20 ticks per
second, side/three-quarter/front views, a shared camera scale for before/after,
and at least four complete cycles of each displayed clip. Native reference
rows accompany the donor-based comparisons. The screenshots and videos are
local review artifacts; they contain player-disc assets and are not published
in the repository.
