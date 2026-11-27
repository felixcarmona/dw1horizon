#!/usr/bin/env python3
"""Horizon Patcher, the desktop app: the four discs, the release package, Build (docs/patcher.md, "The desktop app").

    python3 tools/patcher/gui.py                 # from a checkout (Python 3.10+ with tkinter)
    python3 tools/patcher/gui.py --self-test     # what CI runs on the frozen app (no window, no discs)

The frozen app (PyInstaller, tools/patcher/app/build.py) starts here too: multiprocessing's children and the Python
processes dwpatch starts come back through this file (desktop.python_shim) before any window is made.
"""
import multiprocessing
import os
import sys

def _trace(what):
    """HORIZON_TRACE=FILE: each start of the app (the window, derive, its workers) writes a line there."""
    if os.environ.get('HORIZON_TRACE'):
        with open(os.environ['HORIZON_TRACE'], 'a', encoding='utf-8') as f:
            f.write(f'{os.getpid()} {what} {sys.argv[1:4]!r}\n')


if __name__ == '__main__':
    _trace('start')
    multiprocessing.freeze_support()                     # (a frozen spawn child runs its work and exits here)
    _trace('past freeze_support')
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import desktop as _desktop
    _desktop.use_real_temp()                             # (before any work folder is made, in every process)
    _code = _desktop.python_shim()
    if _code is not None:
        sys.exit(_code)

import json
import queue
import threading
import time
import traceback

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import desktop  # noqa: E402

LANGS = dict(en='English', es='Español', **{'pt-br': 'Português (Brasil)'}, fr='Français', de='Deutsch',
             it='Italiano', ja='日本語', ca='Català', **{'zh-hans':'简体中文'})
WRAP_LEAST = 240                     # the narrowest a wrapped text gets (pixels); its grid column is never narrower
PHASES = dict(check='app.phase.check', tools='now.start', read='now.extract', holes='now.check', write='now.write',
              result='app.phase.result')


