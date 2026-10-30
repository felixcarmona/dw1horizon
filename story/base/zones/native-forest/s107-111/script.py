# The Python view of script 107 of DG.SCN: screen 111 Native Forest.
# Made from the disc by `dws story-base`; the source of the story since 2026-10-15: edit it (no file = no script). Keys only, never the
# game's words. `story-build` reads this file (lowered); the DWS beside it is the proven intermediate; mods import `dw.base`.
from dw import *
from dw.text import text
from dw.names import *

forest = screen(Screen.native_forest_111)
sukamon0 = forest.npc(Species.Sukamon, slot=0)
sukamon1 = forest.npc(Species.Sukamon, slot=1)
t5 = text.s107.sec5
t51 = text.s107.sec51
t6 = text.s107.sec6

@forest.on_enter
def enter():    # section 254
    roll = random.roll(99)
    if roll <= 19:
        spawn_item(Item.Digimushrm, at=(1150, -450))
    roll = random.roll(99)
    if roll <= 4:
        spawn_item(Item.Happymushrm, at=(-1050, 350))
    roll = random.roll(99)
    if roll <= 14:
        spawn_item(Item.Digimushrm, at=(550, -1350))

@forest.on_step(0)
def step0():    # section 51
    if not native_forest_rockslide_cleared_seen and recruited(Species.Tokomon):
        narrator.say(t51.u0)
        native_forest_rockslide_cleared_seen.set()

@sukamon0.on_talk
def talk():    # section 5
    raw.store_date(date_year)
    say(t5.u0)
    raw.store_digimon_type(partner_type)
    raw.store_digimon_value(partner_type, partner_attribute)
    if partner_attribute == 1:
        say(t5.u1)
    if partner_attribute == 2:
        say(t5.u2)
    if partner_attribute == 3:
        say(t5.u3)
    partner.add(tiredness=10)
    partner.sub(happiness=10)

@sukamon1.on_talk
def talk():    # section 6
    say(t6.u0)
    match choose(a=t6.m0.o0, b=t6.m0.o1, c=t6.m0.o2):
        case "a":
            match choose(a=t6.m1.o0, b=t6.m1.o1, c=t6.m1.o2):
                case "a":
                    partner.set(offense=999)
                    partner.set(defense=999)
                    partner.set(speed=999)
                    partner.set(brain=999)
                    partner.set(max_hp=9999)
                    partner.set(max_mp=9999)
                    partner.set(hp=9999)
                    partner.set(mp=9999)
                case "b":
                    partner.set(offense=1)
                    partner.set(defense=1)
                    partner.set(speed=1)
                    partner.set(brain=1)
                    partner.set(max_hp=1)
                    partner.set(max_mp=1)
                    partner.set(hp=1)
                    partner.set(mp=1)
                case "c":
                    partner.set(offense=500)
                    partner.set(defense=500)
                    partner.set(speed=500)
                    partner.set(brain=500)
                    partner.set(max_hp=5000)
                    partner.set(max_mp=5000)
                    partner.set(hp=5000)
                    partner.set(mp=5000)
        case "b":
            match choose(a=t6.m2.o0, b=t6.m2.o1, c=t6.m2.o2):
                case "a":
                    raw.store_date(date_year)
                    raw.add_minutes_to_date_at(date_year, 60)
                    raw.advance_to_date_at(date_year)
                case "b":
                    raw.store_date(date_year)
                    raw.add_minutes_to_date_at(date_year, 360)
                    raw.advance_to_date_at(date_year)
                case "c":
                    raw.store_date(date_year)
                    raw.add_minutes_to_date_at(date_year, 1440)
                    raw.advance_to_date_at(date_year)
        case "c":
            jump_to_script(205, 6)

# the section table, in the order of the original header
sections(254, 51, 5, 6)
