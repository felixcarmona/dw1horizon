# Horizon player data

The main website serves the guide at **`/data/`**, linked from its header.
It uses `web/style.css`, the shared header, buttons, language menu and Plus
Jakarta Sans. The guide vendors that font under its OFL license, so it needs
no CDN, trackers, external fonts or third-party scripts.

Build the release guide with Python 3.10+ and Git (stdlib only):

```sh
python3 tools/guide/build.py --ref v0.0.6
python3 -m unittest discover -s tools/guide -p 'test_*.py'
```

`tools/guide/out/` contains the generated guide. Serve it with a static server;
its language menu uses ES modules and local JSON. Default data is the current
release **v0.0.6**, read directly from Git, never uncommitted game content.
An explicit `--ref COMMIT --version VERSION` selects a pinned source snapshot.
The page shows the matching game version and source commit. Identical inputs
produce identical bytes, without timestamps.

Build the website presentation and guide together:

```sh
python3 web/build.py --tag v0.0.6 --out build/guide-site
python3 -m http.server --directory build/guide-site
```

`web/build.py` preserves any validated engine and `data/discs.json` already
in the destination. It overlays the website UI and generates `data/index.html`
and the localized language pages from the requested tag. The **Release and Pages**
workflow uses this same command with `RELEASE_TAG`, after validating the tag's package
and engine. A dispatch from main with `tag=v0.0.6` therefore takes presentation
code from main and player data from v0.0.6. Each later release regenerates its
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
  whose tree contains that route, and does not appear for v0.0.6.

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
