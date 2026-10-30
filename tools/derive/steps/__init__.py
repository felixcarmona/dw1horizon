"""The steps of tools/derive: one module per group of derived files (tools/derive/README.md, Inventory).

A step module has:
  NAME          the name build-full.sh asks about (derive_owns NAME) and --steps takes
  DESCRIPTION   a short description for derive steps and build reports
  AFTER         names of the steps whose outputs it reads (graph.py)
  FACTS         True: it reads the executable's facts (ctx.facts, facts.py); derive build then needs them
  MOD_BUILD     optional, True: the story mod's build.sh makes it (derive build --steps), build-full.sh's step 0 does not
                (derive build --recipe does: the player's build)
  outputs(ctx)  [(file under ctx.out, disc path or None)]: what it writes, at the paths the bash wrote them
  build(ctx)    makes them, running our scripts through ctx.run (runner.run_script)
  check(ctx)    optional: the checks the bash ran on them (derive build --checks)
  units(ctx)    optional: the step's independent pieces (runner.Unit), run side by side with --jobs
  manifest_plan(ctx)  optional (the plan step): the manifest's "plan"

OWNED lists the steps derive makes in a build: every derived file of the disc; the bash
keeps the executable (make), its tables (balance.py build --no-maps), the language patches and the disc image.
"""
import importlib

# Registered steps, in their documented order.
ALL = ('models', 'imports', 'record_originals', 'overlays', 'species', 'sound', 'story', 'screens', 'maps', 'retouch', 'balance', 'storycopies', 'signs', 'localize', 'title', 'plan')

# Steps derive makes, in the order a build makes those that do not read each other (graph.order)
OWNED = ['models', 'imports', 'record_originals', 'overlays', 'species', 'sound', 'title', 'maps', 'retouch', 'story', 'screens', 'localize', 'signs',
         'balance', 'storycopies', 'plan']


def load(name):
    return importlib.import_module(f'{__name__}.{name}')


def owned():
    return [load(n) for n in OWNED]
