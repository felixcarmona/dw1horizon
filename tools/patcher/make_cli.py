"""The desktop patcher's make buttons from a terminal, all at once (docs/patcher.md, "From a terminal"): the discs in,
the patched disc and every installer out, nothing to click.

    python3 tools/patcher/make_cli.py DISC... --out FOLDER [--only disc,apk,setup,mac,linux]
                                      [--package horizon-package.tar.gz] [--templates FOLDER] [--tag vX.Y.Z]

The frozen app runs the same with `--make` first ("Horizon Patcher.app/Contents/MacOS/Horizon Patcher" --make ...).

DISC: the four discs (Digimon World USA, Digital Card Battle, Digimon World 2, Digimon World 2003), each a .cue, .bin,
.chd or .pbp, in any order: each is recognised as the window's drop does. The package is the latest release's
(downloaded and checked as the window does) unless --package names a package file. Each installer's template comes
from the release of that package, or from --templates: a folder holding them under their release names
(Horizon-Play.apk, Horizon-Setup.exe, Horizon-Play-macOS.zip or a Horizon Play .app, Horizon-Play-Linux-x86_64.tar.gz),
as CI's artifacts give them for a build that is not released. The disc is built once and kept in the cache folder, as
the window keeps it. Exit code 0 when everything asked for was made.
"""
import argparse
import os
import sys
import tempfile
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import desktop  # noqa: E402

KINDS = ('disc',) + desktop.TEMPLATE_KINDS


def say(text):
    print(text, flush=True)


class Bar:
    """A percentage on one line, rewritten (stderr), at most once a second unless it changed by 10 points."""
    def __init__(self, what):
        self.what, self.last, self.at = what, -100, 0

    def __call__(self, done, total):
        pct = done * 100 // total if total else 0
        now = time.monotonic()
        if pct - self.last >= 10 or (pct != self.last and now - self.at >= 1):
            self.last, self.at = pct, now
            sys.stderr.write(f'\r  {self.what}: {pct}%   ')
            sys.stderr.flush()

    def end(self):
        if self.last >= 0:
            sys.stderr.write('\n')


def problem_text(e):
    if isinstance(e, desktop.Problem):
        params = ', '.join(f'{k}={v}' for k, v in getattr(e, 'params', {}).items())
        return f'{e.key}' + (f' ({params})' if params else '')
    return str(e)


def local_template(kind, folder):
    """The template of `kind` in FOLDER, or None (the Mac one: a .app, or the zip unpacked once beside it)."""
    path = os.path.join(folder, desktop.TEMPLATES[kind])
    if kind == 'mac':
        apps = [n for n in os.listdir(folder) if n.endswith('.app')]
        if apps:
            return os.path.join(folder, apps[0])
        if os.path.isfile(path):
            return desktop.unzip_app(path, tempfile.mkdtemp(prefix='horizon-mac-'))
        return None
    return path if os.path.isfile(path) else None


def get_package(args):
    if args.package:
        say(f'package: {args.package}')
        return desktop.install_file(args.package)
    try:
        latest = desktop.latest_release()
    except OSError as e:
        kept = desktop.cached_packages()
        if not kept:
            raise
        say(f'offline ({e}): the package kept here, {kept[0]["version"]}')
        return kept[0]
    kept = [p for p in desktop.cached_packages() if p['version'] == latest['version']]
    if kept:
        say(f'package: {latest["version"]} (kept)')
        return kept[0]
    say(f'package: {latest["version"]}, downloading')
    bar = Bar('package')
    try:
        return desktop.install_release(latest, bar)
    finally:
        bar.end()


def build_disc(slots, package):
    key = desktop.disc_key(slots, package)
    disc = desktop.cached_disc(key)
    if disc:
        say('disc: the one built before from these discs (kept)')
        return disc
    say('disc: building (about 5 to 20 minutes)')
    dw = desktop.load_patcher(package['folder'])
    desktop.forget_built_disc()
    started = time.monotonic()
    try:
        result = dw.apply_disc(slots['us']['image'], desktop.source_disc_args(slots),
                               output=desktop.built_disc_dir(), release=package['folder'])
    except dw.PatchError as e:
        log = getattr(e, 'log', None)
        raise SystemExit(f'the build failed: {e}' + (f'\nlog: {log}' if log else ''))
    desktop.keep_built_disc(key, result, package['version'])
    say(f'disc: built in {desktop.clock(time.monotonic() - started)}')
    return desktop.cached_disc(key)


def main(argv=None):
    p = argparse.ArgumentParser(prog='make_cli.py', description=__doc__.split('\n\n')[0])
    p.add_argument('discs', nargs='+', help='the four discs, any order')
    p.add_argument('--out', required=True, help='the folder everything is written to')
    p.add_argument('--only', help='a comma list of ' + ', '.join(KINDS) + ' (default: all)')
    p.add_argument('--package', help='a horizon-package.tar.gz to build with (default: the latest release)')
    p.add_argument('--templates', help='a folder with the installers\' templates (default: the package\'s release)')
    p.add_argument('--tag', help='the release whose templates to download (default: the package\'s version)')
    args = p.parse_args(argv)
    kinds = [k.strip() for k in args.only.split(',')] if args.only else list(KINDS)
    bad = [k for k in kinds if k not in KINDS]
    if bad:
        p.error(f'unknown --only {", ".join(bad)}; choose from {", ".join(KINDS)}')
    out = os.path.abspath(args.out)
    os.makedirs(out, exist_ok=True)

    say('discs: checking')
    found, problems = desktop.sort_files(args.discs)
    for path, e in problems:
        say(f'  not usable: {path}: {problem_text(e)}')
    for game in desktop.GAMES:
        say(f'  {desktop.GAME_NAMES[game]}: {found[game]["path"] if game in found else "MISSING"}')
    missing = [desktop.GAME_NAMES[g] for g in desktop.GAMES if g not in found]
    if missing:
        raise SystemExit('missing: ' + ', '.join(missing))

    package = get_package(args)
    disc = build_disc(found, package)
    tag = args.tag or 'v' + (disc.get('version') or package['version']).lstrip('v')
    made, failed = [], []
    for kind in kinds:
        bar = Bar(kind)
        try:
            if kind == 'disc':
                path = desktop.copy_disc(disc, out, bar)
            else:
                source = local_template(kind, args.templates) if args.templates else None
                if args.templates and not source:
                    raise desktop.Problem('app.templateMissing', name=desktop.TEMPLATES[kind], tag=args.templates)
                fetch = Bar(f'{kind} template')
                path = desktop.make(kind, disc['cue'], tag, bar, fetch, out_dir=out, source=source)
                fetch.end()
            bar.end()
            say(f'{kind}: {path}')
            made.append(path)
        except (desktop.Problem, OSError) as e:
            bar.end()
            say(f'{kind}: FAILED: {problem_text(e)}')
            failed.append(kind)
    say(f'made {len(made)} of {len(kinds)} in {out}')
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
