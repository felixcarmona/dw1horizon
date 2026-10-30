# The Python view of script 39 of DG.SCN: screen 39 Great Canyon Bridge.
# Made from the disc by `dws story-base`; the source of the story since 2026-10-15: edit it (no file = no script). Keys only, never the
# game's words. `story-build` reads this file (lowered); the DWS beside it is the proven intermediate; mods import `dw.base`.
from dw import *
from dw.text import text
from dw.names import *

bridge = screen(Screen.great_canyon_bridge)
goblimon = bridge.npc(Species.Goblimon, slot=1)
t51 = text.s039.sec51
t6 = text.s039.sec6

@bridge.on_enter
def enter():    # section 254
    spawn_chest(Item.DefChip, at=(1460, -443), opened=trigger(666), facing=3072)

@goblimon.on_talk
def talk():    # section 6
    recruitable(goblimon, line=t6.u0)

@bridge.on_step(0)
def step0():    # section 51
    if ogre_fortress_cleared and canyon_elevator_ridden and not shellmon_plea_heard:
        sound(8, 12)
        narrator.say(t51.u0)
        tamer.turn(1321)
        partner.turn(1321)
        wait(500)
        tamer.play(23)
        wait(750)
        tamer.say(t51.u1)
        tamer.play(anim.idle)
        wait(500)
        narrator.say(t51.u2)
        wait(500)
        tamer.say(t51.u3)
        wait(500)
        narrator.say(t51.u4)
        wait(500)
        tamer.say(t51.u5)
        wait(500)
        sound.jingle()
        narrator.say(t51.u6)
        wait(500)
        tamer.play(16)
        wait(750)
        tamer.say(t51.u7)
        tamer.play(anim.idle)
        wait(500)
        narrator.say(t51.u8)
        wait(500)
        tamer.say(t51.u9)
        wait(500)
        sound.jingle()
        narrator.say(t51.u10)
        wait(500)
        shellmon_plea_heard.set()
        return
    if ogre_fortress_elevator_ridden and shellmon_plea_heard and not recruited(Species.Shellmon):
        return
    return

# the section table, in the order of the original header
sections(254, 6, 51)
