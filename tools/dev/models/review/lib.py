#!/usr/bin/env python3
"""The review tool's engine: species, slots, models built with any donor, and one studio video per (species, slot, donor).

Run under the card-game venv (tools/dev/models/review/server.py starts it that way). As a command it is the job a server worker runs:

  lib.py variant ID DONOR        the model of species ID with the everyday animations retargeted from DW1 donor DONOR
                                 (legs by feet and arms swung like walkpolish.py), build/review/variants/ID-dDONOR.MMD
  lib.py prerender [JOBS] [all|default]   every animation of every species with every donor (or only the default one), resumable,\n                                progress in build/review/progress.json\n  lib.py status                 how the render is going (cheap: reads the progress file)
  lib.py prune                  remove the videos of old versions
  lib.py video ID SLOT DONOR     the studio video of that animation: the model above its donor's own; DONOR 0 = the default
                                 donor (build/walkfix/ID-Name.MMD, made by walkpolish.py all)
"""

from pathlib import Path as _DevPath
import sys as _dev_sys
_DEV_ROOT = str(next(p for p in _DevPath(__file__).resolve().parents if (p / "tools").is_dir()))
_dev_sys.path.insert(0, _DEV_ROOT)
_dev_sys.path.insert(0, str(_DevPath(_DEV_ROOT) / "tools"))
import fcntl, glob, hashlib, json, math, os, shutil, subprocess, sys, time

HERE = os.path.dirname(os.path.abspath(__file__)); TOOLS = str(_DevPath(_DEV_ROOT) / "tools"); ROOT = _DEV_ROOT
sys.path.insert(0, TOOLS)
try:
    import numpy  # noqa: F401
except ImportError:
    py = os.path.join(os.environ.get('DCB_ROOT', os.path.join(ROOT, '..', 'digimoncardbattle')), '.venv', 'bin', 'python')
    if os.path.exists(py) and not os.environ.get('REVIEW_REEXEC'):
        os.environ['REVIEW_REEXEC'] = '1'
        os.execv(py, [py, os.path.abspath(__file__)] + sys.argv[1:])
    raise SystemExit('review: needs numpy and OpenCV (the card-game venv)')

WALKFIX = os.path.join(ROOT, 'build/walkfix')
CACHE = os.path.join(ROOT, 'build/review')
VARIANTS = os.path.join(CACHE, 'variants')
VIDEOS = os.path.join(CACHE, 'videos')
VENV_PY = sys.executable
TOOLS_VERSION = 'F'          # bump when legik/footfix/armswing/walkpolish/variant logic changes: the other-donor models and videos are made again
PANELS = 'mesh:three,mesh:side,skel:side'
SIZE = 240
FFMPEG = os.path.expanduser('~/.local/bin/ffmpeg')

SLOT_NAMES = {0: 'idle', 1: 'condition idle', 2: 'walk', 3: 'condition walk', 4: 'run / catch up', 5: 'happy', 7: 'sad', 8: 'eat',
              9: 'sleep', 10: 'poop', 11: 'reaction / prepares sleep', 12: 'after pooping', 13: 'rejects an item', 14: 'injured / sick',
              0x0f: 'hungry', 0x10: 'needs toilet', 0x11: 'sleepy', 0x12: 'tired', 0x13: 'unhappy', 0x15: 'cutscene object',
              0x16: 'extra', 0x17: 'chest tray', 0x18: 'chest tray', 0x19: 'extra', 0x1b: 'HP training', 0x1c: 'extra', 0x21: 'battle idle',
              0x22: 'battle idle / stunned', 0x23: 'battle walk', 0x24: 'battle run / flee', 0x25: 'block reaction',
              0x28: 'hit', 0x29: 'knocked down', 0x2a: 'victory', 0x2b: 'faint', 0x2c: 'get up'}


def slot_name(s):
    if s in SLOT_NAMES:
        return SLOT_NAMES[s]
    if s >= 0x2e:
        return f'technique {s - 0x2e + 1}'
    return 'extra'


def _walkpolish():
    sys.argv = sys.argv[:1]
    import walkpolish
    return walkpolish


def species_list():
    W = _walkpolish()
    rep = {}
    rp = os.path.join(WALKFIX, 'report.jsonl')
    if os.path.exists(rp):
        rep = {r['id']: r for r in map(json.loads, open(rp))}
    out = []
    for sp in W.all_species():
        r = rep.get(sp['id'], {})
        spec = W.spec_of(sp)
        d = int(spec['source']['type']) if spec else None
        out.append(dict(id=sp['id'], name=sp['name'], game=W.source_game(sp), donor=d, donor_name=W.DN(d) if d else '',
                        legs_fixed=bool(r.get('polished')), arms=str(r.get('arms', '')), why=r.get('why', '')))
    return out


