#!/usr/bin/env python3
"""Other releases of Digimon World as the base disc: their files laid out as the USA dump (extracted/) the build reads.

The mod is built on Digimon World (USA), SLUS-01032. The European releases (English SLES-02914, French SLES-03435,
German SLES-03434, Spanish SLES-03436, Italian SLES-03437) carry the same game data: every model, map, sound bank,
battle and door file is byte-identical to the USA one (2026-10-25, docs/patcher.md "Regional disc inputs"). What
differs, file by file of the USA dump, is one of:

  same       byte-identical under the same path
  renamed    byte-identical under another path (ETCDAT/ETCTIM.BIN is the European ETCTIM_E.BIN)
  patch      nearly the same file: rebuilt from the release's one by a patch kept here
             (license_data.dat, the license sectors: "Europe")
  own        the release's own file is used as it is: Europe's title artwork (then stamped with HORIZON), and the
             four STR movies (PAL masters: MDEC 320x176, 15 fps, XA 37.8 kHz; the Japanese discs' own films)
  localize   text baked into images (the Japanese discs: the menus' and battles' words, the title, the dot-letter
             signposts of five maps): USA bytes we may not carry, so our own recipes make the file from the release's
             one (the release's LOCALIZE tool, tools/localize/fromjp.py). Kept here: the regions the recipes may
             change (the pixel and CLUT blocks of each TIM that differs), the SHA-1 of the USA file with them zeroed
             (what the result must match everywhere else) and, when other bytes differ too, a patch of them (the five
             maps' collision and a warp, which the USA release changed). For GIAS00, FRZL03 and MAYO00 the
             player's enemy lists stay until content/maps regenerates them; MAYO00 also keeps its two hidden
             sprites' unused sorting coordinates. See docs/mods/japanese-map-remainder.md.
  differs    game data of the release that differs from the USA file and has no recipe (the Japanese first
             pressing: 5 models, ETCHI/EFEDAT.EFE, 11 maps): `prepare` stops; the release is not a base
  needs-usa  no counterpart: code and scripts the patched disc replaces with ours (the executable, the overlays,
             SCN/DG.SCN, SCN/MAPHEAD.SCN, SYSTEM.CNF). The build no longer reads them (2026-10-25: the tables are
             committed, the story is story/base, the disc layout tools/disc-layout.xml, SYSTEM.CNF written, SHOP_REL.BIN
             zeros), so `prepare`'s tree is a complete base: the full disc built from the Spanish one differs from the
             USA-based one only in regional title artwork, MOVIE/OP1.STR, OP2.STR and their FILE_OFFSET_TABLE entries.

  basedisc.py make RELEASE DUMP          DUMP: the release dumped with dumpsxiso (tools/extract.sh does it for the USA
                                         disc); writes mods/base-discs/dw1-RELEASE.json (the mapping, the patches,
                                         the USA files' SHA-1)
  basedisc.py prepare RELEASE DUMP OUT   OUT/extracted laid out as the USA dump: every same/renamed/patch file checked
                                         against the USA file's SHA-1, the movies taken as they are, the localize
                                         files made by the release's tool and checked; prints what is still
                                         missing (needs-usa)

The Japanese releases (jp: SLPS-01797, jp1: its Rev 1) boot the same file: told apart by the executable's SHA-1.

A patch rebuilds the USA file from the release's one as ops: {"copy": [offset, length]} from the release's file,
{"data": "hex"} the bytes it does not have (USA bytes: kept to what differs, a few hundred bytes per release),
{"fill": [byte, length]} a run of one byte (the USA license sectors' zeros).
"""
import hashlib
import json
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
USA = os.path.join(ROOT, 'extracted')
OUT_DIR = os.path.join(ROOT, 'mods', 'base-discs')

