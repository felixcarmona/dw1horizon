# The Python view of script 2 of DG.SCN: screen 1 Kunemon's Bed.
# Made from the disc by `dws story-base`; the source of the story since 2026-10-15: edit it (no file = no script). Keys only, never the
# game's words. `story-build` reads this file (lowered); the DWS beside it is the proven intermediate; mods import `dw.base`.
from dw import *
from dw.text import text
from dw.names import *

bed = screen(Screen.kunemons_bed)
redvegiemon0 = bed.npc(Species.RedVegiemon, slot=0)
kunemon = bed.npc(Species.Kunemon152, slot=1)
redvegiemon2 = bed.npc(Species.RedVegiemon, slot=2)
dokunemon3 = bed.npc(Species.Dokunemon, slot=3)
dokunemon4 = bed.npc(Species.Dokunemon, slot=4)
t5 = text.s002.sec5
t6 = text.s002.sec6
t7 = text.s002.sec7
t8 = text.s002.sec8
t9 = text.s002.sec9

@bed.on_enter
def enter():    # section 254
    roll = random.roll(99)
    if roll <= 24:
        spawn_item(Item.Digimushrm, at=(-350, 450))
    roll = random.roll(99)
    if roll <= 4:
        spawn_item(Item.Happymushrm, at=(1050, -950))
    if not recruited(Species.Kunemon):
        kunemon.play(28)

@redvegiemon0.on_talk
def talk():    # section 5
    recruitable(redvegiemon0, line=t5.u0)

@redvegiemon2.on_talk
def talk():    # section 7
    recruitable(redvegiemon2, line=t7.u0)

@dokunemon3.on_talk
def talk():    # section 8
    recruitable(dokunemon3, line=t8.u0)

@dokunemon4.on_talk
def talk():    # section 9
    recruitable(dokunemon4, line=t9.u0)

@kunemon.on_talk(scene=True)
def talk():    # section 6
    play(29)
    say(t6.u0)
    if ask(yes=t6.m0.o0, no=t6.m0.o1):
        pick = pick_item()
        if pick is Picked.EMPTY:
            tamer.say(t6.u1)
        elif pick is Picked.CANCELLED:
            pass
        elif pick in (Item.Meat, Item.GiantMeat, Item.Sirloin, Item.Supercarrot, Item.HawkRadish, Item.Digimushrm, Item.Digianchovy, Item.MoldyMeat):
            take_picked()
            play(30)
            wait(1000)
            play(8, wait=True)
            say(t6.u3)
            play(anim.idle)
            say(t6.u4)
            fight(kunemon, escape=False)
            tamer.face(kunemon)
            face(tamer)
            partner.face(kunemon)
            say(t6.u5)
            tamer.play(20, wait=True)
            tamer.say(t6.u6)
            tamer.play(anim.idle)
            wait(500)
            say(t6.u7)
            walk_away(1219, 984, looks=3)
            send_to_city(line=t6.u8, species=Species.Kunemon)
            return
        else:
            tamer.say(t6.u2)
    say(t6.u9)
    play(28)
    wait(1000)

@bed.on_step(0)
def step0():    # section 51
    if not eastern_bridge_seen:
        tamer.walk(413, 2200, wait=False)
        warp(Screen.digimon_bridge_10, entry=1)
    tamer.walk(413, 2200, wait=False)
    warp(Screen.digimon_bridge_9, entry=1)
    raw.end_script()

# the section table, in the order of the original header
sections(254, 5, 7, 8, 9, 6, 51)
