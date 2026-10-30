# The Python view of script 106 of DG.SCN: screen 110 Native Forest.
# Made from the disc by `dws story-base`; the source of the story since 2026-10-15: edit it (no file = no script). Keys only, never the
# game's words. `story-build` reads this file (lowered); the DWS beside it is the proven intermediate; mods import `dw.base`.
from dw import *
from dw.text import text

forest = screen(Screen.native_forest_110)
sukamon0 = forest.npc(Species.Sukamon, slot=0)
sukamon1 = forest.npc(Species.Sukamon, slot=1)
t5 = text.s106.sec5
t81 = text.s106.sec81

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

@forest.on_use(1)
def use1():    # section 81
    tamer.turn(1536)
    narrator.say(t81.u0)

@sukamon0.on_talk
def talk():    # section 5
    say(t5.u0)
    leave()

@sukamon1.on_talk
def talk():    # section 6
    dws(r"""
        say(sukamon1, text("s106.sec6.u0"));
        choice {
            text("s106.sec6.m0.o0") => {}
            text("s106.sec6.m0.o1") => {
                choice {
                    text("s106.sec6.m2.o0") => {
                        store_date(date_year);
                        add_minutes_to_date_at(date_year, 60);
                        advance_to_date_at(date_year);
                        return;
                    }
                    text("s106.sec6.m2.o1") => {
                        store_date(date_year);
                        add_minutes_to_date_at(date_year, 360);
                        advance_to_date_at(date_year);
                        return;
                    }
                    text("s106.sec6.m2.o2") => {
                        store_date(date_year);
                        add_minutes_to_date_at(date_year, 1440);
                        advance_to_date_at(date_year);
                        return;
                    }
                    cancel => {
                        return;
                    }
                }
            }
            text("s106.sec6.m0.o2") => {
                learn_move(tech("Fire Tower"));
                learn_move(tech("Prominence Beam"));
                learn_move(tech("Spit Fire"));
                learn_move(tech("Red Inferno"));
                learn_move(tech("Magma Bomb"));
                learn_move(tech("Heat Laser"));
                learn_move(tech("Inifinity Burn"));
                learn_move(tech("Meltdown"));
                learn_move(tech("Thunder Justice"));
                learn_move(tech("Spinning Shot"));
                learn_move(tech("Electric Cloud"));
                learn_move(tech("Megalo Spark"));
                learn_move(tech("Static Elect"));
                learn_move(tech("Wind Cutter"));
                learn_move(tech("Confused Storm"));
                learn_move(tech("Hurricane"));
                learn_move(tech("Giga Freeze"));
                learn_move(tech("Ice Statue"));
                learn_move(tech("Winter Blast"));
                learn_move(tech("Ice Needle"));
                learn_move(tech("Water Blit"));
                learn_move(tech("Aqua Magic"));
                learn_move(tech("Aurora Freeze"));
                learn_move(tech("Tear Drop"));
                learn_move(tech("Power Crane"));
                learn_move(tech("All Range Beam"));
                learn_move(tech("Metal Sprinter"));
                learn_move(tech("Pulse Laser"));
                learn_move(tech("Delete Program"));
                learn_move(tech("DG Dimension"));
                learn_move(tech("Full Potential"));
                learn_move(tech("Reverse Prog"));
                learn_move(tech("Poison Powder"));
                learn_move(tech("Bug"));
                learn_move(tech("Mass Morph"));
                learn_move(tech("Insect Plague"));
                learn_move(tech("Charm Perfume"));
                learn_move(tech("Poison Claw"));
                learn_move(tech("Danger Sting"));
                learn_move(tech("Green Trap"));
                learn_move(tech("Tremar"));
                learn_move(tech("Muscle Charge"));
                learn_move(tech("War Cry"));
                learn_move(tech("Sonic Jab"));
                learn_move(tech("Dynamite Kick"));
                learn_move(tech("Counter"));
                learn_move(tech("Megaton Punch"));
                learn_move(tech("Buster Dive"));
                learn_move(tech("Odor Spray"));
                learn_move(tech("Poop Spd Toss"));
                learn_move(tech("Big Poop Toss"));
                learn_move(tech("Big Rnd Toss"));
                learn_move(tech("Poop Rnd Toss"));
                learn_move(tech("Rnd Spd Toss"));
                learn_move(tech("Horizontal Kick"));
                learn_move(tech("Ult Poop Hell"));
            }
            cancel => {
                return;
            }
        }
        loop {
            choice {
                text("s106.sec6.m1.o0") => {
                    choice {
                        text("s106.sec6.m3.o0") => {
                            add_stat(0, 50);
                            add_stat(1, 50);
                            add_stat(2, 50);
                            add_stat(3, 50);
                            add_stat(4, 500);
                            add_stat(5, 500);
                            add_stat(6, 500);
                            add_stat(7, 500);
                        }
                        text("s106.sec6.m3.o1") => {
                            add_stat(0, 100);
                            add_stat(1, 100);
                            add_stat(2, 100);
                            add_stat(3, 100);
                            add_stat(4, 1000);
                            add_stat(5, 1000);
                            add_stat(6, 1000);
                            add_stat(7, 1000);
                        }
                        text("s106.sec6.m3.o2") => {
                            add_stat(0, 200);
                            add_stat(1, 200);
                            add_stat(2, 200);
                            add_stat(3, 200);
                            add_stat(4, 2000);
                            add_stat(5, 2000);
                            add_stat(6, 2000);
                            add_stat(7, 2000);
                        }
                        cancel => {
                            return;
                        }
                    }
                }
                text("s106.sec6.m1.o1") => {
                    choice {
                        text("s106.sec6.m4.o0") => {
                            reduce_stat(0, 50);
                            reduce_stat(1, 50);
                            reduce_stat(2, 50);
                            reduce_stat(3, 50);
                            reduce_stat(4, 500);
                            reduce_stat(5, 500);
                            reduce_stat(6, 500);
                            reduce_stat(7, 500);
                        }
                        text("s106.sec6.m4.o1") => {
                            reduce_stat(0, 100);
                            reduce_stat(1, 100);
                            reduce_stat(2, 100);
                            reduce_stat(3, 100);
                            reduce_stat(4, 1000);
                            reduce_stat(5, 1000);
                            reduce_stat(6, 1000);
                            reduce_stat(7, 1000);
                        }
                        text("s106.sec6.m4.o2") => {
                            reduce_stat(0, 200);
                            reduce_stat(1, 200);
                            reduce_stat(2, 200);
                            reduce_stat(3, 200);
                            reduce_stat(4, 2000);
                            reduce_stat(5, 2000);
                            reduce_stat(6, 2000);
                            reduce_stat(7, 2000);
                        }
                        cancel => {
                            return;
                        }
                    }
                }
                text("s106.sec6.m1.o2") => {
                    set_stat(0, 50);
                    set_stat(1, 50);
                    set_stat(2, 50);
                    set_stat(3, 50);
                    set_stat(4, 500);
                    set_stat(5, 500);
                    set_stat(6, 500);
                    set_stat(7, 500);
                }
                cancel => {
                    return;
                }
            }
        }
        end_selection();
    """)

# the section table, in the order of the original header
sections(254, 81, 5, 6)
