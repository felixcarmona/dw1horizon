"""One release-pinned model for wiki pages, trees and search (stdlib only)."""
import ast
import io
import importlib.util
import json
from pathlib import Path
import re
import subprocess
import sys
import tarfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools/guide'))
_guide_spec = importlib.util.spec_from_file_location('wiki_guide_reader', ROOT / 'tools/guide/build.py')
guide = importlib.util.module_from_spec(_guide_spec)
_guide_spec.loader.exec_module(guide)
import recruits
import learning

LANGS = ('en', 'es', 'pt-br', 'fr', 'de', 'it', 'ja', 'ca', 'zh-hans')
INPUTS = ('content/species', 'content/techniques', 'content/items', 'content/tables',
          'content/maps', 'content/screens', 'content/battle',
          'tools/derive/recipes/everything.json', 'tools/dws/backend.py',
          'story/base', 'story/mods/what-the-island-forgot',
          'text', 'mods/patches', 'docs/reference/partner.md', 'docs/reference/combat.md',
          'docs/mods/options.md', 'docs/release/README-players.md')


def snapshot(ref):
    if ref == 'working':
        # Explicit next-release review only; the public builder still requires a release tag.
        paths = subprocess.check_output(
            ['git', 'ls-files', '-z', '--cached', '--others', '--exclude-standard', '--', *INPUTS],
            cwd=ROOT).decode().split('\0')
        files = {name: (ROOT / name).read_bytes() for name in paths if name and (ROOT / name).is_file()}
        base = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
        return 'working:' + base, files
    commit = subprocess.check_output(['git', 'rev-parse', '--verify', ref + '^{commit}'], cwd=ROOT, text=True).strip()
    raw = subprocess.check_output(['git', 'archive', commit, *INPUTS], cwd=ROOT)
    with tarfile.open(fileobj=io.BytesIO(raw)) as archive:
        files = {m.name: archive.extractfile(m).read() for m in archive if m.isfile()}
    return commit, files


def read_json(files, name):
    return json.loads(files[name])


def patch_sources(files):
    """Active non-removed lines in series order; never read the working game tree."""
    series = files['mods/patches/series'].decode().splitlines()
    for name in series:
        if not name or name.startswith('#'):
            continue
        raw = files['mods/patches/' + name].decode()
        yield name, '\n'.join(line[1:] for line in raw.splitlines()
                             if line[:1] in ('+', ' ') and not line.startswith('+++'))


def save_blocks(files):
    # Resolve the actual card creation expression, including later single-block patches.
    # An unrecognized new layout fails the build rather than publishing stale advice.
    defines, expression = {}, None
    for _, source in patch_sources(files):
        for name, value in re.findall(r'^#define\s+(\w+)\s+(0x[\da-fA-F]+|\d+)\b', source, re.M):
            defines[name] = int(value, 0)
        calls = re.findall(r'status\s*=\s*MemCardCreateFile\(\s*MEMORY_CARD_ID\s*,\s*SAVE_FILE_NAME\s*,\s*([^;]+?)\);', source, re.S)
        if calls:
            expression = calls[0].strip()
    if expression is None:
        raise ValueError('No reviewed memory-card creation expression in release')
    def evaluate(node):
        if isinstance(node, ast.Constant) and isinstance(node.value, int):
            return node.value
        if isinstance(node, ast.Name):
            return defines[node.id]
        if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Div, ast.FloorDiv)):
            return evaluate(node.left) // evaluate(node.right)
        raise ValueError('Review changed memory-card block expression: ' + expression)
    count = evaluate(ast.parse(expression, mode='eval').body)
    if count not in (1, 2):
        raise ValueError('Review changed memory-card block count')
    return count


def article_facts(files):
    """Bind authored timing, food effects and exchange rows to the selected disc."""
    items = {item['id']: item for path, raw in files.items()
             if path.startswith('content/items/') and path.endswith('.json')
             for item in [json.loads(raw)]}
    shops = read_json(files, 'content/tables/shops.json')
    gives, takes = shops['mojyamonGives'], shops['mojyamonTakes']
    if len(gives) != 12 or len(takes) != 12 or any(gives[9:]) or any(takes[9:]):
        raise ValueError('Review changed Mojyamon exchange layout')
    joined = '\n'.join(source for _, source in patch_sources(files))
    for needle in ('evoRequirementPoints(met) >= evoPassPoints() && isPartnerModelFit(target)',
                   'PARTNER_PARA.evoTimer < MOD_EVO_TIMING[MOD_EVO_MEGA]',
                   'MAX_SHOP_AMOUNT = 1;',
                   'isTriggerSet(trade == 8 ? 13 : MOJYA_DAILY_FIRST + trade)'):
        if needle not in joined:
            raise ValueError('Review changed article behavior: ' + needle)
    return dict(chain_melon_hours=items[70]['effect']['lifetime'],
                digiseabass_hours=items[67]['effect']['lifetime'],
                mojyamon=list(zip(gives[:9], takes[:9])))


