"""The settings of the decompilation tree ($W) that change derived bytes, captured once into exe-facts.json.

The player has no $W: make-release ships exe-facts.json and every step reads its settings from it (finding 9 of
tools/derive/README.md). Each fact is what tools/build-full.sh reads from the tree today, with the line:

  ground_pickup_max        MOD_GROUND_PICKUP_MAX of include/dw/item.h (patch 0265); 0 on older targets
  cold_anim                COLD_ANIM_FLAG in include/dw/species.h (:92; the build's COLD=1 unless COLD is set)
  partner_mmd_max_8mb      PARTNER_MMD_MAX_8MB of include/dw/memmap.h (:153 SPECIES_RAM_MB=8, :169), or null
  evl_shard_scratch_size   EVL_SHARD_SCRATCH_SIZE of include/dw/evl.h (:175), or null (an older tree: 5436 + a warning)
  maphead_script_max       MAPHEAD_SCRIPT_MAX of include/dw/memmap.h (:197), or null (an older tree: 0x6800)
  font_glyphs              NUM_EXTRA_GLYPHS of src/main/font_extra.h (:201), 0 without it
  makefile_font            FONT ?= of the Makefile (:203; FONT given to the build wins), or null
  file_table_dgorig        "DGORIG.SCN" in src/main/file_table_us.c (:210, ORIG)
  mod_story_file           modStoryFile in src/main/mod_options.c (:219, ALT)
  file_table_scrn          "SCRN.DAT" in src/main/file_table_us.c (:275, SCRN)
  overlays                 the overlay list of mk/version/us.mk (:445) and MENU (OVERLAY += MENU, :446)
  file_table               every name of FILE_OFFSET_TABLE (newfiles.py plan --table, :462) with its size
  makefile_lang_files      LANG_FILES ?= in the Makefile (:468)
  makefile_new_files       NEW_FILES ?= in the Makefile (:471)
  file_offset_table        FILE_OFFSET_TABLE's offset in SLUS_010.32 (the address in the tree's linker map - 0x80090000,
                           as dwpatch's table_offset), or null without a map: no derived byte, the patcher's (make-release
                           checks it against the image; build-full.sh captures the facts again after the executable)
check only (nothing derived changes with them):
  sound_staging_max        SOUND_STAGING_MAX of include/dw/memmap.h (:246; 0x3E000 without it)
  npc_stage_max            field scratch capacity for compaction before heap allocation (0 without staging)
  npc_anim_keep            exact animation slots compiled for each original species
  heap_total               the malloc3 heap of the tree's last build (DW_HEAP_MAP, :89; membudget.heap_total_now), or null

ORIG, ALT and SCRN are not stored: they also depend on the recipe (TEXT, EXTRA_STORY, FONT), so the steps work them
out from these facts (as the bash does).
"""
import json
import os
import re

FORMAT = 1


def _read(w, rel):
    try:
        with open(os.path.join(w, rel), encoding='utf-8', errors='replace') as f:
            return f.read()
    except OSError:
        return None


def _define(text, name):
    if text is None:
        return None
    m = re.search(r'^#define[ \t]+' + name + r'[ \t]+(0x[0-9A-Fa-f]+|\d+)', text, re.M)
    return int(m.group(1), 0) if m else None


