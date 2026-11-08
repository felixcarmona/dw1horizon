# Horizon wiki proposal

The wiki is part of the main website and maintained only through this repository. It shares `web/style.css`, the header, locally hosted Plus Jakarta Sans, rounded surfaces and legal footer. There are no public edits, accounts, comments, external services, search providers, trackers or analytics.

## Information architecture

The home connects setup, partner care and evolution guides with Digimon, techniques, visual evolution trees and recruitment reference. A Digimon page joins incoming/outgoing routes, requirements on tap, learnable techniques, care and a spoiler-protected recruit record. Stable numeric IDs distinguish same-named species and techniques. Specialty summaries omit empty slots; learning calculations preserve original slot order.

The main page contains a “Wiki” hero button and header link. Its former Digimon and evolution sections are removed; download/patcher, changelog and remaining sections stay in place. Old main-page anchors and `/data/` localized routes/anchors redirect to the relevant wiki destination without opening spoilers.

## Current release and language URLs

The wiki always describes only the latest released game. The deployment’s selected release tag supplies all game inputs; page code and articles come from the dispatching commit. A page-only redeploy can use `tag=v0.0.7` without rebuilding the game. There is no version picker, archive or before/after-version prose. Release-dependent article values come from the tag, so the same public URL receives the correct current facts.

| Route | Content |
| --- | --- |
| `/wiki/` | Preferred-language entry with English fallback |
| `/wiki/<language>/` | Wiki home |
| `digimon/`, `digimon/<id>-<slug>/` | Text directory and species pages |
| `techniques/`, `techniques/<id>-<slug>/` | Move directory and move pages |
| `evolutions/` | Visual tree explorer |
| `recruits/` | Spoiler-controlled recruitment reference |
| `guides/`, `guides/<slug>/` | Authored articles |
| `search/` | Unified article/data search |

All nine page languages have generated HTML and local search JSON. Language switching preserves the article/entity, query and fragment. Spanish is Spain Spanish. The wiki ships without Digimon pictures. Text cards and compact tree nodes show names, labelled coloured level/attribute badges and specialties. Badge contrast is at least 4.5:1; labels carry the meaning alongside colour. An empty `web/wiki/owned-icons.json` map is the single future hook for reviewed owned local icons. See [the artwork audit](docs/wiki-art-audit.md), which lists the main page’s unchanged clips/maps separately.

## Generated facts and written explanations

`tools/wiki/model.py` reads the release snapshot with Git. Species, techniques, routes, care fields, training gains, difficulty factors, save-block requirements, quiz weights, localized questions and recruitment script assertions come from that tag. The manifest records game and presentation commits and must agree with the assembled engine. Unknown save expressions, changed quest operations and missing translations fail for review.

The repository supplies explanatory articles as structured JSON, UI catalogs, templates and reviewed recruitment annotations. `{save_blocks}` and `{pass_points}` are bound facts rather than copied release numbers. Bakemon’s mechanic is selected from actual script capability; its successful choices and displayed questions are extracted from the release script and localized text. Never substitute unreleased readable lines into a snapshot that only contains ghost-language dialogue.

## Spoiler policy

Any spoiler-sensitive information may appear **only inside a clearly marked spoiler, folded by default**. This includes secret recruits, quest solutions, hidden discoveries, special evolution routes, boss strategies, endings and Bakemon’s cemetery questions and answers. Basic setup and ordinary mechanics stay open. The Bakemon speech/partner mechanic explanation stays outside the spoiler; the conversation and successful choices stay inside it.

Do not expose a solution in page titles, summaries, navigation, images, alt text or search snippets. Ordinary recruitment cards show their heading, location and role while folding steps. The tagged City roster’s hidden flag keeps secret recruit identities, locations, services and steps inside the disclosure. Special-route species and tree branches are folded, excluded from open pickers, and shown only in folded search results. Quiz answers, scoring solutions and starter grids are folded. Deep links and search never open a spoiler automatically.

Use the shared `Pages.spoiler` renderer for generated information and article `spoiler_paragraphs` for sensitive authored text. Dialogue must use the release’s real localized strings, with readable Bakemon-partner text when the release implements that branch. Verify the question order and successful choice path against the script, and require every locale key. See [authoring documentation](docs/wiki.md) for the source map and verification procedure.

## Article authoring and review

Add an English record with title, safe summary and paragraphs. Verify every factual claim against released code/data, classify spoilers, and bind changing numbers/capabilities to the release model. Translate all eight other languages using the existing AI-assisted website/changelog approach, keeping placeholders and spoiler classification consistent. Review meaning, settings terminology and Spain Spanish, then update all reviewed source hashes in `review.json`. UI additions follow `web/i18n` key and variable parity checks. No runtime translation service is used.

