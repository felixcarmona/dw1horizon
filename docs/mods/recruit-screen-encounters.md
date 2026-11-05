# Recruit screen encounters

## Lava Cave preferences

Gomamon, Ikkakumon and Zudomon retain favored regions 5, 4 and 3.
The species `partner` record has one `favored_region` byte, with no independent
hated map or region. Each map compares that byte against its `regionA` (liked)
and `regionB` (disliked) lists (`loadMapSetup` in the engine).

Drill Tunnel and Lava Cave maps currently dislike regions 1 and 8. Assigning
one of those to these species would replace their favorites. No preference
change is made: an independent hated-place setting needs a separate format and
engine change.

## Wild encounters around waiting recruits

The extended-story compiler finds newly placed roster recruits whose presence
requires their own unrecruited flag. For each screen, ordinary base wild handlers
(`recruitable`, without a surviving city recruit or other scene calls) get an
additional `recruited(species)` condition on their model load and spawn. Existing
time, random and story conditions remain in force. Multiple waiting recruits
require all of their recruitment flags. Original-story builds are unchanged.

| Screen | Waiting recruit | Ordinary wild slots delayed |
| --- | --- | --- |
| 24, Drill Tunnel | Digmon | 0, Goblimon |
| 36, Great Canyon Entrance | Hawkmon | 0–1, Goblimon; 2–3, Gotsumon |
| 56, Grey Lord's Mansion | Phantomon | 0–2, Soulmon |
| 59, Grey Lord's Mansion | Wizardmon | 0, Tsukaimon |
| 87, Ancient Speedy Region | Triceramon | 0–1, Saberdramon; 2–3, DarkLizardmon |
| 94, Freezeland | Mammothmon | 0–1, SnowGoblimon; 2–3, IceDevimon |
| 162, Factorial Town | Datamon | 1–2, Guardromon |

These handlers only deliver their encounter line and ordinary battle. The
extended roster already excludes their former wild recruitment flags; no
original recruit or story progress requires winning these fights. The Drill
Tunnel cart events depend on tunnel progress and their own step triggers, not
on defeating Goblimon. Factorial Town's remodelling Guardromon (slot 0) stays.

The following story encounters and services remain available:

- Dragon Eye Lake 6: Seadramon and its lake interaction.
- Spore Area 21 and 233: original Centarumon/Unimon scenes.
- Ogre Fortress 45: the Gabumon ambush and fortress progression.
- Gear Savanna 78: Leomon's meeting and stone delivery.
- Ancient Speedy Region 85: Saberdramon's distinct fight and hint scene.
- Ice Sanctuary 97: Angemon's original scene.
- Mt. Infinity 222: the MetalGreymon story battle.
- Kennel 325: the keeper fight that frees Bearmon.

Native Forest 4, Lava Cave 30, Sewer 163 and Toy Mansion 147 have no ordinary
wild handlers to delay. The same applies to Candlemon's destination if its only
other NPC is a service. Future direct `fight()` scenes remain explicit review
points; the compiler never infers that a scripted battle is an ordinary wild.
