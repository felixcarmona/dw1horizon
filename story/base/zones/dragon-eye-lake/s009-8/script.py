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
    tamer.turn(2048)
    narrator.say(t81.vend_daily)
    while True:
        narrator.say(t81.vend_prompt)
        match choose(a=t81.vend_buy0, b=t81.vend_buy1, more=t81.vend_more):
            case "a":
                if bits < 51:
                    narrator.say(t81.vend_poor)
                    return
                give(Item.Digimushrm)
                if engine.item_did_not_fit:
                    narrator.say(t81.vend_full)
                    return
                take(bits=51)
                narrator.say(t81.vend_getDigimushrm)
                return
            case "b":
                if engine.vending_happy_sold:
                    narrator.say(t81.vend_sold)
                    return
                if bits < 1500:
                    narrator.say(t81.vend_poor)
                    return
                give(Item.Happymushrm)
                if engine.item_did_not_fit:
                    narrator.say(t81.vend_full)
                    return
                take(bits=1500)
                engine.vending_happy_sold.set()
                narrator.say(t81.vend_getHappymushrm)
                return
            case "more":
                narrator.say(t81.vend_prompt)
                match choose(a=t81.vend_buy2, back=t81.vend_back, leave=t81.vend_leave):
                    case "a":
                        if engine.vending_ice_sold:
                            narrator.say(t81.vend_sold)
                            return
                        if bits < 1000:
                            narrator.say(t81.vend_poor)
                            return
                        give(Item.IceMushrm)
                        if engine.item_did_not_fit:
                            narrator.say(t81.vend_full)
                            return
                        take(bits=1000)
                        engine.vending_ice_sold.set()
                        narrator.say(t81.vend_getIceMushrm)
                        return
                    case "back":
                        pass
                    case _:
                        return
            case _:
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