At a release, source assertions and tests verify applicable behavior before generation. Changes that require interpretation fail for review. Correcting a page against the same tag changes presentation only; future game releases regenerate the facts at the same stable URLs.

## Search, budget and validation

One static JSON index per language combines articles, Digimon, techniques, evolutions and recruits. Secret species and recruitment records are classified as spoilers and rendered inside a closed, marked results group. Puzzle dialogue, solutions and sensitive article paragraphs are excluded from the index. Search loads only that language’s index and runs locally, including later queries with networking disabled. Type filters, localized labels, safe snippets and directory fallbacks are provided. Queries remain in the URL; nothing is logged remotely.

The complete Pages artifact must remain below 900 MiB and every file below 100 MiB. The nine-language wiki has a 64 MiB incremental cap, with no artwork payload; each locale index is capped at 400 KiB. The wiki is regenerated as one current release, with no retained archives. Budget checks run on the final artifact after release media extraction.

Validation covers every page type and language at desktop and phone widths, links and anchors, language switching, visual trees, absence of pictures and accessible badge contrast, closed spoilers, actual tagged/localized dialogue, spoiler-safe search, redirects, source/engine agreement and artifact size. See `web/test/wiki.mjs`, `tools/wiki/test_wiki.py`, `tools/wiki/check.py` and `tools/release_pages_test.py`. No game C code changes are required.

## First 20 articles

| # | Article | One-line scope |
| --- | --- | --- |
| 1 | Getting started with Horizon | Build from your own discs, boot, choose a language and know what to do on day one. |
| 2 | DuckStation on desktop | BIOS import, disc launch, per-game settings, RAM/CPU checks and first save. |
| 3 | DuckStation on Android | Storage access, BIOS, .cue launch, per-game RAM/CPU settings and memory-card setup. |
| 4 | ePSXe setup | Verified platform-specific BIOS, cards and supported settings; clearly state missing 8 MB features. |
| 5 | RetroArch setup | Choose and identify a tested PlayStation core; explain core-specific BIOS, cards and feature limits. |
| 6 | Playing in a web emulator on iPhone | Verify a named browser/emulator combination, BIOS import, persistent storage and save export before recommending it. |
| 7 | Memory cards, backups and updates | Tag-derived free-block requirement, per-game cards, slot assignment, backups and why updates should load in-game saves. |
| 8 | 2 MB, Chinese and 60 fps | Eight languages on original hardware; Chinese needs 8 MB; CPU overclock and title detection are separate. |
| 9 | Your partner's first day | Food, toilets, sleep, exploration and a small training plan without story spoilers. |
| 10 | Care mistakes and discipline | Explain what counts, warning windows, happiness, rest and consequences using tagged care rules. |
| 11 | Training at the gym | Stat gains, tiredness, food/rest and upgrades from the tagged training tables. |
| 12 | How gym x5 works | Explain block duration, gains, cancellation and fatigue using the actual release behavior. |
| 13 | How evolution requirements work | Four scoring groups, three required points, bonus alternatives, weight and stat scaling. |
| 14 | Evolution timing and competing targets | Time in form, Mega routes, NEW DIGIMON scope, tie behavior and why meeting a row is insufficient. |
| 15 | Learning techniques | Enemy executions, species lists, first specialty slot, candidate rolls and separate Brains training rules. |
| 16 | File City and recruiting residents | City roles, prosperity, prerequisites and links into spoiler-controlled resident records. |
| 17 | Hidden partner mechanics | Explain the release’s Bakemon mechanic openly; verified localized conversation and recruitment choices stay in a folded spoiler. |
| 18 | New-game quiz: questions, points and starters | Generate the full seven-question score table, tie rules and starter grid; keep solution tables and answer rules inside folded spoilers. |
| 19 | HARD and EASY explained | Current difficulty effects and interactions, checked against tagged runtime/configuration rather than proposals. |
| 20 | Player FAQ and troubleshooting | Updating, slow phone patching, storage quotas, texture-cache artifacts, button conventions and useful bug-report details. |

Prioritize setup, saves, evolution and techniques first. Player-question evidence in `docs/ideas.md` and the project report tracker motivates quiz scoring, evolution waits, emulator RAM/CPU, updating, text artifacts and patcher storage guidance. Treat requests for future features as requests, never as shipped features. Every article needs the same release and translation checks regardless of priority.
