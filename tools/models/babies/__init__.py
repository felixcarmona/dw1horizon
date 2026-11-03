"""Hand-made baby Digimon on native DW1 skeletons (species 470-477).

Each baby keeps a DW1 donor baby's skeleton and every animation program byte for
byte; its mesh, UVs and texture page are our own. The authoring scripts in
`authoring/` draw them (NumPy/OpenCV, developer only). What the build replays is
a plain MD3 delta per file against the donor's model and ALLTIM entry, read from
the player's own extraction: the standard library only, so the browser patcher
runs it too. `content/modeldelta/babies.json` pins every source, delta and
result by SHA-256. How the models were made, as a recipe for the next ones: docs/mods/hand-made-species.md.

  python3 -m tools.models.babies check                 # replay all eight from extracted/
  python3 -m tools.models.babies encode ID MMD TIM     # store a new authored pair as deltas + pins
  python3 -m tools.models.babies encode-dir DIR        # the same for every <Name>.MMD/.TIM pair found in DIR

Re-porting a redrawn baby: replace its authoring/<name>.py (paths through authoring/lib.py), run it (it writes
build/babies-authoring/<Name>.MMD/.TIM), then authoring/shrink.py on that folder (the size review scales Nyokimon,
Nyaromon and Yokomon down after their scripts), `encode` or `encode-dir` the folder, then a developer build
(`python3 -m tools.dev build`) rewrites tools/derive/recipes/species-pins.json; commit the script, the deltas,
babies.json and the pins. Re-measure model.height in the species file if the silhouette changed.
"""
import hashlib
import json
from pathlib import Path
import sys

from tools.models import delta as modeldelta

ROOT = Path(__file__).resolve().parents[3]
MANIFEST = 'content/modeldelta/babies.json'
ALLTIM = 'CHDAT/ALLTIM.TIM'


def _sha256(data):
    return hashlib.sha256(data).hexdigest()


def records(root=ROOT):
    return {int(k): v for k, v in json.loads((Path(root) / MANIFEST).read_text())['babies'].items()}


def donor_sources(record, extracted):
    """(donor MMD, donor ALLTIM entry) from the player's extraction, both checked against their pins."""
    import mmd
    extracted = Path(extracted)
    model = (extracted / 'CHDAT' / record['donor_model']).read_bytes()
    texture = mmd.load_tim(str(extracted / ALLTIM), record['donor']).to_bytes()
    for data, pin, what in ((model, record['donor_model_sha256'], 'model'),
                            (texture, record['donor_texture_sha256'], 'texture')):
        if _sha256(data) != pin:
            raise ValueError(f'{record["name"]}: donor {what} SHA-256 mismatch (not the USA DW1 extraction)')
    return model, texture


def build_species(species, extracted, root=ROOT):
    """(MMD, TIM) of one baby: donor sources, deltas and results all checked by SHA-256."""
    record = records(root)[int(species)]
    model, texture = donor_sources(record, extracted)
    result = []
    for kind, source in (('mmd', model), ('tim', texture)):
        row = record[kind]
        delta = (Path(root) / row['delta']).read_bytes()
        if _sha256(delta) != row['delta_sha256']:
            raise ValueError(f'{record["name"]}: {row["delta"]}: delta SHA-256 mismatch')
        data = modeldelta.decode(delta, [source])
        if len(data) != row['size'] or _sha256(data) != row['sha256']:
            raise ValueError(f'{record["name"]}: {kind}: target SHA-256 mismatch')
        result.append(data)
    import motionstorage
    motionstorage.require(result[0], record['bones'])
    return tuple(result)


def encode(species, mmd_bytes, tim_bytes, extracted, root=ROOT):
    """Store an authored pair as deltas against the donor and rewrite its pins."""
    path = Path(root) / MANIFEST
    table = json.loads(path.read_text())
    record = table['babies'][str(species)]
    sources = donor_sources(record, extracted)
    for kind, data, source in (('mmd', mmd_bytes, sources[0]), ('tim', tim_bytes, sources[1])):
        row = record[kind]
        delta = modeldelta.encode(data, [source])
        if modeldelta.decode(delta, [source]) != data:
            raise ValueError(f'{record["name"]}: {kind}: delta does not reproduce the authored file')
        (Path(root) / row['delta']).parent.mkdir(parents=True, exist_ok=True)
        (Path(root) / row['delta']).write_bytes(delta)
        row.update(delta_sha256=_sha256(delta), sha256=_sha256(data), size=len(data))
    path.write_text(json.dumps(table, indent=1) + '\n')
    return record


def main(argv):
    if str(ROOT / 'tools') not in sys.path:
        sys.path.insert(0, str(ROOT / 'tools'))
    if argv[:1] == ['check']:
        for species, record in sorted(records().items()):
            model, texture = build_species(species, ROOT / 'extracted')
            print(f'{species} {record["name"]}: MMD {len(model)} B, TIM {len(texture)} B, SHA-256 verified')
        return 0
    if argv[:1] == ['encode-dir'] and len(argv) == 2:
        folder = Path(argv[1])
        for species, record in sorted(records().items()):
            mmd_path, tim_path = folder / (record['name'] + '.MMD'), folder / (record['name'] + '.TIM')
            if mmd_path.exists() and tim_path.exists():
                encode(species, mmd_path.read_bytes(), tim_path.read_bytes(), ROOT / 'extracted')
                print(f'{species} {record["name"]}: deltas and pins written to {MANIFEST}')
        return 0
    if argv[:1] == ['encode'] and len(argv) == 4:
        record = encode(int(argv[1]), Path(argv[2]).read_bytes(), Path(argv[3]).read_bytes(), ROOT / 'extracted')
        print(f'{argv[1]} {record["name"]}: deltas and pins written to {MANIFEST}')
        return 0
    print(__doc__)
    return 2


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
