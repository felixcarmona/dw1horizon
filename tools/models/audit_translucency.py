#!/usr/bin/env python3
"""Material audit and PSX blend comparison of the six translucency outliers.

python tools/models/audit_translucency.py --from BUILD --after DIR --out build/translucency/evidence
BUILD is a derive output with source-games and imported-models (read only).
DIR contains final provider ID.MMD/TIM pairs after the fix. NumPy/Pillow required.
"""
import argparse
from collections import Counter
import json
import math
from pathlib import Path
import struct
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / 'tools')]
import mmd
from tools.models import edit, meshcheck, psx_blend, audit_textures

IDS = {248: ('MarineAngemon', 'dcb', 230), 409: ('Kyubimon', 'dw3', 'M374KYBI'),
       251: ('Solarmon', 'dcb', 202), 227: ('Apemon', 'dcb', 212),
       294: ('Datamon', 'dw2', 'M141NANO'), 232: ('BomberNanimon', 'dcb', 213)}


def materials(data, texture):
    tmd, tim = audit_textures.load_pair(data, texture)
    faces = []
    for oi, ob in enumerate(tmd.objects):
        for pi, prim in enumerate(ob.prims):
            d = prim.decode()
            row = (d['cba'] >> 6) - 488
            words = Counter(tim.pal[row][tim.idx[y * tim.w + x]]
                            for x, y in audit_textures.texels(d['uv'], tim.w, tim.h)) if d['uv'] else Counter()
            faces.append(dict(object=oi, primitive=pi, abe=bool(prim.mode & 2), abr=(d['tsb'] >> 5) & 3,
                              row=row, opaque_texels=sum(n for c, n in words.items() if c and not (prim.mode & 2 and c & 32768)),
                              blended_texels=sum(n for c, n in words.items() if prim.mode & 2 and c & 32768),
                              discarded_texels=words[0]))
    return dict(**audit_textures.transparency(tmd), palettes=tim.pal,
                stp_indices=[[i for i, c in enumerate(p) if c & 32768] for p in tim.pal], faces=faces)


