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
- `i18n/<lang>.json`: every string of the page in its nine languages (en, es, pt-br, fr, de, it, ja, ca, zh-hans: the game's
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
- `js/changelog.js` renders `content/changelog.json`: translated release history, limited to the served engine's release tag; the English entry also supplies release notes.
- `wiki/`: the unified multilingual wiki, generated with tagged game data by `tools/wiki/`. The main header and wiki card open it; the former modal is replaced. See [wiki maintenance](../docs/wiki.md).
- Box art is not stored here: the browser fetches it from libretro-thumbnails (`BOXART` in `js/app.js`), with `media/disc.svg` as the fallback.
- `media/psx.webp`: the console photo, Evan-Amos, public domain (Wikimedia Commons, PSX-Console-wController.png).
  See the [publication media inventory](../docs/release/media.md) before supplying media.
- The Discord and GitHub links: `LINKS` at the top of `js/app.js`.
- "Build my disc" builds the everything disc from the player's four discs, all required: Digimon World (any of the
  release's seven bases: USA, Europe, France, Germany, Spain, Italy, Japan Rev 1; the redump dump) and the three games
  the imported species come from (Digimon Digital Card Battle, Digimon World 2, Digimon World 3 / 2003: any release
  `data/discs.json` lists and `tools/derive/importers/discs.py` reads). Their checked files are imported locally, then
  our per-model deltas make the imported models; the release carries no raw imported models. With World 3 (USA) seven
  species are made from its own models (docs/patcher.md): the built files and the image are checked against the
  manifest's `"<base>+dw3-us"` checksums (`glue.pin`, picked from the World 3 disc's boot file).

## The desktop app downloads

"Prefer an app?" (`js/desktop.js`, `#desktop` at the end of the patcher section) offers Horizon Patcher, the desktop
patcher (docs/patcher.md "The desktop app"), for Windows and macOS. It links to the served release's own assets,
`https://github.com/<repo>/releases/download/<release_tag>/Horizon-Patcher-<Windows|macOS>.zip` (the repository from
the `source-repository` meta), with the release and the size on each button, the first start's SmartScreen and
Gatekeeper steps per system (collapsed), and "Why it is safe" (built by GitHub Actions from the tag: the build's run,
the code signing policy, both SHA-256).

It shows only when `engine/current.json` has `desktop`, so it never links to a missing file: `desktop.yml` attaches
the two zips to the tag's release, then `horizon-desktop.json` (name, size and SHA-256 of each, whether the Windows
app is signed and the macOS app notarized, the run's URL), then starts `release.yml` again for that tag when it is the
latest release or still a draft. `release.yml` downloads the three when they are there and `tools/release_pages.py`
(`desktop_apps`) writes `desktop` only when both zips match the description and the package's dwpatch has
`GUI_API = 1` (the app refuses older packages); otherwise the page goes out without it (v0.0.4 and earlier, or the
first deployment of a release, before the apps are built). The zips are not copied to the site.

The visitor's system (user agent) comes first and highlighted; Linux gets both outlined and a line pointing to the
browser builder and `dwpatch.py`; phones and tablets get one line that the apps are for computers. Once the macOS app
is notarized (`notarized: true`) its Gatekeeper steps become one line; the "not signed yet" note stays while either
app is unsigned. `node web/test/desktop.mjs URL [SHOTS]` checks it with fixtures for `current.json` (no discs).

## Remembered discs

A returning player builds a new release without giving the four discs again (`js/remember.js`, `js/app.js`
"remembered discs", `js/keep-worker.js`). Each accepted disc is remembered in one of two ways:

- A handle, no copy: where the browser gives file handles (Chromium on a computer). `#add-button` opens
  `showOpenFilePicker({multiple: true})` (the hidden `<input>` elsewhere), and a drop asks every item for
  `getAsFileSystemHandle()` in the drop event itself. The handle is kept as soon as the disc is accepted.
