#!/usr/bin/env python3
"""Audit every raisable Status portrait, including every tick of idle slot 0.

Run after a full build:
  python3 tools/status_portraits.py build/NAME --out build/status-audit [--fix]

Uses the built DIGI.DAT (including resident/cold joins), native disc models,
runtime skeletons and modelScale rules. The camera is renderDigiviceEntity's
GsRVIEW2 (1300,0,-3280 -> 0,0,0), projection 512, screen origin (160,120).
Repairs use the Condition area's free space above Life (y<154), with a
20-pixel readability floor on the fixed pose actually drawn by the game.
Only visible pixels crossing its outer edges qualify for changes. Touching an
edge or the label alone does not change an otherwise fitting original.
All idle frames retain a conservative geometry envelope; every repaired frame
is also rasterized to check opaque pixels, the label and the Life boundary.
No runtime clipping or model edits are needed: --fix changes only viewX/Y/Z.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import animsheet
import coldsplit
import mmd
import species

LENGTH = math.hypot(1300, 3280)
A, B = 3280 / LENGTH, 1300 / LENGTH
# createMenuBox(-150,-89,300,190): screen rect (10,31,300,190).
# renderUIBoxBorder takes four edge pixels; STATS_VIEW_LINES uses y=-18
# (three separator pixels) and statsCareLayout puts the divider at x=-1.
BOUNDS = (160 - 150 + 4, 120 - 18 + 3, 160 - 1 - 1, 120 - 89 + 190 - 4)
BOX_EDGES = (10, 102, 161, 220)
LABEL = (20, 107, 80, 120)
# Life starts at y=154. The label occupies only the upper-left rectangle.
# Native baby portraits retain about 20 visible rows above Life; use that floor.
LIFE_Y = 154
MIN_HEIGHT = 20
READABLE_BOUNDS = (14, 105, 158, LIFE_Y - 1)
GEOMETRY_BOUNDS = (13.5, 104.5, 158.5, LIFE_Y - .5)
TARGET = (16, LABEL[3] + 3, 156, LIFE_Y - 3)
RIGHT_TARGET = (LABEL[2] + 3, 106, 156, LIFE_Y - 3)
FULL_TARGET = (16, 106, 156, LIFE_Y - 3)


def camera(v):
    x, y, z = v
    return A * x + B * z, y, -B * x + A * z


def project(points, position):
    tx, ty, tz = camera(position)
    return [(160 + 512 * (x + tx) / (z + tz + LENGTH),
             120 + 512 * (y + ty) / (z + tz + LENGTH)) for x, y, z in points]


def envelope(points, position):
    p = project(points, position)
    return [min(x for x, y in p), min(y for x, y in p),
            max(x for x, y in p), max(y for x, y in p)]


def inside(box, bounds=BOUNDS):
    return box[0] >= bounds[0] and box[1] >= bounds[1] and box[2] <= bounds[2] and box[3] <= bounds[3]


def fit(points, original, bounds=TARGET, align_x=None):
    """Smallest depth increase inside one rectangle, then the nearest old anchor.

    Edge intervals are affine in camera depth; their intersection supplies the
    exact minimum without repeatedly projecting the complete point cloud.
    """
    left, top, right, bottom = bounds
    ox, oy, oz = camera(original)
    old_depth = oz + LENGTH
    al, ar = (left - 160) / 512, (right - 160) / 512
    at, ab = (top - 120) / 512, (bottom - 120) / 512
    cl = max(al * z - x for x, y, z in points)
    cr = min(ar * z - x for x, y, z in points)
    ct = max(at * z - y for x, y, z in points)
    cb = min(ab * z - y for x, y, z in points)
    depth = max(old_depth, 1 - min(z for x, y, z in points),
                (cl - cr) / (ar - al), (ct - cb) / (ab - at))
    if depth > old_depth:
        depth += 1  # integer view coordinates retain a subpixel margin
    xl, xr, yt, yb = cl + al * depth, cr + ar * depth, ct + at * depth, cb + ab * depth
    tx = (xl + (xr - xl) * align_x if align_x is not None else
          min(xr, max(xl, ox * depth / old_depth)))
    ty = min(yb, max(yt, oy * depth / old_depth))
    tz = depth - LENGTH
    result = [round(A * tx - B * tz), round(ty), round(B * tx + A * tz)]
    actual_depth = camera(result)[2] + LENGTH
    if actual_depth < old_depth:
        result[2] += math.ceil((old_depth - actual_depth) / A)
    if not all(-32768 <= v <= 32767 for v in result):
        raise ValueError(f'portrait position exceeds int16: {result}')
    assert camera(result)[2] + LENGTH >= old_depth - 1e-8
    assert inside(envelope(points, result), GEOMETRY_BOUNDS), result
    return result


def visible_bounds(layer):
    box = layer.getchannel('A').getbbox()
    return None if box is None else [box[0], box[1], box[2] - 1, box[3] - 1]


def overlaps_label(layer):
    return layer.getchannel('A').crop((LABEL[0], LABEL[1], LABEL[2] + 1, LABEL[3] + 1)).getbbox() is not None


def readability_problem(box, label_overlap=False, check_height=True):
    if box is None:
        return 'empty'
    if box[3] >= LIFE_Y:
        return 'Life/care overlap'
    if not inside(box, READABLE_BOUNDS):
        return 'box overflow'
    if label_overlap:
        return 'label overlap'
    if check_height and box[3] - box[1] + 1 < MIN_HEIGHT:
        return 'unreadable height'
    return None


def verify_after(points, frames, model, skeleton, tex, events, width, position, scale):
    """Check every rasterized idle tick, including texture phases and care overlap."""
    if not inside(envelope(points, position), GEOMETRY_BOUNDS):
        return None
    heights = []
    boxes = []
    for tick, pose in enumerate(frames):
        for phase in (None, 0, 1, 2) if width else (None,):
            texture = texture_at(tex, events, tick, width, phase)
            layer = model_layer(model, skeleton, pose, texture, position, scale)
            b = visible_bounds(layer)
            if readability_problem(b, overlaps_label(layer), check_height=tick == 0):
                return None
            height = b[3] - b[1] + 1
            heights.append(height)
            boxes.append(b)
    return dict(frames=len(frames), raster_ticks=list(range(len(frames))),
                label_clear=True, life_clear=True, minimum_height=min(heights),
                maximum_height=max(heights), first_height=boxes[0][3] - boxes[0][1] + 1,
                first_bounds=boxes[0])


def readable_fit(points, frames, model, skeleton, tex, events, width, original, scale):
    # The upper part of the panel is L-shaped: a portrait can extend beside the
    # label. A full-width candidate is accepted only after all poses clear it.
    candidates = {tuple(fit(points, original, rectangle, align))
                  for rectangle, align in ((FULL_TARGET, None), (FULL_TARGET, 1),
                                           (FULL_TARGET, .75), (FULL_TARGET, .5),
                                           (RIGHT_TARGET, None), (TARGET, None))}
    ox, oy, oz = camera(original)
    old_depth = oz + LENGTH
    def cost(position):
        x, y, z = camera(position)
        d = z + LENGTH
        return d, (x / d - ox / old_depth) ** 2 + (y / d - oy / old_depth) ** 2
    for position in sorted(candidates, key=cost):
        verification = verify_after(points, frames, model, skeleton, tex, events,
                                    width, position, scale)
        if verification:
            return list(position), verification
    # A final pixel-verified pass uses the remaining subpixel space. It is
    # accepted only when every opaque pixel still clears the separator/Life.
    for align in (.75, 1, .5, None):
        position = fit(points, original, (14, 104.6, 158, 153.4), align)
        verification = verify_after(points, frames, model, skeleton, tex, events,
                                    width, position, scale)
        if verification:
            return position, verification
    raise ValueError(f'{model.type}: no readable portrait (minimum {MIN_HEIGHT}px)')


def load_model(t, s, record, archive):
    if record['modelSize']:
        off = record['modelSector'] * species.SECTOR
        data = archive[off:off + record['modelSize']]
        if coldsplit.is_split(data):
            off += math.ceil(len(data) / species.SECTOR) * species.SECTOR
            cold = archive[off:off + coldsplit.cold_length(data)]
            data = coldsplit.join(data, cold, record['para']['boneCount'], coldsplit.table_length(data))
    else:
        if 'partner_file' in s['model']:
            data = Path(species.resolve_path(s['model']['partner_file'])).read_bytes()
        else:
            data, _ = species.species_model(s)
    mmd.exe().add_type(t, record['bones'], name=s['name'])
    model = mmd.MMD.parse(data, len(record['bones']))
    model.type = t
    return model, hashlib.sha256(data).hexdigest()


def anchor_frames(frames, anchor, model):
    """Translate the whole portrait camera with one bone; retain every local pose."""
    if not anchor:
        return frames
    result = [[bone[:] for bone in pose] for pose in frames]
    for pose in result:
        world = mmd.bone_matrices(model, pose)[anchor]
        for axis in range(3):
            pose[0][6 + axis] -= world[axis][3]
    return result


def cloud(model, skeleton, scale, anchor=0):
    frames, loop, events = animsheet.slot_frames(model, len(skeleton), 0, max_ticks=10000)
    if len(frames) == 10000:
        raise ValueError('idle clip exceeds audit limit')
    frames = anchor_frames(frames, anchor, model)
    points = []
    vertices = {}
    for oi, parent in skeleton:
        if oi < 0 or oi in vertices:
            continue
        used = sorted({i for p in model.tmd.objects[oi].prims for i in p.decode()['verts']})
        raw = model.tmd.obj_verts(oi)
        vertices[oi] = [raw[i][:3] for i in used]
    for pose in frames:
        mats = mmd.bone_matrices(model, scaled_pose(pose, scale))
        for b, (oi, parent) in enumerate(skeleton):
            if oi < 0:
                continue
            matrix = mats[b]
            for v in vertices[oi]:
                points.append(camera(tuple(sum(matrix[i][j] * v[j] for j in range(3)) + matrix[i][3] for i in range(3))))
    return points, frames, loop, events


def scaled_pose(pose, scale):
    """Entity scale is the initial value; root animation adds its momentum."""
    result = [v[:] for v in pose]
    result[0][0:3] = [v + round(scale * 4096) - 4096 for v in pose[0][0:3]]
    return result


def move_image(texture, source, size, destination):
    """MoveImage coordinates/width are VRAM words (four 4-bit pixels)."""
    sx, sy = source
    dx, dy = destination
    width, height = size
    sx, dx, width = sx * 4, dx * 4, width * 4
    if not (0 <= sx <= sx + width <= texture.w and 0 <= dx <= dx + width <= texture.w and
            0 <= sy <= sy + height <= texture.h and 0 <= dy <= dy + height <= texture.h):
        raise ValueError('idle texture copy exceeds the texture page')
    rows = [texture.idx[(sy + y) * texture.w + sx:(sy + y) * texture.w + sx + width]
            for y in range(height)]
    for y, row in enumerate(rows):
        off = (dy + y) * texture.w + dx
        texture.idx[off:off + width] = row


def texture_at(blob, events, tick, width=0, phase=None):
    texture = mmd.Tim4(blob)
    for frame, kind, command in events:
        if frame <= tick and kind == 'tex':
            move_image(texture, command['src'], command['size'], command['dst'])
    if width and phase is not None:
        move_image(texture, (0, 32 + phase * 32), (width, 32), (0, 0))
    return texture


def model_layer(model, skeleton, pose, texture, position, scale):
    from PIL import Image
    pose = scaled_pose(pose, scale)
    tx, ty, tz = camera(position)

    class Perspective:
        def view(self, vertex):
            x, y, z = camera(vertex)
            depth = z + tz + LENGTH
            return 512 * (x + tx) / depth, 512 * (y + ty) / depth, depth

    image = bytearray(320 * 320 * 4)
    view = Perspective()
    triangles = []
    for triangle in animsheet.world_tris(model, pose, skeleton):
        vertices, uv, primitive = triangle
        p = [view.view(v) for v in vertices]
        area = ((p[1][0] - p[0][0]) * (p[2][1] - p[0][1]) -
                (p[1][1] - p[0][1]) * (p[2][0] - p[0][0]))
        if area >= 0 or primitive['flag'] & 2:
            triangles.append(triangle)
    animsheet.raster(triangles, view, texture,
                     320, 1, 160, 120, image, 0, 320)
    return Image.frombytes('RGBA', (320, 320), bytes(image)).crop((0, 0, 320, 240))


def render(model, skeleton, pose, texture, position, scale):
    from PIL import Image, ImageDraw
    tile = Image.new('RGBA', (320, 240), (39, 56, 66, 255))
    draw = ImageDraw.Draw(tile)
    draw.rectangle((12, 103, 160, 219), outline='#8ae3ef')
    draw.line((12, 103, 308, 103), fill='#8ae3ef')
    draw.rectangle(LABEL, fill='#e5c938')
    draw.text((22, 108), 'STATUS', fill='#171e25')
    draw.text((174, 108), 'ATTRIBUTES', fill='#e5c938')
    tile.alpha_composite(model_layer(model, skeleton, pose, texture, position, scale))
    return tile.convert('RGB')


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('build', type=Path)
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--fix', action='store_true')
    ap.add_argument('--reference', type=Path,
                    help='compare against the original before positions in a previous audit.json')
    ap.add_argument('--verify-repairs', type=Path,
                    help='verify current positions for every fixed species in an earlier audit')
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    archive, _, records = species.read_archive(str(args.build / 'DIGI.DAT'))
    alltim = (args.build / 'ALLTIM.TIM').read_bytes()
    sources = species.load_content()
    built_sources = species.load_content(str(args.build / 'species'))
    verification_set = {r['id'] for r in json.loads(args.verify_repairs.read_text()) if r['fixed']} if args.verify_repairs else set()
    reference_rows = {r['id']: r for r in json.loads(args.reference.read_text())} if args.reference else None
    reference = {t: r['before'] for t, r in reference_rows.items()} if reference_rows else None
    rules = json.loads(Path('content/tables/species-rules.json').read_text())
    scales = {r['species']: (r['percent'] * 4096 // 100) / 4096 for r in rules['modelScale']}
    animated = {r['species']: r['width'] for r in rules['animatedTexture']}
    from PIL import Image, ImageDraw
    tiles, all_tiles, results = [], [], []
    for t, s in sorted(sources.items()):
        if 'partner' not in s:
            continue
        r = records[t]
        if not r['flags'] & species.FLAG_PARTNER:
            raise ValueError(f'{t}: raisable species missing from build')
        model, sha = load_model(t, built_sources[t], r, archive)
        scale = scales.get(t, 1)
        anchor = s['partner'].get('status_screen_anchor_bone', 0)
        if r.get('statusAnchorBone', 0) != anchor:
            raise ValueError(f'{t}: rebuild first: Status anchor differs from archive')
        points, frames, loop, events = cloud(model, r['bones'], scale, anchor)
        source_position = s['partner']['status_screen_position']
        built_position = [r['raise'][k] for k in ('viewX', 'viewY', 'viewZ')]
        if built_position != source_position:
            raise ValueError(f'{t}: rebuild first: archive position {built_position} differs from source {source_position}')
        before = reference[t] if reference is not None else source_position
        before_anchor = reference_rows[t].get('status_anchor_bone', 0) if reference_rows else anchor
        if before_anchor != anchor:
            before_points, before_frames, _, _ = cloud(model, r['bones'], scale, before_anchor)
        else:
            before_points, before_frames = points, frames
        box = envelope(before_points, before)
        if r['texFile'] != species.TEX_ALLTIM:
            tex = archive[r['texSector'] * species.SECTOR:r['texSector'] * species.SECTOR + species.TEX_SIZE]
        else:
            tex = mmd.alltim_entry(alltim, t)
        width = animated.get(t, 0)
        texture = texture_at(tex, events, 0, width, 0)
        worst, pixel_box, worst_phase = None, None, None
        if not inside(box, BOX_EDGES):
            # A transparent texture border or a subpixel tip must not cause a
            # fitting original to change. Refine only the candidate frames.
            count = len(points) // len(frames)
            candidates = []
            for tick in range(len(frames)):
                b = envelope(before_points[tick * count:(tick + 1) * count], before)
                if not inside(b, BOX_EDGES):
                    candidates.append((max(BOX_EDGES[0] - b[0], BOX_EDGES[1] - b[1],
                                           b[2] - BOX_EDGES[2], b[3] - BOX_EDGES[3]), tick))
            for _, tick in sorted(candidates, reverse=True):
                for phase in (None, 0, 1, 2) if width else (None,):
                    current = texture_at(tex, events, tick, width, phase)
                    layer = model_layer(model, r['bones'], before_frames[tick], current, before, scale)
                    b = visible_bounds(layer)
                    if b is None:
                        raise ValueError(f'{t}: candidate portrait has no visible pixels')
                    if not inside(b, BOX_EDGES):
                        worst, pixel_box, worst_phase = tick, b, phase
                        break
                if worst is not None:
                    break
        # A prior audit explicitly scopes a readability repair pass. Preserve
        # the fitting originals outside that set byte-for-byte.
        if reference_rows is not None:
            worst = reference_rows[t]['overflow_tick'] if reference_rows[t]['fixed'] else None
            pixel_box = reference_rows[t]['overflow_pixels'] if worst is not None else None
        if t in verification_set:
            after = source_position
            verification = verify_after(points, frames, model, r['bones'], tex, events, width, after, scale)
            if not verification:
                raise ValueError(f'{t}: current portrait fails readability')
        else:
            after, verification = (readable_fit(points, frames, model, r['bones'], tex, events, width, before, scale)
                                   if worst is not None else (before, None))
        old_depth = camera(before)[2] + LENGTH
        new_depth = camera(after)[2] + LENGTH
        row = dict(id=t, name=s['name'], frames=len(frames), loop=loop, model_sha256=sha,
                   before=before, after=after, before_bounds=box, after_bounds=envelope(points, after),
                   overflow_tick=worst, overflow_pixels=pixel_box, overflow_texture_phase=worst_phase,
                   source_position=source_position, status_anchor_bone=anchor, before_anchor_bone=before_anchor,
                   before_distance=old_depth, after_distance=new_depth,
                   magnification_ratio=old_depth / new_depth,
                   after_verification=verification, readability_checked=verification is not None,
                   unchanged_borderline=worst is None and not inside(box, BOUNDS),
                   fixed=before != after)
        results.append(row)
        print(f'{t} {s["name"]}: {len(frames)} frames, {"FIX" if row["fixed"] else "fits"}', flush=True)
        if args.fix and source_position != after:
            path = Path(s['_path'])
            text = path.read_text()
            old = '"status_screen_position": ' + json.dumps(source_position)
            new = '"status_screen_position": ' + json.dumps(after)
            assert text.count(old) == 1, path
            path.write_text(text.replace(old, new))
        overview = Image.new('RGB', (320, 260), '#171e25')
        ImageDraw.Draw(overview).text((8, 5), f'{t} {s["name"]}', fill='white')
        overview.paste(render(model, r['bones'], frames[0], texture, after, scale), (0, 20))
        all_tiles.append(overview)
        if not row['fixed']:
            continue
        # Show a visibly overflowing frame, retaining the same tick after.
        tile = Image.new('RGB', (640, 265), '#171e25')
        d = ImageDraw.Draw(tile)
        d.text((8, 5), f'{t} {s["name"]} | idle tick {worst} | BEFORE', fill='white')
        d.text((328, 5), 'AFTER', fill='white')
        texture = texture_at(tex, events, worst, width, worst_phase)
        for x, pos in ((0, before), (320, after)):
            pose = before_frames[worst] if x == 0 else frames[worst]
            tile.paste(render(model, r['bones'], pose, texture, pos, scale), (x, 25))
        tile.save(args.out / f'{t}.png')
        tiles.append(tile)
    (args.out / 'audit.json').write_text(json.dumps(results, indent=2) + '\n')
    borderline = [r for r in results if r['unchanged_borderline']]
    (args.out / 'unchanged-borderline.txt').write_text(''.join(
        f'{r["id"]} {r["name"]}: unchanged {r["before"]}\n' for r in borderline))
    # Separate manageable sheets so names and geometry remain legible.
    for start in range(0, len(tiles), 16):
        batch = tiles[start:start + 16]
        sheet = Image.new('RGB', (1280, math.ceil(len(batch) / 2) * 265), '#171e25')
        for i, tile in enumerate(batch):
            sheet.paste(tile, ((i % 2) * 640, (i // 2) * 265))
        sheet.save(args.out / f'contact-{start // 16 + 1:02}.png')
    for start in range(0, len(all_tiles), 36):
        batch = all_tiles[start:start + 36]
        sheet = Image.new('RGB', (1920, math.ceil(len(batch) / 6) * 260), '#171e25')
        for i, tile in enumerate(batch):
            sheet.paste(tile, ((i % 6) * 320, (i // 6) * 260))
        sheet.save(args.out / f'all-{start // 36 + 1:02}.png')
    print(f'{len(results)} raisable species; {sum(r["fixed"] for r in results)} offenders')


if __name__ == '__main__':
    main()
