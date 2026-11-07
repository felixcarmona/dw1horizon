# Release recovery validation

Correctness and timing are separate. This validation used one full keep-going pass and subsequent verified resumes in the same output directory. No cold reference cut or publication was performed. True cold timing remains for the v0.0.7 cut; the observed times below use retained caches and are not a cold performance claim.

The branch includes `origin/main` at `d022435e`. Regional reconstructions and the World 3 USA source derivation share a bounded, memory-aware pool; offline and emulator gates overlap packaging after the fresh native disc passes both heap checks. Independent engine import, map and sign units retain bounded workers. Unproven parallel story batches are disabled; story recording preserves canonical serial order. Literal checks, image pins and isolated verification remain mandatory.

## Recovery behavior

The driver and packager record explicit dependencies, continue independent steps after failure, and mark consumers as blocked by failed inputs. Reports include every failing step, command, log and exit code in JSON and text. A failed round exits nonzero. Successful checkpoints record input fingerprints and SHA-256 output inventories; resume verifies both before reuse. Failed, blocked, changed, missing and corrupted work reruns. Immutable prepared sources are separate from native-generated files.

Use `python3 tools/release.py --resume --out build/releases/candidate` after focused fixes and a commit, retaining the original worktree and output directory. The original gate options are restored. Do not delete markers or copy partial outputs to force success. Full commands, worker logs and quiet-machine preparation are documented in [the release procedure](docs/release/releasing.md).

## Correctness evidence

- Focused tests cover middle-step failure, independent continuation, blocked dependants, verified skips, changed inputs, missing outputs and corruption with preserved timestamps. Cache tests vary source discs, native programs/maps/facts/fonts, metadata, inventories, code and runtime libraries. The combined focused suite passed 162 tests; the standalone recovery suite passed all 20 tests.
- Canonical sequential recording and isolated parallel USA replay matched all 1,717 derived files, totaling 521,396,820 bytes, by direct comparison.
- The complete USA reconstruction matched the native image byte for byte: 910,456,848 bytes, SHA-256 `53625d4cd944d5de3bfa669a4f6efd41a6765eb6c823913856a4d7d039fa03af`.
- The actual browser lazy-source adapter rebuilt that same full image from retained verified derived files, also matching byte for byte. The storage-probe race regression failed before its fix and passed afterward in Chromium; all 18 lifecycle checks passed, including actual cross-tab exclusion.
- All seven default-base and seven World 3 USA source outputs passed their pins. Standalone replay passed for USA, Japan revision 1, and Europe with World 3 USA sources. The offline selftest passed 125 checks with zero skips.
- The original 2 MB build measured `main_BSS_END=0x801cdf84`, leaving 188,272 bytes of main heap. The story heap gate passed; the tight screen retained approximately 3 KiB. No original hardware test was performed.

## Recovery rounds

| Round | Source | Elapsed | Failures and recovery |
| --- | --- | --- | --- |
| 1 | `583f3c8f` | 17,928.855 s (4 h 58 min 49 s) | Selftest species formatting and baked-model expectations were stale, and its decomp selection skipped host checks. Published-save validation used a retired frame-rate encoding and stalled on arrival dialogue. Literal coverage lacked authored feed-note bytes and the exact care-HUD layout recipe. Independent image, journey and ending checks completed; package consumers were blocked. Fixed in `e52b5f02`. |
| 2 | `e52b5f02` | 14,090.751 s (3 h 54 min 51 s) | A standalone recovery-test import failed. Browser asset derivation completed, then Chinese resource rebuilding rejected a lazy source object. All other required work passed, including 14 image pins, literal verification, standalone replay and engine construction. Fixed in `50d38f27`. |
| 3 | `50d38f27` | 8,109.067 s (2 h 15 min 9 s) | The browser Build action raced its own advisory storage-space probe and reported another tab. Every other gate passed or was verified and reused. The production click path reproduced the race; awaiting the probe fixed it while retaining cross-tab exclusion. Fixed in `434e9c1a`. |
| 4 | `434e9c1a` | 12,645.568 s (3 h 30 min 46 s) | Green: every required gate passed, final input/output verification passed, no failed or blocked steps, exit 0. Both engine recordings were verified cache hits. The changed interpreter-library fingerprint forced the affected driver and packaging checkpoints to rerun. |

Round 3 reused the published-save, journey, ending, heap, prerequisite, prepared-decomp and player-interpreter checkpoints after verifying their inputs and outputs. Regional asset caches also recorded verified hits. Round 4 detected a changed interpreter-library fingerprint and invalidated the affected checkpoints: substituting only the previous runtime hash reproduced the previous player-interpreter fingerprint exactly. This is required input invalidation, not a timing comparison.

