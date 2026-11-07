# Scold condition bubble — design review

Status: four offline mockups; selection and implementation are pending. No game
code, patch, disc, or texture input is changed by this proposal.

A Square badge caused by Scold must have a condition bubble explaining it. This
bubble means a justified Scold action is available after misbehaviour, such as
refusing food. It does not mean hunger, low discipline, or general unhappiness.

## Four options

| Option | Pictogram | Rationale |
| --- | --- | --- |
| 1 | The game's own Scold menu icon | Preferred baseline; shares the field menu's visual vocabulary. |
| 2 | Scold icon with a small red warning dot | Preserves the silhouette with a stronger warning cue. |
| 3 | Scold icon with a small red anger accent | Preserves the silhouette with a sharper behaviour cue. |
| 4 | One bold red anger mark | The only alternative to the native Scold icon; no letters or text. |

The numbered review sheet is generated at `build/scold/SCOLD-options-1-4.png`.
Every row shows a complete 320×240 field composite for Scold alone with Square,
a second composite beside another condition, and exact nearest-neighbour 4×
crops of both. These are design composites over existing 2 MB captures, not
screenshots of a working Scold bubble. The neighbour is the existing HP need.

Option 1 derives the actual `MENU_OPTIONS[5]` artwork: ETCTIM entry 4, UV (0,40),
20×20 cell, palette 13, corresponding to CLUT (256,509). The occupied silhouette
is 18×18. It is fitted without filtering into an 11×11 screen-pixel footprint
inside the existing 17×14 captured field bubble. “Native size” on the sheet means
actual field display size; it does not mean pasting the larger menu cell at 1:1.
Options 2 and 3 add only small red accents. There is no enlarged bubble or text.

## Visibility contract for a later implementation

Use the same current eligibility as the badge's Scold case: the care collector
adds `FEED_SCOLD` exactly when `ITEM_SCOLD_FLAG == SCOLD_PENDING` (1). Reuse that
eligibility rather than introducing a separate refusal timer or condition bit.
Apply the existing field/HUD visibility gates and ordinary bubble transition.

- Scold alone: show this bubble with the Square care badge.
- Scold plus other needs: include it once in the existing fixed bubble layout.
- Inventory contents do not affect Scold eligibility.
- Clear it when Scold ceases to be available, including after Scold is used or
  the pending state is cleared by ordinary movement. No extra linger timer.
- Unjustified Scold being selectable through the general field menu does not
  qualify. The trigger is the justified care action represented by the badge.
- Other needs and their actionability keep their existing rules.

Use the existing shell, bob, fixed group spacing, single-bubble tail, multi-bubble
tail suppression, screen clamps, and Square placement. Any later implementation
must handle the additional active slot and verify the full condition combination.

## Evidence and reproduction

`design/scold/render.py` derives the menu icon from local player-disc inputs and
uses `hp29.png` and `hp31.png` from the existing original 2 MB HP/MP proof. The
source proof records 2,097,152 bytes of RAM. The renderer records source SHA-256
hashes, sprite coordinates, footprint, and zoom in `build/scold/evidence.json`.
Disc artwork and full game captures remain untracked.

```sh
.venv/bin/python design/scold/render.py --captures PATH_TO_EXISTING_HPMP_PROOF
```

The complete sheet was visually inspected at native scale and 4× before review
upload: all four silhouettes fit the shell and remain distinct; the single tail,
condition neighbour, and Square are visible. Native Scold is the clearest match
to the existing menu and is the recommended starting point.

No build or emulator was started. No C changed, so heap measurement does not
apply to this design-only commit. Animation, live availability transitions,
maximum bubble count, edge clamps, and original 2 MB heap safety remain untested
for any future implementation. A visual selection does not implement the feature.