def npc_keep(text):
    """Capture the compiled animation masks, including story-specific additions."""
    if not text:
        return None
    masks = re.search(r'NPC_ANIM_KEEP_MASKS\[\d+\]\[2\] = \{(.*?)\};', text, re.S)
    index = re.search(r'NPC_ANIM_KEEP_INDEX\[\w+\] = \{(.*?)\};', text, re.S)
    if not masks or not index:
        raise ValueError('cannot read target NPC animation masks')
    words = [tuple(int(x, 16) for x in pair) for pair in
             re.findall(r'\{\s*(0x[0-9A-Fa-f]+),\s*(0x[0-9A-Fa-f]+)\s*\}', masks[1])]
    ids = [int(x) for x in re.findall(r'\b(\d+)\s*,', re.sub(r'/\*.*?\*/', '', index[1], flags=re.S))]
    return [[slot for slot in range(64) if words[i][slot // 32] >> (slot % 32) & 1] for i in ids]


def capture(w, heap_map=None):
    memmap = _read(w, 'include/dw/memmap.h')
    makefile = _read(w, 'Makefile') or ''
    table = _read(w, 'src/main/file_table_us.c') or ''
    usmk = _read(w, 'mk/version/us.mk') or ''
    font = re.search(r'^FONT \?= ([a-z]*)', makefile, re.M)
    entries = re.findall(r'\{\s*0x[0-9a-fA-F]+,\s*(0x[0-9a-fA-F]+),\s*"([^"]+)"\s*\}', table)
    heap = None
    hm = heap_map if heap_map is not None else os.path.join(w, 'build/us/psx/gcc/SLUS_010.32.elf.map')
    if os.path.isfile(hm):
        import sys
        sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
        import membudget
        heap = membudget.heap_total_now(hm)
    fot = None
    exe_map = os.path.join(w, 'build/us/psx/gcc/SLUS_010.32.elf.map')
    if os.path.isfile(exe_map):
        m = re.search(r'^\s+(0x[0-9a-f]+)\s+FILE_OFFSET_TABLE\s*$', open(exe_map).read(), re.M)
        fot = int(m.group(1), 16) - 0x80090000 if m else None
    return {
        'format': FORMAT,
        'file_offset_table': fot,
        'ground_pickup_max': _define(_read(w, 'include/dw/item.h'), 'MOD_GROUND_PICKUP_MAX') or 0,
        'cold_anim': 'COLD_ANIM_FLAG' in (_read(w, 'include/dw/species.h') or ''),
        'partner_mmd_max_8mb': _define(memmap, 'PARTNER_MMD_MAX_8MB'),
        'evl_shard_scratch_size': _define(_read(w, 'include/dw/evl.h'), 'EVL_SHARD_SCRATCH_SIZE'),
        'maphead_script_max': _define(memmap, 'MAPHEAD_SCRIPT_MAX'),
        'font_glyphs': _define(_read(w, 'src/main/font_extra.h'), 'NUM_EXTRA_GLYPHS') or 0,
        'makefile_font': font.group(1) if font else None,
        'file_table_dgorig': '"DGORIG.SCN"' in table,
        'mod_story_file': 'modStoryFile' in (_read(w, 'src/main/mod_options.c') or ''),
        'file_table_scrn': '"SCRN.DAT"' in table,
        'overlays': sorted(set(re.findall(r'^\$\(eval \$\(call overlay,([A-Z0-9]*),', usmk, re.M))),
        'overlay_menu': bool(re.search(r'^OVERLAY \+= MENU', usmk, re.M)),
        'file_table': {name: int(size, 16) for size, name in entries if name != 'NULL'},
        'makefile_lang_files': bool(re.search(r'^LANG_FILES \?=', makefile, re.M)),
        'makefile_new_files': bool(re.search(r'^NEW_FILES \?=', makefile, re.M)),
        'sound_staging_max': _define(memmap, 'SOUND_STAGING_MAX'),
        'heap_total': heap,
        'npc_stage_max': _define(memmap, 'NPC_STAGE_MAX') or 0,
        'npc_anim_keep': npc_keep(_read(w, 'src/main/npc_anim_keep.c')),
    }


def save(facts, path):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, 'w') as f:
        json.dump(facts, f, indent=1, sort_keys=True)
        f.write('\n')


def load(path):
    with open(path) as f:
        facts = json.load(f)
    if facts.get('format') != FORMAT:
        raise SystemExit(f'{path}: exe facts format {facts.get("format")}, this derive reads {FORMAT}')
    return facts


def sound_staging_max(facts):
    v = facts.get('sound_staging_max')
    return 0x3E000 if v is None else v
