# The Python view of script 135 of DG.SCN: screen 141 Volume Villa.
# Made from the disc by `dws story-base`; the source of the story since 2026-10-15: edit it (no file = no script). Keys only, never the
# game's words. `story-build` reads this file (lowered); the DWS beside it is the proven intermediate; mods import `dw.base`.
from dw import *
from dw.text import text
from dw.names import *

villa = screen(Screen.volume_villa_141)
shogungekomon = villa.npc(Species.ShogunGekomon, slot=0)
gekomon1 = villa.npc(Species.Gekomon, slot=1)
gekomon2 = villa.npc(Species.Gekomon, slot=2)
gekomon3 = villa.npc(Species.Gekomon, slot=3)
t5 = text.s135.sec5
t6 = text.s135.sec6
t7 = text.s135.sec7
t8 = text.s135.sec8
t81 = text.s135.sec81

@villa.on_enter
def enter():    # section 254
    pass

@shogungekomon.on_talk
def talk():    # section 5
    tamer.walk(-77, 119, camera=True, wait=False)
    partner.walk(397, 151, wait=False)
    tamer.arrived()
    partner.arrived()
    tamer.face(shogungekomon)
    partner.face(shogungekomon)
    wait(500)
    camera.to(-400, 2100, speed=20)
    camera.arrived()
    sound(8, 1)
    say(t5.u0)
    tamer.play(22)
    wait(1000)
    tamer.say(t5.u1)
    tamer.play(anim.idle)
    say(t5.u2)
    tamer.play(23)
    wait(1000)
    tamer.say(t5.u3)
    tamer.play(anim.idle)
    play(5)
    wait(1900)
    play(anim.idle)
    say(t5.u4)
    tamer.say(t5.u5)
    say(t5.u6)
    if not misty_trees_visited:
        tamer.say(t5.u7)
    if misty_trees_visited:
        tamer.say(t5.u8)
    say(t5.u9)
    if cherrymon_met:
        tamer.say(t5.u22)
        say(t5.u23)
        play(anim.idle)
        narrator.say(t5.u24)
        if engine.item_did_not_fit and not has(Item.Digiseabass):
            narrator.say(t5.u25)
            engine.picker_mode.clear()
            call(Routine.choose_item)
            take_picked(all=True)
        give(Item.Digiseabass)
        say(t5.u26)
        tamer.play(19)
        wait(1000)
        tamer.say(t5.u27)
        say(t5.u28)
        play(30)
        wait(2750)
        play(anim.idle)
        shogun_gekomon_met.set()
        camera.on(tamer, speed=10)
        camera.arrived()
        return
    tamer.play(16)
    wait(1000)
    tamer.say(t5.u10)
    say(t5.u11)
    tamer.play(25)
    wait(1000)
    tamer.say(t5.u12)
    play(5)
    wait(1900)
    play(anim.idle)
    say(t5.u13)
    tamer.say(t5.u14)
    say(t5.u15)
    tamer.say(t5.u16)
    say(t5.u17)
    play(anim.idle)
    tamer.play(19)
    wait(1000)
    tamer.say(t5.u18)
    say(t5.u19)
    say(t5.u20)
    play(31)
    sound(8, 0)
    wait(3500)
    play(anim.idle)
    tamer.play(15)
    wait(1500)
    say(t5.u21)
    play(30)
    wait(2750)
    play(anim.idle)
    shogun_gekomon_met.set()
    misty_trees_fog_spell_cast.set()
    camera.on(tamer, speed=10)
    camera.arrived()
    return

@villa.on_use(1)
def use1():    # section 81
    tamer.face(shogungekomon)
    partner.face(shogungekomon)
    wait(500)
    camera.to(-400, 2100, speed=20)
    camera.arrived()
    sound(8, 1)
    if monzaemon_costume_tried and partner.species != Species.Monzaemon:
        shogungekomon.say(t81.u0)
        tamer.say(t81.u1)
        shogungekomon.say(t81.u2)
        monzaemon_costume_tried.clear()
        camera.on(tamer, speed=10)
        camera.arrived()
        return
    if merit_shop_explained:
        call(Routine.merit_shop, arg=5)
        camera.on(tamer, speed=10)
        camera.arrived()
        if has(Item.AmazingRod):
            take(Item.AmazingRod)
            have_amazing_rod.set()
            shogungekomon.say(t81.u3)
        return
    if not shogun_gekomon_met:
        return gekomon1.talk()
    sound(8, 1)
    shogungekomon.say(t81.u4)
    camera.on(tamer, speed=10)
    camera.arrived()

@gekomon1.on_talk
def talk():    # section 6
    if merit_shop_explained:
        say(t6.u0)
        return
    say(t6.u1)

@gekomon2.on_talk
def talk():    # section 7
    say(t7.u0)
    say(t7.u1)
    say(t7.u2)
    merit_shop_explained.set()

@gekomon3.on_talk
def talk():    # section 8
    if not recruited(Species.Greymon):
        say(t8.u0)
        return
    say(t8.u1)
    tamer.say(t8.u2)
    say(t8.u3)
    tamer.say(t8.u4)
    narrator.say(t8.u5)
    return

# the section table, in the order of the original header
sections(254, 5, 81, 6, 7, 8)
