# The Python view of script 10 of DG.SCN: screen 9 Digimon Bridge.
# Made from the disc by `dws story-base`; the source of the story since 2026-10-15: edit it (no file = no script). Keys only, never the
# game's words. `story-build` reads this file (lowered); the DWS beside it is the proven intermediate; mods import `dw.base`.
from dw import *
from dw.text import text

bridge = screen(Screen.digimon_bridge_9)
aruraumon = bridge.npc(Species.Aruraumon, slot=0)
slot1 = bridge.npc(None, slot=1)    # the .MAP has Ninjamon175 here; the script spawns what stands here
tsukaimon = bridge.npc(Species.Tsukaimon, slot=2)
etemon = bridge.npc(Species.Etemon162, slot=3)
t5 = text.s010.sec5
t51 = text.s010.sec51
t7 = text.s010.sec7
t8 = text.s010.sec8

@bridge.on_enter
def enter():    # section 254
    if recruited(Species.Kunemon):
        objects[68].show()
        objects[69].show()
        objects[70].show()
    else:
        raw.set_rect_impassable(0, 22, 16, 3, 12)
    if recruited(Species.Kunemon) and engine.prosperity >= 35:
        objects[71].hide()
        objects[72].hide()
        objects[73].hide()
    roll = random.roll(99)
    if roll <= 39:
        spawn_item(Item.Digimushrm, at=(-1250, 150))
    roll = random.roll(99)
    if roll <= 3:
        spawn_item(Item.BlueApple, at=(-1150, -250))

@aruraumon.on_talk
def talk():    # section 5
    recruitable(aruraumon, line=t5.u0)

@tsukaimon.on_talk
def talk():    # section 7
    recruitable(tsukaimon, line=t7.u0)

@bridge.on_step(4)
def step4():    # section 55
    pass

@bridge.on_step(0)
def step0():    # section 51
    if recruited(Species.Ninjamon):
        return
    if not recruited(Species.Devimon) and not recruited(Species.Numemon) and not recruited(Species.Mojyamon) and not recruited(Species.Mamemon):
        return
    narrator.say(t51.u0)
    tamer.play(16)
    wait(1000)
    tamer.play(anim.idle)
    tamer.run(-1050, -1473, wait=False)
    partner.run(-709, -1473, wait=False)
    tamer.arrived()
    partner.arrived()
    tamer.turn(2048)
    partner.turn(2048)
    call(Routine.ninjamon_effect)
    sound(8, 0)
    camera.to(-836, -663, speed=20)
    camera.arrived()
    objects[41].hide()
    raw.move_object_to(1, 41, 1, 7, 153, 349)
    wait(600)
    raw.move_object_to(1, 41, 1, 7, 184, 381)
    wait(600)
    raw.move_object_to(1, 41, 1, 7, 153, 411)
    wait(600)
    raw.move_object_to(1, 41, 1, 7, 184, 443)
    wait(600)
    raw.move_object_to(1, 41, 1, 7, 153, 475)
    wait(600)
    spawn(Species.Ninjamon175, slot=1, autotalk=True)
    objects[42].hide()
    objects[43].hide()
    objects[44].hide()
    objects[45].hide()
    objects[46].hide()
    objects[47].hide()
    objects[48].hide()
    objects[49].hide()
    objects[50].hide()
    objects[51].hide()
    objects[52].hide()
    objects[53].hide()
    objects[54].hide()
    objects[55].hide()
    objects[56].hide()
    objects[57].hide()
    objects[58].hide()
    objects[59].hide()
    objects[60].hide()
    objects[61].hide()
    objects[62].hide()
    objects[63].hide()
    objects[64].hide()
    objects[65].hide()
    objects[66].hide()
    objects[67].hide()
    objects[42].animate(26)
    objects[41].show()
    sound(8, 0)
    slot1.play(28)
    wait(500)
    objects[42].show()
    objects[43].show()
    objects[44].show()
    objects[45].show()
    objects[46].show()
    objects[47].show()
    objects[48].show()
    objects[49].show()
    objects[50].show()
    objects[51].show()
    objects[52].show()
    objects[53].show()
    objects[54].show()
    objects[55].show()
    objects[56].show()
    objects[57].show()
    objects[58].show()
    objects[59].show()
    objects[60].show()
    objects[61].show()
    objects[62].show()
    objects[63].show()
    objects[64].show()
    objects[65].show()
    objects[66].show()
    objects[67].show()
    sound(8, 1)
    wait(500)
    slot1.say(t51.u1)
    tamer.play(15)
    wait(1000)
    slot1.face(tamer)
    wait(500)
    slot1.face(partner)
    wait(500)
    slot1.face(tamer)
    slot1.say(t51.u2)
    if ask(yes=t51.m0.o0, no=t51.m0.o1):
        pass
    else:
        slot1.say(t51.u3)
    fight(slot1, escape=False)
    partner.run(-633, -581, wait=False)
    partner.run(-1033, -481, wait=False)
    slot1.run(-905, -1096, wait=False)
    entity(20).arrived()
    tamer.face(slot1)
    slot1.face(tamer)
    partner.face(slot1)
    tamer.arrived()
    slot1.say(t51.u4)
    tamer.play(19)
    wait(1000)
    tamer.say(t51.u5)
    slot1.say(t51.u6)
    wait(1000)
    slot1.play(28)
    wait(500)
    objects[42].hide()
    objects[43].hide()
    objects[44].hide()
    objects[45].hide()
    objects[46].hide()
    objects[47].hide()
    objects[48].hide()
    objects[49].hide()
    objects[50].hide()
    objects[51].hide()
    objects[52].hide()
    objects[53].hide()
    objects[54].hide()
    objects[55].hide()
    objects[56].hide()
    objects[57].hide()
    objects[58].hide()
    objects[59].hide()
    objects[60].hide()
    objects[61].hide()
    objects[62].hide()
    objects[63].hide()
    objects[64].hide()
    objects[65].hide()
    objects[66].hide()
    objects[67].hide()
    objects[42].animate(26)
    sound(8, 0)
    wait(500)
    slot1.leave()
    wait(2000)
    objects[42].show()
    objects[43].show()
    objects[44].show()
    objects[45].show()
    objects[46].show()
    objects[47].show()
    objects[48].show()
    objects[49].show()
    objects[50].show()
    objects[51].show()
    objects[52].show()
    objects[53].show()
    objects[54].show()
    objects[55].show()
    objects[56].show()
    objects[57].show()
    objects[58].show()
    objects[59].show()
    objects[60].show()
    objects[61].show()
    objects[62].show()
    objects[63].show()
    objects[64].show()
    objects[65].show()
    objects[66].show()
    objects[67].show()
    wait(500)
    sound.jingle()
    narrator.say(t51.u7)
    engine.no_escape.clear()
    camera.on(tamer, speed=10)
    camera.arrived()
    recruit(Species.Ninjamon)
    engine.prosperity.add(2)

