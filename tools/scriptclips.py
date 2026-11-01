#!/usr/bin/env python3
"""Check every built partner's script animation contract, including native disc models."""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import struct
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import coldsplit
import species


def clips(model, cold=b''):
    """Slot -> duration; resolve both resident and cold entries without interpreting poses."""
    table = struct.unpack_from('<I', model, 4)[0]
    result = {}
    for slot in range(coldsplit.table_length(model)):
        entry = struct.unpack_from('<I', model, table + 4 * slot)[0]
        if not entry:
            result[slot] = None
        elif entry & coldsplit.FLAG:
            offset = (entry & 0xffff) * 4
            length = ((entry >> 16) & 0x7fff) * 4
            if length < 2 or offset + length > len(cold):
                raise ValueError(f'slot {slot}: cold clip outside its data')
            result[slot] = struct.unpack_from('<H', cold, offset)[0] & 0x7fff
        else:
            result[slot] = struct.unpack_from('<H', model, table + entry)[0] & 0x7fff
    return result


def missing(clips_by_slot):
    return [slot for slot in species.SCRIPT_SLOTS if not clips_by_slot.get(slot)]


def audit(path, content=None):
    content = Path(content) if content else Path(path).parent / 'species'
    if not content.is_dir():
        raise ValueError('generated species folder required to resolve native partner replacements')
    definitions = species.load_content(str(content))
    data, _, records = species.read_archive(str(path))
    rows = []
    for sid, record in enumerate(records):
        if not record['flags'] & species.FLAG_PARTNER:
            continue
        if record['modelName']:
            definition = definitions[sid]['model']
            replacement = definition.get('partner_file') or definition.get('file')
            source = species.resolve_path(replacement) if replacement else species.originals().model_path(sid)
            model = Path(source).read_bytes()
            cold = b''
        else:
            start = record['modelSector'] * 2048
            model = data[start:start + record['modelSize']]
            start += (len(model) + 2047) // 2048 * 2048
            cold = data[start:start + coldsplit.cold_length(model)] if coldsplit.is_split(model) else b''
        durations = clips(model, cold)
        rows.append(dict(species=sid, name=record['para']['name'], model_sha256=hashlib.sha256(model).hexdigest(),
                         clips={str(s): durations.get(s) for s in species.SCRIPT_SLOTS}, missing=missing(durations)))
    return dict(archive_sha256=hashlib.sha256(data).hexdigest(), required_slots=species.SCRIPT_SLOTS,
                dependencies={'movement_completion_idle': [0], 'walk': [2], 'run_and_walk_away': [4],
                              'face_and_turn': [], 'play': 'the requested slot'},
                partners=len(rows), failures=sum(bool(r['missing']) for r in rows), rows=rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('archive', type=Path)
    parser.add_argument('--out', type=Path)
    parser.add_argument('--content', type=Path, help='generated species folder (default: beside archive)')
    parser.add_argument('--csv', type=Path, help='write a compact per-species audit snapshot')
    args = parser.parse_args()
    report = audit(args.archive, args.content)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(report, indent=2) + '\n')
    if args.csv:
        args.csv.parent.mkdir(parents=True, exist_ok=True)
        with args.csv.open('w') as stream:
            writer = csv.writer(stream, lineterminator='\n')
            writer.writerow(['species', 'name', 'model_sha256', 'missing_script_slots'])
            for row in report['rows']:
                writer.writerow([row['species'], row['name'], row['model_sha256'], ' '.join(map(str, row['missing']))])
    for row in report['rows']:
        if row['missing']:
            print(f"{row['species']} {row['name']}: missing/zero-duration script clips {row['missing']}")
    print(f"Script clips: {report['partners']} partner species, {report['failures']} failures")
    return bool(report['failures'])


if __name__ == '__main__':
    sys.exit(main())
