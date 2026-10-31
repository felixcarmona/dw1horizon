"""Arrival safety from lowered placements and resolved maps; never edits build content."""
from dataclasses import dataclass, field
import math
import os
from pathlib import Path


@dataclass
class Result:
    rows: list = field(default_factory=list)
    unknown: list = field(default_factory=list)
    skipped: int = 0

    @property
    def failed(self):
        return [row for row in self.rows if row['close'] and row['enforced']]


def analyze(placements, resolve_map, source_pos=lambda pos: pos, *, margin=300,
            enforce_sources=(), default_range=1000):
    """Read compiler placement tuples without consuming/mutating their stats.

    Preserve the former author audit's default 1000 and strict distance comparison.
    Additional source coverage is observational until explicitly selected for enforcement.
    Repeated day/night declarations sharing a slot and location use the largest range.
    """
    result = Result()
    groups = {}
    selected = {str(Path(p).resolve()) for p in enforce_sources}
    for screen, slot, species, stats, pos, like in placements:
        if screen < 255:
            result.skipped += 1
            continue
        pos = source_pos(pos)
        try:
            model = resolve_map(screen, stats)
            x, z = stats['posX'], stats['posZ']
            arrivals = [(w['x'], w['z']) for w in model.warps if w['targetMap'] != -1]
            if not arrivals:
                raise ValueError('no target-bearing arrivals')
        except (OSError, KeyError, ValueError) as exc:
            result.unknown.append(dict(screen=screen, slot=slot, pos=pos, reason=str(exc)))
            continue
        key = (screen, slot, x, z)
        row = groups.setdefault(key, dict(screen=screen, slot=slot, x=x, z=z,
                    species=[], positions=[], range=0, arrivals=arrivals, enforced=False))
        row['species'].append(species)
        row['positions'].append(pos)
        row['range'] = max(row['range'], stats.get('trackingRange', default_range))
        row['enforced'] |= not selected or bool(pos and str(Path(pos[0]).resolve()) in selected)
    for key in sorted(groups):
        row = groups[key]
        row['distance'] = min(math.hypot(row['x'] - x, row['z'] - z) for x, z in row['arrivals'])
        row['close'] = row['distance'] < row['range'] + margin
        result.rows.append(row)
    return result


def resolve_map(screen, stats):
    from .. import backend as B
    import dwmap
    path = stats.get('map') or B.map_path(B.MAP_FILES[screen])
    return dwmap.MapFile(Path(path).read_bytes())


