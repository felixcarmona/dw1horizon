# Website wiki

The website and wiki share `web/style.css`, the header, the legal footer and the locally hosted Plus Jakarta Sans font. The main site's Digimon button now opens the wiki directory. The old modal is no longer initialized or included in the page. `/data/`, its language pages and the old section, species and recruit anchors are compatibility redirects. `/data/discs.json` remains patcher metadata.

Build the page presentation from this checkout, with game inputs pinned to a release:

```sh
python3 web/build.py --tag v0.0.7 --out build/pages-site
python3 tools/wiki/check.py --site build/pages-site
python3 -m http.server --bind 127.0.0.1 --directory build/pages-site
```

This standalone command preserves an existing validated engine and disc metadata. The release workflow first runs the release tag's `release_pages.py build`, then overlays `web`, `tools/guide` and `tools/wiki` from the dispatching commit, runs `web/build.py`, adds the release's showcase archives, and checks the complete artifact. No game build is needed for a page-only redeploy. The workflow passes `--presentation-ref` explicitly because HEAD remains on the game tag during a page-only overlay. The manifest records both commits, and wiki stylesheet/script URLs include content hashes to avoid mixing cached presentation assets. The workflow no longer runs the old modal's separate Digimon exporter.

## Release model and routes

`tools/wiki/model.py` uses `git archive` on the selected ref. Every game input—including species, techniques, evolution rules, City roster, story/map assertions, quiz dialogue translations, care/training tables and icons—comes from that snapshot. The dispatching commit supplies templates, UI strings, articles, reviewed recruit annotations and native vector portraits.

`/wiki/<language>/<tag>/` is the canonical release home. Children include `digimon/`, `digimon/<id>-<slug>/`, `techniques/`, `techniques/<id>-<slug>/`, `evolutions/`, `recruits/`, `guides/`, `guides/<slug>/`, and `search/`. `/wiki/` follows the existing language preference; explicit localized release URLs always win. Switching language retains the release, page and query. All normal content is pre-rendered; search, tree dialogs and compatibility redirects use small local scripts. No-script entry links remain available.

The artifact contains the selected release, with all nine languages. Rebuilding for a different tag replaces the served wiki release rather than accumulating copies of all older releases. Source history and release-specific URLs keep revisions distinguishable. A deployment must not mix wiki data with another engine release: `check.py` compares the tag and full commit with `engine/current.json`.

Requirements use the existing guide's scoring and player-unit conversions, not a second handwritten requirements database. Routes incorporate the evolution tree and timed Ultimate rules. An empty technique entry means an unused slot. Specialties omit empty slots in summaries while preserving their positions for learning chances. Finishers retain zero base MP and species-specific power overrides. The old guide's readers/tests remain available as compatibility utilities; production uses the shared wiki model.

## Articles and source review

`web/wiki/articles/<language>.json` stores twenty articles per language as titles, summaries and paragraphs. This is structured, repository-authored content: it needs no Markdown parser, remote CMS or runtime translation service. The English draft and eight translations follow the existing AI-assisted website/changelog authoring approach. Spanish uses Spain Spanish. `review.json` pins the English and all localized source hashes; changing an article invalidates the build until translations are reviewed and those hashes are updated together. UI copy lives in `web/i18n/*.json`, with the existing key/variable parity check.

Bindings `{save_blocks}` and `{pass_points}` resolve from the selected release. Training gains, difficulty factors, evolution timing, quiz points, actual localized opening questions/answers and both starter grids are generated from its data. Memory-card space resolves the primary file-creation expression and numeric constants in the active patch series. The original two-block primary creation is distinguished from its old one-block fallback; a later primary one-block patch changes the article fact. Unknown expressions fail for review instead of guessing. The runtime and data used by v0.0.7 were checked; a synthetic later one-block patch and current-main HARD data are regression cases.

