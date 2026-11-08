"""Compact print edition of the release wiki. No independent game facts or spoiler rules."""
from html import escape
from html.parser import HTMLParser
import hashlib
import re
import subprocess

import model
from localize import translate

LIMIT = 10 * 1024 * 1024


def filename(tag, lang):
    return f'Horizon-Guide-{tag}-{lang}.pdf'


class Node:
    def __init__(self, tag='', attrs=()):
        self.tag, self.attrs, self.children = tag, dict(attrs), []

    def has(self, name):
        return name in self.attrs.get('class', '').split()

    def find(self, name):
        if self.has(name): return self
        for child in self.children:
            if isinstance(child, Node):
                result = child.find(name)
                if result: return result


class Tree(HTMLParser):
    def __init__(self, html):
        super().__init__(convert_charrefs=True)
        self.root = Node(); self.stack = [self.root]; self.feed(html)

    def handle_starttag(self, tag, attrs):
        node = Node(tag, attrs); self.stack[-1].children.append(node)
        if tag not in ('br', 'hr', 'img', 'input', 'meta', 'link'): self.stack.append(node)

    def handle_endtag(self, tag):
        if self.stack[-1].tag == tag: self.stack.pop()

    def handle_data(self, value):
        self.stack[-1].children.append(value)


def split(html):
    """Move whole outer spoiler disclosures, including nested folds, to the appendix."""
    hidden = []
    def render(node, secret=False):
        if isinstance(node, str): return escape(node)
        if node.has('spoiler') and not secret:
            hidden.append(render(node, True)); return ''
        if node.tag == 'summary': return ''
        tag = 'div' if node.tag == 'details' else node.tag
        attrs = ''.join(f' {k}="{escape(v, quote=True)}"' for k, v in node.attrs.items()
                        if k not in ('id', 'open') and not k.startswith('data-'))
        content = ''.join(render(child, secret) for child in node.children)
        if not tag: return content
        return f'<{tag}{attrs}>' + ('' if tag in ('br', 'hr', 'img') else content+f'</{tag}>')
    normal = render(Tree(html).root)
    return normal, ''.join(hidden)


