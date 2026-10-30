"""Allocation of flags (triggers) and variables (pstats) with explicit pinning, collision errors, arrays
and an append-only lock file (story.lock), against a capacity profile.

Profile `original` (the original executable; docs/mods/scripts.md "Free triggers and pstats"):
  persistent flag   trigger 717-799 (83, saved to the memory card)
  persistent var    pstats 7-15 and 20 (the only free pstats below 35, saved; u8 only)
  session/temp var  pstats 45-93 (not saved; 94-99 are the compiler's scratch registers; u8 only)
Profile `extended-save` (extended saved state; three blocks per save slot):
  persistent flag   story bits 0-16383 (trigger 800 + n)       persistent var   v0-v1023, i32 (saved)
  session/screen/temp var   s0-s255, i32 (scene variables: not saved, cleared on a screen change and a load)
  scratch           pstats 45-93: the compiler's own temporaries (loop counters, sub arguments)
Legacy lock identifiers are accepted without changing serialized lock bytes.
An `alias` names something the game already uses (no allocation, no collision check)."""
import json, os
from .diag import DwsError

TYPE_BITS = {'u8': 8, 'i8': 8, 'u16': 16, 'i16': 16, 'u32': 32, 'i32': 32}


class Pool:
    def __init__(self, numbers, label, width=8, unit='pstat'):
        self.numbers = list(numbers); self.label = label; self.width = width; self.unit = unit

    def describe(self):
        n = self.numbers
        if not n: return 'none'
        return f'{n[0]}-{n[-1]}' if n == list(range(n[0], n[-1] + 1)) else ', '.join(map(str, n))


ORIGINAL_POOLS = {
    ('flag', 'save'): Pool(range(717, 800), 'trigger', 1, 'trigger'),
    ('var', 'save'): Pool([7, 8, 9, 10, 11, 12, 13, 14, 15, 20], 'saved pstat', 8),
    ('var', 'temp'): Pool(range(45, 94), 'scratch pstat', 8),
}
EXTENDED_SAVE_POOLS = {
    # Three blocks per slot: five slots per card. Preserve the existing saved capacities.
    ('flag', 'save'): Pool(range(0, 16384), 'story bit', 1, 'bit'),
    ('var', 'save'): Pool(range(0, 1024), 'story variable', 32, 'variable'),
    ('var', 'temp'): Pool(range(0, 256), 'scene variable', 32, 'variable'),
    ('var', 'scratch'): Pool(range(45, 94), 'scratch pstat', 8),
}
PROFILES = {'original': ORIGINAL_POOLS, 'extended-save': EXTENDED_SAVE_POOLS}
# These identifiers occur in existing story locks and compiler callers. Keep the lock format stable.
PROFILE_ALIASES = {'tier0': 'original', 'tier2': 'extended-save', 'tier2xl': 'extended-save'}
LOCK_PROFILES = {'original': 'tier0', 'extended-save': 'tier2'}
PROFILES.update({old: PROFILES[name] for old, name in PROFILE_ALIASES.items()})
STORY_FLAG_BASE = 800          # extended saved state: triggers from here on are the story bits (include/dw/memmap.h)
SCENE_VAR = 0x8000             # extended saved state: variable index of scene variable n

# compatibility names
FREE_TRIGGERS = list(ORIGINAL_POOLS[('flag', 'save')].numbers)
FREE_SAVED_PSTATS = ORIGINAL_POOLS[('var', 'save')].numbers
FREE_TEMP_PSTATS = ORIGINAL_POOLS[('var', 'temp')].numbers
POOLS = {k: v.numbers for k, v in ORIGINAL_POOLS.items()}


