#!/usr/bin/env python3
"""Digimon World 2003 battle models the `dw3` package ($DW3_ROOT,
read only here) cuts short: the fix, and the import of the two Digimon it lost.

What was wrong. A model file starts with a table of u32 section offsets; an offset
of 0 means "no section here" (the packing tool leaves the slot empty). The `dw3`
package slices section i as data[off[i]:off[i+1]], so

  - an empty slot (offset 0) became data[0:next] - a copy of the start of the file,
    the "hierarchy overwritten on the disc" of its README;
  - the real section just before an empty slot became data[off:0] = empty.

When that real section is the hierarchy (M178KNGT Knightmon, M337ZAMB Zanbamon,
M080GOBR, M398GOB2, M391GRPL), the file did not parse at all. Nothing on the disc is
broken: the hierarchy, texture and every bone are in the files. The right slicing:
section i ends at the next larger non-zero offset (or the end of the file); an
empty slot is empty.

The same slicing also lost the texture section of the six "no texture in the file"
models (M054MGDR, M060HKAB, M230GKWA, M375TAOM, M440SIJN, M453TAO9: all have it) and
meshes/tracks of M013MAME, M137FLYM, M375TAOM, M377BLZB, M453TAO9, M456GRP9 and the
M457/M458/M463 card models. `patch()` fixes all of them in-process.

  dw3_extra.py check                      old vs fixed parse of every model on the disc
  dw3_extra.py export NAME OUT_DIR        NAME.glb + NAME.png (preview) with the fix
  dw3_extra.py import NAME CODE           imported/NAME/ like crossgame_sources.py
                                          --import does (glb, raw file, preview, info.json,
                                          index.tsv row)
  dw3_extra.py dw3mmd ARGS...             tools/dw3mmd.py with the fix applied

Other tools use it with `import dw3_extra; dw3_extra.patch()` before parsing.
Runs under the DW2003 project's venv (numpy, pillow).
"""
import glob
import json
import os
import shutil
import struct
import sys

DW3_ROOT = os.environ.get('DW3_ROOT', os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'digimonworld2003'))
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
MODEL_DIR = os.path.join(DW3_ROOT, 'disc', 'AAA', 'DAT', 'FIGHT', 'MODEL')
for p in (HERE, DW3_ROOT):
    if p not in sys.path:
        sys.path.insert(0, p)


def sections_of(data):
    """Sections of a model file; an offset of 0 is an empty slot, and a section runs
    to the next larger non-zero offset."""
    n = struct.unpack_from('<I', data, 0)[0] // 4
    offs = struct.unpack_from(f'<{n}I', data, 0)
    out = []
    for i, o in enumerate(offs):
        if o == 0:
            out.append(b'')
            continue
        nxt = [x for x in offs[i + 1:] if x > o]
        out.append(data[o:min(nxt) if nxt else len(data)])
    return out


def patch():
    """Makes dw3.model.parse_model (and everything built on it) use the fixed slicing."""
    import dw3.model
    if dw3.model.sections_of is not sections_of:
        dw3.model._orig_sections_of = dw3.model.sections_of
        dw3.model.sections_of = sections_of
    return dw3.model


def parse(code):
    m = patch()
    return m.parse_model(open(os.path.join(MODEL_DIR, code + '.BIN'), 'rb').read(), code)


def summary(m):
    return dict(bones=len(m.bones), prims=sum(len(b.mesh.prims) for b in m.bones),
                texture=bool(m.texture), anims=len(m.animations))


def cmd_check():
    import dw3.model
    patch()
    orig = dw3.model._orig_sections_of
    for path in sorted(glob.glob(os.path.join(MODEL_DIR, 'M*.BIN'))):
        data, code = open(path, 'rb').read(), os.path.basename(path)[:-4]
        if orig(data) == sections_of(data):
            continue
        dw3.model.sections_of = orig
        try:
            old = summary(dw3.model.parse_model(data, code))
        except Exception as ex:
            old = f'{type(ex).__name__}: {ex}'
        dw3.model.sections_of = sections_of
        print(code, 'old', old, 'fixed', summary(dw3.model.parse_model(data, code)))


