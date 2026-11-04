# Constant imported-model proportions

The scale audit covers all 175 source-game imports and 8,661 occupied animation
slots, including aliases, care, conditions and techniques. The threshold is a
peak-to-peak change greater than 2% of the walk reference scale (at least 4096
scale units). It checks decoded engine poses, both within each clip and across
slots. Scale keys encode momentum: inspecting key values as absolute scales gives
incorrect results. Finite programs are decoded to their end, including keys
beyond the animation preview limit; infinite programs are decoded through their
first complete loop. A 65,536-tick guard fails explicitly rather than silently
reporting a partial clip.

Sixty-seven species exceeded the threshold; nine of those only changed scale
between clips. The corrected models have **zero decoded scale variance across
all occupied slots**. The other 108 imports remain unchanged.

Infermon and Armageddemon did not use the chibi pass. Their imported programs
retained scale animation, and some clips initialized different scales. Infermon's
foot scale ranged from 4096 to 11096; its field gait used 10240. Armageddemon's
body scale reached 4301/4506/4301 in slots 42 and 53, compared with 4096 in its
field clips. Reshaping and pace passes retained these source differences; their
constant mesh reshaping and grounding were not the source of the scale keys.

The correction uses the first walking pose's per-bone scales in every program
and removes scale momentum. Empty helper branches without rendered descendants
use unit scale. Changed clips use the existing foot-aware grounding solver;
reviewed anatomical foot groups take precedence over walking contact candidates.
The measured standing-foot error is at most 0.5 model units. Lying poses can rest
on another part, and jumps and hovers keep their source clearance. This is not a
new terrain or horizontal foot-IK system.

The final reviewed field model, including its effective skeleton and attached
effect offsets, is baked into the plain model delta with `tools/models/edit.py
put`. Its old live field overlay is retired to avoid applying reshaping or pace
twice. The preceding provider binding, old record fields, reference scales,
source/result hashes, support pieces and storage measurements are retained in
[`content/modeldelta/scale-locks/`](../../content/modeldelta/scale-locks/).
The original field generators and their manifests remain available as authoring
references. Subsequent `edit.py get` calls return the final reviewed model.

Infermon uses Bakemon's battle bank 33 and care bank 0. Battle notes 53, 54 and 55
are all present. Its old Monochromon footstep events now select the native
Kabuterimon/Kuwagamon footstep (bank 1, note 16), at the same contact ticks.

Audit a full derive output, or an authoring folder containing `ID.MMD` and its
effective `ID.json` species record:

```sh
python3 tools/models/scale_lock.py audit --from build/everything --out build/scales.json
python3 tools/models/scale_lock.py audit --models build/scale-review/final --out build/scales.json
python3 tools/models/scale_lock.py bake INPUT.MMD EFFECTIVE.json OUTPUT.MMD --feet BONE ...
python3 tools/models/edit.py --from build/everything put ID OUTPUT.MMD
python3 tools/models/edit.py --from build/everything check ID --species-pins
PYTHONPATH=tools python3 -m unittest tools.test_scale_lock tools.test_chibi tools.test_motionstorage tools.test_model_provider
```

Every changed species passes source, delta, target and provider pins and the
100352-byte resident / 8192-byte sector-aligned cold-read limits. There are no C
or executable-buffer changes. The tightest resident model is Monmon at 99948
bytes. Each species has its own commit.

