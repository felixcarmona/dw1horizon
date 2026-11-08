"""Option A contracts and the production save-slot migrator, compiled on the host."""
import csv
import ctypes
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
PATCH = ROOT / 'mods/patches/Migrate-equipped-technique-identities-for-layout-A.patch'


def production():
    text = PATCH.read_text().split('+++ b/src/main/coherent_slots.h\n', 1)[1]
    return '\n'.join(line[1:] for line in text.split('\ndiff --git ', 1)[0].splitlines() if line.startswith('+'))


def rows():
    return [r for r in csv.DictReader((ROOT/'docs/proposals/technique-coherence.csv').read_text().splitlines())
            if r['current_slots_json'] != r['option_a_slots_json']]


class Coherence(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = rows()
        cls.species = {s['id']:s for p in (ROOT/'content/species').glob('*.json') for s in [json.loads(p.read_text())]}
        cls.techs = {s['id']:s for p in (ROOT/'content/techniques').glob('*.json') for s in [json.loads(p.read_text())]}
        (ROOT/'build').mkdir(exist_ok=True)
        cls.tmp = tempfile.TemporaryDirectory(dir=ROOT/'build')
        path = Path(cls.tmp.name)
        code = '''#include <stdint.h>
#include <stddef.h>
typedef struct {uint8_t moves[16], special[3];} DigimonPara;
typedef struct {uint8_t moves[3];int32_t type;} RegisteredDigimon;
static int registeredSpecies(RegisteredDigimon *p){return p->type;}
static DigimonPara speciesData[1024];
#define DIGI_PARA(t) speciesData[t]
static struct {int32_t power,special;} MOVE_DATA[128];
typedef struct {uint8_t bytes[12];} SaveExtHead;
#define SAVE_TAG_END 0
#define SAVE_TAG_TECHNIQUE_LAYOUT 0x8003
''' + production() + '''
void setpara(int t, uint8_t *m, uint8_t *s){for(int i=0;i<16;i++)speciesData[t].moves[i]=m[i];for(int i=0;i<3;i++)speciesData[t].special[i]=s[i];}
void setmove(int t,int p,int s){MOVE_DATA[t].power=p;MOVE_DATA[t].special=s;}
void migrate(int t,uint8_t *e,const uint32_t *l){migrateCoherentSlots(t,e,l);}
int layout(uint8_t *e){return coherentSlotLayout(e);}
void registered(int t,uint8_t *m){RegisteredDigimon r; r.type=t;for(int i=0;i<3;i++)r.moves[i]=m[i];migrateCoherentRegistered(&r,1);for(int i=0;i<3;i++)m[i]=r.moves[i];}
'''
        (path/'test.c').write_text(code)
        subprocess.run(['cc','-std=c99','-Wall','-Wextra','-Werror','-Wno-sign-compare','-shared','-fPIC',str(path/'test.c'),'-o',str(path/'test.so')],check=True)
        cls.lib = ctypes.CDLL(str(path/'test.so'))
        cls.elements = ['fire','air','ice','mech','nature','battle','filth']
        for t,s in cls.techs.items():
            if t < 128: cls.lib.setmove(t,s['power'],cls.elements.index(s['element']) if s['element'] in cls.elements else 255)
        for r in cls.rows:
            ident = int(r['id']); s=cls.species[ident]
            moves=json.loads(r['option_a_slots_json']); moves=[255 if m is None else m for m in moves]+[255]*(16-len(moves))
            specials=[cls.elements.index(e) if e else 255 for e in s['specialties']]
            cls.lib.setpara(ident,(ctypes.c_uint8*16)(*moves),(ctypes.c_uint8*3)(*specials))

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def migrate(self,ident,equipped,known):
        bits=(ctypes.c_uint32*4)()
        for m in known: bits[m//32] |= 1 << (m%32)
        before=bytes(bits)
        slots=(ctypes.c_uint8*4)(*equipped)
        self.lib.migrate(ident,slots,bits)
        self.assertEqual(bytes(bits),before,'library must never change')
        self.assertEqual(slots[3],equipped[3],'finisher must never move')
        return list(slots)

    def test_exact_proposed_arrays_and_retained_indices(self):
        import sys
        sys.path.insert(0,str(ROOT/'tools'))
        import species
        self.assertEqual(len(self.rows),11)
        for r in self.rows:
            s=self.species[int(r['id'])]
            actual=species.techniques_from_json(s['techniques'],r['name'])
            want=json.loads(r['option_a_slots_json'])
            self.assertEqual(actual[:len(want)],[255 if m is None else m for m in want])
            self.assertEqual(s['specialties'],json.loads(r['option_a_specialties_json']))
            old=json.loads(r['current_slots_json'])
            for i,m in enumerate(old):
                if m in want: self.assertEqual(want.index(m),i)

    def test_every_old_slot_with_full_partial_and_empty_library(self):
        for r in self.rows:
            ident=int(r['id']); old=json.loads(r['current_slots_json']); new=json.loads(r['option_a_slots_json'])
            for i,prior in enumerate(old):
                if prior is None or prior>=58: continue
                for known in (set(range(58)),{prior},set(),{43,34,12,27}):
                    with self.subTest(species=ident,slot=i,known=known):
                        result=self.migrate(ident,[46+i,255,255,46+next(j for j,m in enumerate(old) if m is not None and 58<=m<=112)],known)
                        selected=result[0]
                        if ident==307 and i in (8,10,11,12,13,15):
                            self.assertEqual(selected,255,'unmarked BlackKing history is ambiguous')
                        elif prior in new and prior in known:
                            self.assertEqual(selected,46+new.index(prior))
                        elif selected!=255:
                            move=new[selected-46]
                            self.assertIn(move,known)
                            self.assertLess(move,58)
                            self.assertIn(self.techs[move]['element'],self.species[ident]['specialties'])
                        if not known: self.assertEqual(selected,255)

    def test_fallback_preserves_survivors_and_avoids_duplicates(self):
        result=self.migrate(327,[52,46,47,56],set(range(58)))
        self.assertEqual(result[1:],[46,47,56])
        self.assertEqual(len(set(result[:3])),3)
        # Removed vines must not silently become Wind Cutter even if only vines were known.
        self.assertEqual(self.migrate(327,[52,255,255,56],{39})[0],255)
        # If the old partner already knew Wind Cutter, it can be the nearest learned replacement.
        self.assertEqual(self.migrate(327,[52,255,255,56],{39,13})[0],52)

    def test_empty_invalid_unaffected_and_reload(self):
        self.assertEqual(self.migrate(327,[255,0,99,56],set(range(58))),[255,255,255,56])
        self.assertEqual(self.migrate(3,[46,47,48,49],set()),[46,47,48,49])
        import struct
        for value,want in ((b'',0),(struct.pack('<HHB',0x8003,1,1),1),(struct.pack('<HHB',0x8003,1,2),-1),(struct.pack('<HH',0x8003,0),-1)):
            data=bytes(12)+value+bytes(4)
            self.assertEqual(self.lib.layout((ctypes.c_uint8*len(data)).from_buffer_copy(data)),want)

    def test_released_blackking_layout_never_substitutes_known_ice_for_battle(self):
        # v0.0.7's released row; the audit baseline already had an unversioned Ice rewrite.
        released=[56,52,51,50,54,49,53,55,46,47,45,44,40,43,62,255]
        baseline=next(r for r in self.rows if r['id']=='307')
        audit=json.loads(baseline['current_slots_json'])
        for i,(old,interim) in enumerate(zip(released,audit)):
            if old==interim or old>=58 and interim>=58:continue
            result=self.migrate(307,[46+i,255,255,60],set(range(128)))
            self.assertEqual(result[0],255,(i,old,interim))
        for i in range(8):
            self.assertEqual(self.migrate(307,[46+i,255,255,60],set(range(128)))[0],46+i)

    def test_registered_vs_slots_clear_removed_and_keep_survivors(self):
        moves=(ctypes.c_uint8*3)(52,46,47)
        self.lib.registered(327,moves)
        self.assertEqual(list(moves),[255,46,47])
        patch=PATCH.read_text()
        self.assertIn('coherentSlotLayout(saveExtOf(slot))',patch)
        self.assertIn('migrateCoherentRegistered(SAVE_FILE.saves[0].battleRegistrationData, 40)',patch)

    def test_brains_order_and_weights_remain_global(self):
        table=json.loads((ROOT/'content/tables/brain-training.json').read_text())['brainTraining']
        self.assertEqual(table['techniques']['air'],[12,10,13,9,11,14,8,15])
        self.assertEqual(table['weights'],[[0,15,10],[25,13,8],[22,11,7],[20,9,5],[18,8,2],[15,7,0],[12,6,0],[10,5,0]])
        for r in self.rows:
            normals=set(json.loads(r['option_a_slots_json']))-{None}
            specials=self.species[int(r['id'])]['specialties']
            count=sum(any(e in specials and m in pool and table['weights'][pool.index(m)][specials.index(e)]>0 for e,pool in table['techniques'].items()) for m in normals if m<58)
            self.assertEqual(count,int(r['option_a_positive_brain_pool_count']),r['name'])

    def test_battle_learning_counts_and_enemy_selections(self):
        for r in self.rows:
            s=self.species[int(r['id'])]
            normal={m for m in json.loads(r['option_a_slots_json']) if m is not None and m<58}
            count=sum(self.techs[m]['learnChances'][s['specialties'].index(self.techs[m]['element'])]>0 for m in normal)
            self.assertEqual(count,int(r['option_a_positive_battle_count']),r['name'])
        changed={self.species[int(r['id'])]['name']:json.loads(r['option_a_slots_json']) for r in self.rows}
        for path in (ROOT/'content/maps').glob('*.json'):
            for enemy in json.loads(path.read_text()).get('digimon',[]):
                if enemy.get('species') not in changed: continue
                moves=changed[enemy['species']]
                for slot in enemy['moves']:
                    if slot == 255: continue
                    self.assertTrue(46<=slot<46+len(moves),(path.name,enemy['species'],slot))
                    self.assertIsNotNone(moves[slot-46])
        defaults=json.loads((ROOT/'content/battle/enemy-movesets.json').read_text())
        self.assertEqual(defaults['327']['moves'],['Megaton Punch','Tremar','Wind Cutter',None])

    def test_loader_migrates_once_before_cleanup_and_mode_conversion(self):
        patch=PATCH.read_text()
        self.assertIn('if (layout == 0)',patch)
        self.assertIn('layout = coherentSlotLayout(saveExtOf(0))',patch)
        self.assertRegex(patch, r'@@[^\n]*loadSaveCopy\(int32_t copy\)\n(?:[^\n]*\n){0,12}\+\t\tlayout = coherentSlotLayout')
        self.assertIn('if (layout < 0) return 0',patch)
        self.assertLess(patch.index('migrateCoherentSlots(SAVED_STATE.partnerType'),patch.index('\n \tdropAbsentSaveContent();'))
        self.assertIn('SAVE_TAG_TECHNIQUE_LAYOUT, &layout, 1',patch)
        self.assertIn('.text.coherentSlotLayout*',patch)
        self.assertIn('.text.migrateCoherentSlots*',patch)
        self.assertIn('.rodata.old.*',patch)
        self.assertIn('.text.drawOptionsText* .text.renderOptionsMenu* .text.modSetOption*',patch)


if __name__=='__main__': unittest.main()
