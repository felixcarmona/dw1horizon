# Buster Dive reach audit

Buster Dive (47) is a ranged AI technique with a squared distance of 360000.
The AI launch band is `sqrt(0.7 * (360000 + (attackerRadius + targetRadius)^2))`
through `sqrt(1.3 * (360000 + (attackerRadius + targetRadius)^2))`.
Its EFE script tests a line between the attacker and its species effect origin
during effect frames 23–33. It does not launch a free-moving projectile.

Omnimon (461) has radius 204 and height 500. Its original shared attack clip
lunges only 123 units, mostly before the hit window; the remaining forward
travel during the window is about 2 units. After the field size pass, the
peak is only 112 units. With effects type 5 absent from
Buster Dive’s native table, the entity-origin fallback borrows the launch point
of a native user close in radius. That point and the target’s collision radius
can cover a close target, but cannot compensate for the missing dash at the
outer part of the AI launch band. Smaller targets expose the shortage.

Native reference clips from the DW1 disc:

| User | Radius | Peak forward travel |
|---|---:|---:|
| Tyrannomon (8) | 230 | 550 |
| MetalGreymonVirus (12) | 280 | 600 |
| Mamemon (13) | 100 | 800 |
| Patamon (31) | 130 | 820 |
| Gotsumon (68) | 110 | 800 |

The repair gives the affected Buster Dive slot Patamon’s native entity motion:
about 820 units forward at the peak, settling at 700. The ordinary repair
preserves every body-pose sample and animation event; the three compact
exceptions below use reviewed body-pose selections. Short clips hold their last pose until
the dash finishes. Shared punches, finishers and field slots retain their
original programs. Technique range, power, accuracy, MP cost, collision radii
and effect origins keep their existing values.

The imported-species provider runs `tools/models/buster_dive.py` after slot
aliases and the reviewed field overlays, before the model is packed into
DIGI.DAT. This order keeps body-size passes from shortening the repaired dash.
The native motion is read from the player's own DW1 disc. Existing model
deltas and field-animation source pins remain unchanged.

A separate attack program needs resident model space. The packer discards
unreachable bytes after animation terminators and shares identical live
programs. These bytes can include old clips overwritten by slot aliases.
Every live program's pose samples and events are preserved. The existing
resident and cold buffers and streaming policy remain unchanged.

The historical base-model audit checked 70 imported users with aliases applied.
Nine already had enough travel; 57 short clips received the native track. Four
candidates originally exceeded the fixed resident buffer. Infermon and Datamon
no longer learn Buster Dive, leaving 68 current imported users.

The remaining three tight models — Zudomon (219), Diaboromon (237) and
Beelzemon (403) — now use reviewed compact body clips selected by
`buster_dive_clip` in the imports JSON registry. Each recipe pins its source
program and chooses a few source poses for wind-up, charge and recovery.
Diaboromon holds its charge pose through the end, then uses the ordinary idle
transition. Body channels interpolate within one encoded unit; the root track
is copied exactly from the native dash. Sound and texture events follow the
selected pose progression. Only the Buster Dive slot changes.

Their resident sizes are 99524, 100304 and 99634 bytes respectively, below the
unchanged 100352-byte limit. Streamed reads retain the 8192-byte limit. A
configured recipe that exceeds either buffer stops the build. Runtime tests
must leave a clear attack corridor: the tamer is a real physical obstacle and
can block a native dash. The playtest's `--clear-path` moves the tamer aside
without disabling map or entity collision.

The table records the base-model audit before field scaling and measures forward travel from animation sample 23 through sample 34;
runtime effect timing can differ by one tick from the animation counter.

