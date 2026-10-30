"""Tokens of DWS: identifiers, numbers, strings, punctuation; // and /* */ comments.
`lossless {` and `maphead lossless {` introduce a raw block (verbatim bytecode text up to a line
that starts with `}`), returned as one 'raw' token."""
import re
from .diag import DwsError, SOURCES

PUNCT = ['=>', '->', '~>', '==', '!=', '<=', '>=', '&&', '||', '+=', '-=', '*=', '/=', '%=', '..',
         '{', '}', '(', ')', '[', ']', ',', ';', ':', '.', '=', '<', '>', '+', '-', '!']


class Tok:
    __slots__ = ('kind', 'val', 'file', 'line', 'col', 'end')

    def __init__(self, kind, val, file, line, col, end):
        self.kind, self.val, self.file, self.line, self.col, self.end = kind, val, file, line, col, end

    @property
    def pos(self):
        return (self.file, self.line, self.col)

    def __repr__(self):
        return f'Tok({self.kind},{self.val!r},{self.line}:{self.col})'


def lex(src, fname):
    SOURCES[fname] = src.split('\n')
    toks = []; i = 0; line = 1; ls = 0; n = len(src)
    while i < n:
        c = src[i]
        col = i - ls + 1
        if c == '\n':
            line += 1; i += 1; ls = i; continue
        if c in ' \t\r':
            i += 1; continue
        if src.startswith('//', i):
            while i < n and src[i] != '\n': i += 1
            continue
        if src.startswith('/*', i):
            j = src.find('*/', i + 2)
            if j < 0: raise DwsError('unterminated /* comment', (fname, line, col))
            line += src.count('\n', i, j); 
            k = src.rfind('\n', i, j)
            if k >= 0: ls = k + 1
            i = j + 2; continue
        if c == '"':
            j = i + 1; out = []
            while True:
                if j >= n or src[j] == '\n':
                    raise DwsError('unterminated string', (fname, line, col), 'strings end on the same line')
                if src[j] == '\\':
                    if j + 1 < n and src[j + 1] in '"\\':
                        out.append(src[j + 1]); j += 2; continue
                    raise DwsError(f'unknown escape "\\{src[j + 1:j + 2]}" in a string', (fname, line, j - ls + 1),
                                   'only \\" and \\\\ exist; {color 1}, {player}... are written as they are')
                if src[j] == '"': break
                out.append(src[j]); j += 1
            toks.append(Tok('str', ''.join(out), fname, line, col, j + 1 - ls + 1)); i = j + 1; continue
        m = re.compile(r'0[xX][0-9a-fA-F]+|\d+').match(src, i)
        if m:
            toks.append(Tok('num', int(m.group(), 0), fname, line, col, col + len(m.group()))); i = m.end(); continue
        m = re.compile(r'[A-Za-z_][A-Za-z_0-9]*').match(src, i)
        if m:
            toks.append(Tok('id', m.group(), fname, line, col, col + len(m.group()))); i = m.end()
            continue
        for p in PUNCT:
            if src.startswith(p, i):
                toks.append(Tok('op', p, fname, line, col, col + len(p))); i += len(p)
                if (p == '{' and len(toks) >= 2 and toks[-2].kind == 'id' and toks[-2].val == 'lossless'):
                    # raw block: everything up to a line that starts with '}'
                    j = src.find('\n', i)
                    if j < 0: raise DwsError('lossless block never closed', toks[-1].pos)
                    j += 1; start_line = line + 1; body = []
                    k = j; ln2 = start_line
                    while True:
                        e = src.find('\n', k)
                        e = n if e < 0 else e
                        row = src[k:e]
                        if row.startswith('}'): break
                        body.append(row)
                        if e >= n: raise DwsError('lossless block never closed (a line starting with "}" ends it)', toks[-1].pos)
                        k = e + 1; ln2 += 1
                    toks.append(Tok('raw', '\n'.join(body), fname, start_line, 1, 1))
                    line = ln2; ls = k; i = k
                break
        else:
            raise DwsError(f'unexpected character {c!r}', (fname, line, col))
    toks.append(Tok('eof', None, fname, line, i - ls + 1, i - ls + 1))
    return toks
