"""Compiler capability names backed by the shared allocation registry."""


def profile_pool(name):
    from .alloc import LOCK_PROFILES
    if name not in LOCK_PROFILES:
        raise ValueError(f'unknown allocation profile {name!r}; use original or extended-save')
    return name
