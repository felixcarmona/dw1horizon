# Horizon wiki proposal

Proposal and local mockups only. No deployment, production route changes or game changes are included.

The wiki should be part of the main website: the same header, Plus Jakarta Sans, narrow reading measure, sunset-to-white background, rounded surfaces and quiet buttons from `web/style.css`. It should feel like opening another part of Horizon, with useful cross-links rather than four disconnected tables. It is maintained only through the project repository: no accounts, public editor, comments or community submissions UI.

## One home for guides and reference

The wiki home offers three starting points: set up the game, raise a partner, and plan an evolution. A single search sits above those paths. Below them, data directories let experienced players go directly to Digimon, techniques, evolutions or recruits. A small FAQ draws on recurring player questions without copying Discord messages, names or identifiers.

| Section | Contents | Main connections |
| --- | --- | --- |
| Start here | Build a disc, choose an emulator, first day, updating | Patcher, setup guides, memory cards |
| Care and training | Food, rest, mistakes, discipline, gym, x5 | Partner care data, training rules |
| Digimon | One page per partner form | Incoming/outgoing evolutions, move list, care, recruitment |
| Techniques | Searchable directory and individual move pages | Learnable species, specialty slots, candidate chances, MP and status |
| Evolutions | Route explorer and requirements explanation | Target requirements, age gates, special routes, NEW DIGIMON setting |
| File City and recruits | Residents, roles, prosperity, places and prerequisites | Digimon pages and spoiler-marked recruitment steps |
| Mechanics and FAQ | Quiz table, difficulty, hidden mechanics, troubleshooting | Release facts and short explanatory articles |

A Digimon page is the join between these sections. Keep raising a species distinct from recruiting its resident. Use a stable entity ID, not a display-name join; species twins need an explicit reviewed resident-to-partner association. Do not merge same-named records blindly. Retain technique IDs where names collide, species-specific finisher overrides and original specialty slot positions, including empty slots.

On mobile, navigation wraps, directories become compact cards, and article contents move above the text. Numeric tables scroll inside their own container when necessary. Recruitment instructions are closed by default, labeled before opening, and omitted from search snippets. The Bakemon article may say that a Bakemon partner translates Bakemon's speech. **Never publish the cemetery questions, answers, answer sequence or translated dialogue**, including in HTML, JSON, search indexes, screenshots, accessibility text or hidden disclosures. Do not simply wrap forbidden material in a spoiler toggle.

## URLs, language and version

Use explicit language and immutable release paths for canonical content:

| Route | Purpose |
| --- | --- |
| `/wiki/` | Lightweight language entry, with a usable English link without JavaScript |
| `/wiki/en/` | Current-release wiki home, visibly identifies its release |
| `/wiki/en/v0.0.7/` | Immutable release home |
| `/wiki/en/v0.0.7/digimon/3-agumon/` | Species page, ID is authoritative; slug aids reading |
| `/wiki/en/v0.0.7/techniques/2-spit-fire/` | Technique record |
| `/wiki/en/v0.0.7/evolutions/` | Directory / explorer with linkable target IDs |
| `/wiki/en/v0.0.7/recruits/` | Residents and filterable City directory |
| `/wiki/en/v0.0.7/guides/duckstation-android/` | Written article evaluated for this release |
| `/wiki/en/v0.0.7/search/?q=agumon&type=all` | Shareable search with language and release scope |

Use the same paths for `es`, `pt-br`, `fr`, `de`, `it`, `ja`, `ca`, `zh-hans`; keep guide slugs stable across languages. Add canonical and `hreflang` alternates. The first `/wiki/` visit follows the existing `horizon.lang` preference and browser-language policy. An explicit localized URL always wins. A language switch preserves the release, article/entity and search query; show a clear message if an older release lacks that article. Normal document navigation must not require JavaScript.

The version badge is always visible. A release picker offers current and retained releases, never silently mixing an old record with current requirements. `/wiki/en/` may follow the release currently served by the patcher, but article and search links resolve to its concrete release. Distinguish **game release**, **article revision** and **emulator build verified**. An emulator guide can be updated independently of game mechanics. Display an unverified status instead of claiming a fresh device test.

Preserve existing deep links. The main site's Digimon button should open the wiki's Digimon directory; its former species anchors need explicit ID mappings. `/data/` and its language pages become compatibility entry pages linking to the matching new directories, while a small local script can map old table anchors to records. Keep a no-script directory of replacement links. **Do not repurpose or move `/data/discs.json`**, which the patcher still needs. GitHub Pages has no configurable server redirect layer: generate real HTML compatibility files rather than assuming 301 rules.

