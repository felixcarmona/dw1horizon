import {guess} from '/js/i18n.js';
const config=JSON.parse(document.querySelector('#wiki-redirect').textContent);
let target=config.target;
if(config.legacy){
  const anchor=location.hash.slice(1);
  target=config.mapping[anchor]||target;
}else if(location.pathname==='/wiki/'||location.pathname==='/wiki/index.html'){
  target=target.replace('/wiki/en/','/wiki/'+guess()+'/');
}
const params=new URLSearchParams(location.search);
if(params.get('section')==='digimon'&&!config.legacy){target+='digimon/';params.delete('section');}
const query=params.size?'?'+params:'';
const url=new URL(target,location.origin);
url.search=query;
if(!url.hash)url.hash=location.hash;
location.replace(url.href);
