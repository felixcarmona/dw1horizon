#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Full-resolution SAM silhouettes, palette-safe field sprites, and collision review.

See tools/maps/README.md for the JSON contract and docs/mods/new-maps.md for
acceptance rules. Outputs are candidates; collision suggestions are never applied.
"""

# Allow both direct script execution and package imports.
import sys as _image_sys
from pathlib import Path as _ImagePath
_image_sys.path.insert(0, str(next(p for p in _ImagePath(__file__).resolve().parents if (p / 'tools').is_dir())))
import argparse
import hashlib
import json
from pathlib import Path
import re
import struct
import sys

import cv2
import numpy as np
from tools.image import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import dwmap
import reach

CHECKPOINT_SHA256 = 'a7bf3b02f3ebf1267aba913ff637d9a2d5c33d3173bb679e46d9f338c26f262e'


def digest(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def load_spec(path):
    cfg = json.loads(Path(path).read_text())
    if cfg.get('version') != 1:
        raise ValueError('spec version must be 1')
    if not cfg.get('objects'):
        raise ValueError('spec needs at least one object')
    if len(cfg['size']) != 2 or min(cfg['size']) <= 0:
        raise ValueError('size must contain positive width and height')
    names = []
    for obj in cfg['objects']:
        name = obj['name']
        if not re.fullmatch(r'[a-z0-9][a-z0-9-]*', name) or name in names:
            raise ValueError('object names must be unique safe lowercase filenames')
        names.append(name)
        if len(obj['box']) != 4 or len(obj['depth_world']) != 3:
            raise ValueError(f'{name}: box needs four coordinates; depth_world needs x,y,z')
        x0,y0,x1,y1 = obj['box']
        if not (0 <= x0 < x1 <= cfg['size'][0] and 0 <= y0 < y1 <= cfg['size'][1]):
            raise ValueError(f'{name}: invalid box')
        if set(map(tuple,obj['tiles']['behind'])) & set(map(tuple,obj['tiles']['blocked'])):
            raise ValueError(f'{name}: tile declared both behind and blocked')
        if obj['depth_world'][1] == 10000:
            raise ValueError(f'{name}: foreground cannot use background depth y=10000')
        if not obj.get('positive'):
            raise ValueError(f'{name}: supply at least one positive point')
        for kind in ('behind', 'blocked'):
            for tx, tz in obj['tiles'][kind]:
                if not (0 <= tx < 100 and 0 <= tz < 100):
                    raise ValueError(f'{name}: tile outside collision grid')
    return cfg


def segment(cfg, art, checkpoint, threads):
    import torch
    from tools.maps.sam import sam_model_registry, SamPredictor
    if digest(checkpoint) != CHECKPOINT_SHA256:
        raise ValueError('SAM checkpoint SHA-256 mismatch')
    torch.set_num_threads(threads)
    predictor = SamPredictor(sam_model_registry['vit_h'](checkpoint=str(checkpoint)))
    full = np.array(Image.open(art).convert('RGB'))
    fw, fh = full.shape[1], full.shape[0]
    left, top, right, bottom = cfg['crop']
    width, height = cfg['size']
    if not (0 <= left < right <= fw and 0 <= top < bottom <= fh):
        raise ValueError('crop outside full-resolution art')
    scale = np.array([(right-left)/width, (bottom-top)/height])
    offset = np.array([left, top])
    predictor.set_image(full)                 # encode once, never encode a thumbnail
    result, scores = {}, {}
    for obj in cfg['objects'] + cfg.get('exclusions', []):
        points = obj['positive'] + obj.get('negative', [])
        coords = np.array(points) * scale + offset
        labels = np.array([1]*len(obj['positive']) + [0]*len(obj.get('negative', [])))
        box = (np.array(obj['box']).reshape(2, 2)*scale + offset).flatten() if 'box' in obj else None
        masks, confidence, _ = predictor.predict(point_coords=coords, point_labels=labels,
                                                 box=box, multimask_output=obj.get('multimask', True))
        best = int(confidence.argmax())
        mask = cv2.resize(masks[best, top:bottom, left:right].astype(np.float32),
                          (width, height), interpolation=cv2.INTER_AREA) > .5
        count, components, stats, _ = cv2.connectedComponentsWithStats(mask.astype('uint8'))
        for i in range(1, count):
            if stats[i, cv2.CC_STAT_AREA] < obj.get('min_component', 3):
                mask[components == i] = False
        # Keep holes: a lantern, rail or arch can have real openings.
        result[obj['name']] = mask
        scores[obj['name']] = float(confidence[best])
        print(obj['name'], 'score', round(scores[obj['name']], 3), 'pixels', int(mask.sum()), flush=True)
    return result, scores


def clean_masks(cfg, raw):
    """Explicit per-object cleanup, with floor subtraction before component filtering."""
    result = {}
    for obj in cfg['objects']:
        mask = raw[obj['name']].astype(bool).copy()
        for name in obj.get('subtract', []):
            mask &= ~raw[name].astype(bool)
        n, labels, stats, _ = cv2.connectedComponentsWithStats(mask.astype('uint8'))
        largest = max(stats[1:, cv2.CC_STAT_AREA], default=0)
        minimum = max(obj.get('min_component', 3), largest*obj.get('min_fraction', 0))
        for i in range(1,n):
            if stats[i,cv2.CC_STAT_AREA] < minimum:mask[labels==i]=False
        if obj.get('fill_holes', False):
            # Pad first: (0,0) may itself be inside a frame-touching object.
            inverse = np.pad((~mask).astype('uint8'),1,constant_values=1)
            cv2.floodFill(inverse,None,(0,0),2)
            mask |= inverse[1:-1,1:-1]==1
        result[obj['name']] = mask
    return result


def rectangle_errors(mask, name):
    ys, xs = np.where(mask)
    if not len(xs):
        return [f'{name}: empty mask']
    crop = mask[ys.min():ys.max()+1, xs.min():xs.max()+1]
    errors = []
    if crop.size > 64 and crop.mean() > .98:
        errors.append(f'{name}: rectangular mask; inspect silhouette')
    # An irregular object may legitimately continue beyond an image edge. A long
    # flat edge at the prompt box is suspicious; a filled frame corner is worse.
    h, w = mask.shape
    for edge in (mask[0], mask[-1], mask[:, 0], mask[:, -1]):
        runs = np.diff(np.r_[False, edge, False].astype(int))
        starts, ends = np.where(runs == 1)[0], np.where(runs == -1)[0]
        if len(starts) and max(ends-starts) >= .9*len(edge):
            errors.append(f'{name}: mask fills almost an entire image edge')
            break
    return errors


def palette_indices(m, t, masks, hidden_instances=()):
    _, _, rows = t.image_indices(m)
    indices = np.array([list(r) for r in rows], dtype=np.uint8)
    union = np.logical_or.reduce(list(masks.values()))
    if any(p[0] != 0 for p in t.cluts):
        raise ValueError('background index 0 must be GPU transparent in every palette')
    # A missing donor tile has no valid TFS colour. Do not invent a black cut-out.
    for k, tile in enumerate(m.tiles):
        if tile == -1:
            x, y = k % m.width*128, k // m.width*128
            if union[y:y+128, x:x+128].any():
                raise ValueError('mask touches a missing background tile; use a complete donor layout')
    # Preserve exact TFS quantization. GPU transparency is CLUT word 0, not the
    # numerical index itself. Alias every transparent colour used inside a mask.
    used = set(indices.flatten().tolist())
    # A palette slot unused by the background may still be used by an animation.
    # Never turn one of its transparent colours into an opaque black rectangle.
    for n, inst in enumerate(getattr(m, 'instances', [])):
        if n in hidden_instances or inst['flag'] == 1:
            continue
        for frame in inst['frames']:
            if frame < 0:
                continue
            sprite = m.sprites[frame]
            if sprite['clut'] != -1:
                continue
            for raw in m.tims:
                tim = dwmap.TIM(raw)
                if tim.bpp != 8:
                    continue
                left, top = (tim.x-384)*2, tim.y
                x0 = max(left, sprite['texX']); y0 = max(top, sprite['texY'])
                x1 = min(left+tim.w*2, sprite['texX']+sprite['width'])
                y1 = min(top+tim.h, sprite['texY']+sprite['height'])
                if x0 < x1 and y0 < y1:
                    pixels = np.frombuffer(tim.pixels,np.uint8).reshape(tim.h,tim.w*2)
                    used.update(pixels[y0-top:y1-top,x0-left:x1-left].flatten().tolist())
    aliases = {}
    for i in np.unique(indices[union]):
        i = int(i)
        if not any(p[i] == 0 for p in t.cluts):
            continue
        words = [p[i] or 0x8000 for p in t.cluts]
        alias = next((j for j in range(1, 256) if all(p[j] == v for p, v in zip(t.cluts, words))), None)
        if alias is None:
            alias = next((j for j in range(1, 256) if j not in used), None)
            if alias is None:
                raise ValueError('no unused palette slot for opaque black; reserve a sprite CLUT explicitly')
            for p, word in zip(t.cluts, words):
                p[alias] = word
            used.add(alias)
        aliases[i] = alias
    output = indices.copy()
    for old, new in aliases.items():
        output[(indices == old) & union] = new
    return output, aliases


def pack(m, cfg, masks, indices):
    raws = [bytearray(t) for t in m.tims]
    areas = []
    for a in cfg['packing']:
        k, x, y, w, h = (a[f] for f in ('tim', 'x', 'y', 'width', 'height'))
        tim = dwmap.TIM(raws[k])
        if tim.bpp != 8 or not (0 <= x < x+w <= tim.w*2 and 0 <= y < y+h <= tim.h):
            raise ValueError('packing area must fit an existing 8 bpp TIM')
        tex = (tim.x-384)*2 + x
        if tex < 0 or tex//256 != (tex+w-1)//256 or tim.y+y+h > 256:
            raise ValueError('packing area crosses a texture page')
        for old in areas:
            if old['tim'] == k and x < old['x']+old['width'] and x+w > old['x'] and y < old['y']+old['height'] and y+h > old['y']:
                raise ValueError('overlapping packing areas')
        offset = 8 + struct.unpack_from('<I', raws[k], 8)[0] + 12
        for yy in range(y, y+h):
            start = offset+yy*tim.w*2+x
            raws[k][start:start+w] = bytes(w)
        areas.append(dict(a, cursor_x=0, cursor_y=0, shelf=0, offset=offset, stride=tim.w*2, tex=tex, tim_y=tim.y))
    # Caller explicitly identifies which old instances these areas replace.
    for i in cfg.get('hide_instances', []):
        m.instances[i]['flag'] = 1
    for inst in m.instances:
        if inst['flag'] == 1:
            continue
        for frame in inst['frames']:
            if frame < 0:
                continue
            s = m.sprites[frame]
            for a in areas:
                if s['texX'] < a['tex']+a['width'] and s['texX']+s['width'] > a['tex'] and s['texY'] < a['tim_y']+a['y']+a['height'] and s['texY']+s['height'] > a['tim_y']+a['y']:
                    raise ValueError('packing would overwrite a preserved sprite')
    placements = []
    side = cfg.get('chunk_size', 64)
    if not 1 <= side <= 254:
        raise ValueError('chunk_size must be 1..254')
    cuts = []
    for obj in cfg['objects']:
        mask = masks[obj['name']]
        for y in range(0, mask.shape[0], side):
            for x in range(0, mask.shape[1], side):
                ys, xs = np.where(mask[y:y+side, x:x+side])
                if len(xs):
                    cuts.append((int(xs.max()-xs.min()+1), int(ys.max()-ys.min()+1),
                                 x+int(xs.min()), y+int(ys.min()), obj))
    for w, h, ox, oy, obj in sorted(cuts, key=lambda c: (-c[1], -c[0], c[4]['name'], c[3], c[2])):
        for a in areas:
            cx, cy, shelf = a['cursor_x'], a['cursor_y'], a['shelf']
            if cx+w+2 > a['width']:
                cx, cy, shelf = 0, cy+shelf, 0
            if cy+h+2 <= a['height'] and w+2 <= a['width']:
                break
        else:
            raise ValueError(f"existing TIM space exhausted at {obj['name']}; split masks or repack")
        x, y = a['x']+cx+1, a['y']+cy+1
        crop = masks[obj['name']][oy:oy+h, ox:ox+w]
        pixels = np.where(crop, indices[oy:oy+h, ox:ox+w], 0).astype('uint8')
        for yy in range(h):
            start = a['offset']+(y+yy)*a['stride']+x
            raws[a['tim']][start:start+w] = pixels[yy].tobytes()
        gx, gy, gz = obj['depth_world']
        sprite = dict(texX=a['tex']+cx+1, texY=a['tim_y']+y, width=w, height=h,
                      x=gx, y=gy, z=gz, clut=-1, transparency=4)
        n = len(m.sprites)
        m.sprites.append(sprite)
        m.instances.append(dict(frames=[n]+[-1]*7, times=[0]*8, x=ox, y=oy, flag=0))
        placements.append(dict(name=obj['name'], sprite=n, instance=len(m.instances)-1,
                               tim=a['tim'], source=[ox, oy, w, h], texture=[x, y]))
        a.update(cursor_x=cx+w+2, cursor_y=cy, shelf=max(shelf, h+2))
    if len(m.sprites) > 180 or len(m.instances) > 188:
        raise ValueError('field engine sprite table limit exceeded (180 definitions / 188 instances)')
    m.tims = list(map(bytes, raws))
    return placements


def suggestions(m, cfg, masks):
    basis = dwmap.camera_basis(m)
    result = []
    for obj in cfg['objects']:
        mask = masks[obj['name']]
        declared = {tuple(t): kind for kind in ('behind', 'blocked') for t in obj['tiles'][kind]}
        for i, value in enumerate(m.collision):
            tx, tz = i % 100, i // 100
            p = dwmap.project(m, basis, ((tx-50)*100+50, 0, (49-tz)*100+50))
            if p is None:
                continue
            u, v = map(int, p)
            if not (0 <= u < mask.shape[1] and 0 <= v < mask.shape[0]):
                continue
            body = mask[max(0,v-25):v+1, max(0,u-7):u+8].any()
            if body or (tx,tz) in declared:
                # A depth anchor alone cannot describe a sloping bridge's footprint.
                # Explicit reviewed tiles win; otherwise conservatively block feet.
                world = np.array([(tx-50)*100+50, 0, (49-tz)*100+50])
                beyond_anchor = np.dot(world-np.array(obj['depth_world']), basis[3]) > 0
                automatic = 'blocked' if mask[v,max(0,u-7):u+8].any() else 'behind' if beyond_anchor else 'review'
                kind = declared.get((tx,tz), automatic)
                result.append(dict(object=obj['name'], tile=[tx,tz], suggestion=kind,
                                   value=0 if kind=='behind' else 128 if kind=='blocked' else None,
                                   current=value, hidden=kind=='behind', reviewed=(tx,tz) in declared))
    return result


def review_sheet(bg, cfg, masks, out, quantized=None):
    rows = []
    for obj in cfg['objects']:
        mask = masks[obj['name']]
        contour, _ = cv2.findContours(mask.astype('uint8'), cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
        over = np.array(bg).copy()
        cv2.drawContours(over, contour, -1, (0,255,255), 1)
        checker = np.indices(mask.shape).sum(0)//8 % 2*50+80
        piece = np.repeat(checker[:,:,None], 3, axis=2).astype('uint8')
        piece[mask] = (np.array(bg) if quantized is None else quantized)[mask]
        row = Image.new('RGB', (bg.width*6, bg.height*3+24), '#222222')
        row.paste(Image.fromarray(over).resize((bg.width*3,bg.height*3), Image.Resampling.NEAREST),(0,24))
        row.paste(Image.fromarray(piece).resize((bg.width*3,bg.height*3), Image.Resampling.NEAREST),(bg.width*3,24))
        ImageDraw.Draw(row).text((8,5),obj['name']+' | outline over art / cut on checkerboard (3x)',fill='white')
        rows.append(row)
    sheet = Image.new('RGB',(rows[0].width,sum(r.height for r in rows)), '#222222')
    y=0
    for row in rows:
        sheet.paste(row,(0,y)); y+=row.height
    sheet.save(out)


def check(cfg, out, m):
    errors = []
    masks = np.load(out/'masks.npz', allow_pickle=False)
    for obj in cfg['objects']:
        name = obj['name']; mask = masks[name].astype(bool)
        errors.extend(rectangle_errors(mask,name))
        rgba = np.array(Image.open(out/(name+'.png')).convert('RGBA'))
        if not np.array_equal(rgba[:,:,3]>0, mask):
            errors.append(f'{name}: RGBA alpha differs from mask')
        # All feet under a silhouette need an explicit footprint/depth decision.
        behind = set(map(tuple,obj['tiles']['behind']))
        basis = dwmap.camera_basis(m)
        for i,c in enumerate(m.collision):
            if c & 128:
                continue
            tx,tz=i%100,i//100
            p=dwmap.project(m,basis,((tx-50)*100+50,0,(49-tz)*100+50))
            if p is None:continue
            u,v=map(int,p)
            if 0<=u<mask.shape[1] and 0<=v<mask.shape[0] and mask[v,max(0,u-7):u+8].any() and (tx,tz) not in behind:
                errors.append(f'{name}: walkable feet covered at {tx},{tz}; block or review behind depth')
        for tx,tz in behind:
            if m.collision[tz*100+tx]&128:
                errors.append(f'{name}: declared behind tile {tx},{tz} is blocked')
            world=np.array([(tx-50)*100+50,0,(49-tz)*100+50])
            if np.dot(world-np.array(obj['depth_world']),basis[3]) <= 0:
                errors.append(f'{name}: declared behind tile {tx},{tz} lies in front of depth anchor')
        for tx,tz in obj['tiles']['blocked']:
            if not m.collision[tz*100+tx]&128: errors.append(f'{name}: footprint tile {tx},{tz} is walkable')
    if (out/'placements.json').exists():
        t=dwmap.TfsFile((out/'candidate.TFS').read_bytes())
        for p in json.loads((out/'placements.json').read_text()):
            tim=dwmap.TIM(m.tims[p['tim']]); x,y=p['texture']; ox,oy,w,h=p['source']
            pixels=np.frombuffer(tim.pixels,np.uint8).reshape(tim.h,tim.w*2)[y:y+h,x:x+w]
            mask=masks[p['name']][oy:oy+h,ox:ox+w].astype(bool)
            if np.any(pixels[~mask]!=0): errors.append(f"{p['name']}: opaque pixels outside mask (black box)")
            for pal in t.cluts:
                if any(pal[int(i)]==0 for i in pixels[mask]): errors.append(f"{p['name']}: transparent colour inside object")
    errors.extend(reach.check_arrivals(m))
    return errors


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('command',choices=['generate','check'])
    ap.add_argument('spec',type=Path)
    ap.add_argument('--out',type=Path,required=True)
    ap.add_argument('--art',type=Path)
    ap.add_argument('--map',type=Path,required=True)
    ap.add_argument('--tfs',type=Path)
    ap.add_argument('--checkpoint',type=Path,default=Path('build/sam-models/sam_vit_h_4b8939.pth'))
    ap.add_argument('--threads',type=int,default=3)
    ap.add_argument('--masks',type=Path,help='reuse an already reviewed NPZ instead of running SAM')
    ap.add_argument('--review-only',action='store_true',help='do not pack or emit MAP/TFS candidates')
    args=ap.parse_args(); cfg=load_spec(args.spec); out=args.out
    m=dwmap.MapFile(args.map.read_bytes())
    if (m.width*128,m.height*128)!=tuple(cfg['size']):raise ValueError('map dimensions differ from spec')
    if args.command=='check':
        if (out/'candidate.MAP').exists():m=dwmap.MapFile((out/'candidate.MAP').read_bytes())
        errors=check(cfg,out,m)
        if errors:sys.exit('\n'.join(errors))
        print('PASS: silhouettes, palette, footprints and arrivals');return
    if args.threads < 1:ap.error('--threads must be positive')
    if not args.art:ap.error('generate requires --art')
    if out.exists() and any(out.iterdir()):raise ValueError('output directory must be empty; prevents stale candidates')
    out.mkdir(parents=True,exist_ok=True)
    masks,scores=(dict(np.load(args.masks,allow_pickle=False)),{}) if args.masks else segment(cfg,args.art,args.checkpoint,args.threads)
    for name,mask in masks.items():
        if mask.shape!=tuple(reversed(cfg['size'])):raise ValueError(f'{name}: mask dimensions differ')
    np.savez_compressed(out/'sam-masks.npz',**masks)
    masks=clean_masks(cfg,masks)
    bg=Image.open(args.art).convert('RGB').crop(cfg['crop']).resize(tuple(cfg['size']),Image.Resampling.LANCZOS)
    np.savez_compressed(out/'masks.npz',**masks)
    for obj in cfg['objects']:
        rgba=np.dstack((np.array(bg),masks[obj['name']].astype('uint8')*255))
        Image.fromarray(rgba).save(out/(obj['name']+'.png'))
    quantized=None
    if not args.review_only:
        if not args.tfs:ap.error('packing requires --tfs')
        t=dwmap.TfsFile(args.tfs.read_bytes())
        indices,aliases=palette_indices(m,t,masks,cfg.get('hide_instances', []))
        placements=pack(m,cfg,masks,indices)
        # RGBA review uses the actual quantized sprite colours.
        pal=np.array(t.palette_rgb(0),dtype='uint8')
        quantized=pal[indices]
        for obj in cfg['objects']:
            Image.fromarray(np.dstack((pal[indices],masks[obj['name']].astype('uint8')*255))).save(out/(obj['name']+'.png'))
        (out/'candidate.MAP').write_bytes(m.build());(out/'candidate.TFS').write_bytes(t.build())
        for i,raw in enumerate(m.tims):(out/f'sprite-{i}.tim').write_bytes(raw)
        (out/'placements.json').write_text(json.dumps(placements,indent=2)+'\n')
    else:aliases={}
    review_sheet(bg,cfg,masks,out/'review-3x.png',quantized)
    (out/'tiles.json').write_text(json.dumps(suggestions(m,cfg,masks),indent=2)+'\n')
    (out/'provenance.json').write_text(json.dumps(dict(art_sha256=digest(args.art),spec_sha256=digest(args.spec),
        map_sha256=digest(args.map),tfs_sha256=digest(args.tfs) if args.tfs else None,scores=scores,aliases=aliases,mask_source='cached' if args.masks else 'SAM ViT-H'),indent=2)+'\n')
    print(out/'review-3x.png')


if __name__=='__main__':
    try:main()
    except (ValueError,KeyError,IndexError) as e:sys.exit(str(e))
