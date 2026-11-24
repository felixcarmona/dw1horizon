# The new technique rows

The original game has seven rows of eight techniques (Fire, Battle, Air, Earth, Ice, Machine, Filth). Five more rows
join them: **Darkness**, **Light** and **Water** (ids 122 to 145), then **Weapon** and **Earth** (ids 146 to 161),
eight techniques each. A species lists them like any other technique, they are learned the same ways (in battle, by
brain training, as the gift of an evolution), and the Techset screen scrolls through twelve rows.

The original's fourth row is plants, insects and poison, and the game data has always called it `nature`; the screen
called it Earth. Since the row of rock came, the screen says **Nature** for the fourth row and **Earth** for the new
one. Its techniques did not change.

## The techniques

Power, MP and accuracy are `content/techniques/<id>-<name>.json`; the names of the nine languages are
`text/<language>/names.json`.

| Id | Name | Power | MP | Reach | What it does |
|---|---|---|---|---|---|
| 122 | Shadow Claw | 60 | 9 | close | |
| 123 | Dark Bolt | 170 | 30 | shot | |
| 124 | Nightmare | 110 | 36 | shot | may confuse (45%) |
| 125 | Evil Whisper | 0 | 20 | shot | takes 20% of the target's Defense, once per fighter and battle |
| 126 | Death Grip | 300 | 60 | close | may stun (8%) |
| 127 | Venom Mist | 130 | 62 | area | may poison (50%) |
| 128 | Black Gate | 440 | 78 | shot | may flatten (10%) |
| 129 | Abyss Requiem | 620 | 125 | area | may confuse (20%) |
| 130 | Holy Spark | 60 | 10 | close | |
| 131 | Shining Arrow | 170 | 34 | shot | |
| 132 | Blessing | 0 | 40 | self | gives back 10% of the full HP |
| 133 | Sacred Shield | 0 | 22 | self | Defense up 25% |
| 134 | Flash Burst | 150 | 58 | area | may stun (30%) |
| 135 | Judgment Ray | 410 | 70 | shot | |
| 136 | Heaven's Ring | 380 | 92 | area | may stun (12%) |
| 137 | Grand Cross | 600 | 120 | shot | |
| 138 | Bubble Shot | 58 | 8 | shot | may flatten (20%) |
| 139 | Aqua Jet | 160 | 26 | shot | |
| 140 | Rain Dance | 0 | 18 | self | Speed up 20% |
| 141 | Whirlpool | 180 | 58 | area | may confuse (40%) |
| 142 | Hydro Cannon | 360 | 55 | shot | |
| 143 | Sea Crush | 300 | 62 | close | may stun (12%) |
| 144 | Tidal Wave | 400 | 88 | area | may flatten (15%) |
| 145 | Ocean Fury | 560 | 112 | area | |
| 146 | Quick Slash | 60 | 8 | close |  |
| 147 | Blade Throw | 150 | 24 | shot |  |
| 148 | Armor Break | 0 | 20 | close | takes 25% of the target's Defense, once per fighter and battle |
| 149 | War Stance | 0 | 20 | self | Offense up 20% |
| 150 | Cross Cutter | 230 | 36 | close | may flatten (12%) |
| 151 | Whirling Edge | 210 | 50 | area | may stun (10%) |
| 152 | Giant Cleave | 390 | 60 | close | may stun (10%) |
| 153 | Final Edge | 540 | 96 | shot |  |
| 154 | Rock Throw | 64 | 10 | shot |  |
| 155 | Sand Blast | 110 | 28 | area | may confuse (30%) |
| 156 | Stone Skin | 0 | 24 | self | Defense up 30% |
| 157 | Boulder Crash | 220 | 42 | shot | may flatten (20%) |
| 158 | Fissure | 270 | 62 | area | may stun (20%) |
| 159 | Stalagmite | 430 | 73 | shot |  |
| 160 | Landslide | 450 | 95 | area | may flatten (18%) |
| 161 | Gaia Quake | 650 | 130 | area | may stun (15%) |

