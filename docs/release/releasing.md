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
(the showcase clips: a flat archive of `.mp4` and `.jpg`). Create a **draft** Release
for this tag in the new public repo and attach these three files. For example,
using GitHub CLI from that repo:

```sh
gh release create v0.0.1 --draft --target "$(git rev-parse HEAD)" \
  --title 'Digimon World Horizon 0.0.1' --notes 'Prepared; awaiting CI validation.'
gh release upload v0.0.1 build/pages-upload/horizon-package.tar.gz \
  build/pages-upload/horizon-engine.tar.gz build/pages-upload/horizon-checksums.json \
  horizon-media.tar.gz
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

CI downloads only the four named assets, validates them without executing their
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
and run the workflow from `main` with the current tag, then restore the release notes
(`gh release edit TAG --notes-file ...`): the run rewrites them. The Pages check does not cover
the clips or the box art: the clips are release assets and the browser fetches the box art from
libretro-thumbnails.
