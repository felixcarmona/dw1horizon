# The Python view of script 129 of DG.SCN: screen 134 Freezeland.
# Made from the disc by `dws story-base`; the source of the story since 2026-10-15: edit it (no file = no script). Keys only, never the
# game's words. `story-build` reads this file (lowered); the DWS beside it is the proven intermediate; mods import `dw.base`.
from dw import *
from dw.text import text
from dw.names import *

freezeland = screen(Screen.freezeland_134)
slot0 = entity(5)
penguinmon = freezeland.npc(Species.Penguinmon, slot=0)
mojyamon = freezeland.npc(Species.Mojyamon170, slot=1)
slot5 = freezeland.npc(None, slot=5)    # no NPC of the .MAP in this slot; the script spawns what stands here
t7 = text.s129.sec7

@freezeland.on_enter
def enter():    # section 254
    roll = random.roll(99)
    if roll <= 10:
        spawn_item(Item.Digimushrm, at=(-950, -450))
    curling_match_pending.set(0)
    if mojyamon_traded.set1_row1 or mojyamon_traded.set1_row2 or mojyamon_traded.set1_row3:
        slot0.play(29)
    if mojyamon_traded.set1_row1 and mojyamon_traded.set1_row2:
        slot0.play(30)
    if mojyamon_traded.set1_row1 and mojyamon_traded.set1_row3:
        slot0.play(30)
    if mojyamon_traded.set1_row2 and mojyamon_traded.set1_row3:
        slot0.play(30)
    dws(r"""
        if ((mojyamon_traded.set1_row1 ~> mojyamon_traded.set1_row2) && mojyamon_traded.set1_row3) {
            animate(slot0, 31);
        }
    """)

@penguinmon.on_talk
def talk():    # section 6
    curling_match_pending.set(1)
    jump_to_script(206, 6)

@slot5.on_talk
def talk():    # section 10
    jump_to_script(206, 10)

@mojyamon.on_talk
def talk():    # section 7
    if mojyamon_traded.set1_row1 and mojyamon_traded.set1_row2:
        say(t7.u0)
    elif mojyamon_traded.set1_row1 and mojyamon_traded.set1_row3:
        say(t7.u1)
    elif mojyamon_traded.set1_row2 and mojyamon_traded.set1_row3:
        say(t7.u2)
    elif mojyamon_traded.set1_row1 or mojyamon_traded.set1_row2 or mojyamon_traded.set1_row3:
        say(t7.u3)
    else:
        say(t7.u4)
    engine.arg.set(7)
    engine.menu_result.set(0)
    call(Routine.mojyamon_trade)
    if mojyamon_traded.set1_row1 or mojyamon_traded.set1_row2 or mojyamon_traded.set1_row3:
        slot0.play(29)
    if mojyamon_traded.set1_row1 and mojyamon_traded.set1_row2:
        slot0.play(30)
    if mojyamon_traded.set1_row1 and mojyamon_traded.set1_row3:
        slot0.play(30)
    if mojyamon_traded.set1_row2 and mojyamon_traded.set1_row3:
        slot0.play(30)
    dws(r"""
        if ((mojyamon_traded.set1_row1 ~> mojyamon_traded.set1_row2) && mojyamon_traded.set1_row3) {
            animate(slot0, 31);
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
    say(t7.u5)
    walk_away(-1300, -1351, looks=3)
    leave()
    glances.set(0)
    sound.jingle()
    narrator.say(t7.u6)
    recruit(Species.Mojyamon)
    mojyamon_left.set1.set()
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
    if partner_type == 44:
        jump_to_script(203, 51)
    return

# the section table, in the order of the original header
sections(254, 6, 10, 7, 51)
