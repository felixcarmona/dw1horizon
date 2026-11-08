#!/usr/bin/env python3
"""Execute the actual inline save C helpers with adversarial payloads and IO.

The host shim keeps the PS1 byte layout and 128-byte card frame writes. Every
interruption of an existing save must retain a complete old or new copy.
"""
from pathlib import Path
import re
import subprocess
import sys
import tempfile


def function(source, name):
    match = re.search(r'(?:static )?(?:int32_t|long|void|uint8_t \*) '+name+r'\([^;]*?\)\n\{', source)
    if not match: raise ValueError(name)
    at = source.index('{', match.start()); end = at+1; depth = 1
    while depth:
        depth += (source[end] == '{') - (source[end] == '}'); end += 1
    return source[match.start():end]


HEADER = r'''
#include <stdint.h>
#include <stddef.h>
#include <string.h>
#include <assert.h>
#include <stdio.h>
#define SAVE_INLINE_VERSION 5
#define SAVE_INLINE_BYTES 1120
#define SAVE_FORMAT_VERSION 4
#define SAVE_LEGACY_VERSION 2
#define SAVE_V1_BYTES 8192
#define SAVE_V2_BYTES 16384
#define SAVE_EXT_BYTES 4096
#define SAVE_IO_ERROR 1
#define SAVE_IO_MESSAGES 11
#define SAVE_TAG_END 0
#define NUM_DIGIMON 1024
#define NUM_ORIGINAL_DIGIMON 180
#define NUM_ORIGINAL_SCREENS 255
#define NUM_ITEMS 128
typedef long MemCardSyncWord;
typedef struct { uint8_t used[36], unk24[28]; } RegisteredDigimon;
typedef struct { uint8_t fields[0x4fc]; int32_t checksum; RegisteredDigimon battleRegistrationData[40]; } SavegamePayload;
typedef struct { uint8_t id[3], blockNumber, head[508]; SavegamePayload saves[2]; } SaveFile;
typedef struct { char magic[4]; uint16_t version,size; int32_t v1Checksum; } SaveExtHead;
static SaveFile SAVE_FILE;
static int SAVE_FILE_BYTES, MEMORY_CARD_ID;
static char SAVE_FILE_NAME[20];
static long SAVE_IO_FAILED;
static uint8_t extensions[16384], card[16384];
#define SAVE_EXT_ADDR extensions
static uint8_t *saveExtOf(int copy) {return extensions+copy*4096;}
static int saveExtSize(void) {return 4096;}
static int saveLayoutVersion(void) {return 4;}
static int isLegacyExtensionValid(int copy) {return 0;}
static int createByteSum(uint8_t *p,int n) {int s=0;while(n--)s+=*p++;return s;}
static int createSavegameChecksum(int copy) {uint8_t *p=(uint8_t*)&SAVE_FILE.saves[copy];return createByteSum(p,0x4e4)+createByteSum(p+0x500,0xa00);}
static int getSaveVersion(SavegamePayload *p) {return p->fields[0x4e8];}
static int frames_left=-1, io_result, writes, fail_read, extension_reads;
static int MemCardWriteFile(int c,char *name,void *p,int offset,int size) {
 writes++; io_result=0;
 for(int i=0;i<size;i+=128) {
  if(frames_left==0) {io_result=1;break;}
  memcpy(card+offset+i,(uint8_t*)p+i,128);
  if(frames_left>0)frames_left--;
 }
 return 1;
}
static int MemCardReadFile(int c,char *name,void *p,int offset,int size) {
 if(offset>=8192)extension_reads++;
 if(fail_read==1 || (fail_read==2 && offset>=8192))return 0;
 memcpy(p,card+offset,size);io_result=0;return 1;
}
static int MemCardSync(int m,long *cmd,long *result) {*result=io_result;return 1;}
'''
CASES = r'''
static void prepare(int marker) {
 memset(&SAVE_FILE,0,sizeof(SAVE_FILE));
 for(int k=0;k<2;k++) {
  SavegamePayload *p=&SAVE_FILE.saves[k];
  p->fields[0]=marker;memcpy(p->fields+0x4e4,"DW2",4);p->fields[0x4e8]=5;
  for(int j=0;j<40;j++)memset(p->battleRegistrationData[j].used,j+1,36);
  uint8_t *e=saveExtOf(k);memset(e,0,4096);
  SaveExtHead *h=(SaveExtHead*)e;memcpy(h->magic,"DW4E",4);h->version=4;h->size=1120;
  /* Include arbitrary, incompressible bytes and a record spanning padding slots. */
  e[12]=7;e[14]=0x20;e[15]=3;
  for(int i=16;i<816;i++)e[i]=(i*37+marker)&255;
  h->v1Checksum=inlineBaseChecksum(k);
  *(int32_t*)(e+1116)=createByteSum(e,1116);
  inlineExtension(k,1);p->checksum=~createSavegameChecksum(k);
 }
}
int main(int argc, char **argv) {
 assert(sizeof(SAVE_FILE)==8192);
 SAVE_FILE_BYTES=8192;
 prepare(1);assert(isExtensionValid(0)&&isSaveCopyValid(1));
 for(int i=0;i<40;i++) for(int j=0;j<36;j++) assert(SAVE_FILE.saves[0].battleRegistrationData[i].used[j]==i+1);
 frames_left=-1;assert(writeSaveFile()==1&&!SAVE_IO_FAILED&&writes==2);
 uint8_t old[16384];memcpy(old,card,sizeof(card));
 for(int cut=0;cut<=64;cut++) {
  memcpy(card,old,sizeof(card));prepare(2);frames_left=cut;
  writeSaveFile();frames_left=-1;saveFileStart(0);
  int k=pickSaveCopy();assert(k>=0);
  assert(SAVE_FILE.saves[k].fields[0]==1||SAVE_FILE.saves[k].fields[0]==2);
  assert(isExtensionValid(k));
 }
 prepare(2);inlineExtension(0,0);assert(isTaggedExtensionValid(0));
 saveExtOf(0)[100]^=1;assert(!isTaggedExtensionValid(0));
 prepare(2);SAVE_FILE.saves[0].fields[0]^=1;assert(!isSaveCopyValid(0));
 prepare(2);SAVE_FILE.saves[0].battleRegistrationData[3].unk24[2]^=1;
 inlineExtension(0,0);assert(!isSaveCopyValid(0));assert(pickSaveCopy()==1);
 /* Existing full two-block cards need no allocations, and block 2 is untouched. */
 SAVE_FILE_BYTES=16384;memset(card+8192,0xA5,8192);prepare(3);frames_left=-1;
 writeSaveFile();for(int i=8192;i<16384;i++)assert(card[i]==0xA5);
 fail_read=2;extension_reads=0;
 saveFileStart(0);assert(!SAVE_IO_FAILED&&pickSaveCopy()==0&&isExtensionValid(1));
 assert(extension_reads==0);
 /* A failed legacy extension read cannot hide the intact inline backup. */
 card[0x200+0x4e8]=4;
 saveFileStart(0);assert(!SAVE_IO_FAILED&&pickSaveCopy()==1);
 assert(extension_reads==1);
 /* Failure to read block 1 must never accept stale resident data. */
 fail_read=1;saveFileStart(0);assert(SAVE_IO_FAILED==1);
 fail_read=0;prepare(3);writeSaveFile();
 if(argc>1) {FILE *f=fopen(argv[1],"wb");assert(f);assert(fwrite(card,1,8192,f)==8192);fclose(f);}
 return 0;
}
'''


