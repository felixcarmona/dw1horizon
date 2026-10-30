# The Python view of script 168 of DG.SCN: screen 208 Arena Lobby, screen 223 Arena Lobby.
# Made from the disc by `dws story-base`; the source of the story since 2026-10-15: edit it (no file = no script). Keys only, never the
# game's words. `story-build` reads this file (lowered); the DWS beside it is the proven intermediate; mods import `dw.base`.
from dw import *
from dw.text import text
from dw.names import *

lobby_208 = screen(Screen.arena_lobby_208)
lobby_223 = screen(Screen.arena_lobby_223)
greymon = lobby_208.npc(Species.Greymon178, slot=0)
airdramon = lobby_223.npc(Species.Airdramon131, slot=1)
metalgreymonvirus = lobby_223.npc(Species.MetalGreymonVirus179, slot=2)
slot5 = lobby_208.npc(None, slot=5)    # no NPC of the .MAP in this slot; the script spawns what stands here
slot6 = lobby_208.npc(None, slot=6)    # no NPC of the .MAP in this slot; the script spawns what stands here
t53 = text.s168.sec53
t82 = text.s168.sec82
t84 = text.s168.sec84

@lobby_208.on_enter
def enter():    # section 254
    curling_opponent.set(255)
    if not recruited(Species.Penguinmon):
        objects[0].hide()
        objects[1].hide()
        objects[2].hide()
        objects[3].hide()
    else:
        objects[0].show()
        objects[1].show()
        objects[2].show()
        objects[3].show()
        objects[5].hide()
        objects[6].hide()
    if recruited(Species.Penguinmon) and not engine.game_beaten:
        objects[4].hide()
    if recruited(Species.Penguinmon) and engine.game_beaten:
        objects[4].show()
    if engine.game_beaten:
        objects[7].hide()
        objects[8].hide()

@lobby_208.on_use(1)
def use1():    # section 81
    jump_to_script(213, 81)

@lobby_208.on_step(3)
def step3():    # section 54
    jump_to_script(213, 54)

@lobby_208.on_step(10)
def step10():    # section 61
    jump_to_script(214, 51)

@lobby_208.on_step(0)
def step0():    # section 51
    if recruited(Species.Penguinmon):
        warp(Screen.digimon_curling, entry=0)
        curling_opponent.set(255)

@lobby_208.on_use(2)
def use2():    # section 82
    narrator.say(t82.u0)
    match narrator.choose(a=t82.m0.o0, b=t82.m0.o1, c=t82.m0.o2):
        case "a":
            narrator.say(t82.u1)
            hide_hud()
            return
        case "b":
            narrator.say(t82.u2)
            return
        case "c":
            narrator.say(t82.u3)
            return
        case _:
            return

@lobby_208.on_use(3)
def use3():    # section 83
    jump_to_script(215, 6)

@lobby_208.on_use(4)
def use4():    # section 84
    metalgreymonvirus.face(tamer)
    tamer.face(metalgreymonvirus)
    wait(500)
    metalgreymonvirus.say(t84.u0)
    roll = random.roll(9)
    if roll == 0:
        metalgreymonvirus.say(t84.u1)
        return
    if roll == 1:
        metalgreymonvirus.say(t84.u2)
        return
    if roll == 2:
        metalgreymonvirus.say(t84.u3)
        return
    if roll == 3:
        metalgreymonvirus.say(t84.u4)
        return
    if roll == 4:
        metalgreymonvirus.say(t84.u5)
        return
    if roll == 5:
        metalgreymonvirus.say(t84.u6)
        return
    if roll == 6:
        metalgreymonvirus.say(t84.u7)
        return
    if roll == 7:
        metalgreymonvirus.say(t84.u8)
        return
    if roll == 8:
        metalgreymonvirus.say(t84.u9)
        return
    if roll != 9:
        return airdramon.talk()
    metalgreymonvirus.say(t84.u10)

@airdramon.on_talk
def talk():    # section 6
    jump_to_script(215, 6)

@lobby_208.on_step(2)
def step2():    # section 53
    greymon.face(tamer)
    tamer.face(greymon)
    wait(250)
    greymon.say(t53.u0)
    tamer.run(450, 124)
    camera.on(tamer, speed=10)
    camera.arrived()

