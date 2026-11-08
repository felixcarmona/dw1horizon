#!/usr/bin/env python3
"""Generate static multilingual wiki pages using presentation here and tagged game inputs."""
import argparse
import hashlib
from html import escape, unescape
import json
from pathlib import Path
import re
import shutil
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import model
import articles as article_catalogs
from localize import translate

ROOT = model.ROOT
HERE = Path(__file__).resolve().parent
CONTENT = ROOT / 'web/wiki'
NAMES = dict(zip(model.LANGS, ('English','Español','Português (Brasil)','Français','Deutsch','Italiano','日本語','Català','简体中文')))
WIKI_LIMIT = 64 * 1024 * 1024
SITE_LIMIT = 900 * 1024 * 1024
INDEX_LIMIT = 400 * 1024


def compact(data):
    return json.dumps(data, ensure_ascii=False, separators=(',', ':'))


def plain(text):
    return unescape(re.sub('<[^>]*>', ' ', text)).strip()


def owned_icons():
    """An empty opt-in map ships no pictures; future entries must name reviewed owned assets."""
    icons=json.loads((CONTENT/'owned-icons.json').read_text())
    if not isinstance(icons,dict) or any(not key.isdecimal() or not isinstance(name,str) or not re.fullmatch(r'[a-z0-9][a-z0-9-]*\.(svg|png|webp)',name) for key,name in icons.items()):
        raise ValueError('Owned icons must map species IDs to local filenames')
    return icons


def budget(out):
    paths = [p for p in out.rglob('*') if p.is_file()]
    total = sum(p.stat().st_size for p in paths)
    if total >= SITE_LIMIT or any(p.stat().st_size >= 100 * 1024 * 1024 for p in paths):
        raise ValueError('Assembled Pages size budget exceeded')
    wiki = out / 'wiki'
    size = sum(p.stat().st_size for p in wiki.rglob('*') if p.is_file())
    if size > WIKI_LIMIT:
        raise ValueError('Wiki exceeds 64 MiB budget')
    for index in wiki.glob('*/search-index.json'):
        if index.stat().st_size > INDEX_LIMIT:
            raise ValueError('Search index exceeds 400 KiB: ' + str(index))
    return dict(site_bytes=total, wiki_bytes=size)


