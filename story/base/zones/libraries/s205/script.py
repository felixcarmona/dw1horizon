# The Python view of script 205 of DG.SCN (no screen loads it).
# Made from the disc by `dws story-base`; the source of the story since 2026-10-15: edit it (no file = no script). Keys only, never the
# game's words. `story-build` reads this file (lowered); the DWS beside it is the proven intermediate; mods import `dw.base`.
from dw import *

lib = script(205)
slot1 = lib.npc(None, slot=1)    # no NPC of the .MAP in this slot; the script spawns what stands here

@lib.on_enter
def enter():    # section 254
    pass

@slot1.on_talk
def talk():    # section 6
    dws(r"""
        say(slot1, text("s205.sec6.u0"));
        choice {
            text("s205.sec6.m0.o0") => {
                say(slot1, text("s205.sec6.u1"));
                unless (condition(32) || condition(64)) goto l1;
                say(slot1, text("s205.sec6.u2"));
                if (bits >= 300) {
                    take_bits(300);
                } else {
                    say(slot1, text("s205.sec6.u3"));
                    take_bits(300);
                }
                remove_condition(32);
                remove_condition(64);
                show_textbox(text("s205.sec6.u4"));
                return;
                l1:
                say(slot1, text("s205.sec6.u5"));
                set_dialog_owner(tamer);
                set_selection(l2, l3, l4, text("s205.sec6.m1.o0"), text("s205.sec6.m1.o1"), text("s205.sec6.m1.o2"));
                l2:
                say(slot1, text("s205.sec6.u6"));
                if (stat(8) >= 80) {
                    say(slot1, text("s205.sec6.u7"));
                } else if (stat(8) >= 50) {
                    say(slot1, text("s205.sec6.u8"));
                } else if (stat(8) >= 20) {
                    say(slot1, text("s205.sec6.u9"));
                } else {
                    say(slot1, text("s205.sec6.u10"));
                }
                say(slot1, text("s205.sec6.u11"));
                if (stat(9) >= 100) {
                    say(slot1, text("s205.sec6.u12"));
                } else if (stat(9) >= 70) {
                    say(slot1, text("s205.sec6.u13"));
                } else if (stat(9) >= 30) {
                    say(slot1, text("s205.sec6.u14"));
                } else if (stat(9) >= 0) {
                    say(slot1, text("s205.sec6.u15"));
                } else if (stat(9) >= -20) {
                    say(slot1, text("s205.sec6.u16"));
                } else if (stat(9) >= -50) {
                    say(slot1, text("s205.sec6.u17"));
                } else if (stat(9) >= -80) {
                    say(slot1, text("s205.sec6.u18"));
                } else {
                    say(slot1, text("s205.sec6.u19"));
                }
                say(slot1, text("s205.sec6.u20"));
                set_dialog_owner(tamer);
                set_selection(l2, l3, l4, text("s205.sec6.m2.o0"), text("s205.sec6.m2.o1"), text("s205.sec6.m2.o2"));
                end_selection();
                return;
                l3:
                say(slot1, text("s205.sec6.u21"));
                set_dialog_owner(tamer);
                set_selection(l5, l6, l4, text("s205.sec6.m3.o0"), text("s205.sec6.m3.o1"), text("s205.sec6.m3.o2"));
                end_selection();
                return;
                l4:
                say(slot1, text("s205.sec6.u22"));
                return;
                l5:
                if (has(item("Bandage")) < 1 && engine.item_did_not_fit) {
                    say(slot1, text("s205.sec6.u23"));
                    return;
                }
                if (bits >= 400) {
                    take_bits(400);
                    give_item(item("Bandage"), 1);
                } else {
                    say(slot1, text("s205.sec6.u24"));
                    return;
                    l6:
                    if (has(item("Medicine")) < 1 && engine.item_did_not_fit) {
                        say(slot1, text("s205.sec6.u25"));
                        return;
                    }
                    if (bits >= 1200) {
                        take_bits(1200);
                        give_item(item("Medicine"), 1);
                    } else {
                        say(slot1, text("s205.sec6.u26"));
                        return;
                    }
                }
                say(slot1, text("s205.sec6.u27"));
                set_dialog_owner(tamer);
                set_selection(l2, l3, l4, text("s205.sec6.m4.o0"), text("s205.sec6.m4.o1"), text("s205.sec6.m4.o2"));
                end_selection();
                return;
            }
            text("s205.sec6.m0.o1") => {
                say(slot1, text("s205.sec6.u28"));
                if (treasure_hunt.cheap_ordered || treasure_hunt.cheap_ordered) {
                    if (drimogemon_job_days < 3 && treasure_hunt.cheap_ordered) {
                        say(narrator, text("s205.sec6.u36"));
                        return;
                    }
                    if (drimogemon_job_days < 10 && treasure_hunt.pricey_ordered) {
                        say(narrator, text("s205.sec6.u36"));
                        return;
                    }
                    say(slot1, text("s205.sec6.u37"));
                    unless (!treasure_hunt.cheap_ordered) goto l12;
                    if (treasure_hunt.pricey_ordered) {
                        treasure_hunt.pricey_ordered = false;
                    } else {
                        l12:
                        if (treasure_hunt.cheap_roll <= 0) {
                            give_item(item("Koga laws"), 1);
                            random_roll = 90;
                        } else if (treasure_hunt.cheap_roll <= 1) {
                            give_item(item("Flamingwing"), 1);
                            random_roll = 73;
                        } else if (treasure_hunt.cheap_roll <= 2) {
                            give_item(item("Torn tatter"), 1);
                            random_roll = 82;
                        } else if (treasure_hunt.cheap_roll <= 12) {
                            give_item(item("sup.recovery"), 1);
                            random_roll = 3;
                        } else if (treasure_hunt.cheap_roll <= 15) {
                            give_item(item("Restore"), 1);
                            random_roll = 11;
                        } else if (treasure_hunt.cheap_roll <= 19) {
                            give_item(item("Omnipotent"), 1);
                            random_roll = 9;
                        } else if (treasure_hunt.cheap_roll <= 23) {
                            give_item(item("Protection"), 1);
                            random_roll = 10;
                        } else if (treasure_hunt.cheap_roll <= 33) {
                            give_item(item("Large MP"), 1);
                            random_roll = 6;
                        } else if (treasure_hunt.cheap_roll <= 37) {
                            give_item(item("S.Off.disk"), 1);
                            random_roll = 19;
                        } else if (treasure_hunt.cheap_roll <= 41) {
                            give_item(item("S.Def.disk"), 1);
                            random_roll = 20;
                        } else if (treasure_hunt.cheap_roll <= 45) {
                            give_item(item("S.speed.disk"), 1);
                            random_roll = 21;
                        } else if (treasure_hunt.cheap_roll <= 49) {
                            give_item(item("Omni Disk"), 1);
                            random_roll = 18;
                        }
                        l13:
                        if (engine.item_did_not_fit) {
                            say(slot1, text("s205.sec6.u38"));
                            return;
                        }
                        show_textbox(text("s205.sec6.u39"));
                        treasure_hunt.cheap_ordered = false;
                        treasure_hunt.pricey_ordered = false;
                        say(slot1, text("s205.sec6.u40"));
                        return;
                    }
                    if (treasure_hunt.pricey_roll <= 0) {
                        give_item(item("Off. Chip"), 1);
                        random_roll = 23;
                        goto l13;
                    }
                    if (treasure_hunt.pricey_roll <= 1) {
                        give_item(item("HP Chip"), 1);
                        random_roll = 27;
                        goto l13;
                    }
                    if (treasure_hunt.pricey_roll <= 2) {
                        give_item(item("Brain Chip"), 1);
                        random_roll = 25;
                        goto l13;
                    }
                    if (treasure_hunt.pricey_roll <= 3) {
                        give_item(item("Def. Chip"), 1);
                        random_roll = 24;
                        goto l13;
                    }
                    if (treasure_hunt.pricey_roll <= 4) {
                        give_item(item("MP Chip"), 1);
                        random_roll = 28;
                        goto l13;
                    }
                    if (treasure_hunt.pricey_roll <= 5) {
                        give_item(item("Quick Chip"), 1);
                        random_roll = 26;
                        goto l13;
                    }
                    if (treasure_hunt.pricey_roll <= 6) {
                        give_item(item("Koga laws"), 1);
                        random_roll = 90;
                        goto l13;
                    }
                    if (treasure_hunt.pricey_roll <= 7) {
                        give_item(item("Flamingwing"), 1);
                        random_roll = 73;
                        goto l13;
                    }
                    if (treasure_hunt.pricey_roll <= 8) {
                        give_item(item("Torn tatter"), 1);
                        random_roll = 82;
                        goto l13;
                    }
                    if (treasure_hunt.pricey_roll <= 20) {
                        give_item(item("sup.recovery"), 1);
                        random_roll = 3;
                        goto l13;
                    }
                    if (treasure_hunt.pricey_roll <= 29) {
                        give_item(item("Restore"), 1);
                        random_roll = 11;
                        goto l13;
                    }
                    if (treasure_hunt.pricey_roll <= 49) {
                        give_item(item("Omnipotent"), 1);
                        random_roll = 9;
                        goto l13;
                    }
                    say(slot1, text("s205.sec6.u40"));
                    return;
                }
                say(slot1, text("s205.sec6.u29"));
                choice {
                    text("s205.sec6.m5.o0") => {
                        l7:
                        say(slot1, text("s205.sec6.u30"));
                        set_dialog_owner(slot1);
                        set_selection(l7, l8, l9, text("s205.sec6.m6.o0"), text("s205.sec6.m6.o1"), text("s205.sec6.m6.o2"));
                        end_selection();
                    }
                    text("s205.sec6.m5.o1") => {
                        l8:
                        say(slot1, text("s205.sec6.u31"));
                        choice {
                            text("s205.sec6.m7.o0") => {
                                goto l10;
                            }
                            text("s205.sec6.m7.o1") => {
                                goto l11;
                            }
                            text("s205.sec6.m7.o2") or cancel => {
                                goto l9;
                            }
                        }
                    }
                    text("s205.sec6.m5.o2") => {}
                }
                l9:
                say(slot1, text("s205.sec6.u32"));
                return;
                l10:
                if (bits < 1000) {
                    say(slot1, text("s205.sec6.u35"));
                    return;
                }
                take_bits(1000);
                treasure_hunt.cheap_ordered = true;
                store_date(drimogemon_job_days);
                say(slot1, text("s205.sec6.u33"));
                store_random(treasure_hunt.cheap_roll, 49);
                return;
                l11:
                if (bits < 5000) {
                    say(slot1, text("s205.sec6.u35"));
                    return;
                }
                take_bits(5000);
                treasure_hunt.pricey_ordered = true;
                store_date(drimogemon_job_days);
                say(slot1, text("s205.sec6.u34"));
                store_random(treasure_hunt.pricey_roll, 49);
                return;
            }
            text("s205.sec6.m0.o2") => {
                jump_to_file(215, 6);
            }
            cancel => {
                return;
            }
        }
    """)

# the section table, in the order of the original header
sections(254, 6)