@lobby_208.on_step(1)
def step1():    # section 52
    tamer.walk(250, -5000, wait=False)
    piximon_in_item_shop.clear()
    if recruited(Species.Patamon) or recruited(Species.Biyomon) or recruited(Species.Unimon) or recruited(Species.Monochromon):
        if recruited(Species.Meramon) or recruited(Species.Tyrannomon) or recruited(Species.Garurumon) or recruited(Species.Frigimon):
            if recruited(Species.Centarumon):
                if recruited(Species.Greymon):
                    warp(Screen.file_city_192, entry=6)
                    return
                warp(Screen.file_city_191, entry=6)
                return
            if recruited(Species.Greymon):
                warp(Screen.file_city_193, entry=6)
                return
            warp(Screen.file_city_190, entry=6)
            return
        if recruited(Species.Centarumon):
            if recruited(Species.Greymon):
                warp(Screen.file_city_195, entry=6)
                return
            warp(Screen.file_city_194, entry=6)
            return
        if recruited(Species.Greymon):
            warp(Screen.file_city_196, entry=6)
            return
        warp(Screen.file_city_189, entry=6)
        return
    if recruited(Species.Betamon) or recruited(Species.Coelamon):
        if recruited(Species.Meramon) or recruited(Species.Tyrannomon) or recruited(Species.Garurumon) or recruited(Species.Frigimon):
            if recruited(Species.Centarumon):
                if recruited(Species.Greymon):
                    warp(Screen.file_city_184, entry=6)
                    return
                warp(Screen.file_city_183, entry=6)
                return
            if recruited(Species.Greymon):
                warp(Screen.file_city_185, entry=6)
                return
            warp(Screen.file_city_182, entry=6)
            return
        if recruited(Species.Centarumon):
            if recruited(Species.Greymon):
                warp(Screen.file_city_187, entry=6)
                return
            warp(Screen.file_city_186, entry=6)
            return
        if recruited(Species.Greymon):
            warp(Screen.file_city_188, entry=6)
            return
        warp(Screen.file_city_181, entry=6)
        return
    if recruited(Species.Meramon) or recruited(Species.Tyrannomon) or recruited(Species.Garurumon) or recruited(Species.Frigimon):
        if recruited(Species.Centarumon):
            if recruited(Species.Greymon):
                warp(Screen.file_city_199, entry=6)
                return
            warp(Screen.file_city_198, entry=6)
            return
        if recruited(Species.Greymon):
            warp(Screen.file_city_200, entry=6)
            return
        warp(Screen.file_city_197, entry=6)
        return
    if recruited(Species.Centarumon):
        if recruited(Species.Greymon):
            warp(Screen.file_city_202, entry=6)
            return
        warp(Screen.file_city_201, entry=6)
        return
    if recruited(Species.Greymon):
        warp(Screen.file_city_203, entry=6)
        return
    warp(Screen.file_city_180, entry=6)
    return

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
        goto L133;
        goto L147;
        goto L149;
        goto L169;
        l2:
        show_textbox(text("s168.sec10.u0"));
        l3:
        goto l4;
        goto L134;
        goto L148;
        goto L150;
        goto L170;
        l4:
        show_textbox(text("s168.sec10.u1"));
        l5:
        goto l6;
        goto L135;
        goto L146;
        goto L151;
        goto L171;
        l6:
        show_textbox(text("s168.sec10.u2"));
        l7:
        goto l8;
        goto L136;
        goto L146;
        goto L151;
        goto L172;
        l8:
        show_textbox(text("s168.sec10.u3"));
        l9:
        goto l10;
        goto L137;
        goto L146;
        goto L150;
        goto L173;
        l10:
        show_textbox(text("s168.sec10.u4"));
        l11:
        goto l12;
        goto L134;
        goto L146;
        goto L150;
        goto L174;
        l12:
        show_textbox(text("s168.sec10.u5"));
        l13:
        goto l14;
        goto L134;
        goto L146;
        goto L152;
        goto L175;
        l14:
        show_textbox(text("s168.sec10.u6"));
        l15:
        goto l16;
        goto L134;
        goto L146;
        goto L153;
        goto L176;
        l16:
        show_textbox(text("s168.sec10.u7"));
        l17:
        goto l18;
        goto L134;
        goto L146;
        goto L154;
        goto L177;
        l18:
        show_textbox(text("s168.sec10.u8"));
        l19:
        goto l20;
        goto L134;
        goto L146;
        goto L155;
        goto L178;
        l20:
        show_textbox(text("s168.sec10.u9"));
        l21:
        goto l22;
        goto L134;
        goto L146;
        goto L156;
        goto L179;
        l22:
        show_textbox(text("s168.sec10.u10"));
        l23:
        goto l24;
        goto L138;
        goto L146;
        goto L157;
        goto L180;
        l24:
        show_textbox(text("s168.sec10.u11"));
        l25:
        goto l26;
        goto L139;
        goto L146;
        goto L158;
        goto L181;
        l26:
        show_textbox(text("s168.sec10.u12"));
        l27:
        goto l28;
        goto L140;
        goto L146;
        goto L159;
        goto L182;
        l28:
        show_textbox(text("s168.sec10.u13"));
        l29:
        goto l30;
        goto L141;
        goto L146;
        goto L160;
        goto L183;
        l30:
        show_textbox(text("s168.sec10.u14"));
        l31:
        goto l32;
        goto L142;
        goto L146;
        goto L161;
        goto L184;
        l32:
        show_textbox(text("s168.sec10.u15"));
        l33:
        goto l34;
        goto L143;
        goto L146;
        goto L162;
        goto L185;
        l34:
        show_textbox(text("s168.sec10.u16"));
        l35:
        goto l36;
        goto L144;
        goto L146;
        goto L163;
        goto L186;
        l36:
        show_textbox(text("s168.sec10.u17"));
        l37:
        goto l38;
        goto L145;
        goto L146;
        goto L164;
        goto L187;
        l38:
        show_textbox(text("s168.sec10.u18"));
        l39:
        goto l40;
        goto L142;
        goto L146;
        goto L165;
        goto L188;
        l40:
        show_textbox(text("s168.sec10.u19"));
        l41:
        goto l42;
        goto L141;
        goto L146;
        goto L166;
        goto L189;
        l42:
        show_textbox(text("s168.sec10.u20"));
        l43:
        goto l44;
        goto L141;
        goto L146;
        goto L167;
        goto L190;
        l44:
        show_textbox(text("s168.sec10.u21"));
        l45:
        goto l44;
        goto L133;
        goto L146;
        goto L168;
        goto L191;
    """)

@slot6.on_talk
def talk():    # section 11
    dws(r"""
        data(12, 13, 14, 26, 27, 28, 40, 41, 42, 54, 55, 56, 59, 60, 61);
        shared L133:
        data(0, 0, 0);
        shared L134:
        data(8, 0, 0);
        shared L135:
        data(24, 0, 0);
        shared L136:
        data(8, 4, 2);
        shared L137:
        data(8, 0, 1);
        shared L138:
        data(8, 4, 56);
        shared L139:
        data(8, 4, 48);
        shared L140:
        data(8, 4, 59);
        shared L141:
        data(8, 4, 61);
        shared L142:
        data(8, 4, 60);
        shared L143:
        data(6, 3, 60);
        shared L144:
        data(3, 2, 53);
        shared L145:
        data(8, 4, 61);
        shared L146:
        data(254);
        shared L147:
        data(12, 13, 14, 26, 27, 28, 40, 41, 42, 54, 55, 56, 59, 60, 61, 63, 64, 65, 66);
        shared L148:
        data(12, 13, 14, 26, 27, 28, 40, 41, 42, 54, 55, 56, 59, 60, 61);
        shared L149:
        data(3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40, 41, 42, 45, 46, 47, 48, 49, 50, 51, 52, 53, 54, 55, 56, 57, 58, 59, 60, 61, 63, 64, 65, 66);
        shared L150:
        data(3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40, 41, 42, 45, 46, 47, 48, 49, 50, 51, 52, 53, 54, 55, 56, 57, 58, 59, 60, 61, 63, 64, 65, 254);
        shared L151:
        data(3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40, 41, 42, 45, 46, 47, 48, 49, 50, 51, 52, 53, 54, 55, 56, 57, 58, 59, 60, 61);
        shared L152:
        data(3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 254);
        shared L153:
        data(17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 254);
        shared L154:
        data(31, 32, 33, 34, 35, 36, 37, 38, 39, 40, 41, 42, 254);
        shared L155:
        data(45, 46, 47, 48, 49, 50, 51, 52, 53, 54, 55, 56, 254);
        shared L156:
        data(57, 58, 59, 60, 61, 63, 64, 65, 254);
        shared L157:
        data(3, 5, 9, 21, 36, 47, 56);
        shared L158:
        data(6, 8, 13, 14, 17, 26, 27, 31, 34, 38, 42, 48, 63, 65, 254);
        shared L159:
        data(7, 18, 20, 33, 37, 45, 50, 59, 254);
        shared L160:
        data(4, 10, 22, 23, 24, 35, 49, 52, 57, 61, 254);
        shared L161:
        data(19, 25, 32, 46, 51, 55, 58, 60, 254);
        shared L162:
        data(12, 28, 40, 41, 54, 65, 254);
        shared L163:
        data(11, 39, 53);
        shared L164:
        data(3, 4, 8, 5, 7, 10, 12, 35, 47, 54, 61, 65, 254);
        shared L165:
        data(6, 7, 12, 19, 20, 21, 31, 33, 45, 50, 51, 54, 55, 59, 60);
        shared L166:
        data(14, 22, 24, 33, 36, 38, 42, 48, 57, 63, 254);
        shared L167:
        data(6, 9, 20, 34, 36, 40, 42, 48, 58, 65, 254);
        shared L168:
        data(19, 32, 51, 60, 254);
        shared L169:
        data(3, 4, 17, 18, 31, 32, 45, 46, 57, 74, 80, 82, 83, 86, 96, 103, 109, 111, 254);
        shared L170:
        data(5, 6, 7, 8, 9, 10, 11, 19, 20, 21, 22, 23, 24, 25, 33, 34, 35, 36, 37, 38, 39, 47, 48, 49, 50, 51, 52, 53, 58, 67, 68, 69, 71, 73, 74, 75, 76, 77, 78, 79, 80, 81, 82, 83, 84, 86, 87, 91, 92, 93, 94, 95, 96, 97, 98, 99, 101, 102, 103, 105, 106, 107, 109, 111);
        shared L171:
        data(5, 6, 7, 8, 9, 10, 11, 19, 20, 21, 22, 23, 24, 25, 33, 34, 35, 36, 37, 38, 39, 47, 48, 49, 50, 51, 52, 53, 58, 66, 67, 68, 69, 70, 71, 72, 73, 74, 75, 76, 77, 78, 79, 80, 81, 82, 83, 84, 85, 86, 87, 88, 89, 90, 91, 92, 93, 94, 95, 96, 97, 98, 99, 100, 101, 102, 103, 104, 105, 106, 107, 108, 109, 110, 111);
        shared L172:
        data(5, 6, 7, 12, 13, 14, 19, 20, 21, 26, 27, 28, 32, 33, 34, 40, 41, 42, 47, 48, 49, 54, 55, 56, 58, 59, 60, 61, 63, 64, 65, 66, 70, 72, 85, 88, 89, 90, 100, 104, 108, 110, 254);
        shared L173:
        data(12, 13, 14, 26, 27, 28, 40, 41, 42, 54, 55, 56, 59, 60, 61, 66, 254);
        shared L174:
        data(254);
        shared L175:
        data(3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 254);
        shared L176:
        data(17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 254);
        shared L177:
        data(31, 32, 33, 34, 35, 36, 37, 38, 39, 40, 41, 42, 254);
        shared L178:
        data(45, 46, 47, 48, 49, 50, 51, 52, 53, 54, 55, 56, 254);
        shared L179:
        data(57, 58, 59, 60, 61, 63, 64, 65, 66, 67, 68, 69, 70, 71, 72, 73, 74, 75, 76, 77, 78, 79, 80, 81, 82, 83, 84, 85, 86, 87, 88, 89, 90, 91, 92, 93, 94, 95, 96, 97, 98, 99, 100, 101, 102, 103, 104, 105, 106, 107, 108, 109, 110, 111, 254);
        shared L180:
        data(3, 5, 9, 21, 36, 47, 56, 69, 88, 101, 104, 105, 254);
        shared L181:
        data(6, 8, 13, 14, 17, 26, 27, 31, 34, 38, 42, 48, 68, 70, 72, 78, 79, 80, 81, 82, 83, 97, 106, 107, 108, 90, 254);
        shared L182:
        data(7, 18, 20, 33, 37, 45, 50, 66, 67, 75, 85, 95, 102);
        shared L183:
        data(4, 10, 22, 23, 24, 35, 49, 52, 57, 61, 71, 89, 94, 98, 100, 103, 109, 110, 254);
        shared L184:
        data(19, 25, 32, 46, 51, 55, 58, 60, 74, 77, 86, 91, 93, 99, 254);
        shared L185:
        data(12, 28, 40, 41, 54, 76, 84, 92);
        shared L186:
        data(11, 39, 53, 73, 87);
        shared L187:
        data(3, 4, 8, 5, 7, 10, 12, 35, 47, 54, 61, 69, 71, 83, 84, 88, 91, 98, 101, 106, 254);
        shared L188:
        data(6, 7, 12, 19, 20, 21, 31, 33, 45, 50, 51, 54, 55, 59, 60, 67, 85, 95, 96, 100, 102, 106, 254);
        shared L189:
        data(14, 22, 24, 33, 36, 38, 42, 48, 57, 69, 70, 75, 79, 93, 101, 105, 254);
        shared L190:
        data(6, 9, 20, 34, 36, 40, 42, 48, 52, 58, 66, 72, 80, 85, 89, 97, 100, 110, 104);
        shared L191:
        data(67, 74, 102, 111, 19, 32, 51, 60, 254);
        end_section();
        end_script();
    """)

# the section table, in the order of the original header
sections(254, 81, 54, 61, 51, 82, 83, 84, 6, 53, 52, 10, 11)
