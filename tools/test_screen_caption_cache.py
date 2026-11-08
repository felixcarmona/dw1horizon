#!/usr/bin/env python3
"""Compile the screen cache and revisit cached captions after a language switch."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools.test_cheats import compile_check, function


def main():
    work = Path(sys.argv[1]) if len(sys.argv) > 1 else Path('build/decomp-dev')
    source = (work / 'src/main/mod_screen.c').read_text()
    start = source.index('static ScreenRecordHead *getScreenHead(')
    end = source.index('\n}', start) + 2
    code = r'''
#include <stdint.h>
#include <assert.h>
#include <string.h>
#include <stdio.h>
#define SCREEN_CACHE_SLOTS 4
typedef struct { char caption[36]; } ScreenRecordHead;
static ScreenRecordHead SCREEN_CACHE[SCREEN_CACHE_SLOTS], SECTOR_VALUE, NO_SCREEN;
#define SCREEN_SECTOR (&SECTOR_VALUE)
static int16_t SCREEN_CACHE_ID[SCREEN_CACHE_SLOTS] = {-1,-1,-1,-1};
static int16_t SCREEN_SECTOR_ID = -1;
static int32_t SCREEN_CACHE_NEXT, CURRENT_SCREEN = 302;
static int language, reads;
static int32_t readScreenRecord(int32_t id) {
    if (SCREEN_SECTOR_ID != id) {
        reads++; SCREEN_SECTOR_ID = id;
        strcpy(SECTOR_VALUE.caption, language == 0 ? "The Shaft" : language == 1 ? "O Poco" : "El Pozo");
    }
    return 1;
}
''' + function(source, 'modScreenFileChanged') + '\n' + source[start:end] + r'''
int main(void) {
    assert(strcmp(getScreenHead(302)->caption, "The Shaft") == 0);
    getScreenHead(303); getScreenHead(304); getScreenHead(305);
    int before = reads;
    assert(strcmp(getScreenHead(302)->caption, "The Shaft") == 0 && reads == before);
    language = 1;
    modScreenFileChanged();
    assert(SCREEN_SECTOR_ID == -1);
    assert(strcmp(getScreenHead(302)->caption, "O Poco") == 0 && reads == before + 1);
    assert(strcmp(getScreenHead(303)->caption, "O Poco") == 0 && reads == before + 2);
    before = reads;
    assert(strcmp(getScreenHead(302)->caption, "O Poco") == 0 && reads == before);
    language = 2;
    modScreenFileChanged();
    assert(strcmp(getScreenHead(302)->caption, "El Pozo") == 0 && reads == before + 1);
    puts("PASS: cached current and previous screen captions follow language/font changes");
}
'''
    compile_check(code)


if __name__ == '__main__':
    main()
