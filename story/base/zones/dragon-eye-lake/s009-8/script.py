# The Python view of script 9 of DG.SCN: screen 8 Dragon Eye Lake.
# Made from the disc by `dws story-base`; the source of the story since 2026-10-15: edit it (no file = no script). Keys only, never the
# game's words. `story-build` reads this file (lowered); the DWS beside it is the proven intermediate; mods import `dw.base`.
from dw import *
from dw.text import text

lake = screen(Screen.dragon_eye_lake_8)
t81 = text.s009.sec81
t82 = text.s009.sec82

@lake.on_enter
def enter():    # section 254
    spawn_chest(Item.MediumMP, at=(-1511, 1093), opened=trigger(706))
    roll = random.roll(99)
    if roll <= 14:
        spawn_item(Item.Digimushrm, at=(2450, -1250))
    roll = random.roll(99)
    if roll <= 24:
        spawn_item(Item.Digimushrm, at=(-1850, 450))

@lake.on_use(1)
def use1():    # section 81
    narrator.say(t81.u0)
    tamer.turn(2048)
    wait(250)
    tamer.say(t81.u1)
    match choose(a=t81.m0.o0, b=t81.m0.o1, c=t81.m0.o2):
        case "a":
            if bits >= 300:
                take(bits=300)
                narrator.say(t81.u4)
                give(Item.Meat)
                if engine.item_did_not_fit:
                    if has(Item.Meat, 99):
                        return
                    tamer.say(t81.u5)
                    pick_item()
                    take_picked(all=True)
                    give(Item.Meat)
                return
            tamer.say(t81.u2)
            return
        case "b":
            if bits >= 600:
                take(bits=600)
                narrator.say(t81.u6)
                give(Item.Digimushrm)
                if engine.item_did_not_fit:
                    if has(Item.Digimushrm, 99):
                        return
                    tamer.say(t81.u7)
                    pick_item()
                    take_picked(all=True)
                    give(Item.Digimushrm)
                return
            tamer.say(t81.u3)
            return
    return

@lake.on_use(2)
def use2():    # section 82
    tamer.turn(2048)
    wait(250)
    raw.set_textbox_size(entity(0), 19, 7)
    raw.show_textbox(t82.u0)
    hide_hud()
    return

# the section table, in the order of the original header
sections(254, 81, 82)
