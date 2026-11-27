"""Put the player's patched disc inside the Windows setup template (docs/player.md, "A setup wizard"): one setup program
that installs Horizon Play and the game with nothing to choose. The disc never leaves the player's computer: the
patcher writes this setup next to the disc it built.

    python3 tools/patcher/setup_exe.py TEMPLATE.exe DISC.cue OUT.exe

The template is `Horizon-Setup.exe` (tools/player/installer.py, no game inside). It is copied as it is and the disc is
appended after the end of its data (NSIS reads only the length its first header records, and the template is built with
CRCCheck off, so the extra bytes are ignored); at install time `horizon-play.exe --unpack` (tools/player/horizon_play.c)
reads the trailer back. The layout of what is appended, all numbers little endian:

    BIN bytes | CUE text | bin size u64 | cue size u32 | format version u32 | magic "HZSETUP1"

The cue text is the player's cue with its one FILE line renamed to DISC_NAME.bin; the unpacker writes DISC_NAME.bin and
DISC_NAME.cue. One .bin per disc. Standard library only, so it is frozen into the desktop patcher like apk.py.
"""
import os
import re
import shutil
import struct
import sys

DISC_NAME = 'Digimon World Horizon'   # also in tools/player/installer.py and horizon_play.c
MAGIC = b'HZSETUP1'
VERSION = 1
TRAILER = struct.Struct('<QII8s')
CHUNK = 1 << 20


class SetupError(Exception):
    pass


def read_cue(cue):
    """(the cue text with its FILE renamed, the .bin it names)."""
    with open(cue, 'rb') as f:
        raw = f.read(1 << 16)
    try:
        text = raw.decode('utf-8-sig')
    except UnicodeDecodeError:
        text = raw.decode('latin-1')
    names = [m[1] or m[2] for m in
             (re.match(r'^\s*FILE\s+(?:"([^"]+)"|(\S+))', ln, re.I) for ln in text.splitlines()) if m]
    if not names:
        raise SetupError(f'{cue}: no FILE line, so no disc image')
    if len(names) != 1:
        raise SetupError(f'{cue}: {len(names)} tracks; the setup takes a disc of one .bin')
    image = os.path.join(os.path.dirname(os.path.abspath(cue)), names[0])
    if not os.path.isfile(image):
        raise SetupError(f'{cue}: {names[0]} is missing')
    text = re.sub(r'^(\s*FILE\s+)(?:"[^"]+"|\S+)', lambda m: f'{m[1]}"{DISC_NAME}.bin"', text, count=1,
                  flags=re.I | re.M)
    return '\r\n'.join(text.splitlines()) + '\r\n', image


def build(template, cue, out, progress=None):
    """Write OUT: a copy of TEMPLATE with the disc of CUE appended. progress(done, total) counts bytes."""
    if not os.path.isfile(template):
        raise SetupError(f'{template}: no setup template')
    text, image = read_cue(cue)
    cue_bytes = text.encode('utf-8')
    size = os.path.getsize(image)
    if size == 0:
        raise SetupError(f'{image} is empty')
    total = os.path.getsize(template) + size
    done = 0
    tmp = out + '.new'
    try:
        with open(tmp, 'wb') as dst:
            for src_path in (template, image):
                with open(src_path, 'rb') as src:
                    while True:
                        block = src.read(CHUNK)
                        if not block:
                            break
                        dst.write(block)
                        done += len(block)
                        if progress:
                            progress(done, total)
            dst.write(cue_bytes)
            dst.write(TRAILER.pack(size, len(cue_bytes), VERSION, MAGIC))
        os.replace(tmp, out)
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)
    return out


def read_trailer(path):
    """(bin size, cue size, version) of a setup that has a disc inside, else None."""
    with open(path, 'rb') as f:
        f.seek(0, os.SEEK_END)
        end = f.tell()
        if end < TRAILER.size:
            return None
        f.seek(end - TRAILER.size)
        size, cue_size, version, magic = TRAILER.unpack(f.read(TRAILER.size))
    if magic != MAGIC or size + cue_size + TRAILER.size > end:
        return None
    return size, cue_size, version


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
    except SetupError as e:
        sys.exit(str(e))
    sys.stderr.write('\n')
    print(f'{a[2]}: {os.path.getsize(a[2]) // (1024 * 1024)} MB')


if __name__ == '__main__':
    main()
