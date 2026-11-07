"""Compile the real camera cap and exercise world/menu/battle transitions."""
import os
from pathlib import Path
import re
import subprocess
import tempfile
import unittest


@unittest.skipUnless(os.environ.get('WORLD_FIT_SOURCE'), 'needs a prepared map.c')
class WorldFit(unittest.TestCase):
    def test_field_menus_preserve_fit_and_other_cameras_bypass_it(self):
        source = Path(os.environ['WORLD_FIT_SOURCE']).read_text()
        functions = []
        for name in ('modFitOff', 'modPartnerFitScale', 'modPartnerFitMeasure'):
            match = re.search(r'(?:static )?(?:int32_t|void) ' + name + r'\([^)]*\)\n\{', source)
            self.assertIsNotNone(match)
            end, depth = match.end(), 1
            while depth:
                depth += (source[end] == '{') - (source[end] == '}')
                end += 1
            functions.append(source[match.start():end])
        harness = '''#include <stdint.h>
#include <assert.h>
int32_t GAME_STATE, IS_IN_MENU;
struct { int32_t fitPx, fitMin, fitScale, fitPxSeen; } MOD_CAM_CFG;
''' + '\n'.join(functions) + '''
int main(void) {
    int menu, state, n;
    MOD_CAM_CFG.fitPx = 130;
    MOD_CAM_CFG.fitMin = 2048;
    for (state = 0; state < 2; state++) {
        GAME_STATE = state;
        for (menu = 0; menu < 2; menu++) {
            IS_IN_MENU = menu;
            MOD_CAM_CFG.fitPxSeen = 260;
            assert(modPartnerFitScale() == 2048);
            /* Same projected skeleton behind an opened menu must stay still. */
            for (n = 0; n < 120; n++) {
                modPartnerFitMeasure(130, modPartnerFitScale());
                assert(modPartnerFitScale() == 2048);
            }
            MOD_CAM_CFG.fitPxSeen = 65;
            assert(modPartnerFitScale() == 4096);
        }
    }
    for (state = 2; state < 10; state++) {
        GAME_STATE = state;
        MOD_CAM_CFG.fitPxSeen = 260;
        assert(modPartnerFitScale() == 4096);
        modPartnerFitMeasure(600, 4096);
        assert(MOD_CAM_CFG.fitPxSeen == 260);
    }
    return 0;
}
'''
        with tempfile.TemporaryDirectory() as folder:
            src, exe = Path(folder) / 'fit.c', Path(folder) / 'fit'
            src.write_text(harness)
            subprocess.run(['cc', '-Wall', '-Wextra', '-Werror', str(src), '-o', str(exe)], check=True)
            subprocess.run([str(exe)], check=True)


if __name__ == '__main__':
    unittest.main()
