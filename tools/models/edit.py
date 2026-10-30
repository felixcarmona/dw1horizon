#!/usr/bin/env python3
"""Edit one imported species model without the motion recipes (developer tool; content/modeldelta/README.md).

The build makes each of the 175 imported models as  importer output (from the Card Battle / World 2 / World 3 discs) + our
plain MD3 delta (content/modeldelta/models.json). This tool rebuilds those importer outputs the way derive's imports
step does (the import Provider, crmath and pysum installed), so an animation can be edited and stored again:

  tools/models/edit.py get ID [OUT]             the species' current model and texture -> OUT/<id>-<name>.MMD/.TIM (default
                                      build/imported-model-edit/edit); prints the tools/animstudio.py line to look at it
  tools/models/edit.py put ID MMD [TIM]         re-encode the delta(s) against the pinned importer output; rewrites
                                      content/modeldelta/deltas/<id>-<name>.*.mdelta, the models.json pins
                                      (delta_sha256, sha256, size) and the species' tools/derive/recipes/species-pins.json
                                      entry (--no-species-pins: leave it to a developer build with --write-locks)
  tools/models/edit.py check [ID ...]           decode and verify every pin (all 175 without IDs); --species-pins also the
                                      provider pins (the 65 field overlays are made again: slower)
  tools/models/edit.py sources OUT [ID ...]     write the importer outputs (the delta sources) at their pinned paths under OUT;
                                      --unchecked after an importer change (no pins, no cache)
  tools/models/edit.py rebase OLD NEW [ID ...]  the importer changed: decode each delta against OLD's sources, re-encode against
                                      NEW's (trees as `sources` writes them), update the source pins, rebased.json and
                                      import-sizes.json. The targets stay byte-identical

DW1 record originals also support get/put/check by ID or name; `--originals check --species-pins`
checks them all using extracted/ (no source-game extraction for native DW1 models).

ID is the species id (183) or its name (Wormmon). The player's source games, extracted as derive extracts them:
  --games DIR           a folder with dcb/ dw2/ dw2003/ (a derive build's source-games)
  --from DIR            a derive build's output: its source-games, and its import-work as a read-only cache (each file
                        used only when its SHA-256 is the pinned one)
  --source-disc G=IMG   extract the disc image (dcb, dw2, dw2003) into build/imported-model-edit/source-games once; that
                        folder is the default afterwards
Our own importer workspace is build/imported-model-edit/import-work/<id> (a cache too). Uses the Python standard library.
"""
import argparse
import contextlib
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(1, str(ROOT / 'tools'))

from tools.derive import crmath, pysum  # noqa: E402
from tools.derive.importers import Provider, source_context  # noqa: E402
from tools.models import delta as modeldelta  # noqa: E402

BASE = ROOT / 'content/modeldelta'
MODELS = BASE / 'models.json'
SIZES = BASE / 'import-sizes.json'
REBASED = BASE / 'rebased.json'
WORK = ROOT / 'build/imported-model-edit'
IMPORTED_MODELS_SCRIPT = ROOT / 'content/models/imports/species.py'


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def load(path):
    return json.loads(path.read_text())


def save(path, data):
    path.write_text(json.dumps(data, indent=2) + '\n')


def rows(manifest, ids=None):
    """models.json rows by id or name, in the manifest's order (all without ids)."""
    if not ids:
        return manifest['models']
    out = []
    for key in ids:
        hit = [r for r in manifest['models'] if str(r['id']) == key or r['name'].lower() == key.lower()]
        if not hit:
            raise SystemExit(f'model edit: no imported model {key} in {MODELS.relative_to(ROOT)}')
        out += hit
    return out


