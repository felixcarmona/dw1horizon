"""Exercise the popup's actual C timing helper and localized renderer bounds."""
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
PATCH = ROOT / 'mods/patches/Show-target-time-and-remaining-life-in-evolution-req.patch'


class EvolutionPopup(unittest.TestCase):
    def test_live_timing_tables_and_exact_routes(self):
        added = '\n'.join(line[1:] for line in PATCH.read_text().splitlines()
                          if line.startswith(('+', ' ')) and not line.startswith('+++'))
        start = added.index('static __attribute__((noinline)) int32_t chartTargetHours')
        end = added.index('\n}\n', start) + 3
        function = added[start:end]
        # Same public constants as level.h; no decompilation checkout needed in CI.
        code = '''#include <stdint.h>
#include <assert.h>
#define LEVEL_FRESH 1
#define LEVEL_IN_TRAINING 2
#define LEVEL_ROOKIE 3
#define LEVEL_CHAMPION 4
#define LEVEL_ULTIMATE 5
#define LEVEL_MEGA 6
#define MOD_EVO_ULTIMATE_AGAIN 7
#define MOD_EVO_MEGA 8
#define MOD_EVO_FALLBACK_HOURS 9
#define MOD_EVO_FALLBACK_TARGET 10
#define MOD_EVO_PAIR_MAX 16
int CHART_DETAIL_ID=100;
int16_t MOD_EVO_TIMING[11]={-1,6,24,72,168,48,-1,96,120,96,11};
int16_t MOD_EVO_FRESH[16][2]={{100,2}}, MOD_EVO_ULTIMATE[16][2]={{100,115},{100,245}};
struct {int level;} species[500];
#define DIGI_PARA(id) species[id]
typedef struct {int16_t to[6];} EvolutionPath;
EvolutionPath path={{200,-1,-1,-1,-1,-1}};
EvolutionPath *getEvolutionPath(int id) {return &path;}
int isVanillaSpecies(int id) {return id<180;}
int16_t getFreshEvolutionTarget(int id) {
 int16_t target=-1;
 for(int i=0;i<16;i++) if(MOD_EVO_FRESH[i][0]==id) target=MOD_EVO_FRESH[i][1];
 return target;
}
'''+function+'''
int main(void) {
 species[100].level=1; assert(chartTargetHours(2)==6); assert(chartTargetHours(3)==-1);
 species[100].level=2; assert(chartTargetHours(200)==24);
 species[100].level=3; assert(chartTargetHours(200)==72); assert(chartTargetHours(11)==96);
 assert(chartTargetHours(201)==-1); /* special/item route */
 species[100].level=4; assert(chartTargetHours(200)==168);
 species[100].level=5;
 species[115].level=6; species[245].level=6;
 assert(chartTargetHours(115)==48); /* original Machinedramon timed pair */
 assert(chartTargetHours(245)==120); /* imported Mega timed pair */
 species[200].level=5; assert(chartTargetHours(200)==96);
 species[200].level=6; assert(chartTargetHours(200)==120);
 MOD_EVO_TIMING[8]=36; assert(chartTargetHours(200)==96); assert(chartTargetHours(245)==48);
 MOD_EVO_TIMING[7]=-1; assert(chartTargetHours(200)==-1); assert(chartTargetHours(115)==48);
 MOD_EVO_TIMING[5]=-1; assert(chartTargetHours(115)==-1);
 species[100].level=6; assert(chartTargetHours(200)==-1);
 species[100].level=3; MOD_EVO_TIMING[3]=81; assert(chartTargetHours(200)==81);
 return 0;
}
'''
        with tempfile.TemporaryDirectory() as folder:
            src, exe = Path(folder) / 'timing.c', Path(folder) / 'timing'
            src.write_text(code)
            subprocess.run(['cc', '-Wall', '-Werror', '-Wno-unused-parameter', str(src), '-o', str(exe)], check=True)
            subprocess.run([str(exe)], check=True)

    def test_every_language_both_fonts_and_long_name(self):
        from tools.localize.check import LANGUAGES, ui_width
        from tools.localize.executable.bank import list_width
        rules = json.loads((ROOT / 'content/tables/evolution-rules.json').read_text())['evolutionTiming']
        max_hours = max(*rules['hours'].values(), rules['ultimateAgainHours'], rules['megaHours'])
        for language in LANGUAGES:
            names = json.loads((ROOT / 'text' / ('ours' if language == 'en' else language) / 'names.json').read_text())
            text = lambda key: names['main.CHART_STR_' + key]
            for font in ('b', 'original'):
                width = lambda value: ui_width(value, font, language)
                for verdict in (text('WAIT') % max_hours, text('READY')):
                    self.assertLessEqual(width(text('VERDICT') % (4, 3) + verdict), 244,
                                         (language, font, verdict))
                self.assertLessEqual(width(text('LIFE') % (max_hours - 1)), 244, (language, font))
                # Footer starts at 28; Close ends at 286, with a 13 px icon and 6 px gap.
                self.assertLessEqual(width(text('RANDOM')), 286 - width(text('CLOSE')) - 13 - 6 - 28,
                                     (language, font))
                self.assertLessEqual(width(text('TIME')) + width(str(max_hours)) + 4, 194 - 41)
                # The game's longest canonical name (19 chars) has a full title row.
                self.assertLessEqual(width(text('EVOLVE') % 'MetalGreymonVaccine'), 244, (language, font))
                self.assertLessEqual((width(text('FROM') % 'MetalGreymonVaccine') if language == 'zh-hans' else
                                      list_width(text('FROM') % 'MetalGreymonVaccine', font)) + 49,
                                     280 - max(width(text('YES')), width(text('NO'))) - 4,
                                     (language, font))

    def test_first_partner_matches_birth(self):
        data = json.loads((ROOT / 'content/tables/new-game.json').read_text())['newGame']
        self.assertEqual(data['firstPartner']['lifetimeHours'], 408)
        self.assertEqual(data['firstPartner']['lifetimeHours'], data['partnerBirth']['lifetimeHours'])


if __name__ == '__main__':
    unittest.main()
