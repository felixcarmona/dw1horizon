# Signature attacks: where each one comes from

Every imported Digimon has a finisher of its own, named and designed after the signature attack of the game it
comes from. None of them plays the source game's effect: all 179 play an effect written for this game
([the finishers written here](#finishers-written-here)). This page keeps the record of the source attacks: what each
did in its game, and how the port of it played when the ports were still the effects in the battle. How those
ports were made is in [the signature effects notes](../mods/signature-effects.md); the DW2 effect format is in
[the DW2 effect notes](dw2-effects.md), and the DW2003 one in [the DW2003 effect notes](dw3-effects.md).

The damage, the element, the cost and when the Digimon chooses the attack are the finisher's, as in
[the unique finishers](../mods/unique-finishers.md). Times are battle ticks (20 a second) from the moment the
attack starts.

## The source attacks and their ports (history)

The table describes the converted and composed ports that were played before the finishers were written here. No
species plays them now. The "Target here" column is what the port did, not what the game does today.

| Species | Attack (source game) | Stands in for | Kind | Hits | Launch / hit | Travel | Target here | Target in the source |
|---|---|---|---|---|---|---|---|---|
| 277 SkullMeramon | Metal Fireball (DW2) | Mega Flame | projectile: a flaming metal ball with a fire ring | 1 | flies at tick 29, hits on contact, up to tick 36 | flies straight at the target up to 1,100 units; the DW2 flight, scaled by 0.266 (its size here against its DW2 size), is cut where it would pass the target | one enemy, the first its path touches | all enemies (one ball each) |
| 264 Raremon | Buffalo Breath (DW2) | Death Claw | projectile: a breath ball with a ring | 1 | flies at tick 29, hits on contact, up to tick 36 | as Metal Fireball (scale 0.269) | one enemy, the first its path touches | one enemy |
| 122 Hagurumon | Darkness Gear (DW2) | Electric Shock | projectile: fires a black gear that spins into the target | 1 | flies at tick 29, hits on contact (tick 39 at 2,700 units) | flies to the target (scale 0.166) | one enemy, as for Electric Shock | one enemy |
| 182 Kimeramon | Poison Wing (DW2) | Mega Flame | projectile: a heat blast from the wings | 1 | flies at tick 3, hits on contact (tick 39 at 2,700 units) | flies to the target (scale 0.326) | one enemy, as for Mega Flame | one enemy |
| 257 Triceramon | Tri-Horn Attack (DW2) | Bit Bomb | at the target: charges horns first | 1 | plays at the target, hits at tick 40 | none (scale 0.307) | the enemy it was aimed at (Bit Bomb picks one at random) | one enemy |
| 258 SaberLeomon | Howling Crusher (DW2) | Death Claw | at the target: a claw strike from a leap | 1 | plays at the target, hits at tick 40 | none (scale 0.359) | one enemy, as for Death Claw | one enemy |
| 259 Okuwamon | Duo Scissor Claw (DW2) | Bit Bomb | at the target: two crossing slash arcs over every enemy | 1 | plays at the target, hits at tick 40 | none (scale 0.3) | the enemy it was aimed at (Bit Bomb picks one at random) | all enemies, 2 hits |
| 260 MetalTyrannomon | Fire Blast II (DW2) | Deadly Bomb | projectile: fires an organic missile from the arm | 1 | flies at tick 37, hits on contact (tick 38 at 2,700 units) | flies to the target (scale 0.205) | one enemy, as for Deadly Bomb | one enemy |
| 261 Tortomon | Strong Carapace (DW2) | Iga School Knife Throw | projectile: shoots the horns of its shell at every enemy | 1 | flies at tick 29, hits on contact (tick 39 at 2,700 units) | flies to the target (scale 0.241) | one enemy, as for Iga School Knife Throw | all enemies, 3 hits |
| 262 Flymon | Brown Stinger (DW2) | Spnning Needle | projectile: shoots poisoned needles | 1 | flies at tick 30, hits on contact (tick 39 at 2,700 units) | flies to the target (scale 0.31) | one enemy, as for Spnning Needle | one enemy, 3 hits |
| 265 DarkTyrannomon | Fire Blast (DW2) | Nightmare Syndromer | at the target: sweeps a stream of flame over every enemy | 1 | plays at the target, hits at tick 40 | none (scale 0.246) | one enemy, as for Nightmare Syndromer | all enemies |
| 266 ExTyrannomon | Pretty Attack (DW2) | Lovely Attack | projectile: blows a heart kiss | 1 | flies at tick 20, hits on contact (tick 39 at 2,700 units) | flies to the target (scale 0.287) | one enemy, as for Lovely Attack | one enemy |
| 267 Mammothmon | Tusk Crusher (DW2) | Mail Strome | at the target: charges tusks first | 1 | plays at the target, hits at tick 40 | none (scale 0.294) | one enemy, as for Mail Strome | one enemy |
| 268 SkullMammothmon | S-Bone Crusher (DW2) | Mail Strome | projectile: a spinning bone hits every enemy | 1 | flies at tick 30, hits on contact (tick 39 at 2,700 units) | flies to the target (scale 0.256) | one enemy, as for Mail Strome | all enemies |
| 269 Garbagemon | Junk Chunker (DW2) | Energy Bomb | projectile: throws junk from its can | 1 | flies at tick 20, hits on contact (tick 39 at 2,700 units) | flies to the target (scale 0.267) | one enemy, as for Energy Bomb | one enemy, 3 hits |
| 270 PrinceMamemon | Smiley Warhead (DW2) | Smiley Bomb | at the target: a smiling warhead | 1 | plays at the target, hits at tick 40 | none (scale 0.288) | one enemy, as for Smiley Bomb | one enemy |
| 271 Plesiomon | Sad Water Blast (DW2) | Mail Strome | at the target: a sad song and a wave of water over every enemy | 1 | plays at the target, hits at tick 40 | none (scale 0.249) | one enemy, as for Mail Strome | all enemies |
| 272 Woodmon | Twig Tap (DW2) | Sweet Breath | at the target: two swipes with its twig arms | 1 | plays at the target, hits at tick 40 | none (scale 0.198) | one enemy, as for Sweet Breath | one enemy, 2 hits |
| 273 Floramon | Rain of Pollen (DW2) | Poison Ivy | at the target: blows a cloud of pollen at the target | 1 | plays at the target, hits at tick 40 | none (scale 0.194) | one enemy, as for Poison Ivy | one enemy |
| 274 Blossomon | Ninja Flower (DW2) | Sweet Breath | volley: flower shuriken over every enemy | 1 | flies at tick 30, hits on contact (tick 39 at 2,700 units) | flies to the target (scale 0.238) | one enemy, as for Sweet Breath | all enemies, 4 hits |
| 275 Scorpiomon | Tail Blade (DW2) | Mail Strome | projectile: lunges with its tail blade | 1 | flies at tick 27, hits on contact (tick 39 at 2,700 units) | flies to the target (scale 0.311) | one enemy, as for Mail Strome | one enemy |
| 278 Octomon | Spurting Ink (DW2) | Hydro Pressure | projectile: fires black ink shots | 1 | flies at tick 30, hits on contact (tick 39 at 2,700 units) | flies to the target (scale 0.284) | one enemy, as for Hydro Pressure | one enemy, 3 hits |
| 279 MarineDevimon | Evil Wind (DW2) | Death Claw | projectile: a dark gust over every enemy | 1 | flies at tick 29, hits on contact (tick 39 at 2,700 units) | flies to the target (scale 0.182) | one enemy, as for Death Claw | all enemies |
| 280 Pumpkinmon | Trick or Treat (DW2) | Fireball | projectile: pumpkin bombs over every enemy | 1 | flies at tick 20, hits on contact (tick 39 at 2,700 units) | flies to the target (scale 0.329) | one enemy, as for Fireball | all enemies |
| 281 Cyclonemon | Hyper Heat (DW2) | Fireball | at the target: a super-hot blast from its arm | 1 | plays at the target, hits at tick 40 | none (scale 0.209) | one enemy, as for Fireball | one enemy |
| 282 Kiwimon | Pummel Peck (DW2) | Sweet Breath | volley: sends a mini Kiwimon running at the target | 1 | flies at tick 29, hits on contact (tick 39 at 2,700 units) | flies to the target (scale 0.203) | one enemy, as for Sweet Breath | one enemy |
| 283 Syakomon | Pearl Shot (DW2) | Blasting Spout | projectile: fires a pearl from its shell | 1 | flies at tick 29, hits on contact (tick 39 at 2,700 units) | flies to the target (scale 0.179) | one enemy, as for Blasting Spout | one enemy |
| 284 Crabmon | Scissor Magic (DW2) | Scissor Claw | at the target: a double snip of the claws | 1 | plays at the target, hits at tick 40 | none (scale 0.391) | one enemy, as for Scissor Claw | one enemy, 2 hits |
| 285 Gazimon | E-Stun Blast (DW2) | Poison Ivy | projectile: an electric blast from the mouth | 1 | flies at tick 29, hits on contact (tick 39 at 2,700 units) | flies to the target (scale 0.218) | one enemy, as for Poison Ivy | one enemy |
| 286 Deramon | Royal Smasher (DW2) | Fist of the Beast King | projectile: fires an egg like a shell | 1 | flies at tick 29, hits on contact (tick 39 at 2,700 units) | flies to the target (scale 0.274) | one enemy, as for Fist of the Beast King | one enemy |
| 287 Tapirmon | Waking Dream (DW2) | Solar Ray | at the target: a cloud of nightmare smoke | 1 | plays at the target, hits at tick 40 | none (scale 0.201) | one enemy, as for Solar Ray | one enemy |
| 288 Boltmon | Tomahawk Crunch (DW2) | Giga Scissor Claw | projectile: throws axes at every enemy | 1 | flies at tick 29, hits on contact (tick 39 at 2,700 units) | flies to the target (scale 0.258) | one enemy, as for Giga Scissor Claw | all enemies, 2 hits |
| 289 ChaosLord | Chaos Cannon (DW2) | Energy Bomb | volley: a cannon blast that bursts over the field | 1 | flies at tick 30, hits on contact (tick 39 at 2,700 units) | flies to the target (scale 0.257) | one enemy, as for Energy Bomb | all enemies |
| 290 Clockmon | Chrono Breaker (DW2) | Genoside Attack | at the target: a clock-hand ripple that freezes time | 1 | plays at the target, hits at tick 40 | none (scale 0.244) | one enemy, as for Genoside Attack | anyone (random) |
| 291 Dragomon | Tentacle Claw (DW2) | Mail Strome | projectile: throws its trident | 1 | flies at tick 29, hits on contact (tick 39 at 2,700 units) | flies to the target (scale 0.295) | one enemy, as for Mail Strome | one enemy |
| 292 Deltamon | Triple Forces (DW2) | Mega Flame | projectile: energy bursts from all three heads | 1 | flies at tick 29, hits on contact (tick 39 at 2,700 units) | flies to the target (scale 0.268) | one enemy, as for Mega Flame | all enemies, 3 hits |
| 293 Gryphonmon | Legendary Blade (DW2) | Death Claw | at the target: a sonic blade over every enemy | 1 | plays at the target, hits at tick 40 | none (scale 0.282) | one enemy, as for Death Claw | all enemies |
| 294 Datamon | Digital Bomb (DW2) | Smiley Bomb | projectile: small bombs on every enemy | 1 | flies at tick 21, hits on contact (tick 38 at 2,700 units) | flies to the target (scale 0.184) | one enemy, as for Smiley Bomb | all enemies, 4 hits |
| 401 Pukumon | Needle Squall (DW2) | Mail Strome | volley: spines in every direction | 1 | flies at tick 30, hits on contact (tick 39 at 2,700 units) | flies to the target (scale 0.235) | one enemy, as for Mail Strome | all enemies, 6 hits |
| 402 NeoCrimson | Blind Attack (DW2) | Crimson Flare | at the target: a blind charge at a random fighter | 1 | plays at the target, hits at tick 40 | none (scale 0.187) | one enemy, as for Crimson Flare | one enemy (random) |
| 295 Vilemon | Dark Fear (DW2003) | Death Claw | 3D effect at the caster (MEFT0335) | 1 | plays its whole length (31 frames at 30 fps), hits when it ends | none | one enemy, as for Death Claw | one enemy |
| 297 Marsmon | Mugenhadou (DW2003) | Mega Flame | 3D effect at the caster (MEFT0097) | 1 | plays its whole length (31 frames at 30 fps), hits when it ends | none | one enemy, as for Mega Flame | one enemy |
| 298 Dokugumon | Poison Cobweb (DW2003) | Bit Bomb | 3D effect at the caster (MEFT0328) | 1 | plays its whole length (31 frames at 30 fps), hits when it ends | none | one enemy, as for Bit Bomb | one enemy |
| 299 Hookmon | Captain Cannon (DW2003) | Dark Shot | 3D effect at the caster (MEFT0091) | 1 | plays its whole length (46 frames at 30 fps), hits when it ends | none | one enemy, as for Dark Shot | one enemy |
| 300 SlashAngemon | Golden Ripper (DW2003) | Death Claw | 3D effect at the caster (MEFT0100) | 1 | plays its whole length (51 frames at 30 fps), hits when it ends | none | one enemy, as for Death Claw | one enemy |
| 302 HiAndromon | Atomic Ray (DW2003) | Spiral Sword | 3D effect at the caster (MEFT0361) | 1 | plays its whole length (46 frames at 30 fps), hits when it ends | none | one enemy, as for Spiral Sword | one enemy |
| 303 KingEtemon | Dark Spirits DX (DW2003) | Dark Network & Concert Crush | 3D effect at the caster (MEFT0324) | 1 | plays its whole length (31 frames at 30 fps), hits when it ends | none | one enemy, as for Dark Network & Concert Crush | all enemies |
| 310 Assaultmon | Justice Strike (DW2003) | Genoside Attack | 3D effect at the caster (MEFT0093) | 1 | plays its whole length (56 frames at 30 fps), hits when it ends | none | one enemy, as for Genoside Attack | one enemy, 3 hits |
| 312 Creepymon | Darkness Chaos (DW2003) | Nightmare Syndromer | 3D effect at the caster (MEFT0351) | 1 | plays its whole length (36 frames at 30 fps), hits when it ends | none | one enemy, as for Nightmare Syndromer | all enemies |
| 313 Bulbmon | Mad Pump (DW2003) | Dark Shot | 3D effect at the caster (MEFT0346) | 1 | plays its whole length (38 frames at 30 fps), hits when it ends | none | one enemy, as for Dark Shot | one enemy |
| 317 Fujinmon | Sylph Storm (DW2003) | Spiral Sword | 3D effect at the caster (MEFT0370) | 1 | plays its whole length (38 frames at 30 fps), hits when it ends | none | one enemy, as for Spiral Sword | all enemies |
| 323 Lynxmon | Blazing Mane (DW2003) | Crimson Flare | 3D effect at the caster (MEFT0332) | 1 | plays its whole length (36 frames at 30 fps), hits when it ends | none | one enemy, as for Crimson Flare | one enemy |
| 329 Ghoulmon | Darkness Chaos (DW2003) | Dark Shot | 3D effect at the caster (MEFT0349) | 1 | plays its whole length (38 frames at 30 fps), hits when it ends | none | one enemy, as for Dark Shot | one enemy |
| 333 Raijinmon | Electro Ball (DW2003) | Genoside Attack | 3D effect at the caster (MEFT0363) | 1 | plays its whole length (41 frames at 30 fps), hits when it ends | none | one enemy, as for Genoside Attack | all enemies |
| 334 Mummymon | Dark Fear (DW2003) | Dark Shot | 3D effect at the caster (MEFT0335) | 1 | plays its whole length (31 frames at 30 fps), hits when it ends | none | one enemy, as for Dark Shot | one enemy |
| 335 MegaGargomon | Giant Missile (DW2003) | Genoside Attack | 3D effect at the caster (MEFT0085) | 1 | plays its whole length (35 frames at 30 fps), hits when it ends | none | one enemy, as for Genoside Attack | one enemy |
| 352 Monmon | Swing Swing (DW2003) | Boom Bubble | 3D effect at the caster (MEFT0089) | 1 | plays its whole length (46 frames at 30 fps), hits when it ends | none | one enemy, as for Boom Bubble | one enemy |
| 405 Cannondramon | DynamoCannon (DW2003) | Genoside Attack | 3D effect at the caster (MEFT0094) | 1 | plays its whole length (58 frames at 30 fps), hits when it ends | none | one enemy, as for Genoside Attack | one enemy |
| 406 MaloMyotismon | Melting Blood (DW2003) | Nightmare Syndromer | 3D effect at the caster (MEFT0092) | 1 | plays its whole length (69 frames at 30 fps), hits when it ends | none | one enemy, as for Nightmare Syndromer | one enemy |
| 407 Armageddemon | Ultimate Flare (DW2003) | Crimson Flare | 3D effect at the caster (MEFT0333) | 1 | plays its whole length (61 frames at 30 fps), hits when it ends | none | one enemy, as for Crimson Flare | one enemy |
| 408 Suijinmon | Mugen Cannon (DW2003) | Infinity Cannon | 3D effect at the caster (MEFT0364) | 1 | plays its whole length (51 frames at 30 fps), hits when it ends | none | one enemy, as for Infinity Cannon | one enemy, 4 hits |
| 430 Zanbamon | Cross Slash (DW2003) | Death Claw | 3D effect at the caster (MEFT0039) | 1 | plays its whole length (30 frames at 30 fps), hits when it ends | none | one enemy, as for Death Claw | one enemy |
| 304 Divermon | Striking Fish (DW2003) | Bone Boomerang | sprites at the caster as flat quads (E000COM1 #2) | 1 | plays its whole length (6 frames at 30 fps), hits when it ends | none | one enemy, as for Bone Boomerang | one enemy |
| 305 Ebidramon | Pincer Crusher (DW2003) | Scissor Claw | sprites at the caster as flat quads (E000COM1 #2, E000COM3 #9) | 1 | plays its whole length (33 frames at 30 fps), hits when it ends | none | one enemy, as for Scissor Claw | one enemy |
| 308 Dinohyumon | Lizard Dance (DW2003) | Scissor Claw | sprites at the caster as flat quads (E000COM1 #2, E386DINO #2021, E386DINO #2022, E386DINO #2023) | 1 | plays its whole length (77 frames at 30 fps), hits when it ends | none | one enemy, as for Scissor Claw | one enemy, 4 hits |
| 321 Knightmon | Berserk Sword (DW2003) | Spiral Sword | sprites at the caster as flat quads (E000COM1 #2) | 1 | plays its whole length (6 frames at 30 fps), hits when it ends | none | one enemy, as for Spiral Sword | one enemy |
| 324 Maildramon | Thunder Bolt (DW2003) | Death Claw | sprites at the caster as flat quads (E000COM1 #2, E000COM2 #64, E438RIDN #1011) | 1 | plays its whole length (68 frames at 30 fps), hits when it ends | none | one enemy, as for Death Claw | one enemy |
| 325 Musyamon | Ura Sword (DW2003) | Death Claw | sprites at the caster as flat quads (E000COM1 #2, E000COM3 #7) | 1 | plays its whole length (31 frames at 30 fps), hits when it ends | none | one enemy, as for Death Claw | one enemy |
| 328 Snimon | Twin Sickles (DW2003) | Bit Bomb | sprites at the caster as flat quads (E000COM1 #2) | 1 | plays its whole length (6 frames at 30 fps), hits when it ends | none | one enemy, as for Bit Bomb | one enemy |
| 330 Minotarumon | Darkside Quake (DW2003) | Pummel Whack | sprites at the caster as flat quads (E000COM1 #2) | 1 | plays its whole length (6 frames at 30 fps), hits when it ends | none | one enemy, as for Pummel Whack | all enemies |
| 332 Roachmon | Roach Rush (DW2003) | Electro Shocker | sprites at the caster as flat quads (E000COM1 #2, E000COM3 #7) | 1 | plays its whole length (36 frames at 30 fps), hits when it ends | none | one enemy, as for Electro Shocker | one enemy |
| 351 Kotemon | Hot Head (DW2003) | Blue Blaster | sprites at the caster as flat quads (E000COM1 #0, E000COM1 #2, E000COM3 #4, E383PKEN #2003) | 1 | plays its whole length (47 frames at 30 fps), hits when it ends | none | one enemy, as for Blue Blaster | one enemy |
| 353 Bearmon | Bear Fist (DW2003) | Super Slap | sprites at the caster as flat quads (E000COM1 #0, E145VMON #2014) | 1 | plays its whole length (10 frames at 30 fps), hits when it ends | none | one enemy, as for Super Slap | one enemy |
| 224 MetalGreymonVaccine | Trident Arm (composed) | Giga Scissor Claw | Giga Scissor Claw's play in steel blue, its fireballs read as cold metal | as Giga Scissor Claw | as Giga Scissor Claw | as Giga Scissor Claw | as Giga Scissor Claw | - |
| 309 Antylamon | Bunny Blades (composed) | Death Claw | Death Claw's ring and slashes in orange, a little smaller | as Death Claw | as Death Claw | as Death Claw | as Death Claw | - |
| 319 Pharaohmon | Pyramid Power (composed) | Bit Bomb | Bit Bomb's play in gold: gold-plated head, golden star bursts, 1.2 times larger | as Bit Bomb | as Bit Bomb | as Bit Bomb | as Bit Bomb | - |
| 431 Kurisarimon | Data Crusher (composed) | Bit Bomb | Bit Bomb's play in cyan, its bomb sprites and blast drawn as columns of binary digits | as Bit Bomb | as Bit Bomb | as Bit Bomb | as Bit Bomb | - |
| 311 Arukenimon | Spirit Needle (composed) | Bit Bomb | Bit Bomb's play with its projectile drawn as a thin violet-white needle and its burst as sharp violet sparkles | as Bit Bomb | as Bit Bomb | as Bit Bomb | as Bit Bomb | - |
| 336 Raidenmon | Raiden Strike (composed) | Fireball | Fireball's play with its fireballs drawn as crackling amber-gold lightning | as Fireball | as Fireball | as Fireball | as Fireball | - |
| 432 Bastemon | Cat Laser (composed) | Death Claw | Death Claw's play in green, its ring squeezed into a long thin laser beam | as Death Claw | as Death Claw | as Death Claw | as Death Claw | - |
| 331 Vemmon | Vemmon Crash (composed) | Scissor Claw | Scissor Claw's play as a heavy orange shock ring, 1.6 times larger | as Scissor Claw | as Scissor Claw | as Scissor Claw | as Scissor Claw | - |
| 314 SkullSatamon | Nail Bone (composed) | Nightmare Syndromer | Nightmare Syndromer's play, its flying shapes drawn as fireballs in flame orange, 1.2 times larger | as Nightmare Syndromer | as Nightmare Syndromer | as Nightmare Syndromer | as Nightmare Syndromer | - |
| 307 BlackKingNumemon | Royal Muck (composed) | Death Claw | Death Claw's play as a crown of muck lumps in brown-gold, its ring 1.5 times larger | as Death Claw | as Death Claw | as Death Claw | as Death Claw | - |
| 327 Gargoylemon | Gargoyle Rush (composed) | Pummel Whack | Pummel Whack's play as an orange fist, its ring 1.3 times larger | as Pummel Whack | as Pummel Whack | as Pummel Whack | as Pummel Whack | - |

## Where the port differed from the source (history)

- **Voice.** In DW2 the caster shouts the attack's name; that line is a streamed voice the battles here cannot
  play. DW2 has no other sound of its own for its attacks (only a shared hit sound), so the attack keeps the
  launch sounds of the finisher it stands in for.
- **Metal Fireball** hits every enemy in DW2. Here it hits one, like every finisher.
- **Buffalo Breath** stands in for Death Claw, a close-range finisher: Raremon still walks up to its target as
  for Death Claw, so the breath flies only a short way.
- The hit burst is drawn at 0.1 of the caster's scale: DW2 shows it with a close camera, and at the cast's
  scale it covered a third of the screen here.
- **Every attack after Buffalo Breath** keeps its finisher's damage, element, cost, range and target: one enemy,
  hit once. The DW2 target and hit count are in the last column; attacks that hit every enemy or several times in
  DW2 hit one enemy once here, until the unique finishers give them their own values.
- **Projectiles** fly from the finisher's launch point to the target and hit when they reach it. Attacks without a
  projectile play at the target and hit at tick 40, when the cast ends: DW2 hits 10 ticks later, after a camera cut
  to the target that the battles here do not make.
- **Several objects.** Most of these attacks draw two DW2 objects at once (one at the launch point, one at the feet
  or above the head) and all of them are kept.
- **Bit Bomb** (Triceramon, Okuwamon) picks its enemy at random; the signature attacks that stand in for it hit the
  enemy the attack was aimed at.
- **Mega Flame and Electric Shock** (Kimeramon, Deltamon, Hagurumon) are streams that can hit more
  than once while the target stands in them; the signature attacks that stand in for them hit once.
- **Close-range finishers.** MarineDevimon (Death Claw) and Gazimon (Poison Ivy) walk up to their target first,
  as for those finishers, so their projectiles fly only a short way.
- **Hagurumon** (species 122) is the battle species; its field twin 465 has no techniques.

- **DW2003 attacks** play their 3D effects as on the disc, at the caster, for their whole length, and hit when
  they end: nothing flies to the target on its own. They leave out the attack's flat sprites (sparks, flashes,
  the finisher emblem) and DW2003's camera moves. Most of those that stand in a projectile or beam finisher are
  beams or bursts that reach the target in DW2003 too.
- **DW2003 enemy attacks.** Several of the imports are DW2003 enemies with no signature of their own: their
  attack is the enemy's move 1. Vilemon and Mummymon share Dark Fear, and Creepymon and Ghoulmon Darkness
  Chaos, and each port played it: the source effect won over a composed look of its own. Species whose DW2003
  attack is an unnamed slot-5 move played that move's effect.

## Finishers written here

Every imported finisher, the 179 of them, is written for this game, pictures and behaviour. Each one hits as its
design says: one enemy, every enemy, or where the target stood (34 of them, which a target that walks away
dodges). The list, with what each plays and what it hits, is in
[the signature effects notes](../mods/signature-effects.md#authored-finishers); the designs are in
[the unique finishers](../mods/unique-finishers.md). The source attacks above remain where the names, the kinds and
the looks come from.

The support techniques Kongou (Baihumon), Recovery Power (Tinmon) and Fungus Cruncher (Mushroomon) are damage
finishers here, not buffs or heals, so they play a picture that shows the hit on an enemy.
