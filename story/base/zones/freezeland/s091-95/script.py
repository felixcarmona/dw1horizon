# The Python view of script 91 of DG.SCN: screen 95 Freezeland.
# Made from the disc by `dws story-base`; the source of the story since 2026-10-15: edit it (no file = no script). Keys only, never the
# game's words. `story-build` reads this file (lowered); the DWS beside it is the proven intermediate; mods import `dw.base`.
from dw import *
from dw.text import text
from dw.names import *

freezeland = screen(Screen.freezeland_95)
garurumon = freezeland.npc(Species.Garurumon144, slot=0)
snowagumon1 = freezeland.npc(Species.SnowAgumon, slot=1)
snowagumon2 = freezeland.npc(Species.SnowAgumon, slot=2)
hyogamon3 = freezeland.npc(Species.Hyogamon, slot=3)
hyogamon4 = freezeland.npc(Species.Hyogamon, slot=4)
t5 = text.s091.sec5
t6 = text.s091.sec6
t7 = text.s091.sec7
t8 = text.s091.sec8
t9 = text.s091.sec9

@freezeland.on_enter
def enter():    # section 254
    roll = random.roll(99)
    if roll <= 5:
        spawn_item(Item.Digimushrm, at=(-50, 1350))
    roll = random.roll(99)
    if roll <= 17:
        spawn_item(Item.Digimushrm, at=(950, -550))
    roll = random.roll(99)
    if roll <= 7:
        spawn_item(Item.Digimushrm, at=(-150, -1150))
    roll = random.roll(99)
    if roll <= 2:
        spawn_item(Item.IceMushrm, at=(-1150, -1050))

@snowagumon1.on_talk
def talk():    # section 6
    recruitable(snowagumon1, line=t6.u0)

@snowagumon2.on_talk
def talk():    # section 7
    recruitable(snowagumon2, line=t7.u0)

@hyogamon3.on_talk
def talk():    # section 8
    recruitable(hyogamon3, line=t8.u0)

@hyogamon4.on_talk
def talk():    # section 9
    recruitable(hyogamon4, line=t9.u0)

@garurumon.on_talk
def talk():    # section 5
    if garurumon_duel_promised:
        if garurumon_duel_promised and clock.hour >= 15 and clock.hour <= 17 and garurumon_promise_days == 1:
            say(t5.u4)
        else:
            say(t5.u5)
        tamer.say(t5.u6)
        tamer.face(partner)
        tamer.arrived()
        tamer.play(20)
        raw.show_textbox(t5.u7)
        tamerless_battle.set()
        fight(garurumon, escape=False)
        tamerless_battle.clear()
        tamer.face(garurumon)
        face(tamer)
        partner.face(garurumon)
        say(t5.u8)
        tamer.say(t5.u9)
        say(t5.u10)
        narrator.say(t5.u11)
        tamer.play(19)
        wait(2000)
        say(t5.u12)
        walk_away(-2000, -100, looks=6, pause=500)
        send_to_city(line=t5.u13, species=Species.Garurumon, prosperity=2, camera=False)
        camera.on(tamer, speed=10)
        camera.arrived()
        return step0()
    say(t5.u0)
    fight(garurumon, escape=False)
    tamer.face(garurumon)
    face(tamer)
    partner.face(garurumon)
    say(t5.u1)
    tamer.play(16)
    engine.no_cancel.set()
    dws(r"""
        choice(open) {
            text("s091.sec5.m0.o0") => {}
            text("s091.sec5.m0.o1") => {}
        }
    """)
    say(t5.u2)
    dws(r"""
        choice(open) {
            text("s091.sec5.m1.o0") => {}
            text("s091.sec5.m1.o1") => {}
        }
    """)
    tamer.play(16)
    engine.no_cancel.clear()
    say(t5.u3)
    garurumon_duel_promised.set()
    raw.store_date(garurumon_promise_days)
    walk_away(-2050, -150, looks=6, pause=500)
    leave()
    glances.set(0)
    camera.on(tamer, speed=10)
    camera.arrived()

@freezeland.on_step(0)
def step0():    # section 51
    if not partner.sick or digivolve_scene_seen:
        return
    if partner.species in (Species.Agumon, Species.Greymon, Species.Tyrannomon, Species.Meramon, Species.Monochromon):
        jump_to_script(203, 51)
    if partner_type in (19, 32, 51, 1, 2):
        jump_to_script(203, 51)
    if partner_type in (15, 16, 29, 30, 43):
        jump_to_script(203, 51)
    if partner_type in (44, 21):
        jump_to_script(203, 51)
    return

# the section table, in the order of the original header
sections(254, 6, 7, 8, 9, 5, 51)