| ID | Species corrected | Slots with animated scale before | Resident bytes after |
|---|---|---|---|
| 183 | Wormmon | 0, 33, 42, 46, 47, 50, 51, 52, 53 | 80480 |
| 185 | Armadillomon | 42 | 82316 |
| 189 | Ankylomon | 56 | 89582 |
| 193 | Digmon | 47, 50, 51, 55, 57 | 84456 |
| 205 | MegaKabuterimon | 42 | 84242 |
| 206 | MagnaAngemon | 40, 41, 42, 43, 49, 50, 58 | 83238 |
| 208 | Togemon | 40, 41, 43 | 66490 |
| 217 | Gomamon | 42 | 91078 |
| 219 | Zudomon | 52, 53 | 98586 |
| 220 | Vikemon | Between clips only | 99732 |
| 223 | LadyDevimon | 40, 41, 52, 53 | 77810 |
| 225 | Shurimon | 40, 41, 42, 47, 48, 49, 55, 56 | 87164 |
| 227 | Apemon | 60 | 88358 |
| 229 | Phantomon | 42 | 61814 |
| 231 | ShellNumemon | 0, 2, 3, 4, 33, 40, 41, 42, 43, 58 | 69420 |
| 232 | BomberNanimon | 42, 56 | 85110 |
| 235 | Candlemon | 0, 1, 2, 3, 4, 18, 33, 42, 43 | 73852 |
| 243 | Starmon | 42, 43 | 82382 |
| 244 | SuperStarmon | 42, 43 | 76972 |
| 245 | Piedmon | 42 | 78336 |
| 246 | Infermon | 33, 40, 41, 43, 56, 57 | 97706 |
| 248 | MarineAngemon | 33, 34, 35, 36, 40, 41, 42, 43, 47, 48, 53, 58 | 86038 |
| 250 | Shadramon | 52, 57 | 90264 |
| 252 | Thundermon | 40, 41, 43 | 63290 |
| 253 | Tuskmon | 0, 33, 42 | 83384 |
| 256 | VioletElecmon | 51, 52, 54 | 72560 |
| 260 | MetalTyrannomon | Between clips only | 91758 |
| 261 | Tortomon | 40, 41, 44 | 72320 |
| 264 | Raremon | 0, 2, 3, 4, 33, 40, 41, 43, 44, 46, 47, 48, 49, 50, 51, 56, 58, 59 | 84610 |
| 265 | DarkTyrannomon | 55 | 92030 |
| 266 | ExTyrannomon | 0, 33, 44, 46, 47, 49, 50, 51, 52, 53, 55, 56 | 58512 |
| 267 | Mammothmon | 40, 41, 43, 53, 54, 56, 57 | 76340 |
| 268 | SkullMammothmon | 40, 41, 43, 47, 51, 54, 56, 57, 58, 59 | 83048 |
| 269 | Garbagemon | 43, 44 | 78208 |
| 270 | PrinceMamemon | 0, 33, 43, 47, 49, 50, 51, 52, 53, 54, 55, 56, 57, 58, 59, 60, 61 | 66808 |
| 271 | Plesiomon | Between clips only | 95922 |
| 274 | Blossomon | 0, 1, 18, 33, 44, 51 | 76438 |
| 278 | Octomon | 43, 44 | 90610 |
| 279 | MarineDevimon | 47, 51, 53 | 82896 |
| 280 | Pumpkinmon | 47, 48, 51, 53, 59 | 63378 |
| 281 | Cyclonemon | Between clips only | 95296 |
| 283 | Syakomon | 44, 47, 48, 51, 52, 55, 56 | 30038 |
| 286 | Deramon | 43, 44, 50, 51, 54, 56, 57, 58, 60 | 43174 |
| 287 | Tapirmon | 43, 44, 57 | 76716 |
| 288 | Boltmon | 0, 33 | 84954 |
| 291 | Dragomon | 47, 49, 50, 52, 59 | 81892 |
| 292 | Deltamon | 48 | 81250 |
| 294 | Datamon | 43, 44 | 74092 |
| 298 | Dokugumon | 0, 33, 40, 41, 52, 60 | 90860 |
| 300 | SlashAngemon | Between clips only | 83934 |
| 307 | BlackKingNumemon | 0, 1, 2, 3, 4, 18, 33, 40, 41, 46, 47, 48, 49, 50, 51, 52, 53, 60, 62 | 90728 |
| 313 | Bulbmon | 53 | 72498 |
| 317 | Fujinmon | 60 | 75634 |
| 318 | Gallantmon | Between clips only | 86858 |
| 320 | Growlmon | Between clips only | 84704 |
| 325 | Musyamon | 43, 44 | 84540 |
| 332 | Roachmon | 58 | 88828 |
| 352 | Monmon | 0, 1, 2, 3, 4, 18, 33 | 99948 |
| 353 | Bearmon | 0, 33, 46, 47, 48, 49, 51, 54, 55 | 74200 |
| 400 | Apocalymon | 42, 52, 53, 54 | 95466 |
| 401 | Pukumon | 0, 33, 40, 41, 43, 44, 54, 55, 56, 57, 58, 59, 60, 61 | 56510 |
| 402 | NeoCrimson | Between clips only | 76156 |
| 403 | Beelzemon | 53, 60 | 99464 |
| 404 | BlackWarGreymon | Between clips only | 86584 |
| 406 | MaloMyotismon | 54, 61 | 84492 |
| 407 | Armageddemon | 42, 53 | 73070 |
| 461 | Omnimon | 42, 43 | 80298 |
