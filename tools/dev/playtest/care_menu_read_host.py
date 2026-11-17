#!/usr/bin/env python3
"""Compile care opening with the real file queue; mock only CD I/O and UI.

python3 tools/dev/playtest/care_menu_read_host.py build/decomp-dev
A queued/reading flag is 1 until completion. MENU code must never run early.
"""
from pathlib import Path
import re
import subprocess
import sys
import tempfile

from quick_care_host import function


def main():
    root = Path(sys.argv[1] if len(sys.argv) > 1 else 'build/decomp-dev')
    feed = (root / 'src/main/mod_feed.c').read_text()
    feed = re.sub(r'\bfeedMenuRead\b', 'feedMenuReading', feed)
    queue = (root / 'src/main/file_queue.c').read_text()
    open_fn = function(feed, 'static int32_t feedOpen(void)\n{')
    assert 'loadMenuOverlay' not in open_fn and 'readFile' not in open_fn
    a = feed.index('\tcase FEED_QUEUING:')
    cases = feed[a:feed.index('\tcase FEED_OPENING:', a)]
    # Keep the production queue's flag writes and completion ordering in the test.
    queue_data = queue[queue.index('#define FILE_QUEUE_SIZE'):queue.index('void initFileReadQueueTable(void);')]
    queue_code = '\n'.join(function(queue, signature) for signature in (
        'void initFileReadQueueTable(void)\n{',
        'int32_t isFileReadQueueIdle(void)\n{',
        'void tickFileReadQueue(int32_t unused)\n{',
        'int32_t addFileReadRequest(char *path, uint8_t *buffer, uint8_t *isRunning,\n'))
    prefix = r'''
#include <stdint.h>
#include <assert.h>
#include <stdio.h>
#include <string.h>
#include <stddef.h>
typedef unsigned char u_char;
typedef unsigned long u_long;
typedef struct { uint8_t pos[4]; } CdlLOC;
typedef struct { CdlLOC pos; uint32_t size; } CdlFILE;
typedef int32_t (*FileRequestCallback)(void *);
#define CdlModeSpeed 0
#define CdlSetloc 0
#define MENU_REL 17
enum { FEED_OPENING, FEED_OPEN, FEED_CLOSING, FEED_GIVING, FEED_WATCHING, FEED_QUEUING, FEED_LOADING };
static int32_t feedState = -1, count = 1, entered, shown, queued, tfsBusy;
static int diskDone, menuAvailable, reads;
static uint8_t feedMenuReading, *readFlag, menuBuffer[2048];
static int tfsStreamBusy(void) { return tfsBusy; }
static void tfsStreamCheckTarget(void *buffer, int32_t size) { (void)buffer; (void)size; assert(!tfsBusy); }
static void *CdSearchFile(CdlFILE *file, char *path) { (void)path; file->size=2048; return file; }
static int CdControl(int op, u_char *p, void *r) { (void)op; (void)p; (void)r; return 1; }
static int CdRead(int sectors, u_long *buffer, int mode) { (void)buffer; (void)mode; assert(sectors==1); reads++; return 1; }
static int CdReadSync(int mode, void *r) { (void)mode; (void)r; if (diskDone) menuAvailable=1; return !diskDone; }
'''
    ui = r'''
static int feedCollect(int needsOnly) { (void)needsOnly; return count; }
static void feedEnterMenu(void) { entered++; }
static void feedShow(void) { assert(menuAvailable); shown++; feedState = FEED_OPENING; }
static void loadDynamicLibrary(int lib, uint8_t *flag, int async, void *cb, void *param) {
    CdlLOC loc={{0}};
    assert(lib==MENU_REL && flag==&feedMenuReading && async==1 && cb==NULL && param==NULL);
    queued++; readFlag=flag;
    assert(addFileReadRequest("MENU_REL.BIN", menuBuffer, flag, NULL, NULL, &loc, sizeof(menuBuffer))>=0);
}
'''
    harness = '\nstatic void step(void) {\n\tswitch (feedState) {\n' + cases + '\tdefault: break;\n\t}\n}\n'
    tests = r'''
int main(void) {
    initFileReadQueueTable();
    count=0; assert(!feedOpen() && !entered && feedState==-1);
    count=1;
    for (int attempt=0; attempt<2; attempt++) {
        diskDone=menuAvailable=0;
        assert(feedOpen() && feedState==FEED_QUEUING);
        tfsBusy=1; step(); assert(queued==attempt && feedState==FEED_QUEUING);
        tfsBusy=0;
        /* A request ahead of MENU must drain first. */
        if (attempt==0) {
            CdlLOC loc={{0}};
            addFileReadRequest("ahead",menuBuffer,NULL,NULL,NULL,&loc,2048);
            step(); assert(!queued && feedState==FEED_QUEUING);
            tickFileReadQueue(0); diskDone=1; tickFileReadQueue(0); tickFileReadQueue(0);
            diskDone=menuAvailable=0;
        }
        step(); assert(queued==attempt+1 && feedState==FEED_LOADING && *readFlag==1);
        for (int i=0;i<5;i++) { step(); assert(shown==attempt && feedState==FEED_LOADING); }
        tickFileReadQueue(0); /* CdRead starts, but no bytes are ready */
        for (int i=0;i<5;i++) { tickFileReadQueue(0); step(); assert(shown==attempt && *readFlag==1); }
        diskDone=1; tickFileReadQueue(0); assert(*readFlag==0);
        step(); assert(shown==attempt+1 && feedState==FEED_OPENING);
        step(); assert(shown==attempt+1); /* no double opening */
        tickFileReadQueue(0); assert(isFileReadQueueIdle());
    }
    assert(reads==3);
    puts("care waits for real queue completion, including delayed reads and reopening");
    return 0;
}
'''
    with tempfile.TemporaryDirectory(prefix='care-read-host-') as temp:
        source = Path(temp) / 'care.c'
        exe = Path(temp) / 'care'
        source.write_text(prefix + queue_data + queue_code + ui + open_fn + harness + tests)
        subprocess.run(['cc', '-std=c99', '-Wall', '-Wextra', '-Werror', '-Wno-unused-parameter',
                        '-Wno-unused-but-set-variable', '-Wno-unused-variable', str(source), '-o', str(exe)], check=True)
        subprocess.run([str(exe)], check=True)


if __name__ == '__main__':
    main()
