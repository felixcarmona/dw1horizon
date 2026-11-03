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

if __name__ == '__main__':
    multiprocessing.freeze_support()                     # (a frozen spawn child runs its work and exits here)
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import desktop as _desktop
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
             it='Italiano', ja='日本語', ca='Català')
PHASES = dict(check='app.phase.check', tools='now.start', read='now.extract', holes='now.check', write='now.write',
              result='app.phase.result')


# ---------------------------------------------------------------- strings
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
    """The system's language among the eight, else English."""
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
        if n.startswith('pt-br') or n == 'pt':
            return 'pt-br'
        if n[:2] in LANGS and n[:2] != 'pt':
            return n[:2]
    return 'en'


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
        style.configure('Bad.TLabel', foreground='#b3261e')
        style.configure('Build.TButton', font=self.font_bold, padding=(18, 8))

    def _build(self):
        tk, ttk, t = self.tk, self.ttk, self.t
        for w in self.root.winfo_children():
            w.destroy()
        self.root.title(t('app.title'))
        outer = ttk.Frame(self.root, padding=18)
        outer.grid(sticky='nsew')
        self.root.columnconfigure(0, weight=1); self.root.rowconfigure(0, weight=1)
        outer.columnconfigure(0, weight=1)

        head = ttk.Frame(outer)
        head.grid(row=0, column=0, sticky='ew')
        head.columnconfigure(1, weight=1)
        if getattr(self, 'icon', None) is not None:
            ttk.Label(head, image=self.icon_small).grid(row=0, column=0, rowspan=2, padx=(0, 12))
        ttk.Label(head, text='Digimon World: Horizon', style='Title.TLabel').grid(row=0, column=1, sticky='w')
        ttk.Label(head, text=t('app.lead'), style='Muted.TLabel', wraplength=600).grid(row=1, column=1, columnspan=2,
                                                                                       sticky='w')
        self.lang_var = tk.StringVar(value=LANGS[self.t.lang])
        lang = ttk.Combobox(head, textvariable=self.lang_var, values=list(LANGS.values()), state='readonly', width=18)
        lang.grid(row=0, column=2, sticky='ne')
        lang.bind('<<ComboboxSelected>>', self._language)

        discs = ttk.LabelFrame(outer, text=t('slot.listLabel'), padding=(12, 8))
        discs.grid(row=1, column=0, sticky='ew', pady=(16, 0))
        discs.columnconfigure(1, weight=1)
        counts = {d['id']: d.get('species') for d in desktop.registry()['discs']}
        self.slot_widgets = {}
        for i, game in enumerate(desktop.GAMES):
            name = ttk.Label(discs, text=desktop.GAME_NAMES[game], style='Bold.TLabel')
            name.grid(row=2 * i, column=0, sticky='w', pady=(6 if i else 0, 0))
            purpose = t('slot.purpose.us') if game == 'us' else t('slot.purpose.source', n=counts.get(game) or '')
            ttk.Label(discs, text=purpose, style='Muted.TLabel').grid(row=2 * i + 1, column=0, sticky='nw')
            status = ttk.Label(discs, text='', wraplength=380, justify='left')
            status.grid(row=2 * i, column=1, rowspan=2, sticky='w', padx=12)
            buttons = ttk.Frame(discs)
            buttons.grid(row=2 * i, column=2, rowspan=2, sticky='e')
            choose = ttk.Button(buttons, text=t('app.choose'), command=lambda g=game: self._choose(g))
            choose.grid(row=0, column=0)
            remove = ttk.Button(buttons, text='×', width=3, command=lambda g=game: self._remove(g))
            remove.grid(row=0, column=1, padx=(4, 0))
            self.slot_widgets[game] = (status, choose, remove)
        add = ttk.Frame(discs)
        add.grid(row=8, column=0, columnspan=3, sticky='ew', pady=(12, 0))
        self.add_button = ttk.Button(add, text=t('app.add'), command=self._add)
        self.add_button.grid(row=0, column=0, sticky='w')
        ttk.Label(add, text=t('app.formats'), style='Muted.TLabel').grid(row=0, column=1, sticky='w', padx=10)

        pkg = ttk.LabelFrame(outer, text=t('app.package'), padding=(12, 8))
        pkg.grid(row=2, column=0, sticky='ew', pady=(12, 0))
        pkg.columnconfigure(0, weight=1)
        self.pkg_label = ttk.Label(pkg, text='', wraplength=640, justify='left')
        self.pkg_label.grid(row=0, column=0, columnspan=3, sticky='w')
        self.pkg_download = ttk.Button(pkg, text=t('app.download'), command=self._download)
        self.pkg_download.grid(row=1, column=1, padx=(8, 0), pady=(8, 0))
        self.pkg_file = ttk.Button(pkg, text=t('app.useFile'), command=self._use_file)
        self.pkg_file.grid(row=1, column=2, padx=(4, 0), pady=(8, 0))

        out = ttk.LabelFrame(outer, text=t('app.output'), padding=(12, 8))
        out.grid(row=3, column=0, sticky='ew', pady=(12, 0))
        out.columnconfigure(0, weight=1)
        self.out_var = tk.StringVar(value='')
        ttk.Entry(out, textvariable=self.out_var, state='readonly').grid(row=0, column=0, sticky='ew')
        self.out_button = ttk.Button(out, text=t('app.browse'), command=self._browse)
        self.out_button.grid(row=0, column=1, padx=(8, 0))

        run = ttk.Frame(outer)
        run.grid(row=4, column=0, sticky='ew', pady=(16, 0))
        run.columnconfigure(1, weight=1)
        self.build_button = ttk.Button(run, text=t('patch.button'), style='Build.TButton', command=self._build_disc)
        self.build_button.grid(row=0, column=0, rowspan=2, sticky='w')
        self.why_label = ttk.Label(run, text='', style='Muted.TLabel', wraplength=420, justify='left')
        self.why_label.grid(row=0, column=1, sticky='w', padx=12)
        self.progress = ttk.Progressbar(run, maximum=1000, mode='determinate')
        self.progress.grid(row=1, column=1, sticky='ew', padx=12)
        self.stop_button = ttk.Button(run, text=t('app.cancel'), command=self._stop)
        self.stop_button.grid(row=0, column=2, rowspan=2)
        self.stage = ttk.Label(outer, text='', wraplength=640, justify='left')
        self.stage.grid(row=5, column=0, sticky='w', pady=(8, 0))
        self.finish = ttk.Frame(outer)
        self.finish.grid(row=6, column=0, sticky='w', pady=(8, 0))
        self._refresh()

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

    # -- state shown
    def _refresh(self):
        t = self.t
        for game, (status, choose, remove) in self.slot_widgets.items():
            r = self.slots.get(game)
            if game in self.checking:
                status.configure(text=t('disc.checking', pct=int(self.checking[game] * 100)), style='TLabel')
            elif r:
                words = t('release.' + r['release'])
                text = f'✓ {t("disc.ok")} · {words}\n{os.path.basename(r["path"])}'
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
        for b in (self.add_button, self.pkg_file, self.out_button):
            b.state(['!disabled'] if idle else ['disabled'])
        # the package
        if self.package:
            key = 'app.packageFile' if self.package.get('source') == 'file' else 'app.packageReady'
            text = t(key, version=self.package['version'], date=self.package['date'])
            if self.package.get('source') == 'file' and not self.package.get('verified'):
                text += '\n' + t('app.packageUnverified')
        elif self.latest and desktop.PACKAGE_ASSET in self.latest['assets']:
            mb = (self.latest['assets'][desktop.PACKAGE_ASSET].get('size') or 0) // 2 ** 20
            text = t('app.packageNone', version=self.latest['version'], mb=mb)
        else:
            text = t('app.packageUnknown')
        newer = self.latest and (not self.package or desktop.version_key(self.latest['version'])
                                 > desktop.version_key(self.package['version']))
        if newer and self.package:
            text += '\n' + t('app.newer', version=self.latest['version'])
        if getattr(self, 'latest_error', None) and not self.latest:
            text += '\n' + t('app.offline', error=self.latest_error)
        self.pkg_label.configure(text=text)
        self.pkg_download.configure(text=t('app.download') if (newer or not self.latest) else t('app.checkUpdates'))
        self.pkg_download.state(['!disabled'] if idle else ['disabled'])
        # the output folder
        out = self.output_folder()
        self.out_var.set(out or '')
        # build
        missing = [desktop.GAME_NAMES[g] for g in desktop.GAMES if g not in self.slots]
        if self.busy:
            why = ''
        elif missing:
            why = t('patch.missing', list=', '.join(missing))
        else:
            why = t('app.ready')
        self.why_label.configure(text=why)
        self.build_button.state(['!disabled'] if idle and not missing else ['disabled'])
        self.stop_button.state(['!disabled'] if self.busy in ('build', 'download') and not self.cancel.is_set()
                               else ['disabled'])

    def output_folder(self):
        if self.config.get('output'):
            return self.config.get('output')
        if 'us' in self.slots:
            return desktop.default_output(self.slots['us']['image'])
        return ''

    def _restore(self):
        for game, (entry, reason) in self.config.remembered_discs().items():
            if reason:
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
        threading.Thread(target=run, daemon=True).start()

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
        self.busy = None
        self.cancel.clear()
        self._refresh()

    def _on_error(self, e, tb, quiet):
        if quiet:
            self.latest_error = str(getattr(e, 'reason', None) or e)
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
        text = self.t(e.key, **params)
        if e.game and e.key.startswith('why.'):
            text += '\n' + self.t('works.' + e.game)
        return text

    # -- discs
    def _filetypes(self):
        return [(self.t('app.discFiles'), '*.cue *.bin *.iso *.img'), (self.t('app.allFiles'), '*')]

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
                found, bad = desktop.sort_files([p], lambda _i, n, f, i=i: progress(i, n, f), self.cancel)
                for game, r in found.items():
                    self.events.put(('disc', game, r))
                problems += bad
                if i in current:
                    self.events.put(('checked', current[i]))
            if problems:
                self.events.put(('problems', problems))
        self._spawn(job, busy='check')

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

    def _download(self):
        if self.latest and (not self.package or desktop.version_key(self.latest['version'])
                            > desktop.version_key(self.package['version'])):
            self._spawn(self._job_download, busy='download')
        else:
            self._spawn(self._job_latest_checked, busy='download')

    def _job_latest_checked(self):
        latest = desktop.latest_release()
        self.events.put(('latest', latest))
        if not self.package or desktop.version_key(latest['version']) > desktop.version_key(self.package['version']):
            self._job_download(latest)
        else:
            self.events.put(('stage', self.t('app.upToDate'), 'TLabel'))

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

    def _use_file(self):
        from tkinter import filedialog
        path = filedialog.askopenfilename(parent=self.root, title=self.t('app.choosePackage'),
                                          filetypes=[(self.t('app.packageFiles'), '*.tar.gz *.tgz'),
                                                     (self.t('app.allFiles'), '*')])
        if path:
            def job():
                self.events.put(('stage', self.t('app.verifying'), 'TLabel'))
                info = desktop.install_file(path)
                self.events.put(('package', dict(info, name=os.path.basename(info['folder']), source='file')))
            self._spawn(job, busy='download')

    # -- output and build
    def _browse(self):
        from tkinter import filedialog
        path = filedialog.askdirectory(parent=self.root, title=self.t('app.output'),
                                       initialdir=self.output_folder() or os.path.expanduser('~'))
        if path:
            self.config.set('output', path)
            self._refresh()

    def _language(self, _event=None):
        name = self.lang_var.get()
        code = next(k for k, v in LANGS.items() if v == name)
        self.config.set('language', code)
        self.lang = code
        self.t = Strings(code)
        self._build()

    def _build_disc(self):
        out = self.output_folder()
        problems = desktop.space_problems(out)
        for game, r in self.slots.items():
            why = desktop.file_changed(r)
            if why:
                self.slots.pop(game)
                self.notes[game] = ('app.' + why, dict(path=r['path']))
                self.config.forget_disc(game)
                self._refresh()
                return
        if problems:
            from tkinter import messagebox
            if not messagebox.askokcancel(self.t('app.title'), '\n\n'.join(self.t(k, **p) for k, p in problems)
                                          + '\n\n' + self.t('app.continueAnyway'), parent=self.root):
                return
        for w in self.finish.winfo_children():
            w.destroy()
        self._spawn(self._job_build, out, busy='build')

    def _job_build(self, out):
        """Build pressed: the latest release is asked for (a newer one is downloaded first, a package file the
        player chose is kept); offline, the package already here is used."""
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
                           > desktop.version_key(package['version'])):
                package = self._job_download(latest)
        self.events.put(('stage', self.t('now.start'), 'TLabel'))
        dw = desktop.load_patcher(package['folder'])
        dw.CANCEL = self.cancel
        self.patcher = dw
        try:
            result = dw.apply_disc(self.slots['us']['image'], desktop.source_disc_args(self.slots), output=out,
                                   release=package['folder'])
        except BaseException as e:
            self.events.put(('failed', e, getattr(e, 'log', None), isinstance(e, getattr(dw, 'Stopped', ()))))
            return
        finally:
            self.patcher = None
        self.events.put(('built', result))

    def _on_built(self, result):
        self.progress['value'] = 1000
        self.stage.configure(text=self.t('app.done', file=os.path.basename(result['cue'])) + '\n' + result['cue'],
                             style='Ok.TLabel')
        self._finish_buttons(os.path.dirname(result['cue']), result.get('log'))

    def _on_failed(self, e, log, stopped):
        if stopped:
            text = self.t('app.stopped')
        elif isinstance(e, Exception) and type(e).__name__ == 'PatchError' or hasattr(e, 'log') and not \
                isinstance(e, OSError):
            text = self.t('app.failed', message=str(e)) if type(e).__name__ == 'PatchError' else \
                self.t('app.unexpected', error=f'{type(e).__name__}: {e}')
        else:
            text = self._message(e)
        self.progress['value'] = 0
        self.stage.configure(text=text, style='Bad.TLabel')
        if log:
            self._finish_buttons(None, log)

    def _finish_buttons(self, folder, log):
        ttk = self.ttk
        for w in self.finish.winfo_children():
            w.destroy()
        if folder:
            ttk.Button(self.finish, text=self.t('app.openFolder'),
                       command=lambda: desktop.open_folder(folder)).grid(row=0, column=0, padx=(0, 6))
        if log and os.path.exists(log):
            ttk.Button(self.finish, text=self.t('app.openLog'),
                       command=lambda: desktop.open_folder(log)).grid(row=0, column=1)

    def _stop(self):
        self.cancel.set()
        self.stage.configure(text=self.t('app.cancelling'), style='TLabel')
        self._refresh()

    def close(self):
        if self.busy == 'build':
            from tkinter import messagebox
            if not messagebox.askokcancel(self.t('app.title'), self.t('app.quitBuilding'), parent=self.root):
                return
            self.cancel.set()
            deadline = time.time() + 15
            while self.patcher is not None and time.time() < deadline:   # derive's processes are killed
                self.root.update(); time.sleep(0.1)
        self.root.destroy()


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
    root.minsize(640, 560)
    root.mainloop()
    return 0


if __name__ == '__main__':
    sys.exit(main())