class Sources(Provider):
    """derive's Provider, with read-only caches: a file in a cache folder is used when its SHA-256 is the pinned one.
    unchecked: no caches and no size-pass pins (the importer changed; `sources --unchecked`)."""

    def __init__(self, games, work, caches=(), unchecked=False):
        super().__init__(games, work, ROOT)
        self.caches, self.unchecked = [Path(c) for c in caches], unchecked
        self.known = {}
        for row in load(MODELS)['models']:
            for kind in ('mmd', 'tim'):
                for s in row[kind]['sources']:
                    self.known[s['path']] = s['sha256']
        for r in self.sizes.values():
            self.known.setdefault(r['source'], r['source_sha256'])
            self.known.setdefault(r['target'], r['sha256'])

    def source(self, name):
        if name not in self.cache and not self.unchecked:
            want = self.known.get(name)
            for folder in self.caches:
                p = folder / name
                if want and p.is_file():
                    data = p.read_bytes()
                    if sha256(data) == want:
                        self.cache[name] = data
                        break
        if name not in self.cache and self.unchecked and name in self.sizes:
            import mmd
            import sizes
            recipe = self.sizes[name]
            model = mmd.MMD.parse(self.source(recipe['source']), recipe['bones'])
            if sizes.rescale(model, recipe['scale']):
                raise ValueError(f'{name}: translation overflow')
            self.cache[name] = model.build()
        return super().source(name)

    def keep(self):
        """Store the pinned files made in memory (the size pass) in our workspace, for the next call."""
        for name, data in self.cache.items():
            p = self.work / name
            if not p.is_file() and self.known.get(name) == sha256(data):
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_bytes(data)


@contextlib.contextmanager
def importing(games):
    """derive's arithmetic (crmath, pysum) and the bundled readers on the player's extracted source games; the
    importers' chatter kept and shown only when something fails."""
    log = io.StringIO()
    crmath.install()
    pysum.install()
    try:
        with source_context(games), contextlib.redirect_stdout(log):
            yield
    except Exception:
        sys.stderr.write(log.getvalue()[-4000:])
        raise
    finally:
        crmath.uninstall()
        crmath.clear()
        pysum.uninstall()


def games_dir(a):
    if a.source_disc:
        from tools.derive.importers.discs import extract_to
        out = WORK / 'source-games'
        for spec in a.source_disc:
            game, image = spec.split('=', 1)
            if game not in ('dcb', 'dw2', 'dw2003'):
                raise SystemExit(f'model edit: unknown source game {game} (dcb, dw2, dw2003)')
            n = extract_to(game, image, out)
            print(f'{game}: {n} files extracted into {out.relative_to(ROOT)}', file=sys.stderr)
    games = Path(a.games) if a.games else Path(a.from_dir) / 'source-games' if a.from_dir else WORK / 'source-games'
    missing = [g for g in ('dcb', 'dw2', 'dw2003') if not (games / g / 'disc' / 'SYSTEM.CNF').is_file()]
    if missing:
        raise SystemExit(f'model edit: {games}: no extracted {", ".join(missing)}; pass --from DERIVE_OUT, --games DIR or '
                         '--source-disc dcb=IMAGE --source-disc dw2=IMAGE --source-disc dw2003=IMAGE')
    return games.resolve()


def provider(a, games, species, unchecked=False):
    work = WORK / 'import-work' / str(species)
    caches = [work] + ([Path(a.from_dir) / 'import-work' / str(species)] if a.from_dir else [])
    return Sources(games, work, caches, unchecked)


def sources_of(prov, record):
    """The delta's sources, each checked against its pin (a delta made against other bytes would apply to nothing)."""
    out = []
    for s in record['sources']:
        data = prov.source(s['path'])
        if len(data) != s['size'] or sha256(data) != s['sha256']:
            raise SystemExit(f'model edit: {s["path"]}: the importer made {sha256(data)} ({len(data)} B), pinned '
                             f'{s["sha256"]} ({s["size"]} B): the importer changed (see `rebase`) or crmath is missing')
        out.append(data)
    return out


def decoded(record, srcs):
    delta = (ROOT / record['delta']).read_bytes()
    if sha256(delta) != record['delta_sha256']:
        raise SystemExit(f'model edit: {record["delta"]}: SHA-256 {sha256(delta)}, pinned {record["delta_sha256"]}')
    data = modeldelta.decode(delta, srcs)
    if len(data) != record['size'] or sha256(data) != record['sha256']:
        raise SystemExit(f'model edit: {record["delta"]}: decodes to {sha256(data)}, pinned {record["sha256"]}')
    return data


