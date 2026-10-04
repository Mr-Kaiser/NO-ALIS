'use strict';
const $ = id => document.getElementById(id);
const state = {data:null,platform:null,station:null,rows:[],selected:new Set(),base:new Set(),keyRows:new Map(),filter:'all',busy:false,ticket:null,restore:null,layout:null,theme:null,presets:null};
const token = document.querySelector('meta[name="alis-token"]').content;
const el = (tag, cls, value) => {const n=document.createElement(tag);if(cls)n.className=cls;if(value!==undefined)n.textContent=value;return n;};
async function api(path, body) {
  const response=await fetch(path,{method:body===undefined?'GET':'POST',headers:body===undefined?{}:{'Content-Type':'application/json','X-ALIS-Token':token},body:body===undefined?undefined:JSON.stringify(body)});
  const data=await response.json();
  if(!response.ok){const error=new Error(data.error||`Request failed (${response.status})`);error.status=response.status;throw error;}
  return data;
}
function url(suffix=''){return `/api/platforms/${encodeURIComponent(state.platform.name)}/stations/${state.station.index}${suffix}`;}
function changes(){
  const added=state.rows.filter(w=>state.selected.has(w.id)&&!state.base.has(w.id)).map(w=>w.key);
  const removed=state.station?state.station.allowed.filter(key=>!state.selected.has(state.keyRows.get(key))):[];
  return {add:added,remove:removed};
}
function dirty(){const c=changes();return c.add.length+c.remove.length>0;}
function mayLeave(){return !dirty()||window.confirm('Discard the unsaved changes on this station?');}
function notice(text, kind=''){$('message').textContent=text;$('message').className=`message ${kind}`;$('message').classList.toggle('hidden',!text);}
function setBusy(value){state.busy=value;updateDraft();$('reload-all').disabled=value;$('allow-empty').disabled=value;$('edit-layout').disabled=value||!state.platform;$('theme-open').disabled=value||!state.data;$('presets-open').disabled=value||!state.platform;$('categories-open').disabled=value||!state.data;$('platform-tags-edit').disabled=value||!state.platform;document.querySelectorAll('.platform-item,.station-item,.relation-link,.weapon-row input,.weapon-row button').forEach(b=>b.disabled=value);}
function updateDraft(){
  const c=changes(),count=c.add.length+c.remove.length,has=!!state.station;
  $('draft-status').textContent=state.busy?'WORKING':count?'DRAFT':'SYNCED';
  $('draft-status').classList.toggle('dirty',count>0);
  $('change-count').textContent=count?`${count} pending ${count===1?'change':'changes'}`:'No pending changes';
  $('change-detail').textContent=count?`${c.add.length} to enable · ${c.remove.length} to remove`:'Changes are saved only after review.';
  $('enabled-tab-count').textContent=state.selected.size;
  $('pending-tab-count').textContent=count;
  $('review').disabled=!has||!count||state.busy;
  $('discard').disabled=!count||state.busy;
  $('backups').disabled=!has||state.busy;
}
function platformList(){
  const term=$('platform-search').value.toLowerCase();
  const list=state.data.platforms.filter(p=>`${p.display_name} ${p.name} ${categorySearch(p.categories,'platform')}`.toLowerCase().includes(term)&&matchesCategories(p.categories,'platform'));
  $('platform-match').textContent=list.length;
  $('platform-list').replaceChildren();
  list.forEach((p,i)=>{
    const b=el('button',`platform-item ${p===state.platform?'active':''}`);b.disabled=state.busy;b.setAttribute('aria-pressed',String(p===state.platform));
    b.append(el('span','platform-symbol',String(state.data.platforms.indexOf(p)+1).padStart(2,'0')));
    const copy=el('span','platform-copy');copy.append(el('strong','',p.display_name),el('small','',`${p.name} · ${p.stations.length} stations`),categoryBadges(p.categories,'platform'));b.append(copy);
    b.addEventListener('click',()=>selectPlatform(p));$('platform-list').append(b);
  });
  if(!list.length)$('platform-list').append(el('p','empty','No matching platforms.'));
}
function stationList(){
  $('platform-name').textContent=state.platform.display_name;
  $('platform-id').textContent=state.platform.name;
  $('platform-owner').textContent=state.platform.stations[0]?.owner||'';
  $('platform-tags').replaceChildren(categoryBadges(state.platform.categories,'platform'));
  $('station-count').textContent=state.platform.stations.length;
  $('station-list').replaceChildren();
  state.platform.stations.forEach(s=>{
    const b=el('button',`station-item ${state.station?.index===s.index?'active':''}`);b.disabled=state.busy;
    b.setAttribute('aria-pressed',String(state.station?.index===s.index));
    b.append(el('span','station-index',String(s.index).padStart(2,'0')));
    const copy=el('span','station-copy');copy.append(el('strong','',s.name),el('small','',s.ready?`${s.hardpoints} hardpoint${s.hardpoints===1?'':'s'} · ${s.allowed_count} allowed`:'Station file missing / ambiguous'));
    b.append(copy,el('span','station-dot'));b.addEventListener('click',()=>selectStation(s.index));$('station-list').append(b);
  });
  platformMap();
}
function relationships(){
  const s=state.station,container=$('relationships');container.replaceChildren();
  container.append(el('p','subtle',`${s.hardpoints} hardpoint${s.hardpoints===1?'':'s'}`));
  const pairs=state.platform.stations.filter(t=>t.index!==s.index&&s.symmetry&&t.symmetry===s.symmetry);
  container.append(el('p','relation-label',s.symmetry?`Symmetry group: ${s.symmetry}`:'Symmetry group: none'));
  pairs.forEach(t=>relation(t,'Grouped'));
  container.append(el('p','relation-label',s.precluding.length?'Precludes':'Precludes: none'));
  s.precluding.forEach(index=>{const t=state.platform.stations.find(t=>t.index===index);if(t)relation(t,'Precludes');else container.append(el('p','subtle',`Station ${index}`));});
  function relation(t, type){const b=el('button','relation-link',`${String(t.index).padStart(2,'0')} / ${t.name}`);b.title=`${type}: station ${t.index}`;b.addEventListener('click',()=>selectStation(t.index));container.append(b);}
}
function mountRows(){
  const term=$('weapon-search').value.toLowerCase(),owner=$('owner-filter').value,c=changes();
  const pending=new Set(state.rows.filter(w=>state.base.has(w.id)!==state.selected.has(w.id)).map(w=>w.id));
  const rows=state.rows.filter(w=>(!owner||w.owner===owner)&&matchesCategories(w.categories,'weapon')&&`${w.name} ${w.key} ${w.asset||''} ${w.owner} ${w.note||''} ${categorySearch(w.categories,'weapon')}`.toLowerCase().includes(term)&&
    (state.filter==='all'||state.filter==='enabled'&&state.selected.has(w.id)||state.filter==='pending'&&pending.has(w.id)));
  const list=$('weapon-list'),scroll=list.scrollTop,focused=document.activeElement?.dataset?.mountId;list.replaceChildren();
  $('result-count').textContent=`${rows.length} shown`;
  rows.forEach(w=>{
    const enabled=state.selected.has(w.id),changed=pending.has(w.id);
    const row=el('div',`weapon-row ${enabled?'enabled':''} ${changed?'pending':''}`),toggle=el('label','weapon-toggle');
    const input=el('input');input.type='checkbox';input.checked=enabled;input.disabled=state.busy;input.dataset.mountId=w.id;input.setAttribute('aria-label',`Allow ${w.name} (${w.key})`);
    input.addEventListener('change',()=>{if(input.checked)state.selected.add(w.id);else state.selected.delete(w.id);state.ticket=null;updateDraft();mountRows();});
    const copy=el('span','weapon-copy'),name=el('span','weapon-name',w.name);
    if(w.note||w.unknown){const badge=el('span','note-badge',w.unknown?'UNRESOLVED':w.stale?'STALE-KEY':'CHECK');badge.title=w.note||'Existing key is absent from the current dictionary. Retained until explicitly removed.';name.append(badge);}
    if(changed)name.append(el('span','pending-mark',enabled?'+ ENABLE':'− REMOVE'));
    copy.append(name,el('span','weapon-key',w.key),categoryBadges(w.categories,'weapon'));
    const meta=el('span','weapon-meta');meta.append(el('span','weapon-owner',w.owner),el('span','weapon-ammo',w.unknown?'Existing entry':`${w.ammo} ammo`));
    if(!w.unknown){const edit=el('button','text-button category-edit','Edit tags');edit.disabled=state.busy;edit.setAttribute('aria-label',`Edit categories for ${w.name} (${w.key})`);edit.addEventListener('click',()=>openCategories('weapon',w.key));meta.append(edit);}
    toggle.append(input,copy);row.append(toggle,meta);list.append(row);
  });
  if(!rows.length)list.append(el('p','empty','No mounts match this view. Try changing your search or filters.'));
  list.scrollTop=scroll;
  if(focused){const next=[...list.querySelectorAll('input')].find(n=>n.dataset.mountId===focused);if(next)next.focus({preventScroll:true});}
}
function applyStation(s){
  state.station=s;state.ticket=null;state.restore=null;state.keyRows=new Map();
  state.rows=state.data.weapons.map(w=>({...w,id:`w:${w.key}`}));
  const exact=new Map(state.rows.map(w=>[w.key,w]));
  const assets=new Map();state.rows.forEach(w=>{const rows=assets.get(w.asset)||[];rows.push(w);assets.set(w.asset,rows);});
  const enabled=new Set();
  s.allowed.forEach(key=>{
    let w=exact.get(key);if(!w&&assets.get(key)?.length===1)w=assets.get(key)[0];
    if(!w){w={id:`u:${key}`,key,name:key,owner:'Unresolved',ammo:0,unknown:true};if(!state.rows.some(r=>r.id===w.id))state.rows.unshift(w);}
    enabled.add(w.id);state.keyRows.set(key,w.id);
  });
  state.base=enabled;state.selected=new Set(enabled);
  $('station-kicker').textContent=`${state.platform.name} / STATION ${String(s.index).padStart(2,'0')}`;
  $('station-name').textContent=s.name;
  $('station-subtitle').textContent=`${s.hardpoints} hardpoint${s.hardpoints===1?'':'s'} · ${s.allowed.length} enabled mounts on disk`;
  $('footer-status').textContent='Station connected';
  $('weapon-list').scrollTop=0;stationList();relationships();updateDraft();mountRows();
}
async function selectPlatform(p){
  if(state.busy||!mayLeave())return;
  setBusy(true);notice('');
  const previous=state.platform;
  try{
    const ready=p.stations.find(s=>s.ready);if(!ready)throw new Error('No station file is ready for this platform. Check the parser output.');
    const s=await api(`/api/platforms/${encodeURIComponent(p.name)}/stations/${ready.index}`);
    state.platform=p;applyStation(s);platformList();
  }catch(e){state.platform=previous;notice(e.message,'error');}
  finally{setBusy(false);mountRows();}
}
async function selectStation(index){
  if(state.busy||index===state.station?.index||!mayLeave())return;
  setBusy(true);notice('');
  try{applyStation(await api(`/api/platforms/${encodeURIComponent(state.platform.name)}/stations/${index}`));}
  catch(e){notice(e.message,'error');}
  finally{setBusy(false);mountRows();}
}
async function loadData(){
  if(state.busy||!mayLeave())return;
  setBusy(true);
  try{
    const data=await api('/api/bootstrap');
    state.data=data;state.platform=null;state.station=null;state.rows=[];state.selected=new Set();state.base=new Set();
    applyTheme(activeTheme(data.themes));
    initCategoryFilters();
    $('platform-total').textContent=data.platforms.length;
    $('station-total').textContent=data.platforms.reduce((n,p)=>n+p.stations.length,0);
    $('mount-total').textContent=data.weapons.length;$('preset-total').textContent=data.presets;$('schema').textContent=`Schema ${data.schema||'unknown'}`;
    const owners=[...new Set(data.weapons.map(w=>w.owner))].sort();$('owner-filter').replaceChildren(new Option('All owners',''),...owners.map(o=>new Option(o,o)));
    platformList();setBusy(false);
    await selectPlatform(data.platforms.find(p=>p.name==='CAS1')||data.platforms[0]);
    if(data.issues.length)notice(`${data.issues.length} validation issue(s): ${data.issues[0].message} Run test_parser.py for the full report.`,'warn');
  }catch(e){notice(e.message,'error');$('footer-status').textContent='Connection error';}
  finally{setBusy(false);}
}
function reviewRows(added,removed,restore){
  const list=$('review-changes');list.replaceChildren();
  if(restore)list.append(el('p','review-change',`Restore ${restore}`));
  removed.forEach(k=>list.append(el('p','review-change remove',`− ${k}`)));
  added.forEach(k=>list.append(el('p','review-change add',`+ ${k}`)));
  if(!added.length&&!removed.length&&!restore)list.append(el('p','review-change','No whitelist differences.'));
}
async function preparePreview(){
  $('confirm-save').disabled=true;state.ticket=null;$('review-error').classList.add('hidden');
  if(!state.restore&&!state.selected.size&&state.base.size&&!$('allow-empty').checked)return;
  setBusy(true);
  try{
    const body=state.restore?{revision:state.station.revision,restore:state.restore}:{revision:state.station.revision,...changes(),allow_empty:$('allow-empty').checked};
    const p=await api(url('/preview'),body);state.ticket=p.ticket;
    $('review-summary').textContent=`${state.platform.display_name} (${state.platform.name}) / ${state.station.name} · ${p.before_count} → ${p.after_count} mounts`;
    reviewRows(p.added,p.removed,state.restore);
    $('confirm-save').textContent=state.restore?'Restore station':'Save station';$('confirm-save').disabled=false;
  }catch(e){$('review-error').textContent=e.message;$('review-error').classList.remove('hidden');}
  finally{setBusy(false);}
}
async function openReview(restore=null){
  if(state.busy||!state.station)return;
  state.restore=restore;state.ticket=null;
  $('review-title').textContent=restore?'Review backup restoration':'Review station changes';
  $('review-summary').textContent=`${state.platform.display_name} (${state.platform.name}) / ${state.station.name}`;
  $('review-error').classList.add('hidden');$('allow-empty').checked=false;
  const empty=!restore&&!state.selected.size&&state.base.size;
  $('empty-consent').classList.toggle('hidden',!empty);
  const c=changes();reviewRows(c.add,c.remove,restore);$('confirm-save').disabled=true;
  $('review-dialog').showModal();await preparePreview();
}
function closeReview(){if(state.busy)return;$('review-dialog').close();state.ticket=null;state.restore=null;}
async function save(){
  if(state.busy||!state.ticket)return;
  setBusy(true);$('confirm-save').disabled=true;
  const ticket=state.ticket;state.ticket=null;
  try{
    const r=await api('/api/commit',{ticket});
    $('review-dialog').close();applyStation(r.station);
    const meta=state.platform.stations.find(s=>s.index===r.station.index);if(meta)meta.allowed_count=r.station.allowed.length;stationList();
    notice(r.changed?`Saved and verified. Backup: ${r.backup}`:'Station already matches. No files changed.');
  }catch(e){$('review-error').textContent=`${e.message} Close this review, then reload data or review again.`;$('review-error').classList.remove('hidden');notice(e.status===409?'Station changed outside ALIS. Your draft remains available; reload data to use the current file.':e.message,'error');}
  finally{setBusy(false);mountRows();}
}
async function showBackups(){
  if(state.busy||!state.station)return;
  setBusy(true);
  try{
    const s=await api(url());$('backup-list').replaceChildren();
    s.backups.forEach(b=>{
      const row=el('div','backup-row'),copy=el('div');copy.append(el('strong','',new Date(b.modified*1000).toLocaleString()),el('small','',b.name));
      const button=el('button','quiet','Review restore');button.addEventListener('click',()=>{$('backup-dialog').close();openReview(b.name);});row.append(copy,button);$('backup-list').append(row);
    });
    if(!s.backups.length)$('backup-list').append(el('p','empty','No backups yet. ALIS creates one whenever it saves a change.'));
    $('backup-dialog').showModal();
  }catch(e){notice(e.message,'error');}
  finally{setBusy(false);}
}
$('platform-search').addEventListener('input',()=>{if(state.data)platformList();});
$('weapon-search').addEventListener('input',mountRows);$('owner-filter').addEventListener('change',mountRows);
document.querySelectorAll('[data-filter]').forEach(b=>b.addEventListener('click',()=>{state.filter=b.dataset.filter;document.querySelectorAll('[data-filter]').forEach(t=>{t.classList.toggle('active',t===b);t.setAttribute('aria-pressed',String(t===b));});mountRows();}));
$('reload-all').addEventListener('click',loadData);
$('source-path').addEventListener('click',()=>notice(state.data?`Connected folder: ${state.data.root}`:'No folder connected.'));
$('discard').addEventListener('click',()=>{state.selected=new Set(state.base);state.ticket=null;notice('');updateDraft();mountRows();});
$('review').addEventListener('click',()=>openReview());$('confirm-save').addEventListener('click',save);
$('allow-empty').addEventListener('change',preparePreview);
$('close-review').addEventListener('click',closeReview);$('cancel-review').addEventListener('click',closeReview);
$('review-dialog').addEventListener('cancel',e=>{if(state.busy)e.preventDefault();else{state.ticket=null;state.restore=null;}});
$('backups').addEventListener('click',showBackups);
$('close-backups').addEventListener('click',()=>$('backup-dialog').close());$('done-backups').addEventListener('click',()=>$('backup-dialog').close());
window.addEventListener('beforeunload',e=>{if(dirty()||layoutDirty()||themeDirty()||presetDirty()||categoryDirty()){e.preventDefault();e.returnValue='';}});

