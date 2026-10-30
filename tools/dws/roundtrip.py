"""decompile -> compile -> compare with the bytes of the disc, for all 222 scripts and MAPHEAD.
`run` also reports per script which entries differ and what stayed asm()."""
import os, sys, tempfile
from . import decomp, build as B, textx
from .diag import DwsError


def run(keep=None, quiet=False, layout=False):
    d = keep or tempfile.mkdtemp(prefix='rt-', dir=os.path.join(B.ROOT, 'build'))
    os.makedirs(d, exist_ok=True)
    bank = os.path.join(d, 'orig.en.json'); textx.write_bank(textx.extract(), bank)
    srcs = []; stats = {}
    if layout:
        from . import layout as L
        index, mhp = L.write(os.path.join(d, 'base'), stats=stats)
        scripts = index; srcs = list(index.values()) + [mhp]
    else:
        scripts, mh, stats = decomp.decompile_all()
        for sid, src in scripts.items():
            p = os.path.join(d, f's{sid:03d}.dws'); open(p, 'w', encoding='utf-8').write(src); srcs.append(p)
        p = os.path.join(d, 'maphead.dws'); open(p, 'w', encoding='utf-8').write(mh); srcs.append(p)
    prog = B.compile_sources(srcs, text=[bank])
    out = os.path.join(d, 'DG.SCN'); B.assemble(prog, out)
    got = open(out, 'rb').read(); want = open(os.path.join(B.ROOT, 'extracted/SCN/DG.SCN'), 'rb').read()
    gm = open(prog.b.maphead, 'rb').read(); wm = open(os.path.join(B.ROOT, 'extracted/SCN/MAPHEAD.SCN'), 'rb').read()
    # per entry comparison through the container table
    import struct
    def entries(b):
        offs = []; p = 0
        while True:
            o = struct.unpack_from('<I', b, p)[0]; offs.append(o); p += 4
            if len(offs) > 1 and o >= len(b): break
            if len(offs) > 600: break
        return offs
    wo, go = entries(want), entries(got)
    bad = []
    for i in range(min(len(wo), len(go)) - 1):
        if want[wo[i]:wo[i + 1]] != got[go[i]:go[i + 1]]: bad.append(i)
    ok = len(scripts) - len(bad)
    res = {'scripts': len(scripts), 'identical': ok, 'differs': bad, 'dg_identical': got == want, 'maphead_identical': gm == wm,
           'lifted': stats.get('lifted', 0), 'asm': stats.get('asm', 0), 'asm_ops': stats.get('asm_ops', {})}
    if not quiet:
        print(f'DG.SCN: {"identical" if got == want else "DIFFERENT"}; entries identical {ok}/{len(scripts)}; '
              f'MAPHEAD: {"identical" if gm == wm else "DIFFERENT"}')
        print(f'instructions as typed statements: {res["lifted"]}, as asm(): {res["asm"]} {res["asm_ops"]}')
        if bad: print('entries that differ:', bad[:40])
    return res
