# The Python view of script 215 of DG.SCN (no screen loads it).
# Made from the disc by `dws story-base`; the source of the story since 2026-10-15: edit it (no file = no script). Keys only, never the
# game's words. `story-build` reads this file (lowered); the DWS beside it is the proven intermediate; mods import `dw.base`.
from dw import *
from dw.text import text
from dw.names import *

lib = script(215)
slot1 = lib.npc(None, slot=1)    # no NPC of the .MAP in this slot; the script spawns what stands here
t6 = text.s215.sec6

@lib.on_enter
def enter():    # section 254
    pass

@slot1.on_talk
def talk():    # section 6
    if not fortune_teller_intro_seen:
        fortune_teller_intro_seen.set()
        say(t6.u0)
        return
    say(t6.u1)
    wait(1000)
    say(t6.u2)
    roll = random.roll(11)
    if roll <= 0:
        say(t6.u3)
        roll = random.roll(2)
        if roll <= 0:
            say(t6.u8)
        elif roll <= 1:
            say(t6.u9)
        elif roll <= 2:
            say(t6.u10)
        else:
            say(t6.u4)
            roll = random.roll(3)
            if roll <= 0:
                say(t6.u11)
            elif roll <= 1:
                say(t6.u12)
            elif roll <= 2:
                say(t6.u13)
            elif roll <= 3:
                say(t6.u14)
            else:
                say(t6.u5)
                roll = random.roll(3)
                if roll <= 0:
                    say(t6.u15)
                elif roll <= 1:
                    say(t6.u16)
                elif roll <= 2:
                    say(t6.u17)
                elif roll <= 3:
                    say(t6.u18)
                else:
                    say(t6.u6)
                    roll = random.roll(3)
                    if roll <= 0:
                        say(t6.u19)
                    elif roll <= 1:
                        say(t6.u20)
                    elif roll <= 2:
                        say(t6.u21)
                    elif roll <= 3:
                        say(t6.u22)
                    else:
                        say(t6.u7)
                        roll = random.roll(2)
                        if roll <= 0:
                            say(t6.u23)
                        elif roll <= 1:
                            say(t6.u24)
                        elif roll <= 2:
                            say(t6.u25)
                        else:
                            say(t6.u8)
    elif roll <= 3:
        say(t6.u4)
        roll = random.roll(3)
        if roll <= 0:
            say(t6.u11)
        elif roll <= 1:
            say(t6.u12)
        elif roll <= 2:
            say(t6.u13)
        elif roll <= 3:
            say(t6.u14)
        else:
            say(t6.u5)
            roll = random.roll(3)
            if roll <= 0:
                say(t6.u15)
            elif roll <= 1:
                say(t6.u16)
            elif roll <= 2:
                say(t6.u17)
            elif roll <= 3:
                say(t6.u18)
            else:
                say(t6.u6)
                roll = random.roll(3)
                if roll <= 0:
                    say(t6.u19)
                elif roll <= 1:
                    say(t6.u20)
                elif roll <= 2:
                    say(t6.u21)
                elif roll <= 3:
                    say(t6.u22)
                else:
                    say(t6.u7)
                    roll = random.roll(2)
                    if roll <= 0:
                        say(t6.u23)
                    elif roll <= 1:
                        say(t6.u24)
                    elif roll <= 2:
                        say(t6.u25)
                    else:
                        say(t6.u8)
    elif roll <= 8:
        say(t6.u5)
        roll = random.roll(3)
        if roll <= 0:
            say(t6.u15)
        elif roll <= 1:
            say(t6.u16)
        elif roll <= 2:
            say(t6.u17)
        elif roll <= 3:
            say(t6.u18)
        else:
            say(t6.u6)
            roll = random.roll(3)
            if roll <= 0:
                say(t6.u19)
            elif roll <= 1:
                say(t6.u20)
            elif roll <= 2:
                say(t6.u21)
            elif roll <= 3:
                say(t6.u22)
            else:
                say(t6.u7)
                roll = random.roll(2)
                if roll <= 0:
                    say(t6.u23)
                elif roll <= 1:
                    say(t6.u24)
                elif roll <= 2:
                    say(t6.u25)
                else:
                    say(t6.u8)
    elif roll <= 10:
        say(t6.u6)
        roll = random.roll(3)
        if roll <= 0:
            say(t6.u19)
        elif roll <= 1:
            say(t6.u20)
        elif roll <= 2:
            say(t6.u21)
        elif roll <= 3:
            say(t6.u22)
        else:
            say(t6.u7)
            roll = random.roll(2)
            if roll <= 0:
                say(t6.u23)
            elif roll <= 1:
                say(t6.u24)
            elif roll <= 2:
                say(t6.u25)
            else:
                say(t6.u8)
    elif roll <= 11:
        say(t6.u7)
        roll = random.roll(2)
        if roll <= 0:
            say(t6.u23)
        elif roll <= 1:
            say(t6.u24)
        elif roll <= 2:
            say(t6.u25)
        else:
            say(t6.u8)
    else:
        say(t6.u3)
        roll = random.roll(2)
        if roll <= 0:
            say(t6.u8)
        elif roll <= 1:
            say(t6.u9)
        elif roll <= 2:
            say(t6.u10)
        else:
            say(t6.u4)
            roll = random.roll(3)
            if roll <= 0:
                say(t6.u11)
            elif roll <= 1:
                say(t6.u12)
            elif roll <= 2:
                say(t6.u13)
            elif roll <= 3:
                say(t6.u14)
            else:
                say(t6.u5)
                roll = random.roll(3)
                if roll <= 0:
                    say(t6.u15)
                elif roll <= 1:
                    say(t6.u16)
                elif roll <= 2:
                    say(t6.u17)
                elif roll <= 3:
                    say(t6.u18)
                else:
                    say(t6.u6)
                    roll = random.roll(3)
                    if roll <= 0:
                        say(t6.u19)
                    elif roll <= 1:
                        say(t6.u20)
                    elif roll <= 2:
                        say(t6.u21)
                    elif roll <= 3:
                        say(t6.u22)
                    else:
                        say(t6.u7)
                        roll = random.roll(2)
                        if roll <= 0:
                            say(t6.u23)
                        elif roll <= 1:
                            say(t6.u24)
                        elif roll <= 2:
                            say(t6.u25)
                        else:
                            say(t6.u8)
    roll = random.roll(9)
    if roll <= 0:
        say(t6.u26)
    elif roll <= 1:
        say(t6.u27)
    elif roll <= 2:
        say(t6.u28)
    elif roll <= 3:
        say(t6.u29)
    elif roll <= 4:
        say(t6.u30)
    elif roll <= 5:
        say(t6.u31)
    elif roll <= 6:
        say(t6.u32)
    elif roll <= 7:
        say(t6.u33)
    elif roll <= 8:
        say(t6.u34)
    elif roll <= 9:
        say(t6.u35)
    say(t6.u36)
    roll = random.roll(4)
    if roll <= 0:
        say(t6.u37)
    elif roll <= 1:
        say(t6.u38)
    elif roll <= 2:
        say(t6.u39)
    elif roll <= 3:
        say(t6.u40)
    elif roll <= 4:
        say(t6.u41)

# the section table, in the order of the original header
sections(254, 6)
