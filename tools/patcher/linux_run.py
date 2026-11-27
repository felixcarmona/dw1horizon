"""Put the player's patched disc inside Horizon Play for Linux (docs/player.md): one self-extracting
`<disc>-Linux.run` that installs the game for the current user with nothing to choose. The disc never leaves the
player's computer: this is written next to the disc it built.

    python3 tools/patcher/linux_run.py Horizon-Play-Linux-x86_64.tar.gz DISC.cue OUT.run

The first argument is the Linux Horizon Play bundle (player.yml's tarball, or a folder). The result is a short POSIX sh
header followed by a tar.gz at a byte offset the header records (written streaming, one pass). Running it:

    ./OUT.run [--target DIR] [--no-start] [--uninstall]

installs (no sudo) into ${XDG_DATA_HOME:-~/.local/share}/digimon-world-horizon, writes a launcher in
~/.local/share/applications (and on the desktop folder, marked trusted when gio can), leaves uninstall.sh (which removes
what the installer put there and keeps the saves, ~/.local/share/Horizon/Horizon), and offers to start the game when run
in a terminal (a double click starts it). Standard library only, so it is frozen into the patcher like apk.py.
"""
import gzip
import io
import os
import sys
import tarfile

try:
    from . import setup_exe
except ImportError:
    import setup_exe

NAME = setup_exe.DISC_NAME
LEVEL = 4

HEADER = r'''#!/bin/sh
# {name}: installer made by the Horizon Patcher. It holds your own copy of the game: do not share it.
SKIP={skip:<10d}
NAME="{name}"
usage() {{
  echo "Usage: $0 [--target DIR] [--no-start] [--uninstall]"
  echo "Installs $NAME for the current user (no sudo). Default folder: ${{XDG_DATA_HOME:-$HOME/.local/share}}/digimon-world-horizon"
}}
target=; uninstall=; start=ask
while [ $# -gt 0 ]; do
  case "$1" in
    --target) [ $# -ge 2 ] || {{ usage; exit 2; }}; target=$2; shift 2 ;;
    --uninstall) uninstall=1; shift ;;
    --no-start) start=no; shift ;;
    -h|--help) usage; exit 0 ;;
    *) usage; exit 2 ;;
  esac
done
data=${{XDG_DATA_HOME:-$HOME/.local/share}}
dir=${{target:-$data/digimon-world-horizon}}
case "$dir" in /*) ;; *) dir=$(pwd)/$dir ;; esac
case "$dir" in *[\\\"\$\`]*) echo "The folder name may not hold quotes, backslashes, \$ or backticks." >&2; exit 2 ;; esac
if [ -n "$uninstall" ]; then
  if [ -f "$dir/uninstall.sh" ]; then exec sh "$dir/uninstall.sh"; fi
  echo "Nothing to uninstall in $dir" >&2; exit 1
fi
mkdir -p "$dir" || {{ echo "Cannot create $dir" >&2; exit 1; }}
echo "Installing $NAME into $dir ..."
tail -c +$((SKIP + 1)) "$0" | tar xzf - -C "$dir" || {{ echo "Unpacking failed (is there room on the disk?)" >&2; exit 1; }}
cue="$dir/{name}.cue"
apps=$data/applications
mkdir -p "$apps"
launcher="$apps/digimon-world-horizon.desktop"
cat > "$launcher" <<EOF
[Desktop Entry]
Type=Application
Name=$NAME
Comment=Digimon World: Horizon
Exec="$dir/horizon-play" "$cue"
Icon=$dir/icon.png
Path=$dir
Terminal=false
Categories=Game;
EOF
chmod +x "$launcher"
desk=$(xdg-user-dir DESKTOP 2>/dev/null)
copy=
if [ -n "$desk" ] && [ -d "$desk" ]; then
  copy="$desk/$NAME.desktop"
  cp "$launcher" "$copy" && chmod +x "$copy" && {{ gio set "$copy" metadata::trusted true 2>/dev/null || true; }}
fi
command -v update-desktop-database >/dev/null 2>&1 && update-desktop-database "$apps" 2>/dev/null
cat > "$dir/uninstall.sh" <<EOF
#!/bin/sh
# Removes $NAME: what the installer put in "$dir", the launchers. The saves (~/.local/share/Horizon/Horizon) stay.
rm -f "$launcher" "$copy"
while IFS= read -r n; do [ -n "\$n" ] && rm -rf "$dir/\$n"; done < "$dir/.manifest"
rm -f "$dir/.manifest" "$dir/uninstall.sh"
rmdir "$dir" 2>/dev/null
echo "$NAME removed. Your saves were kept."
EOF
chmod +x "$dir/uninstall.sh"
echo "Done. Start it from your applications menu, or: $dir/horizon-play \"$cue\""
if [ "$start" = ask ]; then
  if [ -t 0 ] && [ -t 1 ]; then
    printf "Start the game now? [Y/n] "; read -r a
    case "$a" in n|N|no|No) start=no ;; *) start=yes ;; esac
  elif [ -n "$DISPLAY$WAYLAND_DISPLAY" ]; then start=yes; else start=no; fi
fi
[ "$start" = yes ] && {{ cd "$dir" && nohup ./horizon-play "$cue" >/dev/null 2>&1 & }}
exit 0
'''


