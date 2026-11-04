# 326, CAMP 2 (design/arc-seam.md §2): the Seam's roster (IceLeomon always, Sorcermon by day, IceDevimon by night), the
# camp's latrine (maps/toilets.py) and its broken notebook in the human hand of the page the Market Manager sells (§3.1c).
# Not a memory fragment: three lines of the human crossing, read the first time the tamer comes by.
from dw import *

seam3 = new_screen(326, map="build/what-the-island-forgot-maps/screens/SEAM04.MAP")
chest_camp2 = flag()
seam3_iceleomon = seam3.npc(Species.IceLeomon, at=(650, 250), hp=4200, mp=4000, offense=600, defense=360, speed=300, brain=280, bits=2000)
seam3_sorcermon = seam3.npc(Species.Sorcermon, at=(-750, -950), hp=3200, mp=4800, offense=560, defense=280, speed=280, brain=300, bits=1500,
                            autotalk=True, when=clock.hour >= 5 and clock.hour < 20)
seam3_icedevimon = seam3.npc(Species.IceDevimon, at=(-750, -550), hp=3900, mp=4600, offense=620, defense=360, speed=200, brain=150, bits=1500,
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
