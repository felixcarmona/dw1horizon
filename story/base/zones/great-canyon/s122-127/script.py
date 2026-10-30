# The Python view of script 122 of DG.SCN: screen 127 Great Canyon.
# Made from the disc by `dws story-base`; the source of the story since 2026-10-15: edit it (no file = no script). Keys only, never the
# game's words. `story-build` reads this file (lowered); the DWS beside it is the proven intermediate; mods import `dw.base`.
from dw import *
from dw.text import text

canyon = screen(Screen.great_canyon_127)
shellmon = canyon.npc(Species.Shellmon155, slot=0)
goblimon = canyon.npc(Species.Goblimon, slot=1)
t5 = text.s122.sec5
t6 = text.s122.sec6

@canyon.on_enter
def enter():    # section 254
    spawn_chest(Item.DefChip, at=(1460, -443), opened=trigger(666), facing=3072)

@goblimon.on_talk
def talk():    # section 6
    recruitable(goblimon, line=t6.u0)

@shellmon.on_talk
def talk():    # section 5
    say(t5.u0)
    tamer.say(t5.u1)
    say(t5.u2)
    tamer.play(19)
    wait(750)
    tamer.say(t5.u3)
    tamer.play(anim.idle)
    say(t5.u4)
    tamer.say(t5.u5)
    say(t5.u6)
    tamer.say(t5.u7)
    say(t5.u8)
    tamer.play(16)
    wait(750)
    tamer.say(t5.u9)
    tamer.play(anim.idle)
    say(t5.u10)
    walk_away(-111, -2962, looks=3)
    send_to_city(line=t5.u11, species=Species.Shellmon, sound=(8, 10), prosperity=2, camera=False)
    return

# the section table, in the order of the original header
sections(254, 6, 5)
