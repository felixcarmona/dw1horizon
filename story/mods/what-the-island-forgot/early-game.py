# What the island forgot: life on the new screens (more maps, with enemies, with a purpose).
# The screens' maps are built by maps/*.py from the player's disc; this file puts the wild Digimon on them: each one is
# an entry the compiler adds to the mod's own map (species, battle stats, the chasing AI of a wild Digimon), spawned by
# the screen's MAPHEAD setup (by the clock where `when=` says so), with the default wild battle on touch. The stats are
# copied from the wild Digimon of the region each screen borders (`dwmap.py describe`), so a screen fights like its
# neighbours.
from dw import *

# 314, the Root Clearing: two Goblimon from the field next door (MAYO03's).
clearing = new_screen(314, map="build/what-the-island-forgot-maps/screens/ROOT01.MAP")
goblin_east = clearing.npc(Species.Goblimon, at=(1642, 935), hp=400, mp=800, offense=160, defense=70, speed=50, brain=50, bits=300)
goblin_south = clearing.npc(Species.Goblimon, at=(750, -850), hp=400, mp=800, offense=160, defense=70, speed=50, brain=50, bits=300)

# 317, the first Iron Hills screen (the Seam Pass, Z1): the savanna's Psychemon always and Shamamon by day (GIAS01's
# stats), and at night the first hunter, a Gururumon (GCAN09's stats), in Shamamon's place. (The screen file's tims4
# must match the donor's map: a wrong count made the engine read a TIM that is not there and the player arrived with no
# position, 2026-10-21.)
hills1 = new_screen(317, map="build/what-the-island-forgot-maps/screens/IRON01.MAP")
hills1_psychemon = hills1.npc(Species.Psychemon, at=(-250, -450), hp=900, mp=2300, offense=340, defense=200, speed=240, brain=200, bits=300)
hills1_shamamon = hills1.npc(Species.Shamamon, at=(289, 699), hp=1000, mp=2100, offense=360, defense=180, speed=100, brain=50, bits=300,
                             autotalk=True, when=clock.hour >= 5 and clock.hour < 20)
hills1_gururumon = hills1.npc(Species.Gururumon, at=(-50, 450), hp=1200, mp=2700, offense=400, defense=190, speed=240, brain=200, bits=400,
                              autotalk=True, when=clock.hour >= 20 or clock.hour < 5)

# 318, the second Iron Hills screen: the same roster as 317 (Psychemon always, Shamamon by day, Gururumon by night).
hills2 = new_screen(318, map="build/what-the-island-forgot-maps/screens/IRON02.MAP")
hills2_psychemon = hills2.npc(Species.Psychemon, at=(-350, -350), hp=900, mp=2300, offense=340, defense=200, speed=240, brain=200, bits=300)
hills2_shamamon = hills2.npc(Species.Shamamon, at=(350, -450), hp=1000, mp=2100, offense=360, defense=180, speed=100, brain=50, bits=300,
                             autotalk=True, when=clock.hour >= 5 and clock.hour < 20)
hills2_gururumon = hills2.npc(Species.Gururumon, at=(950, -550), hp=1200, mp=2700, offense=400, defense=190, speed=240, brain=200, bits=400,
                              autotalk=True, when=clock.hour >= 20 or clock.hour < 5)

# 319, the third Iron Hills screen (the zigzag climb): the same roster, one per leg, with a short chase range (400): the
# legs lie one above the other and a chase across the terrace face starts a battle the two cannot fight (2026-10-21).
hills3 = new_screen(319, map="build/what-the-island-forgot-maps/screens/IRON03.MAP")
hills3_psychemon = hills3.npc(Species.Psychemon, at=(-120, 326), hp=900, mp=2300, offense=340, defense=200, speed=240, brain=200, bits=300, range=400)
hills3_shamamon = hills3.npc(Species.Shamamon, at=(650, -1150), hp=1000, mp=2100, offense=360, defense=180, speed=100, brain=50, bits=300, range=400,
                             autotalk=True, when=clock.hour >= 5 and clock.hour < 20)
