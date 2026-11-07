#!/usr/bin/env python3
"""Imports of another release of a source disc: the same species made from that release's own models (developer tool).

The import recipes were made from one release of each source game. Digimon World 3 (USA) has other models than the
PAL Digimon World 2003 for some species (other meshes, other animation keys, tools/dw3release.py). Its imports come out
otherwise, so they get pins of their own and our edits carried onto them, with nothing of the PAL disc stored:

  content/modeldelta/variants/<release>.json    for the release (today dw3-us):
      sources      {importer output path: SHA-256} of the outputs that differ on this release (frozen recipes)
      sizes        {size-pass target: {source_sha256, sha256}}
      models       {species id: {"mmd": {sources, delta, delta_sha256, sha256, size}, "from": ...}}: the record that
                   replaces models.json's; "from" names the reference record it was carried from (its target SHA-256)
                   and what was carried (tools/models/carry.py's report, the add bytes check below)
      reviewed_as  {SHA-256 of an overlay input made here: SHA-256 of the reviewed input it stands for}
                   (tools/models/field_animations/reviewed.py: the overlays run with their reviewed parameters)
  content/modeldelta/deltas/<release>/<id>-<name>.MMD.mdelta   our edit, carried, against this release's import
  tools/derive/recipes/species-pins.json "imports@<release>"   the species provider's pins of those species

  variants.py make RELEASE --games DIR --reference-games DIR
      DIR: source-games folders (a derive build's) with the release's World 3 and with the reference one (PAL); the
      other two games may be the same. Rewrites the three files above for every species whose import differs.
  variants.py check RELEASE --games DIR
      rebuilds every variant species from DIR and checks every pin (sources, delta, target, species provider)

Each carried delta is checked before it is written: decoding it gives the carried model, and no 8-byte window of what
it adds is found in the reference release's import unless it is in this release's import too or in our reference
delta's own additions (the add bytes are our edits, never the other release's model data). After any edit of a
species listed here (tools/models/edit.py put), run `make` again: the test test_model_variants fails until then.
"""
import argparse
import contextlib
import hashlib
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import zlib

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(1, str(ROOT / 'tools'))

from tools.derive.importers import VARIANTS, source_variant  # noqa: E402
from tools.models import carry as carrying  # noqa: E402
from tools.models import delta as modeldelta  # noqa: E402
from tools.models import edit  # noqa: E402

MODELS = ROOT / 'content/modeldelta/models.json'
BATCHES = ROOT / 'content/modeldelta/import-batches.json'
WINDOW = 8


def sha256(b):
    return hashlib.sha256(b).hexdigest()


def variant_path(release):
    return ROOT / VARIANTS / f'{release}.json'


class Unpinned(edit.Sources):
    """The importer outputs of a release with no pins yet (frozen recipes, no reference pins, no search)."""

    def __init__(self, games, work):
        super().__init__(games, work, (), unchecked=True)
        self.source_pins = {}


def adds(delta):
    """The bytes an MD3 delta adds (its literal part), as one string."""
    n, pos = modeldelta._rv(delta, 5)
    for _ in range(n):
        _, pos = modeldelta._rv(delta, pos)
    _, pos = modeldelta._rv(delta, pos)
    body = zlib.decompress(delta[pos + 32:])
    count, p = modeldelta._rv(body, 0)
    size, p = modeldelta._rv(body, p)
    return bytes(body[p + size:])


def foreign_windows(new_adds, own_source, other_source, our_adds):
    """8-byte windows of the carried delta's additions found in the reference release's import and nowhere ours."""
    out = 0
    for k in range(len(new_adds) - WINDOW + 1):
        w = new_adds[k:k + WINDOW]
        if w in other_source and w not in own_source and w not in our_adds:
            out += 1
    return out


def candidates(release):
    """Species ids whose import reads a model this release has its own file of."""
    sys.path.insert(0, str(ROOT / 'tools'))
    import dw3release
    rel = release.split('-', 1)[1]
    own = set(dw3release.release_list(rel).get('own', {}))
    paths = set()
    for r in json.loads(BATCHES.read_text())['recipes']:
        e = r['entry']
        if e.get('game') == 'dw3' and e.get('model') in own:
            paths |= {f'{r["out"]}/{e["name"]}.{x}' for x in ('MMD', 'TIM')}
    sizes = {r['target']: r['source'] for r in edit.load(edit.SIZES)['files']}
    out = []
    for row in json.loads(MODELS.read_text())['models']:
        srcs = [s['path'] for k in ('mmd', 'tim') for s in row[k]['sources']]
        if any(p in paths or sizes.get(p) in paths for p in srcs):
            out.append(row['id'])
    return out


def nbones(species):
    import mmd
    return mmd.exe().bone_count[species]