## Generated facts and written explanations

| Input | Output | Handling |
| --- | --- | --- |
| Tagged `content/species`, `content/techniques`, `content/tables/evolution-tree.json` | Names, slots, moves, finisher overrides, routes, target requirements | Reuse `tools/guide/build.py` semantics; preserve timed and special route distinctions |
| Tagged City roster, story scripts, map placements; reviewed `tools/guide/recruits.json` assertions | Recruits, places, windows, HP, roles and prosperity | Reuse checked annotation reader; fail on changed scripts or missing roster coverage |
| Tagged training, care, new-game and difficulty configuration, runtime where needed | Small cited facts/tables embedded in articles | Add explicit readers and source assertions; do not transcribe numbers into prose |
| Repository Markdown plus structured metadata | Guides, short answers, explanations and navigation | Written and reviewed; numeric entities/facts are references to generated fields |
| Existing `web/i18n/*.json`, name glossaries and place catalogs | UI, entity and place labels | Keep existing terminology and nine-language contract |

The current main site has two overlapping generators: `tools/site_digimon.py` for its modal and `tools/guide/build.py` for `/data/`. They do not have identical coverage or formatting. Make a shared normalized release model before replacing either presentation. Port and compare the existing semantics; do not concatenate both exports and call that unification. Keep the data tables available as an advanced view, while species pages provide the approachable default.

Use typed Markdown references such as `{{fact:training.block.sessions}}` or `{{digimon:3}}` (proposed syntax) for facts and links. Resolve them from the selected release; reject unknown keys. That avoids nine translations each carrying an independently copied threshold. Evolution explanations must retain the four scoring groups, bonus alternatives, timing, competing targets and NEW DIGIMON scope. Three points do not promise one particular result. Technique articles must preserve the difference between a candidate learning roll and the final awarded move, plus the base MP cost and modifiers.

Some requested content is not in the existing guide export. Extend the snapshot input allowlist deliberately for training, care, new-game quiz and difficulty. A quiz reader must cover all seven questions, point weights, tie rules, cell mappings and NEW DIGIMON on/off results from the selected tag. Publish that table only after checking it against the runtime and source text. HARD/EASY needs its tagged configuration and option behavior checked; a design proposal such as `HARD-PROPOSAL.md` is not release evidence. The initial article list below is a backlog, not a claim that all these articles are ready.

## Adding, translating and reviewing an article

Proposed layout: `web/wiki/articles/<slug>/en.md`, eight sibling translations, and a `meta.json` with ID, category, summary, aliases, spoiler level, source assertions, applicable releases, reviewed game commit, emulator build/platform where relevant, source hash and translation hashes. `web/wiki/` is a proposed production destination; this change only adds `design/wiki-mockups/`.

1. Write concise English using verified release sources. Keep each article about one player task. Add source references and fact bindings before translating. For emulator guides, record exact app build and platform; use a real device walkthrough to verify tap paths and a fresh memory-card save.
2. Apply the existing AI-assisted website/changelog workflow: translate the approved English copy into `es`, `pt-br`, `fr`, `de`, `it`, `ja`, `ca`, `zh-hans`, with the existing game-name glossary and terminology. Keep IDs, fact references, URLs, Markdown structure and variables intact. This extends the existing authoring practice; there is no claim that an article translation CLI already exists.
3. Review every translation for meaning, numbers, menu labels and spoilers; check Japanese/Chinese wrapping in the browser. English edits invalidate translation hashes and trigger regeneration/review of changed sections. AI translation is a draft stage, not approval.
4. Validate metadata, all nine locales, unique IDs, links/anchors, bindings, source assertions and translation hashes. Review the rendered diff and desktop/phone screenshots. Merge through ordinary project review; only maintainers publish.
5. Publish only a complete nine-language article set. If a new article is incomplete, omit that article in all locales until ready; a previously published article with a stale translation blocks the wiki build. Never label English fallback as a finished translation.

Search and all data rendering happen in the visitor's browser or at static build time. No hosted translation API runs on page load; the authoring workflow is separate from the delivered wiki. No analytics, telemetry, remote search, third-party scripts, externally loaded fonts or embedded social widgets. Vendor the existing licensed font once and share it across all wiki pages. External documentation links are ordinary optional links, not runtime dependencies.

## Staying correct per release

