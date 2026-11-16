# Omnimon mesh flicker investigation (2026-11-16)

This is the sibling job's investigation and proposed full split. The current
branch retains its detector and shared splitter, but ships the budget-neutral
[general pipeline repair](mesh-glitch.md), not the 95-quad delta described below.
The quoted full-split hashes and sizes are historical experimental results.

The reproducible mesh defect is **bent quads controlled by one back-face decision**.
Libgs tests a quad's first three vertices with NCLIP, then submits both GPU triangles.
When the halves face opposite directions, one small surface can disappear or show
as the first half crosses edge-on. Treating both halves as separately culled
triangles, as the old meshcheck renderer did, hid this failure in developer views.
At 160×160, the software renderer differs on 390 of 1,544 field
frame/views (1–11 pixels each); one witness is tired-walk slot 3, tick 6,
view above225. This reproduces the scale of the reported small fragments. It has
not been verified on a handheld emulator.

## Evidence and onset

The supplied `imported-models/461.MMD` is the delta target, before the provider's
last passes. The provider's actual final model is named by the generated species
record (`imported-species-models/461-rig.MMD` in the supplied build). Rebuilding
with `edit.provider_output` reproduced that file byte for byte. Its skeleton has
25 bones, the imported DCB rig; Omnimon has no native-bindings.json entry and no
runtime blended vertex weights.

All 52 occupied final slots, including aliases, were decoded without sampling:
2,116 ticks, eight elevated camera directions per tick. No triangle collapses;
minimum area is 38.183766 square model units throughout. Bone transform
determinants remain +1. The largest root-relative coordinate is below 700 units.
Vertex steps and ordinary facing changes are measured, not automatically called
mesh defects. These model-space bounds do not prove camera-space GTE or OT safety.
No stray detached components were found by meshcheck's existing idle check.

95 quads have a dihedral angle above 3 degrees. The worst are object 7,
primitives 60–63 (bone 8), at 24.15–26.16 degrees. Head, pelvis, shin and other
small curved surfaces also have bent quads. As a concrete temporal witness,
walk slot 2, bone 1, primitive 24, view above45 has opposite-facing halves on
16 ticks (first examples 9–16); its first-half culling decision changes at
8→9, 16→17, 28→29 and 36→37. The other half's projected area reaches
177.484 square model units. Facing changes on a rigid triangle alone are normal;
it is the disagreement **inside one quad** that makes this a hazard.

| Stage | Bent quads >3° | Worst bend | TMD SHA-256 |
| --- | ---: | ---: | --- |
| Frozen importer / pre-reshape mesh | 63 | 18.6095° | `ea370f54e3e66378c67ebee5b41c3d96c4ed9616322298ea68059416771f2429` |
| Historical provider before 588eb2f5 | 95 | 26.1585° | `618aae22b4dbda100115107fe151e736a7fc19b44227182ca410846fe7e37530` |
| Delta before be6b12c1 | 95 | 26.1585° | `618aae22b4dbda100115107fe151e736a7fc19b44227182ca410846fe7e37530` |
| Current provider before repair | 95 | 26.1585° | `618aae22b4dbda100115107fe151e736a7fc19b44227182ca410846fe7e37530` |

The old importer already contains the defect. Chibi fitting increased its worst
bend from 18.61° to 26.16°. To reconstruct the pre-588eb2f5 provider, its original
chibi/gait code and manifest were run on the decoded historical delta; the TMD
is identical to today's. The mesh also did not change at be6b12c1: those spring
clips expose an existing hazard, rather than create the bent geometry.
The field clips already have divergent-half and temporal cases before the springs.

## Sibling proposed repair and validation

`tools/models/repair_omnimon_mesh.py` splits the 95 quads above the 3° threshold
along the GPU diagonal, (0,1,2)/(1,3,2). Each half gets its own culling decision
and depth-sort entry. The oriented triangle multiset, all corner UVs, normals,
palettes, texture pages, colors, vertex pools, back faces and animation programs
are preserved. No vertices are deleted or moved. Nearly planar rounded quads
at or below the threshold remain; this does not eliminate ordinary PSX pixel
quantization or prove that every possible camera artifact is gone.

Primitive count: 586 → 681 (limit 713). Repaired delta target resident size:
82,668 bytes; final provider resident size: 82,680 bytes (limit 100,352).
Final model SHA-1: `98aadda802cf515ed672643f33990de64ca4f3f2`.
Texture SHA-1 remains `77ff7be5c5c0a004310213053617a590a61ebaa8`.
No bent quads above the threshold, degenerates or collapsing triangles remain
in the final provider audit. `edit.py put` updates the delta and both manifests
and species pins; no hashes were edited by hand. `edit.py repin` was tried first
but refused the stale pre-bake gait source pin; that historical overlay
is inactive for Omnimon, and its old recipe/pin is retained.