def default_model(sp):
    return os.path.join(WALKFIX, f'{sp["id"]}-{sp["name"]}.MMD')


def donor_choices():
    import import_batch, species
    O = species.originals()
    return [dict(type=t, name=O.rec[t]['para']['name']) for t in import_batch.donor_candidates()]


_RANK = {}


def donor_ranking(sp):
    """The donors of a species, best first (tools/dev/models/review/ranking.py: the anatomy, the proportions, where the head looks, the animations the donor
    has...); the importer's own pick is tagged "(default)": its moves are the species'. The first five carry a star."""
    W = _walkpolish()
    import species; from tools.dev.models.review import ranking as ranking
    if sp['id'] in _RANK:
        return _RANK[sp['id']]
    spec = W.spec_of(sp); dd = int(spec['source']['type']) if spec else 0
    O = species.originals()
    r = ranking.load().get(str(sp['id'])) if os.environ.get('REVIEW_RANK') == 'composite' else None     # the composite score (ranking.py) is opt-in
    if r is None:                                   # the importer's own order (skeleton fit)
        import import_batch as IB
        T = shape_of_mmd(sp['model'], sp['id'])
        r = [dict(donor=d, score=a) for a, d in sorted((IB.donor_score(T, d, 0, 5)[0], d) for d in IB.donor_candidates())]
    out = []
    for k, x in enumerate(r):
        d = x['donor']
        label = O.rec[d]['para']['name'] + (' (default)' if d == dd else '')
        out.append(dict(donor=d, type=d, name=label, default=(d == dd), score=x.get('score'), star=bool(os.environ.get('REVIEW_RANK') == 'composite') and k < 5, rank=k + 1,
                        why={kk: x[kk] for kk in ('parts', 'limbs', 'proportion', 'head', 'gaze', 'slots', 'fit') if kk in x}))
    out.sort(key=lambda x: not x['default'])         # the importer's pick first, then the rest in order (stable)
    _RANK[sp['id']] = out
    return out


def slots_of(path, t):
    import mmd
    m = mmd.MMD.load(path, t)
    return [s for s, i in enumerate(m.anims.table) if i is not None]


# ------------------------------------------------------------------ models with any donor
def shape_of_mmd(path, t):
    import import_batch as IB, mmd, retarget
    e = mmd.exe(); nb = e.bone_count[t]
    m = mmd.MMD.load(path, t)
    pose = retarget.rest_pose(m, nb, 0)
    M = mmd.bone_matrices(m, pose)
    joints, tips, mass, pts, lows = [], [], [], [], []
    for b, (oi, par) in enumerate(e.skeleton[t]):
        joints.append([M[b][r][3] for r in range(3)])
        vs = [IB.m_apply(M[b], v[:3]) for v in m.tmd.obj_verts(oi)] if oi >= 0 else []
        pts += vs
        lows.append(max(v[1] for v in vs) if vs else None)
        tips.append([sum(v[k] for v in vs) / len(vs) for k in range(3)] if vs else joints[-1])
        mass.append(len(vs))
    return IB.Shape(joints, tips, mass, [p for _, p in e.skeleton[t]], IB.bbox(pts), pts, lows)


