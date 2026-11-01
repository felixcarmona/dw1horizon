#!/usr/bin/env python3
"""Host checks of the actual laboratory's field writes, bounds and needs action.

Run: python3 tools/test_lab.py [build/decomp-lab246]
"""
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def function(text, name):
    match = re.search(r'^static [^;\n]+\b' + name + r'\([^;]*?\)\n\{', text, re.M)
    assert match, name
    return text[match.start():text.index('\n}', match.end()) + 2]


def struct(text, name):
    end = text.index('} ' + name + ';') + len('} ' + name + ';')
    return text[text.rfind('typedef struct {', 0, end):end]


def main():
    work = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / 'build/decomp-lab246'
    source = (work / 'src/main/mod_lab_menu.inc').read_text()
    params = (work / 'include/dw/params.h').read_text()
    entity = (work / 'include/dw/entity.h').read_text()
    level = (work / 'include/dw/level.h').read_text()
    code = '#include <stdint.h>\n#include <stddef.h>\n#include <string.h>\n#include <assert.h>\n#include <stdio.h>\n'
    for name in ('BaseStats', 'CurrentStats', 'Stats'):
        code += struct(entity, name) + '\n'
    code += struct(params, 'PartnerPara') + '\n'
    for line in level.splitlines():
        if line.startswith('#define MOD_CARE_LIM_'):
            code += line + '\n'
    for name in sorted(set(re.findall(r'LAB_STR_\w+', source))):
        code += f'#define {name} "{name}"\n'
    code += r'''
#define HPMP_CAP 30000
#define STAT_CAP 9999
#define NUM_PARTNER_DIGIMON 66
PartnerPara PARTNER_PARA;
struct { struct { struct { int type; } entity; Stats stats; } digimonEntity; } PARTNER_ENTITY;
struct { int energyCap, poopTimer; } raise = {70, 420};
#define RAISE_ROW(type) raise
int care[150], HOUR = 12, MINUTE = 25, HAS_BUTTERFLY = -1, BUTTERFLY_ID;
int HAS_IMMORTAL_HOUR;
int CONDITION_BUBBLE_ID = -1, CONDITION_BUBBLE_TYPE, calls;
int careGet(int slot) { return care[slot]; }
void setFoodTimer(int type) { PARTNER_PARA.foodLevel = 240; }
void setSleepTimes(PartnerPara *p, int type) { p->hoursAwakeDefault = 16; p->hoursAsleepDefault = 8; }
void setSleepDisabled(int disabled) { assert(disabled == 1); }
void unsetButterfly(int id) { calls++; }
void removeConditionBubble(int id) { assert(id >= 0); calls++; }
int partnerGetState(void) { return 1; }
void updateConditionAnimation(void) { calls++; }
int isVanillaSpecies(int type) { return type <= 65; }
'''
    start = source.index('typedef struct {\n    char *name;')
    end = source.index('\nstatic int16_t *modLabFieldPtr', start)
    code += source[start:end]
    for name in ('modLabFieldPtr', 'modLabBound', 'modLabClamp', 'modLabSetValue', 'modLabHeal', 'modLabSatiate', 'modLabOldAge', 'modLabNewSpecies'):
        code += '\n' + function(source, name)
    code += r'''
int main(void) {
    memset(care, 0xff, sizeof(care));
    PARTNER_ENTITY.digimonEntity.stats.base.hp = 800;
    PARTNER_ENTITY.digimonEntity.stats.base.mp = 600;
    for (int field = 0; field < LAB_FIELD_COUNT; field++) {
        int lo = modLabBound(field, 0), hi = modLabBound(field, 1);
        assert(lo <= hi);
        modLabSetValue(field, -99999); assert(*modLabFieldPtr(field) == lo);
        modLabSetValue(field, 99999); assert(*modLabFieldPtr(field) == hi);
    }
    modLabSetValue(7, 0); assert(PARTNER_PARA.remainingLifetime == 1); /* zero is the old-age row's, never the editor's */
    HAS_IMMORTAL_HOUR = 1; modLabOldAge();
    assert(PARTNER_PARA.remainingLifetime == 0 && HAS_IMMORTAL_HOUR == 0);
    modLabSetValue(0, 87); assert(PARTNER_PARA.discipline == 87);
    modLabSetValue(1, -25); assert(PARTNER_PARA.happiness == -25);
    modLabSetValue(2, 35); assert(PARTNER_PARA.weight == 35);
    care[MOD_CARE_LIM_DISC_MAX] = 80; modLabSetValue(0, 99); assert(PARTNER_PARA.discipline == 80);
    modLabSetValue(18, 9000); modLabSetValue(12, 3000);
    assert(PARTNER_ENTITY.digimonEntity.stats.current.currentHP == 3000);
    modLabSetValue(19, 9000); modLabSetValue(13, 2000);
    assert(PARTNER_ENTITY.digimonEntity.stats.current.currentMP == 2000);
    PARTNER_PARA.careMistakes = 3; PARTNER_PARA.battles = 5;
    PARTNER_PARA.evoTimer = 72; PARTNER_PARA.age = 4; PARTNER_PARA.virusBar = 42;
    PARTNER_PARA.condition = 0x7f; PARTNER_PARA.tiredness = 99;
    PARTNER_PARA.energyLevel = 0; PARTNER_PARA.foodLevel = 0;
    PARTNER_PARA.sicknessTimer = 9; PARTNER_PARA.injuryTimer = 4;
    PARTNER_PARA.starvationTimer = -1; PARTNER_PARA.poopLevel = 0;
    modLabSatiate();
    assert(!PARTNER_PARA.condition && !PARTNER_PARA.tiredness);
    assert(PARTNER_PARA.energyLevel == 70 && PARTNER_PARA.foodLevel == 240);
    assert(PARTNER_PARA.poopLevel == 420 && PARTNER_PARA.poopingTimer == -1);
    assert(!PARTNER_PARA.sicknessTimer && !PARTNER_PARA.injuryTimer && !PARTNER_PARA.starvationTimer);
    assert(PARTNER_PARA.happiness == 100 && PARTNER_PARA.discipline == 80 && PARTNER_PARA.weight == 35);
    assert(PARTNER_PARA.careMistakes == 3 && PARTNER_PARA.battles == 5);
    assert(PARTNER_PARA.evoTimer == 72 && PARTNER_PARA.age == 4 && PARTNER_PARA.virusBar == 42);
    assert(PARTNER_ENTITY.digimonEntity.stats.current.currentHP == 3000);
    assert(PARTNER_ENTITY.digimonEntity.stats.current.currentMP == 2000);
    assert(calls == 1); /* no removal through an invalid bubble id */
    HAS_BUTTERFLY = 0; CONDITION_BUBBLE_ID = 7; calls = 0;
    modLabSatiate(); assert(calls == 3 && HAS_BUTTERFLY == -1);
    assert(!modLabNewSpecies(3) && !modLabNewSpecies(65));
    assert(modLabNewSpecies(94) && modLabNewSpecies(180));
    puts("PASS: all 20 field bounds/writes, active care rules, HP/MP caps, all needs restored, evolution history preserved, NEW markers");
}
'''
    with tempfile.TemporaryDirectory(prefix='dw-lab-') as temp:
        c = Path(temp) / 'lab.c'
        binary = Path(temp) / 'lab'
        c.write_text(code)
        subprocess.run(['cc', '-std=c99', '-fsanitize=address,undefined', str(c), '-o', str(binary)], check=True)
        subprocess.run([str(binary)], check=True)


if __name__ == '__main__':
    main()
