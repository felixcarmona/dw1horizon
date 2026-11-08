#!/usr/bin/env python3
"""Execute the prepared C save policy against card capacity and IO failures.

Usage: python3 tools/dev/saves/capacity.py build/decomp-dev
No emulator or disc bytes are used; the function bodies come from the prepared
patch series and the card API is a deterministic fault-injection shim.
"""
from pathlib import Path
import subprocess
import sys
import tempfile


def function(source, name):
    start = source.index('static int32_t ' + name + '(')
    while source.index('{', start) > source.index('\n', start) and source[source.index('\n', start) - 1] == ';':
        start = source.index('static int32_t ' + name + '(', start + 1)
    brace = source.index('{', start)
    level = 1
    end = brace + 1
    while level:
        level += (source[end] == '{') - (source[end] == '}')
        end += 1
    return source[start:end]


HARNESS = r'''
#include <stdint.h>
#include <assert.h>
#include <string.h>
#define SAVE_V1_BYTES 0x2000
#define SAVE_V2_BYTES 0x4000
#define NUM_DIGIMON 1024
#define NUM_ORIGINAL_DIGIMON 180
#define NUM_ORIGINAL_SCREENS 255
#define NUM_ITEMS 128
static int SAVE_FILE_BYTES, MEMORY_CARD_ID;
static char SAVE_FILE_NAME[20], *MAIN_D_801346C0[] = {"", "*"};
static struct { int size; } MEMCARD_DIRENTRIES[15];
static struct { int blockNumber; struct { int checksum; } saves[2]; } SAVE_FILE;
static uint8_t SPECIES_RAISED_BITS[128], SPECIES_RECRUITED_BITS[128];
static long SAVE_IO_FAILED;
static int used, dir_error, deletes, creates, writes, write_error;
static int MemCardGetDirentry(int card, char *name, void *entries, long *count, int a, int b) {
    *count = 1; MEMCARD_DIRENTRIES[0].size = used * SAVE_V1_BYTES; return dir_error;
}
static int MemCardDeleteFile(int card, char *name) { deletes++; return 0; }
static int MemCardCreateFile(int card, char *name, int blocks) { creates++; return 0; }
static int createSavegameChecksum(int copy) { return 123; }
static int saveFileStart(int write) { writes++; SAVE_IO_FAILED = write_error; return 1; }
'''

CASES = r'''
static void reset(int bytes, int blocks) {
    SAVE_FILE_BYTES=bytes; used=blocks; dir_error=deletes=creates=writes=write_error=0;
    SAVE_IO_FAILED=99;
}
int main(void) {
    int16_t inventory[30] = {0};
    /* Native content remains compatible; extended history/recruits require the extension. */
    assert(!needsNewExecutable(3, 0, 0, inventory));
    SPECIES_RAISED_BITS[470/8] = 1 << (470%8);
    assert(needsNewExecutable(3, 0, 0, inventory));
    memset(SPECIES_RAISED_BITS, 0, sizeof(SPECIES_RAISED_BITS));
    SPECIES_RECRUITED_BITS[106/8] = 1 << (106%8);
    assert(needsNewExecutable(3, 0, 0, inventory));
    /* A full card must retain its old one-block save byte for byte. */
    reset(SAVE_V1_BYTES, 15); SAVE_FILE.saves[0].checksum = ~123;
    assert(writeSaveFile()==1 && SAVE_IO_FAILED==7);
    assert(!deletes && !creates && !writes && SAVE_FILE.saves[0].checksum==~123);
    /* A failed directory lookup must also leave the card untouched. */
    reset(SAVE_V1_BYTES, 1); dir_error=1;
    assert(writeSaveFile()==1 && SAVE_IO_FAILED==7 && !deletes && !writes);
    /* Existing two-block files can save even on a completely full card. */
    reset(SAVE_V2_BYTES, 15);
    assert(writeSaveFile()==1 && SAVE_IO_FAILED==0 && writes==1 && !deletes);
    assert(SAVE_FILE.blockNumber==2);
    reset(SAVE_V2_BYTES, 15); write_error=1;
    assert(writeSaveFile()==1 && SAVE_IO_FAILED==1 && writes==1);
    /* A native one-block file grows when the card has a spare block. */
    reset(SAVE_V1_BYTES, 14);
    assert(writeSaveFile()==1 && SAVE_IO_FAILED==0 && writes==1 && deletes==1 && creates==1);
    assert(SAVE_FILE_BYTES==SAVE_V2_BYTES && SAVE_FILE.blockNumber==2);
    return 0;
}
'''


def main():
    source = (Path(sys.argv[1]) / 'src/main/main_menu.c').read_text()
    code = HARNESS + '\n'.join(function(source, name) for name in ('needsNewExecutable', 'writeSaveFile')) + CASES
    with tempfile.TemporaryDirectory(prefix='save-capacity-') as work:
        src = Path(work) / 'test.c'
        src.write_text(code)
        exe = Path(work) / 'test'
        subprocess.run(['cc', '-std=c99', '-O2', str(src), '-o', str(exe)], check=True)
        subprocess.run([str(exe)], check=True)
    print('PASS: extended progress, full card, failed lookup, IO error and one-block upgrade')


if __name__ == '__main__':
    main()