class Pages:
    def __init__(self, out, data, lang, articles):
        self.out, self.data, self.lang, self.articles = out, data, lang, articles
        self.base = f'/wiki/{lang}/'
        self.asset_version = hashlib.sha256(b''.join(p.read_bytes() for p in [ROOT/'web/style.css', CONTENT/'style.css', CONTENT/'wiki.js'])).hexdigest()[:12]
        self.strings = json.loads((ROOT / f'web/i18n/{lang}.json').read_text())
        self.english = json.loads((ROOT / 'web/i18n/en.json').read_text())
        self.by_id = {s['id']: s for s in data['species']}
        self.moves = {m['id']: m for m in data['techniques']}
        self.icons = owned_icons()
        self.index = []
        self.records = {}
        self.places = model.place_names(data['files'], lang)
        en_names=json.loads(data['files']['text/ours/names.json'])
        self.names=model.localized_names(data['files'],lang)
        self.item_names={value.casefold():self.names.get(key,value) for key,value in en_names.items() if key.startswith('main.ITEM_NAMES.')}
        # Species food fields use content aliases, which can differ from displayed runtime names.
        for path,raw in data['files'].items():
            if path.startswith('content/items/') and path.endswith('.json'):
                item=json.loads(raw)
                self.item_names[item['name'].casefold()]=self.names.get('main.ITEM_NAMES.'+str(item['id']),item['name'])

    def t(self, key, **values):
        result = self.strings[key]
        for k, v in values.items():
            result = result.replace('{' + k + '}', str(v))
        return escape(result)

    def name(self, species):
        return model.recruits.species_name(self.data['files'], species['name'], self.lang)

    def url(self, species):
        return self.base + f'digimon/{species["id"]}-{model.slug(species["name"])}/'

    def move_name(self, move):
        return self.names.get('main.MOVE_NAMES.'+str(move['id']),move['name'])

    def move_url(self, move):
        return self.base + f'techniques/{move["id"]}-{model.slug(move["name"])}/'

    def image(self, species, size=64):
        name=self.icons.get(str(species['id']))
        if not name:return ''
        return f'<img class="owned-icon" src="/wiki/assets/owned-icons/{name}" width="{size}" height="{size}" loading="lazy" decoding="async" alt="{escape(self.name(species))}">'

    def badges(self, species):
        return f'<span class="badges"><span class="badge" data-level="{species["level"]}">{self.t("digimon.level."+species["level"])}</span><span class="badge" data-attribute="{species["attribute"]}">{self.t("digimon.attr."+species["attribute"])}</span></span>'

    def metadata(self, species):
        return dict(level=species['level'],attribute=species['attribute'],
                    levelLabel=self.strings['digimon.level.'+species['level']],
                    attributeLabel=self.strings['digimon.attr.'+species['attribute']],
                    specialties=plain(self.specs(species)))

    def specs(self, species):
        return ' / '.join(self.t('data.' + x) for x in species['specialties'])

    def label(self, species):
        return f'{self.t("digimon.level." + species["level"])} · {self.t("digimon.attr." + species["attribute"])}'

    def search_form(self, value=''):
        return f'<form class="searchbox" role="search" action="{self.base}search/"><label class="search-icon" for="wiki-query" aria-label="{self.t("wiki.search")}">⌕</label><input id="wiki-query" name="q" type="search" placeholder="{self.t("wiki.searchHint")}" value="{escape(value)}"><button class="button primary">{self.t("wiki.search")}</button></form>'

    def card(self, species):
        return f'<a class="species-card" data-level="{species["level"]}" href="{self.url(species)}">{self.image(species)}<div><h2>{escape(self.name(species))}</h2>{self.badges(species)}<small class="specialties">{self.specs(species)}</small></div></a>'

    def req(self, species):
        result = translate(species['requirements'], self.english, self.strings).strip()
        return result

    def page(self, path, title, body, kind, record=None):
        language_menu = ''.join(f'<option value="{k}" lang="{k}" {"selected" if k == self.lang else ""}>{v}</option>' for k, v in NAMES.items())
        links = [(self.base, 'wiki.nav'),(self.base+'digimon/', 'data.recruit.digimon'),(self.base+'guides/', 'wiki.articles'),(self.base+'search/', 'wiki.search')]
        nav = ''.join(f'<a href="{url}" {"aria-current=page" if url == self.base+path else ""}>{self.t(key)}</a>' for url, key in links)
        config = dict(lang=self.lang, base=self.base, kind=kind,
                      strings={key:self.strings[key] for key in ('wiki.results','wiki.empty','wiki.requirements','wiki.readGuide','digimon.count')},
                      records=self.records if kind in ('digimon','evolutions') else {})
        config_text = compact(config).replace('<', '\\u003c')
        hreflang = ''.join(f'<link rel="alternate" hreflang="{lang}" href="/wiki/{lang}/{path}">' for lang in model.LANGS)
        text = f'''<!doctype html>
<html lang="{self.lang}"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="theme-color" content="#cfd8f6"><title>{escape(title)} · Digimon World: Horizon</title><link rel="canonical" href="{self.base}{path}">{hreflang}<link rel="icon" href="/favicon.svg"><link rel="stylesheet" href="/style.css?v={self.asset_version}"><link rel="stylesheet" href="/wiki/assets/style.css?v={self.asset_version}"><script type="module" src="/wiki/assets/wiki.js?v={self.asset_version}"></script></head>
<body class="wiki-page" data-page="{kind}"><a class="skip" href="#main">{self.t('wiki.contents')}</a><div class="wrap"><header class="bar"><a class="brand" href="/">Digimon World: Horizon</a><nav class="pill" aria-label="{self.t('wiki.nav')}"><label class="lang"><select id="lang" aria-label="{self.t('lang.label')}">{language_menu}</select></label></nav></header><nav class="wiki-nav" aria-label="{self.t('wiki.nav')}">{nav}</nav><main class="wiki-main" id="main">{body}</main><footer class="foot"><p>{self.t('footer.legal')}</p></footer></div><dialog id="wiki-requirements"><button type="button" class="dialog-close" aria-label="{self.t('digimon.close')}">×</button><div class="requirement-body"></div></dialog><script type="application/json" id="wiki-config">{config_text}</script></body></html>\n'''
        dest = self.out / (self.base.strip('/') + '/' + path) / 'index.html'
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(text)
        if record:
            record['aliases']=record.get('aliases','')+' Horizon'
            self.index.append(dict(title=record.pop('title',title), url=self.base+path, **record))

    def article_card(self, ident, article):
        return f'<a class="card" href="{self.base}guides/{ident}/"><span class="eyebrow">{self.t("wiki.guideType")}</span><h2>{escape(article["title"])} ↗</h2><p>{escape(article["summary"])}</p></a>'

    def spoiler(self, html):
        return '<details class="spoiler"><summary>'+self.t('wiki.spoilers')+'</summary>'+html+'</details>'

    def species_cards(self, species):
        normal=''.join(self.card(s) for s in species if not s['spoiler'])
        secret=''.join(self.card(s) for s in species if s['spoiler'])
        return '<div class="species-grid">'+normal+'</div>'+(self.spoiler('<div class="species-grid">'+secret+'</div>') if secret else '')

    def bakemon(self, fold=True):
        conversation=model.bakemon_dialogue(self.data['files'],self.lang)
        rows=''.join('<tr><td>'+escape(r['question'])+'</td><td>'+escape(r['answer'])+'</td></tr>' for r in conversation['rows'])
        html='<div class="table-wrap"><table><thead><tr><th>'+self.t('wiki.question')+'</th><th>'+self.t('wiki.answer')+'</th></tr></thead><tbody>'+rows+'</tbody></table></div><p>'+escape(conversation['ending'])+'</p>'
        return self.spoiler(html) if fold else html

    def bakemon_mechanic(self):
        readable=model.bakemon_dialogue(self.data['files'],self.lang)['readable']
        return self.strings['wiki.bakemonPartner' if readable else 'wiki.bakemonGhost']

    def tree(self, species):
        self.records = {}
        def node(s, main=False):
            extra = ''
            hours = self.data['timed'].get((species['id'], s['id']))
            if hours:
                extra = '<br>' + self.t('digimon.after', hours=hours)
            self.records[str(s['id'])] = dict(name=self.name(s), html=self.req(s)+extra, url=self.url(s))
            return f'<a class="tree-node {"tree-current" if main else ""}" href="{self.url(s)}" data-species="{s["id"]}" {"aria-current=page" if main else ""}>{self.image(s,56)}<b>{escape(self.name(s))}</b>{self.badges(s)}<small class="specialties">{self.specs(s)}</small></a>'
        def graph(parents, targets, suffix):
            parent_html=''.join(node(self.by_id[i]) for i in parents) or f'<p>{self.t("digimon.hatches" if species["level"]=="fresh" else "digimon.noRoute")}</p>'
            target_html=''.join(node(self.by_id[i]) for i in targets) or f'<p>{self.t("digimon.noNext")}</p>'
            return f'<div class="tree-viewport" tabindex="0" role="region" aria-label="{self.t("data.evolutions")}"><div class="evolution-tree"><svg class="tree-edges" aria-hidden="true"><defs><marker id="arrow-{suffix}" markerWidth="7" markerHeight="7" refX="6" refY="3" orient="auto"><path d="M0 0L6 3L0 6" fill="none" stroke="currentColor"/></marker></defs><g></g></svg><div class="tree-column tree-parents">{parent_html}</div><div class="tree-column tree-focus">{node(species,True)}</div><div class="tree-column tree-targets">{target_html}</div></div></div>'
        parents,targets=species['parents'],species['to']
        normal=graph([i for i in parents if not self.by_id[i]['spoiler']], [i for i in targets if not self.by_id[i]['spoiler']], 'normal')
        secrets=any(self.by_id[i]['spoiler'] for i in parents+targets)
        extra=self.spoiler(graph(parents,targets,'spoiler')) if secrets else ''
        return '<p>'+self.t('wiki.treeHint')+'</p>'+normal+extra

    def recruit(self, row, identity_hidden=True, in_species=False):
        name = model.recruits.species_name(self.data['files'], row['name'], self.lang)
        places = ' · '.join(escape(self.places[i]) for i in row['screens'])
        service = self.t('data.recruit.service.' + row['service'])
        # Secret identities and locations stay folded; ordinary recruits show a useful summary.
        details=f'<p>{self.t("data.recruit.when."+str(row["id"]))}</p><p>{self.t("data.recruit.method."+str(row["id"]))}</p>'
        if row['name']=='Bakemon':
            details=self.bakemon(fold=False)
        if row['hp'] is not None:
            details+=f'<p>{self.t("data.recruit.hp",n=row["hp"])}</p>'
        if 'rematch_hp' in row:
            details+=f'<p>{self.t("data.recruit.rematchHp",n=row["rematch_hp"])}</p>'
        partner=next((s for s in self.data['species'] if s['name']==row['name']),None)
        heading=f'<a href="{self.url(partner)}">{escape(name)}</a>' if partner else escape(name)
        if in_species:heading=self.t('wiki.whereToRecruit')
        identity=f'<h2>{heading}</h2><p>{places}</p><div class="chips"><span class="chip">{service}</span><span class="chip">+{row["points"]} {self.t("data.recruit.points")}</span></div>'
        record=self.spoiler(identity+details) if identity_hidden else identity+self.spoiler(details)
        anchor=f'id="recruit-{row["id"]}"' if identity_hidden or in_species else f'data-recruit="recruit-{row["id"]}"'
        mechanic='<p>'+escape(self.bakemon_mechanic())+'</p>' if row['name']=='Bakemon' and in_species else ''
        return f'<section class="surface recruit-record" {anchor}>'+mechanic+record+'</section>'

    def species_pages(self):
        for species in self.data['species']:
            self.records = {}
            name = self.name(species)
            tree = self.tree(species)
            moves = []
            for entry in species['moves']:
                m = self.moves[entry['id']]
                finisher = 58 <= m['id'] <= 112
                power = species['finisher'].get('power',m['power']) if finisher else m['power']
                chance = str(entry['chance'])+'%' if entry['chance'] is not None else '—'
                moves.append(f'<tr><td><a href="{self.move_url(m)}">{escape(self.move_name(m))}</a>{"<br>"+self.t("data.finisher") if finisher else ""}</td><td>{power}</td><td>{m["baseMP"]}</td><td>{chance}</td></tr>')
            move_table = f'<div class="table-wrap"><table><thead><tr><th>{self.t("data.technique")}</th><th>{self.t("data.power")}</th><th>{self.t("data.mp")}</th><th>{self.t("wiki.learning")}</th></tr></thead><tbody>{"".join(moves)}</tbody></table></div>'
            p = species['partner']
            food = str(p.get('favorite_food','—'))
            food = self.item_names.get(food.casefold(),food)
            care = f'<section class="surface" id="care"><h2>{self.t("wiki.care")}</h2><dl class="facts"><dt>{self.t("wiki.food")}</dt><dd>{escape(food)}</dd><dt>{self.t("wiki.sleep")}</dt><dd>{escape(p.get("sleep_cycle","—"))}</dd><dt>{self.t("wiki.birthWeight")}</dt><dd>{p.get("birth_weight","—")}</dd></dl></section>'
            records = [self.recruit(r,identity_hidden=r['hidden'],in_species=True) for r in self.data['recruits'] if r['name']==species['name']]
            special = ''
            if species['special']:
                special = self.spoiler('<p>'+translate(escape(species['special']),self.english,self.strings).strip()+'</p>')
            body = f'<div class="page-title partner-title">{self.image(species,144)}<div><span class="eyebrow">#{species["id"]:03d}</span><h1>{escape(name)}</h1>{self.badges(species)}<p class="specialties">{self.specs(species)}</p></div></div><nav class="anchor-nav"><a href="#evolutions">{self.t("data.evolutions")}</a><a href="#techniques">{self.t("data.techniques")}</a><a href="#care">{self.t("wiki.care")}</a></nav><section class="surface" id="evolutions"><h2>{self.t("data.evolutions")}</h2>{tree}<details><summary>{self.t("wiki.requirements")}</summary><p>{self.req(species)}</p>{special}</details><p><a class="text-link" href="{self.base}guides/evolution-requirements/">{self.t("wiki.readGuide")} →</a></p></section><div class="detail-layout"><section class="surface" id="techniques"><h2>{self.t("data.techniques")}</h2>{move_table}<p class="muted">{self.t("wiki.slots")}</p><p class="muted">{self.t("data.costRule")}</p><a class="text-link" href="{self.base}guides/learning-techniques/">{self.t("wiki.readGuide")} →</a></section><aside>{care}{"".join(records)}</aside></div>'
            record=dict(type='digimon',text=plain(self.label(species)+' '+self.specs(species)),aliases=species['name'],**self.metadata(species))
            if species['spoiler']:
                # Native fragment navigation opens closed details ancestors. Keep public targets outside.
                anchors=re.findall(r' id="(evolutions|techniques|care|recruit-\d+)"',body)
                body=re.sub(r' id="(evolutions|techniques|care|recruit-\d+)"',r' data-spoiler-anchor="\1"',body)
                body=''.join('<span id="'+a+'" class="spoiler-anchor"></span>' for a in anchors)+self.spoiler(body)
                record.update(spoiler=True,title=name)
            self.page(f'digimon/{species["id"]}-{model.slug(species["name"])}/',plain(self.t('wiki.spoilers')) if species['spoiler'] else name,body,'digimon',record)
            if species['spoiler']:continue
            self.index.append(dict(type='evolution',title=name+' · '+plain(self.t('data.evolutions')),url=self.url(species)+'#evolutions',text=plain(self.req(species)),aliases=' '.join(self.by_id[i]['name'] for i in species['parents']+species['to'] if not self.by_id[i]['spoiler'])+' Horizon',**self.metadata(species)))

    def learning_section(self, move):
        ident = move['id']
        rows = self.data['learning_sources'][ident]
        if ident >= 58:
            content = f'<p>{self.t("wiki.notLearnable")}</p>'
        else:
            def source_table(secret):
                grouped = {}
                for row in rows:
                    if row['spoiler'] != secret: continue
                    grouped.setdefault(row['species'], []).append(row)
                rendered = []
                for sid,places in grouped.items():
                    enemy = self.data['enemies'][sid]
                    target = self.enemy_target(enemy)
                    labels = []
                    for row in places:
                        label = escape(self.places[row['screen']])
                        recruit = next((r for r in self.data['recruits'] if r['id']==target['id'] and row['screen'] in r['screens']),None)
                        if recruit and row['kind']=='scripted':
                            label = f'<a href="{self.url(target)}#recruit-{recruit["id"]}">{label}</a>'
                        hours = row['hours']
                        if len(hours) < 24:
                            spans=[]; start=previous=hours[0]
                            for hour in hours[1:]+[25]:
                                if hour != previous+1:
                                    spans.append(f'{start:02}:00–{previous+1:02}:00')
                                    start=hour
                                previous=hour
                            label += ' · ' + ', '.join(spans)
                        if 'via' in row: label += ' · '+self.t('wiki.aliasSource')+f' <a href="{self.move_url(self.moves[row["via"]])}">{escape(self.move_name(self.moves[row["via"]]))} #{row["via"]}</a>'
                        if row['conditional']: label += ' <sup>*</sup>'
                        if row['condition']: label += f' <small>{self.t("wiki."+row["condition"]+"Source")}</small>'
                        if label not in labels: labels.append(label)
                    rendered.append(f'<tr><th scope="row"><a href="{self.url(target)}">{escape(self.name(enemy))}</a></th><td>'+ '<br>'.join(labels)+'</td></tr>')
                if not rendered: return ''
                return f'<div class="table-wrap"><table><thead><tr><th>{self.t("wiki.enemy")}</th><th>{self.t("wiki.places")}</th></tr></thead><tbody>'+''.join(rendered)+'</tbody></table></div>'
            normal,secret = source_table(False),source_table(True)
            content = normal + (self.spoiler(secret) if secret else '')
            if any(r['conditional'] for r in rows): content += f'<p class="muted"><small>* {self.t("wiki.availability")}</small></p>'
            if not rows: content = f'<p>{self.t("wiki.noEnemy")}</p>'
            if ident in self.data['technique_aliases']:
                other = self.moves[self.data['technique_aliases'][ident]]
                content += f'<p>{self.t("wiki.sharedUnlock")} <a href="{self.move_url(other)}#learn">{escape(self.move_name(other))} #{other["id"]}</a></p>'
            brain = self.data['brain_learning'][ident]
            content += f'<h3>{self.t("wiki.brainsGym")}</h3>'
            if brain['positions']:
                content += f'<p>{self.t("wiki.brainsRule",marks=", ".join(map(str,brain["marks"])),orders=", ".join(map(str,brain["orders"])))}</p>'
                order_table = model.read_json(self.data['files'],'content/tables/brain-training.json')['brainTraining']['techniques']
                for position in brain['positions']:
                    content += f'<p>{self.t("wiki.brainsWeights",weights=" / ".join(f"{i+1}: {w}%" for i,w in enumerate(position["weights"])))}</p>'
                    order = ' → '.join(f'<a href="{self.move_url(self.moves[i])}">{escape(self.move_name(self.moves[i]))}</a>' for i in order_table[position['element']])
                    content += f'<details><summary>{self.t("wiki.trainingOrder")} · {self.t("data."+position["element"])}</summary><p>{order}</p></details>'
            else:
                content += f'<p>{self.t("wiki.noBrains")}</p>'
            content += f'<p class="muted">{self.t("wiki.arenaNoLearning")}</p>'
        return f'<section class="surface" id="learn"><h2>{self.t("wiki.whereLearn")}</h2>{content}</section>'

    def enemy_target(self, enemy):
        return self.by_id.get(enemy['id']) or next((s for s in self.data['species'] if s['name']==enemy['name']),enemy)

    def enemy_pages(self):
        # Enemy-only species have no partner care/evolutions; still give sources a real destination.
        ids = {r['species'] for rows in self.data['learning_sources'].values() for r in rows}
        for sid in sorted(ids):
            enemy = self.data['enemies'][sid]
            if self.enemy_target(enemy)['id'] != sid or sid in self.by_id: continue
            links = ''.join(f'<li><a href="{self.move_url(move)}#learn">{escape(self.move_name(move))}</a></li>' for move in self.data['techniques'] if any(r['species']==sid for r in self.data['learning_sources'][move['id']]))
            body = f'<h1>{escape(self.name(enemy))}</h1><section class="surface"><h2>{self.t("data.techniques")}</h2><ul>{links}</ul></section>'
            secret = all(r['spoiler'] for rows in self.data['learning_sources'].values() for r in rows if r['species']==sid)
            self.page(f'digimon/{sid}-{model.slug(enemy["name"])}/',plain(self.t('wiki.spoilers')) if secret else self.name(enemy),self.spoiler(body) if secret else body,'digimon')

    def technique_pages(self):
        cards=[]
        for move in self.data['techniques']:
            ident=move['id']
            species=[s for s in self.data['species'] if any(m['id']==ident for m in s['moves'])]
            chance = ' / '.join(f'{i+1}: {n}%' for i,n in enumerate(move.get('learnChances',[]))) or '—'
            range_key={0:'other',1:'melee',2:'ranged',3:'area',4:'buff'}.get(move['range'],'other')
            status_key={0:None,1:'poison',2:'confusion',3:'stun',4:'flatten'}.get(move['status'])
            status=self.t('data.'+status_key)+f' ({move["statusChance"]}%)' if status_key else '—'
            stats=f'<dl class="facts"><dt>{self.t("data.range")}</dt><dd>{self.t("data."+range_key)}</dd><dt>{self.t("data.status")}</dt><dd>{status}</dd><dt>{self.t("data.specialty")}</dt><dd>{self.t("data."+str(move["element"] if isinstance(move["element"],str) else "other"))}</dd><dt>{self.t("data.power")}</dt><dd>{move["power"]}</dd><dt>{self.t("data.mp")}</dt><dd>{move["baseMP"]}</dd><dt>{self.t("wiki.learning")}</dt><dd>{chance}</dd></dl>'
            partner_heading = self.t("wiki.canLearn" if ident<58 else "data.recruit.digimon")
            body=f'<div class="page-title"><span class="eyebrow">{self.t("data.technique")} #{ident}</span><h1>{escape(self.move_name(move))}</h1></div>{self.learning_section(move)}<section class="surface">{stats}<p>{self.t("data.learningRule")}</p><p>{self.t("data.brainsRule")} {self.t("data.oneRule")}</p><p>{self.t("data.costRule")}</p></section><h2>{partner_heading}</h2>'+self.species_cards(species)
            path=f'techniques/{ident}-{model.slug(move["name"])}/'
            self.page(path,self.move_name(move)+' #'+str(ident),body,'technique',dict(type='technique',text=plain(self.t('data.'+str(move['element'] if isinstance(move['element'],str) else 'other')))+' · '+str(move['power']),aliases=move['name']+' '+' '.join(s['name'] for s in species if not s['spoiler'])))
            cards.append(f'<a class="card" href="{self.move_url(move)}"><h2>{escape(self.move_name(move))}</h2><small>#{ident}</small><p>{self.t("data."+str(move["element"] if isinstance(move["element"],str) else "other"))} · {self.t("data.power")} {move["power"]} · MP {move["baseMP"]}</p></a>')
        self.page('techniques/',plain(self.t('data.techniques')),f'<div class="page-title"><h1>{self.t("data.techniques")}</h1></div>{self.search_form()}<div class="cards">'+''.join(cards)+'</div>','techniques')

    def fact_block(self,ident):
        facts=self.data['facts']
        if ident in ('getting-started','duckstation-desktop','duckstation-android','epsxe','retroarch','iphone-web','memory-cards','faq'):
            return f'<aside class="note">{self.t("wiki.saveBlocks",n=facts["save_blocks"])}</aside>'
        if ident=='evolution-timing':
            # evolution-rules.json spells the level keys in camelCase (inTraining), the guide's level names use hyphens.
            level_key=lambda key: re.sub(r'([A-Z])',lambda m:'-'+m.group(1).lower(),key)
            rows=''.join(f'<tr><th>{self.t("digimon.level."+level_key(level))}</th><td>{hours}</td></tr>' for level,hours in facts['timing']['hours'].items() if level_key(level) in model.guide.LEVELS and level!='ultimate')
            ultimate=self.t('digimon.level.ultimate')
            rows+=f'<tr><th>{ultimate} → Machinedramon</th><td>{facts["timing"]["hours"]["ultimate"]}</td></tr>'
            rows+=f'<tr><th>{ultimate} → {self.t("digimon.level.mega")}</th><td>{facts["timing"].get("megaHours",120)}</td></tr>'
            return self.spoiler(f'<h2>{self.t("wiki.timing")}</h2><div class="table-wrap"><table>{rows}</table></div>')
        if ident=='file-city':
            rows=''.join(f'<tr><th>{i}</th><td>{escape(self.names["main.ITEM_NAMES."+str(give)])}</td><td>→</td><td>{escape(self.names["main.ITEM_NAMES."+str(take)])}</td></tr>' for i,(give,take) in enumerate(facts['mojyamon'],1))
            return self.spoiler('<h2>'+escape(self.name(self.by_id[52]))+'</h2><div class="table-wrap"><table>'+rows+'</table></div>')
        if ident=='training':
            labels={'hp':'hp','mp':'mp','off':'offense','def':'defense','spd':'speed','brain':'brains'}
            entries=facts['training-gains']['trainGain']
            rows=[]
            for row in entries:
                if row.get('slot')!=0:continue
                stat=next((k for k in labels if k in row),'hp')
                rows.append(f'<tr><th>{self.t("data."+labels[stat])}</th><td>{row[stat]}</td><td>{row["tired"]}</td></tr>')
            return f'<div class="table-wrap"><table><tr><th>{self.t("digimon.stats")}</th><th>{self.t("wiki.gain")}</th><th>{self.t("wiki.tired")}</th></tr>{"".join(rows)}</table></div>'
        if ident=='difficulty':
            if not facts['hard']:return ''
            # Numeric config is rendered with localized labels; named factors are not prose copies.
            labels={'hp':'hp','offense':'offense','defense':'defense','speed':'speed','brain':'brains','brains':'brains'}
            rows=''.join(f'<tr><th>{self.t("wiki."+k)}</th><td>{escape(str(v))}</td></tr>' for k,v in facts['hard'].items() if not isinstance(v,(dict,list)))
            return '<aside class="note">'+self.t('wiki.hardPresent')+'</aside><div class="table-wrap"><table>'+rows+'</table></div>'
        if ident=='new-game-quiz':
            quiz=facts['new-game']['newGame']['quiz']; starters=facts['new-game']['newGame']['starters']
            axes={'battle':'data.battle','fire':'data.fire','ice':'data.ice','nature':'data.nature','air':'data.air','vaccine':'digimon.attr.vaccine','data':'digimon.attr.data','virus':'digimon.attr.virus'}
            # Temperament labels are translations in a separate reviewable catalog.
            terms=json.loads((CONTENT/'quiz-terms.json').read_text())[self.lang]
            def axis(key):return self.t(axes[key]) if key in axes else escape(terms[key])
            dialogue=json.loads(self.data['files'][f'text/{self.lang}.json'])
            def clean(value):
                return re.sub(r'\{[^}]+\}', '', value).strip()
            points=[]
            for q,answers in enumerate(quiz['weights'],1):
                for a,weights in enumerate(answers,1):
                    question=' '.join(clean(x) for x in dialogue[f'name.quiz.q{q}.question'][1:])
                    answer=clean(dialogue[f'name.quiz.q{q}.answers'][a])
                    points.append(f'<tr><td>{q}. {escape(question)}</td><td>{a}. {escape(answer)}</td><td>'+', '.join(f'{axis(k)} +{v}' for k,v in weights.items())+'</td></tr>')
            cells=[]
            for i,(on,off) in enumerate(zip(quiz['cells'],quiz['vanillaCells'])):
                element=('battle','fire','ice','nature','air')[i//9];attribute=('vaccine','data','virus')[(i//3)%3];temperament=('bold','calm','cunning')[i%3]
                links=[]
                for index in (on,off):
                    s=self.by_id[starters[index]];links.append(f'<a href="{self.url(s)}">{escape(self.name(s))}</a>')
                cells.append(f'<tr><th>{axis(element)} / {axis(attribute)} / {axis(temperament)}</th><td>{links[0]}</td><td>{links[1]}</td></tr>')
            return f'<h2>{self.t("wiki.quizPoints")}</h2><div class="table-wrap"><table><thead><tr><th>{self.t("wiki.question")}</th><th>{self.t("wiki.answer")}</th><th>{self.t("wiki.quizPoints")}</th></tr></thead><tbody>{"".join(points)}</tbody></table></div><h2>{self.t("wiki.starter")}</h2><div class="table-wrap"><table><thead><tr><th>{self.t("wiki.starter")}</th><th>{self.t("wiki.newOn")}</th><th>{self.t("wiki.newOff")}</th></tr></thead><tbody>{"".join(cells)}</tbody></table></div>'
        return ''

    def article_pages(self):
        values=dict(bakemon_mechanic=self.bakemon_mechanic(),save_blocks=self.data['facts']['save_blocks'],pass_points=self.data['facts']['score']['passPoints'],
                    mega_hours=self.data['facts']['timing']['megaHours'],
                    chain_melon=self.names['main.ITEM_NAMES.70'],digiseabass=self.names['main.ITEM_NAMES.67'],
                    chain_melon_hours=self.data['facts']['chain_melon_hours'],
                    digiseabass_hours=self.data['facts']['digiseabass_hours'])
        for ident,article in self.articles.items():
            paras=[p.format(**values) for p in article['paragraphs']]
            if values['save_blocks']==1:
                singular={'en':{'1 free blocks':'1 free block','1 blocks':'1 block'},'es':{'1 bloques libres':'1 bloque libre'},'pt-br':{'1 blocos livres':'1 bloco livre'},'fr':{'1 blocs libres':'1 bloc libre'},'de':{'1 freien Blöcken':'1 freiem Block','1 freie Blöcke':'1 freien Block','1 Blöcke':'1 Block'},'it':{'1 blocchi liberi':'1 blocco libero'},'ca':{'1 blocs lliures':'1 bloc lliure'}}
                for plural,one in singular.get(self.lang,{}).items():
                    paras=[p.replace(plural,one) for p in paras]
            heading_keys=['wiki.before','wiki.settings','wiki.memoryCards','wiki.troubleshooting'] if ident=='duckstation-android' else ['wiki.basics','wiki.how','wiki.remember']
            toc=''.join(f'<a href="#step-{i}">{self.t(heading_keys[i])}</a>' for i in range(len(paras)))
            body=f'<div class="page-title"><span class="eyebrow">{self.t("wiki.guideType")}</span><h1>{escape(article["title"])}</h1><p>{escape(article["summary"])}</p></div><div class="article-layout"><nav class="toc" aria-label="{self.t("wiki.contents")}"><b>{self.t("wiki.contents")}</b>{toc}<a href="#related">{self.t("wiki.related")}</a></nav><article class="surface article-body">'+''.join(f'<section id="step-{i}"><h2>{self.t(heading_keys[i])}</h2>'+(self.spoiler('<p>'+escape(p)+'</p>') if i in article.get('spoiler_paragraphs',[]) else '<p>'+escape(p)+'</p>')+'</section>' for i,p in enumerate(paras))+(self.spoiler(self.fact_block(ident)) if ident=='new-game-quiz' else self.fact_block(ident))+(self.bakemon() if ident=='hidden-mechanics' else '')+f'<h2 id="related">{self.t("wiki.related")}</h2><a class="text-link" href="{self.base}guides/">{self.t("wiki.articles")} →</a></article></div>'
            self.page(f'guides/{ident}/',article['title'],body,'article',dict(type='article',text=' '.join(p for i,p in enumerate(paras) if i not in article.get('spoiler_paragraphs',[])),summary=article['summary'],aliases=ident.replace('-',' ')))
        self.page('guides/',plain(self.t('wiki.articles')),f'<div class="page-title"><h1>{self.t("wiki.articles")}</h1></div><div class="cards">'+''.join(self.article_card(k,a) for k,a in self.articles.items())+'</div>','articles')

    def directories(self):
        cards=self.species_cards(self.data['species'])
        levels=''.join(f'<button type="button" data-level="{level}" aria-pressed="{str(not level).lower()}">{self.t("digimon.level."+level if level else "digimon.allLevels")}</button>' for level in ['',*model.guide.LEVELS])
        self.page('digimon/',plain(self.t('data.recruit.digimon')),f'<div class="page-title"><h1>{self.t("data.recruit.digimon")}</h1><p id="digimon-count" role="status">{self.t("digimon.count",n=len(self.data["species"]))}</p></div>{self.search_form()}<div class="filters" role="group" aria-label="{self.t("digimon.levels")}">{levels}</div>{cards}','digimon-list')
        self.records={}
        s=self.by_id[3]
        options=''.join(f'<option value="{self.url(sp)}#evolutions" {"selected" if sp["id"]==3 else ""}>{escape(self.name(sp))}</option>' for sp in self.data['species'] if not sp['spoiler'])
        body=f'<div class="page-title"><h1>{self.t("data.evolutions")}</h1><p>{self.t("wiki.newOn")}</p></div><label class="tree-picker">{self.t("data.recruit.digimon")} <select id="tree-picker">{options}</select></label><section class="surface">{self.tree(s)}</section><a class="text-link" href="{self.base}guides/evolution-requirements/">{self.t("wiki.readGuide")} →</a>'
        self.page('evolutions/',plain(self.t('data.evolutions')),body,'evolutions',dict(type='evolution',text=plain(self.t('wiki.treeHint')),aliases='evolution tree Agumon'))
        recruit_cards=''.join(f'<span class="spoiler-anchor" id="recruit-{r["id"]}"></span>' for r in self.data['recruits'])+self.spoiler(''.join(self.recruit(r,identity_hidden=False) for r in self.data['recruits']))
        self.page('recruits/',plain(self.t('data.recruits')),f'<div class="page-title"><h1>{self.t("data.recruits")}</h1><p>{self.t("data.recruit.intro")}</p></div><aside class="note">{escape(self.bakemon_mechanic())}</aside>{recruit_cards}','recruits')
        for row in self.data['recruits']:
            name=model.recruits.species_name(self.data['files'],row['name'],self.lang)
            self.index.append(dict(type='recruit',title=name,url=self.base+f'recruits/#recruit-{row["id"]}',text=' · '.join(self.places[i] for i in row['screens'])+' · '+plain(self.t('data.recruit.service.'+row['service'])),aliases=row['name']+' Horizon',spoiler=True))
        self.records={}
        links=''.join(f'<a href="{self.base}{path}/"><b>{self.t(key)} ↗</b><span>{count}</span></a>' for path,key,count in [('digimon','data.recruit.digimon',len(self.data['species'])),('techniques','data.techniques',len(self.data['techniques'])),('evolutions','data.evolutions',''),('recruits','data.recruits',len(self.data['recruits']))])
        featured=''.join(self.article_card(k,self.articles[k]) for k in ('duckstation-android','care','evolution-requirements'))
        body=f'<div class="intro"><span class="eyebrow">{self.t("wiki.nav")}</span><h1>{self.t("wiki.title")}</h1><p>{self.t("wiki.lead")}</p>{self.search_form()}</div><div class="section-heading"><h2>{self.t("wiki.start")}</h2></div><div class="cards">{featured}</div><div class="section-heading"><h2>{self.t("wiki.lookup")}</h2></div><div class="data-links">{links}</div><div class="section-heading"><h2>{self.t("wiki.articles")}</h2><a href="{self.base}guides/">{self.t("wiki.all")} →</a></div><div class="cards">'+''.join(self.article_card(k,self.articles[k]) for k in ('memory-cards','new-game-quiz','difficulty'))+'</div><div class="section-heading"><h2>'+self.t('data.recruit.digimon')+'</h2></div><div class="species-grid">'+''.join(self.card(self.by_id[i]) for i in (3,17,45))+'</div>'
        self.page('',plain(self.t('wiki.nav')),body,'home')
        types=[('all','wiki.all'),('article','wiki.articles'),('digimon','data.recruit.digimon'),('technique','data.techniques'),('recruit','data.recruits'),('evolution','data.evolutions')]
        filters=''.join(f'<button type="button" data-filter="{kind}" aria-pressed="{str(kind=="all").lower()}">{self.t(label)}</button>' for kind,label in types)
        body=f'<div class="page-title"><h1>{self.t("wiki.search")}</h1><p>{self.t("wiki.searchScope")}</p></div>{self.search_form()}<div class="filters">{filters}</div><p id="search-count" role="status" aria-live="polite"></p><div id="search-results" class="surface"></div><noscript><a href="{self.base}digimon/">{self.t("data.recruit.digimon")}</a> · <a href="{self.base}guides/">{self.t("wiki.articles")}</a></noscript>'
        self.page('search/',plain(self.t('wiki.search')),body,'search')
        (self.out/self.base.strip('/')/'search-index.json').write_text(compact(self.index)+'\n')


def redirect(path, target, out, legacy=False, mapping=None):
    path.parent.mkdir(parents=True,exist_ok=True)
    config=compact(dict(target=target,legacy=legacy,mapping=mapping or {})).replace('<','\\u003c')
    path.write_text(f'<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Horizon Wiki</title><script type="module" src="/wiki/assets/redirect.js"></script></head><body><a href="{target}">Horizon Wiki →</a><script type="application/json" id="wiki-redirect">{config}</script></body></html>\n')


def build(out, tag, presentation_ref=None):
    if not re.fullmatch(r'v\d+\.\d+\.\d+',tag):
        raise ValueError('Wiki requires an explicit release tag')
    data=model.load(tag)
    article_root=article_catalogs.directory(tag, CONTENT/'articles')
    review=article_catalogs.validate(article_root)
    dest=out/'wiki'
    if dest.exists():shutil.rmtree(dest)
    assets=dest/'assets';assets.mkdir(parents=True)
    for name in ('style.css','wiki.js','redirect.js'):
        shutil.copyfile(CONTENT/name,assets/name)
    icons=owned_icons()
    if not set(icons)<=set(str(s['id']) for s in data['species']):
        raise ValueError('Owned icon maps an unknown species')
    for name in set(icons.values()):
        (assets/'owned-icons').mkdir(exist_ok=True)
        shutil.copyfile(CONTENT/'owned-icons'/name,assets/'owned-icons'/name)
    for lang in model.LANGS:
        articles=json.loads((article_root/f'{lang}.json').read_text())
        pages=Pages(out,data,lang,articles)
        pages.species_pages();pages.enemy_pages();pages.technique_pages();pages.article_pages();pages.directories()
        mapping={f'species-{s["id"]}':pages.url(s) for s in data['species']}
        mapping.update({k:pages.base+v+'/' for k,v in [('species','digimon'),('techniques','techniques'),('evolutions','evolutions'),('recruits','recruits')]})
        mapping.update({f'recruit-{r["id"]}':pages.base+f'recruits/#recruit-{r["id"]}' for r in data['recruits']})
        redirect(out/'data'/('index.html' if lang=='en' else lang+'.html'),pages.base,out,True,mapping)
    redirect(dest/'index.html','/wiki/en/',out)
    presentation=__import__('subprocess').check_output(['git','rev-parse','--verify',(presentation_ref or 'HEAD')+'^{commit}'],cwd=ROOT,text=True).strip()
    manifest=dict(schema=1,tag=tag,commit=data['commit'],presentation_commit=presentation,articles=review,counts={k:len(data[k]) for k in ('species','techniques','recruits')},facts=dict(save_blocks=data['facts']['save_blocks'],hard=bool(data['facts']['hard'])))
    (dest/'manifest.json').write_text(compact(manifest)+'\n')
    sizes=budget(out)
    print(f'Wiki {tag}: {len(data["species"])} species, 20 articles × 9 languages; {sizes["wiki_bytes"]:,} bytes')
    return manifest


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',type=Path,required=True);parser.add_argument('--tag',required=True)
    args=parser.parse_args();build(args.out,args.tag)