def suggestions(result, models, *, minimum_arrival=1350, minimum_other=600):
    """Source-positioned suggestions, with the former author's search thresholds.

    Geometry comes from tools/maps. The caller owns the maps and decides whether to
    accept a diff; this API never moves a placement or changes its tracking range.
    """
    from maps import reach
    changes = []
    spots = {(r['screen'], r['slot']): (r['x'], r['z']) for r in result.rows}
    for row in result.rows:
        if not row['close']:
            continue
        model = models[row['screen']]
        reachable = reach.reach(model, starts=row['arrivals'])
        best = None
        for i, value in enumerate(model.collision):
            if value != 0:
                continue
            x, z = i % 100 * 100 - 4950, 4950 - i // 100 * 100
            if (x, z) not in reachable:
                continue
            if min(math.hypot(x - a, z - b) for a, b in row['arrivals']) < minimum_arrival:
                continue
            if any(math.hypot(x - a, z - b) < minimum_other
                   for (screen, slot), (a, b) in spots.items()
                   if screen == row['screen'] and slot != row['slot']):
                continue
            candidate = (math.hypot(x - row['x'], z - row['z']), x, z)
            if best is None or candidate[0] < best[0]:
                best = candidate
        if best and best[0] < 3000:
            value = (best[1], best[2])
            spots[row['screen'], row['slot']] = value
            changes.extend((pos, 'at', value) for pos in row['positions'])
        else:
            value = max(150, int((row['distance'] - 350) // 50) * 50)
            changes.extend((pos, 'range', value) for pos in row['positions'])
    return changes


def suggestion_diffs(changes):
    """Use AST spans to show reviewable changes, including multiline declarations."""
    import ast
    import difflib
    from collections import defaultdict
    by_source = defaultdict(list)
    for pos, keyword, value in changes:
        if pos:
            by_source[str(pos[0])].append((pos[1], keyword, value))
    diffs = []
    for source, changes in sorted(by_source.items()):
        text = Path(source).read_text()
        # AST columns are UTF-8 byte offsets, not Python character offsets.
        raw = text.encode('utf-8')
        lines = raw.splitlines(keepends=True)
        offsets = [0]
        for line in lines:
            offsets.append(offsets[-1] + len(line))
        calls = [n for n in ast.walk(ast.parse(text, source)) if isinstance(n, ast.Call)]
        edits = {}
        for lineno, keyword, value in changes:
            choices = [n for n in calls if n.lineno <= lineno <= n.end_lineno
                       and (isinstance(n.func, ast.Attribute) and n.func.attr == 'npc'
                            or isinstance(n.func, ast.Name) and n.func.id == 'take_over')]
            if not choices:
                raise ValueError(f'{source}:{lineno}: cannot locate the lowered placement for a suggestion')
            call = min(choices, key=lambda n: (n.end_lineno - n.lineno, n.end_col_offset - n.col_offset))
            old = next((kw.value for kw in call.keywords if kw.arg == keyword), None)
            value = repr(value).encode()
            if old is not None:
                start = offsets[old.lineno - 1] + old.col_offset
                end = offsets[old.end_lineno - 1] + old.end_col_offset
            else:
                start = end = offsets[call.end_lineno - 1] + call.end_col_offset - 1
                prefix = b' ' if raw[:start].rstrip().endswith(b',') else (b', ' if call.args or call.keywords else b'')
                value = prefix + keyword.encode() + b'=' + value
            edits[start, end] = value
        for (start, end), value in sorted(edits.items(), reverse=True):
            raw = raw[:start] + value + raw[end:]
        diffs.extend(difflib.unified_diff(text.splitlines(keepends=True), raw.decode().splitlines(keepends=True),
                                        fromfile=source, tofile=source + ' (suggested)'))
    return ''.join(diffs)


def run(args):
    import json
    from .. import backend as B, build
    B.configure(screen_dirs=args.screen_content.split(os.pathsep) if args.screen_content else [],
                maps=args.maps.split(os.pathsep) if args.maps else [], locks_read_only=True)
    try:
        prog = build.compile_sources(args.files, exe=args.exe, lang=args.lang,
                                     text=args.text, lock=args.lock, profile=args.profile or 'original',
                                     text_source='ours')
    except build.DwsErrors as exc:
        import sys
        for error in exc.errors:
            print(error.render(), file=sys.stderr)
        return True
    models = {}
    def resolved(screen, stats):
        model = resolve_map(screen, stats)
        models[screen] = model
        return model
    result = analyze(prog.b.placements, resolved, build.source_pos, margin=args.margin,
                     enforce_sources=args.enforce_source)
    for row in result.rows:
        pos = row['positions'][0]
        where = f'{pos[0]}:{pos[1]}' if pos else 'unknown source'
        status = ('FAIL' if row['enforced'] else 'advisory') if row['close'] else 'ok'
        print(f"{where}: screen {row['screen']} slot {row['slot']} at ({row['x']}, {row['z']}) "
              f"range {row['range']}: nearest arrival {row['distance']:.0f} {status}")
    for row in result.unknown:
        print(f"incomplete: screen {row['screen']} slot {row['slot']}: {row['reason']}")
    advisory = sum(row['close'] and not row['enforced'] for row in result.rows)
    print(f'{len(result.rows)} placement groups checked; {len(result.failed)} enforced failures, '
          f'{advisory} advisory, {len(result.unknown)} unknown, {result.skipped} original-screen placements skipped')
    if args.json:
        path = Path(args.json)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(dict(rows=result.rows, unknown=result.unknown,
                                       skipped=result.skipped), indent=2) + '\n')
    if args.suggest:
        print(suggestion_diffs(suggestions(result, models)), end='')
    return bool(result.failed)
