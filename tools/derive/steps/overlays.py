"""Generate reviewed imported-model field animations and species icons.

The registry in content/models/imports/species.py binds 65 species to generators
and output names. Each overlay is an independent unit, reading the imported-models
folder produced by the imports step and writing a model/report pair into
build/NAME/imported-species-models. The species step reads these results with
make(out, generate=False) and checks their final pins in one process.

Without SPECIES_PROVIDER=imports the step has no unit and makes nothing.

A unit runs with the repository's modules it imported forgotten afterwards (species_tools, as the species step does):
one process running them one after another (the reference), a forked process per unit (--jobs) and a reused Web Worker
see the same fresh modules, so no overlay can depend on what an earlier one left in a module.

Icons: the species icons (tools/portraits.py, ~0.1 s each natively, ~half of the species step in the browser) of the
species that do not wait for the models step are drawn here too, into build/NAME/species-icons (named as the portraits
cache names them: id and the key of the model's and texture's bytes): each overlay unit draws its own species' icon from
the species file the species step will read, and ICON_UNITS units draw the other imported species' and the record
originals'. The species step copies them into its portraits cache (one process) and draws only the rest (the disc's
species and those whose model the models step makes). SPECIES_PORTRAITS=0: none.
"""
import collections
import importlib.util
import json
import os

from .. import runner
from .species import IMPORTED_MODELS_SCRIPT, providers, species_tools

NAME = 'overlays'
DESCRIPTION = 'Imported model field animations and icons'
AFTER = ('imports', 'record_originals')
FACTS = False
ICONS = 'species-icons'
ICON_UNITS = 8


def imported_models(base=None):
    """content/models/imports/species.py, loaded afresh."""
    spec = importlib.util.spec_from_file_location('imported_species', os.path.join(runner.ROOT, IMPORTED_MODELS_SCRIPT))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    m.BASE_MODELS = base
    return m


def folder(ctx):
    """The imported species folder (steps/species.py ImportedModels.folder); the overlays go in its -models sibling."""
    return ctx.path('imported-species')


def _icon(S, s, icons):
    """The icon of species file s into the folder icons (portraits.species_icon, the file as the species step loads it)
    -> a log line."""
    import portraits
    portraits.CACHE = icons
    s = json.loads(json.dumps(s), object_pairs_hook=collections.OrderedDict)
    s['_path'] = s.get('_path') or f'species {s["id"]}'
    try:
        portraits.species_icon(S.validate(s))
    except Exception as ex:            # (the species step draws it again and says why)
        return f'  {s["id"]}: no icon ({ex})'
    return f'  {s["id"]}: icon'


def make_overlay(out, t, icons):
    """One overlay and its species' icon (a unit; in this process, a forked one or a worker) -> its log."""
    with species_tools() as S:     # (every repository module it imports is forgotten afterwards)
        m = imported_models(os.path.join(os.path.dirname(out), 'imported-models'))
        path, proof = m.overlay(out, t)
        log = f'{t}: {os.path.relpath(path, os.path.dirname(out))} ({os.path.getsize(path)} bytes)'
        if icons:
            log += '\n' + _icon(S, m.species_file(out, t)[1], icons)
    return log


def make_icons(out, imported_models_ids, record_ids, icons):
    """The icons of imported species without an overlay (their files as the imported provider writes them into out) and of record
    originals (content/species) (a unit) -> its log."""
    with species_tools() as S:
        m = imported_models(os.path.join(os.path.dirname(out), 'imported-models'))
        recs = m.records()
        names = os.listdir(os.path.join(runner.ROOT, 'content/species'))
        lines = [_icon(S, m.species_file(out, t, recs, names)[1], icons) for t in imported_models_ids]
        content = S.load_content()
        for t in record_ids:
            s = content[t]
            s['model']['file'] = os.path.join(os.path.dirname(out), 'record-originals', f'{t}.MMD')
            if (s.get('texture') or {}).get('file'):
                s['texture']['file'] = os.path.join(os.path.dirname(out), 'record-originals', f'{t}.TIM')
            lines.append(_icon(S, s, icons))
    return '\n'.join(lines)


def icon_ids(ctx):
    """([imported ids without an overlay], [record original ids]) whose icons units draw; ([], []) without icons."""
    if ctx.env.get('SPECIES_PORTRAITS', '1') == '0':
        return [], []
    v = [t for t, e in imported_models().records().items() if not e.get('field_overlay')] if 'imports' in providers(ctx.env) else []
    from .record_originals import ids
    ro = sorted(ids(ctx))
    return v, ro


def wanted(ctx):
    """[(id, field_overlay, generator, model name)] of the records with an overlay, in models.json's order; [] without
    the provider imports."""
    if 'imports' not in providers(ctx.env):
        return []
    m = imported_models()
    out = []
    for t, e in m.records().items():
        if e.get('field_overlay'):
            r = m._recipe(t, e)
            out.append((t, e['field_overlay'], r[1], r[2]))
    return out


def units(ctx):
    out = folder(ctx)
    rel = os.path.relpath(out, ctx.out)
    imported_models_in = [IMPORTED_MODELS_SCRIPT, os.path.join(os.path.dirname(IMPORTED_MODELS_SCRIPT), 'models.json'),
              ctx.path('imported-models'), 'tools', 'content/species']
    v, ro = icon_ids(ctx)
    icons = ctx.path(ICONS) if v or ro else None
    us = [runner.Unit(f'{t} {ov} ({gen})', make_overlay, (out, t, icons), imported_models_in + [f'{gen.replace(".", "/")}.py'],
                      [f'{rel}-models/{name}.MMD', f'{rel}-models/{name}-report.json'] + ([ICONS] if icons else []))
          for t, ov, gen, name in wanted(ctx)]
    if icons:
        both = [(t, 'v') for t in v] + [(t, 'r') for t in ro]
        for k in range(ICON_UNITS):
            part = both[k::ICON_UNITS]
            if part:
                us.append(runner.Unit(f'icons {k + 1}/{ICON_UNITS}', make_icons,
                                      (out, [t for t, w in part if w == 'v'], [t for t, w in part if w == 'r'], icons),
                                      imported_models_in + [ctx.path('record-originals')], [ICONS]))
    return us


def outputs(ctx):
    rel = os.path.relpath(folder(ctx), ctx.out)
    return [(f'{rel}-models/{name}.MMD', None) for _, _, _, name in wanted(ctx)]


def prepare(ctx):
    os.makedirs(folder(ctx) + '-models', exist_ok=True)
    os.makedirs(ctx.path(ICONS), exist_ok=True)


def finish(ctx):
    """Every overlay is there (a unit that failed stopped the build already; this is the scheduler's check)."""
    missing = [p for p, _ in outputs(ctx) if not os.path.isfile(ctx.path(p))]
    if missing:
        raise runner.StepError(f'overlays: not made: {", ".join(missing[:5])}')


def build(ctx):
    prepare(ctx)
    ctx.run_units(units(ctx))
    finish(ctx)
