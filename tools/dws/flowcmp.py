"""Control-flow equivalence of two pieces of script assembly (the same section written two ways).

A section is turned into a graph whose nodes are (instruction, dialog owner known on that path); unconditional
JUMP_TOs and label names disappear (they are edges), a SET_DIALOG_OWNER that sets the owner the path already has
is skipped (nothing changes), and the two graphs are compared by strong bisimulation (partition refinement):
every instruction that can run on one side can run on the other with the same operands, followed by the same choices.
Two sources that pass are the same program up to layout: jump threading, duplicated END_SECTIONs, dead code, a
loop test placed before or after its first body, redundant owner changes, and the way the tests of a condition are split into IFs
(an IF is one node per clause, as the engine folds them: `IF a, or b, else L` is `IF a` then `IF b` with the same then-code, and
`IF a, and b, else L` is `IF a, else L` followed by `IF b, else L`); but not the difference between two SHOW_TEXTBOX in a row, which
are one chained box, and two with a SET_DIALOG_OWNER between them, which are two."""
import re

ROW = re.compile(r'^\s+"(?:[^"\\]|\\.)*"\s*(?:;.*)?$')
LABEL = re.compile(r'^([A-Za-z_][\w.]*):\s*(?:;.*)?$')
INSTR = re.compile(r'^\s+([A-Z][A-Z0-9_]*)\b\s*(.*?)\s*(?:;.*)?$')
KEEPS_OWNER = {'PLAY_ANIMATION', 'DELAY', 'SET_TRIGGER', 'UNSET_TRIGGER', 'SET_PSTAT', 'ADD_TO_PSTAT', 'SHOW_TEXTBOX',
               'IF', 'ENTITY_LOOK_AT_ENTITY'}


def parse(lines):
    """-> (instructions [(op, args, rows)], {label: index}); rows are the quoted strings under an instruction."""
    ins = []; labels = {}
    for line in lines:
        if ROW.match(line):
            ins[-1][2].append(line.strip()); continue
        m = LABEL.match(line)
        if m: labels[m.group(1)] = len(ins); continue
        m = INSTR.match(line)
        if m: ins.append((m.group(1), m.group(2), []))
    return ins, labels


def clauses(args):
    """The clauses of an IF's operands, [(join, test)]: join is 'and', 'or' or '' (the first clause, or one that replaces the
    result so far). The engine (scriptIfInstruction) folds them left to right, without grouping and without side effects."""
    out = []
    for c in args.rpartition(', else ')[0].split(', '):
        j, _, rest = c.partition(' ')
        out.append((j, rest) if j in ('and', 'or') else ('', c))
    return out


FLIP = {'!=': '==', '<': '>=', '>': '<='}


def positive(test):
    """-> (the test without negation, negated): `not trigger 5` is `trigger 5` with the branches swapped, `p3 < 7` is `p3 >= 7`
    swapped (integer comparisons: exact). So `unless (c) J` and `if (!c) { J }` are one program."""
    if test.startswith('not '): return test[4:], True
    m = re.fullmatch(r'(.*) (!=|<|>) (\S+)', test)
    if m: return f'{m.group(1)} {FLIP[m.group(2)]} {m.group(3)}', True
    return test, False


