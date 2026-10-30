"""`dws slots SCREEN`: what a writer needs before `npc(..., slot=, at=)`, `take_over(...)` or `warp(SCREEN, entry=)`: the
screen's NPC slots (species, base name, position), the slot a new NPC goes in, and the entries a warp can arrive at."""
import os
from .. import backend as BE
from . import naming as N

ROOT = BE.ROOT


def resolve(arg):
    """A screen number or a Screen member name -> screen id."""
    if str(arg).isdigit(): return int(arg)
    inv = {m: i for i, m in N.screen_members().items()}
    name = str(arg).split('.')[-1]
    if name not in inv: raise ValueError(f'no screen "{arg}" (a number, or a Screen member such as jijimons_house)')
    return inv[name]


def run(arg, out=print):
    import dwmap
    from .lower import base_npcs
    screen = resolve(arg)
    names, by = N.disc_screens()
    member = N.screen_members().get(screen)
    sid = next((s for s, ss in by.items() if screen in ss), None)
    out(f'screen {screen} {names.get(screen, "")}: Screen.{member}' +
        (f', script {sid}, module dw.base.{member}' if sid is not None else ' (no script of the game loads it)'))
    ent_name = {e: nm for nm, (e, _) in base_npcs(sid).items()} if sid is not None else {}
    sp = N.enum_members('species')
    slots = BE.screen_slots(screen)
    out('NPC slots (the base\'s; to own one: take_over(name)):' if slots else 'no NPC slots in its .MAP')
    for d in slots:
        nm = ent_name.get(d['entity'])
        out(f'  slot {d["slot"]}: {sp.get(d["species"], d["species"])} at ({d["x"]}, {d["z"]})' + (f', `{nm}`' if nm else '')
            + ('' if d['entity'] == 5 + d['slot'] else f' (entity {d["entity"]})'))
    if BE.MAP_FLAGS.get(screen, 0) & 0x80:
        n = BE.next_free_slot(screen)
        if n <= 7: out(f'a new NPC goes in slot {n} (npc(..., at=(x, z)) takes it; the next ones {n + 1}, {n + 2}...: the new NPCs '
                       f'of the mods compiled together, in their order; slots 0-7 on the original engine, 0-15 on the story-state engine)')
        else: out(f'slots 0-7 are all used: a new NPC goes in slot {n} only with the story-state engine (slots 0-15; check --exe story-state)')
        if sid is not None and n <= 15:
            from .lower import Claims
            sec, why = Claims().talk_section(sid, by[sid], n, None)
            if why: out(f'  it answers on talk section {sec} (not {5 + n}: {why})')
        heap_room(screen, out)
    else:
        out('this screen does not read its NPC list from the .MAP (MAP_ENTRIES flags lack 0x80): no new NPCs here')
    src = BE.map_source(screen)
    if src:
        m = dwmap.MapFile(open(os.path.join(ROOT, src), 'rb').read())
        out('a new NPC stands (at=(x, z)) on a walkable tile: ' + BE.walk_hint(screen, m).replace('; python3', ';\n  python3', 1))
        out('entries (warp(Screen.%s, entry=k) arrives there):' % member)
        for k, w in enumerate(m.warps):
            if not dwmap.warp_used(w): continue
            tgt = f'its exit tiles lead to screen {w["targetMap"]} entry {w["targetExit"]}' if w['targetMap'] >= 0 else 'arrival only (the script makes the way out)'
            out(f'  entry {k}: ({w["x"]}, {w["z"]}); {tgt}')
        for kind, lo, hi, what in (('step', 51, 79, 'when the tamer steps on one of its tiles'), ('use', 80, 109, 'when the tamer presses CROSS standing on one')):
            tiles = {}
            for j, v in enumerate(m.collision):
                if lo <= v <= hi: tiles.setdefault(v - lo, []).append(j)
            if not tiles: out(f'no {kind} triggers (on_{kind}(t) needs one of the map)'); continue
            out(f'{kind} triggers (@screen.on_{kind}(t) runs {what}):')
            for t, js in sorted(tiles.items()):
                x, z = dwmap.tile_to_world(js[0] % 100, js[0] // 100)
                out(f'  {kind} {t}: {len(js)} tile{"s" if len(js) != 1 else ""}, the first at ({x}, {z})')
    return 0


def margins(screen, slot, kinds, story_state=False):
    """{species: heap margin in bytes} if one more Digimon of that species stood in `slot` of `screen`, measured as `check`
    measures it (membudget.screen_budget of the screen's setup with the new LOAD_DIGIMON/SET_DIGIMON on every path: the
    worst path, the temporary texture, the instance data) against the heap available there. -> (margins, budget)"""
    import membudget
    b = membudget.screen_budget(screen, sweep_csv=os.devnull) if story_state else membudget.screen_budget(screen)    # (as backend.place_digimon)
    out = {}
    for t in kinds:
        peak = max(membudget.path_cost(tuple(dict.fromkeys((t,) + c['loads'])), c['sets'] + ((t, slot),))['peak'] for c in b['paths'])
        out[t] = b['available'] - peak
    return out, b


def heap_room(screen, out):
    """The screen's heap left for one more Digimon (in its next free slot), on the original engine and on the story-state engine:
    which of the game's species fit there, measured as `check` measures it, and the ones already on the screen (their model
    is loaded once: another one costs its instance data only)."""
    import membudget
    sp = N.enum_members('species')
    kinds = sorted({d for d, nm in sp.items() if d < 180 and not nm[-1].isdigit() and BE.model_size(d)})
    slot = BE.next_free_slot(screen)
    try:
        m0, b0 = margins(screen, slot, kinds)
    except Exception as e:                                       # (no measurement and no estimate for this screen)
        out(f'heap: unknown here ({e})'); return
    m2 = None
    if os.path.exists(os.path.join(ROOT, BE.STORY_STATE_EXE_DIR, 'SLUS_010.32.elf.map')):
        saved = membudget.HEAP_FOR_NPCS, membudget.TRIMMED
        try:
            membudget.HEAP_FOR_NPCS = BE.story_state_heap()
            membudget.TRIMMED = os.path.exists(os.path.join(ROOT, 'build/decomp-story-state/src/main/npc_anim_trim.c'))
            m2, _ = margins(screen, slot, kinds, story_state=True)
        except Exception: m2 = None
        finally: membudget.HEAP_FOR_NPCS, membudget.TRIMMED = saved
    here = sorted({t for c in b0['paths'] for t in c['types']} & set(kinds))
    out(f'heap ({"measured" if b0["measured"] else "estimated"}, as `check` tests it: the setup with one more Digimon in slot {slot}, on its '
        f'worst path): {max(b0["margin"], 0) // 1024} KB free now on the original engine')
    for label, m in (('original engine', m0), ('story-state engine', m2)):
        if m is None: continue
        new = [t for t in kinds if t not in here]
        fit = sorted((t for t in new if m[t] >= 0), key=lambda t: (BE.model_size(t), sp[t]))[-4:]
        big = sorted((t for t in new if m[t] < 0), key=lambda t: (BE.model_size(t), sp[t]))[:4]
        out(f'  ({label}) the largest that fit: {", ".join(f"{sp[t]} {BE.model_size(t) // 1024} KB" for t in fit) or "none"}'
            + (f'; too big: {", ".join(f"{sp[t]} {BE.model_size(t) // 1024} KB" for t in big)}...' if big else ''))
    if here:
        out('  already on this screen (its model is loaded once: another one costs a few KB of instance data): '
            + ', '.join(f'{sp[t]}' + ('' if m0[t] >= 0 else ' (no room even so)') for t in here))
    out('  python3 tools/dws.py check says it for yours')
