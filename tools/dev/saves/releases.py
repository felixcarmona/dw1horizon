#!/usr/bin/env python3
"""A game saved by any published release must load in every later build (docs/reference/save-format.md "Every release's save").

The corpus, tools/dev/saves/corpus/: one memory card per release, NAME.mcd, holding one rich save (only that file; the
header's title and icon, the game's own bytes, zeroed by `memory_card.py strip`), and NAME.json, what that release wrote in it and
what it held in RAM after a Continue from it. The story state is kept by NAME (`story/mods/<mod>/save.lock`): a later build
must find each flag and variable under the same number.

  releases.py check [--corpus DIR] [--tags HEADER] [--story DIR]
      no emulator (seconds): every card parses with the current tag registry (the patch series, or HEADER) and its extension
      is whole; every record keeps its tag number and name; every story flag and variable keeps its number in the locks
      (the story/ tree, or DIR laid out like it); the card decodes to the values recorded
  releases.py emu DISC.cue --exe EXE [--card NAME] [--port N] [--work DIR] [--story DIR]
      the emulator (PCSX-Redux, headless; ~2 min a card): Continue from each card on DISC, compare RAM with the recorded
      values (screen, partner species, stats and name, money, inventory, bank, cards, roster, options, story flags and
      variables by name), then save again at Jijimon and check the new file: a valid tagged extension holding every record
      of the old one with the same content. EXE is DISC's executable with EXE.elf.map beside it (build/NAME/exe/SLUS_010.32)
  releases.py add DISC.cue --exe EXE --name NAME --version V --commit C --date D [--from CARD] [--port N] [--work DIR]
      the release's own card, made on its disc by the game: a scripted play (Continue from CARD, the options set by the
      save's record, the partner changed with the roster shortcut, values poked, the save written at Jijimon with the screen
      of a new place), then NAME.mcd (stripped) and NAME.json (the file decoded, then a Continue from the stripped card
      read back from RAM)

Exit status 0 when every card passes; a table per card says what was compared.
"""

from pathlib import Path as _DevPath
import sys as _dev_sys
_DEV_ROOT = str(next(p for p in _DevPath(__file__).resolve().parents if (p / "tools").is_dir()))
_dev_sys.path.insert(0, _DEV_ROOT)
_dev_sys.path.insert(0, str(_DevPath(_DEV_ROOT) / "tools"))
import argparse, glob, hashlib, json, os, shutil, struct, subprocess, sys, tempfile, time
from pathlib import Path

T = os.path.dirname(os.path.abspath(__file__))
ROOT = _DEV_ROOT
sys.path.insert(0, os.path.join(ROOT, 'tools'))
from tools.dev import memory_card as mcd  # noqa: E402

CORPUS = os.path.join(T, 'corpus')
SAVE = 'BASLUS-01032DMR0'
JIJIMON = 218                         # Jijimon's house: the save NPC is placed-Digimon slot 0
# the v1 payload (main_menu.c SavegamePayload): scriptState[0x17C] ends where the inventory starts (0x40C)
P_SCRIPT = 0x40C - 0x17C
P_BANK, P_CARDS, P_TRIGGERS, P_PSTATS = P_SCRIPT + 84, P_SCRIPT + 212, P_SCRIPT + 245, P_SCRIPT + 345
SAVED_PSTATS = 0x17C - 345            # pstats 0..34 are in the save
OPTION_NAMES = ['japaneseControls', 'digitalClock', 'frameRate', 'newStatusBars', 'font', 'evolutionGuide', 'newDigimon',
                'language', 'mapSigns', 'extendedStory', 'difficulty', 'quickBattleStart']   # SAVE_TAG_OPTIONS bytes


# ---- the story locks: name -> number ------------------------------------------------------------------------------

def load_locks(story=None):
    """{'profile': ..., 'mods': {mod: {'flags': {name: n}, 'vars': {name: n}}}} from story/ (or a tree laid out like it)."""
    story = story or os.path.join(ROOT, 'story')
    base = json.loads(Path(story, 'story.lock').read_text())
    mods = {'base': dict(flags=base.get('flags', {}), vars=base.get('vars', {}))}
    for f in sorted(glob.glob(os.path.join(story, 'mods', '*', 'save.lock'))):
        d = json.loads(Path(f).read_text())
        mods[os.path.basename(os.path.dirname(f))] = dict(flags=d.get('flags', {}), vars=d.get('vars', {}))
    return dict(profile=base.get('profile', 'tier0'), mods=mods)


