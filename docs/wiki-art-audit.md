# Wiki artwork audit

The wiki ships without Digimon pictures: no native icons, imported hand-drawn icons, silhouettes, sprites, model renders or gameplay/map pictures. The production artwork generator has been deleted, and the release snapshot reader no longer requests `content/icons`. The wiki output directory is replaced on every build, which removes the previous generated SVG directory as well.

## Wiki boundary

- Cards, species headings, evolution nodes and species search matches use names, labelled level/attribute badges and specialties as text. Every badge has at least 4.5:1 text contrast; colours are consistent across layouts and languages and are never the only label.
- The only inline SVG in wiki HTML is the evolution connector diagram. It draws geometric lines and arrowheads, with no character art. Shared CSS provides the generic select chevron. The project’s sunset favicon is an abstract site mark, not game imagery. Fonts are the locally hosted licensed website font and system fallbacks.
- Wiki HTML, JSON, CSS and scripts load no showcase clip, map image, box art, console photo, model render or extracted game-art resource. Static checks reject media files and picture/media elements in the default wiki output, and browser checks assert the image-free presentation across every page type and locale.
- `web/wiki/owned-icons.json` is the single future opt-in data hook. It is empty. A future reviewed entry maps a species ID to a local filename under `web/wiki/owned-icons/`; the builder copies only referenced assets and adds lazy-loaded pictures through one rendering helper. Unknown species, remote URLs and path traversal are rejected. No assets are supplied now. Record ownership/source review here before populating the map, and update the image-free checks intentionally.

## Main-page media, separately retained

These existing main-page media resources remain outside the wiki and are unchanged. This inventory describes the publication boundary and actual files; it does not establish redistribution rights or expand approval to use them in the wiki.

The v0.0.7 preview extracts 30 files from `horizon-media.tar.gz` into `media/clips/` (7 MP4s and 23 JPEGs), and 106 files from `horizon-maps.tar.gz` into `media/maps/` (53 numbered JPEG/PNG pairs, `map-01` through `map-53`). The map gallery uses the existing `web/content/maps.json` sizes and `web/js/maps.js` loader. Every extracted byte was compared with its release-archive member during this audit. The main page’s source, feature definitions, map definitions and loader, and both workflow archive-extraction steps are unchanged by the image removal.

| Main-page feature | Media paths from its existing definition | Status |
| --- | --- | --- |
| story | `media/clips/story.jpg`, `media/clips/story.mp4` | Existing main-page feature |
| maps-tour | `media/clips/maps-tour.jpg`, `media/clips/maps-tour.mp4` | Existing main-page feature |
| digimon | `media/clips/digimon-tour.jpg`, `media/clips/digimon-tour.mp4` | Retired section; archive assets retained |
| fps | `media/clips/fps.jpg`, `media/clips/fps.mp4` | Existing main-page feature |
| guide | `media/clips/guide.jpg` | Retired section; archive assets retained |
| battle | `media/clips/battle.jpg`, `media/clips/battle.mp4` | Existing main-page feature |
| language | `media/clips/language-en.jpg`, `media/clips/language-es.jpg` | Existing main-page feature |
| waiting | `media/clips/waiting.jpg`, `media/clips/waiting.mp4` | Existing main-page feature |
| care | `media/clips/care.jpg` | Existing main-page feature |
| options | `media/clips/options-en.jpg`, `media/clips/options-es.jpg` | Existing main-page feature |
| bars | `media/clips/bars-en.jpg`, `media/clips/bars-es.jpg` | Existing main-page feature |
| carem | `media/clips/carem-en.jpg`, `media/clips/carem-es.jpg` | Existing main-page feature |
| cheats | `media/clips/cheats-en.jpg`, `media/clips/cheats-es.jpg` | Existing main-page feature |
| naming | `media/clips/naming-en.jpg`, `media/clips/naming-es.jpg` | Existing main-page feature |
| amount | `media/clips/amount-en.jpg`, `media/clips/amount-es.jpg` | Existing main-page feature |

The clip archive also retains `digimon.jpg` and `digimon.mp4`, which have no active feature reference. Retired Digimon/evolution feature assets stay in the existing archive; this change neither republishes them inside the wiki nor changes the earlier main-page section removal.

The tracked main-page media also includes `web/media/psx.webp` (console photo) and `web/media/disc.svg` (generic disc placeholder). The main page’s existing box-art loading remains in `web/js/app.js`; the wiki does not invoke it. None of those files or behaviors was modified. Engine/package artifacts remain the patcher’s release inputs, not wiki artwork.

| Release archive | SHA-256 of audited input |
| --- | --- |
| `horizon-media.tar.gz` | `2b55a8e399cb2679cc6efb312f4979fb5d1608156fde9efd9d6a2c3d41813e0a` |
| `horizon-maps.tar.gz` | `345e2e4536a32e7bcceeb75a314d66860a1240428afa3603bbb265daa8e24f7a` |