class Allocator:
    def __init__(self, lock_path=None, profile='original'):
        profile = PROFILE_ALIASES.get(profile, profile)
        self.lock_path = lock_path; self.profile = profile; self.pools = PROFILES[profile]
        self.lock = {'flags': {}, 'vars': {}, 'temps': {}, 'sizes': {}, 'profile': LOCK_PROFILES[profile]}
        if profile != 'original': self.lock['scratch'] = {}
        if lock_path and os.path.exists(lock_path):
            self.lock.update(json.load(open(lock_path)))
            if self.lock.get('profile', LOCK_PROFILES['original']) != LOCK_PROFILES[profile]:
                raise DwsError(f'{lock_path} was written for profile {self.lock.get("profile")}, this build is {profile}',
                               None, 'use one lock file per profile (story.lock, story.extended-save.lock)')
        self.used = {}          # (what, scope, number) -> qualified name
        self.table = {}         # qualified name -> number (first number of an array)
        self.sizes = {}         # qualified name -> element count
        self.widths = {}        # qualified name -> bits
        self.new = {}           # allocations that are not in the lock yet
        self.reserved = {}      # pool key -> numbers taken away by `reserve` (engine/other mods)

    @staticmethod
    def section(what, scope):
        if what == 'flag': return 'flags'
        return 'vars' if scope == 'save' else ('scratch' if scope == 'scratch' else 'temps')

    def pool(self, what, scope):
        return self.pools[(what, scope)]

    def engine_number(self, what, scope, n):
        """What the instruction operand is for allocation number n: original profile, the number itself; extended saved state, a story flag
        is the trigger 800 + n and a scene variable the index 0x8000 + n (persistent variables and scratch pstats: n)."""
        if self.profile == 'original': return n
        if what == 'flag' and scope == 'save': return STORY_FLAG_BASE + n
        if what == 'var' and scope == 'temp': return SCENE_VAR + n
        return n

    def capacity(self):
        """{pool name: (used, total)} for the report."""
        out = {}
        for (what, scope), p in self.pools.items():
            used = sum(1 for (w, s, n) in self.used if (w, s) == (what, scope))
            out[f'{scope} {what}'] = (used, len(p.numbers), p.describe())
        return out

    def declare(self, what, scope, qname, pin, alias, node, count=None, vtype=None):
        n_el = count or 1
        if alias:
            if pin is None: raise DwsError(f'alias {what} {qname}: the number it stands for is required', node.pos)
            return pin
        if scope == 'scratch' and ('var', 'scratch') not in self.pools:
            scope = 'temp'               # original profile: the compiler's temporaries share the scratch pstats with `temp var`
        pool = self.pool(what, scope)
        bits = TYPE_BITS.get(vtype or 'u8', None)
        if what == 'var' and vtype and vtype not in TYPE_BITS and not node.__dict__.get('enum_ok'):
            raise DwsError(f'unknown variable type "{vtype}"', node.pos, 'types: ' + ', '.join(TYPE_BITS) + ' or an enum')
        if what == 'var' and bits and bits > pool.width:
            raise DwsError(f'variable "{qname}": {vtype} needs {bits} bits, but a {pool.label} of the {self.profile} profile holds {pool.width}',
                           node.pos, f'{vtype} variables require the extended-save profile; with the original profile use u8 or split the value')
        if what == 'flag' and vtype:
            raise DwsError(f'flag "{qname}" has no type', node.pos)
        sec = self.lock[self.section(what, scope)]
        sizes = self.lock['sizes']
        if qname in sizes and sizes[qname] != n_el and qname in sec:
            raise DwsError(f'{what} "{qname}" has {n_el} element(s) but story.lock says {sizes[qname]}', node.pos,
                           'arrays only grow by adding a new name: the numbers after the array may already belong to others')
        nums = set(pool.numbers)
        if pin is not None:
            if any(pin + k not in nums for k in range(n_el)):
                from .py.lower import LINEMAP
                lowered = bool(node.pos and os.path.abspath(str(node.pos[0])) in LINEMAP)
                raise DwsError(f'{what} "{qname}" pinned to {pin}{f"..{pin + n_el - 1}" if n_el > 1 else ""}, which is not in the free range '
                               f'({pool.describe()})', node.pos,
                               f'a mod\'s [save] range in its mod.toml must be inside the free numbers (a number past them is the '
                               f'game\'s own or does not exist)' if lowered else
                               f'use `alias {what} {qname} = {pin};` to name something the game already uses')
            if qname in sec and sec[qname] != pin:
                raise DwsError(f'{what} "{qname}" is pinned to {pin} but story.lock says {sec[qname]}', node.pos,
                               'saves made with the locked number would read the wrong value; fix the pin or the lock')
            n = pin
        elif qname in sec:
            n = sec[qname]
            if any(n + k not in nums for k in range(n_el)):
                raise DwsError(f'story.lock gives {what} "{qname}" the number {n}, outside the free range', node.pos)
        else:
            taken = set()
            for q, v in sec.items():
                taken.update(range(v, v + sizes.get(q, 1)))
            n = self.first_run(pool, what, scope, n_el, taken)
            if n is None:
                have = sum(1 for p in pool.numbers if (what, scope, p) not in self.used and p not in taken)
                raise DwsError(f'no free {pool.label}s left for "{qname}": it needs {n_el}{" in a row" if n_el > 1 else ""}, '
                               f'{have} of {len(pool.numbers)} ({pool.describe()}) are free', node.pos,
                               f'the {self.profile} profile has few of them; ' +
                               ('compile for extended saved state (bigger pools, new opcodes) or ' if self.profile == 'original' else '') +
                               'reuse a variable, use a `temp var`, or remove unused declarations (see `dws report`)')
        for k in range(n_el):
            key = (what, scope, n + k)
            if key in self.used:
                raise DwsError(f'{what} "{qname}" collides with "{self.used[key]}": both are {self.label(what, n + k)}', node.pos,
                               'two names cannot share one trigger/pstat; remove one pin or change the lock')
            self.used[key] = qname if n_el == 1 else f'{qname}[{k}]'
        self.table[qname] = n; self.sizes[qname] = n_el; self.widths[qname] = bits or 1
        if qname not in sec: self.new[(self.section(what, scope), qname)] = n
        return n

    def first_run(self, pool, what, scope, n_el, taken):
        nums = pool.numbers
        for i in range(len(nums) - n_el + 1):
            run = nums[i:i + n_el]
            if run[-1] - run[0] != n_el - 1: continue
            if all((what, scope, p) not in self.used and p not in taken for p in run):
                return run[0]
        return None

    def label(self, what, n):
        u = self.pools[(what, 'save')].unit
        return f'{u} {n}' if what == 'flag' else f'{u if u != "pstat" else "pstat"} {"p" if self.profile == "original" else "v"}{n}'

    def write_lock(self, path):
        for (sec, q), n in self.new.items():
            self.lock[sec][q] = n
            if self.sizes.get(q, 1) > 1: self.lock['sizes'][q] = self.sizes[q]
        self.lock['profile'] = LOCK_PROFILES[self.profile]
        json.dump(self.lock, open(path, 'w'), indent=1, sort_keys=True); open(path, 'a').write('\n')
