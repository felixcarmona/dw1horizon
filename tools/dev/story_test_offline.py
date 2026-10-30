"""The checks of tools/dev/story_test.py that need no emulator (called by tools/selftest.sh, a few seconds):
scenario files parse and resolve, every instruction of every script decodes the way the tracer decodes it,
and the trace normaliser locates sections and sees a changed operand byte."""

from pathlib import Path as _DevPath
import sys as _dev_sys
_DEV_ROOT = str(next(p for p in _DevPath(__file__).resolve().parents if (p / "tools").is_dir()))
_dev_sys.path.insert(0, _DEV_ROOT)
_dev_sys.path.insert(0, str(_DevPath(_DEV_ROOT) / "tools"))
import os, sys, hashlib

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from tools.dev import story_test as T; from dws import bytecode


def check_scenarios():
    scs = T.scenarios(); assert scs, 'no scenarios'
    for name, s in scs.items():
        assert os.path.basename(s['_path']) == name + '.json', f'{name}: file name'
        for k in ('pre', 'run'):
            for st in s.get(k, []): T.parse_step(st)
        assert s.get('run'), f'{name}: empty run'
        e = s.get('expect', {}).get('digest')
        assert e is None or len(e) == 40, f'{name}: bad digest'
    return f'{len(scs)} scenarios parse'


END_OPS = (0x15, 0x16, 0x17, 0xFE, 0xFF)      # JUMP_RETURN, JUMP_TO, JUMP_TO_FILE, END_SECTION, END_SCRIPT: no fall-through


def decode_reachable(b):
    """Follows the control flow from every section start (fall-through and jump targets) and decodes each instruction on the way:
    returns {offset: (length, op)}."""
    _, secs = bytecode.parse_header(b); seen = {}; todo = [o for _, o in secs]
    while todo:
        p = todo.pop()
        while p not in seen:
            if p >= len(b): raise ValueError(f'runs off the end at {p:#x}')
            if b[p] == 0x12 and b[p + 1] == 0:      # END_SELECTION: the cancel path runs into the 00 that ends the script
                seen[p] = (2, 0x12); break
            n, tg = bytecode.instr_length(b, p)
            if n is None: raise ValueError(f'unknown op {b[p]:02x} at {p:#x}')
            seen[p] = (n, b[p]); todo += tg
            if b[p] in END_OPS: break
            p += n
    return seen, secs


def check_decode():
    d = T.load_discs()['orig']; sc = T.Scripts(d['dg'], d['maphead']); n = 0
    for sid in sorted(sc.raw):
        b = sc.raw[sid]
        try:
            ins, secs = decode_reachable(b)
        except Exception as e:
            raise AssertionError(f'script {sid}: {e}')
        for p, (ln, op) in ins.items():
            for pos in T.label_positions(b, p):
                assert p < pos + 2 <= p + ln, f'script {sid} {p:#x}: label field outside the instruction'
        n += len(ins)
    return f'{n} reachable instructions of {len(sc.raw)} scripts decode; label fields lie inside their instructions'


def raw_trace(sc, sid, sec, limit=40):
    """A synthetic run: the first `limit` instructions of a section in address order, as the Lua tracer would log them."""
    b = sc.raw[sid]; start = dict((s, o) for o, s in sc.sections(sid))[sec]; p = start; lines = []
    for i in range(limit):
        n, _ = bytecode.instr_length(b, p)
        ln = 300 if b[p] in (0x10, 0x1A, 0x18, 0x19, 0x6B, 0x93) else 24
        lines.append(f'I {i} {sid} {p} {b[p]:02x} 0 {b[p:p + ln].hex()}')
        if b[p] in (0xFE, 0xFF): break
        p += n
    return '\n'.join(lines)


def check_normalise():
    d = T.load_discs()['orig']; sc = T.Scripts(d['dg'], d['maphead'])
    sid, sec = 178, 5
    ev = T.parse_trace(raw_trace(sc, sid, sec), sc)
    assert len(ev) > 20 and all(e['sec'] == sec for e in ev if e['kind'] == 'I'), 'sections not located'
    base = T.digest(ev)
    # a changed operand changes the digest; a changed jump target field is named by section+offset, not by number
    b = bytearray(sc.raw[sid]); off = dict((s, o) for o, s in sc.sections(sid))[sec]
    n, _ = bytecode.instr_length(bytes(b), off); b[off + n - 1] ^= 1
    sc2 = T.Scripts(d['dg'], d['maphead']); sc2.raw[sid] = bytes(b)
    first = T.parse_trace(raw_trace(sc2, sid, sec), sc2)
    assert T.digest(first) != base or b[off] in (0xFE,), 'a changed byte is not seen'
    return f'normaliser: {len(ev)} events, digest {base[:12]}'


def run():
    fails = 0
    for f in (check_scenarios, check_decode, check_normalise):
        try:
            print('  ' + f())
        except Exception as e:
            fails += 1; print(f'  FAIL {f.__name__}: {e}')
    sys.exit(1 if fails else 0)


if __name__ == '__main__':
    run()