- A copy in this browser, only when the player ticks "Keep these discs in this browser for next time (about X GB)",
  shown with the real size under the drop zone whenever an accepted disc has no handle to its image: Firefox, Safari,
  anything without handles, and a disc that came out of an archive, ECM or PBP (the converted image is kept; its
  handle would mean unpacking it again). Ticking it asks for persistent storage (`navigator.storage.persist()`), checks
  that the copies and a build after them fit (`storage.estimate()` against the copies plus `buildRoom()`), then copies
  one disc after another in a worker (8 MB slices through a sync access handle: never a whole image in memory, the
  page stays responsive, and it works wherever the build's own OPFS writes do). The choice is remembered (`horizon.keepDiscs` in localStorage) and
  applies to discs added later. Not offered on phones and tablets (`isMobile()`, the engine's low-memory test).

Storage, apart from the build's: IndexedDB `horizon`, store `discs`, one record per game: `{game, kind ('handle' or
'copy'), release, via, name, size, lastModified, image: {crc32, sha1, size}, converted, handle, savedAt}`; the copies in
OPFS `horizon-discs/<game>/<the file's name>` (the build's `horizon-build` is emptied by every build and by
`tidyStorage`, never this folder; `web/test/lifecycle.mjs` checks). Copies and deletions in `horizon-discs` hold the
build's Web Lock (`withLock`): a copy never races a build in this or another tab (it waits, and says so, while another
tab builds; "Build my disc" stops a copy in this tab and it starts again after the build). What no record names (a
copy cut short by a closed tab, a deletion that had to wait) goes at the next tidy: page load, after a build. The
engine's free-space check needs no change: the copies are already in `usage` and the build reads them in place.

Next visit: a copy whose size is the record's goes straight into its slot; a handle the browser still allows
(`queryPermission`: granted) too; one that needs permission again shows its slot as remembered (the cover dimmed,
↺) and one button, "Use my discs from last time", asks for each (`requestPermission`, one after another in that
click; a browser that counts one prompt per click leaves the rest waiting and the button stays). A disc reused this
way is not hashed again when its file is the one checked (name, size and date: `sameFile`) and `data/discs.json` still
accepts its release with that checksum; one checked by files (`via: 'files'`) has those files read again (a later
release may check more). The build still checks its source files and the image it writes. A handle whose file
changed, or an archive, is checked again as if just added. Otherwise that slot is empty again with one line why, the
others stay: the file gone (`NotFoundError`), permission refused, the copy cleared or cut short, the release no longer
accepted, unreadable; its record and copy are forgotten. A new disc for a game replaces what was remembered for it;
the slot's × forgets it; "Forget them" forgets all (records, copies, the option). Without IndexedDB or OPFS (private
windows, storage blocked), with storage full or evicted, everything falls back silently to giving the discs each time.

`node web/test/remember.mjs URL [SHOTS]` tests it in Chromium with fake handles (the native picker cannot be driven,
and a synthetic drop gives none): `test.handles` in localStorage switches them on before the page's scripts, the
fakes give `stored()` for IndexedDB and `self.testHandles.revive` makes them again (the only test hook in
`js/remember.js`). Copies use the real OPFS. The scenarios are listed at the top of the file.

## The engine

Building requires OPFS with `FileSystemFileHandle.createWritable`, synchronous
file access in workers, and raw deflate streams. The page checks storage support
before disc selection. On iPhone and iPad, iOS/iPadOS 26 or later is required,
including when using Chrome. Capability detection also accepts Safari 26 when its
user agent still reports an older OS version.

Python converts extracted files and bounded image chunks to owned JavaScript byte
arrays before calling storage callbacks. These callbacks never receive Python
proxies or views into WebAssembly memory. Temporary proxies used to populate
Python globals are destroyed immediately after assigning the Python reference.

`js/engine/engine.js` (the page's side) and `js/engine/worker.js` (a module Web Worker, one Pyodide each) run a
make-release of the everything variant (format 3, the derive builder: `tools/patcher/dwpatch.py`, docs/patcher.md
§9) as `dwpatch apply` would, with tools/derive's steps spread over the workers:

Before downloads or jobs, all selected discs are copied in 8 MB chunks to `horizon-build/inputs/`. The copies
remain immutable through disc writing; each worker obtains a fresh File from its OPFS handle when mounting it.
They are removed on success, cancellation or failure, and by page-load cleanup after a crash.

1. The engine's files (`engine/<version>/`, made by `web/build-engine.sh`) go into the Cache API the first time (the
   service worker `engine-sw.js` serves `engine/<version>/` from there, Pyodide included): a second build downloads
   nothing.
2. A worker mounts the input copy (WORKERFS: read in place), checks it (`identify_base`) and writes the
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

