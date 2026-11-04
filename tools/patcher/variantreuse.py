"""make-release --source-variant: one tools/derive run on the USA disc instead of one per base, when that is provably
the same.

A source variant (World 3 USA for dw2003) changes only what tools/derive makes from the source discs; a regional base
changes only what it makes from the base's own files. When those two sets of derive steps do not meet, a regional
base's files with the variant are its reference files with the variant's changes on the USA disc put in. reuse() checks
that and gives every base's derived files, or the reason it cannot (make-release then runs derive on every base, as
before). The steps' graph is AFTER of each step in the bundle's tools/derive; what each step reads of the player's disc
is the bundle build's --record manifest (make_bundle_derive).

rule: a step that reads the source discs is named in SOURCE_STEPS (tools/test_variant_reuse.py checks the step
modules), and each one's dependents (AFTER, transitively) count too.
"""
import ast
import os

# The derive steps that open the source discs (build/NAME/source-games): the imported models, the record originals
# that import, the species pins chosen by the World 3 disc's boot file.
SOURCE_STEPS = ('imports', 'record_originals', 'species')


def step_graph(derive_dir):
    """{step: its AFTER} of every step of tools/derive at derive_dir (read, not imported)."""
    steps = os.path.join(derive_dir, 'steps')
    graph = {}
    for name in sorted(os.listdir(steps)):
        if not name.endswith('.py') or name == '__init__.py':
            continue
        with open(os.path.join(steps, name), encoding='utf-8') as f:
            tree = ast.parse(f.read())
        found = {t.id: n.value for n in tree.body if isinstance(n, ast.Assign) for t in n.targets
                 if isinstance(t, ast.Name) and t.id in ('NAME', 'AFTER')}
        if 'NAME' in found:
            graph[ast.literal_eval(found['NAME'])] = tuple(ast.literal_eval(found['AFTER'])) if 'AFTER' in found else ()
    return graph


def dependents(graph, seeds):
    """seeds and every step that reads them (AFTER), transitively."""
    out, todo = set(), list(seeds)
    while todo:
        s = todo.pop()
        if s in out:
            continue
        out.add(s)
        todo += [n for n, after in graph.items() if s in after]
    return out


def same_file(a, b):
    try:
        if os.path.getsize(a) != os.path.getsize(b):
            return False
    except OSError:
        return False
    with open(a, 'rb') as fa, open(b, 'rb') as fb:
        while True:
            x, y = fa.read(1 << 20), fb.read(1 << 20)
            if x != y:
                return False
            if not x:
                return True


def differing_inputs(us_root, base_roots, extract):
    """The disc paths of `extract` whose bytes, as tools/derive read them (ROOT/extracted/), differ between the USA
    tree and any of base_roots ({base: tree}); None when a tree lacks one."""
    out = set()
    for key, root in base_roots.items():
        for q in extract:
            a = os.path.join(us_root, 'extracted', *q.split('/'))
            b = os.path.join(root, 'extracted', *q.split('/'))
            if not (os.path.isfile(a) and os.path.isfile(b)):
                return None
            if not same_file(a, b):
                out.add(q)
    return out


def writers(manifest, disc_path):
    """The steps that list the file derive made for disc_path among their outputs."""
    rel = manifest['files'][disc_path]['file']
    return {n for n, s in manifest['steps'].items() if rel in s.get('outputs', ())}


def reuse(holes, base_holes, made_us, manifest, recorded, graph, differing):
    """-> ({base: {hole id: bytes}}, None) when every base's derived files with the variant are its reference ones
    with the holes the variant changed on the USA disc (made_us) put in; else (None, why).

    holes: the manifest's holes; base_holes {base: {id: bytes}} (the reference pass, 'us' among them); manifest: the
    USA variant derive's derived/manifest.json; recorded: the bundle build's (--record: each step's inputs); graph:
    step_graph(); differing: differing_inputs() over every base that derives on its own files."""
    if 'us' not in base_holes or differing is None:
        return None, 'no USA reference or no regional derive trees'
    us = base_holes['us']
    if any(h['id'] not in made_us for h in holes):
        return None, 'the USA variant derive is missing derived files'
    changed = [h for h in holes if made_us[h['id']] != us[h['id']]]
    regional = {h['id'] for h in holes if any(b[h['id']] != us[h['id']] for b in base_holes.values())}
    both = [h['file'] for h in changed if h['id'] in regional]
    if both:
        return None, f'the variant changes files that differ per base: {", ".join(both[:5])}'
    steps = recorded.get('steps') or {}
    if set(manifest.get('steps', ())) - set(steps) or any('inputs' not in s for s in steps.values()):
        return None, 'the bundle build recorded no inputs for some steps'
    reads = {f'extracted/{q}' for q in differing}
    direct = {n for n, s in steps.items() if reads & set(s['inputs'])}
    by_base = dependents(graph, direct)                 # steps whose bytes may differ per base
    made_by = {}
    for h in changed:
        if h['file'] not in manifest.get('files', {}):
            return None, f'{h["file"]}: not in the USA variant derive\'s manifest'
        made_by[h['file']] = writers(manifest, h['file'])
        if not made_by[h['file']]:
            return None, f'{h["file"]}: no step lists it'
    by_source = dependents(graph, set(SOURCE_STEPS).union(*made_by.values()))
    # rule: plan reads every step (it lists the disc's files and copies the language files); a file it copies keeps
    # its maker's bytes, so plan alone in both sets is allowed: the files the variant changed must not be plan's
    # (checked below) and the files that differ per base must not change on the USA disc (checked above)
    meet = (by_base & by_source) - {'plan'}
    if meet:
        return None, f'derive steps read both the source discs and the base\'s own files: {", ".join(sorted(meet))}'
    for q, made in sorted(made_by.items()):
        if made & by_base:
            return None, f'{q}: made by {", ".join(sorted(made))}, which read the base\'s own files'
    put = {h['id']: made_us[h['id']] for h in changed}
    return {key: {**b, **put} for key, b in base_holes.items()}, None
