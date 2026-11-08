const config = JSON.parse(document.querySelector('#wiki-config').textContent);
const menu = document.querySelector('#lang');
menu.addEventListener('change', () => {
  try { localStorage.setItem('horizon.lang', menu.value); } catch {}
  location.href = location.pathname.replace(`/wiki/${config.lang}/`, `/wiki/${menu.value}/`) + location.search + location.hash;
});
const picker = document.querySelector('#tree-picker');
if (picker) picker.addEventListener('change', () => { location.href = picker.value; });

if(config.kind==='digimon-list'){
  const applyLevel=level=>{
    let count=0;
    for(const card of document.querySelectorAll('.species-card')){card.hidden=!!level&&card.dataset.level!==level;if(!card.hidden)count++;}
    for(const b of document.querySelectorAll('button[data-level]'))b.setAttribute('aria-pressed',String(b.dataset.level===level));
    document.querySelector('#digimon-count').textContent=config.strings['digimon.count'].replace('{n}',count);
    const params=new URLSearchParams(location.search);if(level)params.set('level',level);else params.delete('level');
    history.replaceState(null,'',location.pathname+(params.size?'?'+params:''));
  };
  for(const b of document.querySelectorAll('button[data-level]'))b.addEventListener('click',()=>applyLevel(b.dataset.level));
  applyLevel(new URLSearchParams(location.search).get('level')||'');
}

