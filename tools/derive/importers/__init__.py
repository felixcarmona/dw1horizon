"""Disc import + plain MD3 model provider, in process with the standard library (including Pyodide).

The game directories are explicit extracted inputs, never sibling checkouts.
The vendor directory contains our readers' Python source only.
"""
import contextlib
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys

from .. import runner


def checked(path, expected, size=None):
    data = Path(path).read_bytes()
    actual = hashlib.sha256(data).hexdigest()
    if actual != expected or (size is not None and len(data) != size):
        raise ValueError(f'{path}: SHA-256 {actual}, expected {expected}')
    return data


@contextlib.contextmanager
def source_context(games):
    """Use bundled readers and this player's extracted sources; restore module/environment state."""
    games = Path(games).resolve()
    values = dict(DCB_ROOT=str(games / 'dcb'), DCB_DISC=str(games / 'dcb/disc'),
                  DCB_DRV=str(games / 'dcb/drv'), DW2_ROOT=str(games / 'dw2'),
                  DW2_DISC=str(games / 'dw2/disc'), DW3_ROOT=str(games / 'dw2003'),
                  DW3_DISC=str(games / 'dw2003/disc'))
    env, path = dict(os.environ), sys.path[:]
    packages = ('dcb', 'dw2', 'dw3')
    previous = {n: m for n, m in sys.modules.items() if n.split('.')[0] in packages}
    for name in previous:
        del sys.modules[name]
    try:
        os.environ.update(values)
        sys.path.insert(0, str(Path(__file__).parent / 'vendor'))
        yield
    finally:
        sys.path[:] = path
        os.environ.clear()
        os.environ.update(env)
        for name in list(sys.modules):
            if name.split('.')[0] in packages:
                del sys.modules[name]
        sys.modules.update(previous)