## Observed green phase times

The green round validated code commit `434e9c1a` on 2026-11-07. Total wall time was **12,645.568 seconds (3 h 30 min 46 s)**. These are observed resume times with retained caches, including verified engine-record reuse; source-bundle recording was a cache miss after runtime invalidation. They are not a cold benchmark. Concurrent phase durations do not add up to total elapsed time.

| Driver phase | Wall time (seconds) |
| --- | ---: |
| `prerequisites` | 5.818 |
| `player-python` | 0.153 |
| `decomp` | 2.434 |
| `sources` | 0.469 |
| `native` | 1,347.445 |
| `heap` | 0.150 |
| `story-heap` | 32.945 |
| `fixtures` | 15.206 |
| `selftest` | 1,024.887 |
| `published-save` | 128.132 |
| `journey` | 699.258 |
| `ending` | 620.900 |
| `package` | 8,281.848 |
| `standalone/us` | 1,891.850 |
| `standalone/jp1` | 1,895.853 |
| `standalone/eu+dw3-us` | 1,897.945 |
| `engine` | 14.033 |
| `browser` | 2,901.208 |
| `archive` | 6.842 |
| `checkout` | 0.233 |
| `complete` | 49.280 |

All fast checks passed. The package phase includes these measured substeps:

| Packaging substep | Wall time (seconds) |
| --- | ---: |
| `source-bundle` | 3,202.018 |
| `isolated-verification` | 1,184.351 |
| `encode/everything` | 173.837 |
| `base/everything/us` | 57.417 |
| `base/everything/de` | 3,093.813 |
| `base/everything/es` | 3,118.630 |
| `base/everything/eu` | 3,120.570 |
| `base/everything/fr` | 3,105.559 |
| `base/everything/it` | 3,122.678 |
| `base/everything/jp1` | 3,078.438 |
| `source-derive/dw3-us/us` | 3,131.875 |
| `assembly` | 2.511 |
| `literal-gate` | 137.217 |
| Seven source-variant writes, concurrent | 295.988–300.194 each |

The literal gate reported zero disc-matching, copyable-original, unresolved-mapping and unverified-delta bytes. Browser verification produced the complete 910,456,848-byte image with SHA-1 `91aca9ffb0094710b0d560ace6e34929a7395816`. The browser build took 2,859.1 seconds from Build to DONE; the full gate also includes setup and verification. Its measured browser-process peak RSS was 3,758 MB, with 4.32 GB peak private storage.

Engine construction took 14.033 seconds because both USA and Japan revision 1 graph recordings were verified cache hits. Graph recording itself did not run in the green round. The last actual graph recordings, in round 3, took approximately 2,399 seconds per base with two concurrent bases and three unit workers per base. Their per-worker logs and timing sidecars are retained; this does not measure a cold story-batch speedup.

## Timing limits

The earlier v0.0.6 observations were approximately 44 minutes for source recording, 23 minutes for isolated verification, one hour for deltas, and 25–35 minutes for each sequential regional reconstruction. Its engine recording used one core for more than 30 minutes. These are historical observations, not a controlled baseline for this branch.

Round 3's reused asset path took 2,402.7 seconds for source recording, 902.5 seconds for isolated verification, 151.6 seconds for encoding, and 4,566.6 seconds for packaging overall. Regional default workers took about 513–565 seconds, with World 3 USA derivation overlapping them; source-variant image writes took about 294–299 seconds. Engine construction took 2,438.8 seconds, including roughly 2,399 seconds of graph recording for each of two concurrent bases. Canonical story recording remains serial, so these observations do not establish a story-batch speedup.

The green round reserved 6,144 MiB per regional/source worker, running seven workers with two derive jobs each. Maximum measured worker process-tree RSS was 711,524 KiB (694.8 MiB), for Japan revision 1; source recording peaked at 378,160 KiB (369.3 MiB). Across earlier validation rounds, the regional/source maximum was 712,472 KiB (695.8 MiB). The last actual engine recording in round 3 peaked at 844,512 KiB (824.7 MiB) for its process tree; that scope differs from a regional worker and from the complete browser process tree. Cold elapsed time and the original 2–2.5 hour target remain unmeasured; capture them during the real v0.0.7 cut on a quiet machine.

Private evidence remains under `build/releases/validation-keep-going/`: per-round JSON and archived logs in `rounds/`, the explicit plans and completion markers in `recovery/` and `package-state/`, `package-timing.json`, and the green `failures.json` / `failures.txt` reports containing no failures. Direct byte proofs and focused test logs remain under `build/`. No tag was created; nothing was pushed, published or deployed.