def bone_map_roles(T, S):
    """The bone map of a variant: by anatomy (limbmap.py: legs with legs, arms with arms, head, tail, the bones that host them), and
    what no part covers by the importer's greedy map with the limb roles on (rigfix.role_cost) plus a same-role fill."""
    import import_batch as IB; import rigfix; from tools.dev.models.review import limbmap as limbmap
    try:
        m = dict(limbmap.limb_map(T, S))
    except Exception:
        m = {}
    covered = set(m)
    old = IB.ROLES
    IB.ROLES = True
    try:
        g, _ = IB.bone_map(T, S)
    finally:
        IB.ROLES = old
    rt, rs = rigfix.roles(T), rigfix.roles(S)
    used = set(m.values())
    parts_t = set()
    try:
        P = limbmap.parts(T)
        for _, c in P['legs'] + P['arms']:
            parts_t |= set(c)
        parts_t |= set(P['head']) | set(P['tail']) | ({P['jaw']} if P.get('jaw') else set())
    except Exception:
        pass
    for tb, sb in g.items():                           # the importer's pairs for what the anatomy left out (same role only)
        if tb not in covered and tb not in parts_t and sb not in used and (rt[tb] == rs[sb] or 'body' in (rt[tb], rs[sb])):
            m[tb] = sb; used.add(sb)
    order = sorted(range(1, len(T.joint)), key=lambda b: len(T.ancestors(b)))
    for tb in order:
        if tb in m or tb in parts_t or not T.mass[tb] or rt[tb] in ('body',):
            continue
        side = T.tip[tb][0]
        cands = [sb for sb in range(1, len(S.joint)) if sb not in used and S.mass[sb] and rs[sb] == rt[tb]
                 and (abs(side) < 0.04 or abs(S.tip[sb][0]) < 0.04 or (side > 0) == (S.tip[sb][0] > 0))]
        if cands:
            sb = min(cands, key=lambda c: IB.bone_cost(T, S, tb, c))
            m[tb] = sb; used.add(sb)
    # the wrists: armmatch.py points the upper arm and the forearm along the donor's, and the hand stays under the forearm; a rotation copied
    # from a donor hand (another axis) would twist it, so the last bone of each arm is left out of the map
    try:
        P = limbmap.parts(T)
        for _, c in P['arms']:
            c = [b for b in c if T.mass[b]]
            if len(c) >= 3:
                m.pop(c[-1], None)
    except Exception:
        pass
    # ornaments on the head (crests, wings, ears, a helmet) are not mapped: given a donor bone they move like the donor's head, unmapped they stay rigid with it
    try:
        P = limbmap.parts(T)
        if P['head']:
            hb = P['head'][-1]
            for b in range(1, len(T.parent)):
                a = T.parent[b]
                while a > 0 and a != hb:
                    a = T.parent[a]
                if a == hb and b != P.get('jaw') and b not in P['head']:
                    m.pop(b, None)
    except Exception:
        pass
    return m


