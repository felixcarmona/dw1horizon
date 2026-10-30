# The Python view of script 76 of DG.SCN: screen 79 Ancient Dino Region.
# Made from the disc by `dws story-base`; the source of the story since 2026-10-15: edit it (no file = no script). Keys only, never the
# game's words. `story-build` reads this file (lowered); the DWS beside it is the proven intermediate; mods import `dw.base`.
from dw import *
from dw.text import text
from dw.names import *

region = screen(Screen.ancient_dino_region)
tyrannomon = region.npc(Species.Tyrannomon132, slot=0)
vermilimon1 = region.npc(Species.Vermilimon, slot=1)
vermilimon2 = region.npc(Species.Vermilimon, slot=2)
yanmamon3 = region.npc(Species.Yanmamon, slot=3)
yanmamon4 = region.npc(Species.Yanmamon, slot=4)
t51 = text.s076.sec51
t6 = text.s076.sec6
t7 = text.s076.sec7
t8 = text.s076.sec8
t9 = text.s076.sec9

@region.on_enter
def enter():    # section 254
    roll = random.roll(99)
    if roll <= 9:
        spawn_item(Item.Digimushrm, at=(-1550, -650))
    roll = random.roll(99)
    if roll <= 5:
        spawn_item(Item.Digimushrm, at=(-1250, 650))
    call(Routine.save_clock_speed, arg=2)

@vermilimon1.on_talk
def talk():    # section 6
    recruitable(vermilimon1, line=t6.u0)

@vermilimon2.on_talk
def talk():    # section 7
    recruitable(vermilimon2, line=t7.u0)

@yanmamon3.on_talk
def talk():    # section 8
    recruitable(yanmamon3, line=t8.u0)

@yanmamon4.on_talk
def talk():    # section 9
    recruitable(yanmamon4, line=t9.u0)

@region.on_step(0)
def step0():    # section 51
    if not dino_region_guard_beaten:
        tyrannomon.run(-421, 374)
        tyrannomon.face(tamer)
        tamer.face(tyrannomon)
        partner.face(tyrannomon)
        tyrannomon.arrived()
        sound(8, 10)
        tyrannomon.say(t51.u0)
        tamer.play(19)
        wait(750)
        tamer.say(t51.u1)
        tamer.play(anim.idle)
        sound(8, 10)
        tyrannomon.say(t51.u2)
        tamer.say(t51.u3)
        fight(tyrannomon, escape=False)
        tamer.walk(-97, -448, wait=False)
        partner.walk(-597, -443, wait=False)
        tyrannomon.run(-421, 374, wait=False)
        tamer.arrived()
        partner.arrived()
        tyrannomon.arrived()
        tamer.face(tyrannomon)
        tyrannomon.face(tamer)
        partner.face(tyrannomon)
        tyrannomon.say(t51.u4)
        tamer.play(7)
        wait(750)
        tamer.say(t51.u5)
        tamer.play(anim.idle)
        tyrannomon.say(t51.u6)
        tamer.say(t51.u7)
        tyrannomon.say(t51.u8)
        tamer.say(t51.u9)
        tyrannomon.say(t51.u10)
        tamer.play(16)
        wait(750)
        tamer.say(t51.u11)
        tamer.play(anim.idle)
        tyrannomon.say(t51.u12)
        tamer.say(t51.u13)
        tyrannomon.say(t51.u14)
        tamer.say(t51.u15)
        sound(8, 10)
        tyrannomon.say(t51.u16)
        tamer.say(t51.u17)
        tyrannomon.say(t51.u18)
        dino_region_guard_beaten.set()
        tyrannomon.walk_away(-293, 1172, looks=3)
        tyrannomon.leave()
        glances.set(0)
        camera.on(tamer, speed=10)
        camera.arrived()
        return
    return

# the section table, in the order of the original header
sections(254, 6, 7, 8, 9, 51)