def load(ref):
    commit, files = snapshot(ref)
    all_species = [json.loads(v) for k, v in sorted(files.items()) if k.startswith('content/species/') and k.endswith('.json')]
    techniques = [json.loads(v) for k, v in sorted(files.items()) if k.startswith('content/techniques/') and k.endswith('.json')]
    partners = {s['id']: s for s in all_species if 'partner' in s}
    tree = read_json(files, 'content/tables/evolution-tree.json')
    rules = read_json(files, 'content/tables/evolution-rules.json')
    to = {i: [t for t in tree.get('routes', {}).get(str(i), s.get('evolution', {})).get('to', []) if t in partners] for i, s in partners.items()}
    named = {s['name']: s['id'] for s in partners.values()}
    timed = {}
    for rule in tree['ultimate_rules']:
        a, b = named[rule['from']], named[rule['to']]
        if b not in to[a]:
            to[a].append(b)
        timed[(a, b)] = rules['evolutionTiming'].get('megaHours', 120) if partners[b]['level'] == 'mega' else rules['evolutionTiming']['hours']['ultimate']
    frm = {i: [] for i in partners}
    for a, targets in to.items():
        for b in targets:
            frm[b].append(a)
    rows = []
    for i, s in sorted(partners.items(), key=lambda pair: (guide.LEVELS.index(pair[1]['level']), pair[1]['name'].casefold(), pair[0])):
        moves = []
        for name in s['techniques']:
            if name is None:  # An empty move slot, not a technique named null.
                continue
            move = guide.resolve_move(name, techniques)
            moves.append(dict(id=move['id'], chance=guide.chance(s, move)))
        rows.append(dict(id=i, name=s['name'], level=s['level'], attribute=s['attribute'],
                         specialties=[x for x in s['specialties'] if x], slots=s['specialties'],
                         moves=moves, finisher=s.get('finisher', {}), partner=s['partner'],
                         to=to[i], parents=frm[i], requirements=guide.requirements(s, partners, tree),
                         special=tree['special_routes'].get(s['name'], ''),
                         spoiler=bool(tree['special_routes'].get(s['name']))))
    for move in techniques:
        move['baseMP'] = guide.base_mp(move)
    roster = recruits.load(files, all_species)
    hidden={r['id']:r['hidden'] for r in read_json(files,'content/tables/city-residents.json')}
    # Recruitment prose is presentation; dialogue is resolved separately for folded spoilers.
    for row in roster:
        row['hidden']=hidden[row['id']]
        row.pop('evidence', None)
    tables = {name: read_json(files, f'content/tables/{name}.json') for name in
              ('new-game', 'training-gains', 'care-rules', 'battle-formulas', 'clock')}
    facts = dict(save_blocks=save_blocks(files), timing=rules['evolutionTiming'],
                 score=rules['evolutionFormula']['score'], **tables)
    hard = tables['battle-formulas']['battleFormulas'].get('hard')
    facts['hard'] = hard
    facts.update(article_facts(files))
    # Bind shared article claims to release source, not just a version string.
    patches = dict(patch_sources(files))
    joined = '\n'.join(patches.values())
    for needle in ('MOD_TRAIN_BLOCK', 'modQuizResult', 'MOD_DIFF_EASY'):
        if needle not in joined:
            raise ValueError('Article behavior needs review: ' + needle)
    players = files['docs/release/README-players.md'].decode()
    if '250%' not in players or '20 Hz' not in players:
        raise ValueError('Review frame-rate guidance against selected release')
    return dict(tag=ref, commit=commit, species=rows, techniques=techniques, recruits=roster,
                enemies={s['id']:s for s in all_species},
                learning_sources=learning.sources(files,all_species,techniques,rows),
                brain_learning=learning.brains(files,techniques,rows),
                technique_aliases=learning.shared_aliases(files),
                timed=timed, facts=facts, files=files, rules=rules)


