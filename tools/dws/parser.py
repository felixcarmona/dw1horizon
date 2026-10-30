"""Parser: tokens -> AST (plain Node objects with .kind and .pos)."""
from .diag import DwsError
from .lexer import lex


class Node:
    def __init__(self, kind, tok, **kw):
        self.kind = kind
        self.pos = tok.pos if hasattr(tok, 'pos') else tok
        self.__dict__.update(kw)

    def __repr__(self):
        return 'Node(%s)' % ', '.join(f'{k}={v!r}' for k, v in self.__dict__.items() if k != 'pos')


INCLUDED = []          # files pulled in by `include`, for the dependency report
BIN_PREC = [['~>'], ['||'], ['&&'], ['==', '!=', 'in'], ['<', '<=', '>', '>='], ['+', '-']]
DUR_UNITS = {'s': 20, 'sec': 20, 'secs': 20, 'seconds': 20, 'ticks': 1, 'tick': 1}


class Parser:
    def __init__(self, src, fname):
        self.file = fname
        self.t = lex(src, fname); self.i = 0

    # ---- token helpers
    @property
    def cur(self):
        return self.t[self.i]

    def peek(self, k=1):
        return self.t[min(self.i + k, len(self.t) - 1)]

    def at(self, val, kind=None):
        c = self.cur
        return c.val == val and c.kind in (('op', 'id') if kind is None else (kind,))

    def accept(self, val):
        if self.at(val):
            self.i += 1; return True
        return False

    def next(self):
        c = self.cur; self.i += 1; return c

    def expect(self, val, why=None):
        if not self.at(val):
            c = self.cur
            found = 'end of file' if c.kind == 'eof' else f'"{c.val}"'
            raise DwsError(f'expected "{val}", found {found}' + (f' {why}' if why else ''), c.pos)
        return self.next()

    def label_ref(self):
        """A label of this event, or `original(L)`: a label of the original script outside the event -> (name, external)."""
        n = self.ident('a label')
        if n.val == 'original' and self.at('('):
            self.i += 1; m = self.ident('a label of the original script'); self.expect(')'); return m.val, True
        return n.val, False

    def ident(self, what='a name'):
        c = self.cur
        if c.kind != 'id':
            raise DwsError(f'expected {what}, found "{c.val}"', c.pos)
        self.i += 1; return c

    # ---- file
    def parse_file(self):
        items = []
        while self.cur.kind != 'eof':
            items.append(self.item())
        return items

    def item(self):
        c = self.cur
        if c.kind != 'id':
            raise DwsError(f'unexpected "{c.val}" at the top level', c.pos,
                           'expected flag, var, const, fn, script, place, import or module')
        pub = False
        if c.val == 'pub':
            pub = True; self.i += 1; c = self.cur
        w = c.val
        if w == 'module':
            self.i += 1; name = self.dotted(); self.expect(';')
            return Node('module', c, name=name)
        if w == 'import':
            self.i += 1; s = self.cur
            if s.kind != 'str': raise DwsError('import needs a file name in quotes', s.pos)
            self.i += 1; self.expect(';'); return Node('import', c, path=s.val)
        if w in ('flag', 'var', 'temp', 'session', 'save', 'alias', 'persistent', 'screen'):
            return self.decl(pub)
        if w == 'const':
            self.i += 1; n = self.ident(); self.expect('='); e = self.expr(); self.expect(';')
            return Node('const', c, name=n.val, expr=e, pub=pub, ntok=n)
        if w in ('fn', 'sub'):
            return self.fn(pub)
        if w == 'routine':
            self.i += 1; n = self.ident(); self.expect('='); e = self.cur
            if e.kind != 'num': raise DwsError('a routine number is expected', e.pos)
            self.i += 1; self.expect(';'); return Node('routine', c, name=n.val, num=e.val, pub=pub)
        if w == 'enum':
            return self.enum(pub)
        if w == 'group':
            return self.group(pub)
        if w == 'script':
            return self.script()
        if w == 'maphead':
            self.i += 1
            if self.at('{'):                          # maphead { section(117) replace { ... } }: sections of MAPHEAD.SCN as events
                self.i += 1; body = []
                while not self.at('}'):
                    if self.cur.kind == 'eof': raise DwsError('maphead block never closed', c.pos)
                    body.append(self.script_item())
                self.expect('}')
                return Node('script', c, body=body, text=None, id='maphead', new_for=None, empty=False, lossless=False)
            if self.at('port'):
                self.i += 1; return Node('maphead_port', c, body=self.port_body(c))
            if not self.at('lossless'): raise DwsError('expected "maphead lossless { ... }" or "maphead port { ... }"', self.cur.pos)
            self.i += 1; self.expect('{'); raw = self.next()
            if raw.kind != 'raw': raise DwsError('lossless block expected', raw.pos)
            self.expect('}'); return Node('maphead_lossless', c, text=raw.val, line=raw.line)
        if w == 'place':
            st = self.stmt_call_or_expr(); return Node('place', c, call=st.expr)
        if w == 'city':                                   # city { prosperity, top_map, ... }: docs/mods/city-rules.md
            from . import city
            self.i += 1; return city.parse_city(self, c)
        raise DwsError(f'unexpected "{w}" at the top level', c.pos,
                       'expected flag, var, const, fn, script, place, import or module')

    def dotted(self):
        parts = [self.ident().val]
        while self.accept('.'): parts.append(self.ident().val)
        return '.'.join(parts)

    SCOPES = {'persistent': 'save', 'save': 'save', 'session': 'temp', 'temp': 'temp', 'screen': 'temp'}

    def decl(self, pub):
        """[alias] [persistent|session|temp|screen] flag|var [N] name [: type] [= pin];"""
        c = self.cur; alias = False; scope = 'save'; scope_word = None
        if self.at('alias'): alias = True; self.i += 1
        if self.cur.val in self.SCOPES:
            scope_word = self.cur.val; scope = self.SCOPES[scope_word]; self.i += 1
        k = self.cur
        if k.val not in ('flag', 'var'):
            raise DwsError('expected "flag" or "var"', k.pos)
        self.i += 1; count = None
        if self.accept('['):
            e = self.cur
            if e.kind != 'num': raise DwsError('the size of an array is a number: flag[16] name', e.pos)
            self.i += 1; count = e.val; self.expect(']')
        n = self.ident('the name of the ' + k.val)
        ty = None
        if self.accept(':'): ty = self.ident('a type (u8, u16, i16, u32, i32 or an enum)').val
        pin = None
        if self.accept('='):
            p = self.cur
            if p.kind != 'num': raise DwsError('a pinned number is expected after "="', p.pos)
            pin = p.val; self.i += 1
        self.expect(';')
        return Node('decl', c, what=k.val, name=n.val, pin=pin, alias=alias, scope=scope, scope_word=scope_word,
                    pub=pub, ntok=n, count=count, vtype=ty, group=None)

    def port_body(self, c):
        """`port { tail; entry 254 sec254; statements and labels }`: a whole script as one statement per instruction."""
        o = self.expect('{'); out = []
        while not self.at('}'):
            if self.cur.kind == 'eof': raise DwsError('port block never closed', o.pos, 'missing "}"')
            if self.at('tail') and self.peek().val == ';':
                t = self.next(); self.i += 1; out.append(Node('tail', t)); continue
            if self.at('include') and self.peek().kind == 'str':
                t = self.next(); rel = self.next().val; self.expect(';')
                out += self.include(rel, t); continue
            if self.at('entry') and self.peek().kind == 'num':
                t = self.next(); sid = self.next().val; lab = self.ident('a label').val; self.expect(';')
                out.append(Node('entry', t, sid=sid, label=lab)); continue
            out.append(self.stmt())
        self.expect('}')
        return out

    def include(self, rel, tok):
        """include "file.dws"; inside a port block: the statements of `part { ... }` in that file (path relative to this file)."""
        import os
        path = os.path.join(os.path.dirname(self.file), rel)
        try:
            src = open(path, encoding='utf-8').read()
        except OSError as e:
            raise DwsError(f'include "{rel}": {e.strerror or e}', tok.pos)
        p = Parser(src, os.path.relpath(path) if not os.path.relpath(path).startswith('..') else path)
        p.expect('part'); o = p.expect('{'); out = []
        while not p.at('}'):
            if p.cur.kind == 'eof': raise DwsError('part block never closed', o.pos)
            out.append(p.stmt())
        p.expect('}')
        if p.cur.kind != 'eof': raise DwsError('unexpected text after the part block', p.cur.pos)
        INCLUDED.append(path)
        return out

    def enum(self, pub):
        c = self.next(); n = self.ident('an enum name'); self.expect('{'); vals = []; k = 0
        while not self.at('}'):
            v = self.ident('a value name')
            if self.accept('='):
                e = self.cur
                if e.kind != 'num': raise DwsError('a number is expected', e.pos)
                self.i += 1; k = e.val
            vals.append((v.val, k, v)); k += 1
            if not self.accept(','): break
        self.expect('}')
        return Node('enum', c, name=n.val, values=vals, pub=pub)

    def group(self, pub):
        """group Name { flag a; var b; flag[8] chests; }  names become Name.a, Name.b ..."""
        c = self.next(); n = self.ident('a group name'); self.expect('{'); decls = []
        while not self.at('}'):
            if self.cur.kind == 'eof': raise DwsError('group never closed', c.pos)
            acc = self.accept('pub')
            if self.at('const'):                  # group anim { const idle = 0; }: the name is anim.idle
                self.i += 1; cn = self.ident(); self.expect('='); e = self.expr(); self.expect(';')
                decls.append(Node('const', c, name=f'{n.val}.{cn.val}', expr=e, pub=pub or acc, ntok=cn)); continue
            d = self.decl(pub or acc); d.group = n.val; decls.append(d)
        self.expect('}')
        return Node('group', c, name=n.val, decls=decls, pub=pub)

    def fn(self, pub):
        sub = self.cur.val == 'sub'
        c = self.next(); n = self.ident('a function name'); self.expect('('); params = []
        while not self.at(')'):
            pn = self.ident('a parameter name'); self.expect(':'); pt = self.ident('a type'); default = None
            if self.accept('='): default = self.expr()
            params.append((pn.val, pt.val, default, pn))
            if not self.accept(','): break
        self.expect(')'); ret = None
        if self.accept('->'): ret = self.ident('a return type').val
        return Node('fn', c, name=n.val, params=params, body=self.block(), pub=pub, sub=sub, ret=ret)

    def script(self):
        c = self.next(); info = {'id': None, 'new_for': None, 'empty': False, 'lossless': False}
        if self.at('new'):
            self.i += 1; self.expect('for'); self.expect('screen'); s = self.cur
            if s.kind != 'num': raise DwsError('screen number expected', s.pos)
            self.i += 1; info['new_for'] = s.val
            if self.at('empty'): self.i += 1; info['empty'] = True
        else:
            s = self.cur
            if s.kind != 'num': raise DwsError('script number expected (script 178 { ... })', s.pos)
            self.i += 1; info['id'] = s.val
        if self.at('port'):
            self.i += 1
            return Node('script', c, body=[], text=None, port=self.port_body(c), **info)
        if self.at('lossless'):
            self.i += 1; info['lossless'] = True; self.expect('{'); raw = self.next()
            if raw.kind != 'raw': raise DwsError('lossless block expected', raw.pos)
            self.expect('}')
            return Node('script', c, body=[], text=raw.val, line=raw.line, **info)
        self.expect('{'); body = []
        while not self.at('}'):
            if self.cur.kind == 'eof': raise DwsError('script block never closed', c.pos)
            body.append(self.script_item())
        self.expect('}')
        return Node('script', c, body=body, text=None, **info)

    def script_item(self):
        c = self.cur
        if c.val == 'npc':
            self.i += 1; n = self.ident('an NPC name'); self.expect('=')
            e = self.cur
            if e.kind != 'num': raise DwsError('the NPC entity number (5-12) is expected', e.pos)
            self.i += 1; self.expect(';')
            return Node('npc', c, name=n.val, num=e.val, ntok=n)
        if c.val in ('on', 'section'):
            return self.event()
        if c.val == 'sections' and self.peek().kind == 'num':
            # sections 254, 5, 6, 81 as sec81_dup3;  the script's section table in the order of the header (the build makes the
            # script from its sources alone): an id is that section's event, `id as NAME` an entry whose code is `shared NAME { }`
            self.i += 1; ents = []
            while True:
                n = self.cur
                if n.kind != 'num': raise DwsError('a section id is expected (sections 254, 5, 6;)', n.pos)
                self.i += 1; name = None
                if self.at('as'): self.i += 1; name = self.ident('the shared block of this entry').val
                ents.append((n.val, name, n))
                if not self.accept(','): break
            self.expect(';')
            return Node('sections', c, entries=ents)
        if c.val == 'shared' and self.peek().kind == 'id' and self.peek(2).val == '{':
            # shared NAME { ... }: code of the script that several events reach with `goto NAME;` / `gosub NAME;` (a tail or a
            # subroutine the original shares between sections); compiled once, after the events
            self.i += 1; n = self.ident('the name of the shared block')
            return Node('shared', c, name=n.val, ntok=n, body=self.block())
        raise DwsError(f'unexpected "{c.val}" in a script block', c.pos, 'expected npc, on talk/enter/step/use, section, or shared')

    def event(self):
        c = self.next(); arg = None
        if c.val == 'section':
            self.expect('('); n = self.cur
            if n.kind != 'num': raise DwsError('section number expected', n.pos)
            self.i += 1; self.expect(')'); ev = 'section'; arg = n.val
        else:
            ev = self.ident('talk, enter, step or use').val
            if ev in ('talk', 'step', 'use'):
                self.expect('(')
                a = self.cur
                if ev == 'talk': arg = self.ident('an NPC name').val
                else:
                    if a.kind != 'num': raise DwsError('tile number expected', a.pos)
                    self.i += 1; arg = a.val
                self.expect(')')
            elif ev != 'enter':
                raise DwsError(f'unknown event "{ev}"', c.pos, 'events: talk(npc), enter, step(tile), use(tile), section(n)')
        mode = 'before'
        if self.cur.val in ('replace', 'before', 'after'):
            mode = self.next().val
        return Node('event', c, ev=ev, arg=arg, mode=mode, body=self.block())

    # ---- statements
    def block(self):
        o = self.expect('{'); stmts = []
        while not self.at('}'):
            if self.cur.kind == 'eof': raise DwsError('block never closed', o.pos, 'missing "}"')
            stmts.append(self.stmt())
        self.expect('}')
        return Node('block', o, stmts=stmts)

    def stmt(self):
        c = self.cur
        if c.kind == 'op' and c.val == '{': return self.block()
        if c.kind == 'op' and c.val == ';':
            self.i += 1; return Node('block', c, stmts=[])
        if c.kind == 'id':
            w = c.val
            if w == 'if':
                self.i += 1; self.expect('('); cond = self.expr(); self.expect(')')
                then = self.stmt(); els = None
                if self.at('else'):
                    self.i += 1; els = self.stmt()
                return Node('if', c, cond=cond, then=then, els=els)
            if w == 'while':
                self.i += 1; self.expect('('); cond = self.expr(); self.expect(')')
                return Node('while', c, cond=cond, body=self.stmt())
            if w == 'return':
                self.i += 1; e = None
                if not self.at(';'): e = self.expr()
                self.expect(';'); return Node('return', c, expr=e)
            if w in ('break', 'continue'):
                self.i += 1; self.expect(';'); return Node(w, c)
            if w in ('goto', 'gosub'):
                self.i += 1; n = self.label_ref(); self.expect(';'); return Node(w, c, label=n[0], ext=n[1])
            if w == 'unless' and self.peek().val == '(':
                self.i += 1; self.expect('('); cond = self.expr(); self.expect(')')
                if self.cur.val in ('break', 'continue', 'return') and self.cur.kind == 'id':     # unless (c) break;
                    j = self.next().val; self.expect(';')
                    return Node('unless', c, cond=cond, label=None, jump=j)
                self.expect('goto'); n = self.label_ref(); self.expect(';')
                return Node('unless', c, cond=cond, label=n[0], jump='goto', ext=n[1])
            if w == 'loop' and self.peek().val == '{':
                self.i += 1; return Node('loop', c, body=self.block())
            if w == 'repeat' and self.peek().val == '(':
                self.i += 1; self.expect('('); n = self.expr(); self.expect(')')
                return Node('repeat', c, count=n, body=self.stmt())
            if w == 'for' and self.peek().kind == 'id':
                self.i += 1; v = self.ident(); self.expect('in'); a = self.expr(); self.expect('..'); b = self.expr()
                return Node('for', c, var=v.val, lo=a, hi=b, body=self.stmt())
            if w == 'par' and self.peek().val == '{':
                self.i += 1; return Node('par', c, body=self.block())
            if w == 'match' and self.peek().val == '(':
                self.i += 1; self.expect('('); subj = self.expr(); clamp = False
                if self.accept(','):
                    if not (self.cur.kind == 'id' and self.cur.val == 'clamp'): raise DwsError('match (v, clamp): the only option is `clamp`', self.cur.pos)
                    self.i += 1; clamp = True
                self.expect(')'); self.expect('{'); arms = []
                while not self.at('}'):
                    if self.at('_'): self.i += 1; pat = None
                    else: pat = self.expr()
                    self.expect('=>')
                    if self.at('{') or self.cur.val in ('return', 'goto', 'break', 'continue', 'if'): body = self.stmt()
                    else:
                        bc = self.cur; be = self.expr()
                        if be.kind != 'call': raise DwsError('an arm is a block or a call', bc.pos)
                        body = Node('expr', bc, expr=be)
                    arms.append((pat, body)); self.accept(',') or self.accept(';')
                self.expect('}')
                return Node('match', c, subject=subj, arms=arms, clamp=clamp)
            if self.peek().kind == 'op' and self.peek().val == ':' and w not in ('else',):
                self.i += 2; return Node('label', c, name=w)
            if w == 'shared' and self.peek().kind == 'id' and self.peek(2).kind == 'op' and self.peek(2).val == ':':
                # shared NAME: a label every event of the script can `goto` (the entries of a table the engine reads by position)
                self.i += 1; n = self.next(); self.i += 1; return Node('label', c, name=n.val, shared=True)
            if w == 'cutscene' and self.peek().val == '{':
                self.i += 1; return Node('cutscene', c, body=self.block())
            if w == 'choice' and self.peek().val in ('{', '('):
                self.i += 1; who = None
                openc = False; keep = False
                if self.accept('('):                                                   # choice(narrator) { ... }: who owns the menu
                    while not self.at(')'):
                        if self.cur.kind == 'id' and self.cur.val == 'open' and self.peek().val in (')', ','): self.i += 1; openc = True
                        elif self.cur.kind == 'id' and self.cur.val == 'keep' and self.peek().val in (')', ','): self.i += 1; keep = True
                        else: who = self.expr()
                        if not self.accept(','): break
                    self.expect(')')
                self.expect('{'); opts = []
                cancel = None
                while not self.at('}'):
                    if self.at('cancel') and self.peek().val == '=>':         # the triangle button
                        k = self.next(); self.i += 1
                        if cancel is not None: raise DwsError('a choice has one cancel branch', k.pos)
                        cancel = self.stmt(); self.accept(','); continue
                    t = self.expr(); both = False
                    if self.at('or') and self.peek().val == 'cancel': self.i += 2; both = True      # "No" is also the triangle button
                    self.expect('=>'); b = self.stmt(); opts.append((t, b, both))
                    self.accept(',')
                self.expect('}')
                if not opts: raise DwsError('a choice needs at least one option', c.pos)
                return Node('choice', c, opts=opts, cancel=cancel, who=who, openc=openc, keep=keep)
            if w == 'let':
                self.i += 1; n = self.ident(); self.expect('='); e = self.expr(); self.expect(';')
                return Node('let', c, name=n.val, expr=e)
            if w == 'await':
                self.i += 1; e = self.expr(); self.expect(';'); return Node('await', c, expr=e)
            nx = self.peek()
            if nx.kind == 'op' and nx.val in ('[', '.'):
                save = self.i; tgt = self.postfix()
                if self.cur.kind == 'op' and self.cur.val in ('=', '+=', '-=', '*=', '/=', '%='):
                    op = self.next().val; e = self.expr(); self.expect(';')
                    return Node('assign', c, name=w, op=op, expr=e, target=tgt)
                self.i = save
            if nx.kind == 'op' and nx.val in ('=', '+=', '-=', '*=', '/=', '%='):
                self.i += 2; e = self.expr(); self.expect(';')
                return Node('assign', c, name=w, op=nx.val, expr=e)
        return self.stmt_call_or_expr()

    def stmt_call_or_expr(self):
        c = self.cur; e = self.expr()
        if e.kind != 'call':
            raise DwsError('this is not a statement', c.pos, 'statements are calls such as say(...), assignments, if, while...')
        self.expect(';')
        return Node('expr', c, expr=e)

    # ---- expressions
    def expr(self, level=0):
        if level == len(BIN_PREC): return self.unary()
        left = self.expr(level + 1)
        while (self.cur.kind == 'op' and self.cur.val in BIN_PREC[level]) or \
                (self.cur.kind == 'id' and self.cur.val == 'in' and 'in' in BIN_PREC[level]):
            op = self.next()
            right = self.expr(level + 1)
            left = Node('binary', op, op=op.val, l=left, r=right)
        return left

    def unary(self):
        c = self.cur
        if c.kind == 'op' and c.val == '!':
            self.i += 1; return Node('unary', c, op='!', e=self.unary())
        if c.kind == 'op' and c.val == '-':
            self.i += 1; e = self.unary()
            if e.kind == 'num': return Node('num', c, v=-e.v)
            return Node('unary', c, op='-', e=e)
        return self.postfix()

    def postfix(self):
        e = self.primary()
        while True:
            if self.at('.') :
                self.i += 1; n = self.ident('a member name'); e = Node('member', n, obj=e, name=n.val)
            elif self.at('[') and e.kind in ('id', 'member'):
                o = self.next(); idx = self.expr(); self.expect(']'); e = Node('index', o, obj=e, idx=idx)
            elif self.at('(') and e.kind in ('id', 'member'):
                o = self.next(); args = []
                while not self.at(')'):
                    if self.cur.kind == 'id' and self.peek().val == ':' and self.peek().kind == 'op':
                        nm = self.next().val; self.i += 1
                    else: nm = None
                    args.append((nm, self.expr()))
                    if not self.accept(','): break
                self.expect(')', 'to close the call')
                e = Node('call', o, fn=e, args=args)
            else:
                return e

    def primary(self):
        c = self.cur
        if c.kind == 'num':
            self.i += 1; n = self.cur
            if n.kind == 'id' and n.val in DUR_UNITS and (n.val not in ('s',) or n.col == c.end):
                self.i += 1; return Node('dur', c, v=c.val * DUR_UNITS[n.val])
            return Node('num', c, v=c.val)
        if c.kind == 'str':
            self.i += 1; return Node('str', c, v=c.val)
        if c.kind == 'id':
            self.i += 1
            if c.val in ('true', 'false'): return Node('bool', c, v=c.val == 'true')
            return Node('id', c, name=c.val)
        if c.kind == 'op' and c.val == '(':
            self.i += 1; e = self.expr()
            if self.accept(','):
                items = [e]
                while True:
                    items.append(self.expr())
                    if not self.accept(','): break
                self.expect(')'); return Node('tuple', c, items=items)
            self.expect(')'); e.paren = True; return e
        if c.kind == 'op' and c.val == '[':
            self.i += 1; items = []
            while not self.at(']'):
                items.append(self.expr())
                if not self.accept(','): break
            self.expect(']'); return Node('list', c, items=items)
        found = 'end of file' if c.kind == 'eof' else f'"{c.val}"'
        raise DwsError(f'expected a value, found {found}', c.pos)


def parse(src, fname):
    return Parser(src, fname).parse_file()
