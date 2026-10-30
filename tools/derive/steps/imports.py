"""The player's source discs + plain deltas -> the 175 imported base models."""
import contextlib
import io
import json
import os

from .. import runner
from ..importers import Provider
from .species import providers, species_tools

NAME = 'imports'
DESCRIPTION = 'Imported model and delta replay'
AFTER = ()
FACTS = False


def ids(ctx):
    if 'imports' not in providers(ctx.env):
        return []
    with open(os.path.join(runner.ROOT, 'content/modeldelta/models.json')) as f:
        return [r['id'] for r in json.load(f)['models']]


def make_model(out, species):
    log = io.StringIO()
    with species_tools(), contextlib.redirect_stdout(log):
        m, x = Provider(os.path.join(out, 'source-games'), os.path.join(out, 'import-work', str(species))).model(species)
        target = os.path.join(out, 'imported-models')
        os.makedirs(target, exist_ok=True)
        for ext, data in (('MMD', m), ('TIM', x)):
            with open(os.path.join(target, f'{species}.{ext}'), 'wb') as f:
                f.write(data)
    return f'{species}: imported MMD/TIM SHA-256 verified ({len(m)}/{len(x)} bytes)'


def units(ctx):
    return [runner.Unit(str(t), make_model, (ctx.out, t),
                        ['tools', 'content/modeldelta', 'content/models', 'content/species',
                         'content/imports/specs', 'extracted', ctx.path('source-games')],
                        [f'imported-models/{t}.MMD', f'imported-models/{t}.TIM']) for t in ids(ctx)]


def outputs(ctx):
    return [(f'imported-models/{t}.{ext}', None) for t in ids(ctx) for ext in ('MMD', 'TIM')]


def prepare(ctx):
    if not ids(ctx):
        return
    missing = [game for game in ('dcb', 'dw2', 'dw2003') if not os.path.isfile(ctx.path('source-games', game, 'disc', 'SYSTEM.CNF'))]
    if missing:
        raise ValueError('source discs required: ' + ', '.join(missing) +
                         '; derive build --source-disc dcb=IMAGE --source-disc dw2=IMAGE --source-disc dw2003=IMAGE')
    os.makedirs(ctx.path('imported-models'), exist_ok=True)


def finish(ctx):
    missing = [p for p, _ in outputs(ctx) if not os.path.isfile(ctx.path(p))]
    if missing:
        raise ValueError('missing imported models: ' + ', '.join(missing))


def build(ctx):
    prepare(ctx)
    ctx.run_units(units(ctx))
    finish(ctx)
