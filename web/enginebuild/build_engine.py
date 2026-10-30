"""build_engine.py: the web engine's static files from a make-release (format 3, the derive builder), for the page's
"Build" (web/js/engine/). docs: web/README.md "The engine".

  python3 web/enginebuild/build_engine.py --release REL --disc us=USA.bin [--disc jp1=JP1.bin ...] --pyodide DIR
                                          --out OUT [--work DIR] [--keep-work]

OUT/<version>/ gets
  plan.json            the jobs (derive's steps as the workers run them: prepare / units / finish, build / finish), each
                       with the files it reads (bundle or tree), the folders it lists, what must not exist, the jobs it
                       waits for and its estimated seconds; the bundle's file index (pack, offset, size); the release's
                       bases and holes
  packs/*.pack         the bundle files the jobs read, each deflated on its own (random access by range); code.pack
                       holds every Python file, tools/, the release's patcher files and web/enginebuild/glue.py (a
                       worker loads it whole when it starts)
  pyodide/             Pyodide (the .mjs files renamed .js: the server has no type for .mjs)
OUT/current.json       {"version": the engine's, "release_version", "release_date": the release's}: the page reads it first
Older versions in OUT are removed.

How the jobs' inputs are known: record.py runs the build in a tree of the release's bundle and the extracted files of
each --disc, one job after another as a worker would, and records what each job opens, lists and stats. A job waits
for the jobs that wrote what it reads (and, the other way round, a job that overwrites a file waits for those that
read the older one), besides derive's step order (AFTER) and its own step's prepare. Every --disc is recorded and the
inputs are the union: the jobs and their units must come out the same.
"""
import argparse
import hashlib
import re
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
MANIFEST = 'build/everything/derived/manifest.json'      # every finish reads and writes it: the finish lock orders them
PACK_SIZE = 16 << 20
# a folder tempfile names (mkdtemp: prefix + 8 random characters): another name in every build. A job that reads a
# file under one (the story passes' build/dws/run-*/ maps, which the story's finish copies) gets every file of the
# same path under any such folder (`globs`); such folders are not made, listed exactly or removed for a job.
RANDOM = re.compile(r'(?:^|/)(?:run-|check-|tmp|\.base-gen-|\.base-repro-|lift-|cov-|mh-)[a-z0-9_]{8}(?=/|$)')
NATIVE_TO_BROWSER = 2.3                              # Pyodide / CPython (measured 2.0-2.6 per step)
WRITE_EST = 45                                       # the holes' check and the disc writer in a browser (s)


def say(*a):
    print(*a, flush=True)


def sha1_file(p):
    h = hashlib.sha1()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''):
            h.update(b)
    return h.hexdigest()


# ------------------------------------------------------------------ a tree and its record
def make_tree(rel, key, disc, tree, source_discs=None):
    """The release's bundle (hard links) + extracted/ from `disc` (glue.extract, as the page does)."""
    sys.path.insert(0, HERE)
    import glue
    bundle = os.path.join(rel, 'bundle')
    for dp, dns, fns in os.walk(bundle):
        dns[:] = [d for d in dns if d != '__pycache__']
        for f in fns:
            src = os.path.join(dp, f)
            dst = os.path.join(tree, os.path.relpath(src, bundle))
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            try:
                os.link(src, dst)
            except OSError:
                shutil.copyfile(src, dst)
    k, title = glue.identify(rel, disc)
    if k != key:
        raise SystemExit(f'--disc {key}: that disc is {title} ({k})')

    def put(q, b):
        dst = os.path.join(tree, 'extracted', *q.split('/'))
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        with open(dst, 'wb') as f:
            f.write(b)
    work = tempfile.mkdtemp(prefix='extract-', dir=os.path.dirname(tree))
    t0 = time.time()
    glue.extract(rel, disc, key, put, work, source_discs=source_discs)
    shutil.rmtree(work, ignore_errors=True)
    say(f'  {key}: extracted in {time.time() - t0:.1f} s')