hills3_gururumon = hills3.npc(Species.Gururumon, at=(250, 2450), hp=1200, mp=2700, offense=400, defense=190, speed=240, brain=200, bits=400, range=400,
                              autotalk=True, when=clock.hour >= 20 or clock.hour < 5)

# 320, the fourth Iron Hills screen (the ridge): the same roster, spread over the plateau.
hills4 = new_screen(320, map="build/what-the-island-forgot-maps/screens/IRON04.MAP")
hills4_psychemon = hills4.npc(Species.Psychemon, at=(-27, 1269), hp=900, mp=2300, offense=340, defense=200, speed=240, brain=200, bits=300)
hills4_shamamon = hills4.npc(Species.Shamamon, at=(-550, -750), hp=1000, mp=2100, offense=360, defense=180, speed=100, brain=50, bits=300,
                             autotalk=True, when=clock.hour >= 5 and clock.hour < 20)
hills4_gururumon = hills4.npc(Species.Gururumon, at=(950, -850), hp=1200, mp=2700, offense=400, defense=190, speed=240, brain=200, bits=400,
                              autotalk=True, when=clock.hour >= 20 or clock.hour < 5)

# 321, the fifth Iron Hills screen (the far slope): the same roster; the Gururumon stands by the grey blocks at night.
hills5 = new_screen(321, map="build/what-the-island-forgot-maps/screens/IRON05.MAP")
hills5_psychemon = hills5.npc(Species.Psychemon, at=(106, 1269), hp=900, mp=2300, offense=340, defense=200, speed=240, brain=200, bits=300)
hills5_shamamon = hills5.npc(Species.Shamamon, at=(-432, -1063), hp=1000, mp=2100, offense=360, defense=180, speed=100, brain=50, bits=300,
                             autotalk=True, when=clock.hour >= 5 and clock.hour < 20)
hills5_gururumon = hills5.npc(Species.Gururumon, at=(350, -650), hp=1200, mp=2700, offense=400, defense=190, speed=240, brain=200, bits=400,
                              autotalk=True, when=clock.hour >= 20 or clock.hour < 5)

# 322, the Brink (the last Iron Hills screen): the same roster; the Gururumon stands by the crack at night.
brink = new_screen(322, map="build/what-the-island-forgot-maps/screens/IRON06.MAP")
brink_psychemon = brink.npc(Species.Psychemon, at=(-528, 699), hp=900, mp=2300, offense=340, defense=200, speed=240, brain=200, bits=300)
brink_shamamon = brink.npc(Species.Shamamon, at=(350, -1150), hp=1000, mp=2100, offense=360, defense=180, speed=100, brain=50, bits=300,
                           autotalk=True, when=clock.hour >= 5 and clock.hour < 20)
brink_gururumon = brink.npc(Species.Gururumon, at=(750, -1650), hp=1200, mp=2700, offense=400, defense=190, speed=240, brain=200, bits=400,
                            autotalk=True, when=clock.hour >= 20 or clock.hour < 5)

# Zone 2, the Seam: Analogman's hunters use it as their road. The roster is zone 1's (Psychemon always, Shamamon by day,
# Gururumon by night), the three species whose fights were seen to end. The bible's hunters (DarkLizardmon by day, the
# Overdell stats) can take Shamamon's place after one test fight: the 2026-10-21 crashes blamed on it were the executable
# (patch 0160, the background stream reopening during a fight), not the species. (A fourth species per screen put the heap
# at 253 of 192 KB: three models per screen is the limit of this roster.)
seam1 = new_screen(323, map="build/what-the-island-forgot-maps/screens/SEAM01.MAP")
seam1_psychemon = seam1.npc(Species.Psychemon, at=(-50, 250), hp=900, mp=2300, offense=340, defense=200, speed=240, brain=200, bits=300)
seam1_shamamon = seam1.npc(Species.Shamamon, at=(1090, -1138), hp=1000, mp=2100, offense=360, defense=180, speed=100, brain=50, bits=300,
                 autotalk=True, when=clock.hour >= 5 and clock.hour < 20)
