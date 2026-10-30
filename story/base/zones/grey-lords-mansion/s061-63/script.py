# The Python view of script 61 of DG.SCN: screen 63 Grey Lord's Mansion.
# Made from the disc by `dws story-base`; the source of the story since 2026-10-15: edit it (no file = no script). Keys only, never the
# game's words. `story-build` reads this file (lowered); the DWS beside it is the proven intermediate; mods import `dw.base`.
from dw import *
from dw.text import text
from dw.names import *

mansion = screen(Screen.grey_lords_mansion_63)
t52 = text.s061.sec52
t82 = text.s061.sec82

@mansion.on_enter
def enter():    # section 254
    spawn_chest(Item.Medicine, at=(-503, -2215), opened=trigger(656), facing=3072)

@mansion.on_use(1)
def use1():    # section 81
    swing_door(1)
    sound(8, 1)
    wait(500)
    tamer.walk(336, 1300, wait=False)
    warp(Screen.grey_lords_mansion_62, entry=0)

@mansion.on_use(2)
def use2():    # section 82
    if not mansion_door_unlocked.s53_s63:
        tamer.turn(3072)
        sound(8, 2)
        wait(250)
        sound(8, 2)
        tamer.play(16)
        wait(750)
        tamer.say(t82.u0)
        tamer.play(anim.idle)
        tamer.say(t82.u1)
        sound(8, 3)
        tamer.say(t82.u2)
        mansion_door_unlocked.s53_s63.set()
    swing_door(0)
    sound(8, 1)
    wait(500)
    tamer.walk(1700, 226, wait=False)
    warp(Screen.grey_lords_mansion_53, entry=2)

@mansion.on_step(1)
def step1():    # section 52
    if not mansion_trapdoor_fallen:
        tamer.play(18)
        partner.play(43)
        wait(1000)
        partner.play(44)
        damage_percent.set(30)
        raw.deal_damage(damage_percent)
        call(Routine.loop_once, arg=253)
        tamer.say(t52.u0)
        tamer.play(24)
        wait(750)
        tamer.say(t52.u1)
        tamer.play(anim.idle)
        tamer.walk(150, -340, camera=True)
        tamer.turn(1260)
        wait(500)
        tamer.turn(2796)
        wait(500)
        tamer.face(partner)
        tamer.say(t52.u2)
        mansion_trapdoor_fallen.set()
        return
    tamer.say(t52.u3)
    return

# the section table, in the order of the original header
sections(254, 81, 82, 52)