def short_name(name, most=46):
    """A file name that fits the slot: the middle left out of a long one (its start and extension stay)."""
    if len(name) <= most:
        return name
    keep = most - 1
    return name[:keep - keep // 3] + '…' + name[-(keep // 3):]


# ---------------------------------------------------------------- strings

HAND = 'pointinghand' if sys.platform == 'darwin' else 'hand2'


class MakeTile:
    """A make button: a flat tile (a label with a border) that answers clicks, hover and the disabled state. A native
    macOS button keeps its fixed height and leaves a tall logo hanging over its edges; the tile looks the same
    everywhere."""

    BG, HOVER, PRESS, EDGE, TEXT, OFF = '#ffffff', '#eef0fb', '#dfe3f7', '#c9c6d6', '#1b1a24', '#a3a0b3'

    def __init__(self, parent, text='', image='', compound='top', style=None, command=None):
        import tkinter as tk
        self.command, self.disabled, self.inside = command, False, False
        image = image[0] if isinstance(image, tuple) else image      # a ttk image spec: the label keeps the colours itself
        self.label = tk.Label(parent, text=text, image=image, compound=compound, justify='center', bg=self.BG,
                              fg=self.TEXT, padx=6, pady=10, bd=0, highlightthickness=1,
                              highlightbackground=self.EDGE, highlightcolor=self.EDGE, cursor=HAND)
        self.label.bind('<Enter>', lambda e: self._paint(inside=True))
        self.label.bind('<Leave>', lambda e: self._paint(inside=False))
        self.label.bind('<ButtonPress-1>', lambda e: self._paint(color=self.PRESS))
        self.label.bind('<ButtonRelease-1>', self._release)

    def _paint(self, inside=None, color=None):
        if inside is not None:
            self.inside = inside
        if self.disabled:
            self.label.configure(bg=self.BG, fg=self.OFF, cursor='arrow')
        else:
            self.label.configure(bg=color or (self.HOVER if self.inside else self.BG), fg=self.TEXT, cursor=HAND)

    def _release(self, event):
        self._paint()
        w = event.widget
        if not self.disabled and 0 <= event.x < w.winfo_width() and 0 <= event.y < w.winfo_height():
            self.invoke()

    def invoke(self):
        if not self.disabled and self.command:
            self.command()

    def grid(self, **kw):
        self.label.grid(**kw)

    def configure(self, **kw):
        kw.pop('style', None)
        if isinstance(kw.get('image'), tuple):
            kw['image'] = kw['image'][0]
        self.label.configure(**kw)

    def state(self, flags=None):
        if flags:
            for f in flags:
                if f in ('disabled', '!disabled'):
                    self.disabled = f == 'disabled'
            self._paint()
        return ('disabled',) if self.disabled else ()

    def instate(self, flags):
        return all(('disabled' in self.state()) != f.startswith('!') for f in flags if f.lstrip('!') == 'disabled')


class Strings:
    """web/i18n/<lang>.json (the page's strings: slots, why.*, works.*, release.*, now.*) and the app's own
    (tools/patcher/app/i18n.json); English for anything missing."""
    def __init__(self, lang):
        self.lang = lang if lang in LANGS else 'en'
        with open(desktop.resource('tools', 'patcher', 'app', 'i18n.json'), encoding='utf-8') as f:
            own = json.load(f)
        self.table = {}
        for code in ('en', self.lang):
            try:
                with open(desktop.resource('web', 'i18n', f'{code}.json'), encoding='utf-8') as f:
                    self.table.update(json.load(f))
            except OSError:
                pass
            self.table.update(own.get(code, {}))

    def __call__(self, key, **params):
        text = self.table.get(key, key)
        for k, v in params.items():
            text = text.replace('{' + k + '}', str(v))
        return text


def system_language():
    """The system's language among the supported languages, else English."""
    names = []
    for var in ('LC_ALL', 'LC_MESSAGES', 'LANG', 'LANGUAGE'):
        if os.environ.get(var):
            names += os.environ[var].split(':')
    try:
        if os.name == 'nt':
            import ctypes
            import locale
            names.append(locale.windows_locale.get(ctypes.windll.kernel32.GetUserDefaultUILanguage(), ''))
        elif sys.platform == 'darwin':
            import subprocess
            out = subprocess.run(['defaults', 'read', '-g', 'AppleLanguages'], capture_output=True, text=True,
                                 timeout=5).stdout
            names += [w.strip(' ",()\n') for w in out.split(',')]
        import locale
        names.append(locale.getlocale()[0] or '')
    except Exception:
        pass
    for n in names:
        n = n.lower().replace('_', '-').split('.')[0]
        if n.startswith('zh'):
            return 'zh-hans'
        if n.startswith('pt-br') or n == 'pt':
            return 'pt-br'
        if n[:2] in LANGS and n[:2] != 'pt':
            return n[:2]
    return 'en'


# what the make buttons make, in their order: the disc image first, then the installers with it inside
# (kind, name, file type); a logo each (tools/patcher/app/platform-logos/KIND.png)
MAKERS = (('disc', 'PlayStation', '.bin / .cue'), ('apk', 'Android', '.apk'), ('setup', 'Windows', '.exe'),
          ('mac', 'Mac', '.dmg' if sys.platform == 'darwin' else '.zip'), ('linux', 'Linux', '.run'))


# ---------------------------------------------------------------- the window
class App:
    def __init__(self, root, config):
        import tkinter as tk
        from tkinter import ttk
        self.tk, self.ttk, self.root, self.config = tk, ttk, root, config
        self.events = queue.Queue()
        self.slots = {}                   # game: result (desktop.identify) of the disc in use
        self.notes = {}                   # game: (key, params) shown in an empty or changed slot
        self.checking = {}                # game: fraction while a file is checked
        self.package = None               # package_info in use
        self.latest = None                # latest_release(), when known
        self.busy = None                  # 'build', 'download', 'check' while a job runs
        self.cancel = threading.Event()
        self.patcher = None
        self.result = None
        self.lang = config.get('language') or system_language()
        self.t = Strings(self.lang)
        self._style()
        self._build()
        self._restore()
        self.root.after(100, self._pump)
        # (no network at start: GitHub is asked only when the player presses Download/Check or Build)

    # -- looks
    def _style(self):
        ttk = self.ttk
        style = ttk.Style(self.root)
        if sys.platform.startswith('linux') and 'clam' in style.theme_names():
            style.theme_use('clam')
        import tkinter.font as tkfont
        base = tkfont.nametofont('TkDefaultFont')
        size = base.cget('size')
        self.font_title = base.copy(); self.font_title.configure(size=int(abs(size) * 1.6), weight='bold')
        self.font_bold = base.copy(); self.font_bold.configure(weight='bold')
        self.font_small = base.copy(); self.font_small.configure(size=max(8, int(abs(size) * 0.9)))
        style.configure('Title.TLabel', font=self.font_title)
        style.configure('Bold.TLabel', font=self.font_bold)
        style.configure('Muted.TLabel', foreground='#5b5870', font=self.font_small)
        style.configure('Ok.TLabel', foreground='#1f7a3a')
        style.configure('OkTitle.TLabel', foreground='#1f7a3a', font=self.font_bold)
        style.configure('Bad.TLabel', foreground='#b3261e')
        style.configure('Build.TButton', font=self.font_bold, padding=(18, 8))

    def _build(self):
        tk, ttk, t = self.tk, self.ttk, self.t
        for w in self.root.winfo_children():
            w.destroy()
        self.root.title(t('app.title'))
        # Everything in a frame on a canvas: on a screen too short for the window (a small laptop at 150 %), it
        # scrolls instead of being cut. The scroll bar shows only then.
        bg = ttk.Style(self.root).lookup('TFrame', 'background') or self.root.cget('background')
        self.canvas = tk.Canvas(self.root, highlightthickness=0, borderwidth=0, background=bg)
        self.vbar = ttk.Scrollbar(self.root, orient='vertical', command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=self.vbar.set)
        self.canvas.grid(row=0, column=0, sticky='nsew')
        self.root.columnconfigure(0, weight=1); self.root.rowconfigure(0, weight=1)
        outer = self.outer = ttk.Frame(self.canvas, padding=18)
        outer.columnconfigure(0, weight=1)
        item = self.canvas.create_window(0, 0, window=outer, anchor='nw')
        self.canvas.bind('<Configure>', lambda e: (self.canvas.itemconfigure(item, width=e.width), self._fit()))
        outer.bind('<Configure>', lambda e: self._fit())
        self.root.bind_all('<MouseWheel>', self._wheel)
        self.root.bind_all('<Button-4>', lambda e: self._wheel(e, -1))
        self.root.bind_all('<Button-5>', lambda e: self._wheel(e, 1))

        head = ttk.Frame(outer)
        head.grid(row=0, column=0, sticky='ew')
        head.columnconfigure(1, weight=1)
        if getattr(self, 'icon', None) is not None:
            ttk.Label(head, image=self.icon_small).grid(row=0, column=0, rowspan=2, padx=(0, 12))
        ttk.Label(head, text='Digimon World: Horizon', style='Title.TLabel').grid(row=0, column=1, sticky='w')
        self._wrap(ttk.Label(head, text=t('app.lead'), style='Muted.TLabel')).grid(row=1, column=1, columnspan=2,
                                                                                    sticky='ew')
        self.lang_var = tk.StringVar(value=LANGS[self.t.lang])
        lang = ttk.Combobox(head, textvariable=self.lang_var, values=list(LANGS.values()), state='readonly', width=18)
        lang.grid(row=0, column=2, sticky='ne')
        lang.bind('<<ComboboxSelected>>', self._language)

        discs = ttk.LabelFrame(outer, text=t('slot.listLabel'), padding=(12, 8))
        discs.grid(row=1, column=0, sticky='ew', pady=(16, 0))
        discs.columnconfigure(1, weight=1, minsize=WRAP_LEAST + 24)    # (the wrapped status, with its padx)
        counts = {d['id']: d.get('species') for d in desktop.registry()['discs']}
        self.slot_widgets = {}
        for i, game in enumerate(desktop.GAMES):
            name = ttk.Label(discs, text=desktop.GAME_NAMES[game], style='Bold.TLabel')
            name.grid(row=2 * i, column=0, sticky='w', pady=(6 if i else 0, 0))
            purpose = t('slot.purpose.us') if game == 'us' else t('slot.purpose.source', n=counts.get(game) or '')
            ttk.Label(discs, text=purpose, style='Muted.TLabel').grid(row=2 * i + 1, column=0, sticky='nw')
            status = self._wrap(ttk.Label(discs, text='', justify='left'))
            status.grid(row=2 * i, column=1, rowspan=2, sticky='ew', padx=12)
            buttons = ttk.Frame(discs)
            buttons.grid(row=2 * i, column=2, rowspan=2, sticky='e')
            choose = ttk.Button(buttons, text=t('app.choose'), command=lambda g=game: self._choose(g))
            choose.grid(row=0, column=0)
            remove = ttk.Button(buttons, text='×', width=3, command=lambda g=game: self._remove(g))
            remove.grid(row=0, column=1, padx=(4, 0))
            self.slot_widgets[game] = (status, choose, remove)
        add = ttk.Frame(discs)
        add.grid(row=8, column=0, columnspan=3, sticky='ew', pady=(12, 0))
        add.columnconfigure(1, weight=1, minsize=WRAP_LEAST + 20)
        self.add_button = ttk.Button(add, text=t('app.add'), command=self._add)
        self.add_button.grid(row=0, column=0, sticky='w')
        self._wrap(ttk.Label(add, text=t('app.formats'), style='Muted.TLabel')).grid(row=0, column=1, sticky='ew',
                                                                                     padx=10)

        # what can be made, each its own button: the disc image, and the installers with that disc inside (the
        # disc is built first when this session has not built it from the same discs and package). Each asks for the
        # folder to save in, starting at the last one chosen.
        make = ttk.LabelFrame(outer, text=t('app.makeAs'), padding=(12, 8))
        make.grid(row=3, column=0, sticky='ew', pady=(16, 0))
        make.columnconfigure(tuple(range(len(MAKERS))), weight=1, uniform='makers')
        self.make_buttons = []
        for i, (kind, name, ext) in enumerate(MAKERS):
            b = MakeTile(make, text=f'{name}\n{ext}', image=getattr(self, 'make_icons', {}).get(kind, ''), compound='top',
                      command=lambda kind=kind: self._make(kind))
            b.grid(row=0, column=i, sticky='ew', padx=(0 if i == 0 else 6, 0))
            self.make_buttons.append(b)
        run = ttk.Frame(outer)
        run.grid(row=5, column=0, sticky='ew', pady=(8, 0))
        run.columnconfigure(0, weight=1, minsize=WRAP_LEAST + 24)
        self.why_label = self._wrap(ttk.Label(run, text='', style='Muted.TLabel', justify='left'))
        self.why_label.grid(row=0, column=0, sticky='ew')
        self.progress = ttk.Progressbar(run, maximum=1000, mode='determinate')
        self.progress.grid(row=1, column=0, sticky='ew')
        self.stop_button = ttk.Button(run, text=t('app.cancel'), command=self._stop)
        self.stop_button.grid(row=0, column=1, rowspan=2, padx=(12, 0))
        self.stage = self._wrap(ttk.Label(outer, text='', justify='left'))
        self.stage.grid(row=6, column=0, sticky='ew', pady=(8, 0))
        self.result = ttk.Frame(outer)                       # what was made: how to use it, where it is
        self.result.grid(row=7, column=0, sticky='ew')
        self.result.columnconfigure(0, weight=1)
        self.finish = ttk.Frame(outer)
        self.finish.grid(row=8, column=0, sticky='w', pady=(8, 0))
        self._refresh()
        self.root.update_idletasks()
        # The narrowest the window may be: what the buttons and names need with the texts wrapped at their least.
        self.min_width = max(outer.winfo_reqwidth(), 640)
        self.canvas.configure(width=max(760, self.min_width))
        self.root.geometry('')                               # (back to the natural size after a language change)
        self._fit()

    def _wrap(self, label, least=None):
        """A label whose text wraps at the width it is given (grid sticky 'ew' in a column with weight)."""
        least = least or WRAP_LEAST
        label.configure(wraplength=least)

        def resize(event):
            width = max(least, event.width - 8)          # (the label's own padding)
            if abs(int(str(label.cget('wraplength')) or 0) - width) > 2:
                label.configure(wraplength=width)
                self._fit()
        label.bind('<Configure>', resize)
        return label

    def _fit(self):
        """Never smaller than the content: the window grows when wrapped texts need more lines."""
        if getattr(self, '_fit_pending', False):
            return
        self._fit_pending = True

        def fit():
            self._fit_pending = False
            if not self.outer.winfo_exists():
                return
            self.root.update_idletasks()
            need = self.outer.winfo_reqheight()
            room = self.root.winfo_screenheight() - 120          # (the title bar, the task bar or the menu bar)
            if int(self.canvas.cget('height')) != min(need, room):
                self.canvas.configure(height=min(need, room))
            self.canvas.configure(scrollregion=(0, 0, 0, need))
            if need > self.canvas.winfo_height() + 1:
                self.vbar.grid(row=0, column=1, sticky='ns')
            else:
                self.vbar.grid_remove()
                self.canvas.yview_moveto(0)
            self.root.minsize(getattr(self, 'min_width', 640) + 20, min(need, 320))
        self.root.after_idle(fit)

    def _wheel(self, event, step=None):
        if self.vbar.winfo_ismapped():
            if step is None:
                step = -1 if event.delta > 0 else 1
                if sys.platform != 'darwin' and abs(event.delta) >= 120:
                    step *= abs(event.delta) // 120
            self.canvas.yview_scroll(step, 'units')

    def set_icon(self):
        """The window's icon: tools/patcher/app/make_icons.py's drawing of web/favicon.svg."""
        import base64
        sys.path.insert(0, desktop.resource('tools', 'patcher', 'app'))
        try:
            import make_icons
            self.icon = self.tk.PhotoImage(data=base64.b64encode(make_icons.png(64)))
            self.icon_small = self.tk.PhotoImage(data=base64.b64encode(make_icons.png(48)))
            self.root.iconphoto(True, self.icon)
        except Exception:
            self.icon = None
        self.make_icons = {}
        try:
            for kind, _, _ in MAKERS:
                logo = desktop.resource('tools', 'patcher', 'app', 'platform-logos', kind + '.png')
                img = self.tk.PhotoImage(file=logo)
                self.make_icons[kind] = (img, 'disabled', img)      # in colour while disabled too (Tk greys it)
        except Exception:
            pass
        for (kind, _, _), b in zip(MAKERS, getattr(self, 'make_buttons', [])):
            b.configure(image=self.make_icons.get(kind, ''))

    # -- state shown
    def _refresh(self):
        t = self.t
        for game, (status, choose, remove) in self.slot_widgets.items():
            r = self.slots.get(game)
            if game in self.checking:
                status.configure(text=t('disc.checking', pct=int(self.checking[game] * 100)), style='TLabel')
            elif r:
                words = t('release.' + r['release'])
                text = f'✓ {t("disc.ok")} · {words}\n{short_name(os.path.basename(r["path"]))}'
                if r.get('how') == 'files':
                    text += '\n' + t('app.filesOnly')
                status.configure(text=text, style='Ok.TLabel')
            elif game in self.notes:
                key, params = self.notes[game]
                status.configure(text=t(key, **params), style='Bad.TLabel')
            else:
                status.configure(text=t('app.empty'), style='Muted.TLabel')
            idle = self.busy is None
            choose.state(['!disabled'] if idle else ['disabled'])
            remove.state(['!disabled'] if idle and (r or game in self.notes) else ['disabled'])
        idle = self.busy is None
        self.add_button.state(['!disabled'] if idle else ['disabled'])
        # build
        missing = [desktop.GAME_NAMES[g] for g in desktop.GAMES if g not in self.slots]
        if self.busy:
            why = ''
        elif missing:
            why = t('patch.missing', list=', '.join(missing))
        else:
            why = t('app.ready')
        self.why_label.configure(text=why)
        for b in self.make_buttons:
            b.state(['!disabled'] if idle and not missing else ['disabled'])
        self.stop_button.state(['!disabled'] if self.busy in ('build', 'download', 'check') and not self.cancel.is_set()
                               else ['disabled'])

    def output_folder(self):
        if self.config.get('output'):
            return self.config.get('output')
        if 'us' in self.slots:
            return desktop.default_output(self.slots['us']['path'])
        return ''

    def _restore(self):
        reconvert = []
        for game, (entry, reason) in self.config.remembered_discs().items():
            if reason == 'convert':
                reconvert.append(entry['path'])
            elif reason:
                self.notes[game] = ('app.' + reason, dict(path=entry.get('path', '')))
            else:
                self.slots[game] = dict(entry, game=game)
        info = desktop.cached_packages()
        chosen = self.config.get('package')
        self.package = next((i for i in info if i['folder'] == chosen), None) or \
            next((i for i in info if not i['name'].startswith('file-')), None)
        if self.package and self.package['name'].startswith('file-'):
            self.package['source'] = 'file'
            self.package['verified'] = self.config.get('package_verified', False)
        self._refresh()
        last = self.config.get('last_disc')
        if last and os.path.isfile(last):          # the disc built last time: Play is there at once
            self._finish_buttons(os.path.dirname(last), None, last)
        if reconvert:
            self._check(reconvert)

    # -- background work: one job at a time, results through self.events
    def _spawn(self, fn, *args, busy=None, quiet=False):
        if busy:
            self.busy = busy
            self.cancel.clear()
        self._refresh()

        def run():
            try:
                fn(*args)
            except BaseException as e:            # noqa: shown in the window
                self.events.put(('error', e, traceback.format_exc(), quiet))
            finally:
                if busy:
                    self.events.put(('idle',))
        self.worker = threading.Thread(target=run, daemon=True)
        self.worker.start()

    def _pump(self):
        try:
            while True:
                ev = self.events.get_nowait()
                getattr(self, '_on_' + ev[0])(*ev[1:])
        except queue.Empty:
            pass
        if self.busy == 'build' and self.patcher is not None:
            st = self.patcher.status()
            if st:
                words = self._phase_words(st['phase'], st['words'])
                self.progress['value'] = int(st['fraction'] * 1000)
                times = self.t('app.time', pct=int(st['fraction'] * 100), elapsed=desktop.clock(st['elapsed']),
                               left=desktop.clock(st['left'])) if st['fraction'] > 0.02 else \
                    self.t('app.timeStart', elapsed=desktop.clock(st['elapsed']))
                self.stage.configure(text=f'{words}\n{times}', style='TLabel')
        self.root.after(250, self._pump)

    def _phase_words(self, phase, fallback):
        if not phase:
            return self.t('now.start')
        key = 'now.' + phase[5:] if phase.startswith('step:') else PHASES.get(phase)
        text = self.t(key) if key else fallback
        if text == key:
            text = fallback
        return text[:1].upper() + text[1:]

    def _on_idle(self):
        if self.busy == 'check':
            self.checking.clear()
        self.busy = None
        self.cancel.clear()
        self._refresh()

    def _on_error(self, e, tb, quiet):
        if quiet:
            self.latest_error = str(getattr(e, 'reason', None) or e)
            self.progress['value'] = 0               # a start-up download that failed: nothing to show
            self.stage.configure(text='', style='TLabel')
            self._refresh()
            return
        self.stage.configure(text=self._message(e), style='Bad.TLabel')
        sys.stderr.write(tb)

    def _message(self, e):
        if isinstance(e, desktop.Problem):
            if e.key == 'cancelled':
                return self.t('app.stopped')
            return self._problem_text(e)
        if isinstance(e, OSError):
            return self.t('app.osError', error=f'{e.strerror or e}' + (f': {e.filename}' if e.filename else ''))
        import urllib.error
        if isinstance(e, urllib.error.URLError):
            return self.t('app.offline', error=e.reason)
        return self.t('app.unexpected', error=f'{type(e).__name__}: {e}')

    def _problem_text(self, e):
        params = dict(e.params)
        if 'release' in params and isinstance(params['release'], tuple):
            g, rid = params['release']
            params['release'] = f'{desktop.GAME_NAMES[g]} · {self.t("release." + rid)}'
        if 'game_release' in params:
            g, rid = params.pop('game_release')
            params['game'] = f'{desktop.GAME_NAMES[g]} ({self.t("release." + rid)})'
        if isinstance(params.get('instead'), list):
            names = params['instead']
            params['instead'] = names[0] if len(names) == 1 else f'{", ".join(names[:-1])} {self.t("why.or")} {names[-1]}'
        text = self.t(e.key, **params)
        if e.game and e.key.startswith('why.') and e.key not in ('why.notYet', 'why.useInstead'):
            text += '\n' + self.t('works.' + e.game)
        return text

    # -- discs
    def _filetypes(self):
        return [(self.t('app.discFiles'), '*.cue *.bin *.iso *.img *.pbp *.PBP *.chd *.CHD'), (self.t('app.allFiles'), '*')]

    def _add(self):
        from tkinter import filedialog
        paths = filedialog.askopenfilenames(parent=self.root, title=self.t('app.chooseDiscs'),
                                            filetypes=self._filetypes())
        if paths:
            self._check(list(paths))

    def _choose(self, game):
        from tkinter import filedialog
        path = filedialog.askopenfilename(parent=self.root, title=desktop.GAME_NAMES[game],
                                          filetypes=self._filetypes())
        if path:
            self._check([path])

    def _remove(self, game):
        self.slots.pop(game, None); self.notes.pop(game, None)
        self.config.forget_disc(game)
        self._refresh()

    def _check(self, paths):
        def job():
            current = {}

            def progress(i, n, f):
                g = current.get(i)
                if g:
                    self.events.put(('checking', g, f))
                else:
                    self.events.put(('checking_image', p, f))
            problems = []
            for i, p in enumerate(paths):
                try:
                    image = desktop.cue_image(p) if p.lower().endswith('.cue') else p
                    boot, _ = desktop.boot_and_layout(image)
                    cands = desktop.candidates(boot) if boot else []
                    if cands:
                        current[i] = cands[0][0]
                        self.events.put(('checking', cands[0][0], 0.0))
                except (desktop.Problem, OSError):
                    pass
                found, bad = desktop.sort_files([p], lambda _i, n, f, i=i: progress(i, n, f), self.cancel,
                                                lambda path, f: self.events.put(('converting', path, f)))
                for game, r in found.items():
                    self.events.put(('disc', game, r))
                problems += bad
                if i in current:
                    self.events.put(('checked', current[i]))
            if problems:
                self.events.put(('problems', problems))
        self._spawn(job, busy='check')

    def _on_converting(self, path, f):
        if getattr(self, '_converting_path', None) != path:
            self._converting_path = path
            try:
                kind = desktop.discformats.sniff(path)
            except OSError:
                kind = None  # The worker reports a removed or unreadable source.
            self._converting_key = 'app.convertingChd' if kind == 'chd' else 'app.converting'
        self.stage.configure(text=self.t(self._converting_key, file=os.path.basename(path), pct=int(f * 100)))
        self.progress['value'] = int(f * 1000)

    def _on_checking_image(self, path, f):
        words = self.t('disc.checking', pct=int(f * 100))
        self.stage.configure(text=f'{os.path.basename(path)}: {words}')
        self.progress['value'] = int(f * 1000)

    def _on_checking(self, game, f):
        self.checking[game] = f
        self._refresh()

    def _on_checked(self, game):
        self.checking.pop(game, None)
        self._refresh()

    def _on_disc(self, game, r):
        self.checking.pop(game, None)
        self.slots[game] = r
        self.notes.pop(game, None)
        self.config.remember_disc(game, r)
        self._refresh()

    def _on_problems(self, problems):
        from tkinter import messagebox
        lines = [f'{os.path.basename(p)}\n{self._problem_text(e)}' for p, e in problems]
        messagebox.showwarning(self.t('problems.title'), '\n\n'.join(lines), parent=self.root)

    # -- the package
    def _job_latest(self):
        self.events.put(('latest', desktop.latest_release()))

    def _on_latest(self, latest):
        self.latest = latest
        self.latest_error = None
        self._refresh()

    def _job_download(self, latest=None):
        latest = latest or self.latest
        total = latest['assets'].get(desktop.PACKAGE_ASSET, {}).get('size') or 0

        def progress(done, size):
            size = size or total or 1
            self.events.put(('bar', done / size, self.t('app.downloading', version=latest['version'],
                                                         done=done // 2 ** 20, total=size // 2 ** 20)))
        info = dict(desktop.install_release(latest, progress, self.cancel), source='release')
        info['name'] = os.path.basename(info['folder'])
        self.events.put(('package', info))
        return info

    def _on_bar(self, f, text):
        self.progress['value'] = int(f * 1000)
        self.stage.configure(text=text, style='TLabel')

    def _on_stage(self, text, style):
        self.stage.configure(text=text, style=style)

    def _on_package(self, info):
        self.package = info
        self.config.set('package', info['folder'])
        self.config.set('package_verified', bool(info.get('verified', True)))
        self.stage.configure(text=self.t('app.packageReady', version=info['version'], date=info['date']),
                             style='TLabel')
        self.progress['value'] = 0
        self._refresh()

    # -- output and build
    def _ask_folder(self):
        """The folder to save in, asked at each make button (None: cancelled); remembered for the next time."""
        from tkinter import filedialog
        start = self.output_folder()
        if start and not os.path.isdir(start):
            start = os.path.dirname(start) if os.path.isdir(os.path.dirname(start)) else ''
        path = filedialog.askdirectory(parent=self.root, title=self.t('app.output'),
                                       initialdir=start or os.path.expanduser('~'))
        if not path:
            return None
        self.config.set('output', path)
        return path

    def _language(self, _event=None):
        name = self.lang_var.get()
        code = next(k for k, v in LANGS.items() if v == name)
        self.config.set('language', code)
        self.lang = code
        self.t = Strings(code)
        self._build()

    def _make(self, kind):
        """A make button: the disc image, or an installer with the disc inside, saved in the folder the player
        chooses. Nothing is downloaded before the first press. The disc is built once into the cache folder
        (desktop.built_disc_dir) and kept: every press after it, for any folder, uses it while the discs and the
        package are the same."""
        out = self._ask_folder()
        if not out:
            return
        for game, r in list(self.slots.items()):
            why = desktop.file_changed(r)
            if why == 'convert':
                self._check([r['path']])
                return
            if why:
                self.slots.pop(game)
                self.notes[game] = ('app.' + why, dict(path=r['path']))
                self.config.forget_disc(game)
                self._refresh()
                return
        problems = desktop.space_problems(desktop.cache_dir())
        problems += [p for p in desktop.space_problems(out) if p not in problems and p[0] == 'app.spaceOutput']
        if problems:
            from tkinter import messagebox
            if not messagebox.askokcancel(self.t('app.title'), '\n\n'.join(self.t(k, **p) for k, p in problems)
                                          + '\n\n' + self.t('app.continueAnyway'), parent=self.root):
                return
        for w in self.finish.winfo_children() + self.result.winfo_children():
            w.destroy()
        self._spawn(self._job_make_any, kind, out, busy='build')

    def _job_make_any(self, kind, out):
        package = self._job_package()
        key = desktop.disc_key(self.slots, package)
        disc = desktop.cached_disc(key)
        if not disc:
            disc = self._job_build(key, package)
            if not disc:
                return                                      # failed or stopped: shown already
        if kind == 'disc':
            def copying(done, total):
                self.events.put(('bar', done / total, self.t('app.copyingDisc', done=done * 100 // total)))
            self.events.put(('built', desktop.copy_disc(disc, out, copying, self.cancel)))
        else:
            self._job_make(kind, disc['cue'], disc['version'], out)

    def _job_package(self):
        """The package to build with: the latest release is asked for (a newer one is downloaded first, a package
        file the player chose is kept); offline, the package already here is used."""
        package = self.package
        if not package or package.get('source') != 'file':
            try:
                latest = desktop.latest_release()
                self.events.put(('latest', latest))
            except OSError:
                if not package:
                    raise
                latest = None
            if latest and (not package or desktop.version_key(latest['version'])
                           >= desktop.version_key(package['version'])):
                package = self._job_download(latest)
        return package

    def _job_build(self, key, package):
        """The disc, built into desktop.built_disc_dir() and kept there -> desktop.cached_disc(key), or None when it
        failed or was stopped (shown)."""
        self.events.put(('stage', self.t('now.start'), 'TLabel'))
        dw = desktop.load_patcher(package['folder'])
        dw.CANCEL = self.cancel
        self.patcher = dw
        desktop.forget_built_disc()
        try:
            result = dw.apply_disc(self.slots['us']['image'], desktop.source_disc_args(self.slots),
                                   output=desktop.built_disc_dir(), release=package['folder'])
        except BaseException as e:
            kind = 'stopped' if isinstance(e, dw.Stopped) else 'patch' if isinstance(e, dw.PatchError) else 'other'
            if kind == 'other':
                sys.stderr.write(traceback.format_exc())
            self.events.put(('failed', e, getattr(e, 'log', None), kind))
            return None
        finally:
            self.patcher = None
        desktop.keep_built_disc(key, result, package['version'])
        return desktop.cached_disc(key)

    def _on_built(self, cue):
        self.progress['value'] = 1000
        self.config.set('last_disc', os.path.abspath(cue))
        self._finish_buttons(os.path.dirname(cue), None, cue)
        self.stage.configure(text=self.t('app.done', file=os.path.basename(cue)), style='Ok.TLabel')
        self._show_result('', cue)

    def _on_made(self, path):
        self.progress['value'] = 1000
        key = 'app.macZipDone' if path.endswith('.zip') else 'app.{}Done'.format(
            next(k for k, ext in (('apk', '.apk'), ('setup', '.exe'), ('mac', '.dmg'), ('linux', '.run'))
                 if path.endswith(ext)))
        self._finish_buttons(os.path.dirname(path), None)
        # "Mac app ready: {file}. Open it on a Mac...": the title in green, the steps in plain text below it
        text = self.t(key, file='\0')
        head, _, rest = text.partition('\0')
        self.stage.configure(text=head.rstrip(' :：') or os.path.basename(path), style='OkTitle.TLabel')
        self._show_result(rest.lstrip(' .。'), path)

    def _show_result(self, steps, path):
        """The steps to use what was made, then where it is (small, muted)."""
        row = 0
        if steps:
            self._wrap(self.ttk.Label(self.result, text=steps, justify='left')).grid(row=row, column=0, sticky='ew',
                                                                                  pady=(4, 0))
            row += 1
        self._wrap(self.ttk.Label(self.result, text=path, style='Muted.TLabel', justify='left')).grid(
            row=row, column=0, sticky='ew', pady=(4, 0))

    def _on_failed(self, e, log, kind):
        if kind == 'stopped':
            text = self.t('app.stopped')
        elif kind == 'patch':                       # (dwpatch's own message for the player, in English)
            text = self.t('app.failed', message=str(e))
        else:
            text = self._message(e)
        self.progress['value'] = 0
        self.stage.configure(text=text, style='Bad.TLabel')
        if log:
            self._finish_buttons(None, log)

    def _finish_buttons(self, folder, log, cue=None):
        """Open the folder (and the log after a failure)."""
        ttk = self.ttk
        for w in self.finish.winfo_children() + self.result.winfo_children():
            w.destroy()
        col = 0
        for ok, text, cmd, style in (
                (folder, 'app.openFolder', lambda: desktop.open_folder(folder), 'TButton'),
                (log and os.path.exists(log), 'app.openLog', lambda: desktop.open_folder(log), 'TButton')):
            if ok:
                ttk.Button(self.finish, text=self.t(text), style=style, command=cmd).grid(row=0, column=col, padx=(0, 6))
                col += 1

    def _job_make(self, kind, cue, version=None, out_dir=None):
        """An installer with the built disc inside, into out_dir: the template comes from the release of the
        package it was built with."""
        names = dict(apk='app.makingApk', setup='app.makingSetup', mac='app.makingMac', linux='app.makingLinux')
        version = version or (self.package or {}).get('version') or ''
        tag = 'v' + version.lstrip('v')

        def fetching(done, total):
            if total:
                self.events.put(('bar', done / total, self.t('app.fetchingTemplate', name=desktop.TEMPLATES[kind],
                                                              done=done // 1048576, total=total // 1048576)))

        def progress(done, total):
            self.events.put(('bar', done / total, self.t(names[kind], done=done * 100 // total)))
        self.events.put(('made', desktop.make(kind, cue, tag, progress, fetching, self.cancel, out_dir)))

    def _stop(self):
        self.cancel.set()
        self.stage.configure(text=self.t('app.cancelling'), style='TLabel')
        self._refresh()

    def close(self):
        if not getattr(self, 'closing', False):
            if self.busy == 'build':
                from tkinter import messagebox
                if not messagebox.askokcancel(self.t('app.title'), self.t('app.quitBuilding'), parent=self.root):
                    return
            self.closing = True
        self.cancel.set()
        worker = getattr(self, 'worker', None)
        if worker is not None and worker.is_alive():
            self.root.after(100, self.close)
            return
        desktop.CONVERSIONS.close()
        self.root.destroy()


def clipped(root):
    """[widget description] of every shown text or button narrower or shorter than it asks to be, or reaching out
    of its parent or the window: what the self-test checks in every language."""
    out = []
    rw = root.winfo_width()
    area = next((c for c in root.winfo_children() if c.winfo_class() == 'Canvas'), root)
    rh = area.winfo_height()

    def walk(w):
        for c in w.winfo_children():
            if not c.winfo_ismapped():
                continue
            kind = c.winfo_class()
            if kind in ('TLabel', 'TButton', 'Label', 'Button', 'TCombobox'):
                text = str(c.cget('text')) if kind != 'TCombobox' else ''
                what = f'{kind} {text[:40]!r}'
                if c.winfo_width() + 1 < c.winfo_reqwidth() or c.winfo_height() + 1 < c.winfo_reqheight():
                    out.append(f'{what}: {c.winfo_width()}x{c.winfo_height()} < {c.winfo_reqwidth()}x{c.winfo_reqheight()}')
                x, y = c.winfo_rootx() - root.winfo_rootx(), c.winfo_rooty() - root.winfo_rooty()
                if x + c.winfo_width() > rw + 1:
                    out.append(f'{what}: out of the window')
                content = c.winfo_rooty() - area.winfo_rooty() + int(area.canvasy(0)) if area is not root else y
                if content + c.winfo_height() > int(area.cget('scrollregion').split()[-1] if area is not root
                                                    else rh) + 1:
                    out.append(f'{what}: below the content')
            walk(c)
    walk(root)
    return out


# ---------------------------------------------------------------- start
def quiet_streams():
    """A windowed app has no console: sys.stdout/stderr may be None. stderr goes to app.log in the settings
    folder (what went wrong, for a bug report)."""
    if sys.stdout is None:
        sys.stdout = open(os.devnull, 'w', encoding='utf-8')
    if sys.stderr is None or getattr(sys, 'frozen', False):
        try:
            os.makedirs(desktop.config_dir(), exist_ok=True)
            sys.stderr = open(os.path.join(desktop.config_dir(), 'app.log'), 'a', encoding='utf-8',
                              errors='replace', buffering=1)
        except OSError:
            if sys.stderr is None:
                sys.stderr = open(os.devnull, 'w')


def main():
    if '--self-test' in sys.argv[1:]:
        import selftest
        return selftest.main(sys.argv[sys.argv.index('--self-test') + 1:])
    if sys.argv[1:2] == ['--make']:   # everything from a terminal, no window (make_cli.py)
        import make_cli
        return make_cli.main(sys.argv[2:])
    quiet_streams()
    if os.name == 'nt':
        try:
            import ctypes
            ctypes.windll.shcore.SetProcessDpiAwareness(1)      # sharp text on scaled displays
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID('dw1horizon.patcher')
        except Exception:
            pass
    import tkinter as tk
    root = tk.Tk(className='HorizonPatcher')
    config = desktop.Config()
    app = App.__new__(App)
    app.tk, app.root = tk, root
    app.set_icon()
    app.__init__(root, config)
    root.protocol('WM_DELETE_WINDOW', app.close)
    root.mainloop()
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except Exception:                   # (a windowed app has no console: the traceback goes to app.log)
        traceback.print_exc()
        sys.exit(1)
