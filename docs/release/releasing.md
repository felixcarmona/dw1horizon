# Releasing

An annotated `vMAJOR.MINOR.PATCH` tag names a release. `tools/version.py` supplies
its version, UTC tag date and source commit. Push the tag to run
`.github/workflows/release.yml`: validate the prepared artifacts, assemble and test
the static site, deploy with `actions/deploy-pages`, then publish the draft GitHub
Release with the package attached. Manual dispatch accepts the same existing tag
and retries publication. CI installs Python 3.10 and no Python packages.

## What still requires local discs

This is a publication workflow, **not a disc-free reproduction of the game**.
The checkout can generate the page and its disc metadata without discs:

```sh
python3 tools/release_pages.py page --out build/page-preview
python3 -m http.server --directory build/page-preview
```

The preview has no playable engine. CI never deploys that preview.
`tools/release.py` cannot produce a playable package without all seven registered
DW1 bases, the three source games, extracted USA files, the pinned decomp and the
native toolchain. `make-release` computes patches, output pins and the bundle by
reading those inputs. `web/build-engine.sh` records USA and Japan Rev 1 builds
and source extraction; even cached records do not eliminate all disc reads.
Do not upload discs, extracted trees, native outputs or build caches to Actions.

Prepare locally on the **exact public repository commit and annotated tag**.
Artifacts from the private development repo have a different commit and will be
refused, even if their version text matches. The reviewed public source snapshot needs its own build. Use the local release pipeline and its heap/save/native/browser gates
as described in [the patcher guide](../patcher.md#release-pipeline), retaining the
verified `package/` and `engine/` outputs. The current full pipeline includes a configured local deployment step. For Pages
preparation, use the individual native/package/engine commands in that guide
instead; `--dry-run` previews the pipeline without running it.

The player patcher, source replay and browser engine require neither NumPy nor
Pillow. Python 3.10+ supplies the native replay dependencies.

The existing patch format also documents game-derived literal bytes in patches
and base mappings ([details](../patcher.md#what-the-release-still-carries-that-is-not-ours)).
This workflow does **not** remove or certify those bytes. The owner must resolve
that publication boundary before uploading playable artifacts. Filename and
checksum validation cannot establish copyright provenance. An authored-source
page can be tested now; a copyright-free playable release is not proven here.

## Before the cut

Use `--quiet-machine` for a timed cut: pause other builds, emulator suites,
model conversions and release jobs before starting. The flag records that step;
it does not stop unrelated processes. Start with a new output directory and keep
all gates enabled:

```sh
ISOS=/path/to/digimon-world SOURCE_ISOS=/path/to/source-discs \
  python3 tools/release.py --jobs 8 --base-jobs 4 --save-check-emu \
  --ending-card /path/to/private-before-final-fight.mcd --quiet-machine \
  --out build/releases/candidate
```

This runs the full local cut without tagging, publishing, pushing or deploying.
For an existing annotated release tag, give the tag as the positional argument.
The ending card must Continue immediately before the final fight on screen 225;
keep that fixture private. The ending gate plays the final battle and clear save,
checks that the ending's executable code matches the disc, then captures five
minutes of credits. It assists only battle HP. The journey and published-save
checks use independent emulator ports, starting at `--emu-port-base` (38410 by
default), and original 2 MB RAM. Inspect the resulting quiz and credits images.

Once the fresh native disc and heap checks pass, packaging overlaps the full
offline selftest and the emulator gates. Every job must pass before standalone
replay, engine construction or publication can proceed. Per-job logs and elapsed
times are retained under the cut directory. Packaging still runs its published-
save file check; `--save-check-emu` runs the emulator save check as a concurrent
required job. No gate is removed by this reordering.

`make-release --base-jobs` bounds the base reconstructions and the USA World 3
source derivation together. Results merge in the original base order. Each derive
gets a share of the available CPUs. The scheduler also reserves 8 GiB for the
controller and gates, allowing `--worker-memory-mib` (6144 by default) per worker
against Linux's available memory; on systems without that reading it uses one
worker. Worker process-tree peak RSS and phase times go to the private
`package-timing.json`, outside the player package. Binary deltas run in bounded
processes and merge in their original file/base order. Web-engine USA and Japan
recordings run in separate processes, at most two concurrently.

Release caches live in `build/release-derive-cache`, separate from developer and
player caches. Source recording keys hash every supplied input file, directory
inventory, recipe, source-disc contents, environment and interpreter/runtime
sources. Each snapshot file is SHA-256 checked before any restoration. Regional
steps use the existing audited derive cache in locked stable staging directories:
each cut starts from fresh inputs, checks recorded reads, absent probes and
directory listings, and verifies every restored artifact. Code and runtime inputs
are part of those keys. Changed dependencies rebuild their consumers; conservative
code fingerprints can rebuild more than the minimum. Binary deltas have separate
keys for source bytes, target bytes, algorithm and native producer. Cache entries
are private and must never enter publication archives.

The isolated bundle verification always runs from scratch with only the allowed
disc files. Output pins, standalone replays, browser verification and the literal
gate still run. `--no-derive-cache` disables recording, derive and delta caches;
`--base-jobs 1 --no-derive-cache` supplies the sequential reference. Compare the
DWP payload and every default/source-variant output pin against a parallel run
from the same commit, inputs and version. Whole manifests contain measured times
and therefore need not have identical bytes. A command `--dry-run` only prints a
plan; byte equality requires executing the actual cut without publication.

Play the disc once: `tools/dev/playtest/journey.py DISC.cue OUTDIR` from a new game to a reload. The checks that need no
emulator cannot see a story that is missing from a disc: a new game hung on main for a day with every gate green.

## Engine source

After the tag is public, publish the engine as readers see it, with the tag's name:

```sh
tools/engine_tree.sh build
DW1H_PUBLISH=1 tools/engine_tree.sh push vX.Y.Z FORK_URL
```

The branch is generated: each build dates every commit now and replaces the published branch. Add the release's row to
[compatibility.md](../mods/compatibility.md).

## Changelog

Before tagging, commit the release's entry in `web/content/changelog.json` as the
last change. An AI session reads what changed since the previous tag, writes
bullets for players and translates them into all eight page languages. Use
`tools/changelog_sources.sh PREVIOUS_TAG` to print PR titles and bodies, commits
without a PR and the diff stat; without an argument it uses the newest `v*` tag.
The helper reads Git and GitHub only, writes to stdout and needs no discs.

Use plain names, with no history labels, story spoilers, patch numbers, internal
names or names of people. Include one `upgrade` line in every language saying
whether saves from the previous version work and whether the required discs
changed. Empty New, Changed or Fixed groups are fine.

Both preparation and assembly require the tag's version in the changelog. The
English entry supplies the GitHub release notes. On a tag push or manual dispatch,
assembly reads `web/content/changelog.json` from the checked-out tag. The later
page copy reads that file from the workflow commit (main for a page-only dispatch,
the tag for a dispatch from that tag). The page hides entries newer than the
engine's `release_tag`; previews without that metadata show all entries.

## Stage the verified artifacts, then publish

After the local gates and publication review pass, start with a clean checkout
(including no untracked report), and an owner-created annotated tag on HEAD:

```sh
git tag -a v0.0.1 -m 'Digimon World Horizon 0.0.1'
python3 tools/release_pages.py prepare v0.0.1 \
  --package /absolute/path/to/package --engine /absolute/path/to/engine \
  --out build/pages-upload
```

Preparation reads only those artifact directories, never discs. It writes
`horizon-package.tar.gz` (unpacks directly to the player package files),
`horizon-engine.tar.gz` (current.json and one engine folder), and
`horizon-checksums.json` (SHA-256 of every payload file), plus `horizon-media.tar.gz`
(the showcase clips: a flat archive of `.mp4` and `.jpg`) and
`horizon-maps.tar.gz` (the map gallery: flat `map-NN.png` and `.jpg`). Create a **draft** Release
for this tag in the new public repo and attach these three files. For example,
using GitHub CLI from that repo:

```sh
gh release create v0.0.1 --draft --target "$(git rev-parse HEAD)" \
  --title 'Digimon World Horizon 0.0.1' --notes 'Prepared; awaiting CI validation.'
gh release upload v0.0.1 build/pages-upload/horizon-package.tar.gz \
  build/pages-upload/horizon-engine.tar.gz build/pages-upload/horizon-checksums.json \
  horizon-media.tar.gz horizon-maps.tar.gz
git push origin refs/tags/v0.0.1
```

Keep the tag annotated: if GitHub already created a lightweight remote tag,
resolve that before publication. Alternatively push the annotated tag first,
stage the draft assets, then manually dispatch the failed workflow with that tag.
The workflow does not push, create or replace tags. Missing assets, lightweight
tags and identity mismatches fail before any deployment. Existing published
assets support a deployment retry. Avoid manually dispatching an old tag unless
an intentional rollback is wanted. Serialized runs prevent simultaneous deploys;
they do not enforce semantic version ordering.

CI downloads only the five named assets, validates them without executing their
code, regenerates `data/discs.json`, and copies tracked page assets. Developer
clips, tests, engine build tools and ignored files are excluded. The showcase
clips come from `horizon-media.tar.gz`. The engine's
embedded manifest must match the package byte for byte. The built site preserves
`web/CNAME` and includes `.nojekyll`. Pyodide, plan and packs are served from the
same origin; browser code never needs to fetch GitHub Release assets across CORS.
The engine archive remains attached for reproducibility and deployment retries.
CI replaces the draft title/notes with the version, date and commit, after Pages
succeeds. A failed final publication step can be retried by manual dispatch.

**Only the latest engine is served.** Immutable `engine/<hash>/` paths keep the
service worker cache valid. A cached old page can lose access to uncached old
packs after a deployment; reload before building if a release changes. Historical
engine archives remain on their Releases, not on Pages. The site builder limits
the site to 900 MiB and each file to less than 100 MiB. No COOP/COEP headers are
required by the current worker/OPFS implementation.

## The desktop apps

Pushing the tag also runs `.github/workflows/desktop.yml`: it builds Horizon Patcher for Windows and macOS from the
tag's source, self-tests both (no discs), and its `attach` job uploads `Horizon-Patcher-Windows.zip` and
`Horizon-Patcher-macOS.zip` to the tag's release, the draft staged above (it waits up to ten minutes for it). It
does not publish the release or touch Pages; `release.yml` does that and does not wait for the apps. If the apps
come later or fail, run "Desktop patchers" by hand with the tag: it rebuilds and replaces both zips. The apps take
the latest release's package themselves, so an older app keeps working with newer releases as long as their
patcher keeps `GUI_API = 1` ([the patcher guide](../patcher.md#the-desktop-app)).

## Code signing

Unsigned apps open only after a warning (Windows SmartScreen, macOS Gatekeeper); the players' README says how to
get past it. Signing removes the warning and nothing else changes.

**macOS (Developer ID, outside the App Store).** The macOS job signs every binary of the app with the hardened
runtime and a secure timestamp (PyInstaller, inside out, then the bundle), with only the entitlement in
`tools/patcher/app/entitlements.plist`, sends it to Apple's notary service (`xcrun notarytool submit --wait`),
staples the ticket to the app (`xcrun stapler staple`) and zips the stapled app with `ditto -c -k --keepParent`. It
does this when these repository secrets exist and the run is not a pull request; without them it builds the app
unsigned and says so in a warning:

| Secret | What |
|---|---|
| `MACOS_CERT_P12` | the Developer ID Application certificate with its private key, a `.p12` file, base64 |
| `MACOS_CERT_PASSWORD` | the `.p12` file's password |
| `ASC_KEY_ID`, `ASC_ISSUER_ID`, `ASC_KEY_P8` | an App Store Connect API key for notarytool: its key ID, the issuer ID, the `.p8` file's text |

Making them, once (no Mac needed; OpenSSL on Linux does the key and the certificate request):

1. The private key and the certificate signing request:

   ```sh
   openssl genrsa -out developer-id.key 2048
   openssl req -new -key developer-id.key -out developer-id.csr -subj "/emailAddress=YOUR_APPLE_ID_EMAIL/CN=YOUR NAME"
   ```

   Keep `developer-id.key` private (not in any repository).
2. At [developer.apple.com](https://developer.apple.com/account/resources/certificates/add) > Certificates > **+**,
   choose **Developer ID Application** (the Account Holder must do this; choose the G2 Sub-CA if asked), upload
   `developer-id.csr` and download `developer_id.cer`.
3. The `.p12` with the certificate, its private key and Apple's intermediate certificate (so the CI keychain can
   build the chain). `-legacy` makes the older encryption macOS's `security import` reads (OpenSSL 3's default can
   be refused):

   ```sh
   curl -sO https://www.apple.com/certificateauthority/DeveloperIDG2CA.cer
   openssl x509 -inform der -in developer_id.cer -out developer_id.pem
   openssl x509 -inform der -in DeveloperIDG2CA.cer -out DeveloperIDG2CA.pem
   openssl pkcs12 -export -legacy -inkey developer-id.key -in developer_id.pem -certfile DeveloperIDG2CA.pem \
       -name "Developer ID Application" -out developer-id.p12          # asks for the .p12 password
   base64 -w0 developer-id.p12 > developer-id.p12.b64                    # macOS: base64 -i developer-id.p12
   ```

   (With OpenSSL 1.1, leave out `-legacy`.)
4. The API key: [App Store Connect](https://appstoreconnect.apple.com/access/integrations/api) > Users and Access >
   Integrations > App Store Connect API > **+**, a name, access **Developer**. Download the `.p8` (only once) and note
   the Key ID and the Issuer ID shown above the list.
5. The secrets: GitHub > the repository > Settings > Secrets and variables > Actions > **New repository secret**,
   or with GitHub CLI:

   ```sh
   gh secret set MACOS_CERT_P12 < developer-id.p12.b64
   gh secret set MACOS_CERT_PASSWORD                    # type the .p12 password
   gh secret set ASC_KEY_ID --body KEYID
   gh secret set ASC_ISSUER_ID --body ISSUER-UUID
   gh secret set ASC_KEY_P8 < AuthKey_KEYID.p8
   ```

   Then delete the local copies you do not need. The certificate lasts five years; renewing it means steps 1 to 3
   and `MACOS_CERT_P12`/`MACOS_CERT_PASSWORD` again.

Check a signed build with "Desktop patchers" run by hand (no tag): the log shows `codesign --verify`, the notary
status `Accepted` and `spctl` saying `source=Notarized Developer ID`.

**Windows.** The Windows exe carries version information (product "Digimon World: Horizon Patcher", the release's
version as file and product version, company and description: `tools/patcher/app/build.py`) and is built from the
tag's source in GitHub Actions, the unsigned zip kept as the workflow artifact `Horizon-Patcher-Windows`. That is
what [SignPath Foundation](https://signpath.org/)'s free signing for open-source projects asks for; the project's
[code signing policy](../code-signing-policy.md) is drafted. SignPath signs only projects whose app was already
released unsigned, so the first releases ship it unsigned. Once the project is accepted, the commented
`signpath/github-action-submit-signing-request` step in `desktop.yml` is filled in (with the token SignPath gives as a
repository secret) and the release takes the signed zip; the attribution SignPath requires then goes into the
policy and the README, worded as SignPath's terms give it.

## Owner setup, once

1. Publish the reviewed snapshot as a new root with the approved pseudonym and
   empty author/committer email. Audit tags, refs and nested histories separately;
   do not expose private ancestry. Set the actual repository URL in the build guide.
   In Settings → Pages choose **GitHub Actions**. Allow the `github-pages`
   environment to deploy the release tags as well as manual runs; review any
   environment protection rules. The workflow uses the repository's
   `GITHUB_TOKEN`: contents read for assembly, Pages/OIDC write for deployment,
   contents write only for final Release publication. No personal token or discs.
2. In Settings → Pages set the custom domain to `dw1horizon.com`. The checked-in
   CNAME alone does not configure a custom domain for Actions deployments.
3. At your DNS provider, configure four `A` records for `@`:
   `185.199.108.153`, `185.199.109.153`, `185.199.110.153`, `185.199.111.153`.
   Remove conflicting old apex/IPv6 records. If desired, point `www` with a CNAME
   to `<owner>.github.io` (no repository path). An apex cannot use that ordinary
   CNAME; use the four A records above. DNS changes belong to the owner.
4. Wait for GitHub's DNS check and certificate provisioning, then enable
   **Enforce HTTPS**. Verify https://dw1horizon.com/ and `engine/current.json`.

See GitHub's [custom workflow documentation](https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages)
and [custom domain records](https://docs.github.com/en/pages/configuring-a-custom-domain-for-your-github-pages-site/managing-a-custom-domain-for-your-github-pages-site).

## Page-only changes

The page comes from the commit running the workflow; the engine, package and disc metadata
always come from the tag. To publish a page change without a new release, merge it to `main`
and run the workflow from `main` with the current tag. The run regenerates release notes
from the tag's English changelog entry. v0.0.1 predates this: a run on that tag still writes
the old text, so restore its notes afterwards (`gh release edit TAG --notes-file ...`). The Pages check does not cover
the clips or the box art: the clips are release assets and the browser fetches the box art from
libretro-thumbnails.