def build(a, row):
    """(MMD, TIM, {kind: sources}) of a models.json row, every pin checked."""
    prov = provider(a, a.games_dir, row['id'])
    with importing(a.games_dir):
        srcs = {kind: sources_of(prov, row[kind]) for kind in ('mmd', 'tim')}
    prov.keep()
    return decoded(row['mmd'], srcs['mmd']), decoded(row['tim'], srcs['tim']), srcs


# ------------------------------------------------------------------ species-pins.json (the provider's SHA-1 pins)
def import_records():
    return json.loads((IMPORTED_MODELS_SCRIPT.parent / 'models.json').read_text())


def provider_pin(species, model, tim):
    """[SHA-1 of the model the species file names, SHA-1 of its texture], as derive's species step pins them: the base
    model, or for the 65 field overlays the overlay made on top of it (tools/models/field_animations/*.py, in a temporary folder)."""
    sha1 = lambda b: hashlib.sha1(b).hexdigest()  # noqa: E731
    record = import_records()[str(species)]
    if not record.get('field_overlay'):
        return [sha1(model), sha1(tim)]
    with tempfile.TemporaryDirectory(prefix='imported_model_edit-') as tmp:
        base = Path(tmp) / 'imported-models'
        base.mkdir()
        (base / f'{species}.MMD').write_bytes(model)
        (base / f'{species}.TIM').write_bytes(tim)
        spec = importlib.util.spec_from_file_location('imported_species_edit', IMPORTED_MODELS_SCRIPT)
        imported_models = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(imported_models)
        imported_models.BASE_MODELS = str(base)
        saved = set(sys.modules)
        crmath.install()
        pysum.install()
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                _, s = imported_models.species_file(str(Path(tmp) / 'species'), str(species), generate=True)
            return [sha1(Path(s['model']['file']).read_bytes()), sha1(Path(s['texture']['file']).read_bytes())]
        finally:
            crmath.uninstall()
            crmath.clear()
            pysum.uninstall()
            for n in [n for n in sys.modules if n not in saved and n.split('.')[0] in ('species', 'mmd')]:
                del sys.modules[n]


def species_pins():
    import tools.derive.steps.species as step
    return step, json.loads((ROOT / step.PINS).read_text())


# ------------------------------------------------------------------ commands
def cmd_get(a):
    row, = rows(load(MODELS), [a.id])
    model, tim, _ = build(a, row)
    out = Path(a.out or WORK / 'edit')
    out.mkdir(parents=True, exist_ok=True)
    stem = out / f'{row["id"]}-{row["name"]}'
    Path(f'{stem}.MMD').write_bytes(model)
    Path(f'{stem}.TIM').write_bytes(tim)
    print(f'{stem}.MMD  {len(model)} B  sha256 {row["mmd"]["sha256"]}')
    print(f'{stem}.TIM  {len(tim)} B  sha256 {row["tim"]["sha256"]}')
    print(f'look:  tools/animstudio.py sheet /tmp/{row["id"]}.png {stem}.MMD:{row["id"]}:{stem}.TIM --slot 2')
    overlay = import_records()[str(row['id'])].get('field_overlay')
    if overlay:
        print(f'note: in game its field slots come from the overlay {overlay} (tools/derive/steps/overlays.py), made '
              'on top of this model at build')
    print(f'store: tools/models/edit.py put {row["id"]} {stem}.MMD [{stem}.TIM]')


