# Horizon player data

A small offline guide for technique learning, partner species and evolution.
Open `out/index.html` directly; search and sort use plain JavaScript. All assets
are local. No server, network requests, dependencies, disc data or artwork.

Build with Python 3.10+ and Git from this checkout:

```sh
python3 tools/guide/build.py
python3 -m unittest discover -s tools/guide -p 'test_*.py'
```

The default reads **origin/main**, directly from Git, and labels the output
“data for the next version” (upcoming 0.0.7, rather than released 0.0.6).
It does not fetch or read uncommitted content. The source commit appears in the
page. For a matching release or a reproducible pinned snapshot:

```sh
python3 tools/guide/build.py --ref v0.0.6 --version 0.0.6
python3 tools/guide/build.py --ref COMMIT --version next --out build/guide-site
```

Identical source commits, version labels and builder/assets produce identical
bytes; there are no timestamps. The builder uses only the standard library.
`out/` is the checked-in generated site. After rebuilding, copy its three files
to `build/guide-site/` for review or packaging.

## Sources and scope

Only these owned files supply guide content:

- `content/techniques/*.json`: all technique rows; MP cost is multiplied by three
  for the displayed base battle cost. Range and status codes are labeled using
  `docs/reference/combat.md` (Technique table; Executing a technique).
- `content/species/*.json`: forms with a `partner` block, their ordered specialty
  slots, move lists, requirements and finisher overrides. Shared technique names
  resolve through their explicit IDs. The final technique with ID 58–112 is the
  finisher; IDs 113+ are intrinsic/other moves.
- `content/tables/evolution-tree.json`: current NEW DIGIMON on routes,
  requirement overrides, timed Ultimate routes and special-route notes.
- `docs/reference/partner.md`: Learning techniques; Evolution → Score, timing and
  added-species rules. HP/MP thresholds are multiplied by ten; happiness is
  converted to the player-facing 0–100 scale. The documented Tsunomon→Gabumon
  weight override is shown separately. Special and laboratory forms are labeled;
  the Devimon note reflects its ordinary routes in the current tree as well.

The learning explanation follows `battleMoveLearning` in `main/battle_ui.c`
and enemy execution recording in `BTL_setupMoveExecution` in
`btl/battle_main.c`: casting records a distinct normal technique, with no hit or
partner-target test. The battle learning function checks the first matching
specialty slot and species move list, rolls the technique's chance, and selects
one successful candidate. Brains does not enter this roll. This differs from
learning through Brains training, which has separate rules.

Evolution lists ordinary and timed routes, with special-route notes. It does
not enumerate evolution items or NEW DIGIMON off routes. Four requirement
groups score at most four points; three qualify. The selection explanation
preserves the documented preference for unraised targets, the required-stat
average comparison for Champion/Ultimate targets, its accumulator behavior,
and Rookie-target tie order. No engine changes or game build are needed.