Validation: meshcheck and new synthetic culling/collapse/corner-attribute tests;
Omnimon surface/animation preservation and budget/idempotence proof; existing
Omnimon gait, battle QA, motion storage, chibi proportion and native bone-count
suites; `edit.py check 461 --species-pins`; fresh decoded model's
`chibi_proportions.py check 461`. See the task build artifacts for test logs.

## Imported-species sweep

All 183 registry entries were audited: 8,971 occupied slots, 351,952 decoded ticks,
eight camera directions each, no errors or silently truncated clips. Models were
read from the final files named by generated species records, not the base delta
targets. Two stale build outputs (225 Shurimon and 239 Gizamon) were regenerated
from the current provider and checked against current pins before their results
were substituted. Every other species' final SHA-1 matched current pins; Omnimon's
baseline is the pre-repair pin. Complete compact measurements and input SHA-1s
are in [omnimon-mesh-sweep.json](omnimon-mesh-sweep.json).

**179 other species have quads above the same 3° threshold.** These are geometry
hazards, not 179 confirmed reports of visible flicker; many are occluded or only
edge-on. 22 species also contain static degenerate or pose-collapsing triangles;
these can include intentional hidden geometry. None of those other models or
pins was changed. The table lists every species, including the three without
bent quads. “Collapse slots” includes slots carrying an already-degenerate face.

