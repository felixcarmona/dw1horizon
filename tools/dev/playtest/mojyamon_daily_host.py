#!/usr/bin/env python3
"""Run the actual trade and day-reset C against inventory, cancel and save-state cases."""
import argparse
import json
from pathlib import Path
import re
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[3]


def function(source, name):
    start = source.index('void ' + name + '(void)\n{')
    end = source.index('{', start) + 1
    depth = 1
    while depth:
        depth += (source[end] == '{') - (source[end] == '}')
        end += 1
    return source[start:end]


def check(tree):
    source = (tree / 'src/shop/script_menu.c').read_text()
    common = (tree / 'src/main/script_common.c').read_text()
    header = (tree / 'include/dw/script.h').read_text()
    defines = '\n'.join(re.findall(r'^#define MOJYA_DAILY_.*$', header, re.M))
    code = r'''
#include <stdint.h>
#include <assert.h>
#include <stdio.h>
#include <string.h>
#define PSTAT_254 254
#define PSTAT_249 249
#define MOD_ECON_STACK_CAP 0
#define MOD_DAILY_SIZE 7
#define MOD_DAILY_CARDS 0
#define MOD_DAILY_POOL 1
#define MOD_DAILY_EXCLUDED 2
#define MOD_DAILY_COUNTER_FIRST 3
#define MOD_DAILY_COUNTER_COUNT 4
#define MOD_DAILY_CLEAR_PSTAT 5
#define MOD_DAILY_CLEAR_MASK 6
typedef struct { int topRow, cursor; uint8_t buf[6]; } Box;
typedef struct { uint8_t smth[6]; } ScriptState;
Box left, right, *ITEM_MENU_LEFT=&left, *ITEM_MENU_RIGHT=&right;
ScriptState state, *SCRIPT_STATE_PTR=&state;
int SCRIPT_STATE_2, SCRIPT_NEXT_STATE_2, SCRIPT_TEXTBOX_MODE, ACTIVE_INSTRUCTION;
int ITEM_MENU_TYPE, SHOP_ITEM_TYPE, MOJYA_GOT, MAX_SHOP_AMOUNT, SHOP_AMOUNT;
int inventory[128], pstats[256], flags[800], shown, amountOpened, rejectGive;
int16_t MOD_DAILY[7]={0,0,0,-1,0,-1,-1};
int readPStat(int n) { return pstats[n]; }
void writePStat(int n,int v) { pstats[n]=v; }
int isTriggerSet(int n) { return flags[n]; }
void setTrigger(int n) { flags[n]=1; }
void unsetTrigger(int n) { flags[n]=0; }
int econCap(int n,int fallback) { return 99; }
int getItemCount(int n) { return inventory[n]; }
void setInputRepeatMask(int n) {}
void triggerBoxCloseFlag(int n) {}
void showMapHeadTextbox(int n,int a,int b,int c) { shown=n; }
void openAmountBox(int n) { amountOpened++; }
void removeItem(int n,int count) { inventory[n]-=count; }
int giveItem(int n,int count) { if(rejectGive && n==MOJYA_GOT) return 0; inventory[n]+=count; return 1; }
void allocateItemMenuBox(Box **a,int b,int c,int d,int e,int f,int g) {}
void destroyItemMenuBox(Box **a) {}
void mojyaTradeFillItemList(void) {}
void createMojyaTradeMenu(void) {}
void playShopSoundOnlyInSavannah(void) {}
void modForgetGroundPicked(void) {}
int randomLimit(int n) { return 0; }
void setMojyaItemTradedTrigger(void);
'''
    code += defines + '\n' + '\n'.join(function(source, n) for n in ('openMojyamonShop', 'setMojyaItemTradedTrigger'))
    code += function(common, 'dailyPStatTrigger')
    shops = json.loads((ROOT / 'content/tables/shops.json').read_text())
    code += '\nint inputs[9]={' + ','.join(map(str, shops['mojyamonGives'][:9])) + '};\n'
    code += 'int outputs[9]={' + ','.join(map(str, shops['mojyamonTakes'][:9])) + '};\n'
    code += r'''
int main(void) {
 int row, i, saved[800];
 for(row=0;row<9;row++) {
  ITEM_MENU_TYPE=(row/3)*3; left.cursor=row%3; right.buf[(row%3)*2]=outputs[row];
  pstats[249]=inputs[row]; inventory[inputs[row]]=5; inventory[outputs[row]]=0;
  SCRIPT_STATE_2=4; openMojyamonShop(); assert(MAX_SHOP_AMOUNT==1);
  /* Opening and cancelling must leave the saved allowance available. */
  assert(!flags[MOJYA_DAILY_FIRST+row]);
  SCRIPT_STATE_2=6; openMojyamonShop(); assert(!flags[MOJYA_DAILY_FIRST+row]);
  SCRIPT_STATE_2=4; openMojyamonShop();
  rejectGive=1; SHOP_AMOUNT=1; SCRIPT_STATE_2=5; openMojyamonShop();
  assert(inventory[inputs[row]]==5 && inventory[outputs[row]]==0);
  assert(!flags[MOJYA_DAILY_FIRST+row]); rejectGive=0;
  SCRIPT_STATE_2=4; openMojyamonShop(); SHOP_AMOUNT=1; SCRIPT_STATE_2=5; openMojyamonShop();
  assert(inventory[inputs[row]]==4 && inventory[outputs[row]]==1);
  assert(flags[MOJYA_DAILY_FIRST+row] && flags[5+row]);
  /* The saved trigger array survives a round trip without a transient cache. */
  memcpy(saved,flags,sizeof flags); memset(flags,0,sizeof flags); memcpy(flags,saved,sizeof flags);
  i=amountOpened; SCRIPT_STATE_2=4; openMojyamonShop();
  assert(shown==12 && amountOpened==i);
  assert(inventory[inputs[row]]==4 && inventory[outputs[row]]==1);
 }
 assert(flags[14]); flags[788]=1; flags[798]=flags[799]=1;
 dailyPStatTrigger();
 for(i=0;i<9;i++) assert(!flags[MOJYA_DAILY_FIRST+i] && flags[5+i]);
 assert(flags[788] && !flags[798] && !flags[799] && flags[14]);
 for(row=0;row<9;row++) {
  ITEM_MENU_TYPE=(row/3)*3; left.cursor=row%3; right.buf[(row%3)*2]=outputs[row];
  pstats[249]=inputs[row]; inventory[inputs[row]]=5; inventory[outputs[row]]=0;
  SCRIPT_STATE_2=4; openMojyamonShop(); assert(MAX_SHOP_AMOUNT==1);
  SHOP_AMOUNT=1; SCRIPT_STATE_2=5; openMojyamonShop();
  assert(inventory[inputs[row]]==4 && inventory[outputs[row]]==1);
 }
 puts("PASS actual C: nine independent rows, cap 1, cancel, failed give rollback, saved flags, same-day refusal, day reset, next-day success, recruitment history retained");
}
'''
    with tempfile.TemporaryDirectory() as folder:
        src = Path(folder) / 'trade.c'; exe = Path(folder) / 'trade'
        src.write_text(code)
        subprocess.run(['cc', '-std=c99', '-Wall', '-Werror', str(src), '-o', str(exe)], check=True)
        subprocess.run([str(exe)], check=True)


