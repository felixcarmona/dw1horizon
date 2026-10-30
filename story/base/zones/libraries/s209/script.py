# The Python view of script 209 of DG.SCN (no screen loads it).
# Made from the disc by `dws story-base`; the source of the story since 2026-10-15: edit it (no file = no script). Keys only, never the
# game's words. `story-build` reads this file (lowered); the DWS beside it is the proven intermediate; mods import `dw.base`.
from dw import *

lib = script(209)
slot0 = lib.npc(None, slot=0)    # no NPC of the .MAP in this slot; the script spawns what stands here
slot2 = lib.npc(None, slot=2)    # no NPC of the .MAP in this slot; the script spawns what stands here
slot5 = lib.npc(None, slot=5)    # no NPC of the .MAP in this slot; the script spawns what stands here
slot6 = lib.npc(None, slot=6)    # no NPC of the .MAP in this slot; the script spawns what stands here

@slot0.on_talk
def talk():    # section 5
    dws(r"""
        choice(narrator) {
            text("s209.sec5.m0.o0") => {
                choice {
                    text("s209.sec5.m2.o0") => {
                        shop_stock.med_recovery = true;
                        shop_stock.sup_restore = true;
                        shop_stock.s_def_disk = true;
                        shop_stock.auto_pilot = true;
                        shop_stock.off_chip = true;
                        shop_stock.port_potty = true;
                        shop_stock.gold_acorn = true;
                        shop_stock.grey_claws = true;
                        shop_stock.fireball = true;
                        shop_stock.iron_hoof = true;
                        shop_stock.black_wing = true;
                        shop_stock.white_wing = true;
                        shop_stock.unihorn = true;
                        shop_stock.fertilizer = true;
                        shop_stock.ice_crystal = true;
                        shop_stock.sunglasses = true;
                        shop_stock.fatal_bone = true;
                        shop_stock.cyber_part = true;
                        shop_stock.chainsaw = true;
                        shop_stock.x_bandage = true;
                        shop_stock.gold_banana = true;
                        shop_stock.hispeed_dsk = true;
                        shop_stock.giant_meat = true;
                        shop_stock.digimushrm = true;
                        shop_stock.supercarrot = true;
                        shop_stock.black_trout = true;
                        shop_stock.digianchovy = true;
                        shop_stock.happymushrm = true;
                        shop_stock.torn_tatter = true;
                        shop_stock.flamingwing = true;
                        shop_stock.big_berry = true;
                        shop_stock.steel_drill = true;
                        shop_stock.north_star = true;
                        shop_stock.small_spear = true;
                        shop_stock.moldy_meat = true;
                        shop_stock.spike_club = true;
                        shop_stock.waterbottle = true;
                        shop_stock.hair_grower = true;
                        shop_stock.ray_gun = true;
                        shop_stock.coral_charm = true;
                        shop_stock.mono_stone = true;
                        shop_stock.flamingmane = true;
                        shop_stock.rooster = true;
                        shop_stock.mysty_egg = true;
                        shop_stock.red_ruby = true;
                        shop_stock.red_shell = true;
                        shop_stock.horn_helmet = true;
                        shop_stock.scissor_jaw = true;
                        shop_stock.beetlepearl = true;
                        shop_stock.rainbowhorn = true;
                        shop_stock.koga_laws = true;
                        shop_stock.hard_scale = true;
                        shop_stock.bluecrystal = true;
                        shop_stock.silver_ball = true;
                        shop_stock.metal_armor = true;
                        shop_stock.blue_flute = true;
                        shop_stock.digiseabass = true;
                        shop_stock.chain_melon = true;
                        shop_stock.steak = true;
                        shop_stock.meat = true;
                        shop_stock.sirloin = true;
                        shop_stock.trn_manual = true;
                        engine.picker_mode = false;
                        engine.arg = 7;
                        call_routine(routine("shop"));
                    }
                    text("s209.sec5.m2.o1") => {
                        engine.picker_mode = true;
                        engine.arg = 7;
                        call_routine(routine("shop"));
                    }
                    text("s209.sec5.m2.o2") => {
                        engine.arg = 7;
                        call_routine(routine("merit_shop"));
                    }
                }
            }
            text("s209.sec5.m0.o1") => {
                choice {
                    text("s209.sec5.m3.o0") => {
                        engine.arg = 7;
                        say(slot2, text("s209.sec5.u0"));
                        call_routine(routine("show_bits_box"));
                        loop {
                            choice {
                                text("s209.sec5.m4.o0") => {
                                    if (bits >= 500) {
                                        choice(keep) {
                                            text("s209.sec5.m5.o0") => {
                                                say(slot2, text("s209.sec5.u1"));
                                                engine.picker_mode = false;
                                                card_shop_buy_mode = false;
                                                call_routine(routine("card_shop"));   // asks how many packs and takes their bits (patch 0223)
                                                call_routine(routine("check_tournament_medal"));
                                            }
                                            text("s209.sec5.m5.o1") => {
                                                engine.picker_mode = false;
                                                card_shop_buy_mode = true;
                                                call_routine(routine("card_shop"));
                                                call_routine(routine("check_tournament_medal"));
                                            }
                                            text("s209.sec5.m5.o2") or cancel => {}
                                        }
                                    } else {
                                        choice(keep) {
                                            text("s209.sec5.m6.o0") => {
                                                engine.picker_mode = false;
                                                card_shop_buy_mode = true;
                                                call_routine(routine("card_shop"));
                                                call_routine(routine("check_tournament_medal"));
                                            }
                                            text("s209.sec5.m6.o1") or cancel => {}
                                        }
                                    }
                                }
                                text("s209.sec5.m4.o1") => {
                                    engine.picker_mode = true;
                                    call_routine(routine("card_shop"));
                                }
                                text("s209.sec5.m4.o2") or cancel => {
                                    break;
                                }
                            }
                            say(slot2, text("s209.sec5.u3"));
                        }
                        call_routine(routine("close_box2"));
                        say(slot2, text("s209.sec5.u4"));
                    }
                    text("s209.sec5.m3.o1") => {
                        engine.arg = 7;
                        call_routine(routine("item_keeper"));
                    }
                    text("s209.sec5.m3.o2") => {
                        choice {
                            text("s209.sec5.m8.o0") => {
                                engine.arg = 7;
                                call_routine(routine("jukebox"));
                            }
                            text("s209.sec5.m8.o1") => {
                                engine.arg = 7;
                                call_routine(routine("birdramon_taxi"));
                            }
                            text("s209.sec5.m8.o2") => {
                                engine.arg = 7;
                                engine.menu_result = 2;
                                call_routine(routine("mojyamon_trade"));
                            }
                        }
                    }
                }
            }
            text("s209.sec5.m0.o2") => {
                choice(narrator) {
                    text("s209.sec5.m9.o0") => {
                        if (!tournament_registered) {
                            engine.arg = 7;
                            call_routine(routine("tournament_calendar"));
                        } else {
                            say(slot2, text("s209.sec5.u12"));
                        }
                    }
                    text("s209.sec5.m9.o1") => {
                        if (!tournament_registered) {
                            say(slot2, text("s209.sec5.u13"));
                            return;
                        }
                        engine.arg = 7;
                        call_routine(routine("start_tournament"));
                        warp_to(180, 0, 255);
                        call_routine(routine("check_tournament_medal"));
                    }
                    text("s209.sec5.m9.o2") => {
                        choice(narrator) {
                            text("s209.sec5.m10.o0") => {
                                call_digimon_routine(routine("opening"));
                                await narrator;
                            }
                            text("s209.sec5.m10.o1") => {
                                call_digimon_routine(routine("ending"));
                                await narrator;
                            }
                            text("s209.sec5.m10.o2") => {
                                store_digimon_type(damage_percent);
                                if (damage_percent == 39) {
                                    say(tamer, text("s209.sec5.u9"));
                                    copy_pstat(sukamon_backup_digimon, engine.arg);
                                } else {
                                    say(tamer, text("s209.sec5.u10"));
                                    store_digimon_type(sukamon_backup_digimon);
                                    engine.arg = 39;
                                }
                                fadeout_hud(0);
                                call_digimon_routine(routine("revert_sukamon"));
                                await entity(201);
                                say(tamer, text("s209.sec5.u11"));
                            }
                            text("s209.sec5.m10.o3") => {
                                call_routine(routine("lost_all_lives"));
                            }
                        }
                    }
                    text("s209.sec5.m9.o3") => {
                        loop {
                            call_routine(routine("shopvar_clear"));
                            loop {
                                say(tamer, text("s209.sec5.u14"));
                                choice {
                                    text("s209.sec5.m11.o0") => {
                                        break;
                                    }
                                    text("s209.sec5.m11.o1") => {
                                        engine.shop_hi = 19;
                                        engine.shop_lo = 136;
                                        call_routine(routine("shopvar_add"));
                                    }
                                    text("s209.sec5.m11.o2") or cancel => {
                                        return;
                                    }
                                }
                            }
                        }
                        end_selection();
                    }
                }
            }
            text("s209.sec5.m0.o3") => {
                choice(narrator) {
                    text("s209.sec5.m1.o0") => {
                        engine.arg = 2;
                        call_routine(routine("naming_and_intro"));
                    }
                    text("s209.sec5.m1.o1") => {
                        engine.arg = 3;
                        call_routine(routine("naming_and_intro"));
                    }
                }
            }
        }
    """)

