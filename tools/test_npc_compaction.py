#!/usr/bin/env python3
"""Run the target C compactor on native/replacement models and preserve every kept animation."""
import argparse
import os
import struct
import subprocess
import tempfile
from pathlib import Path
import membudget as m
import npcanims as n
from derive.facts import capture


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('worktree')
    ap.add_argument('--archive', required=True)
    args = ap.parse_args()
    work = Path(args.worktree)
    facts = capture(str(work))
    m.MODEL_ARCHIVE = os.path.abspath(args.archive)
    m.TARGET_FACTS = facts
    source = (work / 'src/main/npc_anim_trim.c').read_text()
    source = '\n'.join(line for line in source.splitlines() if not line.startswith('#include'))
    keep = (work / 'src/main/npc_anim_keep.c').read_text()
    keep = '\n'.join(line for line in keep.splitlines() if not line.startswith('#include'))
    code = '''#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <assert.h>
#include <string.h>
typedef struct { int boneCount; } Para;
Para DIGIMON_DATA[180];
void free3(void *p) { abort(); }
''' + keep + '\n' + source + r'''
int main(int argc, char **argv) {
    int type = atoi(argv[1]), bones = atoi(argv[2]), size, result;
    uint8_t *raw, *data;
    FILE *f = fopen(argv[3], "rb"); assert(f);
    fseek(f, 0, SEEK_END); size = ftell(f); rewind(f);
    raw = malloc(size + 64); assert(raw); memset(raw, 0xA5, size + 64);
    data = raw + 32; assert(fread(data, 1, size, f) == size); fclose(f);
    if (type < 180) DIGIMON_DATA[type].boneCount = bones;
    result = compactNpcModel(type, data, size);
    assert(result > 0 && result <= size);
    for (int i = 0; i < 32; i++) { assert(raw[i] == 0xA5); assert(raw[size + 32 + i] == 0xA5); }
    f = fopen(argv[4], "wb"); assert(f);
    assert(fwrite(data, 1, result, f) == result); fclose(f); free(raw);
    return 0;
}
'''
    count = 0
    with tempfile.TemporaryDirectory(prefix='npc-compact-') as temp:
        root = Path(temp)
        (root / 'test.c').write_text(code)
        subprocess.run(['cc', '-std=c99', '-O1', '-g', '-fsanitize=address,undefined', '-fno-pie', '-no-pie',
                        str(root / 'test.c'), '-o', str(root / 'test')], check=True)
        for t in sorted(m.DIGI):
            try: data = m.model_data(t)
            except (FileNotFoundError, KeyError): continue
            if not data: continue
            (root / 'input').write_bytes(data)
            subprocess.run([str(root / 'test'), str(t), str(m.DIGI[t]['bone_count']),
                            str(root / 'input'), str(root / 'output')], check=True)
            result = (root / 'output').read_bytes()
            assert len(result) == n.trimmed_size(t), (t, len(result), n.trimmed_size(t))
            if len(result) == len(data): assert result == data
            else:
                ta, offsets, sizes = n.mmd_slots(data)
                _, new, _ = n.mmd_slots(result)
                assert result[:ta] == data[:ta], t
                for slot in facts['npc_anim_keep'][t]:
                    if slot >= len(offsets) or not offsets[slot]: continue
                    size = sizes[offsets[slot]]
                    assert result[ta + new[slot]:ta + new[slot] + size] == data[ta + offsets[slot]:ta + offsets[slot] + size], (t, slot)
                assert all(not x or ta + x < len(result) for x in new), t
            count += 1
    print(f'PASS: {count} actual models; target C/Python sizes agree, kept TMD/animations identical, ASan/UBSan and guards clean')


if __name__ == '__main__':
    main()