def cmd_put(a):
    manifest = load(MODELS)
    row, = rows(manifest, [a.id])
    files = {'mmd': Path(a.mmd).read_bytes()}
    if a.tim:
        files['tim'] = Path(a.tim).read_bytes()
    changed = {k: d for k, d in files.items() if a.force or sha256(d) != row[k]['sha256']}
    for kind in files.keys() - changed.keys():
        print(f'{row[kind]["delta"]}: same target, delta kept')
    if not changed:
        return
    prov = provider(a, a.games_dir, row['id'])
    with importing(a.games_dir):
        srcs = {kind: sources_of(prov, row[kind]) for kind in ('mmd', 'tim')}
    prov.keep()
    tim = files.get('tim') or decoded(row['tim'], srcs['tim'])
    # Field overlays can refuse an edited model (no reviewed acting profile). Validate them before
    # replacing any delta or manifest pin, so a rejected put leaves the current models usable.
    step, pins = species_pins()
    new = None if a.no_species_pins else provider_pin(row['id'], files['mmd'], tim)
    pinned = {k: row[k]['sha256'] for k in changed}
    for kind, data in changed.items():
        record = row[kind]
        delta = modeldelta.encode(data, srcs[kind])
        if modeldelta.decode(delta, srcs[kind]) != data:
            raise SystemExit(f'model edit: {record["delta"]}: the new delta does not decode to the file')
        old = (ROOT / record['delta']).read_bytes()
        (ROOT / record['delta']).write_bytes(delta)
        record.update(delta_sha256=sha256(delta), sha256=sha256(data), size=len(data))
        same = 'byte-identical' if delta == old else f'{len(old)} -> {len(delta)} B'
        print(f'{record["delta"]}: {same}; target sha256 {record["sha256"]}')
    save(MODELS, manifest)
    print(f'{MODELS.relative_to(ROOT)}: pins of {row["id"]} {row["name"]} updated')
    if a.no_species_pins:
        print(f'left: {step.PINS} ("{row["id"]}") is rewritten by a developer build (tools/build-full.sh, '
              'derive --write-locks) or `python3 -m tools.derive.steps.species pin OUT` after a derive imports run')
    else:
        if pins['imports'].get(str(row['id'])) != new:
            pins['imports'][str(row['id'])] = new
            step._write_pins(pins)
            print(f'{step.PINS}: imports {row["id"]} -> {new}')
        else:
            print(f'{step.PINS}: imports {row["id"]} unchanged')
    if any(sha256(d) != pinned[k] for k, d in changed.items()):
        print('also: content/modeldelta/verification.json records the last full verification (not rewritten)')


def cmd_check(a):
    selected = rows(load(MODELS), a.ids)
    pins = species_pins()[1]['imports'] if a.species_pins else None
    bad = 0
    for row in selected:
        try:
            model, tim, _ = build(a, row)
            note = ''
            if pins is not None:
                got = provider_pin(row['id'], model, tim)
                if got != pins.get(str(row['id'])):
                    raise SystemExit(f'species-pins.json has {pins.get(str(row["id"]))}, made {got}')
                note = ', provider pins'
            print(f'{row["id"]} {row["name"]}: sources, deltas, MMD and TIM verified{note}', flush=True)
        except (SystemExit, ValueError) as e:
            bad += 1
            print(f'{row["id"]} {row["name"]}: FAILED: {e}', flush=True)
    print(f'{len(selected) - bad}/{len(selected)} verified')
    return 1 if bad else 0


def cmd_sources(a):
    out = Path(a.out)
    for row in rows(load(MODELS), a.ids):
        prov = provider(a, a.games_dir, row['id'], unchecked=a.unchecked)
        if a.unchecked:     # a fresh workspace: never the files the previous importer wrote
            prov.work = Path(tempfile.mkdtemp(prefix=f'imported_model_edit-{row["id"]}-'))
        names = [s['path'] for kind in ('mmd', 'tim') for s in row[kind]['sources']]
        names += [prov.sizes[n]['source'] for n in names if n in prov.sizes]   # the size pass's base: rebase pins it
        with importing(a.games_dir):
            for name in names:
                data = prov.source(name)
                if not a.unchecked and sha256(data) != prov.known[name]:
                    raise SystemExit(f'model edit: {name}: the importer made {sha256(data)}, pinned {prov.known[name]}; '
                                     'after an importer change use --unchecked')
                p = out / name
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_bytes(data)
                if sha256(data) != prov.known[name]:
                    print(f'{row["id"]} {name}: differs from its pin')
        if a.unchecked:
            shutil.rmtree(prov.work)
        else:
            prov.keep()
        print(f'{row["id"]} {row["name"]}: sources written', flush=True)