seam1_gururumon = seam1.npc(Species.Gururumon, at=(750, -1350), hp=1200, mp=2700, offense=400, defense=190, speed=240, brain=200, bits=400,
                            autotalk=True, when=clock.hour >= 20 or clock.hour < 5)

# 324, the ice shelf: the same roster as 323.
seam2 = new_screen(324, map="build/what-the-island-forgot-maps/screens/SEAM02.MAP")
seam2_psychemon = seam2.npc(Species.Psychemon, at=(-550, 450), hp=900, mp=2300, offense=340, defense=200, speed=240, brain=200, bits=300)
seam2_shamamon = seam2.npc(Species.Shamamon, at=(1050, -1150), hp=1000, mp=2100, offense=360, defense=180, speed=100, brain=50, bits=300,
                 autotalk=True, when=clock.hour >= 5 and clock.hour < 20)
seam2_gururumon = seam2.npc(Species.Gururumon, at=(650, -550), hp=1200, mp=2700, offense=400, defense=190, speed=240, brain=200, bits=400,
                            autotalk=True, when=clock.hour >= 20 or clock.hour < 5)

# 325, the kennel: its own file (arcs/seam/kennel.py), the named hunter's scripted fight.

# 326, CAMP 2: its own file (arcs/seam/camp2.py), with the camp's notebook.

# 327, the gallery: the Seam's roster.
seam4 = new_screen(327, map="build/what-the-island-forgot-maps/screens/SEAM05.MAP")
seam4_psychemon = seam4.npc(Species.Psychemon, at=(50, 650), hp=900, mp=2300, offense=340, defense=200, speed=240, brain=200, bits=300)
seam4_shamamon = seam4.npc(Species.Shamamon, at=(-950, -1150), hp=1000, mp=2100, offense=360, defense=180, speed=100, brain=50, bits=300,
                 autotalk=True, when=clock.hour >= 5 and clock.hour < 20)
seam4_gururumon = seam4.npc(Species.Gururumon, at=(-950, -750), hp=1200, mp=2700, offense=400, defense=190, speed=240, brain=200, bits=400,
                            autotalk=True, when=clock.hour >= 20 or clock.hour < 5)

# 329, the great weld: the Seam's roster, the Gururumon by night on the orange side.
seam5 = new_screen(329, map="build/what-the-island-forgot-maps/screens/SEAM07.MAP")
seam5_psychemon = seam5.npc(Species.Psychemon, at=(-650, -650), hp=900, mp=2300, offense=340, defense=200, speed=240, brain=200, bits=300)
seam5_shamamon = seam5.npc(Species.Shamamon, at=(1090, 202), hp=1000, mp=2100, offense=360, defense=180, speed=100, brain=50, bits=300,
                 autotalk=True, when=clock.hour >= 5 and clock.hour < 20)
seam5_gururumon = seam5.npc(Species.Gururumon, at=(750, 450), hp=1200, mp=2700, offense=400, defense=190, speed=240, brain=200, bits=400,
                            autotalk=True, when=clock.hour >= 20 or clock.hour < 5)

# Zone 3, the way down to Overdell: the same trio for now (Gururumon always, Psychemon by day, Shamamon by night). Overdell's
# own roster (DGHA01's stats: DarkLizardmon always, Bakemon by day) goes in after one test fight each (see zone 2).
descent1 = new_screen(330, map="build/what-the-island-forgot-maps/screens/OVPS01.MAP")
descent1_gururumon = descent1.npc(Species.Gururumon, at=(-150, 450), hp=1200, mp=2700, offense=400, defense=190, speed=240, brain=200, bits=400)
descent1_psychemon = descent1.npc(Species.Psychemon, at=(-1050, -1450), hp=900, mp=2300, offense=340, defense=200, speed=240, brain=200, bits=300,
                     autotalk=True, when=clock.hour >= 5 and clock.hour < 20)
descent1_shamamon = descent1.npc(Species.Shamamon, at=(-650, -950), hp=1000, mp=2100, offense=360, defense=180, speed=100, brain=50, bits=300,
                    autotalk=True, when=clock.hour >= 20 or clock.hour < 5)