| Articles | Sources and checked claims |
| --- | --- |
| Getting started | `docs/release/README-players.md`, `web/data/discs.json`, `tools/discs.py`: supported source discs, output pair, patcher checks and save/update procedure. |
| DuckStation desktop / Android | Tagged title settings and `Choose-rendering-rate-from-CPU-speed.patch`, language loading, save creation; named emulator settings checked against [DuckStation upstream](https://github.com/stenzek/duckstation). Android navigation is described by settings name, not an untested tap path. |
| ePSXe | [Official Android setup](https://www.epsxe.com/android/setup.html): base-folder permissions, BIOS and game access. No claim of 8 MB support for every build. Game requirements remain release-bound. |
| RetroArch | [Official BIOS guide](https://docs.libretro.com/guides/bios/): core-specific BIOS and system directory. Cards and enhancements explicitly depend on the chosen core; no claim that all cores support expanded RAM. |
| iPhone web | [EmulatorJS supported systems](https://emulatorjs.org/docs/systems/): PlayStation support in the framework. No iPhone/browser combination is certified. Import, export and reopen checks are prerequisites for the player's chosen host. The wiki embeds no emulator. |
| Memory cards and updates | Active save patches, including primary card creation and `SAVE_V1_BYTES`/`SAVE_V2_BYTES`; tagged players' guide: save states retain old executable/disc offsets, memory cards are the update path. |
| RAM / frame rate | `docs/building.md`, `docs/mods/options.md`, tagged players' guide and title scheduler patch: Chinese 8 MB, other eight languages 2 MB, 250% CPU recommendation, 20/60 fps selection and 20 Hz logic. The builder checks the selected release's frame-rate guidance. |
| First day / care | `content/tables/care-rules.json`, species partner fields, `docs/reference/partner.md`: individual food/sleep, distinct needs, care mistakes and current-form evolution counters. Advice is a routine, not a claim of a guaranteed evolution. |
| Training / gym x5 | `training.json`, `training-gains.json`, `brain-training.json`; training-block patches: R2 x1/x5, sequential ordinary awards, care/lifetime costs, stop checks and separate Bonus Try. Only base slot-zero awards are labeled base gains. |
| Evolution requirements / timing | `evolution-tree.json`, `evolution-rules.json`, species rows and `docs/reference/partner.md`: four groups, required score, alternatives, stat normalization, weight bands, competing-target order and time in form. The time table distinguishes the timed Mega route from the original Ultimate-to-Machinedramon route. |
| Learning techniques | `docs/reference/partner.md`, `docs/reference/combat.md`, technique and species data; battle learning/runtime checks described by the existing guide: execution need not hit, first matching slot, one award among successful candidates, no Brains effect on that roll, separate training learning and base MP. |
| File City | `city-residents.json`, `story/base/city/city.dws`, map placements, story scripts and checked `tools/guide/recruits.json` annotations: roster, prosperity, places, requirements and HP. Shellmon accepts the reviewed pre/post refactor operations without changing its quest meaning. Other script drift fails review. |
| Hidden mechanics | Bakemon partner guards in the cemetery scripts and `tools/test_bakemon_translation.py`; only the translation mechanic is described. Questions, answers and dialogue are excluded. Food/sleep and slot-order notes use species data. |
| Opening quiz | `new-game.json`, `text/<language>.json` named `name.quiz.*` keys, `story/new-game-quiz.dws`, `tools/starter_quiz.py`, and the starter-quiz runtime patches: seven questions, answer positions, sparse weights, tie order, 45 cells and NEW DIGIMON variants. Only these named opening-quiz text keys are exported. |
| Difficulty | Tagged `docs/mods/options.md`, EASY runtime patch and `battle-formulas.json`: EASY's damage/poison effects, limits and VS exclusion. v0.0.7 has no HARD; later HARD factors come from that release's table. |
| FAQ | Players' guide and existing website storage/error messages; texture-cache investigation documented in `docs/investigations/item-bank-text.md` and the text-clear patches. The Android workaround is conditional, not a diagnosis of every text problem. Reports should include version/platform/renderer and exact trigger. |

External references are authoring sources, not page dependencies. The delivered wiki loads no remote fonts, scripts, images, analytics or search service. BIOS and game files are never supplied by the wiki. Emulator/device walk-throughs were not run as part of this website implementation; the articles avoid device-certification claims.

## Spoilers and images

Recruit methods and prerequisites are in closed `<details>` elements, and a deep link does not open them automatically. Search indexes include only safe recruit names, places and services. Bakemon receives only the approved mechanic hint. Its old solution text was removed from the delivered UI catalogs and recruit annotation as well; `check.py` verifies the protected fields against the localized hint. The snapshot reader never exports cemetery dialogue into the model.

The existing hand-drawn `content/icons/*.txt` idle frames are converted into small local SVGs. Native partners without those drawings use original vector portraits in `tools/wiki/art.py`. No disc artwork is added to source or fetched from another host. SVG resources are shared by all locales, include explicit dimensions and alt text, and lazy-load. The evolution graph keeps real connected from/to nodes, with tap-to-open requirements and a link to the selected Digimon. Desktop uses a horizontal tree; phones use a vertical trunk so targets remain visible without horizontal panning.

## Budgets and checks

The incremental wiki limit is 64 MiB. Each language's selected-release search index must be at most 400 KiB; only that locale's index loads, and further queries/filters run without requests. The complete Pages output must stay below the existing 900 MiB limit, with each file below 100 MiB. `check.py` runs after showcase extraction in the workflow and checks all generated local links and anchors, resources, protected recruit copy, engine provenance and budgets. Font files are shared under `media/font/` with their OFL license.

```sh
python3 -m unittest discover -s tools/wiki -p 'test_*.py'
python3 -m unittest discover -s tools/guide -p 'test_*.py'
python3 tools/release_pages_test.py
node web/test/i18n.mjs
python3 tools/wiki/check.py --site build/pages-site
# Set PUPPETEER_MODULE and CHROMIUM as for the existing browser tests.
node web/test/wiki.mjs build/pages-site build/wiki-review
```

Browser checks visit ten page types in all nine languages at 1440 px and 390 px. They exercise language switches, local images, tree requirements, folded spoilers, search filters/empty results with networking disabled after index load, and legacy routes/anchors. Screenshots include the six requested views in English and Spain Spanish at both widths. The browser and its temporary server close in `finally`.
