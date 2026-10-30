"""`dws text review [ZONE ...]`: every text key side by side, for translators (docs/mods/translating.md).

    python3 tools/dws.py text review                     # all keys -> build/text-review/review.csv and index.html
    python3 tools/dws.py text review file-city -o DIR    # the keys of one zone (story/base/zones/<zone>)

One row per key: key, zone, screen, speaker, status (aligned / pages differ / us-only / missing in ours), then JP (jp-rev1,
else jp), US, ES (es-fan) and ours. The disc columns come from text/<source>/ (made by `dws extract-text DISC`, gitignored);
ours from text/ours/ (committed). The output holds the discs' text, so it goes under build/ (gitignored): never commit it.
The HTML page filters by text and status and shows the pages of an utterance one per line."""
import csv, html, json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
sys.path.insert(0, os.path.join(ROOT, 'tools'))
COLS = ('jp', 'us', 'es', 'ours')


def load(src, name='dialogue.json'):
    d = os.path.join(ROOT, 'text', src)
    out = {}
    p = os.path.join(d, name)
    if os.path.exists(p): out.update(json.load(open(p, encoding='utf-8')))
    if src == 'ours' and name == 'dialogue.json' and os.path.isdir(os.path.join(d, 'dialogue')):
        for f in sorted(os.listdir(os.path.join(d, 'dialogue'))):
            if f.endswith('.json'): out.update(json.load(open(os.path.join(d, 'dialogue', f), encoding='utf-8')))
    return {k: v for k, v in out.items() if not k.startswith('_')}


def report(src):
    p = os.path.join(ROOT, 'text', src, 'report.csv')
    if not os.path.exists(p): return {}
    return {r['key']: r for r in csv.DictReader(open(p, encoding='utf-8'))}


def flat(v):
    """A value as display text: pages separated by ' ¶ ', rows by ' / '."""
    if v is None: return ''
    if isinstance(v, str): return v
    pages = [v] if all(isinstance(x, str) for x in v) else v
    return ' ¶ '.join(' / '.join(p) for p in pages)


def zones():
    """{script id: zone folder} and {script id: screen names} of story/base/zones."""
    z, scr = {}, {}
    base = os.path.join(ROOT, 'story', 'base', 'zones')
    for zone in sorted(x for x in os.listdir(base) if os.path.isdir(os.path.join(base, x))) if os.path.isdir(base) else []:
        for d in sorted(os.listdir(os.path.join(base, zone))):
            m = re.match(r's(\d{3})(?:-|$)', d)
            if not m: continue
            z[int(m.group(1))] = zone
            rd = os.path.join(base, zone, d, 'README.md')
            if os.path.exists(rd):
                mm = re.search(r'Screens that load it: (.*)\.', open(rd, encoding='utf-8').read())
                if mm: scr[int(m.group(1))] = mm.group(1)
    return z, scr


def speakers():
    """{utterance key: speaker} from the US disassembly (the dialogue owner set before it), named as story/base names it."""
    from dws.text import extract as E
    from dws import lift
    out = {}
    try:
        scripts, mh = E.us_disassembly()
        names = lift.Names()
    except Exception:
        return out
    def name(sid, o):
        if o in (None, '?'): return ''
        if o == 'TAMER': return 'tamer'
        if o == 'PARTNER': return 'partner'
        if o == '255': return 'narrator'
        if o.isdigit() and 5 <= int(o) <= 12 and sid is not None:
            try: return names.npc_name(sid, int(o))
            except Exception: return f'npc {o}'
        return o
    for sid, txt in list(scripts.items()) + [(None, mh)]:
        for lab, toks in E.sections(txt, 'maphead' if sid is None else 'script', sid).items():
            for t in toks:
                if t.t == 'U': out[t.key] = name(sid, t.owner)
                elif t.t == 'M':
                    for k, _ in t.opts: out[k] = name(sid, t.owner) + ' (menu)'
    return out


def natural(k):
    return [int(t) if t.isdigit() else t for t in re.split(r'(\d+)', k)]


def rows(only_zones=None):
    us = load('us'); jp = load('jp-rev1') or load('jp'); es = load('es-fan'); ours = load('ours')
    rjp = report('jp-rev1') or report('jp'); res = report('es-fan')
    z, scr = zones(); spk = speakers()
    names = {s: load(s, 'names.json') for s in ('us', 'jp-rev1', 'jp', 'es-fan', 'ours')}
    out = []
    keys = sorted(set(us) | {k for k in ours if not k.startswith('x.')}, key=natural)
    for k in keys:
        m = re.match(r's(\d{3})\.', k)
        sid = int(m.group(1)) if m else None
        zone = z.get(sid, 'maphead' if k.startswith('m') else '')
        if only_zones and zone not in only_zones: continue
        st = []
        for name, rep in (('jp', rjp), ('es', res)):
            r = rep.get(k)
            if r is None: continue
            if r['status'] != 'aligned': st.append(f'{name}: {r["status"]}')
            elif r['us_pages'] != r['src_pages']: st.append(f'{name}: pages {r["src_pages"]} (us {r["us_pages"]})')
        if k not in ours: st.append('ours: missing')
        out.append({'key': k, 'zone': zone, 'screen': scr.get(sid, ''), 'speaker': spk.get(k, ''),
                    'status': '; '.join(st) or 'aligned', 'jp': flat(jp.get(k)), 'us': flat(us.get(k)),
                    'es': flat(es.get(k)), 'ours': flat(ours.get(k))})
    if not only_zones or 'names' in only_zones:              # the executable's strings
        from localize.executable import extract as exe
        own = exe.own_keys()                                  # the mod's own strings (lab menu...): their English is ours
        names['us'] = {**own, **names['us']}
        jpn = names['jp-rev1'] or names['jp']
        for k in sorted(set(names['us']) | set(jpn) | set(names['ours']), key=natural):
            st = 'ours: missing' if k not in names['ours'] else 'aligned'
            if k in own: st = 'mod text; ' + st
            out.append({'key': k, 'zone': 'names', 'screen': k.split('.')[0], 'speaker': '', 'status': st,
                        'jp': jpn.get(k, ''), 'us': names['us'].get(k, ''), 'es': names['es-fan'].get(k, ''),
                        'ours': names['ours'].get(k, '')})
    return out