## The support techniques

`Move.status` says what a technique does besides damage and `Move.statusChance` is its percent
(`include/dw/tech_rules.h`, shared by the field battle, the tournament and the versus fight):

- **5, healing**: the caster gets back that share of its full HP, and the amount rises over it in green, as damage
  does in white. A partner heals three times a battle and an enemy or a tournament rival twice. Nobody heals at full
  HP. Left to itself a partner heals only below 60% of its HP and an enemy below 50%; an order of the player heals
  at any HP below the full.
- **6 and 7**: Defense or Speed up, as the original's buff techniques do.
- **8**: the fighter it reaches loses that share of its Defense, once per fighter and battle.
- **9**: Offense up, the way 6 and 7 raise Defense and Speed.

## Type chart

`content/tables/type-factors.json` is twelve by twelve. Darkness and Light do double damage to each other and half to
their own. Water does double damage to Fire and Filth, one and a half to Machine, and half to Earth, Ice and Water;
Fire and Machine do half to it, Air double and Nature one and a half.

Weapon does one and a half to Nature, half to Machine and Earth and double to Filth; Machine does one and a half to
it and Nature half. Earth does double damage to Machine and Filth, one and a half to Fire, and half to Air, Nature
and Earth; Water does double to it, Nature and Ice one and a half, and Fire, Weapon and Earth half.

## Who uses them

A species' three specialties are the rows it learns from (`specialties` in `content/species/<id>-<name>.json`).
Twenty-five species have Darkness as their first specialty, fourteen Light and thirty Water; more have one of them
as a second or third. Fourteen have Weapon first (Kotemon, Musyamon, Knightmon, Gallantmon and other blades) and
sixteen Earth (Gotsumon, Golemon, Drimogemon, Monochromon, Triceramon and other rock and burrowing Digimon), with
a few more as a second or third. Where a species took a new row it gave up one that did not suit it (Devimon's Ice, Seadramon's
Fire). The wild Digimon and bosses of those species cast the new techniques (`content/maps/*.json`).

A model has an attack animation for each technique of its list. A species that got techniques added plays one of
its own attack clips for each of them: an imported model names the clip in `technique_aliases`
(`content/models/imports/models.json`), an original one in `model.slot_aliases` of its species file.

## Saves

A learned technique is one bit. The 58 original bits stay where they were and the new rows take bits 64 to 87 of the
same field, which the original left unused, so a save of an earlier release loads as it is. Its partner already has
its form, so on that first load it learns the first technique of each new row its species lists (Shadow Claw, Holy
Spark, Bubble Shot); the rest it learns as any other. The Weapon and Earth rows take bits 88 to 103 and do the same
for a save made before them (Quick Slash, Rock Throw); the save's layout number says which rows it has seen.

## Effects

Every one of the 40 effects is ours: a script for the battle's effect machine and a small texture, both made by
`tools/technique_effects` (`kit.py` is what they are built with; `dark.py`, `light.py`, `water.py`, `weapon.py` and
`earth.py` are the rows). `tools/derive/steps/effects.py` packs them into the effect file at build. Nothing of them comes from the
disc. To change one, edit its function and rebuild; `tools/playtest/technique_proof.py` casts a technique in the
emulator and records it.

## The cups

Three specialty cups join the arena's calendar, twice in the 30 days each: the **Dark Cup**, the **Holy Cup** and
the **Aqua Cup**, for the species whose first specialty is that row (the rule cups of
[the engine patches](../reference/engine-patches.md)). The winner gets 5000 bits and a Muscle Yam, a Sage Fruit or
a Power Ice. The **Blade Cup** and the **Gaia Cup** do the same for Weapon and Earth, with an Offense Chip and a
Defense Chip. Their banners are `content/localized/tournament/new-cups/<language>/`.
