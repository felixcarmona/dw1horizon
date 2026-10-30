# The Python view of script 16 of DG.SCN: screen 15 Mangrove Region.
# Made from the disc by `dws story-base`; the source of the story since 2026-10-15: edit it (no file = no script). Keys only, never the
# game's words. `story-build` reads this file (lowered); the DWS beside it is the proven intermediate; mods import `dw.base`.
from dw import *
from dw.text import text

region = screen(Screen.mangrove_region_15)
betamon = region.npc(Species.Betamon128, slot=0)
modokibetamon = region.npc(Species.ModokiBetamon, slot=1)
j_mojyamon = region.npc(Species.JMojyamon, slot=2)
slot3 = region.npc(None, slot=3)    # the .MAP has Tsukaimon here; the script spawns what stands here
t5 = text.s016.sec5
t6 = text.s016.sec6
t7 = text.s016.sec7
t8 = text.s016.sec8

@region.on_enter
def enter():    # section 254
    roll = random.roll(99)
    if roll <= 9:
        spawn_item(Item.Digimushrm, at=(-2650, 1850))
    roll = random.roll(99)
    if roll <= 3:
        spawn_item(Item.Happymushrm, at=(1750, 250))

@betamon.on_talk
def talk():    # section 5
    say(t5.u0)
    tamer.play(16)
    say(t5.u1)
    sound(8, 0)
    tamer.face(partner)
    partner.face(tamer)
    wait(1000)
    tamer.say(t5.u2)
    say(t5.u3)
    tamer.face(betamon)
    partner.face(betamon)
    tamer.arrived()
    tamer.say(t5.u4)
    say(t5.u5)
    tamer.play(19)
    tamer.say(t5.u6)
    sound(8, 4)
    say(t5.u7)
    walk_away(421, -1390, looks=10, pause=500)
    send_to_city(line=t5.u8, species=Species.Betamon, sound=(8, 3), camera=False)
    camera.on(tamer, speed=10)
    camera.arrived()

@modokibetamon.on_talk
def talk():    # section 6
    recruitable(modokibetamon, line=t6.u0)

@j_mojyamon.on_talk
def talk():    # section 7
    recruitable(j_mojyamon, line=t7.u0)

@slot3.on_talk
def talk():    # section 8
    recruitable(slot3, line=t8.u0, joins=Species.Tsukaimon)
    return

# the section table, in the order of the original header
sections(254, 5, 6, 7, 8)