def localized_names(files, lang):
    """Use the executable text bank's English-base, selected-language override order."""
    english=read_json(files,'text/ours/names.json')
    if lang=='en':return english
    return {**english,**json.loads(files.get(f'text/{lang}/names.json',b'{}'))}


def slug(name):
    return re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-')


def bakemon_dialogue(files, lang):
    """Resolve the successful choice path and displayed partner dialogue from the snapshot."""
    script = files['story/base/zones/overdell-cemetery/s035-35/script.dws'].decode()
    talk = script.split('on talk(bakemon) replace {', 1)[1].split('on step(', 1)[0]
    # Track nested choice branches up to the recruit operation, rather than copying an answer sequence.
    tokens = re.compile(r'text\("(s035\.sec5\.m\d+\.o\d+)"\)\s*(?:or cancel\s*)?=>\s*\{|recruit\(species\("Bakemon"\)\)|[{}]')
    stack, paths = [], []
    for token in tokens.finditer(talk):
        if token.group(1):
            stack.append(token.group(1))
        elif token.group().startswith('recruit('):
            paths.append([key for key in stack if key])
        elif token.group() == '{':
            stack.append(None)
        elif stack:
            stack.pop()
    if len(paths) != 1 or len(paths[0]) != 3:
        raise ValueError('Review changed Bakemon recruitment choice flow')
    choices = paths[0]
    if [key.rsplit('.', 1)[0] for key in choices] != ['s035.sec5.m0', 's035.sec5.m1', 's035.sec5.m2']:
        raise ValueError('Review changed Bakemon question order')
    english = read_json(files, 'text/ours/dialogue/overdell-cemetery.json')
    own = english if lang == 'en' else read_json(files, f'text/{lang}/dialogue/overdell-cemetery.json')
    readable_keys = [f's035.sec5.u{i}' for i in (8, 9, 10, 11)]
    readable = all(key in english and f'text("{key}")' in talk for key in readable_keys)
    if any(key in english for key in readable_keys) and not readable:
        raise ValueError('Review incomplete Bakemon partner-translation implementation')
    if readable and not re.search(r'partner_type == 37\s*\|\|\s*partner_type == 157', talk):
        raise ValueError('Review changed Bakemon partner guards')
    # Match each question to its actual following choice branch, including localized partner variants.
    positions=[talk.index(f'text("{key}")') for key in choices]
    bounds=[0,*positions,talk.index('recruit(species("Bakemon"))')]
    displayed=[]
    for start,end in zip(bounds,bounds[1:]):
        segment=talk[start:end]
        keys=re.findall(r'say\(bakemon, text\("([^"]+)"\)\)',segment)
        if len(keys)!=(2 if readable else 1):
            raise ValueError('Review changed Bakemon question/choice association')
        if readable and not re.search(r'if \(partner_type == 37\s*\|\|\s*partner_type == 157\)\s*\{\s*say\(bakemon, text\("'+re.escape(keys[0])+r'"\)\);\s*\} else',segment):
            raise ValueError('Review changed readable Bakemon branch')
        displayed.append(keys[0])
    question_keys,ending_key=displayed[:3],displayed[3]
    for key in question_keys + choices + [ending_key]:
        if key not in own or f'text("{key}")' not in talk:
            raise ValueError('Missing release-localized Bakemon text: ' + lang + '/' + key)
    def clean(value):
        if isinstance(value, list):
            return ' '.join(clean(part) for part in value)
        return re.sub(r'\{color\s+\d+\}', '', value).strip()
    return dict(readable=readable, rows=[dict(question=clean(own[q]), answer=clean(own[a]),
                                           question_key=q, answer_key=a) for q, a in zip(question_keys, choices)],
                ending=clean(own[ending_key]))


def place_names(files, lang):
    names = recruits.screen_names(files, lang)
    english = localized_names(files, 'en')
    own = localized_names(files, lang)
    translated = {v.casefold():own.get(k,v) for k,v in english.items()
                  if k.startswith(('main.STR_MAP_NAME_', 'screen.caption.'))}
    for path,raw in files.items():
        if path.startswith('story/mods/what-the-island-forgot/screens/') and path.endswith('.json'):
            screen = json.loads(raw)
            caption = screen['caption']
            if not isinstance(caption,str):
                raise ValueError('Review mod screen caption: ' + path)
            names[screen['id']] = translated.get(caption.casefold(), caption)
    return names