def graph(lines):
    """-> (nodes {id: (label, successors)}, start id, set of instruction indexes reached)."""
    ins, labels = parse(lines)
    ids = {}; nodes = {}; reached = set()

    def lab(name, owner):
        """The node of a label; a label that is not in this text is of the original script (`original(L)`): a leaf."""
        name = name.strip()
        return node(labels[name], owner) if name in labels else ('EXT', name, owner)

    def node(i, owner):
        stack = []
        while True:                                   # jump threading and redundant owner changes
            if i >= len(ins): return ('END',)
            op, args, rows = ins[i]
            if op == 'JUMP_TO':
                reached.add(i)
                if i in stack: raise ValueError('a loop of jumps with no instruction')
                if args.strip() not in labels: return ('EXT', args.strip(), owner)
                stack.append(i); i = labels[args.strip()]; continue
            if op == 'SET_DIALOG_OWNER' and owner == args.strip():
                reached.add(i); i += 1; continue
            if op == 'IF': reached.add(i); return clause(i, owner, 0, False)     # the engine's result starts false
            return (i, owner)
    def clause(i, owner, k, v):
        """The node after the first k clauses of the IF at i gave v: the next clause the engine's left fold still needs (an `and`
        after false or an `or` after true cannot change the result: the clauses are pure reads), else the then or else branch."""
        cl = clauses(ins[i][1])
        while k < len(cl) and (cl[k][0] == 'and' and not v or cl[k][0] == 'or' and v): k += 1
        if k < len(cl): return ('C', i, owner, k)
        return node(i + 1, owner) if v else lab(ins[i][1].rpartition(', else ')[2], owner)
    todo = [node(0, None)]; start = todo[0]
    while todo:
        key = todo.pop()
        if key in nodes: continue
        if key == ('END',): nodes[key] = ('END_SECTION', ()); continue
        # a jump out of the text (to shared code, or to another section's entry): the code there runs with the dialog owner known
        # on this path (a SET_DIALOG_OWNER it starts with may be redundant), so the owner is part of the leaf
        if key[0] == 'EXT': nodes[key] = (f'GOTO_ORIGINAL {key[1]} owner={key[2]}', ()); continue
        if key[0] == 'C':                             # one clause of an IF: true and false successors
            _, i, owner, k = key
            succ = (clause(i, owner, k + 1, True), clause(i, owner, k + 1, False))
            test, negated = positive(clauses(ins[i][1])[k][1])
            if negated: succ = succ[::-1]
            nodes[key] = ('IF ' + test, succ); todo += succ; continue
        i, owner = key; op, args, rows = ins[i]; reached.add(i)
        if op in ('END_SECTION', 'END_SCRIPT', 'JUMP_RETURN', 'JUMP_TO_FILE'): nodes[key] = (op, ()); continue
        after = args.strip() if op == 'SET_DIALOG_OWNER' else (owner if op in KEEPS_OWNER else None)
        if op == 'JUMP_AND_LINK':                 # the callee runs, then the next instruction (owner unknown after a call)
            succ = [lab(args, None), node(i + 1, None)]; text = ''
        elif op in ('SWITCH', 'SWITCH_W'):         # one successor per label, and the instruction after it
            succ = [lab(t, None) for t in args.split(',')[1:]] + [node(i + 1, None)]; text = args.split(',')[0]
        elif op == 'SET_SELECTION':
            targets = [t.strip() for t in args.split(',')]
            succ = [lab(t, None) for t in targets] + [node(i + 1, None)]; text = ''
        else:
            succ = [node(i + 1, after)]; text = args
            # a SHOW_TEXTBOX whose next instruction in the bytes is another one is a CHAINED box (the engine, showTextbox: the opcode after
            # the text is 0x1A, so the page is not finished: the next page goes on with no close and no button); with a SET_DIALOG_OWNER
            # between them the first box ends and a new one is set up. The owner model above does not make these equal.
            if op == 'SHOW_TEXTBOX' and i + 1 < len(ins) and ins[i + 1][0] == 'SHOW_TEXTBOX': text += ' [chained]'
        nodes[key] = (' '.join([op, text] + rows), tuple(succ)); todo += succ
    return nodes, start, reached, ins


def bisimilar(a, b):
    """Strong bisimulation of two graphs (ordered successors). Returns (equal, classes)."""
    (na, sa), (nb, sb) = a, b
    allnodes = {('a', k): (v[0], tuple(('a', s) for s in v[1])) for k, v in na.items()}
    allnodes.update({('b', k): (v[0], tuple(('b', s) for s in v[1])) for k, v in nb.items()})
    colour = {k: v[0] for k, v in allnodes.items()}; count = len(set(colour.values()))
    while True:
        sig = {k: (colour[k], tuple(colour[s] for s in allnodes[k][1])) for k in allnodes}
        ids = {}; new = {k: ids.setdefault(s, len(ids)) for k, s in sig.items()}
        if len(ids) == count: break
        colour, count = new, len(ids)
    return colour[('a', sa)] == colour[('b', sb)], count


def compare(lines_a, lines_b):
    """-> dict: equal, and the numbers that describe the layout differences."""
    ga, gb = graph(lines_a), graph(lines_b)
    eq, classes = bisimilar((ga[0], ga[1]), (gb[0], gb[1]))
    def facts(g):
        nodes, start, reached, ins = g
        return {'instructions': len(ins), 'unreachable': len(ins) - len(reached),
                'nodes': len(nodes), 'jumps': sum(1 for x in ins if x[0] == 'JUMP_TO')}
    return {'equal': eq, 'classes': classes, 'a': facts(ga), 'b': facts(gb)}


def normalized(lines):
    """The instruction stream with every label reference replaced by the index of the instruction it names (and a final
    END_SECTION after a terminal one dropped): two sources with the same stream assemble to the same bytes at the same address."""
    ins, labels = parse(lines)
    names = sorted(labels, key=len, reverse=True)
    out = []
    for op, args, rows in ins:
        a = re.sub(r'[A-Za-z_][\w.]*', lambda m: f'@{labels[m.group(0)]}' if m.group(0) in labels else m.group(0), args)
        out.append((op, a, tuple(rows)))
    if len(out) > 1 and out[-1][0] == 'END_SECTION' and out[-2][0] in ('END_SECTION', 'END_SCRIPT', 'JUMP_TO', 'JUMP_RETURN', 'JUMP_TO_FILE') \
            and not any(v == len(out) - 1 for v in labels.values()):
        out.pop()
    return out


def same_layout(lines_a, lines_b):
    return normalized(lines_a) == normalized(lines_b)
