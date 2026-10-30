# dw1horizon.com

The project's site: a static page with no backend. The patcher runs in the visitor's browser.

- `index.html`, `style.css`, `js/app.js`: the page. `js/disc.js` reads a dropped image's SYSTEM.CNF to tell which game
  it is (2352, 2448, 2336 or 2048-byte sectors) and reads single files through the path table. `js/hash-worker.js`
  streams CRC-32 + SHA-1 in a Worker and compares them with redump.
- Adding discs (`js/app.js`, 2026-10-27): four slots, one per game (made from `data/discs.json` `discs`), each with
  its cover in grey until its disc is added, so what is still missing is seen at a glance and nothing moves when a
  disc arrives. Under the cover: the game and what it is for, in a few words ("Base game"; "Adds 78 Digimon":
  `species` in `discs.json`, counted by `tools/discs.py` from `content/modeldelta`), nothing more, so the cards keep
  one height in every state. The cards only show status; while checking, the colour cover is revealed from
  the left over the grey one (`--p`) with the percentage in a pill on its corner; ready: the cover in colour with a
  green check there, and ×. The release (its title), serials and checksums are only under a collapsed Details;
  `release.<id>`, the release in plain words, is only used by the dialog. Below the slots the drop zone, one button
  (`#add-button`: a click, Enter, or files dropped on it; they can also be dropped anywhere on the page) with our own
  icon (inline SVG in `index.html`: an arrow down into an open tray, `currentColor`; on drag-over the arrow dips into the
  tray, not under reduced motion) and the formats line ("Any language · .bin/.cue, …"), many files at once: each
  file's game and release come from its bytes (the boot file, then the checksum:
  `discs`, `variants`, `other`) and it goes to its game's slot, wherever it was dropped. The last usable
  disc of a game wins, silently (Details shows the one in use); several of one game in one drop are checked one
  after another.
  Desktop: the four in a row; under 860 px two by two; a phone: four rows with the cover on the left. The slots are
  made once and updated in place (a rebuild each progress tick would restart the cover's transition and lose the
  focus). Files that cannot be used are explained together in one dialog per drop (`why.*`,
  with what works for that game, `works.<game>`): an unsupported release (the first Japanese pressing, PlayStation the
  Best, a fan translation), a modified or bad dump (the game it looks like), another PlayStation game, not a disc
  image, a .cue without its .bin, one audio track of a multi-track disc, CHD (chdman), an archive with nothing usable,
  a disc given while another of its game from an earlier drop is still being checked. The same disc twice is ignored.
  "Build my disc" waits for the four games; the line under it names the missing ones.
- Formats, all in the browser:
  - archives (zip, 7z, rar 4/5, tar, gz, bz2, xz, split .partN.rar / .001 / .zNN sets): `js/archive-worker.js`, 7-Zip
    24.09 as WebAssembly (`7z-wasm@1.2.0` from jsDelivr, 1.65 MB wasm + 83 kB js, loaded only when an archive is
    given). The archive is read in place (WORKERFS) and each image streamed out into Blob parts.
  - ECM: `js/ecm.js` (our own, written from the format's description and ECMA-130: EDC/ECC rebuilt, the ECM checksum
    checked; `test/ecm.mjs` in Node, `test/ecm-browser.mjs` through the convert worker in Chromium).
  - PBP (one-disc popstation PBP, not PlayStation Store ones): `js/pbp.js`, raw deflate through `DecompressionStream`.
    Both run in `js/convert-worker.js`; their output is the original .bin, so redump's checksum applies.
  - CHD: not decoded (no maintained libchdr build for the browser; CD CHDs need LZMA, zlib and FLAC); the page says
    how to convert it with `chdman extractcd`.
  - An image whose whole checksum cannot match redump (a 2048-byte .iso, another rip): Digimon World is refused (its
    movies and XA audio are Mode 2 Form 2 sectors such an image drops); the three source discs are checked by the
    files the import reads, listed per release in `data/discs.json` `files` (`tools/discs.py release_files()`, from
    `content/imports/releases/`; a `<game>-<release>.json` with a `files` map is picked up as it is).
- `data/discs.json`: the expected discs, their other releases and the files to check cooked images by. Generated, do not edit: `python3 tools/discs.py web-json web/data/discs.json`
  (`DISCS` + `SOURCE_DISCS` in `tools/discs.py`).
