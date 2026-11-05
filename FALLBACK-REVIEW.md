# Disc fallback review

Reviewed the eight borderline findings from the audit following PR #183 against branch base `8f3fae8d`. The original scratchpad report was unavailable; its exact eight-entry list was recovered from the audit session's recorded report-writing command. Numbering below preserves that list. Source locations refer to this worktree after the fix.

Game decisions and defaults must come from owned JSON. Models, map artwork/geometry, display text, sounds and the code needed to use them may be reconstructed from pinned player assets. A checksum proves identity, not that a byte is an asset rather than a gameplay parameter.

One definite source-of-truth problem is fixed: case 5 used committed CSV instead of the existing screen JSON. It did not read a live disc, but violated the JSON-only configuration requirement and could override edits or deletions. Cases 3, 4, 6 and 7 do not demonstrate a product gameplay fallback in their inspected paths. Cases 1, 2 and 8 remain unresolved classification work; they are **not certified asset-only**. No speculative binary replacement was made.

Effort below describes the work involved, rather than an unmeasured completion-time promise. Small means a localized generator/configuration change; medium includes tracing all readers of a domain and regional comparisons; large requires an inventory across executables/overlays and release replay.

## 1. Mixed records copied during relocation — unresolved

**Where:** `tools/patcher/tabledata.py:210` (`prepare`, especially the `kind='record'` branch); `tools/patcher/fontcopy.py:322` (`table_tail`).

**In plain words:** when a compiled record contains relocated pointers, the packager generates the pointers but may copy the bytes between them from a matching record on the player's disc. It requires complete-layout witnesses and pinned file hashes. Explicit item, aura and UI generators take precedence, as do the existing named semantic generators.

**Rule verdict:** copying code-support structures or text assets is permitted. Copying a combat value, route, price or other gameplay default this way would violate the rule even when it equals the intended JSON value. The generic record mechanism does not identify the meaning of every remaining field. Its existence alone does not identify a particular additional gameplay field to migrate safely.

**Risk if left:** a future mixed structure can introduce an unnoticed numeric disc dependency. Current whole-record and digest checks prevent accepting arbitrary source bytes, but do not establish JSON authority. Conversely, replacing entire records with JSON byte arrays could publish text or other restricted asset bytes.

**Concrete follow-up:** inventory emitted `record` recipes by linker symbol and field offset. For a confirmed gameplay field, put its typed values in the existing domain JSON and add a named `semantic` recipe in `tabledata.authored_recipe` / `fontcopy.semantic_table`. For a newly identified domain, use `content/tables/relocation-data.json`, `objects.<symbol>.numericFields`, containing named typed values, never opaque copied records. Keep pointer expressions and asset references separate. Reject unclassified numeric fields in that domain. Prove all supported regional/language reconstructed fields equal the old output and test that changing the JSON changes output even with unchanged disc bytes. **Effort: large** for the inventory, then small per classified domain. Left documented because the remaining objects have not all been classified.

## 2. Initial bytes of overlay scratch buffers — unresolved

**Where:** `tools/patcher/bufferdata.py:15` (`player_buffers`); `tools/patcher/buffers.json`.

**In plain words:** selected inherited overlay storage is initialized with the corresponding region's on-disc bytes. JSON identifies 146 objects across 11 overlays (167,124 bytes of target storage), their sizes and regional offsets. It does not specify the initial values. The evolution shard buffer has an explicitly checked zero extension.

**Rule verdict:** storage overwritten before any read is scratch residue, not a gameplay default. Bytes read before being written could be real defaults and would then require JSON. Names such as `BTL_BUFF_RING_SPARKS` suggest scratch storage, but names and BSS provenance are insufficient proof of lifetime. `EVL_D_80066274` also has a special extension that must remain covered.

**Risk if left:** an overlooked read-before-write can make behavior depend on regional residue. Blindly zeroing all objects can break initialization or rendering and cannot honestly be claimed byte-identical.

**Concrete follow-up:** trace allocation/reset and every first reader of each configured symbol. Extend `tools/patcher/buffers.json` with `objects.<symbol>.initialization` (`write_before_read`, `zero`, or `values`) and, only for actual numeric initial state, `initialValues` with an element type/count. Generate numeric state in `player_buffers`; retain asset bytes only with explicit classification. Add lifecycle coverage for overlay reload and first use, plus regional replay comparisons. If old initial bytes differ but are dead, semantic equivalence is a separate proof, not byte equivalence. **Effort: large**, because every configured object's lifetime must be checked. No safe, byte-identical numeric migration established here.

## 3. Regional overlay headers — permitted structure

**Where:** `tools/patcher/tabledata.py:331` (`header_recipe`); `tools/patcher/fontcopy.py:322` (`regional_header` handling).