| ID | Species | Bent quads >3° | Static zero-area triangles | Collapse slots |
| --- | --- | ---: | ---: | ---: |
| 180 | Veemon | 110 | 0 | 0 |
| 181 | Puppetmon | 67 | 0 | 0 |
| 182 | Kimeramon | 86 | 0 | 0 |
| 183 | Wormmon | 109 | 0 | 0 |
| 184 | Hawkmon | 84 | 0 | 0 |
| 185 | Armadillomon | 81 | 2 | 50 |
| 187 | Stingmon | 52 | 0 | 0 |
| 188 | Aquilamon | 13 | 0 | 0 |
| 189 | Ankylomon | 59 | 0 | 0 |
| 190 | Angewomon | 138 | 0 | 0 |
| 191 | MetalGarurumon | 40 | 0 | 0 |
| 192 | Imperialdramon | 83 | 0 | 0 |
| 193 | Digmon | 238 | 0 | 0 |
| 194 | ExVeemon | 41 | 0 | 0 |
| 195 | Flamedramon | 78 | 0 | 0 |
| 196 | Halsemon | 151 | 0 | 0 |
| 197 | Magnamon | 136 | 0 | 0 |
| 198 | Nefertimon | 106 | 1 | 48 |
| 199 | Paildramon | 159 | 0 | 0 |
| 200 | Pegasusmon | 184 | 0 | 0 |
| 201 | Lighdramon | 27 | 0 | 0 |
| 202 | Submarimon | 48 | 0 | 0 |
| 203 | Veedramon | 78 | 0 | 0 |
| 205 | MegaKabuterimon | 105 | 0 | 0 |
| 206 | MagnaAngemon | 162 | 0 | 0 |
| 207 | Seraphimon | 150 | 0 | 0 |
| 208 | Togemon | 25 | 0 | 0 |
| 209 | Lillymon | 261 | 0 | 0 |
| 210 | GranKuwagamon | 18 | 0 | 0 |
| 211 | MetalSeadramon | 44 | 0 | 0 |
| 212 | VenomMyotismon | 49 | 0 | 0 |
| 213 | AeroVeedramon | 68 | 0 | 0 |
| 214 | Shakkoumon | 60 | 0 | 0 |
| 215 | Magnadramon | 100 | 0 | 0 |
| 216 | Devidramon | 108 | 0 | 0 |
| 217 | Gomamon | 89 | 0 | 0 |
| 218 | Ikkakumon | 4 | 0 | 0 |
| 219 | Zudomon | 83 | 0 | 0 |
| 220 | Vikemon | 90 | 0 | 0 |
| 221 | Salamon | 120 | 0 | 0 |
| 222 | BlackGatomon | 95 | 0 | 0 |
| 223 | LadyDevimon | 230 | 0 | 0 |
| 224 | MetalGreymonVaccine | 4 | 0 | 0 |
| 225 | Shurimon | 98 | 0 | 0 |
| 226 | Silphymon | 72 | 0 | 0 |
| 227 | Apemon | 24 | 0 | 0 |
| 228 | Baronmon | 69 | 0 | 0 |
| 229 | Phantomon | 94 | 0 | 0 |
| 230 | Rosemon | 117 | 0 | 0 |
| 231 | ShellNumemon | 69 | 1 | 49 |
| 232 | BomberNanimon | 92 | 0 | 0 |
| 233 | RedOtamamon | 53 | 0 | 0 |
| 234 | Gatomon | 112 | 0 | 0 |
| 235 | Candlemon | 70 | 0 | 0 |
| 236 | DemiDevimon | 75 | 0 | 0 |
| 237 | Diaboromon | 60 | 0 | 0 |
| 238 | Dolphmon | 60 | 0 | 0 |
| 239 | Gizamon | 33 | 0 | 0 |
| 240 | Gesomon | 9 | 0 | 0 |
| 241 | Wizardmon | 102 | 0 | 0 |
| 242 | Sorcermon | 98 | 0 | 0 |
| 243 | Starmon | 18 | 0 | 0 |
| 244 | SuperStarmon | 18 | 0 | 0 |
| 245 | Piedmon | 113 | 0 | 0 |
| 246 | Infermon | 100 | 0 | 0 |
| 247 | Kokuwamon | 27 | 0 | 0 |
| 248 | MarineAngemon | 88 | 0 | 0 |
| 249 | Quetzalmon | 86 | 0 | 0 |
| 250 | Shadramon | 112 | 0 | 0 |
| 251 | Solarmon | 15 | 0 | 0 |
| 252 | Thundermon | 67 | 0 | 0 |
| 253 | Tuskmon | 24 | 0 | 0 |
| 254 | Tylomon | 47 | 4 | 47 |
| 255 | Valkyrimon | 81 | 1 | 50 |
| 256 | VioletElecmon | 40 | 0 | 0 |
| 257 | Triceramon | 34 | 0 | 0 |
| 258 | SaberLeomon | 36 | 0 | 0 |
| 259 | Okuwamon | 18 | 0 | 0 |
| 260 | MetalTyrannomon | 72 | 0 | 0 |
| 261 | Tortomon | 13 | 0 | 0 |
| 262 | Flymon | 67 | 0 | 0 |
| 263 | Mushroomon | 72 | 0 | 0 |
| 264 | Raremon | 59 | 0 | 0 |
| 265 | DarkTyrannomon | 17 | 0 | 0 |
| 266 | ExTyrannomon | 38 | 0 | 0 |
| 267 | Mammothmon | 30 | 0 | 0 |
| 268 | SkullMammothmon | 50 | 0 | 0 |
| 269 | Garbagemon | 78 | 0 | 0 |
| 270 | PrinceMamemon | 64 | 0 | 1 |
| 271 | Plesiomon | 143 | 0 | 0 |
| 272 | Woodmon | 44 | 0 | 0 |
| 273 | Floramon | 86 | 0 | 0 |
| 274 | Blossomon | 8 | 0 | 0 |
| 275 | Scorpiomon | 36 | 0 | 0 |
| 276 | Baihumon | 14 | 0 | 0 |
| 277 | SkullMeramon | 53 | 0 | 0 |
| 278 | Octomon | 6 | 0 | 0 |
| 279 | MarineDevimon | 78 | 0 | 0 |
| 280 | Pumpkinmon | 100 | 0 | 0 |
| 281 | Cyclonemon | 44 | 0 | 0 |
| 282 | Kiwimon | 32 | 0 | 0 |
| 283 | Syakomon | 11 | 0 | 0 |
| 284 | Crabmon | 37 | 0 | 0 |
| 285 | Gazimon | 50 | 0 | 0 |
| 286 | Deramon | 16 | 0 | 0 |
| 287 | Tapirmon | 16 | 0 | 0 |
| 288 | Boltmon | 61 | 0 | 0 |
| 289 | ChaosLord | 35 | 0 | 0 |
| 290 | Clockmon | 40 | 0 | 0 |
| 291 | Dragomon | 45 | 0 | 0 |
| 292 | Deltamon | 39 | 0 | 0 |
| 293 | Gryphonmon | 20 | 0 | 0 |
| 294 | Datamon | 91 | 0 | 0 |
| 295 | Vilemon | 94 | 2 | 47 |
| 296 | Grizzlymon | 63 | 5 | 48 |
| 297 | Marsmon | 143 | 0 | 0 |
| 298 | Dokugumon | 44 | 0 | 0 |
| 299 | Hookmon | 76 | 0 | 0 |
| 300 | SlashAngemon | 139 | 0 | 0 |
| 302 | HiAndromon | 102 | 0 | 0 |
| 303 | KingEtemon | 299 | 0 | 0 |
| 304 | Divermon | 56 | 0 | 0 |
| 305 | Ebidramon | 133 | 0 | 0 |
| 306 | GrapLeomon | 285 | 0 | 0 |
| 307 | BlackKingNumemon | 105 | 0 | 0 |
| 308 | Dinohyumon | 150 | 0 | 0 |
| 309 | Antylamon | 128 | 0 | 0 |
| 310 | Assaultmon | 247 | 0 | 0 |
| 311 | Arukenimon | 193 | 0 | 0 |
| 312 | Creepymon | 273 | 0 | 0 |
| 313 | Bulbmon | 150 | 0 | 0 |
| 314 | SkullSatamon | 337 | 0 | 0 |
| 315 | Taomon | 166 | 0 | 50 |
| 316 | Sakuyamon | 271 | 0 | 0 |
| 317 | Fujinmon | 105 | 0 | 0 |
| 318 | Gallantmon | 219 | 16 | 51 |
| 319 | Pharaohmon | 160 | 2 | 51 |
| 320 | Growlmon | 138 | 0 | 0 |
| 321 | Knightmon | 95 | 0 | 0 |
| 322 | Kyukimon | 124 | 0 | 0 |
| 323 | Lynxmon | 26 | 0 | 0 |
| 324 | Maildramon | 197 | 0 | 0 |
| 325 | Musyamon | 207 | 0 | 0 |
| 326 | WarGrowlmon | 266 | 0 | 0 |
| 327 | Gargoylemon | 104 | 0 | 0 |
| 328 | Snimon | 83 | 0 | 0 |
| 329 | Ghoulmon | 62 | 14 | 51 |
| 330 | Minotarumon | 72 | 0 | 0 |
| 331 | Vemmon | 139 | 0 | 0 |
| 332 | Roachmon | 202 | 0 | 48 |
| 333 | Raijinmon | 181 | 0 | 0 |
| 334 | Mummymon | 250 | 0 | 0 |
| 335 | MegaGargomon | 174 | 0 | 52 |
| 336 | Raidenmon | 57 | 0 | 0 |
| 351 | Kotemon | 70 | 0 | 46 |
| 352 | Monmon | 95 | 0 | 0 |
| 353 | Bearmon | 90 | 0 | 0 |
| 354 | Renamon | 134 | 0 | 0 |
| 373 | WarGreymon | 82 | 0 | 0 |
| 400 | Apocalymon | 122 | 0 | 0 |
| 401 | Pukumon | 31 | 0 | 0 |
| 402 | NeoCrimson | 157 | 0 | 0 |
| 403 | Beelzemon | 213 | 0 | 0 |
| 404 | BlackWarGreymon | 149 | 0 | 0 |
| 405 | Cannondramon | 227 | 0 | 0 |
| 406 | MaloMyotismon | 196 | 0 | 0 |
| 407 | Armageddemon | 220 | 2 | 54 |
| 408 | Suijinmon | 194 | 0 | 0 |
| 409 | Kyubimon | 170 | 4 | 47 |
| 430 | Zanbamon | 190 | 0 | 0 |
| 431 | Kurisarimon | 183 | 240 | 46 |
| 432 | Bastemon | 239 | 0 | 0 |
| 433 | Guilmon | 93 | 0 | 0 |
| 460 | Garudamon | 64 | 0 | 0 |
| 461 | Omnimon | 95 | 0 | 0 |
| 470 | Pabumon | 77 | 0 | 0 |
| 471 | Pichimon | 265 | 16 | 36 |
| 472 | YukimiBotamon | 54 | 0 | 0 |
| 473 | Nyokimon | 0 | 0 | 0 |
| 474 | Motimon | 0 | 2 | 36 |
| 475 | Bukamon | 0 | 2 | 36 |
| 476 | Nyaromon | 129 | 4 | 36 |
| 477 | Yokomon | 93 | 0 | 0 |

## Reproduce

Use developer Python with numpy. Extract final archive models with
`python3 tools/models/meshcheck.py extract BUILD/DIGI.DAT AUDIT_DIR`, then run
`python3 tools/models/meshcheck.py flicker AUDIT_DIR 461 --out omnimon.json`.
For the full sweep, pass every numeric key from
`content/models/imports/models.json` in place of `461` and optionally `--jobs 3`.
`AUDIT_DIR/index.json` supplies the final skeletons. The detector includes every
occupied slot; its 65,536-tick guard fails explicitly. Reports include per-slot
minimum area, collapsed triangle IDs, maximum vertex step, coordinate bound,
minimum transform determinant, ordinary facing-change count and divergent-quad
examples by bone, primitive, view and zero-based decoded tick (first eight
examples plus complete counts). A reported cull change at t means t→t+1.
