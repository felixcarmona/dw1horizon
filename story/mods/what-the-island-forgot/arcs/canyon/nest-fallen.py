# 366, the top of the Great Canyon with Birdramon's nest fallen in (R1; maps/nest-fallen.py). The elevator works as on
# 129 (its use trigger 1: up and down the canyon, the game's own menu by its keys); the first time, the tamer sees it.
from dw import *
from dw.text import text
from dw.names import *

top = new_screen(366, map="build/what-the-island-forgot-maps/screens/NEST02.MAP")
seen = flag()
t81 = text.s124.sec81

@top.on_enter
def enter():
    music(6)
    if not seen:
        tamer.say("The nest... It's fallen in. The rock under it sank.", "There's nobody up here anymore.")
        seen.set()

@top.on_use(1)
def elevator():
    tamer.turn(1271)
    narrator.say(t81.u0)
    match choose(a=t81.m0.o0, b=t81.m0.o1, c=t81.m0.o2):
        case "a":
            sound(8, 4)
            sound(8, 5)
            warp(Screen.great_canyon_top_area_38, entry=2, then=55)
        case "b":
            if not canyon_elevator_unjammed:
                tamer.say(text.s124.sec81.u1)
            else:
                sound(8, 4)
                sound(8, 5)
                warp(Screen.great_canyon_bot_area_41, entry=2, then=53)
        case _:
            pass
