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

## Where the port differs from the source

- **Voice.** In DW2 the caster shouts the attack's name; that line is a streamed voice the battles here cannot
  play. DW2 has no other sound of its own for its attacks (only a shared hit sound), so the attack keeps the
  launch sounds of the finisher it stands in for.
- **Metal Fireball** hits every enemy in DW2. Here it hits one, like every finisher.
- **Buffalo Breath** stands in for Death Claw, a close-range finisher: Raremon still walks up to its target as
  for Death Claw, so the breath flies only a short way.
- The hit burst is drawn at 0.1 of the caster's scale: DW2 shows it with a close camera, and at the cast's
  scale it covered a third of the screen here.
