"""get/put/check handlers for tools/models/edit.py's DW1 record originals."""
from pathlib import Path
import json

from tools.models import delta as modeldelta
from tools import recordoriginals as R


def run(a):
    manifest = json.loads((R.ROOT / R.MANIFEST).read_text())
    keys = [a.id] if hasattr(a, 'id') else a.ids
    selected = manifest['models'] if not keys else []
    for key in keys:
        hit = [r for r in manifest['models'] if str(r['id']) == key or r['name'].lower() == key.lower()]
        if not hit:
            raise SystemExit(f'model edit: no record original {key}')
        selected.extend(hit)
    if a.command not in ('get', 'put', 'check'):
        raise SystemExit('record originals support get, put and check')
    from tools.derive.steps import species as step
    pins = json.loads((R.ROOT / step.PINS).read_text())
    provider = None
    if any(s.get('producer') == 'import' for row in selected for kind in ('mmd','tim')
           if kind in row for s in row[kind]['sources']):
        from tools.models.edit import games_dir
        from tools.recordimports import Sources
        games = games_dir(a)
        provider = Sources(games, R.ROOT / 'build/imported-model-edit/record-import-work')
    from tools.derive.importers import source_context
    from tools.derive import crmath, pysum
    def decoded(record):
        if provider is None:
            return R.decode(record)
        from tools.derive.steps.species import species_tools
        crmath.install(); pysum.install()
        try:
            with species_tools(), source_context(provider.games):
                return R.decode(record, provider=provider)
        finally:
            crmath.uninstall(); crmath.clear(); pysum.uninstall()
    for row in selected:
        files = {k: decoded(row[k]) for k in ('mmd', 'tim') if k in row}
        if a.command == 'get':
            out = Path(a.out or R.ROOT / 'build/imported-model-edit/edit')
            out.mkdir(parents=True, exist_ok=True)
            stem = out / f'{row["id"]}-{row["name"]}'
            exported = dict(files)
            if 'tim' not in exported:
                atlas = (R.ROOT / 'extracted/CHDAT/ALLTIM.TIM').read_bytes()
                exported['tim'] = atlas[row['id'] * 0x4800:(row['id'] + 1) * 0x4800]
            for kind, data in exported.items():
                p = Path(f'{stem}.{kind.upper()}');p.write_bytes(data)
                print(f'{p}: {len(data)} B, SHA-256 {R.digest(data)}')
            print(f'look: tools/animstudio.py sheet /tmp/{row["id"]}.png {stem}.MMD:{row["id"]}:{stem}.TIM --slot 2')
            texture = ' [TIM]' if 'tim' in row else ''
            print(f'store: tools/models/edit.py put {row["id"]} {stem}.MMD{texture}')
            if 'tim' not in row:
                print('TIM is the unchanged disc texture for inspection; this record has no texture delta')
        elif a.command == 'put':
            edits = {'mmd': Path(a.mmd).read_bytes()}
            if a.tim:
                if 'tim' not in row:
                    raise SystemExit('this species uses its unchanged disc texture; it has no texture delta')
                edits['tim'] = Path(a.tim).read_bytes()
            for kind, data in edits.items():
                record = row[kind]
                if data == files[kind] and not a.force:
                    print(f'{record["delta"]}: same target, delta kept')
                    continue
                sources = R.sources(record, provider=provider)
                delta = modeldelta.encode(data, sources)
                if modeldelta.decode(delta, sources) != data:
                    raise ValueError('record originals: new delta did not round-trip')
                (R.ROOT / record['delta']).write_bytes(delta)
                record.update(delta_sha256=R.digest(delta), sha256=R.digest(data), size=len(data))
                files[kind] = data
                print(f'{record["delta"]}: {len(delta)} B, SHA-256 {record["sha256"]}')
            (R.ROOT / R.MANIFEST).write_text(json.dumps(manifest, indent=2) + '\n')
            if not a.no_species_pins:
                import hashlib
                pins['record_originals'][str(row['id'])] = [hashlib.sha1(files[k]).hexdigest() if k in files else None
                                                          for k in ('mmd', 'tim')]
                step._write_pins(pins)
        elif a.command == 'check':
            if a.species_pins:
                import hashlib
                actual = [hashlib.sha1(files[k]).hexdigest() if k in files else None for k in ('mmd', 'tim')]
                if actual != pins['record_originals'].get(str(row['id'])):
                    raise ValueError(f'{row["id"]}: record_originals provider SHA-1 pins differ')
            print(f'{row["id"]} {row["name"]}: sources, plain deltas and targets verified')
    if a.command == 'check':
        print(f'{len(selected)}/{len(selected)} record originals verified')
    return 0
