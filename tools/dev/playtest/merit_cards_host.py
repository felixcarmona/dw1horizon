#!/usr/bin/env python3
"""Exercise the actual card-list builder and post-trade cursor repair on the host."""
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from tools.dev.playtest.quick_care_host import function


def main():
    root = Path(sys.argv[1] if len(sys.argv) > 1 else 'build/decomp-dev')
    source = (root / 'src/shop/script_menu.c').read_text()
    builder = function(source, 'int32_t shopFillSellCardList(void)\n')
    trade = function(source, 'void openMeritShop(void)\n')
    marker = '\t\tbox = ITEM_MENU_LEFT;'
    if marker in trade:
        start = trade.index(marker)
        end = trade.index('\n\t\tSCRIPT_STATE_2 = 1;', start)
        repair = ('void repair(void) { ItemMenuBox *box; int32_t row; int32_t top;'
                  + (' int32_t i;' if 'box->itemRow[i]' in trade[start:end] else '')
                  + '\n' + trade[start:end] + '\n}')
    else:
        # The baseline has no cursor repair; still exercise its real builder.
        repair = 'void repair(void) {}'
    prefix = r'''
#include <stdint.h>
#include <string.h>
#include <assert.h>
#include <stdio.h>
typedef struct { uint8_t buf[132]; int itemCount, topRow, cursor, prevTopRow, prevCursor, visibleRows; uint8_t itemRow[8]; } ItemMenuBox;
static ItemMenuBox storage, *ITEM_MENU_LEFT = &storage;
static uint8_t cards[65];
static uint8_t getCardAmount(int id) { assert(id >= 1 && id <= 64); return cards[id]; }
void updateItemMenuStrings(ItemMenuBox *box, int row, int style) {
 assert(box == ITEM_MENU_LEFT && row == 9 && style == 1);
 int rows=box->itemCount-box->topRow;
 if(rows>box->visibleRows)rows=box->visibleRows;
 unsigned used=0;
 for(int i=0;i<rows;i++) {
  assert(box->itemRow[i]>=9 && box->itemRow[i]<9+rows);
  used|=1u<<(box->itemRow[i]-9);
 }
 assert(used==((1u<<rows)-1));
}
'''
    tests = r'''
int main(void) {
 unsigned cases=0;
 for (unsigned mask=0; mask<65536; mask++) {
  memset(cards,0,sizeof(cards));
  for (int i=0;i<16;i++) if(mask & (1u<<i)) cards[i*4+1]=(i%15)+1;
  memset(&storage,0xa5,sizeof(storage));
  storage.visibleRows=6;
  int any=shopFillSellCardList(), n=0;
  for(int i=1;i<=64;i++) if(cards[i]) {
   assert(storage.buf[n*2]==i && storage.buf[n*2+1]==cards[i]); n++;
  }
  assert(storage.itemCount==n && any==(n!=0));
  assert(storage.buf[n*2]==255 && storage.buf[n*2+1]==0);
  for(int old=0;old<64;old++) {
   storage.topRow=old>5?old-5:0;
   storage.cursor=old-storage.topRow;
   for(int i=0;i<6;i++)storage.itemRow[i]=9+(i+old)%6;
   repair();
   int expected=n==0?0:(old<n?old:n-1);
   assert(storage.topRow+storage.cursor==expected);
   assert(storage.topRow<=(n>6?n-6:0));
   assert(storage.topRow>=0 && storage.cursor>=0 && storage.cursor<6);
   assert(storage.prevTopRow==storage.topRow && storage.prevCursor==storage.cursor);
  }
  cases++;
 }
 memset(cards,15,sizeof(cards));
 assert(shopFillSellCardList() && storage.itemCount==64);
 assert(storage.buf[126]==64 && storage.buf[127]==15 && storage.buf[128]==255);
 /* Remove every last copy while positioned at the end of a scrolled list. */
 for(int n=64;n>0;n--) {
  storage.topRow=n>6?n-6:0; storage.cursor=n-1-storage.topRow;
  cards[n]=0; shopFillSellCardList(); repair();
  assert(storage.itemCount==n-1);
  assert(storage.topRow+storage.cursor==(n>1?n-2:0));
 }
 puts("PASS: 65536 sparse inventories, 4194304 cursor positions and rotated texture rows, all 64 cards, depletion to empty");
 return cases!=65536;
}
'''
    with tempfile.TemporaryDirectory(prefix='merit-cards-host-') as temp:
        c = Path(temp) / 'test.c'
        exe = Path(temp) / 'test'
        c.write_text(prefix + builder + repair + tests)
        subprocess.run(['cc', '-std=c99', '-Wall', '-Wextra', '-Werror', '-fsanitize=address,undefined', str(c), '-o', str(exe)], check=True)
        subprocess.run([str(exe)], check=True)


if __name__ == '__main__':
    main()
