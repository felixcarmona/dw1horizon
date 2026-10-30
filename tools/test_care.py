#!/usr/bin/env python3
"""test_care.py: the per-species care overrides (balance.care_overrides): absolute, +n / -n, +n% / -n%, null, and what is refused."""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import balance as B

RULES = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'content', 'tables', 'care-rules.json')))['careRules']
IDX = {p: i for i, p in enumerate(B.NAMED_RULES['careRules']) if p}
fails = 0


def check(name, got, want):
    global fails
    ok = got == want; fails += not ok
    print(f'{"ok " if ok else "BAD"} {name:58s} got {got} expected {want}')


def rows(care, rules=RULES):
    return B.care_overrides({3: {'care': care}}, rules)


def refused(care, text, rules=RULES):
    try: rows(care, rules)
    except SystemExit as e: return text in str(e)
    return False


g = lambda path: B._get(RULES, path)
check('no care: no rows', B.care_overrides({3: {}, 4: {'name': 'x'}}, RULES), [])
check('absolute', rows({'sickness': {'perTry': 9}}), [[3, IDX['sickness.perTry'], 9]])
check('delta +', rows({'sickness': {'perTry': '+3'}}), [[3, IDX['sickness.perTry'], g('sickness.perTry') + 3]])
check('delta -', rows({'sleep': {'later': {'disciplineLoss': '-1'}}}), [[3, IDX['sleep.later.disciplineLoss'], g('sleep.later.disciplineLoss') - 1]])
check('percent -20% of an hour (in frames: 1200 -> 960)', rows({'sickness': {'period': '-20%'}}), [[3, IDX['sickness.period'], 960]])
check('a time as text: "30m" = 600 frames', rows({'sickness': {'period': '30m'}}), [[3, IDX['sickness.period'], 600]])
check('a time as text: "1h30m" = 1800 frames', rows({'sickness': {'period': '1h30m'}}), [[3, IDX['sickness.period'], 1800]])
check('a time in game seconds: 90 = 30 frames', rows({'sickness': {'period': 90}}), [[3, IDX['sickness.period'], 30]])
check('a time plus text: "+10m" on an hour', rows({'sickness': {'period': '+10m'}}), [[3, IDX['sickness.period'], 1200 + 200]])
check('a time minus text: "-30s"', rows({'sickness': {'period': '-30s'}}), [[3, IDX['sickness.period'], 1200 - 10]])
check('a time off a 3 s step refused', refused({'sickness': {'period': '10s'}}, 'steps of 3 s'), True)
check('a time that is not a time refused', refused({'sickness': {'period': 'soon'}}, 'not a duration'), True)
check('an amount is not a time: "10m" refused', refused({'sickness': {'perTry': '10m'}}, 'not "+n"'), True)
check('percent +50% of 5 rounds to nearest (7.5 -> 8)', rows({'sickness': {'perTry': '+50%'}}), [[3, IDX['sickness.perTry'], 8]])
check('null switches the rule off', rows({'lifetime': {'period': None}}), [[3, IDX['lifetime.period'], -1]])
check('a zero is a value', rows({'poop': {'holdOffset': 0}}), [[3, IDX['poop.holdOffset'], 0]])
check('two species, sorted by id', [r[0] for r in B.care_overrides({9: {'care': {'poop': {'holdOffset': 1}}}, 3: {'care': {'poop': {'holdOffset': 2}}}}, RULES)], [3, 9])
check('unknown rule refused', refused({'sickness': {'nope': 1}}, 'unknown rule'), True)
check('-1 refused (use null)', refused({'sickness': {'perTry': -1}}, 'null'), True)
check('negative result refused', refused({'sickness': {'perTry': '-99'}}, 'resolves to'), True)
check('relative to a missing global refused', refused({'sickness': {'perTry': '+1'}}, 'no sickness.perTry', {}), True)
check('absolute with no global is fine', rows({'sickness': {'perTry': 4}}, {}), [[3, IDX['sickness.perTry'], 4]])
check('bad string refused', refused({'sickness': {'perTry': 'x'}}, 'not "+n"'), True)
check('too many rows refused', B.CARE_OVERRIDE_MAX, 192)
big = {i: {'care': {'poop': {'holdOffset': 1}, 'sickness': {'perTry': 1}}} for i in range(100)}
try: B.care_overrides(big, RULES); check('too many rows refused (200 > 192)', False, True)
except SystemExit as e: check('too many rows refused (200 > 192)', 'room for' in str(e), True)
print('PASS' if not fails else f'{fails} FAILED'); sys.exit(1 if fails else 0)