def main():
    source = (Path(sys.argv[1])/'src/main/main_menu.c').read_text()
    names = ['inlineBaseChecksum', 'inlineExtension', 'isTaggedVersion', 'areRecordsWellFormed',
             'isTaggedExtensionValid', 'isExtensionValid', 'isSaveCopyValid', 'saveFileStart', 'writeSaveFile', 'pickSaveCopy']
    code = HEADER + '\n'.join(function(source, n) for n in names) + CASES
    with tempfile.TemporaryDirectory(prefix='inline-save-') as tmp:
        p=Path(tmp);(p/'test.c').write_text(code)
        subprocess.run(['cc','-std=c99','-O2','-Wall','-Werror',str(p/'test.c'),'-o',str(p/'test')],check=True)
        subprocess.run([str(p/'test'),str(p/'save.bin')],check=True)
        sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
        from tools.dev import memory_card as mcd
        data = (p/'save.bin').read_bytes()
        decoded = mcd.decode_save(data)
        assert all(decoded[f'ext{k}']['checksum_ok'] and decoded[f'ext{k}']['matches_v1'] for k in range(2))
        class FileCard:
            def __init__(self): self.data = bytearray(data)
            def read(self, name): return bytes(self.data)
            def write(self, name, offset, value): self.data[offset:offset+len(value)] = value
        card = FileCard()
        for k in range(2):
            e = mcd.extension(card.read('test'), k)
            records = [(tag, bytes([7])*len(value)) for tag,value in mcd.parse_records(e)]
            mcd.write_extension(card,'test',k,mcd.build_extension(e,records,len(e)))
        decoded = mcd.decode_save(card.read('test'))
        assert all(decoded[f'ext{k}']['checksum_ok'] and decoded[f'ext{k}']['matches_v1'] and decoded[f'copy{k}']['refuses_original'] for k in range(2))
    print('PASS: inline checksums, registration preservation, corruption, all 65 frame cuts, two-block overwrite')


if __name__ == '__main__': main()
