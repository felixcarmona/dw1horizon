#!/usr/bin/env python3
"""Exercise actual trigger/recruit routines and the unchanged City page on the host.

Graphics and CD reads are stubs; this does not replace a console save/load test.
"""
import argparse
import ctypes
from pathlib import Path
import re
import subprocess
import tempfile


def function(source, name):
    start = re.search(r'^(?:static )?(?:void|int32_t) ' + name + r'\(', source, re.M).start()
    begin = source.index('{', start)
    end, depth = begin + 1, 1
    while depth:
        depth += (source[end] == '{') - (source[end] == '}')
        end += 1
    return source[start:end]


def check(tree):
    interp = (tree / 'src/main/script_interp.c').read_text()
    species = (tree / 'src/main/mod_species.c').read_text()
    menu = (tree / 'src/main/game_menu.c').read_text()
    code = '''#include <stdint.h>
#include <stddef.h>
typedef unsigned long u_long;
#define NUM_DIGIMON 1024
#define NUM_RECRUITABLE_DIGIMON 112
#define TRIGGER_RECRUITED_BASE 200
#define TRIGGER_SPECIES_RECRUITED_BASE 0x8000
uint8_t SPECIES_RECRUITED_BITS[128], SPECIES_RAISED_BITS[128];
struct ScriptState { uint8_t triggers[100], pstats[256]; } state;
struct ScriptState *SCRIPT_STATE_PTR = &state;
'''
    code += function(interp, 'getTriggerOffset') + '\n'
    for name in ('setTrigger', 'unsetTrigger', 'isTriggerSet'):
        code += function(interp, name) + '\n'
    for name in ('isDigimonRecruited', 'setDigimonRecruited'):
        code += function(species, name) + '\n'
    code += '''
#define SPECIES_CHART_TABS 5
#define CHART_ROWS 5
#define CHART_COLS 6
#define CHART_PAGE_SIZE 30
#define NUM_EVO_CHART_DIGIMON 61
#define SPECIES_CHART_ICONS_PER_SECTOR 7
#define SPECIES_CHART_ICON_SIZE 288
#define CHART_CLUT_X 0
#define CHART_CLUT_Y 0
#define CHART_ICON_X 0
#define CHART_ICON_Y 0
int CHART_PAGE_COUNT, CHART_RAISED, CHART_TEXT_ID, CHART_TAB_COUNT[5];
int CHART_TAB, CHART_TOP, CITY_VIEW = 1, MOD_OPT_STORY = 1;
uint16_t CHART_PAGE_IDS[30], roster[1024], icons[1024];
int grey_calls, raised_calls;
struct { int m[256]; } EVO_CHART_VIEW_COLORS;
struct { int clut; } EVO_CHART_BOXES[61];
typedef struct { int unused; } RECT;
uint8_t *readSpeciesChart(int sector, int city) { return (uint8_t *)(sector ? icons : roster); }
int hasDigimonRaised(int id) { raised_calls++; return 0; }
int chartRows(void) { return (CHART_TAB_COUNT[CHART_TAB] + CHART_COLS - 1) / CHART_COLS; }
int chartSlot(int k) { return k; }
void setRECT(RECT *r, int x, int y, int w, int h) {}
void StoreImage(RECT *r, unsigned long *data) {}
void LoadImage(RECT *r, unsigned long *data) {}
void DrawSync(int n) {}
void cityGreyClut(uint16_t *data, int slot) { grey_calls++; }
'''
    code += function(menu, 'chartLoadPage') + '\nvoid load_city(void) { chartLoadPage(-1); }\n'
    with tempfile.TemporaryDirectory() as folder:
        src, lib = Path(folder) / 'city.c', Path(folder) / 'city.so'
        src.write_text(code)
        subprocess.run(['cc', '-shared', '-fPIC', '-O2', '-Wall', '-Werror', '-Wno-old-style-definition', str(src), '-o', str(lib)], check=True)
        c = ctypes.CDLL(str(lib))
        bits = (ctypes.c_uint8 * 128).in_dll(c, 'SPECIES_RECRUITED_BITS')
        raised = (ctypes.c_uint8 * 128).in_dll(c, 'SPECIES_RAISED_BITS')
        legacy = (ctypes.c_uint8 * 356).in_dll(c, 'state')
        # Ordinary triggers, including all raised triggers, retain their exact offsets.
        for flag in range(800):
            c.setTrigger(flag)
            assert legacy[flag // 8] == 1 << (flag & 7), flag
            assert c.isTriggerSet(flag) == 1
            c.unsetTrigger(flag)
            assert c.isTriggerSet(flag) == 0
        for sp in range(112, 1024):
            flag = 0x8000 + sp
            c.setTrigger(flag)
            assert c.isDigimonRecruited(sp) == 1, sp
            assert bits[sp // 8] == 1 << (sp & 7), sp
            c.unsetTrigger(flag)
            assert c.isDigimonRecruited(sp) == 0, sp
            c.setDigimonRecruited(sp)
            assert c.isTriggerSet(flag) == 1, sp
            c.unsetTrigger(flag)
        assert not any(bits) and not any(raised) and not any(legacy)
        for sp in range(112):
            c.setDigimonRecruited(sp)
            assert c.isTriggerSet(200 + sp) == 1
            c.unsetTrigger(200 + sp)
        assert c.isDigimonRecruited(-1) == c.isDigimonRecruited(1024) == 0
        roster = (ctypes.c_uint16 * 1024).in_dll(c, 'roster')
        ids = [3, 241, 273, 290, 0x8000 | 294]
        roster[:len(ids) + 1] = [len(ids), *ids]
        count = ctypes.c_int.in_dll(c, 'CHART_RAISED')
        page = (ctypes.c_uint16 * 30).in_dll(c, 'CHART_PAGE_IDS')
        for sp in (241, 273, 290, 294):
            c.setTrigger(0x8000 + sp)
        c.load_city()
        assert count.value == 4 and list(page[:5]) == ids
        assert ctypes.c_int.in_dll(c, 'raised_calls').value == 0
        c.unsetTrigger(0x8000 + 294)
        c.load_city()
        assert count.value == 3
        ctypes.c_int.in_dll(c, 'MOD_OPT_STORY').value = 0
        c.load_city()
        assert ctypes.c_int.in_dll(c, 'CHART_PAGE_COUNT').value == 1
        assert page[0] == 3 and count.value == 0
    print('PASS: actual C; 800 ordinary triggers, 912 recruit bits, 112 legacy recruits; City page u16 ids and original filter')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('tree', type=Path)
    check(parser.parse_args().tree)