const dialog = document.querySelector('#wiki-requirements');
dialog.querySelector('button').addEventListener('click', () => dialog.close());
dialog.addEventListener('click', e => { if (e.target === dialog) dialog.close(); });
for (const node of document.querySelectorAll('.tree-node:not(.tree-current)')) {
  node.addEventListener('click', event => {
    event.preventDefault();
    const record = config.records[node.dataset.species];
    const box = dialog.querySelector('.requirement-body');
    box.replaceChildren();
    const title = document.createElement('h2'); title.textContent = record.name;
    const requirements = document.createElement('p'); requirements.innerHTML = record.html;
    const link = document.createElement('a'); link.href = record.url; link.className = 'button primary'; link.textContent = record.name + ' →';
    box.append(title, requirements, link);
    dialog.showModal();
  });
}
function drawTree() {
  for (const graph of document.querySelectorAll('.evolution-tree')) {
  if (!graph.getClientRects().length) continue;
  const bounds = graph.getBoundingClientRect();
  const svg = graph.querySelector('svg');
  svg.setAttribute('viewBox', `0 0 ${bounds.width} ${bounds.height}`);
  const focus = graph.querySelector('.tree-current').getBoundingClientRect();
  const group = svg.querySelector('g'); group.replaceChildren();
  const vertical=matchMedia('(max-width:650px)').matches;
  const connect = (a, b, target=false) => {
    const x1=a.right-bounds.left, y1=(a.top+a.bottom)/2-bounds.top;
    const x2=b.left-bounds.left, y2=(b.top+b.bottom)/2-bounds.top;
    const mid=(x1+x2)/2;
    const path=document.createElementNS('http://www.w3.org/2000/svg','path');
    if(vertical){
      const ax=(a.left+a.right)/2-bounds.left, ay=a.bottom-bounds.top;
      const bx=(b.left+b.right)/2-bounds.left, by=b.top-bounds.top;
      if(target){
        const endX=b.left-bounds.left-6,endY=(b.top+b.bottom)/2-bounds.top;
        path.setAttribute('d',`M${ax} ${ay}C${ax} ${ay+18},12 ${ay+18},12 ${ay+36}V${endY}H${endX}`);
      }else if(graph.querySelectorAll('.tree-parents .tree-node').length>1){
        const startX=a.right-bounds.left,startY=(a.top+a.bottom)/2-bounds.top;
        path.setAttribute('d',`M${startX} ${startY}H${bounds.width-12}V${by-18}H${bx}V${by-6}`);
      }else path.setAttribute('d',`M${ax} ${ay}C${ax} ${(ay+by)/2},${bx} ${(ay+by)/2},${bx} ${by-6}`);
    }else path.setAttribute('d',`M${x1} ${y1}C${mid} ${y1},${mid} ${y2},${x2-6} ${y2}`);
    path.setAttribute('marker-end',`url(#${svg.querySelector('marker').id})`); group.append(path);
  };
  for(const parent of graph.querySelectorAll('.tree-parents .tree-node')) connect(parent.getBoundingClientRect(),focus);
  for(const target of graph.querySelectorAll('.tree-targets .tree-node')) connect(focus,target.getBoundingClientRect(),true);
  }
}
if (document.querySelector('.evolution-tree')) {
  const observer=new ResizeObserver(drawTree);
  for(const graph of document.querySelectorAll('.evolution-tree')) observer.observe(graph);
  for(const spoiler of document.querySelectorAll('details')) spoiler.addEventListener('toggle',drawTree);
  await document.fonts.ready; drawTree();
}
if (config.kind === 'search') {
  const input = document.querySelector('#wiki-query');
  const params = new URLSearchParams(location.search);
  input.value = params.get('q') || '';
  let type = params.get('type') || 'all';
  const entries = await fetch(config.base + 'search-index.json', {cache:'no-cache'}).then(r => {
    if (!r.ok) throw new Error('Search index unavailable');
    return r.json();
  });
  const fold = text => text.normalize('NFKD').replace(/\p{M}/gu,'').toLocaleLowerCase(config.lang).replace(/[^\p{L}\p{N}]+/gu,' ').trim();
  const indexed = entries.map(e => ({...e, folded:fold(e.title+' '+e.text+' '+e.aliases), titleFold:fold(e.title)}));
  const labels={article:'wiki.articles',digimon:'data.recruit.digimon',technique:'data.techniques',recruit:'data.recruits',evolution:'data.evolutions'};
  const strings = await fetch(`/i18n/${config.lang}.json`).then(r=>r.json());
  const render = () => {
    const q=fold(input.value), words=q.split(/\s+/).filter(Boolean);
    const found=indexed.filter(e=>(type==='all'||e.type===type)&&words.every(w=>e.folded.includes(w)))
      .map(e=>({...e,rank:e.titleFold===q?0:e.titleFold.split(/\s+/).includes(q)?1:e.titleFold.startsWith(q)?2:e.titleFold.includes(q)?3:4}))
      .sort((a,b)=>a.rank-b.rank||a.title.localeCompare(b.title,config.lang,{numeric:true}));
    document.querySelector('#search-count').textContent=config.strings['wiki.results'].replace('{n}',found.length);
    const results=document.querySelector('#search-results');results.replaceChildren();
    const spoilers=document.createElement('details');spoilers.className='spoiler';
    const spoilerLabel=document.createElement('summary');spoilerLabel.textContent=strings['wiki.spoilers'];spoilers.append(spoilerLabel);
    for(const entry of found){
      const a=document.createElement('a');a.className='result';a.href=entry.url;a.dataset.kind=entry.type;
      const label=document.createElement('span');label.className='eyebrow';label.textContent=strings[labels[entry.type]];
      const title=document.createElement('h2');title.textContent=entry.title+' ↗';
      const summary=document.createElement('p');summary.textContent=entry.specialties||entry.summary||entry.text.slice(0,220);
      a.append(label,title);
      if(entry.level&&entry.attribute){
        const badges=document.createElement('span');badges.className='badges';
        for(const [key,text] of [['level',entry.levelLabel],['attribute',entry.attributeLabel]]){
          const badge=document.createElement('span');badge.className='badge';badge.dataset[key]=entry[key];badge.textContent=text;badges.append(badge);
        }
        a.append(badges);
      }
      a.append(summary);(entry.spoiler?spoilers:results).append(a);
    }
    if(spoilers.children.length>1)results.append(spoilers);
    if(!found.length) results.textContent=config.strings['wiki.empty'];
    for(const b of document.querySelectorAll('[data-filter]')) b.setAttribute('aria-pressed',String(b.dataset.filter===type));
    const query=new URLSearchParams();if(input.value)query.set('q',input.value);if(type!=='all')query.set('type',type);
    history.replaceState(null,'',location.pathname+(query.size?'?'+query:''));
  };
  document.querySelector('.searchbox').addEventListener('submit',e=>{e.preventDefault();render();});
  input.addEventListener('input',render);
  for(const b of document.querySelectorAll('[data-filter]')) b.addEventListener('click',()=>{type=b.dataset.filter;render();});
  render();
}
if(location.hash.startsWith('#recruit-')) {
  const record=document.querySelector(location.hash);
  // A deep link moves to the record but never opens a spoiler without a tap.
  if(record) record.scrollIntoView();
}

// Fragment proxies prevent browsers from opening spoilers during navigation.
// Once the reader opens a disclosure, move to its now-visible linked record.
for(const spoiler of document.querySelectorAll('.spoiler')) spoiler.addEventListener('toggle',()=>{
  if(!spoiler.open||!location.hash)return;
  const key=decodeURIComponent(location.hash.slice(1));
  const record=[...spoiler.querySelectorAll('[data-recruit],[data-spoiler-anchor]')].find(e=>e.dataset.recruit===key||e.dataset.spoilerAnchor===key);
  if(record?.checkVisibility())record.scrollIntoView({block:'start'});
});
