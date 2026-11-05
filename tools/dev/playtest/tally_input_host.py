#!/usr/bin/env python3
"""Compile the real tally callbacks and exercise pad combinations on the host.

Usage: python3 tools/dev/playtest/tally_input_host.py build/decomp-dev
Only drawing/sound dependencies are stubbed; input, gains and money use the C
callbacks from the supplied prepared patch tree.
"""
from pathlib import Path
import subprocess
import re
import sys
import tempfile


def function(source, name):
    match = re.search(r'\nvoid ' + name + r'\([^;{}]*\)\s*(?:int16_t instanceId;\s*)?\{', source)
    start = match.start() + 1
    body = match.end() - 1
    depth = 1
    end = body + 1
    while depth:
        depth += (source[end] == '{') - (source[end] == '}')
        end += 1
    return source[start:end]


def main():
    tree = Path(sys.argv[1])
    callbacks = [('main/battle_ui.c', 'tickPostBattleStatsBox'),
                 ('main/battle_ui.c', 'tickBitBox'),
                 ('trn/trn_hud.c', 'TRN_tickPostTrainingStatsBox'),
                 ('trn2/trn2_hud.c', 'TRN2_tickPostTrainingStatsBox')]
    source = r'''
#include <stdint.h>
#include <assert.h>
#include <stdio.h>
int MOD_OPT_BUTTONS;
#define CONFIRM_BUTTON (MOD_OPT_BUTTONS ? 0x20 : 0x40)
#define CANCEL_BUTTON (MOD_OPT_BUTTONS ? 0x40 : 0x10)
#define CAP_OF_STAT_INDEX(i) ((i) < 2 ? 9999 : 999)
uint32_t POLLED_INPUT, POLLED_INPUT_PREVIOUS;
int STATS_GAINS[6], INITIAL_COMBAT_STATS[1][6];
int SHOULD_SKIP_BIT_COUNTING, POST_BATTLE_STATS_TIMER, BITS_TO_GAIN, MONEY;
int MAIN_D_80135394, MAIN_D_8013539E, MAIN_D_801353D4, MAIN_D_801353DE;
struct { int state; } UI_BOX_DATA[3];
void playSound(int a, int b) { (void)a; (void)b; }
void BTL_tickBattleEndText(int a) { (void)a; }
'''
    source += '\n'.join(function((tree / 'src' / path).read_text(), name)
                        for path, name in callbacks)
    source += r'''
int main(void) {
    unsigned cases = 0;
    for (MOD_OPT_BUTTONS = 0; MOD_OPT_BUTTONS < 2; ++MOD_OPT_BUTTONS)
    for (unsigned pad2 = 0; pad2 < 3; ++pad2)
    for (unsigned other = 0; other < 65536; ++other)
    for (unsigned which = 0; which < 2; ++which) {
        unsigned button = which ? CANCEL_BUTTON : CONFIRM_BUTTON;
        unsigned background = (other & ~(CONFIRM_BUTTON | CANCEL_BUTTON)) |
            (pad2 == 1 ? 0x00400000 : pad2 == 2 ? 0x02000000 : 0);
        /* A press with any directions/shoulders/other port already held. */
        POLLED_INPUT_PREVIOUS = background;
        POLLED_INPUT = background | button;
        SHOULD_SKIP_BIT_COUNTING = MAIN_D_80135394 = MAIN_D_801353D4 = 0;
        POST_BATTLE_STATS_TIMER = MAIN_D_8013539E = MAIN_D_801353DE = 100;
        STATS_GAINS[0] = 50; INITIAL_COMBAT_STATS[0][0] = 100;
        tickPostBattleStatsBox();
        assert(SHOULD_SKIP_BIT_COUNTING == 1 && STATS_GAINS[0] == 0);
        assert(INITIAL_COMBAT_STATS[0][0] == 150 && POST_BATTLE_STATS_TIMER == 0);
        STATS_GAINS[0] = 50;
        TRN_tickPostTrainingStatsBox();
        assert(MAIN_D_80135394 == 1 && STATS_GAINS[0] == 0 && MAIN_D_8013539E == 0);
        STATS_GAINS[0] = 50;
        TRN2_tickPostTrainingStatsBox();
        assert(MAIN_D_801353D4 == 1 && STATS_GAINS[0] == 0 && MAIN_D_801353DE == 0);
        SHOULD_SKIP_BIT_COUNTING = 0;
        UI_BOX_DATA[2].state = 1; BITS_TO_GAIN = 450; MONEY = 100;
        tickBitBox(2);
        assert(SHOULD_SKIP_BIT_COUNTING == 1 && BITS_TO_GAIN == 0 && MONEY == 550);
        /* A held face button must not turn unrelated input into a new press. */
        POLLED_INPUT_PREVIOUS = POLLED_INPUT;
        SHOULD_SKIP_BIT_COUNTING = 0;
        STATS_GAINS[0] = 50;
        tickPostBattleStatsBox();
        assert(SHOULD_SKIP_BIT_COUNTING == 0 && STATS_GAINS[0] == 50);
        /* A new face button works even while its counterpart stays held. */
        POLLED_INPUT |= which ? CONFIRM_BUTTON : CANCEL_BUTTON;
        tickPostBattleStatsBox();
        assert(SHOULD_SKIP_BIT_COUNTING == 1 && STATS_GAINS[0] == 0);
        ++cases;
    }
    /* Port 2 alone cannot dismiss player 1's results. */
    POLLED_INPUT_PREVIOUS = 0; POLLED_INPUT = 0x00400000;
    SHOULD_SKIP_BIT_COUNTING = 0; STATS_GAINS[0] = 50;
    tickPostBattleStatsBox();
    assert(SHOULD_SKIP_BIT_COUNTING == 0 && STATS_GAINS[0] == 50);
    printf("PASS: %u pad combinations across battle stats, bits and both gyms\n", cases);
}
'''
    with tempfile.TemporaryDirectory(prefix='tally-input-') as tmp:
        path = Path(tmp)
        (path / 'check.c').write_text(source)
        subprocess.run(['cc', '-std=gnu99', '-O2', '-Wall', '-Wextra',
                        str(path / 'check.c'), '-o', str(path / 'check')], check=True)
        subprocess.run([str(path / 'check')], check=True)


if __name__ == '__main__':
    main()