OWN = ('MOVIE/ED2.STR', 'MOVIE/EDR.STR', 'MOVIE/OP1.STR', 'MOVIE/OP2.STR')
NEEDS_USA = ('SLUS_010.32', 'SCN/DG.SCN', 'SCN/MAPHEAD.SCN', 'SYSTEM.CNF')   # + every *_REL.BIN that differs
EU_PATCHED = ('license_data.dat',)
EU_OWN = ('ETCNA/TITLE256.TIM', 'ETCNA/TITLE2.TIM')  # stamp each European disc's own title artwork
# The Japanese discs' baked text (2026-10-25, measured on both against the USA dump): the menu, status, tech and
# shop words (ETCDAT: SYSTEM_W.TIM, FI_INFO.TIM, BI_IN.TIM and their copies in ETCTIM.BIN), the title logo (ETCNA),
# the VS mode and the arena letters (STDDAT), and the 256x256 sign TIM of five maps.
JP_LOCALIZE = ('ETCDAT/BI_IN.TIM', 'ETCDAT/ETCTIM.BIN', 'ETCDAT/FI_INFO.TIM', 'ETCDAT/SYSTEM_W.TIM',
               'ETCNA/TITLE2.TIM', 'ETCNA/TITLE256.TIM', 'STDDAT/STDTIM.BIN', 'STDDAT/TAISEN_F.TIM',
               'MAP/MAP5/GIAS00.MAP', 'MAP/MAP7/FRZL03.MAP', 'MAP/MAP8/MAYO00.MAP', 'MAP/MAP8/MAYO01_2.MAP',
               'MAP/MAP8/MAYO02_2.MAP')
JP_TOOL = 'tools/localize/fromjp.py'
EU = dict(patched=EU_PATCHED, localize=(), tool=None)
JP = dict(patched=('license_data.dat',), localize=JP_LOCALIZE, tool=JP_TOOL)
RELEASES = {
    'eu': dict(EU, boot='SLES_029.14'), 'fr': dict(EU, boot='SLES_034.35'), 'de': dict(EU, boot='SLES_034.34'),
    'es': dict(EU, boot='SLES_034.36'), 'it': dict(EU, boot='SLES_034.37'),
    # SLPS-01797 and its Rev 1 boot the same file name (tools/discs.py: jp, jp-rev1)
    'jp': dict(JP, boot='SLPS_017.97', exe_sha1='d11336b31aeceec48267062676e9c3f0833ec13f'),
    'jp1': dict(JP, boot='SLPS_017.97', exe_sha1='82212496037146885e96573bd43aa3f0f4ccee8e'),
}
MAX_LOCALIZE_PATCH = 1024       # USA bytes outside the text a localize file may carry (the five maps: 261-577)


def sha1(b):
    return hashlib.sha1(b).hexdigest()


def files(root):
    out = {}
    for dp, _, fs in os.walk(root):
        for f in fs:
            p = os.path.join(dp, f)
            out[os.path.relpath(p, root).replace(os.sep, '/')] = p
    return out


def read(path):
    with open(path, 'rb') as f:
        return f.read()


def manifest_path(rel):
    return os.path.join(OUT_DIR, f'dw1-{rel}.json')


def make_patch(src, dst):
    """Ops rebuilding `dst` from `src` (same-length files that differ in places: runs of differing bytes travel)."""
    if len(src) != len(dst):
        raise SystemExit('basedisc: a patch needs files of the same length')
    ops, i, n = [], 0, len(dst)
    while i < n:
        j = i
        while j < n and src[j] == dst[j]:
            j += 1
        if j > i:
            ops.append({'copy': [i, j - i]})
        k = j
        while k < n and (src[k] != dst[k] or (k + 8 < n and src[k + 1:k + 9] != dst[k + 1:k + 9])):
            k += 1                              # short equal gaps inside a changed run stay in it
        ops += data_ops(dst[j:k])
        i = k
    return ops


def data_ops(b, min_fill=32):
    """{"data"} ops for `b`, with runs of one byte (min_fill or longer) as {"fill"}."""
    ops, i, start = [], 0, 0
    while i < len(b):
        j = i
        while j < len(b) and b[j] == b[i]:
            j += 1
        if j - i >= min_fill:
            if i > start:
                ops.append({'data': b[start:i].hex()})
            ops.append({'fill': [b[i], j - i]})
            start = j
        i = j
    if start < len(b):
        ops.append({'data': b[start:].hex()})
    return ops