# 331, the dry riverbed: Overdell's roster.
descent2 = new_screen(331, map="build/what-the-island-forgot-maps/screens/OVPS02.MAP")
descent2_gururumon = descent2.npc(Species.Gururumon, at=(-50, 150), hp=1200, mp=2700, offense=400, defense=190, speed=240, brain=200, bits=400)
descent2_psychemon = descent2.npc(Species.Psychemon, at=(-50, -750), hp=900, mp=2300, offense=340, defense=200, speed=240, brain=200, bits=300,
                     autotalk=True, when=clock.hour >= 5 and clock.hour < 20)
descent2_shamamon = descent2.npc(Species.Shamamon, at=(-650, -650), hp=1000, mp=2100, offense=360, defense=180, speed=100, brain=50, bits=300,
                    autotalk=True, when=clock.hour >= 20 or clock.hour < 5)

# 332, the terraces: Overdell's roster.
descent3 = new_screen(332, map="build/what-the-island-forgot-maps/screens/OVPS03.MAP")
descent3_gururumon = descent3.npc(Species.Gururumon, at=(0, 500), hp=1200, mp=2700, offense=400, defense=190, speed=240, brain=200, bits=400)
descent3_psychemon = descent3.npc(Species.Psychemon, at=(-1050, -1150), hp=900, mp=2300, offense=340, defense=200, speed=240, brain=200, bits=300,
                     autotalk=True, when=clock.hour >= 5 and clock.hour < 20)
descent3_shamamon = descent3.npc(Species.Shamamon, at=(-650, -650), hp=1000, mp=2100, offense=360, defense=180, speed=100, brain=50, bits=300,
                    autotalk=True, when=clock.hour >= 20 or clock.hour < 5)

# 333, the narrows: Overdell's roster.
descent4 = new_screen(333, map="build/what-the-island-forgot-maps/screens/OVPS04.MAP")
descent4_gururumon = descent4.npc(Species.Gururumon, at=(50, 300), hp=1200, mp=2700, offense=400, defense=190, speed=240, brain=200, bits=400)
descent4_psychemon = descent4.npc(Species.Psychemon, at=(-1050, -1150), hp=900, mp=2300, offense=340, defense=200, speed=240, brain=200, bits=300,
                     autotalk=True, when=clock.hour >= 5 and clock.hour < 20)
descent4_shamamon = descent4.npc(Species.Shamamon, at=(-550, -650), hp=1000, mp=2100, offense=360, defense=180, speed=100, brain=50, bits=300,
                    autotalk=True, when=clock.hour >= 20 or clock.hour < 5)

# 334, the standing stones: Overdell's roster.
descent5 = new_screen(334, map="build/what-the-island-forgot-maps/screens/OVPS05.MAP")
descent5_gururumon = descent5.npc(Species.Gururumon, at=(72, 405), hp=1200, mp=2700, offense=400, defense=190, speed=240, brain=200, bits=400)
descent5_psychemon = descent5.npc(Species.Psychemon, at=(-656, -716), hp=900, mp=2300, offense=340, defense=200, speed=240, brain=200, bits=300,
                     autotalk=True, when=clock.hour >= 5 and clock.hour < 20)
descent5_shamamon = descent5.npc(Species.Shamamon, at=(1050, -1250), hp=1000, mp=2100, offense=360, defense=180, speed=100, brain=50, bits=300,
                    autotalk=True, when=clock.hour >= 20 or clock.hour < 5)

# 335, the last descent: Overdell's roster; three arrivals (the top, Overdell below, the ossuary's cave) leave no spot
# a full tracking range away, so the ranges are shorter (tools/dws.py check-spawns).
descent6 = new_screen(335, map="build/what-the-island-forgot-maps/screens/OVPS06.MAP")
descent6_gururumon = descent6.npc(Species.Gururumon, at=(450, 1250), hp=1200, mp=2700, offense=400, defense=190, speed=240, brain=200, bits=400)
descent6_psychemon = descent6.npc(Species.Psychemon, at=(450, 1900), hp=900, mp=2300, offense=340, defense=200, speed=240, brain=200, bits=300,
                     autotalk=True, when=clock.hour >= 5 and clock.hour < 20)
