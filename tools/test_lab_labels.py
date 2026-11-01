#!/usr/bin/env python3
"""Check actual Cheats label helpers against compiled species data and canonical stages."""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import species
from test_lab import function

work = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / 'build/decomp-lab246'
source = (work / 'src/main/mod_lab_menu.inc').read_text()
rows, _ = species.exe_files(str(work / 'build/us/psx/gcc'))
data = species.load_content()
invalid = [s['id'] for s in data.values() if s.get('partner') and s['level'] not in species.LEVELS[1:]]
assert not invalid, invalid
checks = []
for ident in range(180):
    expected = species.LEVELS.index(data[ident]['level'])
    raw = rows[ident]['para']['level']
    # At boot a record original's DIGI.DAT row replaces its resident one (copyRecordOriginal), so the label reads the
    # file's stage. A zero row stays zero here: it proves modLabStage's fallback for the disc's empty rows.
    if raw and species.is_record_original(data[ident]):
        raw = expected
    checks.append(f'para[{ident}].level = {raw}; assert(modLabStage({ident}) == {expected});')
code = r'''
#include <stdint.h>
#include <string.h>
#include <assert.h>
#include <stdio.h>
#define LEVEL_ROOKIE 3
#define LEVEL_ULTIMATE 5
struct { int level; } para[1024];
#define DIGI_PARA(id) para[id]
'''
code += function(source, 'modLabTrimLabel') + '\n' + function(source, 'modLabStage')
code += '\nint main(void) {\n' + '\n'.join(checks) + r'''
char a[] = "       Bosque Indígena     "; modLabTrimLabel(a); assert(!strcmp(a, "Bosque Indígena"));
char b[] = "\x81\x40" " Monte Infinito " "\x81\x40"; modLabTrimLabel(b); assert(!strcmp(b, "Monte Infinito"));
char c[] = "    "; modLabTrimLabel(c); assert(!strcmp(c, ""));
char d[] = ""; modLabTrimLabel(d); assert(!strcmp(d, ""));
char e[] = "Test Hollow"; modLabTrimLabel(e); assert(!strcmp(e, "Test Hollow"));
char f[] = "  A  B  "; modLabTrimLabel(f); assert(!strcmp(f, "A  B"));
char g[] = "\x81\x40"; modLabTrimLabel(g); assert(!strcmp(g, ""));
/* Real data always wins over a fallback, including a future replacement record. */
para[62].level = 6; assert(modLabStage(62) == 6);
para[122].level = 4; assert(modLabStage(122) == 4);
puts("PASS: all 180 compiled native stages match canonical metadata; padded and encoded captions trim correctly.");
}
'''
with tempfile.TemporaryDirectory(prefix='lab-labels-') as td:
    p = Path(td); (p / 'test.c').write_text(code)
    subprocess.run(['cc', '-std=c99', '-fsanitize=address,undefined', '-fno-pie', '-no-pie', '-o', str(p/'test'), str(p/'test.c')], check=True)
    subprocess.run([str(p/'test')], check=True)
print(f'PASS: all {len(data)} project species validate; {sum(bool(s.get("partner")) for s in data.values())} partners have a defined evolution stage.')
