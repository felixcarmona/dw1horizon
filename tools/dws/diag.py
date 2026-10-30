"""Diagnostics: errors and warnings with file, line, column, the source line and a hint."""
SOURCES = {}          # file -> list of source lines (filled by the lexer)


class DwsError(Exception):
    def __init__(self, msg, pos=None, hint=None):
        super().__init__(msg)
        self.msg, self.pos, self.hint = msg, pos, hint      # pos = (file, line, col)

    def render(self, kind='error'):
        if not self.pos:
            out = f'{kind}: {self.msg}'
        else:
            f, ln, col = self.pos
            out = f'{f}:{ln}:{col}: {kind}: {self.msg}'
            src = SOURCES.get(f)
            if src and 0 < ln <= len(src):
                line = src[ln - 1].rstrip('\n')
                out += f'\n    {line}\n    {" " * (max(col, 1) - 1)}^'
        if self.hint:
            out += f'\n  hint: {self.hint}'
        return out

    __str__ = render


def err(node, msg, hint=None):
    return DwsError(msg, getattr(node, 'pos', node), hint)


class Warnings:
    def __init__(self):
        self.items = []

    def add(self, node, msg, hint=None):
        self.items.append(DwsError(msg, getattr(node, 'pos', node), hint))

    def render(self):
        return [w.render('warning') for w in self.items]
