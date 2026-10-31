#!/usr/bin/env python3
"""Check the actual playBGM guard against seqPlay's loop policy on the host.

Usage: python3 tools/dev/playtest/music_continuity_host.py build/decomp-dev
This complements room crossings and sequencer traces in the emulator.
"""
import argparse
from pathlib import Path
import re
import subprocess
import tempfile


def function(source, name):
    matches = list(re.finditer(r'\b(?:void|int32_t) ' + name + r'\([^)]*\)(?!\s*;)[^{]*\{', source))
    if len(matches) != 1:
        raise ValueError(f'expected one definition of {name}, found {len(matches)}')
    match = matches[0]
    start = match.start()
    pos = match.end()
    depth = 1
    while depth:
        depth += (source[pos] == '{') - (source[pos] == '}')
        pos += 1
    return source[start:pos]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('tree', type=Path)
    args = parser.parse_args()
    script = (args.tree / 'src/main/script_interp.c').read_text()
    sound = (args.tree / 'src/main/sound.c').read_text()
    code = r'''
#include <stdint.h>
#include <assert.h>
#include <stdio.h>
#include <setjmp.h>
#define SSPLAY_PLAY 1
#define SSPLAY_INFINITY 0
#define PSTAT_245 245
#define SCRIPT_OP_SET_BGM 0x5d
#define MOD_DT_BGM_FROM 0
#define MOD_DT_BGM_TO 1
int16_t HOUR = 12, MOD_DAYTIME[] = {6, 21};
uint8_t pstats[256];
uint8_t plainHeader[] = {0x5d, 10, 0xfe};
uint8_t *header = plainHeader, *SCRIPT_POINTER;
int useEngineOverride, loadingMode;
uint8_t readPStat(uint8_t id) { return pstats[id]; }
void writePStat(uint8_t id, uint8_t value) { pstats[id] = value; }
void engineMusicOverride(uint8_t *, uint8_t *);
int16_t CURRENT_SEQ_FONT, CURRENT_SEQ_TRACK, SEQ_ACCESS_NUM;
uint8_t ACTIVE_BGM_FONT, ACTIVE_BGM_TRACK;
int stops, plays, loops, overrideFont = -1, overrideTrack;
/* Script entry scaffolding; the entry/reset decisions below come from C. */
static uint8_t modMapHeadBGM;
typedef struct { int smth[4]; } StackEntry;
uint16_t CURRENT_SCRIPT_ID, CURRENT_SCREEN_ID;
int MAIN_D_80134FEC;
jmp_buf SCRIPT_JMP_BUF;
int mapFont, loadingAccess;
void playBGM(uint8_t);
int32_t tickScript(void);
void callScriptSection(uint16_t a, int32_t b, int32_t c) { SCRIPT_POINTER = header; }
void returnFromScriptFile(void) {}
void skipOneReadTwoShort(uint16_t *a, uint16_t *b) { *a = 50; *b = 58; }
void pushScriptStack(StackEntry *entry) {}
void loadMap(uint16_t screen) { loadingAccess = SEQ_ACCESS_NUM; loadingMode = readPStat(PSTAT_245); }
void SsSeqSetVol(int a, int b, int c) {}
void SsSeqPlay(int a, int b, int c) { loops = c; }
void handleMusicOverride(uint8_t *font, uint8_t *track) {
    if (useEngineOverride) { engineMusicOverride(font, track); return; }
    if (overrideFont >= 0) *font = overrideFont;
    *track = overrideTrack;
}
void stopBGM(void) { stops++; CURRENT_SEQ_TRACK = -1; SEQ_ACCESS_NUM = -1; }
void resetBGM(void) { ACTIVE_BGM_FONT = 255; stopBGM(); }
int32_t playMusic(int32_t font, int32_t track) {
    plays++; CURRENT_SEQ_FONT = font; CURRENT_SEQ_TRACK = track; SEQ_ACCESS_NUM = 0;
    return 1;
}
'''
    code += function(script, 'handleMusicOverride').replace(
        'handleMusicOverride', 'engineMusicOverride', 1) + '\n'
    for source, names in ((sound, ('seqPlay',)), (script, (
            'playBGM', 'updateBGM', 'forceUpdateBGM', 'modHeaderKeepsMusic', 'runMapHeadScript', 'scriptInstructionFBtoFF'))):
        for name in names:
            code += function(source, name) + '\n'
    code += r'''
int32_t tickScript(void) {
    if (setjmp(SCRIPT_JMP_BUF) == 0) scriptInstructionFBtoFF(0xfb);
    if (SCRIPT_POINTER[0] == 0x1e) writePStat(PSTAT_245, SCRIPT_POINTER[3]);
    if (mapFont >= 0) playBGM(mapFont);
    return 1;
}
void checkHeader(uint8_t *bytes, int font, int track, int mode, int expected) {
    SCRIPT_POINTER = bytes;
    CURRENT_SEQ_FONT = font; CURRENT_SEQ_TRACK = track; SEQ_ACCESS_NUM = 0;
    writePStat(PSTAT_245, mode);
    assert(modHeaderKeepsMusic() == expected);
    assert(SCRIPT_POINTER == bytes);
    assert(readPStat(PSTAT_245) == mode);
}
int main(void) {
    int cases = 0;
    for (int font = 1; font < 255; font++) {
        for (int track = 0; track < 5; track++) {
            CURRENT_SEQ_FONT = font; CURRENT_SEQ_TRACK = track; SEQ_ACCESS_NUM = 0;
            seqPlay();
            int repeats = loops == SSPLAY_INFINITY;
            overrideTrack = track; stops = plays = 0;
            ACTIVE_BGM_FONT = ACTIVE_BGM_TRACK = 255;
            playBGM(font);
            assert(stops == !repeats && plays == !repeats);
            assert(ACTIVE_BGM_FONT == font && ACTIVE_BGM_TRACK == track);
            /* A stopped/closed sequence must restart, even with stale ids. */
            CURRENT_SEQ_FONT = font; CURRENT_SEQ_TRACK = track; SEQ_ACCESS_NUM = -1;
            stops = plays = 0; playBGM(font);
            assert(stops == 1 && plays == 1);
            /* A different font (battle/jukebox) must return to map music. */
            CURRENT_SEQ_FONT = font == 1 ? 2 : 1; CURRENT_SEQ_TRACK = track;
            SEQ_ACCESS_NUM = 0; stops = plays = 0; playBGM(font);
            assert(stops == 1 && plays == 1);
            /* Day/night variants must switch. */
            CURRENT_SEQ_FONT = font; CURRENT_SEQ_TRACK = (track + 1) % 5;
            stops = plays = 0; playBGM(font);
            assert(stops == 1 && plays == 1);
            cases += 4;
        }
    }
    /* Compare resolved font/variant, and update active state on the no-op. */
    overrideFont = 15; overrideTrack = 2;
    CURRENT_SEQ_FONT = 15; CURRENT_SEQ_TRACK = 2; SEQ_ACCESS_NUM = 0;
    stops = plays = 0; playBGM(22);
    assert(stops == 0 && plays == 0 && ACTIVE_BGM_FONT == 15 && ACTIVE_BGM_TRACK == 2);
    /* 0xff retains the explicit reset, before applying overrides. */
    playBGM(255);
    assert(stops == 1 && plays == 0 && ACTIVE_BGM_FONT == 255 && SEQ_ACCESS_NUM == -1);
    overrideFont = -1; overrideTrack = 0;
    CURRENT_SEQ_FONT = 10; CURRENT_SEQ_TRACK = 0; SEQ_ACCESS_NUM = 0;
    mapFont = 10; stops = plays = 0; runMapHeadScript(58);
    assert(loadingAccess == 0 && stops == 0 && plays == 0 && modMapHeadBGM == 0);
    /* No SET_BGM and an explicit 0xff must leave the new screen silent. */
    mapFont = -1; runMapHeadScript(58);
    assert(SEQ_ACCESS_NUM == -1 && ACTIVE_BGM_FONT == 255);
    CURRENT_SEQ_FONT = 10; CURRENT_SEQ_TRACK = 0; SEQ_ACCESS_NUM = 0;
    mapFont = 255; runMapHeadScript(58);
    assert(SEQ_ACCESS_NUM == -1 && ACTIVE_BGM_FONT == 255);
    /* Explicit script 0xfb outside normal map-header entry still stops. */
    CURRENT_SEQ_FONT = 10; CURRENT_SEQ_TRACK = 0; SEQ_ACCESS_NUM = 0;
    if (setjmp(SCRIPT_JMP_BUF) == 0) scriptInstructionFBtoFF(0xfb);
    assert(loadingAccess == -1 && ACTIVE_BGM_FONT == 255);
    playBGM(10);
    assert(CURRENT_SEQ_TRACK == 0 && SEQ_ACCESS_NUM == 0);
    /* Unchanged normal/forced update rules. */
    stops = plays = 0; updateBGM();
    assert(stops == 0 && plays == 0);
    overrideTrack = 1; updateBGM();
    assert(stops == 1 && plays == 1 && ACTIVE_BGM_TRACK == 1);
    forceUpdateBGM();
    assert(stops == 2 && plays == 2);
    /* Extracted peeker uses the real engine override, including hour and mode. */
    uint8_t same[] = {0x1e, 0, 245, 1, 0x5d, 10, 0xfe};
    uint8_t different[] = {0x5d, 11, 0xfe};
    uint8_t variant[] = {0x1e, 0, 245, 0, 0x5d, 1, 0xfe};
    uint8_t alias[] = {0x1e, 0, 245, 4, 0x5d, 22, 0xfe};
    uint8_t ended[] = {0xfe};
    uint8_t silent[] = {0x1e, 0, 245, 0, 0x5d, 255, 0xfe};
    uint8_t branch19[] = {0x19, 0, 0, 0, 0x5d, 11, 0xfe};
    uint8_t branch25[] = {0x25, 0, 0, 0, 0x5d, 11, 0xfe};
    useEngineOverride = 1; HOUR = 22;
    checkHeader(same, 10, 0, 0, 1);
    checkHeader(different, 10, 0, 1, 0);
    checkHeader(variant, 1, 0, 1, 0);
    checkHeader(variant, 1, 1, 1, 1);
    checkHeader(alias, 15, 2, 0, 1);
    checkHeader(ended, 10, 0, 1, 0);
    checkHeader(silent, 10, 0, 1, 0);
    checkHeader(branch19, 10, 0, 1, 1);
    checkHeader(branch25, 10, 0, 1, 1);
    /* Exercise the actual first-FB handler: inspect the state at loadMap. */
    header = same; mapFont = 10;
    CURRENT_SEQ_FONT = 10; CURRENT_SEQ_TRACK = 0; SEQ_ACCESS_NUM = 0;
    writePStat(PSTAT_245, 0); stops = plays = 0; runMapHeadScript(58);
    assert(loadingAccess == 0 && loadingMode == 0 && stops == 0 && plays == 0);
    header = different; mapFont = 11;
    runMapHeadScript(58);
    assert(loadingAccess == -1 && CURRENT_SEQ_FONT == 11);
    header = variant; mapFont = 1;
    CURRENT_SEQ_FONT = 1; CURRENT_SEQ_TRACK = 0; SEQ_ACCESS_NUM = 0;
    writePStat(PSTAT_245, 1); runMapHeadScript(58);
    assert(loadingAccess == -1 && loadingMode == 1 && CURRENT_SEQ_TRACK == 1);
    header = ended; mapFont = -1; runMapHeadScript(58);
    assert(loadingAccess == -1 && SEQ_ACCESS_NUM == -1);
    header = silent; mapFont = 255; SEQ_ACCESS_NUM = 0; runMapHeadScript(58);
    assert(loadingAccess == -1 && SEQ_ACCESS_NUM == -1);
    header = branch19; mapFont = 10;
    CURRENT_SEQ_FONT = 10; CURRENT_SEQ_TRACK = 0; SEQ_ACCESS_NUM = 0;
    writePStat(PSTAT_245, 1); stops = plays = 0; runMapHeadScript(58);
    assert(loadingAccess == 0 && stops == 0 && plays == 0);
    printf("ok: %d music-state cases, nine header peeks, pre-load stops, mode restoration and updates\n", cases);
}
'''
    with tempfile.TemporaryDirectory(prefix='music-host-') as temp:
        source = Path(temp) / 'music.c'
        binary = Path(temp) / 'music'
        source.write_text(code)
        subprocess.run(['cc', '-std=c99', '-Werror', str(source), '-o', str(binary)], check=True)
        subprocess.run([str(binary)], check=True)


if __name__ == '__main__':
    main()
