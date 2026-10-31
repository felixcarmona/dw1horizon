# Iron Hills 317: the Seam must not enter the northern regions before the
# original forest rockslide (T106) or the invisible bridge crossing (T103).
# Exit 1 back into the Seam stays unconditional, including for old saves.
from dw import *
from dw.names import *

hills1 = new_screen(317, map="build/what-the-island-forgot-maps/screens/IRON01.MAP")
hills1_psychemon = hills1.npc(Species.Psychemon, at=(-250, -450), hp=900, mp=2300, offense=340, defense=200, speed=240, brain=200, bits=300)
hills1_shamamon = hills1.npc(Species.Shamamon, at=(289, 699), hp=1000, mp=2100, offense=360, defense=180, speed=100, brain=50, bits=300,
                             autotalk=True, when=clock.hour >= 5 and clock.hour < 20)
hills1_gururumon = hills1.npc(Species.Gururumon, at=(-50, 450), hp=1200, mp=2700, offense=400, defense=190, speed=240, brain=200, bits=400,
                              autotalk=True, when=clock.hour >= 20 or clock.hour < 5)

@hills1.on_step(0, when=native_forest_rockslide_cleared or invisible_bridge_crossed)
def down_to_the_savanna():
    warp(Screen.gear_savanna_78, entry=1)

@hills1.on_step(0, when=not native_forest_rockslide_cleared and not invisible_bridge_crossed)
def the_old_road_first():
    tamer.say("The trail's blocked. We should open the road to the savanna first.")
    tamer.walk(119, -1750)