def document(pages, tag):
    """Render from the same Pages instance used by the web edition."""
    p = pages
    normal, appendix = [], []
    toc = []
    def heading(ident, title):
        toc.append((ident, title))
        return f'<h1 id="{ident}">{title}</h1>'
    def partition(html, title, ident):
        public, secret = split(html)
        if secret: appendix.append(f'<section id="{ident}-secrets"><h3>{title}</h3>{secret}</section>')
        return public
    normal.append(heading('guides', p.t('wiki.articles')))
    normal.append('<div class="article-contents">'+''.join(f'<p><a href="#guide-{ident}">{escape(article["title"])}</a></p>' for ident,article in p.articles.items())+'</div>')
    # Capture the existing article renderer so release bindings and generated facts stay identical.
    captured = []
    original = p.page
    p.page = lambda path, title, body, *args: captured.append((path, title, body))
    try: p.article_pages()
    finally: p.page = original
    for path, title, body in captured:
        if path == 'guides/': continue
        ident = 'guide-' + path.split('/')[1]
        tree = Tree(body).root
        article = tree.find('article-body')
        # Related navigation belongs to the website, not the print edition.
        for i, node in enumerate(article.children):
            if isinstance(node, Node) and node.attrs.get('id') == 'related':
                article.children = article.children[:i]; break
        # Serialize via split while retaining the wiki's spoiler wrappers.
        def raw(node):
            if isinstance(node, str): return escape(node)
            attrs = ''.join(f' {k}="{escape(v, quote=True)}"' for k,v in node.attrs.items())
            return (f'<{node.tag}{attrs}>' if node.tag else '') + ''.join(raw(c) for c in node.children) + (f'</{node.tag}>' if node.tag not in ('', 'br', 'hr') else '')
        normal.append(f'<section id="{ident}"><h2>{escape(title)}</h2><p>{escape(p.articles[path.split("/")[1]]["summary"])}</p>'+partition(raw(article),escape(title),ident)+'</section>')
    normal.append(heading('digimon', p.t('data.recruit.digimon')))
    for level in model.guide.LEVELS:
        species = [s for s in p.data['species'] if s['level']==level and not s['spoiler']]
        if species: normal.append(f'<h2>{p.t("digimon.level."+level)}</h2>')
        for s in species:
            normal.append(species_entry(p, s, False))
    for s in p.data['species']:
        if s['spoiler']: appendix.append(species_entry(p, s, True))
        elif s['special']: appendix.append(f'<h3>{escape(p.name(s))}</h3><p>'+translate(escape(s['special']),p.english,p.strings)+'</p>')
        if not s['spoiler'] and any(p.by_id[i]['spoiler'] for i in s['parents']+s['to']):
            appendix.append(f'<h3>{escape(p.name(s))} · {p.t("data.evolutions")}</h3>'+routes(p,s,True))
    normal.append(heading('techniques',p.t('data.techniques')))
    innate={}
    for move in p.data['techniques']:
        range_key={0:'other',1:'melee',2:'ranged',3:'area',4:'buff'}.get(move['range'],'other')
        status_key={1:'poison',2:'confusion',3:'stun',4:'flatten'}.get(move['status'])
        status=p.t('data.'+status_key)+f' ({move["statusChance"]}%)' if status_key else '—'
        if 58 <= move['id'] <= 121:
            innate[move['id']]=f'<tr id="move-{move["id"]}"><td>{escape(p.move_name(move))}</td><td>{move["id"]}</td><td>{move["power"]}</td><td>{p.t("data."+range_key)}</td><td>{status}</td></tr>'
            continue
        labels=[p.t(k) for k in ('data.power','data.mp','data.range','data.status')]
        stats='<table><tr>'+''.join('<th>'+x+'</th>' for x in labels)+'</tr><tr>'+''.join('<td>'+str(x)+'</td>' for x in (move['power'],move['baseMP'],p.t('data.'+range_key),status))+'</tr></table>'
        ident=f'move-{move["id"]}'
        normal.append(f'<section id="{ident}"><h3>{escape(p.move_name(move))} · #{move["id"]}</h3>{stats}'+partition(p.learning_section(move),escape(p.move_name(move)),ident)+'</section>')
    normal.append('<p>'+p.t('wiki.notLearnable')+'</p><table class="innate-moves"><thead><tr>'+''.join('<th>'+label+'</th>' for label in (p.t('data.techniques'),'ID',p.t('data.power'),p.t('data.range'),p.t('data.status')))+'</tr></thead><tbody>'+''.join(innate[i] for i in sorted(innate))+'</tbody></table>')
    normal.append(heading('city',p.articles['file-city']['title']))
    normal.append('<p>'+p.t('data.recruit.intro')+'</p>')
    for row in p.data['recruits']:
        ident=f'recruit-{row["id"]}'
        if row['hidden']:
            appendix.append(f'<section id="{ident}">'+split(p.recruit(row,True))[1]+'</section>')
        else:
            public, secret=split(p.recruit(row,False))
            normal.append(f'<section id="{ident}">{public}</section>')
            appendix.append(f'<section id="{ident}-steps"><h3>{escape(model.recruits.species_name(p.data["files"],row["name"],p.lang))}</h3>{secret}</section>')
    # Enemy-only destinations need local anchors as well.
    for sid, enemy in sorted(p.data['enemies'].items()):
        target=p.enemy_target(enemy)
        if target['id'] in p.by_id: continue
        sources=[r for rows in p.data['learning_sources'].values() for r in rows if r['species']==sid]
        if not sources: continue
        entry=f'<p id="species-{sid}">{escape(p.name(enemy))}</p>'
        (appendix if all(r['spoiler'] for r in sources) else normal).append(entry)
    normal.append(heading('spoilers',p.t('wiki.pdfSpoilers')) .replace('<h1 ', '<h1 class="divider-title" '))
    # The divider is a full page; no secret headings enter the contents or outline.
    divider=normal.pop()
    contents='<nav id="contents"><h1>'+p.t('wiki.pdfContents')+'</h1>'+''.join(f'<p><a href="#{i}">{t}</a></p>' for i,t in toc)+'</nav>'
    body=f'<header><h1>Digimon World: Horizon</h1><p>{tag} · {escape(p.lang)}</p><p>{p.t("wiki.title")}</p><p>{p.data["commit"]}</p></header>'+contents+''.join(normal)+f'<section id="spoiler-divider">{divider}<p>{p.t("wiki.pdfWarning")}</p></section><div class="appendix">'+''.join(appendix)+'</div>'
    def rewrite(match):
        url=match[1]
        if not url.startswith(p.base): return match[0]
        path, _, fragment=url[len(p.base):].partition('#')
        parts=path.strip('/').split('/')
        if parts[0]=='digimon' and len(parts)>1:
            dest=('recruit-'+fragment.split('-')[-1]) if fragment.startswith('recruit-') else 'species-'+parts[1].split('-')[0]
        elif parts[0]=='techniques' and len(parts)>1: dest='move-'+parts[1].split('-')[0]
        elif parts[0]=='guides' and len(parts)>1: dest='guide-'+parts[1]
        elif parts[0]=='recruits' and fragment: dest=fragment
        else: dest={'guides':'guides','digimon':'digimon','techniques':'techniques','recruits':'city','evolutions':'digimon'}.get(parts[0],'contents')
        return 'href="#'+dest+'"'
    body=re.sub(r'href="([^"]+)"', rewrite, body)
    # Validate all internal targets before asking the printer to resolve them.
    ids=re.findall(r' id="([^"]+)"',body)
    if len(ids)!=len(set(ids)): raise ValueError('Duplicate print destination')
    for target in re.findall(r'href="#([^"]+)"',body):
        if target not in ids: raise ValueError('Missing print destination: '+target)
    return f'<!doctype html><html lang="{p.lang}"><head><meta charset="utf-8"><title>Horizon Guide {tag} {p.lang}</title><link rel="stylesheet" href="/wiki/assets/print.css"></head><body>{body}</body></html>'


