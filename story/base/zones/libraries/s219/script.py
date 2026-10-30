# The Python view of script 219 of DG.SCN (no screen loads it).
# Made from the disc by `dws story-base`; the source of the story since 2026-10-15: edit it (no file = no script). Keys only, never the
# game's words. `story-build` reads this file (lowered); the DWS beside it is the proven intermediate; mods import `dw.base`.
from dw import *

lib = script(219)

@lib.on_enter
def enter():    # section 254
    pass

@lib.on_step(0)
def step0():    # section 51
    dws(r"""
        say(tamer, text("s219.sec51.u0"));
        choice {
            text("s219.sec51.m0.o0") => {
                if (bits < 100) {
                    say(tamer, text("s219.sec51.u1"));
                    return;
                }
                // ours (patch 0237): how many cards, asked in the amount box; the routine charges them
                // (economy.json cardMachine) and rolls them, one in its box, more in the list of what came
                engine.card_machine = true;
                engine.picker_mode = false;
                card_shop_buy_mode = false;
                engine.arg = 0;
                call_routine(routine("show_bits_box"));
                call_routine(routine("card_shop"));
                call_routine(routine("close_box2"));
                engine.card_machine = false;
                call_routine(routine("check_tournament_medal"));
            }
            text("s219.sec51.m0.o1") => {}
            cancel => {}
        }
    """)

# the section table, in the order of the original header
sections(254, 51)