def cmd_make(a):
    release = a.release
    games, ref_games = Path(a.games).resolve(), Path(a.reference_games).resolve()
    if source_variant(ref_games) is not None:
        raise SystemExit('variants: --reference-games must hold the reference release (PAL World 2003)')
    path = variant_path(release)
    if path.exists():
        path.unlink()                                  # (made again from nothing: no pin of ours is read back)
    import tools.models.field_animations.reviewed as reviewed
    reviewed._table = None
    record = dict(variant=release, note='tools/models/variants.py make: do not edit by hand', sources={}, sizes={},
                  models={}, reviewed_as={})
    rows = {r['id']: r for r in json.loads(MODELS.read_text())['models']}
    deltas = ROOT / 'content/modeldelta/deltas' / release
    deltas.mkdir(parents=True, exist_ok=True)
    for f in deltas.glob('*.mdelta'):
        f.unlink()
    pins = {}
    work = Path(tempfile.mkdtemp(prefix='model-variants-'))
    for sid in candidates(release):
        row = rows[sid]
        theirs = Unpinned(games, work / 'release' / str(sid))
        ours = edit.Sources(ref_games, work / 'reference' / str(sid))
        with edit.importing(games):
            other = {k: [theirs.source(s['path']) for s in row[k]['sources']] for k in ('mmd', 'tim')}
            names = [s['path'] for k in ('mmd', 'tim') for s in row[k]['sources']]
            extra = {n: theirs.source(theirs.sizes[n]['source']) for n in names if n in theirs.sizes}
        with edit.importing(ref_games):
            ref = {k: edit.sources_of(ours, row[k]) for k in ('mmd', 'tim')}
        if other == ref:
            print(f'{sid} {row["name"]}: the same import from this release')
            continue
        if other['tim'] != ref['tim']:
            raise SystemExit(f'{sid} {row["name"]}: the texture differs on this release: not supported by carry.py')
        for k in ('mmd', 'tim'):
            for s, data in zip(row[k]['sources'], other[k]):
                if sha256(data) != s['sha256']:
                    record['sources'][s['path']] = sha256(data)
        for n, base in extra.items():
            r = theirs.sizes[n]
            record['sizes'][n] = dict(source_sha256=sha256(base), sha256=sha256(other['mmd'][names.index(n)]))
            record['sources'][r['source']] = sha256(base)
        target = edit.decoded(row['mmd'], ref['mmd'])
        if len(ref['mmd']) != 1:
            raise SystemExit(f'{sid}: a delta over several sources is not supported by carry.py')
        log = []
        authored = ROOT / 'content/models/authoring/native-polish' / f'{sid}.json'
        profile = json.loads(authored.read_text()) if authored.is_file() else {}
        if profile.get('preceding_delta'):
            # Reconstruct the accepted pre-polish edit on this release first.
            # Resized vertices cannot be matched against a different mesh by
            # coordinate alone; solve its own anatomy and resize its own mesh.
            from tools.models.field_animations import native_polish
            preceding = edit.decoded(profile['preceding_delta'], ref['mmd'])
            carrying.selftest(ref['mmd'][0], preceding, nbones(sid))
            carried_base, report = carrying.carry(ref['mmd'][0], preceding, other['mmd'][0], nbones(sid), log=log.append)
            carried, proof = native_polish.build(carried_base, profile)
            refinement = ROOT / 'content/models/authoring/gait-refinement' / f'{sid}.json'
            if refinement.is_file():
                carried, refinement_proof = native_polish.build(carried, json.loads(refinement.read_text()))
                report['gait_refinement'] = refinement_proof
            report['authored_native_polish'] = dict(recipe=str(authored.relative_to(ROOT)),
                                                    input_sha256=sha256(carried_base), output_sha256=sha256(carried))
        else:
            carrying.selftest(ref['mmd'][0], target, nbones(sid))
            carried, report = carrying.carry(ref['mmd'][0], target, other['mmd'][0], nbones(sid), log=log.append)
        delta = modeldelta.encode(carried, other['mmd'])
        if modeldelta.decode(delta, other['mmd']) != carried:
            raise SystemExit(f'{sid}: the carried delta does not decode to the carried model')
        ref_delta = (ROOT / row['mmd']['delta']).read_bytes()
        foreign = foreign_windows(adds(delta), other['mmd'][0], ref['mmd'][0], adds(ref_delta))
        if foreign:
            raise SystemExit(f'{sid} {row["name"]}: {foreign} windows of the carried delta are the reference '
                             'release\'s model data: refused')
        name = f'{sid}-{row["name"]}.MMD.mdelta'
        (deltas / name).write_bytes(delta)
        mmd_record = dict(sources=[dict(path=s['path'], sha256=sha256(d), size=len(d))
                                   for s, d in zip(row['mmd']['sources'], other['mmd'])],
                          delta=f'content/modeldelta/deltas/{release}/{name}', delta_sha256=sha256(delta),
                          sha256=sha256(carried), size=len(carried))
        record['models'][str(sid)] = {'mmd': mmd_record, 'from': dict(
            sha256=row['mmd']['sha256'], delta_sha256=row['mmd']['delta_sha256'],
            add_bytes=[len(adds(ref_delta)), len(adds(delta))], foreign_windows=foreign,
            **{k: v for k, v in report.items() if v})}
        print(f'{sid} {row["name"]}: {len(carried)} B (reference {len(target)} B), delta {len(delta)} B; '
              + '; '.join(f'{k} {v}' for k, v in report.items() if v) + ''.join('\n' + x for x in log))
        pins[sid] = (carried, edit.decoded(row['tim'], ref['tim']), target)
    # each overlay's input made from this release's model stands for the reviewed one made from the reference's (the
    # input is the species file's model: slot aliases applied); after a base generator (gaits before chibi) too
    chibi_rows = json.loads((ROOT / 'content/models/imports/chibi.json').read_text())
    records = edit.import_records()
    for sid, (carried, tim, target) in pins.items():
        if not records[str(sid)].get('field_overlay'):
            continue
        mine, theirs = overlay_input(sid, carried, tim), overlay_input(sid, target, tim)
        record['reviewed_as'][sha256(mine)] = sha256(theirs)
        row = chibi_rows.get(str(sid))
        if row and row.get('base_generator'):
            write(path, record)
            reviewed._table = None
            import importlib
            gen = importlib.import_module(row['base_generator'])
            skeleton = json.loads(next((ROOT / 'content/species').glob(f'{sid}-*.json')).read_text())['model']['skeleton']
            with edit.importing(games):
                made, _ = gen.build(mine, skeleton)
            record['reviewed_as'][sha256(made)] = row['post_source_sha256']
    write(path, record)
    reviewed._table = None
    step, allpins = edit.species_pins()
    section = allpins.setdefault(f'imports@{release}', {})
    section.clear()
    for sid, (carried, tim, _) in sorted(pins.items()):
        section[str(sid)] = edit.provider_pin(sid, carried, tim)
        print(f'{sid}: species provider pins {section[str(sid)]}')
    allpins[f'imports@{release}'] = dict(sorted(section.items(), key=lambda kv: int(kv[0])))
    step._write_pins(allpins)
    print(f'{path.relative_to(ROOT)}: {len(record["models"])} species, {len(record["sources"])} importer outputs')