@slot5.on_talk
def talk():    # section 10
    dws(r"""
        goto l1;
        goto l3;
        goto l5;
        goto l7;
        goto l9;
        goto l11;
        goto l13;
        goto l15;
        goto l17;
        goto l19;
        goto l21;
        goto l23;
        goto l25;
        goto l27;
        goto l29;
        goto l31;
        goto l33;
        goto l35;
        goto l37;
        goto l39;
        goto l41;
        goto l43;
        goto l45;
        l1:
        goto l2;
        goto L92;
        goto L106;
        goto L108;
        goto L128;
        l2:
        show_textbox(text("s209.sec10.u0"));
        l3:
        goto l4;
        goto L93;
        goto L107;
        goto L109;
        goto L129;
        l4:
        show_textbox(text("s209.sec10.u1"));
        l5:
        goto l6;
        goto L94;
        goto L105;
        goto L110;
        goto L130;
        l6:
        show_textbox(text("s209.sec10.u2"));
        l7:
        goto l8;
        goto L95;
        goto L105;
        goto L110;
        goto L131;
        l8:
        show_textbox(text("s209.sec10.u3"));
        l9:
        goto l10;
        goto L96;
        goto L105;
        goto L109;
        goto L132;
        l10:
        show_textbox(text("s209.sec10.u4"));
        l11:
        goto l12;
        goto L93;
        goto L105;
        goto L109;
        goto L133;
        l12:
        show_textbox(text("s209.sec10.u5"));
        l13:
        goto l14;
        goto L93;
        goto L105;
        goto L111;
        goto L134;
        l14:
        show_textbox(text("s209.sec10.u6"));
        l15:
        goto l16;
        goto L93;
        goto L105;
        goto L112;
        goto L135;
        l16:
        show_textbox(text("s209.sec10.u7"));
        l17:
        goto l18;
        goto L93;
        goto L105;
        goto L113;
        goto L136;
        l18:
        show_textbox(text("s209.sec10.u8"));
        l19:
        goto l20;
        goto L93;
        goto L105;
        goto L114;
        goto L137;
        l20:
        show_textbox(text("s209.sec10.u9"));
        l21:
        goto l22;
        goto L93;
        goto L105;
        goto L115;
        goto L138;
        l22:
        show_textbox(text("s209.sec10.u10"));
        l23:
        goto l24;
        goto L97;
        goto L105;
        goto L116;
        goto L139;
        l24:
        show_textbox(text("s209.sec10.u11"));
        l25:
        goto l26;
        goto L98;
        goto L105;
        goto L117;
        goto L140;
        l26:
        show_textbox(text("s209.sec10.u12"));
        l27:
        goto l28;
        goto L99;
        goto L105;
        goto L118;
        goto L141;
        l28:
        show_textbox(text("s209.sec10.u13"));
        l29:
        goto l30;
        goto L100;
        goto L105;
        goto L119;
        goto L142;
        l30:
        show_textbox(text("s209.sec10.u14"));
        l31:
        goto l32;
        goto L101;
        goto L105;
        goto L120;
        goto L143;
        l32:
        show_textbox(text("s209.sec10.u15"));
        l33:
        goto l34;
        goto L102;
        goto L105;
        goto L121;
        goto L144;
        l34:
        show_textbox(text("s209.sec10.u16"));
        l35:
        goto l36;
        goto L103;
        goto L105;
        goto L122;
        goto L145;
        l36:
        show_textbox(text("s209.sec10.u17"));
        l37:
        goto l38;
        goto L104;
        goto L105;
        goto L123;
        goto L146;
        l38:
        show_textbox(text("s209.sec10.u18"));
        l39:
        goto l40;
        goto L101;
        goto L105;
        goto L124;
        goto L147;
        l40:
        show_textbox(text("s209.sec10.u19"));
        l41:
        goto l42;
        goto L100;
        goto L105;
        goto L125;
        goto L148;
        l42:
        show_textbox(text("s209.sec10.u20"));
        l43:
        goto l44;
        goto L100;
        goto L105;
        goto L126;
        goto L149;
        l44:
        show_textbox(text("s209.sec10.u21"));
        l45:
        goto l44;
        goto L92;
        goto L105;
        goto L127;
        goto L150;
    """)

