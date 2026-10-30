# The Python view of script 64 of DG.SCN: screen 67 Underground Lab.
# Made from the disc by `dws story-base`; the source of the story since 2026-10-15: edit it (no file = no script). Keys only, never the
# game's words. `story-build` reads this file (lowered); the DWS beside it is the proven intermediate; mods import `dw.base`.
from dw import *
from dw.text import text
from dw.names import *

lab = screen(Screen.underground_lab_67)
myotismon = lab.npc(Species.Myotismon177, slot=0)
bakemon = lab.npc(Species.Bakemon157, slot=1)
t5 = text.s064.sec5
t6 = text.s064.sec6
t81 = text.s064.sec81

@lab.on_enter
def enter():    # section 254
    if lab_skullgreymon_beaten:
        objects[0].show()
        objects[1].show()
        objects[2].show()
    else:
        raw.set_rect_impassable(0, 62, 39, 2, 13)
    if not myotismon_joined_city:
        myotismon.play(28)
        bakemon.play(28)

@lab.on_use(1)
def use1():    # section 81
    tamer.face(myotismon)
    tamer.play(19)
    wait(750)
    tamer.say(t81.u0)
    tamer.play(anim.idle)

@bakemon.on_talk(scene=True)
def talk():    # section 6
    if myotismon_joined_city:
        face(tamer)
        say(t6.u0)
        return
    say(t6.u1)

@myotismon.on_talk(scene=True)
def talk():    # section 5
    if myotismon_joined_city:
        face(tamer)
        say(t5.u0)
        return
    if skullgreymon_debut_news_read:
        face(tamer)
        say(t5.u1)
        say(t5.u2)
        return
    tamer.say(t5.u3)
    play(21)
    bakemon.play(21)
    wait(1000)
    play(anim.idle)
    bakemon.play(anim.idle)
    wait(500)
    face(tamer)
    bakemon.face(tamer)
    wait(250)
    say(t5.u4)
    tamer.say(t5.u5)
    say(t5.u6)
    tamer.say(t5.u7)
    say(t5.u8)
    tamer.play(19)
    wait(750)
    tamer.say(t5.u9)
    tamer.play(anim.idle)
    say(t5.u10)
    tamer.say(t5.u11)
    say(t5.u12)
    tamer.say(t5.u13)
    say(t5.u14)
    tamer.say(t5.u15)
    say(t5.u16)
    camera.on(tamer, speed=10)
    camera.arrived()
    myotismon_joined_city.set()
    recruit(Species.Myotismon)
    recruit(Species.SkullGreymon)
    engine.prosperity.add(3)
    return

# the section table, in the order of the original header
sections(254, 81, 6, 5)
