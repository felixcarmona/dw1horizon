"""TOML for the files of story/ on any Python 3.8+: `tomllib` when the interpreter has it (3.11+), else a reader of the
subset story/names.toml and mod.toml use (`[table]`, `key = "string" | 'string' | int | true/false | [strings] |
{ inline table }`, `#` comments). The patcher's local build (docs/patcher.md) runs the beautifier on the player's
machine, which may have Python 3.8."""
import json, re

try:
    import tomllib
except ImportError:          # Python < 3.11
    tomllib = None

_STR = r'"(?:[^"\\]|\\.)*"|\'[^\']*\''
_TOKEN = re.compile(rf'\s*({_STR}|\{{|\}}|\[|\]|,|=|[A-Za-z0-9_.+-]+)')


def load_toml(path):
    if tomllib is not None:
        with open(path, 'rb') as f: return tomllib.load(f)
    with open(path, encoding='utf-8') as f: return loads(f.read())


def _strip_comment(line):
    out = []; q = None; i = 0
    while i < len(line):
        c = line[i]
        if q:
            out.append(c)
            if c == '\\' and q == '"' and i + 1 < len(line): out.append(line[i + 1]); i += 1
            elif c == q: q = None
        elif c in '"\'': q = c; out.append(c)
        elif c == '#': break
        else: out.append(c)
        i += 1
    return ''.join(out).strip()


def _tokens(s):
    pos = 0; out = []
    while pos < len(s):
        m = _TOKEN.match(s, pos)
        if not m:
            if s[pos:].strip() == '': break
            raise ValueError(f'TOML: cannot read {s[pos:pos + 30]!r}')
        out.append(m.group(1)); pos = m.end()
    return out


def _value(toks, i):
    t = toks[i]
    if t == '{':
        d = {}; i += 1
        while toks[i] != '}':
            k = toks[i].strip('"\''); assert toks[i + 1] == '=', 'TOML: = expected'
            v, i = _value(toks, i + 2); d[k] = v
            if toks[i] == ',': i += 1
        return d, i + 1
    if t == '[':
        lst = []; i += 1
        while toks[i] != ']':
            v, i = _value(toks, i); lst.append(v)
            if toks[i] == ',': i += 1
        return lst, i + 1
    if t[0] == '"':
        return json.loads(t), i + 1
    if t[0] == "'": return t[1:-1], i + 1
    if t in ('true', 'false'): return t == 'true', i + 1
    try: return int(t.replace('_', ''), 0), i + 1
    except ValueError: return float(t), i + 1


def loads(text):
    root = {}; cur = root; pending = ''
    for raw in text.splitlines():
        line = _strip_comment(raw)
        if not line and not pending: continue
        line = (pending + ' ' + line).strip() if pending else line
        if line.count('[') - line.count(']') > 0 or line.count('{') - line.count('}') > 0:
            pending = line; continue                     # an array or inline table that goes on over lines
        pending = ''
        m = re.match(r'^\[\s*([^\[\]]+?)\s*\]$', line)
        if m:
            cur = root
            for part in m.group(1).split('.'): cur = cur.setdefault(part.strip().strip('"\''), {})
            continue
        toks = _tokens(line)
        if len(toks) < 3 or toks[1] != '=': raise ValueError(f'TOML: cannot read the line {raw!r}')
        v, _ = _value(toks, 2); cur[toks[0].strip('"\'')] = v
    return root
