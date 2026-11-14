# Signature attacks: how each one plays

Some imported Digimon play the signature attack of the game they come from in place of the shared finisher
picture. This page says, for each of them, what the attack does in a battle here and where it differs from the
original game. How the effects are converted is in [the signature effects notes](../mods/signature-effects.md);
the DW2 effect format is in [the DW2 effect notes](dw2-effects.md).

The damage, the element, the cost and when the Digimon chooses the attack are the finisher's (the technique the
attack stands in for), unless the species' finisher data says otherwise. Times are battle ticks (20 a second) from
the moment the attack starts.

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
| 265 DarkTyrannomon | Fire Blast (DW2) | High Electro Shocker | at the target: sweeps a stream of flame over every enemy | 1 | plays at the target, hits at tick 40 | none (scale 0.246) | one enemy, as for High Electro Shocker | all enemies |
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

## Where the port differs from the source

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
- **Mega Flame and Electric Shock** (Kimeramon, Cyclonemon, Deltamon, Hagurumon) are streams that can hit more
  than once while the target stands in them; the signature attacks that stand in for them hit once.
- **Close-range finishers.** MarineDevimon (Death Claw) and Gazimon (Poison Ivy) walk up to their target first,
  as for those finishers, so their projectiles fly only a short way.
- **Hagurumon** plays Darkness Gear in battle (species 122); its field twin 465 has no techniques.

## Kept on the DW1 finisher

These Digimon have a DW2 signature attack that converts, but they keep the shared finisher picture for now:

- **Baihumon** (Kongou), **Tinmon** (Recovery Power): DW2 support techniques (a buff on the caster, a heal on an
  ally). Their finishers here deal damage to an enemy, and a support picture that plays on the caster would not
  show the hit.
- **Mushroomon** (Fungus Cruncher): a support technique too, and its effect is 616 bytes larger than an effect
  slot even at the coarsest detail.
