'use strict';
const $ = id => document.getElementById(id);
const state = {data:null,platform:null,station:null,rows:[],selected:new Set(),base:new Set(),keyRows:new Map(),filter:'all',busy:false,ticket:null,restore:null};
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
function setBusy(value){state.busy=value;updateDraft();$('reload-all').disabled=value;$('allow-empty').disabled=value;document.querySelectorAll('.platform-item,.station-item,.relation-link,.weapon-row input').forEach(b=>b.disabled=value);}
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
  const list=state.data.platforms.filter(p=>p.name.toLowerCase().includes(term));
  $('platform-match').textContent=list.length;
  $('platform-list').replaceChildren();
  list.forEach((p,i)=>{
    const b=el('button',`platform-item ${p===state.platform?'active':''}`);b.disabled=state.busy;b.setAttribute('aria-pressed',String(p===state.platform));
    b.append(el('span','platform-symbol',String(state.data.platforms.indexOf(p)+1).padStart(2,'0')));
    const copy=el('span','platform-copy');copy.append(el('strong','',p.name),el('small','',`${p.stations.length} stations`));b.append(copy);
    b.addEventListener('click',()=>selectPlatform(p));$('platform-list').append(b);
  });
  if(!list.length)$('platform-list').append(el('p','empty','No matching platforms.'));
}
function stationList(){
  $('platform-name').textContent=state.platform.name;
  $('platform-owner').textContent=state.platform.stations[0]?.owner||'';
  $('station-count').textContent=state.platform.stations.length;
  $('station-list').replaceChildren();
  state.platform.stations.forEach(s=>{
    const b=el('button',`station-item ${state.station?.index===s.index?'active':''}`);b.disabled=state.busy;
    b.setAttribute('aria-pressed',String(state.station?.index===s.index));
    b.append(el('span','station-index',String(s.index).padStart(2,'0')));
    const copy=el('span','station-copy');copy.append(el('strong','',s.name),el('small','',s.ready?`${s.hardpoints} hardpoint${s.hardpoints===1?'':'s'} · ${s.allowed_count} allowed`:'Station file missing / ambiguous'));
    b.append(copy,el('span','station-dot'));b.addEventListener('click',()=>selectStation(s.index));$('station-list').append(b);
  });
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
  const rows=state.rows.filter(w=>(!owner||w.owner===owner)&&`${w.name} ${w.key} ${w.asset||''} ${w.owner} ${w.note||''}`.toLowerCase().includes(term)&&
    (state.filter==='all'||state.filter==='enabled'&&state.selected.has(w.id)||state.filter==='pending'&&pending.has(w.id)));
  const list=$('weapon-list'),scroll=list.scrollTop,focused=document.activeElement?.dataset?.mountId;list.replaceChildren();
  $('result-count').textContent=`${rows.length} shown`;
  rows.forEach(w=>{
    const enabled=state.selected.has(w.id),changed=pending.has(w.id);
    const row=el('label',`weapon-row ${enabled?'enabled':''} ${changed?'pending':''}`);
    const input=el('input');input.type='checkbox';input.checked=enabled;input.disabled=state.busy;input.dataset.mountId=w.id;input.setAttribute('aria-label',`Allow ${w.name} (${w.key})`);
    input.addEventListener('change',()=>{if(input.checked)state.selected.add(w.id);else state.selected.delete(w.id);state.ticket=null;updateDraft();mountRows();});
    const copy=el('span','weapon-copy'),name=el('span','weapon-name',w.name);
    if(w.note||w.unknown){const badge=el('span','note-badge',w.unknown?'UNRESOLVED':w.stale?'STALE-KEY':'CHECK');badge.title=w.note||'Existing key is absent from the current dictionary. Retained until explicitly removed.';name.append(badge);}
    if(changed)name.append(el('span','pending-mark',enabled?'+ ENABLE':'− REMOVE'));
    copy.append(name,el('span','weapon-key',w.key));
    const meta=el('span','weapon-meta');meta.append(el('span','weapon-owner',w.owner),el('span','weapon-ammo',w.unknown?'Existing entry':`${w.ammo} ammo`));
    row.append(input,copy,meta);list.append(row);
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
    $('review-summary').textContent=`${state.platform.name} / ${state.station.name} · ${p.before_count} → ${p.after_count} mounts`;
    reviewRows(p.added,p.removed,state.restore);
    $('confirm-save').textContent=state.restore?'Restore station':'Save station';$('confirm-save').disabled=false;
  }catch(e){$('review-error').textContent=e.message;$('review-error').classList.remove('hidden');}
  finally{setBusy(false);}
}
async function openReview(restore=null){
  if(state.busy||!state.station)return;
  state.restore=restore;state.ticket=null;
  $('review-title').textContent=restore?'Review backup restoration':'Review station changes';
  $('review-summary').textContent=`${state.platform.name} / ${state.station.name}`;
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
window.addEventListener('beforeunload',e=>{if(dirty()){e.preventDefault();e.returnValue='';}});
loadData();