def lock(path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    f = open(path + '.lock', 'w')
    fcntl.flock(f, fcntl.LOCK_EX)
    return f


def variant_path(sp, donor):
    return default_model(sp) if donor == 0 else os.path.join(VARIANTS, f'{sp["id"]}-d{donor}-{version(sp, donor)}.MMD')


def build_variant(sp, donor):
    """The model with its everyday slots retargeted from `donor` (a DW1 type), polished like walkpolish.py. Returns the path."""
    W = _walkpolish()
    import import_batch as IB, mmd, mmdport, species
    out = variant_path(sp, donor)
    if donor == 0:
        return out
    lk = lock(out)
    try:
        if os.path.exists(out):
            return out
        spec0 = W.spec_of(sp)
        t = sp['id']
        T = shape_of_mmd(sp['model'], t)
        S, _, _ = IB.donor_shape(donor)
        bmap = bone_map_roles(T, S)
        roots = [b for b in range(1, len(T.joint)) if T.parent[b] == 0]
        hips_src = [b for b in range(1, len(S.joint)) if S.parent[b] == 0][0]
        k = round(T.H / S.H, 3)
        base = mmd.MMD.load(sp['model'], t)
        own = {int(x, 0) if isinstance(x, str) else int(x) for x in (spec0.get('clips') or {})}
        own |= {0x21, 0x28, 0x29, 0x2a, 0x2b, 0x2c}      # the source game's own clips stay; techniques (0x2e..) stay the default donor's: their effects are timed to that animation
        donor_mmd = mmd.MMD.load(species.originals().model_path(donor), donor)
        slots = [s for s, i in enumerate(base.anims.table) if i is not None and s < 0x2e and s not in own
                 and s < len(donor_mmd.anims.table) and donor_mmd.anims.table[s] is not None]
        os.makedirs(VARIANTS, exist_ok=True)
        tmpdir = os.path.join(CACHE, 'tmp'); os.makedirs(tmpdir, exist_ok=True)
        raw = os.path.join(tmpdir, f'{t}-d{donor}-raw.MMD')
        shutil.copy(sp['model'], raw)
        spec = {'type': t, 'name': sp['name'], 'source': {'type': donor, 'mmd': os.path.relpath(species.originals().model_path(donor), ROOT)},
                'map': {str(tb): sb for tb, sb in sorted(bmap.items())}, 'hips': [roots[0], hips_src, k], 'root_scale': k,
                'tol': spec0.get('tol', 8) if spec0 else 8, 'native': os.path.relpath(raw, ROOT), 'retarget': [f'{s:#04x}' for s in slots], '_own': sorted(own)}
        built = os.path.join(tmpdir, f'{t}-d{donor}-built.MMD'); oversize = False
        limit = mmdport.PARTNER_MMD_MAX + 0x6000        # (the cold animations are not in the buffer: walkpolish.SZ)
        for tol in (spec['tol'], 12, 16, 24, 32, -32):       # coarser keys until the file fits the buffer; the last try is allowed to be over it
            spec['tol'] = abs(tol)
            mmdport.PARTNER_MMD_MAX = limit if tol > 0 else 0x40000
            try:
                mmdport.build_partner(None, spec, built, os.path.join(tmpdir, f'{t}-d{donor}.TIM'), tmpdir, log=lambda *a: None)
                break
            except SystemExit as ex:
                if 'PARTNER_MODEL_BUFFER' not in str(ex) or tol < 0:
                    raise
            finally:
                mmdport.PARTNER_MMD_MAX = limit
        sp2 = dict(sp, model=built)
        rep = W.polish(sp2, tmpdir, spec=spec, final=out)
        json.dump(rep, open(out + '.rep.json', 'w'))             # what the polish did and why not (for debugging a variant)
        json.dump(slots, open(out + '.slots.json', 'w'))
        return out
    finally:
        lk.close()


# ------------------------------------------------------------------ videos
_HASH = {}


def _sha(paths):
    key = tuple((p, os.path.getmtime(p)) for p in paths if os.path.exists(p))
    if key not in _HASH:
        h = hashlib.sha1()
        for p in paths:
            if os.path.exists(p):
                h.update(open(p, 'rb').read())
        _HASH[key] = h.hexdigest()[:8]
    return _HASH[key]


def version(sp, donor):
    """What a video was made from: the default model's bytes, or (another donor) the importer's model and the polish tools."""
    if donor == 0:
        return _sha([default_model(sp)])
    return _sha([sp['model']]) + (frozen_tag(sp, donor) or TOOLS_VERSION)


def frozen_tag(sp, donor):
    """An approved species keeps the model it was approved with: the variant of the donor it was approved on, as it was built then (the
    oldest tools tag it exists with). A change to the polish tools never touches it; to rebuild one, delete its variant file."""
    try:
        d = json.load(open(os.path.join(ROOT, 'build/review/decisions.json')))['species'].get(str(sp['id']), {})
    except Exception:
        return None
    if not d.get('approved') or int(d.get('chosen') or 0) != donor:
        return None
    for tag in ('C', 'D'):
        if os.path.exists(os.path.join(VARIANTS, f'{sp["id"]}-d{donor}-{_sha([sp["model"]])}{tag}.MMD')):
            return tag
    return None


def made_at(sp, donor):
    """When the newest video of the species with `donor` was made, as Spain time 'YYYY-MM-DD HH:MM' (None if there are none)."""
    from datetime import datetime
    from zoneinfo import ZoneInfo
    try:
        ts = [os.lstat(f).st_mtime for f in glob.glob(os.path.join(VIDEOS, str(sp['id']), version(sp, donor), f'*-d{donor}.mp4'))]
    except Exception:
        return None
    return datetime.fromtimestamp(max(ts), ZoneInfo('Europe/Madrid')).strftime('%Y-%m-%d %H:%M') if ts else None


def video_path(sp, slot, donor):
    return os.path.join(VIDEOS, str(sp['id']), version(sp, donor), f'{slot:02x}-d{donor}.mp4')


def _encode(rows, size, ticks, out):
    """Frames straight into ffmpeg (no PNG files): one H.264 loop, written to out atomically."""
    import animstudio as A
    f0 = A.frame(rows, 0, size)
    W, H = f0.size
    os.makedirs(os.path.dirname(out), exist_ok=True)
    tmp = out + f'.{os.getpid()}.part.mp4'
    p = subprocess.Popen([FFMPEG, '-y', '-loglevel', 'error', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{W}x{H}', '-r', '20', '-i', '-',
                          '-vf', 'pad=ceil(iw/2)*2:ceil(ih/2)*2', '-c:v', 'libx264', '-preset', 'superfast', '-threads', '1', '-crf', '27', '-pix_fmt', 'yuv420p', tmp],
                         stdin=subprocess.PIPE)
    p.stdin.write(f0.tobytes())
    for t in range(1, ticks):
        p.stdin.write(A.frame(rows, t, size).tobytes())
    p.stdin.close()
    if p.wait():
        raise RuntimeError('ffmpeg failed')
    os.replace(tmp, out)


def donor_video_path(dt, slot):
    return os.path.join(CACHE, 'donor', f'{dt}-{slot:02x}.mp4')


def render_donor(dt, slot, mod=None):
    """The donor's own animation (shared by every species that uses that donor)."""
    import animstudio as A, species
    out = donor_video_path(dt, slot)
    if os.path.exists(out):
        return out
    path = species.originals().model_path(dt)
    mod = mod or A.Model(f'{path}:{dt}::{slot}:{_walkpolish().DN(dt)} (donor, DW1 #{dt})', slot)
    mod.set_slot(slot)
    _encode(A.build([mod], PANELS.split(','), SIZE), SIZE, len(mod.frames), out)
    return out


def render_species(sp, donor, slots=None, progress=None):
    """Every animation of the species built with `donor` (0 = the default one), plus the donor's own videos that are missing."""
    import animstudio as A, mmd, species
    W = _walkpolish()
    t = sp['id']
    spec = W.spec_of(sp)
    dt = donor or (int(spec['source']['type']) if spec else 0)
    model = build_variant(sp, donor)
    m = mmd.MMD.load(model, t)
    have = [s for s, i in enumerate(m.anims.table) if i is not None]
    slots = [s for s in (slots or have) if s in have]
    if donor:                                       # only the everyday slots the donor changed; the rest is the default model's video
        changed = set(json.load(open(model + '.slots.json'))) if os.path.exists(model + '.slots.json') else set(have)
        for s in slots:
            if s not in changed and not os.path.exists(video_path(sp, s, donor)):
                base = video_path(sp, s, 0)
                if not os.path.exists(base):
                    render_species(sp, 0, [s])
                os.makedirs(os.path.dirname(video_path(sp, s, donor)), exist_ok=True)
                try:
                    os.symlink(base, video_path(sp, s, donor))
                except FileExistsError:
                    pass
        slots = [s for s in slots if s in changed]
    todo = [s for s in slots if not os.path.exists(video_path(sp, s, donor))]
    if not todo:
        return 0
    label = f'{sp["name"]} ({W.source_game(sp)}, donor {W.DN(dt)})'
    mod = A.Model(f'{model}:{t}:{sp["tex"]}:{todo[0]}:{label}', todo[0])
    O = species.originals()
    dmod = None
    if dt:
        d = mmd.MMD.load(O.model_path(dt), dt)
    for s in todo:
        mod.set_slot(s)
        _encode(A.build([mod], PANELS.split(','), SIZE), SIZE, len(mod.frames), video_path(sp, s, donor))
        if dt and s < len(d.anims.table) and d.anims.table[s] is not None and not os.path.exists(donor_video_path(dt, s)):
            if dmod is None:
                dmod = A.Model(f'{O.model_path(dt)}:{dt}::{s}:{W.DN(dt)} (donor, DW1 #{dt})', s)
            render_donor(dt, s, dmod)
        if progress:
            progress()
    return len(todo)


def render_video(sp, slot, donor):
    render_species(sp, donor, [slot])
    return video_path(sp, slot, donor)


PROGRESS = os.path.join(CACHE, 'progress.json')


def _task(a):
    sid, donor, slots = a
    try:
        n = render_species(find(sid), donor, slots)
        return sid, donor, n, ''
    except BaseException as ex:
        return sid, donor, 0, f'{type(ex).__name__}: {str(ex)[:160]}'


def prerender(jobs=14, donors='all', ids=None):
    """Every animation of every species with every donor (donors='default': only the default one): one task per (species, donor),
    resumable (what exists is skipped), progress in build/review/progress.json (read it with `lib.py status`)."""
    from multiprocessing import Pool
    W = _walkpolish()
    cands = [d['type'] for d in donor_choices()]
    sps = [sp for sp in W.all_species() if os.path.exists(default_model(sp)) and (not ids or sp['id'] in ids)]
    tasks = []
    for sp in sps:                      # Digimon by Digimon: walk, idle, first attack with every donor, then the rest with every donor
        spec = W.spec_of(sp); dd = int(spec['source']['type']) if spec else 0
        from tools.dev.models.review import ranking as ranking
        order = [x['donor'] for x in ((ranking.load().get(str(sp['id'])) if os.environ.get('REVIEW_RANK') == 'composite' else None) or [])] or list(cands)
        ds = [0, dd] + ([d for d in order if d != dd] if donors == 'all' else [])
        ds = [d for k, d in enumerate(ds) if d not in ds[:k]]
        tasks += [(sp['id'], d, [2, 0, 0x2e]) for d in ds]
        tasks += [(sp['id'], d, None) for d in ds]
    t0 = time.time(); done, errors, made = 0, [], 0
    state = dict(total=len(tasks), done=0, made_videos=0, errors=[], started=t0, jobs=jobs)

    def save():
        state.update(done=done, made_videos=made, errors=errors[-20:], elapsed=round(time.time() - t0),
                     eta_hours=round((time.time() - t0) / max(done, 1) * (len(tasks) - done) / 3600, 1), updated=time.strftime('%H:%M:%S'))
        json.dump(state, open(PROGRESS + '.tmp', 'w')); os.replace(PROGRESS + '.tmp', PROGRESS)
    save()
    with Pool(jobs, maxtasksperchild=20) as pool:
        for sid, donor, n, err in pool.imap_unordered(_task, tasks, chunksize=1):
            done += 1; made += n
            if err:
                errors.append(f'{sid} donor {donor}: {err}')
            if done % 5 == 0 or err:
                save()
    save()


def status():
    try:
        d = json.load(open(PROGRESS))
    except OSError:
        print('no render run yet'); return
    print(f"{d['done']}/{d['total']} (species, donor) tasks, {d['made_videos']} videos, {d.get('elapsed', 0) // 3600}h{d.get('elapsed', 0) % 3600 // 60:02d} elapsed, "
          f"about {d.get('eta_hours', '?')} h left, {len(d['errors'])} errors, updated {d.get('updated')}")
    for e in d['errors'][-5:]:
        print('  error:', e)
    n = size = 0
    for r, _, f in os.walk(VIDEOS):
        for x in f:
            try:
                size += os.path.getsize(os.path.join(r, x)); n += 1
            except OSError:
                pass
    print(f'  on disk: {n} model videos, {size / 1e9:.1f} GB')


def prune():
    """Delete the videos and models of versions that are no longer current (the model changed, or TOOLS_VERSION was bumped). Kept: the
    current ones, and what an approved species is pinned to (frozen_tag)."""
    W = _walkpolish(); n = 0; freed = 0
    try:
        dec = json.load(open(os.path.join(ROOT, 'build/review/decisions.json')))['species']
    except Exception:
        dec = {}
    for sp in W.all_species():
        sid = sp['id']
        cur = {version(sp, 0), _sha([sp['model']]) + TOOLS_VERSION}
        pin = dec.get(str(sid), {})
        if pin.get('approved'):
            cur.add(version(sp, int(pin.get('chosen') or 0)))
        d = os.path.join(VIDEOS, str(sid))
        if os.path.isdir(d):
            for v in os.listdir(d):
                if v not in cur and os.path.isdir(os.path.join(d, v)):
                    freed += sum(os.path.getsize(os.path.join(r, f)) for r, _, fs in os.walk(os.path.join(d, v)) for f in fs if os.path.exists(os.path.join(r, f)))
                    shutil.rmtree(os.path.join(d, v)); n += 1
        keep = {_sha([sp['model']]) + TOOLS_VERSION}
        if pin.get('approved') and int(pin.get('chosen') or 0):
            keep.add(version(sp, int(pin['chosen'])))
        for f in glob.glob(os.path.join(VARIANTS, f'{sid}-d*-*')):
            base = os.path.basename(f)
            if base.split('-')[0] == str(sid) and not any(f'-{k}.MMD' in base for k in keep):
                freed += os.path.getsize(f) if os.path.exists(f) else 0
                if os.path.exists(f):
                    os.remove(f); n += 1
    print('removed', n, 'old version folders / files,', round(freed / 1e9, 1), 'GB')


def find(sid):
    W = _walkpolish()
    return next(s for s in W.all_species() if s['id'] == sid)


def main():
    a = list(sys.argv[1:])
    if a[0] == 'prerender':
        return prerender(int(a[1]) if len(a) > 1 else 14, a[2] if len(a) > 2 else 'all')
    if a[0] == 'status':
        return status()
    if a[0] == 'prune':
        return prune()
    sp = find(int(a[1]))
    if a[0] == 'variant':
        print(build_variant(sp, int(a[2])))
    elif a[0] == 'video':
        print(render_video(sp, int(a[2], 0), int(a[3])))


if __name__ == '__main__':
    main()