- `i18n/<lang>.json`: every string of the page in its eight languages (en, es, pt-br, fr, de, it, ja, ca: the game's
  own, `js/i18n.js` LANGS), every file with en.json's keys (`node web/test/i18n.mjs` checks keys and placeholders; a
  missing string falls back to English). The first visit follows the browser's languages, the choice in the bar's
  menu (each language by its own name, `NAMES`) is remembered. Japanese uses the system's Japanese font (`--font`).
- The languages line under the hero's lead names the languages the released disc plays in: `languages` in
  `data/discs.json` (`tools/discs.py` from the selected release's everything recipe during deployment;
  `web-json --recipe FILE`, default: this checkout's recipe), also the "language" card's `{n}` and
  `{languages}`; it follows the recipe, never the page's own list.
- `content/features.json`: the "What's new" entries, text in both languages and their media: loops, stills and side by sides in
  `media/clips/` (optional local recordings, excluded from public Pages artifacts;
  `js/features.js` renders text-only cards when media is absent).
- Optional `media/covers/<disc id>.jpg`: historical deployment used libretro-thumbnails box art.
  It is not tracked or approved for publication; the public site uses its disc placeholder.
- Optional `media/psx.webp`: historical console photo attribution names Evan-Amos,
  Wikimedia Commons, PSX-Console-wController.png. The file is absent from the public tree.
  See the [publication media inventory](../docs/release/media.md) before supplying media.
- The Discord and GitHub links: `LINKS` at the top of `js/app.js`.
- "Build my disc" builds the everything disc from the player's four discs, all required: Digimon World (any of the
  release's seven bases: USA, Europe, France, Germany, Spain, Italy, Japan Rev 1; the redump dump) and the three games
  the imported species come from (Digimon Digital Card Battle, Digimon World 2, Digimon World 3 / 2003: any release
  `data/discs.json` lists and `tools/derive/importers/discs.py` reads). Their checked files are imported locally, then
  our per-model deltas make the imported models; the release carries no raw imported models.

## The engine

`js/engine/engine.js` (the page's side) and `js/engine/worker.js` (a module Web Worker, one Pyodide each) run a
make-release of the everything variant (format 3, the derive builder: `tools/patcher/dwpatch.py`, docs/patcher.md
§9) as `dwpatch apply` would, with tools/derive's steps spread over the workers:

1. The engine's files (`engine/<version>/`, made by `web/build-engine.sh`) go into the Cache API the first time (the
   service worker `engine-sw.js` serves `engine/<version>/` from there, Pyodide included): a second build downloads
   nothing.
2. A worker mounts the player's image (WORKERFS: read in place, not copied), checks it (`identify_base`) and writes the
   files the build reads (the release's `extract` list, by USA path; jp1's localized images made by the bundle's
   tool, run in-process) to OPFS (`horizon-build/tree/extracted/`). It also reads the three source images, verifies
   their release file checksums, reads the hidden ISO directories and DCB's DRV, and writes their inputs into
   `build/everything/source-games/` (`tools/derive/importers/discs.py`; a file that differs names its game:
   `engine.sourceDiffers`). It is then closed (jp1's tool needs ~0.3 GB).
3. The workers (below) take the jobs of `plan.json`: each of derive's steps as `derive unit --prepare`, the units side
   by side, `--finish` (one finish at a time: they share the manifest), or `--build` then `--finish`, the critical path
   first (maps, models, overlays). Before a job, its worker copies in the files the job reads: from the packs (the
   bundle) or from OPFS (the player's files, earlier jobs' outputs), makes the folders it lists as they were, and
   removes what must not be there; after it, what the job wrote or removed in the worker's memory file system
   (watched: open for writing, rename, unlink) is copied to OPFS, under `tree/@j<id>/<path>`: every version of a path
   stays where its job put it, so a job reads exactly the version the page's registry (path -> job) gives it even
   while another job writes that path (the story passes edit the new screens' .MAP in place); a version is removed
   once a newer one replaced it and no running job reads it. A path several units of one step write ends as the
   last of them in the recorded order wrote it (natively, the story passes do not all write the same bytes there),
   whichever finished last here.
4. A fresh worker checks every built file against the release's SHA-1 for that base (a different one stops it and
   names the files) and writes the image (`build_disc3`, `isowriter.write` streaming to an OPFS sync access handle,
   8 MB at a time; the built files are read from OPFS as they are written); the image's SHA-1 is compared with the
   release's.
5. The page offers the .bin (the OPFS file itself) and a .cue: "Digimon World Horizon.bin/.cue". The tree is removed;
   the image stays in OPFS (with `done.json`: its size and SHA-1) until the next build.

Storage does not grow: a build first removes the last build's image and tree and the engine versions in the Cache API
that are not the current one; a stopped or failed build removes its tree; when the page loads (`tidyStorage`) the old
engine versions go and, in OPFS, everything but a finished image (image.bin whose size is the one in done.json): the
tree of a crashed build, a half-written image. One build at a time across tabs (Web Locks, `horizon-build`; the
page-load tidy skips while another tab builds). Nothing of this is shown to the player.

### Workers

`workerCount()` in `js/engine/engine.js`: `min(cores - 1, 6)`; with `navigator.deviceMemory` (Chromium only: GB,
rounded down, at most 8) one worker per 0.5 GB above 2 GB (2 with 4 GB or less); without it (Firefox, Safari) at most
4; phones and tablets 2. Past 6 workers the build gains little for a lot of memory (the curve below); 4 workers fit
any computer a build makes sense on (8 GB), which is why an unknown memory gets 4 rather than the cores. If a worker
still runs out of memory (Python's MemoryError, a WebAssembly memory that cannot grow, a worker that dies), its job is
given again to the others and the build goes on with one worker fewer (with none left, one fresh worker; a job that
fails so three times stops the build). Every worker shares the tab's process, so a real out-of-memory of the whole tab
cannot be caught: the conservative counts are what keeps it away; the retry covers a heap that cannot grow. `?test=1&
oom=JOB` makes that job's first run fail as out of memory (the retry path, tested).

### Memory

A worker's WebAssembly heap never shrinks (36 MB empty; up to ~190 MB after the species and signs jobs), and its
memory file system holds the job's files outside the heap. So: after a job a worker whose heap passed 110 MB is
replaced by a fresh one (~3 s, Pyodide from the cache); a worker keeps at most 24 MB of bundle and tree files between
jobs (48 MB before the import speed work, originally 192 MB; a job's outputs are copied to OPFS anyway); the disc is written by a fresh worker after the
others are closed. Use `web/test/run.mjs` to measure the current package, browser version, worker count,
wall time and peak memory on the target machine. Historical benchmarks do not pin
current performance.

### Import computation

The imports are 175 independent units, ready alongside maps after extraction. The recorded inputs already limit
source-game reads to the files each species uses; copying entire source discs per job was not the slowdown.

The converters defer source animation frames until a recipe reads them. Scaling, bone reordering and reparenting
retain their original order for deferred frames; edits to existing frames still happen immediately (including
shared DW2 concatenation frames). World 3 mesh-angle candidates share one source decode and animation set, with a
fresh mesh for each angle. Frozen meshfix specs supply their recorded search winner; replay checks the source
SHA-256 and falls back to the complete search for an older choice that no longer reproduces the pin. Replay
initializes only original donor skeletons and registers its target, restoring the
caller's table afterwards. A texture already generated in that replay can satisfy another source only after its
size and SHA-256 match.

Retargeting calculates rotations and positions together, preserves the original summation order, and reuses at most
128 identical solver states per slot (source pose, layered matrices and previous Euler solution; root travel stays
separate). The DCB reader caches at most 2,048 immutable rotation matrices and hands callers fresh arrays. Both
caches preserve signed zero. Long animation repeat searches compare interned integer timelines with the standard
library, retaining their original tie order. The disc converters and field overlays use the standard-library
numeric helpers in `tools/derive/arraymath.py`; packed textures use byte operations and placement uses integer
bitsets rather than FFTs. No NumPy wheel is downloaded or loaded by a worker.

`python3 tools/test_import_frames.py` checks deferred edit order, independent affine calculations, cached versus
uncached retargeting, and bit-exact DCB rotations. The browser suite additionally checks all source/delta/target pins
and the release's complete image SHA-1. Its logs distinguish input sync, Python execution and output publication;
the runner records browser CPU time and machine load alongside wall time and peak RSS. The engine retains 1,024 log
lines, enough for every job and worker restart in the current graph.

`web/build-engine.sh RELEASE OUT` builds a verified release into an explicit local
engine directory. Defaults are local `build/web-release` and `build/web-engine`;
use explicit paths in separate worktrees. `RECORDS=build/web-records` reuses job records:
`web/enginebuild/build_engine.py` makes a tree of the release's bundle with each recorded disc's files, runs
`web/enginebuild/record.py` there (the jobs one after another in one process, as a worker would, recording what each
opens, lists and stats, and what it changes), and turns that into each job's inputs and the jobs it waits for (who
wrote what it reads, and the other way round). The USA and the Japanese (Rev 1) discs are recorded and their inputs
merged. It writes `plan.json`, the packs (every bundle file a job reads, each deflated on its own: random access by
range; `code.pack` holds every Python file, tools/, the release's patcher files and `enginebuild/glue.py`, the Python
side of the worker) and Pyodide 314.0.7 with no third-party packages, vendored (no third-party host at build time; the `.mjs`
files renamed `.js`, as nginx serves `.mjs` without a JavaScript type). NumPy and Pillow are not used.

The page's progress: one bar for the whole build (getting the builder, reading the discs, building, checking, writing)
and a plain line of what is being done now in the player's words (`now.*` in `i18n/`; while building, the steps most
workers are on), above the per-step and per-worker detail. The bar is the time spent over the time spent and left:
left is what is left of this phase plus the estimates of the next ones (the download from the measured rate; the jobs
from plan.json's estimates, critical path or work over the workers, scaled by how the jobs done so far compared; the
check and the writer from `write_est`), and it never goes back.

Tests: `web/test/suite.sh TAG [URL]` (not deployed): headless Chromium on the real page (`?test=1` sets the title DONE
and `window.RESULTS` at the end; `&shuffle=SEED` runs the jobs in a random order;
`&workers=N`; `&keep=1` keeps the OPFS tree for `web/test/treesums.mjs`) on the seven bases and a random order
(`BASES=` picks); `web/test/run.mjs` gives the four discs together through "Add discs" (`OTHERS="dcb=PATH;dw2=PATH;
dw2003=PATH"`, default the USA Card Battle and World 2 and the European World 2003 of the configured source-disc directory);
`FIREFOX=path node web/test/run.mjs` runs one in Firefox. `web/test/ui.mjs URL [SHOTS]` (the suite's `ui`, no build):
the four slots empty (slots are passive; the drop zone by click and by Enter opens the file chooser), the counts of Digimon per source disc, a
slot showing the check's progress while two are ready, a disc replaced by another of its game (the slot unchanged,
Details showing the new one), one drop of files that cannot be used (one dialog, each listed; the same disc twice
ignored), the four slots ready,
× by keyboard (the focus going to the drop zone), a disc given while another is still being checked; with SHOTS the
screenshots of those states in English and Spanish, desktop and phone width. `web/test/shots.mjs` takes the build's.
`web/test/langs.mjs URL [SHOTS]`: the first visit's language from the browser's, the menu, each of the eight switching
the whole page (no key left untranslated, the cards, the languages line), the choice kept after a reload; with SHOTS the
hero and slots in ja, de and pt-br, desktop and phone.

For a delta-model release, `web/build-engine.sh` takes the three source images from `DCB_IMAGE`, `DW2_IMAGE`,
`DW3_IMAGE` (defaults: the same three in the configured source-disc directory, `SOURCE_ISOS`). They are used for recording the jobs, never
packaged. `build_engine.py` also accepts repeated `--source-disc GAME=IMAGE` arguments and rejects a delta-model
release whose bundle contains `imported-models/files`.

`node web/test/imports.mjs EXTRACTED_GAMES [ID ...]` tests the model provider in actual Pyodide without NumPy or Pillow, including
the source/delta/target SHA-256 checks. Without IDs it tests all 175. It forbids reads of the committed imported oracle
and imports of NumPy, Pillow or Unicorn. Make EXTRACTED_GAMES with `python3 -m tools.derive sources --out DIR` and the three
`--source-disc` arguments. Native import and recipe details: `content/modeldelta/README.md`.

Public deployment follows [the Pages release guide](../docs/release/releasing.md),
which validates a matching package and engine before publishing. The optional
`web/deploy.sh` script targets a separately configured rsync/nginx host; it is a
local hosting utility, not required for Pages. Local preview:
`python3 -m http.server -d web`.