def routes(p,s,secret):
    groups=[]
    for key,label in [('parents','digimon.from'),('to','digimon.to')]:
        links=[]
        for ident in s[key]:
            other=p.by_id[ident]
            if not secret and other['spoiler']: continue
            hours=p.data['timed'].get((ident,s['id']) if key=='parents' else (s['id'],ident))
            links.append(f'<a href="#species-{ident}">{escape(p.name(other))}</a>'+(' · '+p.t('digimon.after',hours=hours) if hours else ''))
        if links: groups.append('<p><b>'+p.t(label)+'</b>: '+', '.join(links)+'</p>')
    return ''.join(groups)


def species_entry(p,s,secret):
    moves=[]
    for entry in s['moves']:
        m=p.moves[entry['id']]
        power=s['finisher'].get('power',m['power']) if 58<=m['id']<=112 else m['power']
        chance=str(entry['chance'])+'%' if entry['chance'] is not None else '—'
        sources=[r for r in p.data['learning_sources'][m['id']] if secret or not r['spoiler']]
        summary=''
        if sources:
            labels=[]
            for source in sources:
                enemy=p.data['enemies'][source['species']]
                label=escape(p.name(enemy))+' → '+escape(p.places[source['screen']])
                if label not in labels: labels.append(label)
            summary=labels[0]
            if len(labels)>1: summary+=f' (+{len(labels)-1})'
        moves.append(f'<li><a href="#move-{m["id"]}">{escape(p.move_name(m))}</a> ({power} / {m["baseMP"]} MP / {chance})'+(f' · {summary}' if summary else '')+'</li>')
    html=f'<section class="species" id="species-{s["id"]}"><h3>{escape(p.name(s))} · #{s["id"]}</h3><p>{p.label(s)} · {p.specs(s)}</p><p class="move-key"><b>{p.t("data.techniques")}</b> ({p.t("data.power")} / MP / {p.t("wiki.learning")}):</p><ul class="species-moves">'+''.join(moves)+'</ul><p><b>'+p.t('wiki.requirements')+'</b>: '+p.req(s).replace('<br>',' · ')+'</p>'+routes(p,s,secret)
    if secret and s['special']: html+='<p>'+translate(escape(s['special']),p.english,p.strings)+'</p>'
    return html+'</section>'


def generate(out, data, instances):
    # Static instances avoid Chromium's Type 3 variable-font fallback in printed output.
    from fontTools.ttLib import TTFont
    from fontTools.varLib.instancer import instantiateVariableFont
    for weight in (400,700):
        font=TTFont(model.ROOT/'tools/guide/assets/font/PlusJakartaSans.ttf',recalcTimestamp=False)
        instantiateVariableFont(font,{'wght':weight},inplace=True).save(out/f'wiki/assets/print-{weight}.ttf')
    for p in instances:
        target=out/'wiki'/p.lang/'print.html'
        target.write_text(document(p,data['tag']))
    subprocess.run(['node',str(model.ROOT/'tools/wiki/print.mjs'),str(out.resolve())],check=True)
    return finish(out,data,instances)