// Native SVG keeps marker coordinates independent of the window size.
function svgEl(tag, attrs={}, text){
  const n=document.createElementNS('http://www.w3.org/2000/svg',tag);
  Object.entries(attrs).forEach(([key,value])=>n.setAttribute(key,String(value)));
  if(text!==undefined)n.textContent=text;return n;
}
function drawMap(canvas, profile, editable=false){
  canvas.replaceChildren(svgEl('image',{href:profile.image||`/static/silhouettes/${profile.silhouette}.svg`,width:1000,height:1000,preserveAspectRatio:'xMidYMid meet'}));
  const selected=state.station, current=editable?state.layout.station:String(selected?.index);
  state.platform.stations.forEach(s=>{
    const points=profile.stations[String(s.index)]?.points||[];
    points.forEach((point,i)=>{
      const active=String(s.index)===current&&(!editable||i===state.layout.point);
      const grouped=!editable&&selected?.symmetry&&s.index!==selected.index&&s.symmetry===selected.symmetry;
      const precluded=!editable&&selected?.precluding.includes(s.index);
      const g=svgEl('g',{class:`map-marker ${active?'selected':''} ${grouped?'grouped':''} ${precluded?'precluded':''}`,transform:`translate(${point[0]*1000} ${point[1]*1000})`,'data-station':s.index,'data-point':i,role:'button',tabindex:0,'aria-label':`Station ${s.index}: ${s.name}, marker ${i+1}`,'aria-pressed':active});
      g.append(svgEl('title',{},`${s.name} · station ${s.index}${points.length>1?` · marker ${i+1}/${points.length}`:''}`),svgEl('circle',{r:30}),svgEl('text',{'text-anchor':'middle',dy:10},String(s.index).padStart(2,'0')));
      const activate=()=>{if(editable){if(state.layout?.busy)return;state.layout.station=String(s.index);state.layout.point=i;editorFields();editorMap();}else selectStation(s.index);};
      if(!editable)g.addEventListener('click',activate);
      g.addEventListener('keydown',e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();activate();}});
      canvas.append(g);
    });
  });
}
function platformMap(){
  const p=state.platform.profile;drawMap($('platform-map'),p);
  const count=state.platform.stations.length-p.unmapped.length;
  $('layout-status').textContent=p.verified?'USER CHECKED':count?'SCHEMATIC / APPROXIMATE':'UNMAPPED';
  $('layout-status').classList.toggle('verified',p.verified);
  let note=p.verified?'Layout checked by you against your reference.':'Marker positions are schematic. Use Edit layout to match your reference.';
  if(!count)note='No spatial layout yet. Select a station below, or map it with Edit layout.';
  if(p.unmapped.length&&count)note+=` ${p.unmapped.length} unmapped station(s) remain in the list.`;
  if(p.stale)note+=' Station metadata changed; outdated markers were removed.';
  $('layout-note').textContent=note;
}
function profileDraft(p){return {display_name:p.display_name,silhouette:p.silhouette,verified:p.verified,image:p.image,stations:JSON.parse(JSON.stringify(p.stations))};}
function layoutDirty(){return !!state.layout&&JSON.stringify(state.layout.draft)!==state.layout.base;}
function layoutError(message=''){$('layout-error').textContent=message;$('layout-error').classList.toggle('hidden',!message);}
function unverify(){state.layout.draft.verified=false;$('layout-verified').checked=false;}
function openLayout(){
  if(state.busy||state.layout||!state.platform)return;
  const draft=profileDraft(state.platform.profile);
  state.layout={draft,base:JSON.stringify(draft),station:String(state.station?.index??state.platform.stations[0].index),point:0,revision:state.data.profiles_revision,busy:false};
  $('layout-name').value=draft.display_name;$('layout-shape').value=draft.silhouette;$('layout-verified').checked=draft.verified;$('layout-image').value='';
  $('layout-station').replaceChildren(...state.platform.stations.map(s=>new Option(`${String(s.index).padStart(2,'0')} / ${s.name}`,String(s.index))));
  layoutError();layoutBusy(false);editorFields();editorMap();$('layout-dialog').showModal();
}
function closeLayout(){
  if(!state.layout||state.layout.busy)return;
  if(layoutDirty()&&!window.confirm('Discard the unsaved layout settings?'))return;
  $('layout-dialog').close();state.layout=null;layoutDrag=null;
}
function editorFields(){
  const l=state.layout;if(!l)return;
  $('layout-station').value=l.station;
  const points=l.draft.stations[l.station]?.points||[];l.point=Math.max(0,Math.min(l.point,points.length-1));
  $('layout-point').replaceChildren(...points.map((_,i)=>new Option(`Marker ${i+1} of ${points.length}`,String(i))));
  if(!points.length)$('layout-point').append(new Option('No marker — add one',''));
  $('layout-point').value=points.length?String(l.point):'';
  const p=points[l.point];$('layout-x').value=p?Math.round(p[0]*1000)/10:'';$('layout-y').value=p?Math.round(p[1]*1000)/10:'';
  ['layout-x','layout-y','layout-point','remove-marker'].forEach(id=>$(id).disabled=l.busy||!p);
  $('add-marker').disabled=l.busy||points.length>=16;
  $('remove-image').disabled=l.busy||!l.draft.image;
  $('layout-shape').disabled=l.busy||!!l.draft.image;
  $('layout-image-status').textContent=l.draft.image?'Custom image attached':'Built-in silhouette';
  const mapped=Object.keys(l.draft.stations).length;
  $('layout-coverage').textContent=`${mapped} / ${state.platform.stations.length} stations mapped · nose / front at top`;
}
function editorMap(){if(state.layout)drawMap($('layout-canvas'),state.layout.draft,true);}
function layoutBusy(value){
  if(!state.layout)return;state.layout.busy=value;
  $('layout-dialog').querySelectorAll('input,select,button').forEach(n=>n.disabled=value);
  $('save-layout').textContent=value?'Saving…':'Save layout';editorFields();
}
function placePoint(x,y){
  const l=state.layout;if(!l||l.busy)return;
  const points=l.draft.stations[l.station]?.points;if(!points?.[l.point])return;
  points[l.point]=[x,y].map(v=>Math.round(Math.max(0,Math.min(1,v))*10000)/10000);
  unverify();layoutError();editorFields();editorMap();
}
function canvasPosition(event){
  const matrix=$('layout-canvas').getScreenCTM();if(!matrix)return null;
  const point=$('layout-canvas').createSVGPoint();point.x=event.clientX;point.y=event.clientY;
  const local=point.matrixTransform(matrix.inverse());return [local.x/1000,local.y/1000];
}
let layoutDrag=null;
$('layout-canvas').addEventListener('pointerdown',e=>{
  if(!state.layout||state.layout.busy||e.button!==0)return;
  const marker=e.target.closest('.map-marker');
  if(marker){state.layout.station=marker.dataset.station;state.layout.point=Number(marker.dataset.point);editorFields();editorMap();}
  const position=canvasPosition(e);if(!position)return;
  if(!state.layout.draft.stations[state.layout.station]?.points.length){layoutError('Add a marker for this station first.');return;}
  e.preventDefault();layoutDrag=e.pointerId;$('layout-canvas').setPointerCapture(e.pointerId);
  // Clicking a marker selects it without changing its coordinates.
  if(!marker)placePoint(...position);
});
$('layout-canvas').addEventListener('pointermove',e=>{if(layoutDrag===e.pointerId){const position=canvasPosition(e);if(position)placePoint(...position);}});
function endLayoutDrag(e){if(layoutDrag===e.pointerId){layoutDrag=null;if($('layout-canvas').hasPointerCapture(e.pointerId))$('layout-canvas').releasePointerCapture(e.pointerId);}}
$('layout-canvas').addEventListener('pointerup',endLayoutDrag);$('layout-canvas').addEventListener('pointercancel',endLayoutDrag);
$('layout-canvas').addEventListener('lostpointercapture',()=>{layoutDrag=null;});
$('layout-name').addEventListener('input',()=>{if(state.layout)state.layout.draft.display_name=$('layout-name').value;});
$('layout-shape').addEventListener('change',()=>{state.layout.draft.silhouette=$('layout-shape').value;unverify();editorMap();});
$('layout-verified').addEventListener('change',()=>{state.layout.draft.verified=$('layout-verified').checked;});
$('layout-station').addEventListener('change',()=>{state.layout.station=$('layout-station').value;state.layout.point=0;editorFields();editorMap();});
$('layout-point').addEventListener('change',()=>{state.layout.point=Number($('layout-point').value);editorFields();editorMap();});
['layout-x','layout-y'].forEach(id=>$(id).addEventListener('change',()=>{
  const x=$('layout-x').valueAsNumber,y=$('layout-y').valueAsNumber;
  if(!Number.isFinite(x)||!Number.isFinite(y)||x<0||x>100||y<0||y>100){layoutError('X and Y must be between 0 and 100%.');return;}
  placePoint(x/100,y/100);
}));
$('add-marker').addEventListener('click',()=>{
  const l=state.layout,s=state.platform.stations.find(s=>String(s.index)===l.station);
  const marker=l.draft.stations[l.station]||{expected_name:s.name,points:[]};if(marker.points.length>=16)return;
  marker.points.push([0.5,0.5]);l.draft.stations[l.station]=marker;l.point=marker.points.length-1;unverify();editorFields();editorMap();
});
$('remove-marker').addEventListener('click',()=>{
  const l=state.layout,marker=l.draft.stations[l.station];if(!marker)return;
  marker.points.splice(l.point,1);if(!marker.points.length)delete l.draft.stations[l.station];unverify();editorFields();editorMap();
});
$('remove-image').addEventListener('click',()=>{state.layout.draft.image=null;$('layout-image').value='';unverify();editorFields();editorMap();});
$('layout-image').addEventListener('change',async()=>{
  const l=state.layout,file=$('layout-image').files[0];if(!l||!file)return;
  if(!['image/png','image/jpeg','image/webp'].includes(file.type)||file.size>2*1024*1024){layoutError('Choose a PNG, JPEG or WebP image up to 2 MiB.');$('layout-image').value='';return;}
  layoutBusy(true);layoutError();
  try{
    const data=await new Promise((resolve,reject)=>{const reader=new FileReader();reader.onload=()=>resolve(reader.result);reader.onerror=()=>reject(new Error('Image could not be read.'));reader.readAsDataURL(file);});
    await new Promise((resolve,reject)=>{const image=new Image();image.onload=resolve;image.onerror=()=>reject(new Error('Image could not be decoded.'));image.src=data;});
    l.draft.image=data;unverify();editorMap();
  }catch(e){layoutError(e.message);}finally{layoutBusy(false);}
});
async function saveLayout(){
  const l=state.layout;if(!l||l.busy)return;
  if(!$('layout-name').reportValidity())return;
  if((!$('layout-x').disabled&&!$('layout-x').checkValidity())||(!$('layout-y').disabled&&!$('layout-y').checkValidity())){layoutError('X and Y must be between 0 and 100%.');return;}
  layoutBusy(true);layoutError();
  try{
    const result=await api(`/api/platforms/${encodeURIComponent(state.platform.name)}/profile`,{revision:l.revision,profile:l.draft});
    state.platform.profile=result.profile;state.platform.display_name=result.profile.display_name;state.data.profiles_revision=result.revision;
    $('layout-dialog').close();state.layout=null;layoutDrag=null;stationList();platformList();
    notice(`Layout saved for ${state.platform.display_name}. Weapon whitelists are unchanged.`);
  }catch(e){layoutError(e.status===409?`${e.message} Your layout draft is still here. Close this editor and reload data to use the current settings.`:e.message);layoutBusy(false);}
}
$('edit-layout').addEventListener('click',openLayout);
$('save-layout').addEventListener('click',saveLayout);
$('close-layout').addEventListener('click',closeLayout);$('cancel-layout').addEventListener('click',closeLayout);
$('layout-dialog').addEventListener('cancel',e=>{e.preventDefault();closeLayout();});
// extras.js starts the application after registering the theme/preset controls.