Room: a build needs about 3 GB plus the combined size of the selected discs in this browser's storage (`roomFor`: twice the holes, the largest image, 1.25 GB;
measured at its fullest: 2.63 GB, `web/test/run.mjs` prints it as "peak storage").
`navigator.storage.estimate()` is advisory, not a measurement of free disk space or a guarantee that the
build fits. `checkRoom` validates finite, nonnegative quota and usage values; zero or insufficient remaining quota
warns, and missing, malformed or rejected estimates show an unknown-space warning. Both let the player try anyway.
The build click starts `persist()` in the user gesture and awaits its result before the engine rechecks quota;
denied or unavailable persistence still allows a build. Persistence protects against eviction and does not guarantee
more room. A 1 MiB OPFS write/flush/length probe checks access, then deletes its file. It does not reserve several GB
in one file: sparse allocation and single-file limits cannot predict a multi-file build. Only a real probe quota or
permission failure blocks startup; real writes that run out of storage stop with `engine.quota` without job retries.
The existing iOS capability gate remains based on the required file APIs.

Browser policies explain why disk space and the estimate differ:

- Firefox applies a best-effort group limit; persistent storage uses a different limit and may prompt for permission.
  Private windows can have different quotas or unavailable storage. Treat both the estimate and private-mode support
  as version-dependent. See [Mozilla’s storage policy](https://developer.mozilla.org/en-US/docs/Web/API/Storage_API/Storage_quotas_and_eviction_criteria).
- Chromium can expose a fixed estimate while enforcing a smaller actual quota. Its incognito storage pool is based on
  RAM, and normal profiles reserve disk headroom under storage pressure. See the
  [Chromium quota implementation](https://chromium.googlesource.com/chromium/src/+/refs/heads/main/storage/browser/quota/quota_settings.cc)
  and [static estimate change](https://groups.google.com/a/chromium.org/g/blink-dev/c/00aHBCiUGzo/m/B0Dq06SFAQAJ).
- Edge also supports [static quota estimates](https://learn.microsoft.com/en-us/deployedge/microsoft-edge-browser-policies/staticstoragequotaenabled).
  Brave is Chromium-based, but its effective quota and persistence grants must be checked at runtime as well;
  neither browser name nor a quota value reliably identifies private browsing.
- Safari/WebKit has per-origin and overall quotas, different limits for browser apps and embedded apps, and
  eviction under storage pressure. See [WebKit’s storage policy](https://webkit.org/blog/14403/updates-to-storage-policy/).

The warning and storage errors explain freeing disk space, using a normal window, allowing persistent storage when
prompted, and trying a current 64-bit Chrome, Edge or Firefox (or the desktop patcher). This advice is translated
in every page language. `node web/test/storage.mjs URL [SHOTS_DIR]` uses Playwright in Chromium, Firefox and WebKit
with regular temporary profiles and simulated low/zero/unknown/malformed quotas, persistence granted/denied/rejected/unavailable, actual tiny input
copies, and injected probe/write failures. It checks warnings, click-to-engine ordering, continuation past the gate,
real quota error handling and probe cleanup. Firefox exception names and messages are preserved alongside stacks,
which can contain only call sites. The expensive builder is replaced after input copying; this is not a
full-disc checksum test. `web/test/errors.mjs` retains the real-engine quota scenario (`?quota=first|JOB`) and
`?room=` overrides the probe size for allocation-failure tests.

Errors: `Build.explain` turns any failure into the player's words by its text: a full storage
(QuotaExceededError and the like) is `engine.quota`, storage not allowed `engine.storageBlocked`, a lost connection
`engine.network`, memory `engine.outOfMemory`; the original text stays under Details. A job whose output cannot be
written stops the build at once (another worker would fail the same way). Under the message the page lists what to
do for that kind (`fix.*`: leave the private window, free N GB, the desktop apps when the release ships them, the
64-bit Firefox on Windows...). The error's Details and the build's log open by themselves, so a screenshot carries
them, and the error's Details include the browser line. `web/test/errors.mjs URL DISC [SHOTS]` tests the warnings
and both stops (`?room=` makes the room check ask for that many bytes, `?quota=first|JOB` makes a job's output
fail as a full storage).

### Workers

`workerCount()` in `js/engine/engine.js`: `min(cores - 1, 6)`; with `navigator.deviceMemory` (Chromium only: GB,
rounded down, at most 8) one worker per 0.5 GB above 2 GB (2 with 4 GB or less); without it (Firefox, Safari) at most
4; phones and tablets 2, or 1 under 8 GB. Past 6 workers the build gains little for a lot of memory (the curve below); 4 workers fit
any computer a build makes sense on (8 GB), which is why an unknown memory gets 4 rather than the cores. The page
compiles Pyodide's WebAssembly module once and gives it to every worker (Firefox's 32-bit Windows build runs out of
memory at the third worker when each compiles its own, and at the fourth sharing it). The disc reader starts alone, and
the build workers after it, one after another; a worker that does not start, or does not answer in 120 s, is left out
and the build goes on with the ones that did (with none, it is tried again after 2 s). If a job fails on a worker (Python's
MemoryError, a WebAssembly memory that cannot grow, a worker that dies, a browser file read that gives up, anything
else), it is given again to the others and the build goes on with one worker fewer (with none left, one fresh worker;
a job that fails three times stops the build). When a build stops, the error's text is shown open with a button that
copies it and the log: that is what a report needs. Every worker shares the tab's process, so a real out-of-memory of the whole tab
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

File access: tree reads obtain fresh directories, file handles and Files from OPFS. `InvalidStateError` or
`NotReadableError` retries the read once from the storage root, preserving the requested job version. A second
failure names the file in the diagnostic log and stops with `engine.fileLost`: reselect discs from local storage,
restart, keep the tab open and device awake, or use the desktop patcher. It does not retry whole jobs on other
workers. Input copying also retries once, reopening the selected handle when one is available; an invalid File
from a plain file picker needs reselection if it cannot be read again.

`node web/test/file-storage.mjs URL` checks stale reads, retry limits, immutable input copies and cancellation in
Chromium using tiny OPFS fixtures and the production worker's read function. `node web/test/lifecycle.mjs URL`
checks failure and cancellation cleanup, worker retries, and locking across tabs without building a disc.

With Playwright installed, `node web/test/capabilities.mjs URL` checks the storage
gate in WebKit, Chromium and Firefox without discs, including iOS Chrome and
Safari's frozen OS version. `node web/test/cross-browser.mjs URL ISO_ROOT BROWSER`
runs a full USA-disc build with one worker and four reported cores; `BROWSER` is
`webkit`, `chromium` or `firefox`. It hashes the stored image independently and
accepts `EXPECT_SHA1` for comparison with a CLI build. `PLAYWRIGHT_MODULE` can
select a local installation, and `CHROMIUM` can select a system executable.
Full builds use a regular temporary profile. `BROWSER_PROFILE` selects a named
profile to retain for inspection after the run.
Provision at least the page's reported storage requirement in the browser test
environment: MiniBrowser's default 1 GB quota is too small for a full build.

`node web/test/downloads.mjs URL` tests the completed build's separate download links and combined button without
source discs. It checks the saved `.bin` and `.cue` names, bytes, binary MIME types and the CUE's BIN reference in
headless Chromium, including Android user agent, viewport and touch emulation. Set `FIREFOX=path` to run in headless
Firefox, or `CHROMIUM=path` for a custom Chromium executable. Both outputs use `application/octet-stream` so download
managers do not infer a `.txt` suffix for the CUE. The two files stay together in the same folder; open the `.cue`.

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
`web/test/changelog-browser.mjs SITE [SHOTS]` checks release history on an isolated copy of a generated preview,
including language changes, release filtering and loading failures, without discs.
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

## Player data at /data/

The header and main-page wiki card link to `/wiki/<language>/`. The old Digimon/evolution sections and `/data/` routes redirect to the unified latest-release wiki. See [wiki authoring and checks](../docs/wiki.md).

For full-disc Chromium verification, `BUILD_WORKERS=4` selects four workers
in `web/test/cross-browser.mjs` (default one); `EXPECT_SHA1` enforces a CLI pin.

## Unified wiki

`python3 web/build.py --tag v0.0.7 --out build/pages-site` builds the website and wiki together. `/data/` and its localized pages/anchors now redirect to the wiki, while `data/discs.json` remains patcher metadata. The release workflow takes page code from the dispatching commit and all wiki game facts from the selected tag. Search runs against local JSON; fonts and Digimon images are hosted locally. See [wiki sources, routes, articles and checks](../docs/wiki.md).
