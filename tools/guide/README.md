# Horizon player data

The production website now serves the unified wiki at `/wiki/<language>/`. `/data/` and its localized pages/anchors are redirects. See [wiki maintenance and spoiler rules](../../docs/wiki.md).

This directory retains shared readers, recruitment annotations, the local font and legacy standalone guide utilities. The production builder uses these readers through `tools/wiki/model.py`; `web/build.py --tag <release> --out <directory>` generates the latest-release wiki with presentation from the dispatching commit and game data from that tag. Run `web/test/wiki.mjs` for the production browser checks.

The legacy standalone exporter remains useful for audits, with Python 3.10+ and Git:

```sh
python3 tools/guide/build.py --ref v0.0.7
python3 -m unittest discover -s tools/guide -p 'test_*.py'
```

It writes to `tools/guide/out/`; it is not deployed. Its older table UI and `web/test/data.mjs` are compatibility utilities, not the production wiki. Shared `data.*` UI copy remains in `web/i18n/*.json`. The wiki keeps the existing `horizon.lang` preference and hosts the shared font locally under its OFL license.

## Sources and rules

- `content/techniques/*.json`: every technique; MP ×3 is the base battle cost.
  Finishers cost no MP despite their unused raw MP field.
  Range/status codes follow `docs/reference/combat.md`.
- `content/species/*.json`: all partner-enabled forms, original specialty slot
  positions, move lists, requirement rows and species finisher overrides. Shared
  technique names use explicit IDs; the last listed ID 58–112 is the finisher.
- `content/tables/evolution-tree.json`: NEW DIGIMON on routes, requirement
  overrides, timed Ultimate routes and special/laboratory notes.
- `docs/reference/partner.md`: learning and evolution scoring. HP/MP thresholds
  are ×10; happiness uses the status screen's 0–100 scale with rounded boundaries
  marked. The later Tsunomon→Gabumon weight override appears only in snapshots
  whose tree contains that route, and does not appear for v0.0.7.

`battleMoveLearning` in `main/battle_ui.c` checks the first matching specialty
slot, species list and known moves, rolls the technique's chance, then selects
one successful candidate. Brains is absent. `BTL_setupMoveExecution` in
`btl/battle_main.c` records distinct enemy normal-technique executions without
a hit or partner-target check. Brains training has separate rules.

Evolution requires three of four groups: care, weight, stats and one bonus.
The explanation preserves the documented unraised-target preference, stat
average comparison and its accumulator behavior, and Rookie-target tie order.
Special/laboratory forms are labeled; item evolutions and NEW DIGIMON off
routes are outside this guide. No game-runtime changes or disc build are needed.

The font is [Plus Jakarta Sans from Google Fonts](https://github.com/google/fonts/tree/main/ofl/plusjakartasans),
redistributed unchanged with `assets/font/OFL.txt`.

## Recruits

The Recruits table covers the extended story’s complete City roster. It shows
player-facing places and screen numbers, game-clock windows, quest steps,
City roles and prosperity. Search and sorting work independently of the other
tables. All nine pages include translated instructions and accessible controls.

`content/tables/city-residents.json` defines membership; `story/base/city/city.dws`
and each species’ level determine prosperity. Battle HP resolves the species’
`wild.hp` plus the placed NPC’s `content/maps` adjustment, or the story mod’s
explicit `npc(hp=...)`. Place vocabulary comes from the snapshot’s authored
names and language place catalogs. Digimon names follow runtime conventions:
the content name in eight languages and the Chinese glossary when present.
Older snapshots without that glossary retain their own content names.

`recruits.json` supplies reviewed quest explanations and source assertions for
base scripts and the story mod. The build reads those scripts from the selected
snapshot and refuses a missing roster annotation or a changed asserted operation.
The explanations are presentation annotations, not another game-data roster.
A changed quest needs its annotation, assertions and nine `data.recruit.*`
translations reviewed together. The source snapshot displayed on the page
applies to every table; generated output never reads working game data.

`test_recruits.py` checks exact roster coverage, prosperity, changed-script
rejection, map HP deltas, names and every language. The ten-entry source review
is recorded in [the recruit audit](recruit-audit.md). Production browser checks in `web/test/wiki.mjs` cover all nine languages and desktop/phone widths, closed recruitment spoilers and legacy redirects. The wiki derives Bakemon’s conversation from tagged localized text; the legacy annotation is not a dialogue source.