descent6_shamamon = descent6.npc(Species.Shamamon, at=(-1150, -950), hp=1000, mp=2100, offense=360, defense=180, speed=100, brain=50, bits=300,
                    autotalk=True, when=clock.hour >= 20 or clock.hour < 5)

# 336, the ossuary: the hunters' dumping ground. A Bakemon haunts it at every hour (Overdell's native ghost).
ossuary = new_screen(336, map="build/what-the-island-forgot-maps/screens/OVPS07.MAP")
ossuary_gururumon = ossuary.npc(Species.Gururumon, at=(-23, -1649), hp=1200, mp=2700, offense=400, defense=190, speed=240, brain=200, bits=400)

# The Galleries arc (design/arc-galleries.md). 337, the Mine Head: the first crossing (four exits), so two wild Digimon
# of short range near the hall's middle (the arrival rule: range + 300 from every arrival); Goblimon with the Drill
# Tunnel's Goburimon stats until the mine's own roster (Gotsumon, Mojyamon, Drimogemon) passes a test fight each.
mine_head = new_screen(337, map="build/what-the-island-forgot-maps/screens/MINE01.MAP")
mine_head_goblin_a = mine_head.npc(Species.Goblimon, at=(-300, 300), hp=400, mp=800, offense=160, defense=70, speed=50, brain=50, bits=300, range=500)
mine_head_goblin_b = mine_head.npc(Species.Goblimon, at=(-900, -600), hp=400, mp=800, offense=160, defense=70, speed=50, brain=50, bits=300, range=500)

# 338, Gallery North I: the upper galleries' roster (Goburimon, Gotsumon, Mojyamon in the design) once each passes a test
# fight; Goblimon with the Drill Tunnel's stats meanwhile, two of them, chasing.
gallery_n1 = new_screen(338, map="build/what-the-island-forgot-maps/screens/MINE02.MAP")
gallery_n1_goblin_a = gallery_n1.npc(Species.Goblimon, at=(200, 400), hp=400, mp=800, offense=160, defense=70, speed=50, brain=50, bits=300)
gallery_n1_goblin_b = gallery_n1.npc(Species.Goblimon, at=(-300, 2200), hp=400, mp=800, offense=160, defense=70, speed=50, brain=50, bits=300)

# 342, the Flooded Gallery: few and slow (the design's Numemon and Gesomon wait for a test fight): one Goblimon, one Psychemon.
flooded = new_screen(342, map="build/what-the-island-forgot-maps/screens/MINE03.MAP")
flooded_goblin = flooded.npc(Species.Goblimon, at=(-350, -850), hp=400, mp=800, offense=160, defense=70, speed=50, brain=50, bits=300)
flooded_psychemon = flooded.npc(Species.Psychemon, at=(250, 50), hp=900, mp=2300, offense=340, defense=200, speed=240, brain=200, bits=300)

# 348, the Great Chamber: the second crossing (four exits): two strong ones of short range in the hall's halves.
chamber = new_screen(348, map="build/what-the-island-forgot-maps/screens/MINE05.MAP")
chamber_psychemon = chamber.npc(Species.Psychemon, at=(-1350, -250), hp=900, mp=2300, offense=340, defense=200, speed=240, brain=200, bits=300, range=600)
chamber_gururumon = chamber.npc(Species.Gururumon, at=(1400, -500), hp=1200, mp=2700, offense=400, defense=190, speed=240, brain=200, bits=400, range=600)

# 349, the Bridge: one Psychemon on the planks (a fight on a bridge).
bridge = new_screen(349, map="build/what-the-island-forgot-maps/screens/MINE04.MAP")
bridge_psychemon = bridge.npc(Species.Psychemon, at=(300, 250), hp=900, mp=2300, offense=340, defense=200, speed=240, brain=200, bits=300, range=800)

