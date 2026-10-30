# The Python view of script 191 of DG.SCN: screen 235 Digimon Curling.
# Made from the disc by `dws story-base`; the source of the story since 2026-10-15: edit it (no file = no script). Keys only, never the
# game's words. `story-build` reads this file (lowered); the DWS beside it is the proven intermediate; mods import `dw.base`.
from dw import *
from dw.text import text
from dw.names import *

curling = screen(Screen.digimon_curling)
slot1 = curling.npc(None, slot=0)    # the .MAP has Penguinmon176 here; the script spawns what stands here
slot6 = curling.npc(None, slot=6)    # no NPC of the .MAP in this slot; the script spawns what stands here
t52 = text.s191.sec52

@curling.on_enter
def enter():    # section 254
    pass

@slot1.on_talk
def talk():    # section 6
    curling_match_pending.set(1)
    if curling_opponent == 0:
        jump_to_script(206, 6)
    if curling_opponent == 1:
        jump_to_script(206, 7)

@slot6.on_talk
def talk():    # section 11
    if curling_opponent == 0:
        jump_to_script(206, 11)
    if curling_opponent == 1:
        jump_to_script(206, 12)

@curling.on_step(0)
def step0():    # section 51
    if not engine.game_beaten:
        warp(Screen.arena_lobby_208, entry=0)
    else:
        warp(Screen.arena_lobby_223, entry=0)

@curling.on_step(1)
def step1():    # section 52
    tamer.say(t52.u0)
    tamer.walk(-2, -619, camera=True)
    return

# the section table, in the order of the original header
sections(254, 6, 11, 51, 52)
