# The Python view of script 211 of DG.SCN (no screen loads it).
# Made from the disc by `dws story-base`; the source of the story since 2026-10-15: edit it (no file = no script). Keys only, never the
# game's words. `story-build` reads this file (lowered); the DWS beside it is the proven intermediate; mods import `dw.base`.
from dw import *

lib = script(211)
slot1 = lib.npc(None, slot=1)    # no NPC of the .MAP in this slot; the script spawns what stands here
slot3 = lib.npc(None, slot=3)    # no NPC of the .MAP in this slot; the script spawns what stands here

@lib.on_enter
def enter():    # section 254
    pass

@slot3.on_talk
def talk():    # section 8
    dws(r"""
        if (!record_keeper_intro_seen) {
            record_keeper_intro_seen = true;
            say(slot1, text("s211.sec8.u0"));
            say(slot1, text("s211.sec8.u1"));
            say(slot1, text("s211.sec8.u2"));
            say(slot1, text("s211.sec8.u3"));
            return;
        }
        if (engine.prosperity == 100) {
            say(slot1, text("s211.sec8.u4"));
            return;
        }
        say(slot1, text("s211.sec8.u5"));
        goto l2;
        loop {
            say(slot1, text("s211.sec8.u6"));
            goto l2;
            l1:
            unless (hints_told == 1) break;
        }
        if (hints_told == 2) {
            say(slot1, text("s211.sec8.u7"));
            goto l2;
        }
        if (hints_told == 3) {
            hint_index = 0;
            hints_told = 0;
            return;
        }
        jump_return();
        l2:
        if (hint_index < 1) {
            hint_index += 1;
        } else {
            goto l3;
        }
        if (!is_recruited(species("Palmon"))) {
            say(slot1, text("s211.sec8.u8"));
            hints_told += 1;
        } else {
            goto l3;
        }
        gosub l1;
        l3:
        if (hint_index < 2) {
            hint_index += 1;
        } else {
            goto l4;
        }
        if (!is_recruited(species("Kunemon"))) {
            say(slot1, text("s211.sec8.u9"));
            hints_told += 1;
        } else {
            goto l4;
        }
        gosub l1;
        l4:
        if (hint_index < 3) {
            hint_index += 1;
        } else {
            goto l5;
        }
        if (!is_recruited(species("Centarumon"))) {
            say(slot1, text("s211.sec8.u10"));
            hints_told += 1;
        } else {
            goto l5;
        }
        gosub l1;
        l5:
        if (hint_index < 4) {
            hint_index += 1;
        } else {
            goto l6;
        }
        if (!is_recruited(species("Coelamon"))) {
            say(slot1, text("s211.sec8.u11"));
            hints_told += 1;
        } else {
            goto l6;
        }
        gosub l1;
        l6:
        if (hint_index < 5) {
            hint_index += 1;
        } else {
            goto l7;
        }
        if (!is_recruited(species("Betamon"))) {
            say(slot1, text("s211.sec8.u12"));
            hints_told += 1;
        } else {
            goto l7;
        }
        gosub l1;
        l7:
        if (hint_index < 6) {
            hint_index += 1;
        } else {
            goto l8;
        }
        if (!is_recruited(species("Bakemon"))) {
            say(slot1, text("s211.sec8.u13"));
            hints_told += 1;
        } else {
            goto l8;
        }
        gosub l1;
        l8:
        if (hint_index < 7) {
            hint_index += 1;
        } else {
            goto l9;
        }
        if (!is_recruited(species("Vegiemon"))) {
            say(slot1, text("s211.sec8.u14"));
            hints_told += 1;
        } else {
            goto l9;
        }
        gosub l1;
        l9:
        if (hint_index < 8) {
            hint_index += 1;
        } else {
            goto l10;
        }
        if (!is_recruited(species("Tyrannomon"))) {
            say(slot1, text("s211.sec8.u15"));
            hints_told += 1;
        } else {
            goto l10;
        }
        gosub l1;
        l10:
        if (hint_index < 9) {
            hint_index += 1;
        } else {
            goto l11;
        }
        if (!is_recruited(species("Meramon"))) {
            say(slot1, text("s211.sec8.u16"));
            hints_told += 1;
        } else {
            goto l11;
        }
        gosub l1;
        l11:
        if (hint_index < 10) {
            hint_index += 1;
        } else {
            goto l12;
        }
        if (!is_recruited(species("Frigimon"))) {
            say(slot1, text("s211.sec8.u17"));
            hints_told += 1;
        } else {
            goto l12;
        }
        gosub l1;
        l12:
        if (hint_index < 11) {
            hint_index += 1;
        } else {
            goto l13;
        }
        if (!is_recruited(species("Garurumon"))) {
            say(slot1, text("s211.sec8.u18"));
            hints_told += 1;
        } else {
            goto l13;
        }
        gosub l1;
        l13:
        if (hint_index < 12) {
            hint_index += 1;
        } else {
            goto l14;
        }
        if (!is_recruited(species("Birdramon"))) {
            say(slot1, text("s211.sec8.u19"));
            hints_told += 1;
        } else {
            goto l14;
        }
        gosub l1;
        l14:
        if (hint_index < 13) {
            hint_index += 1;
        } else {
            goto l15;
        }
        if (!is_recruited(species("Shellmon"))) {
            say(slot1, text("s211.sec8.u20"));
            hints_told += 1;
        } else {
            goto l15;
        }
        gosub l1;
        l15:
        if (hint_index < 14) {
            hint_index += 1;
        } else {
            goto l16;
        }
        if (!is_recruited(species("Elecmon"))) {
            say(slot1, text("s211.sec8.u21"));
            hints_told += 1;
        } else {
            goto l16;
        }
        gosub l1;
        l16:
        if (hint_index < 15) {
            hint_index += 1;
        } else {
            goto l17;
        }
        if (!is_recruited(species("Kokatorimon"))) {
            say(slot1, text("s211.sec8.u22"));
            hints_told += 1;
        } else {
            goto l17;
        }
        gosub l1;
        l17:
        if (hint_index < 16) {
            hint_index += 1;
        } else {
            goto l18;
        }
        if (!is_recruited(species("Monochromon"))) {
            say(slot1, text("s211.sec8.u23"));
            hints_told += 1;
        } else {
            goto l18;
        }
        gosub l1;
        l18:
        if (hint_index < 17) {
            hint_index += 1;
        } else {
            goto l19;
        }
        if (!is_recruited(species("Unimon"))) {
            say(slot1, text("s211.sec8.u24"));
            hints_told += 1;
        } else {
            goto l19;
        }
        gosub l1;
        l19:
        if (hint_index < 18) {
            hint_index += 1;
        } else {
            goto l20;
        }
        if (!is_recruited(species("Patamon")) || !is_recruited(species("Biyomon"))) {
            say(slot1, text("s211.sec8.u25"));
            hints_told += 1;
        } else {
            goto l20;
        }
        gosub l1;
        l20:
        if (hint_index < 19) {
            hint_index += 1;
        } else {
            goto l21;
        }
        if (!is_recruited(species("Greymon"))) {
            say(slot1, text("s211.sec8.u26"));
            hints_told += 1;
        } else {
            goto l21;
        }
        gosub l1;
        l21:
        if (hint_index < 20) {
            hint_index += 1;
        } else {
            goto l22;
        }
        if (!is_recruited(species("Penguinmon"))) {
            say(slot1, text("s211.sec8.u27"));
            hints_told += 1;
        } else {
            goto l22;
        }
        gosub l1;
        l22:
        if (hint_index < 21) {
            hint_index += 1;
        } else {
            goto l23;
        }
        if (!is_recruited(species("Drimogemon"))) {
            say(slot1, text("s211.sec8.u28"));
            hints_told += 1;
        } else {
            goto l23;
        }
        gosub l1;
        l23:
        if (hint_index < 22) {
            hint_index += 1;
        } else {
            goto l24;
        }
        if (!is_recruited(species("Gabumon"))) {
            say(slot1, text("s211.sec8.u29"));
            hints_told += 1;
        } else {
            goto l24;
        }
        gosub l1;
        l24:
        if (hint_index < 23) {
            hint_index += 1;
        } else {
            goto l25;
        }
        if (!is_recruited(species("Ninjamon"))) {
            say(slot1, text("s211.sec8.u30"));
            hints_told += 1;
        } else {
            goto l25;
        }
        gosub l1;
        l25:
        if (hint_index < 24) {
            hint_index += 1;
        } else {
            goto l26;
        }
        if (!is_recruited(species("Whamon"))) {
            say(slot1, text("s211.sec8.u31"));
            hints_told += 1;
        } else {
            goto l26;
        }
        gosub l1;
        l26:
        if (hint_index < 25) {
            hint_index += 1;
        } else {
            goto l27;
        }
        if (!is_recruited(species("Mojyamon"))) {
            say(slot1, text("s211.sec8.u32"));
            hints_told += 1;
        } else {
            goto l27;
        }
        gosub l1;
        l27:
        if (hint_index < 26) {
            hint_index += 1;
        } else {
            goto l28;
        }
        if (!is_recruited(species("Mamemon"))) {
            say(slot1, text("s211.sec8.u33"));
            hints_told += 1;
        } else {
            goto l28;
        }
        gosub l1;
        l28:
        if (hint_index < 27) {
            hint_index += 1;
        } else {
            goto l29;
        }
        if (!is_recruited(species("Numemon"))) {
            say(slot1, text("s211.sec8.u34"));
            hints_told += 1;
        } else {
            goto l29;
        }
        gosub l1;
        l29:
        if (hint_index < 28) {
            hint_index += 1;
        } else {
            goto l30;
        }
        if (!is_recruited(species("Seadramon"))) {
            say(slot1, text("s211.sec8.u35"));
            hints_told += 1;
        } else {
            goto l30;
        }
        gosub l1;
        l30:
        if (hint_index < 29) {
            hint_index += 1;
        } else {
            goto l31;
        }
        if (!is_recruited(species("Giromon"))) {
            say(slot1, text("s211.sec8.u36"));
            hints_told += 1;
        } else {
            goto l31;
        }
        gosub l1;
        l31:
        if (hint_index < 30) {
            hint_index += 1;
        } else {
            goto l32;
        }
        if (!canyon_cave_in.collapsed) {
            say(slot1, text("s211.sec8.u37"));
            hints_told += 1;
        } else {
            goto l32;
        }
        gosub l1;
        l32:
        if (hint_index < 31) {
            hint_index += 1;
        } else {
            goto l33;
        }
        if (!canyon_bandits_beaten) {
            say(slot1, text("s211.sec8.u38"));
            hints_told += 1;
        } else {
            goto l33;
        }
        gosub l1;
        l33:
        if (hint_index < 32) {
            hint_index += 1;
        } else {
            goto l34;
        }
        if (!new_ogre_fortress_cleared) {
            say(slot1, text("s211.sec8.u39"));
            hints_told += 1;
        } else {
            goto l34;
        }
        gosub l1;
        l34:
        if (hint_index < 33) {
            hint_index += 1;
        } else {
            goto l35;
        }
        if (!leomon_stone_taken) {
            say(slot1, text("s211.sec8.u40"));
            hints_told += 1;
        } else {
            goto l35;
        }
        gosub l1;
        l35:
        if (hint_index < 34) {
            hint_index += 1;
        } else {
            goto l36;
        }
        if (!is_recruited(species("Piximon"))) {
            say(slot1, text("s211.sec8.u41"));
            hints_told += 1;
        } else {
            goto l36;
        }
        gosub l1;
        l36:
        if (hint_index < 35) {
            hint_index += 1;
        } else {
            goto l37;
        }
        if (!is_recruited(species("Etemon"))) {
            say(slot1, text("s211.sec8.u42"));
            hints_told += 1;
        } else {
            goto l37;
        }
        gosub l1;
        l37:
        if (hint_index < 36) {
            hint_index += 1;
        } else {
            goto l38;
        }
        if (!is_recruited(species("MetalMamemon"))) {
            say(slot1, text("s211.sec8.u43"));
            hints_told += 1;
        } else {
            goto l38;
        }
        gosub l1;
        l38:
        if (hint_index < 37) {
            hint_index += 1;
        } else {
            goto l39;
        }
        if (!is_recruited(species("Vademon"))) {
            say(slot1, text("s211.sec8.u44"));
            hints_told += 1;
        } else {
            goto l39;
        }
        gosub l1;
        l39:
        if (hint_index < 38) {
            hint_index += 1;
        } else {
            goto l40;
        }
        if (key_chains == 0) {
            say(slot1, text("s211.sec8.u45"));
            hints_told += 1;
        } else {
            goto l40;
        }
        gosub l1;
        l40:
        if (hint_index < 39) {
            hint_index += 1;
        } else {
            goto l41;
        }
        if (key_chains == 1) {
            say(slot1, text("s211.sec8.u46"));
            hints_told += 1;
        } else {
            goto l41;
        }
        gosub l1;
        l41:
        if (hint_index < 40) {
            hint_index += 1;
        } else {
            goto l42;
        }
        if (!myotismon_joined_city) {
            say(slot1, text("s211.sec8.u47"));
            hints_told += 1;
        } else {
            goto l42;
        }
        gosub l1;
        l42:
        if (hint_index < 41) {
            hint_index += 1;
        } else {
            goto l43;
        }
        if (!engine.game_beaten) {
            say(slot1, text("s211.sec8.u48"));
            hints_told += 1;
        } else {
            goto l43;
        }
        gosub l1;
        l43:
        if (hint_index < 42) {
            hint_index += 1;
        } else {
            hint_index = 0;
            hints_told = 0;
            return;
        }
        if (!is_recruited(species("Digitamamon")) && engine.game_beaten) {
            say(slot1, text("s211.sec8.u49"));
            hints_told += 1;
        }
        hint_index = 0;
        hints_told = 0;
        return;
    """)

# the section table, in the order of the original header
sections(254, 8)
