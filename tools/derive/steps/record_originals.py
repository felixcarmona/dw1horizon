"""Selected record originals replayed from player discs and plain deltas."""
NAME = 'record_originals'
DESCRIPTION = 'Original-disc model delta replay'
AFTER = ()
FACTS = False


def ids(ctx):
    """A base disc that carries no record originals needs no cross-game sources."""
    from tools import recordoriginals
    from .species import DEFAULT_SELECTION, species_tools
    selection = ctx.env.get('SPECIES') or ('' if ctx.env.get('IMPORTS', '1') == '0' else DEFAULT_SELECTION)
    selection += ' ' + ctx.env.get('EXTRA_SPECIES', '')
    with species_tools() as S:
        selected, _ = S.parse_selection(selection)
    return {r['id'] for r in recordoriginals.records()} & selected


def outputs(ctx):
    from tools import recordoriginals
    selected = ids(ctx)
    return [(f'record-originals/{r["id"]}.{kind.upper()}', None)
            for r in recordoriginals.records() if r['id'] in selected
            for kind in ('mmd', 'tim') if kind in r]


def build(ctx):
    from tools import recordoriginals
    from .species import species_tools
    selected = ids(ctx)
    with species_tools():
        made = recordoriginals.make(ctx.path('record-originals'), ids=selected)
    ctx.log(f'{len(made)} record originals: source, delta and target SHA-256 verified')
