# Overdell Pass 335: keep the original first crossing into the jungle (Coelamon,
# the repaired bridge, the invisible bridge, or the postgame mansion portal).
# A save stranded in the Seam with NEITHER original road opened predates these
# gates. Let it leave through Overdell; fresh games cannot enter the Seam in that
# state. Otherwise a player entering from the north can always return north.
from dw import *
from dw.names import *

descent6 = new_screen(335, map="build/what-the-island-forgot-maps/screens/OVPS06.MAP")
descent6_skullsatamon = descent6.npc(Species.SkullSatamon, at=(450, 1250), hp=4500, mp=4200, offense=640, defense=360, speed=320, brain=300, bits=2200)
descent6_gargoylemon = descent6.npc(Species.Gargoylemon, at=(450, 1900), hp=3600, mp=3600, offense=580, defense=320, speed=300, brain=200, bits=1600,
                                    autotalk=True, when=clock.hour >= 5 and clock.hour < 20)
descent6_weregarurumon = descent6.npc(Species.WereGarurumon, at=(-1150, -950), hp=4400, mp=4000, offense=660, defense=350, speed=340, brain=300, bits=2200,
                                      autotalk=True, when=clock.hour >= 20 or clock.hour < 5)

@descent6.on_step(0, when=not native_forest_rockslide_cleared or invisible_bridge_crossed or eastern_bridge_seen or coela_point_crossing_done or (engine.game_beaten and back_dimension_portal == 2))
def down_to_overdell():
    warp(Screen.overdell, entry=3)

@descent6.on_step(0, when=native_forest_rockslide_cleared and not invisible_bridge_crossed and not eastern_bridge_seen and not coela_point_crossing_done and not (engine.game_beaten and back_dimension_portal == 2))
def the_jungle_road_first():
    tamer.say("The lower trail is blocked. We need to open the way through the jungle first.")
    tamer.walk(112, -2150, camera=True)
