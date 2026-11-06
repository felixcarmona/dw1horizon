"""Owned encounter move selections; animation slots remain species-local.

These are authoring defaults for DWS placements. Native maps retain explicit
rows and can be compared with the defaults by the moveset audit.
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'content/battle/enemy-movesets.json'


def load(species=None, path=SOURCE):
    if species is None:
        import species as S
        species = S.load_content()
    result = {}
    import content
    technique_data = content.load_techniques()
    for key, row in json.loads(Path(path).read_text()).items():
        if key.startswith('_'):
            continue
        sid = int(key)
        sp = species[sid]
        if set(row) != {'moves', 'weights'}:
            raise ValueError(f'{path}: {key}: expected moves and weights')
        moves, weights = row['moves'], row['weights']
        if len(moves) != 4 or len(weights) != 4 or any(type(w) is not int or not 0 <= w <= 255 for w in weights):
            raise ValueError(f'{path}: {key}: four moves and four byte weights required')
        if sum(weights) != 100 or len({m for m in moves if m is not None}) != sum(m is not None for m in moves):
            raise ValueError(f'{path}: {key}: distinct moves and weights totaling 100 required')
        slots = []
        for move in moves:
            if move is None:
                slots.append(255)
            elif move not in (sp.get('techniques') or []):
                raise ValueError(f'{path}: {key}: {move} is absent from {sp["name"]}')
            else:
                slots.append(46 + sp['techniques'].index(move))
        # A mode switch can disable an attack, but must leave a damaging choice.
        import species as S
        for block in (sp, sp.get('off', sp)):
            techs = S.techniques_from_json(block.get('techniques', sp['techniques']), str(path))
            if not any(w and slot != 255 and slot - 46 < len(techs) and techs[slot - 46] < 58
                       and techs[slot - 46] != 45
                       and technique_data[techs[slot - 46]]['power'] > 0
                       and technique_data[techs[slot - 46]]['range'] != 4
                       for slot, w in zip(slots, weights)):
                raise ValueError(f'{path}: {key}: no ordinary move in one mode')
        result[sid] = (slots, weights)
    return result
