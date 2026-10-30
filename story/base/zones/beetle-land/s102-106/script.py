# The Python view of script 102 of DG.SCN: screen 106 Beetle Land.
# Made from the disc by `dws story-base`; the source of the story since 2026-10-15: edit it (no file = no script). Keys only, never the
# game's words. `story-build` reads this file (lowered); the DWS beside it is the proven intermediate; mods import `dw.base`.
from dw import *
from dw.text import text
from dw.names import *

land = screen(Screen.beetle_land_106)
tentomon = land.npc(Species.Tentomon, slot=0)
slot5 = land.npc(None, slot=5)    # no NPC of the .MAP in this slot; the script spawns what stands here
slot6 = land.npc(None, slot=6)    # no NPC of the .MAP in this slot; the script spawns what stands here
t51 = text.s102.sec51
t81 = text.s102.sec81
t82 = text.s102.sec82

@land.on_enter
def enter():    # section 254
    pass

@land.on_use(1)
def use1():    # section 81
    raw.store_date(date_year)
    tamer.face(tentomon)
    tentomon.face(tamer)
    wait(250)
    if not tournament_registered:
        if date_day == 21 and date_hour >= 10:
            tentomon.say(t81.u0)
            return
        elif date_day >= 20 and date_day <= 21:
            if date_day == 21 and date_hour >= 23:
                tentomon.say(t81.u2)
            if partner.species in (Species.Kabuterimon, Species.Kunemon, Species.Kuwagamon, Species.HerculesKabuterimon):
                if not tournament_registered:
                    tentomon.say(t81.u4)
                    if tentomon.ask(yes=t81.m0.o0, no=t81.m0.o1):
                        tentomon.say(t81.u5)
                else:
                    tentomon.say(t81.u5)
                match tentomon.choose(a=t81.m1.o0, b=t81.m1.o1):
                    case "a":
                        call(Routine.register_cup22)
                        tentomon.say(t81.u11)
                        return
                    case _:
                        return
            else:
                tentomon.say(t81.u3)
                return
        else:
            tentomon.say(t81.u1)
            return
    elif date_day >= 20 and date_day <= 21:
        if date_day == 21 and date_hour >= 23:
            tentomon.say(t81.u7)
        tentomon.say(t81.u8)
        match choose(a=t81.m2.o0, b=t81.m2.o1):
            case "b":
                tournament_registered.clear()
                tentomon.say(t81.u9)
                return
            case _:
                return
    else:
        tentomon.say(t81.u6)
        return
    tentomon.say(t81.u10)

@land.on_step(0)
def step0():    # section 51
    if clock.day != 21:
        tentomon.face(tamer)
        tamer.face(tentomon)
        wait(250)
        tentomon.say(t51.u0)
        tamer.run(-126, 546)
        return
    if not tournament_registered:
        tentomon.face(tamer)
        tamer.face(tentomon)
        wait(250)
        tentomon.say(t51.u1)
        tamer.run(-126, 546)
        return
    if date_hour < 10:
        tentomon.face(tamer)
        tamer.face(tentomon)
        wait(250)
        tentomon.say(t51.u2)
        tamer.run(-126, 546)
        return
    if date_hour >= 23:
        tentomon.face(tamer)
        tamer.face(tentomon)
        wait(250)
        tentomon.say(t51.u3)
        tamer.run(-126, 546)
        return
    call(Routine.start_tournament, arg=5)
    raw.store_date(date_year)
    raw.add_minutes_to_date_at(date_year, 360)
    raw.advance_to_date_at(date_year)
    warp(Screen.beetle_land_106, entry=3, then=82)

