# The Python view of script 79 of DG.SCN: screen 82 Ancient Glacial Region.
# Made from the disc by `dws story-base`; the source of the story since 2026-10-15: edit it (no file = no script). Keys only, never the
# game's words. `story-build` reads this file (lowered); the DWS beside it is the proven intermediate; mods import `dw.base`.
from dw import *
from dw.text import text
from dw.names import *

region = screen(Screen.ancient_glacial_region_82)
tyrannomon0 = region.npc(Species.Tyrannomon132, slot=0)
tyrannomon1 = region.npc(Species.Tyrannomon132, slot=1)
slot2 = region.npc(None, slot=2)    # the .MAP has MasterTyrannomon here; the script spawns what stands here
mastertyrannomon = region.npc(Species.MasterTyrannomon, slot=3)
t51 = text.s079.sec51
t6 = text.s079.sec6
t7 = text.s079.sec7
t8 = text.s079.sec8

@region.on_enter
def enter():    # section 254
    roll = random.roll(99)
    if roll <= 15:
        spawn_item(Item.Digimushrm, at=(450, -550))
    roll = random.roll(99)
    if roll <= 6:
        spawn_item(Item.Digimushrm, at=(-950, 250))
    roll = random.roll(99)
    if roll <= 17:
        spawn_item(Item.Digimushrm, at=(-1050, 350))
    roll = random.roll(99)
    if roll <= 3:
        spawn_item(Item.Happymushrm, at=(850, 1550))
    call(Routine.save_clock_speed, arg=0)

@region.on_step(0)
def step0():    # section 51
    if glacial_tyrannomon_let_through:
        return
    raw.entity_walk_to_entity(partner, 1, tamer)
    tamer.arrived()
    partner.arrived()
    tamer.face(tyrannomon0)
    partner.face(tyrannomon0)
    tyrannomon0.say(t51.u0)
    tamer.play(19)
    wait(750)
    tamer.say(t51.u1)
    tamer.play(anim.idle)
    tyrannomon0.say(t51.u2)
    dws(r"""
        choice(open) {
            text("s079.sec51.m0.o0") => {
                say(tyrannomon0, text("s079.sec51.u3"));
                say(tamer, text("s079.sec51.u4"));
                say(tyrannomon0, text("s079.sec51.u5"));
                say(tamer, text("s079.sec51.u6"));
                say(tyrannomon0, text("s079.sec51.u7"));
                animate(tamer, 19);
                wait(15);
                say(tamer, text("s079.sec51.u8"));
                animate(tamer, anim.idle);
                say(tyrannomon0, text("s079.sec51.u9"));
                run(tyrannomon0, -740, 2145);
                await tyrannomon0;
                face(tyrannomon0, tamer);
                glacial_tyrannomon_let_through = true;
                goto L7;
            }
            text("s079.sec51.m0.o1") => {
                goto L8;
            }
        }
    """)

@tyrannomon0.on_talk
def talk():    # section 5
    return L7()

@tyrannomon1.on_talk
def talk():    # section 6
    if not speedy_time_zone_entered:
        say(t6.u0)
        return
    if not meteormon_checked:
        say(t6.u1)
        tamer.say(t6.u2)
        say(t6.u3)
        return
    if meteormon_checked and recruited(Species.Tyrannomon):
        return
    say(t6.u4)
    tamer.say(t6.u5)
    tamer.play(22)
    say(t6.u6)
    tamer.say(t6.u7)
    spawn(Species.MasterTyrannomon, slot=2)
    sound(8, 7)
    slot2.say(t6.u8)
    tamer.face(slot2)
    partner.face(slot2)
    face(slot2)
    tamer.arrived()
    partner.arrived()
    arrived()
    slot2.walk(64, 1093, wait=False)
    wait(750)
    sound(8, 6)
    tamer.face(slot2)
    partner.face(slot2)
    face(slot2)
    slot2.walk(64, 1093, wait=False)
    wait(750)
    sound(8, 6)
    tamer.face(slot2)
    partner.face(slot2)
    face(slot2)
    slot2.walk(64, 1093, wait=False)
    wait(750)
    sound(8, 6)
    tamer.face(slot2)
    partner.face(slot2)
    face(slot2)
    slot2.walk(64, 1093)
    sound(8, 6)
    tamer.face(slot2)
    partner.face(slot2)
    face(slot2)
    slot2.face(tamer)
    tamer.arrived()
    partner.arrived()
    arrived()
    slot2.arrived()
    tamer.play(23)
    raw.show_textbox(t6.u9)
    say(t6.u10)
    slot2.say(t6.u11)
    sound(8, 8)
    tamer.play(16)
    wait(750)
    tamer.say(t6.u12)
    tamer.play(anim.idle)
    say(t6.u13)
    slot2.say(t6.u14)
    sound(8, 8)
    say(t6.u15)
    tamer.face(tyrannomon1)
    wait(500)
    tamer.say(t6.u16)
    tamer.face(slot2)
    tamer.arrived()
    slot2.say(t6.u17)
    sound(8, 7)
    say(t6.u18)
    face(tamer)
    arrived()
    say(t6.u19)
    tamer.face(tyrannomon1)
    tamer.arrived()
    tamer.play(19)
    tamer.say(t6.u20)
    say(t6.u21)
    while True:
        run(-243, -614, wait=False)
        if glances >= 6:
            break
        glances.add(1)
        wait(500)
        tamer.face(tyrannomon1)
        partner.face(tyrannomon1)
        slot2.face(tyrannomon1)
    arrived()
    send_to_city(line=t6.u22, species=Species.Tyrannomon, sound=(8, 9), prosperity=2, camera=False)
    slot2.say(t6.u23)

@slot2.on_talk
def talk():    # section 7
    tamer.face(slot2)
    tamer.arrived()
    tamer.play(23)
    say(t7.u0)

@mastertyrannomon.on_talk
def talk():    # section 8
    tamer.face(mastertyrannomon)
    tamer.arrived()
    tamer.play(23)
    say(t8.u0)
    return

def L7():    # shared code (the disc's label L7)
    tyrannomon0.say(t51.u10)

def L8():    # shared code (the disc's label L8)
    tyrannomon0.say(t51.u11)
    tamer.walk(-326, 1203, camera=True)

# the section table, in the order of the original header
sections(254, 51, 5, 6, 7, 8)