def cmd_rebase(a):
    old, new = Path(a.old), Path(a.new)
    manifest, rebased, sizes = load(MODELS), load(REBASED), load(SIZES)
    done = []
    for row in rows(manifest, a.ids):
        for kind in ('mmd', 'tim'):
            record = row[kind]
            before = [(old / s['path']).read_bytes() for s in record['sources']]
            for s, data in zip(record['sources'], before):
                if sha256(data) != s['sha256']:
                    raise SystemExit(f'model edit: {old / s["path"]}: not the pinned source of {record["delta"]}')
            after = [(new / s['path']).read_bytes() for s in record['sources']]
            if after == before:
                continue
            target = decoded(record, before)
            delta = modeldelta.encode(target, after)
            if modeldelta.decode(delta, after) != target:
                raise SystemExit(f'model edit: {record["delta"]}: rebase failed')
            previous = len((ROOT / record['delta']).read_bytes())
            (ROOT / record['delta']).write_bytes(delta)
            record['delta_sha256'] = sha256(delta)
            for s, data in zip(record['sources'], after):
                s.update(sha256=sha256(data), size=len(data))
            rebased['models'].append(dict(id=row['id'], name=row['name'], kind=kind.upper(),
                                          previous_bytes=previous, bytes=len(delta)))
            done.append(f'{record["delta"]}: {previous} -> {len(delta)} B')
    for r in sizes['files']:          # the size pass's pins follow its new base and output (derive checks both)
        for path, key in ((r['source'], 'source_sha256'), (r['target'], 'sha256')):
            p = new / path
            if p.is_file() and sha256(p.read_bytes()) != r[key]:
                r[key] = sha256(p.read_bytes())
                done.append(f'{SIZES.relative_to(ROOT)}: {path} {key}')
    if not done:
        print('nothing differs between the two source trees')
        return
    save(MODELS, manifest)
    save(REBASED, rebased)
    save(SIZES, sizes)
    print('\n'.join(done))
    print('the targets are unchanged, so tools/derive/recipes/species-pins.json is too; verify with '
          '`tools/models/edit.py check` on the new importer')


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--originals', action='store_true', help='check all DW1 record originals (IDs/names also select them automatically)')
    p.add_argument('--games', help='extracted source games (dcb/ dw2/ dw2003/)')
    p.add_argument('--from', dest='from_dir', help='a derive build output (source-games, import-work as a cache)')
    p.add_argument('--source-disc', action='append', metavar='GAME=IMAGE')
    sub = p.add_subparsers(dest='command', required=True)
    g = sub.add_parser('get')
    g.add_argument('id')
    g.add_argument('out', nargs='?')
    u = sub.add_parser('put')
    u.add_argument('id')
    u.add_argument('mmd')
    u.add_argument('tim', nargs='?')
    u.add_argument('--force', action='store_true', help='re-encode even when the target is the pinned one')
    u.add_argument('--no-species-pins', action='store_true')
    c = sub.add_parser('check')
    c.add_argument('ids', nargs='*')
    c.add_argument('--species-pins', action='store_true')
    s = sub.add_parser('sources')
    s.add_argument('out')
    s.add_argument('ids', nargs='*')
    s.add_argument('--unchecked', action='store_true')
    r = sub.add_parser('rebase')
    r.add_argument('old')
    r.add_argument('new')
    r.add_argument('ids', nargs='*')
    a = p.parse_args()
    from tools import recordoriginals
    original_rows = recordoriginals.records()
    original_keys = {str(r['id']) for r in original_rows} | {r['name'].lower() for r in original_rows}
    selected_keys = [a.id] if hasattr(a, 'id') else getattr(a, 'ids', [])
    if a.originals or any(key.lower() in original_keys for key in selected_keys):
        from tools import recordedit
        if a.command == 'check' and selected_keys and not a.originals:
            import copy
            original_args = copy.copy(a)
            original_args.ids = [key for key in selected_keys if key.lower() in original_keys]
            result = recordedit.run(original_args)
            a.ids = [key for key in selected_keys if key.lower() not in original_keys]
            if a.ids:
                a.games_dir = games_dir(a)
                result = cmd_check(a) or result
            return result
        return recordedit.run(a)
    if a.command != 'rebase':
        a.games_dir = games_dir(a)
    return {'get': cmd_get, 'put': cmd_put, 'check': cmd_check, 'sources': cmd_sources,
            'rebase': cmd_rebase}[a.command](a) or 0


if __name__ == '__main__':
    sys.exit(main())