def export(code, out_dir, name=None):
    """glb + preview png (front, 35 degrees, back) of one model."""
    from dw3.gltf import export_glb, rest_frame
    from dw3.preview import sheet
    from dw3.render import draw
    m = parse(code)
    os.makedirs(out_dir, exist_ok=True)
    name = name or code
    glb, png = os.path.join(out_dir, name + '.glb'), os.path.join(out_dir, name + '.png')
    open(glb, 'wb').write(export_glb(m))
    frame = rest_frame(m)
    sheet([draw(m, frame, yaw, 320) for yaw in (0, 35, 180)], 3).save(png)
    return m, glb, png


def cmd_import(name, code):
    """imported/NAME/ with the content crossgame_sources.fill_imported writes for a
    DW2003 model (choice and reason from its own rules, metrics with the fix)."""
    import csv
    patch()
    import crossgame_sources as cs
    d = os.path.join(cs.IMPORTED, cs.safe(name))
    _, glb, png = export(code, d, f'DW2003_{code}')
    raw = cs.copy(os.path.join(MODEL_DIR, code + '.BIN'), d, f'DW2003_raw_{code}.BIN')
    row = next(r for r in csv.DictReader(open(cs.MODELS_CSV)) if r['name'] == name)
    M = {f'dw3:{code}': cs.measure_dw3(code)}
    r = next(x for x in cs.build([row], M, {})[0] if x['section'] == 'new')
    info = dict(name=name, model=dict(game='DW2003', id=code, files=[os.path.basename(glb), raw],
                                      metrics=M[f'dw3:{code}']),
                choice={k: r[k] for k in ('model_from', 'anims_from', 'everyday_anims', 'fits', 'over_limits',
                                          'scale', 'height_dw1', 'dw1_slots_own', 'anim_kinds', 'fidelity')},
                reason=r['reason'], previews=[os.path.basename(png)],
                note=('made by tools/dw3_extra.py import: the dw3 package of the DW2003 repo does not parse this '
                      'file (empty slots in its section table, see the docstring there); the .glb and preview '
                      'come from here, not from that repo\'s out/fight'))
    if r['fits'] == 'no':                       # what crossgame_sources.convert_mmd says
        info['mmd'] = 'skipped: does not fit as-is'
    elif r['over_limits']:
        info['mmd'] = 'skipped: texture to repack by hand first'
    json.dump(info, open(os.path.join(d, 'info.json'), 'w'), indent=1)
    idx = os.path.join(cs.IMPORTED, 'index.tsv')
    lines = open(idx).read().splitlines() if os.path.exists(idx) else []
    line = '\t'.join(map(str, [name, cs.safe(name), r['model_from'], code, r['anims_from'], r['anims_id'],
                               r['fits'], r['everyday_anims'], info.get('mmd', ''), info.get('mmd_bytes', '')]))
    body = sorted([x for x in lines[1:] if x.split('\t')[0] != name] + [line], key=str.lower)
    open(idx, 'w').write('\n'.join(lines[:1] + body) + '\n')
    print(json.dumps(info['choice'], indent=1), '\n', info['reason'])


def cmd_dw3mmd(args):
    import runpy
    patch()
    sys.argv = [os.path.join(HERE, 'dw3mmd.py')] + args
    runpy.run_path(sys.argv[0], run_name='__main__')


def main():
    a = sys.argv[1:]
    if a[:1] == ['check']:
        cmd_check()
    elif a[:1] == ['export'] and len(a) == 3:
        m, glb, png = export(a[1], a[2])
        print(glb, png, summary(m))
    elif a[:1] == ['import'] and len(a) == 3:
        cmd_import(a[1], a[2])
    elif a[:1] == ['dw3mmd']:
        cmd_dw3mmd(a[1:])
    else:
        raise SystemExit(__doc__)


if __name__ == '__main__':
    main()