class LinuxRunError(Exception):
    pass


class Counting(io.RawIOBase):
    """Reads of a file, counted."""
    def __init__(self, path, tick):
        self.f = open(path, 'rb')
        self.tick = tick

    def readable(self):
        return True

    def readinto(self, b):
        n = self.f.readinto(b)
        self.tick(n or 0)
        return n

    def close(self):
        self.f.close()
        super().close()


def _strip(names):
    """The folder every entry sits under, when there is one (player.yml's tarball: "Horizon Play/")."""
    tops = {n.split('/')[0] for n in names if n not in ('.', './')}
    return tops.pop() if len(tops) == 1 and all('/' in n or n in tops for n in names) else ''


def _add_member(tar, info, fileobj, top, seen):
    name = info.name[2:] if info.name.startswith('./') else info.name
    if top:
        name = name[len(top):].lstrip('/')
    if not name:
        return
    info.name = name
    info.uid = info.gid = 0
    info.uname = info.gname = ''
    seen.add(name.split('/')[0])
    tar.addfile(info, fileobj if info.isreg() else None)


def build(player, cue, out, progress=None):
    """Write OUT (an executable .run): the Linux player (a .tar.gz or a folder) and the disc of CUE."""
    if not os.path.exists(player):
        raise LinuxRunError(f'{player}: no Linux Horizon Play bundle')
    text, image = setup_exe.read_cue(cue)
    from_dir = os.path.isdir(player)
    if from_dir:
        top = ''
        if not os.path.isfile(os.path.join(player, 'horizon-play')):
            raise LinuxRunError(f'{player}: no horizon-play inside')
        player_size = 1
    else:
        player_size = os.path.getsize(player)
    total = player_size + os.path.getsize(image)
    done = [0]

    def tick(n):
        done[0] += n
        if progress:
            progress(min(done[0], total), total)
    try:
        from . import make_icons
    except ImportError:
        sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'app'))
        import make_icons
    icon = make_icons.png(256)
    header = HEADER.format(name=NAME, skip=0)
    header = HEADER.format(name=NAME, skip=len(header.encode()))
    seen = set()
    tmp = out + '.new'
    try:
        with open(tmp, 'wb') as raw:
            raw.write(header.encode())
            # gzip by hand: tarfile's stream mode takes no compresslevel before Python 3.12
            with gzip.GzipFile(fileobj=raw, mode='wb', compresslevel=LEVEL, mtime=0) as gz, \
                    tarfile.open(fileobj=gz, mode='w|', format=tarfile.GNU_FORMAT) as tar:
                if from_dir:
                    for folder, dirs, files in os.walk(player):
                        dirs.sort()
                        for n in dirs + sorted(files):
                            path = os.path.join(folder, n)
                            rel = os.path.relpath(path, player).replace(os.sep, '/')
                            info = tar.gettarinfo(path, rel)
                            if info.isreg():
                                with open(path, 'rb') as f:
                                    _add_member(tar, info, f, '', seen)
                            else:
                                _add_member(tar, info, None, '', seen)
                    tick(1)
                else:
                    src = tarfile.open(fileobj=io.BufferedReader(Counting(player, tick)), mode='r|gz')
                    top = None
                    for info in src:
                        if top is None:   # a stream: the first entry shows the folder everything sits under
                            first = info.name[2:] if info.name.startswith('./') else info.name
                            top = first.split('/')[0] if '/' in first or info.isdir() else ''
                        _add_member(tar, info, src.extractfile(info) if info.isreg() else None, top, seen)
                    src.close()
                    if 'horizon-play' not in seen:
                        raise LinuxRunError(f'{player}: no horizon-play inside')
                disc = tarfile.TarInfo(NAME + '.bin')
                disc.size = os.path.getsize(image)
                disc.mode = 0o644
                with open(image, 'rb') as f:
                    class Reader:
                        def read(self, n=-1):
                            b = f.read(n if n and n > 0 else 1 << 20)
                            tick(len(b))
                            return b
                    tar.addfile(disc, Reader())
                for name, data, mode in ((NAME + '.cue', text.encode(), 0o644), ('icon.png', icon, 0o644)):
                    info = tarfile.TarInfo(name)
                    info.size, info.mode = len(data), mode
                    tar.addfile(info, io.BytesIO(data))
                    seen.add(name)
                seen.add(NAME + '.bin')
                manifest = ('\n'.join(sorted(seen | {'icon.png'})) + '\n').encode()
                info = tarfile.TarInfo('.manifest')
                info.size, info.mode = len(manifest), 0o644
                tar.addfile(info, io.BytesIO(manifest))
        os.chmod(tmp, 0o755)
        os.replace(tmp, out)
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)
    return out


def main(argv=None):
    a = sys.argv[1:] if argv is None else argv
    if len(a) != 3:
        sys.exit(__doc__.split('\n\n')[0])
    last = [-1]

    def show(done, total):
        pct = done * 100 // total
        if pct != last[0]:
            last[0] = pct
            sys.stderr.write(f'\r{pct}%')
    try:
        build(a[0], a[1], a[2], show)
    except (LinuxRunError, setup_exe.SetupError) as e:
        sys.exit(str(e))
    sys.stderr.write('\n')
    print(a[2])


if __name__ == '__main__':
    main()
