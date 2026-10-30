#!/usr/bin/env python3
"""Other releases of Digimon World 2003's battle models, turned into the PAL files the import recipes are made from.

The recipes (content/imports/specs, the ones with "dw3") and everything built on them were made from
the PAL disc, SLES-03936. Digimon World 3 (USA), SLUS-01436, keeps the same models in AAA/DAT/MODEL/, and 15 of
the 57 the recipes use differ from the PAL files (meshes, animation tracks, bone order, the events section;
docs/patcher.md, "Regional disc inputs"). Instead of recipes per release, each of
those files is patched into the PAL file before anything reads it: the import then sees the same bytes from either
disc and builds the same Digimon. tools/dw3mmd.py applies it when its disc is not the PAL one. The Japanese
release (SLPS-03446) has every recipe model as the PAL disc does: its file holds only the checksums.

  dw3release.py make RELEASE     needs both discs ($DW3_ROOT/disc, the PAL one, and $DW3_DISC, the release's);
                                 writes content/imports/releases/dw3-RELEASE.json
  dw3release.py check RELEASE    every model the recipes use, read from $DW3_DISC through the patch, must equal
                                 the PAL file (by SHA-1); needs only the release's disc

A patch rebuilds the PAL file region by region, in file order (the offset table, then each section):
  {"copy": [offset, length], "what": ...}   bytes the release's file already has, at that offset
  {"data": "hex", "what": ...}              bytes it does not have: PAL model data, kept to what differs
"what" names the region: offset table, bone N mesh, bone N track, texture, hierarchy, animations, section N.
The file also lists the SHA-1 of every recipe model, so a model the release has unchanged is checked too.
"""
import difflib
import glob
import hashlib
import json
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
DW3_ROOT = os.environ.get('DW3_ROOT', os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'digimonworld2003'))
SPECS = os.path.join(ROOT, 'content', 'imports', 'specs')
OUT_DIR = os.path.join(ROOT, 'content', 'imports', 'releases')
PAL_MODELS = os.path.join(DW3_ROOT, 'disc', 'AAA', 'DAT', 'FIGHT', 'MODEL')


def sha1(b):
    return hashlib.sha1(b).hexdigest()


def recipe_models():
    """{model code: Digimon name} of every recipe made from DW2003."""
    out = {}
    for p in sorted(glob.glob(os.path.join(SPECS, '*.json'))):
        j = json.load(open(p))
        if 'dw3' in j:
            out[j['dw3']] = j.get('name', os.path.basename(p)[:-5])
    return out


def patch_path(rel):
    return os.path.join(OUT_DIR, f'dw3-{rel}.json')


# ------------------------------------------------------------------ making a patch

def regions(data):
    """(start, end, section index or None) of the offset table and every section, in file order. A section runs
    to the next larger non-zero offset (dw3_extra's slicing); empty slots (offset 0) have no region."""
    n = struct.unpack_from('<I', data, 0)[0] // 4
    offs = struct.unpack_from(f'<{n}I', data, 0)
    starts = sorted({o for o in offs if o})
    out = [(0, starts[0], None)]
    for k, o in enumerate(starts):
        end = starts[k + 1] if k + 1 < len(starts) else len(data)
        out.append((o, end, offs.index(o)))
    return out


def labels(data):
    """{section index: what it is}, from the hierarchy (dw3.model.find_hierarchy) and the usual first section."""
    sys.path.insert(0, DW3_ROOT)
    sys.path.insert(0, HERE)
    import dw3_extra
    import dw3.model
    secs = dw3_extra.sections_of(data)
    out = {0: 'animations'}
    try:
        hi, tex, entries = dw3.model.find_hierarchy(secs)
    except ValueError:
        return out
    out[hi], out[tex] = 'hierarchy', 'texture'
    for k, (_, mesh, track) in enumerate(entries, 1):
        out[mesh] = f'bone {k} mesh'
        if track:
            out[track] = f'bone {k} track'
    return out


def make_ops(pal, rel):
    """Ops that rebuild `pal` from `rel`."""
    what = labels(pal)
    rel_regions = {i: (a, b) for a, b, i in regions(rel)}
    ops = []

    def copy(o, n, w):
        if ops and 'copy' in ops[-1] and ops[-1]['what'] == w and sum(ops[-1]['copy']) == o:
            ops[-1]['copy'][1] += n
        else:
            ops.append({'copy': [o, n], 'what': w})

    def data(b, w):
        if ops and 'data' in ops[-1] and ops[-1]['what'] == w:
            ops[-1]['data'] += b.hex()
        else:
            ops.append({'data': b.hex(), 'what': w})

    for a, b, i in regions(pal):
        w = 'offset table' if i is None else what.get(i, f'section {i}')
        seg = pal[a:b]
        same = rel.find(seg) if seg else -1
        ra, rb = rel_regions.get(i, (0, 0)) if i is not None else (0, regions(rel)[0][1])
        if seg and rel[ra:rb] == seg:
            copy(ra, len(seg), w)
        elif seg and same >= 0:
            copy(same, len(seg), w)
        else:
            # rule: diff against the release's section of the same index; only the bytes it lacks travel
            sm = difflib.SequenceMatcher(None, rel[ra:rb], seg, autojunk=False)
            for op, i1, i2, j1, j2 in sm.get_opcodes():
                if op == 'equal':
                    copy(ra + i1, i2 - i1, w)
                elif j2 > j1:
                    data(seg[j1:j2], w)
    return ops