@slot6.on_talk
def talk():    # section 11
    dws(r"""
        data(12, 13, 14, 26, 27, 28, 40, 41, 42, 54, 55, 56, 59, 60, 61);
        shared L92:
        data(0, 0, 0);
        shared L93:
        data(8, 0, 0);
        shared L94:
        data(24, 0, 0);
        shared L95:
        data(8, 4, 2);
        shared L96:
        data(8, 0, 1);
        shared L97:
        data(8, 4, 56);
        shared L98:
        data(8, 4, 48);
        shared L99:
        data(8, 4, 59);
        shared L100:
        data(8, 4, 61);
        shared L101:
        data(8, 4, 60);
        shared L102:
        data(6, 3, 60);
        shared L103:
        data(3, 2, 53);
        shared L104:
        data(8, 4, 61);
        shared L105:
        data(254);
        shared L106:
        data(12, 13, 14, 26, 27, 28, 40, 41, 42, 54, 55, 56, 59, 60, 61, 63, 64, 65, 66);
        shared L107:
        data(12, 13, 14, 26, 27, 28, 40, 41, 42, 54, 55, 56, 59, 60, 61);
        shared L108:
        data(3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40, 41, 42, 45, 46, 47, 48, 49, 50, 51, 52, 53, 54, 55, 56, 57, 58, 59, 60, 61, 63, 64, 65, 66);
        shared L109:
        data(3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40, 41, 42, 45, 46, 47, 48, 49, 50, 51, 52, 53, 54, 55, 56, 57, 58, 59, 60, 61, 63, 64, 65, 254);
        shared L110:
        data(3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40, 41, 42, 45, 46, 47, 48, 49, 50, 51, 52, 53, 54, 55, 56, 57, 58, 59, 60, 61);
        shared L111:
        data(3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 254);
        shared L112:
        data(17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 254);
        shared L113:
        data(31, 32, 33, 34, 35, 36, 37, 38, 39, 40, 41, 42, 254);
        shared L114:
        data(45, 46, 47, 48, 49, 50, 51, 52, 53, 54, 55, 56, 254);
        shared L115:
        data(57, 58, 59, 60, 61, 63, 64, 65, 254);
        shared L116:
        data(3, 5, 9, 21, 36, 47, 56);
        shared L117:
        data(6, 8, 13, 14, 17, 26, 27, 31, 34, 38, 42, 48, 63, 65, 254);
        shared L118:
        data(7, 18, 20, 33, 37, 45, 50, 59, 254);
        shared L119:
        data(4, 10, 22, 23, 24, 35, 49, 52, 57, 61, 254);
        shared L120:
        data(19, 25, 32, 46, 51, 55, 58, 60, 254);
        shared L121:
        data(12, 28, 40, 41, 54, 65, 254);
        shared L122:
        data(11, 39, 53);
        shared L123:
        data(3, 4, 8, 5, 7, 10, 12, 35, 47, 54, 61, 65, 254);
        shared L124:
        data(6, 7, 12, 19, 20, 21, 31, 33, 45, 50, 51, 54, 55, 59, 60);
        shared L125:
        data(14, 22, 24, 33, 36, 38, 42, 48, 57, 63, 254);
        shared L126:
        data(6, 9, 20, 34, 36, 40, 42, 48, 58, 65, 254);
        shared L127:
        data(19, 32, 51, 60, 254);
        shared L128:
        data(3, 4, 17, 18, 31, 32, 45, 46, 57, 74, 80, 82, 83, 86, 96, 103, 109, 111, 254);
        shared L129:
        data(5, 6, 7, 8, 9, 10, 11, 19, 20, 21, 22, 23, 24, 25, 33, 34, 35, 36, 37, 38, 39, 47, 48, 49, 50, 51, 52, 53, 58, 67, 68, 69, 71, 73, 74, 75, 76, 77, 78, 79, 80, 81, 82, 83, 84, 86, 87, 91, 92, 93, 94, 95, 96, 97, 98, 99, 101, 102, 103, 105, 106, 107, 109, 111);
        shared L130:
        data(5, 6, 7, 8, 9, 10, 11, 19, 20, 21, 22, 23, 24, 25, 33, 34, 35, 36, 37, 38, 39, 47, 48, 49, 50, 51, 52, 53, 58, 66, 67, 68, 69, 70, 71, 72, 73, 74, 75, 76, 77, 78, 79, 80, 81, 82, 83, 84, 85, 86, 87, 88, 89, 90, 91, 92, 93, 94, 95, 96, 97, 98, 99, 100, 101, 102, 103, 104, 105, 106, 107, 108, 109, 110, 111);
        shared L131:
        data(5, 6, 7, 12, 13, 14, 19, 20, 21, 26, 27, 28, 32, 33, 34, 40, 41, 42, 47, 48, 49, 54, 55, 56, 58, 59, 60, 61, 63, 64, 65, 66, 70, 72, 85, 88, 89, 90, 100, 104, 108, 110, 254);
        shared L132:
        data(12, 13, 14, 26, 27, 28, 40, 41, 42, 54, 55, 56, 59, 60, 61, 66, 254);
        shared L133:
        data(254);
        shared L134:
        data(3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 254);
        shared L135:
        data(17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 254);
        shared L136:
        data(31, 32, 33, 34, 35, 36, 37, 38, 39, 40, 41, 42, 254);
        shared L137:
        data(45, 46, 47, 48, 49, 50, 51, 52, 53, 54, 55, 56, 254);
        shared L138:
        data(57, 58, 59, 60, 61, 63, 64, 65, 66, 67, 68, 69, 70, 71, 72, 73, 74, 75, 76, 77, 78, 79, 80, 81, 82, 83, 84, 85, 86, 87, 88, 89, 90, 91, 92, 93, 94, 95, 96, 97, 98, 99, 100, 101, 102, 103, 104, 105, 106, 107, 108, 109, 110, 111, 254);
        shared L139:
        data(3, 5, 9, 21, 36, 47, 56, 69, 88, 101, 104, 105, 254);
        shared L140:
        data(6, 8, 13, 14, 17, 26, 27, 31, 34, 38, 42, 48, 68, 70, 72, 78, 79, 80, 81, 82, 83, 97, 106, 107, 108, 90, 254);
        shared L141:
        data(7, 18, 20, 33, 37, 45, 50, 66, 67, 75, 85, 95, 102);
        shared L142:
        data(4, 10, 22, 23, 24, 35, 49, 52, 57, 61, 71, 89, 94, 98, 100, 103, 109, 110, 254);
        shared L143:
        data(19, 25, 32, 46, 51, 55, 58, 60, 74, 77, 86, 91, 93, 99, 254);
        shared L144:
        data(12, 28, 40, 41, 54, 76, 84, 92);
        shared L145:
        data(11, 39, 53, 73, 87);
        shared L146:
        data(3, 4, 8, 5, 7, 10, 12, 35, 47, 54, 61, 69, 71, 83, 84, 88, 91, 98, 101, 106, 254);
        shared L147:
        data(6, 7, 12, 19, 20, 21, 31, 33, 45, 50, 51, 54, 55, 59, 60, 67, 85, 95, 96, 100, 102, 106, 254);
        shared L148:
        data(14, 22, 24, 33, 36, 38, 42, 48, 57, 69, 70, 75, 79, 93, 101, 105, 254);
        shared L149:
        data(6, 9, 20, 34, 36, 40, 42, 48, 52, 58, 66, 72, 80, 85, 89, 97, 100, 110, 104);
        shared L150:
        data(67, 74, 102, 111, 19, 32, 51, 60, 254);
        end_section();
        end_script();
    """)

# the section table, in the order of the original header
sections(5, 10, 11)
