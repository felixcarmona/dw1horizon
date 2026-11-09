# Recruit screen encounters

## Lava Cave preferences

Gomamon, Ikkakumon and Zudomon use region 9, an area profile that likes cold
and water screens and dislikes all Lava Cave variants. It uses spare entries
in the maps' existing liked/disliked lists; other species keep their reactions.
The complete before/after screen lists and build rules are in
[Water-line area preferences](water-line-preferences.md).

## Wild encounters around waiting recruits

The extended-story compiler finds newly placed roster recruits whose presence
requires their own unrecruited flag. For each screen, ordinary base wild handlers
(`recruitable`, without a surviving city recruit or other scene calls) have their
model load and spawn delayed only while a waiting recruit's complete presence
condition holds. This includes its time and story requirements, rather than just
its unrecruited flag. Existing wild time, random and story conditions remain in
force. With multiple waiting recruits, all must be absent before ordinary wilds
return. Original-story builds are unchanged.

On screen 56, the original USA game always places the three Soulmon; its MAPHEAD
has no time or flag test for them. In the extended story, Phantomon takes their
place only from 20:00 through 23:59 while unrecruited. The Soulmon appear on entry
at other times, and at any time after Phantomon joins. Previously the compiler
discarded Phantomon's clock condition when guarding the Soulmon, hiding all three
even during the day. Presence is selected on screen entry; re-enter after the
clock changes or recruitment.

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

## Candlemon's battle room

Candlemon waits in terminal Lava Cave screen 125 (`TUNN08_3`) at (2500, -650),
away from the corridor in screen 30. Dialogue, stats and the recruitment flag
are unchanged. Saves with Candlemon still unrecruited can use the new encounter;
saves that already recruited it keep the Forge resident.

The native collision stays intact. The placement must be reachable from entry 0
with the chest and trader footprints included, provide a broad battle floor,
remain more than 300 units from arrivals at tracking range zero, and leave the
chest approach and exit reachable. The card trader remains available.