def flag_of(n, triggers, story_flags=b''):
    """A story flag's value: trigger n (< 800, the v1 bits) or bit n - 800 of the expanded-story record."""
    bits, i = (triggers, n) if n < 800 else (story_flags, n - 800)
    return (bits[i // 8] >> (i % 8)) & 1 if i // 8 < len(bits) else 0


def var_of(n, profile, pstats, story_vars=b''):
    if profile == 'tier0':
        return pstats[n] if n < len(pstats) else None
    return struct.unpack_from('<i', story_vars, 4 * n)[0] if 4 * n + 4 <= len(story_vars) else 0


# ---- a card as data -----------------------------------------------------------------------------------------------

def read_card(path, name=SAVE):
    """(decoded, payload copy 0, records {tag: bytes}) of the save NAME on the card."""
    data = mcd.Card(path).read(name)
    dec = mcd.decode_save(data)
    size = 0x2000 if len(data) >= 0x6000 else 0x1000
    e = data[0x2000:0x2000 + size] if len(data) >= 0x4000 else b''
    recs = dict(mcd.parse_records(e) or []) if e[:4] == b'DW4E' else {}
    return dec, data[0x200:0x200 + 0xF00], recs


def file_values(path, mods, profile, name=SAVE):
    """What a card holds, as data to compare: the v1 fields, every record decoded by its NAME, the story by name."""
    dec, p, recs = read_card(path, name)
    c0 = dec['copy0']
    v = dict(money=c0['money'], partnerType=c0['partnerType'], player=c0['player'],
             stats=p[0x260:0x290].hex(), roster=p[0x500:0xF00].hex(),
             bank=p[P_BANK:P_BANK + 128].hex(), cards=p[P_CARDS:P_CARDS + 33].hex(),
             records={mcd.TAGS.get(t, f'unknown{t:#06x}'): d.hex() for t, d in recs.items()})
    if 'header_options' in dec: v['headerOptions'] = dec['header_options']['bytes']
    v['story'] = story_values(mods, profile, p[P_TRIGGERS:P_TRIGGERS + 100], p[P_PSTATS:P_PSTATS + SAVED_PSTATS],
                              recs.get(0x8001, b''), recs.get(0x8002, b''))
    return v


def story_values(mods, profile, triggers, pstats, story_flags=b'', story_vars=b''):
    out = {}
    for mod, lk in mods.items():
        out[mod] = dict(flags={k: [n, flag_of(n, triggers, story_flags)] for k, n in sorted(lk['flags'].items())},
                        vars={k: [n, var_of(n, profile, pstats, story_vars)] for k, n in sorted(lk['vars'].items())})
    return out


def card_ok(path, name=SAVE):
    """Problems of the file itself: checksums, the extension's head, records that parse, tags the registry lacks."""
    bad = []
    data = mcd.Card(path).read(name)
    dec = mcd.decode_save(data)
    for k in (0, 1):
        c = dec[f'copy{k}']
        if not (c['checksum_ok'] or c['refuses_original']): bad.append(f'copy{k}: the v1 checksum is wrong')
        e = dec.get(f'ext{k}')
        if not e: bad.append(f'ext{k}: no extension (a {len(data)}-byte file)'); continue
        if e.get('magic') != 'DW4E': bad.append(f'ext{k}: not a tagged extension ({e.get("magic")!r})'); continue
        if e['version'] != 4 or e['size'] != (0x2000 if len(data) >= 0x6000 else 0x1000):
            bad.append(f'ext{k}: invalid version or size')
        if not e['checksum_ok']: bad.append(f'ext{k}: the extension checksum is wrong')
        if not e['matches_v1']: bad.append(f'ext{k}: the extension does not link to its v1 copy (stale)')
        if e['records'] is None: bad.append(f'ext{k}: the records do not parse (no end record)')
    return bad


# ---- the pure-file check ------------------------------------------------------------------------------------------

def compare(rows, what, want, got):
    ok = want == got
    rows.append((ok, what, '' if ok else f'recorded {short(want)}, now {short(got)}'))
    return ok


def short(x, n=90):
    s = json.dumps(x) if not isinstance(x, str) else x
    return s if len(s) <= n else s[:n - 3] + '...'


def story_rows(rows, rec, locks, read):
    """Each recorded story flag/variable by name: the current lock must give it the same number and `read(kind, n)`
    (the card's or RAM's value at that number) must be the recorded value."""
    for mod, kinds in rec.items():
        lk = locks['mods'].get(mod)
        for kind in ('flags', 'vars'):
            bad = []
            for name, (n, val) in kinds[kind].items():
                if lk is None:
                    bad.append(f'{mod}: its save.lock is gone; {name} was {kind[:-1]} {n}'); continue
                now = lk[kind].get(name)
                if now is None:
                    bad.append(f'{mod}.{name} ({kind[:-1]} {n}) is no longer in save.lock: a save keeps {val} there and '
                               f'nothing reads it'); continue
                if now != n:
                    bad.append(f'{mod}.{name} was {kind[:-1]} {n}, save.lock now gives it {now}: a save from this '
                               f'release would read {read(kind, now)} instead of {val}'); continue
                got = read(kind, n)
                if got != val: bad.append(f'{mod}.{name} ({kind[:-1]} {n}): recorded {val}, now {got}')
            rows.append((not bad, f'story {mod} {kind} ({len(kinds[kind])} by name)', '; '.join(bad)))


def check_card(js, card, locks, rows):
    """The pure-file checks of one card."""
    m = json.loads(Path(js).read_text())
    compare(rows, 'card SHA-1', m['sha1'], hashlib.sha1(Path(card).read_bytes()).hexdigest())
    data = mcd.Card(card).read(m.get('save', SAVE))
    compare(rows, 'title and icon stripped', False, any(data[4:0x44] + data[0x60:0x200]))
    for b in card_ok(card): rows.append((False, 'file', b))
    if not any(not ok for ok, w, _ in rows if w == 'file'): rows.append((True, 'file (checksums, extension, records)', ''))
    # every record the release wrote keeps its number and its name
    names = {v: k for k, v in mcd.TAGS.items()}
    bad = []
    for tag, name in m['tags'].items():
        t = int(tag, 16)
        if mcd.TAGS.get(t) != name:
            now = mcd.TAGS.get(t)
            bad.append(f'tag {tag} was {name}, the registry now ' + (f'names it {now}' if now else 'does not have it') +
                       (f' (and {name} is {names[name]:#06x})' if name in names else '') +
                       (': a required record nobody knows makes the save unreadable' if t & 0x8000 and not now else ''))
    rows.append((not bad, f'tag registry ({len(m["tags"])} records)', '; '.join(bad)))
    now = file_values(card, locks['mods'], locks['profile'])
    f = m['file']
    for k in ('money', 'partnerType', 'player', 'stats', 'roster', 'bank', 'cards', 'headerOptions'):
        if k in f:
            want = f[k]
            # Patch 0244's decoder exposes CHEATS as a thirteenth option. Older corpus entries recorded twelve;
            # their missing flag must be off. Compare it too, so a changed flag still fails the gate.
            if k == 'headerOptions' and len(want) == 24 and len(now.get(k, '')) == 26:
                want += '00'
            compare(rows, f'file {k}', want, now.get(k))
    for name, hexv in f['records'].items():
        compare(rows, f'record {name}', hexv, now['records'].get(name))
    _, p, recs = read_card(card)
    trig, pst = p[P_TRIGGERS:P_TRIGGERS + 100], p[P_PSTATS:P_PSTATS + SAVED_PSTATS]
    story_rows(rows, f['story'], locks, lambda kind, n: flag_of(n, trig, recs.get(0x8001, b'')) if kind == 'flags'
               else var_of(n, m.get('profile', 'tier0'), pst, recs.get(0x8002, b'')))


def corpus_entries(corpus):
    manifests = sorted(glob.glob(os.path.join(corpus, '*.json')))
    cards = {p[:-4] for p in glob.glob(os.path.join(corpus, '*.mcd'))}
    paired = {p[:-5] for p in manifests}
    if cards != paired:
        sys.exit(f'{corpus}: unpaired corpus entries: {sorted(cards ^ paired)}')
    if not manifests: sys.exit(f'{corpus}: no cards')
    return manifests


def cmd_check(a):
    if a.tags: mcd.load_tags(a.tags)
    locks = load_locks(a.story)
    cards = corpus_entries(a.corpus)
    failed = 0
    for js in cards:
        rows = []
        try:
            check_card(js, js[:-5] + '.mcd', locks, rows)
        except Exception as e:      # a card the current tools cannot even read
            rows.append((False, 'card', f'{type(e).__name__}: {e}'))
        failed += table(os.path.basename(js[:-5]), rows)
    print(f'{len(cards) - failed} of {len(cards)} cards pass (file check)')
    return 1 if failed else 0


def table(name, rows):
    bad = [r for r in rows if not r[0]]
    print(f'== {name}: {"PASS" if not bad else "FAIL"} ({len(rows) - len(bad)}/{len(rows)})')
    for ok, what, why in rows:
        print(f'  {"ok  " if ok else "FAIL"} {what}' + (f': {why}' if why else ''))
    return 1 if bad else 0


# ---- the emulator -------------------------------------------------------------------------------------------------

class Emu:
    """tools/dev/emulator.py on its own port, symbols from the disc's executable (DW_SYMS: never a build/decomp-* tree that
    somebody may be rebuilding)."""

    def __init__(self, disc, exe, port, work):
        self.disc, self.exe, self.port, self.work = disc, os.path.abspath(exe), port, work
        if not os.path.exists(self.exe + '.elf.map'): sys.exit(f'{self.exe}.elf.map: missing (the executable\'s map)')
        self.env = dict(os.environ, EMU_PORT=str(port), DW_SYMS=self.exe, EMU_ARGS='')
        from tools.dev import symbols as dwsyms
        self.sym = {}
        name = dwsyms.explicit_build(self.exe)
        self.table = dwsyms.table(name)
        self.home = os.path.abspath(os.path.join(work, f'home-{port}'))
        self.env['EMU_HOME'] = self.home

    def run(self, *args, check=True):
        r = subprocess.run([sys.executable, os.path.join(ROOT, 'tools', 'dev/emulator.py'), *args], env=self.env,
                           capture_output=True, text=True)
        if check and r.returncode: raise RuntimeError(f'emulator.py {" ".join(args)}: {r.stderr.strip() or r.stdout.strip()}')
        return r.stdout

    def gs(self, *args):
        return subprocess.run([sys.executable, os.path.join(ROOT, 'tools', 'dev/game_state.py'), *args], env=self.env,
                              capture_output=True, text=True, check=True).stdout

    def A(self, expr):
        n, _, off = expr.partition('+')
        if n not in self.table: raise KeyError(f'{n}: not in {self.exe}.elf.map')
        return self.table[n] + (int(off, 0) if off else 0)

    def has(self, n):
        return n in self.table

    def start(self, card):
        self.run('stop', check=False)
        os.makedirs(self.home, exist_ok=True)
        shutil.copy(card, os.path.join(self.home, 'memcard1.mcd'))
        self.run('start', self.disc, '--keep-cards')

    def stop(self):
        self.run('stop', check=False)

    def ram(self):
        ram = subprocess.run([sys.executable, os.path.join(ROOT, 'tools', 'dev/emulator.py'), 'ramdump'], env=self.env,
                             capture_output=True, check=True).stdout
        if len(ram) != 0x200000: raise RuntimeError('save compatibility tests require original 2 MB RAM')
        return ram

    def peek(self, expr, fmt, ram=None):
        ram = ram or self.ram(); a = self.A(expr) - 0x80000000
        v = struct.unpack_from('<' + fmt, ram, a)
        return v[0] if len(v) == 1 else list(v)

    def raw(self, expr, n, ram):
        a = self.A(expr) - 0x80000000
        return ram[a:a + n]

    def poke(self, expr, data):
        self.run('poke', f'{self.A(expr):#x}', data.hex())

    def press(self, button, frames=10):
        if button in ('CONFIRM', 'CANCEL'):
            japanese = self.has('MOD_OPT_BUTTONS') and self.peek('MOD_OPT_BUTTONS', 'i') != 0
            button = ('CIRCLE' if japanese else 'CROSS') if button == 'CONFIRM' else ('CROSS' if japanese else 'TRIANGLE')
        self.run('press', button, str(frames))

    def api(self, path):
        import urllib.request
        return urllib.request.urlopen(f'http://127.0.0.1:{self.port}{path}', timeout=15).read()

    def chord(self, hold, button, frames=8):
        """`button` pressed while `hold` is held (Select+R1)."""
        self.api(f'/api/v1/lua/press?button={hold}')
        try:
            self.wait(0.2); self.press(button, frames)
        finally:
            self.api(f'/api/v1/lua/release?button={hold}')

    def wait(self, s):
        time.sleep(s)

    def card_out(self):
        return os.path.join(self.home, 'memcard1.mcd')

    def continue_game(self):
        """Title -> CONTINUE -> slot 1 -> game 1 -> yes; poll until the game runs
        (CURRENT_MENU -1) or the card is refused (MEMORY_CARD_ERROR); returns the error (0 = loaded)."""
        # Poll menus: recent bilingual releases may show a language picker before
        # the title, and header IO can outlast a fixed button sequence under load.
        self.wait(35)
        selected = False
        for _ in range(120):
            ram = self.ram()
            menu = self.peek('CURRENT_MENU', 'i', ram)
            ticks = self.peek('MAIN_MENU_TICKS', 'i', ram)
            err = self.peek('MEMORY_CARD_ERROR', 'i', ram)
            if selected and err > 0: return err
            if selected and menu == -1:
                if not self.in_control(): return 'no control after Continue'
                return 0
            if menu == 0 and ticks > 3:
                if self.has('MOD_BOOT_LANGUAGE') and self.peek('MOD_BOOT_LANGUAGE', 'i', ram):
                    self.press('CONFIRM', 4)
                else:
                    pos = self.peek('MENU_HIGHLIGHTS', 'b', ram)
                    if pos != 1: self.press('DOWN' if pos == 0 else 'UP', 4)
                    else:
                        self.press('CONFIRM', 4)
                        selected = True
            elif selected and menu in (0x14, 0x17, 0x18):
                self.press('CONFIRM', 4)
            elif not selected:
                self.press('START', 4)
            self.wait(2)
        return f'the game never started (CURRENT_MENU {menu:#x})'

    def in_control(self, tries=40):
        """Waits for the world with control (no script, tamer free); X closes what a script may have opened."""
        for _ in range(tries):
            ram = self.ram()
            if self.peek('IS_SCRIPT_PAUSED', 'i', ram) == 1 and self.peek('TAMER_STATE', 'b', ram) == 0: return True
            self.press('CONFIRM', 6); self.wait(2)
        return False

    def warp(self, screen, ex=0):
        # A field frame between these writes can replace TARGET_MAP from the current exit.
        # Submit the state transition together, without assuming the state bytes are adjacent.
        self.api('/api/v1/execution-flow?function=pause')
        try:
            self.poke('TAMER_SUB_STATE', b'\0')
            self.poke('TARGET_MAP', struct.pack('<h', screen))
            self.poke('CURRENT_EXIT', bytes([ex]))
            self.poke('TAMER_STATE', bytes([5]))
        finally:
            self.api('/api/v1/execution-flow?function=start')
        for _ in range(30):
            self.wait(1)
            ram = self.ram()
            if self.peek('CURRENT_SCREEN', 'h', ram) == screen and self.peek('TAMER_STATE', 'b', ram) == 0: return True
        return False

    def save_at_jijimon(self, at_confirm=None, register=False):
        """Talk to Jijimon (slot 0 of screen 218) and save to slot 1. `at_confirm(emu)` runs at the last confirm (pokes
        that the file must carry: the screen of another place). With `register`, the battle registration prompt (menu
        0x3E) is answered yes. Returns the menu sequence seen."""
        self.gs('approach', '0')
        self.wait(1); self.press('CONFIRM', 4); self.wait(3)
        seen = []
        for _ in range(12):
            m = self.peek('CURRENT_MENU', 'i')
            seen.append(m)
            if m in (0x45, 0x3E): break
            self.press('CANCEL' if m == 0x3C and not register else 'CONFIRM', 4); self.wait(2)
        if not seen or seen[-1] not in (0x45, 0x3E):
            raise RuntimeError(f'never reached the save confirmation: {seen}')
        if at_confirm: at_confirm(self)
        self.run('shot', os.path.join(self.work, 'confirm.png'))
        self.press('CONFIRM', 4)
        for _ in range(40):
            self.wait(1)
            m = self.peek('CURRENT_MENU', 'i')
            if m == -1: break
            if m in (0x45, 0x3E): self.press('CONFIRM', 12)  # a short wall-time press may miss a logic tick
            if m not in seen[-3:]: seen.append(m)
        if m != -1: raise RuntimeError(f'save did not finish (menu {m:#x})')
        self.wait(2)
        self.run('shot', os.path.join(self.work, 'saved.png'))
        return seen


def ram_values(emu, locks, profile):
    """What the running game holds of a save, by field (the story by name through `locks`)."""
    ram = emu.ram()
    pk = lambda e, f: emu.peek(e, f, ram)
    stats = pk('PARTNER_ENTITY+0x38', '4h4B4B2h')
    v = dict(screen=pk('CURRENT_SCREEN', 'h'), previousScreen=pk('PREVIOUS_SCREEN', 'h'),
             partnerType=pk('PARTNER_ENTITY', 'i'),
             stats=dict(off=stats[0], def_=stats[1], speed=stats[2], brain=stats[3], moves=stats[8:12], hp=stats[12], mp=stats[13]),
             partnerName=emu.raw('PARTNER_ENTITY+0x68', 20, ram).split(b'\0')[0].decode('latin-1'),
             lives=pk('PARTNER_ENTITY+0x7C', 'b'),
             money=pk('MONEY', 'i'), merit=pk('MERIT', 'h'),
             inventory=pk('INVENTORY', '30h'), amounts=pk('INVENTORY+60', '30B'),
             bank=emu.raw('SCRIPT_STATE+84', 128, ram).hex(), cards=emu.raw('SCRIPT_STATE+212', 33, ram).hex(),
             raised=emu.raw('SPECIES_RAISED_BITS', 128, ram).hex(), recruited=emu.raw('SPECIES_RECRUITED_BITS', 128, ram).hex())
    opts = {}
    for k, s in (('japaneseControls', 'MOD_OPT_BUTTONS'), ('digitalClock', 'MOD_OPT_CLOCK'), ('newStatusBars', 'MOD_OPT_BARS'),
                 ('evolutionGuide', 'MOD_OPT_EVO_GUIDE'), ('newDigimon', 'MOD_OPT_NEW_DIGIMON'), ('language', 'MOD_LANG'),
                 ('mapSigns', 'MOD_OPT_SIGNS'), ('extendedStory', 'MOD_OPT_STORY'), ('difficulty', 'MOD_OPT_DIFFICULTY'),
                 ('quickBattleStart', 'MOD_OPT_QUICK_BATTLE'), ('cheats', 'MOD_OPT_CHEATS')):
        if emu.has(s): opts[k] = pk(s, 'i')
    if emu.has('MOD_FONT'): opts['font'] = {0: 1, 1: 0, 2: 2}[pk('MOD_FONT', 'b')]
    if emu.has('MOD_FPS_MODE_RUN'): opts['frameRate'] = {0: 20, 1: 30, 2: 60}[pk('MOD_FPS_MODE_RUN', 'i')]
    v['options'] = opts
    v['roster'] = emu.raw('SAVE_FILE+0x700', 0xA00, ram).hex()
    trig = emu.raw('SCRIPT_STATE+245', 100, ram); pst = emu.raw('SCRIPT_STATE+345', 256, ram)
    sf = emu.raw('STORY_FLAG_BITS', 2048, ram) if emu.has('STORY_FLAG_BITS') else b''
    sv = emu.raw('STORY_VAR_VALUES', 4096, ram) if emu.has('STORY_VAR_VALUES') else b''
    v['story'] = story_values(locks['mods'], profile, trig, pst, sf, sv)
    v['_raw'] = (trig, pst, sf, sv)
    return v


# what a save written again after the load may change: the clock and play time are not records; the poop piles and the
# ground spots picked today move with the time the check spends; the script registers w0.. are scratch for some scripts
RESAVE_DRIFT = {'poopMaps', 'groundPicked', 'groundPickupBits', 'wregs'}


def check_emu(emu, js, card, locks, rows, keep):
    m = json.loads(Path(js).read_text())
    profile = m.get('profile', 'tier0')
    print(f'Continue and resave {os.path.basename(card)}', flush=True)
    emu.start(card)
    try:
        err = emu.continue_game()
        rows.append((err == 0, 'Continue', '' if err == 0 else f'MEMORY_CARD_ERROR {err} (refused)' if isinstance(err, int)
                     else err))
        if err != 0: return
        if emu.has('MOD_OPT_TOUCHED') and emu.peek('MOD_OPT_TOUCHED', 'i'):
            rows.append((False, 'options', 'MOD_OPT_TOUCHED is set before the Continue: the save\'s options were not applied'))
        got = ram_values(emu, locks, locks['profile'])
        trig, pst, sf, sv = got.pop('_raw')
        want = m['ram']
        for k in ('screen', 'previousScreen', 'partnerType', 'stats', 'partnerName', 'lives', 'money', 'merit', 'inventory',
                  'amounts', 'bank', 'cards', 'raised', 'recruited', 'roster'):
            compare(rows, f'RAM {k}', want[k], got[k])
        for k, val in want['options'].items():
            if k in got['options']: compare(rows, f'RAM option {k}', val, got['options'][k])
            else: rows.append((False, f'RAM option {k}', f'recorded {val}; this build has no such setting'))
        story_rows(rows, want['story'], locks, lambda kind, n: flag_of(n, trig, sf) if kind == 'flags' else var_of(n, locks['profile'], pst, sv))
        # the round trip: save again at Jijimon (the loaded screen and place put back at the last confirm)
        here = (got['screen'], got['previousScreen'], emu.raw('TAMER_POSITION_DATA+0x78', 12, emu.ram()))
        if not emu.in_control():
            rows.append((False, 'save again', 'no control in the world after the Continue')); return
        if not emu.warp(JIJIMON):
            rows.append((False, 'save again', f'the warp to Jijimon\'s house ({JIJIMON}) did not arrive')); return
        emu.in_control()

        def put_back(e):
            e.poke('CURRENT_SCREEN', struct.pack('<h', here[0])); e.poke('PREVIOUS_SCREEN', struct.pack('<h', here[1]))
            e.poke('TAMER_POSITION_DATA+0x78', here[2]); e.poke('STORED_TAMER_POS', here[2])

        emu.save_at_jijimon(at_confirm=put_back)
        emu.stop()
        out = os.path.join(keep, os.path.basename(card)[:-4] + '.resaved.mcd')
        shutil.copy(emu.card_out(), out)
        compare(rows, 'saved again: new file written', True, mcd.Card(card).read(SAVE) != mcd.Card(out).read(SAVE))
        bad = card_ok(out)
        rows.append((not bad, 'saved again: the file', '; '.join(bad) or f'{out}'))
        if bad: return
        old = file_values(card, locks['mods'], profile); new = file_values(out, locks['mods'], profile)
        miss = [n for n in old['records'] if n not in new['records']]
        rows.append((not miss, f'saved again: every record kept ({len(old["records"])})', ', '.join(miss) and f'dropped: {", ".join(miss)}'))
        for n, hexv in old['records'].items():
            if n in new['records'] and n not in RESAVE_DRIFT:
                compare(rows, f'saved again: record {n} (old prefix)', hexv, new['records'][n][:len(hexv)])
        for k in ('money', 'partnerType', 'player', 'stats', 'roster', 'bank', 'cards'):
            compare(rows, f'saved again: {k}', old[k], new[k])
        _, p, recs = read_card(out)
        story_rows(rows, m['file']['story'], locks, lambda kind, n: flag_of(n, p[P_TRIGGERS:P_TRIGGERS + 100], recs.get(0x8001, b''))
                   if kind == 'flags' else var_of(n, locks['profile'], p[P_PSTATS:P_PSTATS + SAVED_PSTATS], recs.get(0x8002, b'')))
    finally:
        emu.stop()


def cmd_emu(a):
    if a.tags: mcd.load_tags(a.tags)
    locks = load_locks(a.story)
    work = a.work or os.path.join(ROOT, 'build', 'savetest', 'releases')
    os.makedirs(work, exist_ok=True)
    emu = Emu(a.disc, a.exe, a.port, work)
    cards = corpus_entries(a.corpus)
    if getattr(a, 'card', None): cards = [c for c in cards if os.path.basename(c)[:-5] in a.card]
    if not cards: sys.exit(f'{a.corpus}: no cards')
    failed = 0
    for js in cards:
        rows = []
        try:
            check_emu(emu, js, js[:-5] + '.mcd', locks, rows, work)
        except Exception as e:
            rows.append((False, 'emulator', f'{type(e).__name__}: {e}'))
            emu.stop()
        failed += table(os.path.basename(js[:-5]) + f' on {os.path.basename(a.disc)}', rows)
    print(f'{len(cards) - failed} of {len(cards)} cards pass (emulator, {os.path.basename(a.disc)})')
    return 1 if failed else 0


# ---- a release's own card -----------------------------------------------------------------------------------------

# the rich state of a corpus card (the release's own content; everything here is set by the game itself or poked into
# RAM before the game's own save writes it)
RICH = dict(
    options=dict(japaneseControls=1, digitalClock=0, frameRate=30, newStatusBars=0, font=2, evolutionGuide=0, newDigimon=1,
                 language=1, mapSigns=0, extendedStory=1, difficulty=0, quickBattleStart=0),
    money=123456, merit=321,
    stats=dict(off=432, def_=321, speed=234, brain=345, hp=4321, mp=3210),
    inventory=[(0, 3), (1, 2), (12, 5), (26, 1), (39, 9), (50, 2), (73, 1), (100, 4)],   # (item id, amount)
    bank={12: 50, 3: 7, 45: 2, 88: 1},                                                     # item id: amount kept
    recruited=[3, 4, 23, 46, 49, 181, 188, 260],                                          # some above 180: the wide bits
    raised=[1, 2, 3, 13, 180, 181, 182],
)


def poke_rich(emu, locks, mod, screen):
    """The pokes before the save: money, merit, stats, inventory, bank, roster and raised bits, the story of `mod`
    (every other flag set, its variables 1, 2, ...) and the partner's care reset (it must not beg at the checker's load)."""
    r = RICH
    emu.poke('MONEY', struct.pack('<i', r['money'])); emu.poke('MERIT', struct.pack('<h', r['merit']))
    s = r['stats']
    emu.poke('PARTNER_ENTITY+0x38', struct.pack('<4h', s['off'], s['def_'], s['speed'], s['brain']))
    emu.poke('PARTNER_ENTITY+0x48', struct.pack('<4h', s['hp'], s['mp'], s['hp'], s['mp']))
    inv = r['inventory'] + [(-1, 0)] * (30 - len(r['inventory']))
    emu.poke('INVENTORY', struct.pack('<30h', *[t for t, _ in inv])); emu.poke('INVENTORY+60', bytes(n for _, n in inv))
    bank = bytearray(emu.raw('SCRIPT_STATE+84', 128, emu.ram()))
    for i, n in r['bank'].items(): bank[i] = n
    emu.poke('SCRIPT_STATE+84', bytes(bank))
    for sym, ids in (('SPECIES_RECRUITED_BITS', r['recruited']), ('SPECIES_RAISED_BITS', r['raised'])):
        bits = bytearray(emu.raw(sym, 128, emu.ram()))
        for i in ids: bits[i // 8] |= 1 << (i % 8)
        emu.poke(sym, bytes(bits))
    lk = locks['mods'][mod]
    trig = bytearray(emu.raw('SCRIPT_STATE+245', 100, emu.ram()))
    trig[0] |= 1 << 5  # unlock the VS registration prompt
    for species in r['recruited']:
        if species < 66:
            n = 200 + species
            trig[n // 8] |= 1 << (n % 8)
    emu.poke('SCRIPT_STATE+346', bytes([10]))  # File City's prosperity
    for k, (name, n) in enumerate(sorted(lk['flags'].items(), key=lambda x: x[1])):
        if n < 800:
            if k % 2 == 0: trig[n // 8] |= 1 << (n % 8)
            else: trig[n // 8] &= ~(1 << (n % 8))
    emu.poke('SCRIPT_STATE+245', bytes(trig))
    for k, (name, n) in enumerate(sorted(lk['vars'].items(), key=lambda x: x[1])):
        emu.poke(f'SCRIPT_STATE+{345 + n}', bytes([k + 1]))
    emu.gs('set', 'partner.para.foodLevel=100', 'partner.para.energyLevel=100', 'partner.para.poopLevel=0',
           'partner.para.tiredness=0', 'partner.para.discipline=90', 'partner.para.happiness=90',
           'partner.para.sleepyHour=23', 'partner.para.wakeupHour=1', 'partner.para.nextHungerHour=23', 'hour=10')
    emu.gs('set', 'partner.para.condition=0')


def disc_sha1(path):
    if path.lower().endswith('.cue'):
        import re
        match = re.search(r'FILE\s+"([^"]+)"', Path(path).read_text(), re.I)
        if not match: raise ValueError(f'{path}: no FILE in cue')
        path = os.path.join(os.path.dirname(path), match.group(1))
    h = hashlib.sha1()
    with open(path, 'rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''): h.update(block)
    return h.hexdigest()


def cmd_add(a):
    if a.tags: mcd.load_tags(a.tags)
    if os.path.exists(os.path.join(a.corpus, a.name + '.json')) or os.path.exists(os.path.join(a.corpus, a.name + '.mcd')):
        sys.exit(f'{a.name}: already recorded; corpus entries are immutable')
    if glob.glob(os.path.join(a.corpus, '*.json')) or glob.glob(os.path.join(a.corpus, '*.mcd')):
        if cmd_check(a) or cmd_emu(a):
            sys.exit('existing release cards must pass before adding this release')
    locks = load_locks(a.story)
    work = a.work or os.path.join(ROOT, 'build', 'savetest', 'add-' + a.name)
    os.makedirs(work, exist_ok=True)
    emu = Emu(a.disc, a.exe, a.port, work)
    o = RICH['options']
    try:
        # 1. a save of this release to start from: Continue from CARD and save at Jijimon (a v4 file of this build)
        print('Continue from seed card', flush=True)
        emu.start(a.from_card)
        if emu.continue_game() != 0: sys.exit(f'{a.from_card}: the Continue failed')
        if not emu.in_control() or not emu.warp(JIJIMON):
            sys.exit('cannot reach Jijimon for the initial save')
        emu.in_control(); emu.save_at_jijimon(); emu.stop()
        first = os.path.join(work, 'first.mcd'); shutil.copy(emu.card_out(), first)
        if card_ok(first): sys.exit(f'{first}: {card_ok(first)}')
        # 2. the options: the save's own record (the game applies it at the Continue, as a player's settings)
        subprocess.run([sys.executable, os.path.join(ROOT, 'tools', 'dev/memory_card.py'), 'settag', first, SAVE, '0x0009',
                        bytes(o[k] for k in OPTION_NAMES).hex()], check=True, capture_output=True)
        # 3. Continue, the partner changed with the roster shortcut until it is a species from another game
        print('Continue with non-default options', flush=True)
        emu.start(first)
        if emu.continue_game() != 0: sys.exit(f'{first}: the Continue with the options failed')
        emu.in_control()
        for _ in range(a.partner_presses):
            emu.chord('SELECT', 'R1')
            emu.wait(4)
            emu.in_control()
        species = emu.peek('PARTNER_ENTITY', 'i')
        print(f'partner species {species}', flush=True)
        if species < 180: sys.exit('the fixture needs an imported partner; increase --partner-presses')
        # 4. the new place: its screen and a spot of it, read by going there
        if not emu.warp(a.screen): sys.exit(f'cannot reach screen {a.screen}')
        emu.in_control()
        ram = emu.ram()
        there = (emu.peek('CURRENT_SCREEN', 'h', ram), emu.peek('PREVIOUS_SCREEN', 'h', ram),
                 emu.raw('TAMER_POSITION_DATA+0x78', 12, ram))
        emu.run('shot', os.path.join(work, 'place.png'))
        emu.warp(JIJIMON); emu.in_control()
        poke_rich(emu, locks, a.mod, there[0])

        def place(e):
            e.poke('CURRENT_SCREEN', struct.pack('<h', there[0])); e.poke('PREVIOUS_SCREEN', struct.pack('<h', there[1]))
            e.poke('TAMER_POSITION_DATA+0x78', there[2]); e.poke('STORED_TAMER_POS', there[2])

        seen = emu.save_at_jijimon(at_confirm=place, register=True)
        print('menus', [hex(m & 0xFFFFFFFF) for m in seen])
        emu.stop()
        rich = os.path.join(work, 'rich.mcd'); shutil.copy(emu.card_out(), rich)
        if card_ok(rich): sys.exit(f'{rich}: {card_ok(rich)}')
        # 5. the corpus card and what this release reads back from it
        candidate = tempfile.mkdtemp(prefix='candidate-', dir=work)
        card = os.path.join(candidate, a.name + '.mcd')
        subprocess.run([sys.executable, os.path.join(ROOT, 'tools', 'dev/memory_card.py'), 'strip', rich, SAVE, '-o', card], check=True)
        print('Continue from stripped candidate', flush=True)
        emu.start(card)
        err = emu.continue_game()
        if err != 0: sys.exit(f'{card}: the stripped card does not load ({err})')
        got = ram_values(emu, locks, locks['profile']); got.pop('_raw')
        checks = []
        compare(checks, 'fixture screen', a.screen, got['screen'])
        compare(checks, 'fixture imported partner', species, got['partnerType'])
        compare(checks, 'fixture bits', RICH['money'], got['money'])
        compare(checks, 'fixture stats', RICH['stats'], {k: got['stats'][k] for k in RICH['stats']})
        compare(checks, 'fixture inventory', [i for i, _ in RICH['inventory']], got['inventory'][:len(RICH['inventory'])])
        for k, val in got['options'].items():
            compare(checks, f'fixture option {k}', RICH['options'][k], val)
        _, _, saved_records = read_card(card)
        registered = saved_records.get(5, b'')
        checks.append((any(registered), 'fixture VS registration', ''))
        if table(a.name + ' richness', checks): sys.exit('fixture missing required rich state')
        emu.stop()
        _, _, recs = read_card(card)
        m = dict(sha1=hashlib.sha1(Path(card).read_bytes()).hexdigest(), release=dict(version=a.version, commit=a.commit, date=a.date, disc=os.path.basename(a.disc), disc_sha1=disc_sha1(a.disc)),
                 made=f'releases.py add: a Continue from {os.path.basename(a.from_card)}, OPTIONS from the save\'s record, '
                      f'the partner by Select+R1, pokes ({", ".join(k for k in RICH if k != "options")}, the story of '
                      f'{a.mod}), the game\'s save at Jijimon with the screen of {there[0]} put at the last confirm',
                 save=SAVE, profile=locks['profile'],
                 tags={f'{t:#06x}': mcd.TAGS.get(t, f'unknown{t:#06x}') for t in recs},
                 file=file_values(card, {a.mod: locks['mods'][a.mod]}, locks['profile']),
                 ram=got)
        m['ram']['story'] = {a.mod: got['story'][a.mod]}
        js = os.path.join(candidate, a.name + '.json')
        Path(js).write_text(json.dumps(m, indent=1) + '\n')
        rows = []
        check_card(js, card, locks, rows)
        check_emu(emu, js, card, locks, rows, work)
        if table(a.name, rows): sys.exit('candidate failed; corpus unchanged')
        os.makedirs(a.corpus, exist_ok=True)
        shutil.copy(card, os.path.join(a.corpus, a.name + '.mcd'))
        shutil.copy(js, os.path.join(a.corpus, a.name + '.json'))
        shutil.rmtree(candidate)
        print(f'{card} and {a.name}.json: screen {got["screen"]}, partner {got["partnerType"]}, money {got["money"]}')
    finally:
        emu.stop()


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='cmd', required=True)
    for n in ('check', 'emu', 'add'):
        p = sub.add_parser(n)
        p.add_argument('--corpus', default=CORPUS)
        p.add_argument('--story', help='a tree laid out like story/ (story.lock, mods/*/save.lock): the locks to check against')
        p.add_argument('--tags', help='the tag registry from this save_tags.h (default: the patch series)')
        if n == 'check': continue
        p.add_argument('disc'); p.add_argument('--exe', required=True, help="the disc's executable (EXE.elf.map beside it)")
        p.add_argument('--port', type=int, default=38231); p.add_argument('--work')
        if n == 'emu':
            p.add_argument('--card', action='append', help='only these cards (by name)')
        else:
            p.add_argument('--name', required=True); p.add_argument('--version', required=True)
            p.add_argument('--commit', required=True); p.add_argument('--date', required=True)
            p.add_argument('--from', dest='from_card', default=os.path.join(ROOT, 'build', 'states', 'file-city.mcd'))
            p.add_argument('--mod', default='what-the-island-forgot', help='the story mod whose state the card carries')
            p.add_argument('--screen', type=int, default=300, help='the new place the save is made at')
            p.add_argument('--partner-presses', type=int, default=3, help='Select+R1 presses (the roster backwards)')
    a = ap.parse_args()
    sys.exit(dict(check=cmd_check, emu=cmd_emu, add=cmd_add)[a.cmd](a))


if __name__ == '__main__':
    main()
