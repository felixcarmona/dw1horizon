"""The steps' static dependencies (each step module's AFTER) and the smallest set of steps for some holes."""
from . import steps as S


def order(mods):
    """mods in an order where every step comes after the steps it reads (AFTER), those missing from mods added; a cycle
    stops. rule: a MOD_BUILD step (the story mod's maps) is not added: build.sh made it before (derive build --recipe
    names it with the rest)."""
    by = {m.NAME: m for m in mods}
    done, out, busy = set(), [], set()

    def visit(m):
        if m.NAME in done: return
        if m.NAME in busy: raise SystemExit(f'derive: the steps read each other ({m.NAME})')
        busy.add(m.NAME)
        for a in m.AFTER:
            if a not in by:
                x = S.load(a)
                if getattr(x, 'MOD_BUILD', False):
                    continue
                by[a] = x
            visit(by[a])
        busy.discard(m.NAME); done.add(m.NAME); out.append(m)

    for m in list(mods):
        visit(m)
    return out


def producers(ctx, mods):
    """{disc path: step module} of every output with a disc path."""
    out = {}
    for m in mods:
        for _, disc in m.outputs(ctx):
            if disc: out[disc] = m
    return out


def targets(ctx, holes, mods=None):
    """The smallest list of steps (in build order) that makes the disc paths `holes`, with what they read."""
    mods = mods or S.owned()
    prod = producers(ctx, mods)
    missing = [h for h in holes if h not in prod]
    if missing:
        raise SystemExit(f'derive: no step makes {", ".join(missing)}')
    return order(list({prod[h].NAME: prod[h] for h in holes}.values()))