# 339, Gallery North II (the narrows): two Goblimon, one before the rock falls and one past them.
gallery_n2 = new_screen(339, map="build/what-the-island-forgot-maps/screens/MINE06.MAP")
gallery_n2_goblin_a = gallery_n2.npc(Species.Goblimon, at=(-100, -400), hp=400, mp=800, offense=160, defense=70, speed=50, brain=50, bits=300)
gallery_n2_goblin_b = gallery_n2.npc(Species.Goblimon, at=(100, 2600), hp=400, mp=800, offense=160, defense=70, speed=50, brain=50, bits=300)

# 340, the Cart Hall (the roundhouse, three exits): two of short range by the turntable.
cart_hall = new_screen(340, map="build/what-the-island-forgot-maps/screens/MINE07.MAP")
cart_hall_goblin = cart_hall.npc(Species.Goblimon, at=(-150, -250), hp=400, mp=800, offense=160, defense=70, speed=50, brain=50, bits=300, range=500)
cart_hall_psychemon = cart_hall.npc(Species.Psychemon, at=(900, 100), hp=900, mp=2300, offense=340, defense=200, speed=240, brain=200, bits=300, range=500)

# 341, Gallery West I (the damp one): one Goblimon and one Psychemon.
gallery_w1 = new_screen(341, map="build/what-the-island-forgot-maps/screens/MINE08.MAP")
gallery_w1_goblin = gallery_w1.npc(Species.Goblimon, at=(50, -150), hp=400, mp=800, offense=160, defense=70, speed=50, brain=50, bits=300)
gallery_w1_psychemon = gallery_w1.npc(Species.Psychemon, at=(50, -950), hp=900, mp=2300, offense=340, defense=200, speed=240, brain=200, bits=300)

# 343, Gallery West II (the climb): two Goblimon.
gallery_w2 = new_screen(343, map="build/what-the-island-forgot-maps/screens/MINE09.MAP")
gallery_w2_goblin_a = gallery_w2.npc(Species.Goblimon, at=(200, 0), hp=400, mp=800, offense=160, defense=70, speed=50, brain=50, bits=300)
gallery_w2_goblin_b = gallery_w2.npc(Species.Goblimon, at=(-200, 2400), hp=400, mp=800, offense=160, defense=70, speed=50, brain=50, bits=300)

# 344, the Sunken Gallery (the roof fall): one Goblimon at each side of the narrows.
sunken = new_screen(344, map="build/what-the-island-forgot-maps/screens/MINE10.MAP")
sunken_goblin_a = sunken.npc(Species.Goblimon, at=(-550, -50), hp=400, mp=800, offense=160, defense=70, speed=50, brain=50, bits=300, range=700)
sunken_goblin_b = sunken.npc(Species.Goblimon, at=(950, -450), hp=400, mp=800, offense=160, defense=70, speed=50, brain=50, bits=300, range=700)

# 345, Gallery East (the signpost): two Goblimon.
gallery_e = new_screen(345, map="build/what-the-island-forgot-maps/screens/MINE11.MAP")
gallery_e_goblin_a = gallery_e.npc(Species.Goblimon, at=(-550, -350), hp=400, mp=800, offense=160, defense=70, speed=50, brain=50, bits=300)
gallery_e_goblin_b = gallery_e.npc(Species.Goblimon, at=(550, -450), hp=400, mp=800, offense=160, defense=70, speed=50, brain=50, bits=300)

# 346, the Workshop (CAMP 1): one Psychemon prowling the camp; the ledger and the chests are story work.
workshop = new_screen(346, map="build/what-the-island-forgot-maps/screens/MINE12.MAP")
workshop_psychemon = workshop.npc(Species.Psychemon, at=(550, 250), hp=900, mp=2300, offense=340, defense=200, speed=240, brain=200, bits=300, range=800)

# 347, the Workshop Gallery (the ramp down to the chamber): two Goblimon.
workshop_g = new_screen(347, map="build/what-the-island-forgot-maps/screens/MINE13.MAP")
workshop_g_goblin_a = workshop_g.npc(Species.Goblimon, at=(-100, 2800), hp=400, mp=800, offense=160, defense=70, speed=50, brain=50, bits=300)
workshop_g_goblin_b = workshop_g.npc(Species.Goblimon, at=(150, -200), hp=400, mp=800, offense=160, defense=70, speed=50, brain=50, bits=300)

