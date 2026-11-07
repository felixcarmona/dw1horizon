# Horizon player data

The main website serves the guide at **`/data/`**, linked from its header.
It uses `web/style.css`, the shared header, buttons, language menu and Plus
Jakarta Sans. The guide vendors that font under its OFL license, so it needs
no CDN, trackers, external fonts or third-party scripts.

Build the release guide with Python 3.10+ and Git (stdlib only):

```sh
python3 tools/guide/build.py --ref v0.0.7
python3 -m unittest discover -s tools/guide -p 'test_*.py'
```

`tools/guide/out/` contains the generated guide. Serve it with a static server;
its language menu uses ES modules and local JSON. Default data is the current
release **v0.0.7**, read directly from Git, never uncommitted game content.
An explicit `--ref COMMIT --version VERSION` selects a pinned source snapshot.
The page shows the matching game version and source commit. Identical inputs
produce identical bytes, without timestamps.

Build the website presentation and guide together:

```sh
python3 web/build.py --tag v0.0.7 --out build/guide-site
python3 -m http.server --directory build/guide-site
```

`web/build.py` preserves any validated engine and `data/discs.json` already
in the destination. It overlays the website UI and generates `data/index.html`
and the localized language pages from the requested tag. The **Release and Pages**
workflow uses this same command with `RELEASE_TAG`, after validating the tag's package
and engine. A dispatch from main with `tag=v0.0.7` therefore takes presentation
code from main and player data from v0.0.7. Each later release regenerates its
own guide automatically. This command alone does not deploy anything.

Guide UI copy lives in `web/i18n/*.json` under `data.*`, translated into all nine
website languages. Each catalog generates its own guide page. The existing
`horizon.lang` preference and flag menu are shared. Game names stay unchanged.
`web/test/data.mjs SITE [SHOTS]` checks the assembled route, release snapshot,
theme, language switching/fallback, search/sort and phone layout in Chromium;
it also runs in the publication workflow.

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
is recorded in [the recruit audit](recruit-audit.md). Browser checks in
`web/test/data.mjs` exercise recruit filtering, sorting, empty results and all
nine pages at desktop and phone sizes. With a screenshot directory they also
capture recruit details and the phone table’s service columns.
