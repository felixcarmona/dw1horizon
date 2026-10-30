"""The command registry: one description of every engine instruction, from which DWS gets a typed
command for each opcode (so nothing needs `asm()`), the decompiler gets its vocabulary and the
coverage report its counts.

Every opcode of the interpreter (tools/dws/bytecode/__main__.py OPS) is a command named like its mnemonic in lower
case: `entity_walk_to(5, 100, -20, 0, 0)`, `set_obj_visibility(3, 1)`. The operand kinds come from the
field types of bytecode:
  p pstat (`p7` or a declared var)      t trigger (a number or a declared flag)    l label (a name)
  e entity (tamer, partner, camera, a number, an npc)   i item("..")  d species("..")  v tech("..")
  m M m16 screen   s script   S section   k16 card   w wide register (`w3`)   c comparison ("==")
  u8 u16 s16 s32 numbers
Instructions with a body of their own (IF, SET_SELECTION, SHOW_TEXTBOX, SWITCH, DATA, the jumps) have
statements: `unless (cond) goto L;`, `set_selection(L1, L2, text("a"), text("b"))`,
`show_textbox(text("a"), text("b"))`, `switch(p7, L1, L2)`, `data(1, 2, 3)`, `goto L;`, `gosub L;`.

CALL_ROUTINE numbers have names (ROUTINES): `call_routine(routine("choose_item"))`."""
import os, sys
from dws import bytecode

# statements that are not plain "NAME a, b" commands
SPECIAL_OPS = {'IF', 'SET_SELECTION', 'END_SELECTION', 'SHOW_TEXTBOX', 'SWITCH', 'SWITCH_W', 'DATA'}

# CALL_ROUTINE n (docs/data/story-analysis/c-routines.csv); None = reserved no-op
ROUTINES = {
    0x00: 'choose_item', 0x01: 'merit_shop', 0x02: 'mojyamon_trade', 0x03: None, 0x04: None, 0x05: None,
    0x06: 'start_tournament', 0x07: 'training', 0x08: 'shop', 0x09: 'jukebox', 0x0A: 'birdramon_taxi',
    0x0B: 'item_keeper', 0x0C: 'remove_chosen_item', 0x0D: 'remove_all_chosen_item', 0x0E: 'card_shop',
    0x0F: 'show_bits_box', 0x10: 'close_box2', 0x11: None, 0x12: 'tournament_calendar', 0x13: 'dirt_cart_model',
    0x14: 'dirt_pile_shrink', 0x15: 'reset_object_animation', 0x16: 'check_tournament_medal',
    0x17: 'open_chest_tray', 0x18: 'close_chest_tray', 0x19: 'save_clock_speed', 0x1A: 'load_dirt_cart',
    0x1B: 'load_dirt_pile', 0x1C: 'monochromon_mood_bubble', 0x1D: 'egg_choice', 0x1E: 'shopvar_clear',
    0x1F: 'shopvar_add', 0x20: 'naming_and_intro', 0x21: 'register_cup22', 0x22: 'meramon_shake',
    0x23: 'load_shop_library', 0x24: 'reload_map_tfs', 0x25: 'remove_fog', 0x26: 'ninjamon_effect',
    0x27: 'load_training_library', 0x28: 'machinedramon_buildup', 0x29: 'spawn_gearbox',
    0x2A: 'toytown_select_box', 0x2B: 'spawn_toytown_boxes', 0x2C: 'open_toytown_box', 0x2D: 'fade_to_white',
    0x2E: 'fade_from_white', 0x2F: 'lost_all_lives', 0x30: 'save_machine', 0x31: 'spawn_angemon_pedestal',
    0x32: 'raise_angemon_pedestal', 0x33: 'load_ending_boss', 0x34: 'load_ending', 0x35: 'start_ending',
    0x36: 'game_clear_save', 0x37: 'loop_once', 0x38: 'shopvar_store',
}
ROUTINE_BY_NAME = {n: k for k, n in ROUTINES.items() if n}

# CALL_DIGIMON_ROUTINE n
DIGIMON_ROUTINES = {0: 'toilet', 1: 'curling', 2: 'revert_sukamon', 3: 'dying_a', 4: 'dying_b', 5: 'opening',
                    6: 'ending', 7: 'sickness_death', 8: 'machinedramon_appears', 9: 'battle_death',
                    10: 'forced_evolution'}
DIGIMON_ROUTINE_BY_NAME = {n: k for k, n in DIGIMON_ROUTINES.items()}


class Cmd:
    __slots__ = ('name', 'mnemonic', 'op', 'fields')

    def __init__(self, name, mnemonic, op, fields):
        self.name, self.mnemonic, self.op, self.fields = name, mnemonic, op, fields

    def __repr__(self):
        return f'Cmd({self.name}, {self.fields})'


def build():
    cmds = {}
    for op, (mn, fmt) in bytecode.OPS.items():
        if mn in SPECIAL_OPS: continue
        fields = [f for f in fmt.split() if f != '_']
        cmds[mn.lower()] = Cmd(mn.lower(), mn, op, fields)
    return cmds


COMMANDS = build()
# instructions that are statements of the language, not commands
STATEMENT_OPS = {'JUMP_TO': 'goto', 'JUMP_AND_LINK': 'gosub', 'IF': 'unless', 'END_SECTION': 'end_section'}
for _m in ('JUMP_TO', 'JUMP_AND_LINK'):      # still reachable as commands: jump_to(L), jump_and_link(L)
    pass


def by_mnemonic(mn):
    return COMMANDS.get(mn.lower())


# Opcodes that had a typed DWS statement before the registry (milestone 1): used by the coverage report
# to say what the language could express without asm().
BEFORE = {
    'SET_DIALOG_OWNER', 'SHOW_TEXTBOX', 'SET_SELECTION', 'END_SELECTION', 'IF', 'JUMP_TO', 'END_SECTION',
    'GIVE_ITEM', 'REMOVE_ITEM', 'ADD_MONEY', 'REDUCE_MONEY', 'ADD_MERIT', 'GIVE_CARD', 'LEARN_MOVE', 'SET_BGM',
    'PLAY_SOUND', 'WARP_TO', 'DELAY', 'PLAY_ANIMATION', 'ENTITY_LOOK_AT_ENTITY', 'ENTITY_SET_ROTATION',
    'FADEOUT_HUD', 'SET_TRIGGER', 'UNSET_TRIGGER', 'UNLOAD_ENTITY', 'ENTITY_WALK_TO', 'ENTITY_WALK_TO_WITH_CAMERA',
    'WAIT_FOR_ENTITY', 'MOVE_CAMERA_TO', 'MOVE_CAMERA_TO_ENTITY', 'START_BATTLE', 'LOAD_DIGIMON', 'SET_DIGIMON',
    'SET_PSTAT', 'ADD_TO_PSTAT', 'REDUCE_PSTAT', 'STORE_DATE', 'STORE_DIGIMON_TYPE', 'STORE_RANDOM',
}
# IF clause kinds the old conditions could write
BEFORE_CLAUSES = {'trigger', 'not trigger', 'pstat', 'item', 'money', 'stat'}
