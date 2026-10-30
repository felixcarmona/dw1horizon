"""Formatter: one canonical layout (4 spaces per brace level, trailing whitespace removed, one blank
line at most, final newline). Works on text and keeps comments; lossless blocks are left verbatim."""
import re


def format_source(src, fname='<src>'):
    out = []; depth = 0; blank = 0; in_block_comment = False; raw = False
    for line in src.replace('\r\n', '\n').split('\n'):
        if raw:
            if line.startswith('}'): raw = False
            else: out.append(line.rstrip()); blank = 0; continue
        s = line.strip()
        if in_block_comment:
            out.append(('    ' * depth + ' ' + s.lstrip()) if s else ''); 
            if '*/' in s: in_block_comment = False
            continue
        if not s:
            blank += 1
            if blank == 1 and out: out.append('')
            continue
        blank = 0
        code = strip_strings_comments(s)
        if s.startswith('/*') and '*/' not in s: in_block_comment = True
        opens = code.count('{') + code.count('(') * 0; closes = code.count('}')
        lead = len(code) - len(code.lstrip('}'))
        d = max(depth - min(lead, closes if False else lead), 0)
        out.append('    ' * d + s)
        depth = max(depth + opens - closes, 0)
        if re.search(r'\blossless\s*\{\s*$', code): raw = True; depth = max(depth - 1, 0)
    while out and out[-1] == '': out.pop()
    return '\n'.join(out) + '\n'


def strip_strings_comments(s):
    res = []; i = 0; n = len(s)
    while i < n:
        c = s[i]
        if c == '"':
            i += 1
            while i < n and s[i] != '"': i += 2 if s[i] == '\\' else 1
            i += 1; res.append('""'); continue
        if s.startswith('//', i): break
        if s.startswith('/*', i):
            j = s.find('*/', i + 2)
            if j < 0: break
            i = j + 2; continue
        res.append(c); i += 1
    return ''.join(res)
