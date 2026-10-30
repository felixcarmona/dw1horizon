#!/usr/bin/env python3
"""The malloc3 heap of a built executable against what the screens were measured needing.

  heapcheck.py ELF.map [--csv docs/data/memory-budget.csv] [--warn BYTES]

The heap is what main leaves between its bss and the stack: (main_BSS_END & ~15) + 16 (initializeHeap) up to the
stack's bottom (_stack_addr - _stack_size KB). Every byte a patch adds to the main executable (code, strings, tables,
bss) comes off it. The sweep (tools/membudget.py, docs/data/memory-budget.csv) measured each screen's free heap with
the executable of its day; with a smaller heap now, each screen has that much less: projected free = heap_free -
(heap_total of the sweep - heap now). Below 0 a screen's loads fail and its loading never ends (the game hangs).

Prints the heap, how much it shrank since the sweep and the tightest screens. Exit 1 when a screen's projected free
heap is below 0, unless HEAP_OK=1 (tools/build-full.sh runs it after each executable build); a warning under --warn.
"""
import argparse, csv, os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def heap_of_map(path):
    text = open(path, errors='replace').read()

    def word(name):
        m = re.search(r'^\s+0x[0-9a-f]+\s+' + name + r' = \.\n\s+0x[0-9a-f]+\s+0x4 LONG (0x[0-9a-f]+)', text, re.M)
        return int(m.group(1), 16) if m else None
    end, stack, size = word('_end'), word('_stack_addr'), word('_stack_size')
    if None in (end, stack, size):
        sys.exit(f'{path}: no _end / _stack_addr / _stack_size words (not an ELF map of the main executable?)')
    return ((stack - (size << 10)) & ~0xF) - ((end & ~0xF) + 0x10)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('map')
    ap.add_argument('--csv', default=os.path.join(ROOT, 'docs/data/memory-budget.csv'))
    ap.add_argument('--warn', type=int, default=8192, help='warn when a screen would keep less free heap (default 8 KB)')
    a = ap.parse_args()
    now = heap_of_map(a.map)
    rows = [r for r in csv.DictReader(open(a.csv)) if r.get('ok') == '1' and r.get('heap_free')]
    swept = min(int(r['heap_total']) for r in rows)
    shrink = swept - now
    proj = sorted((int(r['heap_free']) - max(0, shrink), r['map'], r['name'], r['hour']) for r in rows)
    print(f'heap: {now} bytes ({now / 1024:.1f} KB); the sweep ({os.path.relpath(a.csv, ROOT)}) had {swept} '
          f'({"-" if shrink > 0 else "+"}{abs(shrink)} since)')
    print('tightest screens (free heap they would keep now): ' +
          ', '.join(f'{m} {n} {h}h {f}' for f, m, n, h in proj[:4]))
    worst = proj[0][0]
    if worst < 0:
        msg = (f'heapcheck: {proj[0][1]} would be {-worst} bytes short of heap: its loads fail and the game hangs. '
               'Take the bytes back (an overlay, a disc file read on demand, GENERAL_BUFFER) or set HEAP_OK=1 '
               '')
        if os.environ.get('HEAP_OK') == '1':
            print('warning: ' + msg)
        else:
            sys.exit(msg)
    elif worst < a.warn:
        print(f'warning: heapcheck: {proj[0][1]} keeps only {worst} bytes of free heap (under {a.warn}); '
              'new screens and bigger models have less room than the originals')


if __name__ == '__main__':
    main()