def apply_patch(ops, src):
    out = bytearray()
    for op in ops:
        if 'copy' in op:
            o, length = op['copy']
            out += src[o:o + length]
        elif 'fill' in op:
            out += bytes([op['fill'][0]]) * op['fill'][1]
        else:
            out += bytes.fromhex(op['data'])
    return bytes(out)


def patch_bytes(ops):
    """USA bytes a patch carries (a fill counts as one)."""
    return sum(len(o['data']) // 2 if 'data' in o else 1 for o in ops if 'copy' not in o)


def tims_in(b):
    """[(offset, end, [(data offset, length) of the CLUT and pixel blocks])] of every TIM found in `b`."""
    out, o, n = [], 0, len(b)
    while o + 20 <= n:
        if b[o:o + 4] == b'\x10\0\0\0' and b[o + 4] in (0, 1, 2, 8, 9) and b[o + 5:o + 8] == b'\0\0\0':
            p, blocks, ok = o + 8, [], True
            for has in ((b[o + 4] & 8) != 0, True):
                if not has:
                    continue
                if p + 12 > n:
                    ok = False
                    break
                length = int.from_bytes(b[p:p + 4], 'little')
                w, h = int.from_bytes(b[p + 8:p + 10], 'little'), int.from_bytes(b[p + 10:p + 12], 'little')
                if not w or not h or length != 12 + w * h * 2 or p + length > n:
                    ok = False
                    break
                blocks.append((p + 12, length - 12))
                p += length
            if ok:
                out.append((o, p, blocks))
                o = p
                continue
        o += 1
    return out


def masked(b, regions):
    m = bytearray(b)
    for o, length in regions:
        m[o:o + length] = bytes(length)
    return bytes(m)


def check_release(rel, dump):
    r = RELEASES[rel]
    if boot_of(dump) != r['boot']:
        raise SystemExit(f'basedisc: {dump} boots {boot_of(dump)}, not the {rel} release ({r["boot"]})')
    if r.get('exe_sha1') and sha1(read(os.path.join(dump, r['boot']))) != r['exe_sha1']:
        others = [k for k, v in RELEASES.items() if v.get('exe_sha1') == sha1(read(os.path.join(dump, r['boot'])))]
        raise SystemExit(f'basedisc: {dump} is not the {rel} release' + (f' (it is {others[0]})' if others else ''))


def boot_of(dump):
    cnf = open(os.path.join(dump, 'SYSTEM.CNF'), encoding='latin-1').read()
    return cnf.split('cdrom:')[1].lstrip('\\').split(';')[0].strip().upper()


def localize_entry(k, src, dst):
    """The localize mapping of USA file `dst` from the release's `src`: the blocks of the TIMs that differ are the
    recipes'; whatever else differs is patched (at most MAX_LOCALIZE_PATCH bytes)."""
    if len(src) != len(dst):
        raise SystemExit(f'basedisc: {k}: the release\'s file is not the USA one\'s size')
    if k in ('MAP/MAP5/GIAS00.MAP', 'MAP/MAP7/FRZL03.MAP', 'MAP/MAP8/MAYO00.MAP'):
        # The build replaces these enemy lists from content/maps before either
        # story compilation or balance output. Keep the player's list in the
        # intermediate file instead of shipping discarded USA stats. Check the
        # actual content generator, including variable-length paths and tails;
        # sprite ordering, warps and collision must still be normalized here.
        import struct
        import content
        count = int.from_bytes(src[:4], 'little') // 4
        offsets = struct.unpack_from(f'<{count}I', src)
        if src[:4 * count] != dst[:4 * count]:
            raise SystemExit(f'basedisc: {k}: map section layout differs')
        start, end = offsets[-2] + 120, offsets[-1]
        own = dst[:start] + src[start:end] + dst[end:]
        name = os.path.basename(k)[:-4]
        if content.build_map(name, own) != content.build_map(name, dst):
            raise SystemExit(f'basedisc: {k}: player enemy list changes generated gameplay')
        dst = own
        if name == 'MAYO00':
            # Sprites 26/27 belong only to hidden instances 28/29. Native
            # Forest script 105 only hides them again; the common day/night
            # visibility handler applies to screen 183, not this screen 109.
            # Their Y affects sorting but renderMapOverlays skips flag == 1.
            # Keep Japan's unused sort values rather than USA's two shorts.
            import dwmap
            original, target_map = dwmap.MapFile(src), dwmap.MapFile(dst)
            for sprite, instance in ((26, 28), (27, 29)):
                for m in (original, target_map):
                    users = [i for i, obj in enumerate(m.instances) if sprite in obj['frames']]
                    if users != [instance] or m.instances[instance]['flag'] != 1:
                        raise SystemExit(f'basedisc: {k}: sprite {sprite} is no longer exclusively hidden')
                target_map.sprites[sprite]['y'] = original.sprites[sprite]['y']
            dst = target_map.build()
    regions = [blk for o, end, blocks in tims_in(dst) if src[o:end] != dst[o:end] for blk in blocks]
    if not regions:
        raise SystemExit(f'basedisc: {k}: no TIM of it differs (not a localize file)')
    e = dict(how='localize', source=k, from_sha1=sha1(src), regions=[list(r) for r in regions],
             masked_sha1=sha1(masked(dst, regions)))
    target = bytearray(dst)
    for o, length in regions:
        target[o:o + length] = src[o:o + length]
    if bytes(target) != src:
        ops = make_patch(src, bytes(target))
        if patch_bytes(ops) > MAX_LOCALIZE_PATCH:
            raise SystemExit(f'basedisc: {k}: {patch_bytes(ops)} bytes differ outside its TIMs')
        e['ops'] = ops
    return e


def cmd_make(rel, dump):
    check_release(rel, dump)
    cfg = RELEASES[rel]
    us, mine = files(USA), files(dump)
    by_hash = {}
    for k, p in mine.items():
        by_hash.setdefault(sha1(read(p)), k)
    out = dict(release=rel, boot=cfg['boot'], note='tools/basedisc.py make: do not edit by hand', files={})
    if cfg.get('exe_sha1'):
        out['exe_sha1'] = cfg['exe_sha1']
    if cfg['tool']:
        out['localize_tool'] = cfg['tool']
    counts, data_bytes = {}, {}
    for k in sorted(us):
        b = read(us[k])
        h = sha1(b)
        if k in mine and sha1(read(mine[k])) == h:
            e = dict(how='same')
        elif h in by_hash:
            e = dict(how='renamed', source=by_hash[h])
        elif k in OWN or rel in ('eu', 'fr', 'de', 'es', 'it') and k in EU_OWN:
            e = dict(how='own', source=k)
        elif k in cfg['patched'] and k in mine:
            ops = make_patch(read(mine[k]), b)
            data_bytes[k] = patch_bytes(ops)
            e = dict(how='patch', source=k, from_sha1=sha1(read(mine[k])), ops=ops)
        elif k in cfg['localize'] and k in mine:
            e = localize_entry(k, read(mine[k]), b)
            if 'ops' in e:
                data_bytes[k] = patch_bytes(e['ops'])
        elif k in NEEDS_USA or k.endswith('_REL.BIN'):
            e = dict(how='needs-usa')
        else:
            e = dict(how='differs')
        e['sha1'] = h
        out['files'][k] = e
        counts[e['how']] = counts.get(e['how'], 0) + 1
    os.makedirs(OUT_DIR, exist_ok=True)
    with open(manifest_path(rel), 'w') as f:
        json.dump(out, f, indent=1)
        f.write('\n')
    print(f'{manifest_path(rel)}: {counts}, {sum(data_bytes.values())} bytes of USA data in the patches')
    for k, n in data_bytes.items():
        print(f'  {out["files"][k]["how"]} {k}: {n} bytes')
    for how in ('localize', 'needs-usa', 'differs'):
        ks = [k for k, e in out['files'].items() if e['how'] == how]
        if ks:
            print(f'  {how}:', ', '.join(ks))


def cmd_prepare(rel, dump, out):
    m = json.load(open(manifest_path(rel)))
    check_release(rel, dump)
    differs = [k for k, e in m['files'].items() if e['how'] == 'differs']
    if differs:
        raise SystemExit(f'basedisc: the {rel} release is not a base: {len(differs)} of its game files differ from '
                         f'the USA ones and have no recipe: {", ".join(differs)}')
    dst_root = os.path.join(out, 'extracted')
    loc = {k: e for k, e in m['files'].items() if e['how'] == 'localize'}
    made = {}
    if loc:
        for k, e in loc.items():
            if sha1(read(os.path.join(dump, e['source']))) != e['from_sha1']:
                raise SystemExit(f'basedisc: {e["source"]} is not the {rel} release\'s file')
        tool = os.path.join(ROOT, m['localize_tool'])
        if not os.path.exists(tool):
            raise SystemExit(f'basedisc: {len(loc)} files of the {rel} release carry baked Japanese text and are made '
                             f'by {m["localize_tool"]}, which does not exist yet:\n  ' + '\n  '.join(loc))
        loc_dir = os.path.join(out, 'localize')
        shutil.rmtree(loc_dir, ignore_errors=True)
        os.makedirs(loc_dir)
        subprocess.run([sys.executable, tool, loc_dir, '--extracted', dump], check=True)
        listed = os.path.join(loc_dir, 'files.txt')
        done = set(open(listed).read().split()) if os.path.exists(listed) else set()
        left = [k for k in loc if k not in done]
        if left:
            raise SystemExit(f'basedisc: {m["localize_tool"]} did not make {len(left)} of the {rel} release\'s '
                             f'localize files:\n  ' + '\n  '.join(left))
        for k, e in loc.items():
            data = read(os.path.join(loc_dir, k))
            if 'ops' in e:
                if len(data) != len(read(os.path.join(dump, e['source']))):
                    raise SystemExit(f'basedisc: {m["localize_tool"]} changed the size of {k}')
                data = apply_patch(e['ops'], data)
            if sha1(masked(data, e['regions'])) != e['masked_sha1']:
                raise SystemExit(f'basedisc: {k}: {m["localize_tool"]} changed more than the text blocks '
                                 f'{e["regions"]}')
            made[k] = data
    missing = []
    for k, e in m['files'].items():
        dst = os.path.join(dst_root, k)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        if e['how'] == 'needs-usa':
            missing.append(k)
            continue
        if e['how'] == 'localize':
            data = made[k]
        else:
            data = read(os.path.join(dump, e.get('source', k)))
            if e['how'] == 'patch':
                if sha1(data) != e['from_sha1']:
                    raise SystemExit(f'basedisc: {e["source"]} is not the {rel} release\'s file')
                data = apply_patch(e['ops'], data)
            if e['how'] != 'own' and sha1(data) != e['sha1']:
                raise SystemExit(f'basedisc: {k} did not come out as the USA file')
        with open(dst, 'wb') as f:
            f.write(data)
    n = len(m['files']) - len(missing) - len(loc)
    print(f'{dst_root}: {n} of {len(m["files"])} USA files ({sum(e["how"] == "own" for e in m["files"].values())} '
          f'files of the {rel} release as they are)' + (f', {len(loc)} made in our words from the release\'s' if loc else ''))
    if missing:
        print(f'  not on this disc and not needed (the build makes its own): {", ".join(missing)}')
    return 0

def main(argv):
    if len(argv) < 3 or argv[0] not in ('make', 'prepare') or argv[1] not in RELEASES:
        print(__doc__)
        return 2
    if argv[0] == 'make':
        cmd_make(argv[1], argv[2])
    else:
        if len(argv) != 4:
            print(__doc__)
            return 2
        cmd_prepare(argv[1], argv[2], argv[3])
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
