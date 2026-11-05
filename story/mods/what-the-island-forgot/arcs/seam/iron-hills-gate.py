# Iron Hills 317: the Seam must not enter the northern regions before the
# original forest rockslide (T106) or the invisible bridge crossing (T103).
# Exit 1 back into the Seam stays unconditional, including for old saves.
from dw import *
from dw.names import *

hills1 = new_screen(317, map="build/what-the-island-forgot-maps/screens/IRON01.MAP")
hills1_assaultmon = hills1.npc(Species.Assaultmon, at=(-250, -450), hp=3800, mp=3600, offense=560, defense=330, speed=260, brain=250, bits=1800)
hills1_tankmon = hills1.npc(Species.Tankmon, at=(289, 699), hp=4000, mp=2300, offense=530, defense=280, speed=120, brain=50, bits=1400,
                            autotalk=True, when=clock.hour >= 5 and clock.hour < 20)
hills1_guardromon = hills1.npc(Species.Guardromon, at=(-50, 450), hp=3200, mp=3800, offense=600, defense=340, speed=120, brain=80, bits=1300,
                               autotalk=True, when=clock.hour >= 20 or clock.hour < 5)

@hills1.on_step(0, when=native_forest_rockslide_cleared or invisible_bridge_crossed)
def down_to_the_savanna():
    warp(Screen.gear_savanna_78, entry=1)

@hills1.on_step(0, when=not native_forest_rockslide_cleared and not invisible_bridge_crossed)
def the_old_road_first():
    tamer.say("The trail's blocked. We should open the road to the savanna first.")
    tamer.walk(119, -1750, camera=True)


# Screens with scene handlers have empty default talk sections; wild encounters need their own handlers.
@hills1_assaultmon.on_talk
def fight_assaultmon():
    say("Grrr!")
    fight()

@hills1_tankmon.on_talk
def fight_tankmon():
    say("Grrr!")
    fight()

@hills1_guardromon.on_talk
def fight_guardromon():
    say("Grrr!")
    fight()