`web/build.py --tag …` already takes presentation from the invoking checkout while `tools/guide/build.py.snapshot()` reads game inputs with `git archive` at the selected tag. The Pages workflow uses that split today. Keep it and add the wiki build there in a later implementation, with a normalized model shared by the main Digimon experience and data directories. Read **every** game fact from the pinned snapshot, including rules, scripts, maps and translated game labels. Avoid imports which accidentally read working-tree game files.

Emit a deterministic wiki manifest containing game tag, resolved game commit, presentation commit, schema version, article revisions, source assertion results and output hashes. Verify its game tag against the served engine metadata. An article edited on main may apply to an older release only if its bindings and applicability checks pass for that release. Never use current recruitment prose without asserting it against the old scene. If a release lacks a feature, state its absence or omit the article; do not substitute current facts.

At each cut, compare normalized facts with the last release, identify affected articles, rerun assertions and regenerate affected translations. Source assertions should cover semantic behavior, not just file hashes; a changed file needs review rather than an automatic claim that the article is wrong. Release publication fails if a required fact, translation, checked recruit operation or article applicability is unresolved. Page-only corrections can rebuild the wiki against the same tag without rebuilding the game.

Validation should include normalized parity with the current data guide; distinct move IDs and specialty slots; evolution scoring/timing; full recruit coverage and script drift; quiz samples and tie cases; nine-language parity; links and locale switching; keyboard search and result filters; no-script access; no horizontal page overflow; forbidden cemetery content exclusion; no external requests; and byte totals. This proposal changes no C: executable/heap measurements and a disc build are unnecessary for these mockups.

## Search without services

Build one compact index per language and release from rendered article headings/summaries and normalized data. Every record has a type, stable ID, title, short safe snippet, aliases, release and URL. Rank exact entity/alias matches first, then title tokens, headings and body terms. Return mixed results with Article / Digimon / Evolution / Technique / Recruit labels and type filters; keep release and language in the result context.

Normalize case and diacritics for Latin text while preserving display labels. Use locale-aware segmentation for Japanese and Chinese with a small local fallback where `Intl.Segmenter` is unavailable. Index glossary aliases and original game names to find localized Digimon. Never send queries away from the page; keep them only in the URL, without query logs or analytics. Show a useful zero-result state and links to directories.

Load only the selected release/locale index when search opens. Worker search keeps typing responsive as content grows. Do not preload nine languages or every retained release. Strip source metadata and hidden spoilers from snippets; forbidden cemetery text must never enter an index. Give the search field a visible/accessible name, keyboard controls and an announced result count; implement directory links for no-script users.

## Pages budget and retention

The existing `tools/release_pages.py` caps the prepared site at **900 MiB** and each file below **100 MiB**. Preserve those project limits. A wiki budget is an addition to the patcher, engine and showcase assets; unused headroom is not a media allowance.

| Allocation | Proposed maximum, uncompressed output |
| --- | ---: |
| All wiki HTML and JSON for one release, nine languages | 18 MiB |
| Of that, search index per language/release | 400 KiB each, included above |
| Shared font, CSS and JS across retained releases | 2 MiB |
| Optional optimized instructional images across retained releases | 8 MiB total |
| Current plus two previous releases | 54 MiB for release-specific content |
| Total incremental wiki budget | **64 MiB** |

These are build gates to measure, not a prediction of final size. Start with current release only. Add old releases only while the assembled site remains below 900 MiB; retain current plus at most two previous releases. Deduplicate fonts and images; do not duplicate engine packs, videos or all showcase maps for wiki versions. If the budget fails, stop publication and prune an old wiki version in a reviewed change before retrying. Provide an unavailable-version page and links to source history for retired releases. Keep versioned source and manifests in Git; no external archive service is required. Recheck assembled size **after** all wiki and media overlays: the existing package-preparation check runs before subsequent Pages additions.

Target first wiki visit: HTML + shared font/CSS/JS below 600 KiB transferred; no article screenshots loaded until needed. Target search adds at most one 400 KiB uncompressed index. Measure compressed transfer and actual build totals separately. Host instructional pictures locally, with alt text and dimensions. Do not introduce videos in this first release.

## First 20 articles

