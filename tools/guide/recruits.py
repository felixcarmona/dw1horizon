"""Recruit guide facts from the selected snapshot, with checked quest annotations.

Annotations supply player-facing quest explanations, never a second roster or
battle-stat table. Source assertions deliberately fail when a cited scene drifts.
"""
import ast
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent


def load(files, species):
    data = json.loads((HERE / 'recruits.json').read_text())
    roster = json.loads(files['content/tables/city-residents.json'])
    by_id = {s['id']: s for s in species}
    annotations = {r['id']: r for r in data}
    ids = {r['id'] for r in roster}
    if ids != annotations.keys():
        raise ValueError(f'Recruit annotations differ from roster: {ids ^ annotations.keys()}')
    city = files['story/base/city/city.dws'].decode()
    special = {m[0]: int(m[1]) for m in re.findall(r'species (\w+): (\d+) when level >= 3;', city)}
    if 'level - 2 when level >= 3' not in city:
        raise ValueError('Review changed City prosperity rules')
    levels = {'rookie': 3, 'champion': 4, 'ultimate': 5, 'mega': 6}
    result = []
    for ident in sorted(ids):
        row = dict(annotations[ident])
        row['name'] = by_id[ident]['name']
        row['points'] = special.get(row['name'], levels[by_id[ident]['level']] - 2)
        for path, needles in row['evidence'].items():
            source = files[path].decode()
            for needle in needles:
                if not any(part in source for part in (needle if isinstance(needle, list) else [needle])):
                    raise ValueError(f'Review recruit {ident}: {path} no longer contains {needle!r}')
        row['hp'] = None
        if 'battle' in row:
            screen, member = row['battle']
            screen_path = next(k for k in files if k.startswith(f'content/screens/{screen}-'))
            map_name = json.loads(files[screen_path])['file']
            # Screen names normalize case; map files preserve their authored spelling.
            map_path = next(k for k in files if k.lower() == f'content/maps/{map_name}.json'.lower())
            placements = json.loads(files[map_path])['digimon']
            slots = [n for n in placements if n.get('species') == member]
            if not slots:
                raise ValueError(f'Recruit {ident}: missing battle NPC {member} on {screen}')
            enemy = next(s for s in species if re.sub(r'[^A-Za-z0-9]', '', s['name']) +
                         (str(s['id']) if re.search(r'\d$', member) else '') == member)
            base = enemy['wild']['hp']
            values = {base + int(n['hp']) if isinstance(n.get('hp'), str)
                      else n.get('hp', base) for n in slots}
            if len(values) != 1:
                raise ValueError(f'Recruit {ident}: battle HP varies by slot; review annotation')
            row['hp'] = values.pop()
            if 'rematch_slot' in row:
                rematch = next(n for n in slots if n['slot'] == row['rematch_slot'])
                row['rematch_hp'] = rematch.get('currentHP', row['hp'])
        if 'npc_source' in row:
            source, member = row['npc_source']
            tree = ast.parse(files[source].decode())
            if 'location_variants' in row:
                screens = {ast.unparse(n.args[0]) for n in ast.walk(tree)
                           if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
                           and n.func.id == 'screen' and n.args}
                variants = [v for v in row['location_variants'] if v['source'] in screens]
                if len(variants) != 1:
                    raise ValueError(f'Review recruit {ident}: expected one known location variant')
                row.update({k: v for k, v in variants[0].items() if k != 'source'})
            calls = [n for n in ast.walk(tree) if isinstance(n, ast.Call)
                     and isinstance(n.func, ast.Attribute) and n.func.attr == 'npc'
                     and n.args and isinstance(n.args[0], ast.Attribute) and n.args[0].attr == member]
            if len(calls) != 1:
                raise ValueError(f'Recruit {ident}: expected one {member} placement')
            attrs = {k.arg: k.value for k in calls[0].keywords}
            row['hp'] = ast.literal_eval(attrs['hp']) if 'hp' in attrs else None
        result.append(row)
    return result


def text_key(row, field):
    """Reviewed text for the placement in this game snapshot."""
    return f'data.recruit.{field}.{row["id"]}{row.get("text_suffix", "")}'


def screen_names(files, lang):
    screens = {data['id']: data for path, raw in files.items()
               if path.startswith('content/screens/') and path.endswith('.json')
               for data in [json.loads(raw)]}
    names = {}
    for path, raw in sorted(files.items()):
        if path.startswith('story/base/zones/') and path.endswith('/script.py'):
            header = raw.decode().splitlines()[0]
            for ident, label in re.findall(r'\bscreen (\d+) (.+?)(?=, screen |\.$)', header):
                names[int(ident)] = label
    # Library scripts can be installed by MAPHEAD even if their old header says
    # no screen loads them. Reuse another screen with the same caption index.
    captions = {screens[i]['caption']: name for i, name in names.items() if i in screens}
    english = json.loads(files['text/ours/names.json'])
    own = json.loads(files.get(f'text/{lang}/names.json', b'{}'))
    terms = json.loads(files.get(f'text/{lang}/places.json', b'{}')).get('places', {})
    translated = {}
    for key, value in english.items():
        if key.startswith('main.STR_MAP_NAME_'):
            translated[value.casefold()] = terms.get(key.removeprefix('main.STR_MAP_NAME_'), {}).get('name', own.get(key, value))
    result = {}
    for ident, data in screens.items():
        label = names.get(ident) or captions.get(data['caption'])
        if label:
            result[ident] = translated.get(label.casefold(), label)
    result[325] = {'en': 'Kennel', 'es': 'Perrera', 'pt-br': 'Canil', 'fr': 'Chenil',
                   'de': 'Zwinger', 'it': 'Canile', 'ja': '犬舎', 'ca': 'Gossera', 'zh-hans': '犬舍'}[lang]
    return result


def screen_name(files, screen, lang):
    return screen_names(files, lang)[screen]


def species_name(files, name, lang):
    # Most runtime languages retain the content name. Chinese uses its glossary.
    if lang != 'zh-hans':
        return name
    glossary = json.loads(files.get('text/zh-hans/glossary.json', b'{}'))
    term = glossary.get('species', {}).get(name) or glossary.get('provisional', {}).get(name) or glossary.get('terms', {}).get(name)
    return term.get('zh', name) if isinstance(term, dict) else term or name