| Species | Radius | Original active-window travel | Repair |
|---|---:|---:|---|
| 181 Puppetmon | 160 | 0 | Native dash |
| 182 Kimeramon | 175 | 381 | Native dash |
| 190 Angewomon | 223 | 0 | Native dash |
| 197 Magnamon | 131 | 89 | Native dash |
| 199 Paildramon | 256 | 0 | Native dash |
| 202 Submarimon | 241 | 0 | Native dash |
| 206 MagnaAngemon | 187 | 0 | Native dash |
| 209 Lillymon | 156 | 0 | Native dash |
| 210 GranKuwagamon | 292 | 0 | Native dash |
| 212 VenomMyotismon | 260 | 0 | Native dash |
| 213 AeroVeedramon | 260 | 0 | Native dash |
| 219 Zudomon | 293 | 0 | Compact native dash |
| 220 Vikemon | 206 | 0 | Native dash |
| 223 LadyDevimon | 197 | 0 | Native dash |
| 226 Silphymon | 189 | 0 | Native dash |
| 237 Diaboromon | 246 | 0 | Compact native dash |
| 244 SuperStarmon | 290 | 6 | Native dash |
| 245 Piedmon | 145 | 0 | Native dash |
| 246 Infermon | 280 | 0 | Historical: no longer learns the move |
| 248 MarineAngemon | 183 | 0 | Native dash |
| 255 Valkyrimon | 211 | 0 | Native dash |
| 257 Triceramon | 259 | 424 | Native dash |
| 258 SaberLeomon | 237 | 0 | Native dash |
| 259 Okuwamon | 280 | 0 | Native dash |
| 266 ExTyrannomon | 127 | 0 | Native dash |
| 267 Mammothmon | 300 | 0 | Native dash |
| 268 SkullMammothmon | 291 | 0 | Native dash |
| 270 PrinceMamemon | 187 | 0 | Native dash |
| 274 Blossomon | 144 | 0 | Native dash |
| 275 Scorpiomon | 300 | 0 | Native dash |
| 276 Baihumon | 300 | 1428 | Existing dash |
| 277 SkullMeramon | 142 | 1019 | Existing dash |
| 279 MarineDevimon | 245 | 0 | Native dash |
| 280 Pumpkinmon | 146 | 0 | Native dash |
| 286 Deramon | 194 | 260 | Native dash |
| 288 Boltmon | 136 | 977 | Existing dash |
| 289 ChaosLord | 300 | 461 | Native dash |
| 291 Dragomon | 151 | 0 | Native dash |
| 293 Gryphonmon | 300 | 0 | Native dash |
| 294 Datamon | 180 | 0 | Historical: no longer learns the move |
| 297 Marsmon | 156 | 0 | Native dash |
| 300 SlashAngemon | 139 | 0 | Native dash |
| 302 HiAndromon | 145 | 1041 | Existing dash |
| 303 KingEtemon | 140 | 0 | Native dash |
| 304 Divermon | 159 | 0 | Native dash |
| 306 GrapLeomon | 136 | 0 | Native dash |
| 307 BlackKingNumemon | 242 | 1214 | Existing dash |
| 309 Antylamon | 161 | 1158 | Existing dash |
| 310 Assaultmon | 233 | 0 | Native dash |
| 311 Arukenimon | 183 | 0 | Native dash |
| 312 Creepymon | 149 | 0 | Native dash |
| 314 SkullSatamon | 122 | 0 | Native dash |
| 318 Gallantmon | 300 | 580 | Existing dash |
| 319 Pharaohmon | 150 | 0 | Native dash |
| 321 Knightmon | 279 | 0 | Native dash |
| 322 Kyukimon | 300 | 0 | Native dash |
| 329 Ghoulmon | 252 | 2 | Native dash |
| 334 Mummymon | 135 | 974 | Existing dash |
| 335 MegaGargomon | 183 | 0 | Native dash |
| 373 WarGreymon | 230 | 0 | Native dash |
| 400 Apocalymon | 217 | 0 | Native dash |
| 401 Pukumon | 100 | 0 | Native dash |
| 402 NeoCrimson | 227 | 0 | Native dash |
| 403 Beelzemon | 215 | 0 | Compact native dash |
| 404 BlackWarGreymon | 133 | 487 | Native dash |
| 406 MaloMyotismon | 216 | 629 | Existing dash |
| 407 Armageddemon | 300 | 0 | Native dash |
| 430 Zanbamon | 228 | 0 | Native dash |
| 432 Bastemon | 147 | 0 | Native dash |
| 461 Omnimon | 204 | 2 | Native dash |

The EFE line-hit handler is also used by melee punches, claws and kicks,
including Megaton Punch (46). Those use range class 1 and approach to the
sum of collision radii before attacking. Buster Dive is the only range-class-2
technique using this handler. Drill Spin (75) and Aerial Attack (84) have
different effect logic and do not depend on this same long melee dash.

Validation: `python3 -m unittest tools.test_buster_dive` checks a shared short
attack and a longer recovery, including exact body samples, other slots and
sound events. The full nine-language build checks the packed models and 2 MB
heap budget. In-game evidence and limitations are recorded in the task report.