@etemon.on_talk
def talk():    # section 8
    say(t8.u0)
    if bits < 50000:
        return
    say(t8.u1)
    if ask(yes=t8.m0.o0, no=t8.m0.o1):
        take(bits=50000)
        give(Item.GoldBanana)
        if engine.item_did_not_fit:
            if has(Item.GoldBanana, 99):
                say(t8.u2)
                give(bits=50000)
                return
            tamer.say(t8.u3)
            pick_item()
            take_picked(all=True)
            give(Item.GoldBanana)
        say(t8.u4)
        return
    say(t8.u5)

@bridge.on_step(1)
def step1():    # section 52
    tamer.walk(-2800, 3000, wait=False)
    if recruited(Species.Patamon) or recruited(Species.Biyomon) or recruited(Species.Unimon) or recruited(Species.Monochromon):
        if recruited(Species.Meramon) or recruited(Species.Tyrannomon) or recruited(Species.Garurumon) or recruited(Species.Frigimon):
            if recruited(Species.Centarumon):
                if recruited(Species.Greymon):
                    warp(Screen.file_city_192, entry=2)
                    return
                warp(Screen.file_city_191, entry=2)
                return
            if recruited(Species.Greymon):
                warp(Screen.file_city_193, entry=2)
                return
            warp(Screen.file_city_190, entry=2)
            return
        if recruited(Species.Centarumon):
            if recruited(Species.Greymon):
                warp(Screen.file_city_195, entry=2)
                return
            warp(Screen.file_city_194, entry=2)
            return
        if recruited(Species.Greymon):
            warp(Screen.file_city_196, entry=2)
            return
        warp(Screen.file_city_189, entry=2)
        return
    if recruited(Species.Betamon) or recruited(Species.Coelamon):
        if recruited(Species.Meramon) or recruited(Species.Tyrannomon) or recruited(Species.Garurumon) or recruited(Species.Frigimon):
            if recruited(Species.Centarumon):
                if recruited(Species.Greymon):
                    warp(Screen.file_city_184, entry=2)
                    return
                warp(Screen.file_city_183, entry=2)
                return
            if recruited(Species.Greymon):
                warp(Screen.file_city_185, entry=2)
                return
            warp(Screen.file_city_182, entry=2)
            return
        if recruited(Species.Centarumon):
            if recruited(Species.Greymon):
                warp(Screen.file_city_187, entry=2)
                return
            warp(Screen.file_city_186, entry=2)
            return
        if recruited(Species.Greymon):
            warp(Screen.file_city_188, entry=2)
            return
        warp(Screen.file_city_181, entry=2)
        return
    if recruited(Species.Meramon) or recruited(Species.Tyrannomon) or recruited(Species.Garurumon) or recruited(Species.Frigimon):
        if recruited(Species.Centarumon):
            if recruited(Species.Greymon):
                warp(Screen.file_city_199, entry=2)
                return
            warp(Screen.file_city_198, entry=2)
            return
        if recruited(Species.Greymon):
            warp(Screen.file_city_200, entry=2)
            return
        warp(Screen.file_city_197, entry=2)
        return
    if recruited(Species.Centarumon):
        if recruited(Species.Greymon):
            warp(Screen.file_city_202, entry=2)
            return
        warp(Screen.file_city_201, entry=2)
        return
    if recruited(Species.Greymon):
        warp(Screen.file_city_203, entry=2)
        return
    warp(Screen.file_city_180, entry=2)
    return

# the section table, in the order of the original header
sections(254, 5, 7, 55, 51, 8, 52)