**In plain words:** it finds the overlay's 64-byte `MWo1` header by name, copies non-pointer header fields from the pinned regional file and regenerates the relocated pointer. These fields identify the program container and its layout.

**Rule verdict:** no gameplay fallback demonstrated. Binary layout metadata is required to reconstruct code; it does not choose a species, stat, evolution or reward. Moving these bytes into gameplay JSON is unnecessary.

**Risk if left:** a format/header change would need review; the present unique-header search and pin checks fail rather than treating an unknown header as a gameplay default. A layout field mistaken for a game rule would need reclassification.

**Concrete fix:** none required under this rule. If independently authored header layout becomes desirable, use `tools/patcher/overlay-layout.json`, `overlays.<name>.regions.<base>.header`, with typed size/layout fields and generated names/pointers; do not store an opaque 64-byte array. Compare every regional header before changing the recipe. **Effort: medium**, optional structural work. Left unchanged.

## 4. YAKA22's malformed, unreachable placement area — permitted opaque asset exception

**Where:** `tools/content.py:463` (`NEVER_READ`), `:549` (`build_map`). Its owned screen row disables Digimon reads.

**In plain words:** this map advertises 63 Digimon but does not contain a valid placement list. The builder preserves its opaque map bytes instead of interpreting or rewriting nonexistent records. The game does not read its Digimon list. All parsed map placement lists still come from JSON, including empty/deleted configurations.

**Rule verdict:** no reachable gameplay default demonstrated. This is retention of an unparsed map asset, not selection of playable enemies from the disc. The exception must not be generalized to a readable placement domain.

**Risk if left:** making the screen read Digimon later would invalidate the exception and could expose malformed data. Arbitrary clearing risks damaging map assets and cannot preserve the old bytes.

**Concrete follow-up:** no numeric migration is needed while unreachable. Optional hardening: put `opaquePlacementAssets: ["YAKA22"]` in `content/tables/map-policy.json`; make the builder reject any corresponding screen JSON with `reads_digimon: true`. If placements are enabled, first establish a valid map format, then provide `content/maps/YAKA22.json` with an explicit `digimon` list and rebuild that domain from empty. **Effort: small** for the guard, large for format recovery. Left unchanged; byte-identical clearing cannot be claimed.

## 5. Native screen defaults from CSV — fixed

**Where:** formerly `tools/dws/backend.py`'s two `docs/data/map_files.csv` comprehensions; now `native_screen_metadata` at `:290`, plus `tools/derive/steps/story.py`'s declared inputs.

**In plain words:** the compiler got native map file names and flags, including sound-region flags used by recruitment jingles, from the reference CSV. Only extended screens overlaid JSON. Editing or deleting a native screen JSON could therefore leave the compiler using stale reference values.

**Rule verdict:** definite JSON source-of-truth violation, although the CSV is committed and no current player-disc read occurs.

**Risk if left:** engine tables and story compilation can disagree about the same screen. A deleted native row can remain visible to the compiler, and a changed sound bank can still select the old recruitment jingle.

**Implemented fix:** `file`, `sound_bank`, `flag20`, `day_night` and `reads_digimon` come from `content/screens/<id>-*.json`. New `content/tables/story-screens.json`, `nativeScreenIds`, explicitly preserves the compiler's 239 native IDs (0–238). It avoids accidentally exposing reserved executable IDs 239–254, including the five populated Back Dimension rows. A deleted screen contributes no entry; a missing visibility file fails closed. Extended screen behavior is unchanged. The new configuration is a declared story cache input and is included by the existing bundle rule for tracked content. CSV remains inspection metadata. **Effort: small; implemented in fix commit `6a133e87`.**

**Proof:** all 239 file names and flag bytes equal the old CSV generator. Fresh before/after builds of the complete owned base story (222 scripts, 1,831 events) produce identical `DG.SCN` (792,576 bytes) and `MAPHEAD.SCN` (24,786 bytes). Mutation tests change a screen's name and flags, remove its JSON, omit the visibility file and reject invalid visibility IDs. They also check that a populated reserved row does not silently enter the compiler namespace.

## 6. Retained display text and partial translation builds — permitted assets

**Where:** `tools/localize/executable/bank.py:132` (`exe_bank`); `tools/dws/textbank.py` (`TextBank.load_defaults`).

**In plain words:** explicit source-text builds retain original display strings; partial development translations retain text outside selected zones. Executable strings can also stay when replacements are absent, unsupported or too large. Ordinary authored languages load authored English for missing translations.

**Rule verdict:** display text is an explicitly allowed disc asset. This does not authorize reading numeric gameplay parameters from strings. No such numeric-default use was established in these paths. Species names already have their owned-data path.

