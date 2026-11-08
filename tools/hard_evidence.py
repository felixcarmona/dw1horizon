#!/usr/bin/env python3
"""Export portable measurements from the real 2 MB HARD playtests."""
import argparse
import csv
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools import battle_audit as B


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--before', type=Path, default=Path('build/hard-primary-before/results.json'))
    parser.add_argument('--fights', type=Path, default=Path('build/hard-primary/results.json'))
    parser.add_argument('--out', type=Path, default=Path('docs/data/hard-difficulty'))
    parser.add_argument('--supplement', type=Path, action='append', default=[])
    args = parser.parse_args()
    rules = B.load('content/tables/battle-formulas.json')['battleFormulas']
    specialties = B.load('content/species/65-metaletemon.json')['specialties']
    factors = B.load('content/tables/type-factors.json')['typeFactors']
    records = []
    sources = [(args.before, 6, 'primary-before'), (args.fights, 12, 'primary-current')]
    sources.extend((path, None, f'supplement-{index + 1}')
                   for index, path in enumerate(args.supplement))
    for path, expected, run in sources:
        trials = json.loads(path.read_text())
        if expected is not None:
            assert len(trials) == expected, (path, len(trials), expected)
        assert len({r['case'] for r in trials}) == len(trials)
        for trial in trials:
            assert trial['ramBytes'] == 2097152 and not trial['expandedRAM']
            assert trial['finished']
            # Optional strategy trials predate the final ceiling-rounding fix.
            # Their incoming ordinary hits must also equal the final formula.
            if trial['mode'] == 'HARD':
                for hit in trial['hits']:
                    if hit['partner'] or hit['finisher']:
                        continue
                    technique = B.load(next((ROOT / 'content/techniques').glob(f"{hit['move']}-*.json")).relative_to(ROOT))
                    total = sum(factors[B.ELEMENTS.index(technique['element'])][B.ELEMENTS.index(x)] for x in specialties)
                    natural = B.damage(hit['power'], hit['offense'], hit['defense'], total,
                                       rules['damage'], roll=hit['roll'], counter=hit['move'] == 45)
                    zero = B.damage(hit['power'], hit['offense'], 0, total,
                                    rules['damage'], roll=hit['roll'])
                    floor = (zero * rules['hard']['minimumDamagePercent'] + 99) // 100
                    assert hit['damage'] == max(natural, floor), (run, trial['case'], hit)
            frames = {hit['frame'] for hit in trial['hits'] if not hit['partner']}
            incoming = [hit for hit in trial['appliedHits']
                        if hit['partnerTarget'] and hit['frame'] in frames]
            record = {key: trial[key] for key in (
                'beforeDefenseCurve', 'case', 'kind', 'profile', 'mode', 'loadout',
                'partnerStats', 'partnerMaxHP', 'partnerMaxMP', 'ramBytes',
                'partnerKnockedOut', 'minimumObservedHP', 'combatSeconds', 'heap')}
            native_checks = [hit for hit in incoming if hit.get('zeroDefenseNative', 0) > 0]
            for hit in native_checks:
                assert hit['damage'] * 100 >= hit['zeroDefenseNative'] * rules['hard']['minimumDamagePercent']
            record['nativeMinimumCheckedHits'] = len(native_checks)
            record['incomingDirectHits'] = incoming
            record['damageCalculations'] = trial['hits']
            record['run'] = run
            record['screen'] = trial.get('screen', 153 if trial['kind'] == 'wild' else 104)
            record['playerActions'] = {key: trial.get(key, default) for key, default in (
                ('recoveriesCarried', 0), ('recoveriesRemaining', None),
                ('recoveryThrows', []), ('finisherInput', False), ('muscleFirst', False))}
            records.append(record)
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / 'live-fights.json').write_text(json.dumps(records, indent=2) + '\n')
    with (args.out / 'live-fights.csv').open('w', newline='') as stream:
        writer = csv.writer(stream, lineterminator='\n')
        writer.writerow(('Run', 'Before Defense curve', 'Encounter', 'Screen', 'Partner', 'Difficulty', 'Loadout',
                         'Combat seconds', 'Knocked out', 'Direct hits taken',
                         'Minimum direct hit', 'Maximum direct hit', 'Direct damage taken'))
        for trial in records:
            hits = [hit['damage'] for hit in trial['incomingDirectHits']]
            writer.writerow((trial['run'], trial['beforeDefenseCurve'], trial['kind'], trial['screen'], trial['profile'],
                             trial['mode'], '/'.join(map(str, trial['loadout'])), trial['combatSeconds'], trial['partnerKnockedOut'],
                             len(hits), min(hits) if hits else '', max(hits) if hits else '', sum(hits)))
    print(f'Exported {len(records)} real 2 MB trials')


if __name__ == '__main__':
    main()