def overlay_input(sid, model, tim):
    """The model a field overlay of species `sid` reads (the species file's model: its slot aliases applied) when the
    imported model is `model`."""
    import importlib.util
    with tempfile.TemporaryDirectory(prefix='model-variants-input-') as tmp:
        base = Path(tmp)
        (base / f'{sid}.MMD').write_bytes(model)
        (base / f'{sid}.TIM').write_bytes(tim)
        spec = importlib.util.spec_from_file_location('imported_species_variant', edit.IMPORTED_MODELS_SCRIPT)
        imported = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(imported)
        imported.BASE_MODELS = str(base)
        recs = imported.records()
        _, s = imported._species(str(sid), recs[str(sid)], os.listdir(ROOT / 'content/species'))
        import species as species_tools
        s['_path'] = str(ROOT / 'content/species' / 'variant.json')
        with contextlib.redirect_stdout(io.StringIO()):
            return species_tools.species_model(s)[0]


def write(path, record):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(record, indent=1) + '\n')


def cmd_check(a):
    from tools.derive.importers import Provider
    games = Path(a.games).resolve()
    if source_variant(games) != a.release:
        raise SystemExit(f'variants: {games} is not the {a.release} release')
    record = json.loads(variant_path(a.release).read_text())
    allpins = edit.species_pins()[1]
    pins = allpins.get(f'imports@{a.release}', {})
    if set(pins) != set(record['models']):
        raise SystemExit('variants: species-pins.json and the variant list name other species')
    bad = 0
    for sid in sorted(record['models'], key=int):
        prov = Provider(games, Path(tempfile.mkdtemp(prefix='model-variants-check-')))
        try:
            with edit.importing(games):
                model, tim = prov.model(int(sid))
            got = edit.provider_pin(int(sid), model, tim)
            if got != pins[sid]:
                raise SystemExit(f'species provider pins {got}, pinned {pins[sid]}')
            print(f'{sid}: sources, carried delta, target and provider pins verified', flush=True)
        except (SystemExit, ValueError) as e:
            bad += 1
            print(f'{sid}: FAILED: {e}', flush=True)
    return 1 if bad else 0


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest='command', required=True)
    m = sub.add_parser('make')
    m.add_argument('release')
    m.add_argument('--games', required=True)
    m.add_argument('--reference-games', required=True)
    c = sub.add_parser('check')
    c.add_argument('release')
    c.add_argument('--games', required=True)
    a = p.parse_args()
    return (cmd_make if a.command == 'make' else cmd_check)(a) or 0


if __name__ == '__main__':
    sys.exit(main())
