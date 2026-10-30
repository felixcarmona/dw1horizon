# The Python view of script 4 of DG.SCN: screen 3 Native Forest.
# Made from the disc by `dws story-base`; the source of the story since 2026-10-15: edit it (no file = no script). Keys only, never the
# game's words. `story-build` reads this file (lowered); the DWS beside it is the proven intermediate; mods import `dw.base`.
from dw import *
from dw.text import text
from dw.names import *

forest = screen(Screen.native_forest_3)
etemon = forest.npc(Species.Etemon162, slot=0)
aruraumon1 = forest.npc(Species.Aruraumon, slot=1)
aruraumon2 = forest.npc(Species.Aruraumon, slot=2)
goblimon3 = forest.npc(Species.Goblimon, slot=3)
goblimon4 = forest.npc(Species.Goblimon, slot=4)
t51 = text.s004.sec51
t6 = text.s004.sec6
t6_dup4 = text.s004.sec6_dup4
t7 = text.s004.sec7
t8 = text.s004.sec8
t81 = text.s004.sec81
t9 = text.s004.sec9

@forest.on_enter
def enter():    # section 254
    roll = random.roll(99)
    if roll <= 2:
        spawn_item(Item.BlueApple, at=(-550, 1850))
    roll = random.roll(99)
    if roll <= 24:
        spawn_item(Item.Digimushrm, at=(-750, -750))
    roll = random.roll(99)
    if roll <= 2:
        spawn_item(Item.Deluxmushrm, at=(250, -150))
    roll = random.roll(99)
    if roll <= 59:
        spawn_item(Item.Digimushrm, at=(1550, 850))

@forest.on_use(1)
def use1():    # section 81
    tamer.turn(2048)
    wait(250)
    tamer.play(16)
    wait(750)
    tamer.say(t81.u0)
    tamer.play(anim.idle)
    narrator.say(t81.u1)
    if not recruited(Species.Etemon):
        tamer.say(t81.u2)

@forest.on_step(0)
def step0():    # section 51
    if recruited(Species.Etemon) or engine.prosperity < 50:
        return
    raw.entity_walk_to_entity(partner, 1, tamer)
    partner.arrived()
    partner.turn(2048)
    wait(250)
    narrator.say(t51.u0)
    sound(8, 5)
    etemon.play(29)
    raw.entity_move_to_axis(etemon, 0, 1, 12)
    etemon.arrived()
    etemon.play(anim.idle)
    sound(8, 6)
    damage_percent.set(30)
    raw.deal_damage(damage_percent)
    tamer.play(15)
    partner.play(40)
    wait(1500)
    fight(etemon, escape=False)
    tamer.face(etemon)
    etemon.face(tamer)
    partner.face(etemon)
    etemon.say(t51.u1)
    sound(8, 13)
    tamer.play(20)
    wait(750)
    tamer.say(t51.u2)
    tamer.play(anim.idle)
    sound(8, 13)
    etemon.play(7)
    etemon.say(t51.u3)
    etemon.walk_away(0, 0, looks=4)
    etemon.leave()
    glances.set(0)
    camera.on(tamer, speed=10)
    sound.jingle()
    narrator.say(t51.u4)
    recruit(Species.Etemon)
    engine.prosperity.add(3)

@aruraumon1.on_talk
def talk():    # section 6
    recruitable(aruraumon1, line=t6.u0)

@aruraumon2.on_talk
def talk():    # section 7
    recruitable(aruraumon2, line=t7.u0)

@goblimon3.on_talk
def talk():    # section 8
    recruitable(goblimon3, line=t8.u0)

@goblimon4.on_talk
def talk():    # section 9
    recruitable(goblimon4, line=t9.u0)
    return

def sec6_dup4():    # shared code (the disc's label sec6_dup4)
    aruraumon1.say(t6_dup4.u0)
    fight()
    recruit(Species.Aruraumon)

# the section table, in the order of the original header
sections(254, 81, 51, 6, (6, sec6_dup4), 7, 8, 9)