def source_marine(port):
    import mmdport
    base = mmdport.base_mmd(port, 248, log=lambda *a: None)
    a = mmd.Anim()
    a.has_scale, a.frame_count = True, 1
    a.pose = [[round(x * 4096) for x in s] + [round(x) for x in mmd.matrix_euler(mmd.quat_matrix(q))]
              + [round(x) for x in t] for q, t, s in port.anims['anim_00'].frames[0]]
    a.instrs = [dict(op='end')]
    base.anims.anims, base.anims.table = [a], [0]
    return meshcheck.Model(base, mmdport.skeleton(port), mmdport.build_tim(port.idx, port.pals))


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--from', dest='build', type=Path, required=True)
    ap.add_argument('--after', type=Path, required=True)
    ap.add_argument('--before', type=Path, help='Pinned final provider pairs before the change (defaults to imported-models)')
    ap.add_argument('--out', type=Path, required=True)
    args = ap.parse_args()
    args.build, args.after, args.out = args.build.resolve(), args.after.resolve(), args.out.resolve()
    before = args.before.resolve() if args.before else args.build / 'imported-models'
    args.out.mkdir(parents=True, exist_ok=True)
    report = {}
    for sid, (name, game, code) in IDS.items():
        data, tex = (before / f'{sid}.MMD').read_bytes(), (before / f'{sid}.TIM').read_bytes()
        with edit.importing(args.build / 'source-games'):
            import dcb2mmd, dw2mmd, dw3mmd
            if game == 'dcb':
                raw = dcb2mmd._dcb().model.parse_model(Path(dcb2mmd.pak_path(code)).read_bytes(), name)
                raw_counts = Counter((p.semi, (p.tpage >> 5) & 3) for b in raw.bones for p in b.mesh.prims)
                port = dcb2mmd.load(code, log=lambda *a: None)
            elif game == 'dw2':
                raw = dw2mmd._dw2().model.load(dw2mmd.model_path(code))
                raw_counts = Counter((p.semi, (p.tpage >> 5) & 3) for b in raw.bones for p in b.prims)
                port = dw2mmd.load(code, log=lambda *a: None)
            else:
                raw = dw3mmd.read_model(code)
                raw_counts = Counter((bool(p.state[14]), (p.state[14] - 1) & 3 if p.state[14] else 0)
                                     for b in raw.bones for p in b.mesh.prims)
                port = dw3mmd.load(code, log=lambda *a: None)
            if sid == 248:
                marine = source_marine(port)
        tm = mmd.Tim4(tex)
        final = materials(data, tex)
        # Compare the sampled 16-bit words, not just RGBA. Tournament sprite
        # stamping changes unused image rows in some final TIMs.
        sampled_changes = 0
        for ob in audit_textures.load_pair(data, tex)[0].objects:
            for prim in ob.prims:
                d = prim.decode()
                if d['uv'] and game != 'dw3':
                    row = (d['cba'] >> 6) - 488
                    for x, y in audit_textures.texels(d['uv'], tm.w, tm.h):
                        sampled_changes += port.pals[row][port.idx[y * 256 + x]] != tm.pal[row][tm.idx[y * tm.w + x]]
        record = dict(name=name, game=game, source=str(code), source_materials=[dict(abe=k[0], abr=k[1], count=n)
                      for k, n in sorted(raw_counts.items())], before=final,
                      palette_words_preserved=all(list(p) == tm.pal[i] for i, p in enumerate(port.pals)),
                      image_indices_preserved=bytes(port.idx) == bytes(tm.idx),
                      sampled_word_changes=sampled_changes if game != 'dw3' else None)
        after_path = args.after / f'{sid}.MMD'
        record['after'] = materials(after_path.read_bytes(), (args.after / f'{sid}.TIM').read_bytes()) if after_path.exists() else final
        report[str(sid)] = record
    (args.out / 'materials.json').write_text(json.dumps(report, indent=2) + '\n')
    from PIL import Image, ImageDraw
    def final_model(sid, folder):
        record = args.after / f'{sid}.json'
        skeleton = json.loads((record if record.exists() else next((ROOT / 'content/species').glob(f'{sid}-*.json'))).read_text())['model']['skeleton']
        # The provider may replace the source skeleton (Kyubimon).
        return meshcheck.Model((folder / f'{sid}.MMD').read_bytes(), skeleton, (folder / f'{sid}.TIM').read_bytes())
    shipped = final_model(248, before)
    kyubi = final_model(409, before)
    fixed = final_model(409, args.after)
    columns, rows, cell = 3, 4, 320
    sheet = Image.new('RGB', (columns * cell, rows * (cell + 35) + 95), '#16202b')
    draw = ImageDraw.Draw(sheet)
    draw.text((15, 12), 'MarineAngemon: translucent in the source. Kyubimon: additive glow restored.', fill='white')
    draw.text((15, 34), 'PSX ABE + CLUT STP + ABR; neutral lighting; approximate depth sort / orthographic camera.', fill='white')
    panels = []
    for yaw in (0, math.pi / 3):
        panels += [(marine, 'Card Battle source', yaw, False), (shipped, 'Shipped / after: unchanged', yaw, False),
                   (shipped, 'ABE disabled: diagnostic only', yaw, True)]
    for yaw in (0, math.pi / 3):
        panels += [(kyubi, 'Kyubimon before: 50/50 glow', yaw, False), (fixed, 'Kyubimon after: additive glow', yaw, False),
                   (fixed, 'After, ABE disabled: diagnostic', yaw, True)]
    for i, (model, title, yaw, opaque) in enumerate(panels):
        rgb, _ = psx_blend.render(model, yaw, math.pi / 12, size=cell, opaque=opaque)
        x, y = (i % columns) * cell, 95 + (i // columns) * (cell + 35)
        draw.text((x + 8, y + 8), title, fill='white')
        sheet.paste(Image.fromarray(rgb), (x, y + 35))
    sheet.save(args.out / 'translucency.png')
    print(args.out / 'translucency.png')


if __name__ == '__main__':
    main()
