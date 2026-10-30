# 326, CAMP 2 (design/arc-seam.md §2): the Seam's roster (Psychemon always, Shamamon by day, Gururumon by night), and the camp's
# broken notebook in the human hand of the page the Market Manager sells (§3.1c). Not a memory fragment: three lines of
# the human crossing, read the first time the tamer comes by.
from dw import *

seam3 = new_screen(326, map="build/what-the-island-forgot-maps/screens/SEAM04.MAP")
chest_camp2 = flag()
seam3_psychemon = seam3.npc(Species.Psychemon, at=(650, 250), hp=900, mp=2300, offense=340, defense=200, speed=240, brain=200, bits=300)
seam3_shamamon = seam3.npc(Species.Shamamon, at=(-750, -950), hp=1000, mp=2100, offense=360, defense=180, speed=100, brain=50, bits=300,
                 autotalk=True, when=clock.hour >= 5 and clock.hour < 20)
seam3_gururumon = seam3.npc(Species.Gururumon, at=(-750, -550), hp=1200, mp=2700, offense=400, defense=190, speed=240, brain=200, bits=400,
                            autotalk=True, when=clock.hour >= 20 or clock.hour < 5)
camp_read = flag()

@seam3.on_enter
def the_camp_notebook():
    spawn_chest(Item.MedRecovery, at=(300, -300), opened=chest_camp2)
    if not camp_read:
        tamer.say("A tent, crates, a rusty generator... Somebody camped here. A long time ago.")
        tamer.say("A notebook in the crate. Human writing again, but most of it's torn out.")
        tamer.say("\"Day 40. The ground changes here. It did not, last year.\"")
        tamer.say("\"Day 41. Half the crates gone. Nobody heard a thing.\"", "\"Day 43. We go on north. CAMP 3 is under the plateau.\"")
        camp_read.set()