def check_texts():
    for lang in ('ours', 'es', 'pt-br', 'fr', 'de', 'it', 'ja', 'ca'):
        base = ROOT / 'text' / lang / 'dialogue'
        script = json.loads((base / 'unused.json').read_text())
        maphead = json.loads((base / 'maphead.json').read_text())
        for n in (10, 12):
            value = maphead[f'm1238.u{n}']
            assert isinstance(value, str) and value
            assert value == script[f's000.sec1238.u{n}'], (lang, n)
        assert '{item 249}' in str(maphead['m1238.u11']), 'keep the live amount-box question'
    print('PASS eight languages: refusal and daily text match in script 0 and the active MAPHEAD bank; amount question retained')


def check_recruitment():
    """Execute the authored handlers for all group orders and all row orders."""
    import ast
    import itertools
    from types import SimpleNamespace as NS
    functions = []
    for group, file, occurrence in [(1, 's129-134', 2), (2, 's128-133', 0), (3, 's128-133', 1)]:
        module = ast.parse((ROOT / 'story/base/zones/freezeland' / file / 'script.py').read_text())
        handler = [n for n in module.body if isinstance(n, ast.FunctionDef) and n.name == 'talk'][occurrence]
        handler.decorator_list = []
        functions.append(compile(ast.Module(body=[handler], type_ignores=[]), file, 'exec'))
    orders = list(itertools.permutations(range(1, 4)))
    noop = lambda *a, **kw: None
    for groups in orders:
        for rows in itertools.product(orders, repeat=3):
            traded = NS(**{f'set{g}_row{r}': False for g in range(1, 4) for r in range(1, 4)})
            joined = []; departed = []
            engine = NS(arg=NS(set=noop), menu_result=NS(set=noop), prosperity=NS(add=noop))
            env = dict(mojyamon_traded=traded, engine=engine, Routine=NS(mojyamon_trade=2),
                       say=noop, play=noop, dws=noop, recruited=lambda species: bool(joined),
                       recruit=lambda species: joined.append(species), Species=NS(Mojyamon=52),
                       walk_away=noop, leave=noop, glances=NS(set=noop), sound=NS(jingle=noop),
                       narrator=NS(say=noop), slot0=NS(play=noop))
            env.update(**{f't{i}': NS(**{f'u{j}': j for j in range(7)}) for i in (5, 6, 7)})
            env['mojyamon_left'] = NS(**{f'set{g}': NS(set=lambda g=g: departed.append(g)) for g in range(1, 4)})
            handlers = []
            for code in functions:
                exec(code, env); handlers.append(env['talk'])
            for g in groups:
                for r in rows[g-1]:
                    env['call'] = lambda routine, g=g, r=r: setattr(traded, f'set{g}_row{r}', True)
                    handlers[g-1]()
                    assert departed in ([], [3]), departed
            env['call'] = noop
            handlers[2]()  # Return to group 3 if group 1 or 2 completed the ninth row.
            assert departed == [3] and joined == [52], (groups, rows, departed)
            for handler in handlers:
                handler()
            assert departed == [3] and joined == [52], 'recruits only once'
    print('PASS authored recruitment handlers: 1296 group/row orders, group 3 only, return after ninth trade, already-recruited guard')


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--tree', type=Path, default=ROOT / 'build/decomp-dev')
    check(p.parse_args().tree)
    check_recruitment()
    check_texts()