@land.on_use(2)
def use2():    # section 82
    tournament_registered.clear()
    if engine.result == 3:
        if tournament.cup == 22:
            give(bits=5000)
            narrator.say(t82.u3)
            give(Item.Beetlepearl)
            if engine.item_did_not_fit:
                tentomon.say(t82.u4)
                pick_item()
                take_picked(all=True)
                give(Item.Beetlepearl)
            jump_to_script(204, 51)
    elif engine.result != 2:
        tentomon.say(t82.u0)
        narrator.say(t82.u1)
        give(Item.GiantMeat)
        if engine.item_did_not_fit:
            tentomon.say(t82.u2)
            pick_item()
            take_picked(all=True)
            give(Item.GiantMeat)
        return
    roll = random.roll(1)
    if tournament.cup == 22 and roll == 0:
        give(bits=2000)
        narrator.say(t82.u5)
        give(Item.HornHelmet)
        insect_contest_horn_helmet_won.set()
        if engine.item_did_not_fit:
            tentomon.say(t82.u6)
            pick_item()
            take_picked(all=True)
            give(Item.HornHelmet)
        return
    if tournament.cup != 22 or roll != 1:
        return
    give(bits=2000)
    narrator.say(t82.u7)
    give(Item.ScissorJaw)
    if engine.item_did_not_fit:
        tentomon.say(t82.u8)
        pick_item()
        take_picked(all=True)
        give(Item.ScissorJaw)

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
        goto L77;
        goto L91;
        goto L93;
        goto L113;
        l2:
        show_textbox(text("s102.sec10.u0"));
        l3:
        goto l4;
        goto L78;
        goto L92;
        goto L94;
        goto L114;
        l4:
        show_textbox(text("s102.sec10.u1"));
        l5:
        goto l6;
        goto L79;
        goto L90;
        goto L95;
        goto L115;
        l6:
        show_textbox(text("s102.sec10.u2"));
        l7:
        goto l8;
        goto L80;
        goto L90;
        goto L95;
        goto L116;
        l8:
        show_textbox(text("s102.sec10.u3"));
        l9:
        goto l10;
        goto L81;
        goto L90;
        goto L94;
        goto L117;
        l10:
        show_textbox(text("s102.sec10.u4"));
        l11:
        goto l12;
        goto L78;
        goto L90;
        goto L94;
        goto L118;
        l12:
        show_textbox(text("s102.sec10.u5"));
        l13:
        goto l14;
        goto L78;
        goto L90;
        goto L96;
        goto L119;
        l14:
        show_textbox(text("s102.sec10.u6"));
        l15:
        goto l16;
        goto L78;
        goto L90;
        goto L97;
        goto L120;
        l16:
        show_textbox(text("s102.sec10.u7"));
        l17:
        goto l18;
        goto L78;
        goto L90;
        goto L98;
        goto L121;
        l18:
        show_textbox(text("s102.sec10.u8"));
        l19:
        goto l20;
        goto L78;
        goto L90;
        goto L99;
        goto L122;
        l20:
        show_textbox(text("s102.sec10.u9"));
        l21:
        goto l22;
        goto L78;
        goto L90;
        goto L100;
        goto L123;
        l22:
        show_textbox(text("s102.sec10.u10"));
        l23:
        goto l24;
        goto L82;
        goto L90;
        goto L101;
        goto L124;
        l24:
        show_textbox(text("s102.sec10.u11"));
        l25:
        goto l26;
        goto L83;
        goto L90;
        goto L102;
        goto L125;
        l26:
        show_textbox(text("s102.sec10.u12"));
        l27:
        goto l28;
        goto L84;
        goto L90;
        goto L103;
        goto L126;
        l28:
        show_textbox(text("s102.sec10.u13"));
        l29:
        goto l30;
        goto L85;
        goto L90;
        goto L104;
        goto L127;
        l30:
        show_textbox(text("s102.sec10.u14"));
        l31:
        goto l32;
        goto L86;
        goto L90;
        goto L105;
        goto L128;
        l32:
        show_textbox(text("s102.sec10.u15"));
        l33:
        goto l34;
        goto L87;
        goto L90;
        goto L106;
        goto L129;
        l34:
        show_textbox(text("s102.sec10.u16"));
        l35:
        goto l36;
        goto L88;
        goto L90;
        goto L107;
        goto L130;
        l36:
        show_textbox(text("s102.sec10.u17"));
        l37:
        goto l38;
        goto L89;
        goto L90;
        goto L108;
        goto L131;
        l38:
        show_textbox(text("s102.sec10.u18"));
        l39:
        goto l40;
        goto L86;
        goto L90;
        goto L109;
        goto L132;
        l40:
        show_textbox(text("s102.sec10.u19"));
        l41:
        goto l42;
        goto L85;
        goto L90;
        goto L110;
        goto L133;
        l42:
        show_textbox(text("s102.sec10.u20"));
        l43:
        goto l44;
        goto L85;
        goto L90;
        goto L111;
        goto L134;
        l44:
        show_textbox(text("s102.sec10.u21"));
        l45:
        goto l44;
        goto L77;
        goto L90;
        goto L112;
        goto L135;
    """)

@slot6.on_talk
def talk():    # section 11
    dws(r"""
        data(12, 13, 14, 26, 27, 28, 40, 41, 42, 54, 55, 56, 59, 60, 61);
        shared L77:
        data(0, 0, 0);
        shared L78:
        data(8, 0, 0);
        shared L79:
        data(24, 0, 0);
        shared L80:
        data(8, 4, 2);
        shared L81:
        data(8, 0, 1);
        shared L82:
        data(8, 4, 56);
        shared L83:
        data(8, 4, 48);
        shared L84:
        data(8, 4, 59);
        shared L85:
        data(8, 4, 61);
        shared L86:
        data(8, 4, 60);
        shared L87:
        data(6, 3, 60);
        shared L88:
        data(3, 2, 53);
        shared L89:
        data(8, 4, 61);
        shared L90:
        data(254);
        shared L91:
        data(12, 13, 14, 26, 27, 28, 40, 41, 42, 54, 55, 56, 59, 60, 61, 63, 64, 65, 66);
        shared L92:
        data(12, 13, 14, 26, 27, 28, 40, 41, 42, 54, 55, 56, 59, 60, 61);
        shared L93:
        data(3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40, 41, 42, 45, 46, 47, 48, 49, 50, 51, 52, 53, 54, 55, 56, 57, 58, 59, 60, 61, 63, 64, 65, 66);
        shared L94:
        data(3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40, 41, 42, 45, 46, 47, 48, 49, 50, 51, 52, 53, 54, 55, 56, 57, 58, 59, 60, 61, 63, 64, 65, 254);
        shared L95:
        data(3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40, 41, 42, 45, 46, 47, 48, 49, 50, 51, 52, 53, 54, 55, 56, 57, 58, 59, 60, 61);
        shared L96:
        data(3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 254);
        shared L97:
        data(17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 254);
        shared L98:
        data(31, 32, 33, 34, 35, 36, 37, 38, 39, 40, 41, 42, 254);
        shared L99:
        data(45, 46, 47, 48, 49, 50, 51, 52, 53, 54, 55, 56, 254);
        shared L100:
        data(57, 58, 59, 60, 61, 63, 64, 65, 254);
        shared L101:
        data(3, 5, 9, 21, 36, 47, 56);
        shared L102:
        data(6, 8, 13, 14, 17, 26, 27, 31, 34, 38, 42, 48, 63, 65, 254);
        shared L103:
        data(7, 18, 20, 33, 37, 45, 50, 59, 254);
        shared L104:
        data(4, 10, 22, 23, 24, 35, 49, 52, 57, 61, 254);
        shared L105:
        data(19, 25, 32, 46, 51, 55, 58, 60, 254);
        shared L106:
        data(12, 28, 40, 41, 54, 65, 254);
        shared L107:
        data(11, 39, 53);
        shared L108:
        data(3, 4, 8, 5, 7, 10, 12, 35, 47, 54, 61, 65, 254);
        shared L109:
        data(6, 7, 12, 19, 20, 21, 31, 33, 45, 50, 51, 54, 55, 59, 60);
        shared L110:
        data(14, 22, 24, 33, 36, 38, 42, 48, 57, 63, 254);
        shared L111:
        data(6, 9, 20, 34, 36, 40, 42, 48, 58, 65, 254);
        shared L112:
        data(19, 32, 51, 60, 254);
        shared L113:
        data(3, 4, 17, 18, 31, 32, 45, 46, 57, 74, 80, 82, 83, 86, 96, 103, 109, 111, 254);
        shared L114:
        data(5, 6, 7, 8, 9, 10, 11, 19, 20, 21, 22, 23, 24, 25, 33, 34, 35, 36, 37, 38, 39, 47, 48, 49, 50, 51, 52, 53, 58, 67, 68, 69, 71, 73, 74, 75, 76, 77, 78, 79, 80, 81, 82, 83, 84, 86, 87, 91, 92, 93, 94, 95, 96, 97, 98, 99, 101, 102, 103, 105, 106, 107, 109, 111);
        shared L115:
        data(5, 6, 7, 8, 9, 10, 11, 19, 20, 21, 22, 23, 24, 25, 33, 34, 35, 36, 37, 38, 39, 47, 48, 49, 50, 51, 52, 53, 58, 66, 67, 68, 69, 70, 71, 72, 73, 74, 75, 76, 77, 78, 79, 80, 81, 82, 83, 84, 85, 86, 87, 88, 89, 90, 91, 92, 93, 94, 95, 96, 97, 98, 99, 100, 101, 102, 103, 104, 105, 106, 107, 108, 109, 110, 111);
        shared L116:
        data(5, 6, 7, 12, 13, 14, 19, 20, 21, 26, 27, 28, 32, 33, 34, 40, 41, 42, 47, 48, 49, 54, 55, 56, 58, 59, 60, 61, 63, 64, 65, 66, 70, 72, 85, 88, 89, 90, 100, 104, 108, 110, 254);
        shared L117:
        data(12, 13, 14, 26, 27, 28, 40, 41, 42, 54, 55, 56, 59, 60, 61, 66, 254);
        shared L118:
        data(254);
        shared L119:
        data(3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 254);
        shared L120:
        data(17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 254);
        shared L121:
        data(31, 32, 33, 34, 35, 36, 37, 38, 39, 40, 41, 42, 254);
        shared L122:
        data(45, 46, 47, 48, 49, 50, 51, 52, 53, 54, 55, 56, 254);
        shared L123:
        data(57, 58, 59, 60, 61, 63, 64, 65, 66, 67, 68, 69, 70, 71, 72, 73, 74, 75, 76, 77, 78, 79, 80, 81, 82, 83, 84, 85, 86, 87, 88, 89, 90, 91, 92, 93, 94, 95, 96, 97, 98, 99, 100, 101, 102, 103, 104, 105, 106, 107, 108, 109, 110, 111, 254);
        shared L124:
        data(3, 5, 9, 21, 36, 47, 56, 69, 88, 101, 104, 105, 254);
        shared L125:
        data(6, 8, 13, 14, 17, 26, 27, 31, 34, 38, 42, 48, 68, 70, 72, 78, 79, 80, 81, 82, 83, 97, 106, 107, 108, 90, 254);
        shared L126:
        data(7, 18, 20, 33, 37, 45, 50, 66, 67, 75, 85, 95, 102);
        shared L127:
        data(4, 10, 22, 23, 24, 35, 49, 52, 57, 61, 71, 89, 94, 98, 100, 103, 109, 110, 254);
        shared L128:
        data(19, 25, 32, 46, 51, 55, 58, 60, 74, 77, 86, 91, 93, 99, 254);
        shared L129:
        data(12, 28, 40, 41, 54, 76, 84, 92);
        shared L130:
        data(11, 39, 53, 73, 87);
        shared L131:
        data(3, 4, 8, 5, 7, 10, 12, 35, 47, 54, 61, 69, 71, 83, 84, 88, 91, 98, 101, 106, 254);
        shared L132:
        data(6, 7, 12, 19, 20, 21, 31, 33, 45, 50, 51, 54, 55, 59, 60, 67, 85, 95, 96, 100, 102, 106, 254);
        shared L133:
        data(14, 22, 24, 33, 36, 38, 42, 48, 57, 69, 70, 75, 79, 93, 101, 105, 254);
        shared L134:
        data(6, 9, 20, 34, 36, 40, 42, 48, 52, 58, 66, 72, 80, 85, 89, 97, 100, 110, 104);
        shared L135:
        data(67, 74, 102, 111, 19, 32, 51, 60, 254);
        end_section();
        end_script();
    """)

def sec81_dup3():    # shared code (the disc's label sec81_dup3)
    return use1()

# the section table, in the order of the original header
sections(254, 81, 51, (81, sec81_dup3), 82, 10, 11)
