"""Compile production card operations on the host, including save record bodies.

Usage: python3 tools/dev/playtest/cards_host.py build/decomp-int
No emulator, source disc artwork, or generated game data is required.
"""
from pathlib import Path
import json
import re
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from tools.dev.playtest.quick_care_host import function
from tools.test_cards import authored, dummy_archive
from tools import cards


def main():
    tree = Path(sys.argv[1] if len(sys.argv) > 1 else 'build/decomp-int')
    common = (tree / 'src/main/script_common.c').read_text()
    interp = (tree / 'src/main/script_interp.c').read_text()
    menu = (tree / 'src/main/game_menu.c').read_text()
    assert 'return modLoadCardImage(id, TEXTURE_BUFFER);' in function(menu, 'int32_t loadCardImage(int32_t id)\n')
    save = (tree / 'src/main/main_menu.c').read_text()
    shop = (tree / 'src/shop/script_menu.c').read_text()
    assert 'modLoadCardImage(PACK_ART,' in function(shop, 'static void tickPackResults(void)\n')
    tamer = (tree / 'src/main/tamer.c').read_text()
    item_type = re.search(r'typedef struct \{\n\tuint8_t \*buf;\n\tint32_t isOpen;.*?\} ItemMenuBox;',
                          (tree / 'include/dw/script.h').read_text(), re.S).group()
    production = '\n'.join(function(text, signature + '\n') for text, signature in [
        (common, 'int32_t modCardIsReal(int32_t id)'),
        (interp, 'uint8_t getCardAmount(int32_t cardId)'),
        (interp, 'int32_t setCardAmount(int32_t cardId, int32_t value)'),
        (common, 'int32_t modLoadCardImage(int32_t id, void *buffer)'),
        (common, 'int32_t modCardRowId(ItemMenuBox *box, int32_t row)'),
        (menu, 'static __attribute__((noinline)) int32_t cardAlbumLimit(void)'),
        (menu, 'static __attribute__((noinline)) int32_t cardAlbumTotal(void)'),
        (menu, 'static __attribute__((noinline)) void cardAlbumScrollBar(int32_t rows)'),
        (menu, 'static int32_t cardAlbumStep(int32_t id, int32_t step, int32_t limit)'),
        (menu, 'int32_t modCardMove(int32_t id, int32_t input)'),
        (menu, 'int32_t modCardTop(int32_t id, int32_t top)'),
        (shop, 'uint16_t rollCard(void)'),
        (shop, 'int32_t shopFillSellCardList(void)'),
        (shop, 'int32_t hasAnyCardToBuy(void)'),
        (common, 'void dailyPStatTrigger(void)'),
        (shop, 'int32_t createMeritCardTradeDialogue(void)'),
        (common, 'void allocateItemMenuBox(ItemMenuBox **box, int32_t bufSize, uint8_t rows, uint8_t x, uint8_t y, uint8_t w, uint8_t h)'),
        (save, 'static uint8_t *putRecord(uint8_t *p, int32_t tag, void *data, int32_t len)'),
        (save, 'static void inlineExtension(int32_t copy, int32_t pack)'),
    ])
    # Run the actual album medal branch; the other medal kinds need game state.
    medal = tamer.split('case MOD_MEDAL_ALL_CARDS:', 1)[1].split('case MOD_MEDAL_ALL_MOVES:', 1)[0]
    production += '\nint album(void) { int i; struct { int a; } value={-1}, *m=&value;' + medal + '}\n'
    # The record dispatcher is shared with many unrelated records. Retain its
    # loop and the two production card cases, excluding unrelated game globals.
    dispatch = function(save, 'static void applyRecords(uint8_t *e)\n')
    start = dispatch.index('\t\tcase SAVE_TAG_CARD_COUNTS:')
    end = dispatch.index('\t\tcase SAVE_TAG_GROUND_PICKUP_BITS:', start)
    production += dispatch[:dispatch.index('\t\tcase SAVE_TAG_SCREENS:')] + dispatch[start:end] + '\t\t}\n\t}\n}\n'
    header = (tree / 'include/dw/save_tags.h').read_text()
    tags = '\n'.join(line for line in header.splitlines() if line.startswith('#define SAVE_TAG_'))
    tags += '\n' + '\n'.join(line for line in (tree / 'include/dw/mod_rules.h').read_text().splitlines()
                             if line.startswith('#define MOD_DAILY'))
    writer = '\n'.join(line for line in save.splitlines() if 'p = putRecord(p, SAVE_TAG_CARD_' in line)
    production += '\nstatic void writeCards(uint8_t *e) { uint8_t *p=e+12; ' + writer + '\nputRecord(p,0,0,0); }\n'
    pack = function(shop, 'static void openPackResults(void)\n')
    pack = pack[:pack.index('\t/* the head:')]
    pack = pack.replace('static void openPackResults(void)', 'static int packBookkeeping(void)')
    pack = pack.replace('\tRECT rect;\n\tRECT origin;\n', '')
    production += pack + '\treturn fresh;\n}\n'
    prefix = r'''
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <assert.h>
#define NUM_CARDS 512
#define CARD_EXTRA_BYTES 223
#define CARD_NONE 65535
#define MOD_ECON_MACHINE_CUT0 0
#define MOD_ECON_CARD_CUT0 0
#define TRIGGER_CARD_MACHINE 0
static int32_t MOD_ECON[4]={1,5,20,50};
static int rarityRoll, pickLast;
static int MOD_OPT_NEW_CARDS=1;
static int16_t CARD_TOP_ROW;
static int boxCalls, barY, barH;
static void renderBox(int16_t x,int16_t y,int16_t w,int16_t h,
                      uint8_t r,uint8_t g,uint8_t b,uint8_t flags,int32_t otz) {
 assert(x==135 && w==3 && flags==0 && otz==5);
 if(boxCalls++==0) {
  assert(r==120 && g==220 && b==255);barY=y;barH=h;
 } else {
  assert(boxCalls==2 && y==-63 && h==138 && r==20 && g==30 && b==38);
 }
}

static int randomLimit(int n) { assert(n>0); if(n==100)return rarityRoll; return pickLast?n-1:0; }
static int machineMode=1;
static int isTriggerSet(int n) { (void)n; return machineMode; }
typedef struct { uint16_t digimonId; uint8_t spriteId,meritValue; } CardData;
static CardData CARD_DATA[512];
static int CARD_PRICES[6]={5000,1500,500,100,50,0}, MONEY=99999;
static uint8_t MOD_CARD_REAL[64], MOD_CARD_EXTRA[223];
static uint16_t MOD_CARD_ART[64];
static uint16_t MOD_CARD_STOCK[6];
typedef struct { uint8_t cards[33],smth[212]; } ScriptState;
static ScriptState script, *SCRIPT_STATE_PTR=&script;
typedef struct { int16_t x,y,w,h; } RECT;
__ITEM_MENU_BOX_TYPE__
static void setWH(RECT *rect,int w,int h) { rect->w=w;rect->h=h; }
static unsigned arenaUsed, allocationCount, sizes[4];
static void *allocations[4];
static void *allocateArray(uint32_t size) {
 assert(allocationCount<4);void *p=calloc(1,size);assert(p);
 allocations[allocationCount]=p;sizes[allocationCount++]=(size+3)&~3u;
 arenaUsed+=((size+3)&~3u)+4;assert(arenaUsed<=0x7800);return p;
}
static void freeArray(uint32_t *p) {
 assert(allocationCount && allocations[allocationCount-1]==p);
 arenaUsed-=sizes[--allocationCount]+4;free(p);
}
static uint8_t rowData[513*3];
static ItemMenuBox box={.buf=rowData}, *ITEM_MENU_LEFT=&box;
static uint16_t SHOP_ITEM_TYPE;
static int SHOP_ITEM_PRICE, MAX_SHOP_AMOUNT, MERIT;
static int SHOP_AMOUNT;
#define MOD_ECON_MERIT_CAP 0
#define MOD_ECON_CARD_MAX 1
static int econAmt(int n) { assert(n==MOD_ECON_CARD_MAX);return 9; }
static int econCap(int a,int b) { (void)a;(void)b;return 9999; }
static ItemMenuBox *getItemMenuFromType(void) { return &box; }
static void openAmountBox(int n) { assert(n==3); }
static void playSound(int a,int b) { (void)a;(void)b; }
static int16_t MOD_DAILY[7]={6,511,4,-1,-1,-1,-1};
#define MOJYA_DAILY_COUNT 0
#define MOJYA_DAILY_FIRST 0
static void unsetTrigger(int n) { (void)n; }
static void modForgetGroundPicked(void) {}
static int readPStat(int n) { (void)n;return 255; }
static void writePStat(int n,int v) { (void)n;(void)v; }
typedef struct { uint8_t magic[4]; uint16_t version,size; int32_t link; } SaveExtHead;
static struct { struct { struct { uint8_t unk24[28]; } battleRegistrationData[40]; } saves[2]; } SAVE_FILE;
static uint8_t ext[2][1120];
static uint8_t *saveExtOf(int copy) { return ext[copy]; }
static int readRecord16(uint8_t *p) { return p[0]|p[1]<<8; }
static const char *archive;
static int lastArchive, lastOffset;
static int loadStackedTIMEntry(char *path,void *buf,int off,int sectors) {
 assert(sectors==14);
 lastArchive=strstr(path,"CARD2.ALL")!=NULL;lastOffset=off;
 if(!lastArchive){assert(strstr(path,"CARD.ALL"));memset(buf,0,sectors*2048);((uint8_t*)buf)[22]=off/14;return 1;}
 FILE *f=fopen(archive,"rb"); assert(f); assert(!fseek(f,off*2048L,SEEK_SET));
 assert(fread(buf,1,sectors*2048,f)==(size_t)sectors*2048); fclose(f); return 1;
}
'''.replace('__ITEM_MENU_BOX_TYPE__', item_type)
    tests = r'''
static void checkAlbumBar(int rows,int top) {
 CARD_TOP_ROW=top;boxCalls=0;cardAlbumScrollBar(rows);
 if(rows<=6){assert(!boxCalls);return;}
 assert(boxCalls==2 && barH>0 && barY>=-63 && barY+barH<=75);
 if(top==0)assert(barY==-63);
 if(top==rows-6)assert(barY+barH==75);
}
int main(int argc,char **argv) {
 assert(argc==6); archive=argv[1];
 FILE *table=fopen(argv[2],"rb");assert(table);assert(fread(CARD_DATA,4,512,table)==512);fclose(table);
 table=fopen(argv[3],"rb");assert(table);assert(fread(MOD_CARD_REAL,1,64,table)==64);fclose(table);
 table=fopen(argv[4],"rb");assert(table);assert(fread(MOD_CARD_ART,2,64,table)==64);fclose(table);
 assert(CARD_DATA[511].digimonId==300);
 for(int i=-2;i<514;i++){ setCardAmount(i,9); assert(getCardAmount(i)==(modCardIsReal(i)?9:0)); }
 setCardAmount(256,42); assert(getCardAmount(256)==9);
 setCardAmount(256,-1); assert(getCardAmount(256)==0);setCardAmount(256,9);
 assert(album());setCardAmount(511,0);assert(!album());setCardAmount(511,9);
 assert(cardAlbumTotal()==511 && cardAlbumLimit()==512);
 for(int rows=6;rows<=47;rows++)for(int top=0;top<=rows-6;top++)checkAlbumBar(rows,top);
 int id=0,top=0;
 for(int n=0;n<46;n++){id=modCardMove(id,0x4000);top=modCardTop(id,top);}
 for(int n=0;n<5;n++){id=modCardMove(id,0x2000);top=modCardTop(id,top);}
 assert(id==511 && top==41);assert(modCardMove(id,0x4000)==511);assert(modCardMove(id,0x2000)==511);
 for(int i=0;i<512;i++)for(int k=0;k<4;k++){
  int move=modCardMove(i,(int[]){0x8000,0x2000,0x1000,0x4000}[k]);
  int row=modCardTop(move,top);assert(move>=0&&move<512&&move/11>=row&&move/11<row+6);
 }
 pickLast=1;
 for(int r=0;r<5;r++){rarityRoll=(int[]){0,1,5,20,50}[r];int card=rollCard();assert(card>=66 && CARD_DATA[card].spriteId==r);}
 assert(shopFillSellCardList() && box.itemCount==510);
 assert(modCardRowId(&box,253)==255 && modCardRowId(&box,254)==256);
 assert(modCardRowId(&box,509)==511 && modCardRowId(&box,510)==65535);
 for(int i=0;i<510;i++) {
  box.topRow=i;box.cursor=0;assert(createMeritCardTradeDialogue());
  assert(SHOP_ITEM_TYPE==modCardRowId(&box,i) && SHOP_ITEM_PRICE==CARD_DATA[SHOP_ITEM_TYPE].meritValue && MAX_SHOP_AMOUNT==9);
 }
 dailyPStatTrigger();
 for(int i=0;i<6;i++) {assert(MOD_CARD_STOCK[i]==511-i);assert(SCRIPT_STATE_PTR->smth[i]==255);}
 MOD_DAILY[1]=2;dailyPStatTrigger();assert(MOD_CARD_STOCK[0]==2 && MOD_CARD_STOCK[1]==1 && MOD_CARD_STOCK[2]==65535);
 for(machineMode=0;machineMode<2;machineMode++)for(SHOP_AMOUNT=1;SHOP_AMOUNT<=99;SHOP_AMOUNT+=98) {
  assert(packBookkeeping()==0 && ITEM_MENU_LEFT->itemCount==1);
  assert(modCardRowId(ITEM_MENU_LEFT,0)>=66 && arenaUsed<=2048);
  /* Every byte of the widened struct must belong to its own allocation. */
  memset(ITEM_MENU_LEFT->itemRow,0x99,sizeof(ITEM_MENU_LEFT->itemRow));
  freeArray((uint32_t*)ITEM_MENU_LEFT->buf);freeArray((uint32_t*)ITEM_MENU_LEFT);
  ITEM_MENU_LEFT=&box;assert(arenaUsed==0);
 }
 for(int i=0;i<6;i++)MOD_CARD_STOCK[i]=(uint16_t[]){66,255,256,511,1,65535}[i];
 memset(ext,0,sizeof(ext));writeCards(ext[0]);inlineExtension(0,1);
 memset(ext[0],0,1120);inlineExtension(0,0);
 memset(MOD_CARD_EXTRA,0,223);memset(MOD_CARD_STOCK,0,12);applyRecords(ext[0]);
 for(int i=66;i<512;i++)assert(getCardAmount(i)==9);
 assert(MOD_CARD_STOCK[1]==255 && MOD_CARD_STOCK[2]==256 && MOD_CARD_STOCK[3]==511 && MOD_CARD_STOCK[5]==65535);
 /* OFF hides new counts and pre-existing stock, without changing saved bytes. */
 setCardAmount(510,0);
 uint8_t kept[223];memcpy(kept,MOD_CARD_EXTRA,223);
 MOD_OPT_NEW_CARDS=0;
 assert(!getCardAmount(66) && !getCardAmount(255) && !getCardAmount(256) && !getCardAmount(511));
 setCardAmount(511,0);assert(!memcmp(kept,MOD_CARD_EXTRA,223));
 assert(album()); /* All originals suffice even while a new card is missing. */
 assert(shopFillSellCardList() && box.itemCount==64);
 for(int i=0;i<64;i++)assert(modCardRowId(&box,i)==i+1);
 assert(hasAnyCardToBuy());
 for(int i=0;i<6;i++)assert(modCardRowId(&box,i)==(i==4?1:CARD_NONE));
 assert(MOD_CARD_STOCK[0]==66 && MOD_CARD_STOCK[3]==511);
 /* Saving, reloading and saving again while OFF preserves extra counts and stock. */
 memset(ext,0,sizeof(ext));writeCards(ext[0]);
 memset(MOD_CARD_EXTRA,0,223);memset(MOD_CARD_STOCK,0,12);applyRecords(ext[0]);
 assert(!memcmp(kept,MOD_CARD_EXTRA,223) && MOD_CARD_STOCK[3]==511);
 writeCards(ext[0]);
 for(machineMode=0;machineMode<2;machineMode++)for(int r=0;r<5;r++) {
  rarityRoll=(int[]){0,1,5,20,50}[r];int card=rollCard();assert(card>=1 && card<=64);
 }
 MOD_DAILY[1]=511;dailyPStatTrigger();
 for(int i=0;i<6;i++)assert(MOD_CARD_STOCK[i]>=1 && MOD_CARD_STOCK[i]<=64);
 id=0;top=0;
 for(int n=0;n<20;n++){id=modCardMove(id,0x4000);top=modCardTop(id,top);}
 for(int n=0;n<20;n++)id=modCardMove(id,0x2000);
 assert(id==65 && top==0 && modCardMove(65,0x4000)==65);
 assert(cardAlbumTotal()==65 && cardAlbumLimit()==66);checkAlbumBar(6,0);
 MOD_OPT_NEW_CARDS=1;assert(getCardAmount(511)==9 && !getCardAmount(510));
 assert(!album());setCardAmount(510,9);
 setCardAmount(511,0);assert(!album());setCardAmount(511,9);
 /* Absent and short records retain zero defaults, with no old-save migration. */
 memset(MOD_CARD_EXTRA,0,223);memset(ext,0,sizeof(ext));applyRecords(ext[0]);assert(!getCardAmount(511));
 uint8_t *p=putRecord(ext[0]+12,SAVE_TAG_CARD_COUNTS,(uint8_t[]){0x91},1);putRecord(p,0,0,0);applyRecords(ext[0]);
 assert(getCardAmount(66)==1 && getCardAmount(67)==9 && !getCardAmount(511));
 uint8_t art[14*2048];
 for(int n=66;n<512;n++){assert(modLoadCardImage(n,art));assert((art[22]|art[23]<<8)==n-65);assert(art[544]==1);}
 /* Real JSON mappings use the same shared loader as viewer, shop and pack results. */
 for(int enabled=0;enabled<2;enabled++){
  MOD_OPT_NEW_CARDS=enabled;
  for(int n=0;n<66;n++){
   int entry=-1;
   if(n>=1 && n<=64)entry=MOD_CARD_ART[n-1]==65535?-1:MOD_CARD_ART[n-1];
   assert(modLoadCardImage(n,art));
   assert(lastArchive==(enabled && entry>=0));
   assert(lastOffset==(enabled && entry>=0?entry:n)*14);
   assert((art[22]|art[23]<<8)==(enabled && entry>=0?entry+1:n));
  }
 }
 assert(!modLoadCardImage(-1,art) && !modLoadCardImage(512,art));
 MOD_OPT_NEW_CARDS=1;
 memset(MOD_CARD_REAL+9,0,55);MOD_CARD_REAL[8]=1;assert(album()); /* Unassigned capacity never blocks the medal. */
 /* The shipped bitmap trims capacity to ID 305; replacement art counts once. */
 table=fopen(argv[5],"rb");assert(table);assert(fread(MOD_CARD_REAL,1,64,table)==64);fclose(table);
 assert(cardAlbumTotal()==305 && cardAlbumLimit()==306);
 id=0;top=0;
 for(int n=0;n<27;n++){id=modCardMove(id,0x4000);top=modCardTop(id,top);}
 for(int n=0;n<10;n++){id=modCardMove(id,0x2000);top=modCardTop(id,top);}
 assert(id==305 && top==22 && modCardMove(id,0x4000)==305 && modCardMove(id,0x2000)==305);
 checkAlbumBar(28,0);assert(barH==29 && barY==-63);
 checkAlbumBar(28,11);assert(barH==29 && barY==-9);
 checkAlbumBar(28,22);assert(barH==29 && barY==46);
 for(int i=0;i<=305;i++)for(int k=0;k<4;k++) {
  int move=modCardMove(i,(int[]){0x8000,0x2000,0x1000,0x4000}[k]);
  int row=modCardTop(move,top);assert(move>=0 && move<=305 && move/11>=row && move/11<row+6);
 }
 /* Sparse additions retain numbered positions, skipping holes along a direction. */
 memset(MOD_CARD_REAL+9,0,55);MOD_CARD_REAL[8]=1;
 MOD_CARD_REAL[70/8]|=1<<(70&7);MOD_CARD_REAL[74/8]|=1<<(74&7);MOD_CARD_REAL[92/8]|=1<<(92&7);
 assert(cardAlbumTotal()==68 && cardAlbumLimit()==93);
 assert(modCardMove(65,0x2000)==65 && modCardMove(70,0x2000)==74 && modCardMove(74,0x8000)==70);
 assert(modCardMove(70,0x4000)==92 && modCardMove(92,0x1000)==70);
 assert(modCardMove(92,0x2000)==92 && modCardMove(92,0x4000)==92);
 MOD_OPT_NEW_CARDS=0;assert(cardAlbumTotal()==65 && cardAlbumLimit()==66);
 checkAlbumBar(6,0);
 puts("PASS: album 305/65 totals, partial final row, sparse navigation, proportional scrollbar through 512 slots; cards 66..511 save round trip, sparse/short records, 510-row shop/trades, daily stock, scroll to 511, all 446 CARD2 images, original/replacement art OFF/ON, JSON pack rarities, real-only medal, OFF/ON visibility and nondestructive resave");
}
'''
    with tempfile.TemporaryDirectory(prefix='cards-host-') as d:
        d = Path(d)
        dummy_archive(d / 'CARD2.ALL')
        (d / 'new.json').write_text(json.dumps([authored(i, i % 5) for i in range(66, 512)]))
        rows = cards.build(d / 'out', d / 'CARD2.ALL', d / 'new.json')
        (d / 'real.bin').write_bytes(cards.real_mask(rows))
        (d / 'shipped.bin').write_bytes(cards.real_mask(cards.load()))
        import struct
        (d / 'art.bin').write_bytes(struct.pack('<64H', *cards.replacement_table()))
        (d / 'test.c').write_text(prefix + tags + '\n' + production + tests)
        subprocess.run(['cc', '-std=c99', '-Wall', '-Wextra', '-Werror', '-fsanitize=address,undefined',
                        str(d / 'test.c'), '-o', str(d / 'test')], check=True)
        subprocess.run([str(d / 'test'), str(d / 'CARD2.ALL'), str(d / 'out/CARDTAB.BIN'), str(d / 'real.bin'), str(d / 'art.bin'), str(d / 'shipped.bin')], check=True)


if __name__ == '__main__':
    main()
