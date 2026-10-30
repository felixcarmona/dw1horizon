# The Python view of script 189 of DG.SCN: screen 233 Mt. Panorama Spore Area.
# Made from the disc by `dws story-base`; the source of the story since 2026-10-15: edit it (no file = no script). Keys only, never the
# game's words. `story-build` reads this file (lowered); the DWS beside it is the proven intermediate; mods import `dw.base`.
from dw import *
from dw.text import text
from dw.names import *

area = screen(Screen.mt_panorama_spore_area_233)
unimon = area.npc(Species.Unimon153, slot=0)
t5 = text.s189.sec5

@area.on_enter
def enter():    # section 254
    roll = random.roll(99)
    if roll <= 14:
        spawn_item(Item.Digimushrm, at=(350, -1450))
    roll = random.roll(99)
    if roll <= 14:
        spawn_item(Item.Digimushrm, at=(650, -1150))
    roll = random.roll(99)
    if roll <= 14:
        spawn_item(Item.Digimushrm, at=(1050, -950))
    roll = random.roll(99)
    if roll <= 14:
        spawn_item(Item.Digimushrm, at=(1350, -550))
    roll = random.roll(99)
    if roll <= 5:
        spawn_item(Item.Happymushrm, at=(650, -1550))
    if not recruited(Species.Unimon) and centar_clinic_intro_seen:
        unimon.play(28)

@unimon.on_talk(scene=True)
def talk():    # section 5
    if recruited(Species.Poyomon):
        sound(8, 9)
        say(t5.u0)
        tamer.say(t5.u1)
    else:
        sound(8, 9)
        say(t5.u2)
        tamer.say(t5.u3)
        say(t5.u4)
        tamer.say(t5.u5)
    tamer.play(4)
    wait(500)
    pick = pick_item()
    if pick is Picked.EMPTY:
        tamer.say(t5.u6)
    else:
        if engine.arg in (Item.SmRecovery, Item.MedRecovery, Item.LrgRecovery, Item.SupRecovery):
            take_picked()
        elif engine.arg in (Item.DoubleFlop, Item.Omnipotent, Item.Bandage, Item.Medicine):
            take_picked()
        else:
            tamer.say(t5.u7)
            tamer.say(t5.u16)
            sound(8, 9)
            say(t5.u17)
            recruit(Species.Poyomon)
            return
        tamer.play(anim.offer_item)
        wait(1000)
        tamer.play(anim.idle)
        wait(250)
        sound(8, 9)
        say(t5.u8)
        play(29, wait=True)
        tamer.say(t5.u9)
        say(t5.u10)
        tamer.say(t5.u11)
        say(t5.u12)
        tamer.say(t5.u13)
        sound(8, 9)
        say(t5.u14)
        while True:
            run(-93, -1821, wait=False)
            if glances >= 3:
                break
            glances.add(1)
            sound(8, 0)
            wait(1000)
            tamer.face(unimon)
            partner.face(unimon)
        arrived()
        send_to_city(line=t5.u15, species=Species.Unimon, sound=(8, 8), prosperity=2, camera=False)
        return
    tamer.say(t5.u16)
    sound(8, 9)
    say(t5.u17)
    recruit(Species.Poyomon)
    return

# the section table, in the order of the original header
sections(254, 5)