class Provider:
    """One species' sources, verified before applying its delta. Each unit owns its workspace."""

    def __init__(self, games, work, repo=None):
        self.repo = Path(repo or runner.ROOT)
        self.games, self.work = Path(games), Path(work)
        self.base = self.repo / 'content/modeldelta'
        self.models = {r['id']: r for r in json.loads((self.base / 'models.json').read_text())['models']}
        self.sizes = {r['target']: r for r in json.loads((self.base / 'import-sizes.json').read_text())['files']}
        self.source_pins = {s['path']: s['sha256'] for model in self.models.values()
                            for kind in ('mmd', 'tim') for s in model[kind]['sources']}
        self.source_pins.update({r['source']: r['source_sha256'] for r in self.sizes.values()})
        self.batches = {}
        for recipe in json.loads((self.base / 'import-batches.json').read_text())['recipes']:
            for ext in ('MMD', 'TIM'):
                self.batches[f'{recipe["out"]}/{recipe["entry"]["name"]}.{ext}'] = recipe
        self.cache = {}

    def source(self, name):
        if name in self.cache:
            return self.cache[name]
        import mmd
        import sizes
        if name in self.sizes:
            recipe = self.sizes[name]
            data = self.source(recipe['source'])
            if hashlib.sha256(data).hexdigest() != recipe['source_sha256']:
                raise ValueError(f'{name}: size input SHA-256 mismatch')
            model = mmd.MMD.parse(data, recipe['bones'])
            if sizes.rescale(model, recipe['scale']):
                raise ValueError(f'{name}: translation overflow')
            data = model.build()
            if hashlib.sha256(data).hexdigest() != recipe['sha256']:
                raise ValueError(f'{name}: size output SHA-256 mismatch')
            self.cache[name] = data
        elif name == 'build/batch13/Suijinmon.TIM':
            self.cache[name] = self.source('build/meshfix2-out/Suijinmon.TIM')
        elif name in self.batches:
            import import_batch
            recipe = self.batches[name]
            spec = json.loads(checked(self.repo / recipe['spec'], recipe['spec_sha256']))
            out = self.work / recipe['out']
            import_batch.replay_model(recipe['entry'], recipe['level'], spec, str(out), log=lambda *a: None)
            stem = f'{recipe["out"]}/{recipe["entry"]["name"]}'
            made = {f'{stem}.{ext}': (self.work / f'{stem}.{ext}').read_bytes() for ext in ('MMD', 'TIM')}
            if any(p in self.source_pins and hashlib.sha256(b).hexdigest() != self.source_pins[p]
                   for p, b in made.items()):
                # Some older specs predate deterministic mesh ordering. Only
                # use their recorded search winner when it reproduces the pin;
                # otherwise retain the original complete search and its checks.
                import_batch.replay_model(recipe['entry'], recipe['level'], spec, str(out),
                                          log=lambda *a: None, frozen_mesh=False)
                made = {f'{stem}.{ext}': (self.work / f'{stem}.{ext}').read_bytes() for ext in ('MMD', 'TIM')}
            self.cache.update(made)
        else:
            self.partner(name)
        return self.cache[name]

    def partner(self, name):
        import dcb2mmd
        import dw2mmd
        import mmdport
        paths = {'build/dcb/Veemon': 'content/models/dcb-import/veemon.json',
                 'build/dcb/Puppetmon': 'content/models/dcb-import/puppetmon.json',
                 'build/dw2/Kimeramon': 'content/models/dcb-import/kimeramon-dw2.json',
                 'build/models/WarGreymon': 'content/models/mega/wargreymon-dcb.json'}
        key = str(Path(name).with_suffix(''))
        if key not in paths:
            raise ValueError(f'no import recipe for {name}')
        spec = json.loads((self.repo / paths[key]).read_text())
        stem = self.work / key
        stem.parent.mkdir(parents=True, exist_ok=True)
        if 'dw2' in spec:
            model = dw2mmd.load(spec['dw2'], scale=spec.get('scale', 1 / 5.1),
                                height=spec.get('height'), maxp=spec.get('max_palettes', 15), log=lambda *a: None)
            spec['_path'] = str(self.repo / paths[key])
            dw2mmd.apply_spec_edits(model, spec)
            dw2mmd.build_partner(model, spec, str(stem) + '.MMD', str(stem) + '.TIM', str(stem.parent),
                                log=lambda *a: None)
        elif key == 'build/models/WarGreymon':
            modspec = importlib.util.spec_from_file_location('imported_mega', self.repo / 'content/models/mega/make-model.py')
            mega = importlib.util.module_from_spec(modspec)
            modspec.loader.exec_module(mega)
            model = dcb2mmd.load(spec['dcb'], log=lambda *a: None)
            model.anims['wg_gaia'] = mega.gaia(model)
            mega.build(model, spec, str(stem), str(stem.parent))
        else:
            model = dcb2mmd.load(spec['dcb'], log=lambda *a: None)
            if spec.get('meshfix') is not None:
                import meshfix
                meshfix.apply(model, spec['meshfix'], log=lambda *a: None)
            mmdport.build_partner(model, spec, str(stem) + '.MMD', str(stem) + '.TIM', str(stem.parent),
                                 log=lambda *a: None)
        for ext in ('MMD', 'TIM'):
            self.cache[f'{key}.{ext}'] = Path(str(stem) + '.' + ext).read_bytes()

    def model(self, species):
        """Return (MMD, TIM); all sources, deltas and results checked by SHA-256."""
        from tools.models import delta as modeldelta
        result = []
        with source_context(self.games), replay_skeletons():
            for kind in ('mmd', 'tim'):
                recipe = self.models[int(species)][kind]
                sources = []
                for source in recipe['sources']:
                    # Different frozen recipes can produce the same texture.
                    # Reuse bytes already generated from this player's files,
                    # matched by their full content hash, before replaying again.
                    data = next((b for b in self.cache.values()
                                 if len(b) == source['size'] and
                                 hashlib.sha256(b).hexdigest() == source['sha256']), None)
                    if data is None:
                        data = self.source(source['path'])
                    if len(data) != source['size'] or hashlib.sha256(data).hexdigest() != source['sha256']:
                        raise ValueError(f'{species}: {source["path"]}: source SHA-256 mismatch')
                    sources.append(data)
                delta = checked(self.repo / recipe['delta'], recipe['delta_sha256'])
                data = modeldelta.decode(delta, sources)
                if len(data) != recipe['size'] or hashlib.sha256(data).hexdigest() != recipe['sha256']:
                    raise ValueError(f'{species}: {kind}: target SHA-256 mismatch')
                result.append(data)
        return tuple(result)


@contextlib.contextmanager
def replay_skeletons():
    """Only original donors are needed: base_mmd registers the replay's target.

    Full imported DIGI.DAT records (including effect tables) are unrelated to
    conversion. Keep the temporary table scoped to this replay, including on
    failure, so other tools retain their usual complete species table.
    """
    import mmd
    previous = mmd._EXE
    try:
        mmd._EXE = mmd.Exe(include_imports=False)
        yield
    finally:
        mmd._EXE = previous