PAGE = """<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Text review</title><style>
:root{--bg:#fff;--fg:#1d1d1f;--mute:#6e6e73;--line:#e3e3e8;--warn:#b25000;--miss:#c0392b;--head:#f5f5f7}
@media (prefers-color-scheme: dark){:root{--bg:#1c1c1e;--fg:#f2f2f7;--mute:#a1a1a6;--line:#38383a;--warn:#ff9f0a;--miss:#ff453a;--head:#2c2c2e}}
body{background:var(--bg);color:var(--fg);font:14px/1.45 system-ui,sans-serif;margin:0 16px}
header{position:sticky;top:0;background:var(--bg);padding:10px 0;border-bottom:1px solid var(--line);display:flex;gap:8px;flex-wrap:wrap;align-items:center}
input,select{font:inherit;padding:4px 8px;border:1px solid var(--line);border-radius:6px;background:var(--bg);color:var(--fg)}
table{border-collapse:collapse;width:100%;table-layout:fixed}th,td{border-bottom:1px solid var(--line);padding:6px;vertical-align:top;text-align:left;word-wrap:break-word}
th{background:var(--head);position:sticky;top:52px}td.k{font-family:ui-monospace,monospace;font-size:12px;color:var(--mute)}
.st{font-size:12px}.st.w{color:var(--warn)}.st.m{color:var(--miss)}.pg{display:block;border-left:2px solid var(--line);padding-left:6px;margin-bottom:4px}
</style></head><body><header><strong>Text review</strong><input id="q" placeholder="filter: key, word, speaker" size="30">
<select id="s"><option value="">every status</option><option>ours: missing</option><option>pages</option><option>us-only</option><option>aligned</option></select>
<span id="n" class="st"></span></header>
<table><thead><tr><th style="width:12%">key</th><th style="width:8%">where / who</th><th style="width:8%">status</th>
<th>JP</th><th>US</th><th>ES</th><th>ours</th></tr></thead><tbody id="b"></tbody></table>
<script>
const R = __ROWS__;
const esc = s => s.replace(/[&<>]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]));
const cell = s => s.split(' \\u00b6 ').map(p => '<span class="pg">' + esc(p) + '</span>').join('');
function draw(){const q=document.getElementById('q').value.toLowerCase(), s=document.getElementById('s').value;
 const out=[]; let n=0;
 for(const r of R){ if(s && !r.status.includes(s)) continue;
  if(q && !(r.key+' '+r.speaker+' '+r.screen+' '+r.jp+' '+r.us+' '+r.es+' '+r.ours).toLowerCase().includes(q)) continue;
  if(++n>3000) continue;
  const c = r.status.includes('missing')||r.status.includes('only') ? 'm' : r.status==='aligned' ? '' : 'w';
  out.push('<tr><td class="k">'+esc(r.key)+'</td><td class="st">'+esc(r.zone)+'<br>'+esc(r.screen)+'<br><b>'+esc(r.speaker)+'</b></td><td class="st '+c+'">'
   +esc(r.status)+'</td><td>'+cell(r.jp)+'</td><td>'+cell(r.us)+'</td><td>'+cell(r.es)+'</td><td>'+cell(r.ours)+'</td></tr>');}
 document.getElementById('b').innerHTML=out.join('');
 document.getElementById('n').textContent=n+' rows'+(n>3000?' (first 3000 shown: filter)':'');}
document.getElementById('q').oninput=draw;document.getElementById('s').onchange=draw;draw();
</script></body></html>
"""


def main(argv):
    import argparse
    ap = argparse.ArgumentParser(prog='dws.py text review')
    ap.add_argument('zones', nargs='*', help='zones of story/base/zones (or "maphead", "names"); default all')
    ap.add_argument('-o', default=os.path.join(ROOT, 'build', 'text-review'))
    a = ap.parse_args(argv)
    rs = rows(set(a.zones) or None)
    os.makedirs(a.o, exist_ok=True)
    with open(os.path.join(a.o, 'review.csv'), 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, ['key', 'zone', 'screen', 'speaker', 'status', 'jp', 'us', 'es', 'ours']); w.writeheader(); w.writerows(rs)
    with open(os.path.join(a.o, 'index.html'), 'w', encoding='utf-8') as f:
        f.write(PAGE.replace('__ROWS__', json.dumps(rs, ensure_ascii=False).replace('</', '<\\/')))
    have = [s for s in ('jp-rev1', 'jp', 'es-fan') if os.path.exists(os.path.join(ROOT, 'text', s, 'dialogue.json'))]
    print(f'{len(rs)} keys -> {os.path.relpath(a.o, ROOT)}/review.csv and index.html (sources: us, {", ".join(have) or "no other disc"}, ours; '
          'local only: it holds the discs\' text)')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