# 350, the High Gallery (between the bridge and the chamber): a Psychemon and a Goblimon.
high_g = new_screen(350, map="build/what-the-island-forgot-maps/screens/MINE14.MAP")
high_g_psychemon = high_g.npc(Species.Psychemon, at=(100, 2600), hp=900, mp=2300, offense=340, defense=200, speed=240, brain=200, bits=300)
high_g_goblin = high_g.npc(Species.Goblimon, at=(-100, -300), hp=400, mp=800, offense=160, defense=70, speed=50, brain=50, bits=300)

# 351, Gallery East II (where the rubbish begins): the dump's roster (Sukamon, Geremon in the design) waits for a test fight;
# a Goblimon and a Psychemon meanwhile.
gallery_e2 = new_screen(351, map="build/what-the-island-forgot-maps/screens/MINE15.MAP")
gallery_e2_goblin = gallery_e2.npc(Species.Goblimon, at=(-550, -350), hp=400, mp=800, offense=160, defense=70, speed=50, brain=50, bits=300)
gallery_e2_psychemon = gallery_e2.npc(Species.Psychemon, at=(550, -250), hp=900, mp=2300, offense=340, defense=200, speed=240, brain=200, bits=300)

# 352, the Rubbish Gallery (the dump): a Goblimon and a Psychemon (Sukamon and Geremon wait for a test fight).
rubbish_g = new_screen(352, map="build/what-the-island-forgot-maps/screens/MINE16.MAP")
rubbish_g_goblin = rubbish_g.npc(Species.Goblimon, at=(-550, -250), hp=400, mp=800, offense=160, defense=70, speed=50, brain=50, bits=300)
rubbish_g_psychemon = rubbish_g.npc(Species.Psychemon, at=(550, -150), hp=900, mp=2300, offense=340, defense=200, speed=240, brain=200, bits=300)

# 353, the Rubbish Mouth (the ladder up to Trash Mountain): one Psychemon by the ladder.
rubbish_m = new_screen(353, map="build/what-the-island-forgot-maps/screens/MINE17.MAP")
rubbish_m_psychemon = rubbish_m.npc(Species.Psychemon, at=(-350, -350), hp=900, mp=2300, offense=340, defense=200, speed=240, brain=200, bits=300, range=800)

# 354, the Stair (down to the heart): the deep roster (Tsukaimon, Bakemon, Soulmon in the design) waits for a test fight;
# a Gururumon meanwhile, at the steps.
stair = new_screen(354, map="build/what-the-island-forgot-maps/screens/MINE18.MAP")
stair_gururumon = stair.npc(Species.Gururumon, at=(0, 400), hp=1200, mp=2700, offense=400, defense=190, speed=240, brain=200, bits=400, range=800)

# 355, the Heart of the Mine: the guardian (an old Drimogemon with a scripted fight, flag G) is story work; a Gururumon
# of short range keeps the face meanwhile.
heart = new_screen(355, map="build/what-the-island-forgot-maps/screens/MINE19.MAP")
heart_gururumon = heart.npc(Species.Gururumon, at=(300, -500), hp=1200, mp=2700, offense=400, defense=190, speed=240, brain=200, bits=400, range=600)

# 356, the Drain (up to Factorial Town's sewer, 220): one Gururumon on the walkway (Numemon and Nanimon wait for a test fight).
drain = new_screen(356, map="build/what-the-island-forgot-maps/screens/MINE20.MAP")
drain_gururumon = drain.npc(Species.Gururumon, at=(-100, -300), hp=1200, mp=2700, offense=400, defense=190, speed=240, brain=200, bits=400, range=800)

# --- File City's new district, the Works (design/district-proposals.md, concept 3): two outdoor screens behind the lower
# town and seven buildings, each a file of its own (district/*.py). Its residents are the recruits the game already makes
# on wild fights (recruitable(...)) but never housed.