def apply_ops(ops, rel):
    out = bytearray()
    for op in ops:
        if 'copy' in op:
            o, n = op['copy']
            out += rel[o:o + n]
        else:
            out += bytes.fromhex(op['data'])
    return bytes(out)


def cmd_make(rel, rel_models):
    if rel == 'us':
        raise SystemExit('US normalization would store PAL game bytes; use the European World 2003 disc')
    models = recipe_models()
    out = dict(release=rel, note='tools/dw3release.py make: do not edit by hand', recipes={}, patches={})
    data_bytes = 0
    for code, name in sorted(models.items(), key=lambda kv: kv[1]):
        pal = open(os.path.join(PAL_MODELS, code + '.BIN'), 'rb').read()
        rp = os.path.join(rel_models, code + '.BIN')
        if not os.path.exists(rp):
            raise SystemExit(f'{code} ({name}): not on the {rel} disc')
        r = open(rp, 'rb').read()
        out['recipes'][code] = sha1(pal)
        if r == pal:
            continue
        ops = make_ops(pal, r)
        if apply_ops(ops, r) != pal:
            raise SystemExit(f'{code} ({name}): the patch does not rebuild the PAL file')
        n = sum(len(o['data']) // 2 for o in ops if 'data' in o)
        data_bytes += n
        out['patches'][code] = dict(name=name, from_sha1=sha1(r), ops=ops)
        print(f'{name:16} {code}: {len(ops)} ops, {n} bytes of PAL data '
              f'({", ".join(sorted({o["what"] for o in ops if "data" in o}))})')
    os.makedirs(OUT_DIR, exist_ok=True)
    with open(patch_path(rel), 'w') as f:
        json.dump(out, f, indent=1)
        f.write('\n')
    print(f'{patch_path(rel)}: {len(out["patches"])} of {len(models)} recipe models patched, '
          f'{data_bytes} bytes of PAL data')


# ------------------------------------------------------------------ using a patch

_loaded = {}


def to_pal(rel, code, data):
    """`data`, the release's file of model `code`, as the PAL file the recipes are made from. Models no recipe
    uses come back as they are."""
    if rel not in _loaded:
        p = patch_path(rel)
        if not os.path.exists(p):
            raise SystemExit(f'dw3release: no patch for the {rel} release ({p})')
        _loaded[rel] = json.load(open(p))
    pt = _loaded[rel]
    if pt.get('supported') is False:
        raise SystemExit('US World 3 normalization is not published; use the European World 2003 disc')
    if code not in pt['recipes']:
        return data
    if code in pt['patches']:
        entry = pt['patches'][code]
        if sha1(data) != entry['from_sha1']:
            raise SystemExit(f'dw3release: {code} on this disc is not the {rel} release\'s file')
        data = apply_ops(entry['ops'], data)
    if sha1(data) != pt['recipes'][code]:
        raise SystemExit(f'dw3release: {code} from the {rel} release did not come out as the PAL file')
    return data


def cmd_check(rel, rel_models):
    pt = json.load(open(patch_path(rel)))
    for code in sorted(pt['recipes']):
        to_pal(rel, code, open(os.path.join(rel_models, code + '.BIN'), 'rb').read())
    print(f'{rel}: all {len(pt["recipes"])} recipe models come out as the PAL files '
          f'({len(pt["patches"])} through the patch)')


def main(argv):
    if len(argv) != 2 or argv[0] not in ('make', 'check'):
        print(__doc__)
        return 2
    import dw3mmd
    if 'DW3_DISC' not in os.environ:
        raise SystemExit('dw3release: set DW3_DISC to the extracted disc of the release')
    rel, models_dir = dw3mmd.release()
    if rel != argv[1]:
        raise SystemExit(f'dw3release: {os.environ["DW3_DISC"]} is the {rel} release, not {argv[1]}')
    rel_models = os.path.join(dw3mmd.disc_dir(), models_dir)
    (cmd_make if argv[0] == 'make' else cmd_check)(rel, rel_models)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
