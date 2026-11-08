# Wiki proposal mockups

Local proposal only: four English preview pages. No production files are modified.

From the repository root:

```sh
python3 design/wiki-mockups/build.py --ref v0.0.7
python3 -m http.server 18743 --bind 127.0.0.1 --directory build/wiki-mockups
```

Open `http://127.0.0.1:18743/`. Pages: `index.html`, `digimon.html`, `article.html`, `search.html?q=Horizon`.
Stop the preview with Ctrl-C when finished.

The build uses `tools/guide/build.py` and `recruits.py` to read the selected Git snapshot and validate recruit assertions. It copies the unchanged main-site stylesheet and the existing licensed local font into ignored build output. `snapshot.json` records the tag/commit and the exact facts displayed. No disc extraction, game build, network service or new artwork is needed.

Search forms, type filters, requirements disclosures and recruitment spoiler controls work locally. The search index covers only the preview records, explicitly labeled on the screen. Home links to unwritten articles use the closest preview; the production URL scheme and nine-language workflow are proposed in `WIKI-PROPOSAL.md`. The header's English label is static. The Android article is a draft with device verification pending.

Capture and check the four pages at 390 px and 1440 px widths:

```sh
npm install --prefix build/wiki-browser puppeteer-core@25.16.0 --no-audit --no-fund
CHROMIUM=/path/to/chromium node design/wiki-mockups/capture.mjs
```

The helper starts its own loopback server (port 18744, override with `WIKI_PREVIEW_PORT`), checks fonts, horizontal overflow, JavaScript errors, external requests, local links/anchors, disclosures, search filtering and empty search, and writes eight full-page PNGs plus `validation.json` under `build/wiki-review/`. It closes its browser and server in `finally`. `CHROMIUM` should point to an installed Chromium executable; it defaults to the system wrapper. There are no OS-specific browser paths in the mockup sources.

The filenames are numbered by screen, with `phone` and `desktop` suffixes. Only source files and the proposal are committed; generated HTML, snapshot JSON, dependencies and PNGs remain in ignored `build/`.