def finish(out, data, instances):
    manifest={}
    from pypdf import PdfReader, PdfWriter
    from pypdf.generic import ArrayObject, ByteStringObject
    for p in instances:
        file=out/'wiki'/p.lang/filename(data['tag'],p.lang)
        reader=PdfReader(file)
        writer=PdfWriter(clone_from=reader)
        writer.add_metadata({'/CreationDate':'D:20000101000000Z','/ModDate':'D:20000101000000Z','/Title':f'Horizon Guide {data["tag"]} {p.lang}','/Subject':data['commit'],'/Author':'','/Creator':'Horizon Wiki'})
        # Use only public section destinations from the clickable contents on page two.
        if '/Outlines' in writer._root_object: del writer._root_object['/Outlines']
        links=[a.get_object() for a in writer.pages[1].get('/Annots',[]) if a.get_object().get('/Dest')]
        titles=[p.t('wiki.articles'),p.t('data.recruit.digimon'),p.t('data.techniques'),escape(p.articles['file-city']['title']),p.t('wiki.pdfSpoilers')]
        if len(links)!=5: raise ValueError('PDF contents must have five resolved destinations')
        from html import unescape
        for title,link in zip(titles,links):
            dest=link['/Dest']
            if isinstance(dest,str):
                page=reader.get_destination_page_number(reader.named_destinations[str(dest)])
            else:
                page=reader.get_page_number(dest[0].get_object())
            writer.add_outline_item(unescape(title),page)
        writer.compress_identical_objects(remove_duplicates=True,remove_unreferenced=True)
        # Stable document IDs and metadata make repeated builds byte-identical.
        writer._ID=ArrayObject([ByteStringObject(hashlib.sha256((data['commit']+'-'+p.lang).encode()).digest()[:16])]*2)
        with file.open('wb') as stream: writer.write(stream)
        import pikepdf
        with pikepdf.open(file,allow_overwriting_input=True) as optimized:
            optimized.save(file,object_stream_mode=pikepdf.ObjectStreamMode.generate,
                           deterministic_id=True,compress_streams=True,recompress_flate=True)
        if file.stat().st_size>=LIMIT: raise ValueError('PDF exceeds 10 MiB: '+file.name)
        manifest[p.lang]=dict(file=f'/wiki/{p.lang}/{file.name}',bytes=file.stat().st_size,pages=len(reader.pages),sha256=hashlib.sha256(file.read_bytes()).hexdigest(),tag=data['tag'],commit=data['commit'])
        # Print sources are build intermediates, never served with unfolded secrets.
        (file.parent/'print.html').unlink(missing_ok=True)
    return manifest


def validate(site, manifest):
    """Verify delivered PDFs, including provenance, outline and resolved local links."""
    from pypdf import PdfReader
    import model
    records=manifest.get('pdfs',{})
    assert set(records)==set(model.LANGS), 'One PDF is required for every language'
    for lang,record in records.items():
        assert record['tag']==manifest['tag'] and record['commit']==manifest['commit'], 'PDF release mismatch'
        expected=f'/wiki/{lang}/'+filename(manifest['tag'],lang)
        assert record['file']==expected, 'Unexpected PDF filename'
        file=site/expected.lstrip('/')
        assert file.is_file(), 'Missing PDF: '+expected
        assert not (file.parent/'print.html').exists(), 'Unfolded print intermediate must not be deployed'
        raw=file.read_bytes()
        assert raw.startswith(b'%PDF-'), 'Invalid PDF'
        assert len(raw)==record['bytes'] and len(raw)<LIMIT, 'PDF size mismatch or budget exceeded'
        assert hashlib.sha256(raw).hexdigest()==record['sha256'], 'PDF digest mismatch'
        reader=PdfReader(file)
        assert reader.metadata.title==f'Horizon Guide {manifest["tag"]} {lang}', 'PDF title/release mismatch'
        assert reader.metadata.subject==manifest['commit'], 'PDF game commit mismatch'
        assert len(reader.pages)==record['pages'], 'PDF page count mismatch'
        assert len(reader.outline)==5, 'Missing PDF section outline'
        refs={pg.indirect_reference.idnum for pg in reader.pages}
        links=0
        destinations=reader.named_destinations
        checked_resources=set()
        def image_resource(resources):
            for ref in resources.get('/XObject',{}).values():
                key=(getattr(ref,'idnum',None),getattr(ref,'generation',None))
                if key in checked_resources: continue
                checked_resources.add(key)
                obj=ref.get_object()
                if obj.get('/Subtype')=='/Image': return True
                if image_resource(obj.get('/Resources',{})): return True
            return False
        for page in reader.pages:
            assert not image_resource(page.get('/Resources',{})), 'Artwork in text-only PDF'
            for ref in page.get('/Annots',[]):
                annotation=ref.get_object()
                if annotation.get('/Subtype')!='/Link': continue
                dest=annotation.get('/Dest')
                assert dest, 'PDF link is not an internal destination'
                if isinstance(dest,str):
                    assert str(dest) in destinations, 'Missing PDF named destination'
                    page_number=reader.get_destination_page_number(destinations[str(dest)])
                    assert page_number is not None and 0<=page_number<len(reader.pages), 'Invalid PDF page'
                else:
                    assert dest[0].idnum in refs, 'PDF link points outside document'
                links+=1
        assert links>100, 'PDF internal links missing'
    return records
