#!/usr/bin/env python3
"""Audit source-game import origins in disposable copies, never in the real build/.

The copies start with an empty build. Only the model builders run: contact sheets
are not inputs to a model. Logs and generated specs remain in the workspace.
This is a developer audit, not the browser importer.
"""
import argparse
import concurrent.futures
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = 'content/modeldelta/import-origins.json'


def snapshot(dst):
    dst.mkdir(parents=True, exist_ok=False)
    for folder in ('tools', 'content', 'docs/data'):
        shutil.copytree(ROOT / folder, dst / folder,
                        ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    (dst / 'extracted').symlink_to(ROOT / 'extracted', target_is_directory=True)
    (dst / 'build').mkdir()


def batch_job(args):
    workspace, python, recipe, names = args
    dst = workspace / recipe.stem
    snapshot(dst)
    # Historical sparse records materialize with the new id as their bonus parent.
    # Disable ONLY that metadata check in this disposable copy, never in tools/.
    p = dst / 'tools/species.py'
    source = p.read_text()
    check = "if ((s.get('evolution') or {}).get('requirements') or {}).get('digimon') == s['id']:"
    assert source.count(check) == 1
    p.write_text(source.replace(check, 'if False:  # historical import metadata (audit only)'))
    bootstrap = """import sys
sys.path.insert(0, 'tools')
import import_batch as b
b.verify = b.verify_dw1 = lambda *a, **kw: None
# fitfix.py run starts with the first budget step, then the fit ladder.
if sys.argv[2].endswith('/fit-2.json'):
    del b.BUDGET_STEPS[1:]
sys.argv = ['tools/import_batch.py', *sys.argv[1:]]
b.main()
"""
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1')
    with (dst / 'import.log').open('w') as log:
        r = subprocess.run([python, '-c', bootstrap, 'run', str(recipe.relative_to(ROOT)),
                            '--only', *sorted(names)], cwd=dst, env=env,
                           stdout=log, stderr=subprocess.STDOUT)
    return recipe.stem, r.returncode


def audit(workspace, python, only, jobs):
    workspace = workspace.resolve()
    # A fresh directory prevents counting old output as a successful reproduction.
    if workspace.exists():
        raise SystemExit(f'workspace must not exist: {workspace}')
    if workspace == ROOT or ROOT in workspace.parents:
        raise SystemExit('workspace must be outside the repository')
    workspace.mkdir(parents=True)
    files = json.loads((ROOT / MANIFEST).read_text())['files']
    tasks, owners = [], {}
    for recipe in sorted((ROOT / 'content/imports/lists').glob('*.json')):
        spec = json.loads(recipe.read_text())
        if 'digimon' not in spec or (only and recipe.stem not in only):
            continue
        out = spec.get('out', 'build/batch')
        names = {Path(f['path']).stem for f in files if str(Path(f['path']).parent) == out}
        names &= {e['name'] for e in spec['digimon']}
        if not names:
            continue
        tasks.append((workspace, python, recipe, names))
        for name in names:
            for ext in ('MMD', 'TIM'):
                owners[f'{out}/{name}.{ext}'] = recipe.stem
    unknown = set(only or []) - {task[2].stem for task in tasks}
    if not tasks or unknown:
        raise SystemExit('no origins for batch selection: ' + ', '.join(sorted(unknown or set(only or []))))
    with concurrent.futures.ThreadPoolExecutor(max_workers=jobs) as pool:
        futures = [pool.submit(batch_job, task) for task in tasks]
        for future in concurrent.futures.as_completed(futures):
            name, code = future.result()
            print(f'{name}: exit {code}', flush=True)
    report = []
    for f in files:
        owner = owners.get(f['path'])
        if owner is None:
            continue
        path = workspace / owner / f['path']
        sha = hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None
        report.append(dict(f, recipe=owner, actual=sha,
                           status='equal' if sha == f['sha'] else 'different' if sha else 'missing'))
    (workspace / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
    counts = {s: sum(f['status'] == s for f in report) for s in ('equal', 'different', 'missing')}
    print(json.dumps(counts), flush=True)
    return counts


def rebuild_sizes(sources, out):
    """Replay the frozen size pass; verify both sides, independent of current species metadata."""
    sources, out = sources.resolve(), out.resolve()
    if out.exists():
        raise SystemExit(f'output must not exist: {out}')
    if out == ROOT or ROOT in out.parents:
        raise SystemExit('size audit output must be outside the repository')
    sys.path.insert(0, str(ROOT / 'tools'))
    import mmd
    import sizes
    recipes = json.loads((ROOT / 'content/modeldelta/import-sizes.json').read_text())['files']
    report = []
    for recipe in recipes:
        path = sources / recipe['source']
        data = path.read_bytes()
        sha = hashlib.sha256(data).hexdigest()
        if sha != recipe['source_sha256']:
            raise ValueError(f'{path}: source sha256 {sha}, expected {recipe["source_sha256"]}')
        model = mmd.MMD.parse(data, recipe['bones'])
        if sizes.rescale(model, recipe['scale']):
            raise ValueError(f'{path}: translation overflow')
        data = model.build()
        sha = hashlib.sha256(data).hexdigest()
        if sha != recipe['sha256']:
            raise ValueError(f'{recipe["target"]}: target sha256 {sha}, expected {recipe["sha256"]}')
        target = out / recipe['target']
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        report.append(dict(target=recipe['target'], sha256=sha))
    (out / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
    print(f'{len(report)}/{len(recipes)} size outputs byte-exact')


def partners(workspace, python):
    workspace = workspace.resolve()
    if workspace == ROOT or ROOT in workspace.parents:
        raise SystemExit('workspace must be outside the repository')
    snapshot(workspace)
    commands = json.loads((ROOT / 'content/modeldelta/import-partners.json').read_text())['commands']
    for i, command in enumerate(commands):
        with (workspace / f'partner-{i}.log').open('w') as log:
            result = subprocess.run([python, *command], cwd=workspace,
                                    env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1'),
                                    stdout=log, stderr=subprocess.STDOUT)
        if result.returncode:
            raise SystemExit(f'{command[0]}: exit {result.returncode}; see partner-{i}.log')
    origins = json.loads((ROOT / MANIFEST).read_text())['files']
    report = []
    for recipe in origins:
        if str(Path(recipe['path']).parent) not in ('build/dcb', 'build/dw2', 'build/models'):
            continue
        path = workspace / recipe['path']
        sha = hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None
        report.append(dict(recipe, actual=sha, status='equal' if sha == recipe['sha'] else 'different'))
    (workspace / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
    equal = sum(r['status'] == 'equal' for r in report)
    print(f'{equal}/{len(report)} partner origins byte-exact')
    return equal == len(report)


def frozen(workspace, python, only, jobs):
    """Replay committed final specs, avoiding changes to the budget-selection ladder."""
    workspace = workspace.resolve()
    if workspace == ROOT or ROOT in workspace.parents:
        raise SystemExit('workspace must be outside the repository')
    snapshot(workspace)
    recipes = json.loads((ROOT / 'content/modeldelta/import-batches.json').read_text())['recipes']
    recipes = [r for r in recipes if not only or r['entry']['name'] in only]
    unknown = set(only or []) - {r['entry']['name'] for r in recipes}
    if not recipes or unknown:
        raise SystemExit('no origins for species selection: ' + ', '.join(sorted(unknown or set(only or []))))
    bootstrap = """import json, sys, hashlib
from pathlib import Path
sys.path.insert(0, 'tools')
import import_batch as b
r = json.loads(sys.argv[1])
data = Path(r['spec']).read_bytes()
if hashlib.sha256(data).hexdigest() != r['spec_sha256']:
    raise ValueError('frozen spec sha256 mismatch: ' + r['spec'])
b.replay_model(r['entry'], r['level'], json.loads(data), r['out'])
"""
    def job(recipe):
        name = recipe['entry']['name']
        logpath = workspace / 'logs' / (recipe['out'].replace('/', '-') + '-' + name + '.log')
        logpath.parent.mkdir(exist_ok=True)
        with logpath.open('w') as log:
            result = subprocess.run([python, '-c', bootstrap, json.dumps(recipe)], cwd=workspace,
                                    env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1'),
                                    stdout=log, stderr=subprocess.STDOUT)
        return recipe['out'] + '/' + name, result.returncode
    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=jobs) as pool:
        for future in concurrent.futures.as_completed([pool.submit(job, r) for r in recipes]):
            name, code = future.result()
            results.append(dict(model=name, exit=code))
            print(f'{name}: exit {code}', flush=True)
            (workspace / 'jobs.json').write_text(json.dumps(results, indent=2) + '\n')
    origins = json.loads((ROOT / MANIFEST).read_text())['files']
    report = []
    selected = {f'{r["out"]}/{r["entry"]["name"]}.{ext}' for r in recipes for ext in ('MMD', 'TIM')}
    for recipe in origins:
        if recipe['path'] not in selected:
            continue
        path = workspace / recipe['path']
        sha = hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None
        report.append(dict(recipe, actual=sha, status='equal' if sha == recipe['sha'] else 'different' if sha else 'missing'))
    (workspace / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
    print(f'{sum(r["status"] == "equal" for r in report)}/{len(report)} present origins byte-exact')
    return all(r['exit'] == 0 for r in results) and all(r['status'] == 'equal' for r in report)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    size = sub.add_parser('sizes', help='verify the frozen size pass from explicitly supplied base models')
    size.add_argument('--sources', type=Path, required=True)
    size.add_argument('--out', type=Path, required=True)
    partner = sub.add_parser('partners', help='replay the four early partner imports in a fresh copy')
    partner.add_argument('workspace', type=Path)
    partner.add_argument('--python', default=sys.executable)
    replay = sub.add_parser('frozen', help='replay committed final import specs without replanning')
    replay.add_argument('workspace', type=Path)
    replay.add_argument('--python', default=sys.executable)
    replay.add_argument('--only', nargs='+')
    replay.add_argument('--jobs', type=int, default=4)
    p = sub.add_parser('batches', help='build batch origins in fresh disposable copies')
    p.add_argument('workspace', type=Path)
    p.add_argument('--python', default=sys.executable)
    p.add_argument('--only', nargs='+')
    p.add_argument('--jobs', type=int, default=4)
    a = parser.parse_args()
    if a.command == 'sizes':
        rebuild_sizes(a.sources, a.out)
        return 0
    if a.command == 'partners':
        return int(not partners(a.workspace, a.python))
    if a.command == 'frozen':
        return int(not frozen(a.workspace, a.python, a.only, a.jobs))
    counts = audit(a.workspace, a.python, a.only, a.jobs)
    return int(bool(counts['missing'] or counts['different']))


if __name__ == '__main__':
    sys.exit(main())
