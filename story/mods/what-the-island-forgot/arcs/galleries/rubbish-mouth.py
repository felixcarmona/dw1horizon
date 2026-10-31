# The Rubbish Mouth (353): the Galleries must not open the northern regions
# before either original road: the forest rockslide (T106) or the invisible bridge
# (T103). The mineward exit stays open, including for saves made beyond the hatch.
from dw import *
from dw.names import *

rubbish_m = new_screen(353, map="build/what-the-island-forgot-maps/screens/MINE17.MAP")
rubbish_m_psychemon = rubbish_m.npc(Species.Psychemon, at=(-350, -350), hp=900, mp=2300, offense=340, defense=200, speed=240, brain=200, bits=300, range=800)

@rubbish_m.on_step(0, when=native_forest_rockslide_cleared or invisible_bridge_crossed)
def up_to_trash_mountain():
    warp(Screen.trash_mountain_165, entry=1)

@rubbish_m.on_step(0, when=not native_forest_rockslide_cleared and not invisible_bridge_crossed)
def closed_hatch():
    tamer.say("The hatch won't budge. Maybe the road above has to open first.")
    tamer.walk(748, -1582)