def extract_reads(rel, key, disc, work, source_discs=None):
    """The bundle files the extraction of `disc` reads (jp1's localize tool and its art), the tool run in this process
    as the page runs it."""
    sys.path.insert(0, HERE)
    import glue
    bundle = os.path.join(rel, 'bundle') + os.sep
    reads = set()

    def hook(ev, args):
        if ev == 'open' and isinstance(args[0], str):
            p = os.path.realpath(os.path.abspath(args[0]))
            if p.startswith(bundle) and '__pycache__' not in p:
                reads.add(p[len(bundle):])
    sys.addaudithook(hook)            # (stays; reads only grows inside the bundle)
    out = tempfile.mkdtemp(prefix='extract-reads-', dir=work)
    glue.extract(rel, disc, key, lambda q, b: None, out, source_discs=source_discs)
    shutil.rmtree(out, ignore_errors=True)
    return reads


def record(tree, out_json):
    t0 = time.time()
    r = subprocess.run([sys.executable, os.path.join(HERE, 'record.py'), tree, out_json], cwd=tree,
                       env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1'))
    if r.returncode:
        raise SystemExit(f'record.py failed in {tree}')
    say(f'  recorded in {time.time() - t0:.0f} s')
    return json.load(open(out_json))


# ------------------------------------------------------------------ the plan
def plan_jobs(recs, bundle_files):
    """The jobs of the records (one per --disc; the same jobs) with their inputs and the jobs they wait for."""
    ref = recs[0]
    names = [j['name'] for j in ref['jobs']]
    for r in recs[1:]:
        if [j['name'] for j in r['jobs']] != names:
            raise SystemExit('the records have different jobs (a step\'s units differ between bases)')
    tree = ref['tree']
    jobs = []
    alive = set()             # files the jobs before this one made (and did not remove): their folders exist
    static = {os.path.dirname(p) for p in bundle_files}
    last_writer = {}          # path -> index of the last job (in the recorded order) that wrote or removed it
    readers = {}              # path -> jobs that read it since its last write
    warn = []
    for i, j in enumerate(ref['jobs']):
        js = [r['jobs'][i] for r in recs]
        existed = set().union(*(set(x['existed']) for x in js))
        lists = {}
        for x in js:
            for d, names_ in x['lists'].items():
                lists.setdefault(d, set()).update(names_)
        absent = set().union(*(set(x['absent']) for x in js)) - existed
        writes = set().union(*(set(x['writes']) for x in js))
        removes = set().union(*(set(x['removes']) for x in js))
        deps = set()
        tree_in, bundle_in = [], []

        def same_step_unit(w):
            # rule (derive, runner.Unit): a step's units do not read what another one writes; the story passes' in-place
            # edits of the new screens' .MAP (backend.keep_orig: the same bytes from each, whichever runs first) are the
            # one case, and they run side by side natively too (--jobs)
            return j['part'] == 'unit' and ref['jobs'][w]['part'] == 'unit' and ref['jobs'][w]['step'] == j['step']
        globs = set()
        for p in sorted(existed):
            if '__pycache__' in p:
                continue
            w = last_writer.get(p)
            if RANDOM.search(p):
                if w is None:
                    warn.append(f'{j["name"]}: reads {p}, which no earlier job wrote')
                deps.add(w)
                globs.add(RANDOM.sub(lambda m: m.group(0)[:m.group(0).rindex('/') + 1 if '/' in m.group(0) else 0] + '*', p))
                continue
            if p == MANIFEST:
                tree_in.append(p)          # (the finish lock orders the finishes; the latest manifest is read)
                continue
            if w is not None:
                if not same_step_unit(w):
                    deps.add(w)
                tree_in.append(p)
            elif p.startswith('extracted/') or p.startswith('build/everything/source-games/'):
                tree_in.append(p)
            elif p in bundle_files:
                bundle_in.append(p)
            else:
                warn.append(f'{j["name"]}: reads {p}, which neither the bundle nor an earlier job has')
        for p in writes | removes:
            if p == MANIFEST:
                continue
            w = last_writer.get(p)
            if w is not None:
                same_step_units = (ref['jobs'][w]['step'] == j['step'] and ref['jobs'][w]['part'] == j['part'] == 'unit'
                                   and all(x['writes'].get(p) == recs[k]['jobs'][w]['writes'].get(p)
                                           for k, x in enumerate(js)))
                if not same_step_units:
                    deps.add(w)
            deps |= {r for r in readers.get(p, set()) - {i} if not same_step_unit(r)}
        made = set()
        for p in alive:
            d = os.path.dirname(p)
            while d and d not in made and d not in static:
                made.add(d); d = os.path.dirname(d)
        leaves = {d for d in made if not d.startswith('extracted/') and not RANDOM.search(d)}
        leaves -= {os.path.dirname(d) for d in leaves}
        alive |= writes; alive -= removes
        for p in existed:
            readers.setdefault(p, set()).add(i)
        for p in writes | removes:
            last_writer[p] = i
            readers[p] = set()
        if j['part'] == 'finish':
            # every finish adds its step to the manifest the finishes before it wrote, whichever ran first (the lock
            # orders them; natively the first one found none)
            if MANIFEST not in tree_in:
                tree_in.append(MANIFEST)
            absent.discard(MANIFEST)
        jobs.append(dict(id=i, step=j['step'], part=j['part'], index=j['index'], name=j['name'],
                         argv=[a.replace(tree, '{ROOT}') for a in j['argv']],
                         seconds=max(x['seconds'] for x in js), deps=sorted(deps), tree=tree_in, bundle=bundle_in,
                         lists={d: [sorted(x for x in n if f'{d}/{x}' in existed),
                                    sorted(x for x in n if f'{d}/{x}' not in existed)] for d, n in lists.items()
                                if not RANDOM.search(d) and not any(RANDOM.search(f'{d}/{x}') for x in n)},
                         absent=sorted(p for p in absent if not RANDOM.search(p)), mkdirs=sorted(leaves),
                         globs=sorted(globs),
                         writes=sorted(writes), removes=sorted(removes)))
    # what a step's units write in place (the story passes' .MAP and .MAP.orig): a unit gets them as they are when it
    # starts (whichever unit wrote them), never removed for it
    for j in jobs:
        if j['part'] == 'unit':
            others = set().union(*(set(x['writes']) for x in jobs if x['part'] == 'unit' and x['step'] == j['step']
                                   and x['id'] != j['id']))
            shared = set(j['absent']) & others
            if shared:
                j['absent'] = [p for p in j['absent'] if p not in shared]
                j['tree'] = sorted(set(j['tree']) | shared)
    # Native imports can retain immutable data between sibling units (the sign
    # cutout index, for example). A browser can assign either unit to a cold
    # worker, so each needs the static bundle inputs observed across its siblings.
    # Keep tree inputs and their version/dependency rules specific to each job.
    unit_bundle = {}
    for j in jobs:
        if j['part'] == 'unit':
            unit_bundle.setdefault(j['step'], set()).update(j['bundle'])
    for j in jobs:
        if j['part'] == 'unit':
            j['bundle'] = sorted(unit_bundle[j['step']])
    return jobs, warn


def schedule_deps(jobs, order, after):
    """derive's own order on top of the recorded one: a step's units after its prepare, its finish after its units, a
    step's first job after the finishes of the steps it reads (AFTER). The `units` jobs are the engine's own (the list
    is in the plan) and are dropped."""
    by_step = {}
    for j in jobs:
        by_step.setdefault(j['step'], []).append(j)
    finish = {s: next(j['id'] for j in by_step[s] if j['part'] == 'finish') for s in order}
    for s in order:
        js = by_step[s]
        first = [j for j in js if j['part'] in ('prepare', 'build')]
        prep = [j['id'] for j in first]
        for j in js:
            d = set(j['deps'])
            if j['part'] in ('prepare', 'build'):
                d |= {finish[a] for a in after[s]}
            elif j['part'] in ('unit', 'units'):
                d |= set(prep)
            elif j['part'] == 'finish':
                d |= {x['id'] for x in js if x['part'] != 'finish'}
            j['deps'] = sorted(d)
    drop = {j['id'] for j in jobs if j['part'] == 'units'}
    keep = [j for j in jobs if j['id'] not in drop]
    for j in keep:
        # (a job that waited for a dropped one waits for what that one waited for)
        d, seen = set(), set()
        st = list(j['deps'])
        while st:
            x = st.pop()
            if x in seen: continue
            seen.add(x)
            if x in drop: st.extend(jobs[x]['deps'])
            else: d.add(x)
        j['deps'] = sorted(d)
    return keep


# ------------------------------------------------------------------ packs
def writer_inputs(bundle_files, code):
    """The fresh writer can regenerate tables from any shipped bundle data.

    Derive-job and extraction traces do not cover those final reader calls.
    Executable code is already installed when the worker starts.
    """
    return set(bundle_files) - set(code)


def make_packs(bundle, files, code, out_dir):
    """packs/code.pack (the `code` files) and packs/data-NN.pack (the rest), each file deflated on its own ->
    index [[path, pack, offset, stored size, size, method (8 deflate, 0 stored)]], packs [{name, size, sha1}]."""
    os.makedirs(os.path.join(out_dir, 'packs'), exist_ok=True)
    index, packs = [], []

    def write(name, paths):
        nonlocal index
        p = os.path.join(out_dir, 'packs', name)
        off = 0
        n = len(packs)
        with open(p, 'wb') as f:
            for rel in paths:
                src = os.path.join(bundle, rel) if not isinstance(files.get(rel), str) else files[rel]
                b = open(src, 'rb').read()
                c = zlib.compressobj(9, zlib.DEFLATED, -15)
                z = c.compress(b) + c.flush()
                method = 8 if len(z) < len(b) * 0.97 else 0
                data = z if method else b
                f.write(data)
                index.append([rel, n, off, len(data), len(b), method])
                off += len(data)
        packs.append(dict(name=name, size=off, sha1=sha1_file(p), files=len(paths)))

    write('code.pack', sorted(code))
    data = sorted(set(files) - set(code))
    chunk, size, k = [], 0, 0
    for rel in data:
        chunk.append(rel)
        size += os.path.getsize(files[rel] if isinstance(files.get(rel), str) else os.path.join(bundle, rel))
        if size >= PACK_SIZE:
            write(f'data-{k:02d}.pack', chunk); chunk, size, k = [], 0, k + 1
    if chunk:
        write(f'data-{k:02d}.pack', chunk)
    return index, packs


def vendor_pyodide(src, dst):
    """Pyodide's runtime; .mjs -> .js (and the one import of pyodide.asm.mjs in pyodide.mjs)."""
    os.makedirs(dst, exist_ok=True)
    lock = json.load(open(os.path.join(src, 'pyodide-lock.json')))
    for f in ('pyodide.asm.wasm', 'python_stdlib.zip', 'pyodide-lock.json'):
        shutil.copyfile(os.path.join(src, f), os.path.join(dst, f))
    esm = open(os.path.join(src, 'pyodide.mjs'), encoding='utf-8').read()
    if esm.count('pyodide.asm.mjs') != 1:
        raise SystemExit('pyodide.mjs: expected one reference to pyodide.asm.mjs')
    esm = esm.replace('pyodide.asm.mjs', 'pyodide.asm.js').replace('//# sourceMappingURL=pyodide.mjs.map', '')
    open(os.path.join(dst, 'pyodide.esm.js'), 'w', encoding='utf-8').write(esm)
    asm = open(os.path.join(src, 'pyodide.asm.mjs'), encoding='utf-8').read()
    open(os.path.join(dst, 'pyodide.asm.js'), 'w', encoding='utf-8').write(asm)
    return lock['info']


# ------------------------------------------------------------------ main
def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--release', required=True)
    ap.add_argument('--disc', action='append', required=True, metavar='KEY=BIN')
    ap.add_argument('--source-disc', action='append', default=[], metavar='GAME=IMAGE',
                    help='source discs for a delta-model release: dcb, dw2, dw2003')
    ap.add_argument('--pyodide', required=True, help='a folder with Pyodide 314.0.7 (npm package)')
    ap.add_argument('--out', required=True)
    ap.add_argument('--work', help='temporary trees (about 1 GB per --disc)')
    ap.add_argument('--keep-work', action='store_true')
    ap.add_argument('--records', help='(developers) reuse the records of an earlier run in this folder')
    a = ap.parse_args()
    rel = os.path.abspath(a.release)
    m = json.load(open(os.path.join(rel, 'manifest.json')))
    if m.get('format') != 3 or m['variants'][m['default']]['local'].get('builder') != 'derive':
        raise SystemExit(f'{rel}: not a format 3 release with the derive builder')
    v = m['variants'][m['default']]
    missing = set(m.get('source_discs', [])) - {s.split('=', 1)[0] for s in a.source_disc}
    if missing:
        raise SystemExit('missing --source-disc: ' + ', '.join(sorted(missing)))
    work = tempfile.mkdtemp(prefix='webengine-', dir=a.work)
    t0 = time.time()
    try:
        recs = []
        for spec in a.disc:
            key, path = spec.split('=', 1)
            if key not in m['bases']:
                raise SystemExit(f'--disc {key}: the release has no base {key}')
            rj = os.path.join(a.records, f'record-{key}.json') if a.records else None
            if rj and os.path.exists(rj):
                say(f'{key}: the record of {rj}')
                recs.append(json.load(open(rj)))
                continue
            say(f'{key}: a tree and its record')
            tree = os.path.join(work, f'tree-{key}')
            make_tree(rel, key, os.path.abspath(path), tree, a.source_disc)
            if m.get('source_discs'):
                argv = [sys.executable, '-m', 'tools.derive', 'sources', '--out', 'build/everything/source-games']
                for source in a.source_disc:
                    game, image = source.split('=', 1)
                    argv += ['--source-disc', game + '=' + os.path.abspath(image)]
                subprocess.run(argv, cwd=tree, check=True)
            out_json = os.path.join(work, f'record-{key}.json')
            recs.append(record(tree, out_json))
            if a.records:
                os.makedirs(a.records, exist_ok=True)
                shutil.copyfile(out_json, os.path.join(a.records, f'record-{key}.json'))
            shutil.rmtree(tree, ignore_errors=True)
        ex_reads = set()
        for spec in a.disc:
            key, path = spec.split('=', 1)
            r = extract_reads(rel, key, os.path.abspath(path), work, a.source_disc)
            say(f'{key}: the extraction reads {len(r)} bundle files')
            ex_reads |= r
        bundle = os.path.join(rel, 'bundle')
        bundle_files = set()
        for dp, dns, fns in os.walk(bundle):
            dns[:] = [d for d in dns if d != '__pycache__']
            for f in fns:
                bundle_files.add(os.path.relpath(os.path.join(dp, f), bundle))
        if m.get('source_discs') and any(p.startswith('mods/experimental/motion/v61-models/files/') for p in bundle_files):
            raise SystemExit('delta-model release contains raw v61-models/files; rebuild the release bundle')
        jobs, warn = plan_jobs(recs, bundle_files)
        for w in warn[:20]:
            say('  note:', w)
        if warn:
            raise SystemExit(f'{len(warn)} inputs come from nowhere')
        jobs = schedule_deps(jobs, recs[0]['order'], recs[0]['after'])

        # the code (every worker, at its start) and the data files the jobs read
        code = {p for p in bundle_files if p.endswith('.py') or p.startswith('tools/') or p == 'exe-facts.json'}
        files = {p: os.path.join(bundle, p) for p in code}
        for j in jobs:
            for p in j['bundle']:
                files[p] = os.path.join(bundle, p)
        # Extraction inputs are also loaded by the fresh disc writer. Its
        # authored table recipes read data that derive jobs need elsewhere,
        # so those job dependencies alone do not populate the writer's tree.
        ex_data = sorted((set(ex_reads) | writer_inputs(bundle_files, code)) - code)
        if m.get('source_discs'):
            ex_data = sorted(set(ex_data) | {p for p in bundle_files
                             if p.startswith(('content/imports/releases/',
                                              'mods/experimental/batch-import/releases/'))})
        for p in ex_data:
            files[p] = os.path.join(bundle, p)
        rel_files = {'manifest.json', v['patch'], 'dwpatch.py', 'isowriter.py'}
        if os.path.isfile(os.path.join(rel, 'fontcopy.py')):
            rel_files.add('fontcopy.py')
        rel_files |= {b['mapping'] for b in m['bases'].values() if b.get('mapping')}
        for f in sorted(rel_files):
            files[f'.release/{f}'] = os.path.join(rel, f); code.add(f'.release/{f}')
        files['.engine/glue.py'] = os.path.join(HERE, 'glue.py'); code.add('.engine/glue.py')

        stage = os.path.join(work, 'stage')
        index, packs = make_packs(bundle, files, code, stage)
        info = vendor_pyodide(os.path.abspath(a.pyodide), os.path.join(stage, 'pyodide'))
        dirs = sorted({os.path.dirname(p) for p in bundle_files} - {''})
        for j in jobs:
            j['est'] = round(j['seconds'] * NATIVE_TO_BROWSER + 0.5, 1)
            for k in ('writes', 'removes'):
                j.pop(k)
        # the longest path from each job to the end (scheduling priority, the estimate)
        rest = {}
        users = {j['id']: [] for j in jobs}
        for j in jobs:
            for d in j['deps']:
                users[d].append(j['id'])
        by = {j['id']: j for j in jobs}
        for j in reversed(jobs):
            rest[j['id']] = j['est'] + max((rest[u] for u in users[j['id']]), default=0)
        for j in jobs:
            j['prio'] = round(rest[j['id']], 1)
        # paths once, the jobs by index
        allp = set()
        for j in jobs:
            allp |= set(j['tree']) | set(j['bundle']) | set(j['absent']) | set(j['lists']) | set(j['mkdirs'])
        paths = sorted(allp)
        ix = {p: i for i, p in enumerate(paths)}
        for j in jobs:
            for k in ('tree', 'bundle', 'absent', 'mkdirs'):
                j[k] = [ix[p] for p in j[k]]
            j['lists'] = [[ix[d], n] for d, n in sorted(j['lists'].items())]
        steps = [dict(name=s, after=recs[0]['after'][s], units=s in recs[0]['units'],
                      jobs=sum(1 for j in jobs if j['step'] == s)) for s in recs[0]['order']]
        plan = dict(format=1, made=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), root='/horizon',
                    release=dict(title=m['title'], version=m['version'], commit=m['commit'], variant=m['default'],
                                 bases={k: dict(title=b['title'], size=b['size'], sha1=b['sha1'], boot=b['boot'])
                                        for k, b in m['bases'].items()},
                                 outputs=v['outputs'], holes=len(v['holes']),
                                 holes_bytes=sum(h['size'] for h in v['holes'])),
                    pyodide=dict(python=info['python'],
                                 files=[[f, os.path.getsize(os.path.join(stage, 'pyodide', f))]
                                        for f in sorted(os.listdir(os.path.join(stage, 'pyodide')))]),
                    extract=m['extract'], extract_inputs=ex_data, source_discs=m.get('source_discs', []), write_est=WRITE_EST,
                    packs=packs, files=index, dirs=dirs, paths=paths, steps=steps, jobs=jobs,
                    manifest=MANIFEST, out='build/everything')
        text = json.dumps(plan, separators=(',', ':'))
        version = hashlib.sha1(text.encode() + b''.join(p['sha1'].encode() for p in packs)).hexdigest()[:12]
        open(os.path.join(stage, 'plan.json'), 'w').write(text)
        out = os.path.abspath(a.out)
        os.makedirs(out, exist_ok=True)
        dst = os.path.join(out, version)
        if os.path.exists(dst):
            shutil.rmtree(dst)
        shutil.move(stage, dst)
        for old in os.listdir(out):
            if old != version and os.path.isdir(os.path.join(out, old)):
                shutil.rmtree(os.path.join(out, old))
        # version: the engine's (the page's cache key); release_version and release_date: the release's (tools/version.py), the
        # page's footer
        json.dump(dict(version=version, release=m['version'], commit=m['commit'], release_version=m['version'],
                       release_date=m.get('date')), open(os.path.join(out, 'current.json'), 'w'))
        size = lambda d: sum(os.path.getsize(os.path.join(dp, f)) for dp, _, fs in os.walk(d) for f in fs)
        say(f'engine {version}: {len(jobs)} jobs, {len(index)} bundle files in {len(packs)} packs '
            f'({sum(p["size"] for p in packs) / 2**20:.1f} MB; code {packs[0]["size"] / 2**20:.1f} MB), '
            f'pyodide {size(os.path.join(dst, "pyodide")) / 2**20:.1f} MB, plan {len(text) / 2**20:.2f} MB, '
            f'{time.time() - t0:.0f} s -> {dst}')
    finally:
        if not a.keep_work:
            shutil.rmtree(work, ignore_errors=True)


if __name__ == '__main__':
    main()
