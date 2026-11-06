# Liked and disliked regions

`partner.favored_region` selects one of nine place-response patterns. It does not name a single geographical area or an attack element. This review covers all **223** new raisable species in scope: **114 changes and 109 retained choices**. Gomamon (217), Ikkakumon (218) and Zudomon (219) are excluded from changes because their review is separate. The 65 original partner ids are reference material and remain unchanged.

Before review, 75 of the 226 new partners matched the current `vanilla_as` species’ region and 151 differed. This reproduces the import baseline; matching a donor is neither a reason to keep nor a reason to change an assignment.

## Reading the map data

All **243 native `.MAP` files** were inspected. The table below covers the **237 named native screen rows** in [map_files.csv](../data/map_files.csv), joined by filename to the player-disc `.MAP` setup headers. `tools/dwmap.py` exposes these as `MapFile.regionA` (please) and `regionB` (displease): four signed 32-bit words each, at setup offsets 112 and 128. `-1` is an unused slot. Screen numbers below are decimal, and ranges are inclusive. These are screen ids, not the zone-caption ids in `map_names.csv`.

`loadMapSetup` compares each pair of slots in order, checking A before B at each slot, and stops at the first match. No native screen has a conflicting A/B membership. A match sets `partnerAreaResponse` to 1 (liked) or 2 (disliked); no match means 0 (neutral). The response affects tiredness, happiness and sleep recovery; a specialty does not directly determine it. See [world.md](world.md#how-a-screen-is-entered), `decomp/src/main/map.c:loadMapSetup` and `decomp/src/main/partner_impl.c`.

The remaining six disc files, `MGEN06`–`MGEN10` and `MGEN17` (unused Mt. Infinity layouts outside the 239-row published screen list), are neutral for every region. Two named rows, mansion transitions 50 (`YAKA01`) and 61 (`YAKA21`), have no `.MAP` on the disc and contribute no header response.

## The nine patterns

| Region | Character | Liked native screens | Disliked native screens |
| --- | --- | --- | --- |
| 0 | Heat, lava, underground and prehistoric terrain; rejects cold. | Drill Tunnel (24, 32, 126); Drill Tunnel 2nd floor (25, 29); Drill Tunnel 3rd floor (26); Residential Area (27); Underground Pond (28); Lava Cave (30–31, 33, 122–125); Ancient Dino Region (79); Ancient Glacial Region (80–82); Ancient Speedy Region (83–87) | Freezeland (88–96, 132–137); Leomon Ancestor's Cave (114) |
| 1 | Cold and snow; rejects lava, warm tunnels and tropical jungle. | Freezeland (88–96, 132–137); Leomon Ancestor's Cave (114) | Tropical Jungle (11–14); Mangrove Region (15–16); Amida Forest (17); Drill Tunnel (24, 32, 126); Drill Tunnel 2nd floor (25, 29); Drill Tunnel 3rd floor (26); Residential Area (27); Underground Pond (28); Lava Cave (30–31, 33, 122–125); Great Canyon Entrance (36) |
| 2 | Holy and sacred; rejects haunted, dark and filthy places. Not the general cold region. | Ice Sanctuary (97–104) | Overdell (34); Overdell Cemetery (35); Grey Lord's Mansion (51–60, 62–65, 224, 232); Mansion Basement (66); Underground Lab (67–68, 221); Trash Mountain (164–165); Mt. Infinity (219) |
| 3 | Machines and industry; rejects misty woods and swamps. Not all city screens. | Factorial Town (152–162) | Misty Trees (115–121); Geko Swamp (138–139); Volume Villa (140–141) |
| 4 | Water, humidity, tropical jungle and swamps; rejects dry canyon terrain. Not every coastline. | Tropical Jungle (11–14); Mangrove Region (15–16); Amida Forest (17); Great Canyon Entrance (36); Geko Swamp (138–139); Volume Villa (140–141) | Great Canyon Top Area (37–38, 43–44); Great Canyon Bridge (39); Fortress Entrance (40); Great Canyon Bot. Area (41–42); Monochrome Shop (49); Great Canyon (127–129) |
| 5 | Open natural wilderness, plains and savanna; rejects industry and sewers. Not every forest. | Path Thru Mt. Panorama (18, 20); Mt. Panorama Plains (19); Mt. Panorama Spore Area (21, 233–234); Foot of Mt. Panorama (22–23); Gear Savanna (69–78, 131) | Factorial Town (152–162); Sewer (163, 220) |
| 6 | Darkness, ghosts, demons and unclean creatures; rejects holy ground and Toy Town. | Overdell (34); Overdell Cemetery (35); Grey Lord's Mansion (51–60, 62–65, 224, 232); Mansion Basement (66); Underground Lab (67–68, 221); Mt. Infinity (219) | Ice Sanctuary (97–104); Toy Town (144); Costume House (145); Robot House (146); Toy Mansion (147–151) |
| 7 | Insects and Beetle Land; rejects cold. Not the general plant or forest region. | Beetle Land (105–108) | Freezeland (88–96, 132–137); Leomon Ancestor's Cave (114) |
| 8 | Safe starting places and baby care; rejects many harsh or dangerous places. | Native Forest (0, 2–4, 109–111); Kunemon's Bed (1); Coela Point (5); Dragon Eye Lake (6, 8); Drill Tunnel Entrance (7); Digimon Bridge (9–10); Green Gym (112) | Drill Tunnel (24, 32, 126); Drill Tunnel 2nd floor (25, 29); Drill Tunnel 3rd floor (26); Residential Area (27); Underground Pond (28); Lava Cave (30–31, 33, 122–125); Overdell (34); Overdell Cemetery (35); Great Canyon Top Area (37–38, 43–44); Great Canyon Bridge (39); Fortress Entrance (40); Great Canyon Bot. Area (41–42); Monochrome Shop (49); Grey Lord's Mansion (51–60, 62–65, 224, 232); Mansion Basement (66); Underground Lab (67–68, 221); Freezeland (88–96, 132–137); Leomon Ancestor's Cave (114); Great Canyon (127–129); Geko Swamp (138–139); Volume Villa (140–141); Factorial Town (152–162); Trash Mountain (164–165); Mt. Infinity (219) |

Native screens neutral to all nine patterns: Ogre Fortress (45–48, 130); Leomon Ancestor's Cave (113); Secret Beach Cave (142–143); Mt. Infinity (166–167, 210, 212, 222, 225, 229–231); File City (168–204, 236–238); Jijimon's house (205–206, 218); Birdra Transport (207); Arena Lobby (208, 223); Treasure Hunt (209); Item Keeper (211); Centar Clinic (213); Restaurant (214–215); Item Shop (216); Secret Item Shop (217); Back Dimension (226–228); Digimon Curling (235).

In particular, Ice Sanctuary is **holy (2)**, while Freezeland is **cold (1)**. Coela Point and Dragon Eye Lake favor babies (8), not aquatic adults (4). Toy Town does not favor holy species; it only displeases dark species. Trash Mountain displeases 2 and 8 but does not actively please 6. File City is neutral, so “machine/city” is only shorthand for Factorial Town. Region 0 includes Ancient Glacial Region despite its name; changing species cannot fix that native map convention.

### Added screens

The built story adds **69 screens (300–368)**. Of these, **65** use `base_map()` in `story/mods/what-the-island-forgot/maps/mapbase.py`, assigning A `[5, -1, -1, -1]` and B `[-1, -1, -1, -1]`. They please region 5 and displease none, including interiors and cold or industrial-looking scenes. This is an existing map limitation; species choices do not compensate for their scenery.

Four screens retain donor responses: the Shaft (302) is neutral to every region; the Fallen Nest (366) and the new canyon passage (368) dislike 4 and 8; the Stone Bridge (367) likes 4 and dislikes 1. These additions introduce no responses for regions 0, 2, 3, 6 or 7. All added headers were checked in the full build; native retouches retain their original region words. No map header changes in this review.

| Screen | Name | File | Liked region | Disliked regions |
| --- | --- | --- | --- | --- |
| 300 | Engine Room | `ENGN01` | 5 | None |
| 301 | The Rift | `RIFT01` | 5 | None |
| 302 | The Shaft | `SHFT01` | None | None |
| 303 | The Descent | `DESC01` | 5 | None |
| 304 | Second Chamber | `SHRN01` | 5 | None |
| 305 | Passage | `PASS01` | 5 | None |
| 306 | Bone Field | `BONE01` | 5 | None |
| 307 | Crypt Corridor | `CRYP01` | 5 | None |
| 308 | Lectern Room | `CRYP02` | 5 | None |
| 309 | Drowned Shore | `SHOR01` | 5 | None |
| 310 | Wall Of Hearts | `VALT01` | 5 | None |
| 311 | Wall Of Hearts Melted | `VALT02` | 5 | None |
| 312 | Infinity Engine | `INFE01` | 5 | None |
| 313 | Infinity Engine Dark | `INFE02` | 5 | None |
| 314 | Root Clearing | `ROOT01` | 5 | None |
| 315 | Old Gallery | `GALL01` | 5 | None |
| 316 | Lake Terrace | `LAKE01` | 5 | None |
| 317 | Iron Hills 1 | `IRON01` | 5 | None |
| 318 | Iron Hills 2 | `IRON02` | 5 | None |
| 319 | Iron Hills 3 | `IRON03` | 5 | None |
| 320 | Iron Hills 4 | `IRON04` | 5 | None |
| 321 | Iron Hills 5 | `IRON05` | 5 | None |
| 322 | The Brink | `IRON06` | 5 | None |
| 323 | Seam 1 | `SEAM01` | 5 | None |
| 324 | Seam 2 | `SEAM02` | 5 | None |
| 325 | Kennel | `SEAM03` | 5 | None |
| 326 | Seam 3 | `SEAM04` | 5 | None |
| 327 | Seam 4 | `SEAM05` | 5 | None |
| 328 | Watchtower | `SEAM06` | 5 | None |
| 329 | Seam 5 | `SEAM07` | 5 | None |
| 330 | Descent 1 | `OVPS01` | 5 | None |
| 331 | Descent 2 | `OVPS02` | 5 | None |
| 332 | Descent 3 | `OVPS03` | 5 | None |
| 333 | Descent 4 | `OVPS04` | 5 | None |
| 334 | Descent 5 | `OVPS05` | 5 | None |
| 335 | Descent 6 | `OVPS06` | 5 | None |
| 336 | Ossuary | `OVPS07` | 5 | None |
| 337 | Mine Head | `MINE01` | 5 | None |
| 338 | Gallery North 1 | `MINE02` | 5 | None |
| 339 | Gallery North 2 | `MINE06` | 5 | None |
| 340 | Cart Hall | `MINE07` | 5 | None |
| 341 | Gallery West 1 | `MINE08` | 5 | None |
| 342 | Flooded Gallery | `MINE03` | 5 | None |
| 343 | Gallery West 2 | `MINE09` | 5 | None |
| 344 | Sunken Gallery | `MINE10` | 5 | None |
| 345 | Gallery East | `MINE11` | 5 | None |
| 346 | The Workshop | `MINE12` | 5 | None |
| 347 | Workshop Gallery | `MINE13` | 5 | None |
| 348 | Great Chamber | `MINE05` | 5 | None |
| 349 | The Bridge | `MINE04` | 5 | None |
| 350 | High Gallery | `MINE14` | 5 | None |
| 351 | Gallery East 2 | `MINE15` | 5 | None |
| 352 | Rubbish Gallery | `MINE16` | 5 | None |
| 353 | Rubbish Mouth | `MINE17` | 5 | None |
| 354 | The Stair | `MINE18` | 5 | None |
| 355 | Heart Of The Mine | `MINE19` | 5 | None |
| 356 | The Drain | `MINE20` | 5 | None |
| 357 | The Stone Yard | `BARR01` | 5 | None |
| 358 | The Courtyard | `BARR02` | 5 | None |
| 359 | Guard House | `BARR03` | 5 | None |
| 360 | Power Station | `BARR04` | 5 | None |
| 361 | Scrap Office | `BARR05` | 5 | None |
| 362 | Forge Workshop | `BARR06` | 5 | None |
| 363 | Cold Store | `BARR07` | 5 | None |
| 364 | Market Shed | `BARR08` | 5 | None |
| 365 | Container House | `BARR09` | 5 | None |
| 366 | Nest Fallen | `NEST02` | None | 4, 8 |
| 367 | Stone Bridge | `GCAN21` | 4 | 1 |
| 368 | Canyon Crack | `GCAN27` | None | 4, 8 |

## Original game reference: ids 1–65

These are the original disc values from `content/tables/disc-species.json` through `tools/species.py:files_from_exe`, using current project names. The row for 62 is a placeholder in the original game; Horizon already gives the restored WereGarurumon region **1** instead of that placeholder’s **0**. Panjyamon is named IceLeomon (63) in the project. All other current original partner regions match the disc.

| Original region | Species (id) | Original design pattern |
| --- | --- | --- |
| 0 | Agumon (3), Greymon (5), Tyrannomon (8), Meramon (9), Birdramon (21), Centarumon (36), Monochromon (47), Phoenixmon (59), WereGarurumon (62) [unused original row] | Heat, lava, underground and prehistoric terrain; rejects cold. |
| 1 | Garurumon (22), Frigimon (23), Mojyamon (52), Penguinmon (57) | Cold and snow; rejects lava, warm tunnels and tropical jungle. |
| 2 | Airdramon (7), Monzaemon (14), Angemon (20), Unimon (33), Piximon (55), IceLeomon (63) | Holy and sacred; rejects haunted, dark and filthy places. Not the general cold region. |
| 3 | MetalGreymonVirus (12), Mamemon (13), MetalMamemon (27), Vademon (28), Andromon (40), Giromon (41), Megadramon (54), Gigadramon (64), MetalEtemon (65) | Machines and industry; rejects misty woods and swamps. Not all city screens. |
| 4 | Betamon (4), Seadramon (10), Whamon (24), Shellmon (35), Coelamon (49), MegaSeadramon (61) | Water, humidity, tropical jungle and swamps; rejects dry canyon terrain. Not every coastline. |
| 5 | Gabumon (17), Elecmon (18), Vegiemon (25), Patamon (31), Ogremon (34), Drimogemon (38), Etemon (42), Biyomon (45), Palmon (46), Leomon (48), Kokatorimon (50), Ninjamon (58) | Open natural wilderness, plains and savanna; rejects industry and sewers. Not every forest. |
| 6 | Devimon (6), Numemon (11), SkullGreymon (26), Bakemon (37), Sukamon (39), Nanimon (53), Digitamamon (56) | Darkness, ghosts, demons and unclean creatures; rejects holy ground and Toy Town. |
| 7 | Kabuterimon (19), Kunemon (32), Kuwagamon (51), HerculesKabuterimon (60) | Insects and Beetle Land; rejects cold. Not the general plant or forest region. |
| 8 | Botamon (1), Koromon (2), Punimon (15), Tsunomon (16), Poyomon (29), Tokomon (30), Yuramon (43), Tanemon (44) | Safe starting places and baby care; rejects many harsh or dangerous places. |

The original design groups all eight babies in region 8, most organic Rookies and woodland fighters in 5, insects in 7, machines and metal mutants in 3, sea creatures in 4, snow creatures in 1, angels and benign magical creatures in 2, ghosts/Filth in 6, and Fire/dinosaurs in 0. These are affinities, not strict taxonomic rules: IceLeomon uses holy 2, Monzaemon and Piximon use 2, Digitamamon uses 6, and Whamon uses water 4. Preserving such reasonable variation is preferable to deriving regions mechanically from the first specialty.

## Review policy and line continuity

Choices weigh the actual liked **and** disliked screens, the committed specialties and techniques, a species’ habitat and identity, and its family. Habitat-specific evidence wins over a superficial name, color, armor or attack. A new region is used only when the old pattern clearly conflicts with that identity. The per-species reasons below are project judgments about the closest available pattern, not claims that canon specifies a DW1 region number.

The main continuities are Wormmon/Stingmon and the beetles → 7; Otamamon/Gekomon/ShogunGekomon and marine species → 4; Salamon/angels and sacred armor → 2; Myotismon and demon/ghost lines → 6; Renamon/Kyubimon/Taomon/Sakuyamon and woodland beasts → 5; Guilmon/Growlmon/WarGrowlmon and Fire Greymon forms → 0; and Kurisarimon/Infermon/Diaboromon/Armageddemon plus the mechanical elemental warriors → 3. MetalGreymon shifts the organic Greymon line toward machinery, while WarGreymon returns to a Fire warrior identity. MetalGarurumon keeps the wolf line’s cold affinity despite its weaponry.

Branches can differ when the identity changes: Shadramon’s Fire armor uses 0 while the ordinary beetle line uses 7; Paildramon and Imperialdramon use machines (3); Gallantmon becomes a holy knight (2) after the Fire Guilmon line (0). Salamon’s holy 2, Gatomon’s retained outdoor 5, BlackGatomon’s dark 6 and Angewomon’s holy 2 follow distinct identities. Both mammoths keep cold 1, and Omnimon retains its defensible Fire-side compromise 0. No region can simultaneously express every parent or every element.

Primary canon checks include the official profiles for [SnowAgumon](https://digimon.net/reference_en/detail.php?directory_name=yukiagumon), [Muchomon](https://digimon.net/reference_en/detail.php?directory_name=muchomon), [MoriShellmon](https://digimon.net/reference_en/detail.php?directory_name=morishellmon), [Vikemon](https://digimon.net/reference_en/detail.php?directory_name=vikemon), [Blossomon](https://digimon.net/reference_en/detail.php?directory_name=blossomon), [Lynxmon](https://digimon.net/reference_en/detail.php?directory_name=lynxmon), [Tapirmon](https://digimon.net/reference_en/detail.php?directory_name=bakumon), [Quetzalmon](https://digimon.net/reference_en/detail.php?directory_name=quetzalmon), [Maildramon](https://digimon.net/reference_en/detail.php?directory_name=maildramon), [Gallantmon](https://digimon.net/reference_en/detail.php?directory_name=dukemon), and [Zanbamon](https://digimon.net/reference_en/detail.php?directory_name=zanbamon). Golemon (108) is the project’s native Rockmon-based record, not the later rock-golem design; Tinmon (123) is the project’s DW2 record. Their committed Ice identities are retained rather than replaced by a similarly named encyclopedia entry.

## Changes

| Id | Species | Specialties | Region before → after | Reason |
| --- | --- | --- | --- | --- |
| 70 | WaruMonzaemon | Battle/Air | 2 → 6 | Malicious possessed toy belongs with the mansion and ghosts, not the holy sanctuary. |
| 71 | SnowAgumon | Ice/Battle | 0 → 1 | Snow and Ice identity requires Freezeland and aversion to lava. |
| 72 | Hyogamon | Ice/Battle | 5 → 1 | Snow-country ogre should share the cold region with Icemon and IceLeomon's icy relatives. |
| 76 | Tankmon | Fire/Mech | 0 → 3 | Mechanical tank belongs in Factorial Town rather than a lava habitat. |
| 92 | Guardromon | Mech/Battle/Fire | 5 → 3 | Mechanical guard should share Andromon and Hagurumon's factory region. |
| 93 | Muchomon | Ice/Air | 1 → 4 | Tropical bird should favor jungle wetlands rather than freezing country. |
| 96 | Tsukaimon | Battle/Air | 5 → 6 | Demonic Patamon counterpart fits Devimon's dark places rather than ordinary grassland. |
| 109 | Otamamon | Ice | 5 → 4 | Aquatic tadpole belongs in the jungle and Geko Swamp with Gekomon. |
| 110 | Gekomon | Ice | 5 → 4 | Amphibious frog musician belongs with ShogunGekomon in Geko Swamp. |
| 183 | Wormmon | Nature/Battle | 1 → 7 | Larval insect should share Stingmon and the beetle family, not dislike warm insect habitats. |
| 187 | Stingmon | Nature/Battle | 6 → 7 | Insect warrior should share Wormmon and other beetle evolutions rather than the ghost region. |
| 188 | Aquilamon | Air/Battle | 0 → 5 | Air/Battle eagle belongs with Hawkmon in open wilderness rather than lava. |
| 190 | Angewomon | Air/Battle | 0 → 2 | Archangel should share Angemon's holy region rather than lava. |
| 192 | Imperialdramon | Mech/Fire/Battle | 1 → 3 | Ancient weaponized dragon with Machine/Fire belongs with Paildramon's machinery, not freezing country. |
| 193 | Digmon | Battle/Nature | 3 → 7 | Drill-armored insect fits the insect family; digging alone does not make it a factory machine. |
| 196 | Halsemon | Air/Battle | 1 → 5 | Wind-armored hawk should follow Hawkmon and Aquilamon's open wilderness, not ice country. |
| 197 | Magnamon | Battle/Mech | 0 → 2 | Holy knight in Miracle armor fits the sanctuary rather than lava. |
| 198 | Nefertimon | Air/Fire | 0 → 2 | Sacred sphinx of Light fits the holy region rather than volcanic terrain. |
| 199 | Paildramon | Battle/Mech | 7 → 3 | Armed cyborg dragon progresses from organic parents into a machine region, not an insect habitat. |
| 201 | Lighdramon | Air/Battle | 1 → 5 | Lightning quadruped fits open grassland like Elecmon rather than freezing country. |
| 206 | MagnaAngemon | Air/Battle | 7 → 2 | High-ranking angel should share Angemon's holy region, not the insect region. |
| 207 | Seraphimon | Air/Fire/Battle | 5 → 2 | Seraph angel should share the holy line rather than generic grassland. |
| 208 | Togemon | Nature/Battle | 1 → 5 | Cactus boxer fits dry grassland and Palmon's natural region, not freezing country. |
| 209 | Lillymon | Nature/Battle | 3 → 5 | Flower fairy should share Palmon and Rosemon's natural region rather than factories. |
| 210 | GranKuwagamon | Nature/Battle/Air | 0 → 7 | Giant stag beetle belongs with Kuwagamon's insect line rather than lava. |
| 211 | MetalSeadramon | Ice/Mech | 0 → 4 | Mechanical sea serpent retains Seadramon's aquatic habitat rather than a lava preference. |
| 212 | VenomMyotismon | Fire/Battle | 0 → 6 | Vampire demon should continue Myotismon's dark-region identity rather than favor lava. |
| 213 | AeroVeedramon | Air/Battle/Fire | 3 → 0 | Fire-bearing winged dragon should continue Veedramon's warm branch rather than favor factories. |
| 214 | Shakkoumon | Nature/Mech | 1 → 2 | Holy earthen idol fits the angel-derived sanctuary branch rather than freezing country. |
| 215 | Magnadramon | Fire/Air | 4 → 2 | Holy dragon has no aquatic identity to justify wetlands; the sanctuary matches its sacred role. |
| 216 | Devidramon | Battle/Air | 3 → 6 | Evil winged dragon fits Devimon and the dark branch rather than factories. |
| 220 | Vikemon | Ice/Battle | 7 → 1 | Arctic beast leader should favor Freezeland and reject lava, not dislike Freezeland as an insect would. |
| 222 | BlackGatomon | Battle/Air | 5 → 6 | Dark Gatomon counterpart fits the demon branch and rejection of holy ground. |
| 223 | LadyDevimon | Battle/Air | 3 → 6 | Female demon belongs with Devimon and Myotismon rather than factories. |
| 224 | MetalGreymonVaccine | Mech/Fire/Battle | 5 → 3 | Cyborg Greymon should share MetalGreymonVirus's industrial region rather than dislike factories. |
| 226 | Silphymon | Air/Battle | 7 → 5 | Aerial beast fusion follows Hawkmon's open wilderness rather than the insect region. |
| 227 | Apemon | Battle/Fire | 7 → 5 | Mountain and woodland ape fits natural wilderness rather than a dedicated beetle habitat. |
| 229 | Phantomon | Air/Ice/Battle | 3 → 6 | Grim-reaper ghost belongs with Bakemon and the haunted mansion rather than factories. |
| 231 | ShellNumemon | Filth/Battle | 0 → 6 | Shelled Numemon retains Filth identity and belongs with Numemon, not a lava habitat. |
| 233 | RedOtamamon | Fire/Battle | 6 → 0 | Fire-specialist tadpole counterpart fits warm places rather than the dark region. |
| 235 | Candlemon | Fire/Battle | 5 → 0 | Living candle with Fire specialty belongs in warm places rather than generic grassland. |
| 236 | DemiDevimon | Battle/Air | 5 → 6 | Little bat demon should continue into Devimon's dark places rather than favor grassland. |
| 240 | Gesomon | Ice/Battle | 6 → 4 | Marine squid should favor aquatic places rather than the haunted mansion. |
| 242 | Sorcermon | Ice/Air | 6 → 1 | Ice sorcerer should favor cold places rather than the dark region. |
| 245 | Piedmon | Battle/Air | 3 → 6 | Demonic magician belongs in the dark region rather than a factory habitat. |
| 246 | Infermon | Mech/Nature | 0 → 3 | Network-destroying artificial insect should share Kurisarimon and Diaboromon's machine affinity rather than lava. |
| 247 | Kokuwamon | Air/Mech | 5 → 3 | Mechanical beetle should share Hagurumon's factory region rather than dislike industry. |
| 248 | MarineAngemon | Ice/Battle | 3 → 4 | Tiny marine angel lives in water; aquatic identity outweighs its angel name and rejects factories. |
| 249 | Quetzalmon | Air/Ice | 3 → 2 | Sacred feathered serpent fits a holy aerial branch rather than a factory habitat. |
| 251 | Solarmon | Fire/Mech | 6 → 0 | Heat-generating sun gear should favor warm places rather than the dark region. |
| 252 | Thundermon | Air/Battle | 7 → 3 | Electrical Mamemon relative fits its family’s factory region, with no insect identity to justify Beetle Land. |
| 253 | Tuskmon | Battle/Fire | 7 → 0 | Dinosaur with Fire/Battle fits Tyrannomon's warm prehistoric region rather than beetle country. |
| 255 | Valkyrimon | Air/Battle/Ice | 7 → 1 | Norse warrior with an explicit Ice specialty fits cold country rather than beetle country. |
| 257 | Triceramon | Battle/Nature | 3 → 0 | Ceratopsian dinosaur should follow Monochromon's warm prehistoric terrain rather than factories. |
| 258 | SaberLeomon | Battle/Air | 0 → 5 | Ancient saber-toothed lion should share Leomon's wilderness region rather than favor lava. |
| 262 | Flymon | Nature/Air | 2 → 7 | Flying insect should share Kunemon and the insect line rather than a holy sanctuary. |
| 263 | Mushroomon | Nature/Battle | 1 → 5 | Woodland mushroom should share Woodmon's natural region rather than freezing country. |
| 264 | Raremon | Filth/Battle | 5 → 6 | Rotting sludge and Filth identity belong with Numemon and unclean dark places rather than grassland. |
| 265 | DarkTyrannomon | Fire/Battle | 7 → 0 | Dark dinosaur retains Fire and Tyrannomon's warm prehistoric identity rather than becoming an insect. |
| 266 | ExTyrannomon | Battle/Fire | 0 → 6 | Sinister stuffed dinosaur fits WaruMonzaemon's haunted-toy branch rather than lava. |
| 269 | Garbagemon | Filth/Mech | 2 → 6 | Garbage collector with Filth identity belongs with Sukamon and trash rather than holy ground. |
| 270 | PrinceMamemon | Battle/Mech | 6 → 3 | Metallic Mamemon royal should follow Mamemon's factory region rather than the ghost region. |
| 271 | Plesiomon | Ice/Air | 0 → 4 | Aquatic plesiosaur should continue Whamon and the marine line rather than favor lava. |
| 273 | Floramon | Nature/Ice | 1 → 5 | Flower Rookie should share Palmon and its plant evolutions rather than freezing country. |
| 274 | Blossomon | Nature/Battle | 7 → 4 | Moisture-loving flower monster explicitly avoids arid terrain; wetlands and dislike of dry canyon fit better than beetle country. |
| 276 | Baihumon | Battle/Mech | 1 → 2 | Divine tiger guardian fits the holy region rather than cold country without an Ice identity. |
| 277 | SkullMeramon | Fire/Battle | 5 → 0 | Flame-bodied Meramon evolution should share Meramon and BlueMeramon's hot-region identity. |
| 278 | Octomon | Ice/Battle | 7 → 4 | Marine octopus should favor water rather than insect habitat. |
| 280 | Pumpkinmon | Battle/Fire | 1 → 6 | Halloween puppet fits haunted places rather than freezing country without an Ice identity. |
| 281 | Cyclonemon | Fire/Battle | 4 → 0 | Fire-bearing land dragon belongs with hot prehistoric reptiles rather than wetlands. |
| 284 | Crabmon | Ice/Battle | 6 → 4 | Aquatic crab should share Syakomon and Ebidramon's water region rather than ghosts. |
| 285 | Gazimon | Battle/Nature | 1 → 5 | Small woodland mammal with Nature specialty fits outdoor wilderness rather than freezing country. |
| 286 | Deramon | Nature/Battle | 3 → 5 | Bird with a shrub-like body belongs with Kiwimon and plant lines rather than factories. |
| 287 | Tapirmon | Battle/Air | 1 → 2 | Dream-eating holy beast fits the sanctuary and rejection of evil places rather than cold country. |
| 288 | Boltmon | Battle/Mech | 5 → 3 | Artificial stitched cyborg fits the machine region rather than rejecting factories. |
| 294 | Datamon | Mech/Air/Fire | 6 → 3 | Computer researcher should share the machine region rather than the dark region. |
| 295 | Vilemon | Battle/Air | 3 → 6 | Small nightmare demon belongs with the dark branch rather than factories. |
| 296 | Grizzlymon | Battle/Ice | 4 → 5 | Forest bear should share Bearmon and woodland beasts rather than aquatic habitats. |
| 298 | Dokugumon | Nature/Battle | 5 → 7 | Poisonous spider belongs with Wormmon and other insect evolutions rather than generic grassland. |
| 299 | Hookmon | Battle/Mech | 5 → 4 | Pirate captain's maritime identity fits the water region rather than grassland. |
| 300 | SlashAngemon | Battle/Air | 5 → 2 | Armed angel should keep the angel line's sanctuary preference rather than generic grassland. |
| 302 | HiAndromon | Mech/Battle | 5 → 3 | Upgraded Andromon should retain its factory preference rather than dislike industry. |
| 304 | Divermon | Ice/Battle | 1 → 4 | Marine diver should favor aquatic places rather than freezing country. |
| 307 | BlackKingNumemon | Filth/Battle | 5 → 6 | Numemon king should retain the Filth line's unclean dark region rather than grassland. |
| 310 | Assaultmon | Mech/Battle | 0 → 3 | Armed mechanical soldier belongs with Tankmon and other machines rather than lava. |
| 311 | Arukenimon | Nature/Battle | 3 → 7 | Spider shapeshifter should share Dokugumon's insect region rather than factories. |
| 312 | Creepymon | Fire/Battle/Air | 3 → 6 | Demon lord should share the demonic dark region rather than factories despite its Fire attacks. |
| 313 | Bulbmon | Mech/Ice | 2 → 3 | Cargo-carrying machine has no holy identity to justify the sanctuary; Factorial Town fits. |
| 314 | SkullSatamon | Battle/Fire | 5 → 6 | Undead demon belongs with ghosts and devils rather than ordinary grassland. |
| 318 | Gallantmon | Battle/Mech/Air | 3 → 2 | Holy knight should favor the sanctuary rather than machinery merely because it wears armor. |
| 319 | Pharaohmon | Nature/Battle | 3 → 6 | Undead pharaoh belongs with the dark mansion and tomb-like places rather than factories. |
| 322 | Kyukimon | Air/Battle | 0 → 5 | Wind-bladed woodland beast fits natural open terrain rather than lava. |
| 324 | Maildramon | Battle/Air | 0 → 3 | Mechanized armored dragon fits the machine branch rather than lava without Fire specialty. |
| 327 | Gargoylemon | Battle/Nature | 5 → 2 | Sacred guardian gargoyle fits the sanctuary rather than generic grassland. |
| 328 | Snimon | Battle/Air/Nature | 6 → 7 | Mantis insect belongs with the insect family rather than ghosts. |
| 329 | Ghoulmon | Mech/Battle/Air | 0 → 6 | Dark demon beast fits the demonic region rather than favoring lava merely for incidental attacks. |
| 331 | Vemmon | Battle/Mech | 5 → 3 | Artificial weapon organism belongs with the machine line rather than disliking factories. |
| 332 | Roachmon | Nature/Filth/Battle | 0 → 6 | Filth-associated cockroach fits unclean dark places with Numemon rather than lava. |
| 334 | Mummymon | Battle/Mech/Air | 5 → 6 | Mummified undead gunman belongs with the dark branch rather than generic grassland. |
| 336 | Raidenmon | Air/Fire/Mech | 7 → 3 | Fusion of mechanical elemental warriors should share Fujinmon and Raijinmon's factory region, not beetle habitat. |
| 353 | Bearmon | Battle/Ice | 0 → 5 | Bear Rookie should share Grizzlymon and woodland beasts rather than lava. |
| 373 | WarGreymon | Fire/Battle/Air | 3 → 0 | Fire-leading dragon warrior should continue Agumon and Greymon's warm branch rather than favor factories. |
| 400 | Apocalymon | Mech/Battle/Ice | 3 → 6 | Destructive darkness-born final antagonist belongs with dark places rather than machinery alone. |
| 401 | Pukumon | Ice/Battle | 3 → 4 | Marine pufferfish brawler belongs with aquatic Digimon rather than factories. |
| 402 | NeoCrimson | Fire/Battle | 0 → 3 | Mechanized crimson weapon belongs with the machine branch rather than lava solely from Fire attacks. |
| 404 | BlackWarGreymon | Fire/Battle/Air | 3 → 0 | Black WarGreymon retains the Fire dragon warrior identity rather than becoming a factory machine. |
| 405 | Cannondramon | Mech/Fire | 1 → 3 | Cannon-equipped dinosaur with Machine/Fire should favor industry rather than freezing country. |
| 406 | MaloMyotismon | Fire/Battle/Air | 5 → 6 | Vampire lord should continue Myotismon's dark preference rather than grassland. |
| 407 | Armageddemon | Fire/Battle/Mech | 0 → 3 | Artificial network-destroying superweapon should continue Diaboromon's machine region rather than lava. |
| 408 | Suijinmon | Ice/Mech | 6 → 3 | Mechanical aquatic warrior reasonably follows the machine fusion line rather than the dark region. |
| 409 | Kyubimon | Fire/Battle | 1 → 5 | Mystic Fire fox should follow Renamon, Taomon and Sakuyamon's natural region rather than freezing country. |
| 430 | Zanbamon | Battle/Air | 2 → 5 | Mounted warrior general should follow Musyamon in outdoor terrain rather than holy ground without a sacred identity. |
| 431 | Kurisarimon | Mech/Nature | 5 → 3 | Artificial network chrysalis should begin Infermon and Diaboromon's machine-region progression. |
| 432 | Bastemon | Battle/Nature | 3 → 5 | Feline beast dancer fits wilderness rather than machinery. |

## Retained choices

| Id | Species | Specialties | Region kept | Reason |
| --- | --- | --- | --- | --- |
| 66 | Myotismon | Air/Battle/Ice | 6 | Vampire and mansion dweller; the dark region already fits Myotismon. |
| 67 | Yanmamon | Air/Nature | 4 | Dragonfly with an aquatic larval identity; humid marshes are a reasonable alternative to Beetle Land. |
| 68 | Gotsumon | Battle | 5 | Rocky outdoor terrain suits this mineral Rookie without implying an ice identity. |
| 69 | Flarerizamon | Fire | 0 | Flame-bodied reptile fits lava and the warm dinosaur areas. |
| 74 | Dokunemon | Nature/Air | 7 | Poisonous caterpillar belongs with Kunemon and the insect region. |
| 80 | Goblimon | Battle/Fire | 5 | Forest-dwelling goblin and Ogremon relative already fits outdoor wilderness. |
| 82 | Psychemon | Battle | 5 | Gabumon-like beast already fits grassland wilderness. |
| 84 | ToyAgumon | Fire/Battle | 0 | Toy construction does not remove its Fire specialty; Agumon's warm region remains reasonable. |
| 85 | Piddomon | Air/Battle | 2 | Angel identity agrees with Angemon's holy sanctuary region. |
| 87 | Geremon | Filth | 6 | Numemon relative and Filth specialist already fits dark and unclean places. |
| 88 | Vermilimon | Fire/Battle | 0 | Volcanic Monochromon relative already fits hot prehistoric terrain. |
| 89 | Fugamon | Air/Battle/Fire | 5 | Wind ogre remains coherent with Ogremon's wilderness region. |
| 90 | Tekkamon | Mech/Battle | 3 | Armed mechanical swordsman fits the same factory region as Giromon. |
| 91 | MoriShellmon | Nature/Ice | 4 | Woodland swamp mollusk fits the wetland region despite its forest camouflage. |
| 94 | Icemon | Ice/Battle | 1 | Ice-bodied mineral Digimon already fits cold places and dislikes lava. |
| 100 | IceDevimon | Ice/Battle | 6 | Ice is secondary to its fallen-angel identity; Devimon's dark region remains reasonable. |
| 104 | BlueMeramon | Ice/Fire | 0 | Superheated blue flames remain a clear lava-region fit despite the Ice specialty. |
| 105 | Gururumon | Battle/Ice | 1 | Garurumon relative with Ice specialty already fits the cold region. |
| 106 | Saberdramon | Fire/Air | 0 | Dark bird retains Fire specialty and Birdramon's warm-region identity. |
| 107 | Soulmon | Air/Ice | 6 | Ghost with a wizard's hat belongs with Bakemon and the haunted mansion. |
| 108 | Golemon | Ice/Battle | 1 | The project's native Rockmon-based Golemon has Ice/Battle and an icy arsenal; its cold choice is defensible. |
| 111 | Tentomon | Nature | 7 | Beetle Rookie already agrees with Kabuterimon's insect region. |
| 112 | WaruSeadramon | Ice/Air | 4 | Dark Seadramon remains aquatic; the water region is already suitable. |
| 113 | Meteormon | Fire/Battle | 0 | Fire-bearing meteor mineral fits warm prehistoric terrain without a stronger habitat requirement. |
| 115 | Machinedramon | Mech/Air/Battle | 3 | Machine dragon already fits Factorial Town. |
| 116 | Analogman | Mech/Air | 3 | Technology-focused human antagonist already fits machines and industry. |
| 117 | Jijimon | Battle | 5 | Nature-adjacent elder and Battle specialist has a reasonable wilderness preference. |
| 119 | ShogunGekomon | Ice | 4 | Gekomon leader already fits the swamp and Volume Villa region. |
| 120 | KingSukamon | Filth | 6 | Filth king already agrees with Sukamon's dark and unclean region. |
| 121 | Cherrymon | Nature | 5 | Living forest tree already fits natural wilderness and dislikes industry. |
| 122 | Hagurumon | Mech/Air | 3 | Gear-shaped machine already fits Factorial Town. |
| 123 | Tinmon | Ice/Nature | 1 | The project's Tinmon uses Ice/Nature and a full ice arsenal; cold remains a reasonable identity choice. |
| 124 | MasterTyrannomon | Battle/Fire | 0 | Tyrannomon elder already shares its family's warm dinosaur region. |
| 126 | Brachiomon | Fire/Battle | 0 | Fire/Battle dinosaur already fits the prehistoric region. |
| 180 | Veemon | Battle/Fire | 5 | Generalist dragon Rookie has a reasonable outdoor preference before its elemental branches specialize. |
| 181 | Puppetmon | Nature/Battle/Mech | 5 | Wooden puppet and forest ruler fits natural woodland rather than an industrial machine habitat. |
| 182 | Kimeramon | Fire/Battle | 3 | Artificial composite Digimon has a defensible laboratory and machine affinity. |
| 184 | Hawkmon | Air/Battle | 5 | Bird Rookie fits open wilderness before its aerial evolutions. |
| 185 | Armadillomon | Battle/Nature | 0 | Armored ancient beast has a defensible prehistoric preference despite its Nature specialty. |
| 189 | Ankylomon | Battle/Nature | 5 | Burrowing armored herbivore already fits outdoor terrain. |
| 191 | MetalGarurumon | Ice/Mech/Battle | 1 | Ice-armed wolf keeps the Garurumon line's cold preference despite its mechanization. |
| 194 | ExVeemon | Battle/Fire | 0 | Fire-bearing Veemon evolution reasonably fits the warm dragon branch. |
| 195 | Flamedramon | Fire/Battle | 0 | Flame armor already fits lava and warm places. |
| 200 | Pegasusmon | Air/Battle | 2 | Holy winged horse already agrees with Unimon's sanctuary preference. |
| 202 | Submarimon | Ice/Battle | 4 | Submarine armor already fits water and wetlands. |
| 203 | Veedramon | Fire/Battle | 0 | Fire-bearing Veedramon already fits the warm dragon branch. |
| 205 | MegaKabuterimon | Nature/Fire/Air | 7 | Kabuterimon evolution already fits the beetle family. |
| 221 | Salamon | Battle/Air | 2 | Holy beast Rookie already fits the angel family's sanctuary region. |
| 225 | Shurimon | Battle/Air/Nature | 5 | Plant-armored ninja already fits Ninjamon's natural wilderness. |
| 228 | Baronmon | Fire/Battle | 0 | Fire-wielding masked guardian has a defensible warm-region identity. |
| 230 | Rosemon | Nature/Air | 5 | Rose fairy already continues Palmon's natural region and aversion to industry. |
| 232 | BomberNanimon | Battle/Mech | 5 | Explosive Battle/Machine variant still has a defensible outdoor brawler preference; no forced machine reassignment. |
| 234 | Gatomon | Battle/Air | 5 | Agile feline has a reasonable outdoor beast preference between Salamon and its holy or dark branches. |
| 237 | Diaboromon | Mech/Nature/Battle | 3 | Network-corrupting artificial organism fits a machine region despite its insect-like shape. |
| 238 | Dolphmon | Ice/Air | 4 | Marine dolphin already fits the aquatic region. |
| 239 | Gizamon | Ice/Battle | 4 | Amphibious creature already fits water and wetlands. |
| 241 | Wizardmon | Air/Battle | 0 | Elemental wizard can reasonably prefer warm places; magic alone does not require a holy or dark alignment. |
| 243 | Starmon | Fire/Battle | 0 | Fire/Battle star warrior has a defensible warm preference; space origin alone does not imply a machine habitat. |
| 244 | SuperStarmon | Fire/Battle | 3 | Metal-armored Starmon evolution has a defensible industrial preference. |
| 250 | Shadramon | Fire/Battle | 0 | Flame-armored insect already fits its Fire specialty; armor changes the ordinary beetle preference. |
| 254 | Tylomon | Ice/Battle | 4 | Marine prehistoric predator already fits the aquatic region. |
| 256 | VioletElecmon | Air/Battle | 5 | Elecmon variant already shares its family's open grassland region. |
| 259 | Okuwamon | Nature/Battle/Air | 7 | Stag beetle evolution already agrees with Kuwagamon's insect line. |
| 260 | MetalTyrannomon | Mech/Fire/Battle | 3 | Armed cyborg Tyrannomon already fits the machine branch. |
| 261 | Tortomon | Battle/Nature | 4 | Turtle Digimon has a defensible aquatic preference despite its Battle/Nature specialties. |
| 267 | Mammothmon | Ice/Battle | 1 | Ice-age mammoth already fits cold country. |
| 268 | SkullMammothmon | Ice/Battle | 1 | Undead mammoth retains the icy mammoth lineage; a skeleton need not force a dark-region change. |
| 272 | Woodmon | Nature/Battle | 5 | Living woodland tree already fits natural places and aversion to factories. |
| 275 | Scorpiomon | Ice/Battle/Nature | 4 | Sea scorpion with Ice specialty already fits water rather than ordinary beetle habitat. |
| 279 | MarineDevimon | Ice/Battle | 6 | Deep-sea devil reasonably prioritizes the demon identity and rejection of holy ground over water. |
| 282 | Kiwimon | Nature/Battle | 5 | Flightless woodland bird already fits natural wilderness. |
| 283 | Syakomon | Ice/Battle | 4 | Bivalve sea creature already fits the aquatic region. |
| 289 | ChaosLord | Mech/Battle | 3 | Mechanical composite boss already fits the machine region. |
| 290 | Clockmon | Mech/Battle | 3 | Clockwork timekeeper already fits Factorial Town. |
| 291 | Dragomon | Ice/Battle | 6 | Occult deep-sea creature has a defensible dark preference despite its aquatic identity. |
| 292 | Deltamon | Battle/Fire | 5 | Mutant dinosaur with Battle/Fire has a reasonable outdoor wilderness preference; no forced volcanic reassignment. |
| 293 | Gryphonmon | Air/Battle | 2 | Mythical guardian already fits the sanctuary with Unimon and other sacred aerial beasts. |
| 297 | Marsmon | Battle/Fire | 5 | Beast warrior already fits Leomon-like open wilderness despite Fire as a secondary specialty. |
| 303 | KingEtemon | Battle/Air/Filth | 5 | Etemon king already shares Etemon's outdoor region; royal dress does not make it a machine. |
| 305 | Ebidramon | Ice/Battle | 4 | Marine crustacean already fits water and wetlands. |
| 306 | GrapLeomon | Battle/Air | 5 | Martial lion already shares Leomon's wilderness preference despite mechanical enhancements. |
| 308 | Dinohyumon | Battle/Nature | 5 | Sword-wielding dragon warrior has a reasonable outdoor Battle/Nature identity. |
| 309 | Antylamon | Battle/Air | 5 | Rabbit beast warrior already fits open natural terrain. |
| 315 | Taomon | Fire/Air/Battle | 5 | Fox-line mystic has a reasonable natural wilderness preference. |
| 316 | Sakuyamon | Air/Fire/Battle | 5 | Shrine maiden and fox guardian reasonably retains Renamon and Taomon's natural region. |
| 317 | Fujinmon | Air/Mech/Battle | 3 | Mechanical wind warrior already fits a factory region despite its Air specialty. |
| 320 | Growlmon | Fire/Battle | 0 | Fire-breathing dragon already agrees with Guilmon's warm branch. |
| 321 | Knightmon | Battle/Mech | 3 | Armored weapon-bearing warrior has a defensible metal and machine affinity without an explicit holy identity. |
| 323 | Lynxmon | Fire/Battle | 5 | Flaming lynx canonically inhabits tropical jungle; its existing natural wilderness preference is reasonable without forcing lava. |
| 325 | Musyamon | Battle/Air | 5 | Wooden samurai has a defensible outdoor warrior identity. |
| 326 | WarGrowlmon | Fire/Mech/Battle | 0 | Fire remains the leading identity of Guilmon's armed dragon evolution; the warm line remains reasonable. |
| 330 | Minotarumon | Battle/Nature | 5 | Bull-man brawler already fits natural Battle/Nature terrain. |
| 333 | Raijinmon | Air/Mech/Battle | 3 | Mechanical thunder warrior already fits the machine region. |
| 335 | MegaGargomon | Mech/Battle | 3 | Missile-armed cyborg rabbit already fits the machine region. |
| 351 | Kotemon | Battle/Fire | 5 | Kendo-trained dragon Rookie already has a reasonable outdoor warrior preference. |
| 352 | Monmon | Battle/Air | 5 | Tree-dwelling monkey already fits open natural terrain. |
| 354 | Renamon | Battle/Fire | 5 | Fox mystic already fits natural wilderness and its Taomon/Sakuyamon line. |
| 403 | Beelzemon | Battle/Mech | 5 | Motorcycle-riding demon has a defensible roaming outdoor preference; its name alone does not require reassignment. |
| 433 | Guilmon | Fire/Battle | 0 | Fire-breathing Rookie already begins a coherent warm dragon line. |
| 460 | Garudamon | Fire/Air/Battle | 0 | Fire bird warrior already continues Birdramon's warm preference. |
| 461 | Omnimon | Battle/Ice/Fire | 0 | Fusion retains WarGreymon's Fire alongside MetalGarurumon's Ice; its existing warm preference is a reasonable compromise. |
| 470 | Pabumon | Nature | 8 | Baby I uses the original babies' safe Native Forest region. |
| 471 | Pichimon | Ice | 8 | Aquatic Baby I still follows the original babies' safe-place preference before habitat specialization. |
| 472 | YukimiBotamon | Air | 8 | Baby I retains the original babies' safe Native Forest region despite its snow-like appearance. |
| 473 | Nyokimon | Nature | 8 | Plant Baby I follows Yuramon's safe forest-region pattern. |
| 474 | Motimon | Nature/Mech | 8 | Baby II follows the original babies before machinery or insect specialization. |
| 475 | Bukamon | Ice/Battle | 8 | Aquatic Baby II retains the safe baby region before cold or marine evolutions. |
| 476 | Nyaromon | Battle/Air | 8 | Feline Baby II retains the safe baby region before holy or dark specialization. |
| 477 | Yokomon | Air/Nature | 8 | Plant-bird Baby II retains the safe region before natural or Fire branches. |

## Excluded parallel review

| Id | Species | Region left untouched |
| --- | --- | --- |
| 217 | Gomamon | 5 |
| 218 | Ikkakumon | 4 |
| 219 | Zudomon | 3 |

Only `partner.favored_region` changes in the species JSON. No original partner, fallback identity, evolution edge, specialty, technique, map header, C allocation or record size changes.
