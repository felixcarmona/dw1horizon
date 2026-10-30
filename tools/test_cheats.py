#!/usr/bin/env python3
"""Compile actual option/save and shortcut functions on the host.

Usage: python3 tools/test_cheats.py [build/decomp-cheats]
"""
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def function(source, name):
    start = re.search(r'^(?:static )?(?:void|int32_t) ' + name + r'\([^;]*?\)\n\{', source, re.M)
    assert start, name
    end = source.index('\n}', start.end()) + 2
    return source[start.start():end]


def main():
    work = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / 'build/decomp-cheats'
    menu = (work / 'src/main/main_menu.c').read_text()
    lab = (work / 'src/main/mod_lab.c').read_text()
    code = r'''
#include <stdint.h>
#include <string.h>
#include <assert.h>
#include <stdio.h>
#define FONT_SWITCH 0
#define MOD_BUTTONS_US 0
#define MOD_DIFF_EASY 0
#define MOD_DIFF_NORMAL 1
#define MOD_OPT_BYTES 13
#define MOD_OPT_HEADER_BYTES 12
#define MOD_OPT_HEADER_CHEATS 0x80
#define PAD_SELECT 0x100
#define PAD_L1 4
#define PAD_R1 8
#define PAD_L2 1
#define PAD_R2 2
int32_t MOD_OPT_BUTTONS, MOD_OPT_CLOCK, MOD_OPT_BARS, MOD_OPT_EVO_GUIDE;
int32_t MOD_OPT_NEW_DIGIMON, MOD_LANG, MOD_OPT_SIGNS, MOD_OPT_STORY;
int32_t MOD_OPT_DIFFICULTY, MOD_OPT_QUICK_BATTLE, MOD_OPT_CHEATS, MOD_OPT_TOUCHED;
int32_t MOD_SAVE_NUMBER, fps = 60;
struct { uint8_t prefix[0x50], pocketStation[16], icon[32]; } SAVE_FILE;
int32_t modFrameRate(void) { return fps; }
void modSetFrameRate(int32_t v) { fps = v; }
void modSetButtons(int32_t v) { MOD_OPT_BUTTONS = v; }
void modSetLanguage(int32_t v) { MOD_LANG = v; }
void modSetSigns(int32_t v) { MOD_OPT_SIGNS = v; }
void modSetStory(int32_t v) { MOD_OPT_STORY = v; }
uint32_t POLLED_INPUT, POLLED_INPUT_PREVIOUS;
int IS_SCRIPT_PAUSED = 1, EVOLUTION_TARGET = -1, state = 1, busy, effects;
struct { struct { struct { int type; } entity; } digimonEntity; } PARTNER_ENTITY;
int partnerGetState(void) { effects++; return state; }
int isFileReadQueueBusy(void) { effects++; return busy; }
void playSound(int a, int b) { effects++; }
int modScreenJump(int step) { effects++; return 1; }
int modRosterStep(int step) { effects++; return 17; }
void modRosterSwitch(int type) { effects++; PARTNER_ENTITY.digimonEntity.entity.type = type; }
void modRosterShowCaption(int type) { effects++; }
'''
    for name in ('modOptionBytes', 'modApplyOptions', 'modTitleOptions', 'modHeaderSaveNumber'):
        code += '\n' + function(menu, name)
    code += '\n' + function(lab, 'modRosterTick')
    code += r'''
int main(void) {
    uint8_t options[MOD_OPT_BYTES + 1];
    for (int cheats = 0; cheats < 2; cheats++) {
        for (int quick = 0; quick < 2; quick++) {
            memset(options, 0xA5, sizeof(options));
            memset(&SAVE_FILE, 0xA5, sizeof(SAVE_FILE));
            MOD_OPT_CHEATS = cheats; MOD_OPT_QUICK_BATTLE = quick;
            modOptionBytes(options);
            assert(options[11] == quick && options[12] == cheats && options[13] == 0xA5);
            modTitleOptions();
            assert(modHeaderSaveNumber((uint8_t *)&SAVE_FILE) == MOD_SAVE_NUMBER);
            assert(!memcmp(SAVE_FILE.pocketStation + 4, options, 12));
            assert(!!(SAVE_FILE.pocketStation[1] & 0x80) == cheats);
            for (int i = 0; i < 32; i++) assert(SAVE_FILE.icon[i] == 0xA5);
            MOD_OPT_CHEATS = !cheats; MOD_OPT_QUICK_BATTLE = !quick;
            modApplyOptions(options, 13);
            assert(MOD_OPT_CHEATS == cheats && MOD_OPT_QUICK_BATTLE == quick);
            MOD_OPT_TOUCHED = 1; MOD_OPT_CHEATS = !cheats;
            modApplyOptions(options, 13); assert(MOD_OPT_CHEATS == !cheats);
            MOD_OPT_TOUCHED = 0;
        }
    }
    for (int len = 0; len <= 12; len++) {
        MOD_OPT_CHEATS = 1; modApplyOptions(options, len); assert(!MOD_OPT_CHEATS);
    }
    for (int count = 0; count < 128; count++) {
        SAVE_FILE.pocketStation[1] = count;
        assert((modHeaderSaveNumber((uint8_t *)&SAVE_FILE) >= 0) == (count > 0 && count <= 12));
    }
    for (int key = 1; key <= 8; key *= 2) {
        POLLED_INPUT = PAD_SELECT | key; POLLED_INPUT_PREVIOUS = 0;
        MOD_OPT_CHEATS = 0; effects = 0;
        assert(modRosterTick() == 0 && effects == 0);
        MOD_OPT_CHEATS = 1;
        assert(modRosterTick() == 1 && effects > 0);
        POLLED_INPUT_PREVIOUS = POLLED_INPUT; effects = 0;
        assert(modRosterTick() == 0 && effects == 0);
    }
    puts("PASS: save round trips, old saves OFF, header bounds, explicit options retained, all four shortcuts gated");
}
'''
    with tempfile.TemporaryDirectory(prefix='dw-cheats-') as tmp:
        source = Path(tmp) / 'check.c'
        source.write_text(code)
        binary = Path(tmp) / 'check'
        subprocess.run(['cc', '-std=c99', '-fsanitize=address,undefined', str(source), '-o', str(binary)], check=True)
        subprocess.run([str(binary)], check=True)


if __name__ == '__main__':
    main()
