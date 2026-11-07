"""Declared unit ordering, separate from recorder worker assignment."""
from pathlib import Path


def same_group(left, right):
    return bool(left.get('order_group')) and (left['step'], left['order_group']) == (
        right['step'], right.get('order_group'))


def groups(specs):
    """Ordinary groups keep state; explicitly prepared-snapshot units may run apart."""
    tasks, ordered, policies = [], {}, {}
    for spec in specs:
        group = spec.get('order_group')
        snapshot = bool(spec.get('record_snapshot'))
        if group:
            identity = (spec['step'], group)
            if identity in policies and policies[identity] != snapshot:
                raise RuntimeError(f'inconsistent snapshot policy: {identity}')
            policies[identity] = snapshot
        if not group or snapshot:
            tasks.append([spec])
        else:
            if identity not in ordered:
                ordered[identity] = []
                tasks.append(ordered[identity])
            ordered[identity].append(spec)
    return tasks


def stateful_peers(left, right):
    return same_group(left, right) and not left.get('record_snapshot') and not right.get('record_snapshot')


def validate_reads(jobs):
    for job in jobs:
        reads = set(job['existed'])
        for sibling in jobs:
            if sibling is job or stateful_peers(job, sibling) or (job.get('record_snapshot') and sibling.get('record_snapshot')):
                continue
            conflict = (reads & set(sibling['writes'])) - set(job['writes'])
            conflict |= reads & set(sibling['removes'])
            if conflict:
                raise RuntimeError(f"dependent sibling units: {job['name']}, {sibling['name']}: {sorted(conflict)}")


def merge_operations(results, digest):
    """Validate every writer pair, then choose the canonical last operation."""
    history, final = {}, {}
    for result in results:
        job = result['graph']
        operations = [(name, None) for name in job['removes']]
        operations += [(name, Path(result['artifact']) / name) for name in job['writes']]
        for name, source in operations:
            value = None if source is None else (digest(source), source.stat().st_mode & 0o7777)
            for previous, old_value in history.get(name, []):
                if not same_group(previous, job) and old_value != value:
                    raise RuntimeError(f"conflicting recorder writes: {job['name']}: {name}")
            history.setdefault(name, []).append((job, value))
            final[name] = source
    return final