**Risk if left:** incomplete translations or formatting failures can remain visible in a release. That is a text coverage problem; it is not a hidden battle/evolution fallback. Checks must continue to distinguish text formatting contracts from game rules.

**Concrete fix:** none required by the data rule. Optional release text policy could use `content/tables/text-policy.json`, `release.requireAuthoredKeys` and `development.allowPartialZones`, to reject unintended retained strings while allowing explicit text-source builds. Keep actual untranslated disc dialogue out of published JSON. **Effort: medium**, because permitted retained keys must be inventoried across languages. Left unchanged.

## 7. Explicit legacy script patching — authoring path, not product fallback

**Where:** `tools/dws/backend.py:227` (`ensure_dis`), `:841` (`apply`); `tools/dws/basebuild.py` (`_build`, temporary replacement of `BE.DIS_CACHE` and `BE.MAPHEAD_SCN`).

**In plain words:** the legacy developer `dws build` command patches a disassembled original script. The product story builder first compiles owned `story/base` sources and temporarily points that same backend at the owned result. A missing product story source already fails; it does not switch to disc scripts.

**Rule verdict:** no product gameplay fallback. Explicit disc import/inspection remains an authoring tool, just like extraction of numeric tables. Using legacy `dws build` directly as a replacement product story build would retain disc decisions and break the rule.

**Risk if left:** command names alone do not prevent someone from treating a legacy developer output as a release input. Product-route tests and the required owned-base check remain important.

**Concrete follow-up:** no gameplay JSON field is needed; scripts belong in owned story sources. Optional separation can use `tools/dws/build-policy.json`, `product.storySource: "owned"`, `authoring.allowDiscScriptImport: true`, enforced at the release entry point. Prefer an explicit authoring command over adding a disc fallback flag to product compilation. **Effort: medium** for command separation and release-entry tests. Left unchanged.

## 8. Generic binary copies and deltas — unresolved per copied object

**Where:** `tools/patcher/datacopy.py:82` / `:153`; `tools/patcher/codecopy.py:181`; `tools/patcher/dwpatch.py:771` (`BaseDisc`).

**In plain words:** packaging finds exact matching bytes and reconstructs code/assets by copying or applying deltas to pinned inputs. It can also regenerate linker fields. The result is hash-checked. This mechanism operates on binary spans, so a match does not explain what a span means.

**Rule verdict:** copying executable instructions, artwork, sound or text is permitted. Copying a numeric gameplay default instead of generating it from JSON is prohibited, even with identical bytes. The generic mechanism cannot be declared compliant for every span without classification. The inspected helpers do not provide a new, individually identified numeric domain that can safely be migrated in this review.

**Risk if left:** provenance checks can pass for a mixed literal that still contains a gameplay decision. This overlaps case 1, but also covers raw copies, regional mappings and binary deltas outside structured record recipes. Removing all copies would obstruct required asset reconstruction and could publish restricted bytes as literals.

**Concrete follow-up:** inventory emitted operations against linker objects and derived output domains. Add `tools/patcher/copy-policy.json`, `objects.<symbol>.category` (`code`, `asset`, `layout`, `gameplay`) and `objects.<symbol>.generator` for gameplay fields. Route gameplay spans through the corresponding existing `content/tables/*.json`, species/item/map JSON and semantic generators; exclude those spans from exact-match copy substitution. Fail unknown gameplay classifications, retain pinned asset provenance, and replay a real package across all supported bases. Do not encode the source bytes in policy JSON. **Effort: large**, including regional packaging proof. Left documented, not claimed resolved by the literal provenance gate.

## Validation and boundaries

Evidence is local under `build/fallback-review/`:

- `metadata-proof.json`: 239 native rows equal; normalized metadata SHA-256 `f33ad81336daee9ae482f87c427dc47d0f6d86bca072353df5c702e188e642ba`.
- `story-proof.json`: before/after `DG.SCN` SHA-256 `2047a2792e43b8c909b52260d0d6c8de4601c847e6a4aad2489b40e14556f534`; `MAPHEAD.SCN` SHA-256 `1828aae4d92acbf42d1bdad26ff7b8942e3d414e21b4895e8d17bb7055f5a8c7`.
- `tests.log`: 47 focused data-source, table-recipe, buffer and code-copy tests pass, including the new deletion/mutation/configuration checks.

No C or patch-series changes were made. The compared story files have identical sizes and bytes; the executable and its BSS are unchanged by this generator change. No new heap measurement, full eight-language ISO build, browser package replay, emulator session or physical-console test was performed. This review does not prove every copied binary literal is non-gameplay data. No media was produced and nothing was pushed.
