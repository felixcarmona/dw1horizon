# Source surface coverage audit

All 183 registered imports were processed against pinned final provider files; no processing errors. 169 have verified transforms for the complete source surface; 14 retain unverified regions. Nine authored native builders use their authored pre-provider meshes as the reference, rather than retired disc imports.

The reference disables face dropping, decimation and rig welding. Four area-weighted interior samples per source triangle are compared with surviving surfaces on the verified final carrier. Tolerance is 2.5 units or 0.3% of the model diagonal, whichever is larger. Authored proportions and poses are fitted first. Coverage is an estimate of geometric preservation, not proof of visible damage: intentional remodeling and ambiguous fits need review. Repeated UVs and split quads must not create false geometric holes; texture attribution is measured separately.

The table ranks the 15 lowest surface coverages among fully verified models, after these repairs. The separate partial table reports coverage only within the verified source region; the rest remains unknown.

| Rank | Import | Surface covered | Action / remaining work |
|---:|---|---:|---|
| 1 | 400 Apocalymon | 91.127% | Body surface changed despite equal triangle count; review authored geometry. |
| 2 | 335 MegaGargomon | 94.008% | Ten head triangles restored; other deleted regions remain. |
| 3 | 407 Armageddemon | 96.436% | Broad reduction; needs a new budgeted authoring pass. |
| 4 | 334 Mummymon | 97.821% | Broad reduction across limbs and body; re-author within storage limits. |
| 5 | 251 Solarmon | 98.095% | Equal triangle count; verify authored proportions before changing geometry. |
| 6 | 328 Snimon | 98.107% | Multiple reduced regions; selective restoration needs budget review. |
| 7 | 310 Assaultmon | 98.665% | Large object 15 deficit; native fit/reduction needs separate review. |
| 8 | 336 Raidenmon | 98.985% | Broad reduction; reserve the thin appendage outlines. |
| 9 | 318 Gallantmon | 99.512% | Localized object 5 deficit; verify and budget a targeted restoration. |
| 10 | 432 Bastemon | 99.592% | Small residual; review quantization/authored geometry before repairing. |
| 11 | 316 Sakuyamon | 99.686% | Small residual; review quantization/authored geometry before repairing. |
| 12 | 325 Musyamon | 99.780% | Small residual; review quantization/authored geometry before repairing. |
| 13 | 314 SkullSatamon | 99.897% | UV-partition false positive corrected; only small arm surface residuals remain. |
| 14 | 312 Creepymon | 99.946% | Small residual; review quantization/authored geometry before repairing. |
| 15 | 311 Arukenimon | 99.956% | Small residual; review quantization/authored geometry before repairing. |

| Partially verified import | Source area checked | Covered within checked area |
|---|---:|---:|
| 409 Kyubimon | 47.311% | 92.631% |
| 405 Cannondramon | 52.440% | 58.030% |
| 206 MagnaAngemon | 62.964% | 87.370% |
| 431 Kurisarimon | 72.096% | 99.947% |
| 402 NeoCrimson | 72.817% | 82.261% |
| 403 Beelzemon | 74.284% | 91.216% |
| 406 MaloMyotismon | 88.481% | 93.242% |
| 460 Garudamon | 90.106% | 99.724% |
| 306 GrapLeomon | 90.426% | 99.620% |
| 324 Maildramon | 95.977% | 99.956% |
| 326 WarGrowlmon | 95.986% | 93.896% |
| 430 Zanbamon | 98.587% | 99.960% |
| 408 Suijinmon | 98.731% | 72.784% |
| 190 Angewomon | 98.959% | 100.000% |

Other fully verified nonzero residuals: 333 Raijinmon (0.033% uncovered), 319 Pharaohmon (0.001% uncovered).

KingEtemon (303): all 76 cape triangles and their UV colours were already present. Independent native panel anchors/orientations and a pelvis assignment for the lower panels opened the cape. All four panels now follow the chest piece’s complete affine fit and carrier. Detected cape attachment gaps decrease from 54.42 units to below the 2.5-unit audit threshold; cape surface coverage remains 100%. This repair changes the native binding, rather than the chibi length axis used for Pharaohmon (319). Pharaohmon remains at 100% source surface coverage; its prior length-axis repair is retained.

MegaGargomon (335): restore source triangles only on objects 17, 18 and 21, preserving indexed positions, UV layout and animation. Each repaired part reaches 100% surface coverage (previously 92.023%, 93.716% and 96.535%). Whole-model coverage improves from 93.776% to 94.008%; ten triangles return. A conservative 416-byte GPU packet-growth bound passes the 1,024-byte authoring allowance. The remaining heavily reduced body regions require a separate budgeted pass; restoring everything is outside this narrow repair.

Resident storage: 303 increases from 100,146 to 100,220 B; 335 increases from 95,686 to 95,994 B. The all-import maximum remains 100,256 B (species 304), below the unchanged 100,352 B buffer. All 183 baseline imports fit; both repairs also pass sector-aligned cold-read checks. No runtime allocation or buffer constant changes.

New decimation authoring pins original open-boundary positions, protecting cloth/cape/wing outlines and attachments while allowing interior simplification. Frozen specs retain their previous replay. The source restoration tool refuses ambiguous pools/textures, requires a full affine fit and checks storage and packet growth. The editor can stage equipment-manifest input pins when repinning a repaired model.

Evidence is local under `build/coverage-final/`, `build/king-final/`, `build/coverage-after/` and `build/303-before-after.png`. The compact [all-import metrics](reduction-audit.json) contain hashes and measurements, with no source assets. The full report combines the baseline scan, rechecked ambiguous carrier assignments, and regenerated repaired providers; unchanged models retain their pinned baseline outputs.

Validation: 71 related tests, 14 native KingEtemon output assertions, delta decoding checks for 303/335, final provider SHA-1 checks, and resident/cold-read audits. Native output assertions reuse the genuinely regenerated provider artifact to avoid repeating the expensive hand-clearance search. No disc build or interactive playback was performed.
