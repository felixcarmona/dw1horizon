# The Python view of script 210 of DG.SCN (no screen loads it).
# Made from the disc by `dws story-base`; the source of the story since 2026-10-15: edit it (no file = no script). Keys only, never the
# game's words. `story-build` reads this file (lowered); the DWS beside it is the proven intermediate; mods import `dw.base`.
from dw import *
from dw.text import text
from dw.names import *

lib = script(210)
slot0 = lib.npc(None, slot=0)    # no NPC of the .MAP in this slot; the script spawns what stands here
t51 = text.s210.sec51
t77 = text.s210.sec77

@lib.on_enter
def enter():    # section 254
    return step0()

@lib.on_step(0)
def step0():    # section 51
    if partner.species in (Species.Botamon, Species.Koromon, Species.Agumon, Species.Betamon):
        jump_to_script(221, 5)
    if partner_type in (15, 16, 17, 18):
        jump_to_script(221, 5)
    if partner_type in (29, 30, 31, 32):
        jump_to_script(221, 5)
    if partner_type in (43, 44, 45, 46):
        jump_to_script(221, 5)
    if not greymon_challenge_ready and not recruited(Species.Greymon) and engine.prosperity >= 15:
        greymon_challenge_ready.set()
    if not mt_infinity_entrance_found and engine.prosperity >= 50 and recruited(Species.Greymon):
        mt_infinity_entrance_found.set()
        slot0.say(t51.u0)
        tamer.say(t51.u1)
        slot0.say(t51.u2)
        tamer.say(t51.u3)
        slot0.say(t51.u4)
        tamer.say(t51.u5)
        slot0.say(t51.u6)
        tamer.say(t51.u7)
        slot0.say(t51.u8)
        return
    if mt_infinity_entrance_found and not engine.game_beaten and recruited(Species.Greymon):
        slot0.say(t51.u9)
        slot0.say(t51.u10)
    jump_to_script(221, 5)

@lib.on_step(26)
def step26():    # section 77
    slot0.say(t77.u0)
    if engine.prosperity <= 10:
        slot0.say(t77.u1)
        return
    if engine.prosperity <= 30:
        slot0.say(t77.u2)
        return
    if engine.prosperity <= 50:
        slot0.say(t77.u3)
        return
    if engine.prosperity <= 70:
        slot0.say(t77.u4)
        return
    if engine.prosperity <= 99:
        slot0.say(t77.u5)
        return
    if engine.prosperity <= 100:
        slot0.say(t77.u6)
        if tamer.level != 10 and not recruited(Species.Tsunomon):
            tamer.add(level=1)
            narrator.say(t77.u7)
            recruit(Species.Tsunomon)
            medal.town_flourishing.set()
            sound(0, 7)
            narrator.say(t77.u8)
    return

# the section table, in the order of the original header
sections(254, 51, 77)