| # | Article | One-line scope |
| --- | --- | --- |
| 1 | Getting started with Horizon | Build from your own discs, boot, choose a language and know what to do on day one. |
| 2 | DuckStation on desktop | BIOS import, disc launch, per-game settings, RAM/CPU checks and first save. |
| 3 | DuckStation on Android | Storage access, BIOS, .cue launch, per-game RAM/CPU settings and memory-card setup. |
| 4 | ePSXe setup | Verified platform-specific BIOS, cards and supported settings; clearly state missing 8 MB features. |
| 5 | RetroArch setup | Choose and identify a tested PlayStation core; explain core-specific BIOS, cards and feature limits. |
| 6 | Playing in a web emulator on iPhone | Verify a named browser/emulator combination, BIOS import, persistent storage and save export before recommending it. |
| 7 | Memory cards, backups and updates | Two free blocks, per-game cards, slot assignment, backups and why updates should load in-game saves. |
| 8 | 2 MB, Chinese and 60 fps | Eight languages on original hardware; Chinese needs 8 MB; CPU overclock and title detection are separate. |
| 9 | Your partner's first day | Food, toilets, sleep, exploration and a small training plan without story spoilers. |
| 10 | Care mistakes and discipline | Explain what counts, warning windows, happiness, rest and consequences using tagged care rules. |
| 11 | Training at the gym | Stat gains, tiredness, food/rest and upgrades from the tagged training tables. |
| 12 | How gym x5 works | Explain block duration, gains, cancellation and fatigue using the actual release behavior. |
| 13 | How evolution requirements work | Four scoring groups, three required points, bonus alternatives, weight and stat scaling. |
| 14 | Evolution timing and competing targets | Time in form, Mega routes, NEW DIGIMON scope, tie behavior and why meeting a row is insufficient. |
| 15 | Learning techniques | Enemy executions, species lists, first specialty slot, candidate rolls and separate Brains training rules. |
| 16 | File City and recruiting residents | City roles, prosperity, prerequisites and links into spoiler-controlled resident records. |
| 17 | Hidden partner mechanics | Include Bakemon's translation ability while excluding every cemetery question, answer and dialogue line. |
| 18 | New-game quiz: questions, points and starters | Generate the full seven-question score table, tie rules and starter grid; this is separate from cemetery content. |
| 19 | HARD and EASY explained | Release-specific effects and interactions, checked against tagged runtime/configuration rather than proposals. |
| 20 | Player FAQ and troubleshooting | Updating, slow phone patching, storage quotas, texture-cache artifacts, button conventions and useful bug-report details. |

Prioritize setup, saves, evolution and techniques first. Player-question evidence in `docs/ideas.md` and the project report tracker motivates quiz scoring, evolution waits, emulator RAM/CPU, updating, text artifacts and patcher storage guidance. Treat requests for future features as requests, never as shipped features. Every article needs the same release and translation checks regardless of priority.

## Review mockups

`design/wiki-mockups/` builds four static, locally served screens: wiki home, Agumon, DuckStation Android article and mixed search results. They reuse `web/style.css` unchanged and the guide's vendored font. The header keeps the main site's brand and simple navigation, with Wiki replacing Player data; the English label is a preview label, not a working nine-language selector.

All displayed species counts, moves, learning chances, base MP, evolution targets/requirements, care fields and recruitment facts come from **v0.0.7**, commit `5861f8c8fb7ea3ffc54fba0d47d4b7582ba91baf`, via the existing guide readers. The mockup has 291 partner forms, 122 technique records and 72 recruits for that snapshot. Counts are data coverage, not advertising totals. Its search is deliberately a small working preview index, labeled as such, rather than the proposed full wiki search. Some home topic links lead to the closest available preview. This is not a production routing implementation.

The Android article demonstrates the full reading layout and includes BIOS, expanded RAM for Chinese, CPU 250%, two-block memory cards, per-game cards and the reported texture-cache workaround. It explicitly marks Android device/tap-path validation as pending. The frame-rate explanation comes from `docs/release/README-players.md`; the emulator settings are consistent with [upstream console settings](https://github.com/stenzek/duckstation/blob/master/src/duckstation-qt/consolesettingswidget.cpp), and the texture-cache caution is supported by [upstream graphics settings](https://github.com/stenzek/duckstation/blob/master/src/duckstation-qt/graphicssettingswidget.cpp). Neither upstream desktop source is a substitute for an Android walkthrough.

Desktop and phone PNGs are review outputs under `build/wiki-review/`, excluded from the commit. Reproduction and browser capture commands are in the mockup README. Approval of this proposal would precede production work: shared data model, content/translation pipeline, full routes/search, compatibility pages, then release-integrated validation. No deployment is part of this change.
