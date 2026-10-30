# The Python view of script 128 of DG.SCN: screen 133 Freezeland.
# Made from the disc by `dws story-base`; the source of the story since 2026-10-15: edit it (no file = no script). Keys only, never the
# game's words. `story-build` reads this file (lowered); the DWS beside it is the proven intermediate; mods import `dw.base`.
from dw import *
from dw.text import text
from dw.names import *

freezeland = screen(Screen.freezeland_133)
mojyamon0 = freezeland.npc(Species.Mojyamon170, slot=0)
mojyamon1 = freezeland.npc(Species.Mojyamon170, slot=1)
t5 = text.s128.sec5
t6 = text.s128.sec6

@freezeland.on_enter
def enter():    # section 254
    roll = random.roll(99)
    if roll <= 17:
        spawn_item(Item.Digimushrm, at=(-350, -1150))
    roll = random.roll(99)
    if roll <= 0:
        spawn_item(Item.SageFruit, at=(1050, -350))
    if mojyamon_traded.set2_row1 or mojyamon_traded.set2_row2 or mojyamon_traded.set2_row3:
        mojyamon0.play(29)
    if mojyamon_traded.set2_row1 and mojyamon_traded.set2_row2:
        mojyamon0.play(30)
    if mojyamon_traded.set2_row1 and mojyamon_traded.set2_row3:
        mojyamon0.play(30)
    if mojyamon_traded.set2_row2 and mojyamon_traded.set2_row3:
        mojyamon0.play(30)
    dws(r"""
        if ((mojyamon_traded.set2_row1 ~> mojyamon_traded.set2_row2) && mojyamon_traded.set2_row3) {
            animate(mojyamon0, 31);
        }
    """)
    if mojyamon_traded.set3_row1 or mojyamon_traded.set3_row2 or mojyamon_traded.set3_row3:
        mojyamon1.play(29)
    if mojyamon_traded.set3_row1 and mojyamon_traded.set3_row2:
        mojyamon1.play(30)
    if mojyamon_traded.set3_row1 and mojyamon_traded.set3_row3:
        mojyamon1.play(30)
    if mojyamon_traded.set3_row2 and mojyamon_traded.set3_row3:
        mojyamon1.play(30)
    dws(r"""
        if ((mojyamon_traded.set3_row1 ~> mojyamon_traded.set3_row2) && mojyamon_traded.set3_row3) {
            animate(mojyamon1, 31);
        }
    """)

@mojyamon0.on_talk
def talk():    # section 5
    if mojyamon_traded.set2_row1 and mojyamon_traded.set2_row2:
        say(t5.u0)
    elif mojyamon_traded.set2_row1 and mojyamon_traded.set2_row3:
        say(t5.u1)
    elif mojyamon_traded.set2_row2 and mojyamon_traded.set2_row3:
        say(t5.u2)
    elif mojyamon_traded.set2_row1 or mojyamon_traded.set2_row2 or mojyamon_traded.set2_row3:
        say(t5.u3)
    else:
        say(t5.u4)
    engine.arg.set(5)
    engine.menu_result.set(1)
    call(Routine.mojyamon_trade)
    if mojyamon_traded.set2_row1 or mojyamon_traded.set2_row2 or mojyamon_traded.set2_row3:
        play(29)
    if mojyamon_traded.set2_row1 and mojyamon_traded.set2_row2:
        play(30)
    if mojyamon_traded.set2_row1 and mojyamon_traded.set2_row3:
        play(30)
    if mojyamon_traded.set2_row2 and mojyamon_traded.set2_row3:
        play(30)
    dws(r"""
        if ((mojyamon_traded.set2_row1 ~> mojyamon_traded.set2_row2) && mojyamon_traded.set2_row3) {
            animate(mojyamon0, 31);
        }
    """)
    if not mojyamon_traded.set1_row1 or not mojyamon_traded.set1_row2 or not mojyamon_traded.set1_row3:
        return
    if not mojyamon_traded.set2_row1 or not mojyamon_traded.set2_row2 or not mojyamon_traded.set2_row3:
        return
    if not mojyamon_traded.set3_row1 or not mojyamon_traded.set3_row2 or not mojyamon_traded.set3_row3:
        return
    if recruited(Species.Mojyamon):
        return
    say(t5.u5)
    walk_away(1931, -1543, looks=6, pause=500)
    leave()
    glances.set(0)
    sound.jingle()
    narrator.say(t5.u6)
    recruit(Species.Mojyamon)
    mojyamon_left.set2.set()
    engine.prosperity.add(2)

@mojyamon1.on_talk
def talk():    # section 6
    if mojyamon_traded.set3_row1 and mojyamon_traded.set3_row2:
        say(t6.u0)
    elif mojyamon_traded.set3_row2 and mojyamon_traded.set3_row3:
        say(t6.u1)
    elif mojyamon_traded.set3_row2 and mojyamon_traded.set3_row3:
        say(t6.u2)
    elif mojyamon_traded.set3_row1 or mojyamon_traded.set3_row2 or mojyamon_traded.set3_row3:
        say(t6.u3)
    else:
        say(t6.u4)
    engine.arg.set(6)
    engine.menu_result.set(2)
    call(Routine.mojyamon_trade)
    if mojyamon_traded.set3_row1 or mojyamon_traded.set3_row2 or mojyamon_traded.set3_row3:
        play(29)
    if mojyamon_traded.set3_row1 and mojyamon_traded.set3_row2:
        play(30)
    if mojyamon_traded.set3_row1 and mojyamon_traded.set3_row3:
        play(30)
    if mojyamon_traded.set3_row2 and mojyamon_traded.set3_row3:
        play(30)
    dws(r"""
        if ((mojyamon_traded.set3_row1 ~> mojyamon_traded.set3_row2) && mojyamon_traded.set3_row3) {
            animate(mojyamon1, 31);
        }
    """)
    if not mojyamon_traded.set1_row1 or not mojyamon_traded.set1_row2 or not mojyamon_traded.set1_row3:
        return
    if not mojyamon_traded.set2_row1 or not mojyamon_traded.set2_row2 or not mojyamon_traded.set2_row3:
        return
    if not mojyamon_traded.set3_row1 or not mojyamon_traded.set3_row2 or not mojyamon_traded.set3_row3:
        return
    if recruited(Species.Mojyamon):
        return
    say(t6.u5)
    walk_away(-1605, -856, looks=6, pause=500)
    leave()
    glances.set(0)
    sound.jingle()
    narrator.say(t6.u6)
    recruit(Species.Mojyamon)
    mojyamon_left.set3.set()
    engine.prosperity.add(2)

@freezeland.on_step(0)
def step0():    # section 51
    if not partner.sick or digivolve_scene_seen:
        return
    if partner.species in (Species.Agumon, Species.Greymon, Species.Tyrannomon, Species.Meramon, Species.Monochromon):
        jump_to_script(203, 51)
    if partner_type in (19, 32, 51, 1, 2):
        jump_to_script(203, 51)
    if partner_type in (15, 16, 29, 30, 43):
        jump_to_script(203, 51)
    if partner_type in (44, 21):
        jump_to_script(203, 51)
    return

# the section table, in the order of the original header
sections(254, 5, 6, 51)
