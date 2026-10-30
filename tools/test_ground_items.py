#!/usr/bin/env python3
"""Stable pickup compiler checks and the actual C pickup functions under UBSan."""

from pathlib import Path as _DevPath
import sys as _dev_sys
_dev_sys.path.insert(0, str(next(p for p in _DevPath(__file__).resolve().parents if (p / "tools").is_dir())))
import json
import hashlib
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from dws.pickups import load_registry, rewrite, rewrite_text


class RegistryTests(unittest.TestCase):
    def test_registry_bound_and_unique(self):
        data, spots = load_registry()
        self.assertGreater(len(spots), 65)
        self.assertTrue(any(screen >= 300 for screen, x, y in spots))
        self.assertEqual(len(spots), len({r['id'] for r in data['spots']}))
        with self.assertRaisesRegex(ValueError, 'bound'):
            load_registry(limit=65)

    def test_existing_save_ids_never_move(self):
        data, _ = load_registry()
        old = [[r['id'], r['screen'], *r['tile']] for r in sorted(data['spots'], key=lambda r: r['id']) if r['id'] < 499]
        self.assertEqual(hashlib.sha256(json.dumps(old, separators=(',', ':')).encode()).hexdigest(),
                         '99abccd9f1bfbba1f2857e1c4d008df51e2f419bb622cc1354c13467ac27c15d')

    def test_bitset_save_decode(self):
        from tools.dev import memory_card as mcd
        self.assertEqual(mcd.decode_records([(0x000C, b'\x81')])['groundPickupBits'], [0, 7])

    def test_manual_compiler_target_capacity(self):
        from dws.build import exe_ground_pickup_max
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            header = root / 'include/dw/item.h'
            header.parent.mkdir(parents=True)
            header.write_text('#define MOD_GROUND_PICKUP_MAX 1024\n')
            target = root / 'build/us/psx/gcc'
            self.assertEqual(exe_ground_pickup_max(target), 1024)
            header.write_text('/* older target */\n')
            self.assertEqual(exe_ground_pickup_max(target), 0)

    def test_item_and_branch_changes_keep_location_id(self):
        spots = {(17, 33, 49): 64}
        text = '    SPAWN_ITEM 1, 33, 49\n    SPAWN_ITEM16 300, 33, 49 ; alternate item\n'
        got = rewrite_text(text, [17], spots)
        self.assertIn('SPAWN_ITEM_DAILY 1, 33, 49, 64', got)
        self.assertIn('SPAWN_ITEM_DAILY 300, 33, 49, 64, 17 ; alternate item', got)

    def test_unregistered_and_nonliteral_spawns_fail(self):
        with self.assertRaisesRegex(ValueError, 'no stable ID'):
            rewrite_text('SPAWN_ITEM 1, 2, 3', [17], {})
        with self.assertRaisesRegex(ValueError, 'cannot assign'):
            rewrite_text('SPAWN_ITEM 1, some_tile, 3', [17], {})

    def test_shared_new_screen_uses_its_own_ids(self):
        from dws import bytecode as bytecode
        from dws.pickups import script_screens
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            registry = work / 'registry.json'
            registry.write_text(json.dumps(dict(format=1, script_screens={'18': [17]}, spots=[
                dict(id=0, screen=17, tile=[33, 49]), dict(id=1, screen=314, tile=[33, 49])])) )
            mh = work / 'MAPHEAD.SCN'
            mh.write_bytes(bytecode.assemble_script('.section 17 old\n.section 314 new\nold:\n SET_SCRIPT 18, 17\n END_SECTION\nnew:\n SET_SCRIPT 18, 314\n END_SECTION\ndead:\n SET_SCRIPT 999, 666\n END_SECTION\n', 'test', {'quiet': True})[0])
            self.assertEqual(script_screens(mh), {18: [17, 314]})
            target = work / 'script_018.scn.txt'
            target.write_text('SPAWN_ITEM 1, 33, 49\n')
            rewrite(work, mh, 2, registry)
            self.assertIn(', 0, 17\n', target.read_text())
            self.assertIn(', 1, 314\n', target.read_text())

    def test_duplicate_registry_entries_fail(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / 'bad.json'
            row = dict(id=0, screen=17, tile=[33, 49])
            p.write_text(json.dumps(dict(format=1, spots=[row, row])))
            with self.assertRaisesRegex(ValueError, 'duplicate'):
                load_registry(p)


def function(source, name):
    start = re.search(r'^(?:static )?(?:void|int32_t) ' + name + r'\([^;]*?\)[^\n]*\n\{', source, re.M)
    assert start, name
    return source[start.start():source.index('\n}', start.end()) + 2]


def native(work):
    source = (work / 'src/main/item.c').read_text()
    header = (work / 'include/dw/item.h').read_text()
    bound = int(re.search(r'#define MOD_GROUND_PICKUP_MAX (\d+)', header)[1])
    code = r'''
#include <stdint.h>
#include <assert.h>
#include <stdio.h>
#include <string.h>
typedef int16_t ItemId;
#define ITEM_NONE -1
#define OBJECT_ID_DROPPED_ITEM 999
struct Vec { int vx,vy,vz; };
struct Pos { struct Vec location; } pos;
struct Entity { struct Pos *posData; } entity={&pos}, *ENTITY_TABLE[]={&entity};
struct Drop { struct { ItemId type; struct Vec spriteLocation; } worldItem; int16_t tileX,tileY; } DROPPED_ITEMS[11];
static uint16_t MOD_DROPPED_SPOT[11];
static int awarded, allow=1;
void renderDroppedItem(int32_t i) { }
void addObject(int a,int b,int c,void(*d)(int32_t)) { }
void removeObject(int a,int b) { }
int giveItem(ItemId id,int n) { if(allow) awarded+=n; return allow; }
void spawnItem(ItemId,int16_t,int16_t);
'''
    code += f'\n#define MOD_GROUND_PICKUP_MAX {bound}\nuint8_t MOD_GROUND_PICKED[MOD_GROUND_PICKUP_MAX/8];\n'
    for name in ('modForgetGroundPicked', 'modGroundPicked', 'spawnDailyItem', 'spawnItem',
                 'deleteDroppedItem', 'clearDroppedItems', 'pickupItem'):
        code += '\n' + function(source, name) + '\n'
    code += r'''
int main(void) {
 for(int i=0;i<11;i++) DROPPED_ITEMS[i].worldItem.type=ITEM_NONE;
 modForgetGroundPicked();
 for(int id=0;id<MOD_GROUND_PICKUP_MAX;id++) {
  spawnDailyItem(1,33,49,id); assert(DROPPED_ITEMS[0].worldItem.type==1);
  assert(pickupItem(0));
  for(int old=0;old<=id;old++) assert(modGroundPicked(old));
 }
 assert(awarded==MOD_GROUND_PICKUP_MAX);
 for(int id=0;id<MOD_GROUND_PICKUP_MAX;id++) {
  spawnDailyItem(1,33,49,id); assert(DROPPED_ITEMS[0].worldItem.type==ITEM_NONE);
 }
 spawnDailyItem(1,33,49,-1); spawnDailyItem(1,33,49,MOD_GROUND_PICKUP_MAX);
 assert(DROPPED_ITEMS[0].worldItem.type==ITEM_NONE);
 modForgetGroundPicked();
 for(int id=0;id<MOD_GROUND_PICKUP_MAX;id++) assert(!modGroundPicked(id));
 spawnDailyItem(1,33,49,0); allow=0; assert(!pickupItem(0)); assert(!modGroundPicked(0));
 allow=1; assert(pickupItem(0)); assert(modGroundPicked(0));
 // A copied instance cannot grant a second pickup of an already spawned ID.
 spawnDailyItem(1,33,49,1); spawnDailyItem(1,33,49,1);
 assert(pickupItem(0)); int before=awarded; assert(!pickupItem(1)); assert(awarded==before);
 // Battle and legacy drops are untracked even when reusing a previously tracked slot.
 spawnItem(1,33,49); assert(pickupItem(0)); assert(awarded==before+1);
 modForgetGroundPicked();
 for(int i=0;i<11;i++) spawnDailyItem(1,33,49,i);
 spawnDailyItem(1,33,49,50); assert(!modGroundPicked(50));
 clearDroppedItems(); spawnDailyItem(1,33,49,50); assert(pickupItem(0));
 puts("PASS: every ID beyond 65, duplicates, failed/full pickups, next day, invalid IDs, untracked drops");
}
'''
    with tempfile.TemporaryDirectory(prefix='dw-ground-items-') as tmp:
        c, binary = Path(tmp) / 'check.c', Path(tmp) / 'check'
        c.write_text(code)
        subprocess.run(['cc', '-std=c99', '-Wall', '-Werror', '-fsanitize=undefined', str(c), '-o', str(binary)], check=True)
        subprocess.run([str(binary)], check=True)


if __name__ == '__main__':
    work = Path(sys.argv.pop(1)) if len(sys.argv) > 1 and not sys.argv[1].startswith('-') else None
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(RegistryTests)
    if not unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful():
        sys.exit(1)
    if work:
        native(work)
