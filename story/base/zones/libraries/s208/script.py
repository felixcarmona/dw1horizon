# The Python view of script 208 of DG.SCN (no screen loads it).
# Made from the disc by `dws story-base`; the source of the story since 2026-10-15: edit it (no file = no script). Keys only, never the
# game's words. `story-build` reads this file (lowered); the DWS beside it is the proven intermediate; mods import `dw.base`.
from dw import *

lib = script(208)

@lib.on_enter
def enter():    # section 254
    pass

@lib.on_use(2)
def use2():    # section 82
    dws(r"""
        entity_set_rotation(tamer, 3152);
        wait(5);
        l1:
        loop {
            if (mystery_circles_grown_seen && engine.prosperity >= 45) {
                vademon_encounter_ready = true;
                set_textbox_size(entity(0), 21, 8);
                show_textbox(text("s208.sec82.u0"));
                fadeout_hud(0);
                choice(narrator) {
                    text("s208.sec82.m0.o0") => {
                        goto l2;
                    }
                    text("s208.sec82.m0.o1") or cancel => {
                        return;
                    }
                }
            }
            l2:
            loop {
                if (is_recruited(species("SkullGreymon"))) {
                    set_textbox_size(entity(0), 21, 10);
                    show_textbox(text("s208.sec82.u1"));
                    fadeout_hud(0);
                    skullgreymon_debut_news_read = true;
                    choice(narrator) {
                        text("s208.sec82.m1.o0") => {
                            goto l4;
                        }
                        text("s208.sec82.m1.o1") => {
                            goto l3;
                        }
                        text("s208.sec82.m1.o2") or cancel => {
                            return;
                        }
                    }
                }
                goto l4;
                l3:
                unless (!mystery_circles_grown_seen || engine.prosperity < 45) goto l1;
                continue;
                l4:
                loop {
                    if (engine.prosperity >= 35 && myotismon_freed) {
                        set_textbox_size(entity(0), 21, 8);
                        show_textbox(text("s208.sec82.u2"));
                        fadeout_hud(0);
                        if (!is_recruited(species("SkullGreymon"))) {
                            unrecruit(species("Myotismon"));
                            myotismon_missing = true;
                        }
                        choice(narrator) {
                            text("s208.sec82.m2.o0") => {
                                goto l6;
                            }
                            text("s208.sec82.m2.o1") => {
                                goto l5;
                            }
                            text("s208.sec82.m2.o2") or cancel => {
                                return;
                            }
                        }
                    }
                    goto l6;
                    l5:
                    unless (!is_recruited(species("SkullGreymon"))) goto l2;
                    unless (!mystery_circles_grown_seen || engine.prosperity < 45) goto l1;
                    continue;
                    l6:
                    if (engine.prosperity >= 25) {
                        set_textbox_size(entity(0), 21, 9);
                        show_textbox(text("s208.sec82.u3"));
                        fadeout_hud(0);
                        choice(narrator) {
                            text("s208.sec82.m3.o0") => {
                                goto l8;
                            }
                            text("s208.sec82.m3.o1") => {
                                goto l7;
                            }
                            text("s208.sec82.m3.o2") or cancel => {
                                return;
                            }
                        }
                    }
                    goto l8;
                    l7:
                    unless (engine.prosperity >= 35 && myotismon_freed) break;
                }
                unless (is_recruited(species("SkullGreymon"))) break;
            }
            unless (!mystery_circles_grown_seen || engine.prosperity < 45) continue;
            goto l6;
            l8:
            loop {
                if (engine.prosperity >= 20) {
                    set_textbox_size(entity(0), 21, 10);
                    show_textbox(text("s208.sec82.u4"));
                    fadeout_hud(0);
                    choice(narrator) {
                        text("s208.sec82.m4.o0") => {
                            goto l10;
                        }
                        text("s208.sec82.m4.o1") => {
                            goto l9;
                        }
                        text("s208.sec82.m4.o2") or cancel => {
                            return;
                        }
                    }
                }
                goto l10;
                l9:
                unless (engine.prosperity < 25) goto l6;
                continue;
                l10:
                if (engine.prosperity >= 15) {
                    set_textbox_size(entity(0), 21, 10);
                    show_textbox(text("s208.sec82.u5"));
                    fadeout_hud(0);
                    choice(narrator) {
                        text("s208.sec82.m5.o0") => {
                            goto l12;
                        }
                        text("s208.sec82.m5.o1") => {
                            goto l11;
                        }
                        text("s208.sec82.m5.o2") or cancel => {
                            return;
                        }
                    }
                }
                goto l12;
                l11:
                unless (engine.prosperity >= 20) break;
            }
            unless (mystery_circles_grown_seen && engine.prosperity >= 45) break;
        }
        goto l10;
        l12:
        loop {
            if (mystery_circles_first_seen) {
                set_textbox_size(entity(0), 21, 9);
                show_textbox(text("s208.sec82.u6"));
                fadeout_hud(0);
                ufo_report_read = true;
                choice(narrator) {
                    text("s208.sec82.m6.o0") => {
                        goto l14;
                    }
                    text("s208.sec82.m6.o1") => {
                        goto l13;
                    }
                    text("s208.sec82.m6.o2") or cancel => {
                        return;
                    }
                }
            }
            goto l14;
            l13:
            unless (engine.prosperity < 15) break;
            continue;
            l14:
            set_textbox_size(entity(0), 21, 9);
            show_textbox(text("s208.sec82.u7"));
            fadeout_hud(0);
            unless (mystery_circles_first_seen || engine.prosperity >= 15) return;
            choice(narrator) {
                text("s208.sec82.m7.o0") => {
                    unless (mystery_circles_first_seen) break;
                }
                text("s208.sec82.m7.o1") => {
                    return;
                }
                cancel => {
                    return;
                }
            }
        }
        goto l10;
        return;
    """)

# the section table, in the order of the original header
sections(254, 82)
