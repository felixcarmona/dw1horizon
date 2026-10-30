# The Python view of script 126 of DG.SCN: screen 131 Gear Savanna.
# Made from the disc by `dws story-base`; the source of the story since 2026-10-15: edit it (no file = no script). Keys only, never the
# game's words. `story-build` reads this file (lowered); the DWS beside it is the proven intermediate; mods import `dw.base`.
from dw import *
from dw.text import text
from dw.names import *

savanna = screen(Screen.gear_savanna_131)
market_manager0 = savanna.npc(Species.MarketManager, slot=0)
market_manager1 = savanna.npc(Species.MarketManager, slot=1)
t51 = text.s126.sec51
t81 = text.s126.sec81
t82 = text.s126.sec82

@savanna.on_enter
def enter():    # section 254
    roll = random.roll(99)
    if roll <= 16:
        spawn_item(Item.Digimushrm, at=(-50, -2050))
    roll = random.roll(99)
    if roll <= 2:
        spawn_item(Item.Happymushrm, at=(-2450, -1850))

@savanna.on_use(1)
def use1():    # section 81
    market_manager0.face(tamer)
    tamer.face(market_manager0)
    if not card_shop_free_card_received:
        card_shop_free_card_received.set()
        sound(8, 4)
        market_manager0.say(t81.u0)
        tamer.say(t81.u1)
        market_manager0.say(t81.u2)
        tamer.say(t81.u3)
        sound(8, 4)
        market_manager0.say(t81.u4)
        tamer.say(t81.u5)
        narrator.say(t81.u6)
        raw.give_card(0)
        return
    market_manager0.say(t81.u7)
    engine.arg.set(5)
    sound(8, 4)
    market_manager0.say(t81.u8)
    call(Routine.show_bits_box)
    while True:
        match choose(a=t81.m0.o0, b=t81.m0.o1, c=t81.m0.o2):
            case "a":
                if bits >= 500:
                    dws(r"""
                        choice(keep) {
                            text("s126.sec81.m1.o0") => {
                                say(market_manager0, text("s126.sec81.u9"));
                                engine.picker_mode = false;
                                card_shop_buy_mode = false;
                                call_routine(routine("card_shop"));   // asks how many packs and takes their bits (patch 0223)
                                call_routine(routine("check_tournament_medal"));
                            }
                            text("s126.sec81.m1.o1") => {
                                engine.picker_mode = false;
                                card_shop_buy_mode = true;
                                call_routine(routine("card_shop"));
                                call_routine(routine("check_tournament_medal"));
                            }
                            text("s126.sec81.m1.o2") or cancel => {}
                        }
                    """)
                else:
                    dws(r"""
                        choice(keep) {
                            text("s126.sec81.m2.o0") => {
                                engine.picker_mode = false;
                                card_shop_buy_mode = true;
                                call_routine(routine("card_shop"));
                                call_routine(routine("check_tournament_medal"));
                            }
                            text("s126.sec81.m2.o1") or cancel => {}
                        }
                    """)
            case "b":
                engine.picker_mode.set()
                call(Routine.card_shop)
            case "c" | _:
                break
        market_manager0.say(t81.u11)
    call(Routine.close_box2)
    market_manager0.say(t81.u12)

@savanna.on_use(2)
def use2():    # section 82
    market_manager1.face(tamer)
    tamer.face(market_manager1)
    sound(8, 4)
    market_manager1.say(t82.u0)
    match choose(a=t82.m0.o0, b=t82.m0.o1, c=t82.m0.o2):
        case "a":
            shop_stock.med_recovery.set()
            shop_stock.medium_mp.set()
            shop_stock.auto_pilot.set()
            shop_stock.giant_meat.set()
            shop_stock.off_disk.set()
            shop_stock.def_disk.set()
            shop_stock.hispeed_dsk.set()
            engine.picker_mode.clear()
            call(Routine.shop, arg=6)
            shop_stock.med_recovery.clear()
            shop_stock.medium_mp.clear()
            shop_stock.auto_pilot.clear()
            shop_stock.giant_meat.clear()
            shop_stock.off_disk.clear()
            shop_stock.def_disk.clear()
            shop_stock.hispeed_dsk.clear()
            return
        case "b":
            engine.picker_mode.set()
            call(Routine.shop, arg=6)
            return

@savanna.on_step(0)
def step0():    # section 51
    if card_shop_seen:
        return
    tamer.say(t51.u0)
    camera.to(800, 4000, speed=30)
    camera.arrived()
    tamer.say(t51.u1)
    camera.on(tamer, speed=10)
    camera.arrived()
    card_shop_seen.set()
    return

# the section table, in the order of the original header
sections(254, 81, 82, 51)
